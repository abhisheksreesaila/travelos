# The trip canvas (F-081)

One surface for the trip that zooms: week, day, block (a park day with its parts and steps), step. Module `gitaway/pages/tripcanvas.py`, styles `assets/css/trip_canvas.css`, script `assets/js/trip_canvas.js`. Designs: frames 5, 6, 7 and 11 of `docs/design/canvas/Trip-Canvas-v2.html`, frames 1 to 3 of `Plan-Steps-v1.html`.

## Addresses (every level has one, drawn by the server)

| Level | Address | Shows |
|---|---|---|
| Week | `/trip/canvas` | a row per day; park days show their parts as mini blocks with counts and one note sticker; free days have a `+` (editors) |
| Day | `/trip/canvas?day=N` | blocks in time order; a park block shows its parts with steps as chips, notes as stickers on their item, who as avatars; the day's Set aside tray |
| Block | `/trip/canvas?block=aN` | parts as sections, steps in order, lanes where people split up, the block's Set aside tray, the trip's lists |
| Step | `/trip/canvas?step=<id>` | a bottom sheet over its block: note, who is going, Mark done / Not done, Set aside / Put back |

An unknown address goes back to the week. `?frag=1` returns the level alone (no page around it) for the script. `POST /trip/canvas/step` does the four writes (`gitaway.canvas.set_done`, `set_aside`) and, for the script (`X-Canvas: 1`), answers 204 with `X-Canvas-Url`; without script it redirects. Only a `/trip/canvas…` address is accepted as the way back. Writes are gated by `gitaway.access` like every write: a viewer reads every level and sees no buttons and no `+`.

## Where it is reached from

Today (`/trip`) stays the first tab. Its heading has a "Week view" link (`#tp-open-canvas`, every role), and the canvas has a Today | Week | Day control (`Today` leaves the canvas). The phone tab bar is unchanged (the canvas shows Today as the current tab). Replacing Today with the canvas, as the storyboard draws it, is a later decision for the captain once the family has used both.

## The zoom

A tap on a link marked `data-zoom` ("in", "out", "side"), a two-finger pinch, or the browser's Back fetches the level as a fragment and swaps it inside `document.startViewTransition`. The tapped element (`data-zk="day-2" | "blk-a3" | "stp-<id>"`) is named `cz-hero` before the swap and its twin after it, so a day row grows into the day heading, a block card into the block heading, a step chip into the sheet, and back. The page behind scales and fades with a soft blur (`html[data-cz-dir]`), the tab bar stays put. Durations and easing are `--cz-dur` and `--cz-ease` on `:root`.

- No View Transitions: the new level scales and fades in (`.cz-in-in`, `.cz-in-out`, `.cz-in-side`).
- `prefers-reduced-motion`: an instant swap, no transition at all.
- Pinch: spread zooms into the level under the fingers, pinch together zooms out one level; the lifting fingers are not a tap. The canvas sets `touch-action: pan-y`, so the browser's own page pinch-zoom is off over it; the buttons (back, close, Today | Week | Day, every row) do the same without a gesture, and Escape zooms out.
- Zooming out to where you came from is the browser's Back (history stays tidy); a write from the sheet zooms out to its block.
- Mark done and Set aside write one coalesced family card ("Abhi finished 3 rides at Universal Studios Hollywood", changed in place for 15 minutes, one push) in `gitaway.canvas._tell`.

## Lanes

Steps of a part that share a time and belong to different people (`who`, with Everyone being nobody in particular) are drawn side by side, one lane per set of people, labelled with the avatars; everything else runs full width (`pages.tripcanvas.slots`).

## Wide day view

At 721px and up the same markup is the laptop view: the week as a strip of day cards across the top (a bar segment per part), the day's parts as lanes (name on the left, rides beside it), the Set aside tray at the side. A strip card swaps the day with a plain cross-fade.

## Touch moves and filters (F-082)

Frame 8 of `Trip-Canvas-v2.html` and frame 4 of `Plan-Steps-v1.html`. Editors only (a viewer has no `data-edit` on `#cz`: no drag, no swipe, no add, no Move; the filters still work).

**Hold and drag** (`trip_canvas.js`, pointer events). Hold a step (a day chip, a block row, a Set aside chip) for 350 ms: it dims, a chip follows the finger, and the drop targets light up. Moving more than 10px first is a scroll. Targets: a part (a line shows where it goes; before the step the finger is above, else at the end), a day in the bar that appears at the top (blocks on other days), the Set aside tray along the bottom. Letting go posts `POST /trip/canvas/move` and swaps the level in place (`dir: side`, scroll kept), then the toast ("<title> moved to <where>") with Undo. A step dropped before a timed step takes that step's time (so it can join or leave a lane); at the end of a part it keeps its own. Dropped on another day it lands at the end of that block's same-named part, else its first. Dragging a Set aside chip onto a part puts it back there.

**Undo** posts the snapshot the move returned (`canvas.move_step` -> `undo`) to `POST /trip/canvas/undo`; `canvas.restore` checks every id, part, time and number in it against the open trip and puts those steps back exactly (block, part, place, time, tray). The family card ("Abhi moved 3 rides at Universal", `canvas._tell` column `moved`) is changed in place for 15 minutes and loses the move when it is undone; adds share the same mechanism ("added").

**Swipe.** On a block row, left reveals Done (Not done) and Set aside (the row gives up room instead of sliding off), right or a tap elsewhere puts them away; they are the same forms as the sheet's. **Add a step** is a sheet over the block, `?block=aN&add=1[&part=&title=&note=]` (works without script): a name, who (Everyone is one choice, then each member, names and initials the trip already uses, Adults, Kids), which part, an optional time (the GitAway time picker), a note; `POST /trip/canvas/add`. **Add a note** and **Move** are on the step sheet: the note form (`POST /trip/canvas/note`, the sheet stays) and a Move menu with the same targets as dragging as buttons (earlier or later in the part, each other part, each other day), for a keyboard or a screen reader.

**Filters.** On a day and a block: Everyone, each family member, names and initials the trip uses, Adults and Kids (only when a step is for them: the family's ages are not known), and each named list of the trip. Single choice; the matching steps get a ring, the rest dim. A step for everyone matches every person. A list matches steps by name (`canvas.same_step`: equal, or one starts with the other by whole words, so "Soarin'" is "Soarin' Around the World"). With a list chosen, a card says "4 more from your <list> list aren't in this day yet" with a chip for each: tap to open the add sheet filled in, or drag it onto a part to add it there. The choice is kept per person and trip in `localStorage` (`cz-filter:<trip>:<user>`; it still works for the page if storage is blocked).

**Writes** (`/trip/canvas/step|move|undo|add|note`) are editor-gated by `gitaway.access`, take the trip the page was drawn for (`trip` field), and the script gets JSON `{url, toast, undo}` or 422 `{error}`.

## Tests

`tests/test_canvas_touch.py` (move, undo, add, note, list matching at the model), `tests/test_canvas_touch_pages.py` (routes, sheets, filters' markup, viewers, another trip), `tests_browser/test_trip_canvas_touch.py` (390 and 320: synthetic-pointer drags to a part, before a step, the tray, another day; Undo; swipe; add a step; notes; Move menu; filters and the list card; a viewer; reduced motion; the View Transition on a drop). Screenshots: `F082_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_trip_canvas_touch.py -k screenshots`.

F-081 tests, kept:

`tests/test_trip_canvas.py` (every level, link and button, roles, fragments), `tests/test_canvas_ticks.py` (the coalesced card, `canvas.plan`), `tests_browser/test_trip_canvas.py` (390 and 320: tap, pinch, Back and Forward, the named element, reduced motion, no-transition fallback, Mark done and Set aside, lanes, no sideways scroll, 44px targets, 13px text; 1280: the wide day view). Screenshots: `F081_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_trip_canvas.py -k screenshots`.

## The plan of the day (F-090)

Brief `docs/briefs/day-plan.md`. On a phone the day level is the plan of the day:

- **Dates across the top** (`day_pills`, `#cz-dpills`): Week (`#cz-z-week`, zooms out) then every trip day (open one `is-open` + `aria-current="date"`, today ringed, a dot when the family planned something). They scroll sideways and the script keeps the open one centred. On a laptop the week strip (`strip`) does this job and the pills are hidden. The Today | Week | Day control stays on the week only.
- **Flick**: the day's `<section>` carries `data-prev` / `data-next`. A touch (not mouse) move of 60px+ that is 1.5× more sideways than up or down, in under 0.9 s, not started on the dates, filters, a sheet or a field and not a held step, goes to that day with `mode: 'replace'` (Back is not a day-by-day walk). The view follows the finger a little. Taps on the dates and flicks slide the way the days go (`html[data-cz-dir="next"|"prev"]`, `.cz-in-next|prev` without View Transitions; nothing under reduced motion).
- **Plans first**: plans and park blocks are the cards; bookings are `booked_line` (`.cz-bk`): time, icon, title, "Booked", a link to Help (`#hp-hotel`, `#hp-car`, else `/trip/help`). A day with no plan shows `#cz-empty` above its booking lines.
- **Say the plan**: editors get `#cz-say` ("Change this day", `/trip/ask?day=N`); an empty day gets `#cz-say-talk` (`&mode=talk`) and `#cz-say-paste` (`&mode=paste`). Viewers get neither.
- **Morning push** title "Today's plan · <place>", opening `/trip/canvas?day=<today>` (`morning.message(..., day=n)`); Today's heading has `#tp-open-day` ("Day plan") to the day it shows.

Tests: `tests/test_day_plan.py`, `tests_browser/test_day_plan.py` (flicks both ways, edges, not on a vertical move or a held step, the slide's direction, dates, Help, Ask links, 390 and 320). Screenshots: `F090_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_day_plan.py -k screenshots`.
