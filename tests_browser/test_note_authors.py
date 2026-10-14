"""F-046: two members write notes in their own browsers; each note names its writer and shows their avatar, and "You" only on the writer's own screen."""
import uuid

from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_family_invite import contexts, invite_from_page, owner_page  # noqa: F401 - the fixture and helpers


def open_notes(page, base_url):
    """The trip's notes are the Notes tab of the Today page."""
    page.goto(f"{base_url}/trip?tab=notes")


def write_note(page, base_url, text):
    open_notes(page, base_url)
    page.fill("#tp-composer input[name=text]", text)
    page.click("#tp-composer button[type=submit]")
    expect(page.locator("#tp-panel-notes .tp-notetext", has_text=text)).to_be_visible()


def note(page, text):
    return page.locator("#tp-panel-notes .tp-note", has=page.locator(".tp-notetext", has_text=text))


def check_note(page, text, meta, avatar):
    entry = note(page, text)
    expect(entry.locator(".tp-notemeta")).to_have_text(meta)
    expect(entry.locator(".tp-av")).to_have_attribute("title", avatar)


def test_each_note_shows_who_wrote_it_on_both_screens(contexts, base_url):  # noqa: F811
    ari = owner_page(contexts, base_url, DESKTOP)
    sam_mail = f"sam.kim@{uuid.uuid4().hex[:8]}.example.com"
    link = invite_from_page(ari, sam_mail, "editor")
    sam = contexts(PHONE).new_page()
    sam.goto(link)
    sam.click("#join-signin")
    sam.fill("#si-email", sam_mail)
    sam.click("#si-dev-form button[type=submit]")
    sam.wait_for_url("**/trip/canvas*")

    write_note(ari, base_url, "Ari remembers the sunscreen")
    write_note(sam, base_url, "Sam packs the snacks")
    for page in (ari, sam):
        open_notes(page, base_url)

    check_note(ari, "Ari remembers the sunscreen", "You · whole trip", "Ari Rivera")
    check_note(ari, "Sam packs the snacks", "Sam Kim · whole trip", "Sam Kim")
    check_note(sam, "Ari remembers the sunscreen", "Ari Rivera · whole trip", "Ari Rivera")
    check_note(sam, "Sam packs the snacks", "You · whole trip", "Sam Kim")
