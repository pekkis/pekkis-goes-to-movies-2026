// Runs index.html's own priceLabel() against a table of price strings.
// Driven by tests/test_price_label.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own. It takes a list of shows and returns a string, so it needs no DOM; it reads
// `L[state.lang].from`, which the sandbox supplies with the three real translations so
// the localisation is exercised rather than stubbed away.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- priceLabel: pure, extracted verbatim by tests/price_label_harness.js ---';
const END = '// --- end priceLabel ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('priceLabel markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/function priceLabel\s*\(/.test(source)) {
  console.error('marker block does not contain priceLabel');
  process.exit(2);
}

// The real strings, read out of index.html rather than retyped, so a change to a
// translation shows up here instead of passing against a stale copy.
function translation(lang, key = 'from') {
  const at = HTML.indexOf(`\n    ${lang}:{`);
  if (at === -1) { console.error('no L block for ' + lang); process.exit(2); }
  const m = HTML.slice(at).match(new RegExp(key + ":'([^']*)'"));
  if (!m) { console.error('no `' + key + '` in the ' + lang + ' block'); process.exit(2); }
  return JSON.parse('"' + m[1] + '"');
}
const L = {};
for (const lang of ['fi', 'sv', 'en'])
  L[lang] = { from: translation(lang), free: translation(lang, 'free') };

const sandbox = { L, state: { lang: 'fi' } };
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__fn = priceLabel;', sandbox, { filename: 'priceLabel' });
const priceLabel = sandbox.__fn;

const rows = prices => prices.map(p => ({ price: p }));

// [name, lang, [price strings]]
const CASES = [
  // -- the defect: a source that publishes its own floor ----------------------------
  ['orion_floor_only',      'fi', ['alkaen 10€']],
  ['orion_floor_repeated',  'fi', ['alkaen 10€', 'alkaen 10€', 'alkaen 10€']],
  ['orion_floor_twelve',    'fi', ['alkaen 12€']],
  ['orion_real_mix',        'fi', ['alkaen 10€', '10€', '8.5€']],
  // -- what already worked and must keep working ------------------------------------
  ['exact_single',          'fi', ['13€']],
  ['exact_repeated',        'fi', ['13€', '13€']],
  ['two_amounts',           'fi', ['13€', '10€']],
  ['decimal_comma',         'fi', ['8,50€']],
  ['decimal_point',         'fi', ['8.50€']],
  ['whole_from_decimal',    'fi', ['12,00€']],
  ['spaced_currency',       'fi', ['13 €']],
  ['nbsp_currency',         'fi', ['13 €']],
  // -- nothing to say ----------------------------------------------------------------
  ['empty_list',            'fi', []],
  ['no_prices',             'fi', ['', null, undefined]],
  ['words_only',            'fi', ['Vapaa pääsy']],
  ['zero',                  'fi', ['0€']],
  ['negative',              'fi', ['-5€']],
  ['mixed_free_and_priced', 'fi', ['Vapaa pääsy', '10€']],
  // -- a source's own free-admission label, localised; nothing else reads as free -------
  ['free_fi',               'fi', ['Vapaa pääsy']],
  ['free_from_english',     'fi', ['Free']],
  ['free_en',               'en', ['Vapaa pääsy']],
  ['free_sv',               'sv', ['Vapaa pääsy']],
  ['free_conditional',      'fi', ['Vapaa pääsy jäsenille']],
  ['free_word_in_title',    'fi', ['Free Solo']],
  ['free_negated',          'fi', ['Ei vapaa pääsy']],
  // -- the prefix is localised --------------------------------------------------------
  ['floor_fi',              'fi', ['alkaen 10€']],
  ['floor_sv',              'sv', ['från 10€']],
  ['floor_en',              'en', ['from 10€']],
  ['range_fi',              'fi', ['13€', '10€']],
  ['range_sv',              'sv', ['13€', '10€']],
  ['range_en',              'en', ['13€', '10€']],
  // -- Finnish typography is Finnish only -----------------------------------------------
  ['decimal_sv',            'sv', ['8.5€']],
  ['decimal_en',            'en', ['8.5€']],
];

const out = {};
for (const [name, lang, prices] of CASES) {
  sandbox.state.lang = lang;
  out[name] = priceLabel(rows(prices));
}
out.__from = { fi: L.fi.from, sv: L.sv.from, en: L.en.from };
out.__free = { fi: L.fi.free, sv: L.sv.free, en: L.en.free };
process.stdout.write(JSON.stringify(out));
