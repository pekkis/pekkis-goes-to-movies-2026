#!/usr/bin/env python3
"""Write data/regions.json from scripts/providers/registry.py.

Same contract as build_providers.py: offline, deterministic, no `generated` timestamp, so
both push paths emit identical bytes and nothing is committed unless the registry changed.

The client treats the file as optional. Without it the picker is exactly what it was
before areas existed, which is what an old service worker or a first deploy will serve.

Run from the repo root.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "providers"))
import registry


def main() -> int:
    out = pathlib.Path("data")
    out.mkdir(exist_ok=True)
    path = out / "regions.json"
    body = json.dumps({"regions": registry.regions()},
                      ensure_ascii=False, indent=1) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if body == old:
        print(f"[regions] unchanged ({len(registry.REGIONS)} regions)")
        return 0
    path.write_text(body, encoding="utf-8")
    print(f"[regions] written ({len(registry.REGIONS)} regions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
