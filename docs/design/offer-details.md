# Design handoff: flight and stay details (F-025, F-026, F-027)

**Approved:** 2026-09-30, layout A. Canvas: https://claude.ai/artifact/N9nH46TYpma8kyxU6Bad8o
Artboard sources: `docs/design/canvas/Details-A.dc.html` (stays), `Details-Flight.dc.html`, `Details-Phone.dc.html`. `Details-B.dc.html` was rejected: the always-on summary card used space only to repeat the price.
**System:** `design-system/DESIGN-SYSTEM.md`. Build every page head with `layout.styles(...)`. The canvas prices and room data are the fixture to move into `gitaway/catalog.py`.

## F-025 Split view
- Expanding the Stays or Flights pane grows it over the workspace. The pane header keeps the key badge, the title and the count, and adds "Esc back to workspace" plus a collapse button.
- Body grid: a 340px list sidebar (`#FFFCF8`, offer cards; the current one gets the selected ring, and the lane's pick gets an ink "YOUR PICK" pill) and a detail column.
- The detail column scrolls. A dark ink bar is pinned at its bottom: the offer name, a one-line summary of the choice, its price in display type, and the coral tactile "Choose this stay" / "Choose this flight" button (label "Chosen" after choosing).
- The top-bar ledger stays visible and updates live.
- Motion: spring-y morph from the tile to the split view (no overshoot on the layout itself); reduced motion swaps instantly.
- Phone: the list and the detail are separate screens. The detail has a photo header with a "‹ Stays" back pill and the same ink choose bar.

## F-026 Stay detail
- **Look around**: a tablist with Photos (default) and "Explore the area in 3D".
  - A nearby strip ("3 min walk to the beach · …", the first three points of interest) is always visible.
  - **Photos**: a 2fr/1fr/1fr grid. The big tile is the area photo, captioned "The area · <area>". The others are CC0 sample photos, each captioned "Sample photo · <label>". Source real CC0 photos and credit them in `assets/photos/CREDITS.md`.
  - **Explore**: loads on first open only, with a skeleton ("Loading the aerial view…") and then the map. The map is a 310px CSS-3D plane (rotateX 42°): land, a streets pattern, an ocean and beach band for coastal hotels, and a park. Pins stand up off the plane: a tint pill with an icon and a short label, with the hotel in ink.
  - Selecting a pin (on the map or in the list on the right) translates the plane to centre it over 0.7s and shows its kicker, name and note. There are "turn the view" (+30°) and "back to the hotel" buttons. The map is captioned "Illustrated map · not to scale". Points of interest per hotel are in the artboard's `POIS`.
- Title, rating and tilted sticker chips; a highlights card.
- **Rooms**: "Pick your rooms" with a fit badge: "Room for all 4" (mint), "Sleeps n of 4 · add a room" (sun), or "Pick at least one room" (bubble). Three room cards each show a sample photo, a view chip, name, beds · sleeps, price per room for the stay, and a − n + stepper (0–4). Choose is disabled until the rooms sleep the whole party.
- **Add-ons**: toggle pills (aria-pressed) with a check dot: Breakfast for 4 +$320, Late checkout, 2 PM +$40, Parking, 4 nights +$180.
- Cancellation policy on a mint card.

## F-027 Flight detail
- Out and back leg cards (`#F4F9FF`): big times, airports, duration, a line with a stop dot (coral when there's a stop), and the aircraft.
- "Pick a fare": a radiogroup of three cards (Basic, Main +$240, Extra legroom +$560). Each shows its price and four perks, ticked in mint or dashed in grey.
- A checked-bags stepper at $70 per bag round trip; Extra legroom includes 4.

## States
- Empty: no room picked → the fit badge says so and Choose is disabled.
- Loading: the explorer skeleton.
- Long content: the detail column scrolls; the choose bar stays pinned.
- Mobile: two screens. No sideways scroll at 1440, 1280, 1000, 800, 390 and 320. No ellipses (see docs/lessons.md).
