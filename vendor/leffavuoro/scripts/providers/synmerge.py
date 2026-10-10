"""Shared helper: merge provider-supplied synopses into films-extra.json.

Providers run before the TMDB pass and their own text is better, so this only ever
fills an empty slot — it never clobbers.

**A synopsis carries a language since 2026-09-16.** `_syn` is either the bare string every
adapter published before that, which is Finnish, or a `{lang: text}` mapping for an adapter
that knows what it is publishing. Bio Savoy is the first: Åland's only official language is
Swedish and its film pages carry a native Swedish blurb, which put into the Finnish slot
would be served as Finnish to every cinema showing that film, because the slot is keyed by
normalised title and shared across chains.

Each language is merged **on its own**. A Swedish text from site 3 does not settle the
Finnish slot, and a Finnish text already in the file does not stop a Swedish one arriving:
the fill-if-empty rule and the SITES-order tie-break below both apply per language.
"""
import html as html_mod
import json, pathlib, re, sys, threading

import common

# A film synopsis never quotes a ticket price. Text that does is a screening note --
# "Elokuvaliput seniorikinon näytöksiin saat hintaan 9€/kpl", "Liput 8€ maksetaan
# Pennittömien edustajalle" -- and it describes one cinema's screening, so it must not
# reach the slot every cinema showing the film reads from.
PRICE_RE = re.compile(r"\d\s*(?:€|eur\b|euroa\b)|€\s*\d", re.I)
# Two unpriced shapes that reached the shared slot (read 2026-10-04): Savon Kinot ends
# each note with "||" ("Ensi-iltapaikkakunnat: Joensuu, ... ja Kitee ||"), and a filmmaker's
# visit is one screening ("Niagarassa tekijävierailunäytös tiistaina 4.8. klo 18.30").
# Kino Iiris heads its Polish film weekend with three lines (Junat, read 2026-10-04):
# "VAPAA PÄÄSY!", "Näytökseen ei voi varata lippuja etukäteen.", "Vain englanninkieliset
# tekstitykset." The first and last are whole paragraphs; booking tickets is no synopsis.
NOTE_RE = re.compile(r"\|\||tekijävierailu|\bvarata lippuja\b|^vapaa pääsy[!.]?$"
                     r"|^vain [a-zåäö]+kieliset tekstitykset\.?$", re.I)
_TAGS = re.compile(r"<[^>]+>")


# Sentences about one cinema's screening rather than the film, each read 2026-10-04 in a
# shared slot: free entry (Järven ääni, Filminor, Käpy selän alla), booking (Järven ääni),
# when and with whom it is held (El espíritu de la colmena, Filminor), a free screening
# announced (El espíritu, Käpy, Vanhustenviikon näytös), admission to a guest's talk
# (Casper, Ghost), a voluntary fee (Anttilanmäen kyläjuhla), and the same in English.
# A whole sentence goes and the rest of the text stays. Sentences part where a stop meets
# a capital, except before "KLO 17:00", which is the end of a date, and also before
# "Näytös järjestetään", which Orion ran on after a quote's attribution with no stop
# ("... – Erkki Lähde 2026 Näytös järjestetään ke 30.9. klo 17:15 ...", read 2026-10-05).
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c5\u00c4\u00d6\"\u201c\u201d])"
                         r"(?![Kk][Ll][Oo]\s*\d)"
                         r"|\s+(?=N\u00e4yt\u00f6s\s+j\u00e4rjestet\u00e4\u00e4n\s)")
NOTE_SENTENCES = tuple(re.compile(p, re.I) for p in (
    r"^(?:huom!?\s+)?(?:n\u00e4yt\u00f6kseen|elokuvaan|tapahtumaan|tilaisuuteen)"
    r"\s+on\s+vapaa\s+p\u00e4\u00e4sy\b",
    r"^vapaa\s+p\u00e4\u00e4sy\s*[!.]*$",
    r"^(?:huom!?\s+)?n\u00e4yt\u00f6kseen\s+ei\s+voi\s+varata\b",
    r"^n\u00e4yt\u00f6s\s+j\u00e4rjestet\u00e4\u00e4n\s+(?:yhteisty\u00f6ss\u00e4\b"
    r"|(?:ma|ti|ke|to|pe|la|su)\s+\d{1,2}\.\d{1,2}\.)",
    r"\bilmaisn\u00e4yt\u00f6",
    r"\bmaksuton\s+n\u00e4yt\u00f6s\b",
    r"\bvoi\s+tulla\s+kuuntelemaan\b[^.!?]*\b(?:ilman\s+p\u00e4\u00e4sylippua|ilmaiseksi)\b",
    r"\bovat\s+osallistujille\s+maksuttomia\b",
    r"\bkannatusmaksu",
    r"^admission\s+to\s+(?:the\s+screening|[^.!?]*\btalk)\b[^.!?]*\bis\s+free\b",
    r"^the\s+screening\s+will\s+(?:take\s+place|be\s+held)\s+on\b",
    r"\bare\s+organi[sz]ing\s+a\s+free\s+screening\b",
))


def sentences(text):
    """A text's sentences. "Huom!" stays with the sentence it introduces."""
    out = []
    for part in SENTENCE_RE.split(text or ""):
        if out and re.fullmatch(r"huom!", out[-1], re.I):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


def drop_note_sentences(text):
    """`text` without its screening-note sentences. -> (text, sentences dropped)"""
    parts = sentences(text)
    kept = [x for x in parts if not any(p.search(x) for p in NOTE_SENTENCES)]
    if len(kept) == len(parts):
        return text, 0
    return " ".join(kept).strip(), len(parts) - len(kept)


def is_note(text):
    """True when a synopsis candidate is a screening note rather than a synopsis."""
    return bool(PRICE_RE.search(text or "") or NOTE_RE.search(text or ""))


def drop_notes_html(desc, names=()):
    """Plain text of an HTML description with its screening-note paragraphs removed.

    A paragraph is a note when it quotes a price or names the cinema itself (`names` are
    stems matched as word prefixes, so "Gilda" also catches "Gildan"). Gilda's
    senior-screening entries open with one such paragraph before the distributor's blurb;
    dropping it at the paragraph boundary is structural, where a sentence split would be a
    guess. Text with no paragraphs is treated as one.
    """
    stems = [re.compile(r"\b" + re.escape(n), re.I) for n in names if n]
    out = []
    for raw in re.split(r"</p\s*>", desc or ""):
        text = html_mod.unescape(_TAGS.sub(" ", raw)).replace("\xa0", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        if not text:
            continue
        if is_note(text) or any(s.search(text) for s in stems):
            continue
        out.append(text)
    return " ".join(out)

# films-extra.json is one file for the whole run and merge() is a read-modify-write of
# it, while run.py now fetches independent hosts in parallel. Two sites merging at once
# would each write back a document built from what they read, so whichever finished
# second would drop the other's synopses -- silently, since neither is an error and the
# only symptom is a film with no Finnish blurb until some later run happens to add it.
#
# Serialised here rather than hoisted out of run_site and merged once after the pool
# joins, because merging in place keeps "[label] synopses merged: N" inside that site's
# own block in the committed log, and the merge itself is a few milliseconds against a
# site's minutes of paced fetching. The lock lives on the function rather than at the
# call site so a second caller cannot reintroduce the race by not knowing about it.
_lock = threading.Lock()

# The languages a slot may be written for: what `index.html` offers a reader, and nothing
# else. An adapter naming anything outside this is a typo or an unconsidered language, and a
# junk slot in a file every chain reads is worse than a missing synopsis, so it is dropped
# and said out loud once per run.
LANGS = ("fi", "sv", "en")
# What a bare `_syn` string means. Every adapter published one before 2026-09-16 and most
# still do, so this is the compatibility contract rather than a default to tidy away.
LEGACY_LANG = "fi"
_unknown = set()


def texts(value):
    """An adapter's `_syn` -> {lang: text}, empty strings dropped.

    A string is Finnish, which is what it has always been. A mapping is read as the adapter
    declared it.
    """
    if isinstance(value, dict):
        out = {}
        for lang, text in value.items():
            lang, text = str(lang).strip().lower(), (text or "").strip()
            if not text:
                continue
            if lang not in LANGS:
                _unknown.add(lang)
                continue
            out[lang] = text
        return out
    text = (value or "").strip()
    return {LEGACY_LANG: text} if text else {}


# Which site supplied each synopsis this run, by its index in the module's SITES, per
# language: a site that wins the Swedish slot has said nothing about the Finnish one.
#
# The lock alone only stops a lost write. It does not decide *whose* text lands when two
# sites publish different `_syn` for the same normalised title -- two chains showing the
# same film, each with its own blurb. Fill-if-empty then means "whichever host answered
# first", which with a pool is a property of the network: measured 2026-09-01 with one
# slow site and one fast one, `workers=1` published the first site's synopsis and
# `workers=2` published the second's, from the same data.
#
# The winner is the earlier site in SITES order, which is what the sequential loop
# produced and is the same on every run at every pool size. A site that is earlier may
# therefore replace text a later site already merged **during this run**; text that was
# in the file before the run began is never touched, which is the rule that matters --
# the provider's own synopsis still beats TMDB's, and the first provider in SITES order
# beats the rest.
_claimed = {}


def reset():
    """Forget this run's claims. run.py calls it before each module's sites are fetched.

    Per module rather than per process: modules run one after the other, so a later
    module's site 0 must not outrank an earlier module's site 5. Once a module is done
    its text is simply what is in the file, and the next module leaves it alone.
    """
    with _lock:
        _claimed.clear()
        _unknown.clear()


def norm(t):
    r"""Must match enrich_tmdb.norm() and normTitle() in index.html.

    `_` is stripped explicitly; \w keeps it, the client's \p{L}\p{N} does not.
    """
    t = re.sub(r"[^\w\s]|_", " ", (t or "").lower().strip(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def read_extra(path: pathlib.Path) -> dict:
    """films-extra.json as a document. A missing file is an empty one.

    Anything else that stops it being read raises, JSONDecodeError being a ValueError.
    Every writer of this file is a read-modify-write, and reading a broken file as {}
    rewrote it from one site's synopses: one stray comma cut 568 entries to 1, with every
    cinema `sv` slot, `id`, `ts` and `kr` gone until something re-supplied them (audit C5,
    2026-09-25). Failing leaves the file for a person to repair, and the step red.
    """
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name}: not a JSON object")
    return doc


def merge(out: pathlib.Path, per_venue: dict, label: str, order: int = 0) -> None:
    """Fold this site's synopses into films-extra.json. `order` is its index in SITES.

    A slot is filled when it is empty, and taken over when this site is earlier in SITES
    order than the site that filled it earlier in the same run. See `_claimed`.

    `synopses merged: N` counts what this call wrote. A later site's line can therefore
    be superseded by an earlier site's, which is visible in the committed log as two
    non-zero lines for one film and is the correct outcome rather than a miscount.
    """
    path = out / "films-extra.json"
    with _lock:
        doc = read_extra(path)
        films = doc.get("films") or {}
        added = skipped = note_sentences = 0
        per_lang = {}
        for shows in per_venue.values():
            for s in shows:
                for lang, syn in texts(s.get("_syn")).items():
                    key = norm(s["title"])
                    syn, dropped = drop_note_sentences(syn)
                    note_sentences += dropped
                    if not syn:
                        continue
                    if is_note(syn):
                        # Never into the shared slot: see PRICE_RE and NOTE_RE. Left empty
                        # for TMDB.
                        skipped += 1
                        continue
                    if norm(syn) == key:
                        # The title where the description goes (Niagara's Romanovin kivet,
                        # 2026-09-27) says nothing; the slot stays open for TMDB.
                        continue
                    e = films.setdefault(key,
                                         {"s": {"fi": "", "en": ""}, "r": 0, "tr": ""})
                    e.setdefault("s", {"fi": "", "en": ""})
                    # Per language: a Finnish text in the file says nothing about whether
                    # the Swedish slot is spoken for, and the other way round.
                    # A slot the TMDB pass filled, recorded in `ts`, is not spoken for:
                    # the provider's own synopsis beats TMDB's, and it takes the slot
                    # out of `ts` so the next TMDB pass leaves it alone.
                    tmdb = lang in (e.get("ts") or ())
                    if e["s"].get(lang) and not tmdb:
                        claimed = _claimed.get((lang, key))
                        # Text from before this run, or from a site at least as early as
                        # this one. Either way it stands.
                        if claimed is None or order >= claimed:
                            continue
                    if tmdb:
                        ts = [x for x in e["ts"] if x != lang]
                        if ts:
                            e["ts"] = ts
                        else:
                            e.pop("ts")
                    # A language slot is created only when there is text for it. An entry
                    # with no `sv` key is the normal case and every reader handles it.
                    e["s"][lang] = syn
                    _claimed[(lang, key)] = order
                    per_lang[lang] = per_lang.get(lang, 0) + 1
                    added += 1
        doc["films"] = films
        common.write_films_extra(path, doc)
    print(f"[{label}] synopses merged: {added}")
    if len(per_lang) > 1 or set(per_lang) - {LEGACY_LANG}:
        print(f"[{label}] synopses by language: "
              + ", ".join(f"{k} {per_lang[k]}" for k in sorted(per_lang)))
    if skipped:
        print(f"[{label}] synopses skipped as screening notes: {skipped}")
    if note_sentences:
        print(f"[{label}] screening-note sentences left out of synopses: {note_sentences}")
    if _unknown:
        print(f"[{label}] synopses in a language nothing reads, dropped: "
              f"{', '.join(sorted(_unknown))}", file=sys.stderr)


def repair_from_twin(films: dict, extra: dict) -> int:
    """Restore characters Finnkino's payload dropped to "?", using another chain's copy
    of the same distributor text. -> number of strings repaired.

    Finnkino publishes "Catherine Laga?aia" and "Auli?i Cravalho" where the name carries
    an okina (U+02BB). It is their CMS and not this pipeline: in the same string `®`,
    `“ ”` and every `ä` survive, `json.loads` would raise on malformed UTF-8 rather than
    emit "?", and the one decode in fetch_data.py uses errors="replace", which produces
    U+FFFD. Several chains run the distributor's blurb verbatim, so a clean copy of the
    same sentence is usually already in films-extra.json.

    A "?" cannot be decoded back on its own -- it could stand for an apostrophe, an okina
    or a real question mark -- so nothing here guesses. A twin is used only when it is
    the same length and differs *only* at positions where this text has "?", which makes
    the substitution a transcription of a string we already hold rather than a repair of
    one we do not. A twin that disagrees anywhere else is a different text and is left
    alone, and a genuine "Mitä?" is never touched because no twin will differ there.
    """
    fixed = 0
    for entry in films.values():
        syns = entry.get("s")
        if not isinstance(syns, dict):
            continue
        title = (entry.get("t") or {}).get("fi") or (entry.get("t") or {}).get("en") or ""
        twin = (extra.get(norm(title)) or {}).get("s") or {}
        for lang, text in syns.items():
            clean = twin.get(lang) or ""
            if not text or "?" not in text or len(clean) != len(text):
                continue
            pairs = [(a, b) for a, b in zip(text, clean) if a != b]
            if pairs and all(a == "?" and b != "?" for a, b in pairs):
                syns[lang] = clean
                fixed += len(pairs)
    return fixed


def strip_helpers(shows) -> None:
    for s in shows:
        s.pop("_syn", None)
        s.pop("movieUrl", None)
