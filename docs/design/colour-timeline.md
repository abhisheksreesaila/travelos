# Design handoff: the colour timeline

Brief: docs/briefs/colour-timeline.md (approved 2026-10-15) · Engine: Google Stitch, project 5068253051282871529 (design system = design/DESIGN.md)
Frames (chosen, "restrained"): docs/design/colour-timeline/restrained/ct-{day,add,move,week}-{desk,phone}.png (+ .html). The first, too-colourful round is in docs/design/colour-timeline/ for contrast only.
Languages: phone = GitAway playful structure with Liquid motion; laptop = the same look, calm motion (F-156). One look on both.

## Read the frames as direction, not pixels
Rebuild on the existing hour grid (`tripcanvas.time_grid`, `assets/css/day_grid.css`), never Stitch's HTML (Tailwind). Stitch got these wrong; do not copy:
- serif text in some phone frames (we use Bricolage Grotesque for display, Figtree for the rest)
- rail labels colliding ("12:30" over "12 PM"): on our grid a plan's start time replaces the hour label it falls on or near
- cards not sized by duration (ours are: `--s`, `--l`)
- the doubled day chips at the bottom of ct-move-phone; invented details (weather tips, "Keyless ready", "Family vote pending", "Active draft inspector", gap labels such as "2h 58m buffer")

## Tokens and components (all from assets/css/tokens.css; no new hex)
- **Day panel**: `--card` with a 1px `--hairline` edge, radius `--r-card`; page ground `--paper`. No day tint anywhere.
- **Day chips** (`.cz-dpills`, laptop day tabs): neutral pill, `--card` fill, `--hairline-2` edge, `--ink` text; the open day solid `--ink` with `--card` text; today keeps a small ring. No coloured dots or keys per day.
- **Time rail**: a 1px `--hairline` vertical line. Hour labels small (`--ink-3`, 600). Each plan and booking prints its **start time** on the rail at its top: Bricolage 800, about 1.5× the hour label, `--ink`, with "AM/PM" small under it; an hour label within 30 minutes of a printed start time is hidden.
- **Plan card**: `--card`, 1px `--hairline`, radius `--r-sm`–`--r-card`, a 3px left edge in the kind's colour (`KIND_TINT`: fun bubble, food sun, outdoors mint, culture grape, travel sky). An **icon tile** (design 40px, radius 12) filled with the kind's `-tint` and its icon in the kind's `-ink`. Title Bricolage 700 in `--ink`; time and detail Figtree in `--ink-2`. A minimum height keeps a short plan readable (title on one line).
- **Booking**: the same card shape, its kind's icon tile (flight sky, hotel grape, car ink), a grey `BOOKED` pill (`--paper-2` fill, `--ink-2` text, caps 11px 700). Bookings stay non-draggable.
- **PLAN / BOOKED labels**: grey pills only, never coloured.
- **Up next**: the one solid `--ink` card (unchanged); its primary action coral.
- **Coral** (`--coral`, `--coral-deep` for text) only for: primary buttons, the now line and its time, a plan's rail time while it is being moved or drafted.
- **Shadows**: none at rest; `--shadow-lg` only on a lifted (dragged) card.

## States
- **Empty day**: the rail with a soft dashed "Free day · Say the plan" slot (the week's free-day look) instead of an empty grid.
- **Adding** (F-101 behaviour): the draft opens in the touched gap with a dashed `--coral` edge, the title field focused ("What's the plan?"), a row of kind chips (each with its kind's tint and ink), "Drag the edges to change the time"; its rail time shows in coral. On the laptop the panel shows the draft too.
- **Moving** (F-097/F-151 behaviour): the lifted card follows the pointer with `--shadow-lg`; the old slot shows as a faint dashed ghost; the landing slot is dashed; the rail time turns coral and updates live; a day chip under the pointer becomes an ink-dashed drop target ("Drop to move to Sat 17").
- **Long content**: titles wrap to two lines then fade; detail one line.
- **Loading / offline**: unchanged (skeletons and the existing offline note).

## Gestures (unchanged behaviour, new look)
| Gesture | What it does | Visible alternative | Threshold |
|---|---|---|---|
| Hold empty time (phone) / click empty time (laptop) | Draft a plan there | "Say the plan" button | existing F-101 hold time |
| Hold-drag a plan / mouse drag | Move it in time | Plan menu → time | existing F-097 |
| Drag a knob / an edge | Change its length | Plan menu → time | existing F-097/F-110 |
| Drop on a day chip / a week column | Move to that day | Plan menu → Move to day (F-152) | existing F-151/F-157 |
| Tap Day / Week | Switch level | the switch itself | n/a |

## Phone vs laptop
- **Laptop** (≥1020px, not the installed app): the day on the left with the docked panel on the right (unchanged layout); the week is the days as columns on **one shared time axis** (items at their times, coloured by kind only, neutral column headers with weekday, date and the day's title), scrolling sideways on a long trip.
- **Phone and installed app**: the same day card, rail and cards in one column with the floating tab bar; the week is a stack of white day cards, each with a mini hour bar (kind-coloured segments) and its items as compact rows.
- Tablet follows the phone.
