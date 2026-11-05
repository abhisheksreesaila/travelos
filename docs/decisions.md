# Autopilot decisions (2026-11-04 run, GOAL.md)

- D-01 · work on branch `autopilot/booking-creators` in worktree `../travelos-autopilot`, not a new repo · the product already has 178 shipped tickets to build on; a branch is the safe copy; master and gitaway.me untouched · reversible? yes (delete the branch)
- D-02 · four places: Los Angeles, San Diego, Honolulu, New York, all from SFO · LA/SD/HI were already named in `catalog.DESTINATIONS`; New York adds a long-haul, two-airport (JFK/EWR) case · yes
- D-03 · control plane, not checkout: every offer links out through `/go/<offer>` with a Travelpayouts-shaped marker + SubID; without keys an in-app `/sandbox/` partner mimics the checkout and posts back a conversion · matches the cheat sheet's decision (partners keep bookings and liability) and lets you feel the loop before any account exists · yes
- D-04 · synthetic data is showcase-only (`showcase.on()`); production keeps "sample prices" labels and 404s the sandbox · AGENTS.md rule for sample data · yes
- D-05 · look: omxqua Travel · Coast family (sand/deep-sea, sea-teal accent, kind colours) on the new and booking/creator pages first, not a whole-app reskin tonight · your design-taste.md assigns Coast to travel; reskinning every page in one night risks the shipped canvas · yes
- D-06 · creators get profile pages `/creators/<handle>` with four made-up creators (one per place), linking out to YouTube/Instagram and into `/plan?to=` · the marketing story is "every stop sends viewers back to your video" · yes
- D-40 · /creators keeps the paste box and gains the pitch plus a creator roster; profiles at /creators/<handle> registered last so draft/finish/done win · old routes keep working, no /creators/new needed · yes
- D-41 · only the LA creator has a cover photo (the only CC0 area photo available); other creators show none rather than reuse hotel photos · never present hotel photos as places · yes
