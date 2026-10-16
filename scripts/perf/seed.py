"""F-168: make the realistic trip on the measuring server (scripts/perf/serve.py) and save the signed-in browser state.
The trip is the browser tests' Universal + DCA trip (the Ask box with the canned model answer) plus a booked stay and five timed plans per day, added through the grid's own route.

    python scripts/perf/seed.py http://127.0.0.1:5020 /tmp/x/state.json
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from tests import canvas_samples as samples  # noqa: E402

PLANS = [("08:00", "09:00", "Breakfast at the hotel", "food"), ("12:30", "13:30", "Lunch", "food"), ("15:00", "16:30", "Pool time", "fun"),
         ("18:30", "20:00", "Dinner downtown", "food"), ("20:30", "21:30", "Evening walk", "fun")]


def main(base, state):
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        ctx.set_default_timeout(15000)
        ctx.request.post(f"{base}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base}/trip/add")
        page.locator("#ak-text").fill(samples.text())
        page.locator("#ak-go").click()
        page.locator('[data-q="park:0"] .ak-opt').nth(1).click()
        page.locator('[data-q="park:1"] .ak-opt').nth(3).click()
        page.locator("#ak-continue").click()
        page.locator("#ak-apply").click()
        page.wait_for_selector("#ak-done")
        page.goto(f"{base}/trip/canvas")
        page.wait_for_selector(".cz-view[data-level=week]")
        days = sorted({int(d) for d in page.eval_on_selector_all("a.cz-row-link[href*='day=']", "as => as.map(a => new URL(a.href).searchParams.get('day'))") if d})
        n = 0
        for d in days:
            for s, e, t, k in PLANS:
                h1, m1 = map(int, s.split(":")); h2, m2 = map(int, e.split(":"))
                r = page.request.post(f"{base}/trip/canvas/plan", headers={"X-Canvas": "1"}, max_redirects=0,      # the grid's own add (day_new.js)
                                      form={"op": "add", "day": str(d), "start": str(h1 * 60 + m1), "end": str(h2 * 60 + m2), "title": t, "kind": k, "next": f"/trip/canvas?day={d}"})
                n += r.ok
        ctx.storage_state(path=state)
        print(f"days {days}, {n} plans seeded")
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
