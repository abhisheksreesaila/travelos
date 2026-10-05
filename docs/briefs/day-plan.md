# Brief: the plan of the day (one day at a time, said out loud, talked about on the block)

Status: approved (captain, 2026-10-04, by voice note before sleeping on the LA trip: "I trust your design skills… pick all your recommendations as the best and go ahead and finish it and deploy it"). The designs below were chosen by Claude and not reviewed by the captain; he will judge them on the phone in the morning.

## Why
This trip (Oct 4–10, two theme parks, a kid, a pregnancy) lives or dies on logistics. On a phone nobody types: they talk or paste. Right now the family still needs WhatsApp to say "let's do Mario Kart after lunch", and the canvas shows bookings (flights, check-in at 3) as loudly as the family's own plans.

## What
1. **One day at a time.** The day view (`/trip/canvas?day=N`) is the plan of the day: a strip of the trip's dates across the top (tap one), flick left for the next day and right for the previous one, pinch to zoom out to the whole trip (and tap a day to zoom back in).
2. **Plans first, bookings in the background.** The family's plans (park days with their parts, meals, meet-ups) are the bright cards. Bookings that come with the trip (flights, hotel check-in and check-out, car pickup and return) are quiet grey lines in time order: the time, what it is, a tap for the details (address, phone, confirmation). Overlaps are fine: no one checks in at exactly 3:00.
3. **Say the plan.** Every day has one clear "Change this day" button (and an empty day a big "Say the plan for this day"). It opens Ask for that day: talk, type, or paste any length; GitAway asks quick questions only when it must (which day, what time, who an initial is), shows one preview, and Apply saves it and tells the family. Opened without a day, a pasted itinerary is spread across the trip's days. (This is F-087.)
4. **Talk on the block.** Any plan or part of a plan (e.g. Lunch 12–1 at Universal) can hold messages: text, a photo, or a voice note. The plan shows only a small indicator (a bubble with a count, a mic when there is a voice note); tapping it opens a chat for that plan, like WhatsApp: bubbles, voice notes that play in place, photos. Messages also appear in the Family thread, and the family gets a push.
5. **Morning.** The morning push says "Today's plan" with the first plans and opens the plan of the day for today.

## Choices (Claude's recommendations)
- Keep the canvas addresses and the Today tab; the day view is the itinerary, Today stays "what's next now". The push and Today's "Day plan" button open the day view.
- Block messages are family-thread items tied to a plan (and optionally a part), so one store, one push path, and the Family tab shows them too.
- Voice notes are recorded in the browser (MediaRecorder; mp4 on iPhone, webm elsewhere), at most 3 minutes, stored on the server's volume like photos, family only. No transcription yet.
- Swipe needs a mostly-horizontal flick of 60px+ that did not start as a held step (hold-to-drag stays).

## Not now
Transcribing voice notes, reactions and replies to a message, read receipts, offline sending.

## How we'll know
In the morning the captain opens the push, sees today's plan clearly, flicks between days, says a change and applies it, and leaves a voice note on lunch that the family can play.
