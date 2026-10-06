# Brief: the day you edit with your finger

Status: approved (captain, 2026-10-05, on the trip: "It has to be touch focused. It has to be blocks of time where I can edit with my finger, just like I would edit a Teams meeting… It should never feel like a web app where I open up a thing, I put a drop down… let's focus on this"; he left the gestures to Claude: "I'll let you figure that out"). Design calls below are Claude's; the captain judges them on the phone.

## Why
The simplified day is easy to read, but changing it still means opening screens and forms. On a phone people talk or paste to fill a day, then nudge it with a finger. A time grid with direct moves, resizes and a hold menu makes the day feel like an app, not a website.

## What
1. **A time grid.** The day view shows the family's plans as blocks on an hour grid, sized by their length (a park day 9–9 is tall, lunch 12–1 short). Bookings stay quiet background lines (F-090). Overlaps sit side by side. A blank day keeps the big Talk / Paste (F-090); Ask fills the grid, and a plan with no length gets 1 hour.
2. **Move.** Hold a block (~350 ms), then drag: it lifts, snaps to 15 minutes, shows the new time under the finger, and drops on release. Undo in a toast. Dragging near the top or bottom edge scrolls.
3. **Resize with a zoom.** Hold the bottom edge and drag: the grid zooms in around the finger (about 2.5×) so 5-minute ticks are easy to hit (snap 5 min while zoomed), and eases back on release. Undo in a toast. Minimum length 15 minutes.
4. **The hold menu.** Hold and release without moving: the block wiggles gently and a small menu pops beside it: Chat (the plan's chat, F-091), Rename, Delete (asks once, with Undo after).
5. **Rename in place.** Double-tap a block's title (or Rename in the menu): the title becomes editable right there; Enter or tapping away saves, Escape cancels.
6. **Tap** opens the block as today (its parts and rides).

## Choices
- No swipe-to-delete: a sideways swipe already changes the day (F-090); Delete lives in the hold menu.
- The zoom is a CSS transform on the grid during the resize only, calm under reduced motion (no zoom, finer snap still available through the time label buttons).
- Every gesture has a keyboard/screen-reader path (the menu is a real menu; move/resize also reachable from the menu as "Earlier / Later / Shorter / Longer" by 15 minutes).
- Writes reuse the calendar's own move/resize/delete/rename rules (gitaway.tripcal), editor-gated by gitaway.access; viewers see the grid with no gestures.

## Not now
Dragging a plan to another day by gesture (the menu can add "Move to another day" later), multi-select, drawing a new block on empty time (Ask does that).

## How we'll know
On the phone the captain pastes a day, sees it as blocks, drags lunch half an hour later, shortens a ride to 30 minutes with the zoom, renames one, deletes one with the hold menu, and never opens a form.
