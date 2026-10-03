"""F-062: signing out is instant. The sign-out response must not ask the browser to clear its HTTP cache (slow), yet the previous
family's saved pages and storage are still gone for the next person on the device."""
import time

import pytest
from playwright.sync_api import Error as PlaywrightError

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_pwa import PAGE_CACHES, book_trip, controlled


def sign_in(ctx, base_url):
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)

THRESHOLD_SECONDS = 1.0  # the ticket: back on the landing within about a second


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_pressing_sign_out_reaches_the_landing_fast_and_forgets_the_family(browser, base_url, viewport):
    ctx = browser.new_context(viewport=viewport, service_workers="allow")
    ctx.set_default_timeout(8000)
    try:
        sign_in(ctx, base_url)
        book_trip(ctx, base_url)
        page = ctx.new_page()
        controlled(page, base_url)
        page.goto(f"{base_url}/calendar")
        assert page.evaluate(PAGE_CACHES), "the family's pages were saved"
        page.goto(f"{base_url}/community")  # a page with the site header (the calendar has its own)
        page.evaluate("localStorage.setItem('ga-test', 'previous family')")
        start = time.perf_counter()
        page.locator("button.ga-signout").first.click()
        page.wait_for_url(f"{base_url}/")
        page.wait_for_load_state("load")
        elapsed = time.perf_counter() - start
        print(f"\nsign-out to landing loaded ({viewport['width']}px): {elapsed:.3f}s")
        assert elapsed < THRESHOLD_SECONDS
        page.wait_for_function("caches.keys().then(k => k.filter(n => n.startsWith('ga-pages-')).length === 0)")
        assert page.evaluate(PAGE_CACHES) == []
        assert page.evaluate("localStorage.getItem('ga-test')") is None
        # the next person on the device is offline: the previous family's calendar is not served from any cache
        ctx.set_offline(True)
        try:
            page.goto(f"{base_url}/calendar")
        except PlaywrightError:
            shown = ""  # the browser has nothing to show
        else:
            shown = page.content()  # the worker's offline page at most
        ctx.set_offline(False)
        assert "LA with the kids" not in shown and 'name="ga-user"' not in shown
    finally:
        ctx.close()


@pytest.mark.parametrize("sw", ["allow", "block"])
@pytest.mark.parametrize("offline", [False, True], ids=["online", "offline"])
def test_back_after_sign_out_never_shows_the_previous_persons_pages(browser, base_url, sw, offline):
    ctx = browser.new_context(viewport=DESKTOP, service_workers=sw)
    ctx.set_default_timeout(8000)
    try:
        sign_in(ctx, base_url)
        book_trip(ctx, base_url)
        page = ctx.new_page()
        if sw == "allow":
            controlled(page, base_url)
        page.goto(f"{base_url}/calendar")
        page.goto(f"{base_url}/community")
        page.locator("button.ga-signout").first.click()
        page.wait_for_url(f"{base_url}/")
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        if offline:
            ctx.set_offline(True)
        for _ in range(2):
            try:
                page.go_back()
                page.wait_for_load_state("load")
            except PlaywrightError:
                continue  # offline and nothing cached: nothing is shown, which is the point
            html = page.content()
            assert 'name="ga-user"' not in html and "Sign out" not in html and "LA with the kids" not in html, page.url
    finally:
        ctx.set_offline(False)
        ctx.close()
