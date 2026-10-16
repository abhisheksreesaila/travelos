# GitAway design system

This project's own system. It replaces the house Terminal Ledger style (brief: "explore a new direction").
Feel: **joyful, trustworthy, alive**. Airbnb-playful (tactile, soft depth, warm photos), colorful like a kid's site, with Apple-level spacing and restraint.
Source canvas: https://claude.ai/artifact/NvLT3Tjf4XUwPbyZ4m6d2Q (brand sheet artboard). The artboard sources are committed in `docs/design/canvas/` (open any `.dc.html` as a reference; values there match this file).
Sample data uses US units (°F, $) for US trips.

## Scale (F-030)
The site renders at **75%** of the size it was first drawn. One number does it: `:root { font-size: 12px }` in `tokens.css`, and every length in the CSS is `rem`. On phones (viewport ≤ 720px) the root returns to 16px, so phone type and touch targets are unchanged.
- **Every size in this file is the design number at a 16px root.** Write it in CSS as `px / 16` rem (button 56px = `3.5rem`, radius 28px = `1.75rem`). On desktop and tablet it shows at 75% (button 42px, body 12.75px); on a phone at 100%.
- Never write `px` for a size, gap, radius, shadow offset or icon. The only `px` allowed are 1px hairlines (borders, rings) and the viewport breakpoints. `tests/test_scale.py` fails on any other.
- Breakpoints are viewport widths and follow the scale: a layout that switched at 1100 now switches at **825**. Phone is ≤ 720 (unchanged). Use these: 720 phone, 825 tablet, 900 and 975 and 1020 for the landing and itinerary collage. Container queries use rem.
- JS that needs pixels (pointer maths) reads the root size: `parseFloat(getComputedStyle(document.documentElement).fontSize)`. The calendar hour is 3rem (`HOUR_REM` in `calendar.js`, `HH` in `calendar.py`).
- `icon(name, size)` takes the design size in px and emits it in rem. Hand-written inline SVG must set `style="width:Xrem;height:Xrem"`.
- Floor: text never goes below 13px on a phone and phone touch targets are at least 44px (F-034): `--text-min` is 13px on phones. On desktop and tablet nothing renders under 11px: any font size below 0.9167rem is written `max(var(--text-min), Xrem)` (`--text-min` is 11px on desktop and tablet, 13px on phones); `tests/test_scale.py` checks it.

## Type
| Role | Family | Use |
|---|---|---|
| Display | Bricolage Grotesque 700–800, tracking −0.02 to −0.04em | Page and day titles, big numbers, totals |
| Body | Figtree 400–800 | Everything else. Body 17px, labels 15px, minimum 13px (design numbers at the 16px root; see Scale) |
| Hand | Caveat 700 | Traveler notes and photo captions only, never UI |

Load from Google Fonts. Fallbacks: `'Segoe UI', system-ui, sans-serif` and `cursive`.

## Colour
Ink text sits on every fill; white text only on Ink.

| Token | Hex | Role |
|---|---|---|
| `--ink` | #1E1A2E | Text, booked items, strongest buttons |
| `--ink-2` | #4A4460 | Secondary text (≥ 6:1 on paper) |
| `--ink-3` | #5A5470 | Captions and labels |
| `--paper` | #FFF8EE | Page ground (Sunset theme) |
| `--card` | #FFFFFF | Surfaces |
| `--coral` / `--coral-deep` | #FF7352 / #C9431F | Primary action and its ledge. Deep is for accent text and link hover on paper or white only (≥ 4.6:1), never text on tints (< 4.5:1) |
| `--ink-ledge` | #000000 | Ledge under ink "Book" buttons |
| `--sun` / tint #FFF1C2 | #FFC93C | Kid friendly, highlights, weather |
| `--mint` / tint #D4F7EA | #48D1A0 | Pet friendly, nature |
| `--sky` / tint #DDEEFF | #5AB0FF | Travel, info, map |
| `--grape` / tint #ECE4FF | #C3B2FF | Culture |
| `--bubble` / tint #FFE3F1 | #FF8CC6 | Couple friendly, fun |
| `--block-sunset` / `--block-pacific` | #FF8A63 / #6DB8FF | Landing hero door panels (door one, door two). Ink text only; not for buttons or small text on other surfaces |

**Itinerary themes** (one layout, the contributor picks a theme):

| Token | Sunset | Pacific |
|---|---|---|
| ground | #FFF8EE | #F4F9FF |
| accent | #FF7352 | #3B9BFF |
| accent-deep | #C9431F | #1B5FB8 |
| accent-2 | #FFC93C | #48D1A0 |
| tint (panels) | #FFE6DA | #DDEEFF |
| tape (primary strip) | rgba(255,201,60,.75) | rgba(72,209,160,.60) |
| tape-2 (second strip) | rgba(255,115,82,.55) | rgba(59,155,255,.45) |
| note slip | #FFF1C2 | #D8F6EA |
| timeline dots | #FFB59F | #9CCBFF |

Day colours cycle sun, mint, grape, sky, bubble. Big day numbers use a deeper ink per tint, sized 24px or more: #8A6200 on sun (4.9:1), #16865F on mint (4.0:1), #6A4FD6 on grape (4.6:1), #1B6FC9 on sky (4.3:1), #C23B82 on bubble (4.1:1).

## Shape and depth
- Radius: 12 (small), 16–20 (cards and offers), 28 (panels, day cards), 36–44 (hero blocks), 999 (pills and stickers).
- Radius 10 is the polaroid frame only.
- Shadows are neutral and layered. The one exception is an accent glow (`0 12px 24px -10px var(--accent-deep)`), which only the hero's primary action and the app mark get:
  - sm `0 2px 3px -1px rgba(0,0,0,.1), 0 0 0 1px rgba(25,28,33,.08)`
  - md `0 0 0 1px rgba(0,0,0,.06), 0 3px 3px -1.5px rgba(0,0,0,.06), 0 12px 12px -6px rgba(0,0,0,.06)`
  - lg `0 6.7px 5.3px rgba(0,0,0,.048), 0 22.3px 17.9px rgba(0,0,0,.072), 0 41.8px 33.4px rgba(0,0,0,.086)`

## Signature components
- **Tactile button**: always a pill (radius 999), 56–64px tall, fill plus a 4px solid ledge shadow in its deep colour (`0 4px 0 var(--coral-deep)`). Hover = `translateY(-1px)` and a 5px ledge. Pressed = ledge 0 and `translateY(4px)`. Primary is coral with ink text; "Book" is ink with white text on the `--ink-ledge`; secondary is white with an ink-12% ledge.
- The app mark alone keeps its bigger brand-sheet glow (`0 20px 30px -12px`) at large sizes; in app chrome it uses the standard ledge only. The Caveat tagline is brand art, never app chrome.
- **Focus**: every link and button gets `outline: 3px solid var(--ink); outline-offset: 3px` on `:focus-visible`. On ink surfaces use a #FFC93C outline. Focused workspace panes get the same ring at radius 26.
- **Sticker tag**: pill 44px, full-strength palette fill (sun, mint, sky, bubble), 3px white border, sticker drop `0 6px 14px -6px rgba(30,26,46,.35)`, rotated −3° to +2°. Small inline tags are 24–28px, full-strength fill, no border, no tilt.
- **Booked pill**: ink fill, white 13px caps "BOOKED". Booked calendar and board items use an ink card with white text.
- **Polaroid**: white frame 12–14px (bottom 50–56px for a Caveat caption), radius 10, lg shadow, rotated ±4–6°, with the theme's tape strips.
- **Note**: Caveat 26px on a tint slip, rotated −1.5°.
- **Pane** (workspace): white, radius 26, md shadow, header = number key badge (26px, tint) + display title 19–21px + count + expand icon button.
- **Offer card**: radius 20, fill #FAF7F2. Selected = #FFF4EF fill and a 3px coral ring.
- Icons: inline stroke SVG, 2–2.4 stroke, round caps, ink colour. No emoji.

## Motion
- **Pop in**: spring overshoot, 320–450ms (`cubic-bezier(.2,.9,.3,1.3)`), for stickers, cards and new items.
- **Bob**: stickers float 6px on a 4.5s loop, at most two per screen.
- **Skeleton to itinerary**: skeleton blocks #F2ECE3 at the real shapes' radius, with a lighter band (#FBF7F1) sweeping across every 1.4s, linear. When content lands, each block cross-fades (opacity plus 8px rise) over 400ms ease-out, with days staggered 120ms apart.
- **Celebrate**: a single confetti burst in palette colours on booking or forking. Never loops.
- **Reduced motion**: everything settles instantly; no loops.

## Laptop skin (F-158)
Captain, 2026-10-14: FINXPLORER's structure, GitAway's colours, light only. Applies to signed-in pages on a desktop (≥1020px, not the installed app); the phone and the landing keep the playful, tactile look above. Board: `docs/design/canvas/Web-Calm-v1.html` (frames C1–C3; C4 dark was not chosen).
- **Surfaces**: white cards with a 1px hairline (`rgba(30,26,46,.10)`), radius 14 (design 18.67 → write 1.1667rem at the 12px root), no layered shadows; sections split by hairlines.
- **Headings**: a small eyebrow (11.5px, 700) over a two-tone Bricolage title ("Friday. *Fly in, check in.*"). On other pages the eyebrow and the second phrase are coral-deep; on the day and the week (F-159) they are grey `--ink-3`, since coral there is for primary buttons and the now line.
- **Top bar**: flat on paper with a hairline under it; text links, the current one ink with a 2px coral underline.
- **Buttons**: flat pills, no ledge — primary coral with ink text, secondary white with a hairline.
- **Data rows**: tile (30px, the kind's tint with its deep ink, initials or icon) · name (700) over a muted detail · right-aligned time; hairline between rows.
- **One accent block per screen**: the ink Up next card. Day colours are gone from the day (F-159, below) and the week (F-162, below).
- **Motion**: the calm desktop fade (F-156).
- **Code**: one file, `assets/css/desk_skin.css`, loaded last by `layout.styles()` on every page. Every rule sits in the desktop query and under `:root:has(.ga-topbar)` (the signed-in pages' top bar), so the phone, the tablet, the installed app, signed-out pages and the landing never match it. It makes `--shadow-sm` and `--shadow-md` a zero shadow (not `none`: that would void the plan blocks' `inset … , var(--shadow-sm)` lists), keeps `--shadow-lg` for what floats (menus, a lifted plan), and uses the tokens `--hairline`, `--hairline-2`, `--coral-tint`, `--r-card`. The second phrase of a heading is a sibling `<span class="ga-h-two">` after the `<h1>` (hidden everywhere else), so the title's own text is unchanged. `tests_browser/test_calm_skin.py` pins the rules.

## The colour timeline (F-159)
Brief `docs/briefs/colour-timeline.md`, handoff `docs/design/colour-timeline.md` (frame `ct-day-desk`). On the laptop day this replaces the F-158 underlined day tabs with a colour key per day and the tinted plan blocks. Colour means the kind of thing only; days are never coloured.
- **Panel**: `--card` with a 1px `--hairline` edge on the paper ground; no day tint anywhere.
- **Day tabs** (`.cz-hchip`): neutral pills (`--card`, `--hairline-2` edge, `--ink` text); the open day solid `--ink` with `--card` text and its title; today ringed in ink. No coloured keys.
- **Rail**: a 1px hairline down the left of the grid. Every plan and booking prints its start time on it at the card's top: Bricolage 800 1.4167rem with a small AM/PM under it and a dot in the kind's colour on the rail (`.cz-g-start`, from `tripcanvas.rail_starts`; a label is `RAIL_ROOM` = 35 minutes of the docked day's 4.5rem hour, handed to the CSS as `--rail`; starts closer than that slide apart, equal minutes share a label). An hour label within 30 minutes of a printed start, or under its label, is hidden (`.is-near`), so labels never overlap.
- **Plan card**: `--card`, a hairline, radius `--r-sm`, the kind's 3px left edge (`--accent`, the inset shadow), a 2.5rem icon tile (`--tint` fill, the kind's `-ink` icon via `--kink`), a Bricolage 700 title, a grey PLAN pill right after the title, the time in `--ink-2`. A card keeps its true height, so cards never cover each other: under 45 minutes it is one compact row (1.5rem tile, title on one line, a long one fades at the edge); 45 to 75 minutes is title row plus time.
- **Booking**: the same card with its kind's tile (flight sky, hotel grape, anything else ink, by its `data-kind`) and a grey BOOKED pill (`--paper-2` fill, `--ink-2`, caps). Its time is on the rail; the link's `aria-label` still says it. A booking under a plan stays a slim pill, in the same white card style.
- **Pills**: PLAN and BOOKED are grey, never coloured.
- **Coral** only for primary buttons, the now line and its time (and drop or draft states, F-161). Up next stays the one ink card.
- **Code**: the new markup (rail starts, tile, PLAN pill, the day chips) is in the page at every width. `desk_skin.css` draws it on a laptop; `day_phone.css` (F-160) draws the same look below 1020px and in the installed app. `tests_browser/test_colour_day.py` pins the rules at 1440 and 1280, `test_colour_day_phone.py` at 390 and 800.
- **Phone and tablet (F-160)**: one column: the plain heading (the way back, the two-tone day title, map, SOS), the neutral day chips (the open one with its title), the filters, the ink Up next card (today), then the white day panel. The ink day header, the coloured date pills (`.cz-dpills`) and the tablet's week strip are gone; the folded bar is white with a hairline. Sizes are `--pu` (one phone rem: 1rem on a phone, 4/3 rem on a tablet), text never under `--tmin` (13px), every target at least `--tap` (44px). The rail label's box is `--rail` minutes of the real hour (`--mm`), so it fits the phone's 72px hour and the tablet's 66px one. A plan keeps the phone's 44px minimum, and plans whose drawn boxes (at least `TOUCH_MIN` = 40 minutes tall) would collide sit side by side (`--tlane` of `--tlanes`, not only when their times overlap; the laptop keeps `--lane`). A plan under 45 minutes is compact: up to 720px wide two short lines in its 44px (the title, the time; no PLAN pill), wider one row that keeps its PLAN pill. A side-by-side plan (`.is-lane`) drops its tile and pill and shows its start alone (`.cz-gb-st`; the link's label has the whole time); its title wraps instead of fading. A short title's right padding equals its fade (0.75rem), so a title that fits is never faded. A title wraps to two lines and stops.

## The week on one time axis (F-162)
Brief `docs/briefs/colour-timeline.md`, handoff `docs/design/colour-timeline.md` (frame `ct-week-desk`). The laptop week (1020px up, not the installed app) is one white panel: an hour axis on the left, a column per day. Same rules as the day: colour is the kind only.
- **Axis**: a sticky first column of hour labels (Figtree 600, `--ink-3`, a label centred on its hour line), 7 AM to 10 PM unless an item is earlier or later in any day. Hour lines are a hairline background of each column.
- **Hour height** comes from the window: the axis is one box tall (percentages of it), so 15 hours fit under the heading without a page scroll at 1440x900 and 1280x800; below 2.25 rem an hour the panel scrolls inside itself.
- **Column header**: neutral, the link that opens the day: "Fri 16" (Bricolage 800), a grey `--paper-2` "Day 1" pill (ink "Today" pill on today), the day's title in `--ink-2`. No tint, no coloured key.
- **Card**: `--card`, a hairline, `--r-sm`, the kind's 3px edge (`--accent`), the kind's tile (`--tint`, icon `--kink`); title Bricolage 700, time Figtree in `--ink-2`, a grey PLAN or BOOKED pill. A card is as tall as it lasts (at least 30 minutes), so at a narrow column the layout steps down with its height: one row under 60 minutes, small tile and one-line title to 90, the full card from 90; side by side with another it is the title and start time only. Pointing at a card opens it down to show everything.
- **Free day**: a soft dashed `--hairline-2` slot the height of the column, "Free day", "Nothing planned yet", Say the plan.
- **Code**: `gitaway/pages/weekdesk.py`, `assets/css/week_desk.css` (the old numbered day cards and the F-158 week rules in `desk_skin.css` are gone). `tests_browser/test_week_axis.py` pins it with real rects.
