Status: built (F-275, founder approved the prototype direction 2026-11-16; live check on the Tahoe search)

# The matrix, made obvious and rich (v3)

## In the founder's words (condensed)
- **The sentence is camouflaged.** "The sentence as a query is sort of camouflaged into the background … if people don't know how to use it, they'll be searching for it. Make it obvious … less gradient around that area … people who will be booking won't be used to such interfaces … even have some autocomplete items down below so that they know what to click."
- **The bands overlap.** "The 4 nights … the CSS is sort of interfering with the other grid … it doesn't look nice."
- **Go wide?** "What is the harm of going wide … use the full screen … or will the mobile version suffer?"
- **Speed.** "It took a while … we have to get clever in how we produce the matrix … people can wait as long as you keep them busy … mask the wait time with something."
- **Hotel photos and reviews.**
  - "One photo … I don't want to make a decision with one photo."
  - "Reviews … people want to read … what the hotel is all about … a lot of information, not just the price."
- **Flights.** "An accordion … flight symbols: when you start, when you finish … if it crosses a date, say +1 … traditional stuff they're used to … flight I'm not too concerned."
- **Side widgets.** "We can sacrifice the widgets on the side … secondary information, it should not dominate … a minimized version of all of them, and only when they click it becomes a card."

## What LiteAPI can give us (live probe, 2026-11-16)
- **Hotel details.** `/data/hotel` for Hilton Los Angeles Airport returned:
  - 112 hotel photos with captions;
  - 35 room types with 197 room photos;
  - 78 facilities;
  - a 715-character description;
  - a 7.6 rating from 6,263 reviews.
  The call takes about 0.3 s.
- **Reviews.** `/data/reviews?getSentiment=true` returns:
  - individual reviews (name, date, score, traveller type, country, pros, cons);
  - an AI summary by category (Cleanliness 8, Service 8, …), with pros and cons.
  The call takes about 0.3 s.
- **Speed.**
  - An uncached `/hotels/rates` for one place and window takes about 6.6 s.
  - The same search repeated returns in 0.4 s, because LiteAPI caches it.
  - `/hotels/min-rates` by hotel ids is no faster (7.6 s).
  - A flight stream completes in about 7.6 s.
  - A 5 × 5 matrix needs about 30 searches, and our gate runs 3 at a time: roughly a minute.

## Open (decide after the prototype)
- How many searches at once LiteAPI's live plan allows.
- Whether to pre-warm popular routes.
- How much of the hotel's detail loads with the square, and how much loads on open.
