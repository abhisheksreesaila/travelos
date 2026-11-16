"""F-046: two members write in their own browsers; each message names its writer, and a member's own messages sit on their side with no name.
M5 triage: the Notes tab of the old Today page is retired (F-254); the same talk is the Together drawer's Talk on /trip/plan (F-252), where a writer is a first name."""
import uuid

from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_family_invite import contexts, invite_from_page, owner_page  # noqa: F401 - the fixture and helpers


def open_talk(page, base_url, phone):
    page.goto(f"{base_url}/trip/plan")
    page.click(".dock [data-together]" if phone else "#pl-together")
    expect(page.locator("#pl-side")).to_be_visible()


def say(page, base_url, phone, text):
    open_talk(page, base_url, phone)
    page.fill("#pl-say", text)
    page.click("#pl-send")
    expect(page.locator("#pl-bubbles .bub.me", has_text=text)).to_be_visible()


def bubble(page, text):
    return page.locator("#pl-bubbles .bub", has_text=text)


def test_each_note_shows_who_wrote_it_on_both_screens(contexts, base_url):  # noqa: F811
    ari = owner_page(contexts, base_url, DESKTOP)
    sam_mail = f"sam.kim@{uuid.uuid4().hex[:8]}.example.com"
    link = invite_from_page(ari, sam_mail, "editor")
    sam = contexts(PHONE).new_page()
    sam.goto(link)
    sam.click("#join-signin")
    sam.fill("#si-email", sam_mail)
    sam.click("#si-dev-form button[type=submit]")
    sam.wait_for_url("**/trip/plan*")      # the trip's home

    say(ari, base_url, False, "Ari remembers the sunscreen")
    say(sam, base_url, True, "Sam packs the snacks")
    for page, phone in ((ari, False), (sam, True)):
        open_talk(page, base_url, phone)

    for page, mine, theirs in ((ari, "Ari remembers the sunscreen", ("Sam packs the snacks", "Sam")), (sam, "Sam packs the snacks", ("Ari remembers the sunscreen", "Ari"))):
        expect(bubble(page, mine)).to_have_class("bub me")      # your own message sits on your side
        expect(bubble(page, mine).locator(".nm")).to_have_count(0)      # and carries no name
        expect(bubble(page, theirs[0])).to_have_class("bub them")
        expect(bubble(page, theirs[0]).locator(".nm")).to_have_text(theirs[1])      # the other's message names its writer
