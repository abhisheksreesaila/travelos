# Autopilot report: booking, partners and creators (2026-11-04 → 05)

Branch `autopilot/booking-creators`, not merged to master, not deployed.

## How far it got
`scripts/check`: M1 PASS · M2 PASS · M3 PASS · M4 PASS · M5 PASS · M6 PASS (full suite included). The reviewer passed it with no blockers.

- **M1 Four places:** LA, San Diego, Honolulu, New York from SFO, each with its own flights, stays, cars, weather, events and news (synthetic, deterministic).
- **M2 Partner seam:** `gitaway/partners/`: Aviasales (flights), Hotellook (stays), DiscoverCars (cars), Uber deep link, all built Travelpayouts-shaped (marker, SubID). Every offer has a "Book on <partner>" link through `/go/…`. With `TRAVELPAYOUTS_MARKER` set it becomes a real tracked `tp.media` link; without one it goes to an in-app sandbox checkout.
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
1. Commission estimates (D-2x): flights 1.1%, hotels 5%, cars $18 flat. These are placeholders until Travelpayouts shows real rates. The program ids 4114–4116 are placeholders too.
2. Phone lanes (D-54): `.ws-grid` itself is the swipe scroller. Try it on your iPhone.
3. No night mode yet (D-51), and the landing page is still the old look. Only the booking, creator and partner pages are in Coast.

## Next
Captain: try it on the phone and merge if it feels right. Then create the Travelpayouts Project and set `TRAVELPAYOUTS_MARKER`/`TOKEN` in Railway (the links go live with no code change). Then move the landing and trip canvas to Coast.
