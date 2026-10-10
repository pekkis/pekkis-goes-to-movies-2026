# Counts

Generated. Run `python3 scripts/build_counts.py` to rewrite the block below and sync the
four figures README states in prose; `--check` reports without writing, and `--posters`
prints the two figures this file does not carry.

Do not edit the block by hand. These numbers were kept by hand in `IDEAS.md` and
re-measured twenty-two times, and five of those passes shipped a wrong one. Every figure
here is derived from `data/`, `scripts/providers/registry.py`, `sitemap.xml` and `sw.js`.
The city rule is `build_pages.city_of`, reused rather than reimplemented, because
Finnkino's areas carry no `city` field and the city sits in the venue name.

Every row below is a pure function of the tree, so the block regenerates byte-identical
and CI's regeneration-drift step checks it beside the other generators.
`tests/test_build_counts.py` pins it as well: the suite answers "is the committed file
current" on a push that regenerates nothing, and the drift step answers "does regenerating
change anything". Different questions, both worth asking.

Off-origin poster references are in the table because that figure is an invariant rather
than a measurement. `safeAssetUrl` refuses a poster outside `data/posters/`, and README's
claim that a page load reaches no third party rests on it being 0.

**Two figures are measured and deliberately not committed:** how many poster references
exist, and how many mirrored files back them. Both move on every data run, a data run does
not re-run this script, and nothing in the repo or the client reads them, so a committed
copy would be behind the data beside it as often as not and would fail the drift step on
the next unrelated push. Print them instead:

    python3 scripts/build_counts.py --posters

Earlier hand-measured passes, and what each of them measured, are in
[archive/2026-09-ops.md](archive/2026-09-ops.md).

<!-- counts:start -->
| | |
|---|---:|
| providers | 83 |
| venues | 134 |
| cities | 96 |
| cities with more than one venue | 17 |
| local providers (venues) | 14 (36) |
| venues per adapter, largest 5 | `etiketti` 31, `Finnkino` 17, `nexxo` 13, `biorex` 12, `johku` 6 |
| generated pages per language | 151 |
| sitemap URLs | 454 |
| off-origin poster references | 0 |
| `sw.js` CACHE | `leffavuoro-v278` |
<!-- counts:end -->
