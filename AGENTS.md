# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- App entry point and route/UI composition: `main.py`; start it with `python main.py` after installing the `pyproject.toml` dependencies.
- Tenant-scoped fixture persistence is implemented in `data.py` with fh-saas host and tenant SQLite databases; generated runtime databases belong under ignored `data/` (or `TRAVELOS_DATA_DIR`).
- Run the deterministic local smoke suite with `python -m unittest discover -s tests -v`. See `README.md` for the product journey and explicitly deferred provider integrations.

## Architecture (post-search-first restructure)

Architecture is **plan-centric**: search is a lightweight gateway that returns matching plans; the plan detail page absorbs all rich context (weather, 10 places, friend recommendations, flights/hotels stubs). The creator pipeline is wired end-to-end: submitting a story auto-generates a discoverable trip.

- Domain glossary: `CONTEXT.md` — defines Traveler, Viewer, Contributor, Professional creator, Plan, Itinerary, and the four distinct actions (plan, collaborate, share link, publish).
- Architecture decisions: `docs/adr/0001-no-platform-usernames.md` (anonymous publishing), `docs/adr/0002-plan-as-atomic-unit.md` (plan-first architecture).
- `TRAVELOS_PROTOTYPE=1` flag gates all traveler-facing prototype routes and the `/search` demo flow.
- `data._generated_trips` is an in-memory runtime registry for creator-generated trips. It does **not** survive a server restart — trips must be regenerated.
- Circular import between `data.py` ↔ `search_fixtures.py` is mitigated via function-local lazy imports; keep cross-module mutations to `_generated_trips` through `data.register_generated_trip()` only.
- Route `/plans/{slug}/preview` serves a no-session workspace preview; no prototype guard — intentional so it works regardless of flag.
- Server: `TRAVELOS_PROTOTYPE=1 .venv/bin/python main.py` (runs on port 5002, auto-reload via uvicorn `--reload`).

## Design system (Wave 0)

The UI uses a modular CSS architecture with two themes. No framework or build step — plain CSS custom properties + ES modules.

**CSS load order** (enforced in `document()`):
1. `assets/tokens.css` — All CSS variables: colors, typography, spacing, shadows, both themes
2. `assets/components.css` — Shared components: badges, buttons, cards, forms, toast
3. `assets/public.css` — Public-facing pages (landing, discover, plan detail, creator, sign-in)
4. `assets/workspace.css` — Command center (scoped under `.command-shell`)
5. `assets/responsive.css` — Shared breakpoints and reduced-motion

**Themes** — two modes controlled by `data-theme` attribute on `<body>`:
- `[data-theme="bright"]` — Public pages (default). Warm sunset palette, colorful, inviting.
- `[data-theme="dark"]` — Workspace. Terminal-inspired, monospaced headings, dense layout.
- Workspace always renders dark; public pages allow toggle via `data-theme-toggle` button.
- Theme preference persists in `localStorage` key `travelos-theme`.

**Icons** — two complementary systems:
- Server-side: Python `icon()` function in main.py with hardcoded SVG paths (used in HTML templates)
- Client-side: ES module `assets/icons.js` exporting `icon()` and `icons()` (used in app.js)
- Keep both in sync when adding new icons. Names should match where possible.
- `assets/brand.js` provides brand marks, playful elements, and gradient CSS styles.

**Key design patterns:**
- `.command-shell` body class → workspace dark theme + pane grid layout
- `data-theme-toggle` buttons in both public_header and workspace_header
- `Ctrl+Shift+T` keyboard shortcut for quick theme toggle
- All icons are inline SVG — zero CDN/external dependencies, works offline

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
