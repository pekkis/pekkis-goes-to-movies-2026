// Drives index.html's chooser flow: selectVenue(), loadSchedule(), showHome(), onPopState()
// and the <head> script that decides the first paint, against stubbed DOM, history and
// data. Driven by tests/test_home_flow.py; prints one JSON line.
//
// Sliced verbatim out of index.html on their own first lines, the way widen_load_harness
// does. renderHome() is the one thing stubbed out of the chooser block: it relabels the
// static list through the DOM, which the static test covers from the markup side.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function slice(start, end, name) {
  const a = HTML.indexOf(start);
  const b = HTML.indexOf(end, a);
  if (a === -1 || b === -1 || b < a) {
    console.error(name + ' anchors not found in index.html');
    process.exit(2);
  }
  return HTML.slice(a, b);
}
const HELPERS = HTML.slice(HTML.indexOf("  const FI_TZ = 'Europe/Helsinki';"),
                           HTML.indexOf('  const fiToday = () => fiDate(new Date());'));
const ROUTING = slice('  // --- area routing: pure, extracted verbatim', '  // --- end area routing ---', 'routing');
const QUERY = slice('  function replaceQuery(q){', '  // --- the chooser: what / is with no location', 'query');
const KNOWN = slice('  function knownArea(id){', '  // Relabels and relinks the static chooser', 'knownArea');
const HOME = slice('  function showHome(note){', '  window.addEventListener(\'popstate\', onPopState);', 'showHome');
const SEL = slice('  // A Back/Forward entry already names its area', '  function syncVenueBtn(){', 'selectVenue');
const DAY = slice('  function selectDay(iso){', '  // The venue ids behind a combined view', 'selectDay');
const LOAD = slice('  async function loadSchedule(opts){', '  // Stale banner and footer credit', 'loadSchedule');
for (const [src, fn] of [[KNOWN, 'knownArea'], [HOME, 'showHome'], [HOME, 'onPopState'], [HOME, 'bootFallback'],
                         [SEL, 'selectVenue'], [LOAD, 'loadSchedule'], [ROUTING, 'areaParamAfterSelect']]) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(src)) {
    console.error('slice does not contain ' + fn);
    process.exit(2);
  }
}
const EARLY = (HTML.match(/<script>(\(function\(\)\{var d=document\.documentElement;[\s\S]*?)<\/script>/) || [])[1];
if (!EARLY) { console.error('early script not found'); process.exit(2); }

const PRELUDE = `
  const fiToday = () => fiDate(new Date());
  const calls = [];
  const prefsStore = {};
  const prefs = { get(){ return Object.assign({}, prefsStore); },
                  set(p){ calls.push('prefs.set ' + JSON.stringify(p)); Object.assign(prefsStore, p); } };
  let state = {};
  const jsonCache = {};
  let lastLoad = 0;
  const swFilled = () => {};   // the worker's replay of an early refresh; tested in swr_refresh_harness.js
  const location = { href: 'https://leffavuoro.fi/', search: '', hash: '' };
  const apply = (url) => { const u = new URL(url, 'https://leffavuoro.fi/'); location.href = u.href; location.search = u.search; location.hash = u.hash; };
  const history = { pushState(_s, _t, url){ calls.push('push ' + url); apply(url); },
                    replaceState(_s, _t, url){ calls.push('replace ' + url); apply(url); } };
  const classes = new Set();
  const document = { documentElement: { classList: {
    add(c){ classes.add(c); calls.push('class+' + c); }, remove(c){ classes.delete(c); calls.push('class-' + c); },
    contains(c){ return classes.has(c); } } } };
  const HOME_TEMPLATE = '<section id="home">HOME</section>';
  let homeNote = '', unknownDeep = false, loadSeq = 0;
  const renderHome = () => calls.push('renderHome ' + homeNote);
  const syncFav = () => calls.push('syncFav');
  const syncVenueBtn = () => calls.push('syncVenueBtn');
  const syncSheet = () => calls.push('syncSheet');
  // The movie sheet is modal, and onPopState closes it: a traversal that changes the
  // area and the fragment at once fires popstate and no hashchange, so this is the
  // only thing that reconciles it with the URL. Logged, so the order is visible.
  const hideSheet = () => calls.push('hideSheet');
  const setListStatus = () => {};
  const main = { innerHTML: '' };
  const L = { fi: { loadingSchedule: 'Ladataan', homeUnknown: 'EI LÖYTYNYT' } };
  const allVenues = [{ id: 'v1' }, { id: 'v2' }];
  const venueIndex = { v1: { id: 'v1', provider: 'finnkino' }, v2: { id: 'v2', provider: 'gilda' } };
  const GROUPS = { 'city:C': ['v1', 'v2'] };
  const groupIdsOf = (a) => GROUPS[a] || null;
  let payloads = {};
  const fetchJSON = (url) => { calls.push('fetch ' + url); return Promise.resolve(payloads[url]).then(p => typeof p === 'function' ? p() : p); };
  const loadGroup = (area) => { calls.push('group ' + area); return Promise.resolve(payloads[area]); };
  const render = () => { calls.push('render'); main.innerHTML = '<div class="shows">' + state.area + '</div>'; };
  const renderTagKey = () => {};
  const renderStatus = () => calls.push('renderStatus');
  const searchEl = null;
  const searchHint = () => '';
  const netErrorHtml = (e) => 'ERR ' + e;
  const daysEl = { children: [] };
  const dayBtns = {};
  const calChip = { innerHTML: '', classList: { add(){}, remove(){} } };
  const resetCalChip = () => {};
  const fiDay = ['Su','Ma','Ti','Ke','To','Pe','La'];
  const dowOf = () => 0;
  const dmOf = () => '';
`;
const EXPORT = `
  globalThis.__api = {
    reset(st, pr, pay, url, scoped){ state = st; for (const k of Object.keys(prefsStore)) delete prefsStore[k];
      Object.assign(prefsStore, pr); payloads = pay; apply(url || 'https://leffavuoro.fi/');
      classes.clear(); if (scoped) classes.add('scoped'); homeNote = ''; main.innerHTML = st.area ? 'SHOWS' : HOME_TEMPLATE;
      for (const k of Object.keys(jsonCache)) delete jsonCache[k]; calls.length = 0; },
    state: () => state, prefs: () => Object.assign({}, prefsStore), calls: () => calls.slice(),
    main: () => main.innerHTML, classes: () => [...classes], location: () => Object.assign({}, location),
    homeNote: () => homeNote, cache: jsonCache, selectVenue, showHome, onPopState, bootFallback, loadSchedule, fiToday,
  };
`;
const sandbox = { Date, Array, Object, Set, Map, Promise, isNaN, console, URL, URLSearchParams, Intl };
vm.createContext(sandbox);
// selectVenue tracks the area it opens. Analytics is not what these tests are about,
// so it is stubbed; tests/test_analytics_privacy.py covers the real one.
sandbox.track = () => {};

vm.runInContext(HELPERS + PRELUDE + ROUTING + QUERY + KNOWN + HOME + SEL + DAY + LOAD + EXPORT, sandbox, { filename: 'homeFlow' });
const api = sandbox.__api;

const today = api.fiToday();
const at = (iso, hhmm) => iso + 'T' + hhmm + ':00+03:00';
const show = (iso, hhmm, provider) => ({ title: 'Zzzz', start: at(iso, hhmm), provider, eventId: 'e' });
const v1 = { generated: 'g', dates: [today], shows: [show(today, '18:00', 'finnkino')] };
const v2 = { generated: 'g', dates: [today], shows: [show(today, '19:00', 'gilda')] };
const home = () => ({ area: '', dateStr: today, shows: [], lang: 'fi', view: 'movies', advanced: false, chains: null, dates: null });
const scoped = (a) => ({ ...home(), area: a });
const snap = () => ({ area: api.state().area, main: api.main(), classes: api.classes(), search: api.location().search,
                      prefs: api.prefs(), homeNote: api.homeNote(), calls: api.calls() });
const out = { today };

(async () => {
  // 5. a pick from the chooser loads the screenings, writes ?area=, saves no favourite
  api.reset(home(), { fav: '' }, { 'data/area-v1.json': v1 }, 'https://leffavuoro.fi/');
  await api.selectVenue('v1');
  out.pick_from_home = snap();

  // a pick of the location already in the URL adds no history entry
  api.reset(scoped('v1'), { fav: '' }, { 'data/area-v1.json': v1 }, 'https://leffavuoro.fi/?area=v1', true);
  await api.selectVenue('v1');
  out.pick_same = snap();

  // 8. the reader goes back to the chooser while the schedule is still loading
  let release;
  const slow = new Promise(r => { release = r; });
  api.reset(home(), { fav: '' }, { 'data/area-v1.json': () => slow.then(() => v1) }, 'https://leffavuoro.fi/');
  const pending = api.selectVenue('v1');
  await Promise.resolve();                 // the fetch is in flight
  api.showHome();
  release();
  await pending;
  out.stale_load = snap();

  // the same, with the load failing after the reader has gone back: no error over the chooser
  let fail;
  const failing = new Promise((_, r) => { fail = r; });
  api.reset(home(), { fav: '' }, { 'data/area-v1.json': () => failing }, 'https://leffavuoro.fi/');
  const pending2 = api.selectVenue('v1');
  await Promise.resolve();
  api.showHome();
  fail(new Error('HTTP 503'));
  await pending2;
  out.stale_failure = snap();

  // a refresh with no location (tab focus, rollover, service-worker update) fetches and draws nothing
  api.reset(home(), { fav: '' }, { 'data/area-.json': v1 }, 'https://leffavuoro.fi/');
  await api.loadSchedule();
  out.refresh_on_chooser = snap();

  // Back from a location to /
  api.reset(scoped('v1'), { fav: '' }, {}, 'https://leffavuoro.fi/', true);
  api.onPopState();
  out.back_to_home = snap();

  // Back to / with a favourite stored: the favourite, as a visit to / gives, URL left bare
  api.reset(scoped('v2'), { fav: 'v1' }, { 'data/area-v1.json': v1 }, 'https://leffavuoro.fi/', true);
  api.onPopState();
  await new Promise(r => setTimeout(r, 0));
  out.back_to_home_with_fav = snap();

  // Forward from / to a known location: shown, nothing pushed
  api.reset(home(), { fav: '' }, { 'data/area-v2.json': v2 }, 'https://leffavuoro.fi/?area=v2');
  api.onPopState();
  await new Promise(r => setTimeout(r, 0));
  out.forward_to_area = snap();

  // a traversal whose venue file is slow, with the reader gone before it lands: the
  // entry's fragment must not reopen a sheet over wherever they are now
  let releaseSlow;
  const slowV2 = new Promise(r => { releaseSlow = r; });
  api.reset(scoped('v1'), { fav: '' },
            { 'data/area-v2.json': () => slowV2.then(() => v2) },
            'https://leffavuoro.fi/?area=v2#m=e', true);
  const travelling = api.onPopState();
  await Promise.resolve();               // the fetch is in flight
  api.showHome();                        // and the reader goes back to the chooser
  releaseSlow();
  await travelling;
  out.stale_sheet_after_move = snap();

  // the same load landing while the reader is still on the venue it named: honoured
  api.reset(scoped('v1'), { fav: '' }, { 'data/area-v2.json': v2 },
            'https://leffavuoro.fi/?area=v2#m=e', true);
  await api.onPopState();
  out.sheet_after_arrival = snap();

  // a history entry naming a location the list does not have: the chooser, with the note
  api.reset(scoped('v1'), { fav: '' }, {}, 'https://leffavuoro.fi/?area=zz', true);
  api.onPopState();
  out.popstate_unknown = snap();

  // a hash-only step (the film sheet) fires popstate too and must change nothing
  api.reset(scoped('v1'), { fav: '' }, {}, 'https://leffavuoro.fi/?area=v1#m=e', true);
  api.onPopState();
  out.popstate_hash_only = snap();

  // a film link with no location waits on the chooser, then opens in the chosen scope
  api.reset(home(), { fav: '' }, { 'data/area-v1.json': v1 }, 'https://leffavuoro.fi/#m=e');
  await api.selectVenue('v1');
  out.film_link_after_pick = snap();

  // a boot that fails before anything is on screen: the chooser, with the load-failure
  // line when a link or a favourite had asked for a location
  // The answer is the string's key: renderHome() draws it in the current language.
  out.boot_fallback = {
    fav_or_link_lists_failed: api.bootFallback('', true),
    nothing_asked_lists_failed: api.bootFallback('', false),
    location_already_shown: api.bootFallback('v1', true),
  };

  // the <head> script: what it decides, and that it never throws
  const early = (search, storage) => {
    const sb = { URLSearchParams, location: { search }, localStorage: storage,
                 document: { documentElement: { classList: { add(c){ sb.__added = c; } } } } };
    vm.createContext(sb);
    try { vm.runInContext(EARLY, sb); return { threw: false, scoped: sb.__added === 'scoped' }; }
    catch (e) { return { threw: true, scoped: false }; }
  };
  const store = (v) => ({ getItem(){ return v; } });
  const throwing = { getItem(){ throw new Error('storage unavailable'); } };
  out.early = {
    nothing: early('', store(null)),
    fav: early('', store(JSON.stringify({ fav: 'v1' }))),
    old_area_slot_only: early('', store(JSON.stringify({ area: 'v1' }))),
    url: early('?area=v2', store(null)),
    corrupt: early('', store('{not json')),
    storage_throws: early('', throwing),
    storage_throws_with_url: early('?area=v2', throwing),
  };
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
