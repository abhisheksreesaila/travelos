# lisbon-48-hours (F-235)

The Planet D, "48 Hours in Lisbon, Itinerary" (https://theplanetd.com/48-hours-in-lisbon-itinerary/), recorded with `scripts/record_import_fixture.py` through the app's own robots check and safe fetcher:
`robots.txt`, `page.html`, `lead.jpg`, `meta.json`. Tests replay them (`tests/creator_import_support.recorded()`); nothing here is shown on a page.

**`answer.json` is NOT a recorded model answer.** The real model has not run on this post: no `ANTHROPIC_API_KEY` was set when this was built. It was written by hand from the page's text and goes through
the real `creatordraft.validate`. To replace it with the real thing, with a key set:

    ANTHROPIC_API_KEY=... pixi run probe-import https://theplanetd.com/48-hours-in-lisbon-itinerary/

then paste the printed JSON over `answer.json` (without `_note`) and run `pixi run pytest tests/test_creator_magic.py`.
