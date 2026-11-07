# Where to pick up

Subagents run at **medium effort** (the founder asked).

**State (2026-11-07):**
- The release branch `autopilot/booking-creators` has F-200, F-203/F-208, F-206, F-201 and F-198/F-199 merged and green: 4,350 unit tests pass, and the browser suite passes except the known `test_publish` failure.
- **Live on gitaway.me:** F-207 only (no CDN scripts).
- **The rest of the release is not deployed.**

**Next:**
1. **The founder says "ship":**
   - Run the shipping checklist (`docs/launch/ship-checklist.md`).
   - Merge the branch into master in the main checkout.
   - Run `railway status` and confirm gitaway / web.
   - Run `railway up --service web --ci`.
   - Check `/`, `/signin`, `/trip`, `/for-creators` and `/plan-for-me` with `?q=<random>`.
2. **Then build F-209 (creators) and F-210 (booking)** from `docs/design/oneproduct/`, plus F-211 (the season background and weather animation), and F-205 once the founder picks the story (postcards with globe, or the diorama).
3. **Follow-ups logged** under F-198 and F-201 in `docs/plan.md`.

**Waiting on the founder:**
- "ship".
- Set `ORS_API_KEY`, later.
- Accept MET Norway's terms, then set `MET_NORWAY_TERMS_ACCEPTED=1`.
- Approve deleting `~/.cache/*-tmp`.
- Confirm the design calls in `docs/design/oneproduct/README.md`: Structured is the default theme, and "Follow this trail" leads to Where to?.

**Dev server:** `cd ~/Projects/travelos-autopilot && GITAWAY_DATA_DIR=$HOME/.cache/gitaway-dev-data/db GITAWAY_DEV_LOGIN=1 pixi run dev`, then open http://localhost:6001.
