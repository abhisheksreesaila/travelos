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
