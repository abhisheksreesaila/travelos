# Design handoff: trip calendar (F-019) and live friends (F-020)

**Approved:** 2026-09-30. Artboard: `docs/design/canvas/Calendar.dc.html`.
**System:** `design-system/DESIGN-SYSTEM.md`. Build every page head with `layout.styles(...)`.

## F-019 Trip calendar (`/calendar`, needs a booking; otherwise show a friendly "book a trip first" state linking to /plan)
- **Top bar**: GitAway mark, trip title ("LA with the kids"), a dates · booked · total line, avatars, "Your forks" button with a count (F-021 fills it), Invite (F-020), and Share trip (F-022). Buttons whose tickets aren't built yet go to their placeholder pages.
- **Grid**: an hour gutter (7 AM–10 PM, 48px per hour) and day columns, each headed by a tinted chip (big date number, weekday, weather from `gitaway/context.py`). Faint hour lines.
- **Blocks**: absolutely positioned by start and end time.
  - **Booked** (flight out and back, check-in, check-out) come from the traveler's booking and the catalog. They are ink, cannot be edited, and carry a lock label for screen readers.
  - **Activities** use tint fills by kind, with an optional "by <name>" pill.
- **Gaps stay empty.** Hovering or focusing an empty hour shows a dashed coral "+ Add something fun" ghost. Clicking it opens a small add form (title, start, end, kind). Save adds the block with the pop-in animation.
- **Editing**: an activity can be moved and resized by pointer (a 15-minute snap) and edited through a small form (keyboard path: select the block, Enter to edit, arrow keys ±15 min). Delete has Undo. Blocks never overlap booked items; the form shows the clash.
- **Notes**: every activity can carry notes. The trip notes feed on the right lists the activity notes and general notes, with a composer at the bottom.
- **Long trips (e.g. 20 days)**:
  - A **whole-trip strip** sits on top: one small chip per day with dots for booked and planned items. It scrolls sideways when the trip is long. Tapping a chip jumps the window to that day.
  - The **day window** shows 5 days on desktop, 3 on tablet and 1 on phone. Prev and next buttons plus swipe move it, and the hour gutter stays sticky.
  - A **"Whole trip" toggle** switches to a compact view: rows of days with just their item titles, and empty days called out ("wide open").
  - The sample trip is 5 days. Add a hidden `?demo=long` 20-day fixture so the long-trip behaviour can be seen and tested.
- **Persistence**: in the session per traveler for now, like forks. It is kept across reloads and never duplicated on refresh.
- **Phone**: one day at a time with the strip on top, and notes as a bottom drawer.

## F-020 Invite and live friends
- **Invite** opens a small dialog with a name field and suggested demo friends (Mom, Sam) plus a "copy invite link" button (fake link). Signed out, it goes through sign-in with `intent=invite`.
- **Invited friends** appear as overlapping avatars with a green "is planning with you" presence dot.
- **Scripted liveness**: a few seconds after arriving, "Mom" adds "Travel Town steam trains" on Sunday 10:00–12:30 (a green ring and "just now" pill, with pop-in) and posts a note in the feed. It happens once per session and is off under reduced motion (the item simply appears).
