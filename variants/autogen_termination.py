"""
CodeRifts enforcement in an AutoGen tool.

Was: coderifts/example-autogen.

The guard sits inside the registered tool, in front of the side effect. It
raises on halt, so the agent cannot talk its way past it: there is no return
value the model can reinterpret as permission.

The original version of this example also wired a `is_termination_msg`
callback. That is deliberately gone. A termination check runs *after* a message
exists — it can end a conversation, but it cannot un-ring a tool call that
already fired. The gate belongs in front of the side effect.

This file simulates the conversation so it runs with no framework installed.

    python3 autogen_termination.py
"""

from coderifts_gate import Halt, gate, log_line
from specs import OLD_SPEC, SAFE_NEW_SPEC, UNSAFE_NEW_SPEC


def order_lookup(old_spec, new_spec):
    """A tool an AutoGen agent may call. Guarded in front of the side effect."""
    ev = gate(old_spec, new_spec)
    print(log_line("tool:order_lookup", ev))
    if ev["halt"]:
        raise Halt(ev["reason"], ev["execution_action"], ev["decision"])
    print("    [tool] calling GET /orders/{id} ...")
    return "order A1: shipped"


# ── production wiring ────────────────────────────────────────────────────────
#   from autogen import ConversableAgent
#   assistant  = ConversableAgent("assistant", llm_config=...)
#   user_proxy = ConversableAgent("user", human_input_mode="NEVER")
#   user_proxy.register_for_execution(name="order_lookup")(order_lookup)
#   assistant.register_for_llm(description="Look up an order")(order_lookup)


def run(label, old_spec, new_spec):
    print("[autogen] %s" % label)
    try:
        print("    [autogen] tool result: %s\n" % order_lookup(old_spec, new_spec))
    except Halt as h:
        print("    [autogen] tool refused: %s" % h.reason)
        print("    [autogen] conversation terminated by the guard\n")


if __name__ == "__main__":
    run("drift: endpoint removed", OLD_SPEC, UNSAFE_NEW_SPEC)
    run("drift: optional field added", OLD_SPEC, SAFE_NEW_SPEC)
