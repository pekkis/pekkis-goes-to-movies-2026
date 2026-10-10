#!/usr/bin/env python3
"""Mirror hot-linked posters into data/posters/ and rewrite the references.

A poster served from a cinema's CDN or from image.tmdb.org is a third-party request made
by the reader's browser, so those hosts see a visitor's IP on every page view. Mirroring
closes that for posters. Runs after enrichment and before build_pages, so a poster
mirrored on this run is same-origin in the pages the same run generates.

Everything is downscaled to POSTER_W. Sources range from TMDB's w342 (~25 kB) to Nexxo's
1984x2835 key art; mirrored verbatim they would add tens of megabytes to a 4 MB repo for
a tile about 130 px wide. Pillow is installed in the workflow for this only.

A poster that fails to download is logged and left hot-linked, never fatal: kinoakseli.fi
challenges datacenter IPs and fails every run by design, and a third party's uptime must
not fail the build. `tries=2` keeps that cheap. Not being able to run at all is a
different state and exits CANNOT_RUN; see the exit codes below.

Filenames are sha1(url)[:16].jpg. The sources share no id namespace, so the URL is the
only identifier common to every host.
"""

import glob
import hashlib
import io
import json
import pathlib
import sys
import time
from urllib.parse import quote, urlsplit, urlunsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

# Exit codes. A missing Pillow reported as OK once left every reference remote and every
# tile a placeholder while the step reported success. 3 because 1 already means a crash
# and 2 is the usage error.
#
#   OK           ran; posters that failed to download are logged
#   CANNOT_RUN   cannot downscale at all; nothing attempted, nothing changed
#   1            uncaught traceback
OK = 0
CANNOT_RUN = 3

POSTER_DIR = pathlib.Path("data/posters")
POSTER_W = 342          # what TMDB already serves and what the client renders from
JPEG_Q = 82
MIN_BYTES = 500         # anything smaller is an error page, not an image
PAUSE = 0.3             # these are other people's CDNs
HEADERS = {"user-agent": common.UA, "accept": "image/*,*/*"}


def key_for(url: str) -> str:
    """Keyed on the URL as the provider published it, not the percent-encoded form: the
    JSON reference carries the published string, and encoding first would rename every
    poster when the encoder changes."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def request_url(url: str) -> str:
    """Percent-encode the path and query for urllib.

    Nexxo publishes filenames with spaces ("SPA WEEKEND_BLACK BEAR_POSTER_70x100_FINLAND.jpg"),
    which urllib rejects as a control character instead of encoding.
    """
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%:@"),
                       quote(p.query, safe="=&%"), ""))


def collect(docs):
    """Every distinct http(s) poster URL currently referenced."""
    urls = set()
    for _, shows in docs:
        for s in shows:
            u = (s.get("img") or "").strip()
            if u.startswith("http"):
                urls.add(u)
    return urls


def area_docs():
    for p in sorted(glob.glob("data/area-*.json")):
        try:
            doc = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[mirror] skip {p}: {e}")
            continue
        yield p, doc


def download(url: str, dest: pathlib.Path) -> bool:
    from PIL import Image
    raw = common.fetch(request_url(url), headers=HEADERS, tries=2, backoff=3, timeout=20)
    if len(raw) < MIN_BYTES:
        raise RuntimeError(f"{len(raw)} bytes")
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if im.width > POSTER_W:
        h = round(im.height * POSTER_W / im.width)
        im = im.resize((POSTER_W, h), Image.LANCZOS)
    tmp = dest.with_name(dest.name + ".tmp")
    im.save(tmp, "JPEG", quality=JPEG_Q, optimize=True)
    tmp.replace(dest)
    return True


def pillow_problem() -> str:
    """Can Pillow downscale and encode a JPEG? -> '' if yes, else why not.

    An import check is not enough: `from PIL import Image` succeeds on an install whose
    imaging library is incomplete, and then every download raises inside its own try and
    counts as a download failure. This does a 4x6 pixel round trip through the calls
    `download` makes: open a paletted image, convert, resize with LANCZOS, save as JPEG.

    Missing and broken get different messages because they need different fixes.
    """
    try:
        from PIL import Image
    except Exception as e:
        return (f"Pillow is not installed for this interpreter ({type(e).__name__}). "
                "Install it with: python3 -m pip install pillow.")
    try:
        im = Image.new("P", (4, 6)).convert("RGB").resize((2, 3), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
        if not buf.getbuffer().nbytes:
            raise RuntimeError("the JPEG encoder returned no bytes")
    except Exception as e:
        return (f"Pillow is installed but cannot encode a JPEG ({type(e).__name__}: "
                f"{e}). Its imaging library is probably incomplete. Reinstall it with: "
                "python3 -m pip install --force-reinstall pillow.")
    return ""


def main() -> int:
    # Checked once, up front, by using Pillow rather than importing it. Without this a
    # machine that cannot downscale reports every poster as a download failure. The exit
    # is non-zero: neither caller stops on it (the cloud workflow commits data before its
    # gate, the local wrapper collects the code and carries on), so showtimes publish
    # either way and returning 0 only hid that no poster was mirrored. Nothing below runs,
    # so the data keeps the cinemas' own poster URLs, which the client does not render.
    problem = pillow_problem()
    if problem:
        print(f"[mirror] {problem} Nothing can be downscaled, so no poster can be "
              "mirrored: posters stay on the cinemas' own hosts, the client will not "
              "render them, and those films show a placeholder tile.")
        return CANNOT_RUN

    POSTER_DIR.mkdir(parents=True, exist_ok=True)

    docs = [(p, doc) for p, doc in area_docs()]
    extra_path = pathlib.Path("data/films-extra.json")
    extra = None
    if extra_path.exists():
        extra = json.loads(extra_path.read_text(encoding="utf-8"))

    urls = collect((p, doc.get("shows") or []) for p, doc in docs)
    if extra:
        for f in (extra.get("films") or {}).values():
            if isinstance(f, dict):
                u = (f.get("img") or "").strip()
                if u.startswith("http"):
                    urls.add(u)

    mapping = {}       # url -> repo-relative path
    had = fetched = 0
    failed = {}        # host -> [reason, ...]
    bytes_added = 0

    for url in sorted(urls):
        dest = POSTER_DIR / f"{key_for(url)}.jpg"
        rel = f"data/posters/{dest.name}"
        if dest.exists():
            mapping[url] = rel
            had += 1
            continue
        host = url.split("/")[2] if "//" in url else url
        try:
            download(url, dest)
        except Exception as e:
            failed.setdefault(host, []).append(f"{type(e).__name__}: {e}")
            continue
        mapping[url] = rel
        fetched += 1
        bytes_added += dest.stat().st_size
        time.sleep(PAUSE)

    # Rewrite references. A URL that failed keeps its remote address so a third party's
    # downtime cannot stop publication. Neither the app (safeAssetUrl) nor a generated
    # page (the data/posters/ check in build_pages) renders a remote poster, so those
    # films show a placeholder tile until a later run mirrors them. Only JSON-LD keeps
    # the remote URL, since a crawler is not a visitor's browser.
    rewritten = files = 0
    for p, doc in docs:
        changed = False
        for s in doc.get("shows") or []:
            u = (s.get("img") or "").strip()
            if u in mapping:
                s["img"] = mapping[u]
                changed = True
                rewritten += 1
        if changed:
            common.write_json(pathlib.Path(p), doc)
            files += 1

    if extra:
        changed = False
        for f in (extra.get("films") or {}).values():
            if isinstance(f, dict):
                u = (f.get("img") or "").strip()
                if u in mapping:
                    f["img"] = mapping[u]
                    changed = True
                    rewritten += 1
        if changed:
            common.write_films_extra(extra_path, extra)
            files += 1

    total = sum(p.stat().st_size for p in POSTER_DIR.glob("*.jpg"))
    print(f"[mirror] {len(urls)} remote poster urls: {had} already mirrored, "
          f"{fetched} downloaded (+{bytes_added // 1024} kB), "
          f"{sum(len(v) for v in failed.values())} failed")
    for host, errs in sorted(failed.items()):
        print(f"[mirror] failed {host} ({len(errs)}): {errs[0]}")
    print(f"[mirror] {rewritten} references rewritten in {files} files; "
          f"data/posters now {len(list(POSTER_DIR.glob('*')))} files, "
          f"{total // 1024} kB")
    return OK


if __name__ == "__main__":
    sys.exit(main())
