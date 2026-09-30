# Design handoff: demo sign-in, one-tap pay, celebration (F-017, F-018)

**Approved:** 2026-09-30. Artboard: `docs/design/canvas/Checkout.dc.html` (its 1-2-3 switch is a prototype control only, not part of the product).
**System:** `design-system/DESIGN-SYSTEM.md`. Build every page head with `layout.styles(...)`.

## F-017 Demo sign-in
- `/signin?next=<local path>&intent=<save|pay|invite|fork>`: a centred dialog card (radius 32, lg shadow) with a "One tiny step" sticker, a title that depends on the intent ("Sign in to book this trip" / "…to fork this trip" / "…to invite your crew" / "…to save this trip"), a one-line promise, and two demo travelers as big buttons (Ari Rivera, family; Sam Kim, couple). The chosen one gets the coral ring.
- Choosing a traveler is a POST that stores the demo traveler in the session and redirects to `next` (local paths only, never an open redirect). With `intent=fork` it also adds the trip to that traveler's forks list (kept in the session for now).
- Header "Sign in" shows the traveler's avatar and a Sign out link once signed in. Already signed in and visiting /signin: go straight to `next`.
- Footnote: "Real sign-in with Google comes later. Nothing here leaves your browser."
- Full-page on phones; focus is kept inside the dialog; Esc and Cancel go back.

## F-018 Pay and celebrate
- "Book this trip" (signed in) opens a bottom sheet over the dimmed workspace. It shows the trip title and dates, three lines (flight, stay, car) with icon tiles and prices from `catalog.quote`, the all-in total, a "Demo card ending 4242 · <traveler> pays" row, an ink "Pay $X" button, and the note "Simulated checkout. No money moves and nothing is really booked."
- Pay records the booked trip for the traveler (session), then shows the celebration: a coral block card saying "You're going to LA!" with a plane badge, flight and hotel chips, confetti in palette colours (once, 1.8s, off with reduced motion), and an ink "Open my trip calendar" button (it goes to the calendar, F-019; until then a friendly placeholder).
- Refresh or retry must not double-book.
