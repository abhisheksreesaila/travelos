# Lessons

<!-- One line per lesson, added when you correct Claude or a mistake gets caught:
- YYYY-MM-DD · the rule that prevents it, and why
Claude reads this at the start of each session. -->
- 2026-09-30 · Page CSS must load after tokens.css and base.css: build every page's <head> with `layout.styles(*extra)` (page() does). tests/test_shell.py checks every route, because a same-specificity rule in base.css silently beat page rules.
- 2026-09-30 · Developer worktrees can start on an old commit: every build brief must say "`git merge --ff-only master` first", and merges must check the combined tree, not just each branch.
- 2026-09-30 · Headless screenshots with --hide-scrollbars hid a sideways page scroll for two reviews: when verifying a page, also measure documentElement.scrollWidth vs clientWidth at 1440, 1280, 1000, 800, 390 and 320.
- 2026-09-30 · No text is cut off with an ellipsis in GitAway UI: labels wrap, shorten, or become icon + accessible name. Check headers and chips at 1280 and 1000, where columns are tightest. Exception: calendar blocks keep their true height (height is time); a short block fades its overflow and expands on hover/focus instead of growing.
- 2026-09-30 · Client-side state seeded at page load (e.g. which offer the split view opens) must follow later picks: test the "change it in the tiled view, then expand" path, not just a fresh page load. String-matching tests missed this in F-025.
- 2026-09-30 · Assert a price or total on its own element (e.g. `id="ws-total"`), never as a substring of the whole page: embedded data made `"$2,308" in html` pass for the wrong pick in F-015.
- 2026-09-30 · GitAway was built too large: the captain needed 75% browser zoom to see a full screen. Design and verify at 1440×900 and 1280×800 at 100% zoom: the main content of every screen must fit without scrolling.
- 2026-09-30 · Sizes are rem off one root (12px desktop and tablet, 16px phone; tokens.css). Never write px for a size; breakpoints scale too (a layout that switched at 1100 switches at 825). tests/test_scale.py enforces it.
- 2026-09-30 · Parallel workers collided on port 5002 and one killed another's browser: each worker brief names its own server port and browser debug port, and workers stop only processes they started (by PID, never by pattern).
