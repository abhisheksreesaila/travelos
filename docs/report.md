# Autopilot report: booking, partners and creators (2026-11-04 → 05)

Branch `autopilot/booking-creators`, not merged to master, not deployed.

## How far it got
`scripts/check`: M1 PASS · M2 PASS · M3 PASS · M4 PASS · M5 PASS · M6 PASS (full suite included). The reviewer passed it with no blockers.

- **M1 Four places:** LA, San Diego, Honolulu, New York from SFO, each with its own flights, stays, cars, weather, events and news (synthetic, deterministic).
- **M2 Partner seam:** `gitaway/partners/`: Aviasales (flights), Klook (stays and cars, F-179), Uber deep link, all built Travelpayouts-shaped (marker, SubID). Every offer has a "Book on <partner>" link through `/go/…`. With `TRAVELPAYOUTS_MARKER` set it becomes a real tracked link (Aviasales marker, Klook partner-links API); without one it goes to an in-app sandbox checkout.
- **M3 Loop closes:** completing the sandbox records a conversion with an estimated commission and puts the booking in the trip as "Booked elsewhere · <partner>". `/partners` lists the family's clicks and bookings.
- **M4 Creators:** four creators with profiles at `/creators/<handle>`, trips with fork counts and "Plan this trip". The paste-a-link import still works.
- **M5 omxqua Travel · Coast** on /plan, creators, sandbox and /partners. On a phone the lanes swipe with a segmented switcher and every control is at least 44px; on a laptop the lanes sit side by side.

## 30-second demo
```
cd ../travelos-autopilot && pixi run dev   # http://localhost:5002
/plan?to=hi&d=2027-03-05&r=2027-03-09&a=2   → tap "Book on Aviasales" → Complete booking → /partners
/creators → a creator → Plan this trip
```
Screenshots: `docs/report/m5-*.png` (phone + laptop).

## Worth a second look
1. Commission estimates (D-71): flights 1.1%, Klook 5%. Estimates until Travelpayouts statistics are wired. Program ids are gone (F-179).
2. Phone lanes (D-54): `.ws-grid` itself is the swipe scroller. Try it on your iPhone.
3. No night mode yet (D-51), and the landing page is still the old look. Only the booking, creator and partner pages are in Coast.

## Next
Captain: try it on the phone and merge if it feels right. Then create the Travelpayouts Project and set `TRAVELPAYOUTS_MARKER`/`TOKEN` in Railway (the links go live with no code change). Then move the landing and trip canvas to Coast.

# Autopilot report, run 2: the trip grid (2026-11-11 → 12)

On `master`, not pushed, not deployed. Ticket F-217, decisions D-416 to D-423.

## How far it got
`scripts/check`: M1 to M10 all PASS (the whole suite included). A reviewer agent asked for changes (a crash on `b=²`, a typed year ignored, the sentence reader guessing in four places, a verdict that contradicted its own word, unsourced wording, the sample label below the fold); each is fixed and has a test.

- **M7 The sentence:** "A family of 4 with Grandma and the dog, SFO to Orlando, Dec 12 to 16, within 20 miles of Disney, under $3,000." is read part by part by plain rules and written back. What it cannot read it names; it never guesses.
- **M8 The sums:** every flight added to every stay; the first day for kids, an older traveler and a pet, from the flight's times, the drive and the stay's own tags.
- **M9 The pages:** `/plan/grid` and `/plan/grid/trip`, plain links first, booking on the partner's site, 404 off the showcase.
- **M10 The feel:** the grid leads; the search folds into an island going down and the panel into a rail going sideways; a phone gets a card a stay with squares that swipe; light and dark.

## 30-second demo
```
pixi run dev    # http://localhost:5002
/plan/grid?to=nyc&senior=Grandma&pet=dog&b=4600     move over a square, switch Price / Ease, tap "under $4,600"
tap the pencil and type: 2 adults to San Diego, Dec 12 to 16, under $2,000
tap a square → Your trip → Book on Aviasales / Klook
```
Screenshots: `docs/report/f217-*.png` (laptop at rest and folded, a pick in light and dark, the phone in light and dark).

## Worth a second look
1. **The sample grid is small** (D-423): three stays a place, so on a laptop it does not scroll and the islands never show. They are proven on a stand-in of 8 flights by 10 stays in the browser tests; to see them yourself, make the window short.
2. **The Ease weights are mine** (D-418): the constants at the top of `gitaway/tripgrid.py`.
3. **What was left out, each for want of a source** (D-421, ticket F-219): fares under the days, family likes, tips from GitAway trips, kinds of trip, the small map, distance to "near …".

## Not verified
A real trackpad or finger (the tests set the scroll position), Safari and Firefox, and nobody has looked at it but the tests and me.

## Next
The founder looks at it. Real stays need the Stay22 key (F-218, blocked on `STAY22_API_KEY`).
