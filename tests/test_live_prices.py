"""F-267: live prices on gitaway.me, booking opens soon (D-767..D-771). With a live LiteAPI key (not `sand_`) a square's stay is LiteAPI's public selling price; Book says "Booking opens
soon" in production and plays the sample stand-in off it (no LiteAPI booking call either way); a sandbox key is as it was. The live answer is hand-shaped from a probe
(tests/fixtures/liteapi_live/README.md): no test holds a key."""
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gitaway import auth, liteapi, matrixbook as mb
from gitaway.pages import tripmatrix as page
from tests.test_liteapi import KEY, answer
from tests.test_liteapi_book import BOOK, PREBOOK
from tests.test_matrixbook_page import FORM, FRAG, GUEST, Sandbox, stays_booked, text, token
from tests.test_signin import sign_in
from tests.test_tripmatrix_page import MATRIX

LIVE = "live_test-key-not-real"
LIVE_ANSWER = Path(__file__).parent / "fixtures" / "liteapi_live" / "hotel_rates.json"
AT = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
TILE = "/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"


class LiveSearch(Sandbox):
    """Sandbox's flights and booking recordings, with the hotels' answer the live probe shaped."""

    def __call__(self, url, headers, body, timeout):
        if "/hotels/rates" in url:
            self.asked.append((url, headers, json.loads(body)))
            return 200, "application/json", LIVE_ANSWER.read_bytes()
        return super().__call__(url, headers, body, timeout)

    def booking_calls(self):
        return [u for u, _, _ in self.asked if u in (PREBOOK, BOOK)]


def live_answer() -> dict:
    return json.loads(LIVE_ANSWER.read_text())


# ---- the price a stay shows ---------------------------------------------------------------------------------------------------

def test_a_live_key_shows_the_public_selling_price_cheapest_first_with_the_fee_paid_at_the_hotel_said(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    found = liteapi.read_stays(live_answer(), AT)
    assert [(s.name, s.cents, s.due_at_stay_cents, s.refundable) for s in found] == [
        ("Best Western PLUS Island Palms Hotel & Marina", 38791, 0, True), ("Margaritaville San Diego Resort", 41594, 12000, False)]
    assert [r.cents for r in found[1].rooms] == [41594]


def test_a_sandbox_key_still_shows_the_retail_rate(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    assert [s.cents for s in liteapi.read_stays(live_answer(), AT)] == [33731, 36169]
    assert [s.cents for s in liteapi.read_stays(answer("hotel_rates.json"), AT)][0] == 59694


def test_a_live_room_with_no_public_price_falls_back_to_the_retail_rate_and_says_nothing_more(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    doc = live_answer()
    del doc["data"][0]["roomTypes"][0]["suggestedSellingPrice"]
    assert [s.cents for s in liteapi.read_stays(doc, AT)] == [33731, 41594]


def test_a_nonsense_public_price_is_ignored_not_shown(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    doc = live_answer()
    doc["data"][0]["roomTypes"][0]["suggestedSellingPrice"] = {"amount": -5, "currency": "USD"}
    doc["data"][1]["roomTypes"][0]["suggestedSellingPrice"] = {"amount": 415.94, "currency": "EUR"}
    assert [s.cents for s in liteapi.read_stays(doc, AT)] == [33731, 36169]


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    fake = LiveSearch()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    return fake


def test_the_squares_total_is_the_flight_and_the_public_price_the_stay_shows(live, client, monkeypatch):
    j = client.get(TILE).json()
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    liteapi.clear()
    retail = client.get(TILE).json()
    assert j["s"] == retail["s"] == "ok" and j["c"] - retail["c"] == 38791 - 33731
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    drawer = client.get(TILE).json()["drawer"]
    assert "$387.91" in text(drawer) and "$337.31" not in text(drawer)


# ---- how Book behaves ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("showcase_on, key, production, want", [
    ("1", "", False, mb.SANDBOX), ("1", LIVE, True, mb.STAND_IN), ("0", KEY, False, mb.SANDBOX), ("0", KEY, True, mb.SANDBOX),
    ("0", LIVE, False, mb.STAND_IN), ("0", LIVE, True, mb.LIVE)])
def test_book_is_the_sandbox_the_stand_in_or_real_by_the_key_and_where_it_runs(monkeypatch, showcase_on, key, production, want):
    """F-274 (D-841): a live key in production books for real; the SOON of F-267 is now only the switch below."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", showcase_on)
    monkeypatch.setenv("LITEAPI_KEY", key)
    monkeypatch.setattr(auth, "production", lambda: production)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    assert mb.mode() == want


@pytest.mark.parametrize("production, flag, want", [(True, "0", mb.SOON), (True, "1", mb.LIVE), (False, "1", mb.LIVE), (False, "0", mb.STAND_IN), (False, "", mb.STAND_IN)])
def test_gitaway_live_booking_switches_real_booking_off_in_production_and_on_elsewhere(monkeypatch, production, flag, want):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", flag)
    monkeypatch.setattr(auth, "production", lambda: production)
    assert mb.mode() == want


def test_switched_off_in_production_book_is_disabled_and_says_booking_opens_soon_and_nothing_is_booked(live, client, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")      # the switch: production books for real unless this says 0
    drawer = client.get(TILE).json()["drawer"]
    words = text(drawer)
    assert "Booking opens soon" in words and "Sandbox booking" not in words and "Sample booking" not in words
    button = re.search(r'<button[^>]*class="[^"]*dr-book-soon[^"]*"[^>]*>', drawer).group(0)
    assert "disabled" in button and 'action="/plan/matrix/book"' not in drawer and "Save this trip" in words
    for path in ("/plan/matrix/book", "/plan/matrix/book/confirm"):      # a forged post gets the same words and no call
        r = client.post(path, data={**FORM, "token": "x", **GUEST}, headers=FRAG)
        assert "Booking opens soon" in text(r.text) and r.status_code == 403
    assert live.booking_calls() == [] and stays_booked() == []
    page_html = text(client.get(MATRIX).text)
    assert "Sandbox booking" not in page_html and "sandbox" not in page_html.lower()


def test_off_production_a_live_key_plays_the_sample_stand_in_and_asks_liteapi_to_book_nothing(live, client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: False)
    sign_in(client)
    drawer = client.get(TILE).json()["drawer"]
    assert "Sample booking: nothing is booked or charged." in text(drawer) and "Sandbox booking" not in text(drawer) and 'action="/plan/matrix/book"' in drawer
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    words = text(html)
    assert "Sample booking: nothing is booked or charged" in words and "Who is the lead guest?" in words and "Sandbox booking" not in words
    done = text(client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG).text)
    assert "your sample booking is confirmed" in done and "SAMPLE-" in done and "Sandbox booking" not in done
    assert live.booking_calls() == []
    rows = stays_booked()
    assert len(rows) == 1 and rows[0]["sample"] == 1


def test_a_sandbox_key_books_as_it_did(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Sandbox()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    sign_in(client)      # the dev sign-in is off in production, so sign in first
    monkeypatch.setattr(auth, "production", lambda: True)
    drawer = client.get(TILE).json()["drawer"]
    assert "Sandbox booking: nothing is charged." in text(drawer) and "Booking opens soon" not in text(drawer) and 'action="/plan/matrix/book"' in drawer
    client.post("/plan/matrix/book", data=FORM, headers=FRAG)
    assert len(fake.calls(PREBOOK)) == 1


def test_the_showcase_is_still_a_sample_booking_even_with_a_live_key_in_production(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: True)
    drawer = client.get(TILE).json()["drawer"]
    assert "Sample booking: nothing is booked or charged." in text(drawer) and "Booking opens soon" not in text(drawer)


# ---- the about-these-prices card -----------------------------------------------------------------------------------------------

def test_the_about_card_says_the_prices_are_live_from_liteapi_with_where_the_time_they_were_checked_goes(live, client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    html = client.get(MATRIX).text
    about = text(html.split('class="mx-tk mx-about"')[1].split("mx-about-foot")[0])
    assert "live from LiteAPI" in about and "Sold by Nuitée through LiteAPI" in about and "never sees your card" in about and "sandbox" not in about.lower() and 'id="mx-age"' in html
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")      # the switch
    assert "Booking opens soon" in text(client.get(MATRIX).text.split('class="mx-tk mx-about"')[1].split("mx-about-foot")[0])
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING")
    monkeypatch.setattr(auth, "production", lambda: False)
    about = text(client.get(MATRIX).text.split('class="mx-tk mx-about"')[1].split("mx-about-foot")[0])
    assert "live from LiteAPI" in about and "A stay booked here is a sample booking: nothing is booked or charged." in about


def test_a_sandbox_keys_card_is_the_one_it_was(monkeypatch, client):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    assert page.FINE in client.get(MATRIX).text and "live from LiteAPI" not in client.get(MATRIX).text


# ---- the dev task ---------------------------------------------------------------------------------------------------------------

def test_dev_live_reads_the_key_by_the_shell_from_its_private_file_and_holds_no_key():
    task = tomllib.loads((Path(__file__).parent.parent / "pixi.toml").read_text())["tasks"]["dev-live"]
    command = task if isinstance(task, str) else task["cmd"]
    assert "set -a; . ~/.config/gitaway/liteapi-live.env; set +a" in command
    assert "GITAWAY_SHOWCASE=0" in command and "GITAWAY_DEV_LOGIN=1" in command and "python main.py" in command
    assert not re.search(r"LITEAPI_KEY\s*=\s*\S", command) and "live_" not in command


# ---- F-269: the saved square's next step ----------------------------------------------------------------------------------------

def save_next(client):
    r = client.post("/plan/matrix/save", data=FORM, headers=FRAG)
    return r.json()


def test_plan_this_trip_after_save_f269_when_booking_is_switched_off(live, client, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")
    j = save_next(client)
    assert j["saved"] == "Saved to your trip." and j["trip"] == "/trip/plan" and j["next"] == "Plan this trip"


def test_open_the_trip_after_save_when_booking_is_real(live, client, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    assert save_next(client)["next"] == "Open the trip"


def test_plan_this_trip_after_save_f269_in_the_stand_in(live, client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: False)
    sign_in(client)
    assert save_next(client)["next"] == "Plan this trip"


def test_plan_this_trip_after_save_f269_sandbox_keeps_open_the_trip(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Sandbox())
    sign_in(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    assert save_next(client)["next"] == "Open the trip"
