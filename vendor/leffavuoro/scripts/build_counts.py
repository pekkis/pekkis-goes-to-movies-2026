#!/usr/bin/env python3
"""Measure the repository's own counts and write them into docs/counts.md and README.

These numbers were kept by hand in IDEAS.md and re-measured twenty-two times between
2026-08 and 2026-09-21. Five of those passes shipped a wrong number: the city count, the
poster count, the page rewrite frequency, and the venue and provider counts, one of them
stated twice in one file with only one copy moved. Every figure here is a function of
`data/`, `scripts/providers/registry.py`, `sitemap.xml` and `sw.js`, so it is derived
rather than transcribed.

    python3 scripts/build_counts.py            # rewrite the block, report what moved
    python3 scripts/build_counts.py --check    # report only, write nothing
    python3 scripts/build_counts.py --posters  # print the two uncommitted figures

The city rule is `build_pages.city_of` over `build_pages.load_venues()`, reused rather
than reimplemented: Finnkino's areas carry no `city` field and the city sits in the venue
name, so a second implementation is a second place to get that wrong.

**What is committed is a pure function of the tree.** The registry, venue, city, page,
sitemap, CACHE and off-origin figures move only when code, a provider or a poster
reference changes, so `docs/counts.md` regenerates byte-identical and CI's
regeneration-drift step can check it like any other generated file.

Two figures are deliberately not committed: how many poster references exist and how many
files back them. Both move on every data run, a data run does not re-run this script --
`ci.yml`'s path filter is `index.html`, `sw.js`, `scripts/**`, `tests/**` -- and nothing
reads them. `--posters` prints them and writes nothing.

Off-origin references stay in the committed block. That figure is an invariant rather than
a measurement: `safeAssetUrl` in the client refuses a poster outside `data/posters/`, and
README's claim that posters are served from this origin rests on it being 0.

Run from the repo root.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "providers"))
import build_pages                                          # noqa: E402
import registry                                             # noqa: E402

DATA = ROOT / "data"
COUNTS = ROOT / "docs" / "counts.md"
README = ROOT / "README.md"
START = "<!-- counts:start -->"
END = "<!-- counts:end -->"

# How many adapters the "largest" row names. Enough to show the shape of the set without
# turning the row into the whole list.
TOP_ADAPTERS = 5


def _poster_refs():
    """-> (total, in shows, in films-extra, off-origin). `img` is the field in both."""
    shows = extra = off = 0
    for f in sorted(DATA.glob("area-*.json")):
        for s in json.loads(f.read_text(encoding="utf-8")).get("shows", []):
            img = s.get("img") or ""
            if img:
                shows += 1
                off += not img.startswith("data/posters/")
    films = json.loads((DATA / "films-extra.json").read_text(encoding="utf-8"))
    for entry in films.get("films", {}).values():
        img = (entry or {}).get("img") or ""
        if img:
            extra += 1
            off += not img.startswith("data/posters/")
    return shows + extra, shows, extra, off


def counts():
    """Every figure, measured. -> dict."""
    venues = build_pages.load_venues()
    cities = {build_pages.city_of(v) for v in venues}
    module_of = {p["id"]: (p["module"] or p["label"]) for p in registry.PROVIDERS}
    per_adapter = {}
    for v in venues:
        key = module_of.get(v["provider"], v["provider"])
        per_adapter[key] = per_adapter.get(key, 0) + 1
    local = [p for p in registry.PROVIDERS if p.get("where") == "local"]
    local_ids = {p["id"] for p in local}

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    urls = sitemap.count("<loc>")
    # Every language carries the same set, and the front page is none of their pages.
    pages_per_language = (urls - 1) // len(build_pages.LANGS)

    off = _poster_refs()[3]
    cache = re.search(r"leffavuoro-v\d+", (ROOT / "sw.js").read_text(encoding="utf-8"))

    return {
        "providers": len(registry.PROVIDERS),
        "venues": len(venues),
        "cities": len(cities),
        "multi_venue_cities": sum(
            1 for c in cities if sum(build_pages.city_of(v) == c for v in venues) > 1),
        "local_providers": len(local),
        "local_venues": sum(1 for v in venues if v["provider"] in local_ids),
        "per_adapter": sorted(per_adapter.items(), key=lambda kv: (-kv[1], kv[0])),
        "pages_per_language": pages_per_language,
        "sitemap_urls": urls,
        "poster_refs_off_origin": off,
        "cache": cache.group(0) if cache else "",
    }


def poster_figures():
    """The two figures that are measured and not committed. -> dict.

    They move on every data run, a data run does not re-run this script, and nothing in
    the repo or the client reads them. Committing them would put a number in a generated
    file that is behind the data beside it as often as not, and would make the drift step
    fail on any push that followed a data run.
    """
    total, in_shows, in_extra, _ = _poster_refs()
    return {
        "poster_refs": total,
        "poster_refs_shows": in_shows,
        "poster_refs_extra": in_extra,
        "mirrored_posters": sum(1 for p in (DATA / "posters").iterdir() if p.is_file()),
        "data_generated": json.loads(
            (DATA / "areas.json").read_text(encoding="utf-8"))["generated"],
    }


def block(c):
    """The generated region of docs/counts.md, markers excluded."""
    largest = ", ".join(f"`{name}` {n}" for name, n in c["per_adapter"][:TOP_ADAPTERS])
    return "\n".join([
        "",
        "| | |",
        "|---|---:|",
        f"| providers | {c['providers']} |",
        f"| venues | {c['venues']} |",
        f"| cities | {c['cities']} |",
        f"| cities with more than one venue | {c['multi_venue_cities']} |",
        f"| local providers (venues) | {c['local_providers']} ({c['local_venues']}) |",
        f"| venues per adapter, largest {TOP_ADAPTERS} | {largest} |",
        f"| generated pages per language | {c['pages_per_language']} |",
        f"| sitemap URLs | {c['sitemap_urls']} |",
        f"| off-origin poster references | {c['poster_refs_off_origin']} |",
        f"| `sw.js` CACHE | `{c['cache']}` |",
        "",
    ])


def render(text, body):
    """`text` with the marked region replaced. Raises when a marker is gone."""
    a, b = text.find(START), text.find(END)
    if a < 0 or b < 0 or b < a:
        raise RuntimeError(f"no {START}/{END} markers in the file")
    return text[:a + len(START)] + body + text[b:]


# README states four of these figures in prose. Each pattern is anchored on words either
# side so it cannot match a number somewhere else, and each must match exactly once: a
# rewording that breaks an anchor is reported rather than silently skipped, which is the
# failure this generator exists to prevent.
def readme_rules(c):
    ones = {1: "one", 2: "two", 14: "fourteen", 17: "seventeen", 20: "twenty"}
    words = ones.get(c["multi_venue_cities"], str(c["multi_venue_cities"]))
    return [
        (r"(Showtimes for )\d+( venues in )\d+( cities across )\d+( providers)",
         rf"\g<1>{c['venues']}\g<2>{c['cities']}\g<3>{c['providers']}\g<4>"),
        (r"(its )\d+( cities and those regions)", rf"\g<1>{c['cities']}\g<2>"),
        (r"\d+( per language, )\d+( sitemap URLs: )\d+( venues plus the )\w+( cities)",
         rf"{c['pages_per_language']}\g<1>{c['sitemap_urls']}\g<2>{c['venues']}"
         rf"\g<3>{words}\g<4>"),
        (r"(the )\d+( providers listed at the)", rf"\g<1>{c['providers']}\g<2>"),
    ]


def readme_text(text, c):
    """README with its four count sites rewritten. Raises when an anchor stopped matching."""
    for pattern, repl in readme_rules(c):
        text, n = re.subn(pattern, repl, text)
        if n != 1:
            raise RuntimeError(
                f"README anchor matched {n} times, expected 1: {pattern}. The prose "
                f"around a count changed; fix the pattern in build_counts.py rather than "
                f"editing the number by hand.")
    return text


def sync(path, new, write, label):
    """-> True when the file on disk differed."""
    old = path.read_text(encoding="utf-8")
    if old == new:
        print(f"[counts] {label} unchanged")
        return False
    if write:
        path.write_text(new, encoding="utf-8")
        print(f"[counts] {label} rewritten")
    else:
        print(f"[counts] {label} is stale: run scripts/build_counts.py")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="report what is stale and write nothing")
    ap.add_argument("--posters", action="store_true",
                    help="print the two figures that are not committed, and write nothing")
    args = ap.parse_args(argv)
    if args.posters:
        p = poster_figures()
        print(f"[posters] measured against the data snapshot of {p['data_generated']}")
        print(f"[posters] poster references: {p['poster_refs']} "
              f"({p['poster_refs_shows']} in shows / {p['poster_refs_extra']} in "
              f"films-extra)")
        print(f"[posters] mirrored poster files: {p['mirrored_posters']}")
        return 0
    c = counts()
    print(f"[counts] {c['providers']} providers, {c['venues']} venues, {c['cities']} "
          f"cities, {c['pages_per_language']} pages per language")
    sync(COUNTS, render(COUNTS.read_text(encoding="utf-8"), block(c)),
         not args.check, "docs/counts.md")
    sync(README, readme_text(README.read_text(encoding="utf-8"), c),
         not args.check, "README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
