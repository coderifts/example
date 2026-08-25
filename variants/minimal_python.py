"""
Minimal CodeRifts enforcement — Python.

Was: coderifts/example-minimal-js's Python sibling, example-minimal-python.

The smallest possible shape: ask before acting, and act only on CONTINUE.

    python3 minimal_python.py
"""

from coderifts_gate import gate, log_line
from specs import OLD_SPEC, SAFE_NEW_SPEC, UNSAFE_NEW_SPEC


def call_the_api():
    """Stand-in for the side effect you are trying to protect."""
    print("    [EXECUTION] calling GET /orders/{id} ...")
    return "order A1: shipped"


def run(label, old_spec, new_spec):
    ev = gate(old_spec, new_spec)
    print(log_line(label, ev))

    if ev["halt"]:
        # One branch, one rule: anything that is not an explicit permission
        # stops here. No BLOCK-only special case to fall through.
        print("    [EXECUTION] ABORTED — %s. The API call never ran.\n" % ev["reason"])
        return None

    result = call_the_api()
    print("    [EXECUTION] ok: %s\n" % result)
    return result


if __name__ == "__main__":
    run("drift: endpoint removed", OLD_SPEC, UNSAFE_NEW_SPEC)
    run("drift: optional field added", OLD_SPEC, SAFE_NEW_SPEC)
