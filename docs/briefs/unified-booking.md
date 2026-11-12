# The trip matrix: see every option, then decide together (draft)

Status: draft, waiting on the founder

> 2026-11-12: replaces the links-only draft of 2026-11-08. The founder chose one source, LiteAPI (Nuitée), for flights and stays: search first, booking after the test. It supersedes D-415's "no in-app booking" for search only; booking itself waits for the test below. The links-only lanes (F-198) stay as they are until then. F-217's trip grid is the start of this view.

## Why
An agent answers the question you asked. The matrix shows you the question you should have asked: "San Diego was my plan, but LA is $300 and San Diego only $50 more, so let's do both." Nobody shows the **whole trip compared** (flight, stay, airport drive, weather, fit for the kids, one total) across **places and dates** in one view, and then lets the family decide together. Flight-only maps exist (Google Flights Explore, Kayak Explore); this does not.

GitAway's core stays sharing, creators and the family trip. The matrix is the moment that makes people say "wow" and stay; booking comes along for the ride.

## What the founder decided (2026-11-12)
- **One source: LiteAPI** for flights and stays (more connections and friendlier for developers than Duffel; says it carries Southwest, to be confirmed by a real search). Aviasales' cached fares only if live search proves too slow (below).
- **Search first, booking after the test.** Live prices, labelled **Preview**. The book button says **"Booking opens soon"** and offers to save the trip and tell them. Never take a card, never pretend to book, never send them to another site carrying LiteAPI's price.
- **Joy over AI everywhere.** The page should feel alive and full of taste, not like a chat box doing search.
- **Dense and useful.** Everything needed to decide sits beside the choice.

## What the family sees
1. **The sentence** (built, F-217): "A family of 4, from SFO, San Diego or nearby, Dec 12 to 16 give or take 2 days, under $3,000." Each underlined part is a dropdown.
2. **The matrix:** places and dates across, stays down, or flights against stays for one place; each square is the whole trip's total. Squares fill in as answers arrive. The best ones are marked by plain rules (cheapest, easiest for kids, best weather), never by a guess.
3. **Weather in the calendar**: each day shows its sky (forecast when near, typical weather labelled "not a forecast yet" when far). Rain is said plainly.
4. **The place has a face**: each destination wears its own art: a beach for San Diego, the Statue of Liberty skyline for New York, mountains and pines for Tahoe. A drawn set of our own, one per place in `places.py`'s table, never a photo passed off as a hotel, never generated per visit.
5. **Living**: a creator's pick on a square ("Maya stayed here with her kids"), the family's votes and comments on squares, the weather moving in the sky.
6. **Booking opens soon**: save the square to the trip; the cockpit, day plan and family chat pick it up like any trip.
7. **The report**: after a planning session, a fun summary: "You compared 6 places and 41 stays; the cheapest week was Dec 14; you found LA + San Diego for $50 more."
8. **Ready to post**: a trip card made for Instagram (the place's art, dates, the route, a link back to the trip), so sharing GitAway is one tap.

## Choose it together (draft, 2026-11-12)
Built on what exists: families with roles and invitations (`members.py`), the family chat keyed per plan (`familychats.py`), friends as other families.
1. **Share the matrix**: "Ask the family" shows it to every member; a link brings in friends coming along (another family).
2. **Heart a square**: anyone, kids included, hearts what they like; the square shows who (faces or initials).
3. **Talk on a square**: each square has its own short thread, the family chat keyed to that square.
4. **The shortlist builds itself**: the most-hearted squares rise ("3 of you like LA + San Diego").
5. **Prices keep watch**: a hearted square says when its price moved ("up $40 since Ana liked it").
6. **One person decides**: the trip's owner taps "This one"; it becomes the family's trip and everyone is told.
7. **Two families**: each picks its own flights, both vote on the shared stay, and the split comes along.
Decided by the founder (2026-11-12): **the owner decides**; hearts are advice. **Friends heart without an account**: the shared link (long, unguessable, the owner can turn it off) asks only for a first name, keeps one heart per person on that phone or laptop, and marks a guest's heart as a guest's. Comments from a guest are the same. Nothing private (bookings, confirmations, the family chat) is on the shared matrix.

## The cover tells this story (draft, 2026-11-12)
Headline (the founder's pick, 2026-11-12): **"The whole trip, compared. With the people you're going with."** Lines about a trip "you didn't know you needed" or "to ask for" were dropped as easy to misread.
Three parts, each with its own beats, replacing the eight stages of cover v5:
1. **Compare.** One sentence types itself ("A family of 4, from SFO, somewhere warm, Dec 12 to 16"); the matrix fills in and one square lights up ("LA + San Diego, $50 more than San Diego alone"); the calendar wears the weather, the place wears its art.
2. **Plan it together.** Family votes land on squares, the chat beside them; the chosen square becomes the family's trip.
3. **Leave a trail others can follow.** Subtitle: "Bloggers and vloggers welcome." The trip becomes the Instagram-ready card; creators (travel bloggers, vloggers) welcome: their trips open into a matrix of their own for their readers.
Close: the headline again, "Booking opens soon" said plainly.
The cockpit and the creator tools leave the cover for their own pages. Fewer, calmer moves (cover v5 felt jittery to the founder); drafted in the designer before any code.

## Look
Direction A, omxqua: tiles stay opaque. Translucency only where the design taste allows it, the floating islands over the matrix (the top and side that already fold into islands on a laptop) and the phone's tab bar, readable over anything under them. Phone and laptop designed together.

## Speed: the matrix is many searches
The arithmetic is trivial; the wait is the API (a live flight search takes seconds; 5 places × 5 date choices is 25 searches before stays). No GPU. Instead:
- **Cache** every answer (flights a few hours, stays shorter), shared across families searching the same route and dates; say how old a price is.
- **Fill as it arrives**: the squares appear one by one, the cheapest first.
- **Search what matters**: search the nearest dates and the likeliest places first; only search a far square when the family scrolls to it or asks.
- **If still slow**: Aviasales' cached fare calendar (one call for a whole month) picks which flight squares deserve a live search.
- **Budget**: a daily search budget per family and in total, so a busy day cannot run up a bill or hit LiteAPI's rate limits.

## The test (about 2 weeks once keys are in)
Show the matrix to 5 to 10 families, including the founder's and a friend's. Success: someone finds an option they did not know about and changes their plan. Then decide on booking through LiteAPI (hotels first) with the founder's friend who has done this, and Nuitée's written answer on who is the seller. If nobody does, the matrix stays a planning view and booking stays links.

## What only the founder can do
1. Open a LiteAPI account. The sandbox key is instant; the live key needs a card and payout details.
2. Request production flight access (dashboard → Flights → Request access): use case "a family trip planner, search now, booking after a test".
3. Put the key on the server as `LITEAPI_KEY` (a `sand_` key is the sandbox; the code tells them apart by that prefix and says which on /admin). Never in chat.
4. Email Nuitée: who is the seller when Nuitée charges the card, and is Southwest bookable in production.

## Not in this brief
Booking itself, payments, cars (links as today), things to do (Klook links), the forwarding address for confirmations (its own brief).

## Known facts (checked 2026-11-10 to 12)
- LiteAPI flights: 600+ airlines through Travelport, Sabre, direct airline (NDC) and low-cost connections; 1% a booking (min €2, max €10), €25 a voluntary change; a 24/7 team handles changes and disruptions; partner markup allowed; the sandbox has only a test airline ("Nuitee Air"). Source: nuitee.com/connect/flights, docs.liteapi.travel.
- LiteAPI stays: self-serve; search is free at a reasonable search-to-booking ratio; extra searches cost about €0.005. To confirm in writing: the limits when nothing is booked yet.
- Travelpayouts closed Hotellook on 2025-10-20; Aviasales' cached fares (Data API v3) are free and labelled with their age.
