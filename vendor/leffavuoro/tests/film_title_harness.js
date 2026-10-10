// Runs index.html's own filmTitle() against the case table tests/test_release_year.py
// sends on stdin, and prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own. filmTitle takes a title, a year and the current year and returns a string, so it
// needs no DOM and no clock: the current year is a parameter precisely so the test can
// fix one.
//
// Every exit path prints JSON. A harness that dies without output scores the mutation
// VOID rather than red, which is how a test can look green while guarding nothing.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function bail(msg) {
  process.stdout.write(JSON.stringify({ error: msg }) + '\n');
  process.exit(2);
}

// The harness must not outlive the suite if a case loops.
const watchdog = setTimeout(() => bail('timed out after 20s'), 20000);
watchdog.unref();

let out;
try {
  const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const START = '// --- filmTitle: pure, extracted verbatim by tests/film_title_harness.js ---';
  const END = '// --- end filmTitle ---';
  const a = HTML.indexOf(START);
  const b = HTML.indexOf(END);
  if (a === -1 || b === -1 || b < a) bail('filmTitle markers not found in index.html');
  const source = HTML.slice(a, b);
  if (!/function filmTitle\s*\(/.test(source)) bail('marker block does not contain filmTitle');

  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(source + '\n;globalThis.__fn = filmTitle;', sandbox, { filename: 'filmTitle' });
  const filmTitle = sandbox.__fn;

  const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
  out = {};
  for (const c of cases) {
    try {
      out[c.name] = filmTitle(c.title, c.oyear, c.now);
    } catch (e) {
      out[c.name] = { threw: String(e && e.message || e) };
    }
  }
} catch (e) {
  bail(String(e && e.stack || e));
}
clearTimeout(watchdog);
process.stdout.write(JSON.stringify(out) + '\n');
