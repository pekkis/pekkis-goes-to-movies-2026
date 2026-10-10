"""One contact address, and no other address anywhere in the tree.

Rotation: the address is a disposable alias, written once in /status/'s markup and
repeated in both documents. It moved there on 2026-09-07 with the rest of the footer's
global half; the app and the page generator now link to that page instead of carrying an
address, which is three fewer copies to miss on a rotation. Markup rather than a
constant, because the address has to survive a script that never ran. Leaks: this repo is
public, and a real name once reached 18 commits. The address is discovered from the page,
so the test carries none of its own and keeps working across a rotation.
"""
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Addresses that are legitimately not the contact route. Kept deliberately short: every
# entry is a place a real address could hide behind a plausible-looking name.
ALLOWED = {
    "noreply@anthropic.com",          # commit trailer, if it ever lands in a file
    # The sanctioned author identity. It is in the metadata of every commit already, and
    # CLAUDE.md names it so a future session can recognise an author line that is *not*
    # it. Added after this test caught that very sentence being written -- which is the
    # guard working, not a false positive: a GitHub noreply address is not a personal one.
    "19388620+Shady-Dev@users.noreply.github.com",
}

# Files that hand-write the address. Generated pages are excluded on purpose: they no
# longer carry one at all, and they are rewritten from build_pages.py on the next run.
SOURCES = ["status/index.html", "README.md", "IDEAS.md"]


def tracked_text_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(_ctx.ROOT),
                         capture_output=True, text=True, timeout=60)
    out.check_returncode()
    for name in out.stdout.split("\0"):
        if not name:
            continue
        p = _ctx.ROOT / name
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".woff2", ".ico"}:
            continue
        yield p


class ContactAddressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = (_ctx.ROOT / "status" / "index.html").read_text(encoding="utf-8")
        m = re.search(r'href="mailto:([^"]+)"', html)
        assert m, "status/index.html no longer carries a mailto link"
        cls.contact = m.group(1)

    def test_the_published_address_is_an_address_at_all(self):
        self.assertRegex(self.contact, EMAIL)

    def test_every_hand_written_copy_agrees(self):
        """The whole point: a half-finished rotation fails here instead of shipping."""
        for name in SOURCES:
            with self.subTest(file=name):
                text = (_ctx.ROOT / name).read_text(encoding="utf-8")
                found = set(EMAIL.findall(text)) - ALLOWED
                self.assertIn(self.contact, found,
                              f"{name} does not carry the contact address")
                self.assertEqual(found, {self.contact},
                                 f"{name} carries an address that is not the contact one")

    def test_the_address_is_static_markup_in_the_contact_section(self):
        """A status page that could not read a single file still has to say who to write
        to, so the address cannot be something the status renderer produces."""
        html = (_ctx.ROOT / "status" / "index.html").read_text(encoding="utf-8")
        markup = re.search(r'<section id="contact".*?</section>', html, re.S)
        self.assertIsNotNone(markup, "the static contact section is gone")
        self.assertIn(self.contact, markup.group(0))

    def test_the_app_and_the_generator_link_rather_than_carry_an_address(self):
        """Three copies removed on 2026-09-07. Any of them coming back is a rotation trap
        this test would otherwise stop covering."""
        for name in ("index.html", "scripts/build_pages.py"):
            text = (_ctx.ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(set(EMAIL.findall(text)) - ALLOWED, set(),
                             f"{name} carries an address again")
            self.assertIn("/status/", text, f"{name} does not link to the status page")

    @unittest.skipIf(shutil.which("git") is None, "git not installed")
    def test_no_other_address_is_tracked_anywhere(self):
        """Including the generated pages. This is the leak guard: a personal address that
        reaches a tracked file in a public repo costs a history rewrite to remove."""
        offenders = {}
        for p in tracked_text_files():
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            extra = set(EMAIL.findall(text)) - ALLOWED - {self.contact}
            if extra:
                offenders[str(p.relative_to(_ctx.ROOT))] = sorted(extra)
        self.assertEqual(offenders, {},
                         "tracked files contain an address that is not the contact one")


if __name__ == "__main__":
    unittest.main()
