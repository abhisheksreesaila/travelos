"""F-260: the sky's mood is chosen by a plain rule from the trip's place and dates (gitaway/moods.py)."""
from datetime import date

import pytest

from gitaway import moods
from gitaway.partners import places


def mood(text, start=None, end=None):
    return moods.of_text(text, start, end)


def test_every_place_in_the_table_has_a_kind():
    missing = [p.name for p in places.known() if not moods.kind(places.resolve(p.name))]
    assert missing == []


@pytest.mark.parametrize("text, start, end, want", [
    ("Lake Tahoe", date(2026, 12, 20), date(2026, 12, 27), "snow"),
    ("Denver", date(2027, 1, 10), date(2027, 1, 14), "snow"),
    ("Vail", date(2027, 3, 1), date(2027, 3, 5), "snow"),
    ("Lake Tahoe", date(2026, 7, 10), date(2026, 7, 17), "hike"),
    ("Lake Tahoe", date(2026, 10, 1), date(2026, 10, 4), "hike"),
    ("San Diego", date(2026, 7, 10), date(2026, 7, 17), "beach"),
    ("San Diego", date(2026, 12, 10), date(2026, 12, 14), "beach"),
    ("Maui", None, None, "beach"),
    ("Yosemite", date(2026, 7, 4), date(2026, 7, 9), "hike"),
    ("Zion", date(2026, 12, 2), date(2026, 12, 6), "hike"),
    ("Chicago", date(2026, 6, 1), date(2026, 6, 4), "city"),
    ("New York", date(2026, 7, 1), date(2026, 7, 5), "city"),
    ("New York", date(2026, 12, 28), date(2027, 1, 2), "celebration"),
    ("New York", date(2026, 12, 31), date(2026, 12, 31), "celebration"),
    ("New York", date(2026, 12, 20), date(2026, 12, 27), "city"),
    ("New York", date(2027, 1, 2), date(2027, 1, 5), "celebration"),
    ("New York", date(2027, 1, 3), date(2027, 1, 5), "city"),
    ("Las Vegas", date(2026, 12, 30), date(2027, 1, 2), "celebration"),
])
def test_the_rule(text, start, end, want):
    assert mood(text, start, end) == want


def test_a_place_the_table_does_not_know_and_no_trip_wear_beach():
    assert mood("Lisbon", date(2026, 12, 30), date(2027, 1, 2)) == "beach"
    assert moods.choose(None) == "beach"


def test_the_preview_only_reads_a_known_mood_on_the_showcase(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert moods.preview("/plan/ask?mood=snow") == "snow"
    assert moods.preview("/plan/ask?mood=lava") == ""
    assert moods.preview("/plan/ask") == ""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert moods.preview("/plan/ask?mood=snow") == ""


@pytest.mark.parametrize("query, want", [
    ("to=Lake+Tahoe&d=2026-12-20&r=2026-12-24", "snow"),
    ("to=New+York&d=2026-12-29&r=2027-01-02", "celebration"),
    ("to=San+Diego&d=2026-12-12&r=2026-12-16", "beach"),
    ("to=Chicago&d=2026-12-12&r=2026-12-16", "city"),
])
def test_the_matrix_wears_the_mood_of_the_searched_place_and_dates(client, query, want):
    import re
    html = client.get(f"/plan/matrix?{query}").text
    assert re.search(r'data-mood="(\w+)" class="v2-bg"', html).group(1) == want


def test_the_landing_ask_wears_beach_and_a_preview_wins(client):
    assert 'data-mood="beach" class="v2-bg"' in client.get("/plan/ask").text
    assert 'data-mood="city" class="v2-bg"' in client.get("/plan/ask?mood=city").text
