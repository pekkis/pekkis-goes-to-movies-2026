# Screening language: Riviera, Cinema Orion, Kino Helios and three without a source

The three adapters publish `"lang": ""` for every screening (`riviera.py`, `orion.py`,
`helios.py`), so the app shows no audio or subtitle language for them. Read 2026-09-23
from an ordinary connection, as a visitor, with the adapters' own User-Agent. The open
item is in [IDEAS.md](../../IDEAS.md).

## Findings

- **Riviera, per screening.** The admin-ajax listing the adapter reads (111 kB) names no
  language. Each screening's ticket page on the ticket host, the page the price pass
  already fetches, carries both: `<p class="spokenLanguage">Kieli: <b>Suomi</b></p>` and
  `<p class="showSubtitles">Tekstitys : <b>Englanti</b></p>`. Values are capitalised
  Finnish language names. One page read (screening 982798, 200, 39.5 kB), then a sample
  of 22 pages over 11 of the 28 films on the listing: every page had the audio line,
  three had no subtitle line (Rakkautta ja virtahepoja twice, Trainspotting), both
  screenings of each sampled film agreed, and one value was English ("Kieli: Spanish",
  Autofiktio). A capped run through the adapter read 12 more; one, Dyyni: Osa kolme,
  had neither line.
- **Cinema Orion, per film.** The front-page table the adapter reads names no language.
  Each film page linked from it, `/elokuvat/{slug}/` (18 on the day), has a definition
  table with `Kieli:` and `Tekstitys:` rows, lower-case Finnish names separated by
  commas. Three pages read: "englanti, portugali, ranska, japani" / "suomi";
  "espanja" / "suomi, ruotsi" (Autofiktio, matching Finnkino's `ES-A, FI-S, SV-S`);
  "suomi" / "ruotsi". Then all 18 linked film pages, 2 s apart: every one had both
  rows, 17 films had one screening on the front page and Hetki ennen valoa two from the
  same page, and no screening note named a version. Two words no table knows, "dari"
  and "paštu" (The Secret Reading Club of Kabul).
- **Kino Helios, nowhere this adapter can read.** The calendar service returned 22 Kino
  Helios events with 16 non-empty fields each, none of them a language, and no language
  wording in any description (one-sentence blurbs). All 22 ticket links go to one ticket
  shop, whose event page reset the connection for a plain client (HTTP/2 stream error
  after 0.1 s) on one attempt.

- **Kino Helios, per screening, read 2026-09-29.** Each calendar row's `key` opens the
  event page a visitor reaches from the calendar before the ticket shop, which the page
  draws from `GetSingleEvent` `{"Key", "Language"}` on the same service. Its `breadtext`
  ends with the film's facts, `Kieli: suomi<br />Tekstitys: suomi`, also `Kesto` and
  `Ikäraja`. 13 of the 17 rows that day parsed as names; the other four are two dubbed
  films, and both records read say `Kieli: puhuttu suomeksi`.
- **Bio-Kaari, Forssan Elävienkuvien teatteri and Kino-Huovi, nowhere, read 2026-09-29.**
  No language wording on Bio-Kaari's four event pages, on four of Elävien kuvien's film
  pages, or on Kino-Huovi's front page, the pages the three adapters read. Bio-Kaari's
  WordPress route index lists no programme route. What remains is each cinema's ticket
  page, which is not read.
- **Bio-Kaari's ticket page, read 2026-10-09.** `websales/show/{id}/` states
  `Kieli: <b>Suomi</b>` on all five pages read, and `Tekstitys : <b>Suomi</b>` where a
  film is subtitled, in Riviera's markup. Where it is not, the page prints
  `<p class="no-subtitles"> Tekstitys : <b>No Subtitles</b>`. Riviera's page for Dyyni: Osa
  kolme printed that same line with no `Kieli` line at all.

## Inferences

- Riviera's language can ride on the price pass: same page, same cache. Pages already
  cached are re-read once, earlier than their expiry, to pick it up.
  At `FETCH_MAX` 40 pages a run and 84 screenings on the day, coverage would fill over
  about three runs, as prices do.
- Orion's is film-level, so one page per film (18 requests a run, paced) and the same
  value on every screening of that film. Orion is a single screen, so a per-screening
  difference would be unusual; unverified.
- Both publish the languages as Finnish names. The adapters map the names to codes, and
  the client displays the codes through `langParts`.
- Reaching the Helios ticket shop would need a browser fingerprint, which the project
  does not do. Helios stays without language unless its calendar service adds a field.
- MyCloudCinema shows "No Subtitles" whenever no subtitle language has been set, so the
  line tells us nothing. The maintainer decided on 2026-10-09 that it is not read for
  Riviera or Bio-Kaari, even next to a stated audio language.

## Open questions

- Whether Orion ever lists two versions of one film under one film page; none on the day.

## Implementation status

Riviera built 2026-09-23: `prices.enrich` takes a `fields` parser and caches its answer
beside the price, and `riviera.page_fields` reads the two lines. Record in
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md). Orion built the same
day on the same cache, one film page per film, capped at 12 a run. Kino Helios built
2026-09-29 on the same cache, one record per screening under its ticket link, capped at 12 a
run. Bio-Kaari built 2026-10-09 on the maintainer's decision: its ticket page joins the
price pass the way Riviera's does, for the price and the two language lines. Elävien kuvien
and Kino-Huovi have no source; revisit if one of them adds the language to a page it
already publishes.
