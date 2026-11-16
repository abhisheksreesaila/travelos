"""F-275 in a real browser (docs/design/matrix-v3, D-860..): the sentence's suggestion chips, the side widgets folded into chips that open into cards, and the opened square's rich hotel
(the recorded Hilton answer, tests/fixtures/liteapi_hotel): the photo mosaic and its lightbox, the reviews as text, the room photos. Shots: F275_SHOTS=1 for docs/report/f275-*.png."""
import os
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi
from tests_browser.helpers import DESKTOP, PHONE, open_rail
from tests_browser.test_tripmatrix import URL, matrix, stand  # noqa: F401 (fixtures)

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "liteapi_hotel"
REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"


@pytest.fixture
def hilton(monkeypatch, stand):  # noqa: F811
    """Every stand square is a live-style one whose hotel LiteAPI knows (the recorded Hilton answers); only the hotel calls reach the fake."""
    monkeypatch.setenv("LITEAPI_KEY", "sand_test-key-not-real")
    liteapi.clear()      # a hotel is kept a day in the process: each test asks for it afresh
    asked = []

    def transport(url, headers, body, timeout):
        asked.append(url)
        name = "reviews.json" if "/data/reviews" in url else "hotel.json"
        return 200, "application/json", (FIX / name).read_bytes()
    monkeypatch.setattr(liteapi, "TRANSPORT", transport)
    inner = gridsource.SQUARE

    def square(*a, **k):
        sq = inner(*a, **k)
        return replace(sq, stays=tuple(replace(s, hotel_id="lp1b8e6") for s in sq.stays)) if sq is not None and sq.ok else sq
    monkeypatch.setattr(gridsource, "SQUARE", square)
    return asked


def shot(page, name):
    if os.environ.get("F275_SHOTS"):
        page.screenshot(path=str(REPORT / f"f275-{name}.png"))


def test_a_suggestion_chip_runs_the_sentence_with_one_word_changed(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    expect(page.locator(".v2-hint")).to_have_text("Tap any word to change it")
    chip = page.locator(".v2-sug", has_text="A week later")
    expect(chip).to_be_visible()
    assert chip.bounding_box()["height"] >= 47.5
    chip.click()
    page.wait_for_url("**d=2026-12-19**")
    assert "r=2026-12-23" in page.url and "home=SFO" in page.url
    expect(page.locator('#v2-sent .v2-w[data-k="start"]')).to_have_text("Sat, Dec 19")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_widget_is_a_chip_until_it_is_tapped_and_then_a_card(matrix, viewport):  # noqa: F811
    page = matrix(viewport)
    page.wait_for_selector("#mx-rail .wchip[data-wg]")
    assert page.locator("#mx-rail .wg:not([hidden])").count() == 0
    chip = page.locator("#mx-rail .wchip[data-wg]").nth(1)
    chip.click()
    expect(chip).to_have_attribute("aria-expanded", "true")
    card = page.locator("#mx-rail .wg:not([hidden])")
    expect(card).to_have_count(1)
    expect(card.first).to_be_visible()
    card.first.locator(".wg-x").click()
    expect(page.locator("#mx-rail .wg:not([hidden])")).to_have_count(0)
    open_rail(page)
    assert page.locator("#mx-rail .wg:not([hidden])").count() == page.locator("#mx-rail .wchip").count()


def test_the_nights_band_never_prints_a_label_on_a_neighbouring_row(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    page.wait_for_selector(".mx-sq.is-ok")
    assert page.evaluate("[...document.querySelectorAll('.mx-band')].every(b => getComputedStyle(b, '::after').content === 'none')")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_opened_square_loads_the_hotels_photos_and_reviews_once_and_the_lightbox_walks_them(matrix, hilton, viewport):  # noqa: F811
    page = matrix(viewport)
    page.wait_for_selector(".mx-sq.is-ok")
    assert [u for u in hilton if "/data/" in u] == []      # nothing about a hotel is asked until a square is opened
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(2).click()
    expect(page.locator("#mx-drawer .dr-photos")).to_be_visible()
    asked = [u for u in hilton if "/data/" in u]
    assert sorted(u.split("?")[0].rsplit("/", 1)[1] for u in asked) == ["hotel", "reviews"]
    expect(page.locator("#mx-drawer .dr-own")).to_have_text("The hotel’s own photos")
    expect(page.locator("#mx-drawer .dr-all")).to_have_text("See all 16 photos")
    expect(page.locator("#mx-drawer .dr-hotel:not([hidden]) .dr-gal")).to_be_hidden()      # the mosaic replaces the one-photo gallery
    expect(page.locator("#mx-drawer .dr-score")).to_have_text("7.6")
    expect(page.locator("#mx-drawer .dr-rev").first).to_contain_text("Excellent airport shuttle service and facilities")
    expect(page.locator("#mx-drawer .dr-cat").first).to_contain_text("Cleanliness")
    shot(page, f"hotel-{viewport['width']}")
    page.locator("#mx-drawer .dr-ph").first.click()
    box = page.locator("dialog.dr-lb")
    expect(box).to_be_visible()
    expect(box.locator(".dr-lb-c")).to_have_text("1 of 16")
    expect(box.locator("figcaption")).to_have_text("Hotel building")
    shot(page, f"lightbox-{viewport['width']}")
    page.keyboard.press("ArrowRight")
    expect(box.locator(".dr-lb-c")).to_have_text("2 of 16")
    expect(box.locator("figcaption")).to_have_text("Lobby")
    box.locator("[data-go='-1']").click()
    box.locator("[data-go='-1']").click()
    expect(box.locator(".dr-lb-c")).to_have_text("16 of 16")      # it wraps round
    page.keyboard.press("Escape")
    expect(box).to_be_hidden()
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(1).click()      # another square, the same hotel: kept, not asked again
    page.wait_for_timeout(600)
    assert len([u for u in hilton if "/data/hotel" in u]) == 1


def test_a_room_you_can_choose_wears_the_hotels_photo_of_it_when_the_names_match(matrix, hilton, monkeypatch):  # noqa: F811
    page = matrix(DESKTOP)
    page.wait_for_selector(".mx-sq.is-ok")
    # the stand's room is "Two queens"; the recorded hotel has "2 Double Beds": the page matches by name only, so nothing is guessed
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(2).click()
    expect(page.locator("#mx-drawer .dr-photos")).to_be_visible()
    assert page.locator("#mx-drawer .dr-rthumb").count() == 0
    page.evaluate("""() => { const b = document.querySelector('#mx-drawer .dr-rooms:not([hidden]) .dr-opt'); b.dataset.roomname = '2 Double Beds';
        const slot = document.querySelector('#mx-drawer .dr-rich'); slot.dataset.state = 'idle'; slot.innerHTML = ''; }""")
    page.evaluate("document.querySelector('#mx-drawer .dr-alts, .dr-rooms') && document.querySelector('#mx-drawer .dr-opt').click()")
    expect(page.locator("#mx-drawer .dr-rthumb")).to_have_count(1)
