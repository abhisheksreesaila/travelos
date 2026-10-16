# Why GitAway doesn't feel zippy (F-168, measured 2026-10-15)

**Short answer:** it is not the tech stack. When a tap lands, the next screen is usually already on the phone. What feels slow is our own timing:

- every move takes about half a second,
- some taps wait on purpose before anything happens,
- some steps run one after another when they could run together,
- the server does about 27× more database work per screen than it needs to.

Only about **5% of the phone's moving time** (11% on the laptop) is spent waiting for the network.

## How it was measured

- A local server with a seeded trip: 5 days, the two park days, and 5 timed plans per day.
- Headless Chromium through Playwright.
- Phone: 390×844 with touch. Laptop: 1440×900 with a mouse.
- The CPU was slowed 4× and 180 ms was added to every request. That is roughly the live round trip: a no-op `/healthz` on gitaway.me answers in 120–170 ms.
- Each interaction was repeated 3 times; the tables show the median.

What the columns mean:

- **Starts**: the time from the input to the first frame of the new thing moving.
- **Settled**: the time until the last transition, animation or DOM change ends.
- **Net wait**: how long the screen sat waiting for a reply.
- **Long task**: the longest piece of blocking script.
- **Drops**: dropped frames.

Rerun with `scripts/perf/run_all.sh <out-folder>`, then `python scripts/perf/report.py <out-folder>`. The scripts are in `scripts/perf/`.

**Caveat:** other agents were loading the machine (load average around 20 on 24 cores) while this ran. The exact ms numbers are noisy and the server times are inflated. The order of the steps and the ratios held in every run.

## Phone (CPU 4× slower, +180 ms per request)

| Tap | Starts | Settled | Net wait | Long task | Drops | Fast-phone settled (CPU 1×) |
|---|---|---|---|---|---|---|
| Day chip, next day already fetched | 120 | 648 | 0 | 60 | 5 | 626 |
| Day chip, not fetched (after a write) | 293 | 836 | 211 | 0 | 5 | 1012 |
| Day chip after 62 s on the day | 322 | 842 | 208 | 0 | 5 | n/a |
| Swipe to next day (from lift) | 170 | 718 | 0 | 75 | 16 | 557 |
| Back | 78 | 619 | 0 | 0 | 5 | 550 |
| Day → Week ("‹ Trip") | 133 | 683 | 0 | 70 | 16 | 578 |
| Week → Day (day row) | 340 | 984 | 0 | 159 | 38 | 562 |
| Filter tap | 34 | 34 | 0 | 0 | 0 | 18 |
| Open a plan (tap its name) | **424** | 1023 | 0 | 101 | 6 | 976 |
| Ask sheet | 305 | 925 | 0 | **331** | 37 | 604 |
| Add: hold empty time → draft | 453 | 717 | 0 | 106 | 16 | 678 |
| Add: Enter → saved | 298 | 1056 | 221 | 161 | 18 | 781 |
| Move: drop → settled | 45 | **1251** | 0 | 73 | 17 | 1108 |

## Laptop (CPU 4× slower, +180 ms per request)

| Click / key | Starts | Settled | Net wait | Long task | Drops |
|---|---|---|---|---|---|
| Day tab, already fetched | 140 | 330 | 0 | 77 | 13 |
| Day tab, not fetched | **461** | 663 | 212 | 198 | 16 |
| Day tab after 62 s on the day | 318 | 494 | 206 | 52 | 6 |
| Arrow key, next day | 116 | 314 | 0 | 80 | 11 |
| Back | 72 | 245 | 0 | 0 | 6 |
| Day → Week | 87 | 250 | 0 | 59 | 5 |
| Week → Day | 128 | 300 | 0 | 90 | 14 |
| Filter click | 18 | 18 | 0 | 0 | 0 |
| Open a plan (panel) | 44 | 202 | 0 | 0 | 2 |
| Ask (panel tab) | 19 | 250 | 0 | 53 | 3 |
| Add: Enter → saved | 256 | 416 | 217 | 90 | 8 |
| Move: drop → settled | 13 | 387 | 0 | 69 | 14 |

The laptop feels fine: every change is one 140 ms fade. The laptop's stop-and-go is the day switch whenever the copy fetched ahead has expired or been thrown away.

## What one tap actually does (phone, timestamps in ms)

**Day chip, fetched ahead:**

- tap at 0
- view transition called at 33
- the swap (new HTML, layout) runs 63–110
- the slide starts at 155
- the slide ends at 662, because the screen motion is 500 ms

**Day chip after a minute on the day:**

- 0 to about 230: waits for the fragment. Nothing moves; there is no outline for a sideways move.
- About 300: the slide starts.
- About 840: settled.
- Then six more fragments (about 250 KB) are fetched again.

**Open a plan by tapping its name:**

- First click at 0 is swallowed, and a timer waits 330 ms for a possible double tap (rename).
- Second click at 388.
- The click handler forces a 103 ms layout.
- The card spring starts at 436 and ends at 1104.

**Move (drop at 0):**

- The block's landing spring and the save start together (good). The save answers at 248.
- The refresh then waits for the landing to finish (614).
- The refresh happens at 630 and starts a second 520 ms glide of every block whose lane changed. Done at 1250.
- So it goes **land, stop, glide**.

**Swipe:**

- The page follows the finger at only 25%.
- At lift the offset snaps back to 0, which is a visible hitch.
- Then, after the swap work (80–240 ms on a slow CPU), the 500 ms slide starts from the middle.

## Causes, ranked

1. **Motion length.**
   - Every phone screen change is a 500 ms transition (`--motion-screen-dur`), and every open or land is a 520 ms spring.
   - On a fast phone the slide itself is about 80% of the time to settle: a day chip settles at 626 ms, of which 500 is the slide.
   - The zoom curve is about 90% of the way there by around 225 ms. The rest is a long soft tail, which can read as "still moving".
2. **Waits by design.**
   - A tap on a plan's name waits 330 ms for a double tap (`day_menu.js` ~L475). This is the single biggest delay on "open a plan".
   - Making a plan needs a 350 ms hold.
3. **Steps in a row that could overlap.**
   - Move: land, then the refresh, then a second glide (`day_grid.js` `save()` waits for `landed`).
   - Swipe: snap back, then the swap, then the slide.
   - Week → Day: a 159 ms swap inside the transition before anything moves.
4. **The copy fetched ahead goes stale or gets thrown away.**
   - `FRESH = 60 s`: after a minute on a day, the next chip waits a full round trip (208 ms here; live it is the round trip plus the server's time).
   - Every write empties the cache, so the next day switch right after a move or add is a miss.
   - The idle refetch then pulls the five days and the week again, about 250 KB, after every swap and every write.
5. **Server render cost.**
   - One day fragment opens the family database **27 times**: a plan card 14 times, the week 15, the day plus plan panel 32.
   - Each opening clones the SQLAlchemy metadata of about 28 tables. About 80% of the fragment's server time is that opening (cProfile, `scripts/perf/profile_server.py`).
   - Alone, a day fragment took 30–50 ms. When two prefetches arrive together each takes 150–230 ms: the membership check runs under one host lock.
   - This sits inside every miss, every write reply (`POST /trip/canvas/plan` renders the level, 47 ms, about 47 KB) and every prefetch.
6. **Wasted prefetch.**
   - The week page prefetches every desktop plan row (`a.cz-wi.is-plan`) even on the phone, where those rows are hidden.
   - That is 12–18 day-plus-panel fragments, about 40 KB each and 0.6–0.75 MB in total, after every visit to the week. Each one costs the server 32 DB opens.
   - They keep the server busy just as the next real tap arrives.
7. **Main-thread work on slow phones.**
   - Ask sheet open: one 331 ms task. `ask_sheet.js` `open()` sets `inert` on the whole page, fills the box and starts the mic, all in the tap.
   - Week → Day: the swap takes 159 ms.
   - Card open: a 100 ms forced layout.
   - On a new iPhone (the CPU 1× rows) these mostly vanish: Ask starts at 58 ms.

## Fixes, with the expected gain

| # | Fix | Expected gain (phone) |
|---|---|---|
| 1 | Open the card on the first tap. Move rename to the hold menu, or handle the double tap from the open card. | Open a plan starts at ~90 instead of 424; −330 ms |
| 2 | Show a copy we already have at once, even if older than 60 s or from before a write, and update it quietly (the `revalidate` path exists). Prefetch ±1 day straight after each write from the level the write handed back. | Day switch after a minute or a write starts at ~120 instead of ~300; live, −250 to 400 ms |
| 3 | Move: put the refreshed day in while the block lands, and glide the neighbours in the same motion. Toast at the drop. | Move settles ~700 instead of 1250 ms; one motion, not two |
| 4 | Swipe: follow the finger 1:1 and carry on the slide from where the finger let go (no snap back to 0). | No hitch; the motion starts under the finger |
| 5 | Shorter phone motion: screens 500 → ~320 ms, springs 520 → ~360 ms, same curves. **This is a taste call: F-138 made them longer on your request. Try it on the phone first.** | About −180 ms on every screen change and open; a day chip settles ~470 instead of 650 |
| 6 | Server: open the family database once per request and reuse it (request-scoped). | Day fragment 27 opens → 1; render about 5× faster, and no pile-up when two requests land together. Shortens every miss and every write reply live |
| 7 | Prefetch diet: on the phone, prefetch only rows that have a box (skip the hidden desktop plan rows); after a swap fetch ±1 day first, the rest later. | −0.6 to 0.75 MB and ~16 server renders per week visit; the next tap no longer queues behind them |
| 8 | Slow-phone main thread: inert one wrapper instead of every child, start the mic after the sheet's first frame, and read layout before writing it in the swap hooks. | −100 to 300 ms on older phones; small on a new iPhone |

Fixes 1–4 and 6 are pure sequencing and server work, and change nothing in the look. Fix 5 changes the feel and needs your eye.

## Is it the tech stack?

**No, mostly not.**

Over the twelve phone interactions above, the screen waited on the network for 432 ms out of 9.5 s of total time to settle, about **5%** (laptop: about 11%). That waiting only happens:

- when the copy fetched ahead was missing (after a minute or after a write), and
- for Add's toast.

Fixes 2 and 6 remove most of it.

The other ~95% is ours: 500 ms motions, deliberate waits (330 ms, 350 ms), and steps that run one after another.

A client-side app would need the same round trips to save. Server fragments plus morphing already give us an instant swap when the copy is in hand: 59 ms to the first frame on a fast phone. What a native app gets for free is finger-tracking gestures and short, interruptible motions. We can do both here (fixes 4 and 5) without changing the stack.
