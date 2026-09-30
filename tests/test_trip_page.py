"""The scrapbook itinerary page at /trips/{slug}."""
import html as htmllib
from dataclasses import replace

from fasthtml.common import to_xml

from gitaway import itineraries
from gitaway.itinerary_view import itinerary_body

SLUG = "sun-tacos-and-tide-pools"


def render(trip):
    return to_xml(itinerary_body(trip))


def render_theme(trip):
    from gitaway.itinerary_view import itinerary_page
    return to_xml(itinerary_page(trip))


def test_known_trip_renders_hero_board_and_every_day(client):
    r = client.get(f"/trips/{SLUG}")
    assert r.status_code == 200
    h = r.text
    assert "TravelOS" not in h
    assert "Sun, tacos &amp; tide pools" in h and "little ones" in h
    assert "Maya &amp; Theo Adventures" in h and "Watch the original" in h
    for label in ["5 days", "4 people", "$3,480", "312"]:
        assert label in h
    assert "The whole trip on one board" in h
    for n in range(1, 6):
        assert f'id="day-{n}"' in h and f'href="#day-{n}"' in h
    for title in ["Touch down &amp; tacos", "Griffith Observatory at sunset", "Farmers Market brunch"]:
        assert title in h
    booked = [s.title for d in itineraries.get(SLUG).days for s in d.stops if s.booked]
    assert len(booked) == 4 and "Skylark Air 219" in booked[-1]
    assert h.count(">BOOKED<") == 4
    assert "/assets/css/itinerary.css" in h and "/assets/css/base.css" in h
    assert "74°F" in h


def test_unknown_trip_keeps_the_friendly_404(client):
    r = client.get("/trips/no-such-trip")
    assert r.status_code == 404 and "This trip wandered off" in r.text


def test_itinerary_css_is_only_loaded_by_this_page(client):
    assert "itinerary.css" not in client.get("/").text
    assert client.get("/assets/css/itinerary.css").status_code == 200


def test_trip_record_chooses_the_theme_and_query_overrides_it(client):
    assert 'data-theme="sunset"' in client.get(f"/trips/{SLUG}").text
    assert 'data-theme="pacific"' in client.get(f"/trips/{SLUG}?theme=pacific").text
    assert 'data-theme="sunset"' in client.get(f"/trips/{SLUG}?theme=bogus").text
    assert 'data-theme="pacific"' in render_theme(replace(itineraries.get(SLUG), theme="pacific"))


def test_fork_button_links_to_signin_with_intent(client):
    h = htmllib.unescape(client.get(f"/trips/{SLUG}").text)
    assert f'href="/signin?next=/trips/{SLUG}&intent=fork"' in h


def test_days_four_and_five_are_collapsed_open_day_cards(client):
    h = client.get(f"/trips/{SLUG}").text
    assert h.count("<details") >= 2 and h.count("Open day") == 2
    assert 'id="day-4"' in h and "Dinosaur hall" in h


def test_loading_state_shows_skeleton_blocks_instead_of_content(client):
    h = client.get(f"/trips/{SLUG}?state=loading").text
    assert "skeleton" in h and "aria-busy" in h
    assert "Griffith Observatory" not in h


def test_free_day_says_nothing_is_planned():
    trip = itineraries.get(SLUG)
    days = list(trip.days)
    days[1] = replace(days[1], stops=[])
    h = render(replace(trip, days=days))
    assert "Free day, nothing planned" in h


def test_more_than_six_stops_collapse_and_board_shows_plus_more():
    trip = itineraries.get(SLUG)
    stops = [itineraries.Stop(time=f"{i}:00 PM", title=f"Long stop {i}") for i in range(1, 9)]
    days = [replace(trip.days[0], stops=stops)] + list(trip.days[1:])
    h = render(replace(trip, days=days))
    assert "Show all 8 stops" in h
    assert "+4 more" in h


def test_trip_without_creator_or_photos_falls_back_to_stickers():
    trip = itineraries.get(SLUG)
    bare = replace(trip, source=None, polaroids=[],
                   days=[replace(d, stops=[replace(s, photo="") for s in d.stops]) for d in trip.days])
    h = render(bare)
    assert "From the vlog" not in h and "Watch the original" not in h
    assert "/assets/photos/" not in h
    assert "collage-stickers" in h
    assert "Fork this trip" in h


def test_one_day_trip_hides_the_board():
    trip = itineraries.get(SLUG)
    h = render(replace(trip, days=[replace(trip.days[0])]))
    assert "The whole trip on one board" not in h
    assert 'id="day-1"' in h


def test_user_text_is_escaped():
    trip = itineraries.get(SLUG)
    evil = "<script>alert(1)</script>"
    stops = [replace(trip.days[0].stops[0], note=evil)] + list(trip.days[0].stops[1:])
    h = render(replace(trip, title=evil, days=[replace(trip.days[0], stops=stops)] + list(trip.days[1:])))
    assert evil not in h and "&lt;script&gt;alert(1)&lt;/script&gt;" in h


def test_couple_friendly_tag_and_unknown_icons_do_not_break_the_page():
    trip = itineraries.get(SLUG)
    tags = [itineraries.Tag("Couple friendly", "bubble", "couple"), itineraries.Tag("Mystery", "sun", "no-such-icon")]
    h = render(replace(trip, tags=tags))
    assert "Couple friendly" in h and "Mystery" in h
    stops = [replace(trip.days[0].stops[0], kind="no-such-icon")] + list(trip.days[0].stops[1:])
    render(replace(trip, days=[replace(trip.days[0], stops=stops)] + list(trip.days[1:])))
