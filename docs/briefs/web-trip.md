# Brief: the web gets the same love (trip pages on a laptop)

Status: approved (captain, 2026-10-13: "yup approve")
Designs: docs/design/canvas/Web-Trip-v1.html, option A (captain, 2026-10-13) · Handoff: docs/design/web-trip.md

## Why
The phone app got all the care during the Oct 4–10 trip; the laptop version drifted. Today it is the phone layout stretched wide (an empty right third, titles wrapping to three lines in the week view), next to older pages in a different style with a different top bar, and nothing that links one to the other. The family uses GitAway at a laptop before the trip (planning) and during it (checking the day in the hotel), so the laptop has to feel like the same app. This also cleans up the pages the captain's itinerary lives on before it is published anonymously as the first community trip (the next brief).

## Who
The captain's family at a laptop (1440×900 and 1280×800 at 100% zoom): planning the days before they leave, and looking at today or tomorrow in the evening during the trip.

## What
1. **One top bar on every signed-in page**, with the trip front and centre (Trip, Family, Ask) in the phone app's look. The signed-out landing keeps its own header.
2. **Desktop day view: grid plus side panel.** The hour grid on the left; the tapped plan's card, its family chat, or Ask docked on the right instead of popping up over the day. Mouse and keyboard versions of the touch moves: drag to move and resize, click for the card, right-click or a ⋯ for rename/delete, Esc closes, arrow keys go between days.
3. **Desktop week view**: the whole trip readable at a glance, titles on one or two lines, a click opens that day.
4. **Family chat as a docked panel**, not a phone-sized screen (and no blank page when its address is opened directly).
5. **Family, trip details and Start restyled** to match.
6. **The old trip calendar is retired**: its address goes to the new day and week views; Invite lives in Family; the 8-button row and its separate notes panel go away (notes live on plans). (assumed: nothing there is still needed; checked before removal)

## Not now
Booking (placeholders stay as they are), Community trips and creators (next brief, including publishing a trip anonymously and the public read-only trip page), Share this day and the scheduled-Uber list (assumed: wait for the community brief).

## Look and feel
Same as the phone: calm, minimal, liquid (the shared motion tokens, one soft spring). Feels like Fantastical / Apple Calendar on a Mac. GitAway's own design system, not Terminal Ledger. Main content fits without scrolling at 1440×900 and 1280×800; sizes in rem; no labels cut off.

## How we'll know
The captain plans a day on the laptop (makes, moves and renames plans, reads and writes in the family chat, uses Ask) without opening the phone and without zooming the browser out, and every signed-in page reads as one app.

## Decisions and trade-offs
- Family first, public view later. Pro: a small, focused round. Con: what strangers see waits for the community brief.
- Grid plus a docked side panel for the desktop day view. Pro: uses the width and nothing covers the day. Con: the most new design work of the three options.
- Retire the old trip calendar. Pro: one app, nothing stitched together. Con: anything still used there has to move first.
- The phone app is unchanged by this work (assumed): desktop layouts start above the tablet breakpoint and the phone layout and tests stay as they are.

## Open questions
- (none; assumed items are marked)
