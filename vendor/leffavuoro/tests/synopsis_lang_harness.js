// Runs the real synopsis language selection out of index.html and prints one JSON line
// of results. Driven by tests/test_synopsis_lang_client.py.
//
// synPick is pure by construction -- it reads one object and a language code, renders no
// DOM and touches no globals -- so it is extracted verbatim between its markers and run in
// a bare vm context, the same technique tests/venue_picker_harness.js uses. What the sheet
// does with the text afterwards (the clamp, the expand button, esc()) is DOM plumbing and
// stays verified live.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- synopsis language: pure, extracted verbatim by tests/synopsis_lang_harness.js ---';
const END = '// --- end synopsis language ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('synopsis language markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/function synPick\s*\(/.test(source)) {
  console.error('marker block does not contain synPick');
  process.exit(2);
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__syn = synPick;', sandbox, { filename: 'synPick' });
const synPick = sandbox.__syn;

const FI = 'Suomeksi.';
const SV = 'På svenska.';
const EN = 'In English.';

// Every shape a films-extra entry's `s` map can have, against every language the toggle
// offers. `sv` is absent from 403 of 403 entries today, so the fallback rows are the
// common case and the sv rows are the new one.
const CASES = {
  all:        { fi: FI, sv: SV, en: EN },
  fi_en:      { fi: FI, en: EN },          // what every entry looks like today
  fi_only:    { fi: FI, en: '' },
  en_only:    { fi: '', en: EN },
  sv_only:    { fi: '', en: '', sv: SV },
  sv_and_en:  { fi: '', en: EN, sv: SV },
  empty:      { fi: '', en: '' },
  none:       null,
  undef:      undefined,
};

const out = { __from: {} };
for (const [name, s] of Object.entries(CASES)) {
  out[name] = {};
  for (const lang of ['fi', 'sv', 'en']) {
    const p = synPick(s, lang);
    out[name][lang] = p.text;
    (out.__from[name] = out.__from[name] || {})[lang] = p.from;
  }
}

// The block must not reach for anything outside itself: a bare context would have thrown
// above if it did, and this records that it ran at all.
out.__ran = true;

process.stdout.write(JSON.stringify(out));
