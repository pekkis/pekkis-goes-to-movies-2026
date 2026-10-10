"""accent_check: the colour maths, against published reference data.

The whole reason this script exists is that the previous accent numbers could not be
checked. A colour tool whose own arithmetic is unverified is the same failure one level
down, so the CIEDE2000 implementation is pinned to Sharma, Wu & Dalal's published pairs
here as well as in --selftest.
"""
import collections
import contextlib
import io
import unittest
from unittest import mock

import _ctx                                                # noqa: F401
import accent_check as A


class Ciede2000Test(unittest.TestCase):
    def test_matches_sharma_reference_pairs(self):
        """Every pair, not the first one: the branches that get implementations wrong
        are the hue wrap and the RT rotation, and only some pairs reach them."""
        self.assertGreaterEqual(len(A.SHARMA), 10)
        for lab1, lab2, want in A.SHARMA:
            with self.subTest(pair=(lab1, lab2)):
                self.assertAlmostEqual(A.ciede2000(lab1, lab2), want, places=4)

    def test_a_colour_is_zero_from_itself(self):
        self.assertEqual(A.dE("#E4551F", "#E4551F"), (0.0, 0.0, 0.0))

    def test_grey_is_unmoved_by_either_dichromat_model(self):
        """The confusion line runs through the neutral axis, so a grey that shifts means
        the simulation is being applied in the wrong space."""
        for grey in ("#808080", "#333333", "#CCCCCC"):
            with self.subTest(grey=grey):
                labs = A.labs_for(grey)
                for i in (1, 2):
                    self.assertLess(A.ciede2000(labs[0], labs[i]), 1.0)

    def test_the_transfer_function_is_piecewise_not_gamma_22(self):
        """They differ most in the dark end, which is where several accents sit."""
        self.assertAlmostEqual(A.srgb_to_linear(0.02), 0.02 / 12.92, places=9)
        self.assertNotAlmostEqual(A.srgb_to_linear(0.02), 0.02 ** 2.2, places=4)


class SharedViewTest(unittest.TestCase):
    """Two views list chains side by side: a combined city, and a region row. The 3 px
    accent rule has to hold in both, so both are generated here from registry.REGIONS and
    the provider cities rather than from a list kept in the tool."""

    def test_pairs_come_from_the_data_not_a_hand_list(self):
        pairs = A.shared_view_pairs()
        self.assertTrue(pairs, "no shared-view pairs found at all")
        for view, a, b in pairs:
            self.assertNotEqual(a, b)
            self.assertLess(a, b, "pairs should be ordered so they cannot duplicate")

    def test_every_region_with_two_chains_is_a_view(self):
        """The regions are read from registry.REGIONS. A region that stopped producing
        pairs would mean the region half of the model had been dropped."""
        by = A.provider_cities()
        views = {v for v, a, b in A.shared_view_pairs()}
        for r in A.registry.REGIONS:
            here = {p for p, cs in by.items() if cs & set(r["cities"])}
            if len(here) >= 2:
                self.assertIn(r["name"], views, f"{r['name']} has {len(here)} chains "
                                                f"and produced no pair")

    def test_a_region_pair_is_not_only_a_city_pair(self):
        """Two chains in different towns of one region never share a city, so a
        city-only model would report nothing for them."""
        cities = {v for v, a, b in A.shared_view_pairs()} & {
            c for r in A.registry.REGIONS for c in r["cities"]}
        pairs = A.shared_view_pairs()
        cross = [(v, a, b) for v, a, b in pairs
                 if v == "Keski-Uusimaa" and {a, b} == {"cine", "kinoakseli"}]
        self.assertEqual(len(cross), 1, "Cine and Kino Akseli are in one region")
        same_city = [(v, a, b) for v, a, b in pairs
                     if v in cities and {a, b} == {"cine", "kinoakseli"}]
        self.assertEqual(same_city, [], "they are in different towns")

    def test_a_provider_with_no_venue_file_brings_its_declared_cities(self):
        """A provider is registered one commit and fetched the next. Its accent is chosen
        in that window, so the adapter's own cities have to count. Fixtures rather than
        the committed data: the day Cine's venue file landed, the data started supplying
        the very pair this used to check, and a broken merge went unnoticed.

        The newcomer is absent from the data by construction and present only in the
        adapters. It has to meet the established chain in the region row through a city
        of its own, and in the city view when it lands in the established chain's town."""
        regions = [{"name": "Keski-Uusimaa", "cities": ["Kerava", "Nummela"]}]
        data = {"kinoakseli": {"Nummela"}}
        with mock.patch.object(A, "cities_by_provider", return_value=dict(data)), \
                mock.patch.object(A, "cities_declared_by_adapters",
                                  return_value={"newcomer": {"Kerava"}}), \
                mock.patch.object(A.registry, "REGIONS", regions):
            self.assertNotIn("newcomer", A.cities_by_provider())
            self.assertEqual(A.provider_cities(),
                             {"kinoakseli": {"Nummela"}, "newcomer": {"Kerava"}})
            self.assertIn(("Keski-Uusimaa", "kinoakseli", "newcomer"),
                          A.shared_view_pairs())
        with mock.patch.object(A, "cities_by_provider", return_value=dict(data)), \
                mock.patch.object(A, "cities_declared_by_adapters",
                                  return_value={"newcomer": {"Nummela"}}), \
                mock.patch.object(A.registry, "REGIONS", regions):
            self.assertIn(("Nummela", "kinoakseli", "newcomer"), A.shared_view_pairs())

    def test_cine_meets_kino_akseli_in_the_keski_uusimaa_row(self):
        """The real pair the fixture above stands for. Kerava and Nummela are different
        towns, so it exists only in the region view."""
        self.assertEqual(A.cities_declared_by_adapters()["cine"], {"Kerava", "Sipoo"})
        self.assertIn(("Keski-Uusimaa", "cine", "kinoakseli"), A.shared_view_pairs())

    def test_star_meets_finnkino_in_oulu(self):
        self.assertIn("Oulu", A.cities_declared_by_adapters()["star"])
        self.assertIn(("Oulu", "finnkino", "star"), A.shared_view_pairs())

    def test_a_candidate_in_kerava_is_measured_against_the_whole_region(self):
        """Kerava has one cinema, so a city-only check would clear a candidate against
        Cine alone and miss the four chains it meets in the Keski-Uusimaa row."""
        by = A.provider_cities()
        ku = next(r for r in A.registry.REGIONS if r["name"] == "Keski-Uusimaa")
        expect = {p for p, cs in by.items() if cs & set(ku["cities"])}
        pairs = A.shared_view_pairs(extra=("candidate", ["Kerava"]))
        got = {b if a == "candidate" else a for v, a, b in pairs
               if v == "Keski-Uusimaa" and "candidate" in (a, b)}
        self.assertEqual(got, expect)
        self.assertGreaterEqual(len(expect), 4)

    def test_a_candidate_is_measured_against_every_city_it_is_given(self):
        """--city took a comma-separated list and then broke after the first entry, so a
        candidate could be cleared in city A while colliding in city B. A validation tool
        that can approve falsely is worse than no tool.

        Two cities minimum, and the candidate has to appear in both, or the loop is
        never exercised."""
        base = {c for c, a, b in A.shared_view_pairs()}
        pairs = A.shared_view_pairs(extra=("candidate", ["Helsinki", "Tampere"]))
        views = {c for c, a, b in pairs if "candidate" in (a, b)}
        self.assertIn("Helsinki", views)
        self.assertIn("Tampere", views,
                      "second city dropped: the candidate loop stops after the first")
        self.assertTrue(base.issubset({c for c, a, b in pairs}),
                        "adding a candidate lost an existing view's pairs")

    def test_a_bare_string_is_one_city_not_a_sequence_of_letters(self):
        """`for c in "Helsinki"` yields 'H', 'e', 'l' ... which would quietly measure
        the candidate against nothing at all."""
        pairs = A.shared_view_pairs(extra=("candidate", "Helsinki"))
        cities = {c for c, a, b in pairs if "candidate" in (a, b)} - {
            r["name"] for r in A.registry.REGIONS}
        self.assertEqual(cities, {"Helsinki"})

    def test_a_candidate_in_a_one_chain_city_is_measured_against_that_one_chain(self):
        """Kokkola has a single cinema today, so a candidate landing there makes exactly
        one pair in the city view. Written after the first version of this test asserted
        zero pairs and was wrong: one existing chain plus a candidate is a pair, which is
        the whole point of asking."""
        pairs = [p for p in A.shared_view_pairs(extra=("candidate", ["Kokkola"]))
                 if p[0] == "Kokkola"]
        self.assertEqual(len(pairs), 1)
        self.assertIn("biorexkokkola", pairs[0])

    def test_cine_clears_the_city_view_floor_in_every_view_it_appears_in(self):
        """Cine is alone in Kerava and in Sipoo, so the city check cleared it while its
        accent sat 3.9 dE00 from Kino Akseli in the Keski-Uusimaa row. 14.4 is the worst
        pair any city view holds, and Cine has to reach it in the region rows too."""
        accents = {p["id"]: p["accent"] for p in A.registry.PROVIDERS}
        pairs = [(v, a, b) for v, a, b in A.shared_view_pairs() if "cine" in (a, b)]
        self.assertTrue(pairs, "Cine shares no view, so this asserts nothing")
        worst = min(min(A.dE(accents[a], accents[b])) for _, a, b in pairs)
        self.assertGreaterEqual(worst, 14.4, f"worst Cine pair is {worst:.1f} dE00")

    def test_a_region_named_like_a_city_stays_its_own_view(self):
        """Cities and regions are keyed apart. Under one dict keyed on the bare name, a
        region called "Tampere" would fold its pairs into the Tampere city view and the
        report would list a chain from Kangasala as though it sat in Tampere's own row."""
        regions = [{"name": "Tampere", "cities": ["Tampere", "Kangasala"]}]
        with mock.patch.object(A, "cities_by_provider",
                               return_value={"a": {"Tampere"}, "b": {"Tampere"}}), \
                mock.patch.object(A, "cities_declared_by_adapters",
                                  return_value={"c": {"Kangasala"}}), \
                mock.patch.object(A.registry, "REGIONS", regions):
            pairs = A.view_pairs()
            flat = A.shared_view_pairs()
        self.assertEqual(flat, [(label, a, b) for _, label, a, b in pairs],
                         "the report's view drops only the kind")
        city = [(a, b) for kind, label, a, b in pairs if kind == "city"]
        region = [(a, b) for kind, label, a, b in pairs if kind == "region"]
        self.assertEqual(city, [("a", "b")])
        self.assertEqual(region, [("a", "b"), ("a", "c"), ("b", "c")])
        self.assertEqual({label for _, label, _, _ in pairs}, {"Tampere"},
                         "both views keep the readable name")

    def test_a_candidate_in_a_town_with_no_cinema_and_no_region_is_unconstrained(self):
        pairs = A.shared_view_pairs(extra=("candidate", ["Nowheresville"]))
        self.assertEqual([p for p in pairs if "candidate" in (p[1], p[2])], [])


class SearchRankingTest(unittest.TestCase):
    """`--search` proposes replacement accents. It ranked them on the deuteranope figure
    alone, which promotes a colour whose normal-vision separation is the binding one.

    Everything here recomputes the three minima from the returned hex with A.dE, the
    public pair function, rather than reading the tuple the implementation built.
    """

    STEP = 8

    @classmethod
    def setUpClass(cls):
        cls.accents = {p["id"]: p["accent"] for p in A.registry.PROVIDERS}
        cls.best, cls.rivals = A.search("cine", cls.accents, step=cls.STEP, top=12)
        cls.grid = [f"#{r:02X}{g:02X}{b:02X}"
                    for r in range(0, 256, cls.STEP)
                    for g in range(0, 256, cls.STEP)
                    for b in range(0, 256, cls.STEP)]

    def minima(self, hexcolour):
        """-> (overall, normal, deutan), recomputed from scratch against the rivals."""
        triples = [A.dE(hexcolour, self.accents[r]) for r in self.rivals]
        normal = min(t[0] for t in triples)
        deutan = min(min(t[1], t[2]) for t in triples)
        return min(normal, deutan), normal, deutan

    def in_band(self, hexcolour):
        return A.L_MIN <= A.labs_for(hexcolour)[0][0] <= A.L_MAX

    def test_the_ranking_is_non_increasing_in_the_three_model_minimum(self):
        self.assertTrue(self.best, "search returned nothing to rank")
        got = [self.minima(h)[0] for *_, h in self.best]
        self.assertEqual(got, sorted(got, reverse=True),
                         "candidates are not ordered by their weakest model")

    def test_the_top_candidate_is_the_best_in_the_band_on_that_minimum(self):
        """Ranked on the wrong figure the leader is some other colour entirely, so this
        is the assertion that fails first if the ordering key changes back."""
        best_possible = max(self.minima(h)[0] for h in self.grid if self.in_band(h))
        self.assertAlmostEqual(self.minima(self.best[0][-1])[0], best_possible, places=6)

    def test_a_deutan_stronger_candidate_does_not_lead_when_normal_vision_binds(self):
        """The defect, stated as a colour: better under both deuteranope models than the
        leader, worse once normal vision is counted. Ranking on deutan alone puts one of
        these first."""
        lead_overall, _, lead_deutan = self.minima(self.best[0][-1])
        trap = [h for h in self.grid if self.in_band(h)
                and self.minima(h)[2] > lead_deutan
                and self.minima(h)[0] < lead_overall]
        self.assertTrue(trap, "no such colour on this grid, so the test proves nothing")
        returned = [h for *_, h in self.best]
        for h in trap:
            with self.subTest(colour=h):
                self.assertNotEqual(h, returned[0])
                self.assertNotIn(h, returned[:3])

    def test_the_reported_columns_carry_all_three_figures(self):
        """The summary line and the table print overall, normal and deutan, so a reader
        can see which model binds without rerunning anything."""
        for entry in self.best:
            self.assertEqual(len(entry), 4)
            overall, normal, deutan, h = entry
            want = self.minima(h)
            self.assertAlmostEqual(overall, want[0], places=6)
            self.assertAlmostEqual(normal, want[1], places=6)
            self.assertAlmostEqual(deutan, want[2], places=6)


class ReportRankingTest(unittest.TestCase):
    """The ordinary report and --all ranked and counted on the deuteranope minimum, so a
    pair whose normal-vision separation is the binding one sorted as though it were fine.

    Kino Engel and Cinema Sheryl are the real case since the Helsinki palette was solved
    for ten chains on 2026-09-21: 19.196 apart to a deuteranope, 16.598 to everyone else.
    Ranked on deutan it sorts behind Finnkino and Kinoset, whose own binding model is
    deutan at 16.616; ranked on the weakest model it leads them. The pair before this one
    was Bio Grani and Gilda, and Gilda's accent moved in that solve.
    """

    ACCENTS = {p["id"]: p["accent"] for p in A.registry.PROVIDERS}

    def report(self, argv=()):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            A.main(list(argv))
        return buf.getvalue()

    def test_the_two_pairs_measure_what_the_ranking_turns_on(self):
        engel_sheryl = A.dE(self.ACCENTS["engel"], self.ACCENTS["sheryl"])
        finnkino_kinoset = A.dE(self.ACCENTS["finnkino"], self.ACCENTS["kinoset"])
        self.assertAlmostEqual(min(engel_sheryl), 16.598, places=3)
        self.assertAlmostEqual(min(engel_sheryl[1:]), 19.196, places=3)
        self.assertEqual(min(engel_sheryl), engel_sheryl[0], "normal vision has to bind")
        self.assertAlmostEqual(min(finnkino_kinoset), 16.616, places=3)
        self.assertAlmostEqual(min(finnkino_kinoset[1:]), 16.616, places=3)
        self.assertLess(min(engel_sheryl), min(finnkino_kinoset))
        self.assertGreater(min(engel_sheryl[1:]), min(finnkino_kinoset[1:]),
                           "the deutan figure has to disagree, or nothing is proved")

    def test_the_report_ranks_the_normal_bound_pair_first(self):
        out = self.report()
        engel = out.index("Kino Engel     Cinema Sheryl")
        finnkino = out.index("Finnkino       Kinoset")
        self.assertLess(engel, finnkino,
                        "ranked on the deutan minimum, Kino Engel/Cinema Sheryl sorts below")

    def test_the_report_counts_every_pair_below_the_floor(self):
        rows = [A.separation(self.ACCENTS[a], self.ACCENTS[b])
                for _, a, b in A.shared_view_pairs()]
        # 139 until 2026-09-15: Julia 1&2 joined Hyvinkää and Keski-Uusimaa (+6) and
        # Kuvakukko joined Kuopio beside Finnkino (+1), then Kino Kilta joined Turku and
        # Turun seutu beside Finnkino (+2) while Kino Laika, alone in Karkkila and in no
        # region, added none. 148 until 2026-09-18, when Kino Myyri joined Vantaa and
        # Pääkaupunkiseutu (+15) and Ritz Vaasa joined Vaasa beside BioRex (+1). Tähti
        # Kino added none: Muhos holds no other chain and no region row holds Muhos.
        # Vihti joined Keski-Uusimaa the same day and put Vihdin Kino in that row (+6),
        # none of the six below the floor, the weakest being BioRex at 14.9.
        #
        # Twelve was the count of pairs below the floor and had to stay twelve. Kino Myyri
        # is the first accent to raise it, to fourteen: no colour in the L* band clears
        # 14.4 against all twelve chains of Pääkaupunkiseutu, its Kino Engel and BioRex
        # pairs sit at 10.1 and 10.8, and the registry entry and the IDEAS entry both
        # record why. The city floor is untouched, which is the invariant the test above
        # holds, and the regional minimum is still 4.5.
        #
        # 185 from 2026-09-19: Cinema Sheryl joined Espoo beside Finnkino and Kino Tapiola
        # and Pääkaupunkiseutu beside eleven more (+15). Four of the fifteen are below the
        # floor and all four are in that region -- Kino Myyri 8.2, Kino Engel 8.3, BioRex
        # 8.3, Bio Grand 9.0 -- for the reason Myyri's entry above already records: no
        # colour in the L* band clears 14.4 against that row. Its two Espoo pairs are 19.8
        # and 42.0, so the city floor is untouched, and the regional minimum is still the
        # 4.479 of Bio Grand against BioRex, which this accent does not lower.
        #
        # 186 from the same day: Elävienkuvien teatteri joined Forssa beside Bio-Kaari
        # (+1), 39.5 apart and well clear, and Haapamäen Elokuvat added none, Haapamäki
        # holding no other chain and no region row.
        # 232 from 2026-09-21: Kino Akustiikka and Kino-Huovi added none, each alone in
        # its town and in no region, and Kino K13 and Kino Helios joined Helsinki beside
        # eight and Pääkaupunkiseutu beside thirteen (+46). Two of the 46 are below the
        # floor and both are in that region, which is where the palette's slack runs out;
        # the city half of the rule holds without exception and the test below is what
        # keeps it that way. Adding those two is also what moved four existing accents:
        # with the eight Helsinki chains held, no colour in the L* band cleared 14.4
        # against them, and the joint solve of all ten did. The record is in IDEAS.md.
        # 237 from 2026-10-04: Kaarina, Lieto and Naantali joined Turun seutu (+5), all five
        # clear of the floor, the weakest Kino Kilta against Kinotour at 16.8.
        # 240 the same day: Oulun seutu put Tähti Kino beside Finnkino and Star (+3), the
        # weakest Finnkino against Tähti Kino at 18.4.
        self.assertEqual(len(rows), 240)
        self.assertEqual(sum(1 for r in rows if r < A.FLOOR), 20)
        self.assertIn(f"20 of 240 pairs are below {A.FLOOR}", self.report())

    def test_the_floor_is_the_fixed_policy_value(self):
        """14.4 is the threshold CLAUDE.md and the registry state, not a reading of the
        current set. Pinned as a literal so the count test above, which reuses A.FLOOR,
        cannot pass with a floor that quietly moved."""
        self.assertEqual(A.FLOOR, 14.4)

    def test_every_combined_city_pair_clears_the_floor(self):
        """The half of the policy that holds without exception. Region rows are measured
        on the same scale but twelve established pairs sit below, so this is asserted on
        the city views alone, against the literal rather than A.FLOOR."""
        city = [(label, a, b) for kind, label, a, b in A.view_pairs() if kind == "city"]
        self.assertGreaterEqual(len(city), 10, "too few city pairs to mean anything")
        for label, a, b in city:
            with self.subTest(city=label, pair=(a, b)):
                self.assertGreaterEqual(min(A.dE(self.ACCENTS[a], self.ACCENTS[b])), 14.4)

    def test_helsinki_is_the_densest_city_and_still_clears_the_floor(self):
        """The city that forced the joint solve of 2026-09-21.

        Ten chains, 45 pairs, and the rule holds without an exception being written for
        it. Held with the eight accents it had, the best colour in the L* 38-60 band
        reached 12.12 against them and a ninth chain was impossible; moving four of the
        eight -- BioRex, Kino Engel, Gilda and Korjaamo Kino -- lifted the whole city to
        14.409. The figure is pinned because it is thin: the next Helsinki cinema has to
        be solved the same way and cannot be waved through.
        """
        by_city = collections.Counter(
            label for kind, label, _, _ in A.view_pairs() if kind == "city")
        self.assertEqual(by_city.most_common(1)[0], ("Helsinki", 45))
        pairs = [min(A.dE(self.ACCENTS[a], self.ACCENTS[b]))
                 for kind, label, a, b in A.view_pairs()
                 if kind == "city" and label == "Helsinki"]
        self.assertEqual(len(pairs), 45)
        self.assertAlmostEqual(min(pairs), 14.409, places=3)
        self.assertGreaterEqual(min(pairs), 14.4)

    def test_two_accents_that_look_alike_never_share_a_view(self):
        """What makes a dense palette safe: it reuses colour only where nobody sees both.

        Fifty pairs in this registry sit under 4 dE00, which is indistinguishable -- Kino
        Aurora and Kinokulma are 0.16 apart, Kino K13 and Lieksan Kino 0.63. None of them
        appears in one city or one region, so no reader is ever asked to tell them apart.
        This is the guard on the reuse the floor leaves room for; without it a later
        provider could put two of them in one town and nothing would say so.
        """
        shared = {frozenset((a, b)) for _, a, b in A.shared_view_pairs()}
        ids = sorted(self.ACCENTS)
        close = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]
                 if A.separation(self.ACCENTS[a], self.ACCENTS[b]) < 4.0]
        self.assertGreater(len(close), 20, "the premise went away; re-read the palette")
        for a, b in close:
            with self.subTest(pair=(a, b)):
                self.assertNotIn(frozenset((a, b)), shared)

    def test_the_worst_pair_summary_uses_the_same_score(self):
        worst = min(A.separation(self.ACCENTS[a], self.ACCENTS[b])
                    for _, a, b in A.shared_view_pairs())
        self.assertAlmostEqual(worst, 6.348, places=3)
        self.assertIn(f"worst shared-view pair: {worst:.1f} dE00 across the three models",
                      self.report())

    def test_all_ranks_and_summarises_on_the_same_score(self):
        ids = sorted(self.ACCENTS)
        worst = min(A.separation(self.ACCENTS[ids[i]], self.ACCENTS[ids[j]])
                    for i in range(len(ids)) for j in range(i + 1, len(ids)))
        self.assertIn(f"global minimum over all pairs: {worst:.1f} dE00 "
                      f"(minimum across the three models)", self.report(["--all"]))

    @staticmethod
    def scores(out):
        """-> the weakest-model figure of every printed pair, in printed order."""
        got = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                n, v, m = (float(parts[i]) for i in range(3))
            except ValueError:
                continue
            got.append(min(n, v, m))
        return got

    def test_all_lists_pairs_in_order_of_their_weakest_model(self):
        """Parsed back out of the printed columns, so this checks what a reader sees
        rather than the key the sort was handed."""
        got = self.scores(self.report(["--all"]))
        self.assertGreater(len(got), 100)
        for i in range(1, len(got)):
            self.assertGreaterEqual(got[i], got[i - 1] - 0.05,
                                    f"row {i} is out of order: {got[i - 1]} then {got[i]}")

    def test_the_report_lists_pairs_in_order_of_their_weakest_model(self):
        got = self.scores(self.report())
        self.assertGreater(len(got), 100)
        for i in range(1, len(got)):
            self.assertGreaterEqual(got[i], got[i - 1] - 0.05,
                                    f"row {i} is out of order: {got[i - 1]} then {got[i]}")

    def test_search_and_the_reports_cannot_diverge(self):
        """One scorer. `separation` is what the reports order on, and `worst_labs` builds
        a candidate's overall figure out of the same call, so a change to one moves both.
        """
        for _, a, b in A.shared_view_pairs():
            with self.subTest(pair=(a, b)):
                self.assertEqual(A.separation(self.ACCENTS[a], self.ACCENTS[b]),
                                 min(A.dE(self.ACCENTS[a], self.ACCENTS[b])))
        rivals = ["biorex", "kinoakseli", "kinojuha"]
        fixed = [A.labs_for(self.ACCENTS[r]) for r in rivals]
        overall, _, _ = A.worst_labs(A.labs_for("#BA7E8A"), fixed)
        self.assertEqual(overall, min(A.separation("#BA7E8A", self.ACCENTS[r])
                                      for r in rivals))


if __name__ == "__main__":
    unittest.main()
