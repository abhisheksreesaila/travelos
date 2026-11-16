# M5: browser suite triage

Start: `pixi run test-browser` on master 816bf702 gave 70 failed, 431 passed. Each failure was run on its own, read, and put in one of four boxes. Nothing was skipped or loosened; a test that checked a
retired page was deleted, or pointed at the v2 page that now holds the behaviour, and said so in its docstring ("M5 triage").

| Box | Failures | |
|---|---|---|
| (a) RETIRED, test deleted | 19 | the old booking lanes, the family trip publish editor |
| (a) RETIRED, test pointed at the v2 page | 24 | the behaviour still exists in v2 |
| (b) STALE, assertion updated to the new rule | 23 | F-262 guide, F-266 cover, F-268, D-761, Book/Plan/Guides bar, trip home is `/trip/plan` |
| (c) REAL BUG, product fixed | 4 | one bug (below) |
| (d) FLAKY | 0 | none of the 70 passed on a rerun unchanged; one of my own rewrites raced (see test_trip_ask) and was fixed |

## Real bug (c)

**The stand-in checkout for Plan it for me was unreachable locally.** `gitaway/pages/__init__.py`: F-254 moved `partners` before `planforme` in `SCREENS`. Starlette serves the first matching
route, and partners' `GET /sandbox/{partner}/{click}` matched `/sandbox/plan-for-me/<order>` (partner = "plan-for-me"), so the page answered "Nothing here" (404) and a buyer on a local copy could
never pay (`tests_browser/test_plan_for_me.py`, 4 failures). Fix: `planforme` registers before `partners` (as before F-254), with a comment. New unit test, red first:
`tests/test_planforme_pages.py::test_on_a_local_copy_the_stand_in_checkout_is_its_own_page_not_a_partners_sandbox` (no unit test had ever read the stand-in page with a 200, which is why 3632 passed).
Production was not affected (the stand-in is local only), but the sale path locally was.

## Every test touched

| Test (tests_browser/) | Verdict | Why |
|---|---|---|
| test_workspace_js.py, all 10 tests | RETIRED, module deleted | drove the old `/plan` booking lanes (split view, tiles, ledger); `/plan` redirects to `/plan/ask` (F-254) |
| test_plan_search.py, 3 tests (6 params) | RETIRED, module deleted | drove `/plan` lanes (`ps-*`, "Plan this trip" on a guide's #todo card); only the words of a search remain (`pages/plan_search.py`); `/go/search-*` has unit tests (tests/test_partners.py) |
| test_launch_blockers.py::test_a_page_that_names_a_child_waits_for_the_tick | RETIRED, deleted | drove `/trip/publish` (the family's own publish editor, in `RETIRED`); nothing in v2 publishes a family trip |
| test_autopilot_look.py::test_m5_plan_lanes_swipe... | RETIRED, deleted | the lanes' scroll-snap and three columns; page retired |
| test_autopilot_look.py::test_m5_sandbox_and_partners_in_omxqua | RETIRED, repointed | opens `/go/hif1?...` (the offer's own link) instead of a lane's link; still checks the stand-in checkout's omxqua look |
| test_autopilot_look.py::test_m5_omxqua_on_phone_and_laptop | STALE | `/plan` now lands on `/plan/ask`, a v2 page where glass is allowed (D-610); the check keeps `/creators` pages; the touch test visits `/plan/ask` too |
| test_partner_flow.py (2) | RETIRED, repointed | followed a lane's "Book on" link and the `/partners` log (retired); now `/go/hif1`, the stand-in checkout, "Booked elsewhere", and the booking in `/trip/details` |
| test_brand_mark.py (4) | STALE | the retired pages left the page list (replaced by `/terms`, `/trip/details`, `/trips/import`); the cover's postcard (F-266) draws the same mark at 36px with its own ink: colours, font and weight are checked, size and ink are not |
| test_cover.py (2) | STALE | F-268, D-772: "San Diego" alone opens the matrix with a default window; a wish with no known place ("Narnia") still stays on the ask in its words |
| test_trip_ask.py::test_a_search_that_cannot_run... | STALE (+ a race of my own, fixed) | F-268: a place alone runs, so the unrunnable wish is one whose flex is out of range ("San Diego Dec 12 to 16 give or take 9 days" says "Say give or take 0 to 3 days"). My first version used "Dec 12 to 16" and passed alone but failed in the full run: typing it fired the place suggester ("We don't know that place yet.") against the Search click's server answer. A wish with a known place and a bad flex has one answer only; 3 reruns pass |
| test_creator_batch.py (2), test_creator_import.py (4) | STALE | F-262: the editor's heading is "The details of your guide"; the public page is a guide (day strip, `.g-nm` stops, a source tile, the hero picture), not the book |
| test_family_invite.py joins (2) | STALE | a joiner lands on `/trip/plan` (the cockpit redirects there) |
| test_family_invite.py::test_a_viewer_can_look_but_cannot_change_the_trip | RETIRED, repointed | the viewer's page is the v2 calendar: no `[data-add]`, a write to `/trip/plan/write` is a 403 and nothing is added |
| test_first_run.py (4) | RETIRED, repointed | `/forks` and its three cards are gone (D-761); the same ways in are checked from `/plan/ask` (ask, `#ak-import`), `/trips/import` (`#ti-build`) and `/guides` |
| test_morning.py::test_the_service_worker_shows_the_push... | STALE | the push's default and fallback address is `/trip/plan` (`morning.URL`, `sw.js`) |
| test_note_authors.py | RETIRED, repointed | the Notes tab is gone; two members talk in the Together drawer, and each message shows its writer's first name, one's own messages carry none |
| test_passkeys.py::test_no_face_id_card_on_help... | RETIRED, repointed | Help and the canvas are gone; no `#pk-card` on `/trip/plan` or `/plan/ask` |
| test_plan_for_me.py (4) | REAL BUG | stand-in checkout shadowed by partners' route (above); after the fix its "Open the trip" lands on `/trip/plan?trip=` (stale URL updated) |
| test_pwa.py (2) | RETIRED, repointed | the canvas and `/trip` redirects are not cached (the worker never keeps a redirect); the trip's page is `/trip/plan`, the manifest's start_url; same assertions (served offline, the offline page for an unvisited page, per-person caches) |
| test_trip_build.py::test_walk_the_whole_builder... | STALE | saving lands on `/trip/plan`, the calendar, titled with the trip |
| test_trip_build.py::test_the_first_run_welcome... | RETIRED, repointed | `/forks` welcome gone; `/plan/ask` offers `/trips/import`, and the import page offers `/trips/build` and the template box |
| test_trip_import.py (5) | RETIRED, repointed | the cockpit and canvas pages are gone; the saved trip is locked blocks (`a.ev.lock[href*=block=b-out]`) on `/trip/plan`, and `/trip/booking?block=b-out` holds the confirmation; the retired trip menu in the old top bar left the import-button test |
| test_weather_credit.py (4 became 3) | RETIRED, repointed | the `/plan` lanes and the `/forks` calendar are gone; the credit is `.wg a.fine` in the planning page's weather widget, one link, 48px on a phone and a touch tablet, no sideways scroll. The laptop test no longer asserts "under 48px": `v2plan.css` makes the link 3rem at every width. The forks test is folded in (same fixture, same trip) |
| test_web_pages.py: look (2) | STALE | the bar is Book, Plan, Guides (F-255); Family members is in the avatar menu |
| test_web_pages.py: many people, change role (2), details button (1) | STALE | joiner and `#ti-cal` land on `/trip/plan` |
| test_web_pages.py::test_the_matrix_offers_the_import_and_the_plan_page_offers_another_trip | RETIRED, repointed | the cockpit's "Plan another trip" is gone; the bar's Book from `/trip/plan` goes to `/plan/ask` |
| test_booked_calm_js.py | RETIRED, repointed | the phone Today card is gone; the locked calendar block must be tinted (not ink), carry one lock icon and have 4.5:1 text |

New: `tests/test_planforme_pages.py::test_on_a_local_copy_the_stand_in_checkout_is_its_own_page_not_a_partners_sandbox`.

## Left alone, for the main session

- `tests_browser/test_booked_calm_js.py` still defines `tint()` (unused now), a small leftover.
- Unit suite in random order (`pixi run pytest -q tests`, pytest-randomly on) errored 10 times in `tests/test_forget_person.py` setup ("table passes has 16 columns but 6 values were supplied"): the fixture's `CREATE TABLE IF NOT EXISTS passes` meets a real table when another test made the family's database first. It passes alone and in the deterministic order (`pixi run test`). Not touched here; a follow-up (an order-dependent fixture, not a product bug).
- 8 browser tests are skipped (they were before M5).

## Totals

Browser suite, one whole run (18m49s): 480 passed, 8 skipped, 1 failed (test_trip_ask's race above, fixed after the run; test_trip_ask.py and test_cover.py together rerun 39 passed), so 481 passed. Start was 70 failed, 431 passed; 19 deleted tests and 1 new unit test account for the rest.
Unit suite (`pixi run test`, deterministic order): 3633 passed (3632 on master plus the new stand-in test).
