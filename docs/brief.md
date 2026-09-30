# Product brief: GitAway

Status: approved

## Why (the mission)
- Why this exists, in one sentence: Travel sites only sell tickets. TravelOS puts every piece of information side by side so a traveler books with confidence, then turns the trip into a reusable itinerary others can fork, making it the GitHub for travel plans.
- Why now, and why you: Creator itineraries are scattered across YouTube and Instagram and hard to reuse. AI can now turn a video or post into a structured itinerary.
- If it disappeared tomorrow, who would miss it and what would they do instead? Travelers would go back to juggling Expedia, weather apps, news tabs, spreadsheets and group chats, and to hunting through YouTube for itineraries.

## Who it's for
- The one person it's for first, in one line: A traveler booking a trip with family or friends (sample: San Francisco to Los Angeles).
- The moment they reach for it (their trigger): Either "we're going to LA" (ready to book) or "I saw a great LA vlog" (inspired). The landing page has a split hero with two doors: plan a trip, and get inspired.
- What they use today, and what's wrong with it: Expedia, Skyscanner and Google Flights show one thing at a time (flights or hotels), with no weather, news or combined cost, and they feel transactional and joyless.

## What it does
- The core job, as one verb phrase: Plan, book and share a trip with all the information on one screen.
- What v1 does:
  1. **Booking workspace** in a tmux layout: flights, hotels and car rental side by side. A cost ledger on top shows the best combination, with weather, news, map, events and community-itinerary panes around it. Then a one-tap Apple Pay-style sheet, and a "You're going to LA!" celebration.
  2. **Trip calendar** (like Google Calendar): bookings are pre-filled as flight, check-in and check-out blocks, and the gaps stay blank to fill in. Invited friends (simulated, live) add activities and notes. Forked itineraries sit in a personal list; applying one previews its activities dropped into the empty slots, the traveler unchecks what they don't want, then applies.
  3. **Artistic itinerary page and community hub**: one tap on Share makes a scrapbook-journal page (day-by-day photo tiles, sticker tags for kid, pet and couple friendly, route squiggles, source card, one layout with color themes). Others find it and fork it. Creators paste a YouTube or Instagram link, a skeleton fades into an AI-drafted itinerary, they edit and submit.
- What it deliberately does not do (out of scope): No real backend, providers, payment, AI or identity in this phase. Everything is realistic fake data (made-up flights, hotels, prices). Sign-in is a demo prompt at save, pay, invite or fork. No bill splitting. The current uncommitted frontend (Compass, Snap, Fieldwork, A/B/C) is scrapped; only its concepts carry over.

## How it should look and feel
- Three words for how it should feel: Joyful, trustworthy, alive.
- Apps or sites it should feel like, and what to borrow from each: Airbnb's playful release (3D and tactile icons, soft shadows, warm imagery), colorful enough for a kid's site, polished like Apple. Not Expedia, Skyscanner or Google Flights. tmux supplies the layout only.
- House style (Terminal Ledger) or explore a new direction? Explore a new direction. The workspace has tiled, resizable, focusable panes with keyboard shortcuts, but it's bright and rounded, with no terminal look.
- The one screen that matters most, and what someone does on it: The artistic itinerary page, where someone reads a trip at a glance and forks it.
- Desktop first. On phones, panes stack and the cost ledger stays pinned. Small emotional animations throughout.

## How we'll know it worked
- The behaviour or number that says it's working: Your gut sign-off that every screen is delightful.
- What "done" means for v1: The full journey is clickable in the real app at localhost on fake data with real animations: landing, booking, pay, celebration, calendar, invite and live friends, forks list and apply, share, community hub, creator import.

## Constraints and risks
- Money, time, data, tenancy, compliance, anything else that limits us: Frontend and design only. The backend (fh-saas, SQLite per tenant) comes later. Revenue will come from affiliate booking links later.
- The riskiest assumption, and the cheapest way to test it: That a dense side-by-side workspace can feel joyful rather than overwhelming. Do a rough workspace artboard in the very first design pass, alongside the itinerary page.

## Decisions and trade-offs
- Design before the backend. Pro: nail the feel and the navigation first. Con: the data shapes get reworked later.
- tmux layout with a joyful look. Pro: side-by-side comparison that feels playful. Con: loses the obvious "dev tool" GitHub look.
- Desktop first. Pro: room for panes. Con: phones get a stacked, simpler workspace.
- Polish the itinerary page first. Pro: the most emotional, shareable screen. Con: the workspace is polished second (it gets a rough early artboard).
- Split-hero landing. Pro: serves both triggers. Con: two calls to action dilute the first impression.
- Sign-in at save, pay, invite or fork. Pro: the fun comes before any friction. Con: the traveler is anonymous until then.
- Booking is the start of the journey (ADR-0003, which revises ADR-0002). Pro: matches how trips start. Con: plans are no longer the first thing a traveler sees.
- Forks go to a personal list and are applied into calendar gaps. Pro: collect many, merge one without wiping friends' additions. Con: needs a clear visual for clashing times.
- Simulated live friends. Pro: visible joy. Con: scripted, so it can feel staged.
- If time runs short, the extra panes (car rental, events, news) become light stubs first.
- One layout with color themes for itineraries. Pro: consistent polish. Con: less self-expression.
- The product is named GitAway (git + getaway). Pro: joyful first, with a GitHub-for-travel wink. Con: the code, routes and docs still say TravelOS until the rename ticket.

## Open questions
- (deferred) More workspace panes: brainstorm in the next design phase.

