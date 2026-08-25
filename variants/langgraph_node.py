"""
CodeRifts enforcement as a LangGraph guard node.

Was: coderifts/example-langgraph.

The guard is a node; the routing decision is a conditional edge that reads
`execution_action`. On halt the graph routes to `abort` and the tool node is
never entered.

This file simulates the graph so it runs with no framework installed. The
production wiring is in the comment block below, and a framework-native version
lives in coderifts/agent-guard → examples/langgraph-guard-python/.

    python3 langgraph_node.py
"""

from coderifts_gate import gate, log_line
from specs import OLD_SPEC, SAFE_NEW_SPEC, UNSAFE_NEW_SPEC


# ── nodes ────────────────────────────────────────────────────────────────────

def guard(state):
    """Ask CodeRifts whether the contract drift is safe to act on."""
    ev = gate(state["old_spec"], state["new_spec"])
    print(log_line("guard", ev))
    # Carry the whole evaluation, not a boolean. A later node that wants the
    # reason should not have to re-derive it.
    return dict(state, evaluation=ev)


def route(state):
    """Conditional edge. Branches on execution_action, via the evaluation."""
    return "abort" if state["evaluation"]["halt"] else "execute"


def execute(state):
    print("    [execute] calling GET /orders/{id} ...")
    return dict(state, result="order A1: shipped")


def abort(state):
    print("    [abort] halted: %s. The tool node was never entered."
          % state["evaluation"]["reason"])
    return dict(state, result=None)


# ── production wiring ────────────────────────────────────────────────────────
#   from langgraph.graph import StateGraph, START, END
#   g = StateGraph(AgentState)
#   g.add_node("guard", guard); g.add_node("execute", execute); g.add_node("abort", abort)
#   g.add_edge(START, "guard")
#   g.add_conditional_edges("guard", route, {"execute": "execute", "abort": "abort"})
#   g.add_edge("execute", END); g.add_edge("abort", END)


def run(label, old_spec, new_spec):
    print("[graph] %s" % label)
    state = {"old_spec": old_spec, "new_spec": new_spec}
    state = guard(state)
    state = execute(state) if route(state) == "execute" else abort(state)
    print("    [graph] result=%r\n" % state["result"])
    return state


if __name__ == "__main__":
    run("drift: endpoint removed", OLD_SPEC, UNSAFE_NEW_SPEC)
    run("drift: optional field added", OLD_SPEC, SAFE_NEW_SPEC)
