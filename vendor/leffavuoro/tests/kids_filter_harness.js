// Drives index.html's own Lapsille gates against the states the published data holds.
//
// The block is sliced verbatim out of index.html between its marker comments, the way
// healthState and the others are. What it pins: an empty `rating` is not "unrestricted",
// a screening limit of seven or below admits children, and Heureka's per-film
// recommendation is read only where a classification is missing.
//
// The fixtures are the real shapes. Heureka publishes `rating: ''`, `age: 'K-5'` on every
// show and its recommendation in `method`; Riviera and Cinema Orion publish no rating and
// no recommendation; Finnkino publishes classifications.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

const START = '  // --- kids gates: pure, extracted verbatim by tests/kids_filter_harness.js ---';
const END = '  // --- end kids gates ---';
const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('kids gate markers not found in index.html');
  process.exit(2);
}
const SRC = HTML.slice(a, b);
for (const fn of ['kidsRated', 'kidsAdmitted']) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(SRC)) {
    console.error('marker block does not contain ' + fn);
    process.exit(2);
  }
}
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(SRC + '\n;globalThis.__r = kidsRated; globalThis.__a = kidsAdmitted;',
                sandbox, { filename: 'kidsGates' });
const kidsRated = sandbox.__r;
const kidsAdmitted = sandbox.__a;

const show = (o) => Object.assign({ rating: '', age: '', method: '', gids: null }, o);

const out = {};

// -- classifications, the line the filter has always drawn --------------------------------
out.ratings = {};
for (const r of ['S', 'K-7', 'K-12', 'K-16', 'K-18']) {
  out.ratings[r] = kidsRated(show({ rating: r }));
}

// -- Heureka: no classification, a recommendation in `method` -------------------------------
out.heureka = {};
for (const m of ['Suositus 5–10 v', 'Suositus yli 7 v', 'Suositus yli 10 v',
                 'Suositus aikuisille']) {
  out.heureka[m] = kidsRated(show({ rating: '', age: 'K-5', method: m }));
}

// -- an unrated show with no recommendation stays out ---------------------------------------
// Riviera (81 showtimes) and Cinema Orion (14) are in this state, and so is every unrated
// showtime at a chain that usually publishes a classification.
out.unrated_no_recommendation = {
  bare: kidsRated(show({ rating: '' })),
  strand: kidsRated(show({ rating: '', method: 'Espoo Ciné' })),
  anniskelu: kidsRated(show({ rating: '', method: 'anniskelu' })),
};

// -- a recommendation never overrides a classification ---------------------------------------
out.recommendation_does_not_override = {
  k18_with_kid_recommendation: kidsRated(show({ rating: 'K-18', method: 'Suositus 5–10 v' })),
  s_with_adult_recommendation: kidsRated(show({ rating: 'S', method: 'Suositus aikuisille' })),
};

// -- the screening's own limit ----------------------------------------------------------------
out.admitted = {};
for (const age of ['', 'S', 'K-5', 'K-7', 'K-12', 'K-16', 'K-18', 'K-3', 'Sallittu', '18']) {
  out.admitted[age || '(empty)'] = kidsAdmitted(age);
}

// -- the two gates together, on the real Heureka shape ------------------------------------------
out.heureka_rows = ['Suositus 5–10 v', 'Suositus yli 7 v', 'Suositus yli 10 v',
                    'Suositus aikuisille'].map(m => {
  const s = show({ rating: '', age: 'K-5', method: m });
  return { method: m, passes: kidsRated(s) && kidsAdmitted(s.age) };
});

// -- a licensed room still refuses, whatever the film is rated ------------------------------------
out.licensed_room = {
  s_film_in_k18_room: kidsRated(show({ rating: 'S', age: 'K-18' }))
                      && kidsAdmitted('K-18'),
};

process.stdout.write(JSON.stringify(out));
