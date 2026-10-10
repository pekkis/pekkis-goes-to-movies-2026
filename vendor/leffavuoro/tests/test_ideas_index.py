"""IDEAS.md is an index of open work, and this test is what keeps it one.

The rule is in CLAUDE.md's placement table: a proposal, a priority, a status or an open
item's next action belongs here; the dated record of a closed decision belongs in
`docs/archive/`, and what was observed probing something belongs in `docs/research/`.

That rule existed in prose and was broken three times in two days anyway, each time the
same way: a piece of work finished, and its measurements, mutation counts and probe output
went into the open-work file because that is where the person doing the work was already
typing. The file went 4,937 lines once before it was split; it started growing back within
hours of the split. Prose did not hold it, so this does.

The same shape as `tests/test_design_contract.py`, and for the same reason: a decision that
keeps being eroded needs something that fails rather than something that asks nicely.

Three guards, each aimed at a real failure seen here:

1. A whole-file ceiling, which is what catches the slow drift nobody notices.
2. A per-entry ceiling, because the drift arrives one over-detailed entry at a time.
3. No measurement tables inside an open-work entry. A table of probe results is evidence,
   and evidence has its own directory. One section legitimately carries a table, the
   archive map, and it is a named exception rather than a general escape.

If an entry genuinely needs more room, that is the signal it is not an open item any more.
Write the record in `docs/archive/` or the evidence in `docs/research/` and leave a status
and a next action here.
"""
import pathlib
import re
import unittest

import _ctx


IDEAS = _ctx.ROOT / "IDEAS.md"

# Lowered from 400 on 2026-09-22, when the 41-line "Documentation state" section left for
# the generated docs/counts.md and the file dropped to 370. 390 leaves 20 lines: about two
# typical entries, or one at the MAX_ENTRY_BODY ceiling below. A cap that has to be raised
# every month is not a cap; raise this only when the number of open items genuinely grows,
# and never to fit a longer entry. The counts are no longer among them -- they are derived
# now, so they cannot drift and cannot take space here.
MAX_LINES = 390

# The per-entry ceiling the maintainer stated. Entries here run 5 to 15 body lines; the two
# that exceeded it were both a finished piece of work written up in place.
MAX_ENTRY_BODY = 15

# Sections whose content is a list of open items, one `###` entry each.
ITEM_SECTIONS = ("Active work", "Blocked", "Deferred")

# The one section a table belongs in: the map of where the history went. "Documentation
# state" was the other until 2026-09-22; its table is generated into docs/counts.md now,
# and the exemption went with it. Named, so the exception cannot quietly widen.
TABLE_SECTIONS = ("Where the rest went",)


def sections():
    """-> [(h2 title, [line, ...])] for IDEAS.md."""
    lines = IDEAS.read_text(encoding="utf-8").split("\n")
    out, title, body = [], None, []
    for line in lines:
        if line.startswith("## "):
            if title is not None:
                out.append((title, body))
            title, body = line[3:].strip(), []
        elif title is not None:
            body.append(line)
    if title is not None:
        out.append((title, body))
    return out


def entries():
    """-> [(section, heading, [non-blank body line, ...])] for every open-work entry."""
    out = []
    for title, body in sections():
        if not title.startswith(ITEM_SECTIONS):
            continue
        heading, buf = None, []
        for line in body:
            if line.startswith("### "):
                if heading is not None:
                    out.append((title, heading, [x for x in buf if x.strip()]))
                heading, buf = line[4:].strip(), []
            elif heading is not None:
                buf.append(line)
        if heading is not None:
            out.append((title, heading, [x for x in buf if x.strip()]))
    return out


class IdeasIndexTest(unittest.TestCase):
    def test_the_file_stays_an_index(self):
        n = len(IDEAS.read_text(encoding="utf-8").split("\n"))
        self.assertLessEqual(
            n, MAX_LINES,
            f"IDEAS.md is {n} lines. It is the index of open work, not the record of "
            f"finished work: move closed decisions to docs/archive/ and probe results to "
            f"docs/research/ rather than raising this cap.")

    def test_no_open_item_is_written_up_like_a_finished_one(self):
        found = entries()
        self.assertGreater(len(found), 5, "the open-work sections went missing")
        for section, heading, body in found:
            with self.subTest(entry=heading):
                self.assertLessEqual(
                    len(body), MAX_ENTRY_BODY,
                    f"[{section}] {heading!r} is {len(body)} body lines. An open item is a "
                    f"status and a next action; if it needs more, it is a record for "
                    f"docs/archive/ or evidence for docs/research/.")

    def test_measurements_do_not_live_in_an_open_item(self):
        """A table of results is evidence. Evidence has its own directory."""
        for section, heading, body in entries():
            rows = [x for x in body if x.strip().startswith("|")]
            with self.subTest(entry=heading):
                self.assertEqual(
                    rows, [],
                    f"[{section}] {heading!r} carries a table. Put the measurement in "
                    f"docs/research/ and link to it.")

    def test_the_table_exception_is_the_named_sections_only(self):
        """So the two allowed tables cannot become a general licence."""
        for title, body in sections():
            rows = [x for x in body if x.strip().startswith("|")]
            if not rows:
                continue
            with self.subTest(section=title):
                self.assertTrue(
                    title.startswith(TABLE_SECTIONS),
                    f"{title!r} carries a table; only {TABLE_SECTIONS} may.")

    def test_claude_md_still_states_where_a_closed_record_goes(self):
        """The test enforces the rule; CLAUDE.md is where a session reads it. If the row
        goes, this guard is enforcing something nothing explains."""
        claude = (_ctx.ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("docs/archive/", claude)
        self.assertRegex(claude, r"dated record of a decision, once the work is closed")


if __name__ == "__main__":
    unittest.main()
