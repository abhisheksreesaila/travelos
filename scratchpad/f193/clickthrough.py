"""F-193 click-through on the running dev server (port 5193, local stand-in checkout, no AI key so the sample builder stands in), phone width. Saves docs/report/f193-live-*.png."""
import re
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:5193"
OUT = Path("docs/report")
PHONE = {"width": 390, "height": 844}


def label(d): return f"{d:%A}, {d:%B} {d.day},"


def shot(pg, name):
    pg.wait_for_timeout(700)
    pg.screenshot(path=str(OUT / f"f193-live-{name}.png"), full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.set_default_timeout(20000)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/")
    card = pg.locator("#plan-for-me")
    card.scroll_into_view_if_needed()
    shot(pg, "1-landing")
    card.locator("#plan-for-me-go").click()
    expect(pg.locator("h1")).to_contain_text("Plan it for")
    pg.fill("#pf-where", "Disneyland, California")
    leave = date.today() + timedelta(days=60)
    home = leave + timedelta(days=3)
    pg.get_by_role("button", name=re.compile("^From:")).click()
    dlg = pg.get_by_role("dialog")
    for d in (leave, home):
        for _ in range(14):
            if dlg.get_by_role("button", name=re.compile("^" + label(d))).count(): break
            dlg.get_by_role("button", name="Next month").click()
        dlg.get_by_role("button", name=re.compile("^" + label(d))).click()
    pg.get_by_role("button", name="Done").click()
    pg.fill("#pf-home", "sfo")
    pg.get_by_role("button", name="More adults").click()
    for _ in range(2): pg.get_by_role("button", name="More kids").click()
    pg.evaluate("""() => { for (const [id, v] of [['pf-k1', '3'], ['pf-k2', '8']]) { const s = document.getElementById(id); s.value = v; s.dispatchEvent(new Event('change', {bubbles: true})); } }""")
    pg.locator("input[name=pace][value=relaxed]").click()
    pg.locator("input[name=budget][value=comfortable]").click()
    pg.fill("#pf-must", "Space Mountain, and a quiet beach morning")
    shot(pg, "2-intake-filled")
    pg.click("#pf-go")
    expect(pg).to_have_url(re.compile("/signin"))
    shot(pg, "3-sign-in")
    pg.fill("input[name=email]", "live.family@example.com")
    pg.click("form button[type=submit]")
    expect(pg.locator("#pf-where")).to_have_value("Disneyland, California")
    expect(pg.locator("#pf-go")).to_contain_text("Plan it for me · $29")
    shot(pg, "4-back-answers-kept")
    pg.click("#pf-go")
    expect(pg.locator("#pf-standin-pay")).to_be_visible()
    shot(pg, "5-stand-in-checkout")
    pg.click("#pf-standin-pay")
    pg.wait_for_url(re.compile(r"/plan-for-me/[0-9a-f]{16}$"))
    shot(pg, "6-after-pay")
    expect(pg.locator("#pf-title")).to_have_text("Your trip is ready", timeout=30000)
    shot(pg, "7-ready")
    pg.click("#pf-open")
    expect(pg).to_have_url(re.compile(r"/trip\?trip="))
    shot(pg, "8-trip")
    print("done", pg.url)
    b.close()
