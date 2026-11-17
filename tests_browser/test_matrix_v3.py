"""F-275 in a real browser (docs/design/matrix-v3, D-860..): the sentence's suggestion chips, the side widgets folded into chips that open into cards, and the opened square's rich hotel
(the recorded Hilton answer, tests/fixtures/liteapi_hotel): the photo mosaic and its lightbox, the reviews as text, the room photos. Shots: F275_SHOTS=1 for docs/report/f275-*.png."""
import json as _json
import os
import re
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


def test_a_suggestion_chip_stages_one_word_changed_and_update_runs_the_sentence(matrix):      # F-280: a chip stages; Update searches  # noqa: F811
    page = matrix(DESKTOP)
    expect(page.locator(".v2-hint")).to_have_text("Change any word")
    chip = page.locator(".v2-sug", has_text="A week later")
    expect(chip).to_be_visible()
    assert chip.bounding_box()["height"] >= 47.5
    chip.click()
    assert "d=2026-12-19" not in page.url      # staged, not searched
    expect(page.locator('#v2-sent .v2-w[data-k="start"]')).to_have_text("Sat, Dec 19")
    page.locator(".v2-update").click()
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


# ---- the live check's fixes (2026-11-16) ------------------------------------------------------------------------------------------------------------------------

def _big_photos(page):
    """Every hotel photo is a real-sized 3000 x 2000 picture, as the live ones are (the first live check drew one photo 1400px tall)."""
    from io import BytesIO

    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (3000, 2000), (90, 120, 160)).save(buf, "JPEG")
    jpeg = buf.getvalue()
    for host in ("https://static.cupid.travel/**", "https://www.hilton.com/**"):
        page.route(host, lambda route: route.fulfill(status=200, content_type="image/jpeg", body=jpeg))


@pytest.mark.parametrize("viewport, cap", [(DESKTOP, 26 * 16), (PHONE, 16 * 16)], ids=["1440", "390"])
def test_the_photo_mosaic_is_a_capped_block_whatever_size_the_photos_are(matrix, hilton, viewport, cap):  # noqa: F811
    page = matrix(viewport)
    _big_photos(page)
    page.wait_for_selector(".mx-sq.is-ok")
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(1).click()
    expect(page.locator("#mx-drawer .dr-mos")).to_be_visible()
    page.locator("#mx-drawer .dr-mos").scroll_into_view_if_needed()
    page.wait_for_function("() => [...document.querySelectorAll('#mx-drawer .dr-mos img')].filter(i => i.offsetParent).every(i => i.complete && i.naturalWidth === 3000)")      # the big pictures really arrived
    got = page.evaluate("""() => { const m = document.querySelector('#mx-drawer .dr-mos').getBoundingClientRect(), d = document.querySelector('#mx-drawer .dr').getBoundingClientRect();
        return {h: m.height, w: m.width, dw: d.width, tiles: [...document.querySelectorAll('#mx-drawer .dr-mos .dr-ph:not([hidden])')].map(e => [e.getBoundingClientRect().width, e.getBoundingClientRect().height])}; }""")
    assert 150 <= got["h"] <= cap + 1, got
    assert len(got["tiles"]) == 5 or viewport is PHONE and len(got["tiles"]) >= 3, got
    assert all(h <= got["h"] and w <= got["w"] for w, h in got["tiles"]), got
    shot(page, f"mosaic-{viewport['width']}")


def test_nothing_in_the_opened_square_runs_past_its_right_edge_but_the_strips_that_scroll(matrix, hilton):  # noqa: F811
    page = matrix(DESKTOP)
    _big_photos(page)
    page.wait_for_selector(".mx-sq.is-ok")
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(1).click()
    expect(page.locator("#mx-drawer .dr-rooms-or-none, #mx-drawer .dr-hrooms")).to_be_visible()
    page.wait_for_timeout(600)
    out = page.evaluate("""() => { const dr = document.querySelector('#mx-drawer .dr'), edge = dr.getBoundingClientRect().right, scrollers = '.dr-hrooms, .dr-alts, .dr-track, .dr-seg, .dr-revs-x';
        return [...dr.querySelectorAll('*')].filter(e => !e.closest(scrollers) && !e.closest('[hidden]') && e.getClientRects().length && e.getBoundingClientRect().right > edge + 1)
          .map(e => e.className + ' ' + Math.round(e.getBoundingClientRect().right - edge)); }""")
    assert out == [], out
    strip = page.evaluate("() => { const s = document.querySelector('#mx-drawer .dr-hrooms'), r = s.getBoundingClientRect(), d = document.querySelector('#mx-drawer .dr').getBoundingClientRect(); return [s.scrollWidth >= s.clientWidth, r.right <= d.right + 1, getComputedStyle(s).overflowX]; }")
    assert strip == [strip[0], True, "auto"] and strip[0] is not None, strip      # the rooms sit in their own strip, which scrolls sideways when they are more than fit
    cats = page.evaluate("() => { const c = [...document.querySelectorAll('#mx-drawer .dr-cat')].map(e => Math.round(e.getBoundingClientRect().top)); return [...new Set(c)].length; }")
    assert cats >= 2      # the sentiment categories wrap into a grid, not one clipped row


def test_reviews_are_not_on_the_square_and_a_score_without_words_is_a_bare_row_in_the_drawer(matrix, hilton):  # noqa: F811
    page = matrix(DESKTOP)
    page.wait_for_selector(".mx-sq.is-ok")
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(1).click()
    expect(page.locator("#mx-drawer .dr-dash")).to_be_visible()
    assert page.locator("#mx-drawer .dr-top .dr-rev, #mx-drawer .dr-reviews, #mx-drawer .dr-rnone").count() == 0      # F-290: nothing long on the square
    page.locator("#mx-drawer .dr-dash .tr-read").click()
    docs = _json.loads((FIX / "reviews.json").read_text())["data"]
    bare = [r for r in docs if not (r.get("headline") or r.get("pros") or r.get("cons"))]
    rows = page.locator(".rv .rv-item")
    assert bare and rows.count() == len(docs)
    assert page.locator(".rv .rv-item:has(.dr-rhead), .rv .rv-item:has(.dr-rp), .rv .rv-item:has(.dr-rc)").count() == len(docs) - len(bare)      # a score with no words is its head and nothing else


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_square_caption_reads_4_5_to_1_on_its_own_square_in_every_state(matrix, scheme):  # noqa: F811
    page = matrix(DESKTOP, scheme=scheme)
    page.wait_for_selector(".mx-sq.is-ok")
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-low").first.click()      # the cheapest start, opened: blue with a "Cheapest" caption
    page.wait_for_selector(".mx-sq.is-open")
    page.wait_for_timeout(700)
    rows = page.evaluate("""() => {
      const ctx = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
      const rgba = c => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1); const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
      const over = (top, under) => top[3] >= 1 ? top : [0, 1, 2].map(i => top[i] * top[3] + under[i] * (1 - top[3])).concat([1]);
      const bg = el => { const chain = []; for (let e = el; e; e = e.parentElement) chain.push(rgba(getComputedStyle(e).backgroundColor)); let c = rgba(getComputedStyle(document.documentElement).backgroundColor); if (c[3] < 1) c = [255, 255, 255, 1];
        return chain.reverse().reduce((acc, x) => over(x, acc), c); };
      const lum = c => { const v = c.slice(0, 3).map(x => x / 255).map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
      const out = [];
      document.querySelectorAll('.mx-sq.is-ok').forEach(sq => { const a = getComputedStyle(sq, '::after'); if (!a.content || a.content === 'none' || a.content === '""' || a.content === 'normal') return;
        const fg = over(rgba(a.color), bg(sq)), b = bg(sq), l1 = lum(fg), l2 = lum(b);
        out.push([sq.className.replace('mx-sq ', ''), a.content, ((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)).toFixed(2)]); });
      return out; }""")
    assert rows, "no caption was drawn"
    assert any("is-open" in c for c, _, _ in rows), rows      # the opened (blue) square is among them
    low = [r for r in rows if float(r[2]) < 4.5]
    assert low == [], low
