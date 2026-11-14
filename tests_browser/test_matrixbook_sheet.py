"""F-233 in a real browser: Book a square. A square is opened, Book grows a sheet out of it (laptop 1440 and phone 390), the guest form books through a recorded LiteAPI
sandbox (tests/fixtures/liteapi: prebook.json, book.json), the steps settle on the springs, the confirmation shows LiteAPI's booking id, and Open your trip lands on the
cockpit with the stay on it. Set F233_SHOTS=1 for docs/report/f233-*.png."""
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi
from tests.test_liteapi import KEY
from tests.test_matrixbook_page import Sandbox
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_tripmatrix import Stand, URL, matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"


class BookStand(Stand):
    """The fixed table's squares, each stay carrying an offer id as the sandbox's search gives."""

    def __init__(self, sample=False):
        super().__init__()
        self.sample = sample

    def __call__(self, *a, **k):
        sq = super().__call__(*a, **k)
        if sq is None or not sq.ok:
            return sq
        return replace(sq, sample=self.sample, stays=tuple(replace(st, offer_id="" if self.sample else f"offer-{i}") for i, st in enumerate(sq.stays)))


def priced(box, total_cents):
    """The recorded prebook priced as the Stand's stay (its $160 resort fee on top): the room still costs what the square said."""
    doc = json.loads(box.prebook[1])
    doc["data"]["price"] = (total_cents - 16_000) / 100
    for rt in doc["data"]["roomTypes"]:
        for rate in rt["rates"]:
            for fee in rate["retailRate"]["taxesAndFees"]:
                if fee["included"] is False:
                    fee["amount"] = 160
    box.prebook = (200, json.dumps(doc).encode())


@pytest.fixture
def sandbox(monkeypatch, stand):  # noqa: F811
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    box = Sandbox()
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    monkeypatch.setattr(gridsource, "SQUARE", BookStand())
    priced(box, 154_000)
    return box


def shot(page, name):
    if os.environ.get("F233_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f233-{name}.png"))


def open_square(page, viewport):
    if viewport is DESKTOP:
        page.click(f".mx-lane[data-lane='sandiego'] .mx-sq >> nth=2")
        return page.locator("#mx-side")
    page.locator(".mx-card[data-lane='sandiego'] .mx-sq").nth(2).click()
    return page.locator(".mx-sheet")


def fill(page, first="Anne-Marie", last="O’Neil", email="anne@example.com"):
    page.fill("#mxb-first", first)
    page.fill("#mxb-last", last)
    page.fill("#mxb-email", email)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_square_grows_into_the_booking_sheet_and_books_through_the_sandbox(matrix, sandbox, viewport):  # noqa: F811
    page = matrix(viewport, motion=True, signed_in=True)
    panel = open_square(page, viewport)
    expect(panel.locator(".mx-book")).to_be_visible()
    expect(panel.locator(".mx-soon-h")).to_have_text("Sandbox booking: nothing is charged.")
    shot(page, f"{viewport['width']}-square")
    panel.locator(".mx-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".mxb-h")).to_have_text("Book San Diego")
    expect(sheet.locator(".mxb-sandbox")).to_have_text("Sandbox booking: nothing is charged")
    opened = page.evaluate("() => GA.motion.log.filter(m => m.kind === 'open').slice(-1)[0]")
    assert opened and not opened.get("calm") and opened["from"]                                 # liquid on the laptop too; it grew out of the square
    assert [s.get_attribute("data-state") for s in sheet.locator(".mxb-step").all()] == ["done", "active", "todo"]
    page.wait_for_timeout(700)                                                                  # landed
    box = sheet.bounding_box()
    if viewport is PHONE:
        assert box["y"] + box["height"] >= viewport["height"] - 2 and box["width"] >= viewport["width"] - 2      # a bottom sheet
    else:
        assert 480 < box["width"] < 600 and box["x"] > 300                                      # a card in the middle
    shot(page, f"{viewport['width']}-sheet")
    page.fill("#mxb-first", "Anne-Marie")
    page.fill("#mxb-last", "O’Neil")
    page.fill("#mxb-email", "anne@example")
    page.click(".mxb-go")
    expect(sheet.locator("#mxb-email-e")).to_have_text("That does not look like an email address.")      # said in the sheet, the typed words kept
    expect(page.locator("#mxb-first")).to_have_value("Anne-Marie")
    assert [r for u, _, r in sandbox.asked if u.endswith("/rates/book")] == []
    shot(page, f"{viewport['width']}-error")
    page.fill("#mxb-email", "anne@example.com")
    page.click(".mxb-go")
    expect(sheet.locator(".mxb-id").first).to_have_text("_5hnX-MI7")
    expect(sheet.locator(".mxb-sandbox")).to_have_text("Sandbox booking: nothing is charged")
    assert sheet.locator(".mxb").get_attribute("data-at") == "booked"
    expect(sheet.locator(".mxb-step[data-state='active'] .mxb-step-n")).to_have_text("Booked")
    expect(sheet).to_contain_text("Anne-Marie O’Neil, your booking is confirmed.")
    assert page.evaluate("() => GA.motion.log.filter(m => m.kind === 'settle').length") >= 1                # the step settled on the spring
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-booked")
    assert page.errors == []
    sheet.locator("[data-trip]").click()
    page.wait_for_url("**/trip/cockpit")
    page.wait_for_timeout(400)
    expect(page.locator("body")).to_contain_text("Check in")                                   # the booked stay is on the trip's days
    shot(page, f"{viewport['width']}-cockpit")


def test_a_sample_square_books_a_sample_stay_and_says_so(matrix, monkeypatch, stand):  # noqa: F811
    monkeypatch.setattr(gridsource, "SQUARE", BookStand(sample=True))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("LiteAPI was asked")))
    page = matrix(DESKTOP, signed_in=True)
    page.click(".mx-lane[data-lane='sandiego'] .mx-sq >> nth=2")
    expect(page.locator("#mx-side .mx-soon-h")).to_have_text("Sample booking: nothing is booked or charged.")
    page.click("#mx-side .mx-book")
    expect(page.locator(".mxb-sandbox")).to_have_text("Sample booking: nothing is booked or charged")
    fill(page)
    page.click(".mxb-go")
    expect(page.locator(".mxb-id").first).to_contain_text("SAMPLE-")
    expect(page.locator(".mxb-sheet")).to_contain_text("your sample booking is confirmed")
    assert page.errors == []


def test_escape_closes_the_sheet_and_the_square_stays_open(matrix, sandbox):  # noqa: F811
    page = matrix(DESKTOP, motion=True, signed_in=True)
    open_square(page, DESKTOP)
    page.click("#mx-side .mx-book")
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".mxb-sheet")).to_have_count(0)
    expect(page.locator("#mx-side .mx-book")).to_be_visible()
    assert page.errors == []


def test_signed_out_it_goes_to_sign_in(matrix, sandbox):  # noqa: F811
    page = matrix(DESKTOP)
    open_square(page, DESKTOP)
    page.click("#mx-side .mx-book")
    page.wait_for_url("**/signin**")


def test_without_the_script_the_two_steps_are_pages(matrix, sandbox):  # noqa: F811
    gridsource.SQUARE.peek_all = True
    page = matrix(DESKTOP, js=False, signed_in=True, url=URL.replace("/plan/matrix?", "/plan/matrix/square?") + "&lane=sandiego&w=2026-12-12")
    page.click(".mx-book")
    expect(page.locator(".mxb-h")).to_have_text("Book San Diego")
    fill(page)
    page.click(".mxb-go")
    expect(page.locator(".mxb-id").first).to_have_text("_5hnX-MI7")
    expect(page.locator("[data-trip]")).to_be_visible()
