Status: draft

# Live LiteAPI: real prices now, a real booking later

## Why (the mission)
- Why this exists: the matrix is the product's revolution, and it only means something with real prices for real places and dates.
- Why now: the founder's LiteAPI account is live (production key available, 2026-11-16); the journey (cover → matrix → plan → guides) is built on sandbox and sample data.
- If it disappeared: a visitor sees sample or sandbox prices and can't trust the matrix to choose a real trip.

## Who it's for
- First: the founder, proving the live experience before anything is advertised (nothing is advertised yet).
- Then: any visitor, who searches and compares without an account (D-761).

## What it does
- Core job: show real, current whole-trip prices in the matrix on gitaway.me.
- Phase 1 (this brief): production key on gitaway.me for search and prices, behind F-265's visitor search limit (shipped first); in production Book is disabled with "Booking opens soon", and Save this trip and Plan this trip lead; in dev the production key gives real prices and Book plays the sample stand-in (no LiteAPI booking call).
- Phase 2 (later, its own go): the founder alone books one real stay and cancels it, paying on LiteAPI's payment form (Nuitee is the merchant of record).
- Out of scope: GitAway taking or holding a card; flights booked here (they stay a partner link, D-483); opening real booking to anyone else.

## How it should look and feel
- Same matrix and drawer as today; only the words, the price and the Book state change.
- A square's hotel price is LiteAPI's public selling price (`suggestedSellingPrice`), taxes and fees in, with fees paid at the hotel said as today. Today's code shows `offerRetailRate`; the build switches the shown price (assumed: when a rate has no public price, show the retail rate and say nothing more).
- Words: "Sandbox booking: nothing is charged" goes; production says "Booking opens soon" on Book; the prices' note says they are live from LiteAPI with the time they were checked (assumed wording, the about-these-prices card).

## How we'll know it worked
- For 5 real trips, a square's hotel price is within about 10% of Booking.com or Expedia for the same room and dates, and the matrix fills in under about 10 seconds.
- Done for phase 1: gitaway.me shows live prices for any searched place, visitors are limited fairly, Book says "Booking opens soon", nothing can be booked or charged.

## Constraints and risks
- Today's booking code pays with ACC_CREDIT_CARD, which live would charge the founder's own card for a guest's hotel: never ship that live. Phase 2 switches to LiteAPI's User Payment (Nuitee SDK). Code already refuses prebook/book unless the key starts `sand_` (D-480).
- Visitors (D-761) would spend the production key's searches: see F-265.
- The production key is a secret: given through the secure card (2026-11-16) and kept in `~/.config/gitaway/liteapi-live.env` (mode 600, outside the repo), which only the dev server's command reads; never printed, never in chat or the repo. Railway gets it only on the founder's go, after F-265.
- Rollback: remove `LITEAPI_KEY` on Railway; the door falls back to the import (`showcase.planning_path`), as today.
- Flights with a production key may need LiteAPI to enable them on the account; if a live search returns no flights, the square says so as today (assumed; checked on the first live search).

## Decisions and trade-offs
- Payment (phase 2): LiteAPI's payment form, Nuitee as merchant of record. Pro: we never touch a card or front money. Con: part of the checkout looks like theirs.
- First real booking: only the founder, one stay, booked and cancelled. Pro: cheapest proof, no stranger's money at risk. Con: one data point.
- Book in production: disabled, "Booking opens soon", with Save and Plan leading. Pro: the loop still works. Con: one visible "not yet".
- Dev: production key for prices, booking faked with the sample stand-in. Pro: dev shows what visitors see. Con: the real booking calls aren't exercised until phase 2.
- Visitor search limit (F-265) ships before the key goes live. Pro: protects the quota. Con: about a day's delay.
- Shown price: the public selling price. Pro: fair against big sites, never undercuts the hotel. Con: our margin is decided in phase 2, inside that price.
- Dev key: through the secure card into a private local file the dev command reads. Pro: no manual step, never printed. Con: a copy of the key lives on this machine (mode 600).
- Phase 2 gets its own brief after phase 1 is live (payment form, founder-only switch, margin, cancel in-app, emails).
- Production booking off until phase 2. Pro: real prices ship now with no money risk. Con: visitors can't book yet.

## Open questions
- None for phase 1. Deferred to the phase 2 brief: margin, the founder-only switch, cancel in-app, confirmation emails, receipts.

## First live probe (2026-11-16, `scripts/probe_liteapi_prices.py`, `probe_liteapi_stream.py`)
- The key is live and works: San Diego, Dec 15 for 3 nights, 2 adults and 2 kids: 28 hotels priced. Flights stream live too (SFO to San Diego: 52 journeys, complete in 7.6 s).
- The public selling price is about 15% above the retail rate on every hotel (Best Western Island Palms: retail $337.31, public $387.91). So the public price is the safe choice for rate parity, and the gap is where phase 2's margin lives.
- Some hotels add resort fees paid at the hotel ($60 to $120), not in either price: the square must keep saying them (it does today, `Room.due`).
- Visitors already share one daily "guest" search budget, inside the site's daily total (`liteapi._spend`): the quota is capped today; F-265 is about fairness between visitors, not the quota.
