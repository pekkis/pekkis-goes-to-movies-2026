#!/usr/bin/env python3
"""Rewrite data/venuelists-local.json and data/venuelists-cloud.json from the committed
data/venues-{id}.json files.

The halves write these themselves, each its own file after each run (run.py, run_cloud.py).
This is the same function run over the committed tree, for the Checks drift step: a
combined file that disagrees with the provider files it was built from is rewritten here,
and the step fails on the diff. Offline and deterministic, no timestamp of its own.

Run from the repo root.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "providers"))
import venuelists


def main() -> int:
    out = pathlib.Path("data")
    for half in venuelists.HALVES:
        doc = venuelists.build(out, half)
        n = len(doc["providers"]) if doc else 0
        state = "rewritten" if venuelists.write(out, half) else "unchanged"
        print(f"[venuelists] {venuelists.path_for(out, half).name} {state} ({n} providers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
