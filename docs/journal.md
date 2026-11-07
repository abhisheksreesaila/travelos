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

## M5 omxqua Coast (ap-m5-look)
- Plan: skin via a before hook + remapped legacy tokens, then per-page sheets (`plan_coast.css`, `creators_coast.css`, `partners.css` tail). Fonts Geist/Geist Mono + OFL licence copied to `assets/fonts/`.
- Slip: my lane-switcher constant `LANES` shadowed plan.py's own `LANES` (a 500 on /plan); renamed `SEG_LANES`. Slip 2: `pkill -f` on a pattern killed my own shell; stop by PID only.
- test_scale rejects px sizes and sub-11px text in any stylesheet: omxqua.css is converted to rem.

## Orange accent and omxqua v0.1.6 (ap-orange)
- Captain: the logo was teal on Coast pages and orange elsewhere (and uppercase and smaller in the top bar). One logo definition now (base.css), Coast accent orange, omxqua `--oq-*` vendored by hand. Decisions D-60 to D-66.
- Slip: I guessed a contrast ratio (5.82) in a test before computing it (6.30); the test caught it. Compute first.

## F-193 Plan it for me (2026-11-06)
- Built test-first on branch f-193-plan-for-me: orders and the server's price, the verified idempotent Stripe webhook, the `plan-for-me` job (Sonnet 5.5) with a validated answer written as a real trip, the worker and its restart, the intake, order page, local stand-in checkout, booking links, the three entry points, /admin orders and refunds due, privacy and terms. Decisions D-197 to D-209.
- Nothing could call the real Stripe or Anthropic: the SDK request was read through a fake HTTP client, and the one thing left is a test-mode purchase by the captain (docs/setup.md "Plan it for me").
- Slips caught by tests: the `/sandbox/{partner}/{click}` route shadowed `/sandbox/plan-for-me/<id>` (route order), the desktop skin's `:root:has(.ga-topbar) .btn` made buttons 32px on the laptop, a stray worker thread from a live-server test built later tests' orders, a function named `_stop` replaced the stop Event.
