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
| `GITAWAY_DEV_LOGIN` | local only | `1` turns on the dev sign-in (see below). Leave it unset anywhere else. |
| `GOOGLE_CLIENT_ID` | for Google sign-in | The OAuth client id (fh-saas reads this name). |
| `GOOGLE_CLIENT_SECRET` | for Google sign-in | The OAuth client secret (fh-saas reads this name). |
| `GITAWAY_SECRET_KEY` | recommended when deployed | Secret that signs the session cookie. If unset, a random key is made once and kept in `.sesskey` (gitignored), which is fine for local development. |
| `PORT` | optional | Port for `pixi run dev`. Default 5002. |
| `FH_SAAS_LOG_LEVEL` | optional | `DEBUG`, `INFO`, `WARNING` (default). The app calls fh-saas's `configure_logging()` at startup. |

There is no redirect-URI variable: fh-saas builds it from the address of the request, as `<scheme>://<host>/auth/callback` (`http` for `localhost` and `127.0.0.1`, `https` for anything else).

### Where the data lives

fh-saas makes each family's database file relative to the process's **working directory** and has no setting to change that. So `main.py` makes `GITAWAY_DATA_DIR` the working directory at startup; the host database (`app_host.db`) and every family database (`<id>_db.db`) then sit side by side in that one folder. Consequences:

- Code must not use relative paths. Assets and templates are found from the project folder (`Path(__file__)`).
- The family database location is stored in the host database as a relative path, so the folder must stay the same for the life of the data. When deploying, point `GITAWAY_DATA_DIR` at the persistent volume and test a redeploy before real users arrive.
- To start fresh locally, stop the server and delete the folder.

## The dev sign-in (local only)

Set `GITAWAY_DEV_LOGIN=1`. The sign-in page then shows an email box and **Dev sign-in (local only)**. Any email works; the first time one is used, a person and their family are created, exactly as the Google sign-in does. It is refused (403) unless **both**:

1. `GITAWAY_DEV_LOGIN` is `1`, and
2. the request comes straight from this machine (`127.0.0.1` or `::1`) with no proxy header (`X-Forwarded-*`, `X-Real-IP`, `Forwarded`). Forwarded addresses are never trusted.

Do not set the flag in production. If you run through a local reverse proxy, the dev sign-in is refused on purpose.

## Google sign-in

It switches on when both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set; the sign-in page then shows **Sign in with Google**. Routes: `/login` (starts), `/auth/callback` (Google returns here), `/logout` (or the header's Sign out).

Google Cloud console steps:

1. Open <https://console.cloud.google.com/> and create (or pick) a project, e.g. "GitAway".
2. **APIs & Services > OAuth consent screen**: choose **External**, fill in the app name (GitAway) and your email, and add the scopes `openid`, `email` and `profile`. While the app is in **Testing**, add each family member's Gmail address under **Test users** (only they can sign in until the app is published).
3. **APIs & Services > Credentials > Create credentials > OAuth client ID**, application type **Web application**.
4. Under **Authorized redirect URIs** add `http://localhost:5002/auth/callback`. Use the same host you browse with: if you open `http://127.0.0.1:5002`, add `http://127.0.0.1:5002/auth/callback` too. For a deployed site add `https://<your domain>/auth/callback`.
5. Copy the client id and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, restart `pixi run dev`, and open <http://localhost:5002/signin>.

## What needs sign-in

Everything public stays browsable signed out: the landing page, hub (`/discover`), trips, creators, `/start`, the demo workspace (`/plan`). Saving, forking, booking and the calendar ask you to sign in and bring you back. `/family` (who you are and your family's id) is the one page that needs sign-in; it is the first page built on fh-saas's `create_auth_beforeware` + `require_tenant_access`.
