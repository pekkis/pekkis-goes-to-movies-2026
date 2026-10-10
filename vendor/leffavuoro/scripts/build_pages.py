#!/usr/bin/env python3
"""Pre-render one indexable page per venue and per multi-venue city, in fi and en.

The app is a single JS-rendered URL, so the site was one entry in a search index. These
pages come from the same committed JSON the app reads: one source of truth, no second
fetcher.

    /teatteri/{slug}/           fi, one venue        /sv/teatteri/{slug}/  /en/theatre/{slug}/
    /kaupunki/{slug}/           fi, a whole city     /sv/kaupunki/{slug}/  /en/city/{slug}/
    /sitemap.xml                every page, every language

City pages exist only where a city has more than one venue, the app's own rule for its
combined view. A city page for a one-venue city would duplicate the venue page, so those
cities go into the venue page's title, h1 and JSON-LD address instead.

Constraints:

- No third-party requests: inline CSS, the self-hosted Archivo (`/fonts/`) and only
  same-origin posters (`data/posters/...`). A hot-linked poster is skipped. See the
  Privacy section of the README.
- No JavaScript that renders content. Two inline scripts handle the theme: the one in the
  head reads `localStorage["kino-theme"]` before first paint and sets `data-theme`, as the
  app does; the one at the end of the body wires the toggle, which writes the same key and
  is hidden when the scripts did not run. The only other script element is the JSON-LD.
- The card is the app's card. Film facts (rating, runtime, genres, score) fold from the
  day's screenings by first non-empty value. Language sits on the card when every
  screening shares it and on the screening when they differ (`lang_parts` is the app's
  `langTxt`, `price_label` its `priceLabel`, each pinned against the client). The showtime
  keeps time, the cinema on a city page, and the room verbatim. `stubTags` is not ported.
- A page is rewritten only when its bytes change, and no timestamp appears in the body:
  several runs a day across ~180 pages would otherwise commit near-identical HTML forever.
- No `aggregateRating` in the markup. The ratings are TMDB's, and presenting another
  party's ratings as the page's own is against Google's structured-data guidelines. The
  rating is shown as credited text.
"""
import argparse
import decimal
import html
import json
import re
import sys
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "providers"))

import common                                    # noqa: E402
from synmerge import norm                        # noqa: E402

ROOT = HERE.parent
DATA = ROOT / "data"
FI = ZoneInfo("Europe/Helsinki")
SITE = "https://leffavuoro.fi"
# The route a cinema uses to ask a question or to be taken out. The pipeline's
# User-Agent points every provider at this site, so these pages have to answer too --
# a search result is as likely a first landing as the app itself. Constant, so
# write_if_changed keeps working.

# Posters that reached the page generator still pointing at somebody else's host. Every
# provider's images are supposed to be rewritten into data/posters/ by mirror_posters,
# which runs immediately before this. A non-zero count here means that did not happen for
# some venue, and the reader sees a placeholder tile instead of a poster -- silently,
# because the page renders fine without it.
#
# Live cause, 2026-08-30: the local half publishes Kino Engel and Kino Akseli posters as
# the cinema's own URLs and only the cloud run rewrites them, so a cancelled cloud run
# left two venues with no posters at all until the next cron. The workflow no longer
# cancels; this line is here so the next way it happens is not silent too.
_unmirrored_hosts = {}


def _unmirrored(img):
    if img.startswith("http") or img.startswith("//"):
        host = img.split("/")[2] if "//" in img else img
        _unmirrored_hosts[host] = _unmirrored_hosts.get(host, 0) + 1
    return ""
# Every language the pages are published in, in the order the selector shows them. The
# app's own LANGS, and the client's `startupLang()` accepts each as `?lang=`.
LANGS = ("fi", "sv", "en")
DAYS = 4          # today plus three: enough to answer "what is on", small enough to commit
CITY_DAYS = 2     # a ten-venue city at seven days was a 1.2 MB page
# An empty page says nothing is published only while the run behind it is recent. The app
# judges that on the reader's clock against `STALE_H`; a page is built for a day, so this
# counts days, which keeps `--date recorded` reproducible: a provider file written before
# the day ahead of the build day is too old to vouch for an empty page.
PAGE_STALE_DAYS = 1
LD_DAYS = 2       # markup for today and tomorrow only, see ld_json()


# ---------------------------------------------------------------- strings

# Finnish city names inflect irregularly: Helsinki -> Helsingissä, Tampere -> Tampereella,
# Espoo -> Espoossa. Suffixing a case ending onto the nominative produces "Helsinkissä",
# which is exactly the tell that a page was generated by a script. Every string below
# therefore uses the city name in the nominative with a separator, which stays correct for
# any city a future provider brings.
L = {
    "fi": {
        "lang": "fi", "locale": "fi_FI",
        "venue_title": "{venue}, {city} \u2013 elokuvat ja n\u00e4yt\u00f6sajat",
        "city_title": "Elokuvat ja n\u00e4yt\u00f6sajat \u2013 {city}",
        "venue_h1": "{venue} \u2013 n\u00e4yt\u00f6sajat",
        "city_h1": "Elokuvat ja n\u00e4yt\u00f6sajat \u2013 {city}",
        # The snippet a search result shows, and the og:description with it. One opening
        # sentence plus the ending the provider's booking mode settles, so the page never
        # offers an action the cinema does not have: the old copy listed "liput" for every
        # venue, which is wrong for door sales and for a screening included in admission.
        # The separator is the en dash the titles and the city links already use, and the
        # names stay uninflected: a case ending glued onto a nominative is the tell.
        "venue_desc": "{venue} \u2013 {city}: tulevat elokuvat ja n\u00e4yt\u00f6sajat.",
        "desc_buy": "Tarkista elokuvien tiedot ja siirry n\u00e4yt\u00f6sajasta ostamaan liput "
                    "teatterin sivulta.",
        "desc_reserve": "Tarkista elokuvien tiedot ja siirry n\u00e4yt\u00f6sajasta varaamaan "
                        "paikat teatterin sivulta.",
        "desc_list": "Tarkista elokuvien tiedot ja avaa n\u00e4yt\u00f6sajasta teatterin oma "
                     "ohjelmisto.",
        # Claim first. Behind the filler sentence these two read "Liput myydään te" at a
        # snippet cut: on all 21 door and admission pages the claim began past char 120.
        "desc_door": "Liput myyd\u00e4\u00e4n teatterin ovelta. Samalta sivulta l\u00f6yd\u00e4t "
                     "my\u00f6s ik\u00e4rajat, kielet ja kestot.",
        "desc_admission": "N\u00e4yt\u00f6kset sis\u00e4ltyv\u00e4t p\u00e4\u00e4sylippuun. Samalta "
                          "sivulta l\u00f6yd\u00e4t my\u00f6s elokuvien tiedot.",
        "desc_other": "Samalta sivulta l\u00f6yd\u00e4t my\u00f6s ik\u00e4rajat, kielet ja "
                      "elokuvien kestot.",
        # No cinema list: a ten-venue city spent the whole snippet on names, and the list
        # went stale in the index whenever a venue was added or renamed.
        "city_desc": "{city}: Mit\u00e4 elokuvia l\u00e4hip\u00e4ivin\u00e4 esitet\u00e4\u00e4n? Vertaa "
                     "elokuvateatterien n\u00e4yt\u00f6saikoja, ik\u00e4rajoja, kieli\u00e4 ja "
                     "saatavilla olevia lippulinkkej\u00e4.",
        "city_sub": "{n} teatteria",
        # One sentence per booking mode, from the registry's `book` field. The old copy
        # promised a ticket page for every cinema, which was wrong for Kino Akseli (no
        # links at all) and for Nexxo (the programme page, not a ticket).
        "intro_buy": "Katso l\u00e4hip\u00e4ivien n\u00e4yt\u00f6sajat. N\u00e4yt\u00f6sajasta p\u00e4\u00e4set "
                     "lipunmyyntiin sivustolla {host}.",
        "intro_reserve": "Katso l\u00e4hip\u00e4ivien n\u00e4yt\u00f6sajat. N\u00e4yt\u00f6sajasta p\u00e4\u00e4set "
                         "paikkavaraukseen sivustolla {host}.",
        "intro_list": "Katso l\u00e4hip\u00e4ivien n\u00e4yt\u00f6sajat. N\u00e4yt\u00f6sajasta p\u00e4\u00e4set "
                      "teatterin ohjelmistoon sivustolla {host}.",
        "intro_door": "Katso l\u00e4hip\u00e4ivien n\u00e4yt\u00f6sajat. Liput myyd\u00e4\u00e4n ovelta.",
        # Screenings included in a general admission ticket (Heureka): the time opens the
        # ticket shop and reserves no seat.
        "intro_admission": "Katso l\u00e4hip\u00e4ivien n\u00e4yt\u00f6sajat. Esitykset sis\u00e4ltyv\u00e4t "
                           "p\u00e4\u00e4sylipun hintaan. P\u00e4\u00e4sylipun voi ostaa osoitteesta {host}.",
        # Appended when every screening on the page shares a screening-level age limit;
        # the pages render no per-stub age chip. See age_note().
        "age_note": "N\u00e4yt\u00f6sten ik\u00e4raja on {n} vuotta.",
        # A city mixes booking modes, so this promises only what every venue has.
        "city_intro": "Katso {n} teatterin n\u00e4yt\u00f6sajat l\u00e4hip\u00e4iville. N\u00e4yt\u00f6sajasta "
                      "p\u00e4\u00e4set teatterin lippu- tai ohjelmistosivulle, kun linkki on "
                      "saatavilla.",
        "cta": "Avaa koko ohjelmisto",
        "days": ["Ma", "Ti", "Ke", "To", "Pe", "La", "Su"],
        "no_shows": "L\u00e4hip\u00e4iville ei ole julkaistu n\u00e4yt\u00f6ksi\u00e4.",
        "no_shows_unchecked": "L\u00e4hip\u00e4ivien n\u00e4yt\u00f6ksi\u00e4 ei voitu tarkistaa.",
        "next_show": "Seuraava n\u00e4yt\u00f6s: {when}",
        "mins": "min", "tmdb": "TMDB",
        "venues_h": "Teatterit \u2013 {city}",
        "city_link": "Kaikki teatterit \u2013 {city}",
        "subs": "tekstitys: {}", "no_subs": "ei tekstityst\u00e4", "lang_nav": "Kieli",
        "theme": "Vaihda teemaa", "a_theme": "Vaihda vaalean ja tumman teeman v\u00e4lill\u00e4",
        "from": "alkaen", "free": "Vapaa p\u00e4\u00e4sy", "votes": "\u00e4\u00e4nt\u00e4", "rtg": "TMDB-arvio {v}/10",
        "rtgN": "TMDB-arvio {v}/10, {n} \u00e4\u00e4nt\u00e4", "rtg1": "TMDB-arvio {v}/10, 1 \u00e4\u00e4ni",
        "dec": ",",
        "sources": "N\u00e4yt\u00f6stiedot: kyseisen teatterin oma ohjelmisto. Arvosanat ja "
                   "kuvaukset: TMDB. Henkil\u00f6kohtainen harrastusprojekti, ei "
                   "sidoksissa teattereihin.",
        "contact": "Elokuvateattereille: yhteydenotot ja poistopyynn\u00f6t",
        "source": "L\u00e4hdekoodi",
        "status_link": "Palvelun tila ja tiedot \u2197",
    },
    "sv": {
        "lang": "sv", "locale": "sv_FI",
        "venue_title": "{venue}, {city} \u2013 filmer och visningstider",
        "city_title": "Filmer och visningstider \u2013 {city}",
        "venue_h1": "{venue} \u2013 visningstider",
        "city_h1": "Filmer och visningstider \u2013 {city}",
        "venue_desc": "{venue} \u2013 {city}: kommande filmer och visningstider.",
        "desc_buy": "L\u00e4s om filmerna och v\u00e4lj en visningstid f\u00f6r att k\u00f6pa biljetter "
                    "p\u00e5 biografens webbplats.",
        "desc_reserve": "L\u00e4s om filmerna och v\u00e4lj en visningstid f\u00f6r att boka platser "
                        "p\u00e5 biografens webbplats.",
        "desc_list": "L\u00e4s om filmerna och v\u00e4lj en visningstid f\u00f6r att \u00f6ppna biografens "
                     "eget program.",
        "desc_door": "Biljetter s\u00e4ljs p\u00e5 plats. P\u00e5 samma sida hittar du ocks\u00e5 "
                     "\u00e5ldersgr\u00e4nser, spr\u00e5k och speltider.",
        "desc_admission": "Visningarna ing\u00e5r i intr\u00e4desbiljetten. P\u00e5 samma sida kan du "
                          "ocks\u00e5 l\u00e4sa om filmerna.",
        "desc_other": "P\u00e5 samma sida hittar du ocks\u00e5 \u00e5ldersgr\u00e4nser, spr\u00e5k och "
                      "speltider.",
        "city_desc": "{city}: vilka filmer visas de n\u00e4rmaste dagarna? J\u00e4mf\u00f6r "
                     "biografernas visningstider, \u00e5ldersgr\u00e4nser, spr\u00e5k och "
                     "tillg\u00e4ngliga biljettl\u00e4nkar.",
        "city_sub": "{n} biografer",
        "intro_buy": "Se visningstiderna f\u00f6r de n\u00e4rmaste dagarna. V\u00e4lj en tid f\u00f6r att "
                     "komma till biljettf\u00f6rs\u00e4ljningen p\u00e5 {host}.",
        "intro_reserve": "Se visningstiderna f\u00f6r de n\u00e4rmaste dagarna. V\u00e4lj en tid f\u00f6r att "
                         "komma till platsbokningen p\u00e5 {host}.",
        "intro_list": "Se visningstiderna f\u00f6r de n\u00e4rmaste dagarna. V\u00e4lj en tid f\u00f6r att "
                      "komma till biografens program p\u00e5 {host}.",
        "intro_door": "Se visningstiderna f\u00f6r de n\u00e4rmaste dagarna. Biljetter s\u00e4ljs p\u00e5 "
                      "plats.",
        "intro_admission": "Se visningstiderna f\u00f6r de n\u00e4rmaste dagarna. Visningarna ing\u00e5r "
                           "i intr\u00e4desbiljetten, som s\u00e4ljs p\u00e5 {host}.",
        "age_note": "\u00c5ldersgr\u00e4nsen f\u00f6r visningarna \u00e4r {n} \u00e5r.",
        "city_intro": "Se visningstiderna fr\u00e5n {n} biografer f\u00f6r de n\u00e4rmaste dagarna. "
                      "V\u00e4lj en tid f\u00f6r att komma till biografens biljett- eller "
                      "programsida n\u00e4r en l\u00e4nk finns.",
        "cta": "\u00d6ppna hela programmet",
        "days": ["M\u00e5n", "Tis", "Ons", "Tors", "Fre", "L\u00f6r", "S\u00f6n"],
        "no_shows": "Inga visningar har publicerats f\u00f6r de n\u00e4rmaste dagarna.",
        "no_shows_unchecked": "Visningarna f\u00f6r de n\u00e4rmaste dagarna kunde inte kontrolleras.",
        "next_show": "N\u00e4sta visning: {when}",
        "mins": "min", "tmdb": "TMDB",
        "venues_h": "Biografer \u2013 {city}",
        "city_link": "Alla biografer \u2013 {city}",
        "subs": "textning: {}", "subs_lead": "Textning: {}", "no_subs": "ingen textning",
        "no_subs_lead": "Ingen textning", "lang_nav": "Spr\u00e5k",
        "theme": "Byt tema", "a_theme": "Byt mellan ljust och m\u00f6rkt tema",
        "from": "fr\u00e5n", "free": "Fritt intr\u00e4de", "votes": "r\u00f6ster", "rtg": "TMDB-betyg {v}/10",
        "rtgN": "TMDB-betyg {v}/10, {n} r\u00f6ster", "rtg1": "TMDB-betyg {v}/10, 1 r\u00f6st",
        "dec": ",",
        "sources": "Visningstider: varje biografs eget program. Betyg och "
                   "beskrivningar: TMDB. Ett personligt hobbyprojekt, utan koppling "
                   "till biograferna.",
        "contact": "F\u00f6r biografer: kontakt och beg\u00e4ran om borttagning",
        "source": "K\u00e4llkod",
        "status_link": "Tj\u00e4nstens status och information \u2197",
    },
    "en": {
        "lang": "en", "locale": "en_GB",
        "venue_title": "{venue}, {city} \u2013 films and showtimes",
        "city_title": "Films and showtimes \u2013 {city}",
        "venue_h1": "{venue} \u2013 showtimes",
        "city_h1": "Films and showtimes \u2013 {city}",
        "venue_desc": "See upcoming films and showtimes at {venue} in {city}.",
        "desc_buy": "Check the film details, then choose a showtime to buy tickets on "
                    "the cinema\u2019s website.",
        "desc_reserve": "Check the film details, then choose a showtime to reserve seats "
                        "on the cinema\u2019s website.",
        "desc_list": "Check the film details, then choose a showtime to open the "
                     "cinema\u2019s own programme.",
        "desc_door": "Tickets are sold at the cinema. You can also check age ratings, "
                     "languages and runtimes.",
        "desc_admission": "Screenings are included with admission. You can also check "
                          "the film details.",
        "desc_other": "You can also check age ratings, languages and runtimes.",
        "city_desc": "What\u2019s showing in {city} over the next few days? Compare cinema "
                     "showtimes, age ratings, languages and available ticket links in "
                     "one view.",
        "city_sub": "{n} cinemas",
        "intro_buy": "See showtimes for the next few days. Choose a time to buy tickets "
                     "on {host}.",
        "intro_reserve": "See showtimes for the next few days. Choose a time to reserve "
                         "seats on {host}.",
        "intro_list": "See showtimes for the next few days. Choose a time to open the "
                      "cinema programme on {host}.",
        "intro_door": "See showtimes for the next few days. Tickets are sold at the door.",
        "intro_admission": "See showtimes for the next few days. Screenings are included in "
                           "the admission ticket, sold on {host}.",
        "age_note": "Age limit {n} years.",
        "city_intro": "See showtimes from {n} cinemas for the next few days. Choose a time "
                      "to open the cinema\u2019s ticket or programme page, where available.",
        "cta": "See the full programme",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "no_shows": "No showtimes published for the next few days.",
        "no_shows_unchecked": "Showtimes for the next few days could not be checked.",
        "next_show": "Next screening: {when}",
        "mins": "min", "tmdb": "TMDB",
        "venues_h": "Cinemas \u2013 {city}",
        "city_link": "All cinemas \u2013 {city}",
        "subs": "{} subtitles", "no_subs": "no subtitles", "lang_nav": "Language",
        "theme": "Switch theme", "a_theme": "Switch between light and dark theme",
        "from": "from", "free": "Free", "votes": "votes", "rtg": "TMDB rating {v}/10",
        "rtgN": "TMDB rating {v}/10 from {n} votes", "rtg1": "TMDB rating {v}/10 from 1 vote",
        "dec": ".",
        "sources": "Showtimes: each cinema's own schedule. Ratings and descriptions: "
                   "TMDB. A personal hobby project, unaffiliated with the cinemas.",
        "contact": "For cinemas: enquiries and removal requests",
        "source": "Source",
        "status_link": "Service status and information \u2197",
    },
}

# The booking verb comes from the registry; a mode this table does not know reads as a
# ticket page, which is what every provider but two offers.
def venue_intro(t, book, host):
    return t.get("intro_" + (book or "buy"), t["intro_buy"]).format(host=host)


# The modes the description has an ending for. Unlike venue_intro, an unknown mode and a
# missing one fall back to the ending that promises nothing beyond the page itself: a
# description is what a search result quotes, so guessing "buy" there would advertise a
# ticket link the next provider may not have.
DESC_MODES = ("buy", "reserve", "list", "door", "admission")


def venue_desc(t, venue, city, book):
    end = t["desc_" + book] if book in DESC_MODES else t["desc_other"]
    return t["venue_desc"].format(venue=venue, city=city) + " " + end


def city_desc(t, city):
    return t["city_desc"].format(city=city)


def city_sv():
    """{Finnish city name: Swedish name}, read from the app's own `CITY_SV` in index.html.

    The Swedish pages printed the Finnish name ("Filmer och visningstider – Turku") while
    the app's Swedish mode shows "Åbo" and links to that page (audit G9). One table, read
    rather than copied, so the pages cannot drift from the app. Display only: slugs, keys,
    `?area=` and the JSON-LD locality keep the Finnish name, as `CITY_SV` does in the app.

    No table found is {}: the Swedish pages print the Finnish name, as before, rather than
    a display name stopping the whole build. test_swedish_city_names.py fails on the
    committed index.html losing it.
    """
    m = re.search(r"const CITY_SV = \{(.*?)\};", INDEX.read_text(encoding="utf-8"), re.S)
    return dict(re.findall(r"([^\s,:'{}]+):'([^']*)'", m.group(1))) if m else {}


def city_name(city, lang, names):
    """The name a page in `lang` prints for `city`: the Swedish one where it exists."""
    return names.get(city, city) if lang == "sv" else city


def age_note(t, shows):
    """One sentence when every screening on the page shares a screening-level age limit.

    `age` is the room's limit, separate from the film's classification: K-18 on some
    Finnkino rows, K-5 on every Heureka row. The app puts it on each stub; these pages
    render no chip, so the venue-wide case is said once in the intro. A mixed page says
    nothing. -> "" when there is nothing to say.
    """
    ages = {(s.get("age") or "").strip() for s in shows}
    if len(ages) != 1:
        return ""
    n = re.sub(r"\D", "", ages.pop())
    return t["age_note"].format(n=n) if n else ""


# The client's language-name tables, copied for fi and en. `tests/test_landing_pages.py`
# reads the client's `LN` out of index.html and asserts these are identical, so the two
# cannot drift apart without a test saying so. Keys are ISO 639-1 codes.
LN = {
    "fi": {"FI": "suomi", "EN": "englanti", "SV": "ruotsi", "ES": "espanja", "DE": "saksa",
           "FR": "ranska", "IT": "italia", "RU": "ven\u00e4j\u00e4", "ET": "viro", "DA": "tanska",
           "NO": "norja", "IS": "islanti", "NL": "hollanti", "PL": "puola", "PT": "portugali",
           "UK": "ukraina", "AR": "arabia", "JA": "japani", "ZH": "kiina", "KO": "korea",
           "HI": "hindi", "TR": "turkki", "KA": "georgia", "TA": "tamili", "LT": "liettua",
           "ML": "malajalam", "FA": "persia", "HE": "heprea", "PS": "pa\u0161tu",
           "EL": "kreikka", "NE": "nepali", "RO": "romania", "YI": "jiddi\u0161"},
    "sv": {"FI": "finska", "EN": "engelska", "SV": "svenska", "ES": "spanska",
           "DE": "tyska", "FR": "franska", "IT": "italienska", "RU": "ryska",
           "ET": "estniska", "DA": "danska", "NO": "norska", "IS": "isl\u00e4ndska",
           "NL": "nederl\u00e4ndska", "PL": "polska", "PT": "portugisiska",
           "UK": "ukrainska", "AR": "arabiska", "JA": "japanska", "ZH": "kinesiska",
           "KO": "koreanska", "HI": "hindi", "TR": "turkiska", "KA": "georgiska",
           "TA": "tamil", "LT": "litauiska", "ML": "malayalam",
           "FA": "persiska", "HE": "hebreiska", "PS": "pashto", "EL": "grekiska",
           "NE": "nepali", "RO": "rum\u00e4nska", "YI": "jiddisch"},
    "en": {"FI": "Finnish", "EN": "English", "SV": "Swedish", "ES": "Spanish", "DE": "German",
           "FR": "French", "IT": "Italian", "RU": "Russian", "ET": "Estonian", "DA": "Danish",
           "NO": "Norwegian", "IS": "Icelandic", "NL": "Dutch", "PL": "Polish",
           "PT": "Portuguese", "UK": "Ukrainian", "AR": "Arabic", "JA": "Japanese",
           "ZH": "Chinese", "KO": "Korean", "HI": "Hindi", "TR": "Turkish", "KA": "Georgian",
           "TA": "Tamil", "LT": "Lithuanian", "ML": "Malayalam",
           "FA": "Persian", "HE": "Hebrew", "PS": "Pashto", "EL": "Greek", "NE": "Nepali",
           "RO": "Romanian", "YI": "Yiddish"},
}
# A code this table does not name still renders, as itself, so a new one is visible on
# the page rather than lost. `tests/test_landing_pages.py` asserts every code in the
# committed data resolves here.
# `CODE_ALIAS` (TU, MA), `NO_SUBTITLES` (XX) and `LN_EXTRA` (LT, ML) stood here from
# 2026-09-02 until 2026-09-15, covering codes the adapters were still publishing while
# their fixes turned the committed data over. All three were deleted once no
# `data/area-*.json` carried TU, MA or XX; LT and ML are in `LN` above. Record in
# docs/archive/2026-09-pipeline.md.
LANG_RE = re.compile(r"^([A-Z]{2}(?:-[A-Z]{2})?)-(A|S)$")
# A source saying outright that there are no subtitles, `XX-S` (the app's LNONE).
NO_SUBS = "XX"


def lang_parts(codes, lang, lead=True):
    """`"EN-A, FI-S, SV-S"` -> `["englanti", "tekstitys suomi/ruotsi"]`, the app's
    `langTxt` rule: -A is the spoken language, -S a subtitle language, a compound
    `FI-SV-A` is two languages, duplicates collapse in source order, an absent role is
    omitted, and a name the tables lack stays visible as its code. `lead` is false where
    the phrase follows other parts of a line; Swedish capitalises its label (`subs_lead`)
    only where it opens the label."""
    by = {"A": [], "S": []}
    none = False
    for raw in (codes or "").split(","):
        c = raw.strip()
        if not c:
            continue
        m = LANG_RE.match(c)
        if not m:
            by["A"].append(c)          # not a tag this app knows: shown rather than lost
            continue
        for x in m.group(1).split("-"):
            if m.group(2) == "S" and x == NO_SUBS:
                none = True
                continue
            name = LN[lang].get(x) or x
            if name not in by[m.group(2)]:
                by[m.group(2)].append(name)
    out = []
    if by["A"]:
        out.append("/".join(by["A"]))
    if by["S"]:
        key = "subs_lead" if lead and not out and "subs_lead" in L[lang] else "subs"
        out.append(L[lang][key].format("/".join(by["S"])))
    elif none:
        key = "no_subs_lead" if lead and not out and "no_subs_lead" in L[lang] else "no_subs"
        out.append(L[lang][key])
    return out


PRICE_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
# The client's FREE_RE: a source's own free-admission label, the whole string.
FREE_RE = re.compile(r"^\s*(?:vapaa\s+p\u00e4\u00e4sy|maksuton|ilmainen|free(?:\s+(?:admission|entry))?|gratis"
                     r"|fritt\s+intr\u00e4de|fri\s+entr\u00e9)\s*[.!]?\s*$", re.I)


def price_label(rows, lang):
    """The app's `priceLabel`, for the same rows. The first number anywhere in the string
    is the price, sign included so "-5\u20ac" stays rejected; a floor is either two different
    amounts or a source that says so itself ("alkaen 10\u20ac"), tested on shape rather than
    on the word because the word is in the provider's language. `tests/test_landing_pages.py`
    runs the client's own harness cases through this and asserts the same answers."""
    floor, free, vals = False, False, []
    for r in rows:
        raw = str(r.get("price") or "").replace(",", ".")
        m = PRICE_NUM.search(raw)
        if not m:
            free = free or bool(FREE_RE.match(raw))
            continue
        try:
            v = float(m.group(0))
        except ValueError:
            continue
        if v != v or v <= 0:
            continue
        if re.search(r"[^\d\s.,\u20ac$\u00a3]", raw.replace(m.group(0), "", 1)):
            floor = True
        vals.append(v)
    if not vals:
        return L[lang]["free"] if free else ""
    lo, hi = min(vals), max(vals)

    def fmt(v):
        n = str(int(round(v))) if round(v * 100) % 100 == 0 else f"{v:.2f}"
        # Finnish typography, as in the client: "10,50 €" with a non-breaking space.
        return n.replace(".", ",") + "\u00a0\u20ac" if lang == "fi" else n + "\u20ac"

    return fmt(lo) if (lo == hi and not floor) else f"{L[lang]['from']} {fmt(lo)}"


VOTE_SOLID = 25     # the app's: a rating on fewer votes is dimmed, not hidden


def js_fixed(x, digits):
    """JavaScript's `x.toFixed(digits)`: the double's exact value, a tie rounded up.
    Python's format rounds a tie to even, so 1250 votes read "1.2k" here and "1.3k" in
    the app (audit G6)."""
    q = decimal.Decimal(1).scaleb(-digits)
    return str(decimal.Decimal(x).quantize(q, rounding=decimal.ROUND_HALF_UP))


def js_number(v):
    """JavaScript's `String(v)` for a score: 8.0 is "8" and 7.5 is "7.5", as the app's
    ring prints it. `str()` wrote "8.0" on 786 rings in 171 committed pages (audit G6)."""
    s = repr(float(v))
    return s[:-2] if s.endswith(".0") else s


def short_votes(n):
    return (f"{js_fixed(n / 1000, 1 if n < 10000 else 0)}k") if n >= 1000 else str(n)


def score_ring(tmdb, votes, t):
    """The app's ring, as static markup: arc for the glance, number for the value, vote
    count beside it. `role="img"` so the label is read as one thing, a phrase in the page's
    language with its own decimal sign: "TMDB-arvio 7,1/10, 41 ääntä", the app's `scoreRing`.
    No `aggregateRating` in the JSON-LD, see the module docstring."""
    if not tmdb:
        return ""
    n = int(votes or 0)
    thin = " thin" if n and n < VOTE_SOLID else ""
    shown = js_number(tmdb)
    lbl = t["rtg1" if n == 1 else "rtgN" if n else "rtg"].format(
        v=shown.replace(".", t["dec"]), n=n)
    return (f'<span class="ring{thin}" role="img" style="--v:{round(float(tmdb) * 10)}" '
            f'title="{esc(lbl)}" aria-label="{esc(lbl)}"><b>{esc(shown)}</b></span>'
            + (f'<span class="votes">{esc(short_votes(n))}</span>' if n else ""))


def first(shows, key):
    """A film fact folded across the day's screenings: the first non-empty value, so a
    chain that publishes no rating cannot blank the card when another one did."""
    for s in shows:
        if s.get(key):
            return s[key]
    return None


# The theme, before first paint. The same key and the same fallback as the app's
# `store`/`applyTheme`: a stored "dark" or "light" wins, otherwise the OS decides. Any
# other stored value is treated as absent rather than applied. Without this script the
# attribute is never set, the CSS falls back to `prefers-color-scheme`, and the toggle
# stays hidden, so a reader without JavaScript loses nothing they could use.
THEME_HEAD_JS = (
    "(function(){var k=null;try{k=localStorage.getItem('kino-theme')}catch(e){}"
    "var t=(k==='dark'||k==='light')?k:(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');"
    "document.documentElement.setAttribute('data-theme',t)})();"
)
# The toggle: the app's own handler, and theme-color follows the applied --bg so a
# translucent status bar draws the clock in the right colour. Both metas are rewritten
# because the no-script page carries one per scheme.
THEME_BODY_JS = (
    "(function(){var b=document.getElementById('themeToggle');if(!b)return;"
    "function paint(){var c=getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()||'#0D0E12';"
    "var m=document.querySelectorAll('meta[name=\\'theme-color\\']');"
    "for(var i=0;i<m.length;i++){m[i].removeAttribute('media');m[i].setAttribute('content',c)}}"
    "paint();"
    "b.onclick=function(){var next=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';"
    "document.documentElement.setAttribute('data-theme',next);"
    "try{localStorage.setItem('kino-theme',next)}catch(e){}paint()}})();"
)

# The app's own tokens, both themes: a stored choice through `data-theme` first, the OS
# through `prefers-color-scheme` otherwise. Same Archivo files, same two unicode-range
# subsets, absolute paths because the pages live in subdirectories. The synopsis is
# clamped to three lines on a phone by CSS alone: the full text stays in the markup, so
# the crawler and the visitor read the same document.
CSS = """
@font-face{font-family:'Archivo';font-style:normal;font-weight:100 900;font-stretch:62% 125%;font-display:swap;src:url(/fonts/archivo-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:'Archivo';font-style:normal;font-weight:100 900;font-stretch:62% 125%;font-display:swap;src:url(/fonts/archivo-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
:root{--bg:#F6F7F9;--surface:#FFFFFF;--ink:#16181D;--muted:#5C6470;--line:#E3E6EB;--accent:#B8860B;--accent-text:#8A6508;--chip-bg:#FFFFFF;--shadow:0 1px 3px rgba(22,24,29,.06)}
:root[data-theme=dark]{--bg:#0D0E12;--surface:#16181F;--ink:#EDEDEA;--muted:#AEB5C2;--line:#262A33;--accent:#E8B84B;--accent-text:#E8B84B;--chip-bg:#1C1F28;--shadow:0 1px 3px rgba(0,0,0,.4)}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0D0E12;--surface:#16181F;--ink:#EDEDEA;--muted:#AEB5C2;--line:#262A33;--accent:#E8B84B;--accent-text:#E8B84B;--chip-bg:#1C1F28;--shadow:0 1px 3px rgba(0,0,0,.4)}}
*{box-sizing:border-box;margin:0;padding:0}
html{color-scheme:light dark}
html[data-theme=dark]{color-scheme:dark}
html[data-theme=light]{color-scheme:light}
body{font:16px/1.5 'Archivo',system-ui,sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
a{color:inherit}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:52rem;margin:0 auto;padding:0 20px 32px}
.bar{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
.bar .logo{margin-right:auto}
#themeToggle{border:1px solid var(--line);background:var(--surface);color:var(--ink);flex:0 0 44px;width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:1rem;line-height:1;display:grid;place-items:center;transition:border-color .15s,transform .15s}
#themeToggle:hover{border-color:var(--accent);transform:rotate(15deg)}
#themeToggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
html:not([data-theme]) #themeToggle{display:none}
.logo{font-stretch:125%;font-weight:900;letter-spacing:.16em;text-transform:uppercase;font-size:1.05rem;text-decoration:none;white-space:nowrap}
.logo span{color:var(--accent)}
.langseg{display:flex;flex:0 0 auto;overflow:hidden;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
.langseg a,.langseg span{display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;padding:0 10px;color:var(--muted);text-decoration:none;font-weight:800;font-size:.74rem;letter-spacing:.06em}
.langseg [aria-current]{background:var(--ink);color:var(--bg)}
.langseg a:hover{color:var(--ink)}
h1{font-size:1.5rem;font-weight:800;line-height:1.2;letter-spacing:-.01em;margin:22px 0 4px}
.sub{color:var(--muted);font-size:.9rem}
.sub .city{color:var(--ink);font-weight:600}
.sub .host{margin-left:14px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0}
.intro{color:var(--muted);margin:12px 0 14px}
.cta{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;min-height:48px;padding:0 16px;border-radius:10px;background:var(--ink);color:var(--bg);text-decoration:none;font-size:1rem;font-weight:800;line-height:1.3;white-space:nowrap;box-shadow:var(--shadow)}
.cta .arr{flex:0 0 auto}
.cta:hover{background:var(--accent-text);color:#fff}
:root[data-theme=dark] .cta:hover{background:var(--accent);color:var(--bg)}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]) .cta:hover{background:var(--accent);color:var(--bg)}}
.legend{display:flex;flex-wrap:wrap;gap:8px 14px;margin:14px 0 0;font-size:.72rem;color:var(--muted)}
.legend .lg{padding-left:8px;border-left:3px solid var(--chain,var(--line))}
h2.day{position:sticky;top:0;z-index:1;background:var(--bg);font-size:.95rem;font-weight:800;padding:16px 0 8px;margin-top:10px;border-bottom:1px solid var(--line)}
.film{display:flex;gap:18px;padding:20px 0;border-bottom:1px solid var(--line)}
.poster{flex:0 0 92px;width:92px;height:132px;border-radius:8px;object-fit:cover;background:var(--surface);box-shadow:var(--shadow)}
.poster.blank{border:1px solid var(--line)}
.info{flex:1;min-width:0}
h3{font-size:1.15rem;font-weight:800;line-height:1.25;letter-spacing:-.01em}
.meta1{margin-top:7px;display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:.82rem}
.rating{display:inline-block;border:1px solid var(--line);border-radius:5px;padding:1px 7px;font-weight:700;font-size:.72rem;color:var(--ink);background:var(--surface)}
.ring{--v:0;position:relative;flex:0 0 auto;width:30px;height:30px;border-radius:50%;background:conic-gradient(var(--accent) calc(var(--v) * 3.6deg),var(--line) 0);display:grid;place-items:center}
.ring::before{content:"";position:absolute;inset:3px;border-radius:50%;background:var(--bg)}
.ring b{position:relative;font-size:.68rem;font-weight:800;color:var(--ink);line-height:1}
.ring.thin{opacity:.55}
.votes{color:var(--muted);font-size:.7rem;font-weight:600}
.meta2{margin-top:5px;color:var(--muted);font-size:.8rem;display:flex;flex-wrap:wrap;gap:4px 14px}
.syn{color:var(--muted);font-size:.88rem;line-height:1.45;margin-top:6px}
.times{list-style:none;margin-top:12px;display:flex;flex-wrap:wrap;gap:8px}
.times.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(240px,100%),1fr))}
.times.grid>li{display:flex}.times.grid>li>.stub{flex:1 1 auto}
.grid .stub{display:grid;grid-template-columns:64px minmax(0,1fr) auto;grid-template-areas:"time aud price";align-items:stretch;min-height:40px}
.grid .stub .time{grid-area:time;padding:0 10px 0 12px}
.grid .stub .aud{grid-area:aud;min-width:0;display:flex;flex-wrap:wrap;align-items:center;align-content:center;gap:2px 4px;padding:6px 8px 6px 4px;line-height:1.2;overflow-wrap:anywhere}
.grid .stub .aud .a{white-space:normal}
.grid .stub .price{grid-area:price;flex:none;width:auto;display:flex;align-items:center;padding:0 10px 0 8px;font-size:.72rem;color:var(--muted);white-space:nowrap}
.stub{display:flex;align-items:stretch;min-height:40px;background:var(--chip-bg);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow);text-decoration:none;color:inherit;font-variant-numeric:tabular-nums;position:relative;overflow:hidden}
.stub[class*="chain-"]{border-left:3px solid var(--chain,var(--line))}
.stub .time{display:flex;align-items:center;padding:0 10px 0 12px;font-weight:800;font-size:.92rem;line-height:1.2;white-space:nowrap}
.stub .aud{display:flex;align-items:center;flex:1 1 auto;min-width:0;padding:6px 12px 6px 10px;font-size:.72rem;line-height:1.3;color:var(--muted);position:relative}
.stub .aud{flex-wrap:wrap;gap:0 4px}
.stub .aud .a{white-space:nowrap}
.stub .aud .slang{flex:1 0 100%;overflow:hidden;min-width:0;line-height:1.25}
.stub .aud .loc{flex:1 0 100%;overflow:hidden;min-width:0}
.fx,.stub .aud .slang .lp{display:flex;flex-wrap:wrap;margin-left:-9px;min-width:0}
.fx>span,.stub .aud .slang .lp>span{position:relative;padding-left:9px;min-width:0;overflow-wrap:anywhere}
.fx>span+span::before,.stub .aud .slang .lp>span+span::before{content:"";display:inline-block;vertical-align:middle;width:3px;height:3px;margin:0 3px 0 -6px;border-radius:.5px;background:var(--sq,var(--muted));opacity:.72}
.stub .price{flex:0 0 56px;width:56px;box-sizing:border-box;align-self:stretch;display:flex;align-items:center;justify-content:center;padding:0 4px;border-left:1px dashed var(--line);text-align:center;white-space:normal;font-size:.78rem;font-weight:700;line-height:1.1;color:var(--ink);position:relative}
.stub .price::before,.stub .price::after{content:"";position:absolute;left:-4px;width:8px;height:8px;border-radius:50%;background:var(--bg);border:1px solid var(--line)}
.stub .price::before{top:-5px}.stub .price::after{bottom:-5px}
.stub .price:empty{flex:0 0 16px;width:16px;padding:0}
.grid .stub .price:empty{width:16px;min-width:16px;padding:0}
.stub:hover,.stub:active,.stub:focus-visible{--sq:var(--accent);border-top-color:var(--accent);border-right-color:var(--accent);border-bottom-color:var(--accent)}
.also{margin-top:24px}
.also h2{font-size:.95rem;font-weight:800;margin-bottom:10px}
.also ul{list-style:none;display:flex;flex-wrap:wrap;gap:0 20px}
.vchip{position:relative;display:inline-flex;align-items:center;min-height:44px;padding:0 2px;color:inherit;font-size:.85rem;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px;text-decoration-color:var(--line)}
.vchip[class*="chain-"]{padding-left:13px}
.vchip[class*="chain-"]::before{content:"";position:absolute;left:0;top:50%;width:3px;height:1em;margin-top:-.5em;border-radius:2px;background:var(--chain,var(--line))}
.vchip:hover{text-decoration-color:var(--ink)}
.vchip:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem;display:flex;flex-direction:column;gap:6px}
footer a{color:inherit}
footer .statuslink a{color:var(--accent-text);font-weight:700;text-decoration:none;display:inline-block;padding:6px 0;min-height:34px}
footer .statuslink a:hover{text-decoration:underline}
@media(min-width:561px){.cta{width:fit-content;padding:0 18px}}
@media(max-width:560px){.wrap{padding:0 14px 28px}.logo{font-size:.82rem;letter-spacing:.08em}h1{font-size:1.3rem}.film{display:block}.poster{float:left;margin-right:18px;width:72px;height:104px}.times{clear:both}.times>li{flex:1 0 100%}.times.grid{grid-template-columns:1fr}.stub .price{margin-left:auto}h3{font-size:1.02rem}.syn{clear:both;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden}}
@media(max-width:360px){.bar{gap:8px}.logo{font-size:.6rem;letter-spacing:.02em}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
""".strip()


# ---------------------------------------------------------------- helpers

def slug(s):
    """URL slug. ä/ö/å are folded by hand first: NFKD does not decompose them in all
    Python builds, and a venue silently losing a letter changes its URL."""
    s = (s or "").lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("å", "a"), ("é", "e"), ("ü", "u")):
        s = s.replace(a, b)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def esc(s):
    return html.escape(str(s or ""), quote=True)


def city_of(v):
    """Mirror of cityOf() in index.html: BioRex and friends ship `city`, Finnkino names
    carry it as the last word ("Plevna Tampere")."""
    if v.get("city"):
        return v["city"]
    w = (v.get("name") or "").strip().split()
    return w[-1] if len(w) > 1 else (v.get("name") or "")


def short_of(v):
    if v.get("short"):
        return v["short"]
    city, n = city_of(v), (v.get("name") or "").strip()
    return n[:-(len(city) + 1)].strip() if n.endswith(" " + city) else n


def label_of(v, chains):
    chain, short = chains.get(v["provider"], ""), short_of(v)
    return f"{chain} {short}" if chain and not short.startswith(chain) else short


def unchecked(fetched, today):
    """Whether a provider file written at `fetched` is too old to vouch for an empty page
    built for `today`. A missing or unreadable stamp is not called old. -> bool"""
    try:
        at = datetime.fromisoformat(fetched).astimezone(FI).date()
    except (TypeError, ValueError):
        return False
    return at < today - timedelta(days=PAGE_STALE_DAYS)


def load_venues():
    """Every venue this build has pages for. -> [venue].

    Registered providers only. The glob used to take whatever `venues-*.json` was on
    disk, so removing a provider from the registry -- the documented way to drop a cinema,
    one entry -- left its venue file behind and this kept building its pages from it. The
    registry is the source of truth and `data/providers.json` is generated from it, which
    is the same list the client reads, so an unregistered file is data with no owner.
    Named in the log rather than dropped in silence: the file is still on disk and the
    reason its pages stopped appearing has to be findable.
    """
    out = []
    areas = json.loads((DATA / "areas.json").read_text())
    for a in areas.get("areas", []):
        out.append({**a, "provider": "finnkino", "fetched": areas.get("generated", "")})
    known = {p["id"] for p in
             json.loads((DATA / "providers.json").read_text())["providers"]}
    orphans = []
    for f in sorted(DATA.glob("venues-*.json")):
        d = json.loads(f.read_text())
        if d["provider"] not in known:
            orphans.append(f.name)
            continue
        for v in d.get("venues", []):
            out.append({**v, "provider": d["provider"], "fetched": d.get("generated", "")})
    if orphans:
        print(f"[pages] {len(orphans)} venue file(s) for providers the registry does not "
              f"list, skipped: {', '.join(orphans)}")
    return out


# A venue in a multi-venue city is read twice, once for its own page and once for the
# city's: 47 of 101 venues on 2026-09-17. The saving is small -- the whole build is about
# 0.19 s and this is a fraction of it -- so the reason to keep the cache is that the second
# read is pure waste, not that it was slow. Keyed by the file's identity rather than the
# venue id: the tests build from temp roots and from data they rewrite between builds, and
# a cache keyed on the id alone would hand the second build the first one's schedule.
_SHOWS = {}


def load_shows(vid):
    p = DATA / f"area-{vid}.json"
    if not p.exists():
        return []
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    hit = _SHOWS.get(key)
    if hit is None:
        hit = _SHOWS[key] = json.loads(p.read_text()).get("shows", [])
    # The caller must not mutate it, and none does: the city pass copies every show it
    # keeps (`{**s, "venueLabel": ...}`) and `group_by_day` only sorts and groups.
    return hit


def duration(minutes):
    try:
        n = int(minutes)
    except (TypeError, ValueError):
        return None
    return f"PT{n}M" if n > 0 else None


def genre_names(gids, genres, gmap, lang):
    """TMDB ids where we have them, the provider's own string otherwise. The chains
    disagree on spelling and their strings are Finnish even in English mode, so ids win
    when both exist."""
    if gids:
        names = [gmap.get(lang, {}).get(str(g)) for g in gids]
        names = [n for n in names if n]
        if names:
            return ", ".join(names)
    return (genres or "").strip().strip(",")


# ---------------------------------------------------------------- rendering

# --- city fold: the app's own film identity, ported ---
# `mergeKey` and `mergeIds` out of index.html. A city page is the app's combined view
# rendered ahead of time, so it has to answer "same film?" the same way; keyed on the raw
# title it did not, and Helsinki drew "Keltaiset Kirjeet" and "Keltaiset kirjeet" as two
# films on one day (7 such pairs across the committed city pages, 2026-09-22).
#
# Two signals, unioned, and neither is complete on its own -- the client's comment on
# mergeIds has the cases. The title key merges chains that agree on the title; the TMDB id
# merges chains that do not ("Coyote vs. Acme" at BioRex, "Kojootti vs. ACME" at Finnkino,
# both 1204680). tests/test_city_merge.py reads the client's regexes and its union rule out
# of index.html and fails if these drift from them.
#
# Venue pages keep grouping on the published title: a single provider's "(Dub)" and
# "(Orig)" rows are two entries in its own programme and two cards in the app's
# single-venue view, so merging them here would make the page disagree with the app in the
# other direction.
_MERGE_STRIP = (
    re.compile(r"\((?:suomeksi|dubattu|dub|orig\.?)\)", re.I),
    re.compile(r"\((?:re-?release|uudelleenjulkaisu|uusi\s+kopio)\)", re.I),
    # re.A on the two `\b` patterns: JavaScript's `\b` is ASCII, so the client strips
    # "suomeksi" from "äsuomeksi" and a Unicode `\b` here did not (audit E9). Only
    # these two: `\s` stays Unicode, as JavaScript's is, and norm() absorbs the rest.
    re.compile(r",?\s*\bsuomeksi\b", re.I | re.A),
    re.compile(r"\b(?:2d|3d|imax|4k)\b", re.I | re.A),
)


def merge_key(title):
    """The client's `mergeKey`. `norm` is its `normTitle`, already shared with
    enrich_tmdb and synmerge."""
    s = title or ""
    for rx in _MERGE_STRIP:
        s = rx.sub(" ", s)
    return norm(s)


def merge_roots(shows):
    """{merge_key: root} after unioning each title key with its films' TMDB ids.

    The client's `mergeIds`, as a union-find over the same two signals. Iteration order is
    the caller's, and the root a group settles on is never rendered -- only the grouping
    it produces is -- so a set's order cannot reach the page.
    """
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for s in shows:
        k = merge_key(s.get("title"))
        find(k)
        if s.get("tmdbId"):
            union(k, f"tmdb:{s['tmdbId']}")
    return {k: find(k) for k in list(parent)}


# A qualifier hangs off the end of a title behind one of these: "Kojootti vs. ACME,
# suomeksi", "Kojootti vs. ACME (englanniksi)", "Kojootti vs. ACME - Dub".
QUALIFIER_CHARS = " ,;:([-\u2013\u2014"
QUALIFIER_SEP = re.compile("[" + re.escape(QUALIFIER_CHARS) + "]+$")
# Below this a shared opening is a coincidence rather than the film's name.
SHARED_HEAD_MIN = 8


def shared_head(titles):
    """The film's name where every title in a merged group only adds a qualifier to it.
    -> str, or "" when they do not share one.

    Used where the TMDB id merged titles the title key did not, which is where a heading
    can lie: Kouvola held "Kojootti vs. ACME (suomeksi)" and "... (englanniksi)" as one
    card, and picking either spelling advertises one audio version for a card holding
    both. The shared opening advertises neither, and it is the cinemas' own text -- no
    word is translated, added or reworded.

    The opening has to end at a word boundary in every title, so "Keltaiset Kirjeet" and
    "Keltaiset kirjeet" could never become "Keltaiset"; that pair shares a title key
    anyway and never reaches here. "Coyote vs. Acme" and "Kojootti vs. ACME" share
    nothing, and fall back to the spelling count.
    """
    shortest = min(titles, key=len)
    n = 0
    while n < len(shortest) and all(t[n] == shortest[n] for t in titles):
        n += 1
    pre = QUALIFIER_SEP.sub("", shortest[:n])
    if len(pre) < SHARED_HEAD_MIN:
        return ""
    for t in titles:
        rest = t[len(pre):]
        if rest and rest[0] not in QUALIFIER_CHARS:
            return ""
    return pre


def merged_title(counts):
    """The heading one merged card carries. `counts` is {title: screenings}. -> str

    The spelling most of the screenings use, then the shortest, then codepoint order. The
    first rule is the one that decides in practice: a capitalisation slip is one cinema's
    and the other cinemas agree. The last two only have to be deterministic, because the
    pages are compared byte for byte by CI's regeneration check.

    `shared_head` comes first where it applies; see it for the case that needs it.

    The app takes the first screening's title instead, which is load order and cannot be
    reproduced here.
    """
    titles = list(counts)
    if len(titles) > 1:
        head = shared_head(titles)
        if head:
            return head
    return sorted(titles, key=lambda t: (-counts[t], len(t), t))[0]


def group_by_day(shows, today, days=DAYS, merge=False):
    """{iso date: {film title: [show, ...]}} for the next `days` days, times ascending.

    `merge` folds the cross-provider identity above, for the city pages. The heading is
    chosen over the whole window, so a film does not change its spelling between today and
    tomorrow on one page.
    """
    window = {(today + timedelta(days=i)).isoformat() for i in range(days)}
    inwin = [s for s in sorted(shows, key=lambda x: x.get("start") or "")
             if (s.get("start") or "")[:10] in window]
    if not merge:
        days = {}
        for s in inwin:
            days.setdefault(s["start"][:10], {}).setdefault(s.get("title") or "?", []).append(s)
        return days

    roots = merge_roots(inwin)
    spellings = {}
    for s in inwin:
        r = roots[merge_key(s.get("title"))]
        t = s.get("title") or "?"
        spellings.setdefault(r, {})
        spellings[r][t] = spellings[r].get(t, 0) + 1
    keys = {}
    for s in inwin:
        keys.setdefault(roots[merge_key(s.get("title"))], set()).add(merge_key(s.get("title")))
    # One title key in the group means the titles already agree up to case, format and the
    # markers mergeKey strips, so the spelling count decides and shared_head is not asked.
    heads = {r: (merged_title(c) if len(keys[r]) > 1
                 else sorted(c, key=lambda t: (-c[t], len(t), t))[0])
             for r, c in spellings.items()}
    days = {}
    for s in inwin:
        head = heads[roots[merge_key(s.get("title"))]]
        days.setdefault(s["start"][:10], {}).setdefault(head, []).append(s)
    return days
# --- end city fold ---


def next_show_day(shows, today, days):
    """The first date this venue or city has a screening on after the page's window. -> str

    An empty page said only that nothing was published for the next few days, which is true
    and unhelpful: the app already knew the cinema's next date and offered it, and the
    landing page for the same cinema did not (docs/research/flow-review.md, 2026-09-22). The data is the
    same file the page is built from, so this costs a pass over shows already in memory.

    Dates before the window are ignored by the comparison: `end` is at least `today`.
    """
    end = (today + timedelta(days=days - 1)).isoformat()
    later = [d for d in ((s.get("start") or "")[:10] for s in shows) if d > end]
    return min(later) if later else ""


def day_label(iso, t):
    """"La 4.10.": the weekday and the date. A page is read until the next build, hours
    after midnight, and "Tänään" named yesterday until then (2026-10-04)."""
    d = date.fromisoformat(iso)
    return f"{t['days'][d.weekday()]} {d.day}.{d.month}."


def clip(text, n=200):
    """Truncate on a word boundary with an ellipsis. Cutting mid-word looked like a bug
    and Google will re-truncate the snippet anyway."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ,.;:") + "\u2026"


# --- stub tags: the app's, for the merged city card ---
# `tagsOf` and `stubTags` out of index.html. A city card merges screenings that differ in
# format, so the difference has to survive on the ticket: "Spider-Man: Brand New Day" and
# "... 2D" are one card now, and LUXE, iSense, Prime and the dubbed/original marker are
# what separates its rows.
#
# City pages only. A theatre page merges nothing, so every row already carries its
# provider's own title and nothing is lost by leaving the tags off it.
#
# No glyph exception: the app keeps a tag it draws as a glyph (Anniskelu) on every stub
# even when all of them share it, because the glyph is where a reader looks. These pages
# draw no glyphs, so a shared tag folds onto the card like any other.
def tags_of(s):
    return [x for x in (s.get("method") or "").split(" · ") if x]


def common_tags(shows):
    """The format tags every screening of this film shares, in the first one's order."""
    sets = [set(tags_of(s)) for s in shows]
    out = []
    for f in tags_of(shows[0] if shows else {}):
        if f not in out and all(f in st for st in sets):
            out.append(f)
    return out


def stub_tags(tags, aud):
    """The app's `stubTags`: 2D is not worth a chip, and a tag the room name already says
    would print twice. Substring containment, as in the client."""
    a = (aud or "").lower()
    return [t for t in tags if t and t.lower() != "2d" and t.lower() not in a]
# --- end stub tags ---


def stub_parts(s, with_venue, lang, own_tags=()):
    """The showtime label, as (css class, text) pairs. The price is not a label part: it
    is its own element on the stub, see film_block.

    Theatre page: the room -- the page already names the cinema, and printing it again
    is how Joensuu read "Tapio · Sali Tapio 4". City page: the chain-prefixed cinema
    first, because a bare "Sali 6" identifies none of twelve. The room is the provider's
    value verbatim after the adapter's own normalisation; Leffabuumi's "KINOLINNA |
    SALI 1" means something and stays. Empty parts vanish, so no separator is ever
    leading, trailing or doubled.

    The language is not a label part: it is the stub's own line, see lang_line. `own_tags`
    is what this screening's format has and the card cannot claim for all of them. The
    classes decide wrapping only: the cinema may break at its spaces, the room stays on
    one line.
    """
    parts = []
    if with_venue:
        parts.append(("v", s.get("venueLabel") or ""))
    parts.append(("a", s.get("aud") or ""))
    parts += [("f", x) for x in (own_tags or [])]
    return [(c, t) for c, t in parts if t]


def lang_line(s, lang, after=False):
    """A screening's audio and subtitles as the stub's own line, the app's `slangHtml`:
    two parts that share a line while they fit and take one each when they do not. ""
    when the screening states no language, so the line is left out rather than guessed.
    Every stub that has one carries it and the card never does (2026-09-23). `after`: the
    stub's other facts precede it, so a hidden comma separates the two blocks."""
    parts = lang_parts(s.get("lang"), lang)
    if not parts:
        return ""
    last = len(parts) - 1
    return ((SR_COMMA if after else "") + '<span class="slang"><span class="lp">'
            + "".join(f"<span>{esc(p).replace('/', '/<wbr>')}{SR_COMMA if i < last else ''}</span>"
                      for i, p in enumerate(parts))
            + "</span></span>")


# A stub's facts are separate elements with a CSS square between two (`.fx`), the app's
# factSpans: each but the last ends in a visually hidden comma, so a screen reader does not
# run two facts together, and no separator is text that could open or end a line.
SR_COMMA = '<span class="sr-only">, </span>'


def _part(cls, text, more=False):
    """One label part. A language phrase joins names with "/", which Chrome will not break
    after on its own, so a six-language screening would clip in a 206 px column; a <wbr>
    after each slash is a break opportunity and no text. `more`: another fact follows."""
    body = esc(text).replace("/", "/<wbr>") if cls == "l" else esc(text)
    return f"<span class={cls}>{body}{SR_COMMA if more else ''}</span>"


# A film's own first release year, published as `oyear` by enrich_tmdb from an exact
# TMDB match. The heading shows it only for a film at least two calendar years old.
FILM_YEAR_FLOOR = 1888          # Roundhay Garden Scene; below it, not a film year
YEAR_RE = re.compile(r"^\d{4}$")
# A published title that already ends in a year, which seven did on 2026-09-20. The
# cinema has answered the question, so no second year is appended.
TITLE_ENDS_IN_YEAR = re.compile(r"\(\s*\d{4}\s*\)\s*$")


def film_title(title, shows, current_year):
    """The heading a reader sees: "Carrie (1976)". -> str.

    The same rule as `filmTitle()` in index.html, and the two are held to one shared
    table by tests/test_release_year.py, because a page and the app showing different
    titles for one film is the failure worth guarding here.

    `current_year` is the year the page is built *for*, in Europe/Helsinki, so a rebuild
    with --date recorded reproduces the committed markup instead of drifting on the day
    it happens to run. Everything else about the rule is in that function's comment: the
    year is the film's own and never the Finnish release or the screening's, anything
    that is not four plain digits is absent, and a missing year stays missing.

    The bare `title` remains the key for films-extra.json and the name in the JSON-LD.
    Only the visible heading carries the year, and no image carries it at all.
    """
    if not title:
        return title
    if TITLE_ENDS_IN_YEAR.search(title):
        return title
    y = str(first(shows, "oyear") or "").strip()
    if not YEAR_RE.match(y):
        return title
    n = int(y)
    if n < FILM_YEAR_FLOOR or not n < current_year - 1:
        return title
    return f"{title} ({y})"


def native_synopses():
    """Finnkino's own synopses, by its film id and by the TMDB id its pass trusted.
    -> (films, {tmdb id: [film id]}). Either file missing reads as none."""
    try:
        films = json.loads((DATA / "films.json").read_text()).get("films", {})
        cache = json.loads((DATA / "tmdb.json").read_text())
    except (OSError, ValueError):
        return {}, {}
    by_tmdb = {}
    for fid in sorted(cache):
        c = cache[fid]
        if isinstance(c, dict) and c.get("x") and c.get("i") and fid in films:
            by_tmdb.setdefault(c["i"], []).append(fid)
    return films, by_tmdb


def native_syn(shows, lang, native):
    """The card's synopsis from films.json when films-extra has none in `lang`: a Finnkino
    show's own film first, then a Finnkino film with the card's TMDB id. The app sheet
    reads films.json the same way; only Finnkino's text is borrowed, never another
    cinema's, which may be a note about its own screening. Finnkino's slots are not
    always what they claim: "fi" holding English, "en" holding the title alone
    (2026-09-27), so a text in another language or of three words or fewer is skipped."""
    films, by_tmdb = native or ({}, {})
    fids = [s.get("eventId") for s in shows if (s.get("provider") or "finnkino") == "finnkino"]
    fids += [f for s in shows for f in by_tmdb.get(s.get("tmdbId"), [])]
    for fid in fids:
        text = (((films.get(fid) or {}).get("s") or {}).get(lang) or "").strip()
        if len(text.split()) > 3 and common.syn_language(text) in (lang, ""):
            return text
    return ""


def film_block(title, shows, extra, gmap, lang, t, with_venue, syn_seen, current_year,
               native=None):
    rating, length = first(shows, "rating"), first(shows, "len")
    genres = genre_names(first(shows, "gids"), first(shows, "genres"), gmap, lang)
    tmdb = first(shows, "tmdb")
    # Language is each stub's own line (lang_line), never the card's. Price never folds: `price_label(shows)` skipped unpriced screenings, so
    # Autofiktio in Tampere carried "11€" at film level from Cinema Niagara's 16:15 while
    # Finnkino's 17:30 and 20:15 published none (2026-09-02). A price is the ticket's --
    # provider, time, format and ticket type differ -- so each stub prints its own or
    # nothing, even when every stub happens to agree.
    # Format, only where a card can merge providers: see stub_tags. A format every
    # screening shares says nothing that separates them and is not drawn at all, so a card
    # looks exactly as it did unless the fold put differing screenings on it.
    shared_tags = common_tags(shows) if with_venue else []

    meta1 = [score_ring(tmdb, first(shows, "votes"), t)]
    if rating:
        meta1.append(f'<span class="rating">{esc(rating)}</span>')
    meta1 = [m for m in meta1 if m]
    meta2 = []
    if genres:
        meta2.append(f"<span>{esc(genres)}</span>")
    if length:
        meta2.append(f"<span>{esc(length)} {t['mins']}</span>")

    # A synopsis only on a film's first appearance: a four-day page repeats the same
    # title daily, and printing it each time both bloated the page and read like padding.
    fx = extra.get(norm(title)) or {}
    syn = ""
    if title not in syn_seen:
        syn = clip(((fx.get("s") or {}).get(lang) or "") or native_syn(shows, lang, native))
        syn_seen.add(title)
    # Only same-origin posters: a hot-linked CDN poster would leak the visitor's IP. A
    # film with none keeps its column with a blank tile, so the text does not jump left.
    img = first(shows, "img") or ""
    if img.startswith("data/posters/"):
        poster = f'<img class="poster" src="/{esc(img)}" alt="" width="92" height="132" loading="lazy">'
    else:
        poster = _unmirrored(img) or '<div class="poster blank" aria-hidden="true"></div>'

    times = []
    for s in shows:
        clock = (s.get("start") or "")[11:16]
        own_tags = (stub_tags([f for f in tags_of(s) if f not in shared_tags], s.get("aud"))
                    if with_venue else [])
        parts = stub_parts(s, with_venue, lang, own_tags=own_tags)
        inline = ('<span class="loc"><span class="fx">'
                  + "".join(_part(c, x, i < len(parts) - 1) for i, (c, x) in enumerate(parts))
                  + "</span></span>") if parts else ""
        line = lang_line(s, lang, after=bool(parts))
        aud = f'<span class="aud">{inline}{line}</span>' if inline or line else ""
        # Always emitted, so the markup is one shape; an empty compartment (`:empty`) narrows
        # to a 16 px tail and keeps its seam and notches in both layouts (2026-09-13, v153).
        own_price = price_label([s], lang)
        price = f'<span class="price">{esc(own_price)}</span>'
        cls = f" chain-{esc(s['venueProvider'])}" if with_venue and s.get("venueProvider") else ""
        inner = f'<span class="time">{clock}</span>{aud}{price}'
        url = s.get("url") or ""
        times.append(f'<li><a class="stub{cls}" href="{esc(url)}" rel="nofollow noopener">{inner}</a></li>'
                     if url.startswith("http") else f'<li><span class="stub{cls}">{inner}</span></li>')

    # The app's combined view stacks time over place in a grid; its single-venue view
    # keeps the row stub. A city page is the combined view, a theatre page is not.
    grid = " grid" if with_venue else ""
    return (f'<article class="film">{poster}<div class="info">'
            f'<h3>{esc(film_title(title, shows, current_year))}</h3>'
            + (f'<div class="meta1">{"".join(meta1)}</div>' if meta1 else "")
            + (f'<div class="meta2">{"".join(meta2)}</div>' if meta2 else "")
            + (f'<p class="syn">{esc(syn)}</p>' if syn else "")
            + f'<ul class="times{grid}">{"".join(times)}</ul></div></article>')


def poster_url(s, extra):
    """Absolute poster URL for markup, or None.

    A URL in JSON-LD is read by the crawler, not fetched by the visitor's browser, so a
    cinema CDN or image.tmdb.org address here does not leak a reader's IP the way an
    <img> would. That is why markup can use posters the page itself refuses to render.
    """
    img = (s.get("img") or "").strip()
    if img.startswith("data/posters/"):
        return f"{SITE}/{img}"
    if img.startswith("http"):
        return img
    fx = extra.get(norm(s.get("title") or "")) or {}
    return fx.get("img") or None


def ld_json(days, today, city, extra):
    """ScreeningEvent per showtime, for today and tomorrow only.

    Three deliberate economies, all of which came out of a 1.2 MB Helsinki page:

    - **Only LD_DAYS of events.** Rich results are a near-term surface, and a crawler
      that revisits weekly would be reading stale markup for day six anyway.
    - **Theatres are `@id` nodes referenced by each event** rather than a nested address
      repeated per showtime. On a ten-venue city page that was most of the payload.
    - **No `availability`.** Sold-out state flips several times a day, so it would
      guarantee a rewrite of every popular page on every run while being stale in the
      index regardless. Price is stable enough to keep.

    No `aggregateRating`: the ratings are TMDB's, and presenting another party's ratings
    as the page's own is against Google's structured-data guidelines.
    """
    window = {(today + timedelta(days=i)).isoformat() for i in range(LD_DAYS)}
    theatres, events = {}, []
    for iso in sorted(d for d in days if d in window):
        for title, shows in days[iso].items():
            for s in shows:
                theatre = s.get("theatre") or ""
                tid = f"#venue-{slug(theatre)}"
                if tid not in theatres:
                    theatres[tid] = {
                        "@type": "MovieTheater", "@id": tid, "name": theatre,
                        "address": {"@type": "PostalAddress",
                                    "addressLocality": city, "addressCountry": "FI"},
                    }
                ev = {
                    "@type": "ScreeningEvent",
                    "name": title,
                    "startDate": s.get("start"),
                    "location": {"@id": tid},
                }
                # Google validates a nested Movie against its own Movie requirements, and
                # `image` is the one it treats as critical: without it the item is parsed,
                # rejected and reported as invalid. A Movie with no poster is no use to it
                # anyway, so the event keeps its name and drops the nested work rather
                # than shipping something that will only ever fail. One showtime in 3509
                # has no poster from any source.
                poster = poster_url(s, extra)
                if poster:
                    work = {"@type": "Movie", "name": title, "image": poster}
                    dur = duration(s.get("len"))
                    if dur:
                        work["duration"] = dur
                    if s.get("tmdbId"):
                        work["sameAs"] = \
                            f"https://www.themoviedb.org/movie/{s['tmdbId']}"
                    ev["workPresented"] = work
                if s.get("url", "").startswith("http"):
                    ev["url"] = s["url"]
                    # A zero price gets no Offer: Google reads `price: 0` as admission with
                    # no payment at all, and a cinema printing 0,00 does not say whether the
                    # screening is free or by invitation (Leffabuumi, 2026-09-24). The
                    # ticket draws no price for it either. The event and its url stay.
                    # A source's own free-admission label is the confirmation the zero
                    # lacked, so it gets `price: 0` with the ticket's label (2026-09-27).
                    if s.get("price"):
                        m = re.search(r"\d+([.,]\d+)?", str(s["price"]))
                        amount = (m.group(0).replace(",", ".") if m and float(
                            m.group(0).replace(",", ".")) > 0 else
                            "0" if not m and FREE_RE.match(str(s["price"])) else None)
                        if amount:
                            ev["offers"] = {"@type": "Offer", "url": s["url"],
                                            "price": amount, "priceCurrency": "EUR"}
                events.append(ev)
    out = json.dumps({"@context": "https://schema.org",
                      "@graph": list(theatres.values()) + events},
                     ensure_ascii=False, separators=(",", ":"))
    # This string is embedded inside <script>, and the HTML parser ends a script
    # element at the first literal "</script>" regardless of its type attribute --
    # valid JSON is not enough here. Titles, venue names and URLs are provider text,
    # so a hostile or merely unlucky title could otherwise close the element and open
    # a live script context. \uXXXX escapes are equivalent JSON, so a consumer parses
    # the identical value. U+2028/U+2029 are legal in JSON but not in JS source, and
    # ensure_ascii=False would emit them raw.
    for ch, rep in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                    ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        out = out.replace(ch, rep)
    return out


def lang_switch(lang, paths, t):
    """FI · SV · EN, the app's own selector. The page's language is a plain span marked
    current and the other two link to the same page in their language.

    Swedish used to link to the app instead, because it had no page: `/en/city/helsinki/`
    plus SV gave `/?area=city%3AHelsinki&lang=sv`, which is a different kind of page with a
    different set of controls and a different span of days, and going back to EN left the
    reader in the app (docs/research/flow-review.md, 2026-09-22). Changing the language now changes the
    language. The pages carry an hreflang for all three."""
    def seg(code):
        if code == lang:
            return f'<span aria-current="page">{code.upper()}</span>'
        return f'<a href="{esc(paths[code])}" hreflang="{code}">{code.upper()}</a>'
    return (f'<nav class="langseg" aria-label="{esc(t["lang_nav"])}">'
            + "".join(seg(c) for c in LANGS) + "</nav>")


def sub_html(sub):
    """The line under the heading. A cinema page's is its city and the cinema's own host,
    set apart by spacing and type rather than a separator character; a city page's is a
    plain count."""
    if isinstance(sub, tuple):
        city, host = sub
        return (f'<span class="city">{esc(city)}</span>'
                + (f'{SR_COMMA}<span class="host">{esc(host)}</span>' if host else ""))
    return esc(sub)


# The page's one analytics hook: /pageview.js sends a cookieless $pageview with this
# category and nothing about which page it was. Production origin only, nothing under DNT
# or GPC; the contract is in pageview.js and README's Privacy section.
PAGEVIEW_KINDS = {"city": "generated_city", "theatre": "generated_theatre"}


def pageview_tag(kind):
    return (f'<script src="/pageview.js" data-category="{PAGEVIEW_KINDS[kind]}" async>'
            f'</script>')


def page(*, lang, paths, title, desc, h1, sub, intro, days, today, t,
         extra, gmap, city, with_venue, legend, also, og_image, app_href, area, chain_css,
         kind, next_day="", native=None, stale=False):
    # One per published language plus x-default on the Finnish page, which is the one a
    # reader with no matching language gets.
    hreflangs = "\n".join(
        [f'<link rel="alternate" hreflang="{c}" href="{SITE}{paths[c]}">' for c in LANGS]
        + [f'<link rel="alternate" hreflang="x-default" href="{SITE}{paths["fi"]}">'])
    body, syn_seen = [], set()
    if not days:
        # The same sentence as before, plus the date the cinema does have something on,
        # when it has one. Same element, same place: a reader is told where to go next
        # rather than only that there is nothing here.
        # `day_label` already ends in the date's own full stop, so the sentence adds none.
        # `stale`: the run that found nothing is too old to repeat as current.
        line = t["no_shows_unchecked" if stale else "no_shows"]
        if next_day:
            line += " " + t["next_show"].format(when=day_label(next_day, t))
        body.append(f'<p class="intro"><span data-nosnippet>{esc(line)}</span></p>')
    for iso in sorted(days):
        body.append(f'<h2 class="day">{esc(day_label(iso, t))}</h2>')
        for title_, shows in sorted(days[iso].items(),
                                    key=lambda kv: (kv[1][0].get("start") or "", kv[0])):
            body.append(film_block(title_, shows, extra, gmap, lang, t,
                                   with_venue=with_venue, syn_seen=syn_seen,
                                   current_year=today.year, native=native))
    self_path = paths[lang]
    # The wordmark is the other way into the app, and it carries this page's language for
    # the same reason the CTA does. It was a bare "/", so an English page sent its reader
    # to a Finnish app unless they had already stored English (docs/research/flow-review.md, 2026-09-22).
    # `?lang=fi` on the Finnish pages too: startupLang() reads an explicit parameter before
    # a stored choice and does not overwrite the stored one, so the page a reader is
    # looking at decides the app they land in, whichever page it is.
    # One link, one line. The intro already says the app carries the days ahead, so the
    # button says only what it does; a two-line version read as a hero panel and pushed
    # the first showtime 16 px further down a phone.
    cta = (f'<a class="cta" href="{esc(app_href)}"><span data-nosnippet>{esc(t["cta"])}</span>'
           f'<span class="arr" aria-hidden="true" data-nosnippet>\u2192</span></a>')
    return f"""<!DOCTYPE html>
<html lang="{t['lang']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#F6F7F9">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0D0E12">
<script>{THEME_HEAD_JS}</script>
<link rel="canonical" href="{SITE}{self_path}">
{hreflangs}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Leffavuoro">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE}{self_path}">
<meta property="og:image" content="{SITE}{esc(og_image)}">
<meta property="og:locale" content="{t['locale']}">
<link rel="icon" href="/icon-192.png">
<link rel="preload" href="/fonts/archivo-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}
{chain_css}</style>
<script type="application/ld+json">{ld_json(days, today, city, extra)}</script>
</head>
<body>
<div class="wrap">
<header><div class="bar" data-nosnippet><a class="logo" href="/?lang={lang}">Leffavuoro<span>.</span></a>{lang_switch(lang, paths, t)}<button id="themeToggle" type="button" title="{esc(t['theme'])}" aria-label="{esc(t['a_theme'])}">\u25d0</button></div></header>
<main>
<h1>{esc(h1)}</h1>
<p class="sub">{sub_html(sub)}</p>
<p class="intro"><span data-nosnippet>{esc(intro)}</span></p>
{cta}
{legend}
{''.join(body)}
{also}
</main>
<footer><div data-nosnippet>{esc(t['sources'])}</div><div class="statuslink" data-nosnippet><a href="/status/?area={urllib.parse.quote(area)}&amp;lang={lang}">{esc(t['status_link'])}</a></div></footer>
</div>
<script>{THEME_BODY_JS}</script>
{pageview_tag(kind)}
</body>
</html>
"""


# ---------------------------------------------------------------- main

# Venue slugs that were public before a naming fix, and the venue id each now belongs to.
#
# A slug is built from the chain label and the city, so correcting a label moves the URL.
# Studio 123's two venues rendered their name twice ("Studio 123 Kouvola Studio 123")
# until 2026-08-30, and the fix silently retired four indexed paths -- bookmarks, links
# and anything Google had already crawled would 404. The pages are regenerated as
# redirects instead of being deleted.
#
# Deliberately a fixed table rather than a general aliasing framework: one entry per moved
# venue, and a mechanism that rewrites URLs on every label edit would make it easy to keep
# moving them. Add here only when a live URL has changed. Elokuvateatteri Elo and Julia 1&2
# printed their names twice the same way until 2026-10-04 ("Julia 1&2 Julia").
LEGACY_VENUE_SLUGS = {
    "studio-123-jarvenpaa-studio-123-jarvenpaa": "s3-jarvenpaa",
    "studio-123-kouvola-studio-123-kouvola": "s3-kouvola",
    "elokuvateatteri-elo-elo-heinola": "tmb-elo",
    "julia-1-2-julia-hyvinkaa": "julia-hyvinkaa",
}


def redirect_page(lang, to_path, label):
    """A minimal page that sends a reader to the URL this one became.

    Not a copy of the venue page: duplicating the content under both URLs is what
    `canonical` exists to prevent, and the schedule would then age in two places. The
    meta refresh moves a browser, the canonical and `noindex` tell a crawler which URL is
    real, and the anchor is what someone lands on if neither runs. `follow` rather than
    `nofollow`, so the link is what carries the old URL's standing to the new one.

    Nothing volatile in it, so `write_if_changed` keeps returning "kept" and these four
    files stop appearing in diffs.
    """
    t = {"fi": "Sivu on siirtynyt", "sv": "Sidan har flyttat",
         "en": "This page has moved"}[lang]
    go = {"fi": "Siirry teatterin sivulle", "sv": "G\u00e5 till biografens sida",
          "en": "Go to the cinema's page"}[lang]
    return (f'<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{esc(t)}: {esc(label)}</title>\n'
            f'<link rel="canonical" href="{SITE}{to_path}">\n'
            f'<meta name="robots" content="noindex,follow">\n'
            f'<meta http-equiv="refresh" content="0;url={to_path}">\n'
            f'</head>\n<body>\n'
            f'<h1>{esc(t)}</h1>\n'
            f'<p><a href="{to_path}">{esc(go)}: {esc(label)}</a></p>\n'
            f'</body>\n</html>\n')


# The four prefixes this generator owns outright. Nothing else under ROOT is ever
# removed, and these are removed only after the whole set has been written.
PAGE_ROOTS = ("teatteri", "kaupunki", "sv/teatteri", "sv/kaupunki",
              "en/theatre", "en/city")
# A build that suddenly owns far fewer pages is a broken input, not a removal: a
# `venues-*.json` that failed to parse, a providers.json truncated mid-write. Removing a
# provider is one entry and a handful of directories, so a prune this large is refused
# and named instead of performed.
PRUNE_CEILING = 0.25


def prune_obsolete(staged, stats):
    """Name the generator-owned page directories this build no longer produces. -> [name].

    **Report only. Nothing is deleted.** Removing them would make indexed URLs answer 404,
    and this file already has redirect machinery for a page that moved
    (`LEGACY_VENUE_SLUGS`, `redirect_page`) which a removal should route through instead.
    What that costs a search engine is the kind of change the SEO record says to measure
    before making, so the deletion waits on the maintainer and on a redirect destination
    for each case: a venue page whose provider is gone has none obvious, and a city page
    that fell to one venue has the surviving venue.

    `data/venues-{id}.json` for a provider the registry has dropped is skipped by
    `load_venues`, which stops its pages being rebuilt; without this they stayed published
    for ever, so the documented "remove one registry entry" left orphan venue and city
    pages serving a cinema this app no longer lists. A city falling from two venues to one
    loses its combined page the same way.

    Run after the flush, never before: "not in the staged set" means "obsolete" only once
    every page that *is* in the set has been written. The legacy redirect stubs are staged
    like any other page while their venue exists, so they never appear here.
    """
    keep = {Path(path).resolve() for path, _ in staged}
    owned, gone = [], []
    for prefix in PAGE_ROOTS:
        base = ROOT / prefix
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            idx = d / "index.html"
            if not d.is_dir() or not idx.is_file():
                continue
            owned.append(d)
            if idx.resolve() not in keep:
                gone.append((f"{prefix}/{d.name}", d, idx))
    if not gone:
        return []
    names = [n for n, _, _ in gone]
    if owned and len(gone) / len(owned) > PRUNE_CEILING:
        print(f"[pages] {len(gone)} of {len(owned)} page directories are not in this "
              f"build, which is too many to be a removal; reporting nothing. Check "
              f"data/providers.json and the venue files.", file=sys.stderr)
        return []
    stats["obsolete"] = len(gone)
    print(f"[pages] {len(gone)} page directory(ies) no longer built and still published: "
          + ", ".join(names) + ". Not removed: a redirect has to be decided for each")
    return names


def write_if_changed(path, text, stats):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        stats["kept"] += 1
        return
    common.write_text_atomic(path, text)
    stats["written"] += 1


def recorded_date():
    """The day the committed pages were built for, read back from sitemap.xml.

    Every URL's `lastmod` is written from `today`, so the sitemap already records the
    date the rest of the generation used and no second file has to carry it. A tree with
    no sitemap has nothing to reproduce, and this says so rather than guessing a day.
    """
    sm = ROOT / "sitemap.xml"
    m = (re.search(r"<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>", sm.read_text(encoding="utf-8"))
         if sm.exists() else None)
    if not m:
        raise SystemExit("[pages] no recorded build date: sitemap.xml is missing or carries "
                         "no <lastmod>")
    return date.fromisoformat(m.group(1))


def main(today=None) -> int:
    """Build every page for `today`; the current Helsinki date unless one is given.

    The pages are a function of the data *and* of the day: each lists a window of days
    starting at `today`, and the sitemap stamps it. Publishing wants the clock.
    Reproducing a committed build -- the CI check regenerates and requires a clean tree --
    wants the day that build was for, or the same input goes red after midnight with
    nothing changed: on 2026-09-05 against -06 it was 173 of 183 files. See recorded_date().

    -> 0, or 3 when the homepage's city links are stale. The pages, the sitemap and the
    run's data are written either way; only the verdict changes. A city crossing into its
    second venue creates a city page that `index.html` does not list, and the print saying
    so is read by nobody: `check_runs.py` reads `exit=`, and the data commit that moves
    the city touches none of the paths that start Checks. 3 puts it in `exit=`.
    """
    providers = {p["id"]: p for p in
                 json.loads((DATA / "providers.json").read_text())["providers"]}
    chains = {k: v.get("label", k) for k, v in providers.items()}
    gmap = json.loads((DATA / "tmdb-genres.json").read_text())
    extra = json.loads((DATA / "films-extra.json").read_text()).get("films", {})
    native = native_synopses()
    if today is None:
        today = datetime.now(FI).date()

    venues = load_venues()
    names_sv = city_sv()
    for v in venues:
        v["city"] = city_of(v)
        v["label"] = label_of(v, chains)
        v["slug"] = slug(f"{v['label']} {v['city']}")

    seen = {}
    for v in venues:                     # a collision would silently drop a venue's page
        if v["slug"] in seen:
            v["slug"] = f"{v['slug']}-{slug(v['id'])}"
        seen[v["slug"]] = v["id"]

    by_city = {}
    for v in venues:
        by_city.setdefault(v["city"], []).append(v)
    multi = {c: vs for c, vs in by_city.items() if len(vs) > 1}

    stats = {"written": 0, "kept": 0}
    # (path, text) for every page this run produces. Nothing reaches the tree until the
    # whole set is built -- see the flush at the bottom of this function.
    pages = []
    urls = []

    def stage(path, text):
        pages.append((path, text))

    # {lang: path} for one venue or one city. Finnish sits at the root and the other two
    # under their language, which is the pair already published for fi and en and the pair
    # the Swedish entry in the archive named.
    def paths_venue(v):
        return {"fi": f"/teatteri/{v['slug']}/", "sv": f"/sv/teatteri/{v['slug']}/",
                "en": f"/en/theatre/{v['slug']}/"}

    def paths_city(c):
        t = slug(c)
        return {"fi": f"/kaupunki/{t}/", "sv": f"/sv/kaupunki/{t}/",
                "en": f"/en/city/{t}/"}

    # ---- venue pages
    for v in venues:
        shows = load_shows(v["id"])
        days = group_by_day(shows, today)
        next_day = next_show_day(shows, today, DAYS) if not days else ""
        paths = paths_venue(v)
        first_poster = next((s["img"] for iso in sorted(days)
                             for sh in days[iso].values() for s in sh
                             if (s.get("img") or "").startswith("data/posters/")), None)
        og = f"/{first_poster}" if first_poster else "/icon-512.png"
        prov = providers.get(v["provider"], {})
        for lang in LANGS:
            t = L[lang]
            shown = city_name(v["city"], lang, names_sv)
            also = ""
            if v["city"] in multi:
                cp = paths_city(v["city"])[lang]
                also = (f'<nav class="also"><ul><li><a class="vchip" href="{esc(cp)}">'
                        f'{esc(t["city_link"].format(city=shown))}</a></li></ul></nav>')
            text = page(
                lang=lang, paths=paths,
                title=t["venue_title"].format(venue=v["label"], city=shown),
                desc=venue_desc(t, v["label"], shown, prov.get("book")),
                h1=t["venue_h1"].format(venue=v["label"]),
                sub=(shown, prov.get("host", "")),
                intro=" ".join(x for x in (
                    venue_intro(t, prov.get("book"), prov.get("host", "")),
                    age_note(t, [s for d in days.values() for sh in d.values() for s in sh]))
                    if x),
                days=days, today=today, t=t, extra=extra, gmap=gmap, city=v["city"], native=native,
                with_venue=False, legend="", also=also, og_image=og,
                next_day=next_day, stale=not days and unchecked(v.get("fetched"), today),
                # Deep link, so a reader arriving from search opens on this venue in this
                # language instead of whatever the app last had selected. Both halves are
                # decided by startupArea()/startupLang() in index.html.
                app_href="/?area=" + urllib.parse.quote(v["id"]) + "&lang=" + lang,
                area=v["id"], chain_css="", kind="theatre")
            stage(ROOT / paths[lang].strip("/") / "index.html", text)
        urls += [paths[c] for c in LANGS]

    # ---- redirects for venue URLs that were public under an older slug. Written after
    # the venue pages so the destination exists, and deliberately not added to `urls`:
    # the sitemap advertises canonical URLs only.
    by_id = {v["id"]: v for v in venues}
    for old_slug, vid in LEGACY_VENUE_SLUGS.items():
        v = by_id.get(vid)
        if v is None or v["slug"] == old_slug:
            continue          # venue gone, or the slug is current again -- nothing to do
        for lang, prefix in (("fi", "teatteri"), ("sv", "sv/teatteri"),
                             ("en", "en/theatre")):
            out = ROOT / prefix / old_slug / "index.html"
            stage(out, redirect_page(lang, paths_venue(v)[lang], v["label"]))

    # ---- city pages, only where the app offers a combined view
    for c, vs in multi.items():
        merged = []
        for v in vs:
            for s in load_shows(v["id"]):
                # The chain-prefixed label, not the bare short: "Tripla" and "Kamppi" are
                # shopping centres and "Kallio" a district. Same rule as the app's
                # combined view.
                merged.append({**s, "venueLabel": v["label"], "venueProvider": v["provider"]})
        days = group_by_day(merged, today, CITY_DAYS, merge=True)
        next_day = next_show_day(merged, today, CITY_DAYS) if not days else ""
        paths = paths_city(c)
        first_poster = next((s["img"] for iso in sorted(days)
                             for sh in days[iso].values() for s in sh
                             if (s.get("img") or "").startswith("data/posters/")), None)
        og = f"/{first_poster}" if first_poster else "/icon-512.png"
        # One 3 px rule per chain on the stubs and on the venue links, and a legend that
        # names each colour. Never colour alone: every stub also names its cinema.
        chain_ids = sorted({v["provider"] for v in vs}, key=lambda k: chains.get(k, k))
        chain_css = "".join(f".chain-{esc(k)}{{--chain:{esc(providers[k]['accent'])}}}"
                            for k in chain_ids if providers.get(k, {}).get("accent"))
        legend = ('<p class="legend">' + "".join(
            f'<span class="lg chain-{esc(k)}">{esc(chains.get(k, k))}</span>' for k in chain_ids)
            + "</p>")
        for lang in LANGS:
            t = L[lang]
            chips = "".join(
                f'<li><a class="vchip chain-{esc(v["provider"])}" '
                f'href="{esc(paths_venue(v)[lang])}">{esc(v["label"])}</a></li>'
                for v in sorted(vs, key=lambda x: x["label"]))
            shown = city_name(c, lang, names_sv)
            also = (f'<nav class="also"><h2>{esc(t["venues_h"].format(city=shown))}</h2>'
                    f"<ul>{chips}</ul></nav>")
            text = page(
                lang=lang, paths=paths,
                title=t["city_title"].format(city=shown),
                desc=city_desc(t, shown),
                h1=t["city_h1"].format(city=shown),
                sub=t["city_sub"].format(n=len(vs)),
                intro=t["city_intro"].format(n=len(vs)),
                days=days, today=today, t=t, extra=extra, gmap=gmap, city=c, native=native,
                with_venue=True, legend=legend, also=also, og_image=og,
                next_day=next_day,
                stale=not days and any(unchecked(v.get("fetched"), today) for v in vs),
                app_href="/?area=" + urllib.parse.quote("city:" + c) + "&lang=" + lang,
                area="city:" + c, chain_css=chain_css, kind="city")
            stage(ROOT / paths[lang].strip("/") / "index.html", text)
        urls += [paths[c] for c in LANGS]

    # ---- sitemap
    lastmod = today.isoformat()
    entries = "\n".join(
        f"  <url><loc>{SITE}{u}</loc><lastmod>{lastmod}</lastmod></url>"
        for u in ["/"] + sorted(urls))
    sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f"{entries}\n</urlset>\n")
    stage(ROOT / "sitemap.xml", sm)

    # Everything above only decided what the pages say. This is where they land.
    #
    # The build used to write each page as it produced it, so an exception partway
    # through left the tree holding some of this run's pages and some of the last run's
    # -- and the cloud workflow stages `teatteri kaupunki en sitemap.xml` and pushes
    # before it checks whether the build exited non-zero, so the mixture was published
    # and only then did the run turn red. Measured against real data by raising on the
    # 41st write: 40 of 172 pages new, 132 from the previous build, all committed.
    #
    # The mixture is worse than a partial update sounds. A city page is built from the
    # venues it merges and after them, and the sitemap after both, so a half-built run
    # can serve a city page whose showtimes disagree with the venue pages it links to,
    # under a sitemap describing neither. Nothing on the page says it is inconsistent.
    #
    # Holding the whole set costs 4.5 MB across 173 files, measured, in a process that
    # already has every showtime in memory. The loop does no work that can raise on its
    # own -- it compares and writes -- so a build that fails now writes nothing at all.
    # The previous complete page set stays exactly where it was, and because the failed
    # build stages no page changes, the run's fresh schedule data still publishes.
    for path, text in pages:
        write_if_changed(path, text, stats)
    prune_obsolete(pages, stats)

    print(f"[pages] {len(venues)} venues, {len(multi)} multi-venue cities "
          f"({', '.join(sorted(multi))})")
    stale_home = sync_home(write=False, venues=venues)
    if stale_home:
        print("[pages] index.html city links stale: run build_pages.py --home")
    if _unmirrored_hosts:
        total = sum(_unmirrored_hosts.values())
        where = ", ".join(f"{h} x{n}" for h, n in sorted(_unmirrored_hosts.items()))
        print(f"[pages] WARNING: {total} poster references were still remote and were "
              f"dropped from the markup, so those films render a placeholder tile: "
              f"{where}. mirror_posters should have rewritten these; check whether the "
              f"cloud run before this one completed.")

    print(f"[pages] {len(urls) + 1} urls in sitemap, "
          f"{stats['written']} files written, {stats['kept']} unchanged")
    # Last, so the summary still reaches the log. biorex.yml commits the pages and the
    # data before it reads this, and fails the run at its final step; the stale list is
    # then a red run with the reason in the committed run-pages.log, not a line in a log
    # nobody opens. `--home` fixes it and is a human commit, because index.html carries a
    # service-worker bump.
    return 3 if stale_home else 0


# ---------------------------------------------------------------- the homepage's city links
# index.html opens on a chooser when neither the URL nor a stored favourite names a
# location, and the chooser lists the city landing pages this script builds. The list is
# markup in index.html, between these markers, so it is there without JavaScript and
# before any data loads; it is generated from the same multi-venue rule as the pages, so
# a link can only point at a page that exists. `--home` rewrites the block; main() only
# reports when it is stale, because a change to index.html carries a service-worker bump
# and is a human commit, and the cloud workflow stages the pages alone.
HOME_START = "<!-- cities:start -->"
HOME_END = "<!-- cities:end -->"
# The same links again under the chooser's "Kaupunkisivut" disclosure. The app points the
# first list at the programme, so this copy is the homepage's rendered link into the city
# pages (2026-09-29): without it a rendered crawl from `/` reached none of them.
PAGES_START = "<!-- citypages:start -->"
PAGES_END = "<!-- citypages:end -->"
HOME_BLOCKS = ((HOME_START, HOME_END), (PAGES_START, PAGES_END))
INDEX = ROOT / "index.html"


def home_cities(venues=None):
    """The cities with a landing page, Finnish order. -> [{"city", "slug"}]"""
    venues = load_venues() if venues is None else venues
    by_city = {}
    for v in venues:
        by_city.setdefault(city_of(v), []).append(v)
    multi = [c for c, vs in by_city.items() if len(vs) > 1]
    return [{"city": c, "slug": slug(c)} for c in sorted(multi, key=str.casefold)]


def home_links_html(cities):
    """One <li> per city. The Finnish page is the static href; `data-city` and
    `data-slug` let the client relabel and relink the list for sv and en, and point the
    first list at the programme."""
    return "".join(f'\n<li><a href="/kaupunki/{c["slug"]}/" data-city="{esc(c["city"])}" '
                   f'data-slug="{c["slug"]}">{esc(c["city"])}</a></li>' for c in cities) + "\n"


def home_block(html, links=None, start=HOME_START, end=HOME_END):
    """index.html with the marked block replaced by `links`; the current block when
    `links` is None. -> (text, current block) or raises when the markers are missing."""
    a, b = html.index(start) + len(start), html.index(end)
    current = html[a:b]
    if links is None:
        return html, current
    return html[:a] + links + html[b:], current


def sync_home(write, venues=None):
    """Compare index.html's city links with the data; rewrite them when `write`.
    -> True when they differed.

    `venues` is the list the caller already holds. main() checks the links at the end of a
    build with every venue in memory, and reloading them there read 56 files a second time:
    `data/areas.json` and 55 `venues-*.json` on 2026-09-17. The cities come out the same,
    because `city_of` returns `v["city"]` once that key is set and main sets it to
    `city_of(v)`. `--home` runs on its own with nothing loaded, so it passes none and the
    files are read."""
    new = INDEX.read_text(encoding="utf-8")
    links = home_links_html(home_cities(venues))
    stale = False
    for start, end in HOME_BLOCKS:
        new, current = home_block(new, links, start, end)
        stale = stale or current != links
    if stale and write:
        common.write_text_atomic(INDEX, new)
    return stale


def cli(argv):
    ap = argparse.ArgumentParser(
        description="Render the indexable venue and city pages from data/.")
    ap.add_argument("--date", metavar="YYYY-MM-DD|recorded",
                    help="the day to build for: an ISO date, or `recorded` for the day the "
                         "committed sitemap.xml carries, which is how CI reproduces the "
                         "committed pages. Default: today in Europe/Helsinki.")
    ap.add_argument("--home", action="store_true",
                    help="rewrite the homepage's city links in index.html from the data "
                         "and exit 0; bump sw.js when committing the result. Without it a "
                         "build whose links are stale writes every page and exits 3")
    args = ap.parse_args(argv)
    if args.home:
        changed = sync_home(write=True)
        print(f"[pages] index.html city links {'rewritten' if changed else 'unchanged'}")
        return 0
    if args.date is None:
        today = None
    elif args.date == "recorded":
        today = recorded_date()
    else:
        try:
            today = date.fromisoformat(args.date)
        except ValueError:
            ap.error(f"--date: not an ISO date or `recorded`: {args.date!r}")
    return main(today=today)


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
