# Autopilot journal


## M1 four places (ap-m1-places)
- Catalog: `Destination.airports`, `Offer.place`, per-place offers, stay details, ride table; `trip_from_url(..., to)`, `sample_trip(to)`, `offer_place(id)`.
- Context panes (weather highs, events, news, map pins) keyed by place; LA-only tip and community pane hidden elsewhere.
- Threaded `to` through plan, quote, pay, booking records (tripcal), start form and continue card; Uber places for SAN/HNL/JFK/EWR.
- Known, left alone: calendar weather (`tripcal.weather_for`) is still the LA sample; flight block durations ignore time zones for HNL/JFK; `tests/test_rides.py::test_a_ride_is_stored...` fails on the base too (hard-coded Oct 2026 dates are now past).
