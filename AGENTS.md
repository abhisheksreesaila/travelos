# Project agent memory

GitAway (repo name `travelos`, the product's former name). Design-first frontend on fake data; read `docs/brief.md` and `docs/plan.md` first.

- Python via pixi only: `pixi run dev` (port 5002), `pixi run test`. Never pip. Page-JS browser tests (`tests_browser/`, headless Chromium, ~5s): `pixi run test-browser`, after a one-time `pixi run test-browser-install`. `pixi run test-random` runs the suite in random order (add `--randomly-seed=N` to repeat a run).
- `main.py` builds the FastHTML app and serves `/assets/…`; every screen is a module in `gitaway/pages/` exposing `register(app)`, appended to `SCREENS` in `gitaway/pages/__init__.py`. Placeholders register last as fallbacks, so a real screen on the same path wins; delete its entry from `placeholders.PLACEHOLDERS` when you ship it. Keep screens in their own modules so tickets can be built in parallel.
- `gitaway/layout.py` `page()` is the shared shell (fonts, tokens, header, footer, `data-theme` sunset|pacific). `gitaway/icons.py` `icon()` gives inline SVG icons; never use emoji.
- `gitaway/catalog.py` is the single fake catalog. Money is integer cents; display with `catalog.money()`.
- Visual rules: `design-system/DESIGN-SYSTEM.md` (tokens in `assets/css/tokens.css`, shared components in `assets/css/base.css`). The artboard sources for each screen are in `docs/design/canvas/`.
- Photos in `assets/photos/` are CC0 area photos (see `CREDITS.md`), never presented as a hotel or room.
- Sign-in, families and storage are fh-saas (`gitaway/auth.py`, `docs/setup.md`). The process runs with the data folder (`GITAWAY_DATA_DIR`) as its working directory, so never use relative file paths; resolve from `Path(__file__)`. A family's trips, bookings, calendar, friends, rides, forks and saves live in its tenant database (`gitaway/familydb.py`, `docs/family-db.md`); the cookie holds only the sign-in. Tests sign in with the dev sign-in (`tests/test_signin.py` `sign_in`, `tid`; `person()` for model-level tests).
- Production (Railway, `Dockerfile`, `docs/setup.md`): `auth.production()` is true with `GITAWAY_ENV=production` or `RAILWAY_ENVIRONMENT`; it needs `GITAWAY_SECRET_KEY`, forces the dev sign-in off and the cookie https-only. `/healthz` skips every beforeware. Sign-in is a 30-day sliding cookie (`session.slide`); test pins and fixtures that need dev settings must not set `GITAWAY_ENV`.
- People join a family by invitation and have a role (admin, editor, viewer): `gitaway/members.py` (invites, memberships, active family), `gitaway/access.py` (the beforeware that gates every write by role), `docs/family-members.md`.
- One Ask box (`/trip/ask`, F-087): `gitaway/say.py` routes (a short request is a speak change, a long paste a convert plan), asks follow-ups and applies; `gitaway/pages/tab_ask.py` draws it. The old `/trip/add` Convert screens are gone (it redirects to the box). On a phone the centre Ask tab opens it as a sheet over the screen (F-104, `docs/trip-canvas.md`): the same routes answer fragments to `X-Ask: 1`, and `ask.js` is reused via `AskBox.init`.
- Sample data has one switch: `gitaway/showcase.py` (`showcase.on()` is false in production; `showcase.HIDDEN` lists the routes that then 404; `GITAWAY_SHOWCASE=1/0` overrides, never set it on Railway). New sample or community content must check `showcase.on()` and be tested in both modes (`tests/test_showcase.py`).
- Test seams: HTTP routes through Starlette's TestClient (`tests/conftest.py` `client`) and the catalog's public functions.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
