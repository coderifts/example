/**
 * Minimal CodeRifts enforcement — Node.
 *
 * Was: coderifts/example-minimal-js.
 *
 * The predecessor of this file failed open. It read `decision.decision`, the
 * live endpoint does not return that field, and `undefined === 'BLOCK'` is
 * false — so it printed "Proceeding with API call..." on every run, including
 * against a spec whose endpoint had been deleted.
 *
 * The fix is structural, not a patched comparison: permission is now the one
 * narrow branch and everything else halts.
 *
 *   node minimal_js.mjs
 */

import { gate, logLine } from './coderifts_gate.mjs';
import { OLD_SPEC, SAFE_NEW_SPEC, UNSAFE_NEW_SPEC } from './specs.mjs';

function callTheApi() {
  console.log('    [EXECUTION] calling GET /orders/{id} ...');
  return 'order A1: shipped';
}

async function run(label, oldSpec, newSpec) {
  const ev = await gate(oldSpec, newSpec);
  console.log(logLine(label, ev));

  if (ev.halt) {
    console.log(`    [EXECUTION] ABORTED — ${ev.reason}. The API call never ran.\n`);
    return null;
  }

  const result = callTheApi();
  console.log(`    [EXECUTION] ok: ${result}\n`);
  return result;
}

await run('drift: endpoint removed', OLD_SPEC, UNSAFE_NEW_SPEC);
await run('drift: optional field added', OLD_SPEC, SAFE_NEW_SPEC);
