"""Screenshot the storyboard: png/storyboard.png (1440 wide, full page), png/panel-NN.png and png/sheet-*.png (each
frame cropped), png/storyboard-phone.png (390 wide). Prints any speech bubble that overlaps a face or leaves its frame.
Run: cd travelos-autopilot && pixi run python docs/design/cover-v2/story/tools/shoot.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

STORY = Path(__file__).resolve().parent.parent
OUT = STORY / "png"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    errors = []
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.on("requestfailed", lambda r: errors.append("failed: " + r.url))
    pg.goto((STORY / "index.html").as_uri())
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(400)
    OUT.mkdir(exist_ok=True)
    pg.screenshot(path=str(OUT / "storyboard.png"), full_page=True)
    hi = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    hi.goto((STORY / "index.html").as_uri()); hi.wait_for_load_state("networkidle"); hi.wait_for_timeout(400)
    for i in range(1, 14):
        hi.locator(f"#p{i:02d} .frame").screenshot(path=str(OUT / f"panel-{i:02d}.png"))
    for k in ("maya-sam", "rosa-tomas"):
        hi.locator(f'[data-sheet="{k}"]').screenshot(path=str(OUT / f"sheet-{k}.png"))
    bad = [q for q in pg.evaluate("window.BUBBLE_QA") if q["outside"] or [f for f in q["faces"]]]
    print("bubbles checked:", len(pg.evaluate("window.BUBBLE_QA")), "problems:", bad or "none")
    ph = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ph.goto((STORY / "index.html").as_uri()); ph.wait_for_load_state("networkidle"); ph.wait_for_timeout(400)
    ph.screenshot(path=str(OUT / "storyboard-phone.png"), full_page=True)
    print("phone scroll width:", ph.evaluate("document.documentElement.scrollWidth"))
    print("errors:", errors or "none")
    b.close()
