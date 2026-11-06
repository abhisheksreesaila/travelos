# Feature brief: the first real creator trip, with real booking links

Status: approved (captain's answers, 2026-11-05: Disneyland California; publish a trip already in GitAway plus bookings, photos and notes; live on gitaway.me; under my own name, no channel)

## Why
- GitAway needs real content before it can be marketed. The captain's family Disneyland trip is the first creator trip; publishing it is how we learn the real use case.
- Travelpayouts is approved for the Gitaway Project (marker 801445). Aviasales and Klook are connected; links must earn from day one.

## What it does
1. **Booking links are real.** Flights → Aviasales (deep link to the search for the trip's route and dates, `marker=801445.<subid>`). Stays, cars and things to do → Klook (tracked links through the Travelpayouts partner-links API with `TRAVELPAYOUTS_TOKEN`; without the token, the captain's plain Klook link). Prices in the ledger stay estimates, labelled; the partner shows the real price.
2. **Booking journey** (docs/design/booking-journey.html): one "Book this trip" checklist from the total, a calm hand-off screen, "Did you book it?" on return, bookings land on the trip as "Booked elsewhere · <partner>". Commission figures are admin-only, never shown to families.
3. **Publish a trip as a creator, live.** From a family's own trip: pick photos already on the plan (or add more), write a note per day and tips, preview, publish under the person's name. Private details never publish: confirmation numbers, family members' names, chat, addresses of where you stayed beyond the area, photo GPS/EXIF. A published trip gets a public scrapbook page, sits on the person's creator profile and on Community trips, and anyone can fork it or "Plan this trip" (Disneyland → the LA place, Anaheim area).
4. **Production shows only real content.** The made-up sample creators and trips stay local-only (`showcase.on()`); real published trips and real creator profiles show on gitaway.me. The creator can unpublish at any time.

## Not now
- AI drafting from a video link (the paste-a-link flow stays simulated and local-only).
- Live hotel/car prices (LiteAPI, Duffel), Uber, payouts, revenue share.
- A fifth place (Orlando).

## How we'll know
- The captain's Disneyland trip is live on gitaway.me under his name, with photos and day notes, and a stranger (signed out) can read it, and fork it after signing in.
- Tapping "Book on Aviasales" from it reaches aviasales.com with marker 801445 and a SubID; a Klook link reaches klook.com tracked to 801445.
