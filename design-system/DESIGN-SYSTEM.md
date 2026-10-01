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
- Floor: text never goes below 13px on a phone. On desktop the 13px caption size shows at 9.75px, which is the intended 75%.

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
