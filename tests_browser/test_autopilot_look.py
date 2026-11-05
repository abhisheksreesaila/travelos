"""Autopilot contract M5 (GOAL.md): omxqua Travel · Coast, touch first. Written before the work; never edited to pass."""
import re

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "d=2027-03-05&r=2027-03-09&a=2"


def _creator(page, base_url):
    page.goto(f"{base_url}/creators")
    hrefs = page.eval_on_selector_all("a[href^='/creators/']", "els => els.map(e => e.getAttribute('href'))")
    return next(h for h in hrefs if h.rsplit("/", 1)[-1] not in ("draft", "finish", "done"))


def _pages(page, base_url):
    yield f"/plan?to=hi&{TRIP}"
    yield "/creators"
    yield _creator(page, base_url)


def _omxqua(page):
    return page.evaluate("""() => {
      const root = document.documentElement, body = document.body;
      const fam = root.classList.contains('ul-family-travel') || body.classList.contains('ul-family-travel');
      const tok = getComputedStyle(root).getPropertyValue('--ul-accent').trim() || getComputedStyle(body).getPropertyValue('--ul-accent').trim();
      const blur = [...document.querySelectorAll('*')].some(e => { const s = getComputedStyle(e); return (s.backdropFilter && s.backdropFilter !== 'none') || (s.filter || '').includes('blur'); });
      return {fam, tok, blur};
    }""")


def test_m5_omxqua_on_phone_and_laptop(browser, base_url):
    for vp in (PHONE, DESKTOP):
        ctx = browser.new_context(viewport=vp, has_touch=vp is PHONE)
        page = ctx.new_page()
        for path in list(_pages(page, base_url)):
            page.goto(base_url + path)
            look = _omxqua(page)
            assert look["fam"], f"{path}: ul-family-travel root"
            assert look["tok"], f"{path}: --ul-accent token"
            assert not look["blur"], f"{path}: no glass or blur"
        ctx.close()


def test_m5_phone_touch_targets_and_no_sideways_scroll(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    for path in list(_pages(page, base_url)):
        page.goto(base_url + path)
        wide = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert wide <= 1, f"{path}: sideways scroll {wide}px"
        small = page.evaluate("""() => [...document.querySelectorAll('main button, main .btn, main a.btn, main [role=button]')]
            .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 40; })
            .map(e => (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 30))""")
        assert not small, f"{path}: buttons under 40px tall: {small}"
    ctx.close()


def test_m5_plan_lanes_swipe_on_phone_and_sit_side_by_side_on_laptop(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan?to=sd&{TRIP}")
    snap = page.evaluate("() => [...document.querySelectorAll('*')].some(e => getComputedStyle(e).scrollSnapType.includes('x'))")
    assert snap, "phone lanes swipe sideways with scroll-snap"
    ctx.close()
    ctx = browser.new_context(viewport=DESKTOP)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan?to=sd&{TRIP}")
    tops = page.evaluate("""() => [...document.querySelectorAll('a[href^="/go/"]')].slice(0, 200)
        .map(a => a.closest('section, [data-lane], .lane, .pane')).filter(Boolean)
        .filter((v, i, arr) => arr.indexOf(v) === i).map(e => Math.round(e.getBoundingClientRect().top))""")
    assert len(tops) >= 3 and len(set(tops[:3])) == 1, f"three lanes side by side at 1440px: {tops}"
    ctx.close()


def test_m5_sandbox_and_partners_in_omxqua(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan?to=nyc&{TRIP}")
    href = page.get_attribute("a[href^='/go/']", "href")
    page.goto(base_url + href)
    assert re.search(r"/sandbox/", page.url)
    look = _omxqua(page)
    assert look["fam"] and look["tok"] and not look["blur"]
    ctx.close()
