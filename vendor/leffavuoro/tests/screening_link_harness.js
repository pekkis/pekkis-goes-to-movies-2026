// Drives index.html's screeningHash(), screeningUrl(), parseSheetHash() and
// screeningTarget() against fixed inputs. Driven by tests/test_screening_link.py; prints
// one JSON line.
//
// The block is sliced verbatim out of index.html between its marker comments, the way
// nextMatch and the area routing are, together with nextMatch itself (screeningTarget
// falls back to it) and the Helsinki date helpers, so the real code runs.
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
const SRC = slice('  // --- screening link: pure, extracted verbatim by tests/screening_link_harness.js ---',
                  '  // --- end screening link ---', 'screening link');
for (const fn of ['screeningHash', 'screeningUrl', 'parseSheetHash', 'screeningTarget', 'shareText', 'menuSide']) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(SRC)) {
    console.error('marker block does not contain ' + fn);
    process.exit(2);
  }
}
const NEXT = slice('  // --- nextMatch: pure, extracted verbatim by tests/next_match_harness.js ---',
                   '  // --- end nextMatch ---', 'nextMatch');
const HELPERS = HTML.slice(HTML.indexOf("  const FI_TZ = 'Europe/Helsinki';"),
                           HTML.indexOf('  const fiToday = () => fiDate(new Date());'));
if (!/fiDate = /.test(HELPERS)) {
  console.error('date helpers not found in index.html');
  process.exit(2);
}
const sandbox = { URL, URLSearchParams, encodeURIComponent };
vm.createContext(sandbox);
vm.runInContext(HELPERS + '\n' + NEXT + '\n' + SRC
                + '\n;globalThis.__h = screeningHash; globalThis.__u = screeningUrl;'
                + 'globalThis.__p = parseSheetHash; globalThis.__t = screeningTarget; globalThis.__d = fiDate;'
                + 'globalThis.__x = shareText; globalThis.__m = menuSide;',
                sandbox, { filename: 'screeningLink' });
const screeningHash = sandbox.__h, screeningUrl = sandbox.__u;
const parseSheetHash = sandbox.__p, screeningTarget = sandbox.__t, fiDate = sandbox.__d;
const shareText = sandbox.__x, menuSide = sandbox.__m;

const out = { hash: {}, url: {}, parse: {}, target: {}, share: {}, side: {} };

// -- building ---------------------------------------------------------------------------
out.hash.plain = screeningHash('HO00000413');
out.hash.full = screeningHash('HO00000413', '2026-09-13', '2026-09-13T15:10:00+03:00');
out.hash.with_venue = screeningHash('spider man', '2026-09-13', '2026-09-13T17:00:00+03:00', '1151');
out.hash.odd_id = screeningHash('a&b=c #x', '', '');
out.url.full = screeningUrl('https://leffavuoro.fi/?area=old&lang=sv#m=zzz', '1004',
                            'HO00000413', '2026-09-13', '2026-09-13T15:10:00+03:00', '1004');
out.url.bare = screeningUrl('https://leffavuoro.fi/', 'city:Helsinki', '1499');
out.url.from_page = screeningUrl('https://leffavuoro.fi/kaupunki/tampere/', 'city:Tampere', '61');

// -- parsing -----------------------------------------------------------------------------
out.parse.round_trip = parseSheetHash('#' + out.hash.full);
out.parse.with_venue = parseSheetHash('#' + out.hash.with_venue);
out.parse.odd_id = parseSheetHash('#' + out.hash.odd_id);
out.parse.old_link = parseSheetHash('#m=HO00000413');
out.parse.old_link_encoded = parseSheetHash('#m=' + encodeURIComponent('Ryhmä Hau: Dinoelokuva'));
out.parse.bad_day = parseSheetHash('#m=x&d=2026-9-1&t=2026-09-13T15:10:00+03:00');
out.parse.bad_start = parseSheetHash('#m=x&d=2026-09-13&t=tonight');
out.parse.no_film = parseSheetHash('#d=2026-09-13&t=2026-09-13T15:10:00%2B03:00');
out.parse.empty_film = parseSheetHash('#m=&d=2026-09-13');
out.parse.nothing = parseSheetHash('');
out.parse.other_hash = parseSheetHash('#top');

// -- the screening the sheet opens on --------------------------------------------------
// Helsinki is UTC+3 in September. `at` is 'YYYY-MM-DDTHH:MM' Helsinki wall time.
const show = (at, vid) => ({ start: new Date(at + ':00+03:00'), at, _vid: vid || '1004' });
const shows = ['2026-09-13T12:00', '2026-09-13T15:10', '2026-09-14T18:00', '2026-09-16T20:45'].map(a => show(a));
const now = new Date('2026-09-13T14:00:00+03:00');
const pick = (hit) => hit ? hit.at : null;
const target = (want) => pick(screeningTarget(shows, want, now, fiDate));
out.target.exact_ahead = target({ day: '2026-09-13', start: '2026-09-13T15:10:00+03:00' });
out.target.exact_other_offset = target({ day: '', start: '2026-09-13T12:10:00Z' });     // same instant, UTC
out.target.exact_gone_same_day = target({ day: '2026-09-13', start: '2026-09-13T12:00:00+03:00' });
out.target.start_unknown_day_known = target({ day: '2026-09-14', start: '2026-09-14T21:00:00+03:00' });
out.target.day_only = target({ day: '2026-09-16', start: '' });
out.target.day_past = target({ day: '2026-09-12', start: '2026-09-12T18:00:00+03:00' });
out.target.day_without_screenings = target({ day: '2026-09-15', start: '' });
out.target.nothing_named = target({ day: '', start: '' });
out.target.no_want = pick(screeningTarget(shows, null, now, fiDate));
out.target.all_gone = pick(screeningTarget(shows, { day: '2026-09-13', start: '' },
                                           new Date('2026-09-17T00:00:00+03:00'), fiDate));
out.target.empty = pick(screeningTarget([], { day: '2026-09-13', start: '' }, now, fiDate));
// Two cinemas in one combined view, the same film at the same minute (Sello and Omena,
// 17:00), plus a later Omena screening and a Sello one the next day.
const pair = [show('2026-09-13T17:00', '1151'), show('2026-09-13T17:00', '1157'),
              show('2026-09-13T20:30', '1157'), show('2026-09-14T17:00', '1151')];
const pickV = (hit) => hit ? hit.at + '@' + hit._vid : null;
const targetV = (want) => pickV(screeningTarget(pair, want, now, fiDate));
out.target.pair_sello = targetV({ day: '2026-09-13', start: '2026-09-13T17:00:00+03:00', venue: '1151' });
out.target.pair_omena = targetV({ day: '2026-09-13', start: '2026-09-13T17:00:00+03:00', venue: '1157' });
out.target.pair_no_venue = targetV({ day: '2026-09-13', start: '2026-09-13T17:00:00+03:00', venue: '' });
out.target.pair_venue_time_gone = targetV({ day: '2026-09-13', start: '2026-09-13T16:00:00+03:00', venue: '1157' });
out.target.pair_venue_time_moved = targetV({ day: '2026-09-13', start: '2026-09-13T16:00:00+03:00', venue: '1151' });
out.target.pair_unknown_venue = targetV({ day: '2026-09-13', start: '2026-09-13T17:00:00+03:00', venue: 'zzz' });

// -- the share text and the menu's side (v145) -----------------------------------------
out.share.with_hall = shareText('Ryhmä Hau: Dinoelokuva', 'Finnkino Promenadi', 'Sali 3', 'Ti 15.9.', 'klo', '16:30');
out.share.no_hall = shareText('Kino Regina', 'Kino Regina', '', 'La 13.9.', 'kl.', '20:45');
out.share.verbatim = shareText('<b>A & B</b>', 'V', 'H', 'D', 'at', 'T');
out.side.far_from_edge = menuSide(120, 375);
out.side.at_199_no_room_left = menuSide(176, 375);   // the single-view ticket at 375
out.side.at_199_room_left = menuSide(1001, 1200);
out.side.at_200 = menuSide(1000, 1200);
out.side.at_edge = menuSide(375, 375);
out.side.wide = menuSide(900, 1200);

process.stdout.write(JSON.stringify(out) + '\n');
