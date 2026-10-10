// Runs the real venue-picker model out of index.html and prints one JSON line of
// results per scenario. Driven by tests/test_venue_picker.py.
//
// The model (vfold / vhl / venueRows) is pure by construction -- it renders no DOM and
// reads no globals -- so it is extracted verbatim between its markers and executed in a
// bare vm context, the same technique tests/health_state_harness.js uses. What cannot
// be tested this way stays verified live: focus, inert, Escape handling and the
// on-screen-keyboard behavior are DOM and event plumbing, not decisions of this model.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- venue picker model: pure, extracted verbatim by tests/venue_picker_harness.js ---';
const END = '// --- end venue picker model ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('venue picker model markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/function venueRows\s*\(/.test(source)) {
  console.error('marker block does not contain venueRows');
  process.exit(2);
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__rows = venueRows; globalThis.__hl = vhl;',
                sandbox, { filename: 'venueRows' });
const venueRows = sandbox.__rows;
const vhl = sandbox.__hl;

// A small fixture in the shape fillAreaSelect builds: labels are chain-prefixed and
// carry no city; the city lives on the group. Turku is here for the Swedish alias.
const VENUES = {
  itis:   { id: 'itis',   provider: 'finnkino', label: 'Finnkino Itis',   city: 'Helsinki' },
  tripla: { id: 'tripla', provider: 'biorex',   label: 'BioRex Tripla',   city: 'Helsinki' },
  ja:     { id: 'ja',     provider: 'jarvelankino', label: 'Järvelän Kino', city: 'Järvelä' },
  tku:    { id: 'tku',    provider: 'x',        label: 'Kinopalatsi',     city: 'Turku' },
};
const cityOrder = ['Helsinki', 'Järvelä', 'Turku'];
const cityVenues = {
  Helsinki: [VENUES.itis, VENUES.tripla],
  'Järvelä': [VENUES.ja],
  Turku: [VENUES.tku],
};
const SV_CITY = { Helsinki: 'Helsingfors', Turku: 'Åbo' };
// Two areas, because one would leave the loop and the ordering untested. Areas are
// passed only by the scenarios that want them: without them the ctx is what it was
// before areas existed, which is what a missing data/regions.json produces.
const REGION_NAMES = {
  Uusimaa: { sv: 'Nyland', en: 'Uusimaa region' },
  'Varsinais-Suomi': { sv: 'Egentliga Finland', en: 'Southwest Finland' },
};
const REGIONS = {
  regionOrder: ['Uusimaa', 'Varsinais-Suomi'],
  regionVenues: {
    Uusimaa: [VENUES.itis, VENUES.tripla, VENUES.ja],
    'Varsinais-Suomi': [VENUES.tku],
  },
  regionCities: { Uusimaa: ['Helsinki', 'Järvelä'], 'Varsinais-Suomi': ['Turku'] },
  // Every name an area answers to, joined the way buildAreaOptions joins them, so a
  // query in one language finds an area labelled in another.
  regionText: Object.fromEntries(Object.entries(REGION_NAMES).map(
    ([k, v]) => [k, `${k} ${v.sv} ${v.en}`])),
};

function ctx(overrides) {
  const lang = (overrides && overrides.lang) || 'fi';
  return Object.assign({
    T: { allIn: lang === 'sv' ? '{city} – alla biografer' : '{city} – kaikki teatterit',
         vOwn: 'Oma teatteri', vAreas: 'Alueet' },
    fav: null,
    area: 'itis',
    cityOrder,
    cityVenues,
    venueIndex: VENUES,
    labelOf: v => v.label,
    cityOf: v => v.city,
    cityLabel: c => (lang === 'sv' && SV_CITY[c]) || c,
    regionLabel: r => (REGION_NAMES[r] && REGION_NAMES[r][lang]) || r,
  }, overrides || {});
}

const rowsOf = (q, o) => venueRows(q, ctx(o))
  .map(r => (r.kind === 'head' ? `#${r.text}` : `${r.kind}:${r.id}`));

const out = {
  no_query: rowsOf(''),
  diacritics: rowsOf('jarvela'),
  venue_query_first_row: rowsOf('itis'),
  city_query: rowsOf('helsinki'),
  kaikki_query: rowsOf('kaikki'),
  sv_alias_fi_name: rowsOf('turku', { lang: 'sv' }),
  sv_alias_sv_name: rowsOf('abo', { lang: 'sv' }),
  fav_venue: rowsOf('', { fav: 'ja' }),
  fav_city: rowsOf('', { fav: 'city:Helsinki' }),
  fav_city_filtered_out: rowsOf('turku', { fav: 'city:Helsinki' }),
  none: rowsOf('zzzz'),
  hl: vhl('Järvelän Kino', 'jarvela', s => s),

  // Areas. `view` decides only what an empty query browses; a query reads both lists
  // from either view.
  areas_view: rowsOf('', Object.assign({ view: 'areas' }, REGIONS)),
  cities_view: rowsOf('', Object.assign({ view: 'cities' }, REGIONS)),
  areas_view_counts: venueRows('', ctx(Object.assign({ view: 'areas' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => `${r.name}:${r.count}`),
  area_name_query: rowsOf('uusimaa', Object.assign({ view: 'cities' }, REGIONS)),
  area_name_query_from_areas_view: rowsOf('uusimaa', Object.assign({ view: 'areas' }, REGIONS)),
  city_query_puts_area_below: rowsOf('turku', Object.assign({ view: 'cities' }, REGIONS)),
  city_query_from_areas_view: rowsOf('turku', Object.assign({ view: 'areas' }, REGIONS)),
  kaikki_query_with_areas: rowsOf('kaikki', Object.assign({ view: 'cities' }, REGIONS)),
  fav_area_in_cities_view: rowsOf('', Object.assign({ view: 'cities', fav: 'region:Uusimaa' }, REGIONS)),
  fav_area_in_areas_view: rowsOf('', Object.assign({ view: 'areas', fav: 'region:Uusimaa' }, REGIONS)),
  fav_venue_in_areas_view: rowsOf('', Object.assign({ view: 'areas', fav: 'ja' }, REGIONS)),
  area_current: venueRows('', ctx(Object.assign({ view: 'areas', area: 'region:Uusimaa' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => `${r.name}:${r.current}`),

  // Area names in three languages: the row shows the reader's, the search reads all.
  area_cities: venueRows('', ctx(Object.assign({ view: 'areas' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => `${r.name}: ${r.cities}`),
  area_cities_sv: venueRows('', ctx(Object.assign({ view: 'areas', lang: 'sv' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => r.cities),
  area_labels_en: venueRows('', ctx(Object.assign({ view: 'areas', lang: 'en' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => r.name),
  area_labels_sv: venueRows('', ctx(Object.assign({ view: 'areas', lang: 'sv' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => r.name),
  en_query_in_finnish: rowsOf('southwest', Object.assign({ view: 'cities' }, REGIONS)),
  sv_query_in_finnish: rowsOf('egentliga', Object.assign({ view: 'cities' }, REGIONS)),
  fi_query_in_english: rowsOf('varsinais', Object.assign({ view: 'cities', lang: 'en' }, REGIONS)),
  en_query_highlight: venueRows('southwest', ctx(Object.assign({ lang: 'en' }, REGIONS)))
    .filter(r => r.kind === 'area').map(r => vhl(r.name, 'southwest', x => x)),
};
process.stdout.write(JSON.stringify(out));
