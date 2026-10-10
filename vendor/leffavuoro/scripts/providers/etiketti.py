"""eTiketti platform adapter (etiketti.app powers several Finnish cinema sites).

The etiketti.app API host sits behind Cloudflare, but the cinema's own site is
server-rendered and fetchable, so this parses the public pages:

  /elokuvat/ohjelmistossa   -> movie links  /elokuvat/{id}/{slug}
  /elokuvat/{id}/{slug}     -> every screening for that film, with room, price,
                               free seats and a booking link

Two screening templates render those pages. Kotka's (nineteen of the twenty hosts) prints
"KE 2.9. klo 20.00", "TRIO 123 | SALI 2", "Lippu 15,00€" and "Vapaat paikat 27/35";
Cinema Niagara's (2026-09-02) prints the time in a `time` div, the price in `show-price`,
"Paikkoja vapaana: 126/127", per-screening tags in `movie-specs`, no place line, and its
detail labels carry no colon. Every regex below accepts exactly those two shapes. The
listing, the film links and the `/salikartta?id=` ticket href are the same on both, and
the ticket page is never fetched: it is the outbound link and nothing more.

Adding another eTiketti cinema = an entry in SITES.

Empty venues (2026-09-13). A site's film pages carry every screening, so a registered
venue with no row is either out of programme or renamed. `EMPTY_VENUES_CONFIRMED` lets
run.py publish a fresh empty file for such a venue instead of keeping its last, past
shows marked stale, but only on positive evidence from this read: the listing's own
theatre navigation (`/teatterit/<slug>` links, which 6 of the 20 hosts render) names the
venue with anchor text carrying its registered `match`, every film page was fetched and
produced at least one row, and every screening row matched a registered venue. A fetch
that skipped a page, a page that produced no row (no block found, or every block without a
readable time), a row naming a place nobody registered, or a venue the navigation does not
list leaves the venue out of the result, and run.py keeps the previous file. Cine Nikkilä's
programme ended on 2026-09-13 and the provider read "not updated" for its past shows.
"""
import re
import datetime, html as html_mod, json, re, time
from zoneinfo import ZoneInfo

from common import EmptyProgramme, budget_or_raise, fetch, syn_language
from synmerge import is_note

FI = ZoneInfo("Europe/Helsinki")
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"

# See "Empty venues" in the module docstring: a venue returned with an empty list is
# known empty, and fetch_site returns one only on that evidence.
EMPTY_VENUES_CONFIRMED = True
# The theatre navigation, on the sites that render one: the venue's own page link with the
# venue's name as the text. Not every site. Measured 2026-09-14, one listing read per host:
# 6 of the 20 carry `/teatterit/` anchors at all, and on those six the anchors name all 10
# of their registered venues. The other 19 venues cannot be confirmed empty, which is the
# safe side of this. Anchors only, never prose: "Esitysjaksot Keravalla ja Nikkilässä"
# names the town without identifying the venue. Any attributes on the anchor, because one
# that gains a class would otherwise stop identifying anything with no other symptom;
# no host carried one on 2026-09-14, so this buys nothing today and costs nothing either.
VENUE_LINK_RE = re.compile(r'<a[^>]*href="/teatterit/[^"]+"[^>]*>([^<]*)</a>', re.I)

SITES = [
    {"provider": "kotkanleffat", "base": "https://kotkanleffat.fi", "label": "Kotkan Leffat",
     "venues": [
         {"id": "kl-kinopalatsi", "match": "kinopalatsi", "name": "Kinopalatsi Kotka",
          "short": "Kinopalatsi", "city": "Kotka"},
         {"id": "kl-trio123", "match": "trio 123", "name": "Trio 123",
          "short": "Trio 123", "city": "Kotka"},
     ]},
    # One cinema, three rooms (DIGI 1, DIGI 2, SALI 3), all reported under the single
    # place name "BIO 1&2 REX". A room is not a venue, so this is one entry and the
    # room lands in `aud` verbatim, the way it is printed on the ticket.
    {"provider": "biorexkokkola", "base": "https://www.biorex.org", "label": "Bio Rex Kokkola",
     "venues": [
         {"id": "bx-kokkola", "match": "rex", "name": "Bio Rex Kokkola",
          "short": "Bio Rex Kokkola", "city": "Kokkola"},
     ]},
    # Savon Kinot moved here from Vista on or before 2026-08-30: its /xml/ services now
    # 404 from every network and the site serves this listing instead. The venue ids are
    # the ones vista.py used, deliberately -- they key the saved home cinema in
    # localStorage and every /teatteri/ URL, so renaming them would wipe both.
    # Like Leffabuumi, this deployment prints the *town* as the place and the cinema in
    # the room field ("JOENSUU | TAPIO | TAPIO 3"); `match` runs against the two joined.
    # Rooms arrive as `VENUE | VENUE n`, the venue repeated inside its own room name.
    # The flag turns on normalise_aud here and on Cine below; the other eighteen
    # keep the room verbatim, and Leffabuumi's pipe means something else entirely.
    {"provider": "savonkinot", "base": "https://www.savonkinot.fi", "label": "Savon Kinot",
     "aud_repeats_venue": True,
     "venues": [
         {"id": "sk-tapio", "match": "tapio", "name": "Tapio Joensuu",
          "short": "Tapio", "city": "Joensuu"},
         {"id": "sk-killa", "match": "killa", "name": "Killa Savonlinna",
          "short": "Killa", "city": "Savonlinna"},
         {"id": "sk-kuvalinna", "match": "kuvalinna", "name": "Kuvalinna Savonlinna",
          "short": "Kuvalinna", "city": "Savonlinna"},
         {"id": "sk-kuvalipas", "match": "kuvalipas", "name": "Kuvalipas Iisalmi",
          "short": "Kuvalipas", "city": "Iisalmi"},
         {"id": "sk-maxim", "match": "maxim", "name": "Maxim Varkaus",
          "short": "Maxim", "city": "Varkaus"},
         {"id": "sk-kinohovi", "match": "kino-hovi", "name": "Kino-Hovi Kitee",
          "short": "Kino-Hovi", "city": "Kitee"},
     ]},
    # The 2026-08-30 sweep. Fourteen more hosts serving this same listing, verified
    # against it rather than against the etiketti.app signature in their HTML. Most are
    # one cinema on one host, so `match` is the place name the screening block prints.
    {"provider": "kinopirtti", "base": "https://kinopirtti.fi", "label": "Kinopirtti",
     "venues": [
         {"id": "kp-kemi", "match": "kinopirtti", "name": "Kinopirtti",
          "short": "Kinopirtti", "city": "Kemi"},
     ]},
    # The one host here that is three cinemas in two towns, and the one that prints the
    # *town* as the place and the cinema as the room ("MIKKELI | KINOLINNA | SALI 2").
    # `match` runs against place and room joined, so the cinema name still selects.
    {"provider": "leffabuumi", "base": "https://leffabuumi.fi", "label": "Leffabuumi",
     "venues": [
         {"id": "lb-kinolinna", "match": "kinolinna", "name": "Kinolinna",
          "short": "Kinolinna", "city": "Mikkeli"},
         {"id": "lb-ritz", "match": "ritz", "name": "Kino Ritz",
          "short": "Kino Ritz", "city": "Mikkeli"},
         {"id": "lb-saimaa", "match": "kino saimaa", "name": "Kino Saimaa",
          "short": "Kino Saimaa", "city": "Puumala"},
     ]},
    # Two unrelated hosts both print the place name "STUDIO 123", in different towns.
    # The label spells the town out for the same reason Bio Rex Kokkola does -- and, like
    # that entry, `short` repeats the label rather than shortening to "Studio 123". Both
    # the client and build_pages drop the chain prefix only when the venue's short name
    # already starts with it, so a short that is a *prefix* of the chain renders as
    # "Studio 123 Järvenpää Studio 123" in the picker and slugs the same way.
    {"provider": "studio123jarvenpaa", "base": "https://studiot123.com",
     "label": "Studio 123 Järvenpää",
     "venues": [
         {"id": "s3-jarvenpaa", "match": "studio 123", "name": "Studio 123 Järvenpää",
          "short": "Studio 123 Järvenpää", "city": "Järvenpää"},
     ]},
    {"provider": "studio123kouvola", "base": "https://studio123.fi",
     "label": "Studio 123 Kouvola",
     "venues": [
         {"id": "s3-kouvola", "match": "studio 123", "name": "Studio 123 Kouvola",
          "short": "Studio 123 Kouvola", "city": "Kouvola"},
     ]},
    {"provider": "ihmekompleksi", "base": "https://ihmekompleksi.fi", "label": "Ihme Kompleksi",
     "venues": [
         {"id": "ik-kankaanpaa", "match": "ihme kompleksi", "name": "Ihme Kompleksi",
          "short": "Ihme Kompleksi", "city": "Kankaanpää"},
     ]},
    {"provider": "kino123", "base": "https://kino123.fi", "label": "Kino 123",
     "venues": [
         {"id": "k3-kouvola", "match": "kino 123", "name": "Kino 123",
          "short": "Kino 123", "city": "Kouvola"},
     ]},
    {"provider": "kinotar", "base": "https://jamsankinotar.fi", "label": "Kinotar 123",
     "venues": [
         {"id": "kt-jamsa", "match": "kinotar", "name": "Kinotar 123",
          "short": "Kinotar 123", "city": "Jämsä"},
     ]},
    # Two screening spaces at two addresses in Nurmijärvi, published on one listing and
    # distinguished only by the place line: "KINO JUHA" is Keskustie 7 and "VIP-SALI" is
    # Pratikankuja 3. Read from the two salikartta pages as a visitor on 2026-09-14, which
    # print the address under the place; the site's own footer names Kino Juha on both, and
    # it runs Taaborin kesäteatteri besides. VIP-Sali was unregistered until then, so its
    # 6 of the site's 13 screenings were dropped as an unclaimed place on every run.
    {"provider": "kinojuha", "base": "https://kinojuha.fi", "label": "Kino Juha",
     "venues": [
         {"id": "kj-nurmijarvi", "match": "kino juha", "name": "Kino Juha",
          "short": "Kino Juha", "city": "Nurmijärvi"},
         {"id": "kj-vipsali", "match": "vip-sali", "name": "VIP-Sali",
          "short": "VIP-Sali", "city": "Nurmijärvi"},
     ]},
    # The site says Tikkurila throughout and never Vantaa; Vantaa is the postal town on
    # the address the industry directory lists, and is what a visitor searches for.
    {"provider": "biogrand", "base": "https://biogrand.fi", "label": "Bio Grand",
     "venues": [
         {"id": "bg-vantaa", "match": "bio grand", "name": "Bio Grand",
          "short": "Bio Grand", "city": "Vantaa"},
     ]},
    {"provider": "biovuoksi", "base": "https://biovuoksi.fi", "label": "Bio Vuoksi",
     "venues": [
         {"id": "bv-imatra", "match": "bio vuoksi", "name": "Bio Vuoksi",
          "short": "Bio Vuoksi", "city": "Imatra"},
     ]},
    {"provider": "kinoiiris", "base": "https://kinoiiris.com", "label": "Kino Iiris",
     "venues": [
         {"id": "ki-lahti", "match": "kino iiris", "name": "Kino Iiris",
          "short": "Kino Iiris", "city": "Lahti"},
     ]},
    # Fetched from the local half: kino.joutsa.fi answers a runner with a Cloudflare 403
    # and an ordinary connection fine. `where="local"` on its registry entry is what
    # routes it; run.py filters SITES by half, so the other sixteen stay cloud-side.
    {"provider": "joutsankino", "base": "https://kino.joutsa.fi", "label": "Joutsan Kino",
     "venues": [
         {"id": "jk-joutsa", "match": "joutsan kino", "name": "Joutsan Kino",
          "short": "Joutsan Kino", "city": "Joutsa"},
     ]},
    {"provider": "kkino", "base": "https://k-kino.fi", "label": "K-Kino",
     "venues": [
         {"id": "kk-kangasala", "match": "k-kino", "name": "K-Kino",
          "short": "K-Kino", "city": "Kangasala"},
     ]},
    {"provider": "biograni", "base": "https://biograni.fi", "label": "Bio Grani",
     "venues": [
         {"id": "bn-kauniainen", "match": "bio grani", "name": "Bio Grani",
          "short": "Bio Grani", "city": "Kauniainen"},
     ]},
    # kiertue.cine.fi publishes the two cinemas below. Cine Mäntsälä runs a separate
    # MyCloudCinema deployment and the touring page lists no stops, so neither is here.
    # The second field of each place line repeats the cinema name, so `aud` goes through
    # normalise_aud and comes out empty.
    {"provider": "cine", "base": "https://kiertue.cine.fi", "label": "Cine",
     "aud_repeats_venue": True,
     "venues": [
         {"id": "cine-keuda", "match": "cine keuda-talo", "name": "Cine Keuda-Talo",
          "short": "Cine Keuda-Talo", "city": "Kerava"},
         {"id": "cine-nikkila", "match": "cine nikkilä", "name": "Cine Nikkilä",
          "short": "Cine Nikkilä", "city": "Sipoo"},
     ]},
    # Cinema Niagara, Tampere (2026-09-02): the host the sweep left behind, because its
    # screenings render in the second template. It prints no place line at all, so
    # `match` runs against the item's place class -- "tampere" -- which is what the
    # fallback in parse_movie exists for. arthousecinemaniagara.fi redirects here.
    {"provider": "niagara", "base": "https://cinemaniagara.fi", "label": "Cinema Niagara",
     "venues": [
         {"id": "cn-tampere", "match": "tampere", "name": "Cinema Niagara",
          "short": "Cinema Niagara", "city": "Tampere"},
     ]},
    # Elokuvateatteri Star, Oulu (2026-09-07). The public site is
    # elokuvateatteristar.fi, which the footer credits; the programme and every
    # /salikartta link are on lippu., which is what `base` reads and run.py paces on.
    # Five rooms, SALI 1 to SALI 5, so no `aud_repeats_venue`.
    {"provider": "star", "base": "https://lippu.elokuvateatteristar.fi",
     "label": "Elokuvateatteri Star",
     "venues": [
         {"id": "star-oulu", "match": "star", "name": "Elokuvateatteri Star",
          "short": "Elokuvateatteri Star", "city": "Oulu"},
     ]},
    # Moved from Johku 2026-09-29: the site now serves this listing, Kotka's template with
    # the place line "HAAPAMÄEN ELOKUVAT". Read that day, five screenings, each with a
    # price, a language, a runtime and a /salikartta ticket link. The venue id is Johku's.
    {"provider": "haapamaki", "base": "https://haapamaenelokuvat.fi",
     "label": "Haapamäen Elokuvat",
     "venues": [
         {"id": "haapamaki-haapamaki", "match": "haapamäen elokuvat",
          "name": "Haapamäen Elokuvat", "short": "Haapamäen Elokuvat", "city": "Haapamäki"},
     ]},
]

MOVIE_LINK_RE = re.compile(r'href="(/elokuvat/(\d+)/[a-z0-9-]+)"')
# Three signals used only to tell "this cinema has nothing on" from "this parser stopped
# reading a listing that still has films on it". They are deliberately independent of
# MOVIE_LINK_RE: a slug that gains an uppercase letter, an underscore, a Scandinavian
# character or a second attribute inside the href makes that regex match nothing while
# the page is still full of films, and zero matches must never be read as an empty
# programme on its own.
#   - the film container, which says the expected template rendered at all
#   - the per-film cards inside it, parsed without touching the href
#   - the server-rendered empty state the template prints *instead of* the cards
# Measured across five live sites on 2026-08-31: four populated ones carry the container
# and the cards and never the phrase; the one genuinely empty cinema carries the
# container and the phrase and no cards; three hosts on a different template carry no
# container at all.
LISTING_CONTAINER_RE = re.compile(r'<div[^>]*class="[^"]*\bmovie-list\b[^"]*"[^>]*>')
LISTING_ITEM_RE = re.compile(r'class="item[ "]')
LISTING_EMPTY_RE = re.compile(r"ohjelmistoa saatavilla", re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
# One screening. Kotka writes `<div class="item kotka date-2.9.2026">`; Niagara breaks the
# line after `<div` and, on its listing, appends a `name-` class after the date, so the
# tag is matched on whitespace and the class attribute is captured whole. The date and the
# place are read out of it afterwards. The block runs to the next item or to the template's
# three closing divs, as before.
ITEM_RE = re.compile(r'<div\s+class="(item [^"]*\bdate-\d{1,2}\.\d{1,2}\.\d{4}\b[^"]*)"(.*?)'
                     r'(?=<div\s+class="item |</div>\s*</div>\s*</div>|\Z)', re.S)
ITEM_DATE_RE = re.compile(r"\bdate-(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
# Kotka: "KE 2.9. klo 20.00". Niagara: <div class="time"><span>16.15</span>.
TIME_RE = re.compile(r'(?:klo\s*|class="time"[^>]*>\s*(?:<span[^>]*>\s*)?)(\d{1,2})[.:](\d{2})')
# Trio 123 screenings read "TRIO 123 | SALI 1"; Kinopalatsi has no room at all.
PLACE_RE = re.compile(r"<p>\s*([^<|]+?)\s*(?:\|\s*([^<]+?)\s*)?<br", re.S)
# Kotka: "Lippu 15,00€". Niagara: <div class="show-price"> 13,00€. Per screening on both;
# eleven of Niagara's films carried two or three different prices on 2026-09-02.
PRICE_RE = re.compile(r'(?:Lippu\s*|class="show-price"[^>]*>\s*)([\d,\.]+)')


def _price(raw):
    """"15,00" -> "15€", "12,50" -> "12.5€", "10" -> "10€".

    A trailing zero is only stripped from a decimal amount: "10" must not become "1".
    All 20 tenants printed two decimals on 2026-09-24 (22 amounts, 0,00 to 24,00), so the
    bare case had not fired.
    """
    v = raw.replace(",", ".")
    if "." in v:
        v = v.rstrip("0").rstrip(".")
    return v + "\u20ac"


# Kotka: "Vapaat paikat 27/35". Niagara: "Paikkoja vapaana: 126/127". Read only to derive
# soldOut; the counts themselves are not published (docs/archive/2026-09-pipeline.md,
# "Cinema Niagara, Tampere").
SEATS_RE = re.compile(r"(?:Vapaat paikat|Paikkoja vapaana):?\s*(\d+)\s*/\s*(\d+)")
BOOK_RE = re.compile(r'href="(/salikartta\?id=\d+)"')
# Niagara's per-screening labels: "Seniorikino", "Ensi-ilta", "Q&amp;A" ... Kotka has none.
TAG_RE = re.compile(r'<span class="tag"[^>]*>(.*?)</span>', re.S)
AGE_RE = re.compile(r"ikarajat/fi-(\d+|s)\.svg", re.I)
# Kotka: `Kesto:</span> 1 h 46 min`. Niagara: `Kesto </span> 1 h 48 min`, no colon.
DUR_RE = re.compile(r"Kesto:?\s*</span>\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*min)?", re.I)
LANGV_RE = re.compile(r"Kieli:?\s*</span>\s*([^<]+)", re.I)
SUBS_RE = re.compile(r"Tekstitys:?\s*</span>\s*([^<]+)", re.I)
POSTER_RE = re.compile(r'<img class="poster-img" src="([^"]+)"')
GENRES_RE = re.compile(r'<span class="movie-genre">([^<]+)</span>')
# Niagara lists its genres under a detail label that literally reads "genre".
GENRES2_RE = re.compile(r'<span class="label">\s*genre\s*</span>\s*([^<]+)', re.I)
DESC_RE = re.compile(r'class="description-container[^"]*"[^>]*>\s*<span>(.*?)</span>', re.S)
# The description opens with an age-limit boilerplate line; drop it. Only an age statement
# and its known follow-up: "Elokuva on K16. Ikärajoista voi joustaa ..." (Kotka, 2026-10-04),
# "Elokuva on sallittu yli 16-vuotiaille. Sisältää kauhua." Any two sentences after
# "Elokuva on" also took the opening of a synopsis that starts "Elokuva on saanut ...".
AGE_BOILER_RE = re.compile(r"^Elokuva on (?:K-?\d{1,2}|S|sallittu [^.]*)\.\s*"
                           r"(?:(?:Ikärajoista|Sisältää) [^.]*\.\s*)?", re.S)
# A description's paragraphs are separated by `<br />` runs on every host read 2026-09-28.
PARA_RE = re.compile(r"(?:\s*<br\s*/?>\s*)+", re.I)
TAGS_RE = re.compile(r"<[^>]+>")


def _txt(x):
    """Plain text. Tags go twice: Star's descriptions carry them escaped ("&lt;p&gt;",
    read 2026-10-04 on 9 film pages), which unescaping turns into markup in the text."""
    text = html_mod.unescape(TAGS_RE.sub(" ", x or ""))
    return re.sub(r"\s+", " ", TAGS_RE.sub(" ", text)).strip()


def get(url, tries=3):
    """Server-rendered HTML. common.fetch supplies the retry: same tries=3 and the
    same 5 s * n backoff and 30 s timeout this loop had, so behaviour is unchanged."""
    return fetch(url, headers={
        "user-agent": UA, "accept-language": "fi-FI,fi;q=0.9",
        "accept": "text/html,application/xhtml+xml"}, tries=tries,
        cache=True).decode("utf-8", "replace")


# Finnish language names -> ISO 639-1, the inverse of the client's `LN.fi`. The sites
# print names, not codes: "Suomi ja ruotsi", "englanti, espanja". Matched on the first
# four letters of a word so the inflected and abbreviated forms the templates use --
# "suomeksi", "ruots.", "englanniksi" -- resolve too. SV rather than SE: SE is Sweden the
# country, which this app used to store because Finnkino does.
LANG_NAMES = {
    "suomi": "FI", "englanti": "EN", "ruotsi": "SV", "espanja": "ES", "saksa": "DE",
    "ranska": "FR", "italia": "IT", "venäjä": "RU", "viro": "ET", "tanska": "DA",
    "norja": "NO", "islanti": "IS", "hollanti": "NL", "puola": "PL", "portugali": "PT",
    "ukraina": "UK", "arabia": "AR", "japani": "JA", "kiina": "ZH", "korea": "KO",
    "hindi": "HI", "turkki": "TR", "georgia": "KA", "tamili": "TA", "liettua": "LT",
    "malajalam": "ML", "persia": "FA", "heprea": "HE", "pa\u0161tu": "PS", "kreikka": "EL",
    "nepali": "NE", "romania": "RO", "jiddi\u0161": "YI",
}
LANG_WORD_RE = re.compile(r"[a-zåäö]+")


def lang_codes(v):
    """'Suomi ja ruotsi' -> ['FI', 'SV']; 'englanti, espanja' -> ['EN', 'ES'];
    'Alkuperäinen' -> []. Source order, no repeats."""
    out = []
    for word in LANG_WORD_RE.findall((v or "").lower()):
        for name, code in LANG_NAMES.items():
            if word.startswith(name[:4]) and code not in out:
                out.append(code)
                break
    return out


# The client's own English names (`LN.en` in index.html), for the pages that print one:
# Riviera's ticket page read "Kieli: Spanish" for Autofiktio on 2026-09-23.
# tests/test_riviera_language.py holds the two tables together.
EN_NAMES = {
    "finnish": "FI", "english": "EN", "swedish": "SV", "spanish": "ES", "german": "DE",
    "french": "FR", "italian": "IT", "russian": "RU", "estonian": "ET", "danish": "DA",
    "norwegian": "NO", "icelandic": "IS", "dutch": "NL", "polish": "PL",
    "portuguese": "PT", "ukrainian": "UK", "arabic": "AR", "japanese": "JA",
    "chinese": "ZH", "korean": "KO", "hindi": "HI", "turkish": "TR", "georgian": "KA",
    "tamil": "TA", "lithuanian": "LT", "malayalam": "ML", "persian": "FA", "hebrew": "HE",
    "pashto": "PS", "greek": "EL", "nepali": "NE", "romanian": "RO", "yiddish": "YI",
}
STRICT_SPLIT_RE = re.compile(r"\s*(?:,|/|\bja\b|\band\b)\s*", re.I)


def strict_codes(value):
    """A labelled language field -> its codes in order, or [] unless every word in it names
    a language. lang_codes finds any name in free text; this is for a field that is only
    names, where "Alkuperäinen", "dari" or anything no table knows makes the field say
    nothing reliable, so it says nothing rather than half of it. "-" and "" are []."""
    out = []
    for word in (w for w in STRICT_SPLIT_RE.split((value or "").strip()) if w and w != "-"):
        codes = lang_codes(word) if len(word.split()) == 1 else []
        code = codes[0] if len(codes) == 1 else EN_NAMES.get(word.lower())
        if not code:
            return []
        if code not in out:
            out.append(code)
    return out


# "Tekstitys: Ei tekstitystä" is the film page saying the screening has no subtitles:
# `XX-S`, as at Kino Engel. Read 2026-10-04 over 231 film pages it stood on Finnish films
# and dubs at sixteen sites, 139 screenings. Not read at two whose template shows it where
# it cannot hold: Niagara prints it on pages with no Kieli row (Black Magic Rites,
# Rakkautta ja virtahepoja), Star beside Italian audio (La Grazia) and beside Swedish and
# Russian dialogue (Punainen peto).
NO_SUBS_RE = re.compile(r"^ei\s+tekstityst\u00e4\.?$", re.I)
NO_SUBS_UNREAD = frozenset({"niagara", "star"})


def _lang(page, no_subs=True):
    """'Alkuperäinen' / 'Suomi ja ruotsi' -> Finnkino-style tags; "Ei tekstitystä" -> `XX-S`
    unless `no_subs` is False."""
    codes = lang_codes
    a = LANGV_RE.search(page)
    s = SUBS_RE.search(page)
    av = _txt(a.group(1)) if a else ""
    sv = _txt(s.group(1)) if s else ""
    parts = [f"{c}-A" for c in codes(av)]
    if not parts and "alkuper" in av.lower():
        parts = []                       # original version: audio language unstated
    if no_subs and NO_SUBS_RE.match(sv):
        return ", ".join(parts + ["XX-S"])
    parts += [f"{c}-S" for c in codes(sv)]
    return ", ".join(parts)


# Two eTiketti sites put the audio version in the film-page H1 as well as in the language
# rows: Bio Rex Kokkola sells "Kojootti vs. ACME" beside "Kojootti vs. ACME ENG", and
# Kinopirtti sells "Kojootti vs. ACME DUB" and "Kojootti vs. ACME SUB". The suffix is a
# label, not part of the film's name, and it cost those rows their TMDB match: the search
# string is the published title, and no query with a trailing ENG or SUB reaches the film
# (0 results, probed 2026-09-14; see docs/research/tmdb-matching.md).
#
# Stripped here rather than in the shared TMDB cleaner on purpose. `enrich_tmdb.clean()`
# would have to strip these words from every provider's titles, and ENG, SUB and DUB are
# ordinary words that can end a real title; here the adapter knows the site and can require
# the page to corroborate the label before removing it.
VERSION_SUFFIXES = ("ENG", "SUB", "DUB")


def strip_version_suffix(title, lang):
    """Drop a trailing audio-version label from an eTiketti title. -> title

    Four conditions, all required, because the cost of being wrong is a mangled film name:
    the last word is one of exactly three known labels; it is published in capitals, which
    a word inside a real title is not; something is left of the title after it; and the
    page stated a language of its own, so the fact the label carries is not the only copy
    and nothing is lost by dropping it. A page with no language row keeps its title
    untouched.
    """
    if not lang:
        return title
    head, sep, last = title.rstrip().rpartition(" ")
    if not sep or last not in VERSION_SUFFIXES:
        return title
    return head.rstrip() or title


def normalise_aud(raw, short):
    """`VENUE | HALL` -> the hall alone, or "" when the hall is only the venue again.

    Savon Kinot reports a room as the venue and the room joined by a pipe, and the room
    half repeats the venue: `TAPIO | TAPIO 4`. Both the app and the generated pages print
    `aud` verbatim -- correctly, because for every other eTiketti site it is already the
    room as printed on the ticket -- so Joensuu showed "TAPIO | TAPIO 4" beside a venue
    label that already said Tapio.

    Three shapes, all of them in the committed data and all handled here:

    - `TAPIO | TAPIO 4` -> `Sali Tapio 4`. The number is the room, and the name stays
      with it because a bare "Sali 4" means nothing on a city page listing four cinemas.
      The casing comes from the registry's `short`, so nothing here has to guess how a
      Finnish name is capitalised.
    - `KUVALIPAS | KUVALIPAS` -> `""`. One screen, and the hall half carries nothing the
      venue label does not already say.
    - `KILLA`, unpiped and equal to the venue -> `""`, the same case without the pipe.

    Empty for a single-screen cinema is this provider family's own convention rather than
    a choice made here: eight other eTiketti cinemas -- Bio Grand, Bio Grani, Bio Vuoksi,
    Ihme Kompleksi, Joutsan Kino, Kino Iiris, Kino Juha and K-Kino -- already publish
    `aud` as "".

    Anything that matches none of those is returned unchanged. A room this does not
    recognise should reach the page looking odd rather than be silently dropped, and
    **this runs only for sites that opt in** with `aud_repeats_venue`. Leffabuumi also
    pipes -- `KINOLINNA | SALI 1` -- and means something different by it: there the right
    half is a real room name, not the venue again. A rule applied to every eTiketti site
    would flatten that.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    parts = [x.strip() for x in raw.split("|")]
    if len(parts) == 2:
        left, hall = parts
        if hall.casefold() == left.casefold():
            return ""                                  # one screen, named twice
        m = re.fullmatch(re.escape(left) + r"\s+(\d+)", hall, re.I)
        if m:
            return f"Sali {short} {m.group(1)}"
        return hall                                    # a room name of its own
    if len(parts) == 1 and parts[0].casefold() == (short or "").casefold():
        return ""                                      # the venue name and nothing else
    return raw


def _place_class(cls):
    """`item tampere date-3.9.2026 name-x` -> "tampere": the class tokens that are not the
    item marker, a date or a name. Kotka would give "kotka", but there the place line
    wins and this is never consulted."""
    return " ".join(t for t in cls.split()
                    if t != "item" and not t.startswith(("date-", "name-")))


def house_facts_cut(paras):
    """The paragraphs before K-Kino's facts block. Its six film pages, read 2026-10-04, end
    the description with a "Tiedot" heading, "Kesto: ...", "Ikäraja: ...", then ticket
    sales, snacks and house rules, which reached a shared slot. Only the heading followed by
    a runtime line counts."""
    for i, t in enumerate(paras[:-1]):
        if t == "Tiedot" and paras[i + 1].startswith("Kesto:"):
            return paras[:i]
    return paras


def parse_movie(page, site, movie_url):
    """-> (list of raw screenings, film meta).

    `meta["skipped"]` counts screening blocks this parser found and could not read a time
    out of. A page whose blocks all land there is a template that moved, and fetch_site
    needs to tell that apart from a film with no screenings left.
    """
    h1 = H1_RE.search(page)
    title = _txt(h1.group(1)) if h1 else ""
    age = AGE_RE.search(page)
    rating = ""
    if age:
        a = age.group(1).lower()
        rating = "S" if a == "s" else f"K-{a}"
    dur = DUR_RE.search(page)
    minutes = ""
    if dur and (dur.group(1) or dur.group(2)):
        minutes = str(int(dur.group(1) or 0) * 60 + int(dur.group(2) or 0))
    poster = POSTER_RE.search(page)
    img = poster.group(1).split("?")[0] if poster else ""
    lang = _lang(page, no_subs=site["provider"] not in NO_SUBS_UNREAD)
    genre_hits = GENRES_RE.findall(page)
    if not genre_hits:
        g2 = GENRES2_RE.search(page)
        genre_hits = g2.group(1).split(",") if g2 else []
    genres = ", ".join(dict.fromkeys(_txt(g) for g in genre_hits if _txt(g)))
    d = DESC_RE.search(page)
    # A screening-note paragraph goes whole, as at Gilda. Savon Kinot opens films with one
    # ("... Kitee ||"), and kept, it reached the slot every chain reads (2026-10-04).
    paras = [t for t in map(_txt, PARA_RE.split(d.group(1))) if t] if d else []
    paras = [t for t in house_facts_cut(paras) if not is_note(t)]
    syn = AGE_BOILER_RE.sub("", " ".join(paras))

    out, skipped = [], 0
    for m in ITEM_RE.finditer(page):
        cls, block = m.group(1), m.group(2)
        dm = ITEM_DATE_RE.search(cls)
        d, mo, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        tm = TIME_RE.search(block)
        if not tm:
            skipped += 1
            continue
        place = PLACE_RE.search(block)
        # Niagara prints no place line; its item carries the place as a class instead
        # ("item tampere date-..."), and `match` runs against that.
        theatre = _txt(place.group(1)) if place else _place_class(cls)
        room = _txt(place.group(2)) if (place and place.group(2)) else ""
        price = PRICE_RE.search(block)
        seats = SEATS_RE.search(block)
        book = BOOK_RE.search(block)
        tags = [_txt(t) for t in TAG_RE.findall(block)]
        out.append({
            "theatre_raw": theatre, "aud": room,
            "start": datetime.datetime(y, mo, d, int(tm.group(1)), int(tm.group(2)),
                                       tzinfo=FI).isoformat(),
            "price": _price(price.group(1)) if price else "",
            "free": int(seats.group(1)) if seats else None,
            "method": " \u00b7 ".join(dict.fromkeys(t for t in tags if t)),
            # The public screening id, as the ticket href carries it. The key a show is
            # deduplicated on: Niagara's programme renders every screening twice, in a
            # desktop and a mobile wrapper, and a film page must never be able to do the
            # same. Never fetched.
            "sid": book.group(1) if book else "",
            "url": site["base"] + (book.group(1) if book else movie_url),
        })
    # "no subtitles" alone does not corroborate a DUB or ENG label: the audio is unstated.
    stated = ", ".join(t for t in lang.split(", ") if t and t != "XX-S")
    return out, {"title": strip_version_suffix(title, stated), "rating": rating,
                 "len": minutes, "img": img,
                 "lang": lang, "genres": genres, "syn": syn, "paras": paras,
                 "skipped": skipped}


def _film_container(listing):
    """The film container's own contents -> str, or None if it is not there.

    Depth-aware rather than a regex to the next `</div>`, because everything asked of
    this has to be true *inside* the container and not merely somewhere on the page. The
    template already ships one hidden element holding a different "nothing here" phrase
    (`no-results`, `display: none`, present on populated sites too), which is exactly the
    shape that would turn a page-wide text search into a false empty programme if the
    empty state ever moved into a hidden sibling.
    """
    m = LISTING_CONTAINER_RE.search(listing)
    if not m:
        return None
    depth = 1
    for tag in re.finditer(r"<(/?)div\b", listing[m.end():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return listing[m.end():m.end() + tag.start()]
    return listing[m.end():]          # unclosed markup: treat what is there as the body


def _classify_no_films(listing, url):
    """No movie links were found. Decide why, and raise accordingly. Never returns.

    Zero regex matches proves only that *this* regex matched nothing. It does not prove
    the cinema published nothing, and treating the two as the same turns a parser
    regression into a soft ageing signal: the run exits 0, the previous data is kept, and
    the only symptom is the health line going amber hours later.

    So EmptyProgramme is raised only on positive evidence that the template rendered its
    own "nothing on" state:

      * the film container is present, so the expected page rendered at all, and
      * it holds no per-film cards, read without going near the href, and
      * the template's empty-state phrase is inside that same container -- not merely
        somewhere on the page, where a hidden element could put it.

    Anything else is a failure, including the case that looks most like emptiness -- a
    container full of cards whose links this parser can no longer read. A false hard
    failure costs one red run; a false empty publishes stale data indefinitely and says
    nothing.
    """
    inner = _film_container(listing)
    if inner is None:
        raise RuntimeError(
            f"{url}: no film container in the response, so this is not the listing this "
            f"parser reads -- treating it as a fetch or template failure, not as a "
            f"cinema with nothing on")
    entries = len(LISTING_ITEM_RE.findall(inner))
    if entries:
        raise RuntimeError(
            f"{url}: the film container holds {entries} entr(y/ies) and MOVIE_LINK_RE "
            f"matched none of them. The markup changed; this is a parser break, not an "
            f"empty programme")
    if LISTING_EMPTY_RE.search(inner):
        raise EmptyProgramme(f"{url} renders the template's empty programme")
    raise RuntimeError(
        f"{url}: no film entries and no empty-programme marker either, so there is no "
        f"evidence the cinema published nothing. Failing rather than guessing")


def identified_venues(listing, site):
    """The registered venues the listing's theatre navigation names -> set of ids.

    Positive identification for an empty venue: the site itself lists the venue, under the
    name `match` expects, so a venue with no screening row is out of programme rather than
    renamed or gone. `match` is looked for *inside* the anchor text, case-folded, the way
    a screening row is matched: Leffabuumi's anchors read "Mikkeli Kinolinna" and "Puumala
    Kino Saimaa", so a whole-text comparison identified 0 of its 3 venues. That comparison
    was what cost the coverage, not the anchor pattern: 6 venues of 29 identified whole,
    10 as a substring, measured 2026-09-14 across all 20 hosts. Both ends run the same
    rule, so a `match` loose enough to take a foreign anchor here was already taking
    foreign rows there.
    """
    names = [_txt(t).lower() for t in VENUE_LINK_RE.findall(listing)]
    return {v["id"] for v in site["venues"]
            if any(v["match"].lower() in n for n in names)}


# A parenthesised aside lists titles or names, and its English function words placed a
# Finnish cast paragraph as English: "Jenny Slate (Marcell the Shell with Shoes On, ...)"
# on Unohdettu saari (2026-10-04).
ASIDE_RE = re.compile(r"\([^()]*\)")


def _language(text):
    return syn_language(ASIDE_RE.sub(" ", text))


def syn_value(text, paras=()):
    """What `_syn` carries. -> {lang: str}, or "" to publish none.

    The whole text is placed by `syn_language` and an unplaceable one withheld. When the
    paragraphs place in more than one language the text is split instead: each language
    takes its own paragraphs, and those none places (headlines, source lines, the `***`
    between) are dropped. Niagara prints Finnish then Swedish in one description, and read
    whole the Swedish half outvoted the Finnish. Parenthesised asides are not scored.
    """
    placed = [(_language(p), p) for p in paras]
    langs = sorted({lang for lang, _ in placed if lang})
    if len(langs) > 1:
        return {lang: " ".join(p for x, p in placed if x == lang) for lang in langs}
    lang = _language(text)
    return {lang: text} if lang else ""


def fetch_site(site, sleep=1.2):
    listing = get(site["base"] + "/elokuvat/ohjelmistossa")
    seen, movies = set(), []
    for path, mid in MOVIE_LINK_RE.findall(listing):
        if mid not in seen:
            seen.add(mid); movies.append((path, mid))

    if not movies:
        _classify_no_films(listing, site["base"] + "/elokuvat/ohjelmistossa")

    per_venue = {v["id"]: [] for v in site["venues"]}
    seen_shows = set()
    unclaimed = {}        # place text -> rows, named in the log below
    # Emptiness is confirmed only for a read with nothing unexplained: every film page
    # fetched and producing rows, every screening row taken by a registered venue. Any
    # miss clears it.
    complete = True
    for path, mid in budget_or_raise(movies, site['provider']):
        try:
            page = get(site["base"] + path)
        except Exception as e:
            # The screenings are on the film pages, so publishing the rest would put out
            # part of some venue's day, and which venues this film plays at is on the page
            # that failed. Fail the site and keep every previous file, `budget_or_raise`'s
            # rule and kinola's (2026-09-25).
            raise RuntimeError(f"{site['provider']}: movie {mid} did not answer ({e}); "
                               f"its screenings are on that page, so no venue of this "
                               f"site publishes a partial schedule") from e
        rows, meta = parse_movie(page, site, path)
        if rows and not meta["title"]:
            # The H1 moved: every row of this film would go out titled "?". Dropped and
            # counted, and the read confirms no venue empty, so a site whose every film
            # went this way has no live venue and fails.
            print(f"[{site['provider']}] movie {mid}: {len(rows)} row(s) with no title, "
                  f"dropped; no venue of this site can be called empty")
            complete = False
            continue
        # A film page that produced no row. Screening blocks with no readable time are
        # TIME_RE off the template; no block at all is ITEM_RE off it, and the page names
        # no empty state of its own (the hidden `no-results` phrase ships on populated
        # pages too). Either looks exactly like a film nobody is showing any more: every
        # venue ends the read rowless and every venue the navigation names would be
        # published empty. nexxo.py raises on the same shape; here the read is only
        # disqualified, so the venues that did parse still publish their rows.
        if not rows:
            print(f"[{site['provider']}] movie {mid}: no screening row "
                  f"({meta['skipped']} block(s) without a readable time); "
                  f"no venue of this site can be called empty")
            complete = False
        for r in rows:
            # One public screening, one show, whatever the markup repeats. The ticket id
            # is the key. A row without one is keyed on the film, its start, the place
            # and the auditorium together: a shared host screens one film in two halls
            # at the same minute, and film-plus-start alone would have folded them.
            key = r["sid"] or (path, r["start"], r["theatre_raw"], r["aud"])
            if key in seen_shows:
                continue
            hay = f"{r['theatre_raw']} {r['aud']}".lower()
            venue = next((v for v in site["venues"] if v["match"] in hay), None)
            if not venue:
                # A place nobody registered: a renamed venue looks exactly like this, so
                # no venue of this site can be called empty on this read. Deliberately not
                # excused by the navigation naming the place as one of the site's own
                # theatres -- Cine's navigation names Cine Mäntsälä and Kiertuenäytökset,
                # neither of them registered here -- because a `match` that has rotted off
                # a *registered* venue drops its rows onto a place the navigation names
                # too, and excusing that would publish a venue that is showing films as
                # confirmed empty. The cost is the other direction: one row for a sibling
                # cinema withholds every empty confirmation on the site, and the venue
                # reads "not updated" again. It keeps its real data while it does.
                complete = False
                unclaimed[r["theatre_raw"]] = unclaimed.get(r["theatre_raw"], 0) + 1
                continue
            # Recorded only once a registered venue took the row, so a malformed copy
            # that matched nothing cannot suppress the valid copy that follows it.
            seen_shows.add(key)
            per_venue[venue["id"]].append({
                "eventId": mid,
                "title": meta["title"],
                "original": "",
                "len": meta["len"],
                "rating": meta["rating"],
                "genres": meta["genres"],
                "method": r["method"],
                "theatre": venue["name"],
                # Verbatim for every site but the ones that repeat the venue inside the
                # room; see normalise_aud.
                "aud": (normalise_aud(r["aud"], venue["short"])
                        if site.get("aud_repeats_venue") else r["aud"]),
                "start": r["start"],
                "url": r["url"],
                "img": meta["img"],
                "lang": meta["lang"],
                "soldOut": r["free"] == 0,
                "price": r["price"],
                "provider": site["provider"],
                "venue": venue["id"],
                "_syn": syn_value(meta["syn"], meta["paras"]),
            })
        time.sleep(sleep)

    # Named, because withholding the confirmation is otherwise invisible: the venue simply
    # goes on reading "not updated" and nothing says which place did it.
    if unclaimed:
        print(f"[{site['provider']}] no registered venue claims "
              + ", ".join(f"{p!r} ({n} row(s))" for p, n in sorted(unclaimed.items()))
              + "; no venue of this site is confirmed empty on this read")
    for k in per_venue:
        per_venue[k].sort(key=lambda s: s["start"])
    # A venue with rows is reported. A venue without rows is reported, empty, only when
    # the navigation identified it and the read was complete; otherwise it is left out
    # and run.py keeps its previous file.
    empty_ok = identified_venues(listing, site) if complete else set()
    return {k: v for k, v in per_venue.items() if v or k in empty_ok}
