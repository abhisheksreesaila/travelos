"""F-083: passes & documents in a real browser at phone width. An editor adds a flight and passes on Help (every button pressed: add, fix, open full screen, remove),
on the travel day Today's focal card opens the gate view, a real touch swipe moves to the next traveller (dots and count follow), the arrows and dots work, and
nothing scrolls sideways. The files are generated here."""
import io
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect
from pypdf import PdfWriter

from gitaway import catalog
from tests.photo_files import image
from tests_browser.helpers import PHONE

NARROW = {"width": 320, "height": 640}


def pdf():
    w = PdfWriter()
    w.add_blank_page(width=300, height=500)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


@pytest.fixture
def trip(browser, base_url, tmp_path):
    """trip(viewport=PHONE) -> (page on /trip/help, files). Ari (admin) has the sample trip, Oct 16 to 20."""
    contexts = []

    def make(viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/help")
        files = {}
        for name, data in (("a.pdf", pdf()), ("b.png", image("png", size=(300, 500))), ("c.jpg", image("jpeg", size=(300, 500)))):
            (tmp_path / name).write_bytes(data)
            files[name] = str(tmp_path / name)
        (tmp_path / "notes.txt").write_text("not a pass")
        files["text"] = str(tmp_path / "notes.txt")
        return page, files

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def add_flight(page):
    page.locator("#pz-add-flight summary").click()
    form = page.locator("#pz-add-flight form")
    form.locator("[name=airline]").fill("United")
    form.locator("[name=number]").fill("1234")
    form.locator("[name=origin]").fill("lax")
    form.locator("[name=dest]").fill("sfo")
    form.locator("[name=fly_on]").fill("2026-10-17")
    form.locator("[name=time]").fill("14:25")
    form.locator("[name=terminal]").fill("7")
    form.get_by_role("button", name="Save the flight").click()


def add_pass(page, name, seat, file=None, app_url=""):
    block = page.locator("#pz-flight-0")
    block.get_by_text("Add a pass", exact=True).click()
    form = block.locator("form[data-form=pass]").last
    form.locator("[name=traveller]").fill(name)
    form.locator("[name=seat]").fill(seat)
    form.locator("[name=grp]").fill("3")
    form.locator("[name=gate]").fill("71B")
    form.locator("[name=boards]").fill("13:40")
    if app_url:
        form.locator("[name=app_url]").fill(app_url)
    if file:
        form.locator("[name=file]").set_input_files(file)
    form.get_by_role("button", name="Save the pass").click()


def swipe(page, dx):
    """A real touch swipe on the strip of passes (Chrome's own scroll gesture, so the snap points apply)."""
    box = page.locator("#gp-track").bounding_box()
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.synthesizeScrollGesture", {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2, "xDistance": dx, "yDistance": 0, "gestureSourceType": "touch", "speed": 800})
    cdp.detach()


def test_an_editor_adds_a_flight_and_passes_fixes_one_opens_it_full_screen_and_removes_it(trip):
    page, f = trip()
    expect(page.locator("#pz-none")).to_be_visible()   # the sample trip has no imported flight
    add_flight(page)
    expect(page.locator("#pz-flight-0")).to_contain_text("United 1234 · LAX → SFO")
    expect(page.locator("#pz-flight-0")).to_contain_text("Sat Oct 17")
    expect(page.locator("#pz-flight-0")).to_contain_text("Terminal 7")
    add_pass(page, "Abhi", "21a", f["a.pdf"], app_url="https://www.united.com/app")
    expect(page.locator(".pz-pass")).to_have_count(1)
    card = page.locator(".pz-pass").first
    expect(card).to_contain_text("Abhi")
    expect(card).to_contain_text("21A")
    expect(card).to_contain_text("71B")
    expect(card).to_contain_text("1:40 PM")
    expect(card.get_by_role("link", name="Open in airline app")).to_have_attribute("href", "https://www.united.com/app")
    assert card.locator("img.pz-thumb").evaluate("i => i.complete && i.naturalWidth > 0")   # the first page of the PDF, served to the family's own browser
    add_pass(page, "Kay", "21b", f["b.png"])
    expect(page.locator(".pz-pass")).to_have_count(2)
    expect(page.locator(".pz-pass").nth(1).get_by_role("link", name="Open in airline app")).to_have_count(0)   # no link pasted, none shown
    # fix: change the seat
    first = page.locator(".pz-pass").first
    first.get_by_text("Fix this pass").click()
    form = first.locator("form[data-form=pass]")
    form.locator("[name=seat]").fill("22C")
    form.get_by_role("button", name="Save the pass").click()
    expect(page.locator(".pz-pass").first).to_contain_text("22C")
    expect(page.locator(".pz-pass").first.locator("img.pz-thumb")).to_have_count(1)   # the file stayed
    assert overflow(page) <= 0
    # open full screen: the thumbnail opens the gate view on that person
    page.locator(".pz-pass").nth(1).locator("a.pz-stub").click()
    expect(page.locator("#gp")).to_be_visible()
    expect(page.locator(".gp-slide").nth(1)).to_be_in_viewport(ratio=0.9)
    expect(page.locator("#gp-count")).to_contain_text("2 of 2")
    page.locator("#gp-close").click()
    expect(page).to_have_url(lambda u: u.endswith("/trip"))
    # remove a pass: two taps
    page.goto(page.url.replace("/trip", "/trip/help"))
    last = page.locator(".pz-pass").nth(1)
    last.get_by_text("Remove", exact=True).click()
    last.get_by_role("button", name="Yes, remove it").click()
    expect(page.locator(".pz-pass")).to_have_count(1)
    # remove the flight: two taps
    page.get_by_text("Remove this flight").click()
    page.get_by_role("button", name="Yes, remove it").click()
    expect(page.locator("#pz-none")).to_be_visible()


def test_a_refused_file_and_a_bad_flight_say_why_and_keep_nothing(trip):
    page, f = trip()
    page.locator("#pz-add-flight summary").click()
    form = page.locator("#pz-add-flight form")
    form.locator("[name=airline]").fill("United")
    form.locator("[name=number]").fill("1234")
    form.locator("[name=origin]").fill("LAX")
    form.locator("[name=dest]").fill("LAX")
    form.locator("[name=fly_on]").fill("2026-10-17")
    form.locator("[name=time]").fill("14:25")
    form.get_by_role("button", name="Save the flight").click()
    expect(page.locator("#pz-problem")).to_contain_text("two different three-letter airport codes")
    add_flight(page)
    expect(page.locator("#pz-flight-0")).to_be_visible()
    add_pass(page, "Abhi", "21A", f["text"])
    expect(page.locator("#pz-problem")).to_contain_text("Only PDF, JPEG, PNG, WebP and HEIC")
    expect(page.locator(".pz-pass")).to_have_count(0)
    assert overflow(page) <= 0


@pytest.fixture
def travel_day(trip, monkeypatch):
    """The flight and three passes (a PDF, a picture, no file) on the page, and the clock set to Sat Oct 17, 12:58 PM in Los Angeles."""
    def make(viewport=PHONE):
        page, f = trip(viewport)
        add_flight(page)
        add_pass(page, "Abhi", "21A", f["a.pdf"])
        add_pass(page, "Kay", "21B", f["b.png"])
        add_pass(page, "Bhoomija", "21C")
        expect(page.locator(".pz-pass")).to_have_count(3)
        utc = datetime(2026, 10, 17, 19, 58, tzinfo=timezone.utc)
        monkeypatch.setattr(catalog, "now_utc", lambda: utc)
        monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())
        return page
    return make


def test_on_the_travel_day_the_flight_card_opens_the_gate_and_a_swipe_moves_to_the_next_person(travel_day):
    page = travel_day()
    page.goto(page.url.replace("/trip/help", "/trip"))
    card = page.locator("#tp-up.pz-up")
    expect(card).to_be_visible()
    expect(card).to_contain_text("BOARDING IN 42 MIN")
    expect(card).to_contain_text("LAX")
    expect(card).to_contain_text("2:25 PM")
    expect(card).to_contain_text("21A, 21B, 21C")
    assert overflow(page) <= 0
    page.get_by_role("link", name="Show everyone's passes").click()
    expect(page.locator("#gp")).to_be_visible()
    expect(page.get_by_text("Brightness up")).to_be_visible()
    expect(page.locator("#gp-count")).to_contain_text("1 of 3")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(255, 255, 255)"
    imgs = page.locator(".gp-slide").first.locator("img.gp-img")
    assert imgs.evaluate("i => i.complete && i.naturalWidth > 0")   # the PDF's first page, drawn large
    assert overflow(page) <= 0
    swipe(page, -300)   # a finger moving left: the next person
    expect(page.locator("#gp-count")).to_contain_text("2 of 3")
    expect(page.locator(".gp-dot").nth(1)).to_have_attribute("aria-current", "true")
    expect(page.locator(".gp-slide").nth(1)).to_be_in_viewport(ratio=0.9)
    swipe(page, -300)
    expect(page.locator("#gp-count")).to_contain_text("3 of 3")
    expect(page.locator(".gp-slide").nth(2)).to_contain_text("No boarding pass file added yet")
    expect(page.locator("#gp-next")).to_be_disabled()
    swipe(page, 300)   # back
    expect(page.locator("#gp-count")).to_contain_text("2 of 3")
    assert overflow(page) <= 0
    # the arrows and the dots move too
    page.locator("#gp-prev").click()
    expect(page.locator("#gp-count")).to_contain_text("1 of 3")
    expect(page.locator("#gp-prev")).to_be_disabled()
    page.locator("#gp-next").click()
    expect(page.locator("#gp-count")).to_contain_text("2 of 3")
    page.locator(".gp-dot").nth(2).click()
    expect(page.locator("#gp-count")).to_contain_text("3 of 3")
    page.locator("#gp-close").click()
    expect(page.locator("#tp-up.pz-up")).to_be_visible()


def test_the_card_and_the_gate_fit_a_320_wide_phone(travel_day):
    page = travel_day(NARROW)
    page.goto(page.url.replace("/trip/help", "/trip"))
    expect(page.locator("#tp-up.pz-up")).to_be_visible()
    assert overflow(page) <= 0
    page.get_by_role("link", name="Show everyone's passes").click()
    expect(page.locator("#gp")).to_be_visible()
    assert overflow(page) <= 0
    page.goto(page.url.split("/trip/passes")[0] + "/trip/help")
    assert overflow(page) <= 0
