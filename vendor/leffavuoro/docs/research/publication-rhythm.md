# When cinemas actually publish their programmes

Moved out of `IDEAS.md` on 2026-09-15. Two independent readings: `scripts/poll_windows.py`
walking consecutive committed data commits, and Finnkino's own published statement. Every
row a window measurement produces is an observation window, never a publication time, and
can never be narrower than the polling interval.

**Status.** Nothing is scheduled off this. As of 2026-08-30 the measurement had 9 organic
arrivals over 4.4 days, too few to set anything by.

**Open.** A local slot shortly after 15:00 Helsinki on a Tuesday would be the highest-value
fetch of the week if Finnkino's stated weekly drop holds. Deliberately not built on a sample
of one, and Finnkino is local-only, so the slot would live in the out-of-repo wrapper. Next
step: collect a few more Tuesdays from the committed data before changing any cadence.

---

### Measuring when cinemas publish (2026-08-30)
`scripts/poll_windows.py` reads committed data and walks every pair of consecutive data
commits, reporting when new schedule data first became visible, so polling slots can follow
the publication rhythm.

Its first three runs reported 125, 20 and 4 arrivals over one history; the difference was
its own bugs, now fixtures in `tests/test_poll_windows.py`:

- ISO strings are not comparable across offsets: the local half commits `+03:00` and the
  runner `+00:00`. Starts are epoch seconds.
- The weekday was the committer's, not the cinema's. Everything is normalised to
  `Europe/Helsinki`.
- An adapter commit usually touches no data file, so the Orion parser landing read as Orion
  publishing 27 screenings. The check covers the whole range since the previous observation.
- A venue whose file is momentarily empty names no provider, so `seen` stopped advancing.
  Venues are attributed globally and first-population is tracked explicitly.

First-seen titles are the weakest signal; the primary measure is future screenings added
between observations, keyed `venue + title + start + aud`, plus horizon extension. Every
row is an observation window, never a publication time, and can never be narrower than the
polling interval. As of 2026-08-30: 9 organic arrivals over 4.4 days, too few to set
anything by.

### Finnkino publishes weekly, Tuesday ~15:00 -- their own statement (2026-09-01)
Finnkino's site: the new programme, Friday through the following Thursday, goes on sale no
later than about 15:00 on Tuesdays; a holiday can push it a day; special cases sell
earlier. The committed data on the morning of Tue 2026-09-01 matched:

    Finnkino, most venues      horizon 2026-09-03    2 days out
    Finnkino 1101 / 1100       horizon 09-06 / 09-07 the "special cases" selling early
    twelve non-Finnkino venues horizon 2026-09-30    29 days out
    eTiketti tail              out to 2026-12-20

A 2-day Finnkino horizon beside a 29-day small-cinema horizon is Finnkino not having sold
the weekend yet, not under-fetching. Prediction: after ~15:00 on a normal Tuesday the
Finnkino horizons jump a week.

For the weekly drop, read the showtime-count signal, not horizon, which a single
advance-sale screening drags. A local slot shortly after 15:00 Helsinki on Tuesdays would
be the highest-value fetch of the week; deliberately not done on a sample of one, and
Finnkino is local-only so the slot lives in the out-of-repo wrapper. Not surfaced in the
UI: promising one chain's policy on behalf of all would break on holidays and special
cases.
