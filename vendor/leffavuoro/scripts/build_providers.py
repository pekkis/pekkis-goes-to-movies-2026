#!/usr/bin/env python3
"""Write data/providers.json from scripts/providers/registry.py, and keep index.html's
offline fallback list the same set.

Offline and deterministic, so both push paths (Mac and Actions) can run it and emit
identical bytes: no rebase conflict between the two writers, and no commit at all
unless the registry changed. That is also why the file carries no
`generated` timestamp, unlike every other file in data/.

`PROV_FALLBACK` in index.html is the list the client uses when `data/providers.json`
cannot be read, and `fetchVenueLists` derives the `data/venues-{id}.json` requests from
whichever list is in force. So a short fallback does not merely lose a label: every
provider missing from it loses its venues from the picker, the health line and the chain
palette. Measured on 2026-09-14, when it held 11 of 42 entries: 31 providers and 38 of
86 venues. It is generated here from the same registry rather than kept by hand.

    python3 scripts/build_providers.py                # write data/, report on index.html
    python3 scripts/build_providers.py --sync-index   # also rewrite the fallback block

A plain run reports a stale block and still exits 0, unlike `build_pages.py --home`,
which exits 3. The difference is deliberate: biorex.yml runs this script ungated before
it fetches anything, so a non-zero exit here would abort a data run over a documentation
problem. `tests/test_prov_fallback.py` is the gate instead, and it runs in CI on every
push that touches the registry.

Run from the repo root.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "providers"))
import registry

INDEX = pathlib.Path("index.html")
START = "/* providers:start */"
END = "/* providers:end */"


def _js(value):
    """A single-quoted JS string literal for provider text.

    The registry is this repo's own file, so this is not sanitising hostile input; it
    keeps the generator honest about the two things that would break the element. A
    backslash or an apostrophe would end the literal early, and a literal `</script>`
    ends a script element whatever its type attribute says, which is the rule
    `ld_json()` in build_pages.py already follows.
    """
    out = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return "'" + out.replace("</", "<\\/") + "'"


def fallback_body(providers=None):
    """The `PROV_FALLBACK` entries, one line per provider, in registry order.

    Columns are padded so the block reads like the hand-written one it replaces; the
    padding is derived from the data, so it stays aligned as labels change.
    """
    providers = registry.frontend() if providers is None else providers
    cols = {k: max(len(_js(p[k])) for p in providers) for k in ("id", "label", "host")}
    lines = []
    for i, p in enumerate(providers):
        end = "" if i == len(providers) - 1 else ","
        lines.append(
            f"    {{ id:{_js(p['id']) + ',':<{cols['id'] + 1}} "
            f"label:{_js(p['label']) + ',':<{cols['label'] + 1}} "
            f"host:{_js(p['host']) + ',':<{cols['host'] + 1}} "
            f"accent:{_js(p['accent'])}, book:{_js(p['book'])}"
            + (f", site:{_js(p['site'])}" if p.get("site") else "") + f" }}{end}")
    return "\n".join(lines)


def index_block(html, body):
    """index.html with the marked block replaced by `body`. Raises when a marker is gone.

    Returns the whole file rather than the block, so "is it in sync" is one string
    comparison against the file on disk. Comparing the extracted region instead needed
    the surrounding newline and indent trimmed back off, and getting that wrong made the
    generator report a stale block on a file it had just written.
    """
    a, b = html.find(START), html.find(END)
    if a < 0 or b < 0 or b < a:
        raise RuntimeError("index.html has no providers:start/providers:end markers")
    return html[:a + len(START)] + "\n" + body + "\n    " + html[b:]


def sync_index(write):
    """Compare index.html against the registry; rewrite it when `write`.
    -> True when they differed."""
    html = INDEX.read_text(encoding="utf-8")
    new = index_block(html, fallback_body())
    if new == html:
        return False
    if write:
        INDEX.write_text(new, encoding="utf-8")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sync-index", action="store_true",
                    help="rewrite index.html's PROV_FALLBACK block from the registry; "
                         "bump sw.js when committing the result")
    args = ap.parse_args(argv)

    out = pathlib.Path("data")
    out.mkdir(exist_ok=True)
    path = out / "providers.json"
    body = json.dumps({"providers": registry.frontend()},
                      ensure_ascii=False, indent=1) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if body == old:
        print(f"[providers] unchanged ({len(registry.PROVIDERS)} providers)")
    else:
        path.write_text(body, encoding="utf-8")
        print(f"[providers] written ({len(registry.PROVIDERS)} providers)")

    stale = sync_index(write=args.sync_index)
    if args.sync_index:
        print(f"[providers] index.html fallback {'rewritten' if stale else 'unchanged'}")
    elif stale:
        print("[providers] index.html fallback is stale: run --sync-index and bump sw.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
