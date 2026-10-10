"""Every adapter's real output meets common.Show, and run.py refuses one that does not.

The show dict is read by key in run.py, synmerge and the client, and a key one adapter
leaves out is the bug class that filled the day multi-provider landed. BioRex shipped
without `price` and was covered only by a `|| ''` in the client. This parses each of the
thirteen registry modules' own fixtures, the ones its adapter tests already use, and
checks every emitted show: the seventeen keys present with the annotated type, an
`eventId`, a `start` that parses as an aware ISO instant, an absolute http(s) `url`, and
`provider` and `venue` naming the site the fixture is for. Extra keys are allowed when
they are the adapter's own (`_`-prefixed) or a documented optional field; anything else
is a typo until it is named here.

`common.check_shows` is the same rule at runtime: run_site calls it on what fetch_site
returned, so a violation fails the site like a parse error and the previous files stay.
"""
import contextlib
import datetime
import html
import io
import json
import pathlib
import tempfile
import unittest
from urllib.parse import urlsplit

import _ctx                                                # noqa: F401
import common
import registry
import run

import test_cinemahouse as C
import test_etiketti_templates as E
import test_gilda_duplicates as G
import test_isohannu as I
import test_tmb as T
import test_julia as J
import test_biokaari as BK
import test_vaakuna as V
import test_kuvakukko as KK
import test_kirkkonummi as KN
import test_biosavoy as BS
import test_cinemantsala as CM
import test_hamina as HM
import test_johku as JK
import test_kinola as KL
import test_kinotour as KT
import test_lieksa as LK
import test_marita as MA
import test_navetta as NV
import test_tribe as TR
import test_vpk as VK
import test_pallas as PL
import test_huvimylly as HV
import test_alatalo as AL
import test_elavienkuvien as EK
import test_matintupa as MT
import test_kuusamotalo as KU
import test_kinohuovi as KH
import test_localhub as LH
import test_k13 as K13
import test_helios as HE
import test_heureka as H
import test_nexxo_rooms as N
import test_orion
import test_regina
import test_riviera_links as R
import test_tapiola
import test_vista

# README "Data shape": `age` is the screening's own limit, `year` the release year the
# cinema publishes; `movieUrl` is BioRex's film page for its enrichment loop.
OPTIONAL = {"age", "year", "movieUrl"}
TODAY = datetime.date(2026, 9, 4)


def mod(name):
    import importlib
    return importlib.import_module(name)


def per_venue(x):
    """Every sample as {venue_id: [shows]}, the fetch_site shape."""
    if isinstance(x, dict):
        return x
    out = {}
    for s in x:
        out.setdefault(s.get("venue"), []).append(s)
    return out


def sample_orion():
    return mod("orion").parse(test_orion.PAGE, today=test_orion.TODAY), "orion", ["or-helsinki"]


def sample_nexxo():
    site = N.SITE
    return (mod("nexxo").parse(N.PAYLOAD, site, site["venues"][0]),
            site["provider"], [v["id"] for v in site["venues"]])


def sample_regina():
    site = test_regina.SITE
    return mod("regina").parse_schedule(test_regina.WINDOW_1), site["provider"], [v["id"] for v in site["venues"]]


def sample_riviera():
    """Through fetch_site: `parse` returns rows the site loop normalises. The POST is
    answered from the fixture and the price pass is stood down."""
    rv = mod("riviera")
    site = rv.SITES[0]
    page = R.listing(
        R.item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", R.button("982926")),
        R.item("The Odyssey", "Ti 15.9.2026", "18:30", "Punavuori, Sali 2", R.button("983270")))
    real_fetch, real_prices = rv.fetch, rv.prices.run
    rv.fetch = lambda url, **kw: json.dumps({"data": {"movies": page}}).encode()
    rv.prices.run = lambda *a, **kw: None
    try:
        out = rv.fetch_site(site)
    finally:
        rv.fetch, rv.prices.run = real_fetch, real_prices
    return out, site["provider"], [v["id"] for v in site["venues"]]


def sample_tapiola():
    site = test_tapiola.SITE
    return mod("tapiola").parse(test_tapiola.LISTING), site["provider"], [v["id"] for v in site["venues"]]


def sample_vista():
    site = test_vista.SITE
    return (mod("vista").parse_schedule(test_vista.SCHEDULE, site, site["venues"]),
            site["provider"], [v["id"] for v in site["venues"]])


def sample_gilda():
    site = G.SITE
    doc = G.payload(G.film(1513, "Presidentin kyyditys", [
        G.show(1513, "Presidentin kyyditys", "2026-09-05 18:00:00"),
        G.show(1513, "Presidentin kyyditys", "2026-09-06 20:00:00")]))
    with contextlib.redirect_stdout(io.StringIO()):
        out = mod("gilda").parse(doc, site)
    return out, site["provider"], [v["id"] for v in site["venues"]]


def sample_heureka():
    hk = H.heureka()
    shows, _ = hk.parse_calendar(H.CALENDAR, H.TODAY, days=7)
    return shows, hk.SITES[0]["provider"], [v["id"] for v in hk.SITES[0]["venues"]]


def sample_cinemahouse():
    """Through `parse`, because the rows carry no metadata: the film grid supplies the
    poster, the age limit, the runtime and the genres, and a sample taken from the row
    parser alone would never exercise that join."""
    site = C.PIISPANRISTI
    with contextlib.redirect_stdout(io.StringIO()):
        shows = mod("cinemahouse").parse(C.PR_PAGE, site, today=C.TODAY)
    return shows, site["provider"], [v["id"] for v in site["venues"]]


def sample_etiketti():
    e = E.load()
    real = e.get
    e.get = E.stub_get({"/elokuvat/ohjelmistossa": E.listing("/elokuvat/3268/insidious"),
                        "/elokuvat/3268/insidious": E.KOTKA_FILM})
    try:
        out = e.fetch_site(E.site("kotkanleffat"), sleep=0)
    finally:
        e.get = real
    return out, "kotkanleffat", [v["id"] for v in E.site("kotkanleffat")["venues"]]


def sample_biorex():
    """No BioRex fixture exists elsewhere: two admin-ajax items in the shape biorex.py's
    regexes name, the data layer JSON attribute-escaped as WordPress prints it."""
    br = mod("biorex")
    venue = br.SITES[0]["venues"][0]
    def item(show_id, when):
        dl = html.escape(json.dumps({"movieId": 4711, "movieName": "Autofiktio", "showId": show_id,
                                     "showCinemaName": venue["name"], "showDateTime": when}), quote=True)
        return ('<div class="showtime-item ">'
                f'<div data-click-data-layer="{dl}"><a\nhref="https://biorex.fi/secure-redirect/{show_id}"\n'
                'class="x">Osta</a></div>'
                f'<div class="showtime-item__place__value">{venue["name"]}, Sali 6</div>'
                '<span class="showtime-item__movie-rating">(K-16)</span>'
                '<span class="showtime-item__format">EN</span>'
                '<a class="showtime-item__movie-name" href="https://biorex.fi/elokuva/autofiktio/">Autofiktio</a></div>')
    page = item(99, "2026-09-05T18:00:00+03:00") + item(100, "2026-09-06T20:00:00+03:00")
    return br.parse(page, venue), "biorex", [venue["id"]]


def sample_engel():
    en = mod("engel")
    # The weekdays are the ones 2026 actually carries: 5 September is a Saturday and
    # 6 September a Sunday. `engel.parse` selects the year from them since 2026-09-19,
    # so a fixture weekday that contradicts its own date would skip the row.
    page = ('<a href="/elokuva/autofiktio/"><span>La 05.09.</span><span>klo 21:30</span>'
            '<h3>Autofiktio</h3>Osta liput</a>'
            '<a href="/elokuva/troija/"><span>Su 06.09.</span><span>klo 19:00</span>'
            '<h3>Troija</h3>Osta liput</a>')
    return en.parse(page, today=TODAY), "engel", [en.VENUE["id"]]


def sample_kinoakseli():
    ka = mod("kinoakseli")
    # 5 September 2026 is a Saturday and 6 September a Sunday. `kinoakseli.parse`
    # selects the year from the row's weekday since 2026-09-19, so a fixture weekday
    # that contradicts its own date would skip the row.
    page = ('<p>Draama</p><p>Ikäraja : 12</p><p>Liput : 9€</p>'
            '<h2 class="elementor-heading-title x"><a href="https://kinoakseli.fi/elokuva-autofiktio/">'
            'Autofiktio</a></h2><p>Näytösajat La 5.9. klo 18:00, Su 6.9. klo 20:00 (dub.)</p>')
    return ka.parse(page, today=TODAY), "kinoakseli", [ka.VENUE["id"]]


def sample_isohannu():
    """Through `parse`, which is the whole read: the film pages only fold metadata onto
    rows this already produced, so the contract is met or missed here."""
    site = I.SITE
    return (mod("isohannu").parse(I.PAGE), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_tmb():
    """The two-screen fixture: it exercises the auditorium branch the single-screen sites
    never enter, and `parse` is the whole read."""
    site = T.MANIA
    return (mod("tmb").parse(T.TWO_SCREEN, site, site["venues"][0]), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_biosavoy():
    """No `today`: this source publishes a full instant per row."""
    site = BS.biosavoy.SITES[0]
    return (mod("biosavoy").parse(BS.LISTING), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_cinemantsala():
    """No `today` and no window: every row carries a UTC instant, and the sample is the
    concatenation of two windows the way `fetch_site` assembles them."""
    site = CM.cm.SITES[0]
    rows = [CM.show(13394, "2026-09-15T13:45:00.000Z"),
            CM.show(13391, "2026-09-15T14:00:00.000Z", mid=1013,
                    title="Presidentin kyyditys", screen="Sali 2", rating="K12"),
            CM.show(13233, "2026-12-01T16:30:00.000Z", mid=1003, title="Hamnet",
                    rating="K16", audio="EN")]
    return (mod("cinemantsala").parse(rows), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_kinola():
    """One provider per sample, so this is Laika: the template with the sold-out
    fallback and the live act the policy omits, both in the input. Kilta's template is
    held to the same contract inside tests/test_kinola.py."""
    site = KL.LAIKA
    out = mod("kinola").parse(
        site,
        KL.listing(KL.laika_row("hetki", "Hetki ennen valoa"),
                   KL.laika_row("hetki", "Hetki ennen valoa", date="17/09/2026 16:00"),
                   KL.laika_row("arppa", "Arppa", date="30/10/2026 19:00", sold=True)),
        {"hetki": KL.laika_film(), "arppa": KL.LIVE_ACT})[0]
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_hamina():
    """`today` pinned: the page prints a weekday and no year. One film with a line-level
    price override and one with none, so both price paths are in the sample."""
    site = HM.SITE
    shows, _ = mod("hamina").rows(site, HM.TWO, HM.TODAY)
    return ({site["venues"][0]["id"]: shows}, site["provider"],
            [v["id"] for v in site["venues"]])


def sample_johku():
    """Bio Marilyn: a coming-soon entry with no time and a hall hire in the same schedule,
    so the sample carries both of the shapes that must not reach a venue file."""
    site = JK.MARILYN
    blocks = JK.blocks_of(JK.front((1, JK.two_days() + [
        JK.entry("3", "Digger", "2026-10-16 00:00", product="1052", upcoming="1"),
        JK.entry("4", "Salivaraus", "2026-10-09 20:00", product="94",
                 path="/fi_FI/products/94-sali")])))
    out = mod("johku").parse(site, blocks, {"1038": JK.film(), "1039": JK.film(syn=JK.SYN_SV)},
                             JK.NOW)[0]
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_kirkkonummi():
    """`today` pinned: the page publishes no year."""
    site = KN.kirkkonummi.SITES[0]
    return (mod("kirkkonummi").parse(KN.LISTING, today=KN.TODAY), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_kuvakukko():
    """Two venues on one page; `today` pinned because the page publishes no year."""
    site = KK.kuvakukko.SITES[0]
    per = mod("kuvakukko").parse(KK.LISTING_PAGE, site, today=KK.TODAY)
    return ([s for v in per.values() for s in v], site["provider"],
            [v["id"] for v in site["venues"]])


def sample_vaakuna():
    """`today` is pinned: the page publishes no year and a sample resolved against the
    real clock would drift."""
    site = V.vaakuna.SITES[0]
    return (mod("vaakuna").parse(V.LISTING, today=V.TODAY), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_biokaari():
    """Through `parse`: the film pages only fold metadata onto rows this produced."""
    site = BK.biokaari.SITES[0]
    return (mod("biokaari").parse(BK.LISTING), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_julia():
    site = J.julia.SITES[0]
    return (mod("julia").parse(J.LISTING), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_kinotour():
    """One declared town and one this repo does not list, so the sample carries the row
    that must not reach a venue file as well as the one that must."""
    site = KT.SITE
    out, _ = mod("kinotour").rows(site, KT.page(
        KT.DECLARED, KT.UNDECLARED,
        KT.card(title="Ryhmä Hau, Dinoelokuva", iso="2026-10-04T17:00:00+03:00",
                shown="4.10.2026 · klo 17.00", city="Lieto", place="Lieto · Valtuustosali")))
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_lieksa():
    """Two films in the programme section and one in the coming-soon one, so the sample
    carries the article that must not reach a venue file as well as those that must."""
    site = LK.SITE
    out, _ = mod("lieksa").rows(site, LK.TWO, LK.TODAY)
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_marita():
    """Two films over three screenings, one of them priced by a band, so the row that must
    publish no amount is in the sample beside the two that must."""
    site = MA.SITE
    out, _ = mod("marita").rows(site, MA.page(
        MA.row("19.09.2026", "17.00", "Hetki ennen valoa"),
        MA.row("20.09.2026", "14.00", "Hetki ennen valoa"),
        MA.row("20.09.2026", "16.00", "Minemare", url=MA.OTHER, price="Hinta: 10/8 €",
               age="16")))
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_navetta():
    """Two screenings against a shelf of three blocks, so the block that must publish
    nothing is in the sample beside the two that must."""
    site = NV.SITE
    out, _ = mod("navetta").rows(site, NV.TWO, NV.TODAY)
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_vpk():
    """Two occurrences in the declared category, priced from the cinema's own page."""
    site = VK.SITE
    return (mod("vpk").parse(site, VK.TWO, "12€"), site["provider"],
            [v["id"] for v in site["venues"]])


def sample_pallas():
    """Three rows: one priced outright, one whose block names two amounts and must publish
    none, and one whose image is the page's landscape hero and must publish no poster."""
    site = PL.SITE
    out, _ = mod("pallas").rows(site, PL.page(
        PL.heading(PL.SAT),
        PL.row(PL.SAT, "18.00", "Myrskyn ikkuna"),
        PL.row(PL.SAT, "19.00", "Orchestra Nazionale della Luna", meta=None,
               price="22/25€"),
        PL.row(PL.SAT, "20.00", "Resident Evil", meta="1h 34min -K16-",
               poster=PL.image(PL.HERO, 3704, 2248))), PL.TODAY)
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_huvimylly():
    """Three screenings over two headings, one of them a title split across two items, so
    the continuation rule is exercised beside two rows that close their own titles."""
    site = HV.SITE
    a = HV.TODAY + datetime.timedelta(days=3)
    b = HV.TODAY + datetime.timedelta(days=4)
    out, _ = mod("huvimylly").rows(site, mod("huvimylly").items(HV.payload(
        HV.head(a), "Klo 14.00 Pirjo -s-", "Klo 18.00 Kerro se kaikille -k12/9-",
        HV.head(b), "Klo 15.00 Dome Karukosken", "Rakkautta ja virtahepoja -k12/9-")),
        HV.TODAY)
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_tribe():
    """Ritz Vaasa: a band price, a portrait poster and a calendar illustration in one
    sample, so the two fields that must stay empty are exercised here as well."""
    site = TR.RITZ
    out = mod("tribe").parse(site, [
        TR.event(1, "Donnie Darko", "2026-09-27 17:00:00", "2026-09-27 14:00:00",
                 image=TR.POSTER),
        TR.event(2, "Blue Baby", "2026-09-29 19:30:00", "2026-09-29 16:30:00",
                 cost="10€ – 12€", values=("10", "12"), image=TR.CALENDAR_IMG)])[0]
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_alatalo():
    """Two towns on one page, the first with a title split across two lines, so the venue
    switch and the continuation rule are exercised together."""
    site = AL.SITE
    a, b = AL.soon(5), AL.soon(6)
    out, _ = mod("alatalo").rows(site, mod("alatalo").lines(AL.page(
        "Pudasj\u00e4rvi Pohjant\u00e4hti", AL.head(a), "Klo 16.30 Saapasjalkakissa",
        "unohdettu saari -k7/4-", "Kiuruvesi Kiurusali", AL.head(b),
        "Klo 13.00 Pirjo -s-")), AL.TODAY)
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_elavienkuvien():
    """Two films, one of them with a screening whose clock time is not set yet, so the
    row that must not reach a venue file is exercised beside the two that must."""
    site = EK.SITE
    out = EK.E.shows_of(site, {"slug": "ohjelmisto/a/",
                               "url": f"{EK.BASE}/ohjelmisto/a/", "img": "p.jpg"},
                        EK.film_page(title="Film A"))
    out += EK.E.shows_of(site, {"slug": "ohjelmisto/b/",
                                "url": f"{EK.BASE}/ohjelmisto/b/", "img": "q.jpg"},
                         EK.film_page(title="Film B", age="7",
                                      rows=("ti 22.9.2026 klo 19:30 | 13€ / 11€",
                                            "pe 2.10.2026")))
    return (out, site["provider"], [v["id"] for v in site["venues"]])


def sample_matintupa():
    """Two film blocks, one priced and one whose ticket line states a condition, so the
    row that publishes no price is exercised beside the rows that do."""
    out, _ = MT.M.rows(MT.SITE, MT.page(
        MT.block(),
        MT.block(slug="neulekino", title="Kaunis Rietas Onnellinen", age="12",
                 liput="14,00 €. Kts. lisätiedot", kesto="1 h 57 min",
                 times=("to 24.9. klo 18.00", "pe 25.9. klo 18.00"))), MT.TODAY)
    return (out, MT.SITE["provider"], [v["id"] for v in MT.SITE["venues"]])


def sample_k13():
    """A festival block with two timed rows beside a dated entry with no clock, so the
    row that must not exist is exercised beside the two that must."""
    out, _ = K13.K.rows(K13.SITE, K13.page(K13.KINOKKA, K13.KINOKKA_BODY, K13.FESTIVAL,
                                           K13.FREE, K13.ROW1, K13.ROW2), K13.TODAY)
    return (out, K13.SITE["provider"], [v["id"] for v in K13.SITE["venues"]])


def sample_helios():
    """Two Kino Helios rows beside a Doc Helios one, so the strand that must not publish
    is exercised beside the two that must."""
    out, _ = HE.H.rows(HE.SITE, [
        HE.event(),
        HE.event(subtitle="Doc Helios", title="Kappale kauneinta Suomea"),
        HE.event(title="Myrskyn ikkuna (12)", start="2026-09-24T15:00",
                 end="2026-09-24T17:00", master="792036"),
    ], HE.TODAY)
    return (out, HE.SITE["provider"], [v["id"] for v in HE.SITE["venues"]])


def sample_kinohuovi():
    """One card with a single date and one with a range, so the row that comes from an
    expanded range is exercised beside the one that does not."""
    out, _ = KH.K.rows(KH.SITE, KH.page(KH.card(), KH.RANGE), KH.TODAY)
    return (out, KH.SITE["provider"], [v["id"] for v in KH.SITE["venues"]])


def sample_localhub():
    """Two film pages, one carrying two dates and a sold-out one, so a row with a
    date-level flag is exercised beside the ordinary ones."""
    out, _ = LH.L.rows(LH.SITE, LH.payload(
        LH.page(dates=[LH.date(), LH.date("2026-10-04T10:00:00.000Z",
                                          "2026-10-04T12:00:00.000Z", sold=True)]),
        LH.page(pid="6a8e9b61600c7004a13930d4", name="Heart of the Beast",
                ticket="https://verkkokauppa.ylivieska.fi/tuote/heart-of-the-beast")),
        LH.TODAY)
    return (out, LH.SITE["provider"], [v["id"] for v in LH.SITE["venues"]])


def sample_kuusamotalo():
    """Two film posts and a notice, so the post that must not reach a venue file is
    exercised beside the two that must."""
    out, _ = KU.K.rows(KU.SITE, [
        KU.post(),
        KU.post(pid=15950, title="Rakkautta ja virtahepoja", rating="-K12-",
                kesto="Kesto 1h 40min", times=("Pe 25.9. klo 19", "La 26.9. klo 19")),
        KU.notice(),
    ], KU.TODAY)
    return (out, KU.SITE["provider"], [v["id"] for v in KU.SITE["venues"]])


SAMPLES = {
    "orion": sample_orion, "nexxo": sample_nexxo, "regina": sample_regina,
    "riviera": sample_riviera, "tapiola": sample_tapiola, "vista": sample_vista,
    "gilda": sample_gilda, "heureka": sample_heureka, "etiketti": sample_etiketti,
    "biorex": sample_biorex, "engel": sample_engel, "kinoakseli": sample_kinoakseli,
    "cinemahouse": sample_cinemahouse, "isohannu": sample_isohannu, "tmb": sample_tmb,
    "julia": sample_julia, "biokaari": sample_biokaari,
    "vaakuna": sample_vaakuna, "kuvakukko": sample_kuvakukko,
    "kirkkonummi": sample_kirkkonummi, "biosavoy": sample_biosavoy,
    "cinemantsala": sample_cinemantsala, "kinola": sample_kinola,
    "johku": sample_johku, "tribe": sample_tribe, "hamina": sample_hamina,
    "kinotour": sample_kinotour, "marita": sample_marita,
    "lieksa": sample_lieksa, "navetta": sample_navetta, "vpk": sample_vpk,
    "pallas": sample_pallas, "huvimylly": sample_huvimylly,
    "alatalo": sample_alatalo, "elavienkuvien": sample_elavienkuvien,
    "matintupa": sample_matintupa, "kuusamotalo": sample_kuusamotalo,
    "kinohuovi": sample_kinohuovi, "localhub": sample_localhub,
    "k13": sample_k13, "helios": sample_helios,
}


class EveryModuleHasASampleTest(unittest.TestCase):
    def test_the_registry_modules_and_the_samples_are_the_same_set(self):
        """A new adapter has to bring a sample here, or its output is never held to the
        contract before it runs."""
        modules = {p["module"] for p in registry.PROVIDERS if p["module"]}
        self.assertEqual(modules, set(SAMPLES))


class ShowContractTest(unittest.TestCase):
    """Runs once per adapter over its fixture output."""

    def check(self, name):
        out, provider, venue_ids = SAMPLES[name]()
        pv = per_venue(out)
        shows = [s for v in pv.values() for s in v]
        self.assertGreaterEqual(len(shows), 2, f"{name}: the fixture yields fewer than two shows")
        # The runtime rule first, so the two cannot disagree.
        common.check_shows(pv, name, set(venue_ids))
        for s in shows:
            with self.subTest(adapter=name, title=s.get("title")):
                for k, t in common.Show.__annotations__.items():
                    self.assertIn(k, s)
                    self.assertIsInstance(s[k], t, f"{k}={s[k]!r}")
                extra = {k for k in s if k not in common.SHOW_KEYS and not k.startswith("_")}
                self.assertEqual(extra - OPTIONAL, set(), f"undocumented keys {extra - OPTIONAL}")
                self.assertTrue(s["eventId"], "empty eventId")
                self.assertTrue(s["title"].strip(), "blank title")
                when = datetime.datetime.fromisoformat(s["start"])
                self.assertIsNotNone(when.tzinfo, f"naive start {s['start']!r}")
                parts = urlsplit(s["url"])
                self.assertIn(parts.scheme, ("http", "https"), s["url"])
                self.assertTrue(parts.netloc, f"no host in {s['url']!r}")
                self.assertEqual(s["provider"], provider)
                self.assertIn(s["venue"], venue_ids)
        # Identity: two shows of one film at one instant in one room are one screening.
        keys = [(s["venue"], s["eventId"], s["start"], s["aud"]) for s in shows]
        self.assertEqual(len(keys), len(set(keys)), f"{name}: duplicate screenings in the fixture output")


for _name in SAMPLES:
    setattr(ShowContractTest, f"test_{_name}", (lambda n: lambda self: self.check(n))(_name))


class CheckShowsAtTheBoundaryTest(unittest.TestCase):
    """run_site refuses a fetch_site result that breaks the contract, before any write."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self.old_out))

    @staticmethod
    def show(**over):
        s = {k: ("" if t is str else False) for k, t in common.Show.__annotations__.items()}
        s.update(eventId="e1", title="Autofiktio", start="2026-09-05T18:00:00+03:00",
                 url="https://example.org/x", provider="fake", venue="v1", theatre="Kino")
        s.update(over)
        return s

    def site(self):
        return {"provider": "fake", "label": "Fake", "venues": [{"id": "v1", "name": "Kino", "short": "Kino", "city": "X"}]}

    def run_with(self, shows):
        class Mod:
            __name__ = "fake"
            def fetch_site(self, site):
                return {"v1": shows}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run.run_site(Mod(), self.site(), "2026-09-05T12:00:00+00:00")

    def test_a_conforming_result_is_written(self):
        live, total, *_ = self.run_with([self.show(), self.show(eventId="e2", start="2026-09-06T18:00:00+03:00")])
        self.assertEqual((live, total), (1, 2))
        self.assertTrue((run.OUT / "area-v1.json").exists())

    def test_a_missing_key_fails_the_site_and_writes_nothing(self):
        bad = self.show(); del bad["price"]
        with self.assertRaisesRegex(RuntimeError, r"no 'price'"):
            self.run_with([self.show(), bad])
        self.assertEqual(list(run.OUT.iterdir()), [])

    def test_a_wrong_type_fails_the_site(self):
        with self.assertRaisesRegex(RuntimeError, r"'soldOut' is str, not bool"):
            self.run_with([self.show(), self.show(soldOut="no")])

    def test_a_show_filed_under_another_venue_fails_the_site(self):
        with self.assertRaisesRegex(RuntimeError, r"filed under venue 'v2'"):
            self.run_with([self.show(), self.show(venue="v2")])

    def test_shows_for_an_unlisted_venue_fail_the_site(self):
        with self.assertRaisesRegex(RuntimeError, r"which the site does not list"):
            common.check_shows({"ghost": [self.show(venue="ghost")]}, "fake", {"v1"})

    def test_a_start_with_no_offset_fails_the_site_and_writes_nothing(self):
        """The client would read it in the viewer's zone: three hours out on a laptop in
        UTC, which is the fault the offset exists to prevent."""
        for start in ("2026-09-26T18:00:00", "2026-09-26 18:00", "pe 26.9. klo 18"):
            with self.subTest(start=start):
                with self.assertRaisesRegex(RuntimeError, r"not ISO 8601 with an offset"):
                    self.run_with([self.show(), self.show(start=start)])
                self.assertEqual(list(run.OUT.iterdir()), [])

    def test_a_url_that_is_not_absolute_http_fails_the_site(self):
        for url in ("/checkout/1f2e", "//example.org/x", "javascript:alert(1)",
                    "ftp://example.org/x", "https:/example.org"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(RuntimeError, r"not an absolute http\(s\) URL"):
                    self.run_with([self.show(), self.show(url=url)])

    def test_an_empty_url_and_a_cleartext_one_are_accepted(self):
        """"" is the contract's empty value, and two hosts serve no TLS at all."""
        live, total, *_ = self.run_with([self.show(url=""),
                                         self.show(eventId="e2", url="http://example.org/x")])
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()
