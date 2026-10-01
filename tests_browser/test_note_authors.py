"""F-046: two members write notes in their own browsers; each note names its writer and shows their avatar, and "You" only on the writer's own screen."""
import uuid

from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_family_invite import contexts, invite_from_page, owner_page  # noqa: F401 - the fixture and helpers


def open_notes(page):
    """On a phone the notes sit behind a button."""
    toggle = page.locator("#cal-notes-toggle")
    if toggle.is_visible() and toggle.get_attribute("aria-expanded") != "true":
        toggle.click()


def write_note(page, base_url, text):
    page.goto(f"{base_url}/calendar?view=days")
    open_notes(page)
    page.fill(".cal-composer input[name=text]", text)
    page.click(".cal-composer .cal-send")
    expect(page.locator(".cal-notetext", has_text=text)).to_be_visible()


def note(page, text):
    return page.locator(".cal-note", has=page.locator(".cal-notetext", has_text=text))


def check_note(page, text, meta, avatar):
    entry = note(page, text)
    expect(entry.locator(".cal-notemeta")).to_have_text(meta)
    expect(entry.locator(".cal-noteav")).to_have_attribute("title", avatar)


def test_each_note_shows_who_wrote_it_on_both_screens(contexts, base_url):  # noqa: F811
    ari = owner_page(contexts, base_url, DESKTOP)
    sam_mail = f"sam.kim@{uuid.uuid4().hex[:8]}.example.com"
    link = invite_from_page(ari, sam_mail, "editor")
    sam = contexts(PHONE).new_page()
    sam.goto(link)
    sam.click("#join-signin")
    sam.fill("#si-email", sam_mail)
    sam.click("#si-dev-form button[type=submit]")
    sam.wait_for_url("**/calendar")

    write_note(ari, base_url, "Ari remembers the sunscreen")
    write_note(sam, base_url, "Sam packs the snacks")
    for page in (ari, sam):
        page.goto(f"{base_url}/calendar?view=days")
        open_notes(page)

    check_note(ari, "Ari remembers the sunscreen", "You · whole trip", "Ari Rivera")
    check_note(ari, "Sam packs the snacks", "Sam Kim · whole trip", "Sam Kim")
    check_note(sam, "Ari remembers the sunscreen", "Ari Rivera · whole trip", "Ari Rivera")
    check_note(sam, "Sam packs the snacks", "You · whole trip", "Sam Kim")
