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

## F-017 Demo sign-in at save, pay, invite and fork [done]
Design: approved 2026-09-30 (docs/design/canvas/Checkout.dc.html)
Needs: F-012
- [x] everything is browsable signed out; the demo sign-in accepts save, pay, invite or fork and continues to a safe local `next` (pay and fork are wired here; invite is wired in F-020, save in F-021)
- [x] after sign-in with intent=fork, the trip lands in the traveler's forks list; `next` only accepts local paths (no open redirect)

## F-018 One-tap pay and celebration [done]
Design: approved 2026-09-30 (docs/design/canvas/Checkout.dc.html)
Needs: F-015, F-017
- [x] Apple Pay-style sheet (clearly simulated) for the selected combination; when signed in, Book skips sign-in and opens the sheet directly
- [x] "You're going to LA!" celebration flows into the trip calendar

## F-019 Trip calendar [done]
Design: docs/design/calendar.md (approved 2026-09-30; artboard docs/design/canvas/Calendar.dc.html)
Needs: F-018
- [x] Google-Calendar-like view with flight, check-in and check-out blocks pre-filled from the booking
- [x] long trips (e.g. 20 days) stay readable: a whole-trip day strip on top, a window of days that fits the screen (5 desktop, 3 tablet, 1 phone) scrolling sideways, and a compact whole-trip view
- [x] gaps stay blank; add, move and resize activities in a fun way; notes on any item

## F-020 Invite and simulated live friends [done]
Design: docs/design/calendar.md (approved 2026-09-30; artboard docs/design/canvas/Calendar.dc.html)
Needs: F-019
- [x] invite a family member or friend (signed out: through the demo sign-in with intent=invite); their avatar appears
- [x] a scripted friend adds an activity and a note live, with animation

## F-021 Forks list and apply preview [done]
Captain said go 2026-09-30 ("do the missing sections, I want to see it fully").
Design: docs/design/canvas/Forks.dc.html
Needs: F-014, F-019
- [x] personal forks list in the workspace; fork any number
- [x] the itinerary page's Save heart saves a trip (signed out: through the demo sign-in with intent=save) and saved trips show beside forks
- [x] apply one: preview its activities in the empty calendar slots around bookings and friends' items, uncheck the unwanted ones, apply with animation; clashes are clearly shown

## F-022 Share to the community hub [done]
Captain said go 2026-09-30 (build the hub, then the creator flow).
Design: docs/design/canvas/Hub.dc.html
Needs: F-014, F-019
- [x] one tap on Share turns the trip into a scrapbook itinerary page (no private notes or payment info)
- [x] community hub lists shared and creator itineraries, filterable by kid, pet and couple friendly
- [x] user-written itinerary text stays escaped and source links only allow http(s)

## F-023 Creator link import [done]
Captain said go 2026-09-30. The creator is the editor: under 5 minutes from paste to submit, or creators won't bother.
Design: docs/design/canvas/Creator.dc.html
Needs: F-014, F-022
- [x] paste a YouTube or Instagram link → skeleton with a fade → a (simulated) transcript-drafted scrapbook itinerary with the creator's source card
- [x] a few quick clarifying questions as chips (which days, who it suits, best season) instead of trusting the transcript blindly
- [x] only 4–5 editable spots, artistically placed (title, day highlights, a tip, cover photo pick); everything else is laid out for them
- [x] the creator confirms it's accurate and gives permission to publish before Submit
- [x] submit; it appears in the community hub and links back to the creator's channel; the whole flow fits in under 5 minutes

## F-024 Talk to plan: scripted voice fills the calendar [done]
Captain said go 2026-09-30 ("do the missing sections, I want to see it fully").
Brief: docs/briefs/voice.md (approved 2026-09-30) · Design: docs/design/canvas/Voice.dc.html · Needs: F-019, F-021 (reuses the apply-preview)
- [x] mic on the trip calendar plays a scripted sentence word by word with a listening animation; no audio captured
- [x] the sentence becomes 3–4 draft plans previewed in the right empty slots around bookings and friends' items
- [x] one quick question chip resolves an unclear bit (which Friday, what time) and updates the preview
- [x] Apply drops them in with the pop-in, and trip notes log it; reduced motion shows everything instantly

# Flight and stay details

Brief: docs/briefs/offer-details.md (approved 2026-09-30). Same fake-data rules as above.

## F-025 Split view: expand Flights or Stays into list + detail [done]
Design: docs/design/offer-details.md (layout A approved 2026-09-30; canvas https://claude.ai/artifact/N9nH46TYpma8kyxU6Bad8o) · Needs: F-015
- [x] expanding the Flights or Stays pane (button, or its key then Enter) morphs it into a list sidebar plus a detail panel; the picked offer (or the first) opens by default
- [x] Esc or the collapse button morphs back to the tiled workspace; reduced motion swaps instantly; focus lands sensibly both ways
- [x] detail shows what the catalog already knows (name, headline, detail, rating, tags, area photo labelled as the area); Choose makes it the lane's pick and the ledger updates
- [x] phone: list and detail are two screens with a back button; no sideways scroll at 1440/1280/1000/800/390/320

## F-026 Stay detail: sample photos, room types and add-ons [done]
Design: docs/design/offer-details.md · Needs: F-025
- [x] "Explore the area in 3D" tab loads only when opened: tilted illustrated map, pins with walking times, tapping a pin flies to it; a nearby-walks strip shows when closed
- [x] each hotel has a credited CC0 sample-photo gallery (always labelled "sample photo"), highlights and a cancellation policy
- [x] room types (e.g. City-view King, Ocean-view King, Family suite) with price, occupancy, beds and view; pick a room and a count (Ocean-view King ×2 for 4 people)
- [x] add-ons toggle on and off: breakfast, late checkout, parking
- [x] the pick URL carries room, count and add-ons; the ledger, pay sheet and calendar itemize them, computed by the catalog (the page never does arithmetic); a bad or missing room falls back to the default
- [x] sample trip: The Tidewater, Ocean-view King ×2 + breakfast gives the right total through pay and calendar

## F-027 Flight detail: legs, fare types and checked bags [done]
Design: docs/design/offer-details.md · Needs: F-026 (shares the pick URL and itemized ledger)
- [x] out and back legs with times, duration, stops and aircraft
- [x] fare types (Basic, Main, Extra legroom) with price and what each includes (seat choice, carry-on, checked bag, changes)
- [x] checked-bag count as an add-on; fare and bags carry through the URL, ledger, pay and calendar like stays

## F-028 Phone: expanding a non-offer pane hides the context panes [done]
Needs: F-025 · Found during F-025 (predates it)
- [x] on a phone, expanding Cars or a context pane shows only that pane; the other context panes no longer show underneath (a same-specificity clash between the base and phone rules)

## F-029 Browser smoke test for workspace JS [done]
Needs: F-025 · Suggested in F-025 review
- [x] a small headless-browser test covers tiled pick → expand, Choose updating the ledger, Esc, and phone back → reload
- [x] also covers F-026: picking another stay tiled resets the old panel; Choose is held while a room edit waits for its price and recovers if the price fails

# Captain's feedback round, 2026-09-30

## F-030 Compact size: the whole site at about 75% of today [done]
Captain: at 100% zoom everything is extra large and spacey; a full screen only fits at 75% zoom. Applies everywhere (landing, workspace, calendar, pay, itinerary).
Needs: none
- [x] type, spacing, radii, buttons, cards and panes scale to about 75% of today on desktop and tablet, so a 1440×900 and a 1280×800 laptop show the whole workspace and the whole landing hero without scrolling
- [x] layouts that fit the viewport (workspace, calendar) still fit; no sideways scroll at 1440/1280/1000/800/390/320; no ellipses
- [x] phone stays readable: body text no smaller than 13px (DESIGN-SYSTEM minimum), touch targets at least 44px
- [x] DESIGN-SYSTEM.md and tokens updated to the new scale, so new screens are built at it

## F-031 Workspace: the cost ledger becomes a slim line at the top [done]
Captain (said twice): the ledger bar takes too much room. Push it to the top as subtle information so the panes and the details get the space; like Safari's bar or a Dynamic Island.
Needs: F-030
- [x] the ledger moves into the top bar as one slim line beside the trip and dates (flight · stay · car = total, plus Book); the old ledger band is gone and the panes take its height
- [x] tapping the total opens a small breakdown popover (itemized lines, the best-value hint); Esc or tapping outside closes it
- [x] in the split view, scrolling down the detail shrinks the line further to a pill (total + Book); scrolling up or tapping it restores it; animated, reduced motion instant
- [x] the total stays live; phone uses the same pattern pinned at the top

## F-032 Calendar opens on the whole-trip view [done]
Captain: the hour grid is intimidating first; the whole-trip snapshot should be the default, with an easy switch to the day view for editing.
Needs: none
- [x] /calendar opens on the whole-trip view; the switch to the day view is obvious and remembered while the traveler is on the page
- [x] links that need the day view (e.g. after adding an activity) still land there

## F-033 Book any mix of lanes, with rides when there's no car [done]
Brief: docs/briefs/optional-lanes.md (approved 2026-09-30)
Needs: F-027 (shares the pick URL and ledger)
- [x] each lane has a skip choice ("I'll drive", "Staying with friends", "No car") that collapses it and can be undone
- [x] ledger, pay and calendar work for any mix (at least one lane), with no empty or $0 lines
- [x] no car → "Uber and Lyft from LAX/BUR" card with sample fares and times; estimate added to the total as a labelled estimate, not charged on pay
- [x] skips live in the URL; done means: skip car, then flight, books stay-only through pay and calendar; undoing both gives $3,088
- [ ] (later) note for later: research Uber/Lyft partner APIs for scheduling a ride in the app

Later (not built): research Uber and Lyft partner API access for scheduling a ride from the app. The rides card is sample data only; nothing books or charges.

## F-034 Phone text floor and leftover ellipses [done]
Found during F-030 (both predate it).
- [x] on phones (390, 320) no text renders below 13px on /plan, /calendar (incl. ?demo=long) and the landing page; touch targets at least 44px
- [x] remove the four leftover `text-overflow: ellipsis` rules (landing `.field input` and `.paste`, workspace `.ws-slot-name`) in favour of wrapping or shortening (docs/lessons.md)

## F-035 "Where to?" trip start after sign-in [done]
Brief: docs/briefs/trip-start.md (approved 2026-09-30) · Design: follows landing and workspace language, no artboard (captain wants the full journey now)
Needs: F-030
- [x] /start asks from, to (LA live; others "coming soon"), dates, adults and kids with ages; "Find my trip" opens the workspace for that trip
- [x] sign-in without a specific `next` lands on /start; landing's "Plan a trip" door and the header link go there; a returning traveler sees "Continue <trip>" above the form
- [x] nights and travelers drive prices in the catalog (stays and cars by night, flights by traveler, room fit by party size); the trip lives in the URL through reload, pay and calendar
- [x] done means: LA, Oct 16–20, 2 adults + kids 4 and 7 gives $3,088; 3 nights or 3 adults change prices consistently through pay and calendar

## F-036 Small polish found while building F-035 [done]
- [x] weather, news and events panes follow the trip's dates (today they're fixed to Oct 16–20)
- [x] at 1000 wide the stay card's "Pool" and "Pet friendly" tags are clipped; wrap them (docs/lessons.md)
- [x] the landing door and feature pop-in (`scale(1.06)`) briefly causes sideways scroll at 1000, 800 and 390; contain it

## F-037 Small follow-ups from the F-024 review [done]
- [x] after a voice or fork Apply, focus lands on the toast's Undo button for keyboard users
- [x] voice: don't move focus to the first chip if the traveler has already moved focus elsewhere
- [x] the calendar's opening "Booked!" note reads naturally for every lane mix (today: "Your flights and The Tidewater (…) and Breeze Rentals rental are on the calendar")

# Real app: rides simulation and backend (brief: docs/briefs/real-app.md, approved 2026-10-01 · ADR-0004)

## F-038 Milestone 1: schedule an Uber, simulated faithfully [done]
Research: docs/research/uber-api.md · Needs: F-033
- [x] with no car, the rides card offers "Schedule an Uber" for arrival (pickup = landing + buffer) and departure (leave in time for the flight)
- [x] the flow mirrors Uber's API: product choice with price and time estimates, confirm pickup and dropoff, scheduled, then a simulated status timeline (scheduled → driver assigned → arriving → on trip → completed) and cancel
- [x] labelled "Simulated: no real ride is booked"; scheduled rides show on the trip calendar
- [x] a `RideProvider` seam with a simulator implementation, so a real Uber client can replace it later

## F-039 Backend foundation: fh-saas host, families as tenants, sign-in [done]
Needs: none (ADR-0004)
- [x] fh-saas wired in main.py: SQLite host DB, `DB_TYPE=SQLITE`, data files under a configurable data folder, `configure_logging`
- [x] Google sign-in through fh-saas (`/login`, `/auth/callback`, `/logout`), enabled when the Google env keys are set; a dev sign-in only when `GITAWAY_DEV_LOGIN=1` and the request is from localhost, through the same session path
- [x] first sign-in creates the person's family tenant; public pages (landing, hub, trips, creators, /start, the demo workspace) stay browsable signed out
- [x] the demo sign-in (Ari, Sam) is replaced; tests use the dev sign-in; a setup doc lists the env vars and the Google console steps

## F-040 Trips, bookings and the calendar live in the family database [done]
Needs: F-039
- [x] a family's trips, bookings, activities, notes and rides are stored in its tenant DB and survive a server restart; the cookie holds only the sign-in
- [x] the demo booking flow (workspace → pay) creates a trip in the family DB; the calendar, voice, forks-apply and rides read and write it
- [x] a family can have several trips, with a trip switcher; the cookie budget code for these parts is retired

## F-041 Community space for shared and creator trips [done]
Needs: F-039
- [x] shared trips and creator trips are stored in a community DB everyone can browse; forks and saves are stored per family
- [x] a shared trip's page works for anyone, signed in or out, on any device

## F-042 Import a trip booked elsewhere [done]
Needs: F-040
- [x] docs/trip-template.md: a fill-in template (travelers, flight legs with airline, number, airports, local times and confirmation; hotel with address, dates, confirmation and room; optional car; notes)
- [x] /trips/import: paste the filled template (or fill a form) → preview → save; validation with friendly errors
- [x] imported flights, hotel and car show on the calendar like bookings, marked "Booked elsewhere", with confirmation numbers visible only to family members
- [ ] stretch: pasting an Expedia confirmation email pre-fills the template

## F-043 Invite family by Gmail [done]
Needs: F-040
- [x] the family owner invites an email as editor or viewer; the invite shows a link to copy (email sending later)
- [x] when that email signs in, they join the family and see its trips; viewers can't edit; members and roles are listed with remove
- [x] the calendar's avatars and "planning with you" use real members; the scripted Mom demo only runs on the demo trip

## F-044 Install on iPhone [done]
Needs: none
- [x] web app manifest, icons (192, 512, Apple touch), theme colour and Apple meta tags; "Add to Home Screen" opens full screen at /start or the current trip
- [x] safe areas and the phone layouts work in standalone mode; a minimal service worker caches the app shell and the last-viewed trip for flaky connections

## F-045 Keep the test suite fast [done]
`pixi run test` grew from ~40s to ~170s as every test now wipes every family database (tests/wipe.py).
- [x] wipe only the families a test touched (record tenant ids opened in a set that survives `forget_schema_cache`), skip per-tenant `ensure_schema` in the wipe
- [x] `pixi run test` back under ~60s with the same isolation guarantees (a test proving a family opened before a reset is still wiped)

## F-046 Fixes from the end-to-end check [done]
Found by the full real-app walkthrough on master (2026-10-01).
- [x] notes show who wrote them (the member's name and avatar; "You" only for the viewer's own), on every member's screen
- [x] the first "Booked!" note matches the trip's actual lanes after a Replace (no car → no car wording)
- [x] viewers don't see "Talk to plan" or live "Schedule an Uber" links (like the add links)
- [x] the forks page's "Your calendar" preview shows scheduled rides, and fork placement treats them as busy
- [x] public shared pages don't reveal when and where a family is away: no flight numbers, no calendar dates (Day 1…N instead), and the hotel as its area ("a hotel in Santa Monica"), not its name; the family still sees everything
- [x] the invite expiry reads "expires in 14 days" when brand new

## F-047 Tests pass in any order [done]
Found while reviewing F-045: run in reverse order, tests/test_family_storage.py::test_a_real_second_process_sees_the_same_trip fails (on master too; master had 209 order-dependent failures before F-045).
- [x] the suite passes in reverse and random order (add pytest-randomly or an equivalent via pixi and run it once in CI-style)

# Go live (brief: docs/briefs/go-live.md, approved 2026-10-01)

## F-048 Deploy to Railway [blocked]
Blocked: in Railway project "gitaway" set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the web service, and add https://web-production-2d117.up.railway.app/auth/callback as a redirect URI in the Google console; then say go.
Live: https://web-production-2d117.up.railway.app (deployed 2026-10-01; volume at /data; secret set)
Needs: none
- [x] the app builds and runs on Railway (pixi-based image), with all databases on a persistent volume (working directory on the volume), assets resolved from the code folder
- [x] production settings: session cookie https-only, `GITAWAY_DEV_LOGIN` never set, secret key from `GITAWAY_SECRET_KEY`, a health check route; docs/setup.md has a Railway section
- [x] a new Railway project "gitaway" with a volume and a public *.up.railway.app address
- [ ] a redeploy keeps a test family's data (needs Google sign-in to create one)
- [ ] Google sign-in works on the live address once the captain adds the keys

## F-049 Stay signed in about 30 days [done]
Needs: none
- [x] sign-in lasts about 30 days on a device, sliding with use (fh-saas `SessionConfig` / `create_session_middleware`), secure cookie in production
- [x] sign-out and removed members still end access immediately

## F-050 "Discover" becomes "Community trips" [doing]
Needs: none
- [ ] the hub is named "Community trips" everywhere (header, landing, links, page title); /discover keeps working and /community is the new path
- [ ] the page says plainly that these are trips shared by travelers and creators, with "Share yours" and "Turn a link into a trip" up front

## F-051 Themed date pickers and dropdowns [doing]
Design: approved 2026-10-01 (docs/design/canvas/GoLive-Pickers.dc.html) · Needs: none
- [ ] a GitAway date-range picker (rounded, tokens, keyboard and screen-reader accessible, phone-friendly) replaces browser date inputs on "Where to?" and every other date field
- [ ] dropdowns and number pickers (adults, kids' ages, roles, times) use a GitAway style; no browser-default widgets left

## F-052 A sign-in page that makes you want to travel [blocked]
Blocked: open https://claude.ai/artifact/4FeSUmETnJ26kLXdA4EYvN and pick (sign-in A or B; phone A or B; pickers as drawn) or say what to change.
Design: canvas first · Needs: none
- [ ] the boarding pass fills from context: after a search (from, to, dates), after a fork (the trip's route and days, no creator), or a generic pass when there is no context
- [ ] emotional, animated, fun travel sign-in (Google button and dev sign-in) per the approved artboard; fast, accessible, reduced motion calm

## F-053 Good when empty [doing]
Needs: none
- [ ] a new family's first screens offer: start a trip, import a booked trip, browse community trips; no blank calendar, forks, family or trip pages anywhere

## F-054 Phone-first trip view [doing]
Design: phone A approved 2026-10-01 (docs/design/canvas/GoLive-Phone-Today.dc.html); B rejected as bland · Needs: F-051
- [ ] on phones the trip opens on "Today": what's next, flight and hotel cards, a swipeable day list, add a plan in two taps, notes
- [ ] works installed to the Home Screen; all data and roles as on desktop

# Go live phase 1.5

## F-055 Guided trip builder [todo]
Needs: F-051
- [ ] a few friendly questions (where, when, who, flights, hotel, car) build the same trip as the template, with preview and save; no YAML

## F-056 Paste an Expedia confirmation email [blocked]
Blocked: forward or paste one real Expedia confirmation email (it can stay on your machine; I only need its layout).
- [ ] pasting an Expedia confirmation email pre-fills the trip for review (never saves directly)
