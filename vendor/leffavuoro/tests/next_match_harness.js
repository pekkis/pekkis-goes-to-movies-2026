// Drives index.html's nextMatch() against controlled schedules.
//
// The block is sliced verbatim out of index.html between its marker comments, the way
// kidsGates and the others are, together with the Helsinki date helpers it is given.
// What it pins: the earliest screening on a later day than the selected one that is
// still ahead of now and passes the list's own predicate; a blank query means no
// suggestion; a past screening on a later day never wins; the Helsinki date, not the
// UTC date, decides which day a screening belongs to.
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
const SRC = slice('  // --- nextMatch: pure, extracted verbatim by tests/next_match_harness.js ---',
                  '  // --- end nextMatch ---', 'nextMatch');
if (!/function nextMatch\s*\(/.test(SRC)) {
  console.error('marker block does not contain nextMatch');
  process.exit(2);
}
// The date helpers as the page defines them, so the boundary case runs the shipped
// formatter rather than a re-implementation.
const HELPERS = HTML.slice(HTML.indexOf("  const FI_TZ = 'Europe/Helsinki';"),
                           HTML.indexOf('  const fiToday = () => fiDate(new Date());'));
if (!/fiDate = /.test(HELPERS)) {
  console.error('date helpers not found in index.html');
  process.exit(2);
}
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(HELPERS + '\n' + SRC + '\n;globalThis.__n = nextMatch; globalThis.__d = fiDate;',
                sandbox, { filename: 'nextMatch' });
const nextMatch = sandbox.__n;
const fiDate = sandbox.__d;

// Helsinki is UTC+3 in September. `at` is 'YYYY-MM-DDTHH:MM' Helsinki wall time.
const show = (title, at, extra) =>
  Object.assign({ title, start: new Date(at + ':00+03:00'), eventId: title }, extra || {});
const has = (q) => (s) => s.title.toLowerCase().includes(q.toLowerCase());
const out = {};
const pick = (hit) => hit ? { title: hit.title, iso: fiDate(hit.start), at: hit.start.toISOString() } : null;

// 1. nothing today, the film plays tomorrow
const now = new Date('2026-09-15T10:00:00+03:00');
out.tomorrow = pick(nextMatch(
  [show('Other', '2026-09-15T18:00'), show('Dune', '2026-09-16T19:30')],
  'dune', '2026-09-15', now, has('dune'), fiDate));

// 2. several days later, other films in between
out.days_later = pick(nextMatch(
  [show('Other', '2026-09-16T18:00'), show('Other', '2026-09-17T18:00'),
   show('Dune', '2026-09-19T15:00'), show('Other', '2026-09-18T18:00')],
  'dune', '2026-09-15', now, has('dune'), fiDate));

// 3. an earlier candidate fails an active filter (a stand-in predicate: only FI-A)
const fiOnly = (s) => has('dune')(s) && /FI-A/.test(s.lang || '');
out.filtered = pick(nextMatch(
  [show('Dune', '2026-09-16T19:30', { lang: 'EN-A' }), show('Dune', '2026-09-18T19:30', { lang: 'FI-A' })],
  'dune', '2026-09-15', now, fiOnly, fiDate));

// 4. no future match
out.none = pick(nextMatch(
  [show('Other', '2026-09-16T18:00'), show('Dune', '2026-09-15T09:00')],
  'dune', '2026-09-15', now, has('dune'), fiDate));

// 5. every match today has passed; a later one is offered
out.today_passed = pick(nextMatch(
  [show('Dune', '2026-09-15T09:00'), show('Dune', '2026-09-15T09:30'), show('Dune', '2026-09-17T12:00')],
  'dune', '2026-09-15', now, has('dune'), fiDate));

// 6. unsorted input, several matches: the earliest wins
out.earliest = pick(nextMatch(
  [show('Dune', '2026-09-20T12:00'), show('Dune', '2026-09-16T21:00'), show('Dune', '2026-09-16T12:15'),
   show('Dune', '2026-09-18T12:00')],
  'dune', '2026-09-15', now, has('dune'), fiDate));

// 9. whitespace-only search is no search
out.blank = pick(nextMatch([show('Dune', '2026-09-16T19:30')], '   ', '2026-09-15', now, () => true, fiDate));
out.empty = pick(nextMatch([show('Dune', '2026-09-16T19:30')], '', '2026-09-15', now, () => true, fiDate));

// 10. the Helsinki date decides, not UTC: 00:30 Helsinki on the 16th is 21:30 UTC on the 15th
out.boundary_after_midnight = pick(nextMatch(
  [show('Dune', '2026-09-16T00:30')], 'dune', '2026-09-15', now, has('dune'), fiDate));
// and 23:30 Helsinki on the 15th (20:30 UTC) is still the selected day, so not a later one
out.boundary_same_day = pick(nextMatch(
  [show('Dune', '2026-09-15T23:30')], 'dune', '2026-09-15', now, has('dune'), fiDate));

// a later day whose screening is already past (the selected day lies behind now)
out.later_day_but_past = pick(nextMatch(
  [show('Dune', '2026-09-16T09:00')], 'dune', '2026-09-15',
  new Date('2026-09-16T12:00:00+03:00'), has('dune'), fiDate));

// bad input stays quiet
out.bad_start = pick(nextMatch([{ title: 'Dune', start: 'not a date' }, { title: 'Dune' }],
  'dune', '2026-09-15', now, has('dune'), fiDate));

process.stdout.write(JSON.stringify(out));
