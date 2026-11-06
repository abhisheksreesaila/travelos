"""F-193 Plan it for me, in a real browser at phone (390) and laptop (1440) width: the whole thing a stranger does. They open the intake signed out, fill it in with the app's own pickers,
meet sign-in (their answers survive it), pay at the local stand-in checkout, watch the order page go from paid to ready on its own while the worker builds the trip with a fake Claude,
and open the trip on their calendar. No sideways scroll, controls at least 40px tall, the omxqua look. The app and its worker run in this process.
Set F193_SHOTS=1 to save screenshots to docs/report/f193-*.png."""
import os
import re
from datetime import timedelta
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, catalog
from tests.creator_import_support import Model
from tests.test_planforme_build import ANSWER
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]


def shot(page, name):
    if os.getenv("F193_SHOTS"):
        page.wait_for_timeout(700)      # let the page-change motion settle
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f193-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector):
    """The visible controls matching `selector` that are shorter than 40px (a clipped native control behind a dressed picker is not one)."""
    return page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
        return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && r.height < 40; }).map(e => (e.getAttribute('aria-label') || e.name || e.id || e.textContent.trim()).slice(0, 40) + ' ' + Math.round(e.getBoundingClientRect().height))""", selector)


def day_label(d):
    return f"{d:%A}, {d:%B} {d.day}"


CONTROLS = "#pf button, #pf .btn, #pf .pf-pill, #pf input[type=text], #pf textarea, #pf [role=button], #pf a.pf-link"


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(ANSWER, usage=(6000, 1500)))
    yield


@pytest.fixture
def stranger(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(20000)
        contexts.append(ctx)
        return ctx

    yield make
    for c in contexts:
        c.close()


def pick_dates(page, leave, home):
    page.get_by_role("button", name=re.compile("^From:")).click()
    dialog = page.get_by_role("dialog")
    for day in (leave, home):
        for _ in range(14):      # the picker opens on the month of "today" and shows one month at a time
            if dialog.get_by_role("button", name=re.compile("^" + day_label(day) + ",")).count():
                break
            dialog.get_by_role("button", name="Next month").click()
        dialog.get_by_role("button", name=re.compile("^" + day_label(day) + ",")).click()
    page.get_by_role("button", name="Done").click()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_stranger_fills_the_intake_signs_in_pays_and_opens_their_trip(setup, stranger, base_url, viewport):
    w = viewport["width"]
    ctx = stranger(viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan-for-me")
    expect(page.locator("h1")).to_contain_text("Plan it for me")
    expect(page.locator("#pf-price")).to_have_text("$29 once")
    expect(page.locator("#pf-promise")).to_have_text("Not useful? Reply within 7 days for a full refund.")
    expect(page.locator("#pf-go")).to_have_text("Continue")
    assert overflow(page) <= 1
    assert not too_small(page, CONTROLS), too_small(page, CONTROLS)
    shot(page, f"intake-{w}")

    leave = catalog.today() + timedelta(days=75)
    home = leave + timedelta(days=3)
    page.fill("#pf-where", "Disneyland, California")
    pick_dates(page, leave, home)
    assert page.input_value("#pf-start") == leave.isoformat() and page.input_value("#pf-end") == home.isoformat()
    page.fill("#pf-home", "sfo")
    page.get_by_role("button", name="More kids").click()
    page.get_by_role("button", name="More kids").click()
    expect(page.locator("#pf-kids .pf-kid:not([hidden])")).to_have_count(2)
    page.evaluate("""() => { for (const [id, v] of [['pf-k1', '4'], ['pf-k2', '7']]) { const s = document.getElementById(id); s.value = v; s.dispatchEvent(new Event('change', {bubbles: true})); } }""")
    page.locator("input[name=pace][value=relaxed]").click()      # the radio fills its pill, so a finger on the pill is a tap on it
    page.fill("#pf-must", "Space Mountain and a quiet beach morning")
    assert overflow(page) <= 1
    assert not too_small(page, CONTROLS), too_small(page, CONTROLS)
    shot(page, f"filled-{w}")

    page.click("#pf-go")      # signed out: sign-in first, the answers are kept in this browser
    expect(page).to_have_url(re.compile(r"/signin\?next=%2Fplan-for-me|/signin\?next=/plan-for-me"))
    page.fill("input[name=email]", "family.rivera@example.com")
    page.click("form button[type=submit]")
    expect(page).to_have_url(re.compile(r"/plan-for-me$"))
    expect(page.locator("#pf-where")).to_have_value("Disneyland, California")
    assert page.input_value("#pf-start") == leave.isoformat() and page.input_value("#pf-home") == "sfo"      # shown in capitals, sent as typed, the server makes it SFO
    expect(page.locator("#pf-must")).to_have_value("Space Mountain and a quiet beach morning")
    expect(page.locator("#pf-kids .pf-kid:not([hidden])")).to_have_count(2)
    expect(page.locator("#pf-go")).to_contain_text("Plan it for me · $29")
    shot(page, f"signed-in-{w}")

    page.click("#pf-go")
    expect(page.locator("h1")).to_have_text("Pay for Plan it for me")
    expect(page.locator("#pf-standin-pay")).to_have_text("Pay $29 (simulated)")
    assert overflow(page) <= 1 and not too_small(page, CONTROLS)
    shot(page, f"checkout-{w}")
    page.click("#pf-standin-pay")

    expect(page.locator("#pf-title")).to_have_text("Your trip is ready", timeout=20000)      # the page reloads itself when the status changes
    expect(page.locator("#pf-open")).to_be_visible()
    expect(page.locator("#pf-promise")).to_have_text("Not useful? Reply within 7 days for a full refund.")
    expect(page.locator("#pf-go-flight")).to_be_visible()
    assert overflow(page) <= 1 and not too_small(page, CONTROLS), too_small(page, CONTROLS)
    shot(page, f"ready-{w}")

    page.click("#pf-open")
    expect(page).to_have_url(re.compile(r"/trip\?trip="))
    expect(page.get_by_text("Check in and rest").first).to_be_visible()
    assert overflow(page) <= 1
    shot(page, f"trip-{w}")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_mistake_is_said_on_the_field_and_the_order_page_waits_without_a_payment(setup, stranger, base_url, viewport):
    ctx = stranger(viewport)
    ctx.request.post(f"{base_url}/signin", form={"email": "family.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan-for-me")
    expect(page.locator("#pf-go")).to_contain_text("Plan it for me · $29")
    page.click("#pf-go")
    expect(page.locator("#pf-err-where")).to_have_text("Where you are going is needed.")
    expect(page.locator("#pf-where")).to_have_attribute("aria-invalid", "true")
    assert overflow(page) <= 1
    shot(page, f"mistakes-{viewport['width']}")
    page.fill("#pf-where", "San Diego")
    leave = catalog.today() + timedelta(days=60)
    pick_dates(page, leave, leave + timedelta(days=2))
    page.click("#pf-go")
    expect(page.locator("h1")).to_have_text("Pay for Plan it for me")
    page.click("text=Back")      # the buyer changes their mind: the order waits, unpaid
    expect(page.locator("#pf-title")).to_have_text("Almost there")
    expect(page.locator("#pf-pay")).to_have_text("Pay $29")
    assert overflow(page) <= 1 and not too_small(page, CONTROLS)
    shot(page, f"waiting-{viewport['width']}")


def test_a_creators_trip_leads_to_the_intake_started_from_it(setup, stranger, base_url):
    from tests.live_trips import live_trip
    row, _, _ = live_trip()
    page = stranger(PHONE).new_page()
    page.goto(f"{base_url}/trips/{row['slug']}")
    card = page.locator("#plan-for-me")
    expect(card.locator("h2")).to_have_text("Want this trip built around your family?")
    card.scroll_into_view_if_needed()
    shot(page, "card-390")
    assert overflow(page) <= 1 and not too_small(page, "#plan-for-me .btn")
    card.locator("#plan-for-me-go").click()
    expect(page.locator("#pf-where")).to_have_value("Los Angeles, California")
    expect(page.locator("#pf-like")).to_have_text("Starting from “Three easy days in Santa Monica”.")


def test_the_signed_out_landing_has_the_card(setup, stranger, base_url):
    page = stranger(PHONE).new_page()
    page.goto(base_url)
    card = page.locator("#plan-for-me")
    expect(card.locator("h2")).to_have_text("Rather not plan it yourself?")
    card.scroll_into_view_if_needed()
    assert overflow(page) <= 1 and not too_small(page, "#plan-for-me .btn")
    shot(page, "landing-390")
    card.locator("#plan-for-me-go").click()
    expect(page).to_have_url(re.compile(r"/plan-for-me$"))
