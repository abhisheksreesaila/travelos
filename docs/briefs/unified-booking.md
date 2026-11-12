# One view for booking (draft)

Status: draft, waiting on the founder

> 2026-11-11: the founder kept booking links-only (D-415) and settled a new view on the design canvas, the trip grid (every flight against every stay). It is built on sample data as F-217 (docs/plan.md); real stays are F-218 and still wait on the Stay22 key below.

## Why
Booking a trip means a dozen tabs: hotels on one site, flights on another, filters in a sidebar, then guessing how it all adds up. GitAway should give one calm view of the choices with everything needed to decide beside them, and never own a booking.

## What the founder decided (2026-11-08)
- **We never sell.** No booking APIs that make us the seller (LiteAPI, Duffel, Expedia Rapid): cancellations, refunds and support would be ours. Booking always finishes on the partner's site.
- **Convenience over commission.** The easiest view wins, even if it pays less. A known brand on the page (Booking.com, Expedia) is fine, even good.
- **Filters are a sentence.** "A family of 4, SFO to Orlando, Dec 12–16, within 20 miles of Disney, with breakfast, under $3,000." Each underlined part is a dropdown; the sentence can be retyped in plain English. No filter sidebar.

## How it works
1. **Now:** the sentence opens each partner's search with its filters set (Aviasales, Expedia, Booking, Airbnb, Klook), beside the parts we can really compute: the Aviasales fare (Data API v3, real), the airport drive, the weather, the running total.
2. **Next:** hotels inside GitAway through **Stay22**: a map or list of hotels with live prices from Booking.com, Expedia and others side by side, booked on that site. Stay22 is an iframe widget (no API key), so we style around it, not inside it.

## What we checked (2026-11-08)
- Travelpayouts closed Hotellook (its hotel search) on 2025-10-20 and says no hotel brand offers it an API now. So hotel results won't come from Travelpayouts. Source: support.travelpayouts.com, "FAQ on the closure of Hotellook".
- Stay22: iframe map, free, no API key (dev.stay22.com). Commission is locked 7 days after checkout and paid monthly. Its split is private (one blogger reports 30%). Booking.com and Expedia are partners; Vrbo is unconfirmed.
- Our flight price uses Aviasales' Data API v3 (`prices_for_dates`), not the old Flights Search API that stopped on 2026-06-15.

## Knowing what they picked (checked 2026-11-08)
- The map embed is an iframe from another site: GitAway cannot read it or see a click in it. No click events found in the docs.
- So use Stay22's **Direct Travel API** instead (api.stay22.com, key from hub.stay22.com): live availability, prices and deep links for Booking.com, Vrbo, Expedia and Hotels.com. We draw the list and map ourselves, so we know which hotel was picked and can say "All in $1,944" (a quote before booking).
- What was actually booked: a `campaign` tag per trip on every link, read back from Stay22's transaction reporting endpoint (exact fields unconfirmed: check `api.stay22.com/openapi.json`); or the family pastes the confirmation (`gitaway/confirmations.py`, built).

## Flights (checked 2026-11-08)
- No free, live, search-only flight API is open to a small site. Aviasales live search needs 50,000 monthly users; Skyscanner and Kiwi are partner-gated; Amadeus Self-Service closed on 2026-07-17. Duffel is live but makes us the seller (no).
- So: Aviasales' cached fares now (free, labelled with their age), behind one interface (a fare: price, airline, times, seen when, live or not, link) so a live source plugs in later without touching the page.

## Open
- The founder signs up for Stay22 (an account only they can open).
- Confirm on Stay22's dev docs: which brands show, how much of the widget's look we control, whether a list view (not only a map) exists.
- Prototype: the sentence search, with the Stay22 map under it.
