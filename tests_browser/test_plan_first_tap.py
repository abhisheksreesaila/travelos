"""F-169: a plan opens on the first tap. One tap (or click) on a plan's name opens its card (390) or its panel (1440) at once: no wait for a possible double tap. A double tap opens one
thing, not two. Rename stays a gesture away: from the hold menu (test_day_menu.py) and by tapping the title inside the open card (Enter saves, Escape cancels, an empty title is refused,
the keyboard reaches it); a viewer's title is only a title. A finger is Playwright's real touch tap; 1440 is a real mouse."""
import uuid

from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import SUNDAY, box, now, open_day, plan, show, toast
from tests_browser.test_trip_canvas import canvas_page, model, settle  # noqa: F401 - fixtures

# the time from the first input on the page to the first match in the page; the page records it itself, so Playwright's own round trips do not count
WATCH = """(sel) => { window.__open = null; let t0 = null;
  addEventListener('pointerdown', e => { if (t0 === null) t0 = e.timeStamp; }, true);
  const seen = () => { if (window.__open === null && t0 !== null && document.querySelector(sel)) window.__open = performance.now() - t0; };
  new MutationObserver(seen).observe(document.documentElement, { subtree: true, childList: true, attributes: true }); }"""
FRAME_BUDGET = 100      # ms: a frame is 16; the old double-tap wait alone was 330


def block(act):
    return f'.cz-gb[data-act="{act}"]'


def card(page):
    return page.locator(".cz-card")


def tap_title(page, act, dx=10):
    t = box(page, f"{block(act)} .cz-gb-t")
    page.touchscreen.tap(t["x"] + dx, t["y"] + t["height"] / 2)


def open_card(page, act):
    show(page, block(act))
    tap_title(page, act)
    expect(card(page)).to_be_visible()
    page.wait_for_timeout(450)


def test_one_tap_on_a_plans_name_opens_its_card_at_once(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    show(page, block(lunch.id))
    page.evaluate(WATCH, ".cz-card")
    tap_title(page, lunch.id)
    expect(card(page)).to_be_visible()
    took = page.evaluate("window.__open")
    assert took is not None and took < FRAME_BUDGET, f"the card took {took} ms to appear"


def test_one_click_on_a_plans_name_opens_its_panel_at_once_on_the_laptop(canvas_page):
    page = canvas_page(viewport=DESKTOP, motion="no-preference", touch=False)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    show(page, block(lunch.id))
    page.evaluate(WATCH, ".cz-dock-body[data-pane=plan]")
    t = box(page, f"{block(lunch.id)} .cz-gb-t")
    page.mouse.click(t["x"] + 10, t["y"] + t["height"] / 2)
    page.wait_for_function("window.__open !== null")
    took = page.evaluate("window.__open")
    assert took < FRAME_BUDGET, f"the panel took {took} ms to open"


def test_a_double_tap_on_a_name_opens_one_card_and_no_rename_field(canvas_page):
    page = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    show(page, block(lunch.id))
    t = box(page, f"{block(lunch.id)} .cz-gb-t")
    for _ in range(2):
        page.touchscreen.tap(t["x"] + 10, t["y"] + t["height"] / 2)
        page.wait_for_timeout(60)
    page.wait_for_timeout(500)
    assert card(page).count() == 1 and page.locator(".cz-gb-edit").count() == 0
    assert now(lunch.id)[2] == "Lunch"


def test_tapping_the_title_in_the_open_card_renames_the_plan(canvas_page):
    page = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    open_card(page, lunch.id)
    card(page).locator(".cz-card-t").tap()
    field = card(page).locator(".cz-card-name")
    expect(field).to_be_focused()
    assert field.input_value() == "Lunch" and field.evaluate("f => parseFloat(getComputedStyle(f).fontSize)") >= 16      # 16px or more: iOS does not zoom
    field.fill("Late lunch")
    field.press("Enter")
    expect(toast(page)).to_contain_text("Renamed to Late lunch")
    expect(card(page).locator(".cz-card-t")).to_have_text("Late lunch")
    assert now(lunch.id)[2] == "Late lunch" and card(page).locator(".cz-card-name").count() == 0
    expect(page.locator(f"{block(lunch.id)} .cz-gb-t")).to_have_text("Late lunch")
    page.keyboard.press("Escape")
    expect(card(page)).to_have_count(0)


def test_in_the_card_escape_keeps_the_name_an_empty_one_is_refused_and_the_keyboard_reaches_it(canvas_page):
    page = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    open_card(page, lunch.id)
    title = card(page).locator(".cz-card-t")
    title.focus()
    page.keyboard.press("Enter")                                                       # the keyboard opens the field too
    field = card(page).locator(".cz-card-name")
    expect(field).to_be_focused()
    field.fill("Nothing")
    page.keyboard.press("Escape")
    expect(field).to_have_count(0)
    expect(card(page)).to_be_visible()                                                  # Escape ended the rename, not the card
    expect(title).to_have_text("Lunch")
    assert now(lunch.id)[2] == "Lunch"
    title.tap()
    field = card(page).locator(".cz-card-name")
    field.fill("   ")
    field.press("Enter")
    expect(card(page).locator(".cz-card-err")).to_have_text("Give it a title.")
    expect(field).to_be_focused()
    assert now(lunch.id)[2] == "Lunch"


def test_a_viewers_card_title_is_only_a_title(canvas_page, browser, base_url):
    owner = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        open_card(page, lunch.id)
        card(page).locator(".cz-card-t").tap()
        page.wait_for_timeout(200)
        assert card(page).locator(".cz-card-name").count() == 0 and card(page).locator(".cz-card-t").get_attribute("tabindex") is None
        assert now(lunch.id)[2] == "Lunch"
    finally:
        ctx.close()
