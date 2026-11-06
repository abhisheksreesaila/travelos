import re, sys
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:5193"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.request.post(f"{BASE}/signin", form={"email": "probe@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/plan-for-me")
    pg.fill("#pf-where", "San Diego")
    pg.evaluate("""() => { document.getElementById('pf-start').value='2027-05-10'; document.getElementById('pf-end').value='2027-05-12'; }""")
    pg.click("#pf-go")
    pg.wait_for_url(re.compile("sandbox"))
    for sel in ("#pf-standin-pay", ".pf-back"):
        print(sel, pg.evaluate("sel => { const e = document.querySelector(sel); const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return [r.height, s.minHeight, s.display, document.documentElement.className.slice(0,40), getComputedStyle(document.querySelector('.pf')).getPropertyValue('--pf-tap')] }", sel))
    print(pg.evaluate("[...document.styleSheets].map(s => s.href).filter(Boolean).map(h => h.split('/').pop())"))
    b.close()
