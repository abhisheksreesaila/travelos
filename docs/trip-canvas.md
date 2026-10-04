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

## Tests

`tests/test_trip_canvas.py` (every level, link and button, roles, fragments), `tests/test_canvas_ticks.py` (the coalesced card, `canvas.plan`), `tests_browser/test_trip_canvas.py` (390 and 320: tap, pinch, Back and Forward, the named element, reduced motion, no-transition fallback, Mark done and Set aside, lanes, no sideways scroll, 44px targets, 13px text; 1280: the wide day view). Screenshots: `F081_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_trip_canvas.py -k screenshots`.
