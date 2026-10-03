"""F-071: photos in a real browser at phone width. Pick generated pictures with the camera button, see them as cards in the thread and in the
Photos view (a strip per day, the latest on a polaroid pinned to its plan), open one and remove it, a refused file says why, and nothing scrolls
sideways. The pictures are generated here with the EXIF a phone writes."""
import pytest
from playwright.sync_api import expect

from tests.photo_files import image
from tests_browser.helpers import PHONE

NARROW = {"width": 320, "height": 640}


@pytest.fixture
def family(browser, base_url, tmp_path):
    """family(viewport=PHONE) -> (page on /trip/family, the generated files). Ari has the sample trip and a plan on Sat Oct 17, 10:00-11:30."""
    contexts = []

    def make(viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "1", "start": "10:00", "end": "11:30", "title": "Venice Canals stroll", "kind": "outdoors"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/family")
        files = {}
        for name, taken in (("stroll", "2026:10:17 10:30:00"), ("morning", "2026:10:17 08:15:00"), ("sunday", "2026:10:18 16:20:00")):
            path = tmp_path / f"{name}.jpg"
            path.write_bytes(image("jpeg", size=(400, 300), taken=taken))
            files[name] = str(path)
        (tmp_path / "notes.txt").write_text("not a picture")
        files["text"] = str(tmp_path / "notes.txt")
        return page, files

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def pick(page, button, *paths):
    with page.expect_file_chooser() as chooser:
        page.locator(button).click()
    chooser.value.set_files(list(paths))


def loaded(locator):
    return locator.evaluate("i => i.complete && i.naturalWidth > 0")


def test_pick_photos_with_the_camera_button_and_see_them_in_the_thread_and_the_strips(family):
    page, f = family()
    expect(page.locator("#ft-camera")).to_be_visible()
    pick(page, "#ft-camera", f["stroll"], f["morning"], f["sunday"])
    expect(page.locator("#ft-thread img.ft-photo")).to_have_count(3, timeout=15000)               # a card per photo, in the thread
    assert loaded(page.locator("#ft-thread img.ft-photo").first)                                  # served to the family's own browser
    page.locator("#fam-photos").click()                                                          # the switch, without a reload
    expect(page.locator("#fp")).to_be_visible()
    expect(page.locator("#ft-chat")).to_be_hidden()
    assert page.url.endswith("/trip/family?view=photos")
    expect(page.locator(".fp-day")).to_have_count(2)                                             # a strip per day
    expect(page.locator(".fp-day").first.locator(".fp-time")).to_have_text(["8:15 AM", "10:30 AM"])
    expect(page.locator(".fp-day").last.locator(".fp-time")).to_have_text(["4:20 PM"])
    expect(page.locator("#fp-polar")).to_contain_text("Oct 18 · 4:20 PM")                         # the latest taken, on a polaroid
    expect(page.locator("#fp-pinto")).to_contain_text("Not during a plan")
    assert loaded(page.locator(".fp-thumb").first)
    assert overflow(page) <= 0
    page.locator("#fam-chat").click()
    expect(page.locator("#ft-chat")).to_be_visible()
    expect(page.locator("#fp")).to_be_hidden()


def test_a_photo_taken_during_a_plan_is_pinned_to_it(family):
    page, f = family()
    pick(page, "#ft-camera", f["stroll"])
    expect(page.locator("#ft-thread img.ft-photo")).to_have_count(1, timeout=15000)
    expect(page.locator("#ft-thread .ft-cap")).to_have_text("At Venice Canals stroll")
    page.locator("#fam-photos").click()
    expect(page.locator("#fp-polar")).to_contain_text("Venice Canals stroll · 10:30 AM")
    expect(page.locator("#fp-pinto")).to_contain_text("Pinned to Venice Canals stroll")
    expect(page.locator("#fp-pinto")).to_contain_text("1 photo on this stop")


def test_open_a_photo_and_remove_it(family):
    page, f = family()
    pick(page, "#ft-camera", f["stroll"], f["morning"])
    expect(page.locator("#ft-thread img.ft-photo")).to_have_count(2, timeout=15000)
    page.locator("#fam-photos").click()
    page.locator(".fp-s").last.click()                                                           # the 10:30 photo
    expect(page.locator("#fp-big")).to_be_visible()
    expect(page.locator("#fp-meta")).to_contain_text("Pinned to Venice Canals stroll")
    assert loaded(page.locator("#fp-big"))
    assert overflow(page) <= 0
    page.locator("#fp-back").click()                                                             # the back link works
    expect(page.locator("#fp")).to_be_visible()
    page.locator(".fp-s").last.click()
    page.locator("#fp-remove").click()                                                           # the Remove button works
    expect(page.locator("#fp")).to_be_visible()
    assert page.url.endswith("/trip/family?view=photos")
    expect(page.locator(".fp-s")).to_have_count(1)
    page.locator("#fam-chat").click()
    page.reload()
    expect(page.locator("#ft-thread img.ft-photo")).to_have_count(1)                              # the card went with it
    page.locator("#fam-photos").click()
    page.locator(".fp-s").first.click()
    page.locator("#fp-remove").click()
    expect(page.locator("#fp-empty")).to_be_visible()
    expect(page.locator(".fp-day")).to_have_count(0)


def test_the_library_button_adds_photos_too_and_a_refused_file_says_why(family):
    page, f = family()
    page.locator("#fam-photos").click()
    expect(page.locator("#fp-empty")).to_be_visible()
    pick(page, "[data-pick=library]", f["text"])
    expect(page.locator("#ph-status")).to_contain_text("Only JPEG, PNG, WebP and HEIC", timeout=9000)
    expect(page.locator("#fp-empty")).to_be_visible()                                            # nothing was added
    pick(page, "[data-pick=library]", f["sunday"])
    expect(page.locator(".fp-s")).to_have_count(1, timeout=15000)
    assert page.url.endswith("/trip/family?view=photos")                                         # reloaded into the same view
    pick(page, "#fp [data-pick=camera]", f["morning"], f["stroll"])
    expect(page.locator(".fp-s")).to_have_count(3, timeout=15000)


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_no_sideways_scroll_and_big_targets_in_both_views(family, viewport):
    page, f = family(viewport)
    pick(page, "#ft-camera", f["stroll"], f["morning"], f["sunday"])
    expect(page.locator("#ft-thread img.ft-photo")).to_have_count(3, timeout=15000)
    assert overflow(page) <= 0
    for sel in ("#ft-camera", "#ft-send", "#fam-chat", "#fam-photos"):
        box = page.locator(sel).bounding_box()
        assert box["height"] >= 43.9 and box["width"] >= 43.9, sel
    page.locator("#fam-photos").click()
    assert overflow(page) <= 0
    for sel in ("#fp [data-pick=camera]", "[data-pick=library]"):
        assert page.locator(sel).bounding_box()["height"] >= 43.9, sel
    small = page.evaluate("""() => [...document.querySelectorAll('#ft *')].filter(e => e.offsetParent && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).length""")
    assert small == 0
