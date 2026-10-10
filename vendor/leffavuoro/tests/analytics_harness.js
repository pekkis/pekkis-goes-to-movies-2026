// Runs a file's own analyticsScrub() against the table tests/test_analytics_privacy.py
// sends on stdin, plus fixed probes, and prints one JSON line. The file is the first
// argument, relative to the repository root: index.html (the default) or pageview.js.
//
// Sliced verbatim out of that file between its marker comments. It takes a posthog
// CaptureResult and returns one or null, so it needs no DOM and no network.
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

const watchdog = setTimeout(() => bail('timed out after 20s'), 20000);
watchdog.unref();

// The 43 posthog-js 1.434.2 attaches before before_send, as observed on the wire on
// 2026-09-20. Listed here so the strip probe exercises the real shape.
const LIB_PROPS = ['$os', '$os_version', '$browser', '$device_type', '$timezone',
  '$timezone_offset', '$current_url', '$host', '$pathname', '$raw_user_agent',
  '$browser_version', '$browser_language', '$browser_language_prefix', '$screen_height',
  '$screen_width', '$viewport_height', '$viewport_width', '$lib', '$lib_version',
  '$insert_id', '$time', '$sdk_dist_channel', '$initialization_time', '$device_id',
  '$referrer', '$referring_domain', '$config_defaults', '$cookieless_mode',
  '$is_identified', '$process_person_profile', '$initial_person_info',
  '$autocapture_disabled_server_side', '$web_vitals_enabled_server_side',
  '$exception_capture_enabled_server_side', '$dead_clicks_enabled_server_side'];

let out;
try {
  const SRC = process.argv[2] || 'index.html';
  const HTML = fs.readFileSync(path.join(__dirname, '..', SRC), 'utf8');
  const START = '// --- analyticsScrub: pure, extracted verbatim by tests/analytics_harness.js ---';
  const END = '// --- end analyticsScrub ---';
  const a = HTML.indexOf(START);
  const b = HTML.indexOf(END);
  if (a === -1 || b === -1 || b < a) bail('analyticsScrub markers not found in ' + SRC);
  const source = HTML.slice(a, b);
  if (!/function analyticsScrub\s*\(/.test(source)) bail('marker block does not contain analyticsScrub');
  if (!/const PH_ALLOW\s*=/.test(source)) bail('marker block does not contain PH_ALLOW');

  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(source + '\n;globalThis.__fn = analyticsScrub;'
    + 'globalThis.__allow = Object.keys(PH_ALLOW); globalThis.__cats = PH_CATEGORIES.slice();',
    sandbox, { filename: 'analyticsScrub' });
  const scrub = sandbox.__fn;

  // The origin guard, sliced from its own markers and run in the same way.
  const GS = '// --- phAllowedOrigin: pure, extracted verbatim by tests/analytics_harness.js ---';
  const GE = '// --- end phAllowedOrigin ---';
  const ga = HTML.indexOf(GS), gb = HTML.indexOf(GE);
  if (ga === -1 || gb === -1 || gb < ga) bail('phAllowedOrigin markers not found in ' + SRC);
  const gsrc = HTML.slice(ga, gb);
  if (!/function phAllowedOrigin\s*\(/.test(gsrc)) bail('marker block does not contain phAllowedOrigin');
  const gbox = {};
  vm.createContext(gbox);
  vm.runInContext(gsrc + '\n;globalThis.__g = phAllowedOrigin;', gbox, { filename: 'phAllowedOrigin' });
  const allowed = gbox.__g;

  const run = (event, properties, extra) => {
    const e = Object.assign({ event, properties: Object.assign({}, properties) }, extra || {});
    const r = scrub(e);
    return r ? r.properties : null;
  };

  out = {};
  for (const c of JSON.parse(fs.readFileSync(0, 'utf8'))) {
    try { out[c.name] = run(c.event, c.properties); }
    catch (e) { out[c.name] = { threw: String((e && e.message) || e) }; }
  }

  // Every library property set to a marker value, so anything surviving is visible.
  const leak = {};
  for (const k of LIB_PROPS) leak[k] = 'LEAK-' + k;
  leak.venue = 'v';
  out._stripprobe = run('cinema_opened', leak);

  // The pair the SDK needs to build a request at all.
  out._mandatory = run('cinema_opened', { venue: 'v', token: 'phc_x', distinct_id: '$posthog_cookieless' });

  // The same two probes on $pageview, the one event both files send, with the file's
  // first category. Every library property is planted, $current_url and $pathname with a
  // title and a query, so the synthetic URL has to replace them rather than pass them on.
  out._allow = sandbox.__allow.slice();
  out._categories = sandbox.__cats.slice();
  const pvleak = Object.assign({}, leak, {
    $current_url: 'https://leffavuoro.fi/teatteri/kino-x/?q=Carrie&title=Carrie',
    $pathname: '/teatteri/kino-x/', title: 'Carrie | Kino X', $referrer: 'https://example.com/?q=Carrie',
    category: out._categories[0] });
  delete pvleak.venue;
  out._pvstripprobe = run('$pageview', pvleak);
  out._pvmandatory = run('$pageview', { category: out._categories[0], token: 'phc_x',
                                        distinct_id: '$posthog_cookieless' });

  // The origin guard, over every shape that must be refused.
  out._origins = {};
  for (const [name, proto, host] of [
    ['prod_https', 'https:', 'leffavuoro.fi'],
    ['prod_http', 'http:', 'leffavuoro.fi'],
    ['localhost_http', 'http:', 'localhost'],
    ['localhost_https', 'https:', 'localhost'],
    ['loopback_v4', 'http:', '127.0.0.1'],
    ['loopback_v6', 'http:', '[::1]'],
    ['file_url', 'file:', ''],
    ['gh_pages', 'https:', 'shady-dev.github.io'],
    ['gh_preview', 'https:', 'kino-preview.github.io'],
    ['www_prefix', 'https:', 'www.leffavuoro.fi'],
    ['suffix_attack', 'https:', 'leffavuoro.fi.evil.example'],
    ['prefix_attack', 'https:', 'notleffavuoro.fi'],
    ['unrelated', 'https:', 'example.com'],
    ['empty_host', 'https:', ''],
  ]) out._origins[name] = allowed(proto, host);

  // $set / $set_once must not survive.
  const e = { event: '$pageview', properties: { category: out._categories[0] },
              $set: { a: 1 }, $set_once: { b: 2 } };
  const r = scrub(e);
  out._setprobe = { set: (r && r.$set) !== undefined ? (r.$set || null) : null,
                    set_once: (r && r.$set_once) !== undefined ? (r.$set_once || null) : null };
} catch (e) {
  bail(String((e && e.stack) || e));
}
clearTimeout(watchdog);
process.stdout.write(JSON.stringify(out) + '\n');
