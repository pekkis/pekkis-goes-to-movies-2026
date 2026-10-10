// Runs index.html's own startsAtOrAfter() against a table of (clock, min) cases.
// Driven by tests/test_time_filter.py; prints one JSON line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its
// own: it is a pure function of two HH:MM strings, so it needs no DOM and no clock.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- startsAtOrAfter: pure, extracted verbatim by tests/time_filter_harness.js ---';
const END = '// --- end startsAtOrAfter ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('startsAtOrAfter markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
if (!/const startsAtOrAfter\s*=/.test(source)) {
  console.error('marker block does not contain startsAtOrAfter');
  process.exit(2);
}

const S2 = '// --- timeSlots: pure, extracted verbatim by tests/time_filter_harness.js ---';
const E2 = '// --- end timeSlots ---';
const c = HTML.indexOf(S2), d = HTML.indexOf(E2);
if (c === -1 || d === -1 || d < c) {
  console.error('timeSlots markers not found in index.html');
  process.exit(2);
}
const slotSrc = HTML.slice(c, d);

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source + '\n' + slotSrc
  + '\nthis.startsAtOrAfter = startsAtOrAfter; this.timeSlots = timeSlots;', sandbox);
const f = sandbox.startsAtOrAfter;
const slots = sandbox.timeSlots;

const cases = {
  // No restriction: the default, and every screening passes.
  no_min_empty:        ['18:00', ''],
  no_min_null:         ['18:00', null],
  no_min_undefined:    ['18:00', undefined],
  // The boundary. "Alkaen 18:00" includes the 18:00 screening.
  exactly_at:          ['18:00', '18:00'],
  one_minute_before:   ['17:59', '18:00'],
  one_minute_after:    ['18:01', '18:00'],
  // Zero-padding is what makes a string compare a time compare.
  morning_vs_evening:  ['09:00', '10:00'],
  evening_vs_morning:  ['10:00', '09:00'],
  padded_nine_vs_ten:  ['09:59', '09:00'],
  // Ends of the day.
  midnight_vs_evening: ['00:30', '18:00'],
  late_vs_midnight:    ['23:45', '00:00'],
  midnight_exact:      ['00:00', '00:00'],
  // A screening with no readable clock is not admitted while a restriction is on.
  blank_clock:         ['', '18:00'],
  null_clock:          [null, '18:00'],
  // ...but with no restriction it is not excluded either.
  blank_clock_no_min:  ['', ''],
};

const out = {};
for (const [k, [clock, min]] of Object.entries(cases)) {
  try {
    out[k] = f(clock, min);
  } catch (e) {
    out[k] = { threw: String((e && e.message) || e) };
  }
}
// Half-hour marks. `now` is passed only for today; another day has no "now" to sit behind.
const slotCases = {
  today_starts_30_back:   [['13:00', '18:00', '21:30'], '18:05'],
  today_rounds_down:      [['13:00', '22:00'], '18:29'],
  today_on_the_half:      [['13:00', '22:00'], '18:30'],
  today_before_first:     [['20:00', '21:00'], '06:10'],
  other_day_from_first:   [['13:10', '15:00', '18:40'], ''],
  other_day_single:       [['19:20'], ''],
  now_past_last:          [['13:00', '14:00'], '23:30'],
  early_morning_clamped:  [['10:00', '12:00'], '00:10'],
  no_screenings:          [[], '18:00'],
  junk_ignored:           [['nope', '18:00', ''], ''],
  all_junk:               [['nope', ''], ''],
};
const slotOut = {};
for (const [k, [clocks, now]] of Object.entries(slotCases)) {
  try { slotOut[k] = slots(clocks, now); }
  catch (e) { slotOut[k] = { threw: String((e && e.message) || e) }; }
}
process.stdout.write(JSON.stringify({ after: out, slots: slotOut }) + '\n');
