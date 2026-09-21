# TravelOS

A polished, **local-only** travel discovery and trip-planning demo. It pairs an Expedia-like discovery surface with public, creator-authored itineraries and a tmux-inspired trip command center.

**Status:** local-only demo — no provider credentials or external services required.

## What is included

- A colorful travel landing page and searchable public discovery feed.
- Four high-quality, deterministic destination fixtures rendered with original CSS/SVG-style scene treatments—no remotely hosted photos or image APIs.
- Public itinerary pages that work logged out, with clear fixture weather, maps, price, and availability labels.
- A local demo sign-in that explains its scope, then lets a traveler fork a public plan into a tenant workspace.
- Rich creator-led public plans with local field notes, channel-context cards, and clear fixture-only reach language—no social-platform connection.
- A dense, responsive command center with larger terminal-inspired hierarchy where a traveler can change trip dates, group size, comfort budget, pace, and interests; local fixture itinerary, cost ledger, and prep checklist views recalculate from those saved choices.
- A creator studio with YouTube/Instagram presence language and a locally persisted route-pitch form.
- SQLite-backed demo state using `fh-saas`' host database plus an isolated tenant database.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python main.py
```

Open `http://localhost:5001` (or the port FastHTML reports). If a system Python does not include `pip`, create the virtual environment with a Python distribution that does, then install the project normally.

The first request creates ignored SQLite files in `data/`:

- `travelos_host.db` — the fh-saas host records (local demo identity, tenant membership)
- `travelos-weekend-club_db.db` — the isolated Weekend Club tenant records (forks, per-fork planning preferences, and creator submissions)

Set `TRAVELOS_DATA_DIR=/some/local/path` before starting to store those files elsewhere. Set a unique `SESSION_SECRET` before exposing even a demo instance beyond your machine.

## Demo journey

1. Browse **Discover** while signed out and open any public plan.
2. Choose **Sign in to fork this plan**. The app uses the explicit local fixture traveler, Ari Rivera; no OAuth, email, or real identity provider is invoked.
3. Fork the plan and open **Trip command center**. Set dates, travelers, a comfort budget, pace, and interests, then apply them to see the fixture itinerary, ledger, and prep checklist update and persist locally. Try `⌘/Ctrl + K` or pane keys `1`–`6` for local interaction polish.
4. Visit **For creators** and submit a route pitch. It is saved in the local tenant SQLite queue only.

## Design and data notes

All destination scenes, route drawings, map context, forecasts, booking cards, costs, channel reach, and plan metrics are authored local fixtures or generated CSS/SVG treatments. There are no external image assets, tracking calls, booking providers, weather providers, map providers, social APIs, or paid AI services.

The command center intentionally borrows its dense panels, muted terminal palette, monospaced labels, and keyboard cues from an Omarchy-style terminal while keeping discovery bright and travel-forward.

## Extension boundaries

The demo leaves deliberate seams rather than speculative integrations:

| Need later | Current seam |
| --- | --- |
| Account identity / OAuth | `POST /signin` in `main.py` can be replaced with `fh_saas.utils_auth` OAuth handlers. |
| Workspace authorization | The local session records user/tenant IDs; production routes should apply `fh_saas` auth beforeware and `require_tenant_access`. |
| Travel inventory | `data.PUBLIC_TRIPS` is the normalized public-plan contract; booking cards are clearly labeled fixture view models. |
| Fork personalization | `TripPreferences` in `models.py` and `update_trip_preferences()` in `data.py` persist local planning inputs; `workspace_plan_context()` in `main.py` derives the fixture workspace views. |
| Weather and maps | `workspace()` and `plan_detail()` own their presentational fixture modules, ready for adapter-fed view models. |
| Collaboration | The command drawer is a visual cue only; its buttons identify realtime invite/share boundaries. |
| Creator publishing | `CreatorSubmission` in `models.py` persists local pitches. Review, publishing, analytics, and social integrations are future workflows. |

## Validation

```bash
python -m unittest discover -s tests -v
```

The tests use an isolated temporary SQLite location and exercise public discovery, creator context, sign-in/fork/workspace state, persisted fork-personalization updates and validation, creator submission, and the no-provider fixture claims.
