# Brief: the mobile trip companion

Status: approved (captain, 2026-10-03: "I love it… make it happen in the mobile view… I want it tomorrow")
Design: docs/design/canvas/Mobile-Storyboards-v1.html (https://claude.ai/artifact/PdpT9PSRGUAT7tpDjMyUBm)

## Why
During the trip (Oct 4–10, 2026, with Disneyland days) the captain won't open a laptop. The phone app must carry the day: what's next and when to leave, the map, what's around, help, the family's thread and photos, and changing the plan by voice.

## What (in build order)
1. Phone shell with a bottom tab bar (Today, Map, Ask, Family, Help) and Today as in frame 3: the dark "Up next" card with a leave-by countdown, Directions and Uber, the day as tinted cards, the hotel tonight, a small route strip.
2. Map: the day's stops numbered in order on a real map, a bottom sheet per stop (address, Directions, Uber, call).
3. Help: tonight's hotel (address, front desk call, check-in/out, confirmation behind a tap, Directions), emergency (911, family contacts, the car rental's number), readable offline.
4. Family: one thread per trip with messages, plan-change cards and photos; everyone gets a push on plan changes and new messages.
5. Photos: take or pick a photo, it lands on the plan/stop it was taken at, a strip per day.
6. Ask by voice: say what you need; GitAway proposes a change to the day; nothing changes until Apply; Apply tells the family.
7. Around you: food (vegetarian preference from the family profile), coffee, groceries, Costco/Walmart, pharmacy, gas, restrooms, with Directions, Call, Add to plan.
8. Face ID sign-in (passkeys).

## Choices
- A web app on the Home Screen (no App Store app now).
- Maps without paid keys: OpenStreetMap tiles and geocoding, public routing for drive times, Apple/Google Maps links for directions, Uber deep links.
- The assistant and nearby search use one Gemini API key (free tier from Google AI Studio) with Google Search/Maps grounding, instead of paid Google Places/Directions keys. Claude or OpenAI can replace it later.
- Location only while the app is open, and only sent for the search asked for.

## Not now
Background location alerts, lock-screen countdowns, booking, community.
