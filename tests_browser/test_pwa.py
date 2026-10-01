"""F-044: the service worker serves a visited page offline and falls back to the offline page for the rest."""
from tests_browser.helpers import PHONE


def _controlled(page):
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()  # a reload lets the freshly installed worker control the page
    page.wait_for_function("navigator.serviceWorker.controller !== null")


def _open(browser, base_url, path):
    ctx = browser.new_context(viewport=PHONE, service_workers="allow")
    ctx.set_default_timeout(8000)
    page = ctx.new_page()
    page.goto(f"{base_url}{path}")
    _controlled(page)
    return ctx, page


def test_a_visited_page_is_served_offline_and_an_unvisited_one_gets_the_offline_page(browser, base_url):
    ctx, page = _open(browser, base_url, "/discover")
    page.goto(f"{base_url}/creators")  # visited while online and controlled
    assert page.locator("#main").count() == 1
    ctx.set_offline(True)
    page.goto(f"{base_url}/discover")
    assert "GitAway" in page.title() and page.locator("#main").count() == 1
    page.goto(f"{base_url}/creators")
    assert page.locator("#main").count() == 1
    page.goto(f"{base_url}/never-visited")
    assert "offline" in page.locator("body").inner_text().lower()
    ctx.set_offline(False)
    ctx.close()


def test_assets_come_from_the_cache_when_offline(browser, base_url):
    ctx, page = _open(browser, base_url, "/discover")
    ctx.set_offline(True)
    assert page.evaluate("fetch('/assets/css/base.css').then(r => r.status)") == 200
    ctx.set_offline(False)
    ctx.close()


def test_a_post_is_never_answered_from_the_cache(browser, base_url):
    ctx, page = _open(browser, base_url, "/discover")
    ctx.set_offline(True)
    assert page.evaluate("fetch('/signout', {method: 'POST'}).then(() => false, () => true)"), "an offline POST must fail"
    ctx.set_offline(False)
    ctx.close()
