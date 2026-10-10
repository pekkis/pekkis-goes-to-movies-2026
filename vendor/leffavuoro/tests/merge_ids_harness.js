// Runs index.html's own `mergeIds` and `sheetId` over one set of shows in several orders.
// Driven by tests/test_merge_ids.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments. The shows carry what
// `cityPayload` hands `mergeIds`: `eventId` already the title's merge key, and `tmdbId`.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- merge ids: pure, extracted verbatim by tests/merge_ids_harness.js ---';
const END = '// --- end merge ids ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('merge ids markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
for (const fn of ['mergeIds', 'sheetId']) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(source)) {
    console.error('marker block does not contain ' + fn);
    process.exit(2);
  }
}
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\nthis.mergeIds = mergeIds; this.sheetId = sheetId;', sandbox);

// Kotka's shape on 2026-09-24: the English-audio copy and the Finnish-dubbed one (whose
// ", suomeksi" mergeKey strips) share a TMDB id; a third chain lists the plain title with
// no id. Two unrelated films, one joined by id only, one alone.
const SHOWS = [
  { n: 1, eventId: 'kojootti vs acme englanniksi', tmdbId: 1204680 },
  { n: 2, eventId: 'kojootti vs acme', tmdbId: 1204680 },
  { n: 3, eventId: 'kojootti vs acme', tmdbId: 0 },
  { n: 4, eventId: 'mutiny lavastettu syylliseksi', tmdbId: 7 },
  { n: 5, eventId: 'mutiny', tmdbId: 7 },
  { n: 6, eventId: 'autofiktio' },
];

function fold(list) {
  const shows = list.map(s => ({ ...s }));
  sandbox.mergeIds(shows);
  const ids = {}, own = {};
  for (const s of shows) { ids[s.n] = s.eventId; own[s.n] = s._mk; }
  return { ids, own, shows };
}

const orders = {
  given: SHOWS,
  reversed: [...SHOWS].reverse(),
  rotated: [...SHOWS.slice(3), ...SHOWS.slice(0, 3)],
};
const out = { orders: {}, dropped: null, resolve: {} };
for (const [k, list] of Object.entries(orders)) {
  const { ids, own } = fold(list);
  out.orders[k] = { ids, own };
}
// The first day gone: the English copy's only row leaves, and the name must not move.
out.dropped = fold(SHOWS.filter(s => s.n !== 1)).ids;

const shows = fold(SHOWS.slice().reverse()).shows;
for (const fid of ['kojootti vs acme englanniksi', 'kojootti vs acme', 'mutiny',
                   'mutiny lavastettu syylliseksi', 'autofiktio', 'ei tätä elokuvaa', '']) {
  out.resolve[fid] = sandbox.sheetId(shows, fid);
}
console.log(JSON.stringify(out));
