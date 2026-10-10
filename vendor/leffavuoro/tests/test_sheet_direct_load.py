"""A direct film link opens its sheet on load (2026-09-03, sw.js v106).

`syncSheet()` reads `#m=<id>` and opens the film sheet, and it ran on `hashchange` and
inside `applyLang()` when a sheet was already open. Nothing called it after the first
schedule arrived, so a link such as `/?area=cn-tampere#m=61` loaded the list with the
fragment intact and the sheet closed; a refresh with the sheet open closed it the same
way. Reproduced on the live site on 2026-09-03 with an id that was in the day's list.

The call has to come after `loadSchedule()` in the boot sequence, because `showSheet`
reads the film's screenings from `jsonCache[state.area]`, which the first load fills.
Pinned on the source: the boot's last awaited step is the schedule, and the sync follows
it, guarded on a fragment being present so an ordinary load never touches the sheet.
"""
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def boot_tail():
    """The end of the boot IIFE: from the last `await loadSchedule()` to the script's end."""
    at = HTML.rfind("await loadSchedule();")
    return HTML[at:]


class DirectLoadOpensSheetTest(unittest.TestCase):

    def test_the_boot_syncs_the_sheet_after_the_first_schedule(self):
        tail = boot_tail()
        self.assertIn("if(location.hash) syncSheet();", tail)
        self.assertLess(tail.index("await loadSchedule();"), tail.index("syncSheet();"))
        # Before the catch: a failed load renders the error and opens nothing.
        self.assertLess(tail.index("syncSheet();"), tail.index("} catch(e){"))

    def test_the_sync_still_follows_hash_changes(self):
        self.assertIn("window.addEventListener('hashchange', syncSheet);", HTML)

    def test_show_sheet_reads_the_loaded_schedule(self):
        """Why the call sits after the load: the sheet lists the film's screenings from
        the schedule cache, so a sync before it would open an empty sheet."""
        body = re.search(r"async function showSheet\(fid, want, keepFocus\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertIn("jsonCache[state.area]", body)


if __name__ == "__main__":
    unittest.main()
