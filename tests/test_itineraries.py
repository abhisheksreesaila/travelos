"""The fake itinerary data behind the scrapbook page."""
from gitaway import itineraries


def test_the_sample_trip_is_found_by_slug():
    trip = itineraries.get("sun-tacos-and-tide-pools")
    assert trip is not None
    assert trip.title == "Sun, tacos & tide pools"
    assert trip.theme == "sunset"
    assert itineraries.get("nope") is None


def test_the_sample_trip_has_five_days_with_the_artboard_stops():
    trip = itineraries.get("sun-tacos-and-tide-pools")
    assert [d.title for d in trip.days] == [
        "Touch down & tacos", "Canals & boardwalk", "Steam trains & stars",
        "Dinos & tar pits", "Market brunch, fly home",
    ]
    assert [len(d.stops) for d in trip.days] == [4, 3, 3, 3, 3]
    first = trip.days[0].stops
    assert first[0].booked and first[0].title == "Skylark Air 214 · SFO → LAX"
    assert first[2].tag == "Kid friendly" and first[2].note
    assert [d.collapsed for d in trip.days] == [False, False, False, True, True]
    assert all("°F" in d.weather for d in trip.days)


def test_the_source_card_credits_the_fictional_creator():
    src = itineraries.get("sun-tacos-and-tide-pools").source
    assert "Maya & Theo Adventures" in src.byline


def test_board_shows_at_most_four_cards_then_a_count():
    stops = [itineraries.Stop(time="9:00 AM", title=f"Stop {i}") for i in range(7)]
    shown, extra = itineraries.board_cards(itineraries.Day(n=1, date="X", title="T", stops=stops))
    assert len(shown) == 4 and extra == 3
    shown, extra = itineraries.board_cards(itineraries.Day(n=1, date="X", title="T", stops=stops[:4]))
    assert len(shown) == 4 and extra == 0


def test_days_cycle_through_the_five_day_colours():
    assert [itineraries.day_color(n) for n in range(1, 7)] == ["sun", "mint", "grape", "sky", "bubble", "sun"]
