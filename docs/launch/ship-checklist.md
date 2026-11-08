# Ship checklist: `autopilot/booking-creators` to gitaway.me

Ships partner Book links (`/go`), creator publishing and import, Plan it for me (Stripe, F-193, F-197), `/admin`, the one orange logo, security headers and two draft-job worker threads. Target: Railway project **gitaway**, service **web**. One deploy, then 30 minutes watching it.

## Before (10 minutes)
- [ ] `pixi run test` and `pixi run test-browser` pass on the commit you ship, and the reviewer has passed it.
- [ ] `railway status` shows **Project: gitaway** and service **web**. On 2026-11-06 the worktree showed **appcol**, so first run `railway link --project gitaway --environment production --service web`.
- [ ] Check variable names, never values: `railway variable list --service web --json | jq -r 'keys[]'`. Must have: `TRAVELPAYOUTS_MARKER` (without it every Book link 404s), `GITAWAY_SECRET_KEY` and `GITAWAY_PUBLIC_URL`. Should have: `ANTHROPIC_API_KEY`, `GITAWAY_ADMIN_EMAILS` and `GITAWAY_CONTACT_EMAIL` (set them with `pixi run setup-money`), plus `TRAVELPAYOUTS_TOKEN`, `TRAVELPAYOUTS_TRS` and `TRAVELPAYOUTS_DRIVE_ID`, and `MET_NORWAY_TERMS_ACCEPTED=1` once you have read and accepted MET Norway's terms (https://api.met.no/doc/TermsOfService; without it real trips show typical weather only, see docs/setup.md "Weather"). To sell Plan it for me it needs `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` and `ANTHROPIC_API_KEY` (also from `pixi run setup-money`: without all three, in production every `/plan-for-me` address is a 404); `PLAN_FOR_ME_REVIEW` is optional (unset or `1` is the founder check on, `0` delivers at once). Must **not** have `GITAWAY_SHOWCASE`.
- [ ] Stripe's webhook endpoint is `https://gitaway.me/stripe/webhook`, with the events `checkout.session.completed` and `checkout.session.async_payment_succeeded`, and its signing secret is `STRIPE_WEBHOOK_SECRET`. Start in test mode: a test card (4242 4242 4242 4242) pays an order, `/admin` shows it, and an unsigned `curl -X POST https://gitaway.me/stripe/webhook` answers 400.
- [ ] Rollback target: run `railway deployment list --service web --limit 3` and write the live SUCCESS id here: `__________` (it was `49e10849-06f6-42b7-b3c0-1bbc461093c4` on 2026-11-06).
- [ ] Back up the volume: web > web-volume > Backups > create a manual backup. The branch only adds tables, and adds columns only to tables it creates itself, so the old code still runs on the new data.
- [ ] Check that no `*.gitaway.me` subdomain needs plain http. The new HSTS header (`includeSubDomains`, one year) stays in browsers after a rollback.

## Deploy
From `~/Projects/travelos-autopilot` with a clean `git status`, run `railway status && railway up --service web --detach`, then follow `railway logs --service web --build`. Expect up to a minute of 502s while the volume moves to the new container.

## What could break for existing families
| Change | How it breaks | Where to look |
|---|---|---|
| One orange logo in base.css (D-61) | Wrong colour or size, or old and new CSS mixed | `/`, `/signin`, `/trip/canvas`, `/plan` at 390 and 1440 px. In the installed app, open it twice: the service worker swaps on the second visit |
| New routes: `/go`, `/creators/*`, `/claim`, `/trip/publish`, `/admin`, `/report`, `/privacy`, `/badge` | Book links are dead, or sample content shows to real families | A Book on `/plan` lands on Aviasales or Klook with `marker=`. `/sandbox/...`, `/admin` (signed out) and `/community` (until a real trip is published) return 404 |
| Travelpayouts Drive (`tp-em.com`) | Loads on a signed-in page, where a third party would see names and trips | It loads once on the signed-out `/` and never on `/trip/canvas` (view source) |
| Worker threads at boot (morning push and 2 draft jobs) | A crash loop, or the event loop freezes | The logs below. `/healthz` stays under 1 s |

## How we'd know within minutes
```bash
R=$RANDOM$RANDOM; B=https://gitaway.me
curl -s -o /dev/null -w 'healthz %{http_code} %{time_total}s\n' "$B/healthz?q=$R"        # 200, under 1 s
for p in / /signin /privacy /plan /for-creators /trip/canvas /trip/publish /admin /sandbox/klook/x; do
  printf '%-16s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' "$B$p?q=$R")"; done  # 200 x5, 303 303, 404 404
curl -s "$B/?q=$R" | grep -o -e tp-em.com -e ga-brand-mark | sort | uniq -c            # 1 of each (Drive only with its id)
curl -s "$B/assets/css/tokens.css?q=$R" | grep -c 'brand-orange: #FF7352'             # 1 (0: the old code is still live)
curl -sI "$B/?q=$R" | grep -i -e strict-transport -e content-security-policy           # both present
railway logs --service web --lines 300 | grep -E 'Traceback|ERROR|draftjobs'          # no Traceback, no repeats
railway logs --service web --http --lines 300 --filter '@httpStatus:>=500'             # empty
```
Then, signed in on the phone and the laptop, open Today, a day, the family chat, one Book link and `/creators/import`. With your admin address, `/admin` opens.

## Roll back (under 5 minutes)
Roll back when `/healthz` is not 200 for 2 minutes, any family page returns a 500, the logo or the Book links are broken, `tp-em.com` shows up on a signed-in page, or the same error keeps repeating in the logs.
```bash
railway deployment list --service web --limit 5                                       # find the SUCCESS id before yours
railway api 'mutation($id: String!) { deploymentRollback(id: $id) }' --raw-var id=<that id>
```
The same rollback in the dashboard: web > Deployments > that deployment > ⋮ > Rollback. If neither works: `cd ~/Projects/travelos && git switch master && railway status && railway up --service web --detach`. Then run the checks above again. Leave the data and the variables alone, since the old code ignores the new tables and keys. Add one line to `docs/lessons.md` saying what broke.
