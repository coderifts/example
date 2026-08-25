/**
 * Shared CodeRifts control-flow gate — Node.
 *
 * Line-for-line the same rule as coderifts_gate.py. See that file's header for
 * the contract; test_gate.py and gate.test.mjs pin both against the same cases.
 *
 * Control-flow contract (app.coderifts.com/.well-known/coderifts.json):
 *   branch_on                      = execution_action
 *   unrecognised_execution_action  = not_permission_fail_closed
 *   safe_for_agent                 = not_for_control_flow_use_execution_action
 *
 * The predecessor of this file, coderifts/example-minimal-js, branched on
 * `decision === 'BLOCK'`. The live endpoint returns no `decision` field, so
 * `undefined === 'BLOCK'` was false and the example printed "Proceeding with
 * API call" on every single run. That is the specific bug this shape removes:
 * here, permission is the narrow case and everything else halts.
 *
 * Zero dependencies.
 */

// Zero-auth synchronous diff endpoint — the one that returns a gateable verdict.
//
// NOTE: GET /api/v1/public/preflight is *analyze-only*. It returns
// authorization_effect="NONE", may_execute=false and no execution_action; its
// own scope_note says "Keyless public demo is analyze-only (no authorize /
// receipts)". It cannot be used as an execution gate.
export const CODERIFTS_DEMO_URL = 'https://app.coderifts.com/api/v1/demo';

export const CLOSED_EXECUTION_ACTIONS = Object.freeze([
  'CONTINUE',
  'CONTINUE_WITH_MONITORING',
  'REQUEST_APPROVAL',
  'STOP',
]);

// Applied ONLY when execution_action is absent.
const DECISION_TO_ACTION = Object.freeze({
  ALLOW: 'CONTINUE',
  WARN: 'CONTINUE_WITH_MONITORING',
  REQUIRE_APPROVAL: 'REQUEST_APPROVAL',
  BLOCK: 'STOP',
});

export class Halt extends Error {
  constructor(reason, executionAction, decision) {
    super(`CodeRifts halt (${reason}) execution_action=${JSON.stringify(executionAction)}`);
    this.name = 'Halt';
    this.reason = reason;
    this.executionAction = executionAction;
    this.decision = decision; // diagnostic only
  }
}

/** Diagnostic only. Not the control-flow field. */
function readDecision(verdict) {
  if (typeof verdict !== 'object' || verdict === null) return 'UNKNOWN';
  const env = verdict.decision_result;
  if (env && typeof env === 'object' && typeof env.decision === 'string') return env.decision;
  return verdict.omega_decision ?? verdict.decision ?? 'UNKNOWN';
}

/** Returns [value, source]; [null, 'missing'] when absent or empty. */
function rawExecutionAction(verdict) {
  if (typeof verdict !== 'object' || verdict === null) return [null, 'missing'];
  const env = verdict.decision_result;
  if (env && typeof env === 'object' && 'execution_action' in env) {
    const v = env.execution_action;
    if (v !== null && v !== undefined && v !== '') return [v, 'envelope'];
  }
  if ('execution_action' in verdict) {
    const v = verdict.execution_action;
    if (v !== null && v !== undefined && v !== '') return [v, 'top_level'];
  }
  return [null, 'missing'];
}

/** Pure, offline control-flow evaluation. No network. */
export function evaluate(verdict, { monitoringSinkWired = false } = {}) {
  const decision = readDecision(verdict);
  const [raw, source] = rawExecutionAction(verdict);

  let action;
  let actionSource;

  if (raw !== null) {
    if (typeof raw !== 'string' || !CLOSED_EXECUTION_ACTIONS.includes(raw)) {
      return {
        halt: true,
        reason: 'EXECUTION_ACTION_UNRECOGNISED',
        execution_action: typeof raw === 'string' ? raw : null,
        decision,
        action_source: source,
      };
    }
    action = raw;
    actionSource = source;
  } else {
    action = DECISION_TO_ACTION[decision];
    actionSource = 'legacy_decision_map';
    if (action === undefined) {
      return {
        halt: true,
        reason: 'UNREADABLE_DECISION',
        execution_action: null,
        decision,
        action_source: 'missing',
      };
    }
  }

  let halt;
  let reason;
  if (action === 'STOP') {
    halt = true; reason = 'STOP';
  } else if (action === 'REQUEST_APPROVAL') {
    halt = true; reason = 'REQUEST_APPROVAL';
  } else if (action === 'CONTINUE_WITH_MONITORING') {
    halt = !monitoringSinkWired;
    reason = monitoringSinkWired ? 'CONTINUE_WITH_MONITORING' : 'MONITORING_UNWIRED';
  } else {
    halt = false; reason = 'CONTINUE';
  }

  return { halt, reason, execution_action: action, decision, action_source: actionSource };
}

export async function fetchVerdict(oldSpec, newSpec, { timeoutMs = 20000 } = {}) {
  const res = await fetch(CODERIFTS_DEMO_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_spec: oldSpec, new_spec: newSpec }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Fetch a verdict and evaluate it.
 *
 * Any transport, HTTP or decode failure halts with reason TRANSPORT_FAILURE. A
 * guard that cannot reach its authority has not been granted anything.
 */
export async function gate(oldSpec, newSpec, { monitoringSinkWired = false, timeoutMs = 20000 } = {}) {
  let verdict;
  try {
    verdict = await fetchVerdict(oldSpec, newSpec, { timeoutMs });
  } catch (err) {
    return {
      halt: true,
      reason: 'TRANSPORT_FAILURE',
      execution_action: null,
      decision: 'UNKNOWN',
      action_source: 'missing',
      error: `${err.name}: ${err.message}`,
    };
  }
  return evaluate(verdict, { monitoringSinkWired });
}

export function logLine(tag, ev) {
  return `[${tag}] execution_action=${JSON.stringify(ev.execution_action)} `
    + `reason=${ev.reason} source=${ev.action_source} `
    + `decision=${JSON.stringify(ev.decision)}(diagnostic)`;
}
