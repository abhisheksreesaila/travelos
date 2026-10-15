# Brief: the colour timeline (the trip's new look, phone and laptop)

Status: approved (captain, 2026-10-15: "approved")
Designs: docs/design/colour-timeline/restrained/ (Stitch project 5068253051282871529; captain, 2026-10-15: "direction is right and I like it")

## Why
The calm laptop skin (F-158) is "okay, not the best": flat and tidy, but it lost GitAway's joy. The phone and the laptop also look like two products. The captain wants one look on both, where you read the time at a glance ("you look at it and you know exactly what the time is") and colour helps without shouting.

## Who
The captain's family, on the iPhone during the trip and at a laptop before it (1440×900 and 1280×800 at 100% zoom).

## What
1. **The day as a colour timeline.** A time rail down the left. Each item sits at its real time and is as tall as it lasts. Its start time is printed big on the rail beside it (e.g. "12:30" with a small "PM"), so the time needs no reading inside the card. Empty hours stay visible as gaps.
2. **Restrained colour.** Colour means the kind of thing only: the icon tile (food sun, outdoors mint, hotel grape, flight sky, fun bubble) and a thin left edge on the card. Days are never coloured: neutral day chips, the selected one solid ink, white day panels. PLAN and BOOKED are quiet grey pills. Coral only for primary buttons, the moving time, and a thin "now" line across today's timeline (assumed). Up next stays the one solid ink card.
3. **Add, move and day↔week keep today's behaviour, in the new look.** Add: touch empty time and a dashed draft opens in that gap, ready to type, with kind chips. Move: lift and drag; the old slot shows as a ghost, the landing slot is dashed, the rail time turns coral and follows the finger; day chips are drop targets; the knobs resize. Week: the phone shows a stack of day cards, each with a mini hour bar; the laptop shows the days as columns on one shared time axis (a long trip scrolls sideways, as today).
4. **It replaces the F-158 calm skin on the laptop and the current day look on the phone, laptop first.** The laptop day ships first, then the phone, then add/move and the week on both. Motion stays as it is: liquid on the phone, the short fade on the laptop (F-156).

## Not now
Gap labels between plans ("Drive to Santa Monica · 1h", which needs real travel times): a later ticket. Family, trip details, Start and the map keep their current look except for shared pieces (chips, cards, buttons) (assumed). Invented details from the Stitch frames (weather tips, "Keyless ready", "Family vote pending") are not built.

## Look and feel
Joyful, calm, clear. GitAway's colours and fonts (Bricolage Grotesque, Figtree), never a serif. Feels like Apple Calendar's day view with Airbnb's warmth. The screen that matters most is the day: open it and know what's next and when.

## How we'll know
On the phone and on the laptop, the captain can say what time each plan starts without opening it, and finds no day colours. Adding, moving and switching to the week work exactly as before. The laptop still fits at 1440×900 and 1280×800 with no page scroll.

## Decisions and trade-offs
- Colour only for kinds, never days. Pro: works for a 20-day trip, calmer. Con: days are told apart by name and date only.
- Time rail plus a real time grid, not a list. Pro: time at a glance, and drag-to-time keeps working. Con: short plans make small cards (a minimum height keeps them readable).
- Gap labels later. Pro: the skin ships without a maps dependency. Con: the gaps stay plain for now.
- One look on phone and laptop, laptop first. Pro: one product. Con: the phone's ink day header and playful ledges go.

## Open questions
-
