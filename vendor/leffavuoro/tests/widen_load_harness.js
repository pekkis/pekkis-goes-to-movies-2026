// Drives index.html's selectVenue(), loadSchedule(), selectDay() and widenTo() together,
// against stubbed DOM and data, to pin what a wider search does to the selected day.
//
// The functions are sliced verbatim out of index.html on their own first lines and the
// comment that follows each. Everything they touch outside themselves is a stub here:
// the schedule payloads, the prefs store, the picker, the day chips, the renderers. What
// it pins: a wider search keeps the selected day through the load even when the wider
// scope has nothing on it, on a fetch and on a cache hit; a plain pick from the venue
// list still advances as before; search, chips, chain restriction, view and the starred
// venue are untouched by either. The late-evening advance moves the day without tracking
// `date_changed` or saving it; a reader's own choice through selectDay() does both.
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
const SEL = slice('  function selectVenue(id, opts){', '  function syncVenueBtn(){', 'selectVenue');
const DAY = slice('  function selectDay(iso){', '  // The venue ids behind a combined view', 'selectDay');
const LOAD = slice('  async function loadSchedule(opts){', '  // Stale banner and footer credit', 'loadSchedule');
const WIDEN = slice('  function widenTo(id){', '  // What an empty list offers', 'widenTo');
for (const [src, fn] of [[SEL, 'selectVenue'], [DAY, 'selectDay'], [LOAD, 'loadSchedule'], [WIDEN, 'widenTo']]) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(src)) {
    console.error('slice does not contain ' + fn);
    process.exit(2);
  }
}

const PRELUDE = `
  const fiToday = () => fiDate(new Date());
  const calls = [];
  const prefsStore = {};
  const prefs = { get(){ return Object.assign({}, prefsStore); },
                  set(p){ Object.assign(prefsStore, p); } };
  let state = {};
  const jsonCache = {};
  let lastLoad = 0;
  const swFilled = () => {};   // the worker's replay of an early refresh; tested in swr_refresh_harness.js
  const location = { search: '', hash: '' };
  const areaParamAfterSelect = () => null;
  const replaceQuery = () => {};
  const pushQuery = () => {};
  let homeNote = '', loadSeq = 0;
  const syncSheet = () => {};
  const document = { documentElement: { classList: { add(){}, remove(){}, contains(){ return true; } } } };
  const syncFav = () => calls.push('syncFav');
  const syncVenueBtn = () => calls.push('syncVenueBtn');
  const setListStatus = () => {};
  const main = { innerHTML: '' };
  const L = { fi: { loadingSchedule: 'Ladataan' } };
  const venueIndex = { v1: { id: 'v1', provider: 'finnkino' }, v2: { id: 'v2', provider: 'gilda' } };
  const GROUPS = { 'city:C': ['v1', 'v2'] };
  const groupIdsOf = (a) => GROUPS[a] || null;
  let payloads = {};
  const fetchJSON = async (url) => { calls.push('fetch ' + url); return payloads[url]; };
  const loadGroup = async (area) => { calls.push('group ' + area); return payloads[area]; };
  const render = () => calls.push('render');
  const renderTagKey = () => {};
  const renderStatus = () => {};
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
  const areaSel = { focus(){ calls.push('focus areaSelect'); } };
`;
const EXPORT = `
  globalThis.__api = {
    reset(st, pr, pay){ state = st; for (const k of Object.keys(prefsStore)) delete prefsStore[k];
                        Object.assign(prefsStore, pr); payloads = pay;
                        for (const k of Object.keys(jsonCache)) delete jsonCache[k]; calls.length = 0; },
    state: () => state, prefs: () => Object.assign({}, prefsStore), calls: () => calls.slice(),
    cache: jsonCache, widenTo, selectVenue, selectDay, fiDate, fiToday,
  };
`;
const sandbox = { Date, Array, Object, Set, Map, Promise, isNaN, console };
vm.createContext(sandbox);
// Recorded by name only: which events a path sends. What is sent and whether it may be
// is tests/test_analytics_privacy.py's.
const tracked = [];
sandbox.track = (name) => { tracked.push(name); };

vm.runInContext(HELPERS + PRELUDE + SEL + DAY + LOAD + WIDEN + EXPORT, sandbox, { filename: 'widenLoad' });
const api = sandbox.__api;

const today = api.fiToday();
const plusDays = (iso, n) => {
  const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const tomorrow = plusDays(today, 1);
const at = (iso, hhmm) => iso + 'T' + hhmm + ':00+03:00';
const show = (iso, hhmm, provider) => ({ title: 'Zzzz', start: at(iso, hhmm), provider, eventId: 'e' });

const venueToday = { generated: 'g', dates: [today, tomorrow],
  shows: [show(today, '18:00', 'finnkino'), show(tomorrow, '18:00', 'finnkino')] };
// The wider scope has nothing on today's date at all: the late-evening rule would move
// the day on a plain load.
const cityTomorrowOnly = { generated: 'g', dates: [tomorrow],
  shows: [show(tomorrow, '17:00', 'finnkino'), show(tomorrow, '19:00', 'gilda')] };
const cityBothDays = { generated: 'g', dates: [today, tomorrow],
  shows: [show(today, '17:00', 'gilda'), show(tomorrow, '19:00', 'finnkino')] };

const fresh = () => ({ area: 'v1', dateStr: today, shows: [], filter: 'Zzzz', lang: 'fi',
  view: 'times', fLang: false, fKids: true, fAnnis: false, advanced: false,
  chains: new Set(['finnkino']), revealed: new Set(), dates: [today, tomorrow] });
const reset = (...a) => { tracked.length = 0; api.reset(...a); };
const snap = () => {
  const s = api.state(); const p = api.prefs();
  return { area: s.area, dateStr: s.dateStr, advanced: s.advanced, filter: s.filter,
           chains: s.chains ? [...s.chains] : null, fKids: s.fKids, view: s.view,
           shows: s.shows.length, fav: p.fav, prefArea: p.area, prefDay: p.day,
           renders: api.calls().filter((c) => c === 'render').length,
           focused: api.calls().includes('focus areaSelect'), calls: api.calls(),
           tracked: tracked.slice() };
};
const out = { today, tomorrow };

(async () => {
  // 1. widen to a scope with nothing today: the day stays, the empty state renders
  reset(fresh(), { fav: 'v1', area: 'v1' }, { 'city:C': cityTomorrowOnly });
  await api.widenTo('city:C');
  out.widen_nothing_today = snap();

  // 2. the same load as a plain pick from the venue list: advances as before
  reset(fresh(), { fav: 'v1', area: 'v1' }, { 'city:C': cityTomorrowOnly });
  await api.selectVenue('city:C');
  out.pick_nothing_today = snap();

  // 3. widen to a scope that has shows today: nothing to advance, the day stays
  reset(fresh(), { fav: 'v1', area: 'v1' }, { 'city:C': cityBothDays });
  await api.widenTo('city:C');
  out.widen_shows_today = snap();

  // 4. cache hit: the synchronous path through loadSchedule
  reset(fresh(), { fav: 'v1', area: 'v1' }, {});
  api.cache['city:C'] = cityTomorrowOnly;
  await api.widenTo('city:C');
  out.widen_cached = snap();

  // 5. a plain pick with the day already chosen by hand keeps it (unchanged rule)
  const st = fresh(); st.advanced = true;
  reset(st, { fav: 'v1', area: 'v1' }, { 'city:C': cityTomorrowOnly });
  await api.selectVenue('city:C');
  out.pick_after_manual_day = snap();

  // 6. widenTo refuses an id the picker does not know
  reset(fresh(), { fav: 'v1', area: 'v1' }, {});
  await api.widenTo('city:Nowhere');
  out.widen_unknown = snap();

  // 7. a reader choosing a day: tracked and saved, as before
  reset(fresh(), { fav: 'v1', area: 'v1' }, { v1: venueToday });
  api.cache.v1 = venueToday;
  await api.selectDay(tomorrow);
  out.reader_picks_day = snap();

  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
