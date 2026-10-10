// Runs index.html's own pastLabel() against a table of (open, count, lang) cases.
// Driven by tests/test_past_label.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own: it is a pure function of the toggle state, the hidden count and the language
// table, so it needs no DOM. The three tables are read out of index.html rather than
// retyped, so a changed string shows up here instead of passing against a stale copy.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- pastLabel: pure, extracted verbatim by tests/past_label_harness.js ---';
const END = '// --- end pastLabel ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('pastLabel markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/const pastLabel\s*=/.test(source)) {
  console.error('marker block does not contain pastLabel');
  process.exit(2);
}

function table(lang) {
  const at = HTML.indexOf(`\n    ${lang}:{`);
  if (at === -1) { console.error('no L block for ' + lang); process.exit(2); }
  const block = HTML.slice(at, HTML.indexOf('\n    ', at + 1 + HTML.slice(at + 1).indexOf('\n    ') + 1));
  const pick = key => {
    const m = HTML.slice(at).match(new RegExp(`\\b${key}:'((?:[^'\\\\]|\\\\.)*)'`));
    if (!m) { console.error(`no ${key} in the ${lang} block`); process.exit(2); }
    return m[1];
  };
  return { showPast: pick('showPast'), showPastOne: pick('showPastOne'), hidePast: pick('hidePast') };
}
const L = { fi: table('fi'), sv: table('sv'), en: table('en') };

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\nthis.pastLabel = pastLabel;', sandbox);
const pastLabel = sandbox.pastLabel;

// [name, open, n, lang]
const CASES = [
  ['fi_one',      false, 1, 'fi'],
  ['fi_two',      false, 2, 'fi'],
  ['fi_eleven',   false, 11, 'fi'],
  ['fi_open_one', true,  1, 'fi'],
  ['fi_open_two', true,  2, 'fi'],
  ['sv_one',      false, 1, 'sv'],
  ['sv_three',    false, 3, 'sv'],
  ['en_one',      false, 1, 'en'],
  ['en_three',    false, 3, 'en'],
];
const out = {};
for (const [name, open, n, lang] of CASES) out[name] = pastLabel(open, n, L[lang]);
out.__L = L;
process.stdout.write(JSON.stringify(out));
