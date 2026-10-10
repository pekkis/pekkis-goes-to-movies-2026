"""The design contract (DESIGN.md) holds: the ticket's key values in the client and the
generator match what the file says, and the working rules point at it.

This test exists because the ticket's perforation was removed from unpriced tickets on
2026-09-13 by a task spec, with the pinning tests rewritten in the same commit, and put
back the same evening. A test that pins the current CSS offers no resistance when it is
edited alongside the CSS; a test that pins a separate, named contract file makes the
change visible as a change to the contract. CI (ci.yml) additionally refuses a push that
touches DESIGN.md or this file without an IDEAS.md change.
"""
import re
import unittest

import _ctx

ROOT = _ctx.ROOT
DESIGN = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
GEN = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
CLAUDE = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def contract():
    out = {}
    for block in re.findall(r"```\n(.*?)```", DESIGN, re.S):
        out.update(re.findall(r"^(\S+)\s*=\s*(.+?)\s*$", block, re.M))
    return out


def rule(src, selector):
    m = re.search(r"^\s*" + re.escape(selector) + r"\{(.*?)\}", src, re.S | re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def prop(body, name):
    m = re.search(r"(?<![-\w])" + re.escape(name) + r"\s*:\s*([^;]+)", body or "")
    return m.group(1).strip() if m else None


class DesignContractTest(unittest.TestCase):

    def setUp(self):
        self.c = contract()

    def test_the_contract_names_its_own_change_procedure(self):
        self.assertIn("## Changing this", DESIGN)
        self.assertIn("explicit written instruction that names this file", DESIGN)
        self.assertIn("conflict to raise before building", DESIGN)

    def test_the_working_rules_and_ci_point_at_the_contract(self):
        self.assertIn("## Design contract", CLAUDE)
        self.assertIn("DESIGN.md", CLAUDE)
        self.assertIn("DESIGN.md", CI)
        self.assertIn("tests/test_design_contract.py", CI)

    # -- the client -------------------------------------------------------------------------
    def test_the_client_ticket_matches(self):
        c, stub = self.c, rule(HTML, ".stub")
        self.assertEqual(prop(stub, "min-height"), c["ticket.min_height"])
        self.assertEqual(prop(stub, "--r"), c["ticket.radius"])
        self.assertEqual(prop(stub, "--pw"), c["ticket.price.width"])
        self.assertEqual(prop(stub, "--pe"), c["ticket.tail.width"])
        time = rule(HTML, ".stub .time")
        self.assertEqual(prop(time, "font-size"), c["ticket.time.size"])
        self.assertEqual(prop(time, "font-weight"), c["ticket.time.weight"])
        price = rule(HTML, ".stub .price")
        self.assertEqual(prop(price, "border-left"), c["ticket.seam"])
        self.assertEqual(prop(price, "font-size"), c["ticket.price.size"])
        self.assertEqual(prop(price, "font-weight"), c["ticket.price.weight"])
        notch = rule(HTML, ".stub .price::before,.stub .price::after")
        self.assertEqual(prop(notch, "width"), c["ticket.notch.size"])
        self.assertEqual(prop(notch, "height"), c["ticket.notch.size"])
        self.assertEqual(prop(notch, "left"), c["ticket.notch.left"])

    def test_the_client_perforation_is_always_present(self):
        """`ticket.empty.display = not none`: an unpriced ticket keeps seam and notches."""
        self.assertEqual(self.c["ticket.empty.display"], "not none")
        for sel in (".stub .price:empty", ".stubs.grid .stub .price:empty", ".trow .stub .price:empty"):
            body = rule(HTML, sel)
            self.assertIsNotNone(body, sel)
            self.assertNotIn("display:none", body.replace(" ", ""), sel)
            self.assertNotIn("border-left:0", body.replace(" ", ""), sel)
            self.assertNotIn("border-left:none", body.replace(" ", ""), sel)
        self.assertNotRegex(HTML, r"\.price:empty::before[^{]*\{[^}]*display:\s*none",
                            "no rule hides the notches of an empty compartment")
        self.assertIn("var(--pe)", rule(HTML, ".stub .price:empty"))
        self.assertIn("var(--pe)", rule(HTML, ".stubs.grid .stub .price:empty"))

    # -- tap targets on a phone --------------------------------------------------------------
    def test_pills_stay_36_to_the_eye_and_reach_44(self):
        c = self.c
        vis, reach = c["tap.pill.visible"], c["tap.pill.reach"]
        self.assertEqual((int(vis[:-2]) + 2 * int(reach[:-2])), int(c["tap.floor"][:-2]), "36 + 2 x 4 = 44")
        pills = rule(HTML, ".seg button, .chip, .legend .lg-btn")
        self.assertEqual(prop(pills, "min-height"), vis)
        self.assertIn("position:relative", pills)
        self.assertIn("z-index:1", pills, "later content in the DOM painted over the extension below (measured 2026-09-13)")
        ext = rule(HTML, ".seg button::after, .chip::after, .legend .lg-btn::after")
        self.assertEqual(prop(ext, "top"), "-" + reach)
        self.assertEqual(prop(ext, "bottom"), "-" + reach)
        # the bordered pills measure from the padding edge, one more px for the border
        bordered = rule(HTML, ".chip::after, .legend .lg-btn::after")
        more = f"-{int(reach[:-2]) + 1}px"
        self.assertEqual((prop(bordered, "top"), prop(bordered, "bottom")), (more, more))
        self.assertIn('content:""', ext)
        self.assertIn("position:absolute", ext)
        self.assertNotIn("overflow:hidden", rule(HTML, ".seg"), "it would clip the extension")
        self.assertIsNotNone(rule(HTML, ".seg button:first-child"))
        self.assertIsNotNone(rule(HTML, ".seg button:last-child"))

    def test_the_header_controls_and_the_sheet_close_reach_44_on_a_phone(self):
        floor = self.c["tap.floor"]
        mobile = HTML[HTML.index("    .fav{flex:0 0 auto; padding:8px 11px}"):]
        mobile = mobile[:mobile.index("\n  }\n")]
        self.assertIn(f".langseg button{{height:{floor};", mobile)
        self.assertIn(f"#themeToggle{{flex-basis:{floor}; width:{floor}; height:{floor}}}", mobile)
        self.assertIn(f"#areaSelect, .search, .fav{{min-height:{floor}}}", mobile)
        self.assertIn(f"@media (max-width:699px){{ .sheet-close{{width:{floor}; height:{floor};", HTML)
        self.assertRegex(HTML, r"\.day\{[^}]*min-height:" + re.escape(floor), "the day chip has carried the floor since v129")

    def test_text_links_reach_44_without_moving(self):
        floor = self.c["tap.floor"]
        links = rule(HTML, ".pastlink, .synmore")
        self.assertEqual(prop(links, "min-height"), floor)
        self.assertEqual(prop(links, "padding"), "13px 0")
        self.assertEqual(prop(links, "margin"), "-13px 0", "the padding is taken back, so the text stays where it was")
        self.assertIn("display:inline-flex", links)
        self.assertNotIn("border-bottom", links, "a border would sit on the padding edge")
        self.assertIn("text-decoration:underline dotted", links)

    def test_the_ticket_is_the_recorded_exception(self):
        self.assertEqual(self.c["tap.ticket"], self.c["ticket.min_height"])
        self.assertLess(int(self.c["tap.ticket"][:-2]), int(self.c["tap.floor"][:-2]))

    # -- the generator ----------------------------------------------------------------------
    def test_the_generated_ticket_matches(self):
        c = self.c
        stub = rule(GEN, ".stub")
        self.assertEqual(prop(stub, "min-height"), c["ticket.min_height"])
        self.assertEqual(prop(stub, "border-radius"), c["ticket.radius"])
        price = rule(GEN, ".stub .price")
        self.assertEqual(prop(price, "width"), c["ticket.price.width"])
        self.assertEqual(prop(price, "border-left"), c["ticket.seam"])
        self.assertEqual(prop(price, "font-size"), c["ticket.price.size"])
        notch = rule(GEN, ".stub .price::before,.stub .price::after")
        self.assertEqual(prop(notch, "width"), c["ticket.notch.size"])
        self.assertEqual(prop(notch, "left"), c["ticket.notch.left"])
        empty = rule(GEN, ".stub .price:empty")
        self.assertEqual(prop(empty, "width"), c["ticket.tail.width"])
        self.assertNotIn("display:none", empty.replace(" ", ""))
        self.assertEqual(prop(rule(GEN, ".grid .stub .price:empty"), "width"), c["ticket.tail.width"])


if __name__ == "__main__":
    unittest.main()
