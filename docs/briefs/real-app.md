# Feature brief: GitAway as a real app for our LA trip (rides simulation + real backend)

Status: approved (2026-10-01, the captain: "any recommendations that you have, assume that I have approved it")

## Why
- The design is settled. The captain wants to use GitAway for real on an upcoming LA trip that was booked on Expedia, together with family who use Gmail, on their iPhones.
- Booking doesn't have to start on GitAway: people book wherever they like (corporate tools, favourite sites). The plan, collaborating with family, forking and contributing are the first real value. Live booking inventory, through Expedia or another partner, comes later.

## Milestone 1: Uber rides, simulated faithfully
- When there's no rental car, the rides card offers "Schedule an Uber" for arrival (pickup at flight landing plus a buffer) and for departure (leave in time for the flight).
- The steps mirror Uber's real API (see docs/research/uber-api.md):
  1. choose a product (UberX, XL, Comfort) with price and time estimates
  2. confirm the pickup and dropoff
  3. it's scheduled
  4. a simulated status timeline follows: scheduled → driver assigned → arriving → on trip → completed
  5. cancel is available
- It's clearly labelled "Simulated: no real ride is booked". The scheduled rides appear on the trip calendar.
- The code sits behind a small `RideProvider` seam, so a real Uber client can replace the simulator once API access is granted. Lyft stays information only.

## Milestone 2: the backend (fh-saas, SQLite, multi-tenant)
- **Built on fh-saas.** The captain's package, on SQLite: a host database for people, families and memberships, plus one tenant database per family.
- **Sign-in with Google.** It's built fully but switched off until the captain adds keys. Meanwhile a clearly marked **local dev sign-in** (any email, only when `GITAWAY_DEV_LOGIN=1` and only on localhost) lets everything be tested. Nothing is deployed; the captain verifies locally first.
- **One family = one tenant.** The person who signs up owns the family. They invite family members by Gmail address as editors or viewers. When an invited person signs in with that address, they join the family instead of getting a new empty one.
- **Real storage for everything that lives in the browser cookie today:** trips, bookings, calendar activities, notes, members, forks, saves, rides. The cookie keeps only the sign-in.
- **A shared community space** for hub and creator trips that every family can browse and fork.
- **Import a booked trip.** A fill-in template (`docs/trip-template.md`) and an import page with a paste box. The trip is built from:
  - travelers
  - each flight leg: airline, number, airports, local times, confirmation
  - the hotel: name, address, check-in and check-out, confirmation, room
  - the car (optional)
  - notes

  Imported trips show on the calendar like booked ones, marked "Booked elsewhere". Pasting an Expedia confirmation email to fill the template automatically is a stretch goal; the template comes first.
- **Installable on iPhone.** A web app manifest, icons and Apple meta tags, so "Add to Home Screen" gives a full-screen app. The trip, calendar and notes keep working on the phone.
- **The sample LA trip and fake catalog stay as the demo.** The booking workspace keeps working on sample data, labelled as a demo, until a real inventory partner is chosen.

## Out of scope (for now)
- Real Uber or Lyft API calls, real hotel or flight inventory or booking, payments (the pay sheet stays simulated), deployment, and email sending (invites are shown as a link to copy, and email comes later via fh-saas `utils_email`).

## Done means
- **Locally, with the dev sign-in:**
  1. Sign in as the captain.
  2. Import the real LA trip from the template.
  3. Invite two family Gmail addresses.
  4. Sign in as one of them (dev sign-in) and see the same trip.
  5. Add an activity and a note together.
  6. Schedule a simulated Uber from LAX to the hotel; it appears on the calendar.
  7. Fork a hub itinerary into the trip.
  8. Restart the server: everything is still there.
- On an iPhone-sized screen the app installs (manifest valid) and the trip is usable.

## Decisions and trade-offs
- **Families as tenants.**
  - Pro: matches how trips are shared, and the data is private per family.
  - Con: travelers outside the family need a public share link, which the hub already provides.
- **Dev sign-in until Google keys exist.**
  - Pro: everything is testable tonight.
  - Con: it must never be on in production, so it's guarded by an env flag plus a localhost check, and covered by a test.
- **Keep the demo catalog.**
  - Pro: the booking design stays alive.
  - Con: two kinds of trips (demo-booked and imported) must both work everywhere.
