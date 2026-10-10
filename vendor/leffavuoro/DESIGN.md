# Design contract

The visual elements below are decisions, not defaults. They were each argued out once
(the app entries in `docs/archive/2026-09-app.md` hold the reasoning and the measurements)
and one of them was lost twice in a single day when a task spec said otherwise and the
tests that pinned it were rewritten in the same commit. `tests/test_design_contract.py`
checks the CSS in `index.html` and `scripts/build_pages.py` against the values here, so a
change has to touch this file, and CI refuses a push that touches this file or that test
without an IDEAS.md entry in the same push.

## Changing this

Only on the maintainer's explicit written instruction that names this file. A task spec
that contradicts a value here is a conflict to raise before building, not a change to
make. The change lands in one commit with a dated IDEAS.md entry saying why, and the
value here is updated in that commit.

## The ticket

Every showtime is a ticket, in every view and on the generated pages: a time compartment
on the left, the details beside it, and a perforation on the right where the price
compartment tears off. The perforation is always present. With a price the compartment
is 56 px wide on the row ticket and content-wide on the combined ticket; without a price
it narrows to a 16 px tail and keeps the dashed seam and both notches.

```
ticket.min_height        = 40px
ticket.radius            = 7px
ticket.time.size         = .92rem
ticket.time.weight       = 800
ticket.price.width       = 56px
ticket.price.size        = .78rem
ticket.price.weight      = 700
ticket.tail.width        = 16px
ticket.seam              = 1px dashed var(--line)
ticket.notch.size        = 8px
ticket.notch.left        = -4px
ticket.empty.display     = not none
```

The Ajat list is the one exception in width: its unpriced ticket keeps the full 56 px
compartment so every ticket in the list is 120 px and the titles share one x. It keeps
the seam and notches like every other ticket.

## Tap targets

On a phone every control reaches 44 px of hit area (Apple's floor): day chips, the header
controls, the picker and search, the sheet's close button, the menu rows and the text-only
reveal links all measure 44 or more at 393 px wide. The view segment, the filter chips and
the chain legend buttons stay 36 px tall to the eye and reach 44 through a transparent 4 px
extension above and below the border, so the filter row does not weigh as much as the day
row. The ticket is the one control under the floor, at 40 px (the archive entry "Tickets
are 40 px"). Desktop keeps the smaller header sizes; a mouse needs no 44.

```
tap.floor          = 44px
tap.pill.visible   = 36px
tap.pill.reach     = 4px
tap.ticket         = 40px
```
