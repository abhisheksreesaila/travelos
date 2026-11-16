# Overnight goal (2026-11-16, autopilot while the founder sleeps)

**End goal (founder's words):** "go on autopilot and then go ahead and fix all the changes and cover page and all the stuff that we talked about. I'll check in the morning and … play around with it."

**Milestones (each checked by `pixi run python scripts/check_overnight.py`):**
1. M1 F-268: a place-only wish opens the matrix with a chosen, editable window.
2. M2 F-269: after Save, with booking opening soon, the next step says "Plan this trip".
3. M3 F-270: no page loads fonts from Google.
4. M4 F-256: every browser test module collects; the stale front-door, publish and letting-go tests are fixed or retired with a reason.
5. M5 The full unit suite passes; the browser suite passes (any flaky test named with evidence in docs/journal.md).
6. M6 Deploy readiness for live prices: docs/ship/live-prices.md (what could break, how we'd know, rollback) and a script that sets LITEAPI_KEY on Railway from the private file without printing it, ready to run on the founder's "deploy".

**Out of bounds:** deploying, setting Railway variables, pushing to GitHub, reading or printing the live key, real bookings, anything outside this repo.
**Assumptions:** the cover keeps eight beats (founder: "cover looks good"); default window = Friday ≥ 28 days out, 3 nights, ±2 days; Caveat self-hosted.
**Budget:** this one session overnight.
