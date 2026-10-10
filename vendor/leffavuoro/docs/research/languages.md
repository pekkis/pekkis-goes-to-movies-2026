# Which providers publish which languages

Moved out of `IDEAS.md` on 2026-09-15. Probed 2026-08-29 by counting films on each
provider's own Swedish path, not by counting HTTP 200s: a soft-404 answers 200 with zero
film links.

**Status.** Swedish is the third UI language and has been since 2026-08-29. Swedish
*titles* are not built: `title` is the merge key, so they would cost BioRex a second fetch
per venue and a new per-show field. Finnish is the fallback title, not English, because the
Finnish distributor title is what the ticket prints.

**Open.** One thing. The Swedish interface strings are drafted rather than translated and
still want a native Finland-Swedish reader, the contact line most of all.

**The language codes closed 2026-09-15.** Measured twice by parsing each `lang` value
with `LANG_RE` and splitting compounds, not by grepping: at `bb409cc0` over 86
`data/area-*.json` and 4,178 shows, then again at `887a7988` over 86 files and 4,262
shows, after a cloud push landed. Same verdict both times: `TU`, `MA` and `XX` absent in
both roles, no value failing `LANG_RE`, every code named. At `887a7988` the published set
is AR, DA, DE, EN, ES, FI, FR, IT, JA, KO, LT, NO, SV, TR, all named in the client's `LN`
and the generator's mirror; `NO` was not in the first measurement, and `ML` is absent from
the data entirely. `CODE_ALIAS`, `NO_SUBTITLES` and `LN_EXTRA` are gone from
`build_pages.py` with the assertions that pinned them; the adapter tests that keep the
data clean stay. Record:
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md).

**`XX-S` came back 2026-09-29 with a meaning**: a source saying outright that a screening
has no subtitles; an absent or unknown field stays blank. Kino Engel published it first,
from its "TEKSTITYS: Ei tekstitystä". On 2026-10-04, on the maintainer's decision, five
more sources publish it, each from its own subtitle field and nothing looser, read that
day:

- eTiketti: the Tekstitys row "Ei tekstitystä", 139 screenings at sixteen sites, all
  Finnish films or dubs. Niagara and Star are not read: Niagara prints the row on pages
  with no Kieli row, Star beside Italian audio and beside Swedish and Russian dialogue.
- Nexxo: a bare `XX` in `code_subtitles`, 29 rows at five sites. Unknown is `OV`.
- Kino Regina: the whole Tekstitys cell "ei tekstitystä", 10 of 110 film pages.
- Gilda: audio style "Ei tekstitystä" with `subtitle_lang` "-", 18 of 21 screenings. The
  Lighthouse names subtitles beside the style and keeps them.
- Bio Marilyn: the labelled line "Tekstitys: Ei tekstitystä" (its ballet).

Since 2026-10-05 Bio Forum's "Elokuva on ilman tekstitystä." (Lilla Spöket) is read as
`XX-S`. Still unread: the same words with another subject ("se on ilman tekstitystä"),
Niagara's Black Magic Rites with the rest of Niagara and Star until a screening is
confirmed, and every source that names no subtitle field. "(dub)" alone, a no-dialogue code
and a cinema's house-wide rule stay unread by the same decision.

MyCloudCinema's "Tekstitys : No Subtitles" on Riviera's and Bio-Kaari's ticket pages is not
read either. On 2026-10-09 it showed up on a page that names no language at all, which
means the platform prints it when nothing has been set. The maintainer decided the same day
to leave it unread even when the page names the audio. Subtitles stay unknown unless the
cinema has a separate, reliable subtitle field.

---

### Swedish: who actually publishes it (probed 2026-08-29)
Four covered cities are Swedish-strong (Vaasa, Pietarsaari, Porvoo, Kokkola), 23 of 48
venues sat in bilingual municipalities and 1920 showtimes carried Swedish subtitles, so a
Swedish mode has an audience. It has little Swedish source text.

- BioRex publishes a real Swedish edition: `admin-ajax.php?lang=sv` returns genuine
  Swedish distributor titles (Autot -> Bilar, Päivien lumo -> Skimrande dagar); 6 of 22
  differ, and its 12 venues include Vaasa, Pietarsaari and Porvoo.
- Finnkino has none: `hreflang` declares `fi-fi` and `en`, `/sv/` redirects to Finnish,
  and the site's configuration API accepts only `fi-FI` and `en`.
- eTiketti has none: `/sv/` on kotkanleffat.fi and biorex.org is a soft-404 with zero film
  links. Count the films, not the 200s.
- Savon Kinot's `/sv` is a 404.

Decision: Swedish UI everywhere, Swedish titles at BioRex when built, and Finnish as the
fallback title, not English: the Finnish distributor title is what the ticket and the
cinema's page print. The UI strings need no pipeline change and are most of the value;
Swedish titles would cost BioRex a second fetch per venue and a new per-show field, since
`title` is the merge key.
