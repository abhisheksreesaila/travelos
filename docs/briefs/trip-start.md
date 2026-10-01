# Feature brief: "Where to?" trip start after sign-in

Status: approved (2026-09-30, the captain asked for it directly: "once you sign in, shouldn't you get a page to enter where you want to go … press submit and that has to lead to the trip")

## Why
- Today, signing in drops the traveler back on the marketing landing page. A signed-in traveler should land somewhere they can start a trip.

## Who and when
- A signed-in traveler, or anyone who clicks "Plan a trip", who hasn't started a trip yet.

## What it does (v1, fake data)
1. **/start: a "Where to?" page.** It has from (SFO prefilled), to (destination with suggestions), dates (depart and return), and who's going (adults, plus kids with ages). One big Submit: "Find my trip".
2. **Signing in without a specific destination lands on /start**, not the landing page. The header shows a "Plan a trip" link to it. The landing page's "Plan a trip" door goes to /start.
3. **Submit opens the booking workspace for that trip.** The trip title, dates and travelers in the header come from the form.
   - Nights and travelers drive the sample prices honestly: stays and cars scale by nights, flights by travelers, and the room fit badge uses the real party size. The catalog does the maths.
   - The trip lives in the URL, so reload, pay and the calendar respect it.
4. **Sample data covers Los Angeles only.** Other destinations show as "coming soon" suggestions and can't be submitted, so nothing is faked.
5. **Returning travelers** see their booked or in-progress trip as a card above the form ("Continue LA with the kids").

- Out of scope: real search, other cities' inventory, flexible dates.

## Look and feel
- GitAway system at the new compact scale. It is joyful and quick: a big friendly question, sticker-style suggestion chips (LA, San Diego and Hawaii marked "coming soon"), and a date range and party picker that need no typing on a phone.

## Done means
- Sign in → lands on /start.
- Choose LA, Oct 16–20 and 2 adults plus kids aged 4 and 7, then submit → the workspace shows today's sample trip at $3,088.
- Change to 3 nights or 3 adults → the prices change accordingly, through pay and the calendar.

## Decisions and trade-offs
- Built without a separate artboard, following the landing and workspace design language, because the captain wanted to see the whole journey working now. The captain reviews it in the running app.
