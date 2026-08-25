#!/usr/bin/env python3
"""
Offline control-flow checks for coderifts_gate.py.

Standard library only. No network. No test framework.

    python3 test_gate.py
"""

import json
import sys
import urllib.error
import urllib.request

import coderifts_gate as g

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("ok  %s" % name)
    else:
        print("FAIL %s  %s" % (name, detail))
        FAILURES.append(name)


# Nothing in this file may touch the network.
def _no_network(*a, **k):
    raise AssertionError("test_gate.py must not call the network")


urllib.request.urlopen = _no_network


# ── the closed set is the published one ──────────────────────────────────────

def test_closed_set_matches_well_known():
    expected = {"CONTINUE", "CONTINUE_WITH_MONITORING", "REQUEST_APPROVAL", "STOP"}
    check("closed set matches /.well-known",
          set(g.CLOSED_EXECUTION_ACTIONS) == expected,
          repr(g.CLOSED_EXECUTION_ACTIONS))


# ── the four closed actions ──────────────────────────────────────────────────

def test_continue_proceeds():
    r = g.evaluate({"execution_action": "CONTINUE", "decision": "ALLOW"})
    check("CONTINUE proceeds", r["halt"] is False and r["reason"] == "CONTINUE", r)


def test_stop_halts():
    r = g.evaluate({"execution_action": "STOP", "decision": "BLOCK"})
    check("STOP halts", r["halt"] is True and r["reason"] == "STOP", r)


def test_request_approval_always_halts():
    # Approval is not optional, and no flag relaxes it.
    r = g.evaluate({"execution_action": "REQUEST_APPROVAL", "decision": "ALLOW"})
    check("REQUEST_APPROVAL halts even when decision says ALLOW",
          r["halt"] is True and r["reason"] == "REQUEST_APPROVAL", r)


def test_monitoring_requires_wired_sink():
    unwired = g.evaluate({"execution_action": "CONTINUE_WITH_MONITORING"})
    wired = g.evaluate({"execution_action": "CONTINUE_WITH_MONITORING"},
                       monitoring_sink_wired=True)
    check("CONTINUE_WITH_MONITORING halts without a sink",
          unwired["halt"] is True and unwired["reason"] == "MONITORING_UNWIRED", unwired)
    check("CONTINUE_WITH_MONITORING proceeds with a sink",
          wired["halt"] is False, wired)


# ── the two ways permission gets reinvented ──────────────────────────────────

def test_present_unknown_halts_and_never_falls_back_to_decision():
    # decision says ALLOW. If the unknown action fell through to the legacy map
    # this would proceed. It must not.
    r = g.evaluate({"execution_action": "PROBABLY_FINE", "decision": "ALLOW"})
    check("present-but-unknown halts",
          r["halt"] is True and r["reason"] == "EXECUTION_ACTION_UNRECOGNISED", r)
    check("present-but-unknown does not consult decision",
          r["action_source"] == "top_level", r)


def test_non_string_action_halts():
    for bad in (True, 1, {"a": 1}, ["CONTINUE"]):
        r = g.evaluate({"execution_action": bad, "decision": "ALLOW"})
        check("non-string action %r halts" % (bad,),
              r["halt"] is True and r["reason"] == "EXECUTION_ACTION_UNRECOGNISED", r)


# ── absent action: legacy map, then the same closed rules ────────────────────

def test_absent_uses_legacy_decision_map():
    r = g.evaluate({"decision": "BLOCK"})
    check("absent + BLOCK -> STOP",
          r["halt"] is True and r["execution_action"] == "STOP"
          and r["action_source"] == "legacy_decision_map", r)
    r = g.evaluate({"decision": "ALLOW"})
    check("absent + ALLOW -> CONTINUE", r["halt"] is False, r)


def test_omega_decision_is_read():
    # This is the shape POST /api/v1/demo actually returns today.
    r = g.evaluate({"omega_decision": "BLOCK", "should_block": True})
    check("omega_decision BLOCK -> STOP",
          r["halt"] is True and r["execution_action"] == "STOP", r)


def test_envelope_preferred_over_top_level():
    r = g.evaluate({"decision_result": {"execution_action": "STOP", "decision": "BLOCK"},
                    "execution_action": "CONTINUE"})
    check("envelope wins over top level",
          r["halt"] is True and r["action_source"] == "envelope", r)


# ── the regression that caused the original fail-open ────────────────────────

def test_analyze_only_response_halts():
    """
    The exact live payload the five predecessor examples received.

    GET /api/v1/public/preflight is analyze-only: no decision, no
    safe_for_agent, no execution_action. The old code compared
    decision['decision'] == 'BLOCK', got undefined/KeyError, and proceeded.
    Here it must halt.
    """
    analyze_only = {
        "preflight_mode": "analyze",
        "analysis_outcome": "NO_BREAK_DETECTED",
        "authorization_effect": "NONE",
        "may_execute": False,
        "receipt_kind": "NONE",
        "decision_spec_version": "2.0",
        "risk_score": 0,
    }
    r = g.evaluate(analyze_only)
    check("analyze-only response halts (no permission field present)",
          r["halt"] is True and r["reason"] == "UNREADABLE_DECISION", r)


def test_pending_response_halts():
    """The endpoint's other live shape: {'status': 'PENDING', ...}."""
    r = g.evaluate({"status": "PENDING", "message": "Analysis scheduled. Retry in 5 seconds."})
    check("PENDING response halts", r["halt"] is True, r)


def test_empty_and_garbage_halt():
    for bad in ({}, None, [], "BLOCK", 0):
        r = g.evaluate(bad)
        check("garbage verdict %r halts" % (bad,), r["halt"] is True, r)


def test_safe_for_agent_is_never_consulted():
    """
    safe_for_agent = not_for_control_flow_use_execution_action.

    A verdict that says safe_for_agent=True but carries STOP must still halt,
    and one that says safe_for_agent=False with CONTINUE must still proceed.
    """
    r = g.evaluate({"execution_action": "STOP", "safe_for_agent": True})
    check("safe_for_agent=True does not override STOP", r["halt"] is True, r)
    r = g.evaluate({"execution_action": "CONTINUE", "safe_for_agent": False})
    check("safe_for_agent=False does not override CONTINUE", r["halt"] is False, r)


# ── transport ────────────────────────────────────────────────────────────────

def test_transport_failure_halts():
    """gate() must never return proceed because the request failed."""
    real = g.fetch_verdict
    for exc in (urllib.error.URLError("down"),
                ValueError("not json"),
                OSError("socket"),
                RuntimeError("something nobody anticipated")):
        g.fetch_verdict = lambda *a, _e=exc, **k: (_ for _ in ()).throw(_e)
        r = g.gate({"a": 1}, {"a": 2})
        check("transport failure (%s) halts" % type(exc).__name__,
              r["halt"] is True and r["reason"] == "TRANSPORT_FAILURE", r)
    g.fetch_verdict = real


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
    print()
    if FAILURES:
        print("%d FAILED: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all checks passed")
