# Handoff (2026-10-04)

Where things stand for the next session.

- Live: https://gitaway.me (Railway "gitaway"/"web"). Master = what's live; GitHub origin is up to date. Railway does not deploy on push: deploy with `railway up --ci --service web` (the Windows VM is logged in and linked since 2026-10-05), then push master to GitHub.
- Done and live: the mobile companion (Today, Map, Family + photos, Help, morning push, Face ID), Paste & Convert, trip canvas with semantic zoom, touch moves and filters, Ask GitAway (voice/text proposals), Around you, Passes & documents, clean production, privacy and terms.
- Plans and status: docs/plan.md (tickets), docs/briefs/ (approved briefs: trip-week, mobile-companion, trip-canvas), designs in docs/design/canvas/ (Mobile-Storyboards-v1, Plan-Steps-v1, Trip-Canvas-v2).
- Shipped 2026-10-05 (live): F-090 plan of the day (dates on top, flick between days, bookings quiet, Change this day), F-091 talk on a plan (text, photo, voice notes), F-087 one Ask box (talk/type/paste, follow-ups, one preview, Apply). Not yet tried on a real iPhone, voice recording above all.
- Next ticket: F-077 Forget a person safely (the forget-person script is dry-run only until then). Open: F-089, one Windows-only browser test (passes swipe).
- The captain is on the trip (Oct 4–10, 2026) and will send live feedback; fix and deploy each item through the reviewer.
- After the trip: review what the AI did (`pixi run ai-report`, docs/ai-usage.md) and decide per job.
- Known trade-offs told to the captain: pinch on the canvas replaces page zoom there; Ask removals can't be undone; plans may overlap (Ask warns).
- All old agent worktrees were removed on 2026-10-04 (every one was merged and clean). The unused Sept 29 "Field Notes" redesign spec is kept on branch worktree-opus-redesign-spec.
