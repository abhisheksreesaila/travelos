# Autopilot journal


## M1 four places (ap-m1-places)
- Catalog: `Destination.airports`, `Offer.place`, per-place offers, stay details, ride table; `trip_from_url(..., to)`, `sample_trip(to)`, `offer_place(id)`.
- Context panes (weather highs, events, news, map pins) keyed by place; LA-only tip and community pane hidden elsewhere.
- Threaded `to` through plan, quote, pay, booking records (tripcal), start form and continue card; Uber places for SAN/HNL/JFK/EWR.
- Known, left alone: calendar weather (`tripcal.weather_for`) is still the LA sample; flight block durations ignore time zones for HNL/JFK; `tests/test_rides.py::test_a_ride_is_stored...` fails on the base too (hard-coded Oct 2026 dates are now past).
- M4: built creator_profiles data and the profile route; m4 contract tests pass. Full suite green except the ride-pruning test in tests/test_rides.py, which also fails on the base branch. m1 hi/nyc fail until the other agent lands the places.

## M2 + M3 partners (ap-m23-partners)
- `gitaway/partners/` (seam, Travelpayouts links, statistics row), `gitaway/partners/log.py` (clicks and sandbox bookings in the family DB table `partner_clicks`), `gitaway/pages/partners.py` (/go, /sandbox, /partners), "Book on" links on /plan (`ws-offer-wrap` around each card, the link cannot live inside the card's button), `assets/css/partners.css`.
- First attempt at the contract passed without changes to the tests; the sandbox is a standalone page on purpose: the site header carries a sign-out form that the contract's "first form on the page" regex would have posted to.
- Ride-pruning test: pinned `catalog.today` hid that the rides clock is real; fixed with a date relative to `rides.now()` (D-28).
