// Runs index.html's own tileInitials() against a table of titles.
// Driven by tests/test_tile_initials.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own: it is a pure function of a title string, so it needs no DOM.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- tileInitials: pure, extracted verbatim by tests/tile_initials_harness.js ---';
const END = '// --- end tileInitials ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('tileInitials markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/const tileInitials\s*=/.test(source)) {
  console.error('marker block does not contain tileInitials');
  process.exit(2);
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\nthis.tileInitials = tileInitials;', sandbox);
const f = sandbox.tileInitials;

const cases = {
  // The reported case: the word split is on letters, so "&" and ":" break the prefix into
  // two words and every R&A title drew the same tile. 30 of them on 2026-09-20.
  ra_two_words:        'R&A: Dry Leaf',
  ra_one_word:         'R&A: NOX',
  ra_finnish:          'R&A: Yön lapsi',
  ra_shorts:           'R&A Shorts: Silmäkarkkia',
  ra_spaced:           'R & A : Blue Film',
  ra_lowercase:        'r&a: mother of flies',
  ra_digits:           'R&A: 2 Fast',
  // The prefix must leave something behind, or the tile would read "?" for a title that
  // has letters in it.
  ra_only:             'R&A:',
  ra_only_spaced:      'R&A: ',
  // Untouched: an ordinary title, a franchise colon, a strand this list does not name.
  plain:               'Carrie',
  colon_franchise:     'Dyyni: Osa kolme',
  other_strand:        'Seniorikino: Hetki Ennen Valoa',
  // A title that merely starts with the letter R must not be mistaken for the prefix.
  r_word:              'Ran',
  rafiki:              'Rafiki: Ystavä',
  // Shapes the render path can hand it.
  empty:               '',
  null_title:          null,
  digits_only:         '2001',
  punctuation_only:    '---',
};

const out = {};
for (const [k, t] of Object.entries(cases)) {
  try {
    out[k] = f(t);
  } catch (e) {
    out[k] = { threw: String((e && e.message) || e) };
  }
}
process.stdout.write(JSON.stringify(out) + '\n');
