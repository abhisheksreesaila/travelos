# Project agent memory

GitAway (repo name `travelos`, the product's former name). Design-first frontend on fake data; read `docs/brief.md` and `docs/plan.md` first.

- Python via pixi only: `pixi run dev` (port 5002), `pixi run test`. Never pip. Page-JS browser tests (`tests_browser/`, headless Chromium, ~5s): `pixi run test-browser`, after a one-time `pixi run test-browser-install`.
- `main.py` builds the FastHTML app and serves `/assets/…`; every screen is a module in `gitaway/pages/` exposing `register(app)`, appended to `SCREENS` in `gitaway/pages/__init__.py`. Placeholders register last as fallbacks, so a real screen on the same path wins; delete its entry from `placeholders.PLACEHOLDERS` when you ship it. Keep screens in their own modules so tickets can be built in parallel.
- `gitaway/layout.py` `page()` is the shared shell (fonts, tokens, header, footer, `data-theme` sunset|pacific). `gitaway/icons.py` `icon()` gives inline SVG icons; never use emoji.
- `gitaway/catalog.py` is the single fake catalog. Money is integer cents; display with `catalog.money()`.
- Visual rules: `design-system/DESIGN-SYSTEM.md` (tokens in `assets/css/tokens.css`, shared components in `assets/css/base.css`). The artboard sources for each screen are in `docs/design/canvas/`.
- Photos in `assets/photos/` are CC0 area photos (see `CREDITS.md`), never presented as a hotel or room.
- Sign-in, families and storage are fh-saas (`gitaway/auth.py`, `docs/setup.md`). The process runs with the data folder (`GITAWAY_DATA_DIR`) as its working directory, so never use relative file paths; resolve from `Path(__file__)`. A family's trips, bookings, calendar, friends, rides, forks and saves live in its tenant database (`gitaway/familydb.py`, `docs/family-db.md`); the cookie holds only the sign-in. Tests sign in with the dev sign-in (`tests/test_signin.py` `sign_in`, `tid`; `person()` for model-level tests).
- People join a family by invitation and have a role (admin, editor, viewer): `gitaway/members.py` (invites, memberships, active family), `gitaway/access.py` (the beforeware that gates every write by role), `docs/family-members.md`.
- Test seams: HTTP routes through Starlette's TestClient (`tests/conftest.py` `client`) and the catalog's public functions.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
