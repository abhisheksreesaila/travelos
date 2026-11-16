"""A hotel's own details and its reviews (F-275, D-860): LiteAPI's /data/hotel and /data/reviews, read from a trimmed real answer for Hilton Los Angeles Airport
(tests/fixtures/liteapi_hotel, recorded 2026-11-16), through the gate and the cache like the other calls."""

import json
from pathlib import Path

import pytest

from gitaway import liteapi

FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
KEY = "sand_test-key-not-real"
ID = "lp1b8e6"


class Fake:
    def __init__(self, hotel=None, reviews=None, status=200):
        self.asked, self.hotel, self.reviews, self.status = [], hotel, reviews, status

    def __call__(self, url, headers, body, timeout):
        self.asked.append(url)
        if self.status != 200:
            return self.status, "application/json", b"{}"
        if "/data/reviews" in url:
            return 200, "application/json", self.reviews if self.reviews is not None else (FIX / "reviews.json").read_bytes()
        if "/data/hotel" in url:
            return 200, "application/json", self.hotel if self.hotel is not None else (FIX / "hotel.json").read_bytes()
        raise AssertionError(url)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def test_the_hotel_comes_with_its_photos_captions_facilities_and_check_in(fake):
    h = liteapi.hotel(ID)
    assert (h.name, h.stars, h.rating, h.review_count, h.address) == ("Hilton Los Angeles Airport", 4, 7.6, 6263, "5711 West Century Boulevard")
    assert (h.photos[0].url, h.photos[0].caption) == ("https://static.cupid.travel/hotels/490862436.jpg", "Hotel building")
    assert h.photos[1].caption == "Lobby" and len(h.photos) == 16
    assert h.facilities[:2] == ("Fitness facilities", "WiFi available") and len(h.facilities) == 24
    assert (h.checkin, h.checkout) == ("04:00 PM", "12:00 PM")
    assert fake.asked == [f"https://api.liteapi.travel/v3.0/data/hotel?hotelId={ID}"]


def test_the_description_is_plain_paragraphs_with_a_lead(fake):
    first = liteapi.hotel(ID).paragraphs[0]
    assert first.lead == "Convenient Airport Shuttle Service"
    assert first.text.startswith("Benefit from the free 24-hour shuttle service to Los Angeles International Airport")
    assert "<" not in first.text and "<" not in first.lead


def test_each_room_has_its_name_beds_size_sleeps_and_its_own_photos(fake):
    rooms = liteapi.hotel(ID).rooms
    r = rooms[0]
    assert (r.name, r.beds, r.size_m2, r.sleeps) == ("2 Double Beds", ("Double bed",), None, 4)
    assert len(r.photos) == 3 and all(p.startswith("https://") for p in r.photos)
    assert (rooms[1].name, rooms[1].size_m2) == ("2 Double Hearing Accessible Room", 30)


def test_a_photo_that_is_not_https_never_reaches_a_page(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    doc = json.loads((FIX / "hotel.json").read_text())
    for i, bad in enumerate(("javascript:alert(1)", "http://insecure.example/a.jpg")):
        doc["data"]["hotelImages"][i]["url"] = doc["data"]["hotelImages"][i]["urlHd"] = bad
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(hotel=json.dumps(doc).encode()))
    urls = [p.url for p in liteapi.hotel(ID).photos]
    assert len(urls) == 14 and all(u.startswith("https://") for u in urls)


def test_a_hotel_is_asked_once_and_kept(fake):
    assert liteapi.hotel(ID) is liteapi.hotel(ID)
    assert len(fake.asked) == 1


def test_the_old_description_call_shares_the_hotel_call(fake):
    assert liteapi.about(ID).startswith("Convenient Airport Shuttle Service")
    liteapi.hotel(ID)
    assert len(fake.asked) == 1


def test_no_key_no_call_and_a_failed_call_is_none(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", "")
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: pytest.fail("asked without a key"))
    assert liteapi.hotel(ID) is None and liteapi.reviews(ID) is None
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(status=503))
    assert liteapi.hotel("lp503") is None and liteapi.reviews("lp503") is None


def test_an_id_that_is_not_an_id_is_never_asked(fake):
    assert liteapi.hotel("../x?y=1") is None and liteapi.reviews("a b") is None
    assert fake.asked == []


def test_reviews_carry_who_when_score_type_and_both_sides_in_their_own_words(fake):
    rv = liteapi.reviews(ID)
    first = rv.items[0]
    assert (first.name, first.score, first.type, first.country, first.date) == ("Maria", 8, "extended_group", "au", "2026-11-14")
    assert first.headline == "Excellent airport shuttle service and facilities" and first.pros == "Clean and inviting"
    assert first.cons.startswith("Breakfast was not included") and rv.total == 6263 and len(rv.items) == 8
    assert fake.asked == [f"https://api.liteapi.travel/v3.0/data/reviews?hotelId={ID}&limit=8&getSentiment=true"]


def test_the_sentiment_has_a_score_and_a_sentence_per_category_and_the_pros_and_cons(fake):
    rv = liteapi.reviews(ID)
    assert (rv.categories[0].name, rv.categories[0].rating) == ("Cleanliness", 8)
    assert rv.categories[0].description.startswith("Overall reviewers frequently noted clean") and len(rv.categories) == 8
    assert rv.pros[0] and rv.cons[0] and len(rv.pros) == 7 and len(rv.cons) == 5


def test_reviews_are_kept_and_a_hotel_with_no_reviews_says_so(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fake(reviews=json.dumps({"data": [], "sentimentAnalysis": None, "total": 0}).encode())
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    rv = liteapi.reviews("lp0")
    assert rv.items == () and rv.categories == () and rv.total == 0
    assert liteapi.reviews("lp0") is rv and len(f.asked) == 1


def test_a_spent_budget_is_not_asked(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "_spend", lambda *a, **k: False)
    assert liteapi.hotel(ID) is None and fake.asked == []
