# Chain accents: how they are measured and what binds them

Moved out of `IDEAS.md` on 2026-09-15. `scripts/accent_check.py` is the method and the
only source for a number here: the figures that used to sit in `IDEAS.md` were CIE76
mislabelled as ΔE and are corrected below. Run `--selftest` to check the implementation
against Sharma, Wu & Dalal's reference data.

**Status.** The rule is in [CLAUDE.md](../../CLAUDE.md) under "Adding a provider": score on
the weakest of normal vision and both deuteranope models, clear 14.4 ΔE00 in every view a
new accent enters where that is reachable, and never lower an existing regional minimum
without recording why. `FLOOR = 14.4` is that policy threshold, not a measurement.

**Open.** Fourteen established region pairs sit below 14.4 and none is recoloured, of 170
shared-view pairs measured 2026-09-19; the twelve the entry below lists are the twelve that
were below on 2026-09-07, and `tests/test_accent_check.py` holds the current totals. Next
step: nothing, unless a new provider lands in one of those regions, which is when the pair
has to be re-measured.

---

### The accent rule covers regions as well as cities (2026-09-07)
`scripts/accent_check.py` compared chains that share a city. Region rows shipped in v125
and list every chain in a region's cities together, so two chains in different towns of one
region sit side by side without ever sharing a city. The tool cleared those pairs because
it could not see them.

`shared_view_pairs()` replaces `shared_city_pairs()` and builds both views: the combined
cities, and the regions read from `registry.REGIONS`. There is no second list to maintain.
Provider cities come from the committed `data/venues-*.json` and from the adapters'
`SITES`, so a provider that is registered but not yet fetched is included. An accent is
chosen in exactly that window, and Cine had no venue file when this was measured.

Cine's `#FE4719` measured 3.9 dE00 against Kino Akseli under both deuteranope models.
Kerava and Nummela are different towns in Keski-Uusimaa, so the city-only check reported
nothing at all. Cine now carries `#BA7E8A`, L\* 59.2, worst case 21.4: BioRex
34.7 / 37.7 / 35.6, Kino Akseli 33.1 / 22.3 / 21.5, Kino Juha 26.6 / 24.7 / 23.9,
Studio 123 Järvenpää 23.0 / 25.8 / 23.6, Kino Marilyn 51.5 / 21.4 / 21.4.

An exhaustive search at step 2 over the L\* 38 to 60 band tops out at `#BC808E` with 22.2
at L\* 60.0. That is 0.8 dE00 better on the band edge, so `#BA7E8A` at L\* 59.2 was kept.
`separation()` is the one scorer: the minimum across normal vision and both deuteranope
models. `--search`, the ordinary report and `--all` rank and count through it, so a colour
whose normal-vision separation is the binding one cannot sort as though it were fine. On
its own step 6 grid `--search` returns `#BA7E8A` first.

A combined-city pair holds a strict 14.4 dE00 minimum across normal vision and both
deuteranope models, and the worst is exactly that, Finnkino against Cinema Orion. Region
pairs are measured on the same scale because a region row is one result view, but twelve
of the 139 pairs sat below 14.4 on the day this was written and every one is an
established colour: Bio Grand and
BioRex at 4.479 in Pääkaupunkiseutu, BioRex and Kinopirtti at 5.7 in Meri-Lappi, Bio Grani
and Kino Regina at 6.8, Heureka and Kino Regina at 7.1, Bio Grani and Gilda at 14.093, and
seven more. None is recoloured here. Bio Grani and Gilda is the pair a deutan-only count
missed: 19.942 apart under both simulations, 14.093 in normal vision, so it read as clear
while normal vision was the binding model. A new or changed accent clears 14.4 in every view it enters where that is reachable,
and must not lower an existing regional minimum without the reason recorded here. Colour
stays supplementary in both views, which also print the venue name and the chain legend.

### FLOOR is the policy threshold, not a measurement (2026-09-12)
`FLOOR = 14.4` in `accent_check.py` began as the worst combined-city pair, Finnkino against
Cinema Orion, which measures 14.425. Read as a measurement it is a coincidence 0.025 dE00
wide, and a mutation to 14.3 or 14.42 turned nothing red because the only test reused
`A.FLOOR` in its own arithmetic. It is the threshold CLAUDE.md and the registry already
state as policy, so the comment now says so, one test pins the literal, and another asserts
every combined-city pair clears 14.4 written out. Scoring and the printed count are
unchanged.

### Accent views are keyed by kind as well as name (2026-09-12)
`shared_view_pairs()` built both views in one dict keyed on the bare name, so a region
named like a city would have merged with that city's pairs under one label. No current
region name is a city name, and the client never had the problem (it keys areas as
`region:` plus the name), but nothing enforced it in the tool. `view_pairs()` now keys on
`("city", name)` and `("region", name)` and returns the kind with each pair;
`shared_view_pairs()` is the same list without the kind, which is what the report prints.
A fixture test with a region called "Tampere" shows the two views staying apart.

### The accent numbers, re-derived (2026-08-30)
The recorded ΔE figures could not be reproduced. Re-derived with `scripts/accent_check.py`
(sRGB -> linear via IEC 61966-2-1; deuteranope simulation on linear RGB by
Viénot–Brettel–Mollon 1999 and Machado–Oliveira–Fernandes 2009 at severity 1.0; XYZ ->
CIELAB D65; CIEDE2000; `--selftest` against 15 pairs of Sharma, Wu & Dalal's reference
data), the result: the old figures were CIE76 labelled ΔE, and one same-city pair was a
single colour to a deuteranope.

CIE76 reproduces three recorded normal-vision numbers to the decimal:

| recorded as | pair | CIE76 | CIEDE2000 |
|---|---|---|---|
| 25.9 | old Finnkino / old Gilda | **25.9** | 15.3 |
| 46.9 | BioRex / Riviera, normal | **46.9** | 23.3 |
| 36.9 | Engel / BioRex, normal | **36.9** | 18.5 |

The recorded deuteranope figures (34.5, 28.0, 37.3, 5.0) match no model at any severity
and are not quoted again. Corrected, with the harsher model:

| claim | recorded | measured |
|---|---|---|
| worst same-city pair, normal | 46.9 | 18.5 (Engel/Gilda) |
| worst same-city pair, deutan | 28.0 | **3.9 (BioRex/Riviera)** |
| old Finnkino / old BioRex, deutan | 5.0 | 1.8 |
| global minimum, any pair, deutan | 32.1 | 0.7 (Finnkino/Kino Akseli) |

Four of 45 cities had more than one chain on 2026-08-30 (Helsinki with six, Vantaa, Lahti,
Kouvola); Kotka has one chain, so the old "Kotka only ever shows two chains" claim is
retired. Superseded 2026-09-01: Kino Metso made Jyväskylä a third chain city, 5 of 52;
its worst pair is 26.9 ΔE00 deutan and the set's worst stays Helsinki's 14.4.

Decisions:
- Riviera moved from `#7B3FD4` to `#0C6464`: blue and violet differ mostly in the red-green
  channel a deuteranope lacks, so BioRex and Riviera sat 3.9 apart in the one city where
  they meet. Riviera rather than BioRex because Riviera's two venues are both in Helsinki
  while BioRex is unconstrained in twelve towns. The tiebreak among candidates clearing
  14.4 was normal vision: `#0C6464` scores 16.5 deutan / 28.1 normal against `#24664E` at
  19.1 / 18.8. Only six hue families clear the ceiling, all at L* 38-39.
- Kino Akseli's gold at 0.7 from Finnkino's orange stays: Nummela has one chain.
- "About the ceiling for six chains" was wrong. Five of the six Helsinki colours are free,
  and a greedy max-min search over the same L* band reaches 19.5 deutan / 21.0 normal.
  Not applied: it moves five learned accents and the current floor hurts nobody.
- `--city` took a list and used only the first entry, so a candidate could be cleared in
  Helsinki while colliding in Tampere. Fixed to measure every city; a bare string is
  wrapped rather than iterated.
