# Feature brief: book any mix of flight, stay and car (plus rides when there's no car)

Status: approved (2026-09-30, captain)

## Why
- Real travelers often book only part of a trip: they drive, stay with family, or skip the rental. Today the workspace, ledger, pay and calendar assume all three, so a partial trip can't be booked honestly.

## Who and when
- The traveler in the booking workspace (/plan) who wants only some of the lanes.

## What it does (v1, fake data)
1. Flights, Stays and Car each get a clear **skip** choice, e.g. "I'll drive", "Staying with friends", "No car". A skipped lane collapses to a slim, friendly row that can be undone in one tap.
2. The **ledger, pay sheet and calendar** work with any mix: flight only, stay only, car only, or any two. Missing pieces leave no blank lines or $0 items. At least one lane must be picked to book.
3. **No car → rides card**: "Uber and Lyft from LAX" (or BUR) with sample fares and times to the picked hotel (or to the area when there's no stay) for arrival and departure. Its estimate is added to the total as a clearly labelled estimate line ("Rides, estimated"), separate from paid items.
4. The picks, including skips, live in the URL like today, so reload, pay and the calendar respect them.

- Out of scope: real ride booking. Scheduling an Uber or Lyft in the app needs partner API access; research it later.

## Look and feel
- GitAway system. Skipping should feel light and positive, never like an error. The rides card uses the sky tint with simple car icons. No logos are copied; "Uber" and "Lyft" are plain text.

## Done means
- On the sample trip:
  - skip the car → the rides card shows, and the total = flight + stay + rides estimate
  - skip the flight too → the stay-only total books through pay and shows on the calendar with no flight blocks
  - undo both → back to today's $3,088 default

## Decisions and trade-offs
- Rides added to the total as an estimate. Pro: an honest picture of trip cost. Con: mixes estimates with paid items, so the estimate is shown separately on pay and isn't charged.
