#!/usr/bin/env python3
"""Measure the chain accents against each other, in normal and deuteranope vision.

Run it:

    python3 scripts/accent_check.py            # shared-view pairs, worst first
    python3 scripts/accent_check.py --all      # every pair
    python3 scripts/accent_check.py --candidate '#B47ACC' --city Helsinki,Tampere
    python3 scripts/accent_check.py --selftest # CIEDE2000 against Sharma's test data

This is the method behind the accent figures in docs/research/accent-colour.md; earlier
figures were recorded
without one and two of them disagreed. Its CIEDE2000 is checked against published
reference data on every run. Nothing in the pipeline imports it: run it by hand before
choosing an accent, and again when the set changes.

WHAT IS COMPUTED, EXACTLY
-------------------------
1. sRGB hex -> linear RGB, using the piecewise IEC 61966-2-1 transfer function, not a
   gamma-2.2 approximation.
2. Deuteranope simulation, applied to LINEAR RGB. Applying it to gamma-encoded values
   shifts the numbers a long way.
   - Primary: Vienot, Brettel & Mollon (1999), the LMS projection mainstream simulators
     implement. Full dichromacy, no severity parameter.
   - Cross-check: Machado, Oliveira & Fernandes (2009), deuteranomaly at severity 1.0.
3. Linear RGB -> CIE XYZ (sRGB primaries, D65) -> CIELAB (D65, 2 degree observer).
4. CIEDE2000 (Sharma, Wu & Dalal 2005 formulation), kL = kC = kH = 1.

A pair's separation is its dE00. For a set, the figure that matters is the minimum over
the pairs that can appear together. Two views put chains side by side: a combined city,
and a region row from registry.REGIONS. Both are checked.
"""
import argparse
import importlib
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "providers"))
import registry                                            # noqa: E402

DATA = HERE.parent / "data"


# ---------------------------------------------------------------- colour

def hex_to_srgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_to_linear(c):
    """IEC 61966-2-1 piecewise transfer function. Not gamma 2.2 -- they differ most in
    the dark end, which is where several of these accents sit."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def mat3(m, v):
    return tuple(sum(m[r][c] * v[c] for c in range(3)) for r in range(3))


# Linear sRGB (D65) -> CIE XYZ. sRGB primaries, IEC 61966-2-1.
RGB_TO_XYZ = ((0.4124564, 0.3575761, 0.1804375),
              (0.2126729, 0.7151522, 0.0721750),
              (0.0193339, 0.1191920, 0.9503041))

# Vienot, Brettel & Mollon (1999). Linear RGB -> LMS on the Smith & Pokorny cone
# fundamentals, the matrix pair used by Vischeck and everything downstream of it.
RGB_TO_LMS = ((17.8824, 43.5161, 4.11935),
              (3.45565, 27.1554, 3.86714),
              (0.0299566, 0.184309, 1.46709))
LMS_TO_RGB = ((0.080944, -0.130504, 0.116721),
              (-0.0102485, 0.0540194, -0.113615),
              (-0.000365294, -0.00412163, 0.693513))
# Deuteranope: the M cone is absent, so M is reconstructed as a fixed combination of the
# two remaining cones. L and S pass through untouched.
LMS_DEUTAN = ((1.0, 0.0, 0.0),
              (0.494207, 0.0, 1.24827),
              (0.0, 0.0, 1.0))

# Machado, Oliveira & Fernandes (2009), deuteranomaly severity 1.0, on linear RGB.
# Derived from a different starting point (a stage-based opponent model) than Vienot,
# so agreement between the two is real corroboration rather than one model restated.
MACHADO_DEUTAN_100 = ((0.367322, 0.860646, -0.227968),
                      (0.280085, 0.672501, 0.047413),
                      (-0.011820, 0.042940, 0.968881))

D65 = (0.95047, 1.00000, 1.08883)


def deutan_vienot(lin):
    lms = mat3(RGB_TO_LMS, lin)
    return mat3(LMS_TO_RGB, mat3(LMS_DEUTAN, lms))


def deutan_machado(lin):
    return mat3(MACHADO_DEUTAN_100, lin)


def lab(lin):
    """Linear RGB -> CIELAB, D65 2 degree observer."""
    x, y, z = mat3(RGB_TO_XYZ, lin)

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(max(0.0, x) / D65[0]), f(max(0.0, y) / D65[1]), f(max(0.0, z) / D65[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000(lab1, lab2, kL=1.0, kC=1.0, kH=1.0):
    """CIEDE2000, following Sharma, Wu & Dalal (2005). Checked by --selftest."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7))) if Cbar > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = 0.0 if (a1p == 0 and b1 == 0) else math.degrees(math.atan2(b1, a1p)) % 360
    h2p = 0.0 if (a2p == 0 and b2 == 0) else math.degrees(math.atan2(b2, a2p)) % 360

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)

    Lbar = (L1 + L2) / 2
    Cbarp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbarp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbarp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbarp = (h1p + h2p + 360) / 2
    else:
        hbarp = (h1p + h2p - 360) / 2

    T = (1 - 0.17 * math.cos(math.radians(hbarp - 30))
         + 0.24 * math.cos(math.radians(2 * hbarp))
         + 0.32 * math.cos(math.radians(3 * hbarp + 6))
         - 0.20 * math.cos(math.radians(4 * hbarp - 63)))
    dtheta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    RC = 2 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7)) if Cbarp > 0 else 0.0
    SL = 1 + (0.015 * (Lbar - 50) ** 2) / math.sqrt(20 + (Lbar - 50) ** 2)
    SC = 1 + 0.045 * Cbarp
    SH = 1 + 0.015 * Cbarp * T
    RT = -math.sin(math.radians(2 * dtheta)) * RC

    return math.sqrt((dLp / (kL * SL)) ** 2 + (dCp / (kC * SC)) ** 2
                     + (dHp / (kH * SH)) ** 2
                     + RT * (dCp / (kC * SC)) * (dHp / (kH * SH)))


def labs_for(hexcolour):
    """-> (normal, vienot deutan, machado deutan) CIELAB triples for one hex colour."""
    lin = tuple(srgb_to_linear(c) for c in hex_to_srgb(hexcolour))
    return lab(lin), lab(deutan_vienot(lin)), lab(deutan_machado(lin))


def dE(a, b):
    """-> (normal, vienot, machado) dE00 between two hex colours."""
    la, lb = labs_for(a), labs_for(b)
    return tuple(ciede2000(la[i], lb[i]) for i in range(3))


# ---------------------------------------------------------------- the set

def cities_by_provider():
    """-> {provider_id: {city, ...}} measured from the committed data, not listed here.

    Finnkino keeps the legacy areas.json shape with no city field; its venue names end
    in the city, which is the same rule the client's picker uses.
    """
    out = {}
    for f in sorted(DATA.glob("venues-*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        pid = doc.get("provider") or f.stem.replace("venues-", "")
        for v in doc["venues"]:
            out.setdefault(pid, set()).add(v["city"])
    areas = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]
    out["finnkino"] = {a["name"].split()[-1] for a in areas}
    return out


def cities_declared_by_adapters():
    """-> {provider_id: {city, ...}} from every adapter's SITES.

    A provider is registered one commit and fetched the next, so for that window it has
    no data/venues-{id}.json and its cities exist only in the adapter. Without this an
    accent would be chosen against an incomplete set on the one day it is being chosen.

    The adapters are imported here rather than at module level. A provider module
    imported before tests/test_common_fetch.py reloads `common` is left holding a stale
    EmptyProgramme, which turns unrelated tests red.
    """
    out = {}
    for name in registry.modules():
        mod = importlib.import_module(name)
        for site in mod.SITES:
            for v in site["venues"]:
                out.setdefault(site["provider"], set()).add(v["city"])
    return out


def provider_cities():
    """-> {provider_id: {city, ...}} from the committed data and the adapters together."""
    out = {pid: set(cs) for pid, cs in cities_by_provider().items()}
    for pid, cs in cities_declared_by_adapters().items():
        out.setdefault(pid, set()).update(cs)
    return out


def view_pairs(extra=None):
    """-> [(kind, label, a, b)] for every pair of providers that can appear in one list.

    Two views put chains side by side, and the 3 px rule has to survive both:

    - a combined city, where every chain in that town is listed together;
    - a region row, where every chain in any of the region's cities is listed together.

    `kind` is "city" or "region" and `label` is the city or the region name. The two are
    keyed apart, so a region that happened to carry a city's name would still be its own
    view rather than merging with the city's pairs under one label. The regions come from
    registry.REGIONS, so there is no second list to maintain. A city inside a region
    yields pairs under both views, which is correct: they are two lists a reader can open.

    `extra` adds a hypothetical (id, cities) so a candidate accent can be tested before
    it is committed, and the regions it lands in follow from those cities.

    `cities` is a sequence, not a string. A chain that lands in two cities has to clear
    the existing accents in *both*, and taking only the first is how a tool like this
    approves a colour that collides one town over. A bare string is the common slip; it is
    accepted and wrapped rather than iterated, since iterating one would silently test
    the letters of the city name.
    """
    by = provider_cities()
    if extra:
        pid, cities = extra
        if isinstance(cities, str):
            cities = [cities]
        by.setdefault(pid, set()).update(cities)

    views = {}
    for pid, cs in by.items():
        for city in cs:
            views.setdefault(("city", city), set()).add(pid)
    for r in registry.REGIONS:
        member_cities = set(r["cities"])
        here = {pid for pid, cs in by.items() if cs & member_cities}
        if here:
            views.setdefault(("region", r["name"]), set()).update(here)

    pairs = []
    for kind, label in sorted(views):
        here = sorted(views[(kind, label)])
        for i in range(len(here)):
            for j in range(i + 1, len(here)):
                pairs.append((kind, label, here[i], here[j]))
    return pairs


def shared_view_pairs(extra=None):
    """-> [(label, a, b)]: view_pairs without the kind, which is what the report prints."""
    return [(label, a, b) for _, label, a, b in view_pairs(extra)]


# ---------------------------------------------------------------- selftest

# Sharma, Wu & Dalal (2005), "The CIEDE2000 Color-Difference Formula: Implementation
# Notes ...", Table 1. The pairs chosen here are the ones that exercise the parts an
# implementation gets wrong: the hue-difference wrap, the arithmetic-mean-hue branch,
# and the RT rotation term near hue 275.
SHARMA = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


def selftest():
    bad = 0
    for l1, l2, want in SHARMA:
        got = ciede2000(l1, l2)
        ok = abs(got - want) < 1e-4
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'}  want {want:8.4f}  got {got:8.4f}")
    # A colour is unchanged by its own comparison, and a grey is unchanged by any
    # dichromat simulation -- the confusion line runs through the neutral axis.
    assert dE("#E4551F", "#E4551F") == (0.0, 0.0, 0.0)
    g = labs_for("#808080")
    assert max(ciede2000(g[0], g[i]) for i in (1, 2)) < 1.0, "grey moved under simulation"
    print(f"\n{len(SHARMA) - bad}/{len(SHARMA)} CIEDE2000 reference pairs match")
    return 1 if bad else 0


# ---------------------------------------------------------------- report

def row(label, a, b, n, v, m):
    return (f"{n:7.1f} {v:7.1f} {m:7.1f}   {label:<26} {a:<14} {b}")


# L* window for the 3 px border. Below ~38 the rule disappears against the dark theme,
# above ~60 it washes out against the light one. Inherited from the Engel search, which
# is the one constraint in the old notes that did not depend on the broken metric.
L_MIN, L_MAX = 38.0, 60.0

# The policy floor, in dE00 on the weakest of the three models. A new or changed accent
# clears it in every view it enters where that is reachable, and no combined-city pair sits
# below it. Fixed rather than measured: it is the number CLAUDE.md and the registry state,
# and tests/test_accent_check.py pins the value and the city-view contract separately from
# the count the report prints against it. Region rows are measured on the same scale and
# twelve established pairs sit below; docs/research/accent-colour.md lists them.
FLOOR = 14.4


def separation_labs(x, y):
    """-> the dE00 a pair offers: the minimum across normal vision and both deuteranope
    models.

    The one scorer. A pair separates only as well as its weakest model, and that model is
    as often normal vision as it is either simulation: Bio Grani and Gilda are 19.9 apart
    to a deuteranope and 14.1 to everyone else. Ranking or counting on the deutan figure
    alone hides exactly that pair, so the reports and `search` both come through here.
    """
    return min(ciede2000(x[i], y[i]) for i in range(3))


def separation(a, b):
    """-> separation_labs for two hex colours."""
    return separation_labs(labs_for(a), labs_for(b))


def worst_labs(cand, fixed):
    """-> (overall, normal, deutan) minimum dE00 from one labs triple to any of `fixed`.

    `overall` is the score the reports rank on, taken over every rival.
    """
    overall = min(separation_labs(cand, f) for f in fixed)
    normal = min(ciede2000(cand[0], f[0]) for f in fixed)
    deutan = min(min(ciede2000(cand[i], f[i]) for i in (1, 2)) for f in fixed)
    return overall, normal, deutan


def worst_against(hexcolour, fixed):
    """-> (overall, normal, deutan) for one hex colour against `fixed`, a list of
    labs_for() triples."""
    return worst_labs(labs_for(hexcolour), fixed)


def search(pid, accents, step=6, top=12):
    """Best replacement accents for one provider.

    -> ([(worst_overall, worst_normal, worst_deutan, hex)], rivals), ranked by
    `worst_overall` descending.

    Maximises the *minimum* separation against the chains that share a city or a region
    with this one, because the minimum is what a reader has to resolve. That minimum is
    taken across normal vision and both deuteranope models together. Ranking on the
    deutan figure alone promotes a colour whose normal-vision separation is the binding
    constraint. Chains this one never appears beside are unconstrained.
    """
    rivals = sorted({b if a == pid else a
                     for _, a, b in shared_view_pairs() if pid in (a, b)})
    if not rivals:
        return [], rivals
    fixed = [labs_for(accents[r]) for r in rivals]
    out = []
    for r in range(0, 256, step):
        for g in range(0, 256, step):
            for b in range(0, 256, step):
                h = f"#{r:02X}{g:02X}{b:02X}"
                cand = labs_for(h)
                if not (L_MIN <= cand[0][0] <= L_MAX):
                    continue
                wo, wn, wd = worst_labs(cand, fixed)
                out.append((wo, wn, wd, h))
    out.sort(reverse=True)
    return out[:top], rivals


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="every pair in the set, not only pairs that share a view")
    ap.add_argument("--candidate", metavar="HEX",
                    help="test a hypothetical accent before committing it")
    ap.add_argument("--city", metavar="CITY", default=None,
                    help="city or cities the candidate would appear in, comma separated;"
                         " it is measured against the existing chains in every one and"
                         " in every region those cities belong to")
    ap.add_argument("--search", metavar="PROVIDER_ID",
                    help="best replacement accent for one chain, against every chain it"
                         " shares a city or a region with")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    accents = {p["id"]: p["accent"] for p in registry.PROVIDERS}
    labels = {p["id"]: p["label"] for p in registry.PROVIDERS}
    extra = None
    if args.candidate:
        if not args.city:
            ap.error("--candidate needs --city")
        accents["candidate"] = args.candidate
        labels["candidate"] = f"CANDIDATE {args.candidate}"

    if args.search:
        accents = {p["id"]: p["accent"] for p in registry.PROVIDERS}
        labels = {p["id"]: p["label"] for p in registry.PROVIDERS}
        if args.search not in accents:
            ap.error(f"unknown provider id: {args.search}")
        best, rivals = search(args.search, accents)
        if not rivals:
            print(f"{labels[args.search]} shares no city or region with another chain, "
                  f"so its accent is unconstrained. Nothing to search.")
            return 0
        fixed = [labs_for(accents[r]) for r in rivals]
        co, cn, cd = worst_against(accents[args.search], fixed)
        print(f"{labels[args.search]} shares a city or region with: "
              f"{', '.join(labels[r] for r in rivals)}")
        print(f"current {accents[args.search]}: worst overall {co:.1f} "
              f"(normal {cn:.1f}, deutan {cd:.1f})\n")
        print(f"best candidates in L* {L_MIN:.0f}-{L_MAX:.0f}, ranked by worst overall:")
        print("  hex       worst overall  worst normal  worst deutan")
        for wo, wn, wd, h in best:
            print(f"  {h}   {wo:12.1f}   {wn:11.1f}   {wd:11.1f}")
        return 0

    print("dE00 between chain accents. Higher is more separable; the number that")
    print("matters for a set is the smallest one, since that is the pair a reader")
    print("has to tell apart. Deutan columns are full dichromacy.\n")
    print(" normal  vienot machado   where                      chain          chain")
    print(" " + "-" * 84)

    if args.all:
        ids = sorted(accents)
        rows = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = accents[ids[i]], accents[ids[j]]
                n, v, m = dE(a, b)
                rows.append((separation(a, b), row("(any)", labels[ids[i]],
                                                   labels[ids[j]], n, v, m)))
        for _, line in sorted(rows):
            print(line)
        worst = min(r[0] for r in rows)
        print(f"\nglobal minimum over all pairs: {worst:.1f} dE00 "
              f"(minimum across the three models)")
        return 0

    cities = [c.strip() for c in (args.city or "").split(",") if c.strip()]
    if cities:
        extra = ("candidate", cities)

    rows = []
    for view, a, b in shared_view_pairs(extra):
        n, v, m = dE(accents[a], accents[b])
        rows.append((separation(accents[a], accents[b]), view,
                     row(view, labels[a], labels[b], n, v, m)))
    if not rows:
        print("no city or region has two chains in it")
        return 0
    for _, _, line in sorted(rows):
        print(line)

    worst = sorted(rows)[0]
    below = sum(1 for r in rows if r[0] < FLOOR)
    print(f"\nworst shared-view pair: {worst[0]:.1f} dE00 across the three models, "
          f"in {worst[1]}")
    print(f"{below} of {len(rows)} pairs are below {FLOOR}")
    print("L* of each accent (the 3 px rule needs this legible on both themes):")
    for pid in sorted(accents):
        print(f"  {labels[pid]:<26} {accents[pid]}  L* {labs_for(accents[pid])[0][0]:5.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
