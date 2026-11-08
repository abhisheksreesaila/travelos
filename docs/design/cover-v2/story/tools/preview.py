"""Render art.js pieces to PNGs for a quick look: preview.py sheet maya-sam | panel 01 ..."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
STORY = Path(__file__).resolve().parent.parent
kind, keys = sys.argv[1], sys.argv[2:]
html = """<!doctype html><html><body style="margin:0;background:#f3ecdf"><script src="%s"></script>
<div id=r style="width:1600px;height:900px"></div><script>
document.body.insertAdjacentHTML('afterbegin', ART.sprite);
</script></body></html>""" % (STORY / "art" / "art.js").as_uri()
tmp = STORY / "png" / "_preview.html"
tmp.write_text(html)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.goto(tmp.as_uri())
    for k in keys:
        src = "sheets" if kind == "sheet" else "panels"
        pg.evaluate("([s,k]) => { const r=document.getElementById('r'); r.innerHTML = ART[s][k]; r.firstChild.style.width='1600px'; r.firstChild.style.height='900px'; }", [src, k])
        pg.wait_for_timeout(150)
        pg.locator("#r").screenshot(path=f"/tmp/prev-{kind}-{k}.png")
        print("/tmp/prev-%s-%s.png" % (kind, k))
    b.close()
tmp.unlink()
