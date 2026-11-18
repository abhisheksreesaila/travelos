# Shipping live prices (F-265, F-266, F-267, D-761)

Run on the founder's "deploy", one change at a time.

## What ships
- The cover is the postcard (F-266), and its wish opens the ask.
- Visitors search without an account (D-761), with 60 new searches a day each (F-265).
- Live LiteAPI prices, using the public selling price. Book is disabled and says "Booking opens soon" (F-267).
- Overnight fixes F-268 to F-270, if merged by then.

## Before
1. Run `pixi run python scripts/check_overnight.py`: every milestone must pass, and the full suite must be green.
2. Run `railway status`. It must show Project: gitaway, service web (lessons 2026-10-15 and 2026-11-13).
3. Note the current deployment for rollback: `railway deployment list --service web`, and record the top id here.

## Deploy
1. Deploy the code with the sandbox key still on Railway: `railway up --service web --detach`. Then check gitaway.me (below).
2. Switch to the live key: `RAILWAY=<path> scripts/railway_set_liteapi_key.sh`. It reads the private file, never prints the key, and does not trigger a deploy. Then run `railway redeploy --service web`, or `railway up` again.

## How we'd know it works (check on gitaway.me after each step)
- `/healthz` returns 200.
- `/` shows the postcard, and `?q=<random>` serves the new cover.css.
- Signed out, Plan a trip opens /plan/ask. A wish like "San Diego Dec 15 to 18 from SFO" opens the matrix and squares fill in.
- /admin's LiteAPI line says "live · N searches today", and the about-prices card says live from LiteAPI.
- Book says "Booking opens soon". A POST to /plan/matrix/book returns 403. Nothing reaches LiteAPI's book.
- The visitor allowance is per visitor. From two networks (phone on cellular, laptop on Wi-Fi), each one's searches count separately. If every visitor shares one count, the last X-Forwarded-For hop is not the client (reviewer's note on `reports.client_ip`). Then fix before telling anyone.
- The site-wide daily cap (`liteapi.A_DAY`) holds. Watch the /admin count for the first day.

## What could break
- **The live key's quota or rate limit.** Squares say "busy". Site and visitor caps bound the spend.
- **Prices compared with big sites.** The founder spot-checks 5 trips; within about 10% is the bar.
- **Shared visitor bucket behind the proxy** (above).
- **Flights not enabled on the live account.** Squares would say no flights. The 2026-11-16 probe got live flights.

## Rollback
- Prices: set LITEAPI_KEY back to the sandbox key, or delete it (`railway variables --service web` in the dashboard), then redeploy. With no key, the door falls back to the import.
- Code: `railway redeploy` the deployment id noted above, or `git revert` the merge and run `railway up`.

# Real booking on gitaway.me (F-274, D-840..D-847)

The founder books their own stay here after a deploy. Money moves: Nuitée charges the card through LiteAPI's payment form; GitAway never sees a card. Run on the founder's "deploy", one change at a time, and watch each step.

## What ships
- With the live key, Book on an opened square takes a signed-in person through: guest and mobile number, the review (who sells it, the refund rules in LiteAPI's words, "Have a code?"), LiteAPI's card form in our sheet, then the booking and its pass. Cancel is on the stay's booking page.
- Live searches carry `margin: 16`, so the price charged is the public price the square shows (D-840).
- The off switch: `GITAWAY_LIVE_BOOKING=0` on Railway makes Book say "Booking opens soon" again with no code change (restart the service).

## Before (the founder, once)
1. In LiteAPI's dashboard, check the live account can take card payments through the payment form (Nuitée as merchant of record): a live prebook with `usePaymentSdk: true` must return a `secretKey`. If it does not, Book says "LiteAPI did not answer just now" and nothing is charged: ask LiteAPI to enable it.
2. Make the founder's promo code in LiteAPI (dashboard, or `POST https://da.liteapi.travel/vouchers` with the live key: `voucher_code`, `discount_type: "percentage"`, `discount_value: 10`, `minimum_spend`, `maximum_discount_amount`, `usages_limit` a few, `currency: "USD"`, `validity_start`, `validity_end`, `status: "active"`). The discount comes out of our margin.
3. Railway needs `GITAWAY_PUBLIC_URL=https://gitaway.me` (the card form returns the browser to it). `LITEAPI_KEY` is already the live key (the "Live prices" steps above).
4. `pixi run test`, `pixi run test-browser` and the security auditor's pass are green. Note the current deployment id for rollback (`railway deployment list --service web`).

## Also before (review fixes, D-848..D-850)
- **Ask Nuitée (LiteAPI) when the card is captured**: at the payment form, or when the book is made. A guest who paid and was never booked may be holding money. The booking worker retries such a stay every minute from 10 minutes on, and /admin shows "Paid, not booked (10+ min)": if it is not 0, look at it the same day.
- **Make live codes strong**: at least 10 random characters, with a usage limit, a budget and a maximum discount (`maximum_discount_amount`), so a code cannot be guessed or run away. The site stops answering codes for the day after 30 wrong ones (the log says "booking codes are off for today").
- The matrix sends a report-only Content-Security-Policy (`gitaway/csp.py`): open DevTools on the booking sheet during the first booking and note anything the console says it would block; nothing is blocked.

## Deploy and the first booking
1. `railway up --service web --detach`. Check `/healthz`, a matrix square's price, and that the about-prices card says "Sold by Nuitée through LiteAPI ... GitAway never sees your card".
2. Sign in on gitaway.me. Open a square, press Book, answer the questions (your real name, email and mobile number), and read the review: the total must be the square's (there is no "The price moved" line; if there is, the margin did not make the charge equal the shown price: stop and tell the builder the two numbers).
3. First booking: pick a **refundable** stay. Apply your code, check the discounted total, pay with a real card in LiteAPI's form. The pass must show LiteAPI's booking id; the stay must be on /trip/plan "Booked on LiteAPI". LiteAPI's or the hotel's email arrives.
4. Cancel that stay from its booking page. It must say what comes back ("LiteAPI says $X comes back to the card you paid with") and the card must be refunded. The sandbox already did this path (a refundable stay paid in the real form with the test card, then cancelled: `tests_browser/test_matrixbook_real_sandbox.py`); this is the same with a real card and the live account, so it is the real test.
5. Then book the real trip.

## How we'd know it works
- /admin's LiteAPI line counts prebook and book calls (booking budgets D-511: 20 a family and 200 a day) apart from searches.
- A booking appears in LiteAPI's dashboard with our `clientReference`; the stay's confirmation on the plan is its booking id.
- The Railway log has "LiteAPI book not done (HTTP 400, code ...)" on a failure and never a name, email, card, key or `secretKey`.

## What could break
- **The card form is LiteAPI's and Stripe's**: if it does not load (an ad blocker, a corporate network) the sheet says so and nothing is charged.
- **Paid, but not booked.** The browser returns to `/plan/matrix/book/return`, which books. If LiteAPI does not answer then, the page says "Do not pay again" with the payment reference; reloading it books once with the same reference. If it still fails, give LiteAPI that reference.
- **The charge differs from the shown price.** The margin was proven on the sandbox only; if the live numbers differ, set `LITEAPI_MARGIN` (a percentage) and restart, and say so.
- **A code that LiteAPI rejects** says "That code is not valid"; check its dates, minimum spend and uses in the dashboard.
- **Anyone signed in can book** (founder's choice): the per-person limit is 5 presses a minute and 20 a day, and 20 booking calls a family and 200 a site a day.
- **Several places in one trip** is not booked in one go: it says to book one stay at a time.

## Rollback
- Stop new bookings at once: `GITAWAY_LIVE_BOOKING=0` on Railway, restart. Book says "Booking opens soon"; cancel and the return page keep working only while the flag is not 0, so cancel any stay first through LiteAPI's dashboard if the flag is set.
- Code: `railway redeploy` the deployment id noted above (an earlier build has no booking at all and keeps D-768's "Booking opens soon").

## Deployed 2026-11-17 (founder: "deploy the current status")
- Rollback point before: `70520b35` (2026-11-13). Code deploy `db9d9034` (sandbox key), then the live key, GITAWAY_PUBLIC_URL, Resend SMTP and GOOGLE_MAPS_API_KEY (`scripts/railway_set_liteapi_key.sh`, `scripts/railway_set_launch_env.sh`, nothing printed), redeploy `047a4cd4`.
- Checked on gitaway.me: /healthz 200; signed out, "Lake Tahoe from SFO" opens the matrix and 7 squares fill with live whole-trip prices in 7 s; no sample label; the bar is "Find a trip · Guides".
- Not yet checked live: the founder's own booking and cancel (the steps above), the booking email from production, the visitor allowance from two networks, Wallet (no credentials yet, buttons hidden).
- `.railwayignore` now keeps docs/report and scratch off the upload (233 MB hit Railway's limit).
- Launch polish deployed the same day (`c75b4524`, then `a345231e` and `5138bb5b` for the Heads up chips): /trust, the calm hotel dashboard with Ask the reviews in the drawer, the gotchas line, "Sold by Nuitée through LiteAPI", More menus, the creator offer, polished emails. Checked live on Margaritaville Resort Lake Tahoe: score 8.4, the last-100 strip, clean Heads up chips (LiteAPI does send `hotelImportantInformation`).
- 2026-11-18: the Stage look live (F-296: Apple-grey stage, colour from the trips, black action, orange heads-up, green good news, the new black logo with an orange dot), deploys `f9fb1811` then `5389822c` (a pick cheaper by under 50 cents says "the same as"). Checked live: the cover and a Tahoe search (14 of 15 squares priced).

# Flights booked on gitaway.me (F-276, D-972..D-979): before this is deployed

Not deployed. The checkout now books the flight too (two LiteAPI payment forms, the flight first); nothing here changes until it ships.

## Before (the founder, once)
- **Seller of travel (D-979):** register with the California Attorney General ($100 a year) and put the registration number in the site's footer. This is not legal advice (docs/research/booking-apis-and-payments.md).
- **Flight earnings:** LiteAPI's flight search takes no `margin` (D-976): GitAway's flight revenue is the markup set in the LiteAPI dashboard. Set it before launch; the price charged is LiteAPI's quote, which the square already shows.
- **One real sandbox booking through the form** (`GITAWAY_SANDBOX_FORM=1`, a `sand_` key, card 4242 4242 4242 4242, twice: the flight, then the stay), then its cancel quote and cancel on the booking page. The recordings are of calls made without the form's payment: no one has seen LiteAPI's flight form pay and redirect yet.
- **Ask LiteAPI** whether a flight `TRANSACTION_ID` book is refused when the payment was not made, as it is for stays (code 2014). The sandbox booked an unpaid one (D-978); the server only books from the form's return, but a person could forge that return address.

## How we'd know it works
- /admin "Paid, not booked" counts a flight whose book call may have gone through (`needs_help`) or is still in flight; the worker never books a flight, so a person who paid and closed the tab is not booked until the captain looks (LiteAPI's dashboard shows the payment).
- A booked flight turns CONFIRMED within minutes (the worker asks at 1, 3, 10, 30 and 60 minutes); one "tickets issued" email goes once.
- No passenger name, birth date, passport or phone number is in any log line; `matrix_flight_payments.travellers` is empty once a flight is booked.

## Rollback
`GITAWAY_LIVE_BOOKING=0` stops new flight and stay prebooks at once and strands nobody who paid (a book, lookup and cancel still work). No table is dropped; the new tables are additive.
