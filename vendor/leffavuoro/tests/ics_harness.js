// Drives index.html's icsFor() against fixed screenings. Driven by tests/test_ics.py;
// prints one JSON line of file texts.
//
// The block is sliced verbatim out of index.html between its marker comments, with the
// Helsinki date helpers and safeUrl it calls, so the real code runs.
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
const SRC = slice('  // --- ics: pure, extracted verbatim by tests/ics_harness.js ---',
                  '  // --- end ics ---', 'ics');
if (!/function icsFor\s*\(/.test(SRC) || !/function venuePlace\s*\(/.test(SRC)) {
  console.error('marker block does not contain icsFor');
  process.exit(2);
}
const HELPERS = HTML.slice(HTML.indexOf("  const FI_TZ = 'Europe/Helsinki';"),
                           HTML.indexOf('  const fiToday = () => fiDate(new Date());'));
const SAFE = HTML.slice(HTML.indexOf('  const CTRL = /'), HTML.indexOf('  const safeAssetUrl'));
if (!/fiDate = /.test(HELPERS) || !/safeUrl/.test(SAFE)) {
  console.error('helpers not found in index.html');
  process.exit(2);
}
// The picker's naming rules, sliced from the page: cityOf, shortOf, labelOf, with the
// chain table they read.
const NAMES = HTML.slice(HTML.indexOf('  function cityOf(a){'), HTML.indexOf('  // "Itis Helsinki" never says Finnkino'))
  + HTML.slice(HTML.indexOf('  function shortOf(a){'), HTML.indexOf('  // Split out of fillAreaSelect'));
if (!/function labelOf/.test(NAMES)) { console.error('naming rules not found'); process.exit(2); }
const sandbox = { URL, CHAIN: { finnkino: 'Finnkino', riviera: 'Riviera', niagara: 'Cinema Niagara' } };
vm.createContext(sandbox);
vm.runInContext(HELPERS + '\n' + SAFE + '\n' + NAMES + '\n' + SRC + '\n;globalThis.__i = icsFor; globalThis.__v = venuePlace;'
                + 'globalThis.__c = cityOf; globalThis.__l = labelOf;',
                sandbox, { filename: 'ics' });
const icsFor = sandbox.__i, venuePlace = sandbox.__v, cityOf = sandbox.__c, labelOf = sandbox.__l;

const NOW = new Date('2026-09-13T12:00:00Z');
const base = {
  title: 'Ryhmä Hau: Dinoelokuva', len: '88', aud: 'Sali 3', method: '2D',
  start: new Date('2026-09-15T16:30:00+03:00'),
  url: 'https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1004-5281',
};
const finnkino = { id: '1004', label: 'Finnkino Promenadi', city: 'Pori' };
// Real shapes, kept next to each other so test_ics.py can assert the round trip.
const AMP_URL = 'https://www.elavienkuvienteatteri.fi/lipunvaraus/?movieid=1383&date=2026-09-22&time=17:30';
const APOS_URL = "https://x.fi/lippu/o'brien?d=1";
const out = {};
out.plain = icsFor(base, finnkino, 'fi', NOW);
out.no_hall = icsFor({ ...base, aud: '' }, { id: 'kr-regina', label: 'Kino Regina', city: 'Helsinki' }, 'fi', NOW);
out.no_len_fi = icsFor({ ...base, len: '' }, finnkino, 'fi', NOW);
out.no_len_sv = icsFor({ ...base, len: undefined }, finnkino, 'sv', NOW);
out.no_len_en = icsFor({ ...base, len: '0' }, finnkino, 'en', NOW);
out.punctuation = icsFor({ ...base, title: 'Mission: Impossible, Part; Two\\Three', method: 'IMAX · dubattu' },
                         { id: 'br-tripla', label: 'BioRex Tripla', city: 'Helsinki' }, 'fi', NOW);
// Control characters a provider's title can carry. Written as escapes so the fixture
// stays readable in a diff and no literal control byte enters this file.
out.lone_cr = icsFor({ ...base, title: 'Elokuva\u000dDESCRIPTION:injected' }, finnkino, 'fi', NOW);
out.c0 = icsFor({ ...base, title: 'Elo\u0007kuva\u0000loppu', aud: 'Sali\u001f3' }, finnkino, 'fi', NOW);
out.long_title = icsFor({ ...base, title: 'Ääkkösiä '.repeat(12).trim() }, finnkino, 'fi', NOW);
out.bad_url = icsFor({ ...base, url: 'javascript:alert(1)' }, finnkino, 'fi', NOW);
// A ticket URL is not HTML. Both characters esc() rewrites and a calendar follows
// literally: 21 of 4486 committed ticket URLs carry an `&`.
out.amp_url = icsFor({ ...base, url: AMP_URL }, finnkino, 'fi', NOW);
out.apostrophe_url = icsFor({ ...base, url: APOS_URL }, finnkino, 'fi', NOW);
// The three characters icsText rewrites. No committed ticket URL carries one; this is
// here so the escaping on the URL line is exercised rather than assumed.
out.comma_url = icsFor({ ...base, url: 'https://x.fi/a?list=1,2;3' }, finnkino, 'fi', NOW);
out.iso_start = icsFor({ ...base, start: '2026-11-01T18:00:00+02:00' }, finnkino, 'fi', NOW);   // winter time
out.same_again = icsFor(base, finnkino, 'fi', new Date('2027-01-01T00:00:00Z'));

// -- the place behind a screening: a two-venue combined view and a single view -------
const INDEX = {
  '1100': { id: '1100', name: 'Kinopalatsi Helsinki', provider: 'finnkino' },
  'rv-kallio': { id: 'rv-kallio', name: 'Riviera Kallio', short: 'Kallio', city: 'Helsinki', provider: 'riviera' },
  'cn-tampere': { id: 'cn-tampere', name: 'Cinema Niagara', short: 'Cinema Niagara', city: 'Tampere', provider: 'niagara' },
};
const venueName = s => s.venueLabel || s.venueShort || (s.theatre || '').split(',')[0];
const place = (s, area) => venuePlace(s, area, INDEX, labelOf, cityOf, venueName);
out.place = {
  combined_riviera: place({ theatre: 'Riviera Kallio', venue: 'rv-kallio', _vid: 'rv-kallio', venueLabel: 'Riviera Kallio' }, 'city:Helsinki'),
  combined_finnkino: place({ theatre: 'Kinopalatsi Helsinki', _vid: '1100' }, 'city:Helsinki'),   // the stamped id alone decides
  combined_by_venue_only: place({ theatre: 'Riviera Kallio', venue: 'rv-kallio', venueLabel: 'Riviera Kallio' }, 'city:Helsinki'),
  single_finnkino: place({ theatre: 'Kinopalatsi Helsinki' }, '1100'),
  single_niagara: place({ theatre: 'Cinema Niagara', venue: 'cn-tampere' }, 'cn-tampere'),
  unknown: place({ theatre: 'Plevna Tampere', venueLabel: 'Finnkino Plevna' }, 'city:Tampere'),
};

process.stdout.write(JSON.stringify(out) + '\n');
