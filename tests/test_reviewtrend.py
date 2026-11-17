"""F-278: the last hundred reviews as a trend (gitaway/reviewtrend.py, drawn by pages/hotelview.py). The recorded answer is tests/fixtures/liteapi_hotel/reviews100.json (shaped like LiteAPI's
/data/reviews?limit=100: 100 reviews over 18 days, 64 with words, types couple 51 / solo 28 / group 13 / family 8, newest first); its counts were checked by hand, not by the code under test
(good 53, mixed 22, poor 25; the newest ten average 9.1 and are all 8 or more; the 8 family reviews average 7.75)."""
import json
from pathlib import Path

import pytest

from gitaway import liteapi, reviewtrend as rt
from gitaway.pages import hotelview

FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
KEY = "sand_test-key-not-real"


@pytest.fixture(scope="module")
def hundred():
    return liteapi.read_reviews(json.loads((FIX / "reviews100.json").read_text(encoding="utf-8")))


def rev(score, date="2026-11-10", type="couple", name="Ana", headline="", pros="", cons="", source=""):
    return liteapi.Review(name, date, score, type, "us", headline, pros, cons, source)


def run(scores):
    """Reviews newest first (LiteAPI's order) with these scores, one a day going back."""
    return [rev(s, f"2026-11-{16 - i:02d}") for i, s in enumerate(scores)]


def test_a_score_is_good_from_8_mixed_from_6_and_poor_below_that():
    assert [rt.kind(s) for s in (10, 8, 7.9, 7, 6, 5.9, 5, 1)] == ["good", "good", "mixed", "mixed", "mixed", "poor", "poor", "poor"]


def test_the_strip_is_every_scored_review_oldest_to_newest_with_its_counts(hundred):
    t = rt.trend(hundred.items, 7.6, "couple")
    assert len(t.dots) == 100 and (t.good, t.mixed, t.poor) == (53, 22, 25)
    assert (t.dots[0].date, t.dots[-1].date) == ("2026-10-30", "2026-11-16") and t.span == "Oct 30 to Nov 16"
    assert [d.date for d in t.dots] == sorted(d.date for d in t.dots)
    assert [d.score for d in t.dots[-10:]] == [10, 9, 8, 9, 9, 10, 8, 9, 9, 10]      # the newest ten, now oldest to newest
    assert rt.trend([rev(None)], 8) is None      # nothing scored: no strip


def test_the_recent_average_is_said_only_when_it_differs_from_the_hotels_rating_by_half_a_point(hundred):
    words = lambda overall: rt.trend(hundred.items, overall).recent      # noqa: E731
    assert words(7.6) == "The last 10 averaged 9.1, above the hotel’s 7.6."
    assert words(8.6) == "The last 10 averaged 9.1, above the hotel’s 8.6."      # exactly half a point counts
    assert words(8.7) == ""      # 0.4: not worth saying
    assert words(9.6) == "The last 10 averaged 9.1, below the hotel’s 9.6."
    assert words(None) == ""
    assert rt.recent_words(rt._oldest_first(run([9] * 9)), 7) == ""      # fewer than ten reviews: no recent average


def test_a_streak_is_the_newest_run_of_good_scores_from_six_or_three_poor_of_the_last_six(hundred):
    assert rt.trend(hundred.items).streak == "The last 10 were all 8 or more."
    assert rt.streak_words(rt._oldest_first(run([8, 9, 10, 8, 9, 8, 4, 9]))) == "The last 6 were all 8 or more."
    assert rt.streak_words(rt._oldest_first(run([8, 9, 10, 8, 9, 7, 9]))) == ""      # a 7 breaks it
    assert rt.streak_words(rt._oldest_first(run([3, 9, 4, 9, 5, 9, 10]))) == "3 of the last 6 were poor (5 or less)."
    assert rt.streak_words(rt._oldest_first(run([3, 9, 4, 9, 9, 9, 10]))) == ""      # two poor are not a streak
    assert rt.streak_words(rt._oldest_first(run([9, 9, 9, 9, 9]))) == ""      # fewer than six reviews


def test_the_average_for_travellers_like_you_needs_five_reviews_of_their_type(hundred):
    assert rt.trend(hundred.items, None, "family_with_children").like_you == "Families with children: 7.8 on average, from 8 of the last 100 reviews."
    assert rt.trend(hundred.items, None, "couple").like_you.startswith("Couples: ") and "from 51 of the last 100 reviews." in rt.trend(hundred.items, None, "couple").like_you
    four = [rev(9, type="family_with_children") for _ in range(4)] + [rev(5) for _ in range(6)]
    assert rt.trend(four, None, "family_with_children").like_you == ""
    assert rt.trend(four + [rev(9, type="family_with_children")], None, "family_with_children").like_you == "Families with children: 9.0 on average, from 5 of the last 11 reviews."
    assert rt.trend(hundred.items, None, "").like_you == ""


@pytest.mark.parametrize("adults, kids, expect", [(1, [], "solo_traveller"), (2, [], "couple"), (3, [], "extended_group"), (2, [7], "family_with_children"), (1, [3, 9], "family_with_children")])
def test_the_partys_traveller_type_is_what_liteapi_calls_it(adults, kids, expect):
    assert rt.party_type(adults, kids) == expect


def test_the_source_is_what_liteapi_names_in_its_own_spelling_and_never_a_guess():
    assert rt.source_name([rev(9, source="nuitee"), rev(9, source="nuitee"), rev(8, source="other")]) == "Nuitée"
    assert rt.source_name([rev(9)]) == ""
    assert hotelview.source_line(liteapi.HotelReviews((rev(9, source="nuitee"),), (), (), (), 1)) == "Reviews from Nuitée (LiteAPI)"
    line = hotelview.source_line(liteapi.HotelReviews((rev(9),), (), (), (), 1))
    assert line == "Reviews from LiteAPI" and "Google" not in line and "Expedia" not in line


def test_the_fragment_draws_the_strip_with_its_streak_and_the_drawer_holds_the_source(hundred):
    h = liteapi.read_hotel(json.loads((FIX / "hotel.json").read_text(encoding="utf-8")))
    html = hotelview.to_xml(hotelview.rich(h, hundred, "family_with_children"))
    square = html.split("<aside")[0]
    assert "Last 100 reviews · Oct 30 to Nov 16" in square
    assert square.count('class="tr-d is-') == 103      # 100 dots and the legend's three
    assert "The last 10 were all 8 or more." in square      # F-290: one streak line; the average and the party's own average are in the fine print and the drawer
    assert "Reviews from Nuitée (LiteAPI)" in html.split("<aside")[1] and 'class="dr-rev"' not in square
    assert "8 or more · 53" in html and "6 or 7 · 22" in html and "5 or less · 25" in html
    assert 'aria-label="The last 100 reviews, oldest to newest: 53 good, 22 mixed, 25 poor"' in html


def test_what_a_guest_wrote_is_escaped_never_markup():
    evil = rev(2, name="<script>alert(1)</script>", headline='<img src=x onerror="alert(2)">', pros="<b>bold</b>", cons="a & b", source="<i>x</i>")
    html = hotelview.to_xml(hotelview.rich(liteapi.read_hotel(json.loads((FIX / "hotel.json").read_text(encoding="utf-8"))), liteapi.HotelReviews((evil,) * 3, (), (), (), 3), "couple"))
    assert "<script>alert" not in html and "<img src=x" not in html and "<b>bold" not in html and "<i>x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "&lt;img" in html and "a &amp; b" in html


def test_the_reviews_are_one_call_for_a_hundred_kept_a_day(monkeypatch):
    asked = []

    def transport(url, headers, body, timeout):
        asked.append(url)
        return 200, "application/json", (FIX / "reviews100.json").read_bytes()
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", transport)
    liteapi.clear()
    assert len(liteapi.reviews("lp1b8e6").items) == 100 and len(liteapi.reviews("lp1b8e6").items) == 100
    assert asked == ["https://api.liteapi.travel/v3.0/data/reviews?hotelId=lp1b8e6&limit=100&getSentiment=true"]
