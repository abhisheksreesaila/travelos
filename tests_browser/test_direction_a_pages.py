"""F-200: Direction A on every main page, in a real browser at 390 and 1440, in light and dark: no sideways scroll, every phone tap target at least 48px,
running text at least 16px on the phone (fine print 14, all-caps labels 13, nothing smaller), every piece of text at least 4.5:1 against what is behind it,
no glass or blur anywhere, and the one "Early preview" label in the shell. Dark follows the system (`color_scheme`); tests_browser/look.py says how each thing is measured."""
import pytest
from playwright.sync_api import expect

from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

TRIP = "d=2027-03-05&r=2027-03-09&a=2"
SIGNED_OUT = (("landing", "/"), ("sign-in", "/signin"), ("creators", "/creators"), ("for creators", "/for-creators"), ("plan for me", "/plan-for-me"))
SIGNED_IN = (("matrix", "/plan/matrix"), ("plan", f"/plan?to=la&{TRIP}"), ("trip canvas", "/trip/canvas?day=1"), ("family chat", "/trip/family"), ("family", "/family"),
             ("ask", "/trip/ask"), ("book", "/trip/book"))
TABLET = {"width": 900, "height": 1000}      # between the phone and the laptop layouts (the tablet keeps the old header; 12px root)
OWNED_ELSEWHERE = {}      # (the signed-out landing was F-206's to finish; since the merge the cover meets the whole audit)


def context(browser, viewport, mode):
    phone = viewport is PHONE
    ctx = browser.new_context(viewport=viewport, color_scheme=mode, reduced_motion="reduce", has_touch=phone, is_mobile=phone)
    ctx.set_default_timeout(15000)
    return ctx


def published(ctx, base_url):
    """Sign Ari in with the imported LA trip and a plan, publish it, and return the creator trip's address."""
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
    ctx.request.post(f"{base_url}/trip/plans", form={"id": "a1", "day": "1", "start": "10:00", "title": "Rope drop at the park", "kind": "fun"}, max_redirects=0)
    ctx.request.post(f"{base_url}/trip/publish/save", form={"title": "Our Disneyland week", "name": "Ari Rivera", "tip": "Bring a poncho for the water rides."}, max_redirects=0)
    ctx.request.post(f"{base_url}/trip/publish", form={"names_ok": "1"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/publish?live=1")
    href = page.get_attribute("#pb-view", "href")
    page.close()
    assert href and href.startswith("/trips/"), "the trip was published"
    return href


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, TABLET, DESKTOP], ids=["390", "900", "1440"])
def test_every_main_page_reads_fits_and_is_easy_to_tap(browser, base_url, viewport, mode):
    signed_in, signed_out = context(browser, viewport, mode), context(browser, viewport, mode)
    try:
        trip = published(signed_in, base_url)
        problems = []
        for ctx, (name, path) in [(signed_out, p) for p in (*SIGNED_OUT, ("creator trip", trip))] + [(signed_in, p) for p in SIGNED_IN]:
            page = ctx.new_page()
            page.goto(base_url + path, wait_until="networkidle")
            seen = audit(page)
            labels = page.evaluate("() => [...document.querySelectorAll('.ga-preview-pill')].filter(e => e.getClientRects().length && getComputedStyle(e).visibility === 'visible').length")
            page.close()
            if labels != 1:
                problems.append(f"{name}: {labels} Early preview labels on screen (one, in the shell)")
            if seen["wide"] > 1:
                problems.append(f"{name}: scrolls sideways by {seen['wide']}px")
            for key, what in (("small", "tap targets under 48px"), ("tiny", "text under the type scale"), ("low", "text under 4.5:1"), ("glass", "glass or blur")):
                if seen[key] and key not in OWNED_ELSEWHERE.get(name, ()):
                    problems.append(f"{name}: {len(seen[key])} {what}: {seen[key][:6]}")
        assert not problems, "\n".join(problems)
    finally:
        signed_in.close()
        signed_out.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_early_preview_label_opens_its_line_and_esc_closes_it(browser, base_url, viewport):
    signed_in, signed_out = context(browser, viewport, "light"), context(browser, viewport, "light")
    try:
        published(signed_in, base_url)
        for ctx, path in ((signed_out, "/creators"), (signed_out, "/signin?next=%2Fstart"), (signed_out, f"/plan?to=la&{TRIP}"), (signed_in, "/trip/canvas?day=1"), (signed_in, "/trip/family")):
            page = ctx.new_page()
            page.goto(base_url + path, wait_until="networkidle")
            label = page.locator(".ga-preview-sum:visible")
            line = page.locator(".ga-preview[open] .ga-preview-pop")
            label.click()
            expect(line).to_be_visible()
            expect(line).to_have_text("GitAway is new. Things will change; tell us what breaks.")
            box = line.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"], box      # the line stays on the screen
            page.keyboard.press("Escape")
            expect(page.locator(".ga-preview[open]")).to_have_count(0)
            page.close()
    finally:
        signed_in.close()
        signed_out.close()


CANVAS = "getComputedStyle(document.body).backgroundColor"


def test_light_by_default_and_the_button_switches_to_dark_and_is_remembered_on_this_device(browser, base_url):
    """D-460: light whatever the system says; one button turns dark on and off, remembered on this device before the first paint."""
    ctx = context(browser, DESKTOP, "dark")
    try:
        page = ctx.new_page()
        page.goto(f"{base_url}/privacy")
        toggle = page.locator(".ga-footer [data-mode-toggle]")
        assert page.evaluate(CANVAS) == "rgb(242, 242, 245)"                              # the system says dark; the site is light
        assert toggle.get_attribute("aria-pressed") == "false"
        toggle.click()
        assert page.evaluate(CANVAS) == "rgb(0, 0, 0)" and page.evaluate("document.documentElement.dataset.mode") == "dark"
        assert toggle.get_attribute("aria-pressed") == "true"
        assert page.locator('meta[name="theme-color"]').first.get_attribute("content") == "#000000"     # the browser bar follows
        page.goto(f"{base_url}/creators")                                                   # another page: still dark, chosen before the first paint
        assert page.evaluate(CANVAS) == "rgb(0, 0, 0)"
        page.emulate_media(color_scheme="light")                                            # the system changes its mind; the person's choice stays
        page.reload()
        assert page.evaluate(CANVAS) == "rgb(0, 0, 0)"
        page.locator(".ga-footer [data-mode-toggle]").click()                               # and back
        assert page.evaluate(CANVAS) == "rgb(242, 242, 245)" and page.evaluate("document.documentElement.dataset.mode") == "light"
    finally:
        ctx.close()


def test_on_a_phone_the_footer_is_short_and_keeps_the_button(browser, base_url):
    ctx = context(browser, PHONE, "light")
    try:
        page = ctx.new_page()
        page.goto(f"{base_url}/privacy")
        assert page.locator(".ga-footer [data-mode-toggle]").is_visible()                 # D-460: no Auto any more, so the phone has the button too
        assert page.locator(".ga-footer > .ga-fine").bounding_box()["height"] < 80       # the fine print is its own lines, not 18rem of empty column
    finally:
        ctx.close()
