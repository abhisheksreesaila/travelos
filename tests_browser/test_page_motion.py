"""F-099: moving between screens is smooth. Same-site navigations run a short cross-document view transition (forward and back slide
opposite ways, nothing under reduced motion, no white flash), and a link starts loading on pointerdown so the service worker can answer
the tap from the fresh copy."""
import pytest

from tests_browser.helpers import PHONE

# records what the browser says about each page reveal, so a test can read the transition's types after a navigation
RECORD = "addEventListener('pagereveal', e => { setTimeout(() => { try { sessionStorage.setItem('vt', e.viewTransition ? [...e.viewTransition.types].sort().join(',') || 'plain' : 'none'); } catch (x) {} }, 0); });"


@pytest.fixture
def ctxs(browser):
    made = []

    def make(reduced="no-preference"):
        ctx = browser.new_context(viewport=PHONE, service_workers="allow", reduced_motion=reduced)
        ctx.set_default_timeout(8000)
        made.append(ctx)
        return ctx

    yield make
    for c in made:
        c.close()


def signed_in(ctx, base_url):
    ctx.request.post(f"{base_url}/signin", form={"email": "ari@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)


def controlled(page, base_url, path):
    page.goto(f"{base_url}{path}")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("navigator.serviceWorker.controller !== null")


def vt(page):
    return page.evaluate("sessionStorage.getItem('vt')")


def test_a_tab_switch_runs_a_view_transition_forward_and_back_runs_the_other_way(ctxs, base_url):
    ctx = ctxs()
    ctx.add_init_script(RECORD)
    signed_in(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/ask")
    page.click("#ph-tab-family")
    page.wait_for_url("**/trip/family")
    assert vt(page) == "ga-fwd"
    page.go_back()
    page.wait_for_url("**/trip/ask")
    assert vt(page) == "ga-back"


def test_nothing_animates_under_reduced_motion(ctxs, base_url):
    ctx = ctxs("reduce")
    ctx.add_init_script(RECORD)
    signed_in(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/ask")
    page.click("#ph-tab-family")
    page.wait_for_url("**/trip/family")
    assert vt(page) == "none"


def test_the_tab_bar_and_heading_are_held_still_and_the_page_never_flashes_white(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/ask")
    assert page.evaluate("getComputedStyle(document.querySelector('.ph-tabs')).viewTransitionName") == "cz-tabs"
    assert page.evaluate("getComputedStyle(document.querySelector('.tp-head')).viewTransitionName") == "ph-head"
    assert page.evaluate("getComputedStyle(document.documentElement).backgroundColor") == "rgb(255, 248, 238)"
    page.goto(f"{base_url}/plan")  # a page on the other theme, too
    assert page.evaluate("getComputedStyle(document.documentElement).backgroundColor") != "rgba(0, 0, 0, 0)"


def tap_then_navigate(page, selector, wait=400):
    page.locator(selector).dispatch_event("pointerdown")
    page.wait_for_timeout(wait)
    with page.expect_navigation() as nav:
        page.evaluate("s => document.querySelector(s).click()", selector)
    return nav.value


def test_a_tap_starts_loading_and_the_next_navigation_is_answered_from_the_prefetched_copy(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/ask")
    res = tap_then_navigate(page, "#ph-tab-family")
    assert res.headers.get("x-ga-prefetch") == "1"
    assert page.url.endswith("/trip/family")


def test_without_a_touch_the_navigation_is_not_prefetched(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/ask")
    with page.expect_navigation() as nav:
        page.evaluate("document.querySelector('#ph-tab-family').click()")
    assert nav.value.headers.get("x-ga-prefetch") is None


def test_a_prefetched_copy_is_used_once_and_goes_stale_after_a_few_seconds(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/ask")
    page.locator("#ph-tab-family").dispatch_event("pointerdown")
    page.wait_for_timeout(5600)
    with page.expect_navigation() as nav:
        page.evaluate("document.querySelector('#ph-tab-family').click()")
    assert nav.value.headers.get("x-ga-prefetch") is None


def test_zoom_links_new_tabs_downloads_and_sign_out_routes_are_never_prefetched(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/family")
    page.evaluate("""() => { const add = (id, attrs) => { const a = document.createElement('a'); a.id = id; a.textContent = id; Object.entries(attrs).forEach(([k, v]) => a.setAttribute(k, v)); document.body.appendChild(a); };
      add('zz', {href: '/trip/ask', 'data-zoom': 'in'}); add('blank', {href: '/trip/ask', target: '_blank'}); add('dl', {href: '/trip/ask', download: ''}); }""")
    for sel in ("#zz", "#blank", "#dl"):
        page.locator(sel).dispatch_event("pointerdown")
    page.wait_for_timeout(500)
    with page.expect_navigation() as nav:
        page.evaluate("location.assign('/trip/ask')")
    assert nav.value.headers.get("x-ga-prefetch") is None
    page.evaluate("() => { const a = document.createElement('a'); a.id = 'out'; a.href = '/signin?next=%2Ftrip'; a.textContent = 'out'; document.body.appendChild(a); }")
    page.locator("#out").dispatch_event("pointerdown")
    page.wait_for_timeout(500)
    with page.expect_navigation() as nav:
        page.evaluate("location.assign('/signin?next=%2Ftrip')")
    assert nav.value.headers.get("x-ga-prefetch") is None


def test_signing_out_drops_a_prefetched_page(ctxs, base_url):
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/ask")
    page.locator("#ph-tab-family").dispatch_event("pointerdown")
    page.wait_for_timeout(400)
    page.evaluate("fetch('/signout', {method: 'POST'}).then(r => r.status)")
    with page.expect_navigation() as nav:
        page.evaluate("document.querySelector('#ph-tab-family').click()")
    assert nav.value.headers.get("x-ga-prefetch") is None


STAMP = """addEventListener('click', () => { try { sessionStorage.setItem('t0', String(performance.timeOrigin + performance.now())); } catch (x) {} }, true);
addEventListener('pagereveal', e => { try { sessionStorage.setItem('reveal', String(performance.timeOrigin + performance.now()));
  setTimeout(() => { sessionStorage.setItem('vt2', e.viewTransition ? [...e.viewTransition.types].sort().join(',') : 'none'); }, 0); } catch (x) {} });"""


def test_a_tab_switch_on_a_warm_copy_reaches_the_new_page_within_150_ms_and_runs_the_transition(ctxs, base_url):
    ctx = ctxs()
    ctx.add_init_script(STAMP)
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/ask")
    tap_then_navigate(page, "#ph-tab-family")                      # pointerdown first, then the click 400 ms later
    page.wait_for_url("**/trip/family")
    page.wait_for_function("sessionStorage.getItem('vt2') !== null")
    ms = page.evaluate("Number(sessionStorage.getItem('reveal')) - Number(sessionStorage.getItem('t0'))")
    print(f"\nF099 tab switch, warm service-worker copy: click -> pagereveal {ms:.0f} ms")
    assert 0 <= ms < 150
    assert page.evaluate("sessionStorage.getItem('vt2')") == "ga-fwd"


def test_switching_between_today_and_family_opens_the_saved_copy_at_once_and_it_brings_itself_up_to_date(ctxs, base_url):
    """F-116: the captain felt a second's lag between Today and Family. A tab screen seen before opens from the saved copy (marked stale) while a fresh one is fetched;
    the Today tab goes straight back to the day last shown (no /trip redirect); the chat polls at once and the day revalidates, so a message sent meanwhile shows."""
    ctx = ctxs()
    signed_in(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url, "/trip/canvas?day=0")
    page.goto(f"{base_url}/trip/family")
    page.wait_for_selector("#ft-compose")
    assert page.locator("#ph-tab-today").get_attribute("href") == "/trip/canvas?day=0"
    page.locator("#ph-tab-today").click()
    page.wait_for_url("**/trip/canvas?day=0")
    page.wait_for_selector(".cz-view")
    assert page.evaluate("document.documentElement.hasAttribute('data-ga-stale')")
    with page.expect_request(lambda r: "since=" in r.url, timeout=4000):
        ctx.request.post(f"{base_url}/trip/family/message", form={"text": "Sent while away", "cid": "away1", "since": "0"}, headers={"X-Fragment": "1"})
        page.locator("#ph-tab-family").click()
        page.wait_for_url("**/trip/family")
    assert page.evaluate("document.documentElement.hasAttribute('data-ga-stale')")
    page.wait_for_selector("#ft-thread .ft-msg:has-text('Sent while away')")
