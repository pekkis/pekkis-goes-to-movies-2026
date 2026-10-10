# When the runner is challenged and an ordinary connection is not

Why a cloud run can fail on many unrelated cinemas at once while the same sites answer a
laptop minutes later, and what the pipeline does about it. Nothing here is a rule; the
decision it records is the maintainer's, taken 2026-09-19: **accepted as a known failure
mode, not routed local, no adapter change, no retry on a challenge body, no header
change.**

**Its own file rather than a section of
[ticketing-platforms.md](ticketing-platforms.md).** That file is organised per platform,
one section each for BioRex, Nexxo, eTiketti, Vista, Johku and the sweeps, and answers
"what does this platform publish". This answers "what did the runner get", spans seven
modules over five platforms and eighteen hosts, and belongs to none of them. Filed under a
platform it would be unfindable from any of the other six.

## Findings

**Two runs, the same nine red logs.** Measured 2026-09-19 from the committed logs at the
two commits those runs produced, `15ada2243` and `1ac89b049`, not from the Actions UI.
Both are `workflow_dispatch` of `biorex.yml`:

| run | started | commit | red logs |
|---|---|---|---|
| 35404792959 | 2026-09-18T23:12:48Z | `15ada2243` | cinemahouse, kinotour, kirkkonummi, lieksa, navetta, nexxo, tmb, vpk, cloud |
| 35443942404 | 2026-09-19T12:48:58Z | `1ac89b049` | the same nine |

`run-cloud.log` is the run's own tally, so eight modules failed and the ninth log is the
aggregate.

**A third run carried the same nine, and the fourth carried none.** Measured 2026-09-19
the same way, from the committed logs:

| run | started | event | commit | red logs |
|---|---|---|---|---|
| 35447253315 | 2026-09-19T13:57:01Z | `schedule` | `048ff5c5a` | the same nine |
| 35457381191 | 2026-09-19T17:12:51Z | `workflow_dispatch` | `1327b328c` | none; all 33 logs that commit carries read `exit=0` |

So the mode is intermittent at the run level rather than standing on the runner's address,
which is the reading three consecutive runs over fourteen hours had made worth ruling out.
Nothing in this repository accounts for the recovery: between `048ff5c5a` and `1327b328c`
the only adapter touched was `kinotour.py`, in `2802cc150`, which adds a price read that
runs after the listing is already parsed, so it explains neither kinotour's listing fetch
nor cinemahouse, kirkkonummi, lieksa, navetta, nexxo, tmb and vpk going green alongside it.

**What the failing hosts served, quoted from the logs.** The logs keep the response's byte
count and its `<title>` only; the body is never kept and never committed, which
CLAUDE.md's "Never commit a raw probe dump" requires. Nine hosts answered with a page of
about 12 kB titled `One moment, please...`. At `1ac89b049`:

| host | bytes | module |
|---|---:|---|
| www.kinopiispanristi.fi | 12089 | cinemahouse |
| www.kinolumo.fi | 12092 | cinemahouse |
| kinokirkkonummi.fi | 12095 | kirkkonummi |
| kino-mania.info | 12120 | tmb |
| elokuvat-elo.info | 12122 | tmb |
| www.lieksanelokuvat.net | 12134 | lieksa |
| kinosampo.info | 12201 | tmb |
| toijalan-kino.info | 12205 | tmb |
| www.pyhasalmenvpk.fi | 12257 | vpk |

The same nine at `15ada2243` ran 12051 to 12182 B, so the page differs slightly run to run
and is about 12.1 kB either time.

**Three more hosts answered 403, and only those three carry a `Server` header in a log.**
From `run-nexxo.log`, identical at both commits:

    [http] 403 from kinoset.fi, gave up after 3 attempt(s) -- Server: openresty/1.31.1.1
    [http] 403 from kinohirvi.fi, gave up after 3 attempt(s) -- Server: openresty/1.31.1.1
    [http] 403 from kino-olympia.fi, gave up after 3 attempt(s) -- Server: Apache

`kinohirvi.fi` serves both Kino Hirvi and Bio Säde, which is why four Nexxo providers
failed on three hosts.

**Two hosts failed with no evidence in the log of what they received.**
`www.navettakino.fi` and `www.kinotour.fi` failed on their own markers
(`the page renders no 'Tulevan viikonlopun näytökset' heading`, `no screening row in the
table`) and neither message passes the response through `common.served()`, so those two
logs say the marker was missing and nothing more. They are counted red here and are not
counted as challenged.

**Fourteen of the eighteen hosts the nine modules attempted were red.** A record and the
first NS record as `dig` returned them from an ordinary connection on 2026-09-19. These
are lookups, not page reads; no page was fetched for this table.

| host | run | A | first NS |
|---|---|---|---|
| kinokirkkonummi.fi | red | 152.115.36.105 | ns2.intendit.se |
| kino-olympia.fi | red | 157.180.98.77 | ns3.suncomet.fi |
| www.kinotour.fi | red | 31.217.192.36 | ns1.hostingpalvelu.fi |
| www.laitilankino.fi | **green** | 31.217.192.103 | ns2.hostingpalvelu.fi |
| www.kinolumo.fi | red | 31.217.193.150 | ns2.hostingpalvelu.fi |
| www.kinopiispanristi.fi | red | 31.217.193.150 | ns2.hostingpalvelu.fi |
| kinoaurora.fi | **green** | 5.44.244.43 | cns1.cloudpit.de |
| www.lieksanelokuvat.net | red | 5.44.244.228 | ns2.int2000.net |
| jarvelankino.fi | **green** | 5.44.245.76 | ns3.zoner.fi |
| www.navettakino.fi | red | 77.240.19.23 | dns1.louhi.net |
| elokuvat-elo.info | red | 77.240.19.48 | y.ns.joker.com |
| kino-mania.info | red | 77.240.19.48 | y.ns.joker.com |
| kinosampo.info | red | 77.240.19.48 | x.ns.joker.com |
| toijalan-kino.info | red | 77.240.19.48 | z.ns.joker.com |
| kinohirvi.fi | red | 77.240.19.57 | dns3.louhi.fi |
| www.pyhasalmenvpk.fi | red | 77.240.19.61 | dns3.louhi.fi |
| kinoset.fi | red | 80.69.174.12 | dns1.louhi.net |
| kinomarilyn.fi | **green** | 95.216.140.247 | ns2.dvn.fi |

Two rows are the ones worth keeping. **`www.laitilankino.fi` was green on 31.217.192.103
while `www.kinotour.fi` was red on 31.217.192.36 and two more were red on
31.217.193.150**, all four on one /23 behind one hosting company's nameservers, in the same
run. And **`kinoaurora.fi` was green on 5.44.244.43 while `www.lieksanelokuvat.net` was red
on 5.44.244.228**, adjacent addresses under different nameserver operators. So the split is
not per hosting company and not per address range.

**The gap to the previous run was not short.** Both from one read of the `biorex.yml` run
list: 35404792959 started **38 min 36 s** after 35402123826, and 35443942404 started
**95 min 17 s** after 35439529910. The rule this repository already carries, that a
dispatch should leave an hour after the previous cloud run, is therefore not what these
two failures test: the second waited well over an hour and failed anyway, and the run
95 minutes before it succeeded.

**The rate, over the 50 most recent `biorex.yml` runs**, 2026-09-13T07:34:17Z to
2026-09-19T12:48:58Z, out of 282 in the workflow's history: **8 concluded `failure`** and
one more was `cancelled`. Ids: 34868488107, 34894004566, 34983009141, 34999969305,
35070394363, 35126793232, 35404792959, 35443942404. Only the last two were read
log-by-log for this section, so 8 in 50 is the rate at which a run fails, not the rate at
which it fails **this way**, which is not established here.

**Re-measured 2026-09-19T17:21Z**, one read of the run list, same method: over the 50 most
recent runs, 2026-09-13T10:57:18Z to 2026-09-19T17:20:41Z, out of 285 in the workflow's
history, **9 concluded `failure`**, one `cancelled` and one still running. Ids: the eight
above plus 35447253315, the third same-nine run. The window slid by three hours and gained
one failure.

**What a failure costs, and it is not bad data.** `run.publish_site` compares each venue's
parse against the file already on disk: a venue that returns nothing while a previous file
exists is appended to `stale`, the previous file is kept untouched, and the provider file
is written with `status: partial` and the stale venue ids named. Confirmed in the committed
`data/venues-kinoset.json` at `1ac89b049`: `status partial`, `stale
['ks-huittinen', 'ks-loimaa', 'ks-sastamala']`. So a challenged run publishes older data,
says which venues are older and how old, and publishes nothing wrong. A module whose parse
yields zero rows against a listing that does list films still fails the run, which is the
behaviour that turned these logs red rather than letting them pass quietly.

## Inferences, marked as such

- **A shared bot filter with a centrally distributed IP reputation list would explain the
  shape.** Unrelated hosting companies, unrelated nameserver operators and two different
  origin servers (`openresty/1.31.1.1` and `Apache`) refused one runner address inside one
  minute, while a neighbour on the same /23 answered. A per-host configuration change at
  fourteen sites simultaneously is the alternative and is much less likely. **Not
  verified**, and it cannot be verified from here: the response body is never kept, and an
  ordinary connection cannot reproduce a datacenter challenge.
- **The hostname pattern does not identify the product.** No log line and no header the
  logs keep names a vendor, and `One moment, please...` is used by more than one. This
  file deliberately names none.
- **That the sites were up is established; that the runner was challenged is not, for
  every host.** Nine hosts are evidenced by the title and byte count their log quotes.
  Three are evidenced by a 403 with a `Server` header. Two, Navettakino and Kinotour, are
  inferred from failing in the same run as the others and from nothing else.

**The three headers are recorded but not yet observed on a challenge.** `served()` gained
`Server`, `CF-Ray` and `Retry-After` on 2026-09-20 in `fb3c6beb7`. The first cloud run after
it, 35478523891 at commit `3cd8e008a`, was green: 42 committed logs, all `exit=0`, 63 sites
fetched, no challenge. The only header line that run committed is the **pre-existing** 403/404
hint path, `[http] 404 from api.themoviedb.org, gave up after 3 attempt(s) -- Server: openresty`
in `run.log`, which predates the change. So the recorder is deployed and unexercised, and the
table above still rests on a byte count and a title. Compare from `3cd8e008a` when a run next
goes red.

## Status and next step

Accepted 2026-09-19 at the measured rate, as a known failure mode of reading the public web
from a datacenter address. No adapter changes, no retry on a challenge body, no header
change, and nothing routed local on it: CLAUDE.md's rule that a datacenter read is not
evidence a site is unreachable is what makes this a failure of the reading side rather than
a property of the cinema.

**Next step: none**, unless the rate rises. What counts as a rise is the maintainer's
decision and is deliberately not a number chosen here; the figure to re-measure against is
the 9-in-50 of 2026-09-19T17:21Z above, taken the same way, one read of the run list.

**Not proposed, and it should not be:** keeping the challenge page in the log to identify
the filter. A challenge page is a third party's content and CLAUDE.md forbids committing a
raw dump. The title and the byte count are what the logs keep and are enough to recognise
the state.

## Kino-Huovi: the runner cannot resolve the host (2026-09-25)

A different failure from the challenges above: no request reaches the site at all.

**Findings.**
- Committed `logs/run-kinohuovi.log`, read 2026-09-26: green on every cloud run from
  2026-09-22 to `437cfb4c6` (2026-09-25 11:17Z), 1 venue and 6 showtimes each time. Red on
  the next three: `5d0cb4fbb` (15:27Z), `253476568` (17:18Z), `10c17b0ee` (23:19Z), each
  `<urlopen error [Errno -3] Temporary failure in name resolution>`. The only commit between
  the last green run and the first red one changed `enrich_tmdb.py` alone.
- Resolved from an ordinary connection on 2026-09-25: Google, Cloudflare and Quad9 all
  return the CNAME to the site builder's host and two addresses; all four authoritative
  nameservers answer the same record. The front page answers 200.
- `run.py kinohuovi --half all` from an ordinary connection on 2026-09-26, into a scratch
  copy: `exit=0`, 1 venue, 6 showtimes, the same rows as `437cfb4c6`; both ticket links
  answer 200.

**Inference, not verified.** The four authoritative nameservers sit in one /24, so a
runner resolver that cannot reach that network fails every lookup at once. Nothing from
here can test the runner's resolver path.

**Status.** Routed local on 2026-09-26, the maintainer having authorised the move if a
third routine cloud run failed resolution and an ordinary connection parsed the site. No
adapter or DNS change. Verified on the first routine local run after the push.

## Heureka: Cloudflare answers the runner 429 (2026-10-02)

The runner reaches the site, and the site's CDN refuses it before any page is served.

**Findings.**
- Committed `logs/run-heureka.log`, read 2026-10-03: green on every cloud run up to
  `e805c8555` (2026-10-02 05:22Z), 1 venue and 199 showtimes. Red on the next four:
  `b5c106ec2` (08:48Z), `5f7fcfaec` (11:18Z), `d92012fde` (16:22Z), `d27fedb4c`
  (17:17Z), each `429 from www.heureka.fi, gave up after 3 attempt(s) -- Server:
  cloudflare` with `Retry-After: 60`, on the calendar page, the run's first request.
  CF-Ray suffixes IAD three times and ORD once.
- A run makes five requests, 1.2 s apart (the calendar and four film pages), so the
  refusal is not an answer to this adapter's own rate.
- From an ordinary connection on 2026-10-03 the same calendar page answered 200 and parsed
  to 199 showtimes over four films and 21 dates, the last good cloud run's count.

**Inference, not verified.** Cloudflare rate-limits or scores the runners' address ranges
for this zone; nothing from here can see its rules.

**Status.** Routed local on 2026-10-03 on the maintainer's word, after four routine cloud
runs in a row. No adapter or pacing change. The first routine local run after the push
verifies it.
