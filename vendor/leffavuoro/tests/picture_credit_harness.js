// Runs index.html's own pictureCredit() over a table of non-film pictures and languages.
// Driven by tests/test_picture_credit.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its own:
// it is a pure function of the row, the language table and an escaper. The strings are
// read out of index.html rather than retyped, so a changed word shows up here.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- pictureCredit: pure, extracted verbatim by tests/picture_credit_harness.js ---';
const END = '// --- end pictureCredit ---';
const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('pictureCredit markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);

function table(lang) {
  const at = HTML.indexOf(`\n    ${lang}:{`);
  if (at === -1) { console.error('no L block for ' + lang); process.exit(2); }
  const pick = key => {
    const m = HTML.slice(at).match(new RegExp(`\\b${key}:'((?:[^'\\\\]|\\\\.)*)'`));
    if (!m) { console.error(`no ${key} in the ${lang} block`); process.exit(2); }
    return m[1];
  };
  return { photo: pick('photo'), eventOnly: pick('eventOnly') };
}
const L = { fi: table('fi'), sv: table('sv'), en: table('en') };
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\nthis.pictureCredit = pictureCredit;', sandbox);
const credit = sandbox.pictureCredit;

const SRC = 'Espoon tapahtumarajapinta';
const CASES = [
  ['event_only_credited', { imgLic: 'event_only', imgBy: 'Mikko Mäntyniemi', imgSrc: SRC }, 'fi'],
  ['event_only_uncredited', { imgLic: 'event_only', imgBy: '', imgSrc: SRC }, 'fi'],
  ['cc_by_uncredited', { imgLic: 'cc_by', imgBy: '', imgSrc: SRC }, 'fi'],
  ['event_only_sv', { imgLic: 'event_only', imgBy: 'Katri Kuusela', imgSrc: SRC }, 'sv'],
  ['event_only_en', { imgLic: 'event_only', imgBy: '', imgSrc: SRC }, 'en'],
  ['unknown_licence', { imgLic: 'cc_by_sa', imgBy: 'X', imgSrc: SRC }, 'fi'],
  ['no_licence', { imgBy: 'X', imgSrc: SRC }, 'fi'],
  ['escaped', { imgLic: 'event_only', imgBy: '<b>Kuvaaja</b>', imgSrc: SRC }, 'fi'],
];
const out = {};
for (const [name, row, lang] of CASES) out[name] = credit(row, L[lang], esc);
process.stdout.write(JSON.stringify(out));
