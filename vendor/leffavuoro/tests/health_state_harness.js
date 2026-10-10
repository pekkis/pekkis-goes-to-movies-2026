// Runs status/index.html's own healthState() against a table of provider states.
// Driven by tests/test_health_state.py; prints one JSON line.
//
// The function is sliced verbatim out of status/index.html between its two marker comments and
// evaluated on its own. It is pure by construction -- it takes the provider metadata and
// an age in hours and returns a string -- so it needs no DOM, and the alternative would
// have been either stubbing the whole app or splitting the single file, which the repo
// deliberately does not do. If the markers are ever removed the harness fails loudly
// rather than silently testing nothing.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'status', 'index.html'), 'utf8');
const START = '// --- healthState: pure, extracted verbatim by tests/health_state_harness.js ---';
const END = '// --- end healthState ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('healthState markers not found in status/index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/function healthState\s*\(/.test(source)) {
  console.error('marker block does not contain healthState');
  process.exit(2);
}

const sandbox = { STALE_H: 8 };
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__fn = healthState;', sandbox, { filename: 'healthState' });
const healthState = sandbox.__fn;

// [name, meta, ageHours]
const CASES = [
  ['fresh_ok',            { status: 'ok', stale: 0, unverified: 0 }, 2],
  ['partial_recent',      { status: 'partial', stale: 1, unverified: 0 }, 2],
  ['partial_flag_only',   { status: 'partial', stale: 0, unverified: 0 }, 2],
  ['stale_count_only',    { status: '', stale: 1, unverified: 0 }, 2],
  ['unverified_only',     { status: 'partial', stale: 0, unverified: 1 }, 2],
  // No `status`, so only the unverified term can catch it. Without this the term
  // could be deleted and every test still passed -- found by trying exactly that.
  ['unverified_count_only', { stale: 0, unverified: 1 }, 2],
  // Both at once: the stale venue is the worse problem and must win the label.
  ['stale_and_unverified', { status: 'partial', stale: 1, unverified: 1 }, 2],
  ['unverified_but_old',  { status: 'partial', stale: 0, unverified: 1 }, 9],
  // Pending: run.py grants it only on the adapter's word (EMPTY_VENUES_CONFIRMED),
  // and such a file carries status ok. It never outranks anything above it.
  ['pending_only',        { status: 'ok', stale: 0, unverified: 0, pending: 1 }, 2],
  ['pending_count_only',  { pending: 1 }, 2],
  ['pending_and_stale',   { status: 'partial', stale: 1, unverified: 0, pending: 1 }, 2],
  ['pending_and_unverified', { status: 'partial', stale: 0, unverified: 1, pending: 1 }, 2],
  ['pending_but_old',     { status: 'ok', stale: 0, unverified: 0, pending: 1 }, 9],
  ['legacy_no_status',    { stale: 0, unverified: 0 }, 2],
  ['too_old',             { status: 'ok', stale: 0, unverified: 0 }, 9],
  ['too_old_and_partial', { status: 'partial', stale: 1, unverified: 0 }, 9],
  ['invalid_timestamp',   { status: 'ok', stale: 0, unverified: 0 }, null],
  ['gone',                { gone: true, venues: 0 }, null],
  ['gone_but_fresh_age',  { gone: true, status: 'ok', stale: 0 }, 1],
  ['missing_meta',        null, 2],
  ['exactly_at_threshold', { status: 'ok', stale: 0, unverified: 0 }, 8],
];

const out = {};
for (const [name, meta, age] of CASES) out[name] = healthState(meta, age);
process.stdout.write(JSON.stringify(out));
