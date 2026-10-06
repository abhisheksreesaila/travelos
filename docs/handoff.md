# Handoff (2026-10-06)

Where things stand for the next session.

- Live: https://gitaway.me (Railway "gitaway"/"web"). Master = what's live; GitHub origin is up to date. Railway does not deploy on push: deploy with `railway up --ci --service web` from this Windows VM (logged in and linked), then push master. Checkouts are LF (.gitattributes) so the upload matches git; Cloudflare caches unversioned asset URLs, so check a live file with `?q=<random>`.
- The phone app is now the plan of the day: Today = the day view on today (F-092), an hour grid you edit by touch (F-097/F-098 move, resize with zoom, hold menu; F-101 hold empty time to make a plan), bookings open in place with SOS and filters (F-093), three tabs Today · Ask · Family with glass (F-096), smooth page and level changes with prefetch (F-099), a docked chat box (F-100), Ask hears you through Sarvam AI in any Indian language with English plans (F-102), a small Day | Week switch and a folding top (F-103).
- Briefs: docs/briefs/day-plan.md, docs/briefs/touch-day.md (approved by the captain on the trip). Canvas doc: docs/trip-canvas.md (every F-090..F-103 section). AI: docs/ai-usage.md (jobs, Sarvam's 30 s limit, providers).
- To try on the captain's iPhone (headless tests can't): Ask recording in the Home Screen app, the keyboard opening when a new plan is made, the chat box with the keyboard up, the resize zoom and hold timing, F-099's iPhone check.
- Parked: F-095 Around you (maps/coffee) by the captain; F-077 Forget a person safely. Open: F-089 one Windows-only browser test (passes gate swipe).
- Not reachable on the new screens yet (captain to decide): Share this day, the Notes tab, the scheduled-Uber list.
- The captain's bar (docs/lessons.md 2026-10-05): touch-first, minimal, smooth, never a form where a finger will do.
