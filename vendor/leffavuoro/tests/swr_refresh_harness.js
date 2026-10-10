// Drives index.html's own background-refresh handler -- what a `{fresh: path}` message
// from the service worker does to the page's payload cache -- and the city fold it
// compares with. Run by tests/test_swr_refresh.py; prints one JSON line.
//
// Two blocks are sliced verbatim out of index.html between their marker comments and
// evaluated together, the way healthState, venueRows and the area routing are: the city
// fold (`cityPayload`, `mergeIds`) and the refresh handler (`refreshKey`, `readCached`,
// `makeFreshHandler`). The handler is a function of the `io` object it is built with --
// the current selection, the payload cache, the city groups and the readers -- so every
// one of those is a stub here and the shipped decision runs against them. Where a
// scenario needs "the reader switched cinema during the await", the read is a promise the
// scenario settles by hand; where it needs the copy the worker just cached, `caches` is a
// stub store and the real readCached() reads it. The sandbox has no fetch on purpose: a
// re-read that reached for the network would be the message loop coming back.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function slice(start, end, mustHave) {
  const a = HTML.indexOf(start);
  const b = HTML.indexOf(end);
  if (a === -1 || b === -1 || b < a) {
    console.error(`markers not found in index.html: ${start}`);
    process.exit(2);
  }
  const src = HTML.slice(a, b);
  for (const fn of mustHave) {
    if (!new RegExp('function ' + fn + '\\s*\\(').test(src)) {
      console.error('marker block does not contain ' + fn);
      process.exit(2);
    }
  }
  return src;
}

const FOLD = slice('// --- city fold: pure, extracted verbatim by tests/swr_refresh_harness.js ---',
                   '// --- end city fold ---', ['cityPayload', 'mergeIds']);
const META = slice('// --- film metadata store: pure, extracted verbatim by tests/swr_refresh_harness.js ---',
                   '// --- end film metadata store ---', ['readCached', 'makeExtraStore']);
const HANDLER = slice('// --- background refresh: pure, extracted verbatim by tests/swr_refresh_harness.js ---',
                      '// --- end background refresh ---', ['refreshKey', 'makeFreshHandler']);

// What `caches.match` answers with, by relative path -- the copy the worker put there.
const store = new Map();
const sandbox = {
  caches: {
    match: async p => store.has(p) ? { json: async () => clone(store.get(p)) } : undefined,
  },
};
vm.createContext(sandbox);
vm.runInContext(FOLD + '\n' + META + '\n' + HANDLER +
                '\n;globalThis.__mk = makeFreshHandler; globalThis.__fold = cityPayload;' +
                ' globalThis.__rc = readCached; globalThis.__key = refreshKey;' +
                ' globalThis.__store = makeExtraStore;',
                sandbox, { filename: 'backgroundRefresh' });
const makeFreshHandler = sandbox.__mk;
const cityPayload = sandbox.__fold;
const readCached = sandbox.__rc;
const refreshKey = sandbox.__key;
const makeExtraStore = sandbox.__store;

function clone(x) { return JSON.parse(JSON.stringify(x)); }

// A payload the way an area file arrives: `generated` and the shows. The show list is
// what proves which cinema's programme ended up in a slot.
const payload = (venue, generated, title) => ({
  generated,
  dates: ['2026-09-05'],
  shows: [{ title: title || `Film at ${venue}`, start: '2026-09-05T18:00:00+03:00',
            theatre: venue, eventId: `${venue}-1` }],
});

// The two-member city every city scenario uses, keyed the way the page keys a combined
// view: the whole area string, so a city and an area resolve through one map. The fold
// needs the venue index for the member names and providers, and a merge key; the
// identity rule is not under test here.
const GROUPS = { 'city:X': ['a', 'b'] };
const VENUES = {
  a: { id: 'a', provider: 'p1', short: 'A', label: 'Chain A' },
  b: { id: 'b', provider: 'p2', short: 'B', label: 'Chain B' },
};
const CTX = { venueIndex: VENUES, mergeKey: t => t.toLowerCase() };
const fold = parts => cityPayload(GROUPS['city:X'], parts, CTX);

// Reads a scenario settles by hand, in arrival order per path.
function makeReads() {
  const queue = [];
  const calls = [];
  const read = p => {
    calls.push(p);
    return new Promise((resolve, reject) => queue.push({ p, resolve, reject }));
  };
  const settle = (p, value) => {
    const i = queue.findIndex(q => q.p === p);
    if (i === -1) throw new Error('no pending read for ' + p);
    const [q] = queue.splice(i, 1);
    if (value instanceof Error) q.reject(value); else q.resolve(clone(value));
  };
  return { read, calls, settle, queue };
}

// Every scenario builds a handler over the same shape of `io`. `read` is either the
// hand-settled one or the real readCached over the stub store.
function setup(opts) {
  const reads = makeReads();
  const st = { area: opts.area, applied: 0 };
  const cache = clone(opts.cache);
  const io = {
    area: () => st.area,
    cache,
    groups: () => opts.groups || GROUPS,
    // Both readers record the path they are asked for, so a scenario can assert which
    // slots a message reached. The cached one resolves from the stub store, so a read for
    // a path the scenario did not stage answers a miss rather than throwing: a mutation
    // that reaches for the wrong slot then produces a wrong payload instead of killing
    // the harness, and killing it shows up as no test going red at all.
    read: opts.cached ? (p => { reads.calls.push(p); return readCached(p); }) : reads.read,
    // loadGroup is the thin thing it is in the app -- read every member, fold with the
    // real cityPayload -- minus the prefs write. It takes the area string, so the same
    // stub serves a city and an area.
    loadGroup: async (area, read) => {
      const ids = (opts.groups || GROUPS)[area] || [];
      const parts = await Promise.all(ids.map(id => read(`data/area-${id}.json`).catch(() => null)));
      return cityPayload(ids, parts, CTX);
    },
    applied: () => { st.applied++; },
    extra: { fresh: () => { st.metaFresh = (st.metaFresh || 0) + 1; return Promise.resolve(); } },
  };
  return { io, st, cache, reads, handler: makeFreshHandler(io) };
}

// The metadata store over hand-settled fetches and reads. `sheetOpen` stands for the one
// consumer of the file: the redraw hook counts when it fires with a sheet open.
function metaSetup(opts) {
  const fetches = [], reads = [];
  const st = { redraws: 0, changed: 0, sheetOpen: !!opts.sheetOpen };
  const io = {
    fetch: () => new Promise((resolve, reject) => fetches.push({ resolve, reject })),
    read: () => new Promise((resolve, reject) => reads.push({ resolve, reject })),
    changed: () => { st.changed++; if (st.sheetOpen) st.redraws++; },
  };
  const store = makeExtraStore(io);
  const settleFetch = v => { const f = fetches.shift(); if (!f) throw new Error('no fetch pending'); v instanceof Error ? f.reject(v) : f.resolve(clone(v)); };
  const settleRead = v => { const r = reads.shift(); if (!r) throw new Error('no read pending'); v instanceof Error ? r.reject(v) : r.resolve(clone(v)); };
  return { store, st, fetches, reads, settleFetch, settleRead };
}
const META_OLD = { generated: '2026-09-05', films: { carrie: { s: { fi: 'Carrie: teksti' }, r: 7.3 } } };
const META_NEW = { generated: '2026-09-05', films: { carrie: { s: { fi: 'Carrie: teksti' }, r: 7.3 },
                                                     persepolis: { s: { fi: 'Marjane Satrapin lapsuus' }, r: 7.9 } } };
const synopsisOf = (films, key) => (films && films[key] && films[key].s && films[key].s.fi) || null;

const tick = () => new Promise(r => setImmediate(r));
const titles = p => (p.shows || []).map(s => s.title);
const summary = p => ({ generated: p.generated, oldest: p.oldest, missing: p.missing,
                        titles: titles(p), key: refreshKey(p) });

const A1 = payload('A', '2026-09-05T06:00:00+00:00');
const A2 = payload('A', '2026-09-05T09:00:00+00:00');
const A3 = payload('A', '2026-09-05T10:00:00+00:00', 'Film at A, reloaded');
const A4 = payload('A', '2026-09-05T11:00:00+00:00', 'Film at A, latest');
const B1 = payload('B', '2026-09-05T07:00:00+00:00');
const a1 = payload('a', '2026-09-05T06:00:00+00:00');
const a2 = payload('a', '2026-09-05T09:00:00+00:00', 'Film at a, later');
const b1 = payload('b', '2026-09-05T07:00:00+00:00');
const b2 = payload('b', '2026-09-05T08:00:00+00:00', 'Film at b, later');

const out = {};

async function run() {

  // ===== the slot a late answer lands in ================================================

  // -- a late answer for A after the reader moved to B -----------------------------------
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const done = s.handler('/data/area-A.json');
    await tick();
    s.st.area = 'B';                                   // the reader switches during the read
    s.reads.settle('data/area-A.json', A2);
    await done;
    out.late_answer_after_switch = { reads: s.reads.calls, applied: s.st.applied, B: s.cache.B, A: s.cache.A };
  }

  // -- the same read with the reader still on A -----------------------------------------
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const done = s.handler('/data/area-A.json');
    await tick();
    s.reads.settle('data/area-A.json', A2);
    await done;
    out.answer_still_selected = { reads: s.reads.calls, applied: s.st.applied, A: s.cache.A, B: s.cache.B };
  }

  // -- the cache emptied during the read (refreshAll on resume does exactly this) -------
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const done = s.handler('/data/area-A.json');
    await tick();
    for (const k of Object.keys(s.cache)) delete s.cache[k];
    s.reads.settle('data/area-A.json', A2);
    await done;
    out.invalidated_during_read = { applied: s.st.applied, keys: Object.keys(s.cache) };
  }

  // -- the slot emptied and refilled during the read: refreshAll then loadSchedule ------
  // The refill is a newer schedule than the snapshot the read started for. The old
  // check only asked whether an entry existed after the await, so the refill lost.
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const done = s.handler('/data/area-A.json');
    await tick();
    delete s.cache.A;
    s.cache.A = clone(A3);                              // loadSchedule refilled it, later than the read
    s.reads.settle('data/area-A.json', A2);             // the read answers with the older snapshot
    await done;
    out.refilled_during_read = { applied: s.st.applied, A: s.cache.A, reads: s.reads.calls };
  }

  // -- the same, with a message queued behind the read: the follow-up still runs and
  // compares against the refill rather than the snapshot the first read started from -----
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const first = s.handler('/data/area-A.json');
    await tick();
    delete s.cache.A;
    s.cache.A = clone(A3);
    const second = s.handler('/data/area-A.json');     // queued behind the first read
    await tick();
    const duringFirst = s.reads.calls.length;
    s.reads.settle('data/area-A.json', A2);             // older than the refill: discarded
    await tick(); await tick();
    const afterFirst = { applied: s.st.applied, generated: s.cache.A.generated, reads: s.reads.calls.length };
    s.reads.settle('data/area-A.json', A4);             // the follow-up sees a newer copy
    await Promise.all([first, second]);
    out.refilled_then_follow_up = { duringFirst, afterFirst, applied: s.st.applied, A: s.cache.A,
                                    reads: s.reads.calls.length, pending: s.reads.queue.length };
  }

  // -- emptied and not refilled, with a message queued: the follow-up has nothing to
  // compare against and does not read --------------------------------------------------------
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const first = s.handler('/data/area-A.json');
    await tick();
    const second = s.handler('/data/area-A.json');
    await tick();
    delete s.cache.A;
    s.reads.settle('data/area-A.json', A2);
    await Promise.all([first, second]);
    out.emptied_then_follow_up = { reads: s.reads.calls.length, applied: s.st.applied,
                                   keys: Object.keys(s.cache), pending: s.reads.queue.length };
  }

  // -- nothing changed: the same generated comes back --------------------------------------
  {
    const s = setup({ area: 'A', cache: { A: A1, B: B1 } });
    const done = s.handler('/data/area-A.json');
    await tick();
    s.reads.settle('data/area-A.json', A1);
    await done;
    out.unchanged = { applied: s.st.applied, A: s.cache.A };
  }

  // -- a file no held slot is fed by ------------------------------------------------------
  {
    const s = setup({ area: 'A', cache: { A: A1, 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-B.json');          // no B slot, and no city holds B
    await s.handler('/data/venues-finnkino.json');
    await s.handler('');
    out.not_a_hit = { reads: s.reads.calls, applied: s.st.applied };
  }

  // -- a venue the reader has left, still held ------------------------------------------
  // The message arrives for A while B is on screen. loadSchedule serves a held slot
  // without re-reading it, so leaving A's slot alone froze that cinema until a reload.
  {
    store.clear(); store.set('data/area-A.json', A2); store.set('data/area-B.json', B1);
    const s = setup({ area: 'B', cached: true, cache: { A: A1, B: B1 } });
    await s.handler('/data/area-A.json');
    out.unselected_venue_slot = { reads: s.reads.calls, applied: s.st.applied,
                                  A: s.cache.A, B: s.cache.B };
  }

  // -- a member of a held city the reader is not looking at ------------------------------
  {
    store.clear(); store.set('data/area-a.json', a1); store.set('data/area-b.json', b2);
    const s = setup({ area: 'A', cached: true, cache: { A: A1, 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-b.json');
    out.unselected_city_member = { reads: s.reads.calls, applied: s.st.applied,
                                   city: summary(s.cache['city:X']), A: s.cache.A };
  }

  // -- one file feeding both a venue slot and the city holding it ------------------------
  // The two slots are separate entries and both go stale on their own, so one message has
  // to write both. The fold reads the same file a second time; only the slot on screen is
  // drawn.
  {
    store.clear(); store.set('data/area-a.json', a2); store.set('data/area-b.json', b1);
    const s = setup({ area: 'a', cached: true, cache: { a: a1, 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-a.json');
    out.venue_and_its_city = { reads: s.reads.calls, applied: s.st.applied,
                               a: s.cache.a, city: summary(s.cache['city:X']) };
  }

  // -- one file feeding a venue, its city and the area holding that city -----------------
  // A venue belongs to one city and a city to one area, so a message reaches at most
  // three slots. Before areas existed the filter sliced the 'city:' prefix off by hand
  // and an area slot would have been skipped: held, stale, and served on the way back.
  {
    store.clear(); store.set('data/area-a.json', a2); store.set('data/area-b.json', b1);
    const s = setup({ area: 'region:R', cached: true,
                      groups: { 'city:X': ['a', 'b'], 'region:R': ['a', 'b'] },
                      cache: { a: a1, 'city:X': fold([a1, b1]), 'region:R': fold([a1, b1]) } });
    await s.handler('/data/area-a.json');
    out.venue_city_and_area = { applied: s.st.applied, a: s.cache.a,
                                city: summary(s.cache['city:X']),
                                area: summary(s.cache['region:R']) };
  }

  // -- nothing loaded yet for the selection ----------------------------------------------
  {
    const s = setup({ area: 'A', cache: { B: B1 } });
    await s.handler('/data/area-A.json');
    out.nothing_held = { reads: s.reads.calls, applied: s.st.applied, keys: Object.keys(s.cache) };
  }

  // ===== a refresh that lands before its slot exists ========================================
  // The boot order that left a 24-hour-old schedule on screen: the worker answered the
  // prefetch from its cache, its refresh landed while the page still waited on the venue
  // lists, and loadSchedule then filled the slot with the older copy. filled() replays it.

  // -- a venue: the message reads nothing, the fill replays it once --------------------------
  {
    store.clear(); store.set('data/area-A.json', A2);
    const s = setup({ area: 'A', cached: true, cache: {} });
    await s.handler('/data/area-A.json');
    const readsAtMessage = s.reads.calls.length;
    s.cache.A = clone(A1);                             // loadSchedule fills it, older copy
    const ids = await s.handler.filled('A');
    const again = await s.handler.filled('A');
    out.early_then_filled = { readsAtMessage, ids, again, reads: s.reads.calls.length,
                              applied: s.st.applied, A: s.cache.A.generated };
  }

  // -- a city member: the whole city is re-read ---------------------------------------------
  {
    store.clear(); store.set('data/area-a.json', a1); store.set('data/area-b.json', b2);
    const s = setup({ area: 'city:X', cached: true, cache: {} });
    await s.handler('/data/area-b.json');
    s.cache['city:X'] = fold([a1, b1]);
    const ids = await s.handler.filled('city:X');
    out.early_city_member = { ids, applied: s.st.applied, city: summary(s.cache['city:X']) };
  }

  // -- a fill with no early message reads nothing --------------------------------------------
  {
    store.clear(); store.set('data/area-A.json', A2);
    const s = setup({ area: 'A', cached: true, cache: { A: A1 } });
    const ids = await s.handler.filled('A');
    out.filled_nothing_early = { ids, reads: s.reads.calls.length, applied: s.st.applied };
  }

  // -- switching cinemas: A's early refresh waits for A's slot -------------------------------
  // The reader moved to B before A's slot was filled. Filling B replays nothing of A's;
  // A's slot, filled later, still gets the newer copy and draws nothing over B.
  {
    store.clear(); store.set('data/area-A.json', A2); store.set('data/area-B.json', B1);
    const s = setup({ area: 'A', cached: true, cache: {} });
    await s.handler('/data/area-A.json');
    s.st.area = 'B';
    s.cache.B = clone(B1);
    const onB = await s.handler.filled('B');
    const earlyA = s.handler.early('A');
    s.cache.A = clone(A1);
    const onA = await s.handler.filled('A');
    out.early_across_switch = { onB, earlyA, onA, applied: s.st.applied,
                                A: s.cache.A.generated, B: s.cache.B.generated };
  }

  // ===== a combined city: every member counts ============================================

  // -- the fold itself: freshness is the oldest member's ----------------------------------
  {
    out.fold = { both: summary(fold([a1, b1])), a_missing: summary(fold([null, b1])),
                 a_newer: summary(fold([a2, b1])), none: summary(fold([null, null])) };
  }

  // -- the reported defect: the newer member updates, the oldest one does not -------------
  {
    store.clear(); store.set('data/area-a.json', a1); store.set('data/area-b.json', b2);
    const s = setup({ area: 'city:X', cached: true, cache: { 'city:X': fold([a1, b1]), A: A1 } });
    await s.handler('/data/area-b.json');
    out.newer_member_updates = { applied: s.st.applied, city: summary(s.cache['city:X']), A: s.cache.A };
  }

  // -- the oldest member updates: the banner's source moves to the other one ---------------
  {
    store.clear(); store.set('data/area-a.json', a2); store.set('data/area-b.json', b1);
    const s = setup({ area: 'city:X', cached: true, cache: { 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-a.json');
    out.oldest_member_updates = { applied: s.st.applied, city: summary(s.cache['city:X']) };
  }

  // -- a member drops out of the cache, and one comes back ----------------------------------
  {
    store.clear(); store.set('data/area-a.json', a1);
    const s = setup({ area: 'city:X', cached: true, cache: { 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-a.json');
    out.member_goes_missing = { applied: s.st.applied, city: summary(s.cache['city:X']) };
  }
  {
    store.clear(); store.set('data/area-a.json', a1); store.set('data/area-b.json', b1);
    const s = setup({ area: 'city:X', cached: true, cache: { 'city:X': fold([a1, null]) } });
    await s.handler('/data/area-b.json');
    out.member_comes_back = { applied: s.st.applied, city: summary(s.cache['city:X']) };
  }

  // -- nothing moved --------------------------------------------------------------------------
  {
    store.clear(); store.set('data/area-a.json', a1); store.set('data/area-b.json', b1);
    const s = setup({ area: 'city:X', cached: true, cache: { 'city:X': fold([a1, b1]) } });
    await s.handler('/data/area-b.json');
    out.city_unchanged = { applied: s.st.applied, city: summary(s.cache['city:X']) };
  }

  // -- a burst: every member messages within the first read -----------------------------------
  {
    const s = setup({ area: 'city:X', cache: { 'city:X': fold([a1, b1]) } });
    const first = s.handler('/data/area-a.json');
    await tick();
    const afterFirst = s.reads.calls.length;
    const second = s.handler('/data/area-b.json');      // arrives while the read runs
    const third = s.handler('/data/area-a.json');
    await tick();
    const duringFirst = s.reads.calls.length;
    s.reads.settle('data/area-a.json', a2);
    s.reads.settle('data/area-b.json', b1);              // b has not landed yet
    await tick(); await tick();
    const afterSecondStarted = s.reads.calls.length;
    s.reads.settle('data/area-a.json', a2);
    s.reads.settle('data/area-b.json', b2);              // now it has
    await Promise.all([first, second, third]);
    const settled = s.reads.calls.length;
    // The drain is over; a later message starts a fresh read rather than being swallowed.
    const fourth = s.handler('/data/area-b.json');
    await tick();
    const afterFourth = s.reads.calls.length;
    s.reads.settle('data/area-a.json', a2);
    s.reads.settle('data/area-b.json', b2);
    await fourth;
    out.burst = { afterFirst, duringFirst, afterSecondStarted, settled, afterFourth,
                  applied: s.st.applied, city: summary(s.cache['city:X']),
                  pending: s.reads.queue.length };
  }

  // ===== film metadata: films-extra.json behind an open sheet ============================

  // -- an open sheet whose film had no synopsis gets one when the file refreshes ----------
  {
    const m = metaSetup({ sheetOpen: true });
    const p = m.store.ensure();
    m.settleFetch(META_OLD);
    const first = await p;
    const before = synopsisOf(first, 'persepolis');
    const f = m.store.fresh();
    await tick();
    m.settleRead(META_NEW);
    await f;
    out.meta_open_sheet_gains_synopsis = { before, after: synopsisOf(m.store.get(), 'persepolis'),
      redraws: m.st.redraws, changed: m.st.changed, fetches: m.fetches.length, pendingReads: m.reads.length };
  }

  // -- the first fetch fails; a later sheet fetches again and succeeds --------------------
  {
    const m = metaSetup({ sheetOpen: true });
    const p1 = m.store.ensure();
    const p1b = m.store.ensure();                        // a second caller during the load
    const shared = p1 === p1b;
    m.settleFetch(new Error('HTTP 503'));
    const r1 = await p1;
    const p2 = m.store.ensure();
    const fetchedAgain = m.fetches.length === 1;
    m.settleFetch(META_NEW);
    const r2 = await p2;
    const p3 = m.store.ensure();                         // memoised now: no third fetch
    await tick();
    out.meta_failed_then_succeeds = { shared, firstResult: Object.keys(r1), fetchedAgain,
      second: synopsisOf(r2, 'persepolis'), thirdFetches: m.fetches.length, memoised: (await p3) === r2,
      changed: m.st.changed };
  }

  // -- an unchanged rewrite: same content, new file bytes, no redraw, no fetch -------------
  {
    const m = metaSetup({ sheetOpen: true });
    const p = m.store.ensure(); m.settleFetch(META_NEW); await p;
    const f1 = m.store.fresh();
    const f2 = m.store.fresh();                          // a second message during the read
    const f3 = m.store.fresh();
    await tick();
    const readsDuring = m.reads.length;
    m.settleRead({ generated: '2026-09-06', films: clone(META_NEW.films) });   // only the date moved
    await tick(); await tick();
    const followUp = m.reads.length;
    if (m.reads.length) m.settleRead({ generated: '2026-09-06', films: clone(META_NEW.films) });
    await Promise.all([f1, f2, f3]);
    out.meta_unchanged_no_redraw = { readsDuring, followUp, changed: m.st.changed, redraws: m.st.redraws,
      fetches: m.fetches.length, pendingReads: m.reads.length };
  }

  // -- a slow first load answers after the worker already cached a newer copy --------------
  {
    const m = metaSetup({ sheetOpen: true });
    const p = m.store.ensure();                          // fetch in flight, answered later
    const f = m.store.fresh();                           // the worker's message arrives first
    await tick();
    const readBeforeLoad = m.reads.length;
    // A store that did not wait for the load has a read pending now; it gets the newer
    // copy first, and the older load answer then lands on top of it. A store that waited
    // reads after the load and applies the newer copy last.
    if (m.reads.length) m.settleRead(META_NEW);
    await tick();
    m.settleFetch(META_OLD);                             // the delayed, older answer
    await p;
    await tick();
    if (m.reads.length) m.settleRead(META_NEW);
    await f;
    out.meta_delayed_load_cannot_overwrite = { readBeforeLoad, final: synopsisOf(m.store.get(), 'persepolis'),
      changed: m.st.changed, redraws: m.st.redraws };
  }

  // -- a message before anyone asked for the file: nothing to update, nothing read ----------
  {
    const m = metaSetup({ sheetOpen: false });
    await m.store.fresh();
    out.meta_fresh_before_any_load = { reads: m.reads.length, fetches: m.fetches.length, changed: m.st.changed,
      films: m.store.get() };
  }

  // -- a change with no sheet open: the map moves, nothing is redrawn -------------------------
  {
    const m = metaSetup({ sheetOpen: false });
    const p = m.store.ensure(); m.settleFetch(META_OLD); await p;
    const f = m.store.fresh(); await tick(); m.settleRead(META_NEW); await f;
    out.meta_change_sheet_closed = { changed: m.st.changed, redraws: m.st.redraws,
      after: synopsisOf(m.store.get(), 'persepolis') };
  }

  // -- the handler routes the file's message to the store and nowhere else -------------------
  {
    const s = setup({ area: 'A', cache: { A: A1 } });
    await s.handler('/data/films-extra.json');
    await s.handler('/data/films-extra.json');
    out.meta_routed = { metaFresh: s.st.metaFresh || 0, reads: s.reads.calls.length, applied: s.st.applied };
    const s2 = setup({ area: 'A', cache: { A: A1 } });
    const done = s2.handler('/data/area-A.json'); await tick(); s2.reads.settle('data/area-A.json', A2); await done;
    out.meta_routed.areaMessageMetaFresh = s2.st.metaFresh || 0;
  }

  // -- the reader the handler is built with -----------------------------------------------------
  {
    store.clear(); store.set('data/area-a.json', a1);
    const hit = await readCached('data/area-a.json');
    let miss = null;
    try { await readCached('data/area-zz.json'); } catch (e) { miss = String(e.message); }
    out.read_cached = { hit: summary(hit), miss, fetchDefined: typeof sandbox.fetch !== 'undefined' };
  }

}

// A scenario that throws, or one whose handler never settles because the code under test
// asked for a slot the scenario did not stage, used to print nothing at all. The Python
// side then saw empty stdout, every test errored in setUpClass, and a mutation run scored
// that as "nothing went red" rather than as the breakage it is. Whatever `out` holds is
// printed either way now, and `__error` turns the death itself into one failing test.
const WATCHDOG_MS = 10000;
let watchdog;
Promise.race([
  run(),
  new Promise((_, reject) => {
    watchdog = setTimeout(
      () => reject(new Error(`a scenario did not settle within ${WATCHDOG_MS} ms`)), WATCHDOG_MS);
  }),
]).catch(e => { out.__error = String((e && e.stack) || e); })
  .then(() => { clearTimeout(watchdog); process.stdout.write(JSON.stringify(out)); });
