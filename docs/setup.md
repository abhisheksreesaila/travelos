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
| `GITAWAY_DEV_LOGIN` | local only | `1` turns on the dev sign-in (see below). Leave it unset anywhere else; production ignores it. |
| `GOOGLE_CLIENT_ID` | for Google sign-in | The OAuth client id (fh-saas reads this name). |
| `GOOGLE_CLIENT_SECRET` | for Google sign-in | The OAuth client secret (fh-saas reads this name). |
| `GITAWAY_SECRET_KEY` | required in production | Secret that signs the session cookie. In production the app will not start without it. Locally, if unset, a random key is made once and kept in `.sesskey` (gitignored), which is fine for local development. |
| `PORT` | optional | Port for `pixi run dev`. Default 5002. |
| `FH_SAAS_LOG_LEVEL` | optional | `DEBUG`, `INFO`, `WARNING` (default). The app calls fh-saas's `configure_logging()` at startup. |
| `GITAWAY_VAPID_PUBLIC`, `GITAWAY_VAPID_PRIVATE`, `GITAWAY_VAPID_SUBJECT` | for the morning plan push | The Web Push (VAPID) key pair and a `mailto:` contact (F-066). Without them the Morning plan card is not shown and nothing is sent. Make them with `pixi run vapid-keys mailto:you@example.com` (below). |

There is no redirect-URI variable: fh-saas builds it from the address of the request, as `<scheme>://<host>/auth/callback` (`http` for `localhost` and `127.0.0.1`, `https` for anything else).

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

Proxy headers: in production uvicorn runs with `proxy_headers=True` and `forwarded_allow_ips="*"` (the container is reachable only through Railway's proxy), so the request scheme is `https`. uvicorn applies that to the client address as well, which is why production also switches the dev sign-in off outright; locally proxy headers are ignored, so the dev sign-in's "no proxy header, local peer only" rule still holds. Cookie: `Secure` and `HttpOnly`, `SameSite=Lax`, 30 days.

Local check of the image: `docker build -t gitaway . && docker run --rm -p 8080:8080 -e PORT=8080 -e GITAWAY_SECRET_KEY=x -v gitaway-data:/data gitaway`, then open `http://localhost:8080/healthz`.
