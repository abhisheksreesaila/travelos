"""F-090: one day at a time, plans first. The day view has the trip's dates across the top and knows its neighbours (for the flick), bookings are quiet lines
behind the family's plans, every day has "Change this day" (an empty one: say or paste the plan), and the morning push and Today lead to it.
The trip is the demo booking (Fri 16 fly in and check in, Sat 17 Universal, Sun 18 free, Mon 19 California Adventure, Tue 20 fly home) with the captain's
park messages added through the canned model answer (no network)."""

import re

from gitaway import morning
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_trip_canvas import bare, tag, text, trip  # noqa: F401 - fixtures



def day(client, n):
    r = client.get(f"/trip/canvas?day={n}")
    assert r.status_code == 200
    return bare(r.text)


def pills(page):
    return re.findall(r'<a\b[^>]*class="cz-dp(?! cz-dp-week)[ "][^>]*>', page)


# ---- the dates across the top and the neighbours --------------------------------------------------------------------------

def test_the_day_has_every_date_across_the_top_with_the_open_one_marked(trip):
    page = day(trip, 1)
    days = pills(page)
    assert len(days) == 5
    for i, a in enumerate(days):
        assert f'href="/trip/canvas?day={i}"' in a and 'data-zoom="side"' in a
        assert ('aria-current="date"' in a) == (i == 1) and ("is-open" in a) == (i == 1)
    assert "SAT" in text(page) and "17" in text(page)


def test_the_week_is_one_tap_out_from_the_dates(trip):
    page = day(trip, 2)
    week = tag(page, "cz-z-week")
    assert 'href="/trip/canvas"' in week and 'data-zoom="out"' in week


def test_a_date_with_plans_is_marked_and_one_with_only_bookings_is_not(trip):
    days = pills(day(trip, 0))
    assert "has-plans" in days[1] and "has-plans" in days[3]       # Universal, California Adventure
    assert "has-plans" not in days[0] and "has-plans" not in days[2]  # only the flight and check in; a free day


def test_the_day_knows_its_neighbours_for_the_flick(trip):
    first, mid, last = day(trip, 0), day(trip, 2), day(trip, 4)
    view = lambda p: re.search(r'<section\b[^>]*data-level="day"[^>]*>', p).group(0)  # noqa: E731
    assert 'data-next="/trip/canvas?day=1"' in view(first) and "data-prev" not in view(first)
    assert 'data-prev="/trip/canvas?day=1"' in view(mid) and 'data-next="/trip/canvas?day=3"' in view(mid)
    assert 'data-prev="/trip/canvas?day=3"' in view(last) and "data-next" not in view(last)


def test_every_date_link_lands_on_its_day(trip):
    for i in range(5):
        r = trip.get(f"/trip/canvas?day={i}&frag=1")
        assert r.status_code == 200 and f'data-day="{i}"' in r.text


# ---- plans first, bookings in the background ---------------------------------------------------------------------------------

def test_bookings_are_quiet_lines_in_time_order_with_a_tap_to_their_details(trip):
    page = day(trip, 0)
    lines = re.findall(r'<a\b[^>]*class="cz-bk[ "][^>]*>.*?</a>', page, re.S)
    assert len(lines) == 2
    flight, hotel = lines
    assert "8:05 AM" in text(flight) and "SFO" in text(flight) and 'href="/trip/canvas?day=0&amp;booked=b-out"' in flight     # F-093: the sheet opens in place, not Help
    assert "3:00 PM" in text(hotel) and "Check in" in text(hotel) and 'href="/trip/canvas?day=0&amp;booked=b-in"' in hotel
    assert "cz-plain is-booked" not in page        # no booking is a bright card any more


def test_a_day_with_only_bookings_says_nothing_is_planned_and_still_shows_them(trip):
    page = day(trip, 0)
    assert "Nothing planned yet" in text(page) and page.index('id="cz-empty"') < page.index('class="cz-bk')


def test_a_park_day_shows_its_plan_as_the_card_and_no_booking_line(trip):
    page = day(trip, 1)
    assert "Universal Studios Hollywood" in text(page) and 'class="cz-block"' in page and 'class="cz-bk' not in page and 'id="cz-empty"' not in page


# ---- change this day -----------------------------------------------------------------------------------------------------------

def test_an_empty_day_offers_talk_and_paste_to_an_editor(trip):
    park = day(trip, 1)
    assert 'id="cz-say"' not in park     # F-092: the centre Ask changes the day (the script points it at the day shown)
    assert 'id="cz-say-talk"' not in park
    free = day(trip, 2)
    assert 'href="/trip/ask?day=2&amp;mode=talk"' in tag(free, "cz-say-talk") and 'href="/trip/ask?day=2&amp;mode=paste"' in tag(free, "cz-say-paste")
    assert "Say the plan for this day" in text(free) and 'id="cz-say"' not in free


def test_a_viewer_sees_the_day_but_no_way_to_change_it(azure, crew):
    ari, viewer = crew
    added(ari)
    page = bare(viewer.get("/trip/canvas?day=2").text)
    assert len(pills(page)) == 5 and "Nothing planned yet" in text(page)
    assert 'id="cz-say' not in page


# ---- the morning and Today lead to it ----------------------------------------------------------------------------------------

def test_the_morning_push_is_todays_plan_and_opens_the_day():
    m = morning.message("Los Angeles", "during", [(9 * 60, "Universal Studios Hollywood")], day=3)
    assert m["title"] == "Today's plan · Los Angeles" and m["url"] == "/trip/canvas?day=3"
    assert morning.message("Los Angeles", "during", [], day=0)["body"].startswith("Nothing planned yet")


def test_today_has_a_day_plan_button(trip):
    page = bare(trip.get("/trip?tab=today").text)
    assert 'href="/trip/canvas?day=0"' in tag(page, "tp-open-day") and re.search(r'id="tp-open-day"[^>]*>.*?Day plan</a>', page, re.S)


def test_during_the_trip_today_is_ringed_and_named(trip, monkeypatch):
    from datetime import datetime, timezone
    from gitaway import catalog
    now = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)      # Monday 8:00 AM in Los Angeles: day 4 of 5
    monkeypatch.setattr(catalog, "now_utc", lambda: now)
    monkeypatch.setattr(catalog, "today", lambda: now.astimezone(catalog.TZ).date())
    days = pills(day(trip, 1))
    assert ["is-today" in a for a in days] == [False, False, False, True, False] and ", today" in days[3]
    assert 'href="/trip/canvas?day=3"' in tag(bare(trip.get("/trip?tab=today").text), "tp-open-day")


def test_signed_out_day_goes_to_sign_in(client):
    assert client.get("/trip/canvas?day=1", follow_redirects=False).headers["location"].startswith("/signin")
