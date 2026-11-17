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

## F-217 The trip grid (2026-11-11, overnight, unattended)
- Read D-415 first (the same evening): no in-app booking, so the grid is a way to compare and choose, with booking on the partner's site. LiteAPI is not used.
- Built in four slices, each with its tests: the sentence reader, the sums and the source seam, the two pages as plain links, then the script (look-ahead panel, live budget and lens, scroll-linked islands).
- The page and the script each mark the squares (the server for the first paint and for no script, the script after a change). One browser test compares the two for the lens, whose day and the budget, so they cannot drift.
- Looked at the real page in headless Chromium at 1440 and 390, light and dark, at rest and folded (docs/report/f217-*.png). Slips caught that way: a `.tg-row` rule after `.tg-head` un-hid the flight headers on a phone; a one-column grid without `minmax(0, 1fr)` let the page scroll sideways by 686px; columns sized by their longest label pushed the last flight under the panel (the pad now has a computed width and the columns share it); a fare divided by the party showed "$258.25 each".
- Not verified: a real trackpad or touch scroll (the tests set the scroll position), Safari and Firefox (the islands use `@property`; without it a tap's glide is a jump, the fold still follows the scroll), and nothing was looked at by a person.

## 2026-11-16 overnight (founder asleep; docs/overnight-goal.md)
- Merged F-266 (the postcard cover), F-265 (each visitor's own 60 searches a day), F-267 (live public prices; Book "opens soon" in production, a stand-in off it), F-268 (a place-only wish opens the matrix with a window ~4 weeks out), F-269 ("Plan this trip" after Save), F-270 (Caveat self-hosted), F-256 (browser tests collect) and M5 (the browser suite's 70 stale failures triaged: docs/report/m5-browser-triage.md; one real bug fixed: the local Plan it for me checkout was shadowed by partners' /sandbox route).
- Live check with the production key on a local server: San Diego from SFO, Dec 15-18, family of 4: $1,017 the whole trip (Best Western Island Palms, refundable); Los Angeles $855 marked Our pick.
- Walked the visitor journey at 1440 and 390: found and fixed the guide page header overflowing a phone (1098a40f). Noted: the sign-in page is still the old purple Direction A look, unlike the cover and v2 pages (recommendation, not changed).
- Not done on purpose: deploy, Railway variables, real bookings (founder: autopilot is development and testing only).
## 2026-11-17 overnight
- Goal and checker committed (docs/overnight-goal-2026-11-17.md, scripts/check_overnight2.py). F-281, F-284, F-285 merged earlier; F-286 in review; F-282 building.
- F-286 merged and done (M1); test_aerial clean 3x on master.
- Full unit suite on master (after F-282, F-286, the complaint fix): 3946 passed. Walk fixes 1-11 committed; checkout hint after that run (its unit + browser files green).
- All seven milestones PASS (scripts/check_overnight2.py). Morning report: docs/report/overnight-2026-11-17.md.
