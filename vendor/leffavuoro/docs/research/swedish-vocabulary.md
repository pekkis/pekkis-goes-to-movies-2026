# Swedish cinema vocabulary in Finland

What Swedish-language cinema sites in Finland call a screening, a schedule and subtitles.
Read 2026-09-23 as a visitor, the server HTML of each page with script and style removed,
counted as whole words. Content rendered only by JavaScript was not seen. The decisions
this fed are in [docs/archive/2026-09-app.md](../archive/2026-09-app.md).

## Findings

| page | loaded | screening | schedule | subtitles | other |
|---|---|---|---|---|---|
| ritz.fi/sv/ | 200 | "visningar" (1, a button) | none | none | "evenemang" for listings |
| walhalla.fi/sv/event/page/14/ | 200 | "visning", "visningar" | "program" | "textning" beside the Finnish "tekstitys" | archive page, 2020-21 content |
| bioforum.fi/sv_SE/visningstider | 200 | none in rows | "Visningstider" (title, nav, heading) | no subtitle field | "föreställning" once, in opening-hours text |
| biorex.fi/sv/filmer/scarlet/ | 200 | "visning", "visningar" | "föreställningstider" (54, mostly one link label) | "Textspråk" filter, "Beskrivande textning" | "Föreställningar och biljetter" heading |
| ritz.fi/sv/event/yellow-letters-gelbe-briefe/2026-09-15/ | 200 | "visningen", "visningar" | none | "Textning:" label | "säljs vid dörren" for the ticket sale |
| bioforum.fi/sv_SE/visningstider/presidentin-kyyditys | 200 | none | "Visningstider" (nav) | "svensk textning" in prose | |

None of the six uses "tidtabell", "startvy" or "på plats".

## Inferences

- A single screening is "visning" wherever a site names one; "föreställning" survives in
  Biorex's schedule links and in fixed phrases, not as the word for one screening.
- "Visningstider" and "föreställningstider" are both in use for the schedule. Choosing
  "visningstider" matches the choice for a screening.
- "Textning" as a label is attested once (Ritz). Biorex labels the field "Textspråk".
- "Biljetter säljs på plats" is an editorial choice, not an attested one: Ritz writes "vid
  dörren". "På plats" was preferred because a door sale here includes box offices and cafés.

## Open questions

- A native Finland-Swedish reader has not reviewed the result.
- Sample of six pages from four operators; no Swedish-language chain site was read beyond
  Biorex.

## Implementation status

Applied 2026-09-23 to the app, the status page, the privacy page's links and the generated
Swedish pages. Next step: the reader review listed in [IDEAS.md](../../IDEAS.md).
