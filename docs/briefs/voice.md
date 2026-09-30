# Feature brief: talk to plan (voice in the trip calendar)

Status: approved

## Why
- Adding activities one by one is slow and joyless. Saying the plan out loud is how families actually plan ("tacos Friday night, observatory Sunday at sunset, keep Monday free").

## Who and when
- The traveler on the trip calendar right after booking, often with family around, wanting to fill the gaps quickly.

## What it does (v1, demo)
1. A friendly mic button on the calendar. Tapping it plays a **fully scripted** demo sentence that appears word by word, as if heard live, with a listening animation. No real audio is captured and nothing leaves the browser.
2. The sentence becomes **draft plans shown in the calendar as a preview** (the same "preview, uncheck, then drop in" pattern as applying a fork), placed around the bookings and friends' items.
3. When something is unclear, **one quick question chip** appears ("Friday the 16th or Saturday the 17th?", "Dinner at 6:30?"). One tap answers it and the preview updates. Then Apply adds everything with the pop-in animation.
- Out of scope for now: real speech-to-text, AI understanding, voice in the booking workspace, other languages. Those are the next step once the flow feels right.

## Look and feel
- The GitAway system: a big tactile mic button, a soft pulsing "listening" ring, the transcript typed out in a speech bubble, and draft plans as dashed ghost blocks that turn solid when applied. Reduced motion: no pulse, and the text appears at once.

## Done means
- On the sample trip, tap the mic, watch the sentence appear, answer one question, see 3–4 plans previewed in the right slots, apply them, and the calendar and trip notes update. The captain signs it off by feel.

## Decisions and trade-offs
- The calendar comes first. Pro: that's where one-by-one entry hurts most. Con: booking by voice waits.
- Fully scripted. Pro: works everywhere, with no keys or privacy questions. Con: it's a demo; people can't try their own words yet.
- Ask one quick question when a request is unclear. Pro: no silent wrong guesses. Con: one extra tap.
- Voice never writes straight to the calendar; it always goes through a preview. Pro: trust, and it reuses the fork-apply pattern. Con: one confirm step.

## Open questions
- (deferred) Real transcription and AI understanding: which provider, and when.
