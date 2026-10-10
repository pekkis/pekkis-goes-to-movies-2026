"""The areas the picker offers, and the join between them and the venue data.

`REGIONS` in the registry is the only place a city is assigned to an area, so nothing at
runtime notices a typo or a town that has quietly lost its cinema: the client would draw
an area whose count is short, or none at all. Both directions are asserted here, and
data/regions.json is checked against the registry so an edit without a rebuild fails.

A city is backed either by committed venue data or by an adapter that names it. A
provider is registered one commit and fetched the next, so for that window its cities
are real and its `data/venues-{id}.json` does not exist. A typo appears in neither set.

The two sets agree after the next successful run of a site, not immediately: run.py
writes `data/venues-{provider}.json` from the site's SITES entry, city included
(tests/test_run_partial.py pins that), so a venue added to SITES joins the data on that
run and a venue removed from SITES leaves it then. Between the edit and the run the two
differ, and nothing here compares them: that is the window in which every provider is
added, and a check on it would fail each addition until the pipeline had run. A town
whose cinema is dropped from SITES therefore fails here once the run lands, when the
stale venue file stops backing it.
"""
import importlib
import json
import unittest

import _ctx
import registry

DATA = _ctx.ROOT / "data"


def cities_with_venues():
    """-> {city: venue count} from the committed venue data, Finnkino included."""
    out = {}
    for path in DATA.glob("venues-*.json"):
        for v in json.loads(path.read_text(encoding="utf-8"))["venues"]:
            out[v["city"]] = out.get(v["city"], 0) + 1
    for a in json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]:
        city = a["name"].rsplit(" ", 1)[-1]
        out[city] = out.get(city, 0) + 1
    return out


def cities_declared_by_adapters():
    """-> {city} every adapter's SITES names, run or not.

    Imported inside the function. A provider module imported at the top of a test file
    is captured before `test_common_fetch` reloads `common`, and the stale
    `EmptyProgramme` that leaves behind turns unrelated tests red.
    """
    out = set()
    for name in registry.modules():
        mod = importlib.import_module(name)
        for site in mod.SITES:
            for v in site["venues"]:
                out.add(v["city"])
    return out


def cities_covered():
    """Committed venue data plus the cities the adapters name."""
    return set(cities_with_venues()) | cities_declared_by_adapters()


def dead_entries(regions, backed):
    """-> [(area, city)] for every region city that nothing in `backed` accounts for.

    `backed` is the union of the data's cities and the adapters' cities. The decision is
    kept apart from the file reads so the fetched, not-yet-fetched and typo cases can be
    exercised on fixtures below, and the live check runs the same function over the
    registry.
    """
    return [(r["name"], c) for r in regions for c in r["cities"] if c not in backed]


REGION = {"name": "Testiseutu", "sv": "Testregionen", "en": "Test region",
          "cities": ["Fetched", "Pending"]}


class RegionBackingTest(unittest.TestCase):
    """The cases dead_entries() has to tell apart, on fixtures so they exist whatever the
    committed data holds today. `data` stands for cities_with_venues(), `adapters` for
    cities_declared_by_adapters(); the live test unions the two exactly like this."""

    def backed(self, data=(), adapters=()):
        return set(data) | set(adapters)

    def test_a_fetched_provider_backs_its_city_through_the_data(self):
        self.assertEqual(dead_entries([REGION], self.backed(data=["Fetched", "Pending"])),
                         [])

    def test_a_provider_that_has_not_run_backs_its_city_through_its_adapter(self):
        """Registered this commit, fetched by the next run: the venue file does not exist
        yet and the adapter is the only thing naming the city."""
        self.assertEqual(dead_entries([REGION], self.backed(data=["Fetched"],
                                                            adapters=["Pending"])), [])

    def test_a_city_in_neither_set_is_a_dead_entry(self):
        """A typo, or a town whose cinema has left SITES and whose venue file has since
        been regenerated without it."""
        self.assertEqual(dead_entries([REGION], self.backed(data=["Fetched"])),
                         [("Testiseutu", "Pending")])

    def test_a_dropped_venue_is_still_backed_until_the_run_regenerates_the_data(self):
        """The window this file does not close, stated so it is a decision: after a
        venue leaves SITES its city stays in the stale venue file until the next run,
        and only then does the entry above go dead. Closing it would compare SITES to the
        data directly, which fails every provider addition until the pipeline has run."""
        self.assertEqual(dead_entries([REGION], self.backed(data=["Fetched", "Pending"],
                                                            adapters=["Fetched"])), [])

    def test_every_city_of_every_region_is_checked(self):
        """Two regions and a dead entry in the second, so a loop that stopped at the
        first region or the first city would pass by luck."""
        other = {**REGION, "name": "Toinen seutu", "cities": ["Fetched", "Gone"]}
        self.assertEqual(dead_entries([REGION, other], self.backed(data=["Fetched"],
                                                                    adapters=["Pending"])),
                         [("Toinen seutu", "Gone")])


class RegionsTest(unittest.TestCase):
    def test_a_city_belongs_to_one_area(self):
        """Overlapping areas would offer the same cinema through two rows and make a
        city's area ambiguous."""
        seen = {}
        for r in registry.REGIONS:
            for c in r["cities"]:
                self.assertNotIn(c, seen, f"{c} is in {seen.get(c)} and {r['name']}")
                seen[c] = r["name"]

    def test_every_city_named_has_a_cinema(self):
        """A name that neither the data nor an adapter backs is a dead entry: the
        area's count is short and nothing else says so."""
        self.assertEqual(dead_entries(registry.REGIONS, cities_covered()), [],
                         "no venue file and no adapter backs these")

    def test_an_area_holds_two_cinema_cities(self):
        """One city is not an area, it is that city's own combined row under a second
        name. The client drops such an area as well; this says so at the source."""
        have = cities_covered()
        for r in registry.REGIONS:
            live = [c for c in r["cities"] if c in have]
            self.assertGreaterEqual(len(live), 2, r["name"])

    def test_the_generated_file_matches_the_registry(self):
        """data/regions.json is generated by scripts/build_regions.py. Committed stale, the
        client draws yesterday's areas."""
        body = json.loads((DATA / "regions.json").read_text(encoding="utf-8"))
        self.assertEqual(body["regions"], registry.regions())

    def test_the_published_file_carries_only_what_the_client_reads(self):
        """The registry row and the published one are the same four keys since the `km`
        field was deleted on 2026-09-18. Nothing may reach data/ that the client does not
        read: a figure there reads as measured whether or not anyone measured it."""
        body = json.loads((DATA / "regions.json").read_text(encoding="utf-8"))
        for r in body["regions"] + registry.regions() + registry.REGIONS:
            self.assertEqual(sorted(r), ["cities", "en", "name", "sv"])

    def test_every_area_is_named_in_three_languages(self):
        """An area with no translation reads out in Finnish to an English reader, and the
        search misses it entirely when the query is in their language."""
        for r in registry.REGIONS:
            for key in ("name", "sv", "en"):
                self.assertTrue(r.get(key), f"{r['name']} has no {key}")

    def test_no_two_areas_share_a_name_in_any_language(self):
        """Two areas reading the same in one language would make the picker ambiguous in
        that language only."""
        for key in ("name", "sv", "en"):
            names = [r[key] for r in registry.REGIONS]
            self.assertEqual(len(names), len(set(names)), key)


if __name__ == "__main__":
    unittest.main()
