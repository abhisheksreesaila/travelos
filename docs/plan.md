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

## F-048 Deploy to Railway [done]
Live: https://gitaway.me (was https://web-production-2d117.up.railway.app, which now forwards) (deployed 2026-10-01; volume at /data; secret set)
Needs: none
- [x] the app builds and runs on Railway (pixi-based image), with all databases on a persistent volume (working directory on the volume), assets resolved from the code folder
- [x] production settings: session cookie https-only, `GITAWAY_DEV_LOGIN` never set, secret key from `GITAWAY_SECRET_KEY`, a health check route; docs/setup.md has a Railway section
- [x] a new Railway project "gitaway" with a volume and a public *.up.railway.app address
- [x] a redeploy keeps a family's data (captain confirmed their trip survived the 2026-10-03 deploys)
- [x] Google sign-in works on the live address (captain signed in 2026-10-02; keys set with oauth-setup)

## F-049 Stay signed in about 30 days [done]
Needs: none
- [x] sign-in lasts about 30 days on a device, sliding with use (fh-saas `SessionConfig` / `create_session_middleware`), secure cookie in production
- [x] sign-out and removed members still end access immediately

## F-050 "Discover" becomes "Community trips" [done]
Needs: none
- [x] the hub is named "Community trips" everywhere (header, landing, links, page title); /discover keeps working and /community is the new path
- [x] the page says plainly that these are trips shared by travelers and creators, with "Share yours" and "Turn a link into a trip" up front

## F-051 Themed date pickers and dropdowns [done]
Design: approved 2026-10-01 (docs/design/canvas/GoLive-Pickers.dc.html) · Needs: none
- [x] a GitAway date-range picker (rounded, tokens, keyboard and screen-reader accessible, phone-friendly) replaces browser date inputs on "Where to?" and every other date field
- [x] dropdowns and number pickers (adults, kids' ages, roles, times) use a GitAway style; no browser-default widgets left

## F-052 A sign-in page that makes you want to travel [done]
Design: sign-in A (boarding pass) chosen 2026-10-01 as recommended; captain said "go ahead and do what you have to do" and will review locally (docs/design/canvas/GoLive-SignIn-A.dc.html) · Needs: none
- [x] the boarding pass fills from context: after a search (from, to, dates), after a fork (the trip's route and days, no creator), or a generic pass when there is no context
- [x] emotional, animated, fun travel sign-in (Google button and dev sign-in) per the approved artboard; fast, accessible, reduced motion calm

## F-053 Good when empty [done]
Needs: none
- [x] a new family's first screens offer: start a trip, import a booked trip, browse community trips; no blank calendar, forks, family or trip pages anywhere

## F-054 Phone-first trip view [done]
Design: phone A approved 2026-10-01 (docs/design/canvas/GoLive-Phone-Today.dc.html); B rejected as bland · Needs: F-051
- [x] on phones the trip opens on "Today": what's next, flight and hotel cards, a swipeable day list, add a plan in two taps, notes
- [x] works installed to the Home Screen; all data and roles as on desktop

# Go live phase 1.5

## F-055 Guided trip builder [done]
Needs: F-051
- [x] a few friendly questions (where, when, who, flights, hotel, car) build the same trip as the template, with preview and save; no YAML

## F-056 Paste or upload an Expedia itinerary [done]
Layout: the captain's real Expedia itinerary PDF (car + three stays, 2026-10-01), kept off the repo; tests use a made-up copy of the same layout. More real samples coming from the captain. · Needs: none
- [x] on /trips/import, pasting the text of an Expedia itinerary (or uploading its PDF) fills the trip for review, never saving directly; it becomes the same template text, so preview, "Change something" and save work as they do now
- [x] reads every "Stay in …" (hotel name, confirmation, check-in and check-out dates and times, address, room) and "Car rental in …" (company, confirmation, pick-up and drop-off place, date and time, car type); trip dates span all bookings; booked on Expedia
- [x] "Reserved for … N adults, M child" becomes placeholder travelers to rename (the named person first); confirmation numbers are kept exactly (a leading “#” dropped)
- [x] parts it can't read are named plainly in the preview (e.g. "We couldn't read the check-out time for Stay in Burbank"), and pasting something that isn't an Expedia itinerary still goes through the normal template reader
- [x] card digits, prices and Expedia's support text are never stored

## F-057 A trip has its own time zone [done]
Found reviewing F-054: "today" and "now" use Los Angeles time; a non-LA trip (e.g. an imported Paris trip) would be off by up to a day.
- [x] a trip has a time zone (from its arrival airport via an IATA → zone map, or chosen on import); /trip's today, up next and countdowns use it; the server's past-date check keeps one "today"

# Ready for the captain's trip (week of 2026-10-04)

## F-058 Import is easy to find, and "Change something" edits [done]
Captain, 2026-10-01: couldn't find Import a trip without the link; the Choose file button wasn't themed; "Change something" did nothing ("I should be able to edit"). · Needs: none
- [x] "Import a booked trip" is a visible button where people start trips (the Plan a trip page, the trips list/switcher and the calendar), on desktop and phone
- [x] the PDF picker is a GitAway-styled button (tokens, focus ring, shows the chosen file's name), no browser-default "Choose file" left
- [x] "Change something" on the import preview opens the trip in the guided builder, filled with everything previewed (travelers, flights, every hotel, car, notes, booked on, confirmations), so it can be edited and previewed again; editing as template text stays available as a secondary link
- [x] a browser test presses "Change something" and lands on an editable form with the previewed values

## F-059 Booked items are calm, colourful and clearly booked [done]
Captain, 2026-10-01: booked items are "all black", bold, and "Booked elsewhere · Expedia" is shouted on every line; wants subtle colours per kind, a plane icon for flights, a hotel icon with check-in/check-out times, keep the lock. · Needs: none
- [x] booked flights, hotel check-ins/check-outs and car pick-up/drop-off show as soft tinted blocks per kind (design-system tint/ink pairs), not solid black, on the calendar (whole trip and day views) and the phone Today view
- [x] each keeps its icon (plane, bed, car) and the lock, with readable contrast (WCAG AA)
- [x] "Booked elsewhere · Expedia" appears once, quietly (the trip header or the booking's detail), not as a bold label on every block

## F-060 Landing v2: one clear door, a page that tells the story [done]
Design: docs/design/landing-v2.md (approved 2026-10-02) · Needs: none
- [x] the landing header shows only the brand and Sign in; Community trips, For creators and Sign in move to the footer; other pages keep their header
- [x] "Fork a getaway." with the fork gloss; one wide primary "We're going. Let's book it." panel with Plan a trip; forking is one quiet line (option A) that leads to the Community trips section
- [x] the four feature tiles animate on hover and keyboard focus (once on scroll on touch screens), calm under reduced motion
- [x] the shared calendar plays four people filling three days in real time, loops, rests complete before it starts and under reduced motion
- [x] Community trips and creators sections as designed, creators copy about inspiring others, not followers; desktop and phone, no sideways scroll

## F-061 Edit a saved trip [done]
Captain, 2026-10-02: "it's good to have edit trip button… if the OCR makes mistakes, then you at least have the opportunity to fix it." · Needs: F-058
- [x] an "Edit trip" button on the trip's details page, the calendar's trip bar and the phone trip view opens the guided builder filled with the saved trip (travelers, flights, every hotel, car, notes, booked on, confirmations)
- [x] saving replaces the trip's bookings in place (same trip, no duplicate) and keeps everyone's plans, notes and rides, with scheduled rides moving to the new flight times and hotel as the import's replace already does; the preview says so before saving
- [x] only editors and admins see the button and can save; viewers never see it; a stale tab can't edit a different trip than the one it opened
- [x] a browser test presses Edit trip, changes a flight time and a hotel name, saves, and sees both on the calendar with an existing plan still there

# The captain's trip week (from 2026-10-03)

## F-062 Sign-out is instant [done]
Captain, 2026-10-02: "the sign out was very slow." Likely cause: the sign-out response sends `Clear-Site-Data: "cache", "storage"`, and browsers can take seconds to clear the HTTP cache. · Needs: none
- [x] signing out returns to the landing within about a second (headless Chromium ~0.1s; the slow HTTP-cache clear is gone; confirm on the captain's iPhone after deploy)
- [x] the next person on the device still can't see the previous family's pages or cached data (the service worker's caches are cleared, as F-049/F-041 required)

## F-063 Invite by sharing a link, not "email" [done]
Captain, 2026-10-02: "there's no email sender… Why is it saying send an email?" · Needs: none
- [x] the invite form says plainly that GitAway doesn't send email: you enter the Gmail address they'll sign in with, then share the link yourself
- [x] after inviting, a "Share invite" button opens the phone's share sheet (Messages, WhatsApp…) with a short message and the link; where sharing isn't available it copies the link and says "Copied"

## F-064 The live site shows only what's real [done]
Brief: docs/briefs/trip-week.md · Needs: none
- [x] in production (`auth.production()`), no sample trips or sample data appear anywhere: Community trips (page, landing section, fork line), creators pages, sample itineraries and their fork counts and names, the demo calendar and any "LA with the kids" sample; those routes 404 or redirect home, and no link points at them
- [x] the landing keeps its approved story without the community and creators parts; the booking workspace stays, labelled clearly as a preview with sample prices
- [x] a brand-new family's first screens and an empty trip look intentional (warm empty states), checked in screenshots at phone and desktop
- [x] the local copy (not production) still shows all sample data; tests cover both modes

## F-065 Today, laid out to read and share [done]
Brief: docs/briefs/trip-week.md · Needs: none
- [x] a "Today" view of the day's plan (time, what, where with a Directions link, notes, who added it, bookings with their lock and confirmation one tap away) reads cleanly on a phone; any day can be opened, today by default in the trip's time zone
- [x] a Share button sends a short plain-text summary of that day (times, plans, places, hotel tonight) through the phone's share sheet, or copies it; no prices, confirmation numbers or private notes in the shared text
- [x] every family member (viewer, editor, admin) sees it live; viewers can't edit from it

## F-066 Morning plan push [done]
Brief: docs/briefs/trip-week.md · Needs: F-065 for the page it opens
- [x] on the phone app (added to the Home Screen), "Morning plan" can be turned on with a time (default 7:30 AM, trip time zone); iPhone asks for permission once; it can be turned off
- [x] each trip morning at that time the person gets a push "Today: <first plans…>" that opens the Today view; nothing is sent on days outside the trip or when there's no trip
- [x] push keys come from environment variables (never in the repo); sending survives a redeploy (subscriptions in the family database); a failed or expired subscription is dropped quietly

# Mobile companion (brief docs/briefs/mobile-companion.md, design docs/design/canvas/Mobile-Storyboards-v1.html)

## F-067 Phone shell and Today v2 [done]
- [x] on phones every trip screen sits in one shell with a bottom tab bar (Today, Map, Ask in the raised centre, Family, Help) as in the storyboards; tabs not built yet show a short "coming" card; desktop keeps its layout
- [x] Today matches frame 3: dark "Up next" card with countdown and "Leave by" (when a drive time is known; otherwise no leave-by line), Directions and Uber (deep link with the destination filled in), the rest of the day as tinted cards (done items struck through), hotel tonight, a route strip of the day's stops
- [x] it keeps everything F-065/F-066 added (share, confirmation tap, who added it, morning plan card) and passes phone checks (no sideways scroll, 44px targets, 13px text floor)

## F-068 Map of the day [done]
- [x] places (hotels, plans with a place, airports, the car counter) get coordinates from OpenStreetMap geocoding, cached per family so each place is looked up once, at most one lookup per second, with a clear "couldn't find this place" state
- [x] the Map tab shows the day's stops numbered in order on an OpenStreetMap map with the route between them; tapping a stop opens a bottom sheet (address, time, Directions, Uber, call when a phone number is known)
- [x] drive times between consecutive stops come from a public routing service, cached; Today's "Leave by" uses them

## F-069 Help [done]
- [x] Help shows tonight's hotel (address, phone with a call button, check-in/out, confirmation behind a tap, Directions), the car rental (counter address, phone), 911, and the family's own phone numbers (each member can add theirs on the family page)
- [x] a hotel's or car's phone number can be added or fixed (Edit trip or right there); Help still opens offline on a phone that opened it before (only for the signed-in person)

## F-070 Family thread with notifications [done]
- [x] one thread per trip with messages, photos (taking and adding photos is F-071; the thread shows them) and automatic cards for plan changes (who added, moved or removed what); new items appear within seconds while open
- [x] everyone in the family with Morning plan notifications on also gets a push for plan changes and messages (not their own); a "Quiet" switch turns that off per person

## F-071 Photos on the plan [done]
- [x] take or pick photos in the app; each lands on the plan it was taken during (by time, then place if the photo carries a location), with a strip per day; only the family can see them, stored on the server's volume
- [x] a photo can be removed by whoever added it or an admin

## F-075 Leave by for a departure flight [done]
Found reviewing F-068: drives to and from airports are skipped, so a departure flight that is up next gets no "Leave by". · Needs: none
- [x] the drive from the stop before (or the hotel) to a departure airport is cached and Today shows "Leave by" for an up-next departure flight, with a margin before the flight (e.g. 2 hours domestic); no drive is ever asked between two airports
- [x] the arrival-day test checks 9:40 (after landing): Up next is the car pickup and no "min drive" line shows

## F-072 Ask by voice [done]
Azure OpenAI is set up (deployment gpt-5.6-sol, tested 2026-10-04; env AZURE_OPENAI_*). Known limit: a plan removed through Ask GitAway cannot be undone (the change list says so); the calendar's own Undo covers only its own delete button.
- [x] talk (or type) to ask for a change; GitAway proposes a new day (added, moved, removed plans) and changes nothing until Apply; Apply tells the family

## F-073 Around you [done]
Uses the same Azure OpenAI setup as F-072; nearby places come from OpenStreetMap and the model ranks and explains them.
- [x] quick chips (vegetarian food, coffee, groceries, Costco/Walmart, pharmacy, gas, restrooms) find places near you with distance, open now, Directions, Call and Add to plan; the family's food preference applies

## F-074 Face ID sign-in [done]
- [x] after Google sign-in once, a phone can add a passkey and later sign in with Face ID

## F-076 Privacy policy and terms pages [done]
Captain, 2026-10-03: Google won't publish the sign-in app until the Branding page has a home page, privacy policy and terms on an authorized domain. · Needs: none
- [x] /privacy and /terms are plain, readable pages in the house style saying truthfully what GitAway stores (Google name, email and picture; trips, plans, notes, messages, photos with their time and place, phone numbers, push subscriptions, passkeys), who sees it (only the family; nothing public), which outside services get what (Google sign-in, Railway hosting, OpenStreetMap place lookup and routing get place text only, Apple/Google push services, Gemini when the assistant is on), that nothing is sold or used for ads, and how to get data deleted (a contact address from a setting)
- [x] both are reachable signed out, linked from the footer and the sign-in page, and work on the live address

## F-077 Forget a person safely [todo]
Found reviewing F-076: `pixi run forget-person` (dry run by default) is not safe to run for real yet. · Needs: none
- [ ] `--family` also removes the person's own sign-in, and only deletes a family the person owns or is the only admin of (otherwise refuses, or the operator names the family id)
- [ ] refuses when more than one account has the email, listing them; photo and database paths are kept inside the data folder; audit rows matched exactly, not with LIKE; warns or refuses when the plain run would leave a family with no admin
- [ ] its tests build the family database through the app's own schema and write rows through the app's own code

## F-078 One address: gitaway.me [done]
Captain, 2026-10-04: bought gitaway.me; the site, Google sign-in and Face ID move there. · Needs: none
- [x] in production, a request to any other host (the old *.up.railway.app address) gets a permanent redirect to the same path and query on GITAWAY_PUBLIC_URL, except /healthz (Railway's check) and /auth/callback (a sign-in already under way finishes where it started)
- [x] locally and in tests nothing redirects; docs/setup.md says how to change the address

## F-079 Keep track of what the AI does [done]
Captain, 2026-10-04: Azure OpenAI is a stopgap for the trip; after a week we review which jobs it actually did (transcription, OCR, Convert, search, recommendations) and decide what to keep, swap for a cheaper model or classifier, or drop. · Needs: none
- [x] every AI call goes through one place (`gitaway/ai.py`) and is logged with: when, which job (e.g. convert, speak, ask, around-you, ocr), which family, model/deployment, tokens in and out, time taken, success or error; never the prompt text, answers or personal details
- [x] a short report (`pixi run ai-report`, and docs/ai-usage.md listing each job, what it replaces and why) shows counts, time and tokens per job and per day, so the captain can review after the trip
- [x] switching the model or provider for one job is one setting, not a code change

# Trip canvas (brief docs/briefs/trip-canvas.md, approved 2026-10-04)

## F-080 Paste & Convert [done]
Needs: F-079 (built together)
- [x] a block (calendar plan) can hold parts and steps (title, optional time, who, note, done, set aside) and a trip can hold named lists (e.g. Pregnancy-safe rides) and a Set aside tray; stored in family tables
- [x] "Add to the trip" takes pasted text (or dictation) and Convert, using the Azure model, returns park days → parts → steps with notes on their items, repeats merged, "skip" items set aside, lists made; then asks who each initial/name is (family members, someone new, or keep the initials) and which trip day each day is; nothing is saved until "Add to trip"
- [x] it works on the captain's real Universal Studios and California Adventure messages (a test fixture with that text), and a model failure or timeout leaves a clear message and the pasted text intact
- [x] adding writes one family-thread change card and notifies the family

Note: the block page (`/trip/block?id=aN`, with Mark done, Set aside and Put back) was built here as a simple stepping stone so the captain can see parts and steps today; F-081's canvas replaces it.

## F-081 The trip canvas with semantic zoom [done]
Needs: F-080
- [x] on phones the trip tab is one canvas: week → day → block → step; tapping or pinching zooms with a fluid animation where the summary grows into its detail and back (View Transitions where supported, calm under reduced motion)
- [x] notes show on their block or step; a Set aside tray per day; Mark done; parts show as lanes when people split up (Everyone / per person)
- [x] works on desktop too (wide day view)

## F-082 Touch moves and filters [done]
Needs: F-081
- [x] hold and drag a step to another time, part, day or the Set aside tray, with Undo; swipe for Done or Set aside
- [x] filter chips by who and by named lists (e.g. Pregnancy-safe) highlight matching steps and dim the rest

## F-083 Passes & documents [done]
Needs: none
- [x] in Help, per traveller: flight, seat, boarding group, gate, boarding time and an attached boarding pass (PDF or image), family only; editors add or fix them
- [x] on travel day the flight is Today's focal card with "Show everyone's passes": full-screen, bright, swipe between travellers

# Trip feedback, 2026-10-04 (captain, on the trip)

## F-084 Invite from the phone's Family tab [done]
Captain, 2026-10-04: couldn't find how to invite from the phone; the invite page (/family#invite) isn't linked from the Family tab. · Needs: none
- [x] for an admin, the phone Family tab (chat and photos) shows a clear "Invite" button that opens the invite form; non-admins see who is in the family (link to /family) instead
- [x] passes phone checks (44px target, 13px text floor, no sideways scroll); a test covers admin and editor views

## F-085 Today: notes start folded [done]
Captain, 2026-10-04: notes take too much room on Today; hide them, tap to read. · Needs: none
- [x] on Today (and the selected day's list), a plan's notes are folded by default behind a small "1 note" / "2 notes" tap that opens them in place; the up-next card does the same; nothing else on the card changes
- [x] works with keyboard and screen readers (a real button with aria-expanded, or details/summary), calm under reduced motion; a browser test opens a note

## F-086 Plans may overlap bookings and each other [done]
Captain, 2026-10-04: Add to trip refused a plan because it overlapped hotel check-out ("Pick a gap"). Overlapping is fine: families split up, and plans sit on top of check-out, flights and car pickups. · Needs: none
- [x] adding, editing or moving a plan (calendar form, Add to the trip, canvas moves, forks, voice) is never refused for overlapping a booking, a ride or another plan; the plan is saved and shows a small "overlaps <title>" tag on Today and the up-next card, and in the fork, voice and Ask previews (the desktop calendar grid shows overlapping plans side by side instead)
- [x] the other checks stay (inside the trip, end after start, minimum length); tests that expected an overlap refusal now expect the save and the tag

## F-087 One box: talk, type or paste a change or a whole itinerary [done]
Captain, 2026-10-04: Ask stops at 600 characters and one day; paste lives on separate screens; "simplify, it could be overwhelming". Keep paste: "sometimes we copy paste from the internet". Replaces the earlier "Paste for one day". · Needs: F-086
- [x] one Ask box (the raised centre tab, and Ask on a day) takes talking, typing or pasting of any length up to the paste limit (about 20,000 characters), with a visible Paste button; the separate Add to the trip screens fold into it (old links land in the box)
- [x] opened from a day, everything goes on that day; opened without a day, it reads the text and spreads it across the trip's days
- [x] it asks quick follow-ups only when needed (which day, what time, who an initial is), one tap each with a suggested answer; times written in the text are used as given
- [x] one preview, day by day, of what is added, moved or removed; one Apply saves it all in one go and tells the family once; overlaps are allowed (F-086); a model failure keeps the text
- [x] the captain's real Universal Studios and California Adventure messages (existing fixture) still convert into park days, parts and steps

## F-088 Face ID only where it is set up [done]
Captain, 2026-10-04: tapping Face ID on a phone without a GitAway passkey shows a QR code (iPhone offering another device), which a phone can't scan itself. Passkeys made before the move to gitaway.me don't work there. · Needs: none
- [x] the sign-in page shows the Face ID button only on a device that turned on Face ID for this address (remembered on the device after a successful setup or sign-in); everywhere else Google is the one button
- [x] if a Face ID attempt is cancelled or fails, the page says so plainly and points to Google; a test covers both cases

## F-089 Builds and tests on Windows [doing]
Captain, 2026-10-04: the project moved from Linux to a Windows VM; the build and pixi environment must work there. · Needs: none
- [x] `pixi install` solves for win-64 and `pixi run test` passes on Windows
- [x] the test suite runs at a normal speed on Windows (throwaway test databases skip the on-disk journal and fsync, which cost ~17 ms a write there)
- [ ] `pixi run test-browser` passes on Windows (354 of 356 on 2026-10-05; the passkey device name now follows the OS; left: `test_passes.py` travel-day swipe stops at 0.73 of the next slide in Windows headless Chromium, unchanged code, not seen on Linux)

# Plan of the day (brief docs/briefs/day-plan.md, approved 2026-10-04)

## F-090 One day at a time, plans first [done]
Needs: none
- [x] the day view (`/trip/canvas?day=N`) has a strip of the trip's dates at the top (the open day marked, today marked, each a tap); a mostly-horizontal flick of 60px or more goes to the next day (left) or the previous day (right) with a sideways slide (instant under reduced motion); a held step still drags; pinch out still goes to the whole trip
- [x] on the day, the family's plans are the bright cards; bookings (flights, check-in/out, car) are quiet grey lines in time order with their time and a tap to their details; a day with only bookings still reads as "nothing planned yet" with the bookings below
- [x] every day has a clear "Change this day" button (mic) for editors that opens Ask on that day, and an empty day a big "Say the plan for this day" with Talk and Paste; after Apply, "See the day" lands back on the day view
- [x] the morning push reads "Today's plan · <place>" and opens the day view for today; Today's heading has a "Day plan" button to it
- [x] phone checks at 390 and 320 (no sideways scroll, 44px targets, 13px text) and the laptop view still works; browser tests flick both ways, tap the strip, and press every new button

## F-091 Talk on the block: text, photos and voice notes on a plan [done]
Needs: none
- [x] any plan, and any part of a park day (e.g. Lunch), can hold messages: text, a photo, or a voice note recorded in the app (up to 3 minutes; mp4 on iPhone, webm elsewhere); stored in the family thread with the plan (and part) they belong to, files on the server's volume, family only
- [x] the plan (and the part) shows a small indicator only (a bubble with the count; a mic when there is a voice note); tapping it opens that plan's chat: bubbles (mine on the right), voice notes that play in place with their length, photos, who and when; a composer with text, photo and a tap-to-record mic (cancel and send)
- [x] each message also shows in the Family tab's thread, labelled with its plan, and the family gets a push (the existing thread push rules); viewers can post messages too, as in the thread
- [x] a voice note or photo that is too big, the wrong type or empty is refused with a plain message; tests cover the model, the routes (roles, another family's file is not served) and a browser test records (fake media), sends and plays


## F-092 Today is the day view [done]
Captain, 2026-10-05 (on the trip): Today is "very complicated… all I need to know is what I do today"; the day and week views already show today, so cut Today rather than add to it; one floating button to change the day. · Needs: F-090
- [x] the Today tab, the installed app's start page and "Back to Today" (plain `/trip`) open the day view on today during the trip (the first day before it, the last after); the old page stays only behind its query addresses
- [x] on today the day view starts with what is happening now or up next (Directions, Uber, leave-by), or on a flight day the flight with everyone's passes; other days have no such card
- [x] the centre Ask is the one way to change the day and opens on the day being looked at; the day and block lose their own Ask and "Change this day" buttons (an empty day keeps Say / Paste)
- [x] the week has no Today | Week | Day control or pinch hint and marks today; the morning plan switch and the Face ID card move to Help

## F-095 Around you finds places from the live server [blocked]
Blocked: parked by the captain, 2026-10-05 ("the maps and the coffees are not that big of a deal… skip that for now"). A first try asked public Overpass mirrors, but the two mirror names are one server that did not answer, so it was reverted. Pick this up after the itinerary work.
Captain, 2026-10-05: searched for coffee on the Map and nothing came up. Live logs: POST /trip/map/around answered 503 (Overpass refused or timed out from Railway; a refusal also shut the door for 10 minutes). · Needs: none
- [ ] when the main Overpass server refuses or is slow, the public mirrors are asked in turn within one 20-second budget, each with its own pacing and back-off; the privacy page names them
- [ ] a coffee search on the live site returns places (checked after deploy)

## F-093 Bookings open in place; filters; Help leaves the tab bar [done]
Captain, 2026-10-05: Help is not useful as its own tab; tap a hotel or flight on the itinerary for everything about it (passes too); a subtle filter (hotels, flights, chats…) instead of hunting for dates; fewer tabs, fewer clicks. · Needs: F-092
- [x] a booking line opens a sheet in place with all Help showed for it (hotel, flight with passes, car); the week's bookings too
- [x] a subtle filter row (All · Plans · Hotels · Flights · Car · Chats) on the week and the day
- [x] Help leaves the tab bar; an SOS sheet (911, hotel, rental counter, family phones) is always one tap away; the morning plan and Face ID cards keep a quiet home
- [x] phone checks and a browser test pressing every new button

## F-094 The family chat, lighter and instant [done]
Captain, 2026-10-05: keep the family chat, but the chat/photos switch must be small, and a sent bubble should appear at once and fade in so the delay is not felt. · Needs: none
- [x] a small, quiet chat/photos switch; a sent message shows at once (fading in), confirmed quietly, a failed one offers Retry without losing the text; poll items fade in; plan chats behave the same

## F-096 Three tabs and a touch of glass [done]
Captain, 2026-10-05: four tabs around a raised centre break the symmetry ("either three or five, you cannot have four"); "a sheet here and there can be a little translucent… a Liquid Glass effect". Claude's call: three tabs, glass only on what floats. · Needs: F-093
- [x] the tab bar is Today · Ask · Family with Ask in the true centre; Map becomes a small map button in the day heading (beside SOS) opening that day's map; `/trip/map` keeps working
- [x] the tab bar and the sheets (step, booking, SOS, add) are translucent with a strong blur (Liquid Glass feel) over a tinted base so text stays at full contrast; cards and text stay solid
- [x] `prefers-reduced-transparency: reduce` and browsers without backdrop-filter get solid surfaces; phone checks at 390 and 320; contrast checked on the sheets over the busiest day

# The day you edit with your finger (brief docs/briefs/touch-day.md, approved 2026-10-05)

## F-097 The day as a time grid; move and resize by touch [done]
Needs: F-090, F-092, F-093
- [x] on a phone the day view draws the family's plans as blocks on an hour grid sized by their length (overlaps side by side, bookings as the quiet background lines of F-090/F-093 at their times, today's now line); a blank day keeps Talk / Paste; the week, the filters, Day | Week, the flick between days and SOS keep working; a laptop gets the same grid wider
- [x] editors hold a block ~350 ms and drag to move it (15-minute snap, live time label, edge scroll), and hold its bottom edge and drag to change its length (min 15 minutes) while the grid zooms in around the finger (~2.5×, 5-minute snap while zoomed) and eases back on release; each change saves through the calendar's own rules and shows an Undo toast; viewers get no gestures
- [x] a plan Ask adds without a length gets 1 hour
- [x] browser tests (390 and 320) drive move, resize-with-zoom, Undo, a viewer, reduced motion; phone checks (no sideways scroll, 44px targets, 13px text)

## F-098 Hold menu, rename in place, delete [done]
Needs: F-097
- [x] hold and release a block without moving: it wiggles and a small menu offers Chat (opens its plan chat), Rename, Delete (asks once; Undo after), plus Earlier / Later / Shorter / Longer by 15 minutes for keyboards and screen readers
- [x] double-tap a block's title (or Rename) edits it in place; Enter or tapping away saves, Escape cancels; a too-long or empty title is refused plainly
- [x] tap still opens the block; browser tests press every menu item and the double-tap

## F-099 Smooth, quick moves between screens [doing]
Captain, 2026-10-05: moving between screens (week to day, a chat bubble to its chat, the tabs) feels "abrupt… like stop and go… fragmented"; "I would rather give that extra micro second to animate"; it must feel like an app, not a website. · Needs: none (the canvas part waits for F-097)
- [x] same-site page navigations animate (cross-document View Transitions: a short shared fade/slide, the tab bar and heading held still, forward and back in opposite directions) where the browser supports them, and nothing moves under reduced motion; no white flash between pages
- [x] a link starts loading when the finger touches it (pointerdown), and the service worker answers that navigation from the fresh prefetched copy at once (a few seconds' freshness, per person, never a POST or an auth route); tabs, chat bubbles, booking and map links all benefit
- [ ] on the canvas the next levels (every day of the trip from the week, neighbours from a day) are fetched while idle so Day | Week and the flick start at once; one motion token set (duration, easing) used by every transition
- [ ] measured in the browser test: a tab switch and week-to-day render within a target (e.g. under 150 ms after the tap on a warm cache) and the transition runs; checked on the captain's iPhone after deploy

## F-100 The chat box stays at the bottom [todo]
Captain, 2026-10-05 (screenshot of a plan chat): the message box sits right after the messages; after sending, the screen jumps to an empty bottom. It must be fixed at the bottom like WhatsApp. · Needs: F-094
- [ ] in the Family chat and every plan chat the composer is docked above the tab bar (safe areas and the iPhone keyboard respected: it rides up with the keyboard), the messages scroll in the space above it and open scrolled to the newest, which sits right above the box; sending keeps the newest in view; no empty gap below the last message
- [ ] phone checks at 390 and 320 with the keyboard area simulated; browser tests send several messages and check the box stays put and the newest is visible

## F-101 Make a plan by touching empty time [todo]
Captain, 2026-10-05: "just like an event, you should be able to select the time… create an event. Then you just drag, and… give it a title… and boom, it should be done… driven off that calendar". · Needs: F-097, F-099 (grid script)
- [ ] on the day grid an editor holds an empty slot (or taps it, then taps the "+" that appears): a 1-hour block appears there snapped to 15 minutes, with its title field open in place and the keyboard up; typing a title and Enter (or tapping away) saves it; Escape or an empty title removes it; it can be dragged and resized at once with the F-097 gestures; Undo toast; the family is told once
- [ ] a viewer gets nothing; reduced motion; browser tests at 390 and 320 create, rename-on-create, cancel, and move a new block

## F-102 Ask hears you on the iPhone app [blocked]
Captain, 2026-10-05: the Ask mic "is not capturing or transcribing". Cause: Ask only uses the browser's speech recognition, which iPhone does not give to Home Screen apps. Fix: record on the phone (as voice notes do) and transcribe on the server through gitaway/ai.py (job "transcribe"), falling back to it whenever speech recognition is missing or fails.
Blocked: in the Azure OpenAI resource GitAway already uses, deploy a speech-to-text model (gpt-4o-mini-transcribe, or whisper) and tell Claude its deployment name; Claude sets it on Railway as AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT. Checked 2026-10-05: gpt-5.6-sol answers "OperationNotSupported" for audio transcriptions and refuses audio in chat. The code is built and tested in the meantime.
- [ ] where speech recognition is missing or fails (Home Screen app on iPhone), the Ask mic records (MediaRecorder, as F-091) with a clear recording state and stop, uploads the audio, and the transcript fills the box for review; up to 3 minutes; a failure keeps any typed text and says so plainly
- [ ] the transcription runs through gitaway/ai.py as job "transcribe" (logged like every AI call, no audio or text kept), its deployment one setting; tests use a fake transport; browser test with a fake microphone
- [ ] the Ask box looks like GitAway: the handwriting note font and warm note look (readable, 13px floor, grows with the text); dictated words fade in, interim words lighter until final; nothing moves under reduced motion
- [ ] the speech-to-text provider is one setting with a small adapter per provider (Azure now; the captain will bring another that handles Hindi and Indian languages), with an optional language hint (auto-detect by default)

## F-103 A small Day | Week switch; the top folds away [todo]
Captain, 2026-10-05: the Day | Week toggle "is very big and occupies a lot of real estate… make it subtle… bold and obvious, but it doesn't have to be so big… it should fade away, and the only thing I should see is a compact version". · Needs: F-101 (same heading code)
- [ ] Day | Week is a small, crisp segmented switch inside the dark heading (no row of its own), still 44px to tap and clearly showing which is on
- [ ] scrolling the day folds the heading, the filters and the date strip into one compact sticky bar (day name, the small switch, SOS, map), and scrolling back up or tapping it opens them again, smoothly and calm under reduced motion; the week keeps its full heading
- [ ] phone checks at 390 and 320; browser tests scroll, fold, unfold and press the switch both ways
