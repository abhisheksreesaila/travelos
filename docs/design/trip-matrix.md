# F-221 handoff (draft): the trip matrix, weather in the calendar, the place art, the cover

Status: draft, waiting for the founder's picks on `docs/design/trip-matrix/compare.html`.
Brief: `docs/briefs/unified-booking.md` (approved 2026-11-12). Builds: F-222 (matrix), F-223 (weather, art), F-224 (together), F-226 (report, card), F-227 (cover).

## Engine and where things are
- **Engines:** Stitch drafts (project 5068253051282871529, design system "GitAway" re-uploaded from `design/DESIGN.md` as Direction A on 2026-11-12, id 5524012603041697844) beside Claude's live HTML of the same screens, on one compare page.
- **Compare page:** `docs/design/trip-matrix/compare.html` (pick Stitch, Claude or both per screen, option and device; picks kept in the browser; Light/Dark switch).
- **Claude's artboards** (`docs/design/trip-matrix/`, open any directly, `?mode=dark` pins dark): `matrix-a.html` Grid, `matrix-b.html` Place cards, `matrix-c.html` Calendar lanes, `weather.html`, `art.html`, `together.html`, `report.html`, `cover-a.html` One stage, `cover-b.html` Editorial, `cover-c.html` Postcards. Shared: `tm.css` (Direction A tokens, light and dark), `tm.js` (sample data, shell, drawn faces), `art.js` (the place art), `icons.js` (exported from `gitaway/icons.py`).
- **Stitch:** the screen links are in `stitch/links.js` and listed below. Screenshots could not be saved: see "Open" at the end.
- **Language:** Direction A (`design-system/DESIGN-SYSTEM.md`), omxqua texture, phone motion Liquid, laptop motion the calm fade (`GA.motion.calm()`).

## Options (one line each)
- **Matrix A, Grid:** a calm table, places down and date windows across; the chosen place's December sky on a date strip above; the square's full panel beside it (laptop) or a sheet (phone).
- **Matrix B, Place cards:** the place leads; the find is one ink hero with paired art and the route; every other place is a card wearing its art, its five windows as small squares.
- **Matrix C, Calendar lanes:** the calendar is the axis; each place a lane of days wearing its own sky; the four nights a band across them; the total under each start day; the chosen trip in a bar below.
- **Cover A, One stage:** one pinned product frame; three chapters scroll past and the frame cross-fades between them.
- **Cover B, Editorial:** no pinning; a huge two-tone hero, then three tall art bands, each revealing once with a real product card.
- **Cover C, Postcards:** the three parts as three big postcards; a row that deals in (laptop), a swipe row with the next peeking (phone).
- **Designer's recommendation:** matrix C on the laptop (the weather and the calendar are one thing, the founder's "genius" idea, and the discovery reads as a band you can see across days), with A's square panel for the detail; B's place cards on the phone (a 13-day lane is a sideways scroll on 390, cards are one thumb). Cover B (nothing pinned, one reveal per section: the cure for "jittery").

## Tokens and components (names from `assets/css/tokens.css`)
- Surfaces: `--paper` canvas, `--card` tiles, `--card-2` sheets, `--paper-2` a square's resting fill; radii `--r-md` (squares 14 design px), `--r-lg` (panels 26); shadows `--sh1` tiles, `--sh2` the panel and the find, `--sh3` sheets and the tab bar.
- The find (lit square, hero, band): the inverse card `--up-bg` / `--up-fg` / `--up-fg2` / `--up-tile`; its "Found" chip uses `--beacon-acc`.
- Kinds only for kinds: flight `--k-flight`, stay `--k-stay`, drive `--k-car`, weather icons `--k-wx`; each square's three-part bar is flight/stay/drive in proportion. Days are never coloured: neutral day cells, the asked day and the chosen window in ink.
- Cheapest in a row: `--ok-ink` numbers; "Sample" and over-budget notes: `--warn-tint` / `--warn-ink`; Preview dot `--ok`.
- Numbers: Geist Mono (`--font-mono`); everything else Geist. Phone sizes: body 17, secondary 16, labels 13 (`--label-min`); nothing under `--text-min`.
- Translucency only on the laptop nav pill and the phone tab bar (`backdrop-filter`, 80% card). Every tile, square, sheet and panel opaque.
- New shared pieces to add to the system: **the square** (total, middle line for a mark or faces, the three-part bar), **the day sky cell** (icon, high, chance; dotted = typical, solid = forecast), **the band** (a window across days), **the drawn face** (`tm.js` `face()`: skin, hair, no colour code; a guest is an outlined initial), **the place art** (below).

## Place art
- One style: five flat layers (sky, far, mid, near, ground), one landmark, eight tones at most, no outlines, no text; the sky is a two-stop gradient. Ten drawn: San Diego, Los Angeles, New York, Lake Tahoe, Orlando, Palm Springs, Santa Barbara, Orange County, Honolulu, Yosemite (`art.js`; build: one SVG per place next to `places.py`'s table, fixed, never generated per visit).
- Each place has a day palette (light mode) and a night palette (dark mode) as CSS variables; the scenes use classes, so a palette is fourteen numbers.
- The weather layer is the same for every place: `data-wx` sun, cloud, rain or snow sets clouds, rain or snow and hides the sun; clouds drift (70 s and 95 s a crossing), rain and snow fall, Palm Springs' turbines turn, Orlando's fireworks bloom. All of it stops under reduced motion.
- Legibility: words sit on an opaque tile, or on the sky's top third (drawn pale in day palettes, deep in night ones); never on the busy lower half. Behind the matrix the art is a band masked to fade into the canvas.
- A place without art falls back to its kind's scene (beach, city, snow, desert, park) until drawn; never a stock photo.

## Gestures
| Screen | Gesture | What it does | Visible alternative | Threshold |
|---|---|---|---|---|
| Matrix (all) | Tap a square | Opens its panel (laptop) or sheet (phone) | The square is a button; Enter opens it | tap < 10 px travel |
| Matrix A, C (phone) | Swipe the grid sideways | Scrolls the date columns; the place column stays | Columns peek at the edge | native scroll, snap to a column |
| Matrix C | Tap a start price | Moves the 4-night band to that start | Same, with a keyboard focus ring | tap |
| Matrix B | Tap a window square in a card | That card's total cross-fades to that window | Same | tap |
| Matrix | Tap a sort chip | Re-orders cards or rows (cheapest, kids, weather, hearted) | Same | tap |
| Matrix | Double-tap a square | Hearts it (a heart pops in place) | The heart button in its sheet | two taps < 300 ms |
| Sheet (phone) | Drag the sheet down | Closes it | Centred close button | 80 px or a flick |
| Weather | Swipe the date strip | Scrolls the days | Day chips peek at the edge | native scroll |
| Weather | Tap a day | Opens its sky (sheet or panel) | Same | tap |
| Together | Tap the heart | Hearts the square (guests by first name) | The heart button beside the composer | tap |
| Together | "This one" (owner only) | Makes the square the family's trip; everyone is told | — (a button is the gesture) | tap, then a 4 s undo toast |
| Report | Share | Opens the phone's share sheet with the card and its link | Save image | tap |
| Cover C (phone) | Swipe the postcards | Next part; dots follow | Dots are buttons | scroll-snap |

## States to build
- **Loading:** the sentence and the empty grid appear at once; squares fill cheapest first; a square still searching shows "Searching" over a calm shimmer (no shimmer under reduced motion); the count says "28 of 30 in". Like map tiles, only the squares in view plus a margin are searched; scrolling reveals skeletons that fill as their answers land. While it fills, one fun fact about the place sits in the waiting space (sourced, hand-written per place), and fades when the squares land.
- **Empty:** no answers for a place: its lane says "No flights for these dates" in words, never a blank; a place with no weather says "No weather for this place yet".
- **Error:** a search that failed says so on its square ("Couldn't search · try again"), the rest stay; over the daily budget says "Today's searches are used up · back tomorrow" (F-220).
- **Long content:** 10+ places scroll inside the grid card with its header pinned; long place names wrap to two lines, never cut (no ellipsis, no line clamp: `tests/test_polish.py`).
- **Offline:** last answers stay with their age ("Preview · 3 h ago"), new searches wait; the sheet's "This one" queues.
- **Stale price:** older than its cache life, the age turns to `--warn-ink`; a hearted square that moved says "Up $40 since Ana liked it".
- **Booking:** every book action says "Booking opens soon" and saves the square to the trip; no card is taken, no partner link carries a LiteAPI price.
- **Sample:** off the showcase nothing invented is in a square, a sky or a face (`showcase.on()`); in the artboards everything is labelled Sample.

## Phone vs laptop
- **Laptop (1020 up):** the whole matrix and the square's panel fit 1440 × 900 without page scroll (A and C checked; B too); the calm desktop: new things fade in `--motion-desk`, nothing zooms or springs, a tapped square moves the ink outline only.
- **Phone:** the sentence wraps to four lines; the find card sits right under it; the grid scrolls sideways with the place column sticky (A, C) or becomes cards (B); a tapped square rises as a sheet; the tab bar floats (Book is current). Squares arrive with a settle (scale .96 → 1, `--motion-spring`, 280 ms, 40-45 ms apart, cheapest first).
- **Both:** live prices update in place without bouncing; the panel or sheet cross-fades its content when the square changes.

## Motion
- **Matrix:** arrival as above; the lit find gets no extra motion (its ink is the emphasis); hearts land with a 160 ms pop on the phone, a fade on the laptop; the band in C slides on the phone (`--motion-spring`), fades on the laptop.
- **Art:** clouds drift, rain and snow fall, turbines turn, fireworks bloom; all linear and slow (it is weather, not UI); none of it under reduced motion.
- **Cover:** scroll-driven CSS only (`animation-timeline: view()` with `animation-range`), transforms and opacity, no JavaScript scroll handlers, no layout reads, no text parallax. Each file's top comment lists every move. A: the frame is sticky; chapters cross-fade (opacity only) as each chapter's text enters 30-50%; the sentence types once; squares settle on a spring. B: as each section enters (entry 0-40%), its words fade up 16 px, the art settles from scale 1.04 to 1, the product card rises 56 px; then nothing moves. C: the cards deal in once from ±7° to ±1° (laptop) and lift 4 px on hover; on the phone the snapped card scales .94 → 1. Without scroll timelines an IntersectionObserver adds a class once; reduced motion shows everything still with fades only. B is the least jitter by construction (nothing pinned, each element moves once).

## Open
- **Stitch screenshots are not saved.** The CLI (v0.11.1) returns each screen's screenshot and HTML only as `files/…:download` links that need the Stitch sign-in token, and its preview server and `find screens` do not list the new screens. The compare page shows the Stitch canvas link for each draft instead. To save them: open each link in Stitch and export, or give the CLI a working download path.
- The first Stitch batch (19 screens) ran with an empty prompt by mistake and drew a generic shell; those screens are in the project with "F-221" titles and the IDs in `stitch/links.js` under `stray`. Delete them only with the founder's yes.
- Stitch drew five of the "phone" drafts as laptop screens (art, cover A, cover B, report, weather) despite `--device MOBILE`; regenerate those if the founder wants Stitch's phone take on them.
