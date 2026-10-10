"""A screening note is not a synopsis (2026-09-03).

`films-extra.json` holds one Finnish synopsis per normalised title, filled by the first
provider to publish one. Gilda's senior-screening entries open with the cinema's own
paragraph (a price and a coffee offer) before the distributor's blurb, so it landed in the
shared slot and Cinema Niagara showed Gilda's price. Two rules: at the adapter, a paragraph
that quotes a price or names the cinema is dropped whole; at the merge, text quoting a
price never enters the shared slot and is counted in the log. The slot stays empty for
TMDB. Provider modules are imported inside the tests because they bind
`common.EmptyProgramme` at import time and test_common_fetch reloads `common`.
"""
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

import _ctx


PROMO = ("<p>Gildan seniorikinon&auml;yt&ouml;kset joka kuun ensimm&auml;isen&auml; tiistaina. "
         "Elokuvaliput seniorikinon n&auml;yt&ouml;ksiin saat hintaan 9&euro;/kpl. "
         "Lipun hintaan sisältyy leffakahvit!</p>")
BLURB1 = "<p>Derya on Ankaran suurimman teatterin t&auml;hti.&nbsp;</p>"
BLURB2 = "<p>KELTAISET KIRJEET on kuvaus el&auml;m&auml;st&auml; autorit&auml;&auml;risen yhteiskunnan puristuksissa.</p>"
# The two unpriced notes found in shared slots on 2026-10-04, as published.
SAVON_NOTE = ("Ensi-iltapaikkakunnat: Joensuu, Savonlinna, Iisalmi, Varkaus ja Kitee || "
              "Ennakkoesitykset Hopeatähdessä 7.10. ||")
SAVON_SYN = ("Kerro kaikille on voimaelokuva Amanda Aaltosesta, joka kieltäytyy alistumasta "
             "hänelle varattuun köyhän naisen kohtaloon.")
NIAGARA_NOTE = ("Niagarassa tekijävierailunäytös tiistaina 4.8. klo 18.30. Vieraana ohjaaja "
                "Jarmo Lampela sekä näyttelijä Juha Kukkonen!")


class DropNotesHtmlTest(unittest.TestCase):

    def test_the_price_paragraph_goes_and_the_blurb_stays_in_order(self):
        import synmerge
        out = synmerge.drop_notes_html(PROMO + " " + BLURB1 + " " + BLURB2, names=("Gilda",))
        self.assertEqual(out, "Derya on Ankaran suurimman teatterin tähti. "
                              "KELTAISET KIRJEET on kuvaus elämästä autoritäärisen yhteiskunnan puristuksissa.")

    def test_a_paragraph_naming_the_cinema_goes_without_a_price(self):
        import synmerge
        desc = "<p>Koe eepos 70mm-filmilt&auml;. Vain Gildan Bio Rex Lasipalatsissa.</p><p>Nolanin eepos.</p>"
        self.assertEqual(synmerge.drop_notes_html(desc, names=("Gilda",)), "Nolanin eepos.")
        # The stem is a word prefix, so "Gildan" matches "Gilda" and "gildattu" would not
        # match a name that is not a prefix of it.
        self.assertEqual(synmerge.drop_notes_html("<p>Elokuva on gildattu.</p>", names=("Gilda",)), "")
        self.assertEqual(synmerge.drop_notes_html("<p>Elokuva on kullattu.</p>", names=("Gilda",)),
                         "Elokuva on kullattu.")

    def test_text_without_paragraphs_is_one_paragraph(self):
        import synmerge
        self.assertEqual(synmerge.drop_notes_html("Pelkk&auml;&nbsp;teksti.", names=("Gilda",)), "Pelkkä teksti.")
        self.assertEqual(synmerge.drop_notes_html("Liput 8€ ovelta.", names=()), "")
        self.assertEqual(synmerge.drop_notes_html("", names=("Gilda",)), "")

    def test_is_note_reads_a_price_in_either_order_and_nothing_else(self):
        import synmerge
        for s in ("Liput 8€ ovelta", "hintaan 9 €/kpl", "vain 12 euroa", "€ 10 ovelta", "5 EUR"):
            self.assertTrue(synmerge.is_note(s), s)
        for s in ("Vuonna 1930 Ankarassa", "72 tuntia ennen h-hetkeä", "Ainoa näytös, klubialennus.", ""):
            self.assertFalse(synmerge.is_note(s), s)

    def test_is_note_reads_savon_kinots_separator_and_a_filmmaker_visit(self):
        """Both reached the shared slot unpriced: Savon Kinot's note on Kerro kaikille and
        Ortotopologia, Cinema Niagara's on Don Quijote Barcelonassa (read 2026-10-04)."""
        import synmerge
        for s in (SAVON_NOTE, "Joensuu 30.9. + 3.10. ||", NIAGARA_NOTE,
                  'Vierailunäytöksissä on oranssi "Tekijävierailu"-merkki.'):
            self.assertTrue(synmerge.is_note(s), s)
        for s in (SAVON_SYN, "KINOLINNA | SALI 1", "Tekijät kertovat elokuvasta."):
            self.assertFalse(synmerge.is_note(s), s)


class IirisAdmissionLinesTest(unittest.TestCase):
    """Kino Iiris's Polish film weekend, read 2026-10-04: three note lines above Junat's
    and Hyvä talo's synopses, each its own paragraph on the eTiketti page."""

    LINES = ("VAPAA P\u00c4\u00c4SY!", "N\u00e4yt\u00f6kseen ei voi varata lippuja etuk\u00e4teen.",
             "Vain englanninkieliset tekstitykset.")

    def test_each_line_is_a_note(self):
        import synmerge
        for s in self.LINES:
            self.assertTrue(synmerge.is_note(s), s)

    def test_the_words_inside_a_synopsis_are_not(self):
        import synmerge
        for s in ("Puolalaisen nykyelokuvan k\u00e4rkitekij\u00e4n uusi elokuva on raju kuvaus "
                  "parisuhdev\u00e4kivallasta.",
                  "Vapaa p\u00e4\u00e4sy taivaaseen on vain unelma.",
                  "Elokuvassa on vain englanninkieliset tekstitykset ja paljon musiikkia."):
            self.assertFalse(synmerge.is_note(s), s)

    def test_the_etiketti_page_keeps_the_synopsis_alone(self):
        import etiketti
        desc = ("VAPAA P\u00c4\u00c4SY!<br />\nN\u00e4yt\u00f6kseen ei voi varata lippuja etuk\u00e4teen."
                "<br />\nVain englanninkieliset tekstitykset.<br />\n<br />\n")
        site = next(x for x in etiketti.SITES if x["provider"] == "kinoiiris")
        for body, want in (("&quot;Junat&quot; alkaa Franz Kafkan lainauksella.",
                            '"Junat" alkaa Franz Kafkan lainauksella.'),
                           ("Raju kuvaus.<br />\n<br />\nGo\u015bka tutustuu Grzesiekiin.",
                            "Raju kuvaus. Go\u015bka tutustuu Grzesiekiin.")):
            page = ('<main><h1>JUNAT</h1><div class="description-container"><span>'
                    + desc + body + "</span></div></main>")
            self.assertEqual(etiketti.parse_movie(page, site, "/elokuvat/1/x")[1]["syn"], want)


class NoteSentenceTest(unittest.TestCase):
    """Screening-note sentences inside an otherwise good synopsis, as they stood in shared
    slots on 2026-10-04. Each goes whole; a similar sentence about the film stays."""

    NOTES = (
        "N\u00e4yt\u00f6kseen on vapaa p\u00e4\u00e4sy.",                                    # Järven ääni
        "Elokuvaan on vapaa p\u00e4\u00e4sy.",                                               # Anttilanmäen kyläjuhla
        "N\u00e4yt\u00f6kseen on vapaa p\u00e4\u00e4sy ja mukaan mahtuu 250 ensimm\u00e4ist\u00e4 "
        "paikalle saapunutta.",                                                    # Käpy selän alla
        "VAPAA P\u00c4\u00c4SY!",                                                           # Lahden videokuvaajat
        "Huom! N\u00e4yt\u00f6kseen ei voi varata lippuja etuk\u00e4teen.",                     # Järven ääni
        "N\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n yhteisty\u00f6ss\u00e4 Lahti-Seura ry:n ja "
        "elokuvateatteri Kino Iiriksen kanssa.",                                   # Järven ääni
        "N\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n KE 7.10. klo 19:00.",                     # El espíritu
        "N\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n TO 15.10. KLO 17:00.",                    # Filminor
        "Suomi-Espanja Seura ja Espanjan suurl\u00e4hetyst\u00f6 j\u00e4rjest\u00e4v\u00e4t "
        "ilmaisn\u00e4yt\u00f6ksen Orionissa.",                                       # El espíritu
        "Vanhusten viikon maksuton n\u00e4yt\u00f6s.",                                       # Joutsan Kino
        "Pia L\u00e5ngbackan puheenvuoroa voi tulla kuuntelemaan ilman p\u00e4\u00e4sylippua.",  # Casper
        "Pian puheenvuoro on osa Meedioelokuvap\u00e4iv\u00e4\u00e4 ja sit\u00e4 voi tulla "
        "kuuntelemaan ilmaiseksi.",                                                # Pia Långbacka
        "Elokuvat n\u00e4ytet\u00e4\u00e4n elokuvateatteri Starissa, ja ne ovat osallistujille "
        "maksuttomia.",                                                            # Star
        "Katsojilla on mahdollisuus tukea tallennusty\u00f6t\u00e4 vapaaehtoisella "
        "kannatusmaksulla.",                                                       # Anttilanmäen
        "Admission to the screening is free, no advance reservation is required.",  # El espíritu
        "Admission to Piia L\u00e5ngbacka\u2019s talk is free.",                           # Casper
        "The screening will take place on Wednesday, October 7 at 19:00.",         # El espíritu
        "The screening will be held on Thursday, 22 October at 17:15.",            # Ghost in the Machine
        "Sociedad Finlandia Espa\u00f1a and the Embassy of Spain are organizing a free "
        "screening at Orion.",                                                     # El espíritu
    )
    KEPT = (
        "Elokuva on toteutettu yhteisty\u00f6ss\u00e4 Vesij\u00e4rvis\u00e4\u00e4ti\u00f6n kanssa.",   # Järven ääni
        "Vapaa p\u00e4\u00e4sy taivaaseen on vain unelma.",
        "Puistoon on vapaa p\u00e4\u00e4sy kaikille kyl\u00e4l\u00e4isille.",
        "N\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n vankilan pihalla, ja vartijat katsovat sivusta.",
        "Kosiomatkalla M\u00e4nttari saa ikaan kuin ilmaisen tilaisuuden hahmotella naiskuvaa.",
        "Maksuton koulutus muutti h\u00e4nen el\u00e4m\u00e4ns\u00e4.",
        "Kuka tahansa voi tulla kuuntelemaan h\u00e4nen tarinaansa.",
        "Palvelut ovat kaikille maksuttomia.",
        "Yhdistyksen kannatusj\u00e4senet kokoontuvat torstaisin.",
        "Admission to the academy is free for gifted children.",
        "The screening of his first film took place in Cannes.",
        "The screening will be held in secret, the colonel decides.",
        "Elokuva on tekstitetty englanniksi.",
    )

    def test_each_note_sentence_goes(self):
        import synmerge
        lead, tail = "Elokuva kertoo j\u00e4rvest\u00e4.", "Lopussa j\u00e4rvi toipuu."
        for note in self.NOTES:
            with self.subTest(note=note[:40]):
                self.assertEqual(synmerge.drop_note_sentences(f"{lead} {note} {tail}"),
                                 (f"{lead} {tail}", 1))

    def test_a_note_run_on_after_an_attribution_still_goes(self):
        """Metsäsota ja rauha's Finnish text, read 2026-10-05: the note follows the quote's
        attribution with no stop between them."""
        import synmerge
        quote = ("\u201dJos kaikki hakkuut lopetettaisiin, saisivat linnut pesi\u00e4 rauhassa.\u201d "
                 "\u2013 Erkki L\u00e4hde 2026")
        note = ("N\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n ke 30.9. klo 17:15 Suomen Luonnon ja "
                "Orionin yhteisell\u00e4 Luontoelokuvaklubilla.")
        guests = "N\u00e4yt\u00f6ksess\u00e4 ovat vieraina elokuvan ohjaaja Jari Kokko."
        self.assertEqual(synmerge.drop_note_sentences(f"{quote} {note} {guests}"),
                         (f"{quote} {guests}", 1))
        plot = ("Kirjeess\u00e4 kerrotaan, ett\u00e4 n\u00e4yt\u00f6s j\u00e4rjestet\u00e4\u00e4n ke 30.9. "
                "kyl\u00e4n talolla.")
        self.assertEqual(synmerge.drop_note_sentences(plot), (plot, 0))

    def test_a_similar_sentence_about_the_film_stays(self):
        import synmerge
        for kept in self.KEPT:
            with self.subTest(kept=kept[:40]):
                text = f"Elokuva kertoo j\u00e4rvest\u00e4. {kept} Lopussa j\u00e4rvi toipuu."
                self.assertEqual(synmerge.drop_note_sentences(text), (text, 0))

    def test_the_merge_keeps_the_film_and_leaves_the_note_out(self):
        """Järven ääni as Kino Iiris published it, through the merge every provider uses."""
        import synmerge
        text = ("Huom! N\u00e4yt\u00f6kseen ei voi varata lippuja etuk\u00e4teen. J\u00e4rven \u00e4\u00e4ni "
                "kertoo Vesij\u00e4rvest\u00e4. N\u00e4yt\u00f6kseen on vapaa p\u00e4\u00e4sy.")
        synmerge.reset()
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            buf = io.StringIO()
            with redirect_stdout(buf):
                synmerge.merge(out, {"v": [{"title": "J\u00e4rven \u00e4\u00e4ni", "_syn": text},
                                           {"title": "Toinen", "_syn": "Vapaa p\u00e4\u00e4sy!"}]},
                               "t")
            films = json.loads((out / "films-extra.json").read_text())["films"]
        self.assertEqual(films["j\u00e4rven \u00e4\u00e4ni"]["s"]["fi"],
                         "J\u00e4rven \u00e4\u00e4ni kertoo Vesij\u00e4rvest\u00e4.")
        self.assertNotIn("toinen", films)
        self.assertIn("screening-note sentences left out of synopses: 3", buf.getvalue())


class MergeRefusesNotesTest(unittest.TestCase):

    def run_merge(self, shows):
        import synmerge
        synmerge.reset()
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            buf = io.StringIO()
            with redirect_stdout(buf):
                synmerge.merge(out, {"v1": shows}, "test")
            doc = json.loads((out / "films-extra.json").read_text())
        return doc["films"], buf.getvalue()

    def test_a_priced_text_never_enters_the_shared_slot(self):
        films, log = self.run_merge([
            {"title": "Nouvelle Vague", "_syn": "Juhlanäytös! Liput 8€ maksetaan ovella."},
            {"title": "Autofiktio", "_syn": "Almodóvarin melodraama."},
        ])
        self.assertNotIn("nouvelle vague", films)
        self.assertEqual(films["autofiktio"]["s"]["fi"], "Almodóvarin melodraama.")
        self.assertIn("[test] synopses merged: 1", log)
        self.assertIn("[test] synopses skipped as screening notes: 1", log)

    def test_an_unpriced_note_never_enters_the_shared_slot_either(self):
        films, log = self.run_merge([
            {"title": "Kerro kaikille", "_syn": SAVON_NOTE + " " + SAVON_SYN},
            {"title": "Don Quijote Barcelonassa",
             "_syn": NIAGARA_NOTE + " Don Quijote Barcelonassa on lämmin fiktiodraama."},
            {"title": "Autofiktio", "_syn": "Almodóvarin melodraama."},
        ])
        self.assertEqual(sorted(films), ["autofiktio"])
        self.assertIn("[test] synopses skipped as screening notes: 2", log)

    def test_a_text_that_is_only_the_title_is_no_synopsis(self):
        """Niagara's page gives "Romanovin kivet" where its description goes (2026-09-27)."""
        films, _ = self.run_merge([
            {"title": "Romanovin kivet", "_syn": "Romanovin kivet"},
            {"title": "Romeo + Juliet", "_syn": "Romeo & Juliet"},
            {"title": "Autofiktio", "_syn": "Autofiktio on Almodóvarin melodraama."}])
        self.assertEqual(sorted(films), ["autofiktio"])

    def test_the_skipped_line_is_silent_when_nothing_was_skipped(self):
        _, log = self.run_merge([{"title": "Autofiktio", "_syn": "Almodóvarin melodraama."}])
        self.assertIn("synopses merged: 1", log)
        self.assertNotIn("skipped", log)


class GildaParseTest(unittest.TestCase):
    # Gilda's synopsis is placed by `common.syn_language` since 2026-09-24, and the two
    # blurbs above are too short to place, so both films carry one Finnish paragraph more.
    TAIL_TEXT = "Kun hän ja mies menettävät työnsä, heidän on muutettava Istanbuliin."
    TAIL = f"<p>{TAIL_TEXT}</p>"

    def test_parse_drops_gildas_own_paragraph_from_the_synopsis(self):
        import gilda
        site = {"provider": "gilda", "base": "https://www.gilda.fi", "listing": "/",
                "venues": [{"id": "gd-gilda", "name": "Gilda Kamppi", "short": "Gilda", "screens": [1]}]}
        show = {"movie_name": "Keltaiset Kirjeet", "cinema_screen_id": 1, "show_is_visible": 1,
                "show_time": "2026-09-05T18:00:00+03:00", "running_time": 120,
                "screen_name": "Gilda 3", "rating_name": "12"}
        payload = {"fi": {"data": [
            {"movie_id": 1574, "movie_name": "Seniorikino: Keltaiset kirjeet",
             "description": PROMO + BLURB1 + BLURB2 + self.TAIL, "show_times": [show]},
            {"movie_id": 1575, "movie_name": "Toinen", "description": BLURB1 + self.TAIL, "show_times": [dict(show, movie_name="Toinen")]},
        ]}}
        per_venue = gilda.parse(payload, site)
        rows = per_venue.get("gd-gilda") or []
        self.assertEqual(len(rows), 2, per_venue)
        by_title = {r["title"]: r for r in rows}
        self.assertEqual(by_title["Keltaiset Kirjeet"]["_syn"],
                         {"fi": "Derya on Ankaran suurimman teatterin tähti. "
                          "KELTAISET KIRJEET on kuvaus elämästä autoritäärisen yhteiskunnan puristuksissa. "
                          + self.TAIL_TEXT})
        self.assertEqual(by_title["Toinen"]["_syn"],
                         {"fi": "Derya on Ankaran suurimman teatterin tähti. " + self.TAIL_TEXT})
        for r in rows:
            self.assertNotIn("€", r["_syn"]["fi"]); self.assertNotIn("Gilda", r["_syn"]["fi"])


if __name__ == "__main__":
    unittest.main()
