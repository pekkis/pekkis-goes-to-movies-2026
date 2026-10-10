#!/usr/bin/env python3
"""Generic provider runner.

    python3 scripts/providers/run.py biorex nexxo etiketti ...
    python3 scripts/providers/run.py --where cloud      # module list from the registry
    python3 scripts/providers/run.py --where local      # the modules with local sites

Every adapter module exposes two things:

    SITES             list of sites. One module can serve several providers
                      (nexxo -> kinoset, etiketti -> kotkanleffat), so the provider
                      id lives on the site, not on the module:
                        {provider, label, venues: [{id, name, short, city}, ...]}
    fetch_site(site)  -> {venue_id: [show, ...]}. A failed venue may be absent.

Written per site: data/area-{venueId}.json and data/venues-{provider}.json.

venues-{provider}.json always lists every venue of the site. The client builds its picker
from it, so dropping a failed venue would make its still-committed area file unreachable
while the health line stayed green.

A venue with no shows is one of three things, checked in this order:

  * pending: the module sets `EMPTY_VENUES_CONFIRMED` and reported the venue explicitly,
    so the upstream answered in schema and listed nothing. The venue gets an empty file
    stamped fresh and stays quiet on the health line, whether or not it had data before.
  * stale: it has a previous file with a day still ahead, which it keeps. An empty parse
    and a cinema with nothing on today both arrive as `[]`, so this is not treated as a
    failure.
  * unverified: no data worth keeping, either never any or a previous file whose every
    day has passed. A venue added before its programme is published and a parse that has
    never worked look the same here, so it stays visibly degraded.

A fetch, schema or parse failure never reaches that loop: the site fails as a whole and
every file it owns is left as it was. `common.EmptyProgramme` is not a failure: every venue
is published empty and pending, and the site is logged as `no programme published`. The provider file carries `status`, `stale`,
`unverified`, `pending` and `oldest`; the health line ages on `oldest`, so a provider is
as fresh as its weakest venue with data. A site where every venue came back empty fails
the run, unless every one was confirmed empty, in which case the file is written with
them all pending (Heureka: one venue, and a paused programme must clear old screenings).

Sites on different hosts are fetched at the same time, sites on the same host one after
the other. Pacing inside an adapter's fetch_site is what a cinema experiences and is
untouched. See host_groups and MAX_HOSTS.
"""
import concurrent.futures
import contextlib
import datetime
import importlib
import json
import os
import pathlib
import sys
import threading
import urllib.parse
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common              # noqa: E402
import registry            # noqa: E402
import strands             # noqa: E402
import synmerge            # noqa: E402
import venuelists          # noqa: E402

OUT = pathlib.Path("data")

# One string, because two copies of it drifted: main() printed it for an empty
# module list and half_of() had none to print at all.
HALVES = ("cloud", "local", "all")
WHERES = ("cloud", "local")
USAGE = ("usage: run.py <module>... [--half cloud|local|all] | "
         "run.py --where cloud|local")


def previous(path):
    """What is already committed for a venue. -> (generated, show count).

    The count is the part that matters. `path.exists()` conflates two different states:
    a venue holding real older data, and a venue whose only file is the empty one written
    so the picker would not link to a 404. Keying on existence marks the second as
    "keeping previous data" from its second run onward, which claims data that was never
    there and drags the provider's `oldest` down forever.

    Unreadable is unknown rather than an error: a torn or hand-edited file must not stop
    the run publishing showtimes.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc.get("generated") or "", len(doc.get("shows") or [])
    except Exception:
        return "", 0


def generated_of(path):
    """The `generated` already committed for a venue. -> str, or '' if unreadable."""
    return previous(path)[0]


# What the TMDB pass stamps onto a show and an adapter cannot know. `gids` is the one
# that matters most: it drives the genre names the client renders and the kids filter's
# id rule, so losing it is not just a missing score ring. The set equals enrich_tmdb's
# PUBLISHED; a test holds the two together.
ENRICHED = ("tmdbId", "tmdb", "votes", "tr", "gids", "oyear")
# A poster is carried too, but only a mirrored one: `data/posters/...` is what the TMDB
# pass and mirror_posters left behind for a film whose adapter publishes no image, and
# it is as much the film's as its id. A provider's own remote URL is the adapter's to
# resupply and is not carried. Applied only where the fresh show has no `img` at all.
MIRRORED = "data/posters/"


def enrichment_of(path):
    """Previously committed enrichment, keyed by title. -> {title: {field: value}}.

    A run rewrites a venue file wholesale from what the adapter returned, so every
    enrichment field in the old file is dropped. In the cloud that is invisible, because
    enrich_tmdb runs straight afterwards and puts them back. On the local half nothing
    does: Kino Engel and Kino Akseli lose their ratings, trailers and genre ids on every
    run and get them back only when the next cloud run lands, and the same happens to
    anyone running run.py by hand -- the trap docs/archive/2026-09-pipeline.md records as
    having cost 1201 showtimes their tmdbId.

    Keyed by the normalised title, `synmerge.norm`, because that is what the TMDB pass
    itself keys on, and because these are properties of the *film*, not of the
    screening. Normalised rather than exact since 2026-09-05: Kino Regina's adapter
    started recasing the site's capitals, and an exact key would have dropped every
    poster and id the previous run had attached to "PIUKAT PAIKAT" the moment the same
    film came back as "Piukat paikat". Carried values are a floor, never an override:
    `setdefault` leaves anything the adapter supplied alone, and the next enrichment
    pass overwrites the lot with fresh figures.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for s in doc.get("shows") or []:
        title = synmerge.norm(s.get("title"))
        if not title or title in out:
            continue
        keep = {k: s[k] for k in ENRICHED if s.get(k) is not None and s.get(k) != ""}
        if str(s.get("img") or "").startswith(MIRRORED):
            keep["img"] = s["img"]
        if keep:
            out[title] = keep
    return out


def run_site(mod, site, now, order=0, claim=None):
    """Fetch and write one site. -> publish_site's tuple. Raises on a fetch failure.

    Two steps rather than one since 2026-09-15, because `run_cloud.py` fetches on a pool
    thread and publishes on a single thread in a fixed order: films-extra.json is one file
    for the whole run and the site that wins a synopsis has to be the earlier one in SITES
    order, not whichever host answered first. Nothing else changed: this is still the whole
    of one site for every caller that fetches it itself.

    `claim` wraps the fetch alone, and `run_sites` passes `common.reading`: the claims are
    released and a swallowed refusal re-raised before anything is written. Wrapping the
    publish as well let a site whose adapter caught `HostBusy` write its files, `status: ok`
    included, before the refusal came back out of the context (2026-09-25).
    """
    try:
        with (claim if claim is not None else contextlib.nullcontext()):
            per_venue = mod.fetch_site(site)
    except common.EmptyProgramme:
        publish_empty(mod, site, now, order)
        raise
    return publish_site(mod, site, per_venue, now, order)


def publish_empty(mod, site, now, order=0):
    """Publish a site whose adapter raised `EmptyProgramme`: every venue empty and pending.

    The exception is raised only on the upstream's own empty state, so it is the same
    evidence `EMPTY_VENUES_CONFIRMED` gives for one venue, given for all of them. Keeping
    the previous files, as this did until 2026-09-24, left the screenings a cinema had
    withdrawn on the page with their ticket links. The caller still records the site as
    `no programme published`.
    """
    return publish_site(mod, site, {v["id"]: [] for v in site["venues"]}, now, order,
                        confirmed=True)


def publish_site(mod, site, per_venue, now, order=0, confirmed=False):
    """Check, merge and write what one site's fetch returned.

    -> (venues_written, showtimes, stale, unverified, pending). Raises if the adapter's
    result does not meet the contract, which is a site failure like a parse error.

    `order` is the site's index in the module's SITES, and only synmerge uses it: two
    sites publishing different synopses for one film are decided by SITES order rather
    than by which host answered first. A caller that fetches one site alone can leave it
    at 0.

    `confirmed` vouches for every venue `per_venue` reports, as `EMPTY_VENUES_CONFIRMED`
    does for a module; `publish_empty` is its one caller.
    """
    label = site.get("provider") or mod.__name__
    # Every show is checked against common.Show before a byte is written. An adapter
    # that drops a key or changes a type fails its site here, like a parse error, rather
    # than publishing a file the client reads by key.
    common.check_shows(per_venue, label, {v["id"] for v in site["venues"]})
    # A strand prefix belongs in `method`, not in the title: left there it fragments the
    # film, blocks the TMDB match and gives every film in the strand the same fallback
    # tile. Applied centrally so a new adapter gets it without knowing it exists.
    split = sum(bool(strands.apply(s)) for shows in per_venue.values() for s in shows)
    if split:
        print(f"[{label}] strand prefix split off {split} showtimes")

    # Nothing this site owns is published until all of it has serialized. `check_shows`
    # above is contract validation and catches a malformed venue before any write, but it
    # is not atomicity: anything that raises after it -- a corrupt previous file under
    # `enrichment_of`, a full disk under the write itself -- used to leave the earlier
    # venues on the new fetch, films-extra.json updated, and the rest of the site on the
    # previous one, which the workflow then committed despite the site having failed.
    # Measured 2026-09-19 with a write failure on the second of two venues: the first
    # venue's file and films-extra.json both changed. So the venue payloads are built and
    # staged first, films-extra is merged only once they all exist, and the live files
    # move afterwards.
    # `strip_helpers` drops `_syn` from every show as each venue is serialized, and
    # `synmerge.merge` now runs after that, so it is handed a projection of the two fields
    # it reads taken before the loop rather than the live shows. Missing this ordering
    # emptied films-extra.json for every site and three synopsis tests caught it.
    syn_input = {vid: [{"title": sh.get("title"), "_syn": sh.get("_syn")} for sh in shows]
                 for vid, shows in per_venue.items()}
    # The day a screening belongs to is Helsinki's, the zone every `start` carries.
    today = datetime.datetime.fromisoformat(now).astimezone(ZoneInfo("Europe/Helsinki")).date().isoformat()
    live = total = 0
    staged = []           # (tmp, path) per venue; nothing is live until commit_staged
    stale = []            # kept its previous file: the data is real, just older
    unverified = []       # never any data, emptiness unconfirmed: parse rot looks the same
    pending = []          # the adapter confirmed the venue empty: no programme at the moment
    try:
        for v in site["venues"]:
            shows = per_venue.get(v["id"]) or []
            path = OUT / f"area-{v['id']}.json"
            prev_gen, prev_shows = previous(path)
            vouched = ((confirmed or getattr(mod, "EMPTY_VENUES_CONFIRMED", False))
                       and v["id"] in per_venue)
            if not shows and vouched:
                # Positive evidence: the module promises that a venue it reported with an
                # empty list is *known* empty -- the upstream answered in schema and listed
                # nothing. Whether the venue had data before does not change that. A touring
                # cinema's town is empty between visits, and keeping its last, past show
                # marked stale for weeks said "not updated" about a programme that had ended.
                # The empty file is stamped fresh so it cannot drag `oldest` down.
                pending.append(v["id"])
                print(f"[{label}] {v['name']}: no programme at the moment (adapter confirmed "
                      f"the venue empty); publishing an empty file", file=sys.stderr)
            elif not shows and prev_shows and common.has_future_shows(path, today):
                stale.append(v["id"])
                print(f"[{label}] {v['name']}: no showtimes, keeping previous data "
                      f"from {prev_gen or 'an unknown time'}", file=sys.stderr)
                continue
            elif not shows and prev_shows:
                # fetch_data.py's rule for Finnkino since the Maxim Helsinki incident: a kept
                # file whose every day has passed protects nothing, and keeping it froze the
                # venue's `generated`, so the provider stayed stale and every combined city
                # view holding the venue aged on it without bound. Published empty and
                # stamped fresh; unverified, which is what the next run calls it anyway.
                unverified.append(v["id"])
                print(f"[{label}] {v['name']}: no showtimes and nothing left ahead in the "
                      f"previous file from {prev_gen or 'an unknown time'}; publishing an "
                      f"empty file", file=sys.stderr)
            elif not shows:
                # Never produced a showtime and nobody vouches for the emptiness: "added
                # before its programme is published" and "a parse that has never worked" are
                # not distinguishable here, so it is recorded rather than judged and must not
                # read as healthy. It still gets the empty file, so the picker does not link
                # to a 404, stamped fresh so a venue with no data cannot drag `oldest` down.
                unverified.append(v["id"])
                print(f"[{label}] {v['name']}: no showtimes and none previously; "
                      f"publishing an empty file", file=sys.stderr)
            shows.sort(key=lambda s: s["start"])
            synmerge.strip_helpers(shows)
            # Read before the write, so a venue keeps its ratings, trailers and genre ids
            # rather than losing them for however long it takes the next enrichment pass to
            # run. Never overrides what the adapter itself produced.
            carried = enrichment_of(path)
            for sh in shows:
                for field, val in (carried.get(synmerge.norm(sh.get("title"))) or {}).items():
                    if field == "img":
                        if not sh.get("img"):
                            sh["img"] = val         # the adapter published none; the mirrored poster stays
                            # ...marked as the TMDB pass's, so that pass can replace it when
                            # the film's match changes and drop it when the match is not
                            # trusted. A poster the adapter publishes carries no mark.
                            sh["isrc"] = "tmdb"
                    else:
                        sh.setdefault(field, val)
            days = sorted({s["start"][:10] for s in shows if s.get("start")})
            staged.append(common.stage_json(path,
                {"generated": now, "dates": days, "horizon": days[-1] if days else "",
                 "shows": shows}))
            if shows:
                live += 1
                total += len(shows)
                print(f"[{label}] {v['name']}: {len(shows)} showtimes, {len(days)} dates")
        # Every venue's bytes exist as a .tmp and none of them is live yet, so this is the
        # first point at which publishing anything is safe. films-extra goes first: it holds
        # the cross-site lock and the claim bookkeeping that decides which site owns a
        # synopsis, and staging that as well would hand a later site a claim whose text an
        # earlier failure had discarded.
        synmerge.merge(OUT, syn_input, label, order)
        common.commit_staged(staged)
    except BaseException:
        common.discard_staged(staged)
        raise

    # Every venue, not just the fresh ones — see the module docstring. Written whatever
    # the outcome, because this file is the site's health record and a site with no live
    # venue is the case the record exists for. It used to be withheld unless a venue went
    # live or the adapter confirmed every one empty, so a dead site could not stamp itself
    # fresh; that also discarded the `stale` list just computed, and the previous file
    # stayed on disk reading `status: ok` with an empty `stale`. Measured 2026-09-14: four
    # Nexxo sites 403ed, six venues kept previous data, and all four provider files still
    # read ok for the 5.7 h it took `oldest` to cross the client's STALE_H. `healthState`
    # reads `stale` before age, so naming the venues is what makes that window degraded.
    #
    # `oldest` is the honest number and `generated` was not. `generated` says when this
    # file was written, which is now; the health line was reading it and calling the
    # whole provider fresh while one of its venues sat on week-old data. Taken from the
    # files on disk rather than from `stale`, so it cannot drift from what was
    # written. Same rule the combined city view already applies: a group is as fresh as
    # its weakest member — and a site with nothing live keeps every previous stamp, so
    # `oldest` goes on ageing here exactly as it did while the file was withheld.
    #
    # A fetch that raised never gets here: run_sites catches it, the site's files are
    # untouched and its previous provider file stands.
    stamps = [generated_of(OUT / f"area-{v['id']}.json") or now
              for v in site["venues"]
              if (OUT / f"area-{v['id']}.json").exists()]
    common.write_json(OUT / f"venues-{site['provider']}.json",
        {"generated": now, "oldest": min(stamps) if stamps else now,
         "status": "partial" if (stale or unverified) else "ok",
         "stale": stale, "unverified": unverified, "pending": pending,
         "provider": site["provider"],
         "venues": [{k: v[k] for k in ("id", "name", "short", "city")}
                    for v in site["venues"]]})
    return live, total, stale, unverified, pending


def confirmed_empty_site(site, pending):
    """True when the adapter confirmed every venue of the site empty.

    Such a site has answered: the programme is paused. Its files are fresh and empty and
    the provider is healthy. A site with pending venues beside stale or unverified ones
    and no live venue is not this -- part of it is unexplained -- and keeps failing.
    """
    return bool(pending) and len(pending) == len(site["venues"])


# How many hosts this end reads at the same time. Not a rate limit at any cinema: the
# sleep inside each adapter's fetch_site is that, and host_groups below keeps every site
# on one host in a single thread so that sleep still describes what the host sees. What
# this number bounds is this end -- open sockets, and the response bodies in flight, at
# most MAX_HOSTS * common.MAX_BODY.
#
# 8 is twice the four vCPUs an ubuntu-latest runner has, which is the usual shape for a
# pool that spends most of its time waiting and parses HTML in between. It caps bodies in
# flight at 160 MB against the runner's 16 GB, covers Nexxo's six host groups outright,
# and takes eTiketti's cloud half, the largest set of hosts any module reads (each site is
# its own host, so its size is the site count), in a few waves instead of one site at a
# time. "As many as there are sites" was rejected as a default: it would raise the ceiling
# every time a cinema is added, with nobody deciding to.
#
# KINO_MAX_HOSTS overrides it, in the style of KINO_PAGE_BUDGET and KINO_MAX_BODY. 1 is
# the sequential path this replaced, and the tests use it to show that path still writes
# the same files and prints the same summary line.
MAX_HOSTS = int(os.environ.get("KINO_MAX_HOSTS") or 8)


def host_of(site):
    """The host a site is read from. -> netloc, or "" when the adapter holds it.

    `base` is where the API lives; `site`, where a module carries one, is where a visitor
    is sent. Bio Säde is the case: its showtimes come from kinohirvi.fi and its ticket
    links go to biosade.fi. The pacing key is the host read, so it is `base` and
    never `site`.

    A site with no `base` keeps its host inside the adapter, out of reach from here.
    Those all answer "" and so share one group, which reads them one after the other
    rather than assuming they are different cinemas. Treating an unknown host as its own
    would put two requests at one server at once; treating two servers as one costs
    seconds.
    """
    return urllib.parse.urlsplit(site.get("base") or "").netloc


def hosts_of(site):
    """Every host a site is read from. -> (netloc, ...), empty when the adapter holds them.

    `base` is the schedule's host. `reads` names any further one the adapter requests -- a
    ticket API on its own subdomain is the case that exists today, Riviera's
    tickets.rivieracinemas.fi -- because two sites that touch one server have to be read one
    after the other whether or not that server is the one their `base` names. An entry may
    be a URL or a bare host.

    What it cannot name is a URL read out of a page: four adapters fetch one and none of
    them checks its host. `common.reading` is the guard for those; see the comment on
    `common.HOST_CLAIM_WAIT`.
    """
    out = []
    for url in (site.get("base") or "", *(site.get("reads") or ())):
        netloc = urllib.parse.urlsplit(url if "//" in url else "//" + url).netloc
        if netloc and netloc not in out:
            out.append(netloc)
    return tuple(out)


def group_indices(host_sets):
    """Which group each member belongs to. -> [int], numbered in first-seen order.

    The groups are the connected components of members and the hosts they name: a member
    reading two hosts joins every member reading either. Grouping on one key per member was
    enough while a site had one host, and stops being enough the moment it has two -- the
    property that has to hold is "no two groups read a host in common", not "one key each".

    An empty host set is its own key, "", shared by every member with one, which is the
    conservative answer for an adapter that keeps its host to itself.
    """
    owner, at, nxt = {}, [], 0
    for hosts in host_sets:
        hosts = tuple(hosts) or ("",)
        joined = sorted({owner[h] for h in hosts if h in owner})
        if joined:
            g = joined[0]
            for other in joined[1:]:
                for h, o in list(owner.items()):
                    if o == other:
                        owner[h] = g
                at[:] = [g if v == other else v for v in at]
        else:
            g, nxt = nxt, nxt + 1
        for h in hosts:
            owner[h] = g
        at.append(g)
    order = {}
    for g in at:
        order.setdefault(g, len(order))
    return [order[g] for g in at]


def host_groups(sites):
    """Sites grouped so that no two groups read a host in common.

    -> [[(index, site), ...], ...], groups in the order their first member appears and
    members in SITES order, so a run reads the same way every time.

    This is the unit the pool works in, and the host is the key rather than the site
    because the data says so today, not hypothetically: kinoaurora.fi serves both
    kinoaurora and kinometso, and kinohirvi.fi serves both kinohirvi and biosade. Keyed
    on the site, two of Nexxo's eight would be read concurrently against one cinema's
    server at twice the rate its adapter paces for -- which is the courtesy the whole
    access story rests on. One thread per host is what keeps that pacing accurate.
    """
    at = group_indices([hosts_of(s) for s in sites])
    groups = {}
    for i, (site, g) in enumerate(zip(sites, at)):
        groups.setdefault(g, []).append((i, site))
    return [groups[g] for g in sorted(groups)]


# How much of one site's output is held while the pool runs. A pool keeps every
# unreplayed site's block in memory at once, so without a bound an adapter that prints per
# row decides how much memory a run takes. 1 MiB a site is two orders of magnitude past the
# largest committed provider log, and what it drops it says it dropped.
MAX_CAPTURE = int(os.environ.get("KINO_MAX_CAPTURE") or 1_048_576)


class _Buffer:
    """One captured stream: quacks like the real one and files its writes with `rec`."""

    def __init__(self, rec, real):
        self.rec, self.real = rec, real

    def write(self, text):
        return self.rec.write(self, text)

    def flush(self):
        self.real.flush()

    def __getattr__(self, name):
        return getattr(self.real, name)


class Recorder:
    """Holds a pooled run's output back so the committed log still reads in site order.

    Sites finish out of order, so printing as they go shuffles `[provider] Venue: N
    showtimes` into a list nobody can read downwards. Each worker's output is collected
    instead and replayed when its turn comes, which leaves every site's lines contiguous
    and in SITES order however long that site took.

    Both streams, not stdout alone: run_site reports stale, pending and unverified venues
    on stderr and the workflow merges the two (`> run-$m.log 2>&1`), so capturing one of
    them would move half the lines. They share one list per thread, so the order the two
    were written in is the order they come back in. That also changes what a committed
    log looks like: today stdout is block-buffered into a redirected log while stderr is
    line-buffered, so a stderr line written last can land first in the file, which is why
    run-nexxo.log opens with kinometso's empty-venue notice from the eighth site of eight.
    """

    def __init__(self):
        self._local = threading.local()
        self.out = _Buffer(self, sys.stdout)
        self.err = _Buffer(self, sys.stderr)

    def install(self):
        """Stand in for sys.stdout and sys.stderr. A thread that is not capturing writes
        straight through, so anything printed outside a worker is unaffected."""
        sys.stdout, sys.stderr = self.out, self.err

    def remove(self):
        sys.stdout, sys.stderr = self.out.real, self.err.real

    @contextlib.contextmanager
    def sink(self, fh):
        """Send this thread's writes straight into `fh` until the context ends.

        The coordinator's half of the same mechanism: a worker's output is collected and
        replayed, and the coordinator's own lines -- the publish step's, the summary's --
        are written where that module's log is. One install of `sys.stdout`, not one per
        module, because two threads swapping the interpreter's streams between them is a
        race with nothing to gain.
        """
        prev = getattr(self._local, "fh", None)
        self._local.fh = fh
        try:
            yield
        finally:
            self._local.fh = prev

    def capture(self):
        """Start collecting this thread's writes. -> the list they land in."""
        self._local.chunks = chunks = []
        self._local.size = 0
        return chunks

    def release(self):
        self._local.chunks = None

    def write(self, buf, text):
        chunks = getattr(self._local, "chunks", None)
        if chunks is None:
            fh = getattr(self._local, "fh", None)
            return fh.write(text) if fh is not None else buf.real.write(text)
        # Bounded, because a pool holds every unreplayed site's output at once and an
        # adapter printing per row would otherwise decide how much memory a run takes.
        # No real block comes near this: the largest committed provider log is a few kB.
        # Truncation is announced rather than silent, and the cap is per site.
        size = self._local.size + len(text)
        if size > MAX_CAPTURE:
            if self._local.size <= MAX_CAPTURE:
                chunks.append((buf, f"[run] output past the {MAX_CAPTURE}-byte capture "
                                    f"cap for this site; the rest is not in this log\n"))
            self._local.size = size
            return len(text)
        self._local.size = size
        chunks.append((buf, text))
        return len(text)

    def replay_into(self, chunks, fh):
        """One site's captured output into an open log file, in the order it was written.

        Both streams land in one file, which is what `> run-$m.log 2>&1` does to them, so
        there is nothing to interleave and none of `replay`'s flushing is needed.
        """
        for _, text in chunks:
            fh.write(text)

    def replay(self, chunks):
        """Write one site's captured output back out, in the order it was written.

        Both real streams are flushed at every switch between them, and before the first
        write, because once the workflow merges them they are two buffers over one file
        descriptor: without the flushes the file would be ordered by whichever buffer
        filled up first, which is the reordering this class exists to remove.
        """
        self.out.real.flush()
        self.err.real.flush()
        buf = None
        for b, text in chunks:
            if buf is not None and b is not buf:
                buf.real.flush()
            buf = b
            buf.real.write(text)
        if buf is not None:
            buf.real.flush()


def run_sites(mod, sites, now, workers=None):
    """Fetch a module's sites, hosts at once and each host's sites in order.

    Yields (label, result, error) in SITES order, `result` being run_site's tuple or None
    when `error` holds what it raised. Yielded one at a time, after that site's output has
    been replayed, so the caller's own line about a site -- `no programme published`,
    `FAILED` -- still lands inside that site's block in the log.

    The exception travels back rather than out. One site failing has never stopped the
    rest of a run, and in a pool a raise would take its host group's remaining sites with
    it as well.
    """
    workers = MAX_HOSTS if workers is None else workers
    synmerge.reset()          # this module's sites decide their own synopsis winners
    groups = host_groups(sites)
    slots = [None] * len(sites)
    done = [threading.Event() for _ in sites]
    fatal = []                # a BaseException out of a worker, re-raised by the reader
    rec = Recorder()

    def read_host(group):
        """One host's sites, one after the other.

        An ordinary failure is caught per site and travels back as that site's error,
        which is the isolation a pool needs: one cinema refusing must not take the rest
        of its host with it, let alone the run.

        Anything that is not an ordinary failure -- a `SystemExit` out of adapter code --
        ended a sequential run and has to end this one. Left alone it would not: the
        thread dies, `ThreadPoolExecutor` puts the exception on a future nobody reads,
        and the run carries on and publishes. So it is recorded here and re-raised by the
        reader, which is the thread a sequential run would have raised it on. Recorded
        rather than reported: a `SystemExit` is not a cinema that could not be fetched and
        must not be written into the log as one.

        The two `finally` blocks stop the reader waiting on a site that will never
        report. The inner one releases a site once it has an outcome; the outer one
        releases everything still held, and runs *after* `fatal` is recorded, so the
        reader always sees the exception before it can reach an empty slot.
        """
        try:
            for i, site in group:
                label = site.get("provider") or mod.__name__
                chunks = []
                try:
                    chunks = rec.capture()
                    # Claims every host this site turns out to read, page-derived ones
                    # included, for the fetch, and releases them before the publish. See
                    # common.reading and run_site.
                    slots[i] = (label, run_site(mod, site, now, i,
                                                claim=common.reading(label)), None, chunks)
                except Exception as e:
                    slots[i] = (label, None, e, chunks)
                finally:
                    rec.release()
                    # Set only once there is an outcome to read. A site whose thread is
                    # being unwound has none yet, and releasing the reader first would
                    # hand it an empty slot before `fatal` was there to be seen.
                    if slots[i] is not None:
                        done[i].set()
        except BaseException as e:          # noqa: BLE001 -- forwarded, not handled
            fatal.append(e)
        finally:
            for i, _ in group:
                done[i].set()

    rec.install()
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(workers, len(groups) or 1)))
    try:
        for group in groups:
            pool.submit(read_host, group)
        for i in range(len(sites)):
            done[i].wait()
            if fatal:
                # Raised on this thread, which is where a sequential run would have
                # raised it. The `finally` below has already cancelled what was queued
                # and put the streams back by the time it leaves here.
                raise fatal[0]
            label, result, error, chunks = slots[i]
            rec.replay(chunks)
            yield label, result, error
    finally:
        # cancel_futures, so a run being torn down -- Ctrl-C, a closed laptop, a caller
        # that stops reading -- stops asking hosts it has not reached yet. The hosts
        # already in flight are still waited for: a thread part-way through writing a
        # venue file has to finish, and `wait=True` is what makes the atomic write mean
        # something. Nothing is cancelled on the normal path, where every group has run
        # by the time the drain ends.
        pool.shutdown(wait=True, cancel_futures=True)
        rec.remove()


def half_of(argv):
    """Which half of the pipeline is running -> "cloud", "local" or "all".

    Routing used to be per *module*, so a single site that has to be fetched from an
    ordinary connection dragged its whole adapter with it: marking one eTiketti provider
    local would have put all sixteen sites in both halves, with two writers on the same
    files. That cost Joutsan Kino, which parses fine at home and answers a runner with a
    Cloudflare 403.

    Derived rather than passed, because the cloud workflow calls this per module with a
    bare name and adding a flag there is a change to a file this could not touch. Actions
    always sets GITHUB_ACTIONS and nothing else here does, so the workflow keeps working
    unchanged and starts skipping the sites it was never able to fetch.

    The default off Actions is "all", not "local": `run.py etiketti` on a laptop is how
    an adapter gets exercised, and silently fetching one site of fifteen would make that
    useless. The local *wrapper* therefore has to be explicit -- `--where local` -- which
    is also what keeps one writer per provider file.
    """
    for flag in ("--half", "--where"):
        if flag in argv:
            i = argv.index(flag) + 1
            if i >= len(argv):
                # `run.py --where` with the value lost to a shell variable that expanded
                # to nothing used to be an IndexError and a traceback, which reads as a
                # broken runner rather than as a mistyped command.
                print(f"{USAGE}\n{flag} needs a value", file=sys.stderr)
                raise SystemExit(2)
            value = argv[i]
            # A value that is not a half matches no site's `where`, so `run.py biorex
            # --half typo` used to print "no sites for the typo half" and exit 0. A
            # scheduled caller cannot tell that from a provider that legitimately has
            # nothing on this half, so a typo in the wrapper would look like a quiet,
            # successful run forever. `--where` takes the two real halves only, which is
            # what USAGE has always said: it selects the modules to import and "all" is
            # not a value `registry.modules` can answer.
            allowed = HALVES if flag == "--half" else WHERES
            if value not in allowed:
                print(f"{USAGE}\n{flag} takes {'|'.join(allowed)}, not {value!r}",
                      file=sys.stderr)
                raise SystemExit(2)
            return value
    return "cloud" if os.environ.get("GITHUB_ACTIONS") else "all"


def module_names(argv):
    """The module names in argv -> list.

    A flag's *value* is not a module name. Dropping only the flags left "local" behind
    for `run.py etiketti --half local`, which run.py then tried to import: "[local]
    unusable: No module named 'local'", counted as a failure, and printed the word in
    the run summary. Caught by running it rather than by reading it.
    """
    skip = {argv.index(f) + 1 for f in ("--half", "--where") if f in argv}
    return [a for i, a in enumerate(argv) if not a.startswith("-") and i not in skip]


class UnregisteredProvider(Exception):
    """A SITES entry naming a provider the registry does not have."""


def sites_for(mod, half):
    """The sites in this module that belong to `half`, in SITES order.

    A site whose provider has no registry entry was kept here until 2026-09-19, on the
    argument that tests/test_registry_sites.py is where a misconfiguration should be
    reported. It is, and it still is; what that left behind was the *consequence* when
    one gets past the suite. `p is None` matched on both halves, so the site was fetched
    twice a run by two processes writing the same `data/venues-{provider}.json`, which is
    the exact failure per-site routing exists to prevent. Reversed on the maintainer's
    instruction: name the provider and fail.

    Raising rather than dropping, because a site fetched by nobody is the quiet half of
    the same fault. The module is the blast radius: both callers now count this the way
    they count a module that will not import, so one bad entry costs its own adapter's
    log and the run's exit code, not every other module's fetch.
    """
    if half == "all":
        return list(mod.SITES)
    out, orphans = [], []
    for site in mod.SITES:
        pid = site.get("provider") or ""
        p = registry.by_id(pid)
        if p is None:
            orphans.append(pid or "<no provider id>")
        elif p.get("where") == half:
            out.append(site)
    if orphans:
        raise UnregisteredProvider(
            f"{', '.join(sorted(set(orphans)))} has no entry in registry.py, so it "
            f"belongs to no half and would be fetched on both")
    return out


def site_of(mod, sites, label):
    """The site a result line came from. Labels are provider ids, unique per module."""
    return next(s for s in sites if (s.get("provider") or mod.__name__) == label)


def summary_line(names, venues, shows, partial, pendings, empty, failures):
    """The run's one-line verdict, in the committed log's fixed vocabulary.

    Pending is counted here even though it is neither a failure nor a partial state:
    the summary is what a sweep of the log reads, and a venue publishing nothing must
    be visible in it rather than looking like a venue that does not exist.
    """
    return (f"[run] {' '.join(names)}: {venues} venues, {shows} showtimes, "
            f"{sum(len(i) for _, i, _ in partial)} stale, "
            f"{sum(len(u) for _, _, u in partial)} unverified, "
            f"{sum(len(i) for _, i in pendings)} pending, "
            f"{len(empty)} with no programme, {failures} failures")


class Tally:
    """One log's outcome: every site's verdict, the closing lines, and the exit code.

    `main` counts a whole invocation with one of these and `run_cloud` counts one module
    with one, because the two now write the same kind of file -- `logs/run-{module}.log`,
    read by `check_runs.py` and by a person -- and its vocabulary and its exit rule must
    not drift apart depending on which of them produced it.
    """

    def __init__(self, names):
        self.names = list(names)
        self.venues = self.shows = self.failures = 0
        self.partial = []       # (provider, stale ids, unverified ids)
        self.pendings = []      # (provider, [venue ids]) whose adapter confirmed no programme
        self.empty = []         # sites whose listing loaded and had no films on it
        self.skipped = []       # modules with no sites for this half, which is not a problem

    def unusable(self, name, error):
        """A module that could not be imported, or that has no SITES."""
        print(f"[{name}] unusable: {error}", file=sys.stderr)
        self.failures += 1

    def no_sites(self, name, half):
        """Not a failure: the module's sites all belong to the other half. The cloud
        workflow iterates every cloud module, so this is the normal answer for a module
        whose only local site is fetched at home."""
        print(f"[{name}] no sites for the {half} half")
        self.skipped.append(name)

    def site(self, mod, sites, label, result, error):
        """Record one site, printing the run's own line about it inside its own block."""
        if isinstance(error, common.EmptyProgramme):
            # Not a failure, and deliberately still noisy: a cinema with nothing on
            # is a fact worth seeing in the committed log, and one that stays empty
            # for weeks is worth chasing even though no run went red over it.
            print(f"[{label}] no programme published: {error}")
            self.empty.append(label)
            return
        if error is not None:
            print(f"[{label}] FAILED: {error}", file=sys.stderr)
            self.failures += 1
            return
        v, s, stale, unverified, pending = result
        self.venues += v
        self.shows += s
        if stale or unverified:
            self.partial.append((label, stale, unverified))
        if pending:
            self.pendings.append((label, pending))
        if not v and not confirmed_empty_site(site_of(mod, sites, label), pending):
            self.failures += 1

    def report(self, stats, throttle, hosts=()):
        """The closing lines, in the order a committed log carries them."""
        # Every request this run asked an upstream for, and how it was asked. Printed
        # because the alternative is a claim: the pipeline says it revalidates where it can
        # and never stores what an origin marks no-store, and this is the line that shows
        # whether that is true on the day. `full` is not waste -- most origins here offer no
        # validator at all, so there is nothing to revalidate with.
        if stats["hit"] or stats["miss"]:
            print(f"[run] http: {stats['hit']} revalidated (304), {stats['miss']} full, "
                  f"{stats['nostore']} not stored (origin said no-store), "
                  f"{stats['stored']} cache entries written")

        # Silent on a normal run. When it does appear, it is a provider telling us the
        # rate is wrong, which is worth seeing in the committed log rather than inferring
        # from a failure four hours later.
        if throttle["asked"]:
            print(f"[run] throttled: {throttle['asked']} Retry-After responses, "
                  f"{throttle['waited']:.0f}s waited, {throttle['refused']} not retried "
                  f"(asked for longer than a run can wait)")

        # What requests were aimed at, not what the sites declare. Four adapters fetch a URL
        # out of a page, so the two can differ, and a host appearing here that no site names
        # in `base` or `reads` is the thing to act on: it is being serialised by the runtime
        # claim rather than by the grouping. See common.reading.
        #
        # Attempted, not reached: the host is recorded when the request goes out, so a
        # refused connection or a 403 counts the same as a body. This line is evidence about
        # where a module aimed, which is the question `reads` answers.
        if hosts:
            print(f"[run] hosts: {len(hosts)} attempted -- {', '.join(sorted(hosts))}")

        # Named, not counted. A venue that kept its previous data is not a failure the run
        # can act on -- at this layer an empty parse and a cinema with nothing on today are
        # the same signal, `[]`, so failing here would fire on every ordinary closure. What
        # it must not do is disappear: the venue file is published with a `partial` status
        # and the health line ages on the oldest venue, so the app stops claiming the
        # provider is fresh, and this line puts the venue names in the committed log.
        # Pending is neither a failure nor a partial state -- the adapter confirmed the
        # programme is empty -- but a venue publishing nothing is a fact the committed log
        # must state, or the summary line reads as if the venue did not exist.
        for label, ids in self.pendings:
            print(f"[run] pending: {label} has {len(ids)} venue(s) with no programme "
                  f"yet: {', '.join(ids)}")
        for label, ids, new_ids in self.partial:
            if ids:
                print(f"[run] partial: {label} kept previous data for "
                      f"{len(ids)} venue(s): {', '.join(ids)}")
            if new_ids:
                print(f"[run] partial: {label} has {len(new_ids)} venue(s) that have "
                      f"never produced a showtime: {', '.join(new_ids)}")

        print(summary_line(self.names, self.venues, self.shows, self.partial,
                           self.pendings, self.empty, self.failures))

    def code(self):
        """`not venues` is still a failure, because a run that wrote nothing and cannot
        say why is the case this whole check exists for. It stops being one only when every
        site said so itself -- an empty listing, every venue confirmed empty, or no sites on
        this half at all."""
        return 1 if self.failures or (not self.venues and not self.empty
                                      and not self.pendings and not self.skipped) else 0


def main(argv) -> int:
    half = half_of(argv)
    names = (registry.modules(argv[argv.index("--where") + 1])
             if "--where" in argv else module_names(argv))
    if not names:
        print(USAGE, file=sys.stderr)
        return 2

    OUT.mkdir(exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    tally = Tally(names)
    halves = set()

    for name in names:
        try:
            mod = importlib.import_module(name)
            mod.SITES          # a module without it is unusable, and says so here
            sites = sites_for(mod, half)
        except Exception as e:
            tally.unusable(name, e)
            continue
        if not sites:
            tally.no_sites(name, half)
            continue
        halves |= venuelists.halves_of(sites)
        for label, result, error in run_sites(mod, sites, now):
            tally.site(mod, sites, label, result, error)

    write_venuelists(OUT, halves)
    tally.report(common.cache_stats(), common.throttle_stats(), common.hosts_attempted())
    return tally.code()


def write_venuelists(out, halves, stream=None):
    """Rewrite the combined venue file of each half this run fetched for, from the
    provider files as they now stand. The local wrapper runs one module per process, so
    every process rebuilds the whole local file and the last one leaves it matching every
    local provider file. A failure is printed and the run goes on: the per-provider files
    are already written and the client falls back to them."""
    for h in sorted(halves):
        try:
            if venuelists.write(out, h):
                print(f"[run] {venuelists.path_for(out, h).name} rewritten", file=stream)
        except Exception as e:          # noqa: BLE001 -- printed; the fallback holds
            print(f"[run] {venuelists.path_for(out, h).name} not written: {e!r}",
                  file=stream or sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
