# What changed, and why

These five variants replace five archived repositories. They were **not moved
as-is** — they were broken, and moving them unchanged would have moved a
fail-open gate into the repo we point new users at.

| This file | Replaces | Source last touched |
|---|---|---|
| `minimal_js.mjs` | `coderifts/example-minimal-js` | 2026-03-19 |
| `minimal_python.py` | `coderifts/example-minimal-python` | 2026-03-19 |
| `autogen_termination.py` | `coderifts/example-autogen` | 2026-03-19 |
| `langgraph_node.py` | `coderifts/example-langgraph` | 2026-03-19 |
| `openai_tool_call.py` | `coderifts/example-openai-functions` | 2026-03-19 |

## What was wrong

All five were written against a response shape the API no longer returns, and
all five branched on fields the published contract forbids branching on.

**1. They branched on `decision` and printed `safe_for_agent`.**
`/.well-known/coderifts.json` says, in these words:

```
branch_on      = execution_action
safe_for_agent = not_for_control_flow_use_execution_action
```

**2. They called an analyze-only endpoint and treated it as a gate.**
All five called `GET /api/v1/public/preflight`. Measured against the live
endpoint, it returns:

```json
{"preflight_mode":"analyze","analysis_outcome":"NO_BREAK_DETECTED",
 "authorization_effect":"NONE","may_execute":false,"receipt_kind":"NONE",
 "decision_spec_version":"2.0","risk_score":0,
 "scope_note":"... Keyless public demo is analyze-only (no authorize / receipts)."}
```

No `decision`. No `safe_for_agent`. No `execution_action`. There was never
anything there to gate on. (Its other live shape is
`{"status":"PENDING","message":"Analysis scheduled. Retry in 5 seconds."}` —
also with no `decision` field, so the examples' `PENDING` branch was
unreachable too.)

**3. The JS one failed open.** `decision.decision` was `undefined`,
`undefined === 'BLOCK'` is false, `undefined === 'PENDING'` is false, so
control fell through to the success path. Run against the live endpoint on
2026-08-25 it printed:

```
[CODERIFTS] decision: undefined
[CODERIFTS] risk_score: 0
[CODERIFTS] safe_for_agent: N/A
[EXECUTION] Proceeding with API call...
```

**4. The four Python ones crashed.** Against a healthy endpoint all four die
with `KeyError: 'decision'` before any gating logic runs:

```
example-minimal-python  main.py:17  print(f"[CODERIFTS] decision: {decision['decision']}")   KeyError: 'decision'
example-langgraph       main.py:18  state["coderifts_decision"] = decision["decision"]       KeyError: 'decision'
example-autogen         main.py:38  if decision["decision"] == "BLOCK":                      KeyError: 'decision'
example-openai-functions main.py:48 print(f"[CODERIFTS] decision={decision['decision']} ...") KeyError: 'decision'
```

Fail-closed by accident, not by design — and a demo that tracebacks is not a
demo. (The endpoint also intermittently returns a plain-text `502`, which turns
the same line into `requests.exceptions.JSONDecodeError`. Neither path was
handled.)

## What changed

- **Endpoint**: `GET /api/v1/public/preflight` → `POST /api/v1/demo` (zero auth,
  synchronous, returns a gateable verdict). This is the same endpoint the
  maintained sibling in `coderifts/agent-guard` uses.
- **Control flow**: branch on `execution_action` against the closed set of four.
  Present-but-unrecognised halts and never falls back to `decision`. Absent
  falls back to the legacy `decision`→action map and is then held to the same
  rules.
- **`safe_for_agent`**: never read. Pinned by a test in both languages.
- **`decision`**: printed, labelled `(diagnostic)`. Never branched on.
- **Fail-closed transport**: any network, HTTP or decode failure halts with
  `TRANSPORT_FAILURE`. The gate never returns "proceed" because a request failed.
- **One implementation, five variants**: the rule lives in `coderifts_gate.py` /
  `coderifts_gate.mjs`. The variants are thin.
- **A real breaking change to demonstrate**: `specs.py` / `specs.mjs` carry a
  before/after contract pair. Each variant runs both — one that must halt
  (endpoint removed) and one that must proceed (optional field added) — so the
  gate is shown *not* firing as well as firing. An example that only ever shows
  the halt path cannot distinguish a working gate from a gate stuck closed.
- **AutoGen**: the old `is_termination_msg` callback is gone. A termination
  check runs after a message exists; it cannot un-ring a tool call that already
  fired. The gate belongs in front of the side effect.

## Verification

Run on 2026-08-25 against the live endpoint.

```
python3 test_gate.py    # 29 offline checks, network blocked in-process
node     gate.test.mjs  # 28 offline checks, mirrors the Python cases
```

Both suites include the regression directly: the exact analyze-only payload
above, asserted to halt.

All five variants were run end to end against live `POST /api/v1/demo`. Each
halts on the removed endpoint and proceeds on the additive change:

```
[drift: endpoint removed]      execution_action='STOP'     reason=STOP     -> ABORTED, the API call never ran
[drift: optional field added]  execution_action='CONTINUE' reason=CONTINUE -> ok: order A1: shipped
```

Note `action_source=legacy_decision_map` in those runs: `POST /api/v1/demo`
currently returns `omega_decision` and no `execution_action`, so the documented
absent-field path is what actually executes. Both the closed-set path and the
legacy path are covered by the tests; if the endpoint starts emitting
`execution_action`, these variants pick it up with no change and prefer it.
