// Runs index.html's own stubTags() against a table of (tags, room) cases.
// Driven by tests/test_stub_tags.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own: it is a pure function of a tag list and a room name, so it needs no DOM.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- stubTags: pure, extracted verbatim by tests/stub_tags_harness.js ---';
const END = '// --- end stubTags ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('stubTags markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/const stubTags\s*=/.test(source)) {
  console.error('marker block does not contain stubTags');
  process.exit(2);
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\nthis.stubTags = stubTags;', sandbox);
const stubTags = sandbox.stubTags;

// Every class of duplicate the committed data held on 2026-09-03, plus the cases that
// must survive: a format the room does not name, 3D, IMAX in an ordinary room.
const cases = {
  luxe_room:        [['2D', 'Anniskelu', 'LUXE'], 'LUXE 6'],
  plus_room:        [['Anniskelu', 'Plus'], '1 Plus'],
  isense_room:      [['2D', 'iSense'], 'iSense'],
  prime_room:       [['Prime', '2D'], 'Prime'],
  imax_room:        [['2D', 'Anniskelu', 'IMAX'], 'IMAX'],
  luxe_isense_room: [['LUXE', 'iSense', '2D'], 'LUXE iSense'],
  imax_in_sali:     [['2D', 'IMAX'], 'Sali 2'],
  three_d_kept:     [['3D', '2D'], 'Sali 1'],
  no_room:          [['2D', 'Anniskelu'], ''],
  null_room:        [['LUXE'], null],
  case_folds:       [['LUXE'], 'luxe 3'],
  bare_room_only:   [['Anniskelu', 'Perheleffa'], 'Sali 7'],
  empty_tag:        [['', 'Anniskelu'], 'Sali 7'],
};
const out = {};
for (const [k, [tags, aud]] of Object.entries(cases)) out[k] = stubTags(tags, aud);
process.stdout.write(JSON.stringify(out) + '\n');
