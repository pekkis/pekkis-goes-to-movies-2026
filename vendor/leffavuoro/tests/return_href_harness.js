// Runs the real "way back" decision out of status/index.html and prints one JSON line of
// results. Driven by tests/test_return_href.py.
//
// `internalPath` and `returnHref` are pure by construction -- they read four values and a
// string origin, render no DOM and touch no globals -- so the block is extracted verbatim
// between its markers and run in a bare vm context, the technique
// tests/synopsis_lang_harness.js and tests/venue_picker_harness.js already use. Which
// element gets the href, and the label beside it, are DOM plumbing and stay verified live.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'status', 'index.html'), 'utf8');
const START = '// --- return link: pure, extracted verbatim by tests/return_href_harness.js ---';
const END = '// --- end return link ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('return link markers not found in status/index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
for (const fn of ['internalPath', 'returnHref']) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(source)) {
    console.error('marker block does not contain ' + fn);
    process.exit(2);
  }
}

// URL and URLSearchParams are the platform's, not the page's; a bare context has neither.
const sandbox = { URL, URLSearchParams };
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__r = returnHref;\n;globalThis.__p = internalPath;',
                sandbox, { filename: 'returnHref' });
const returnHref = sandbox.__r;
const internalPath = sandbox.__p;

const ORIGIN = 'https://leffavuoro.fi';
const LANGS = ['fi', 'sv', 'en'];
const SCREENING = '/?area=engel-helsinki&lang=sv#m=abc&d=2026-09-28&t=2026-09-28T16%3A30%3A00%2B03%3A00&v=engel';

// Two of everything the page can be opened with, so no loop is entered once.
const CASES = {
  // no return URL at all: the area link, in each language
  area_fi:      ['engel-helsinki', 'fi', ''],
  area_sv:      ['engel-helsinki', 'sv', ''],
  area_en:      ['engel-helsinki', 'en', ''],
  city_area:    ['city:Helsinki', 'en', ''],
  no_area:      ['', 'en', ''],
  unknown_lang: ['engel-helsinki', 'de', ''],
  // a screening to return to
  back_fi:      ['engel-helsinki', 'fi', SCREENING],
  back_en:      ['engel-helsinki', 'en', SCREENING],
  back_no_lang: ['engel-helsinki', 'en', '/?area=engel-helsinki#m=abc'],
  back_no_area: ['', 'sv', SCREENING],
  // a return URL that is not this origin's
  other_host:   ['engel-helsinki', 'en', 'https://example.invalid/steal'],
  protocol_rel: ['engel-helsinki', 'en', '//example.invalid/steal'],
  javascript:   ['engel-helsinki', 'en', 'javascript:alert(1)'],
  data_url:     ['engel-helsinki', 'en', 'data:text/html,<script>x</script>'],
  nonsense:     ['engel-helsinki', 'en', 'http://['],
  same_host:    ['engel-helsinki', 'en', 'https://leffavuoro.fi/?area=x#m=y'],
};

const out = { href: {}, path: {} };
for (const [name, [area, lang, back]] of Object.entries(CASES)) {
  out.href[name] = returnHref(area, lang, LANGS, back, ORIGIN);
  out.path[name] = internalPath(back, ORIGIN);
}
out.__ran = true;
process.stdout.write(JSON.stringify(out));
