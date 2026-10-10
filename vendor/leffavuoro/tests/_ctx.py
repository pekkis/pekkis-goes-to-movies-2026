"""Import path for the tests. `unittest discover` puts this directory on sys.path.

The pipeline modules live in scripts/providers and import each other by bare name,
because run.py and fetch_data.py put that directory first on sys.path at runtime. The
tests have to reproduce that or every `import common` inside an adapter fails.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

for p in (ROOT / "scripts" / "providers", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
