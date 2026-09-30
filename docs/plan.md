# Plan

<!-- Tickets, one per vertical slice (each independently shippable and testable).
Status is one of: todo, doing, review, done, blocked. Update it as work moves.
A blocked ticket gets a "Blocked:" line saying exactly what the person has to do.
Format:

## F-001 Tenant signup [done]
Brief: docs/brief.md · Design: docs/design/signup.md · Needs: none
- [x] a new visitor can create a tenant with an email and password
- [x] the tenant gets its own SQLite database
- [ ] a duplicate email shows a clear error

## F-002 Stripe billing [blocked]
Blocked: set STRIPE_SECRET_KEY in Railway, then say go.
- [ ] pricing page uses register_billing_routes
-->

# GitAway v1: design-first clickable journey (fake SFO → LA data)

Brief: docs/brief.md (approved). Frontend only: FastHTML serves the pages, plain JS for interactions, all data is fake. Numbering continues after the earlier F-001–F-010 prototype work in `.work/`, which is superseded.

## F-011 GitAway visual direction and first artboards [done]
Brief: docs/brief.md · Design: https://claude.ai/artifact/NvLT3Tjf4XUwPbyZ4m6d2Q · Handoff: docs/design/itinerary-page.md · System: design-system/DESIGN-SYSTEM.md · Needs: none
- [x] brand: GitAway wordmark, color palette, type, radius, shadow and motion tokens (Airbnb-playful, Apple-polished, joyful, trustworthy, alive)
- [x] polished artboard of the scrapbook itinerary page (the hero screen), in at least two color themes
- [x] rough artboard of the booking workspace, to test whether the dense panes feel joyful rather than crowded
- [x] navigation map of the whole journey (landing → workspace → pay → calendar → share → community → creator import)
- [x] captain signs off on direction before any build ticket starts

## F-012 Clean app shell, fake trip catalog and GitAway rename [done]
Design: design-system/DESIGN-SYSTEM.md, journey map on the F-011 canvas · Needs: F-011 (old frontend archived on branch archive/travelos-prototype)
- [x] new frontend shell with the F-011 tokens and navigation; old TravelOS prototype routes are no longer linked
- [x] one fake catalog: SFO → LAX/BUR, made-up dates, airlines, flights, hotels, cars and prices that look real
- [x] user-facing name reads GitAway everywhere; README run instructions work
- [x] project runs through pixi

## F-013 Landing page with split hero [done]
Design: docs/design/landing.md (Landing A, two doors; chosen 2026-09-29) · Needs: F-012
- [x] cover page explains what makes GitAway different, with delightful motion
- [x] two doors: "Plan a trip" opens the booking workspace; "Get inspired" opens the community hub

## F-014 Scrapbook itinerary page [done]
Design: docs/design/itinerary-page.md (option A + board) · Needs: F-012
- [x] day-by-day scrapbook layout: photo tiles, sticker tags (kid, pet, couple friendly), route squiggles, source card for the creator
- [x] one layout, switchable color themes
- [x] Fork button sends a signed-out viewer to the demo sign-in with intent=fork (adding to the forks list is F-017 + F-021)

## F-015 Booking workspace: flight, hotel and car lanes with cost ledger [done]
Design: docs/design/workspace.md (polished workspace; chosen 2026-09-29) · Needs: F-012
- [x] tmux-style tiled panes you can resize and focus, with keyboard shortcuts, in a bright rounded look
- [x] flights, hotels and cars side by side; picking one in each lane updates the cost ledger on top
- [x] ledger highlights the best-value combination
- [x] phone width: panes stack, ledger stays pinned

## F-016 Workspace context panes [done]
Needs: F-015 · First to be trimmed to light stubs if time runs short
- [x] weather, news, map, events and community itineraries for LA on the trip dates
- [ ] community itinerary pane can fork into the forks list (Fork link in place; the list itself lands with F-017 + F-021)

## F-017 Demo sign-in at save, pay, invite and fork [blocked]
Blocked: look at "Sign in → pay → celebrate" on the canvas (use its 1-2-3 switch) and say go or what to change.
Needs: F-012
- [ ] everything is browsable signed out; save, pay, invite or fork shows a friendly demo sign-in, then continues the action
- [ ] after sign-in with intent=fork, the trip lands in the traveler's forks list; `next` only accepts local paths (no open redirect)

## F-018 One-tap pay and celebration [blocked]
Blocked: same canvas board as F-017: approve the pay sheet and "You're going to LA!" moment.
Needs: F-015, F-017
- [ ] Apple Pay-style sheet (clearly simulated) for the selected combination
- [ ] "You're going to LA!" celebration flows into the trip calendar

## F-019 Trip calendar [blocked]
Blocked: look at "Trip calendar with live friends" on the canvas and say go or what to change.
Needs: F-018
- [ ] Google-Calendar-like view with flight, check-in and check-out blocks pre-filled from the booking
- [ ] gaps stay blank; add, move and resize activities in a fun way; notes on any item

## F-020 Invite and simulated live friends [blocked]
Blocked: same canvas board as F-019: approve the live-friend avatars, pop-in and notes feed.
Needs: F-019
- [ ] invite a family member or friend; their avatar appears
- [ ] a scripted friend adds an activity and a note live, with animation

## F-021 Forks list and apply preview [todo]
Needs: F-014, F-019
- [ ] personal forks list in the workspace; fork any number
- [ ] apply one: preview its activities in the empty calendar slots around bookings and friends' items, uncheck the unwanted ones, apply with animation; clashes are clearly shown

## F-022 Share to the community hub [todo]
Needs: F-014, F-019
- [ ] one tap on Share turns the trip into a scrapbook itinerary page (no private notes or payment info)
- [ ] community hub lists shared and creator itineraries, filterable by kid, pet and couple friendly
- [ ] user-written itinerary text stays escaped and source links only allow http(s)

## F-023 Creator link import [todo]
Needs: F-014, F-022
- [ ] paste a YouTube or Instagram link → skeleton with a fade → an AI-drafted (fake) scrapbook itinerary with the creator's source card
- [ ] edit, then submit; it appears in the community hub and links back to the creator's channel
