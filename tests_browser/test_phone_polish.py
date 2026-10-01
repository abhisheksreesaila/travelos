"""F-034 / F-036: phone text floor and touch targets, wrapping tags, and the pop-in that must not widen the page."""
import pytest

from tests_browser.helpers import PHONE

SMALL_TEXT = """() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const e = n.parentElement; if (!n.nodeValue.trim() || !e || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(e.tagName)) continue;
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || (!r.width && !r.height)) continue;
    if (parseFloat(cs.fontSize) < 12.95) out.push(e.className + ' ' + cs.fontSize + ' ' + n.nodeValue.trim().slice(0, 20)); }
  return out; }"""

SMALL_CONTROLS = """() => [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]')]
  .filter(e => { const r = e.getBoundingClientRect(); return !e.closest('[hidden]') && !e.classList.contains('sr-only') && getComputedStyle(e).display !== 'none'
    && getComputedStyle(e).visibility !== 'hidden' && r.width && r.height && (r.width < 43.5 || r.height < 43.5); })
  .map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))"""

OVERFLOW = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


@pytest.fixture
def phone_page(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    ctx.set_default_timeout(5000)
    page = ctx.new_page()
    page.request.post(f"{base_url}/signin", form={"traveler": "ari", "next": "/", "intent": "save"}, max_redirects=0)
    page.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    yield page
    ctx.close()


@pytest.mark.parametrize("path", ["/plan", "/calendar", "/calendar?demo=long"])
def test_phone_has_no_small_text_small_controls_or_sideways_scroll(phone_page, base_url, path):
    phone_page.goto(base_url + path)
    phone_page.wait_for_load_state("networkidle")
    assert phone_page.evaluate(SMALL_TEXT) == []
    assert phone_page.evaluate(SMALL_CONTROLS) == []
    assert phone_page.evaluate(OVERFLOW) == 0


def test_stay_tags_wrap_inside_their_card_at_1000(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1000, "height": 800}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(base_url + "/plan")
    clipped = page.evaluate("""() => [...document.querySelectorAll('.ws-tags')].flatMap(t => {
        const r = t.getBoundingClientRect(); return [...t.children].filter(c => { const q = c.getBoundingClientRect();
        return q.right > r.right + 1 || q.bottom > r.bottom + 1; }).map(c => c.textContent); })""")
    ctx.close()
    assert clipped == []


@pytest.mark.parametrize("path", ["/", "/start"])
@pytest.mark.parametrize("width", [1000, 800, 390])
def test_pop_in_never_widens_the_page(browser, base_url, path, width):
    """Animations on (no reduced motion): sample the page width on every frame from the first paint."""
    ctx = browser.new_context(viewport={"width": width, "height": 800})
    page = ctx.new_page()
    page.add_init_script("""window.__maxOver = 0; const tick = () => { const d = document.documentElement;
        if (d) window.__maxOver = Math.max(window.__maxOver, d.scrollWidth - d.clientWidth); requestAnimationFrame(tick); }; tick();""")
    page.goto(base_url + path)
    page.wait_for_timeout(1500)  # the pop-in is 0.4s plus up to 0.4s of stagger
    over = page.evaluate("window.__maxOver")
    ctx.close()
    assert over == 0
