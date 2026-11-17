# Overnight run, 2026-11-17

**Your words:** "take a step back, ask yourself what is the soul, make it happen with design skills … world class travel website."

**Rules followed:** development and testing only. Nothing deployed, no Railway change, no real booking, no email sent. The only live calls were read-only LiteAPI reads: one reviews read and searches.

## What GitAway is for (the soul, written down)
GitAway is the friend who has already been there.
- You say a wish in plain words.
- It shows the whole trip, flights and stay together, across nearby places and days, as one number.
- It tells you the truth the listings leave out.
- You decide in one sitting, book in one place, and plan together.

Three promises, which every page was judged against:
1. **The whole trip, one number.**
2. **The truth, up front.**
3. **Calm confidence.**

The full text is in `docs/report/journey-2026-11-17.md`.

## Milestones (`pixi run python scripts/check_overnight2.py`)
| | |
|---|---|
| M1 F-286 pins that are there when you look | PASS |
| M2 F-282 hotel dashboard, fine print, review drawer, map pins | PASS |
| M3 F-283 stay and flights apart, rooms row | PASS |
| M4 the soul and the walk, with screenshots | PASS |
| M5 at least 6 fixes from the walk | PASS (10 fixed) |
| M6 unit suite and tonight's browser files green | PASS (the whole unit suite and 10 browser files) |
| M7 this report | PASS |

## Matrix v5 is complete (F-281 to F-286, all reviewed and merged)
- **F-281 Harbour ground and Fill chips.** The deep sky stays deep in light mode, and the extra-info tray stands out.
- **F-282 The hotel as a decision dashboard.** Beside the photos:
  - the score, the last-100 strip and the category bars;
  - "The fine print, up front": costs not in the price, policies that bite (including "your flight lands 3 h 10 min before check-in"), fits your family, getting there (with the map's pins and "See it from above"), and what guests complain about;
  - "Heads up" flags on unusual items, and "not listed" whenever the hotel doesn't say;
  - a side drawer with all the reviews, filterable by traveller type.
- **F-283 Stay and flights apart.**
  - A "Your stay" band and a "Your flights · SFO ⇄ SAN · 4 people" band, with a dashed "Now, getting there" between them.
  - A sticky Stay · Flights · Total · Book bar.
  - Every room type in a swipe row.
- **F-284 See it from above** (merged yesterday evening). Photoreal 3D needs sign-in, each person gets 10 opens a day, and the site 100.
- **F-285 Booking emails** (merged yesterday evening).
- **F-286 Pins that are there when you look.**
  - Three OpenStreetMap servers to try in turn.
  - Pins are fetched in the background as soon as a square opens.

## The walk: what I fixed (each with a test that fails on the old code)
1. **Guides page, light mode:** the headline was nearly invisible on the deep sky.
2. **A colour-name clash.** The new sky's word colour reused `--sky-ink`, which two older stylesheets already use, so pass labels could turn near-white on white. It's now `--ground-ink`.
3. **Phone search box:** the hint was cut off mid-word. It's now "Try “Tahoe with kids”".
4. **Phone matrix:** the place fact sat on top of the floating Book · Guides bar.
5. **Book my trip never stayed in view.** The drawer clipped its sticky foot. On a laptop it now stays at the bottom of the screen the whole way down the trip.
6. **"What guests complain about" never opened a review on real data.** I checked live Hilton LAX reviews: real reviews are short, and the two-word rule matched 0. Now one meaningful word matches, and the link says what's shared: "Read 8 reviews that mention pricey or breakfast".
7. **Checkout:** the final "Book for $984" was greyed with no reason given. A "Tick the rules to book" link now shows the box. It never ticks it for you.
8. **Three things the whole suite caught after merges:**
   - two page sweeps tripped on a data route;
   - F-284's pixel sizes, and its counts were missing from the forget-a-person script;
   - a false black-on-black in the drawer's audit.

## Worth your look (recommendations, not built)
1. **A phone's first screen is all sentence, no prices.** Fold the search card to one line once results land, so the cheapest whole trip shows without scrolling.
2. **Two totals in one checkout.** The square says "Book my trip $1,276" and the checkout "Book for $984": the stay only, because the flight is booked on the airline's site. It's honest, but it reads like a price change.
3. **One word for one thing.** A visitor's bar says "Plan a trip" for the search, while a member's says "Book" for the search and "Plan" for the calendar.
4. **The cover is the one light page left.** Try a Harbour version of the postcard stage.
5. **The phone planner stacks two floating bars**, so the calendar barely shows.

## Decisions most worth a second look
- **D-919: complaints match on one shared word.** The link and drawer always name the words ("mention", never "say").
- **D-918: Book my trip sticks on a laptop but not on a phone.** On a phone the foot (note, Save, Book) is about 14rem tall.
- **The photoreal 3D view needs sign-in** (F-284 security fix). The free map with pins stays open to everyone.

## Try it
- Sample data: `GITAWAY_DEV_LOGIN=1 pixi run python -m uvicorn main:app --port 6015`, then open `/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&x=2` and open any square.
- Live prices plus your Google key: port 6002 (the live-prices server command in docs/ship/live-prices.md, plus `. ~/.config/gitaway/google-maps.env`).
- Screenshots: `docs/report/journey-2026-11-17/`, `docs/report/f282-*.png`, `docs/report/f283-*.png`.

## Next
Say "deploy" to put matrix v5, the emails and the live prices on gitaway.me (docs/ship/live-prices.md). Or pick from the five recommendations first.
