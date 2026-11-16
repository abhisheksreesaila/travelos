# Overnight run, 2026-11-16

**Goal:** "fix all the changes and cover page and all the stuff that we talked about". Scope is development and testing only. Nothing was deployed or booked, and no Railway setting was changed.

## Milestones (`pixi run python scripts/check_overnight.py`)

| Milestone | Status | What it means |
|---|---|---|
| M1 F-268 | PASS | Typing just a place opens the matrix, with a window about 4 weeks out that you can change in the sentence. |
| M2 F-269 | PASS | After Save, "Plan this trip" leads to the calendar. |
| M3 F-270 | PASS | No page loads fonts from Google; the hand font is served from our own site. |
| M4 F-256 | PASS | Every browser test file loads. |
| M5 | PASS | Unit tests: 3,634 passed, in fixed order and in random order. Browser tests: 481 passed, 8 skipped (the skips already existed). |
| M6 | PASS | `docs/ship/live-prices.md` (what could break, how we'd know, rollback) and `scripts/railway_set_liteapi_key.sh`, ready for your "deploy". |

The first check run failed M5, because one test helper broke when tests ran in random order. I fixed it and re-ran.

## Also done tonight (all reviewed)

- **F-266, the postcard cover.** The wish on the card is a real search.
- **F-265, visitor searches.** Each visitor has their own 60 searches a day, and sign-in is offered after that.
- **F-267, live prices.** Squares show the public price, and Book says "Booking opens soon" in production.
- **The browser test clean-up (M5):**
  - 19 tests of removed pages deleted.
  - 24 tests moved to the v2 pages.
  - 23 tests updated to the new rules.
  - One real bug fixed: the local Plan it for me checkout page was hidden behind another page with the same address pattern.
  - The full table is in `docs/report/m5-browser-triage.md`.
- **Walking the journey at laptop and phone sizes.** The guide page's header was wider than a phone screen; fixed.

## Live prices, checked with your key on this machine

San Diego from SFO, Dec 15 to 18, 2 adults and 2 kids: **$1,017 for the whole trip** (flights plus Best Western Island Palms, refundable). Los Angeles came out at **$855** and was marked Our pick.

## Worth a second look (decisions)

1. **The window picked for a place-only wish (D-772).** It starts on the Friday at least 28 days out, for 3 nights, give or take 2 days. Off the showcase, it still asks where you fly from.
2. **The visitor allowance (D-764).** 60 new searches a day, about three full matrices. The count resets when the server restarts.
3. **Retired tests (`docs/report/m5-browser-triage.md`).** These are the deleted ones; each covered a page removed with the old app.

## Recommendation, not done

The sign-in page still has the old purple "Compare the whole trip" look, which no longer matches the cover or the v2 pages. It's the one screen in the journey that feels like a different site. I'd redesign it in the v2 look as a prototype first.

## Next

1. Say "start the servers" to try it on dev.
2. Spot-check 5 trips against Booking.com.
3. Say "deploy" when happy (`docs/ship/live-prices.md`).
