/**
 * Offline control-flow checks for coderifts_gate.mjs.
 *
 * Mirrors test_gate.py case for case, so the two implementations cannot drift.
 * Zero dependencies. No network.
 *
 *   node gate.test.mjs
 */

import { CLOSED_EXECUTION_ACTIONS, evaluate, gate } from './coderifts_gate.mjs';

const failures = [];
function check(name, cond, detail) {
  if (cond) console.log(`ok  ${name}`);
  else { console.log(`FAIL ${name}  ${JSON.stringify(detail)}`); failures.push(name); }
}
const eq = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

// ── the closed set is the published one ──────────────────────────────────────
check('closed set matches /.well-known',
  eq(CLOSED_EXECUTION_ACTIONS, ['CONTINUE', 'CONTINUE_WITH_MONITORING', 'REQUEST_APPROVAL', 'STOP']),
  CLOSED_EXECUTION_ACTIONS);

// ── the four closed actions ──────────────────────────────────────────────────
{
  const r = evaluate({ execution_action: 'CONTINUE', decision: 'ALLOW' });
  check('CONTINUE proceeds', r.halt === false && r.reason === 'CONTINUE', r);
}
{
  const r = evaluate({ execution_action: 'STOP', decision: 'BLOCK' });
  check('STOP halts', r.halt === true && r.reason === 'STOP', r);
}
{
  const r = evaluate({ execution_action: 'REQUEST_APPROVAL', decision: 'ALLOW' });
  check('REQUEST_APPROVAL halts even when decision says ALLOW',
    r.halt === true && r.reason === 'REQUEST_APPROVAL', r);
}
{
  const unwired = evaluate({ execution_action: 'CONTINUE_WITH_MONITORING' });
  const wired = evaluate({ execution_action: 'CONTINUE_WITH_MONITORING' }, { monitoringSinkWired: true });
  check('CONTINUE_WITH_MONITORING halts without a sink',
    unwired.halt === true && unwired.reason === 'MONITORING_UNWIRED', unwired);
  check('CONTINUE_WITH_MONITORING proceeds with a sink', wired.halt === false, wired);
}

// ── the two ways permission gets reinvented ──────────────────────────────────
{
  const r = evaluate({ execution_action: 'PROBABLY_FINE', decision: 'ALLOW' });
  check('present-but-unknown halts',
    r.halt === true && r.reason === 'EXECUTION_ACTION_UNRECOGNISED', r);
  check('present-but-unknown does not consult decision', r.action_source === 'top_level', r);
}
for (const bad of [true, 1, { a: 1 }, ['CONTINUE']]) {
  const r = evaluate({ execution_action: bad, decision: 'ALLOW' });
  check(`non-string action ${JSON.stringify(bad)} halts`,
    r.halt === true && r.reason === 'EXECUTION_ACTION_UNRECOGNISED', r);
}

// ── absent action: legacy map, then the same closed rules ────────────────────
{
  const r = evaluate({ decision: 'BLOCK' });
  check('absent + BLOCK -> STOP',
    r.halt === true && r.execution_action === 'STOP' && r.action_source === 'legacy_decision_map', r);
  check('absent + ALLOW -> CONTINUE', evaluate({ decision: 'ALLOW' }).halt === false);
}
{
  // The shape POST /api/v1/demo actually returns today.
  const r = evaluate({ omega_decision: 'BLOCK', should_block: true });
  check('omega_decision BLOCK -> STOP', r.halt === true && r.execution_action === 'STOP', r);
}
{
  const r = evaluate({ decision_result: { execution_action: 'STOP', decision: 'BLOCK' }, execution_action: 'CONTINUE' });
  check('envelope wins over top level', r.halt === true && r.action_source === 'envelope', r);
}

// ── the regression that caused the original fail-open ────────────────────────
{
  // The exact live payload example-minimal-js received. It printed
  // "Proceeding with API call..." on this. It must halt.
  const analyzeOnly = {
    preflight_mode: 'analyze',
    analysis_outcome: 'NO_BREAK_DETECTED',
    authorization_effect: 'NONE',
    may_execute: false,
    receipt_kind: 'NONE',
    decision_spec_version: '2.0',
    risk_score: 0,
  };
  const r = evaluate(analyzeOnly);
  check('analyze-only response halts (no permission field present)',
    r.halt === true && r.reason === 'UNREADABLE_DECISION', r);
}
{
  const r = evaluate({ status: 'PENDING', message: 'Analysis scheduled. Retry in 5 seconds.' });
  check('PENDING response halts', r.halt === true, r);
}
for (const bad of [{}, null, undefined, [], 'BLOCK', 0]) {
  check(`garbage verdict ${JSON.stringify(bad) ?? 'undefined'} halts`, evaluate(bad).halt === true, bad);
}
{
  check('safe_for_agent=true does not override STOP',
    evaluate({ execution_action: 'STOP', safe_for_agent: true }).halt === true);
  check('safe_for_agent=false does not override CONTINUE',
    evaluate({ execution_action: 'CONTINUE', safe_for_agent: false }).halt === false);
}

// ── transport ────────────────────────────────────────────────────────────────
{
  // Point the gate at an unroutable address; it must halt, not proceed.
  const realFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new TypeError('fetch failed'); };
  const r = await gate({ a: 1 }, { a: 2 });
  globalThis.fetch = realFetch;
  check('transport failure halts', r.halt === true && r.reason === 'TRANSPORT_FAILURE', r);
}
{
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 502 });
  const r = await gate({ a: 1 }, { a: 2 });
  globalThis.fetch = realFetch;
  check('HTTP 502 halts', r.halt === true && r.reason === 'TRANSPORT_FAILURE', r);
}

console.log();
if (failures.length) { console.log(`${failures.length} FAILED: ${failures.join(', ')}`); process.exit(1); }
console.log('all checks passed');
