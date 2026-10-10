// Runs index.html's own calCell() against a table of day states and prints one JSON
// line. Driven by tests/test_cal_cell.py.
//
// The function is sliced verbatim out of index.html between its two marker comments and
// evaluated on its own. It builds a string from four arguments and touches no DOM and no
// globals, which is the same property tests/health_state_harness.js relies on. Opening
// the picker, moving focus into the grid and Escape stay verified live against the
// served page; what is decided here is which element a day becomes, which classes it
// carries, and whether it announces itself as the current date.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- calCell: pure, extracted verbatim by tests/cal_cell_harness.js ---';
const END = '// --- end calCell ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('calCell markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/function calCell\s*\(/.test(source)) {
  console.error('marker block does not contain calCell');
  process.exit(2);
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__fn = calCell;', sandbox, { filename: 'calCell' });
const calCell = sandbox.__fn;

const SEL = '2026-09-01';

// [name, day, iso, hasShowtimes, selectedIso]
const CASES = [
  ['selected_available',     1,  '2026-09-01', true,  SEL],
  ['unselected_available',   2,  '2026-09-02', true,  SEL],
  // A day with no showtimes is a <span>: not a control, and not selectable.
  ['unselected_unavailable', 3,  '2026-09-03', false, SEL],
  // The same date as the selection but with nothing on. Cannot happen from drawCal
  // today, and must still never announce a state a <span> cannot hold.
  ['selected_unavailable',   1,  '2026-09-01', false, SEL],
  ['two_digit_day',          30, '2026-09-30', true,  SEL],
];

const out = {};
for (const [name, d, iso, has, sel] of CASES) out[name] = calCell(d, iso, has, sel);
process.stdout.write(JSON.stringify(out));
