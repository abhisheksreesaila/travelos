"""F-044: the service worker serves a visited trip offline, never caches a POST or an auth route, keeps one person's
pages away from another, and serves a changed asset after a reload."""
import re

import pytest
from playwright.sync_api import Error as PlaywrightError

from tests_browser.helpers import PHONE

ALL_CACHED_URLS = """async () => {
  const out = [];
  for (const name of await caches.keys()) for (const r of await (await caches.open(name)).keys()) out.push(r.method + ' ' + new URL(r.url).pathname + new URL(r.url).search);
  return out;
}"""
PAGE_CACHES = "async () => (await caches.keys()).filter(n => n.startsWith('ga-pages-'))"


@pytest.fixture
def ctxs(browser):
    made = []

    def make():
        ctx = browser.new_context(viewport=PHONE, service_workers="allow")
        ctx.set_default_timeout(8000)
        made.append(ctx)
        return ctx

    yield make
    for c in made:
        c.set_offline(False)
        c.close()


def sign_in(ctx, base_url, who="ari"):
    ctx.request.post(f"{base_url}/signin", form={"email": f"{who}@example.com", "next": "/", "intent": "save"}, max_redirects=0)


def book_trip(ctx, base_url):
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)


def controlled(page, base_url, path="/community"):
    page.goto(f"{base_url}{path}")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("navigator.serviceWorker.controller !== null")


def goes_offline_ok(page, url):
    try:
        page.goto(url)
    except PlaywrightError:
        return None
    return page.locator("body").inner_text()


def test_a_booked_trip_calendar_is_served_offline_and_an_unvisited_page_gets_the_offline_page(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    book_trip(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    page.goto(f"{base_url}/calendar")
    online_text = page.locator("#main").inner_text()
    assert "Los Angeles" in online_text or "LA" in online_text
    ctx.set_offline(True)
    page.goto(f"{base_url}/calendar")
    assert page.locator("#main").inner_text() == online_text
    page.goto(f"{base_url}/never-visited")
    assert "offline" in page.locator("body").inner_text().lower()


def test_assets_come_from_the_cache_when_offline(ctxs, base_url):
    ctx = ctxs()
    page = ctx.new_page()
    controlled(page, base_url)
    href = page.evaluate("document.querySelector('link[href*=\"base.css\"]').href")
    assert "?v=" in href
    ctx.set_offline(True)
    assert page.evaluate("href => fetch(href).then(r => r.status)", href) == 200


def test_posts_and_auth_routes_never_end_up_in_any_cache(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    page.evaluate("fetch('/pay', {method: 'POST', body: new URLSearchParams({f: 'f1', h: 'h1', c: 'c1'})}).then(r => r.status)")
    page.evaluate("fetch('/signin', {method: 'POST', body: new URLSearchParams({email: 'ari@example.com', next: '/', intent: 'save'})}).then(r => r.status)")
    for path in ("/signin", "/signin?next=%2Fplan", "/login", "/logout", "/auth/callback"):
        page.goto(f"{base_url}{path}")
    page.goto(f"{base_url}/community")  # the worker is still busy being useful
    cached = page.evaluate(ALL_CACHED_URLS)
    assert cached, "the worker should have saved something"
    assert not [u for u in cached if not u.startswith("GET ")], cached
    assert not [u for u in cached if re.match(r"GET /(login|logout|signin|signout|auth|pay)\b", u)], cached
    ctx.set_offline(True)
    assert page.evaluate("fetch('/pay', {method: 'POST', body: new URLSearchParams({f: 'f1'})}).then(() => false, () => true)")


def test_a_changed_asset_is_served_after_a_reload(ctxs, base_url, monkeypatch):
    from gitaway import assetver
    real = assetver.file_hash
    changed = {"on": False}
    monkeypatch.setattr(assetver, "file_hash", lambda url: "c0ffee00" if changed["on"] and url.endswith("base.css") else real(url))
    ctx = ctxs()
    page = ctx.new_page()
    controlled(page, base_url)
    link = "document.querySelector('link[href*=\"base.css\"]').href"
    first = page.evaluate(link)
    assert first.endswith("?v=" + real("/assets/css/base.css"))
    changed["on"] = True  # the file "changed": same URL path, new content hash
    page.reload()
    second = page.evaluate(link)
    assert second.endswith("?v=c0ffee00") and second != first
    assert page.evaluate("href => fetch(href).then(r => r.status)", second) == 200
    assets = page.evaluate("async () => { const out = []; for (const n of await caches.keys()) if (n.startsWith('ga-assets-') || n.startsWith('ga-shell-')) for (const r of await (await caches.open(n)).keys()) out.push(r.url); return out; }")
    assert second in assets, "the new URL was fetched from the network and saved"


def test_signing_out_leaves_no_private_page_offline(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    book_trip(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    page.goto(f"{base_url}/calendar")
    assert page.evaluate(PAGE_CACHES)
    page.evaluate("fetch('/signout', {method: 'POST'}).then(r => r.status)")
    assert page.evaluate("caches.keys().then(k => k.length)") == 0
    ctx.set_offline(True)
    text = goes_offline_ok(page, f"{base_url}/calendar")
    assert text is None or "Ari" not in text and "Los Angeles" not in text


def test_a_different_person_never_sees_the_previous_persons_saved_pages(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url, "ari")
    book_trip(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    page.goto(f"{base_url}/calendar")
    ari_caches = page.evaluate(PAGE_CACHES)
    assert len(ari_caches) == 1
    sign_in(ctx, base_url, "sam")
    page.goto(f"{base_url}/community")  # the worker sees Sam's key and drops Ari's pages
    page.evaluate("new Promise(r => setTimeout(r, 300))")
    sam_caches = page.evaluate(PAGE_CACHES)
    assert len(sam_caches) == 1 and sam_caches != ari_caches
    ctx.set_offline(True)
    page.goto(f"{base_url}/calendar")  # Sam never opened it: the offline page, not Ari's trip
    body = page.locator("body").inner_text().lower()
    assert "offline" in body
