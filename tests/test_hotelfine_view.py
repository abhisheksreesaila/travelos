"""F-282: the dashboard, the fine print and the review drawer as the page draws them (pages/hotelview.py, fineprint.py, reviewdrawer.py), from the recorded Hilton Los Angeles Airport answers
(tests/fixtures/liteapi_hotel). A page's script fills the rows that depend on the chosen room and flight: tests_browser/test_hotelfine.py."""
import json
import re
from html import unescape
from pathlib import Path

import pytest
from fasthtml.common import to_xml

from gitaway import liteapi
from gitaway.pages import hotelview

FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
IMPORTANT = "<p>A resort fee of USD 35 per night is charged at the property.</p><p>Guests must be 21 or older to check in.</p>"


def hotel(important=None, place=True):
    d = json.loads((FIX / "hotel.json").read_text(encoding="utf-8"))
    if place:
        d["data"]["location"] = {"latitude": 33.9461921, "longitude": -118.3816538}      # the recording has none: F-284's card needs a place
    if important is not None:
        d["data"]["hotelImportantInformation"] = important
    return liteapi.read_hotel(d)


@pytest.fixture(scope="module")
def hundred():
    return liteapi.read_reviews(json.loads((FIX / "reviews100.json").read_text(encoding="utf-8")))


def draw(h, rv, pt=""):
    return to_xml(hotelview.rich(h, rv, pt))


def test_the_dashboard_is_the_score_with_words_and_count_the_strip_and_the_category_bars_beside_the_photos(hundred):
    html = draw(hotel(), hundred)
    top = html[html.index('class="dr-top'):html.index('class="dr-info"')]
    assert 'class="dr-photos"' in top and 'class="dr-dash"' in top and top.index("dr-photos") < top.index("dr-dash")
    assert '<span class="dr-score num">7.6</span>' in top and "Good" in top and "6,263 reviews" in top
    assert "How the last 100 reviews went" in top and "The last 10 were all 8 or more." in top
    assert 'aria-label="Cleanliness 8 out of 10"' in top and 'aria-label="Value for Money 6.5 out of 10"' in top
    assert 'aria-label="Rated 7.6 out of 10, Good, from 6,263 reviews. Read the guests’ reviews"' in top


def test_the_fine_print_has_its_five_cards_in_order_and_the_usual_line_last(hundred):
    html = draw(hotel(IMPORTANT), hundred)
    fine = html[html.index('class="fp"'):]
    heads = [fine.index(t) for t in ("The fine print, up front", "Costs not in the price", "Policies that bite", "Fits your family?", "Getting there and around", "What guests complain about", "The usual: ")]
    assert heads == sorted(heads)
    assert fine.index("See it from above") < fine.index("What guests complain about") and fine.index("Getting there and around") < fine.index("See it from above")      # F-284's card lives in "Getting there and around"


def test_a_cost_the_hotel_names_wears_heads_up_and_a_listed_amenity_does_not(hundred):
    html = draw(hotel(IMPORTANT), hundred)
    fine = html[html.index('class="fp"'):]
    assert re.search(r'A resort fee of USD 35 per night is charged at the property\.<span class="fp-flag">Heads up</span>', fine)
    assert re.search(r"Guests must be 21 or older to check in\.</span>", fine) and "Guests must be 21 or older to check in.<span" not in fine      # a condition, not a cost: shown, not flagged
    assert 'class="fp-usual"' in fine and "WiFi available" in fine.split('class="fp-usual"')[1]


def test_what_the_hotel_did_not_say_is_said_not_listed_never_none(hundred):
    fine = draw(hotel(), hundred)
    fine = fine[fine.index('class="fp"'):]
    assert "Parking</span>" in fine and "Listed by the hotel; the price is not listed" in fine
    assert "Cribs: not listed" in fine and "Kids’ club: not listed" in fine and "Connecting rooms: not listed" in fine
    assert "Paid at the hotel: not listed" in fine and "Refundability: not listed" in fine      # the script fills these from the chosen room
    assert "Resort fee" not in fine and "None charged" not in fine and "No fees" not in fine


def test_a_complaint_opens_the_matching_reviews_and_one_no_review_says_is_not_a_button(hundred):
    fine = draw(hotel(), hundred)
    fine = fine[fine.index('class="fp"'):fine.index('class="fp-usual"')]
    m = re.search(r'data-rv-open="some" data-rv-ids="([\d,]+)" data-rv-why="Pricey \(breakfast, taxes, parking, lobby shop\)"', unescape(fine))
    assert m and len(m[1].split(",")) > 3 and f"Read the {len(m[1].split(','))} reviews" in fine
    assert "No review we fetched says it" in fine


def test_the_drawer_lists_every_review_newest_first_with_a_chip_for_each_traveller_type(hundred):
    html = draw(hotel(), hundred)
    drawer = html[html.index("<aside"):]
    assert drawer.count('class="rv-item"') == 100 and 'role="dialog"' in drawer and "What guests said" in drawer
    dates = re.findall(r"· (\d{4}-\d{2}-\d{2})</small>", drawer)
    assert dates == sorted(dates, reverse=True) and len(dates) == 100
    chips = re.findall(r'data-rv-type="([a-z_]*)" aria-pressed="(?:true|false)" class="rv-chip">([^<]+)<', drawer)
    assert chips == [("", "All 100"), ("couple", "Couple 51"), ("solo_traveller", "Solo 28"), ("extended_group", "Group 13"), ("family_with_children", "Family 8")]
    assert drawer.count('data-type="couple"') == 51 and drawer.count('data-type="family_with_children"') == 8


def test_no_reviews_means_no_drawer_no_open_buttons_and_the_score_is_plain(hundred):
    html = draw(hotel(), None)
    assert "<aside" not in html and "data-rv-open" not in html and 'class="dr-rate"' in html and "dr-scorebtn" not in html
    assert "Complaints: not listed" in html


def test_a_guest_or_hotel_line_is_text_never_markup():
    evil = liteapi.Review("<script>alert(1)</script>", "2026-11-10", 3, "couple", "us", "<img src=x onerror=alert(2)>", "", "a & b", "")
    rv = liteapi.HotelReviews((evil,) * 6, (), (), ("a & b <i>costly</i>",), 6)
    html = draw(hotel("<p>Fee <b>USD 9</b><script>x()</script></p>"), rv)
    assert "<script>" not in html and "<img src=x" not in html and "<i>costly" not in html and "<b>USD" not in html
    assert "a &amp; b &lt;i&gt;costly&lt;/i&gt;" in html


def test_the_showcase_has_the_sample_dashboard_and_fine_print_labelled_and_off_it_nothing(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = to_xml(hotelview.sample_fragment("San Diego"))
    assert "Sample: this is a real hotel’s recorded data" in html and "The hotels in this square are made up" in html
    assert "The fine print, up front" in html and 'class="rv-item"' in html and "av-card" in html and "Sample view" in html
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert hotelview.sample_fragment("San Diego") == ""
