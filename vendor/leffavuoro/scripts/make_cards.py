#!/usr/bin/env python3
"""Generate Leffavuoro's own title cards for films that have no poster we may publish.

**These are editorial illustrations, not posters.** Nothing here is the distributor's
artwork, nothing is derived from it, and none of it may be presented as an official
poster. The card is an abstract background this repository draws from a seed, with the
film's published title set over it in Archivo. A reader sees a titled card instead of a
two-letter initials tile; a cinema sees nothing of theirs republished.

Why this exists. Heureka's planetarium films carry no TMDB record and no poster this
repository is licensed to mirror: Heureka's FAQ licenses none of its promotional
artwork, and public availability is not permission. That left three of its four films
drawing initials tiles. Asking for written permission stays the way to publish Heureka's
*own* artwork and is unaffected by this; these cards are what the site shows in the
meantime, and they are ours to publish because we made them.

What the art may and may not be, as a rule rather than as this run's taste:

- **Abstract only.** Colour fields, gradients, geometry and noise. No representational
  figure, no character, no logo, no lettering inside the art layer, and nothing drawn in
  a named artist's or studio's manner. The theme enters only as a palette and a motif
  ("space", "forest"), never as a depiction of the film.
- **Deterministic.** Every card is a pure function of its title and a fixed seed, so a
  regeneration produces the same bytes and a reviewer can reproduce what shipped. There
  is no model, no external service and no network call in this script.
- **Typography is not art direction.** The title is set from the published string with
  no editing, no translation and no abbreviation, in the same Archivo the site serves.

Where they live. `data/posters/`, with a `card-` prefix, and not a directory of their
own: the client loads an image only from `data/posters/` (`ASSET_DIR` in index.html) and
build_pages.py drops any reference outside it, both of them guards against a third-party
request. A card in `data/cards/` would have been silently refused by one and dropped by
the other. The prefix is what separates our work from the mirrored files, named by the
sha1 of the source URL (Finnkino's by its image UUID), and it is what the README's licence
note points at.

Readability is the constraint that sets the layout. The smallest the client draws a
poster is about 72x104 px, so the card is designed at 342x513 (the 2:3 the rest of the
posters use, at mirror_posters.POSTER_W) and checked by downscaling to 72 px wide. At
that size a title line is about ten pixels tall, which is why the type is heavy, the
lines are few and a scrim guarantees contrast rather than the background being trusted
to provide it.

Run it by hand; nothing in the pipeline calls it. It needs Pillow and fontTools, neither
of which the pipeline itself requires:

    .venv/bin/python scripts/make_cards.py            # write the cards
    .venv/bin/python scripts/make_cards.py --check    # verify the committed ones match
"""
import argparse
import hashlib
import io
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "fonts" / "archivo-latin.woff2"
OUT = ROOT / "data" / "posters"   # the only directory the client will load from

W, H = 342, 513                 # 2:3, the width mirror_posters downscales posters to
THUMB_W = 72                    # the smallest the client draws one
MARGIN = 34                     # 10% safe area, all four sides
MAX_LINES = 3

# One entry per film. `slug` names the file, `theme` picks the palette and motif, and
# `title` is the string the adapter publishes, character for character: the card is
# mapped onto that title and a mismatch means no card is shown rather than a wrong one.
CARDS = [
    {"slug": "card-heureka-asteroid-quest", "title": "Asteroid Quest", "theme": "space"},
    {"slug": "card-heureka-metsan-sydan", "title": "Metsän sydän", "theme": "forest"},
    {"slug": "card-heureka-the-stellars", "title": "The Stellars - Tähtijengi", "theme": "stars"},
]

# Palettes are stated rather than sampled, so a change to one is visible in the diff.
# Each is (top, bottom) for the base field plus the motif's ink; all are dark enough that
# white type clears 7:1 before the scrim is applied at all.
THEMES = {
    "space":  {"top": (14, 20, 48), "bottom": (6, 8, 20), "ink": (86, 132, 214)},
    "forest": {"top": (12, 42, 32), "bottom": (5, 16, 13), "ink": (78, 156, 108)},
    "stars":  {"top": (44, 18, 58), "bottom": (14, 7, 24), "ink": (198, 128, 196)},
}


def seed_for(title):
    """A fixed seed per title, so the same title always draws the same card."""
    return int(hashlib.sha256(title.encode("utf-8")).hexdigest()[:16], 16)


def font_bytes():
    """The site's Archivo, as a TTF Pillow can open. -> bytes.

    The repository stores woff2 because that is what the browser wants; FreeType does
    not read woff2, so it is decompressed here rather than a second copy of the same
    font being committed.
    """
    from fontTools.ttLib import TTFont
    f = TTFont(str(FONT))
    f.flavor = None
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()


def load_font(raw, size, weight=800, width=100):
    from PIL import ImageFont
    fo = ImageFont.truetype(io.BytesIO(raw), size)
    fo.set_variation_by_axes([float(weight), float(width)])
    return fo


def base_field(img, theme):
    """A vertical gradient, drawn per row so there is no interpolation to argue about."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    top, bottom = theme["top"], theme["bottom"]
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))


def motif(img, theme, name, rng):
    """The abstract layer. Geometry and noise only; nothing here depicts anything."""
    from PIL import Image, ImageDraw, ImageFilter
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ink = theme["ink"]

    if name == "space":
        # Concentric arcs off a centre that sits outside the frame, plus a few discs.
        cx, cy = W * 1.15, H * 0.30
        for i in range(7):
            r = 150 + i * 78
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink + (70 - i * 7,),
                      width=2 + (i % 2))
        for _ in range(9):
            r = rng.randint(6, 46)
            x, y = rng.randint(-10, W), rng.randint(0, int(H * 0.62))
            d.ellipse([x - r, y - r, x + r, y + r], fill=ink + (rng.randint(40, 105),))
    elif name == "forest":
        # Vertical bands of varying width and opacity, and a soft canopy light.
        x = -20
        while x < W + 20:
            w = rng.randint(10, 46)
            d.rectangle([x, 0, x + w, H], fill=ink + (rng.randint(18, 64),))
            x += w + rng.randint(8, 40)
        gx, gy, gr = W * 0.34, H * 0.16, 190
        for i in range(gr, 0, -14):
            d.ellipse([gx - i, gy - i, gx + i, gy + i],
                      fill=(255, 255, 255, max(1, int(11 * (1 - i / gr)))))
    elif name == "stars":
        # A star field over a wide diagonal sweep.
        d.polygon([(-40, H * 0.52), (W + 40, H * 0.20), (W + 40, H * 0.40),
                   (-40, H * 0.72)], fill=ink + (54,))
        for _ in range(150):
            x, y = rng.randint(0, W), rng.randint(0, int(H * 0.70))
            r = rng.choice((1, 1, 1, 2, 2, 3))
            a = rng.randint(70, 235)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, a))

    layer = layer.filter(ImageFilter.GaussianBlur(0.4))
    img.alpha_composite(layer)


def grain(img, rng):
    """A little noise, so the flat areas do not band when the card is re-encoded."""
    from PIL import Image
    px = bytearray()
    for _ in range(W * H):
        v = rng.randint(0, 14)
        px += bytes((v, v, v, 16))
    img.alpha_composite(Image.frombytes("RGBA", (W, H), bytes(px)))


def scrim(img):
    """Contrast that does not depend on what the motif happened to draw.

    The type sits in the lower half, so the scrim is transparent across the top, ramps
    through the middle and is near-solid under the text. Without it a light patch of the
    motif could land behind a line and take it below the contrast the smallest size
    needs.
    """
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    start = int(H * 0.30)
    for y in range(start, H):
        t = (y - start) / (H - start - 1)
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(238 * (t ** 1.35))))
    img.alpha_composite(layer)


# A separator standing alone between two words. Greedy wrapping is happy to leave one
# at the end of a line -- "The Stellars -" over "Tahtijengi" -- which reads as a broken
# word rather than as the dash the cinema wrote. It is carried down to the next line
# instead. The published title is never edited; only where it breaks is decided here.
SEPARATORS = ("-", "\u2013", "\u2014", "/", "|", ":")


def wrap(title, raw, size, max_w):
    """Greedy wrap on spaces. -> lines, or None when a word cannot fit the safe area."""
    fo = load_font(raw, size)
    words, lines, cur = title.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if fo.getbbox(trial)[2] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for i in range(len(lines) - 1):
        parts = lines[i].split()
        if len(parts) > 1 and parts[-1] in SEPARATORS:
            lines[i] = " ".join(parts[:-1])
            lines[i + 1] = f"{parts[-1]} {lines[i + 1]}"
    if any(fo.getbbox(l)[2] > max_w for l in lines):
        return None
    return lines


def fit(title, raw):
    """The largest size whose wrap stays within the safe area and MAX_LINES."""
    best = None
    for size in range(78, 21, -1):
        lines = wrap(title, raw, size, W - 2 * MARGIN)
        if lines and len(lines) <= MAX_LINES:
            best = (size, lines)
            break
    if not best:
        raise SystemExit(f"cannot set {title!r} in {MAX_LINES} lines inside the safe area")
    return best


def draw_title(img, title, raw):
    from PIL import ImageDraw
    size, lines = fit(title, raw)
    fo = load_font(raw, size)
    d = ImageDraw.Draw(img)
    lead = int(size * 1.06)
    block = lead * len(lines)
    y = H - MARGIN - block
    eyebrow = load_font(raw, 15, weight=700, width=100)
    d.text((MARGIN, y - 30), "LEFFAVUORO", font=eyebrow, fill=(255, 255, 255, 165))
    for line in lines:
        d.text((MARGIN, y), line, font=fo, fill=(255, 255, 255, 255))
        y += lead
    return size, lines


def render(card, raw):
    from PIL import Image
    rng = random.Random(seed_for(card["title"]))
    theme = THEMES[card["theme"]]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    base_field(img, theme)
    motif(img, theme, card["theme"], rng)
    grain(img, rng)
    scrim(img)
    size, lines = draw_title(img, card["title"], raw)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=88, optimize=True, progressive=False)
    return buf.getvalue(), size, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare against the committed files instead of writing")
    args = ap.parse_args()
    try:
        raw = font_bytes()
    except ImportError:
        print("make_cards needs fontTools and Pillow; neither is a pipeline dependency",
              file=sys.stderr)
        return 3
    OUT.mkdir(parents=True, exist_ok=True)
    drift = 0
    for card in CARDS:
        data, size, lines = render(card, raw)
        dest = OUT / f"{card['slug']}.jpg"
        if args.check:
            same = dest.exists() and dest.read_bytes() == data
            drift += 0 if same else 1
            print(f"[cards] {dest.name}: {'matches' if same else 'DIFFERS'}")
            continue
        dest.write_bytes(data)
        print(f"[cards] {dest.name}: {len(data)//1024} kB, {size}px over "
              f"{len(lines)} line(s) -- {' / '.join(lines)}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
