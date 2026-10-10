"""One file per half holding every provider's venue list as committed.

    data/venuelists-local.json    written by the local half (run.py on the laptop)
    data/venuelists-cloud.json    written by the cloud half (run_cloud.py on Actions)

The client read one `data/venues-{id}.json` per provider on every load: 82 requests and,
through the service worker, 82 revalidations for 25 KiB of data (docs/research/cold-load.md).
Each file here is `{"half": ..., "providers": {id: <that provider's file, verbatim>}}`,
built from the per-provider files on disk, which stay written and stay the client's
fallback.

One file per half, because each half is the only writer of its providers' files. A local
commit touches only the local file and a cloud commit only the cloud one, so neither can
conflict on the other's, and neither lags the other: the local half's venues and `pending`
reach the client in the same commit as its per-provider files.

A half's file lists the registry's providers with that `where` that have a file on disk.
Finnkino is not in either: its list is `areas.json`, in its own shape. A per-provider file
that does not parse is left out, and the client fetches it on its own, as before.
"""
import json
import pathlib

import common
import registry

HALVES = ("local", "cloud")


def path_for(out, half):
    return pathlib.Path(out) / f"venuelists-{half}.json"


def providers_of(half):
    """The registry's providers in `half` that publish a venue file. -> sorted ids."""
    return sorted(p["id"] for p in registry.PROVIDERS
                  if p.get("where") == half and p.get("module"))


def build(out, half):
    """The combined document for `half` from the files in `out`. -> dict, or None when
    no provider of that half has a file there."""
    lists = {}
    for pid in providers_of(half):
        f = pathlib.Path(out) / f"venues-{pid}.json"
        try:
            lists[pid] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {"half": half, "providers": lists} if lists else None


def text_of(doc):
    return json.dumps(doc, ensure_ascii=False)


def write(out, half):
    """Rewrite `half`'s combined file from the files on disk. -> True when it changed.

    Written only when the bytes differ, so a run whose sites all failed, which touches no
    provider file, touches this one neither."""
    doc = build(out, half)
    if doc is None:
        return False
    p = path_for(out, half)
    text = text_of(doc)
    try:
        if p.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    common.write_text_atomic(p, text)
    return True


def halves_of(sites):
    """The halves the given SITES entries belong to, by their provider's registry entry.
    A provider the registry does not have belongs to neither."""
    out = set()
    for site in sites:
        p = registry.by_id(site.get("provider") or "")
        if p and p.get("where") in HALVES:
            out.add(p["where"])
    return out
