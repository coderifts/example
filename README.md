# CodeRifts Example

Two ways to use CodeRifts, in one place:

1. **[At review time](#1-at-review-time-github-app)** — the GitHub App comments on a PR that changes an API contract.
2. **[At execution time](#2-at-execution-time-agent-variants)** — an agent asks before it acts, and does not act unless it is told it may.

---

## 1. At review time (GitHub App)

### Install
https://github.com/apps/coderifts

### Configure
Put `.coderifts.yml` in your repo root. The copy in this repo is a working
reference: spec path, comment mode, merge blocking, and per-branch risk
profiles.

### Open a PR
CodeRifts analyses the OpenAPI change and posts a comment. `openapi.yaml` here
is a spec you can edit to trigger one.

Live demo PR — 13 breaking changes, $195,000 estimated impact:
https://github.com/coderifts/demo/pull/2

---

## 2. At execution time (agent variants)

`variants/` holds five worked examples of the same single idea:

> An agent was built against one API contract. The API now serves a different
> one. Before the agent acts, ask CodeRifts whether the drift is safe — and
> **act only on an explicit permission**.

| Variant | Run | Shows |
|---|---|---|
| [`minimal_python.py`](variants/minimal_python.py) | `python3 minimal_python.py` | The smallest shape: gate, then one branch. |
| [`minimal_js.mjs`](variants/minimal_js.mjs) | `node minimal_js.mjs` | Same, in Node. |
| [`langgraph_node.py`](variants/langgraph_node.py) | `python3 langgraph_node.py` | The gate as a graph node; routing as a conditional edge. |
| [`autogen_termination.py`](variants/autogen_termination.py) | `python3 autogen_termination.py` | The gate inside a registered tool, raising in front of the side effect. |
| [`openai_tool_call.py`](variants/openai_tool_call.py) | `python3 openai_tool_call.py` | The gate in a tool-call handler; refusal returned as a tool message. |

All five import one shared implementation of the rule —
[`coderifts_gate.py`](variants/coderifts_gate.py) /
[`coderifts_gate.mjs`](variants/coderifts_gate.mjs) — so there is one place the
control flow lives, not five. Standard library / zero dependencies. Every
variant runs standalone with no framework installed; the production wiring for
each framework is in a comment block in its file.

```
cd variants
python3 minimal_python.py     # or any variant above
python3 test_gate.py          # 29 offline checks, no network
node     gate.test.mjs        # 28 offline checks, mirrors the Python cases
```

### The rule

Taken verbatim from
[`/.well-known/coderifts.json`](https://app.coderifts.com/.well-known/coderifts.json)
→ `recommended_usage`:

```
branch_on                          = execution_action
execution_action                   = [CONTINUE, CONTINUE_WITH_MONITORING,
                                      REQUEST_APPROVAL, STOP]
unrecognised_execution_action      = not_permission_fail_closed
continue_with_monitoring_requires  = monitoringSinkWired
safe_for_agent                     = not_for_control_flow_use_execution_action
```

Branch on `execution_action`. Not on `decision` — that field is diagnostic, and
the variants print it labelled `(diagnostic)` for exactly that reason. Not on
`safe_for_agent` — the well-known says so in those words.

Permission is the narrow case. Everything else halts:

| Situation | Result |
|---|---|
| `CONTINUE` | proceed |
| `CONTINUE_WITH_MONITORING` **and** a monitoring sink is wired | proceed |
| `CONTINUE_WITH_MONITORING` with no sink | **halt** |
| `REQUEST_APPROVAL` | **halt** — approval is not optional |
| `STOP` | **halt** |
| present but unrecognised (e.g. `PROBABLY_FINE`) | **halt** — and it must *not* fall back to `decision` |
| absent | legacy `decision`→action map, then the same rules above |
| unreadable / empty / not a dict | **halt** |
| the request failed | **halt** — a guard that cannot reach its authority has not been granted anything |

### Which endpoint

The variants call **`POST /api/v1/demo`** — zero auth, synchronous, returns a
verdict you can gate on.

They deliberately do **not** call `GET /api/v1/public/preflight`. That endpoint
is analyze-only. It answers "does this single spec look hallucinated or low
quality", and it says so itself:

```
"authorization_effect": "NONE",
"may_execute": false,
"receipt_kind": "NONE",
"scope_note": "... Keyless public demo is analyze-only (no authorize / receipts)."
```

It carries no `execution_action`, no `decision` and no `safe_for_agent`. There
is nothing there to gate on, and pointing a guard at it is how you build a gate
that always opens. See [`variants/CHANGES.md`](variants/CHANGES.md).

### Going further

- **A framework-native Python guard**, with a `@coderifts_guard` decorator and
  real LangGraph / LangChain / AutoGen nodes:
  [`coderifts/agent-guard` → `examples/langgraph-guard-python/`](https://github.com/coderifts/agent-guard/tree/main/examples/langgraph-guard-python)
- **The enforcing TypeScript package**: [`@coderifts/agent-guard`](https://github.com/coderifts/agent-guard)
- **Verifying the receipt afterwards**: [`coderifts/receipt-verifier`](https://github.com/coderifts/receipt-verifier)
