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

## F-011 GitAway visual direction and first artboards [todo]
Brief: docs/brief.md · Design: docs/design/ (to write) · Needs: none
- [ ] brand: GitAway wordmark, color palette, type, radius, shadow and motion tokens (Airbnb-playful, Apple-polished, joyful, trustworthy, alive)
- [ ] polished artboard of the scrapbook itinerary page (the hero screen), in at least two color themes
- [ ] rough artboard of the booking workspace, to test whether the dense panes feel joyful rather than crowded
- [ ] navigation map of the whole journey (landing → workspace → pay → calendar → share → community → creator import)
- [ ] captain signs off on direction before any build ticket starts

## F-012 Clean app shell, fake trip catalog and GitAway rename [todo]
Design: F-011 · Needs: F-011, captain decision on parking the old uncommitted frontend
- [ ] new frontend shell with the F-011 tokens and navigation; old TravelOS prototype routes are no longer linked
- [ ] one fake catalog: SFO → LAX/BUR, made-up dates, airlines, flights, hotels, cars and prices that look real
- [ ] user-facing name reads GitAway everywhere; README run instructions work
- [ ] project runs through pixi

## F-013 Landing page with split hero [todo]
Design: F-011 · Needs: F-012
- [ ] cover page explains what makes GitAway different, with delightful motion
- [ ] two doors: "Plan a trip" opens the booking workspace; "Get inspired" opens the community hub

## F-014 Scrapbook itinerary page [todo]
Design: F-011 · Needs: F-012
- [ ] day-by-day scrapbook layout: photo tiles, sticker tags (kid, pet, couple friendly), route squiggles, source card for the creator
- [ ] one layout, switchable color themes
- [ ] Fork button (asks for demo sign-in if signed out) adds the plan to the traveler's forks list

## F-015 Booking workspace: flight, hotel and car lanes with cost ledger [todo]
Design: F-011 (polished workspace pass first) · Needs: F-012
- [ ] tmux-style tiled panes you can resize and focus, with keyboard shortcuts, in a bright rounded look
- [ ] flights, hotels and cars side by side; picking one in each lane updates the cost ledger on top
- [ ] ledger highlights the best-value combination
- [ ] phone width: panes stack, ledger stays pinned

## F-016 Workspace context panes [todo]
Needs: F-015 · First to be trimmed to light stubs if time runs short
- [ ] weather, news, map, events and community itineraries for LA on the trip dates
- [ ] community itinerary pane can fork into the forks list

## F-017 Demo sign-in at save, pay, invite and fork [todo]
Needs: F-012
- [ ] everything is browsable signed out; save, pay, invite or fork shows a friendly demo sign-in, then continues the action

## F-018 One-tap pay and celebration [todo]
Needs: F-015, F-017
- [ ] Apple Pay-style sheet (clearly simulated) for the selected combination
- [ ] "You're going to LA!" celebration flows into the trip calendar

## F-019 Trip calendar [todo]
Needs: F-018
- [ ] Google-Calendar-like view with flight, check-in and check-out blocks pre-filled from the booking
- [ ] gaps stay blank; add, move and resize activities in a fun way; notes on any item

## F-020 Invite and simulated live friends [todo]
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

## F-023 Creator link import [todo]
Needs: F-014, F-022
- [ ] paste a YouTube or Instagram link → skeleton with a fade → an AI-drafted (fake) scrapbook itinerary with the creator's source card
- [ ] edit, then submit; it appears in the community hub and links back to the creator's channel
