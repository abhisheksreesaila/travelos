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

## Compass travel suite — connected frontend

Open **http://localhost:5002/prototype**. The default signed-out landing explains the complete travel workflow; **Demo sign-in** selects a local persona, not a real account.

```bash
TRAVELOS_PROTOTYPE=1 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 5002
```

**Try it:** demo sign-in → compare independent flight and stay lanes → select a combination → **Save pair** (Draft, not reserved) → review complete costs, flight legs and hotel dates → acknowledge **simulated checkout** → the actual selected plan’s Calendar. Notes and local Invite are primary; History, Undo, payer demo, PDF snapshot and separate public contribution remain available. Refresh/retry does not create duplicate trips. Sign-out preserves work; the next sign-in resumes a confirmed plan, or a saved draft / My Trips fallback.

### Local catalog, not provider APIs

`assets/compass-demo.json` contains original synthetic offers, child fares, baggage, cancellation/room policies, integer-cent costs, sample ratings/amenities, daily weather examples, neutral fictional stories/events and two fictional creator examples. The adapter loads it with a local GET and validates it before use; failed loads have Retry, unsupported choices have explicit empty results. No airline, hotel, payment, weather, news, map or social API is called.

- **Default:** SFO → BUR, return SAN → SFO, October 5–10, 2026; 3 adults, child age 4, 2 rooms, 5 nights (Hollywood 2 + coast 3). Four flight offers and three stay bundles.
- **Whole-trip arithmetic:** direct + standard **$4,135.40**; one-stop + upgrade **$4,298.40**; net upgrade **$163.00**. Every total includes sample taxes and mandatory fees. Changing dates, adults, child ages or rooms recalculates actual fare/room/night lines; it never mixes per-person and per-room headline prices.
- **Other supported destinations:** San Diego (SFO↔SAN) and Santa Monica (SFO↔LAX), each with four flights and three distinct single-base stay bundles. October 1–31 only; 1–7 nights, or 3–7 for the two-base coast trip. 1–12 adults, up to 6 children ages 0–17, 1–6 rooms; maximum flight party 12 and room occupancy 2 including children.
- **Query vs filters:** query typing marks both lanes, context and total stale and blocks checkout. Refresh commits the query; changed-query offers require explicit reselection. Independent filters never silently clear the other lane or a valid hidden selection; its known cost remains in the summary.
- **Context:** date-bound authored weather in °C, not a forecast; original fictional stories/events, not current news. Real async catalog refresh has a 180ms fade, disabled for reduced motion. Stay drawers show exact dates, sample policies and unknown amenities. The interactive area map is only a rotatable region schematic—not Street View, property coordinates, verified distances or walking directions.
- **Photographs:** five optimized local public-domain / CC0 JPGs (564,013 bytes) in `assets/photos/compass/`. Every image identifies the depicted destination, never a hotel/room. La Jolla is not Del Mar and establishes no hotel-to-beach walking distance. Canonical source/license URLs, authors, dimensions and hashes are embedded in the JSON and available through **Photo credits**; external links open only on user request.

### Community, calendar and preservation

Community and public deep links remain account-free. Two clearly fictional YouTube-/Instagram-style examples can be selected, edited stop by stop, exactly previewed, published as immutable local editions and copied whole into private My Trips. They are not extracted from real accounts. The existing URL example and blank author remain available. Public payloads retain their strict allowlist: no participant names, private notes, payer/receipt data or private history. A separate contribution must be reviewed again after edits; old editions never change.

The existing **18-stop California family sample is unchanged**, including every detail and unverified claim: BUR **11:30 is arrival**, with no supplied outbound departure. United 2117 SAN **15:56** → SFO **17:38**, Loews Monday–Wednesday and Del Mar Wednesday–Saturday are preserved. The new package’s synthetic 09:58 departure and planned hotel arrival anchors are separate data, not changes to that seed. Existing UTC plans remain UTC; California uses America/Los_Angeles / PDT, with no automatic conversion.

Calendar retains its **96px/hour, 24-hour, 2304px grid**, accurate duration bands, pointer movement/resizing, labeled keyboard edits and Undo. Short/overlapping activities remain individually reachable in the Timed activity list. Unscheduled time stays empty unless an activity is explicitly added. Frozen PDF snapshots include all dates, endpoints and details even when disclosures are closed, exclude private fields, and change only when explicitly regenerated.

### Appearance, storage and boundaries

- **Compass is the new missing/invalid-preference default.** Intentionally saved Fieldwork and Snap preferences stay respected. The appearance selector is available in the header and every drawer. Switching changes only attributes/select values and guarded `localStorage['travelos.connected.appearance.v1']`; dirty forms, focus, scroll, route and domain state are not remounted.
- Compass uses Arial/local sans, 14px body, 13px rows, 12px secondary, 24px working headings and compact controls; coarse-pointer controls are at least 44px. Measured at 1440×900: first offer **418.16px**, all four flights and three stays fully visible by **866.16px**, with the combined total above. Mobile lanes stack with a sticky total and query drawer. All three themes passed 320/390px reflow; 720×450 equivalent 200% reflow was checked, **not certified as native browser zoom**.
- Canonical work remains in `sessionStorage['travelos.connected.v1']`, upgraded additively and separated by demo persona. Reload/sign-out preserve it; closing the tab may discard it. Quota/storage failures report memory-only persistence until reload. Existing drafts, private trips and immutable editions are not reset or replaced.
- `/prototype` and its allowlisted modules/JSON/photos are opt-in (`TRAVELOS_PROTOTYPE=1`). Only static frontend routes changed; root/auth, fh-saas beforeware, tenant databases and production package behavior did not. No new dependencies or frameworks.
- Deep modules: `compass-fixtures.mjs` (load/validate/search/quote/context), `compass-model.mjs` (additive state transitions), `compass-views.mjs` (rendering), `compass-flow.mjs` (thin browser orchestration), `compass.css` (scoped presentation). Existing connected public/calendar modules remain authoritative.

```bash
node --test tests/*.test.mjs
.venv/bin/python -m unittest discover -s tests -v
```

The checkout has an existing `.venv` but no pixi executable. Verification uses the existing isolated Node/CDP browser and unittest runner; no dependencies were installed. Compass reports, isolated browser harnesses, before/after screenshots, density measurements and PDF replays are session-only under `files/.lavish/travelos-parallel-suite/implementation/`; its `before/` directory preserves the current-turn source baseline. Earlier compact-family/readability evidence remains intact.

## Earlier frontend layout previews — GitHub for travel

The opt-in, throwaway prototype explores one consistent visual language across discovery, sign-in, creator intake, public itineraries, and the traveler workspace. It is separate from the persisted demo described below.

```bash
TRAVELOS_PROTOTYPE=1 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 5002
```

Open **http://localhost:5002/?variant=A** or **http://localhost:5002/creators?variant=A**. The creator layout switcher compares **A: source desk**, **B: transcript review**, and **C: itinerary board**. Traveler pages compare **A: sunny fieldnotes**, **B: route atlas**, and **C: family postcard**. These are different working layouts, not different skins. Preview navigation preserves the selected variant; switching creator layouts also preserves the current draft.

- **Creators:** paste a URL (or use the sample), inspect a synthetic transcript, generate structured itinerary stops, review the draft, and preview the output. This is source-to-plan, not a blog editor.
- **Travelers:** explore the sample plan, fork into a preview workspace, try family/date/pace controls, and inspect a share/print preview.
- **Simulation boundary:** no URL is fetched; transcripts, attribution, weather, and trip content are authored fixtures. No real account, publication, invite, booking, or collaboration is created. Preview edits live only in the current page and reset on reload/navigation.
- **Isolation:** without `TRAVELOS_PROTOTYPE=1` and an explicit `?variant=`, the existing local demo remains unchanged. Its sign-in, tenant forks, and preferences still use SQLite. The application still bootstraps the existing demo store at startup; preview interactions do not write to it.

Prototype code is deliberately named `prototype_*.py` and `assets/prototype*.{css,js}`. Layout selection is pending visual feedback; these are not production integrations.

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

The tests use an isolated temporary SQLite location and exercise public discovery, creator context, sign-in/fork/workspace state, persisted fork-personalization updates and validation, creator submission, and the no-provider fixture claims. They also cover opt-in prototype routes/assets for all three layouts and verify that the normal workspace still requires sign-in.
