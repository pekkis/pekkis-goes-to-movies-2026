"""Adapters whose synopses are not all Finnish declare the language of each one.

A bare `_syn` string is filed as Finnish in films-extra.json, in a slot keyed by normalised
title that every chain showing the film reads. Read 2026-09-24: Kino Engel's
`BARNSÖNDAGAR` film pages carry a Swedish synopsis beside Finnish ones for everything
else, and the page declares neither (`<html lang="en-US">` on both kinds). Gilda's booking
feed carries English `description`s for 6 of 36 films and no language field, and Savon
Kinot's film pages carry English for one of 24. So each text is placed by
`common.syn_language`, and one it cannot place is withheld. eTiketti does so for all 20
sites since 2026-09-28, splitting a description whose paragraphs place in two languages:
Niagara prints Finnish, `***`, then Swedish, and read whole it was outvoted into Swedish.
"""
import io
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import engel
import etiketti
import gilda
from test_etiketti_templates import HIDDEN, Stubbed, listing

SV = ("Efter en lång vinter tar familjen sig till skärgården, och där väntar ett äventyr "
      "som ingen av dem har räknat med.")
FI = ("Kun perhe lähtee saaristoon pitkän talven jälkeen, siellä odottaa seikkailu, jota "
      "kukaan ei osannut odottaa, ja kaikki muuttuu.")
EN = ("After a long winter the family travels to the islands, and there an adventure "
      "waits that none of them expected.")
# Long enough for Engel's 40-character floor, and no function word of any of the three.
UNPLACED = "Seikkailu saaristossa: perhe, talvi, meri, lokit, majakka ja myrsky."


def engel_page(text):
    return (f'<div class="cmd-desription"><h5>KOMEDIA,SEIKKAILU</h5>\n<p>{text}</p>\n'
            f"</div>")


class EngelTest(unittest.TestCase):
    def test_a_swedish_synopsis_is_filed_as_swedish(self):
        self.assertEqual(engel.details(engel_page(SV))["_syn"], {"sv": SV})

    def test_a_finnish_synopsis_is_filed_as_finnish(self):
        self.assertEqual(engel.details(engel_page(FI))["_syn"], {"fi": FI})

    def test_an_english_synopsis_is_filed_as_english(self):
        self.assertEqual(engel.details(engel_page(EN))["_syn"], {"en": EN})

    def test_a_synopsis_no_language_settles_is_withheld(self):
        d = engel.details(engel_page(UNPLACED))
        self.assertNotIn("_syn", d)
        self.assertEqual(d["genres"], "Komedia, Seikkailu", "the rest of the page stands")


def gilda_rows(*descriptions):
    films = []
    for n, desc in enumerate(descriptions):
        title = f"Elokuva {n}"
        films.append({"movie_id": n + 1, "movie_name": title, "description": desc,
                      "show_times": [{"movie_name": title, "cinema_screen_id": 66,
                                      "show_time": f"2026-09-26T1{n}:00:00Z",
                                      "screen_name": "Gilda 1", "rating_name": "12"}]})
    with redirect_stdout(io.StringIO()):
        per_venue = gilda.parse({"fi": {"data": films}}, gilda.SITES[0], {})
    return {r["title"]: r for rows in per_venue.values() for r in rows}


class GildaTest(unittest.TestCase):
    def test_each_description_is_filed_in_its_own_language(self):
        rows = gilda_rows(f"<p>{EN}</p>", f"<p>{FI}</p>", f"<p>{SV}</p>")
        self.assertEqual(rows["Elokuva 0"]["_syn"], {"en": EN})
        self.assertEqual(rows["Elokuva 1"]["_syn"], {"fi": FI})
        self.assertEqual(rows["Elokuva 2"]["_syn"], {"sv": SV})

    def test_a_description_no_language_settles_is_withheld(self):
        # "Not Supplied" is the feed's own placeholder, read 2026-09-24.
        rows = gilda_rows("<p>Not Supplied</p>", f"<p>{UNPLACED}</p>", f"<p>{FI}</p>")
        self.assertNotIn("_syn", rows["Elokuva 0"])
        self.assertNotIn("_syn", rows["Elokuva 1"])
        self.assertEqual(rows["Elokuva 2"]["_syn"], {"fi": FI}, "the next film is unaffected")


# Cinema Niagara's The Love That Remains, read 2026-09-28: a headline, the Finnish text,
# its source, `***`, then the same in Swedish. Its films-extra entry was split by hand
# on 2026-09-24 into exactly these three paragraphs.
NIAGARA_FI = ("The Love That Remains on herkkävireinen kuvaus vuoden pituisesta "
              "ajanjaksosta perheessä, jossa vanhemmat yrittävät selviytyä "
              "erostaan. The Love That Remains kuvaa vastikään eronneiden Annan "
              "ja Magnúsin elämää vuoden ajan parin yrittäessä selviytyä työstä, "
              "seksistä ja monimutkaisista perhesuhteista, joihin kuuluvat "
              "teini-ikäinen tytär ja kaksospojat. Perhe-elämää kuvaavat "
              "kohtaukset vetävät puoleensa vanhoja totuuksia ja tunnesiteitä, "
              "jotka ovat muuttuneet mutta eivät täysin hävinneet.")
NIAGARA_SV = ("Det vardagliga ställs mot det fantastiska i en film fylld av "
              "värme, humor och en rejäl dos berättarglädje.")
NIAGARA_SV2 = ("The Love That Remains fångar ömsint ett år i en familjs liv. Ett "
               "år där föräldrarna försöker navigera genom sin separation "
               "långsamt, men oundvikligen glider de isär. Med en blandning av "
               "lekfullhet och djup porträtterar filmen det bitterljuva i en "
               "kärlek som har bleknat, men där minnena fortfarande binder samman "
               "– allt mot en fond av årstidernas tysta förändring. Filmskaparen "
               "Hlynur Pálmason (Godland) för in både oväntad humor och "
               "känslomässig tyngd i denna visuellt slående, intima och samtidigt "
               "imponerande vidsträckta skildring av ett äktenskap i upplösning – "
               "mot en storslagen fond av årstidernas skiftningar.")
NIAGARA = ("POHJOISMAISEN NEUVOSTON ELOKUVAPALKINTOEHDOKAS 2026!<br />\r\n <br />\r\n"
           f"{NIAGARA_FI} <br />\r\n<br />\r\n Lähde: Norden.org<br />\r\n<br />\r\n"
           "***<br />\r\n<br />\r\nNORDISKA RÅDETS FILMPRISKANDIDAT 2026!<br />\r\n <br />\r\n"
           f"{NIAGARA_SV}<br />\r\n<br />\r\n{NIAGARA_SV2}<br />\r\n<br />\r\nKälla: TriArt")


class EtikettiTest(Stubbed):
    def site(self, provider):
        return next(s for s in etiketti.SITES if s["provider"] == provider)

    def placed(self, description):
        page = (f'<main><h1>Elokuva</h1><div class="description-container"><span>{description}'
                "</span></div></main>")
        _, meta = etiketti.parse_movie(page, self.site("niagara"), "/elokuvat/1/elokuva")
        return etiketti.syn_value(meta["syn"], meta["paras"])

    def test_each_synopsis_is_placed(self):
        self.assertEqual(self.placed(EN), {"en": EN})
        self.assertEqual(self.placed(FI), {"fi": FI})
        self.assertEqual(self.placed(SV), {"sv": SV})

    def test_finnish_then_swedish_is_split_by_paragraph(self):
        self.assertEqual(self.placed(NIAGARA),
                         {"fi": NIAGARA_FI, "sv": f"{NIAGARA_SV} {NIAGARA_SV2}"})

    def test_one_line_break_is_a_paragraph_break(self):
        self.assertEqual(self.placed(f"{FI}<br />{SV}"), {"fi": FI, "sv": SV})

    def test_a_text_in_one_language_is_kept_whole(self):
        # Niagara's Autofiktio: the release line places nowhere and stays with the blurb.
        text = ("Espanjalaisen ohjaajalegendan Pedro Almodóvarin melodraama kertoo "
                "luomiskriisissä kamppailevasta elokuvantekijästä, joka ammentaa läheistensä "
                "tragedioista materiaalia teokseensa.")
        self.assertEqual(self.placed(f"{text} <br />\r\nElokuvateattereissa 28.8."),
                         {"fi": f"{text} Elokuvateattereissa 28.8."})

    def test_only_the_age_statement_comes_off_the_opening(self):
        """Kotka's boilerplate, read 2026-10-04, goes; a synopsis that itself opens
        "Elokuva on" keeps its first two sentences."""
        k16 = ("Elokuva on K16. Ikärajoista voi joustaa kolme vuotta silloin, kun lapsi on "
               "täysi-ikäisen huoltajan seurassa.<br />\n<br />\n")
        self.assertEqual(self.placed(k16 + FI), {"fi": FI})
        own = ("Elokuva on saanut innoituksensa 30 vuotta Oulun yliopistossa vaikuttaneen "
               "Aapo Heikkilän värikkäästä elämästä. Opiskelijat alkoivat seurata hänen "
               "luentojaan ja kutsuivat häntä dosentiksi.")
        self.assertEqual(self.placed(own), {"fi": own})

    def test_a_screening_note_paragraph_goes_and_the_synopsis_stays(self):
        """Savon Kinot's notes on Kerro kaikille and Linkin Park, and Niagara's on Don
        Quijote Barcelonassa, as they reached the shared slot (read 2026-10-04)."""
        br = "<br />\n<br />\n"
        savon = ("Ensi-iltapaikkakunnat: Joensuu, Savonlinna, Iisalmi, Varkaus ja Kitee || "
                 "Ennakkoesitykset Hopeatähdessä 7.10. ||")
        niagara = ("Niagarassa tekijävierailunäytös tiistaina 4.8. klo 18.30. Vieraana ohjaaja "
                   "Jarmo Lampela sekä näyttelijä Juha Kukkonen!")
        self.assertEqual(self.placed(savon + br + FI), {"fi": FI})
        self.assertEqual(self.placed("Joensuu 30.9. + 3.10. ||" + br + EN), {"en": EN})
        self.assertEqual(self.placed(niagara + br + FI), {"fi": FI})

    def test_titles_in_parentheses_do_not_place_a_paragraph(self):
        """Unohdettu saari's cast paragraph on kiertue.cine.fi, read 2026-10-04 and cut off
        mid-word by the cinema, was filed as English."""
        cast = ("Elokuvan ääninäyttelijöiden tähtisikermää täydentävät Emmy-ehdokas Jenny "
                "Slate (Marcell the Shell with Shoes On, Dying for Sex), Manny Jacinto (The "
                "Good Place, Top Gun: Maverick), BAFTA-ehdokas Dolly de Leon (Triangle of "
                "Sadness, Ghostlight), komedian supertähti Jo Koy (Haunted Mansion, Jo Koy: "
                "Live from B")
        self.assertEqual(self.placed(f"{FI}<br />\n<br />\n{cast}"), {"fi": f"{FI} {cast}"})
        sv = f"{SV} En film av David Ayer (Fury, End of Watch, The Beekeeper)."
        self.assertEqual(self.placed(f"{FI}<br />{sv}"), {"fi": FI, "sv": sv})

    def test_a_text_no_language_places_is_withheld(self):
        # Read 2026-09-28: Niagara's Twilight Zone tagline, Kinopirtti's placeholder and a
        # Kotkan Leffat closure notice listed as a film.
        for text in ("Hämärän pelottavat varjot", "Lisätietoja tulossa myöhemmin",
                     "Kinopalatsi on suljettu keskiviikkona 7.10.", UNPLACED):
            with self.subTest(text=text):
                self.assertEqual(self.placed(text), "")

    def test_fetch_site_publishes_the_placed_value(self):
        item = ('<div class="item joensuu date-26.9.2026"> <div> <p> <strong><span>LA 26.9. '
                'klo 18.00</span></strong> </p> <p> JOENSUU | TAPIO | TAPIO 3<br /> </p> </div> '
                '<div> <a class="button-screening" href="/salikartta?id=901"> Osta </a> </div> '
                "</div>")
        page = (f'<main><h1>Konsertti</h1><div class="description-container"><span>{NIAGARA}'
                f'</span></div><div class="screenings">{HIDDEN}{item}</div></main>')
        e = self.stub({"/elokuvat/ohjelmistossa": listing("/elokuvat/7/konsertti"),
                       "/elokuvat/7/konsertti": page})
        with redirect_stdout(io.StringIO()):
            out = e.fetch_site(self.site("savonkinot"), sleep=0)
        self.assertEqual([r["_syn"] for r in out["sk-tapio"]],
                         [{"fi": NIAGARA_FI, "sv": f"{NIAGARA_SV} {NIAGARA_SV2}"}])


if __name__ == "__main__":
    unittest.main()
