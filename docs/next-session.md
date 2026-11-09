# 2026-11-08 evening: booking concept (prototype only)
- Concept agreed in talk, brief still draft: `docs/briefs/unified-booking.md` (sentence search; stays live via Stay22 API; flights = Aviasales recent prices, "about"; never the seller).
- Prototype: `docs/design/booking-split/flow.html` (slim cover + booking view + hand-off + paste confirmation). Serve with `python -m http.server 6040` in that folder.
- Founder: open a Stay22 account; approve the brief.

# Overnight 2026-11-08 (on master, NOT pushed, NOT deployed)

Built, reviewed and merged on local master:
- **Where to? takes any place** (off the showcase: one box, no sample cities, no sample prices or sample kids).
- **Make this a trip**: on /plan and Where to?, a search becomes the family's trip and opens the cockpit (POST /trip/new; signed out goes through sign-in).
- **Widgets beside the booking lanes**: weather (NOAA typical or MET forecast, labelled), cost so far (only Aviasales' real fare, else "No price yet"), drive from the airport (OSRM; hidden when unknown). Nothing invented.
- **The cover rebuilt on the agreed story**: 11 scenes with real screenshots (book, cockpit, day, Ask, family, published trip, creators), 3D Tahoe behind the opening and closing scenes. Screenshots: `scripts/cover_shots.py`.
- Reviewer: two bugs fixed (US towns named after foreign cities got a foreign clock; junk place text gave a 500), plus a busy-router cache fix. Known gap: `geo.fetch` is not yet behind `deadline.py`.
- Tests: full suite green; 72 browser tests for the touched pages green.

To ship: `git push origin master`, then deploy as before (`railway status` first: Project gitaway, service web).
Founder to check: the cover's headlines on your phone (`docs/report/cover-story-*.png`); the 3D world's labels still say "five days" while the copy says a week.

# Where to pick up

Subagents run at **medium effort** (the founder asked).

**Live on gitaway.me (2026-11-08 00:51, deployment d7789a07):** the whole release.
- Direction A reskin, light and dark
- the 3D Tahoe cover ("Take a trip. Leave a trail.")
- the trip cockpit (Ticket line)
- real weather: typical weather until MET Norway's terms are accepted
- booking links for any destination
- free Plan it for me (off until `ANTHROPIC_API_KEY` is set)
- no CDN scripts

Checks after the deploy: `/healthz` 200 in 0.16 s; `/`, `/signin`, `/privacy`, `/plan` and `/for-creators` 200; `/trip` 303; `/admin`, `/sandbox` and `/community` 404 as designed; no Tracebacks in the logs. Rollback target: `388eefbf-69f0-4062-84e4-dceb15fd182c`.

**Branches:** master is pushed (f08e5bd). Start new work from master.
- `autopilot/booking-creators` is merged, but its history still holds two films of 160 MB each, which GitHub rejects. Don't push it.
- Backups of the pre-strip refs: `backup/pre-strip-master`, `backup/pre-strip-autopilot`.
- The films are in `~/.cache/gitaway-film/`.

**What the release does and doesn't do (checked on 2026-11-08 with sample data off, as production runs):**
- **Booking:** `/plan` takes any place. For Lake Tahoe in December it gives flights on Aviasales, stays on Expedia, Airbnb and Vrbo, cars, things to do, and five ski resorts to buy from directly.
  - No weather, money or drive-time widgets on the booking page yet (F-210).
  - **"Where to?" (`/start`) still offers only four sample cities**, with "Sample prices for Los Angeles". It's the same on the old live site.
  - **A booking search never becomes a trip**, so a new person can't reach the cockpit except by importing a trip. This is the biggest gap. Fix it in F-210.
- **Planning:** the cockpit, the day view, Ask, family chat, and Plan it for me once the key is set. All of it needs a trip first (see above).
- **Contributing:** `/for-creators` and creator import are live. Community trips, forks and thanks appear once the first real trip is published (by design, F-181).

**Waiting on the founder:**
- Set `ANTHROPIC_API_KEY` on Railway (service web) to turn on free Plan it for me.
- Accept MET Norway's terms, then set `MET_NORWAY_TERMS_ACCEPTED=1`.
- `ORS_API_KEY`, later.
- The cover: the story is agreed (why GitAway exists → booking with everything in view → planning tools → leave a trail; one travel story, real screenshots per feature, a plain headline per scene). Screenshots will come from the new look, now live. Storyboard: `docs/design/cover-v2/story/`; Sol's scroll prototype: `docs/design/cover-v2/scroll-prototype/`.
- Gemini image generation needs billing on the key's Google project. The storyboard was drawn by hand instead.

**Next:**
1. F-210: booking as one product. Any place on "Where to?", the widgets beside each lane, and a search that becomes a trip.
2. The cover rebuilt on the agreed story with real screenshots.
3. F-209 (creators), F-211 (season and weather), F-205 (shared-trip story).

**Bugs found tonight:**
- A test fixture leaves 809 MB `/tmp/gitaway-test-*-copy-*` folders behind (111 of them filled `/tmp`, and SQLite then failed with "disk I/O error"). Find the copy fixture and clean it up. Until then, run tests with `TMPDIR=$HOME/.cache/gitaway-testtmp`.
- The Dockerfile copied `docs/research/creators.csv`, which `.dockerignore` dropped, so the first build failed. Fixed; `tests/test_dockerfile.py` now guards it.

**Dev server:** `cd ~/Projects/travelos && GITAWAY_DATA_DIR=$HOME/.cache/gitaway-dev-data/db GITAWAY_DEV_LOGIN=1 pixi run dev` (add `GITAWAY_SHOWCASE=0` to see what production shows).
