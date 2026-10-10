// Runs index.html's own safeUrl() and safeAssetUrl() against a table of hostile and
// ordinary URLs. Driven by tests/test_safe_url.py; prints one JSON line.
//
// The two sinks are sliced verbatim out of index.html between their marker comments and
// evaluated on their own. They are pure -- a string in, a string out -- so they need no
// DOM, and the alternative would have been either stubbing the whole app or splitting
// the single file, which the repo deliberately does not do. If the markers are ever
// removed the harness fails loudly rather than silently testing nothing.
//
// Every accepted result is then resolved the way a browser resolves an href, with
// node's WHATWG URL parser, and the protocol it lands on is reported alongside. That
// second step is the point of the whole harness: the bug it was written for was a
// disagreement between the string the function tested and the URL a browser built out
// of it, so a test that only re-read the function's own regex would have passed.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- url sinks: pure, extracted verbatim by tests/safe_url_harness.js ---';
const END = '// --- end url sinks ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('url sink markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
for (const name of ['safeUrl', 'safeUrlRaw', 'safeAssetUrl', 'esc']) {
  if (!new RegExp('const ' + name + '\\s*=').test(source)) {
    console.error('marker block does not contain ' + name);
    process.exit(2);
  }
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__u = safeUrl; globalThis.__a = safeAssetUrl;'
                + 'globalThis.__r = safeUrlRaw;',
                sandbox, { filename: 'urlSinks' });
const safeUrl = sandbox.__u;
const safeAssetUrl = sandbox.__a;
const safeUrlRaw = sandbox.__r;

// Written as char codes so no literal control byte sits in this file, where an editor
// would hide it and a diff would not show it.
const C = n => String.fromCharCode(n);
const LF = C(10), CR = C(13), TAB = C(9), NUL = C(0), VT = C(11), DEL = C(127);

const BASE = 'https://leffavuoro.fi/';

// The five entities esc() writes, undone the way a browser undoes them when it reads
// the attribute back. None of them can change a scheme; this only keeps `resolved`
// readable and the query strings honest.
const unesc = s => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
                    .replace(/&quot;/g, '"').replace(/&#39;/g, "'");

// [name, which function, input]
const CASES = [
  // -- the reported hole, and the fourth payload found while reproducing it ----------
  ['js_plain',        'url', 'javascript:alert(1)'],
  ['js_lf',           'url', 'java' + LF + 'script:alert(1)'],
  ['js_cr',           'url', 'java' + CR + 'script:alert(1)'],
  ['js_tab',          'url', 'java' + TAB + 'script:alert(1)'],
  ['js_leading_nul',  'url', NUL + 'javascript:alert(1)'],
  ['js_crlf',         'url', 'java' + CR + LF + 'script:alert(1)'],
  ['js_many_lf',      'url', 'j' + LF + 'a' + LF + 'v' + LF + 'a' + LF + 'script:alert(1)'],
  ['js_trailing_del', 'url', 'javascript:alert(1)' + DEL],
  // trim() removes a vertical tab, so this one never reached the scheme test at all;
  // here to show the trim and the control check do not overlap by accident.
  ['js_leading_vt',   'url', VT + 'javascript:alert(1)'],
  // -- schemes that were already refused, kept so a rewrite cannot lose them ---------
  ['js_mixed_case',   'url', 'JaVaScRiPt:alert(1)'],
  ['js_upper',        'url', 'JAVASCRIPT:alert(1)'],
  ['data_html',       'url', 'data:text/html,<img src=x onerror=alert(1)>'],
  ['vbscript',        'url', 'vbscript:msgbox(1)'],
  ['file_scheme',     'url', 'file:///etc/passwd'],
  // -- what a real ticket or trailer link looks like ---------------------------------
  ['https_plain',     'url', 'https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1'],
  ['http_plain',      'url', 'http://kinohirvi.fi/ohjelmisto'],
  ['https_upper',     'url', 'HTTPS://WWW.FINNKINO.FI/x'],
  ['https_amp',       'url', 'https://x.fi/a?b=1&c=2'],
  ['https_quote',     'url', 'https://x.fi/a?t="p"'],
  ['https_apostrophe','url', "https://x.fi/lippu/o'brien?d=1"],
  // An adapter leaving a newline on the end must still work: trim() runs first, so the
  // control check never sees it. This is the case that decides reject-vs-strip.
  ['https_trailing_lf',   'url', 'https://x.fi/a' + LF],
  ['https_surrounding_ws','url', '  https://x.fi/a  '],
  ['relative_page',   'url', 'teatteri/itis.html'],
  ['protocol_rel',    'url', '//www.finnkino.fi/x'],
  ['empty',           'url', ''],
  ['blank',           'url', '   '],
  ['null',            'url', null],
  ['undefined',       'url', undefined],
  // -- the raw sink: same rules, no HTML escaping, for the calendar file -------------
  // Paired with the `https_*` cases above on the same inputs, so a test can assert the
  // two differ only in the escaping.
  ['raw_amp',         'raw', 'https://x.fi/a?b=1&c=2'],
  ['raw_apostrophe',  'raw', "https://x.fi/lippu/o'brien?d=1"],
  ['raw_quote',       'raw', 'https://x.fi/a?t="p"'],
  ['raw_plain',       'raw', 'https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1'],
  ['raw_relative',    'raw', 'teatteri/itis.html'],
  ['raw_js',          'raw', 'javascript:alert(1)'],
  ['raw_js_lf',       'raw', 'java' + LF + 'script:alert(1)'],
  ['raw_js_leading_nul', 'raw', NUL + 'javascript:alert(1)'],
  ['raw_data_html',   'raw', 'data:text/html,<img src=x onerror=alert(1)>'],
  ['raw_trailing_lf', 'raw', 'https://x.fi/a' + LF],
  ['raw_empty',       'raw', ''],
  // -- the poster sink: same control rule, and its own path allowlist ---------------
  ['asset_ok',            'asset', 'data/posters/tt1234.jpg'],
  ['asset_dot_slash',     'asset', './data/posters/tt1234.jpg'],
  ['asset_root_slash',    'asset', '/data/posters/tt1234.jpg'],
  ['asset_third_party',   'asset', 'https://image.tmdb.org/t/p/w500/x.jpg'],
  ['asset_protocol_rel',  'asset', '//image.tmdb.org/x.jpg'],
  ['asset_outside_dir',   'asset', 'data/other/x.jpg'],
  ['asset_js',            'asset', 'javascript:alert(1)'],
  ['asset_js_lf',         'asset', 'java' + LF + 'script:alert(1)'],
  ['asset_lf_inside',     'asset', 'data/posters/tt' + LF + '1234.jpg'],
  ['asset_lf_in_prefix',  'asset', 'data' + LF + '/posters/tt1234.jpg'],
  ['asset_empty',         'asset', ''],
];

const out = {};
for (const [name, which, raw] of CASES) {
  const got = which === 'url' ? safeUrl(raw)
            : which === 'raw' ? safeUrlRaw(raw) : safeAssetUrl(raw);
  const rec = { out: got, accepted: got !== '' };
  if (rec.accepted) {
    try {
      const url = new URL(unesc(got), BASE);
      rec.proto = url.protocol;
      rec.resolved = url.href;
      rec.sameOrigin = url.origin === new URL(BASE).origin;
    } catch (e) {
      rec.proto = 'PARSE_ERROR';
      rec.resolved = '';
      rec.sameOrigin = false;
    }
  }
  out[name] = rec;
}
process.stdout.write(JSON.stringify(out));
