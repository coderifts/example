"""
Shared CodeRifts control-flow gate — Python.

Every variant in this directory imports `gate()` from here. There is one
implementation of the rule, not five.

Control-flow contract (app.coderifts.com/.well-known/coderifts.json)
--------------------------------------------------------------------
    branch_on                      = execution_action
    execution_action               = [CONTINUE, CONTINUE_WITH_MONITORING,
                                      REQUEST_APPROVAL, STOP]
    unrecognised_execution_action  = not_permission_fail_closed
    continue_with_monitoring_requires = monitoringSinkWired
    safe_for_agent                 = not_for_control_flow_use_execution_action

Branch on `execution_action`. Never on `decision`. Never on `safe_for_agent` —
the well-known says so in those words.

Everything that is not an explicit permission is a halt:

  * a present but unrecognised action halts (it is not a missing action, and it
    must never fall back to `decision` — that is how you reinvent permission),
  * an absent action falls back to the legacy decision map and is then held to
    the same closed-set rules,
  * an unreadable verdict halts,
  * a transport failure halts. This module never returns "proceed" because a
    request failed.

Standard library only.
"""

import json
import urllib.error
import urllib.request

# Zero-auth synchronous diff endpoint. This is the endpoint that returns a
# verdict you can gate on.
#
# NOTE: GET /api/v1/public/preflight is *analyze-only* — it answers "does this
# single spec look hallucinated / low quality", and its own scope_note says
# "Keyless public demo is analyze-only (no authorize / receipts)". It returns
# authorization_effect="NONE" and may_execute=false and carries no
# execution_action. It cannot be used as an execution gate. Do not point a
# guard at it.
CODERIFTS_DEMO_URL = "https://app.coderifts.com/api/v1/demo"

CLOSED_EXECUTION_ACTIONS = frozenset({
    "CONTINUE",
    "CONTINUE_WITH_MONITORING",
    "REQUEST_APPROVAL",
    "STOP",
})

# Applied ONLY when execution_action is absent — never when it is present but
# unrecognised.
_DECISION_TO_ACTION = {
    "ALLOW": "CONTINUE",
    "WARN": "CONTINUE_WITH_MONITORING",
    "REQUIRE_APPROVAL": "REQUEST_APPROVAL",
    "BLOCK": "STOP",
}


class Halt(Exception):
    """Raised to stop the agent before an unsafe call."""

    def __init__(self, reason, execution_action=None, decision=None):
        self.reason = reason
        self.execution_action = execution_action
        self.decision = decision  # diagnostic only
        super().__init__(
            "CodeRifts halt (%s) execution_action=%r decision=%r(diagnostic)"
            % (reason, execution_action, decision)
        )


def _decision(verdict):
    """Diagnostic only. Not the control-flow field."""
    if not isinstance(verdict, dict):
        return "UNKNOWN"
    env = verdict.get("decision_result")
    if isinstance(env, dict) and isinstance(env.get("decision"), str):
        return env["decision"]
    return verdict.get("omega_decision") or verdict.get("decision") or "UNKNOWN"


def _raw_execution_action(verdict):
    """Return (value, source); (None, 'missing') when absent or empty."""
    if not isinstance(verdict, dict):
        return None, "missing"
    env = verdict.get("decision_result")
    if isinstance(env, dict) and "execution_action" in env:
        v = env.get("execution_action")
        if v is not None and v != "":
            return v, "envelope"
    if "execution_action" in verdict:
        v = verdict.get("execution_action")
        if v is not None and v != "":
            return v, "top_level"
    return None, "missing"


def evaluate(verdict, monitoring_sink_wired=False):
    """
    Pure, offline control-flow evaluation. No network.

    Returns {halt, reason, execution_action, decision, action_source}.
    """
    decision = _decision(verdict)
    raw, source = _raw_execution_action(verdict)

    if raw is not None:
        if not isinstance(raw, str) or raw not in CLOSED_EXECUTION_ACTIONS:
            return {
                "halt": True,
                "reason": "EXECUTION_ACTION_UNRECOGNISED",
                "execution_action": raw if isinstance(raw, str) else None,
                "decision": decision,
                "action_source": source,
            }
        action, action_source = raw, source
    else:
        action = _DECISION_TO_ACTION.get(decision)
        action_source = "legacy_decision_map"
        if action is None:
            return {
                "halt": True,
                "reason": "UNREADABLE_DECISION",
                "execution_action": None,
                "decision": decision,
                "action_source": "missing",
            }

    if action == "STOP":
        halt, reason = True, "STOP"
    elif action == "REQUEST_APPROVAL":
        # Approval is not optional. There is no strict= flag that relaxes this.
        halt, reason = True, "REQUEST_APPROVAL"
    elif action == "CONTINUE_WITH_MONITORING":
        halt = not monitoring_sink_wired
        reason = "CONTINUE_WITH_MONITORING" if monitoring_sink_wired else "MONITORING_UNWIRED"
    else:  # CONTINUE
        halt, reason = False, "CONTINUE"

    return {
        "halt": halt,
        "reason": reason,
        "execution_action": action,
        "decision": decision,
        "action_source": action_source,
    }


def fetch_verdict(old_spec, new_spec, timeout=20):
    """POST the before/after contract to the zero-auth endpoint."""
    payload = json.dumps({"old_spec": old_spec, "new_spec": new_spec}).encode()
    req = urllib.request.Request(
        CODERIFTS_DEMO_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def gate(old_spec, new_spec, monitoring_sink_wired=False, timeout=20):
    """
    Fetch a verdict and evaluate it. Returns the evaluation dict.

    Any transport, HTTP or decode failure is a halt with reason
    TRANSPORT_FAILURE — a guard that cannot reach its authority has not been
    granted anything.
    """
    try:
        verdict = fetch_verdict(old_spec, new_spec, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - deliberate: any failure is a halt
        # Broad on purpose. Narrowing this to a known exception tuple means an
        # unanticipated error escapes the gate instead of halting at it.
        return {
            "halt": True,
            "reason": "TRANSPORT_FAILURE",
            "execution_action": None,
            "decision": "UNKNOWN",
            "action_source": "missing",
            "error": "%s: %s" % (type(exc).__name__, exc),
        }
    return evaluate(verdict, monitoring_sink_wired=monitoring_sink_wired)


def log_line(tag, ev):
    """Uniform one-line trace used by every variant."""
    return (
        "[%s] execution_action=%r reason=%s source=%s decision=%r(diagnostic)"
        % (tag, ev.get("execution_action"), ev.get("reason"),
           ev.get("action_source"), ev.get("decision"))
    )
