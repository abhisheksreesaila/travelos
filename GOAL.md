# GOAL (autopilot run, started 2026-11-04)

**End goal (captain's words):** "a cool website with colors with the omxqua design language and a really touch-sensitive mobile app ... mimic the data for the bookings, create three or four vacations or places, generate synthetic data so I can see how this will work with the experience and the backend and Travelpayouts ... design the booking along with the planning along with the creator's thingy so people can start doing this, and I want to market this."

Branch `autopilot/booking-creators` (worktree `../travelos-autopilot`). Never deployed by this run.

## Milestones (each has tests in `tests/test_autopilot_contract.py` or `tests_browser/test_autopilot_look.py`; `scripts/check` runs them)
- **M1 Four places.** `/plan?to=<key>&d=&r=&a=` works for `la`, `sd` (San Diego), `hi` (Honolulu) and `nyc` (New York): each has its own flights, hotels and cars with place-specific names and prices; the start/search form offers all four.
- **M2 Partner seam (control plane).** Every offer on `/plan` has a "Book on <partner>" link to `/go/<offer_id>?to=&d=&r=&a=`. `/go/...` logs a click and answers 302. With `TRAVELPAYOUTS_MARKER` set it goes to a Travelpayouts-shaped https link carrying `marker=` and `sub_id=` (SubID names family + trip); without it, to the in-app `/sandbox/...` partner that mimics the partner's checkout. Providers sit behind one seam (`gitaway/partners/`): synthetic now; Travelpayouts / LiteAPI / Duffel Cars / Uber clients drop in when keys exist.
- **M3 The loop closes.** Completing a sandbox checkout (POST its form) records a simulated conversion, Travelpayouts statistics-API shaped; `/partners` (signed in) lists the family's clicks and bookings with partner, offer, sub_id, status and estimated commission; the booked offer appears in the family's trip as "Booked elsewhere · <partner>".
- **M4 Creators.** `/creators` shows at least four creators (one per place); `/creators/<handle>` is a profile: name, channel link, their trips, forks; each creator trip offers "Plan this trip" to `/plan?to=<its place>`.
- **M5 omxqua look, touch first.** `/plan`, `/creators`, `/creators/<handle>`, `/sandbox/...` and `/partners` use the omxqua Travel · Coast tokens (`--oq-*`, root class `oq-family-travel`); no glass or blur; at 390px wide no sideways scroll, every button/link-button at least 40px tall, the plan lanes swipe sideways (scroll-snap); at 1440px the lanes sit side by side.
- **M6 Production stays honest.** With `GITAWAY_SHOWCASE=0`: `/sandbox/...`, `/creators...` and `/partners` 404 unless real keys exist; `/plan` shows no invented offers or prices at all, only the honest booking lanes (amended 2026-11-07, D-304; it said "still labels sample prices"); the whole existing suite still passes (`pixi run test`).

**Done means:** `scripts/check` prints PASS for M1 to M6, and `docs/report.md` has screenshots (phone + laptop) of plan, creator profile and partners.

**Out of bounds:** no deploy (no `railway`), no push, no paid services or sign-ups, no secrets read, nothing outside this worktree, never touch `master` or `../travelos`. Don't edit these milestones or the checker/contract tests to pass (add milestones only, logged).

**Assumptions:** see `docs/decisions.md` D-01 onward.

**Budget:** 80 agent turns per milestone, about 8 hours total.
