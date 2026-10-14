"""F-142: Ask in the panel, in a real browser (a mouse and the keyboard, at 1440 and 1280). On the trip canvas's day the top bar's Ask, the panel's Ask tab, the compose bar, the mic of Up next and the `/`
key open the phone's Ask box in the panel, without a page load; Say the plan starts the (fake) microphone, Paste a plan focuses the note; a proposal is shown in the panel and Apply changes the grid in
place, glows what changed and toasts that the family has been told. On the week the same links open the day with the Ask panel. Other pages, the tablet and a viewer keep the Ask page.
A fake model and a fake microphone answer (nothing reaches Azure or Sarvam). Screenshots on request: F142_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import ai
from tests import canvas_samples as samples
from tests.test_speak import answer, op
from tests_browser.helpers import DESKTOP
from tests_browser.test_ask_box import FAKE_MIC, HEARD, NO_SPEECH
from tests_browser.test_ask_sheet import Voice
from tests_browser.test_day_grid import open_day
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT
from tests_browser.test_topbar import BAR, LAPTOP, TABLET, signed_in  # noqa: F401 - fixture
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

SATURDAY = 1
DOCK = "#cz-dock"
NO_SCROLL = "[document.documentElement.scrollWidth <= document.documentElement.clientWidth, document.documentElement.scrollHeight <= document.documentElement.clientHeight, window.scrollY]"


def shot(page, name):
    if os.environ.get("F142_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F142_SHOTS"], name))


@pytest.fixture
def voice(monkeypatch):
    """voice() -> installs the fake for the model (it adds Pool at 3 PM) and the speech service (it hears HEARD). Called once the trip is made: that is made by the default fake."""
    def install():
        fake = Voice(samples.FakeAzure(answer(op("add_plan", title="Pool", start="15:00", end="16:00"))))
        monkeypatch.setattr(ai, "TRANSPORT", fake)
        monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "stt-test")
        return fake
    return install


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page, voice):
    page = canvas_page(viewport=request.param, touch=False)
    voice()
    open_day(page, SATURDAY)
    page.evaluate(NO_SPEECH + FAKE_MIC)                 # the browser records (the fake microphone) and the server hears HEARD (after the page load: it is the page's own)
    page.evaluate("window.__loaded = 1")                # a marker: a page load would lose it
    return page


def mode(page):
    return page.locator(DOCK).get_attribute("data-mode")


def ready(page):
    """The box is in the panel and the page did not load again."""
    expect(page.locator(f"{DOCK} .cz-ak #ak-form")).to_be_visible()
    assert mode(page) == "ask" and page.evaluate("window.__loaded") == 1


def fetched_ahead(page, link):
    """The way a real mouse gets there first: the box was fetched ahead as the pointer came over the link."""
    page.locator(link).hover()
    page.wait_for_timeout(500)


def say_it(page):
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    page.wait_for_timeout(1200)
    page.locator("#ak-go").click()


def propose(page):
    """Say it and press Done: the proposal for Pool appears in the panel."""
    say_it(page)
    expect(page.locator(f"{DOCK} #ak-prop")).to_be_visible()


def test_the_top_bar_ask_opens_the_box_in_the_panel_with_the_mic(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    assert "/trip/canvas" in desk.url and "day=1" in desk.url                                  # nothing navigated: still the day
    expect(desk.locator(f"{DOCK} .cz-dock-tab[data-tab=ask]")).to_have_attribute("aria-selected", "true")
    expect(desk.locator(f"{DOCK} #ak-mic")).to_be_visible()                                    # the microphone is there, to tap
    expect(desk.locator(f"{DOCK} #ak-mic")).not_to_have_class(re.compile("is-recording"))
    expect(desk.locator("#ak-text")).to_be_focused()                                           # and the keyboard types straight in
    expect(desk.locator(f"{DOCK} #ak-chip-label")).to_have_text("Sat Oct 17")                  # the day being looked at is chosen
    expect(desk.locator(f"{DOCK} [data-pane=idle]")).to_be_hidden()
    expect(desk.locator(f"{DOCK} .cz-compose")).to_be_hidden()
    assert desk.evaluate(NO_SCROLL)[:2] == [True, True] and desk.evaluate(OVERFLOW) <= 0
    shot(desk, f"ask-idle-{desk.viewport_size['width']}.png")


def test_the_panels_ask_tab_opens_the_same_box(desk):
    desk.locator(f"{DOCK} .cz-dock-tab[data-tab=ask]").click()
    ready(desk)
    expect(desk.locator(f"{DOCK} #ak-mic")).to_be_visible()
    assert "/trip/ask" not in desk.url


def test_the_slash_key_opens_it_but_not_while_typing(desk):
    desk.keyboard.press("/")
    ready(desk)
    desk.locator("#ak-text").fill("")
    desk.keyboard.type("lunch at 1/2 past")                                                   # a slash typed into the note is a slash
    expect(desk.locator("#ak-text")).to_have_value("lunch at 1/2 past")
    assert mode(desk) == "ask" and desk.evaluate("window.__loaded") == 1
    desk.keyboard.press("Escape")                                                              # the note lets go first, what was typed stays
    expect(desk.locator("#ak-text")).to_have_value("lunch at 1/2 past")
    assert mode(desk) == "ask"


def test_the_compose_bar_says_press_slash_and_opens_ask(desk):
    bar = desk.locator(f"{DOCK} #cz-dock-compose")
    expect(bar).to_contain_text("Type to Ask")
    expect(bar).to_contain_text("or press")
    expect(bar.locator("kbd")).to_have_text("/")
    bar.click()
    ready(desk)
    expect(desk.locator("#ak-text")).to_be_focused()


def test_the_mic_in_the_idle_panel_starts_listening_in_the_panel(desk):
    fetched_ahead(desk, "#cz-dock-mic")
    desk.locator("#cz-dock-mic").click()
    ready(desk)
    expect(desk.locator("#ak-mic")).to_have_class(re.compile("is-recording"))


def test_say_the_plan_starts_the_microphone_in_the_panel(desk):
    fetched_ahead(desk, "#cz-desk-talk")
    desk.locator("#cz-desk-talk").click()
    ready(desk)
    expect(desk.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    desk.locator("#ak-rec-cancel").click()                                                    # Cancel is a button of the box: it stops the recording
    expect(desk.locator("#ak-mic")).not_to_have_class(re.compile("is-recording"))


def test_paste_a_plan_focuses_the_note_ready_for_a_long_paste(desk):
    desk.locator("#cz-desk-paste").click()
    ready(desk)
    expect(desk.locator("#ak-form")).to_have_attribute("data-mode", "paste")
    expect(desk.locator("#ak-text")).to_be_focused()
    desk.keyboard.insert_text("Universal day. " * 80)                                          # a long paste goes into the note
    expect(desk.locator("#ak-text")).to_have_value(re.compile(r"^Universal day\."))
    expect(desk.locator(f"{DOCK} #ak-count")).to_be_hidden()                                    # (well under the limit)
    desk.locator("#ak-paste").click()                                                          # the Paste button is the box's own: it reads the clipboard or says how
    assert mode(desk) == "ask"


def test_a_proposal_is_shown_in_the_panel_and_apply_changes_the_grid_in_place(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    desk.locator("#ak-text").fill(HEARD)
    desk.locator("#ak-go").click()
    expect(desk.locator(f"{DOCK} #ak-prop")).to_be_visible()
    expect(desk.locator(f"{DOCK} .ak-chip[data-kind=new]")).to_contain_text("Pool")
    expect(desk.locator("#ak-apply")).to_have_text("Apply")
    assert desk.url.count("/trip/ask") == 0 and desk.evaluate("window.__loaded") == 1 and desk.evaluate(NO_SCROLL)[:2] == [True, True]
    expect(desk.locator('.cz-gb[data-title="Pool"]')).to_have_count(0)                          # nothing changed yet
    shot(desk, f"ask-proposal-{desk.viewport_size['width']}.png")
    desk.locator("#ak-apply").click()
    expect(desk.locator('.cz-gb[data-title="Pool"]')).to_be_visible()                           # the grid changed in place
    expect(desk.locator(".cz-gb.ak-fresh")).to_have_count(1)                                    # and what is new glows
    expect(desk.locator("#ga-toast")).to_contain_text("Added 1 plan")
    expect(desk.locator("#ga-toast")).to_contain_text("The family has been told")              # as on the phone
    expect(desk.locator(f"{DOCK} .cz-ak")).to_have_count(0)
    assert mode(desk) == "idle" and desk.evaluate("window.__loaded") == 1
    expect(desk.locator(f"{DOCK} .cz-dock-tab[data-tab=plan]")).to_have_attribute("aria-selected", "true")
    shot(desk, f"ask-applied-{desk.viewport_size['width']}.png")
    expect(desk.locator(".cz-gb.ak-fresh")).to_have_count(0, timeout=4000)


def test_talking_ends_in_a_proposal_and_change_it_goes_back_to_the_box(desk):
    fetched_ahead(desk, "#cz-desk-talk")
    desk.locator("#cz-desk-talk").click()
    ready(desk)
    propose(desk)
    assert desk.locator("#ak-text").count() == 0
    desk.locator("#ak-change").click()                                                         # Change it: the box again, with what was said
    expect(desk.locator(f"{DOCK} #ak-text")).to_have_value(HEARD)
    assert mode(desk) == "ask"


def test_the_close_button_and_escape_put_the_panel_back_to_up_next(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    desk.locator(f"{DOCK} .cz-ak .cz-pp-close").click()
    expect(desk.locator(f"{DOCK} .cz-ak")).to_have_count(0)
    assert mode(desk) == "idle"
    expect(desk.locator(f"{DOCK} [data-pane=idle]")).to_be_visible()
    desk.keyboard.press("/")
    ready(desk)
    desk.keyboard.press("Escape")                                                              # an empty note: Esc closes
    expect(desk.locator(f"{DOCK} .cz-ak")).to_have_count(0)
    assert mode(desk) == "idle" and desk.evaluate("window.__loaded") == 1


def test_a_plan_opened_while_ask_is_open_takes_over_the_panel(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    desk.locator(".cz-gb.is-park").first.click(position={"x": 120, "y": 40})
    expect(desk.locator(f"{DOCK} .cz-pp:not(.is-leaving)")).to_be_visible()
    assert mode(desk) == "plan"
    expect(desk.locator(f"{DOCK} .cz-ak")).to_have_count(0)
    desk.locator(f"{DOCK} .cz-dock-tab[data-tab=ask]").click()                                 # and back to Ask: the box is new
    ready(desk)
    expect(desk.locator(f"{DOCK} .cz-pp")).to_have_count(0)


def test_the_days_own_refresh_leaves_the_box_alone(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    desk.locator("#ak-text").fill("move lunch")
    desk.locator("#ak-text").blur()
    desk.evaluate("CZ.quiet()")
    desk.wait_for_timeout(600)
    expect(desk.locator("#ak-text")).to_have_value("move lunch")
    assert mode(desk) == "ask"


def test_on_the_week_ask_opens_the_day_with_the_ask_panel(canvas_page, voice):
    page = canvas_page(viewport=DESKTOP, touch=False)
    voice()
    page.evaluate(NO_SPEECH + FAKE_MIC)
    page.wait_for_selector(".cz-view[data-level=week]")
    page.evaluate("window.__loaded = 1")
    page.locator(f"{BAR} .ga-tb-ask").click()
    page.wait_for_selector(".cz-view[data-level=day]")
    ready(page)
    assert "/trip/ask" not in page.url and re.search(r"day=\d", page.url)
    page.locator(f"{DOCK} .cz-pp-close").click()
    page.go_back()                                                                             # the way back to the week
    page.wait_for_selector(".cz-view[data-level=week]")
    page.keyboard.press("/")                                                                   # the key does the same
    page.wait_for_selector(".cz-view[data-level=day]")
    ready(page)


def test_say_the_plan_on_a_week_column_opens_that_day_listening(canvas_page, voice):
    page = canvas_page(viewport=DESKTOP, touch=False)
    voice()
    page.evaluate(NO_SPEECH + FAKE_MIC)
    page.wait_for_selector(".cz-view[data-level=week]")
    page.evaluate("window.__loaded = 1")
    link = page.locator(".cz-wcol .cz-wsay").first                                              # a free day's "Say the plan"
    day = re.search(r"day=(\d+)", link.get_attribute("href")).group(1)
    link.click()
    page.wait_for_selector(f".cz-view[data-level=day][data-day='{day}']")
    ready(page)
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))                   # listening, as on the phone


def test_other_pages_keep_going_to_the_ask_page(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.locator(f"{BAR} .ga-tb-ask").click()
    page.wait_for_url("**/trip/ask")
    page = signed_in(DESKTOP, path="/family")
    page.keyboard.press("/")
    page.wait_for_url("**/trip/ask")


def test_the_tablet_keeps_the_ask_page_links(signed_in):
    page = signed_in(TABLET, path="/trip/canvas?day=1")
    expect(page.locator(DOCK)).to_be_hidden()
    page.evaluate("document.getElementById('cz-desk-talk').click()")                          # (the buttons are not drawn at this width: the link itself is followed)
    page.wait_for_url(re.compile(r"/trip/ask\?day=1&mode=talk"))


# ---- review follow-ups: decided when it is asked, viewers, block and step, the fallback and another day ------------------------------

def test_a_page_first_loaded_at_a_block_then_zoomed_out_to_the_day_opens_the_panel(desk, base_url):
    act = desk.locator(".cz-gb.is-park").first.get_attribute("data-act")
    desk.goto(f"{base_url}/trip/canvas?block={act}")
    desk.wait_for_selector(".cz-view[data-level=block]")
    desk.evaluate("window.__loaded = 1")
    desk.evaluate("CZ.goto(document.querySelector('.cz-view[data-level=block] .cz-back').getAttribute('href'))")      # zoom out to the day (the back link is not drawn on a laptop)
    desk.wait_for_selector(".cz-view[data-level=day]")
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)


def test_a_block_and_a_step_keep_the_plain_link(desk, base_url):
    act = desk.locator(".cz-gb.is-park").first.get_attribute("data-act")
    desk.goto(f"{base_url}/trip/canvas?block={act}")
    desk.wait_for_selector(".cz-view[data-level=block]")
    assert desk.evaluate("[Dock.show('ask'), Dock.has('ask')]") == [False, False]
    desk.locator(f"{BAR} .ga-tb-ask").click()
    desk.wait_for_url(re.compile(r"/trip/ask"))
    desk.goto(f"{base_url}/trip/canvas?block={act}")
    desk.wait_for_selector(".cz-view[data-level=block]")
    step = desk.locator(".cz-view[data-level=block] a[href*='step=']").first.get_attribute("href")
    desk.goto(f"{base_url}{step}")
    desk.wait_for_selector(".cz-view[data-level=step]")
    desk.locator(f"{BAR} .ga-tb-ask").click()
    desk.wait_for_url(re.compile(r"/trip/ask"))


def test_dock_show_ask_is_false_on_the_week_so_a_caller_can_fall_back(canvas_page, voice):
    page = canvas_page(viewport=DESKTOP, touch=False)
    page.wait_for_selector(".cz-view[data-level=week]")
    assert page.evaluate("Dock.show('ask', {})") is False


def test_a_viewer_clicking_ask_on_the_canvas_lands_on_the_only_editors_page(canvas_page, browser, base_url, voice):
    owner = canvas_page(viewport=DESKTOP, touch=False)
    mail = f"vi.panel@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        viewer = ctx.new_page()
        viewer.goto(f"{base_url}/trip/canvas?day=1")
        viewer.wait_for_selector(".cz-view[data-level=day]")
        assert viewer.locator("#cz-dock").get_attribute("data-ask") is None
        viewer.locator("#cz-dock .cz-dock-tab[data-tab=ask]").click()
        viewer.wait_for_url(re.compile(r"/trip/ask"))
        expect(viewer.locator("#ak-viewer")).to_be_visible()
        viewer.go_back()
        viewer.wait_for_selector(".cz-view[data-level=day]")
        viewer.locator(f"{BAR} .ga-tb-ask").click()
        viewer.wait_for_url(re.compile(r"/trip/ask"))
        expect(viewer.locator("#ak-viewer")).to_be_visible()
    finally:
        ctx.close()


def test_when_the_box_cannot_load_the_panel_says_so_and_offers_the_page(desk):
    desk.route(re.compile(r"/trip/ask\?day=\d+&mode=type"), lambda route: route.fulfill(status=500, body="no"))
    desk.locator(f"{BAR} .ga-tb-ask").click()
    link = desk.locator(f"{DOCK} .cz-ak .cz-pp-open")
    expect(link).to_have_text("Open the Ask page")
    link.click()
    desk.wait_for_url(re.compile(r"/trip/ask\?day=1"))
    expect(desk.locator("#ak-form")).to_be_visible()


def test_apply_after_choosing_another_day_shows_that_day(desk):
    desk.locator(f"{BAR} .ga-tb-ask").click()
    ready(desk)
    desk.locator("#ak-text").fill(HEARD)
    desk.locator("#ak-chip").click()
    desk.locator('.ak-dpick[data-d="2"]').click()
    desk.locator("#ak-go").click()
    expect(desk.locator(f"{DOCK} #ak-prop")).to_be_visible()
    desk.locator("#ak-apply").click()
    desk.wait_for_selector(".cz-view[data-level=day][data-day='2']")
    expect(desk.locator('.cz-gb[data-title="Pool"]')).to_be_visible()
    expect(desk.locator("#ga-toast")).to_contain_text("The family has been told")
    assert mode(desk) == "idle" and desk.evaluate("window.__loaded") == 1
