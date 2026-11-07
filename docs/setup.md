# Setup: running GitAway with sign-in

GitAway runs on [fh-saas](https://pypi.org/project/fh-saas/) with SQLite. Each person who signs in gets a **family** (a tenant with its own database); `docs/adr/0004-families-as-tenants-on-fh-saas.md` says why.

```
pixi install
pixi run dev          # http://localhost:5002 (set PORT to use another port)
pixi run test         # the test suite; it uses a throwaway data folder and the dev sign-in
pixi run test-browser # headless-browser tests (after one `pixi run test-browser-install`)
```

Put settings in a `.env` file in the project folder (it is gitignored) or export them in your shell. Never commit keys.

## Environment variables

| Variable | Needed | What it does |
|---|---|---|
| `DB_TYPE` | set for you | The app sets `SQLITE`. fh-saas defaults some modules to PostgreSQL, so GitAway forces it. |
| `DB_NAME` | optional | Host database file name (without `.db`), inside the data folder. Default `app_host`. |
| `GITAWAY_DATA_DIR` | optional | Folder for every database file. Default `./data/db` (gitignored). A relative value is read from the project folder. Created if missing. |
| `GITAWAY_ENV` | on the server | `production` switches on production mode (so does Railway's own `RAILWAY_ENVIRONMENT`): the app refuses to start without `GITAWAY_SECRET_KEY`, the session cookie is https-only, the dev sign-in is off whatever `GITAWAY_DEV_LOGIN` says, uvicorn does not reload and trusts the proxy's `X-Forwarded-*` headers. |
| `GITAWAY_SHOWCASE` | never on the server | `1` or `0` overrides `gitaway/showcase.py`'s default (samples on locally, off in production). **Leave it unset on Railway: `1` there turns the sample trips, Community trips, creators, forks, sharing, simulated Uber and voice demo back on for real families.** |
| `GITAWAY_CONTACT_EMAIL` | for /privacy, /terms and Plan it for me | The address people write to for questions and to have their data deleted (F-076). Set it on the live site (Plan it for me needs it to be for sale in production: it is where a refund is asked for); unset, the pages say "Contact the person who runs this GitAway site." and show no address. Give Google's Branding page the site address plus `/privacy` and `/terms`. |
| `TRAVELPAYOUTS_DRIVE_ID` | to verify the site with Travelpayouts | Your Travelpayouts partner id (digits, e.g. `596534`). Set, the signed-out landing loads Travelpayouts Drive (`https://tp-em.com/<base64 id>.js?t=<id>`), their site-verification script. Never on signed-in pages (they show a family's names and trips); unset or not digits, nothing loads. |
| `GITAWAY_DEV_LOGIN` | local only | `1` turns on the dev sign-in (see below). Leave it unset anywhere else; production ignores it. |
| `GOOGLE_CLIENT_ID` | for Google sign-in | The OAuth client id (fh-saas reads this name). |
| `GOOGLE_CLIENT_SECRET` | for Google sign-in | The OAuth client secret (fh-saas reads this name). |
| `GITAWAY_SECRET_KEY` | required in production | Secret that signs the session cookie. In production the app will not start without it. Locally, if unset, a random key is made once and kept in `.sesskey` (gitignored), which is fine for local development. |
| `PORT` | optional | Port for `pixi run dev`. Default 5002. |
| `FH_SAAS_LOG_LEVEL` | optional | `DEBUG`, `INFO`, `WARNING` (default). The app calls fh-saas's `configure_logging()` at startup. |
| `GITAWAY_PUBLIC_URL` | for Face ID in production | The site's public address, e.g. `https://web-production-2d117.up.railway.app` (F-074). A passkey belongs to this site name, and the browser's origin is checked against it strictly. Falls back to Railway's own `RAILWAY_PUBLIC_DOMAIN`; with neither set, Face ID is switched off in production. Never taken from the request's Host or `X-Forwarded-*` headers. In production it is also the one address (F-078): see "One address" below. |
| `GITAWAY_VAPID_PUBLIC`, `GITAWAY_VAPID_PRIVATE`, `GITAWAY_VAPID_SUBJECT` | for the morning plan push | The Web Push (VAPID) key pair and a `mailto:` contact (F-066). Without them the Morning plan card is not shown and nothing is sent. Make them with `pixi run vapid-keys mailto:you@example.com` (below). |
| `TRAVELPAYOUTS_MARKER` | **required for booking links** | Your Travelpayouts partner marker (digits, e.g. `801445`). **Without it `/go/<offer>` answers 404 and every Book link on the site is dead.** It goes on every Aviasales link, and on Klook links through the partner-links call. A creator's own marker (set at `/creators/settings`) replaces it on flights only. |
| `TRAVELPAYOUTS_TRS` | with the token, for Klook links | Your Travelpayouts **project id**, digits only (e.g. `596534`). Sent as a number: the API answers 400 when it is a string. Without it (or without the token) Klook links fall back to `KLOOK_FALLBACK_URL`. With the token set but the project id missing or wrong, every Klook click loses its tracking: /admin counts them ("Klook links not tracked", last 7 days) and the log has a WARNING with the reason. |
| `TRAVELPAYOUTS_TOKEN` | for Klook links | The Travelpayouts API token that builds a tracked Klook link. A secret: set it in Railway only. |
| `KLOOK_FALLBACK_URL` | optional | The plain Klook partner link used when the partner-links call is not configured or fails. Default: the one built into `gitaway/partners/travelpayouts.py`. |
| `ANTHROPIC_API_KEY` | for drafting a trip from a creator's post, and for Plan it for me | Switches the `creator-import` job (Claude Haiku) and the `plan-for-me` job (Claude Sonnet) on; Plan it for me is not for sale without it. The pasted or fetched post text is sent to Anthropic, and nothing else (the privacy page says so). Without it the paste page says drafting "is not switched on yet" and "Write it myself" still works. See `docs/ai-usage.md`. |
| `GITAWAY_AI_PROVIDER_<JOB>`, `GITAWAY_AI_MODEL_<JOB>`, `GITAWAY_AI_EFFORT_<JOB>` | optional | Per job (`<JOB>` is the job name in capitals with `_`, e.g. `CREATOR_IMPORT`): the provider (`anthropic` or `azure`), the model, and the effort (`low`, `medium`, `high`; default `low`). `docs/ai-usage.md` lists the jobs. |
| `GITAWAY_CREATOR_IMPORT_SITE_LIMIT` | optional | The most creator-import drafts all creators together may ask for in a day (UTC). Default 500; a person's own limit is 20 a day. Over it, the paste page asks the creator to come back tomorrow, and nothing is fetched or sent to the model. It caps the model bill if many accounts are made. |
| `GITAWAY_CREATOR_SCAN_SITE_LIMIT` | optional | The most blogs all creators together may have read ("Import several posts") in a day (UTC). Default 500; one person's own limit is 30 a day, and at most 4 scans run at once (a fifth is told to try again in a minute). Over it, the creator is asked to come back tomorrow or paste a post's link. It caps outgoing fetches if many accounts are made. |
| `GITAWAY_ADMIN_EMAILS` | for the admin page | The sign-in email addresses that may open `/admin` (take down, restore, reports, commission), separated by commas, spaces or semicolons, any case. The address must be a verified one. Unset, nobody is an admin and `/admin` is a 404 for everyone. |
| `DMCA_AGENT` | for /terms, before you take creators' content | The designated copyright agent's name and address as registered with the U.S. Copyright Office (copyright.gov/dmca-directory, a form and a small fee), one line, up to 300 characters, shown as text on `/terms` under "Copyright takedown" (F-196). Unset, the page says the agent is **pending registration** and sends notices to `GITAWAY_CONTACT_EMAIL`. Without a registered agent the safe harbor of 17 U.S.C. 512(c) does not cover GitAway, so register before creators publish and set this to the name on the registration. |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_MAIL_FROM` (and optional `SMTP_PORT` 587, `SMTP_SSL`, `SMTP_STARTTLS`) | optional, to be emailed about reports | fh-saas's mail settings (F-196). When all four are set, each new report sends an email to every address in `GITAWAY_ADMIN_EMAILS` through `fh_saas.utils_email.send_email`; it names the page and the reason and links `/admin`, never the reporter's words or address. **fh-saas does not declare the library it sends with**: until `pixi add --pypi markdown-merge` is run (it is not in `pixi.toml` yet, so a lock change for the captain to decide), the send fails and says so in one WARNING line (`report email was not sent: ...`). Without SMTP nothing is emailed; every report is still one WARNING line in `railway logs` (`new report: trip <slug>, reason <reason>`) and an "N new" count in your account menu, the header and `/admin` until you press "Mark all as read" on `/admin`. Proven with the library added outside the project (a wheel unpacked in `/tmp`, a local SMTP sink): the real `send_email` delivered the message; so once `markdown-merge` is a declared dependency the email half works. |
| `STRIPE_SECRET_KEY` | **required to sell Plan it for me** | Your Stripe secret key (`sk_live_...`, or `sk_test_...` to try it). A secret: set it in Railway only. **The offer is hidden in production unless the key, `STRIPE_WEBHOOK_SECRET` and an AI key (`ANTHROPIC_API_KEY`) are all set** (no cards, every `/plan-for-me` address is a 404), so nobody can pay for something that cannot be matched or built; locally, with no key, a stand-in checkout completes the order so the whole flow can be clicked (never in production). Each order makes one Checkout session, mode payment, one line item. |
| `STRIPE_WEBHOOK_SECRET` | **required with the key** | The signing secret (`whsec_...`) of the Stripe webhook endpoint `https://<your domain>/stripe/webhook`, subscribed to `checkout.session.completed` (and `checkout.session.async_payment_succeeded`). Without it every webhook is refused (503) and no order is ever marked paid. |
| `PLAN_FOR_ME_PRICE_CENTS` | optional | The founding families' price for Plan it for me, in US cents, whole digits between 100 and 50000. Default `2900` ($29). The server picks the price when an order is made and keeps it on the order; a price sent by a browser changes nothing. |
| `PLAN_FOR_ME_FOUNDING_LIMIT` | optional | How many families pay the founding price (F-197): paid orders that were not failed take a spot, and the offer shows how many are left. Whole digits, 0 to 10000; `0` means no founding price. Default `10`. |
| `PLAN_FOR_ME_FULL_PRICE_CENTS` | optional | The price once the founding spots are taken, in US cents, 100 to 50000. Default `4900` ($49). The offer says "$29 for the first 10 families, then $49"; it never shows a former or struck-through price. |
| `PLAN_FOR_ME_REVIEW` | optional | The founder check (F-197). On unless it is `0`: a built plan waits on /admin for "Send to family" (with a quick edit) before it reaches the family, and every page says it is "checked by a person, usually within a few hours". `0` delivers at once and the pages say "in a few minutes". |
| `SARVAM_API_KEY`, `SARVAM_STT_MODEL`, `SARVAM_TRANSLATE_MODEL`, `GITAWAY_AI_TRANSCRIBE_PROVIDER`, `AZURE_OPENAI_TRANSCRIBE_API_VERSION` | for voice typing | Speech-to-text for the Ask box's microphone: the Sarvam key (and optional model names), the provider choice (`sarvam` or `azure`) and the Azure API version. All in `docs/ai-usage.md`. |
| `MET_NORWAY_TERMS_ACCEPTED` | for real weather forecasts | `1` once **you** have read and accepted MET Norway's [Terms of Service](https://api.met.no/doc/TermsOfService) (since 21 October 2026 they must be accepted by a person in charge before the service is used, and code an AI wrote does not change that). Set, a real trip shows MET Norway's forecast for the days it covers (about nine days ahead), credited "Forecast based on data from MET Norway"; the requests carry `GITAWAY_PUBLIC_URL` (else gitaway.me) and `GITAWAY_CONTACT_EMAIL` as their contact, so set that address too. Unset, nothing is asked and real trips show only typical weather (NOAA climate normals, labelled "not a forecast yet"). See "Weather" below. |
| `UBER_MODE`, `UBER_CLIENT_ID` | optional | `UBER_MODE` is `simulated` (the only mode; a real Uber client is not built yet). `UBER_CLIENT_ID` is added to the Uber deep link when set. |

There is no redirect-URI variable: fh-saas builds it from the address of the request, as `<scheme>://<host>/auth/callback` (`http` for `localhost` and `127.0.0.1`, `https` for anything else).

### The caller's address (reports and click counts)

`gitaway/reports.py` `client_ip` takes the **last** `X-Forwarded-For` entry as the caller's address (kept only as a salted hash, for the per-address limits on reports and on counted creator clicks). That assumes exactly one trusted proxy that appends the connecting address, which is how Railway's edge is believed to behave. **This is unconfirmed for Railway.** To confirm it once on the live site, send a report from your own phone and compare the stored `ip_hash` with `reports.ip_hash(<your real address>)`. If Railway puts the caller's address anywhere else, or adds a second proxy, the limits would count the proxy instead of the caller: change `client_ip` before relying on them.

### Where the data lives

fh-saas makes each family's database file relative to the process's **working directory** and has no setting to change that. So `main.py` makes `GITAWAY_DATA_DIR` the working directory at startup; the host database (`app_host.db`) and every family database (`<id>_db.db`) then sit side by side in that one folder. Consequences:

- Code must not use relative paths. Assets and templates are found from the project folder (`Path(__file__)`).
- The family database location is stored in the host database as a relative path, so the folder must stay the same for the life of the data. When deploying, point `GITAWAY_DATA_DIR` at the persistent volume and test a redeploy before real users arrive.
- To start fresh locally, stop the server and delete the folder.
- What is inside a family's file (trips, bookings, calendar, friends, rides, forks and saves), how its schema changes and how two people editing at once is handled: `docs/family-db.md`.

### Staying signed in

Sign-in lasts about 30 days on a device and slides with use: the first request after a day away re-issues the cookie (`gitaway.session.slide`), so anyone who visits at least monthly stays in. Sign-out clears it at once, and a member removed from a family loses that family on their next request (membership is checked on every request, not read from the cookie). fh-saas's `create_session_middleware` is not used: its `SlidingSessionMiddleware` only wraps Starlette's, which sends the cookie only when the session changed, so reading never extends it (see `docs/fh-saas-proposals.md`).

## The dev sign-in (local only)

Set `GITAWAY_DEV_LOGIN=1`. The sign-in page then shows an email box and **Dev sign-in (local only)**. Any email works; the first time one is used, a person and their family are created, exactly as the Google sign-in does. It is refused (403) unless **both**:

1. `GITAWAY_DEV_LOGIN` is `1`, and
2. the request comes straight from this machine (`127.0.0.1` or `::1`) with no proxy header (`X-Forwarded-*`, `X-Real-IP`, `Forwarded`). Forwarded addresses are never trusted.

Do not set the flag in production. If you run through a local reverse proxy, the dev sign-in is refused on purpose.

## Google sign-in

It switches on when both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set; the sign-in page then shows **Continue with Google**. Routes: `/login` (starts), `/auth/callback` (Google returns here), `/logout` (or the header's Sign out).

Google Cloud console steps:

1. Open <https://console.cloud.google.com/> and create (or pick) a project, e.g. "GitAway".
2. **APIs & Services > OAuth consent screen**: choose **External**, fill in the app name (GitAway) and your email, and add the scopes `openid`, `email` and `profile`. While the app is in **Testing**, add each family member's Gmail address under **Test users** (only they can sign in until the app is published).
3. **APIs & Services > Credentials > Create credentials > OAuth client ID**, application type **Web application**.
4. Under **Authorized redirect URIs** add `http://localhost:5002/auth/callback`. Use the same host you browse with: if you open `http://127.0.0.1:5002`, add `http://127.0.0.1:5002/auth/callback` too. For a deployed site add `https://<your domain>/auth/callback`.
5. Copy the client id and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, restart `pixi run dev`, and open <http://localhost:5002/signin>.

## Face ID sign-in (F-074)

After signing in once (Google), a person can turn on **Face ID** (a WebAuthn passkey, so also a fingerprint or a device PIN) on a phone and later sign in with one tap. It uses the `webauthn` package (py_webauthn, added with `pixi add --pypi webauthn`).

- **Where it shows**: the sign-in page has **Sign in with Face ID** (and, where the browser supports it, the email box also offers the saved passkey). A signed-in person sees **Use Face ID next time** on Today the first time they open GitAway as a Home Screen app on a phone (**Not now** hides it on that phone), and on `/family` under **This phone**, where they can also **Add another phone** and **Remove** each passkey.
- **What is stored**: in the host database table `ga_passkeys` (a passkey identifies a person, not a family): the person's id, credential id, public key, sign count, transports, a device name, and created and last-used times. No private key ever leaves the phone, and nothing about a passkey is logged.
- **Sign-in** ends in the same step as Google sign-in (`auth.start_session`): same session, same active family, and a person with no family left gets a new one. The passkey asks for a resident key and user verification; a sign count that goes backwards is refused.
- **Site and origin**: in production they come from `GITAWAY_PUBLIC_URL` (or `RAILWAY_PUBLIC_DOMAIN`), never from request headers. Locally they are the address you browse with, and it must be `localhost` (browsers refuse an IP address such as `127.0.0.1` for a passkey). A passkey made on `localhost` does not work on the deployed site, and the other way round.
- **On Railway** (once): set `GITAWAY_PUBLIC_URL` to the site address, redeploy, then add a passkey from `/family` on the phone. Changing the domain later makes every existing passkey stop working (people sign in with Google and add it again).
- **CSRF**: the four JSON routes (`/passkeys/register/options`, `/passkeys/register`, `/passkeys/auth/options`, `/passkeys/auth`) take `application/json` only (a cross-site form cannot send that without a preflight) and check the `Origin` header against the site. **Remove** is an ordinary form POST (`/passkeys/remove`) and relies on the SameSite=Lax session cookie, like the other forms. A challenge is single-use: its hash is kept in the host database (`ga_passkey_challenges`) for 5 minutes and deleted by the first answer, so an old copy of the cookie cannot replay it. All five routes are open to every member (and the two auth ones to signed-out visitors) in `gitaway/access.py`, mirrored in `tests/test_roles.py`, because they only change the person's own sign-in.
- **The email-box suggestion** (the browser offering the saved passkey) only exists where the dev email box does, so locally; in production the sign-in page has the **Sign in with Face ID** button only.
- **After Face ID** the sign-in page shows a full-screen "Welcome back" moment for about 1.2 seconds and then opens Today (or the page the person was headed to).
- **Tests**: `tests/test_passkeys.py` runs the real verification against a software authenticator (`tests/softkey.py`); `tests_browser/test_passkeys.py` uses Chromium's virtual authenticator.

## Family thread pushes (F-070)

The Family tab's thread uses the same keys and the same switch: anyone with the Morning plan on for a phone also gets a push when someone posts a message or changes a plan (never for their own doing). Tapping it opens `/trip/family`. A person can go **Quiet** on the Family tab to stop these (the morning plan is unaffected). A person is pushed at most once every two minutes; what happens in between is counted and told in one push ("3 more updates on the trip"), sent by the same once-a-minute loop as the morning plan. Pushes carry names and plan titles only, never prices or confirmation numbers. Without the keys the thread still works (it polls every few seconds while open) and no push is sent.

## Morning plan push (F-066)

On the phone Today view, a family member can turn on a "Morning plan": at the time they pick (default 7:30 AM, the trip's time zone) each trip morning, their phone gets "Today in <place>" with the first plans, and tapping it opens Today. It uses Web Push, which needs a key pair that only your server knows. On an iPhone it works once GitAway is on the Home Screen (iOS 16.4 or later); in a browser tab the card explains how to add it.

1. **Make the keys**: `pixi run vapid-keys mailto:you@example.com`. It writes `GITAWAY_VAPID_PUBLIC`, `GITAWAY_VAPID_PRIVATE` and `GITAWAY_VAPID_SUBJECT` into `./.env` (gitignored) and never prints the private key. It refuses to replace keys that are already there unless you add `--force`: new keys end every phone's morning plan until each person turns it on again.
2. **Locally**: restart `pixi run dev`. Push needs https, so a phone only gets it from the deployed site; on your computer the card works in Chrome on `localhost`.
3. **On Railway** (once, from the project folder, with the Railway CLI linked to the project). This reads each value from `.env` and sends it straight to Railway without printing it:

   ```
   for k in GITAWAY_VAPID_PUBLIC GITAWAY_VAPID_PRIVATE; do grep "^$k=" .env | cut -d= -f2- | tr -d '\n' | railway variable set "$k" --stdin --service web --skip-deploys; done; grep "^GITAWAY_VAPID_SUBJECT=" .env | cut -d= -f2- | tr -d '\n' | railway variable set GITAWAY_VAPID_SUBJECT --stdin --service web
   ```

   The first two are set with `--skip-deploys` so Railway does not redeploy between them; the third triggers one redeploy that starts the service with all three keys. Never commit the keys or paste them into chat.

How it runs: one background thread in the app (one per process; Railway runs one) wakes every minute and sends what is due. Each phone's subscription, chosen time and the day it was last sent live in the family database (`push_subscriptions`, migration `002`), so a redeploy loses nothing and a restart never double-sends. A push service answering "gone" (404 or 410) deletes that subscription quietly; any other failure is logged without the phone's address and retried for the next hour. Nothing is sent on days outside the trip, or when the family has no trip. The text holds plan titles and times only.

## Deleting a person's or a family's data (F-076)

**Not ready for real data yet (F-077):** review found that `--family` can delete a family the person only belongs to and leaves their sign-in, and two accounts with one email are not refused. Use only the dry run until F-077 is done.

`pixi run forget-person EMAIL [--content] [--family] [--yes] [--data-dir DIR]` (`scripts/forget_person.py`). Stop the app first and copy the data folder (on Railway: the `/data` volume; run it in a shell on the service, where `GITAWAY_DATA_DIR` is set). Without `--yes` it is a dry run that lists what it would delete. Tables that do not exist yet are skipped. It uses plain SQLite, so it works on a throwaway copy too (`tests/test_forget_person.py` does).

- **Plain run**: the person's sign-in (`core_users`), memberships, passkeys, last-family choice, invites sent to or by them, audit-log rows with their id or email (`sys_audit_logs`), and in each of their families their member row, push subscriptions and thread settings. Their messages and photos stay with the family.
- **`--content`**: also the messages they wrote and the photos they added (rows and files under `photos/<family>/`). Use it when they ask for their messages and photos to go.
- **`--family`**: the whole family of each family they belong to: its database file with `-wal` and `-shm`, `photos/<family>/`, memberships, invites, last-family choices, subscriptions and the family row. Other members' own sign-ins stay (run the script for them too if they ask). Implies `--content`.

Server logs on Railway age out on their own; say so when you confirm. After a real run, tell the person it is done.

## Drafting for creators (F-188, F-194)

The captain drafts a creator's post privately and sends them its claim link **on the live site**: open `https://gitaway.me/admin` (your email must be in `GITAWAY_ADMIN_EMAILS`) and use "Draft for a creator" (a post link, or tick rows of `docs/research/creators.csv`). Use /admin on gitaway.me; do not run the script for this. Each draft has "Review the draft": fix what the model got wrong, then copy the message with its claim link. A claim by someone whose email is not at the post's site, and an open import's byline, wait under "Waiting for your approval" on the same page until you approve them.

`pixi run draft-creators` (`scripts/draft_creators.py`) refuses to run unless `GITAWAY_DATA_DIR` is `/data`, the live data folder: run anywhere else it would keep its drafts in a local folder, so its claim links would not work on gitaway.me, and `scripts/` is not in the image. The pre-draft fetch is honest about who asked (its User-Agent says the author has not), and reads the site's robots.txt first: a site that asks `anthropic-ai`, `ClaudeBot`, `Claude-Web`, `GPTBot` or all robots to stay away from that page is not drafted from.

## Weather (F-203)

A real trip never shows invented weather (`gitaway/weather.py`). Each day shows one of three things:

- **MET Norway's forecast** for the days it covers (about nine days ahead), once `MET_NORWAY_TERMS_ACCEPTED=1`. It is free, also for commercial use, with credit: every place a forecast shows says "Forecast for <station>, based on data from MET Norway" and links their licence page (CC BY 4.0, NLOD 2.0), and /privacy names them. GitAway's server asks (never a browser), and only `https://api.met.no`: it never follows a redirect, tries each of its addresses in turn, and one 3-second deadline covers the whole call (a call is not started with under a second left; `gitaway/deadline.py` keeps the deadline). It sends a NOAA station's coordinates at four decimals (never a family's address), identifies itself with the site's address and `GITAWAY_CONTACT_EMAIL`, keeps each answer until its `Expires` header (12 hours at most) and at least three hours, then asks with `If-Modified-Since`. An answer that does not read cleanly counts as a failed call: the place is not asked again for five minutes. One gate keeps the whole site under five calls a second (MET's limit is 20); a 429 or 403 stops all calls for 10 or 60 minutes and is one WARNING line in the log, and so is a 203 (the product is deprecated: move to its successor before it is switched off).
- **Typical weather before the forecast opens**: NOAA's 1991-2020 U.S. Climate Normals (public domain), for 60 common US destinations in `gitaway/normals.json`, labelled "Typical late December · not a forecast yet" (the span of the trip's typical days) and naming the station. A destination gets a station only when one of the station's names starts it and every part after it is a state the station stands for, the United States, or another of its names ("Lake Placid, New York", "Hollywood Florida" and "Disneyland Paris, France" get none); abroad gets none. `pixi run build-normals` rebuilds the file (the station list is in `scripts/build_normals.py`; its downloads stay in `~/.cache/gitaway-normals`, mode 0700).
- **Nothing**, for a day that has passed or a place GitAway has nothing real for.

Sample weather stays only on the showcase's own sample trip. To try the forecast once with your settings: `pixi run probe-weather` (one real call for South Lake Tahoe; it needs `MET_NORWAY_TERMS_ACCEPTED=1`).

## What needs sign-in

Everything public stays browsable signed out: the landing page, hub (`/discover`), trips, creators, `/start`, the demo workspace (`/plan`). Saving, forking, booking and the calendar ask you to sign in and bring you back. `/family` (who you are and your family's id) is the one page that needs sign-in; it is the first page built on fh-saas's `create_auth_beforeware` + `require_tenant_access`.

## Deploy to Railway

The repo has a `Dockerfile` (Railway builds it by itself) that installs the locked `prod` pixi environment (no pytest or playwright), copies the code to `/app`, and starts `main.py` from the data folder. Health check: `GET /healthz` (200 `ok`, no session, no database).

1. **New project** from this GitHub repo (or `railway up`). It builds the Dockerfile; no start command is needed.
2. **Volume**: add one and mount it at `/data`. Every database (the host's `app_host.db` and each family's `<id>_db.db`) lives there. The app runs with `/data` as its working directory, which fh-saas needs because it stores family database paths relative to it. Do not change the mount path later.
3. **Variables** (service > Variables):
   - `GITAWAY_ENV=production` (also implied by Railway's `RAILWAY_ENVIRONMENT`)
   - `GITAWAY_DATA_DIR=/data`
   - `GITAWAY_SECRET_KEY=<long random string>` (for example `openssl rand -hex 32`). Keep it: changing it signs everyone out.
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
   - Do **not** set `GITAWAY_DEV_LOGIN` (production ignores it anyway) or `PORT` (Railway sets it).
4. **Networking**: generate a domain (`<app>.up.railway.app`). Set the service's health check path to `/healthz`.
5. **Google console**: under Authorized redirect URIs add `https://<app>.up.railway.app/auth/callback`. fh-saas builds the redirect from the request's host (`X-Forwarded-Host` if present) and uses `https` for any host that is not localhost, so it matches. Either **publish** the OAuth app (consent screen > Publish app) or leave it in Testing and add every family member's Gmail under **Test users**; in Testing, anyone else is refused by Google.
6. **Check a redeploy keeps the data**: sign in on the live site, create a trip, trigger a redeploy (Deployments > Redeploy), and confirm you are still signed in and the trip is there. Do this before the family arrives.

## One address (F-078)

In production, a request on any host other than the one in `GITAWAY_PUBLIC_URL` (for example the old `*.up.railway.app` address) gets a permanent redirect (308, so POSTs keep their body) to the same path and query on `GITAWAY_PUBLIC_URL`. `/healthz` (Railway's check) and `/auth/callback` (a sign-in already under way finishes where it started) are never redirected. The target comes only from the configured value, never from request headers. Locally, in tests, and when `GITAWAY_PUBLIC_URL` is unset or not a plain `https://host` address, nothing redirects. The code is `OneAddress` in `main.py`.

To move to another domain:

1. **Railway**: Settings > Networking > add the custom domain; Railway shows the DNS record to create.
2. **DNS**: create that record at the registrar and wait until Railway shows the domain as active.
3. **Google console**: add `https://<new domain>/auth/callback` under Authorized redirect URIs, and update the consent screen branding (app domain, authorized domains). Keep the old redirect URI until everyone has moved.
4. **Variable**: set `GITAWAY_PUBLIC_URL=https://<new domain>` and redeploy. From then on the old address redirects to the new one.

Things tied to the address, which do not carry over to a new one: passkeys (people sign in with Google and add the passkey again), Home Screen installs (re-add the app from the new address), and push subscriptions (switch the morning plan on again).

Proxy headers: in production uvicorn runs with `proxy_headers=True` and `forwarded_allow_ips="*"` (the container is reachable only through Railway's proxy), so the request scheme is `https`. uvicorn applies that to the client address as well, which is why production also switches the dev sign-in off outright; locally proxy headers are ignored, so the dev sign-in's "no proxy header, local peer only" rule still holds. Cookie: `Secure` and `HttpOnly`, `SameSite=Lax`, 30 days.

Local check of the image: `docker build -t gitaway . && docker run --rm -p 8080:8080 -e PORT=8080 -e GITAWAY_SECRET_KEY=x -v gitaway-data:/data gitaway`, then open `http://localhost:8080/healthz`.

## Plan it for me: the money and the agent (F-193)

A family pays once ($29) and an agent builds their whole trip in their GitAway account. **Nothing is sold until you do the steps below; the brief (`docs/briefs/plan-for-me.md`) is still a draft you approve.**

1. **Stripe**: in the Dashboard (test mode first) copy the secret key into Railway as `STRIPE_SECRET_KEY`. Under Developers > Webhooks add the endpoint `https://<your domain>/stripe/webhook` for `checkout.session.completed` and `checkout.session.async_payment_succeeded`, and copy its signing secret into Railway as `STRIPE_WEBHOOK_SECRET`. Redeploy.
2. **The agent**: `ANTHROPIC_API_KEY` (the same key the creator import uses). The job is `plan-for-me`, Claude Sonnet 5.5 by default; `GITAWAY_AI_MODEL_PLAN_FOR_ME`, `GITAWAY_AI_EFFORT_PLAN_FOR_ME` and `GITAWAY_AI_PROVIDER_PLAN_FOR_ME` change it (`docs/ai-usage.md`).
3. **Try one real purchase** in test mode with Stripe's test card `4242 4242 4242 4242`. With the founder check on (`PLAN_FOR_ME_REVIEW`, the default) the order page says "Your plan is built and being checked by a person"; open `/admin`, look at the plan ("Look and edit first"), tap **Send to family**, and check the order page reaches "Your trip is ready". Nothing in the tests could reach the real Stripe, so this is the one check that has to be done by hand.
4. **Refunds** are yours, by hand: Stripe Dashboard > the payment > Refund. The page promises "Not useful? Email us within 7 days for a full refund." and shows your address beside it, so **`GITAWAY_CONTACT_EMAIL` must be set** (the same variable as /privacy; in production Plan it for me is not for sale and `/plan-for-me` is a 404 without it). Add it to the ship checklist (`docs/launch/ship-checklist.md` is not on this branch). `/admin` lists every order, flags a failed one as "refund due" and shows what each cost in model tokens.
5. **The founder check** (F-197): while `PLAN_FOR_ME_REVIEW` is on, nothing reaches a family until you tap Send to family on `/admin`, so check `/admin` a few times a day; the pages promise "usually within a few hours". Set it to `0` to deliver at once.
6. **The founding price**: the first `PLAN_FOR_ME_FOUNDING_LIMIT` (10) paid families pay `PLAN_FOR_ME_PRICE_CENTS` ($29), everyone after `PLAN_FOR_ME_FULL_PRICE_CENTS` ($49). A refunded order is marked failed only when the build failed; a refund you give by hand for a "not useful" plan still counts as a taken spot. The limit is held when a payment page is opened: an unpaid order made at $29 keeps it only while its page (open for one hour) may still be paid; after that, once the spots are gone, it is repriced to $49 and its Pay button says so. A founding spot held by someone's open payment page is not given to a second page.
7. A paid order that was building when the app stopped is built again at the next start (`planforme.start()` in `on_startup`), without a second model call if the first answer was already saved.
