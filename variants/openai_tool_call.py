"""
CodeRifts enforcement in an OpenAI tool-calling loop.

Was: coderifts/example-openai-functions.

The guard runs in the tool-call handler, before the tool body. On halt the
handler returns a tool message describing the refusal — the model is told what
happened, but the side effect does not run and the model is given no field it
can treat as permission.

This file simulates one tool call so it runs with no SDK installed.

    python3 openai_tool_call.py
"""

import json

from coderifts_gate import gate, log_line
from specs import OLD_SPEC, SAFE_NEW_SPEC, UNSAFE_NEW_SPEC

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "order_lookup",
            "description": "Look up an order by id",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    }
]


def handle_tool_call(tool_call, old_spec, new_spec):
    """Return the tool message content for one tool call."""
    args = json.loads(tool_call["arguments"])

    ev = gate(old_spec, new_spec)
    print(log_line("tool_call:%s" % tool_call["name"], ev))

    if ev["halt"]:
        # Report the refusal. Note there is no `safe_for_agent` and no
        # `decision` in this payload — nothing here is a permission field.
        return json.dumps({
            "status": "refused",
            "reason": ev["reason"],
            "execution_action": ev["execution_action"],
            "detail": "CodeRifts halted this call; the API contract drifted.",
        })

    print("    [tool] calling GET /orders/%s ..." % args["id"])
    return json.dumps({"status": "ok", "order": {"id": args["id"], "state": "shipped"}})


# ── production wiring ────────────────────────────────────────────────────────
#   from openai import OpenAI
#   client = OpenAI()
#   resp = client.chat.completions.create(model="gpt-4o", tools=TOOLS, messages=msgs)
#   for tc in resp.choices[0].message.tool_calls:
#       content = handle_tool_call(
#           {"name": tc.function.name, "arguments": tc.function.arguments},
#           old_spec, new_spec)
#       msgs.append({"role": "tool", "tool_call_id": tc.id, "content": content})


def run(label, old_spec, new_spec):
    print("[openai] %s" % label)
    tool_call = {"name": "order_lookup", "arguments": json.dumps({"id": "A1"})}
    content = handle_tool_call(tool_call, old_spec, new_spec)
    print("    [openai] tool message: %s\n" % content)


if __name__ == "__main__":
    run("drift: endpoint removed", OLD_SPEC, UNSAFE_NEW_SPEC)
    run("drift: optional field added", OLD_SPEC, SAFE_NEW_SPEC)
