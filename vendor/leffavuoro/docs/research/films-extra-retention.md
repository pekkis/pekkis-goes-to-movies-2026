# Retention for films-extra.json and tmdb-titles.json

Nothing removes an entry from `data/films-extra.json` or `data/tmdb-titles.json`: 250
commits of films-extra since 2026-08-27 and not one key ever deleted. This file measures
what the entries hold and what keeping them costs, and proposes a design. Audit item E10.
Nothing here is built.

All figures were read on 2026-09-26 from the committed data at `2433b57e5` and the git
history up to it, unless a line says otherwise. "Live" means the key, `norm(title)`, of a
show in some committed `data/area-*.json`, Finnkino's included; "dormant" means not live.

## Findings

**What writes each field** (code read 2026-09-26):

- films-extra `s.fi`, `s.sv`, `s.en`: the cinema's text through `synmerge.merge`, from an
  adapter's `_syn`, or TMDB's overview through `enrich_tmdb.sync_extra`. The TMDB pass
  lists the slots it filled in `ts` and the id they came from in `id`; a slot not in `ts`
  is the cinema's, or a hand edit. `sv` is only ever the cinema's (`SYN_SLOTS = fi, en`).
- films-extra `r`, `tr`, `img`: the TMDB pass alone (`sync_extra`, `unpublish_extra`).
- films-extra `kr`, `krs`: `merge_shared`, cleared and rewritten every run from live data.
  No dormant entry holds one.
- `merge_extra` projects **every** trusted tmdb-titles entry into films-extra, dormant
  ones included. Removing TMDB fields from films-extra alone is undone by the next pass.
- tmdb-titles holds TMDB's answer per key (`i`, `x`, `r`, `n`, `g`, `v`, `p`, `fi`, `en`,
  `ry`) and bookkeeping (`c` last usable read, `a` last attempt, `o`, `y`, `q` the evidence
  judged on, `t`, `al` for a weak candidate). All of it can be refetched.
- `refresh.due` is handed only the titles gathered from live area files, so a dormant
  tmdb-titles entry costs no TMDB request.
- `synmerge.merge` fills a slot only when it is empty or in `ts`. An adapter supplies
  `_syn` on every run while the film is in its listing, capped per run in some
  (`cinemahouse.enrich`), and nothing after the film leaves it. An empty slot means "fill
  me": a slot cleared on purpose cannot be told from one never filled. Commit `c54e45232`
  records Star's run refilling a slot a hand edit had cleared.
- Finnkino does not write films-extra; its synopses are in `films.json`.

**Contents** (`data/films-extra.json`, 2026-09-26):

- 573 entries, 489,011 B, 170,702 B at gzip -9. Served gzip-encoded, 172,787 B on the wire
  (`curl` of leffavuoro.fi, 2026-09-26), `cache-control: max-age=600`.
- 192 entries are dormant, holding 137,726 B of the file (28.2%), 44,790 B of it gzipped
  (26.1%). By time since last live: 50 under 7 days, 61 from 7 to 14, 81 from 14 to 30.
- Of the 192 dormant entries, 120 hold some cinema or hand text, and 72 hold only fields
  TMDB can refill. 119 dormant entries carry a TMDB `id`, the 119 trusted dormant cache
  entries.
- Filled synopsis slots, all entries: 312 in `ts` (TMDB's), 365 not in `ts` with an `id` or
  in `sv` (cinema or hand), 94 with no `id` (cinema text, or TMDB text written before `ts`
  existed and never matched since).
- The file changed 10 to 24 times a day from 2026-09-19 to 2026-09-25. The client reads it
  only when a film sheet opens, and again from the worker's cache after each change.

**Hand corrections**, found from the history rather than the file, which carries no
marker. Method: commits touching `data/films-extra.json` by the maintainer identity (46,
against 204 by `kino-bot` and `kino-local`), narrowed to the `data:` subject prefix and
confirmed by reading each message; then every one of the 250 versions walked to find which
commit last set each current slot's text. Eight `data:` commits touch the file;
`5dd5080cb` (2026-09-19) is a pipeline snapshot after a rebase, and the other seven,
all 2026-09-24, edited slots:

- `0ca34e631` (Kilta menu, 46 slots), `36d43f119` (Korjaamo, ten fi to en), `c54e45232`
  (Hanuman Ansh, cleared), `1a867e4da` and `3449419b7` (two Kilta Nordic films' full fi
  and sv from the pages), `4c0f15fc1` (three mixed fi/sv strings split), and `da385e278`,
  which cleared other films' TMDB text by rule.
- 20 current slots of cinema text were last set by one of the first six; 14 of the 20 are in
  dormant entries (Korjaamo's ten, four of the split). `0ca34e631` and `c54e45232` only
  emptied slots: of Kilta's 46, 27 have been refilled by later runs and 19 are empty.
- Three adapter commits moved slots and fixed the adapter together (`1540b200b` Engel,
  `147d61d71` Gilda and eTiketti, `31e4262bf` Tapiola). Those adapters now supply the
  corrected form, so a refill reproduces the correction.
- The other maintainer commits that set current text are provider additions and TMDB rule
  changes committing a pipeline run: adapter or TMDB output, refillable like a bot run's.
- At least one hand fix would not survive a refill: Cinema Niagara has no `declare_syn`
  in `etiketti.py`, so it still publishes the mixed fi/sv string, and `4c0f15fc1` records
  that a merge of it over the split text merges nothing only because the slot is filled.
  Status 2026-09-28: `etiketti.syn_value` now splits that text by paragraph into the same
  `fi` and `sv` the hand fix wrote, so a refill reproduces it.

**Returning films**, from every commit that changed an area file, 567 from 2026-08-26 to
2026-09-26, with the set of live keys at each:

- 739 distinct keys. 77 absences ended in a return, over 55 keys. 34 lasted under a day.
  43 lasted a day or more, over 28 keys: median 2.0 days, 90th percentile 7.1, longest
  16.9 ("iván hadoum", Orion to Kino Kilta). Five came back after 7 days or more, one after
  14 or more.
- Of the 41 of those 43 whose chains at both ends could be read, 28 came back at a chain
  that had listed them before and 13 only at another chain. 16 were Finnkino both times.
- The window is 31 days and every dormancy is cut off at its end: a film back after a
  month or more cannot appear in this data.

**tmdb-titles.json**: 654 entries, 324,199 B on one line, 108,590 B gzipped; 226 dormant
keys hold 89,002 B. Not requested by the client. History in this clone: 250 blobs,
40.0 MiB raw, 0.67 MiB packed on disk (films-extra: 253 blobs, 0.89 MiB packed).

**TMDB requests per title** (`enrich_tmdb.main`, read 2026-09-26): a fresh match costs at
least three, a search, the fi-FI detail and the videos; four when TMDB has no Finnish
overview and en-US is asked; one more for each year-filtered search that misses and each
further candidate. A refresh of a known id skips the search. An unmatched or weak title is
searched again daily while live whether or not its entry exists.

## Inferences

- The dormant entries are download weight only: the sheet looks up the film on screen, and
  a dormant key is never on screen. The generated pages cover live films only.
- Keeping tmdb-titles in full costs almost nothing: dormant entries do not change between
  versions, so each version's delta carries little of them, and no request is spent on
  them. Dropping them would cost three or more requests per returning matched film.
- Deleting a dormant films-extra entry loses: TMDB fields, which the cache restores with no
  request if tmdb-titles is kept; the cinema's text, which comes back only if a chain that
  publishes `_syn` lists the film again, and as that chain's text (13 of 41 returns came
  back elsewhere); and hand text, which comes back as the adapter's uncorrected text or
  not at all.

## Options

1. **Prune dormant entries after N days**, in both files. Needs a per-entry last-seen
   stamp, a new persistent field. Client saving at N=7: 34,560 B gzipped (20.2%), at N=14:
   20,912 B (12.2%). Of the 43 returns, five at N=7 and one at N=14 would have found their
   entry gone. Loses hand text (14 of 20 slots are dormant today) and cross-chain cinema
   text; three or more TMDB requests per returning matched film.
2. **Project TMDB fields for live titles only; keep cinema and hand text.** `merge_extra`
   would sync only live keys and strip `ts` slots, `r`, `tr`, `img`, `id` and `ts` from
   dormant entries, deleting an entry left with no text. tmdb-titles stays whole. Client
   saving now: 18,934 B gzipped (11.0%); 72 entries go, 120 keep only their text. A
   returning film loses nothing and costs no TMDB request: the next pass projects the
   cache back, and `sync_extra`'s no-`id` rule treats kept text that differs from TMDB's as
   the cinema's. No new state: liveness is read from the area files each pass. A title
   absent for one run loses and regains its TMDB fields, about 150 entry rewrites a month
   at most, at the measured rate.
3. **Move dormant entries to a file the client does not request**, for example
   `data/films-dormant.json`, and move each back when its key is live again. Client saving
   now: 44,790 B gzipped (26.1%). A returning film loses nothing and costs no request. The
   cost is a second file every films-extra writer has to read under the lock, a move-back
   that must run before `synmerge`'s fill check or the adapter's text lands first, and
   more places for the two halves' commits to conflict.
4. **Recover from git history on return.** Needs full history at run time, which ties the
   pipeline to checkout depth (shallow checkouts were held on 2026-09-24,
   `docs/archive/2026-09-ops.md`), and a history search for every returning key. Recovers
   only what was committed.

## Recommendation

Option 2. It separates the two kinds of data by where they live: TMDB's in tmdb-titles,
projected into films-extra only while a film is showing, and the cinema's and hand text in
films-extra for good. It deletes no text, adds no field and no file, and a return costs no
request. It saves less than option 3; option 3 can follow if the extra 25,856 B gzipped
per sheet download is wanted, since an entry holding only text moves cleanly.
Keep tmdb-titles.json whole under any option.

## Status

Option 2 built on 2026-09-26, on the maintainer's decision, with one change: a dormant
entry that keeps text keeps its `id` too, so a kept slot equal to TMDB's overview is not
taken for TMDB's when the film returns. Record: `docs/archive/2026-09-pipeline.md`.
Applied to the committed data the same day: 72 entries removed, 123 dormant entries kept
with text only, no slot outside `ts` changed, no live entry changed. The file went from
488,949 B to 433,503 B, and gzip -6 from 171,416 B to 152,955 B, 18,461 B (10.8%) less
per download.
