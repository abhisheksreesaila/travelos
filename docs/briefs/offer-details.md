# Feature brief: flight and stay details (iPad-style list and detail in the workspace)

Status: approved (2026-09-30)

## Why
- A real booking API returns far more than a list: photos, room types, views, meals, fare rules. Today GitAway shows only the list, so travelers can't make an informed choice, which is the whole point of the workspace.

## Who and when
- The traveler in the booking workspace (/plan) comparing flights and stays, especially a family deciding between rooms.

## What it does (v1, fake data)
1. **Expanding** the Flights or Stays pane (the expand button, or its key then Enter) animates it into a **split view**: the offers shrink into a list sidebar on the left, and the selected offer opens in a **detail panel** on the right, like an iPad master-detail view. Esc, or the collapse button, animates it back into the tiled workspace. The first offer, or the currently picked one, opens by default.
2. **Stay detail**:
   - a photo gallery (CC0/public-domain sample photos, credited, labelled "sample photo")
   - an area note, rating and highlights
   - **room types**, e.g. City-view King, Ocean-view King, Family suite, each with its own price, occupancy, bed setup and view
   - **add-ons** toggled on and off: breakfast, late checkout, parking
   - the cancellation policy

   The traveler picks a room (for 4 people this may mean 2 rooms, or 1 suite) plus add-ons.
3. **Flight detail**:
   - the out and back legs with times, duration, stop and aircraft
   - **fare types** (Basic, Main, Extra legroom), each with its price and what it includes (seat choice, carry-on, checked bag, changes)
   - checked-bag count as an add-on
4. **Choose** makes that option (with its room or fare and add-ons) the lane's pick. The **cost ledger** updates instantly, and the stay and flight lines itemize room and fare plus add-ons. The picks live in the URL like today, so reloading, pay and the calendar all respect them.

- Out of scope: cars (stay as they are), real inventory or availability, seat maps, room photos claiming to show the fictional hotel's real rooms.

## Look and feel
- GitAway system. A smooth, spring-y (not bouncy) morph from the tile to the sidebar, with big tactile room cards and playful feature chips (sea view, breakfast, crib available). Reduced motion swaps instantly.
- Phone: the list and the detail become two screens with a back button.

## Done means
- On the sample trip: expand Stays, see the split view animate in, browse the three hotels, pick "Ocean-view King ×2 + breakfast" at The Tidewater, and the total updates correctly. The same works for a flight fare. It carries through to pay and the calendar. The captain signs it off by feel.

## Decisions and trade-offs
- Stays and flights. Pro: covers the two big choices. Con: about twice the design of stays alone.
- CC0 sample photos. Pro: looks like a real booking site. Con: they're generic rooms, so they're always labelled "sample photo" and never presented as the real hotel.
- Room plus add-ons. Pro: fun, real choices and an honest itemized total. Con: a more complex ledger and pick URL.
- Split view only when expanded. Pro: the tiled "everything side by side" workspace stays the default. Con: the details are one click away.

## Open questions
- None blocking. The photo sources are chosen during design.
