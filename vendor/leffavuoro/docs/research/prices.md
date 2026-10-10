# Where a ticket price can be read, and where it cannot

Moved out of `IDEAS.md` on 2026-09-15. Findings from reading each provider as an ordinary
visitor, with the date each was read. The access rule they are all measured against:
booking, payment and administrative endpoints are never called and not inventoried.

**Status.** The shared step is `scripts/providers/prices.py`: one GET per screening id
against the public ticket page a showtime already links to, sequential, 1 s apart, at most
40 pages a run, re-read after 48 h. Riviera, Kino Regina and Korjaamo Kino use it.
Coverage, re-measured 2026-09-19 over the committed `data/area-*.json`: **1,584 of 5,371**
showtimes carry a price, 29.5 %, against 907 of 3,773 on 2026-09-13. Sixteen providers
publish none at all, and two of them are most of the gap: Finnkino 2,241 unpriced showtimes
and BioRex 921, both of which keep their prices inside a booking flow this repo does not
call.

**Deferred, 2026-09-16.** The one route not looked at is a visitor-facing *price page*,
which would be ordinary content rather than a booking endpoint. The maintainer deferred it
for Finnkino and BioRex on the grounds that neither is easily done. It is not probed, and
the dated entries below that call it "not looked at" are unchanged records of the day they
were written rather than a next action.

**Decided against.** Kino Engel's prices sit behind the Johku widget's API key; a headless
render was measured at about 6 s a page and deferred by the maintainer on 2026-09-13.
Inferring a screening's price from a site's footer house rates, as Kino Tapiola would
need, is an inference and is not published.

---

### BioRex, Gilda and Tapiola publish no per-screening price (probed 2026-09-13)
Asked whether the shared ticket-page price step (`prices.py`) could cover the three
unpriced non-Finnkino providers. Read as a visitor from an ordinary connection, one page or
payload each, nothing kept:
- **BioRex**: the admin-ajax listing's `data-click-data-layer` carries event, movie,
  cinema, show id and time only (82 objects, no price field). The showtime link lands on
  `webshop.biorex.fi/fi/#/book/{id}`, a 3.9 kB single-page shell whose prices come from
  the booking flow, which is never called.
- **Gilda**: the booking API's `show_times[].tickets` is `[]` on all 81 screenings; the
  film page prints no amount but "0,00 €". Prices appear only inside MyCloudCinema's
  purchase flow.
- **Kino Tapiola**: the screening page's ticket box carries no amount; the only prices on
  the site are the footer's house rates, "Liput 12,50 / 11,50 €", which are not a
  screening's price and would be an inference to publish.
So the step applies to none of them today. Coverage stays 907 of 3773 showtimes priced;
Finnkino (booking flow only), Heureka (admission) and Engel (Johku widget, deferred) are
the other zeros.

### Listing data leaves four fifths of showtimes unpriced (2026-09-01)
| | |
|---|---:|
| showtimes with a price on the listing we read | **1,043 of 5,079** |
| showtimes without | 4,030 |
| providers publishing at least one listing price | 27 of 32 |
| unpriced showtimes contributed by Finnkino | 2,333 |
| unpriced showtimes contributed by BioRex | 1,364 |

The provider count flatters it: the two largest chains are among the five that publish
nothing, so showtimes are the denominator. An earlier draft claimed cinemas publish prices
on the booking page; that was not measured, booking pages were not inspected, and the claim
is removed.

The booking flow stays out of bounds: booking, payment and administrative endpoints are
never called and not inventoried, and per-showtime prices would mean about 4,000 extra
fetches at the current cadence against small ticketing platforms. Not looked at: a
visitor-facing price page, which would be ordinary content and could give per-ticket-type
pricing.

### Finnkino publishes no prices outside the booking flow (2026-09-01)
Two backlog entries wanted Finnkino prices and were the same endpoint counted twice. An
earlier draft said the client half was done and that the price cell carried a ticket-type
breakdown in a `title`; both were wrong (the `title` belongs to Cinema Orion's page markup),
and checking found the parseFloat bug above.

The programme response carries no prices: a showtime object is `areaCategories,
attributeIds, eventId, filmAdvanceBookingRuleId, filmId, id, isAllocatedSeating,
isSoldOut, requires3dGlasses, restrictions, schedule, screenId, seatLayoutId, siteId`, and
scanning the whole response for any key containing price, amount, cost, ticket, fee,
tariff or currency returns zero matches. Per-showtime, per-site and bare ticket-type paths
answer 404; four attempts, not inventoried further.

The only route left is the seat-selection flow, which the access rule forbids: blocked by
the repo's own rule, not by difficulty. Open on one possibility: a visitor-facing price
page, not probed. The probe was one `/sites`, two programme reads and four 404s; nothing
raw was written to the repo.

## The providers added 2026-09-14/15, surveyed for a price (2026-09-16)

**Findings.** Committed data at `0b4a167f`, then each site read as a visitor, once.

| Provider | Where a price is stated | Cost to read it |
|---|---|---|
| Kino-Toijala, -Sampo, KinoMania, Elo | under each screening on the `?ohjelmisto=` film page; the `?hinnat=N` tariff prices nothing | one request per distinct film, already made for the runtime |
| Kino Kirkkonummi | `<div>Liput 14,50</div>` in each film's block | none, already fetched |
| Iso-Hannu | `LIPUT Ma-to 13,50 € Pe-su ja arkipyhä 14,50 €` on the front page | none, already fetched |
| Kino Manttu | `Kino Mantun liput: 11 € / 9 €` in the listing text | none, already fetched |
| Kino Kuvakukko | a `/liput/` page | one request |
| Bio-Kaari | a `/liput/` page, rules by film, day, length and 2D/3D | one request |
| Bio Savoy | `Pris: 15 €`, a labelled field on each `/film/{slug}` page | one request per distinct film |
| Kino Kilta, Kino Laika | only behind the Kinola checkout | forbidden |
| Cine Mäntsälä | a "Liput" content page in the app's own content API | one request per venue |
| Julia, Kino Vaakuna | already read | — |

- **TMB states a tariff and no screening can be priced from it.** 2D and 3D differ by 2.50
  and the list view carries no 3D marker -- the three `3D` strings are the `<title>` and the
  "Mediapalvelu W3D" footer, none on a row -- so the format of every row is unknown. The
  `+0.50` covers Saturday, Sunday *and* weekday public holidays, so a weekday row is
  unknown too. Both gaps together leave no screening settled.
- **Kirkkonummi states a price per film**, not per house: 14,50 and 15,50 both appear. The
  block prints it either side of the screening list. This is the strongest of the three,
  because the amount is attached to the film rather than derived from a rule.
- **Iso-Hannu's tariff settles part of the week.** `Pe-su ja arkipyhä 14,50 €` fixes Friday,
  Saturday and Sunday whatever else the day is. `Ma-to 13,50 €` does not fix a weekday,
  because the same line puts an *arkipyhä* on the dearer tariff. The discounts beside it --
  student, pensioner, under-12, S-Etukortti Tuesdays at 10,00 € -- all need a card at the
  counter, so they describe no ordinary ticket.
- **Bio Savoy states a price per film, in a labelled field.** Each `/film/{slug}` page
  carries `<section class="field field-name-field-price">` with `<h2>Pris:</h2>` and the
  amount: *Uprising* 15 €, *Practical Magic 2* 15 €, *Dog Stars* 15 €, *Marsupilami* 13 €,
  read 2026-09-16. That matches what `/om-oss` says the two gift-card denominations are
  for, "13€ (barnfilmer samt filmer med svenskt tal)", but the field is the film's own
  statement rather than a rule to apply. The front page, which is all the adapter fetches,
  carries only the gift-card sentence: "13€ (barnfilmer) och 15€", and 135€ for ten
  tickets. A ticket price read out of *that* would be an inference; the field is not.
- **Bio-Kaari's page states rules rather than a table**: the price varies by film, by day,
  by running length and by 2D/3D.

**Inferences and open questions**

- Kinola's price sits behind the checkout, which this repo does not call. Closed.
- **Cine Mäntsälä publishes a tariff, and it settles no screening.** Corrected: the first
  pass said "not located", which was a failure to look rather than a finding. The schedule
  payload carries no price -- 53 keys over 41 rows, no `€` anywhere in the body -- but the
  site is an AngularJS app whose own content API serves its pages, and
  `webservices/content/getContent` with `content_id=10` returns the one titled `Liput`. The
  route came from the app's own bundle, which names `content/getContent` beside the
  `show_times/` calls the adapter already uses.

      Arkipäivät (ma–to)                     12,50 €   ·  3D 13,50 €
      Viikonloppu (pe–su) sekä arkipyhät     14,50 €   ·  3D 15,50 €
      Lapset (11v ja alle), opiskelijat, eläkeläiset  −1 €

  Unlike TMB, **3D is readable**: the schedule payload carries `version_3d` per screening,
  along with `premiere`, `running_time` and `rating`. What still settles nothing is the rest
  of the page. *Arkipyhä* shares the weekend tariff and no calendar here knows those days.
  Premieres that open Wednesday rather than Friday are priced as a weekend, and what the
  payload's `premiere` flag means was not established. And the page states its own escape:
  "Erikoiselokuvat, kestoltaan pitkät elokuvat tai muuten esitysoikeuksiltaan erityiselokuvat
  hinnoitellaan erikseen. **Hinta kannattaa tarkistaa elokuvan näytösajan yhteydessä.**" The
  cinema is saying the tariff is not authoritative for a given screening, with no threshold
  for "long" and no marker for "special". Event cinema is priced per event.

  So a Saturday 2D ordinary film is 14,50 € *unless it is one of those*, and nothing in what
  this repo may read says which. Under the rule on `common.Show` that publishes nothing.
  It is the clearest candidate so far for a labelled house tariff, which is a different
  field and the maintainer's decision.
- Whether a labelled house tariff should be published where a per-screening price cannot be
  is a product question. The `price` field is a per-screening claim, so that would be a
  different field.

**Status and next step**

The rule, stated by the maintainer 2026-09-16 and now in `CLAUDE.md` and on `common.Show`:
an exact price only where its applicability to that screening is established, otherwise
blank. Implemented the same day: Kino Kirkkonummi publishes its per-film amount and blanks
any film whose association is ambiguous; Iso-Hannu publishes Friday to Sunday and blanks
Monday to Thursday; TMB publishes nothing and no longer fetches the price page.

Cine Mäntsälä and Bio Savoy were finished on 2026-09-16 and the table above is corrected.
Neither is implemented.

- **Bio Savoy is implemented**, 2026-09-16, on the maintainer's instruction. Thirteen
  public-page requests is a modest absolute workload and the order-of-magnitude framing was
  not a reason to hold it. One request per *distinct* film, paced 1.5 s, cached, and bounded
  by `common.capped`; a film past the cap or whose page will not answer keeps its screenings
  and loses only the amount.
  **Coverage was established, not sampled**: all thirteen films were read on 2026-09-16 and
  every one carried the field with a single amount -- 15 €, and 13 € for the two children's
  films, which is what `/om-oss` says the cheaper gift card is for. No page carried a second
  amount or any per-screening note, so no screening-specific exception was found. That says
  the field is single-valued today and not that it always will be, so the reader publishes
  nothing whenever it cannot be sure: no field, no readable amount, two different amounts,
  an unread page, or a film past the budget.
- **Cine Mäntsälä needs no further research.** The tariff is readable at one request per
  venue and settles no screening; nothing more is pending unless a house tariff is wanted.
- Kino Manttu, Kino Kuvakukko and Bio-Kaari were read on 2026-09-16 and are below. Nothing
  in this file is now unread.


## The three sources left unread, read (2026-09-16)

**Findings.** Each page read once as an ordinary visitor, `Leffavuoro/1.0`, nothing kept.

**Kuvakukko's `/liput/` states both venues' prices and states no condition.**
`https://www.kuvakukko.fi/liput/`, 200, 56 kB. Under `Kino Kuvakukko liput`:

    Liput: 11,50 € / 9,50 € (alle 12-vuotiaat, opiskelijat, eläkeläiset, varusmiehet,
    työttömät). Sarjaliput (kuusi näytöstä) 57,50 € / 47,50 €. Lahjalippu 11,50 €.

and under `Kino Manttu liput`, `Liput: 11 € / 9 €` with the same list in the parenthesis.
Neither line turns on a day, a format, a running length or a kind of film, and neither
carries an escape clause of the sort Cine Mäntsälä's page prints. The series ticket and the
gift ticket are other products, not conditions on one admission.

**That answers what `11 € / 9 €` settles.** The programme page the adapter already fetches
carries Manttu's line in full -- `Kino Mantun liput: 11 € / 9 € (opiskelijat, eläkeläiset,
varusmiehet, työttömät, lapset alle 12v)` -- so the parenthesis names who the second figure
is for and the first is the ordinary admission. Two statements on the cinema's own site
agree. Kuvakukko's own amount is **not** on that page: only `/liput/` carries it, which is
one request a run for both venues, since both cinemas are the city of Kuopio's and share
the host.

**What is not settled is a strand screening.** The listing carried
`Hopeatähti-sarja: Laula minulle Arja`, linked to `isak.fi` rather than to this site, and a
`KUVIn aluesarja` mention. Nothing on either page says whether a series screening run with
an outside organiser is sold at the house price. The house statement names no exception,
which is not the same as excluding one.

**Bio-Kaari's `/liput/` settles no screening**, `https://www.bio-kaari.fi/liput/`, 200,
191 kB. The tariff is 2D 14 € at the weekend and on public holidays, 2D 13 € on a weekday,
3D one euro dearer, `Korotettu lipunhinta normaalia pidempiin elokuviin. Korotus 1-2 €`,
children's films 12 €, and Event Cinema priced separately. Four separate reasons a row
cannot be settled, and they do not cancel out at the weekend the way Iso-Hannu's do:
*pyhinä* shares the weekend rate and no calendar here knows those days, the length
surcharge states neither a threshold nor a single amount, "lasten elokuvat" is not defined
in anything readable, and the format is not published at all.

**Bio-Kaari's own pages carry no amount either.** The weekly posts titled
`Elokuvat, näytösajat ja hinnat …` publish the week as a JPG
(`2026_09_11_Bio-Kaari_viikko-ohjelma_nettiin.jpg`); their HTML contains no `€` at all. The
`/tapahtuma/?event={id}` page the adapter already fetches contains no `€` and no 2D or 3D
string, only `Osta lippu`. The showtime link goes to
`bio-kaari.azurewebsites.net/websales/show/{id}/`, which is the sales flow and is not
called.

**Status.** Bio-Kaari is closed: there is no readable per-screening price and the tariff
settles nothing.

**Changed 2026-10-09, on the maintainer's decision.** The ticket page is now read the way
Riviera's is. Its `showPrices-table` had one "Normaali" row on each of the five pages read
that day, at 12, 13 or 14 €, and `biokaari.ordinary_price` publishes that row. A page with
no such row, or two that disagree, publishes nothing.

Riviera's event screenings sold as a single bundle ("Elokuva + Konsertti 39,00 €", read
2026-10-09) have no ordinary row and stay unpriced. Taking a table's only row was
considered and not done: a page listing only a wheelchair seat must not be priced, and
`test_riviera_prices` holds that.

**Kuvakukko and Manttu are implemented**, 2026-09-16, on the maintainer's instruction:
publish the venue's tariff where its applicability is established, leave an externally sold
or otherwise ambiguous screening unpriced, do not infer applicability from an on-site link
alone, honour an explicit screening-specific price or exception, fetch `/liput/` once a run,
and leave the amount blank where the source is unavailable or ambiguous. Live at the time of
writing: Kuopio 32 of 36 rows at 11,50 €, Nilsiä 9 of 9 at 11 €. The four blanks are the
outside organisers' rows -- one Hopeatähti series screening, one Hyvät Kuvat film club
screening and two Vilimit festival screenings, all four linking to isak.fi or
hyvätkuvat.fi. The record is in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md).

## TMB is priced after all, from the screening and not the tariff (2026-09-16)

The entry above says no TMB screening can be priced, and it is right about the tariff: 2D
against 3D is unreadable and *arkipyhä* needs a calendar. Both questions turned out to be
the wrong ones. The film page, which this adapter began reading the same day for the
runtime, prints `Hinta:` under **each screening** -- `14.45€ / 12.45€ / 11.45€` on a
Wednesday and `14.95€ / 12.95€ / 11.95€` on the Sunday of the same film, read 2026-09-16.
The operator has already applied its own tariff, so the format and the +0.50 the maintainer
confirmed for weekends and public holidays are both in the figure.

The first of the three is the ordinary admission: `?hinnat=2` prints Aikuinen 14.45,
Eläkeläinen 12.45, Lapsi 11.45 in that order, read the same day, and the film page prints
the same three numbers in the same order.

Published on the maintainer's instruction 2026-09-16, at no extra request: the page was
already being fetched. The tariff page is read by nothing.

## The three providers added after the 2026-09-16 survey (2026-09-19)

That survey ran on the batch of 2026-09-14/15 and nothing since was checked, so these
three stood unpriced with no record of whether that was a decision or an omission. Read as
a visitor from an ordinary connection, once each.

| Provider | Where a price is stated | Verdict |
|---|---|---|
| Kinotour | `<label>Hinta</label><strong>€11,00</strong>` on each `/events/{slug}/` page | **readable, now published** |
| Kino Myyri | nowhere on `kinomyyri.fi/ohjelmisto/`; no euro amount in the whole response | correct absence |
| Bio-Kaari | a `/liput/` page, amounts by film, day, length and 2D/3D | correct absence; the ticket page is read since 2026-10-09 |

**Kinotour was an omission, and the adapter said the opposite.** `kinotour.py` carried
"the event page carries a booking form with no amount rendered anywhere on it, so nothing
settles a screening" from the day it was written. The amount is there, server-rendered, in
Events Manager's single-ticket block, and it is the amount for that screening rather than a
tariff. Whoever wrote that line read the listing table, or read the word "booking" and
stopped. Ten showtimes went unpriced for a day over one wrong sentence, which is the case
for checking a negative claim about a page against the page.

**The price reads survive a runner pass.** They had only ever run from an ordinary
connection, and kinotour was one of the nine modules the runner was being challenged on
when they were written, so the cloud half had never executed them. It has now.
`logs/run-kinotour.log` at `1327b328c`, the commit run 35457381191 produced on
2026-09-19 at 17:16:13Z:

    [kinotour] prices: 10 event page(s) read, 10 of 10 row(s) priced, 0 page(s) that did not answer

Ten event pages, ten rows priced, none that failed to answer, and `exit=0` for the module.
The amounts landed in the committed data: 9 EUR and 11 EUR across
`data/area-kinotour-kyro.json` (3 shows), `-naantali.json` (3) and `-lieto.json` (4). The
per-row request cost is therefore paid on the cloud half at the same shape it was measured
at locally, one request per distinct event page.

**Kino Myyri is a correct absence and simply post-dates the survey.** It joined on
2026-09-18, and like its two Kinola siblings its prices sit behind the checkout, which this
repo does not call. `/ohjelmisto/` was read on 2026-09-19 and carries no euro amount at all.

**Bio-Kaari is a correct absence for the reason Cine Mäntsälä already records.** The
`/liput/` page states 12 €, 13 €, 14 € and 7,50 € among others, conditioned on the film, the
day, the running length and 2D against 3D. None of that is on the screening row, so no row
settles an amount and `price` stays empty. It was in the 2026-09-16 table as "one request"
but the adapter never carried a sentence saying why it was not taken; this is that sentence.
Since 2026-10-09 the price comes from each screening's ticket page instead; see above.

**Coverage after this**, measured at `0409aa452` over the committed data: 1516 of 4956
showtimes priced. The zeros that remain are all recorded decisions -- Finnkino and BioRex
(booking flow only), Heureka (admission), Gilda and Kino Tapiola (probed 2026-09-13), the
four Johku storefronts and Kino Engel (widget, bands only), Cine Mäntsälä and Bio-Kaari
(tariff conditions the row does not settle), and the three Kinola tenants (behind the
checkout).
