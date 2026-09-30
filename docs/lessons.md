# Lessons

<!-- One line per lesson, added when you correct Claude or a mistake gets caught:
- YYYY-MM-DD · the rule that prevents it, and why
Claude reads this at the start of each session. -->
- 2026-09-30 · Page CSS must load after tokens.css and base.css: build every page's <head> with `layout.styles(*extra)` (page() does). tests/test_shell.py checks every route, because a same-specificity rule in base.css silently beat page rules.
- 2026-09-30 · Developer worktrees can start on an old commit: every build brief must say "`git merge --ff-only master` first", and merges must check the combined tree, not just each branch.
