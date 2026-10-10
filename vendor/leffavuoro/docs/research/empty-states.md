# Empty states: what a site renders when it has nothing on

`common.EmptyProgramme` and `EMPTY_VENUES_CONFIRMED` need the upstream's own empty state,
and since 2026-09-24 both clear a venue's previous screenings. This file holds what was
read to establish or check one. The decision is in
[docs/archive/2026-09-pipeline.md](../archive/2026-09-pipeline.md), "An empty programme
clears withdrawn screenings".

## Findings

- **Alatalo**, two Wayback captures of the listing, read 2026-09-24: 20250430205300 lists
  the five town headings in a row with nothing under them; 20250803183148 puts `ELOKUVAT
  JATKUU SYYSKUUSSA` under each. In both, every digit on the page (price line, "75
  vuotta", a phone number) sits above the first town heading, and below the headings only
  non-programme lines follow. The adapter's no-digit check is built on this.
- **Alatalo**, the listing, live, 2026-09-24: HTTP 200. Four town headings, Pudasjärvi,
  Haapajärvi, Kiuruvesi and Kemijärvi, each with dated rows; Toholampi is not on the page.
  Below Kemijärvi only the footer, with no digit. Parsed to 13 screenings, Toholampi empty.
- **Heureka**, the calendar page the adapter reads, live, 2026-09-24: HTTP 200, 24 calendar
  items, 6 in the planetarium category, 28 exceptions. Every item and exception carries all
  seven weekday keys as lists, which is the shape the empty-window check requires. It
  parsed to 198 showtimes. Heureka's paused state itself has not been seen.
- **Navettakino**, front page, live, 2026-09-24: the heading reads "Tulevan viikonlopun
  näytökset", no longer the "viikolopun" the adapter's comment records. Two films with
  screenings on la 26.9 and su 27.9; every date and clock on the page is inside the
  listing paragraphs, so the new date-or-clock check does not fire on a populated page.
- **Tähti Kino** (tribe.py), the events route with its film category, live, 2026-09-24:
  HTTP 200, a JSON object with `events` `[]`, `total` 0 and `total_pages` 0. That list is
  what the adapter now requires before the category check may confirm the venue empty.
- **Kuvakukko**, the programme page, live, 2026-09-24: HTTP 200, 33 Kuopio and 9 Manttu
  screenings. Besides its days, Kuopio's section holds one line, when the next week is
  published; Manttu's holds three, when the next weekend is published, the address and the
  ticket line. None opens with `Klo`, a weekday and a date, or a date.
- **Kino Tapiola**, the committed 2026-09-05 fixture: the `filter-no-results` phrase is on
  the populated listing, for the client-side filter. It is not an empty state.

## Inferences

- A site whose empty state has never been seen fails the run on a genuinely empty week.
  That is the intended direction: red with old data kept, rather than green with real
  screenings deleted.
- Toholampi's absence reads as the town having nothing on because the page is the
  operator's whole programme. A heading typed another way would read the same, which is
  why no empty town is confirmed while a line sits under a heading no town owns.

## Open questions

- What these sites render with nothing on: Julia, Kino Vaakuna, Kino Kirkkonummi, the four
  TMB cinemas, Bio-Kaari, Bio Savoy, Iso-Hannu, Kino Tapiola, Kinotour, Kuvakukko. Heureka's
  paused calendar: ended runs left in place, or the planetarium items removed.

## Implementation status

Each site above raises `RuntimeError` on zero rows. Next step: when a run fails on one with
the cinema's own page showing nothing on, read that page as a visitor, record the empty
state here with its date, and let the adapter raise `EmptyProgramme` on it.
