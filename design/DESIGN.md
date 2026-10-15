# GitAway design system (for Stitch)

GitAway is a family trip planner: one shared trip (days, plans, bookings, family chat, an Ask box you speak or type into). Feel: joyful, trustworthy, alive, calm. Warm and colourful like a kid's site, with Apple-level spacing and restraint. Light mode only.

## Colour (keep exactly)
- Ink `#1E1A2E` (text, booked items, strongest surfaces). Secondary text `#4A4460`, captions `#5A5470`.
- Page ground: warm paper `#FFF8EE`. Surfaces: white `#FFFFFF`; a step darker `#FAF7F2`.
- Hairline `rgba(30,26,46,0.10)`; control edge `rgba(30,26,46,0.16)`.
- Primary action: coral `#FF7352` with ink text; coral-deep `#C9431F` for accent text on white/paper only. Coral tint `#FFE6DA`.
- Day and kind colours (fill / tint / deep ink for text on the tint):
  - sun `#FFC93C` / `#FFF1C2` / `#8A6200` (food, kid friendly)
  - mint `#48D1A0` / `#D4F7EA` / `#16865F` (outdoors, nature)
  - grape `#C3B2FF` / `#ECE4FF` / `#6A4FD6` (hotel, culture)
  - sky `#5AB0FF` / `#DDEEFF` / `#1B6FC9` (flights, travel, map)
  - bubble `#FF8CC6` / `#FFE3F1` / `#C23B82` (fun, going home)
  Days cycle sun, mint, grape, sky, bubble. Ink text sits on every fill; white text only on ink.

## Type
- Display: Bricolage Grotesque 700–800, tight tracking (−0.02 to −0.04em): page and day titles, big numbers.
- Body: Figtree 400–800: everything else.
- Hand: Caveat 700, only for traveller notes and photo captions, never UI.

## Shape
- Pills (radius 999) for every button, chip and tab.
- Cards radius 14–20; big panels 28.
- Icons: thin rounded stroke icons in ink. Never emoji.

## Rules
- Bookings (flights, hotels, cars) read as confirmed: a quiet "BOOKED" label.
- One accent block per screen at most (e.g. the "Up next" card in ink).
- Phone: floating glass tab bar at the bottom (Today, a centre Ask button with a mic, Trip), big thumb targets (48px), bottom sheets instead of dialogs.
- Laptop: fits 1440×900 at 100% with no page scroll; calm, no heavy shadows.
