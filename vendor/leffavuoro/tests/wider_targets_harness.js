// Drives index.html's widerTargets() against controlled registries.
//
// Sliced verbatim out of index.html between its marker comments. What it pins: a venue
// offers its city and its region, a city its region, a region nothing; a target counts
// only when it adds a theatre the chain restriction admits; a region admitting exactly
// the city's theatres is dropped in favour of the city; a city in two regions or none
// gets no region; geography comes from the registries handed in and nothing else.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function slice(start, end, name) {
  const a = HTML.indexOf(start);
  const b = HTML.indexOf(end);
  if (a === -1 || b === -1 || b < a) {
    console.error(name + ' markers not found in index.html');
    process.exit(2);
  }
  return HTML.slice(a, b);
}
const SRC = slice('  // --- widerTargets: pure, extracted verbatim by tests/wider_targets_harness.js ---',
                  '  // --- end widerTargets ---', 'widerTargets');
if (!/function widerTargets\s*\(/.test(SRC)) {
  console.error('marker block does not contain widerTargets');
  process.exit(2);
}
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(SRC + '\n;globalThis.__w = widerTargets;', sandbox, { filename: 'widerTargets' });
const widerTargets = sandbox.__w;

// A small country. Helsinki has three venues of two chains, Espoo one, Vantaa one;
// Tampere has two venues of one chain and belongs to no region; Kotka and Kouvola share
// a region; Lahti belongs to two regions in the ambiguous fixture.
const VENUES = {
  'hki-a': { city: 'Helsinki', provider: 'finnkino' },
  'hki-b': { city: 'Helsinki', provider: 'finnkino' },
  'hki-c': { city: 'Helsinki', provider: 'gilda' },
  'esp-a': { city: 'Espoo', provider: 'finnkino' },
  'van-a': { city: 'Vantaa', provider: 'heureka' },
  'tre-a': { city: 'Tampere', provider: 'finnkino' },
  'tre-b': { city: 'Tampere', provider: 'finnkino' },
  'kot-a': { city: 'Kotka', provider: 'kotkanleffat' },
  'kou-a': { city: 'Kouvola', provider: 'kino123' },
  'lah-a': { city: 'Lahti', provider: 'finnkino' },
  'jar-a': { city: 'Järvelä', provider: 'jarvelankino' },
};
const CITY = {
  Helsinki: ['hki-a', 'hki-b', 'hki-c'], Espoo: ['esp-a'], Vantaa: ['van-a'],
  Tampere: ['tre-a', 'tre-b'], Kotka: ['kot-a'], Kouvola: ['kou-a'],
  Lahti: ['lah-a'], 'Järvelä': ['jar-a'],
};
const REGION_CITIES = {
  'Pääkaupunkiseutu': ['Helsinki', 'Espoo', 'Vantaa'],
  Kymenlaakso: ['Kotka', 'Kouvola'],
  'Lahden seutu': ['Lahti', 'Järvelä'],
};
const REGION_IDS = {};
for (const r of Object.keys(REGION_CITIES)) {
  REGION_IDS[r] = REGION_CITIES[r].flatMap((c) => CITY[c] || []);
}
const ctx = (area, chains, over) => Object.assign({
  area, chains: chains ? new Set(chains) : null,
  venue: (id) => VENUES[id] || null,
  cityGroups: CITY, regionCities: REGION_CITIES, regionGroups: REGION_IDS,
}, over || {});
const ids = (out) => out.map((t) => t.id);
const out = {};

out.venue_in_capital = ids(widerTargets(ctx('hki-c', null)));
out.city_helsinki = ids(widerTargets(ctx('city:Helsinki', null)));
out.region = ids(widerTargets(ctx('region:Pääkaupunkiseutu', null)));
out.alone_in_city_region_adds = ids(widerTargets(ctx('kot-a', null)));
out.city_alone_in_region_twin = ids(widerTargets(ctx('city:Kotka', null)));
// Tampere: two venues, in no region.
out.venue_no_region = ids(widerTargets(ctx('tre-a', null)));
out.city_no_region = ids(widerTargets(ctx('city:Tampere', null)));
// Chains: from a Gilda-only view in Helsinki nothing outside admits Gilda.
out.chain_blocks_both = ids(widerTargets(ctx('hki-c', ['gilda'])));
// Finnkino-only from hki-a: the city adds hki-b, the region adds esp-a.
out.chain_admits_both = ids(widerTargets(ctx('hki-a', ['finnkino'])));
// Heureka-only from hki-a: the city adds nothing, the region adds van-a.
out.chain_region_only = ids(widerTargets(ctx('hki-a', ['heureka'])));
// Same eligible sets: Finnkino-only from hki-c where the region's extra venue is not
// Finnkino would be a twin; build it with Espoo removed from the region.
out.twin_sets_city_only = ids(widerTargets(ctx('hki-c', ['finnkino'], {
  regionCities: { 'Pääkaupunkiseutu': ['Helsinki', 'Vantaa'] },
  regionGroups: { 'Pääkaupunkiseutu': ['hki-a', 'hki-b', 'hki-c', 'van-a'] },
})));
// Ambiguous membership: Lahti listed in two regions.
out.ambiguous_region = ids(widerTargets(ctx('lah-a', null, {
  regionCities: Object.assign({}, REGION_CITIES, { 'Etelä-Suomi': ['Lahti', 'Kotka'] }),
  regionGroups: Object.assign({}, REGION_IDS, { 'Etelä-Suomi': ['lah-a', 'kot-a'] }),
})));
out.unknown_venue = ids(widerTargets(ctx('nope', null)));
out.blank_area = ids(widerTargets(ctx('', null)));
out.shape = widerTargets(ctx('hki-c', null));
// Registry order does not matter: the same answer with the region maps reversed.
const rev = (o) => Object.fromEntries(Object.entries(o).reverse());
out.order_independent = ids(widerTargets(ctx('hki-c', null, {
  regionCities: rev(REGION_CITIES), regionGroups: rev(REGION_IDS),
})));
process.stdout.write(JSON.stringify(out));
