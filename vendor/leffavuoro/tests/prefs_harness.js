// Runs a page's own `prefs` against stored values the page did not write: index.html by
// default, or the page named as the first argument (status/index.html).
// Driven by tests/test_prefs_store.py; prints one JSON line.
//
// Sliced verbatim out of the page between its marker comments and evaluated against a
// Map standing in for localStorage, so each case starts from exactly the stored string it
// names and the test reads back exactly what `set` left behind.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PAGE = process.argv[2] || 'index.html';
const HTML = fs.readFileSync(path.join(__dirname, '..', PAGE), 'utf8');
const START = '// --- prefs: pure, extracted verbatim by tests/prefs_harness.js ---';
const END = '// --- end prefs ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error(`prefs markers not found in ${PAGE}`);
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/const prefs\s*=/.test(source)) {
  console.error('marker block does not contain prefs');
  process.exit(2);
}

function run(stored) {
  const m = new Map();
  if (stored !== undefined) m.set('kino-prefs', stored);
  const localStorage = {
    getItem: k => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
  };
  const sandbox = { localStorage, JSON, Object };
  vm.createContext(sandbox);
  vm.runInContext(source + '\nthis.prefs = prefs;', sandbox);
  const prefs = sandbox.prefs;
  const r = {};
  try {
    const g = prefs.get();
    r.get = JSON.parse(JSON.stringify(g));
    r.getIsArray = Array.isArray(g);
    r.lang = g.lang === undefined ? null : g.lang;   // what boot reads, prefs.get().lang
  } catch (e) {
    r.threw = String((e && e.message) || e);
  }
  try {
    prefs.set({ lang: 'sv' });
  } catch (e) {
    r.setThrew = String((e && e.message) || e);
  }
  r.after = m.has('kino-prefs') ? m.get('kino-prefs') : null;
  r.keys = [...m.keys()];
  return r;
}

const cases = {
  missing:     undefined,
  empty_obj:   '{}',
  saved:       '{"fav":"1103","view":"times","lang":"en"}',
  null_json:   'null',
  number:      '3',
  string:      '"fi"',
  boolean:     'true',
  array:       '["lang"]',
  torn:        '{"fav":"11',
};
const out = {};
for (const [k, v] of Object.entries(cases)) out[k] = run(v);
process.stdout.write(JSON.stringify(out) + '\n');
