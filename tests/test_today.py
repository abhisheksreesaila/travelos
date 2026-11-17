"""F-287: Today. The logic (gitaway/today.py) says what the day holds for a trip at a moment: before, a travel day, during, after; the page (/trip/today) draws it, and the planner
shows a card for it while the trip is near. Nothing is invented: a phone, a code, an airline's check-in page appears only where a source gave it, and the leave-by time says it is an estimate."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from gitaway import showcase, today as td
from tests.test_calendar import add, book
from tests.test_signin import sign_in
from tests.test_trip_import import TEMPLATE, imported, visible as _visible


def visible(html):
    return " ".join(_visible(html).split())


def trip(**over):
    out = dict(
        title="LA with the kids", place="Los Angeles", start=date(2026, 10, 16), end=date(2026, 10, 20),
        flights=(td.Flight("Delta", "DL 1234", "SFO", "LAX", datetime(2026, 10, 16, 8, 5), datetime(2026, 10, 16, 9, 32), "ABCDEF"),
                 td.Flight("Delta", "DL 1235", "LAX", "SFO", datetime(2026, 10, 20, 14, 10), datetime(2026, 10, 20, 15, 37), "ABCDEF")),
        stays=(td.Stay("The Example Hotel", datetime(2026, 10, 16, 15, 0), datetime(2026, 10, 20, 11, 0), "123 Ocean Ave, Santa Monica, CA 90401", confirmation="987654321", phone="+1 310 555 0100"),),
        plans=(td.Plan(date(2026, 10, 18), 14 * 60, 15 * 60, "Pier"), td.Plan(date(2026, 10, 18), 9 * 60, 10 * 60 + 30, "Venice Canals"), td.Plan(date(2026, 10, 19), 9 * 60, 10 * 60, "Not today")))
    return td.Trip(**{**out, **over})


def at(day, hour=7, minute=0):
    return datetime(2026, 10, day, hour, minute)          # a clock at the trip (its zone: Los Angeles unless the trip says)


def local(zone, day, hour=0, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo(zone))


PT, ET = "America/Los_Angeles", "America/New_York"


# ---- where the trip is ---------------------------------------------------------------------------------------------------------------

def test_the_state_is_before_travel_during_or_after():
    t = trip()
    assert [td.state(t, at(d)) for d in (10, 16, 17, 18, 19, 20, 21)] == ["before", "travel", "during", "during", "during", "travel", "after"]


def test_a_day_with_a_flight_or_a_check_in_is_a_travel_day_and_a_quiet_one_is_not():
    t = trip(flights=(), stays=(td.Stay("Inn", datetime(2026, 10, 17, 15, 0), datetime(2026, 10, 19, 11, 0)),))
    assert [td.state(t, at(d)) for d in (16, 17, 18, 19)] == ["during", "travel", "during", "travel"]


def test_the_card_is_near_three_days_before_and_until_the_trip_ends():
    t = trip()
    assert [td.near(t, at(d)) for d in (12, 13, 16, 20, 21)] == [False, True, True, True, False]


# ---- before ----------------------------------------------------------------------------------------------------------------------------

def test_before_counts_the_days_and_says_when_check_in_opens_with_the_airlines_own_page():
    today = td.build(trip(), at(10))
    assert (today.state, today.to_go) == ("before", 6)
    out = today.flights[0]
    assert out.flight.name == "Delta DL 1234" and out.opens == local(PT, 15, 8, 5)
    assert out.checkin_url == "https://www.delta.com/us/en/check-in/overview"


def test_an_airline_we_have_no_page_for_has_no_check_in_link():
    t = trip(flights=(td.Flight("Alaska Airlines", "AS 1234", "SFO", "LAX", datetime(2026, 10, 16, 8, 5), datetime(2026, 10, 16, 9, 32)),))
    assert td.build(t, at(10)).flights[0].checkin_url == ""


# ---- a travel day --------------------------------------------------------------------------------------------------------------------

def test_the_flight_comes_first_with_a_leave_by_time_from_the_drive_and_the_buffer():
    today = td.build(trip(home="San Francisco"), at(16), drives={"SFO": 45})
    assert today.state == "travel"
    first = today.items[0]
    assert isinstance(first, td.FlightItem) and first.flight.name == "Delta DL 1234"
    assert first.leave.at == local(PT, 16, 5, 20)          # 8:05 less 45 min of driving and 2 h at the airport
    assert first.leave.words() == "An estimate: 45 min by car from San Francisco, plus 2 h at the airport."


def test_no_drive_no_leave_by_and_an_international_flight_keeps_three_hours():
    assert td.build(trip(home="San Francisco"), at(16)).items[0].leave is None
    f = td.Flight("Air France", "AF 83", "SFO", "CDG", datetime(2026, 10, 16, 15, 0), datetime(2026, 10, 17, 10, 0))
    assert td.leave_by(f, 60, "San Francisco").at == datetime(2026, 10, 16, 11, 0)


def test_the_flight_home_leaves_from_the_hotels_address():
    today = td.build(trip(), at(20, 6), drives={"LAX": 30})
    flight = next(i for i in today.items if isinstance(i, td.FlightItem))
    assert flight.leave.at == local(PT, 20, 11, 40) and flight.leave.town == "123 Ocean Ave, Santa Monica, CA 90401"


def test_the_hotel_follows_with_its_address_check_in_time_and_code():
    today = td.build(trip(), at(16, 10))
    stay, flight = today.items
    assert isinstance(flight, td.FlightItem) and flight.past
    assert isinstance(stay, td.StayItem) and stay.phase == "checkin" and stay.at == local(PT, 16, 15, 0)
    assert (stay.stay.address, stay.stay.confirmation, stay.stay.phone) == ("123 Ocean Ave, Santa Monica, CA 90401", "987654321", "+1 310 555 0100")


def test_what_has_not_happened_yet_comes_first():
    today = td.build(trip(), at(16, 10))
    assert [type(i).__name__ for i in today.items] == ["StayItem", "FlightItem"] and [i.past for i in today.items] == [False, True]
    assert td.build(trip(), at(16, 7)).items[0].past is False
    late = td.build(trip(), at(16, 16))
    assert all(i.past for i in late.items)


def test_a_checkout_day_with_a_flight_puts_the_checkout_before_the_flight():
    today = td.build(trip(), at(20, 7))
    assert [(type(i).__name__, getattr(i, "phase", "")) for i in today.items] == [("StayItem", "checkout"), ("FlightItem", "")]


# ---- time zones: each flight is in its own airports' clocks -------------------------------------------------------------------

def flight_of(today):
    return next(i for i in today.items if isinstance(i, td.FlightItem))


def coast_trip(**over):
    """San Francisco to New York: the trip (and the hotel) is on Eastern time, the flight out leaves on Pacific time and the one home leaves on Eastern."""
    out = dict(zone=ET, place="New York", home="San Francisco",
               flights=(td.Flight("Delta", "DL 400", "SFO", "JFK", datetime(2026, 10, 16, 8, 5), datetime(2026, 10, 16, 16, 35), "ABCDEF"),
                        td.Flight("Delta", "DL 401", "JFK", "SFO", datetime(2026, 10, 20, 14, 10), datetime(2026, 10, 20, 17, 40), "ABCDEF")),
               stays=(td.Stay("The Hudson", datetime(2026, 10, 16, 17, 0), datetime(2026, 10, 20, 11, 0), "1 Pier Way, New York, NY"),))
    return trip(**{**out, **over})


def test_a_flight_leaving_home_is_judged_by_the_home_clock_not_the_trips():
    t = coast_trip()
    late_morning_et = datetime(2026, 10, 16, 10, 30)      # 7:30 AM in San Francisco: the 8:05 AM flight has not left
    out = flight_of(td.build(t, late_morning_et))
    assert (out.flight.name, out.past) == ("Delta DL 400", False)
    assert flight_of(td.build(t, datetime(2026, 10, 16, 11, 30))).past is True       # 8:30 AM in San Francisco: it has


def test_each_time_is_in_its_own_airports_zone_and_the_flight_lasts_what_it_lasts():
    f = flight_of(td.build(coast_trip(), datetime(2026, 10, 16, 6, 0))).flight
    assert (f.depart.tzname(), f.arrive.tzname()) == ("PDT", "EDT") and (f.depart.hour, f.arrive.hour) == (8, 16)
    assert f.arrive - f.depart == timedelta(hours=5, minutes=30)


def test_the_flight_home_leaves_on_the_hotels_clock_and_leave_by_follows_it():
    today = td.build(coast_trip(), datetime(2026, 10, 20, 12, 0), drives={"JFK": 50})
    flight = next(i for i in today.items if isinstance(i, td.FlightItem))
    assert flight.past is False and flight.leave.at == local(ET, 20, 11, 20) and flight.flight.arrive.tzname() == "PDT"


def test_a_red_eye_crossing_midnight_is_still_the_travel_day_it_left_on():
    eye = td.Flight("Delta", "DL 480", "SFO", "JFK", datetime(2026, 10, 16, 23, 30), datetime(2026, 10, 17, 8, 0), "ABCDEF")
    t = coast_trip(flights=(eye,))
    now = datetime(2026, 10, 17, 0, 15)            # past midnight in New York, 9:15 PM on the 16th in San Francisco
    today = td.build(t, now)
    assert today.state == "travel" and flight_of(today).flight.name == "Delta DL 480" and flight_of(today).past is False
    assert flight_of(today).flight.arrive - flight_of(today).flight.depart == timedelta(hours=5, minutes=30)
    assert (flight_of(td.build(t, datetime(2026, 10, 17, 3, 0))).past, flight_of(td.build(t, datetime(2026, 10, 17, 3, 0))).airborne) == (True, True)      # 11:30 PM in San Francisco is gone by 3 AM in New York


def test_an_airport_or_airline_we_do_not_know_falls_back_safely():
    nowhere = td.Flight("Tiny Air", "TA 1", "XYZ", "QQQ", datetime(2026, 10, 16, 8, 5), datetime(2026, 10, 16, 9, 30))
    assert td.buffer_for(nowhere) == 180 and td.checkin_url(nowhere) == ""      # not provably domestic: the longer buffer; no airline page: no link
    t = trip(flights=(nowhere,), home="Springfield")
    item = flight_of(td.build(t, at(16, 6), drives={"XYZ": 30}))
    assert item.flight.depart.tzname() == "PDT" and item.leave.at == local(PT, 16, 4, 35) and item.checkin_url == ""      # the trip's own clock stands in for an airport we do not know


# ---- during, after, and the booking as facts ---------------------------------------------------------------------------------------

def test_during_lists_only_todays_plans_in_time_order_with_the_hotel_and_its_check_out():
    today = td.build(trip(), at(18))
    assert today.state == "during" and today.day == 2
    assert [(p.title, p.start) for p in today.plans] == [("Venice Canals", 540), ("Pier", 840)]
    assert today.stay.name == "The Example Hotel" and today.stay.check_out == local(PT, 20, 11, 0)


def test_after_has_nothing_but_the_end_of_the_trip():
    today = td.build(trip(), at(22))
    assert (today.state, today.items, today.plans) == ("after", (), ())


def test_a_pasted_booking_is_read_as_written_confirmation_codes_included(client):
    imported(client)
    from tests.test_signin import person
    from gitaway import session as ses
    t = td.from_booking(person(), ses.booking(person()))
    assert [f.name for f in t.flights] == ["Alaska Airlines AS 1234", "Alaska Airlines AS 1235"] and t.flights[0].confirmation == "ABCDEF"
    assert t.stays[0].name == "The Example Hotel Santa Monica" and t.stays[0].confirmation == "987654321" and t.stays[0].phone == "+1 310 555 0100"
    assert t.sample is False and t.home == ""


def test_the_sample_booking_is_labelled_sample_and_has_no_code_or_phone_to_show(client):
    book(client)
    from tests.test_signin import person
    from gitaway import session as ses
    t = td.from_booking(person(), ses.booking(person()))
    assert t.sample and t.home == "San Francisco"
    out = t.flights[0]
    assert (out.name, out.origin, out.dest, out.depart.time().isoformat("minutes")) == ("Skylark Air 214", "SFO", "LAX", "08:05")
    assert (t.stays[0].name, t.stays[0].area, t.stays[0].confirmation, t.stays[0].phone, t.stays[0].address) == ("The Tidewater", "Santa Monica", "", "", "")


def test_a_stay_that_was_cancelled_never_reaches_the_day(client):
    from tests.test_signin import person
    from gitaway import matrixbook, session as ses
    imported(client)
    assert [h.name for h in td.from_booking(person(), ses.booking(person())).stays] == ["The Example Hotel Santa Monica"]
    with ses.family(person()) as fam:
        trip_id = fam.trip_id
    matrixbook.mark_cancelled(person(), trip_id, "987654321")
    assert td.from_booking(person(), ses.booking(person())).stays == ()
    html = client.get("/trip/today?day=2026-10-16").text
    assert "987654321" not in html and "The Example Hotel" not in visible(html)


# ---- the page ------------------------------------------------------------------------------------------------------------------------

def test_signed_out_signs_in_and_without_a_booking_starts_one(client):
    r = client.get("/trip/today", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Ftrip%2Ftoday"
    sign_in(client)
    assert client.get("/trip/today", follow_redirects=False).headers["location"] == showcase.planning_path()


def test_before_the_trip_the_page_counts_down_and_says_this_is_a_sample(client):
    book(client)
    html = client.get("/trip/today").text
    text = visible(html)
    assert "16 days to go" in text and "Sample trip" in text
    assert "Flight check-in opens Thu Oct 15, 8:05 AM PDT" in text and "Skylark Air 214" in text


def test_the_day_query_previews_another_date_on_the_showcase_only(client, monkeypatch):
    book(client)
    text = visible(client.get("/trip/today?day=2026-10-16").text)
    assert "Leave by" not in text          # no drive answer from the router (refused in tests): no time is guessed
    assert "Check in 3:00 PM" in text and "The Tidewater" in text and "Preview of Fri, Oct 16" in text
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert "Preview of" not in visible(client.get("/trip/today?day=2026-10-16").text)


def test_a_travel_day_shows_the_hotel_directions_a_ride_and_who_to_call(client):
    imported(client)
    text_html = client.get("/trip/today?day=2026-10-16")
    html = text_html.text
    text = visible(html)
    assert "The Example Hotel Santa Monica" in text and "123 Ocean Ave, Santa Monica, CA 90401" in text
    assert "987654321" in text and "Check in 3:00 PM" in text and "Alaska Airlines AS 1234" in text and "Fri Oct 16, 8:05 AM PDT" in text and "Fri Oct 16, 9:32 AM PDT" in text
    assert 'href="https://www.google.com/maps/search/?api=1&amp;query=The+Example+Hotel+Santa+Monica%2C+123+Ocean+Ave%2C+Santa+Monica%2C+CA+90401"' in html
    assert 'href="https://m.uber.com/ul/' in html
    assert 'href="tel:+13105550100"' in html
    assert 'td-checkin' not in html          # a travel day has no check-in card, and Alaska has no page of ours anyway


def test_the_leave_by_time_is_the_drive_and_a_stated_buffer_labelled_an_estimate(client, monkeypatch):
    from gitaway import airportdrive
    asked = []
    monkeypatch.setattr(airportdrive, "drive", lambda iata, town: asked.append((iata, town)) or airportdrive.Drive(iata, town, 45))
    book(client)
    text = visible(client.get("/trip/today?day=2026-10-16").text)
    assert asked == [("SFO", "San Francisco")]
    assert "Leave by about 5:20 AM" in text and "An estimate: 45 min by car from San Francisco, plus 2 h at the airport." in text


def test_use_my_location_is_offered_only_where_the_map_has_the_hotels_coordinates(client):
    from gitaway import geo, familydb
    from tests.test_signin import person
    imported(client)
    assert 'id="td-locate"' not in client.get("/trip/today?day=2026-10-16").text
    with familydb.using(person()) as db:
        geo._put(db, "place", geo._norm("The Example Hotel Santa Monica, 123 Ocean Ave, Santa Monica, CA 90401"), lat=34.0141, lon=-118.4934)
    html = client.get("/trip/today?day=2026-10-16").text
    assert 'id="td-locate"' in html and 'data-lat="34.014100"' in html and 'data-lon="-118.493400"' in html
    assert "Your position is used on this page" in visible(html)


def test_a_stay_with_no_phone_says_so_and_points_to_who_to_call_with_the_code(client):
    imported(client, text=re.sub(r'\n  phone: "[^"]*"[^\n]*', "", TEMPLATE))
    html = client.get("/trip/today?day=2026-10-16").text
    text = visible(html)
    assert "No phone number from the hotel yet" in text and "tel:" not in html and "987654321" in text
    assert 'href="/trip/booking?sos=1"' in html


def test_during_the_trip_the_page_lists_the_days_plans_and_the_check_out(client):
    imported(client)
    add(client, id="a1", day="1", start="09:00", title="Venice Canals stroll", kind="outdoors")
    text = visible(client.get("/trip/today?day=2026-10-17").text)
    assert "Venice Canals stroll" in text and "Check out Tue Oct 20, 11:00 AM" in text and "Day 2 of 5" in text


def test_after_the_trip_it_asks_how_it_was_and_shares_to_instagram(client):
    imported(client)
    html = client.get("/trip/today?day=2026-10-22").text
    assert "How was it?" in visible(html) and "Share to Instagram" in html


def test_the_planner_has_a_today_card_only_while_the_trip_is_near(client, monkeypatch):
    book(client)
    assert 'id="td-card"' not in client.get("/trip/plan").text
    html = client.get("/trip/plan?day=2026-10-14").text
    assert 'id="td-card"' in html and 'href="/trip/today?day=2026-10-14"' in html
    assert 'id="td-card"' not in client.get("/trip/plan?day=2026-10-30").text


def test_the_page_is_a_page_of_the_app_with_the_location_button_and_no_coordinates_sent(client):
    book(client)
    html = client.get("/trip/today?day=2026-10-16").text
    assert "/assets/css/today.css" in html and "/assets/js/today.js" in html
    assert 'id="td-locate"' not in html          # the sample's stay has no coordinates: no button to measure to nothing


def test_the_page_is_never_kept_by_the_browser_after_sign_out(client):
    book(client)
    assert client.get("/trip/today").headers["cache-control"] == "private, no-store"


def test_the_page_carries_when_it_was_drawn_for_the_saved_copy_notice(client):
    book(client)
    html = client.get("/trip/today").text
    m = re.search(r'<div[^>]*id="td-saved"[^>]*>', html)
    assert m and 'hidden' in m.group(0) and 'data-saved="0"' in m.group(0)
    assert re.search(r'data-at="20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d', m.group(0))


def test_a_signed_in_page_says_when_the_session_runs_out_and_a_signed_out_one_says_nothing(client):
    import time
    assert 'name="ga-until"' not in client.get("/offline").text
    book(client)
    until = int(re.search(r'<meta name="ga-until" content="(\d+)">', client.get("/trip/today").text).group(1))
    assert 29 * 86400 < until - time.time() <= 30 * 86400 + 5


# ---- F-293 (D-948): the stay card's secondary actions are on demand, in its More menu -----------------------------------------------

def stay_card(html):
    """The hotel card's html, and its More menu's html."""
    card = html[html.index('<section id="td-stay"'):]
    card = card[:card.index("</section>")]
    start = card.rfind("<div", 0, card.index('id="td-more"'))
    menu = card[start:card.index("</div>", card.index('id="td-more-menu"')) + 6]
    return card.replace(menu, ""), menu


def test_the_hotel_card_leads_with_directions_and_keeps_the_ride_the_location_and_the_wallet_in_more(client, monkeypatch):
    from gitaway import geo, familydb, walletpass
    from tests.test_signin import person
    imported(client)
    with familydb.using(person()) as db:
        geo._put(db, "place", geo._norm("The Example Hotel Santa Monica, 123 Ocean Ave, Santa Monica, CA 90401"), lat=34.0141, lon=-118.4934)
    monkeypatch.setenv("APPLE_PASS_TYPE_ID", "pass.example")
    monkeypatch.setattr(walletpass, "apple_configured", lambda: True)
    monkeypatch.setattr(walletpass, "offered", lambda ref: True)
    html = client.get("/trip/today?day=2026-10-16").text
    rest, menu = stay_card(html)
    assert [x.strip() for x in re.findall(r'role="menuitem"[^>]*>(?:<svg.*?</svg>)?(?:<span>)?([^<]+)', menu, re.S) if x.strip()] == ["Get a ride", "Use my location", "Add to Apple Wallet"]
    for ident in ("td-ride", "td-locate", "wp-apple"):
        assert f'id="{ident}"' in menu and f'id="{ident}"' not in rest, ident
    assert 'id="td-directions"' in rest and "Directions" in visible(rest)          # the one bold action stays on the card
    assert 'id="td-near"' in rest                                                   # where the measured distance is read
    assert "Your position is used on this page" in visible(menu)                    # the privacy note stays with its row


def test_a_hotel_card_with_nothing_to_hold_still_has_the_ride_in_more(client):
    imported(client)
    html = client.get("/trip/today?day=2026-10-16").text
    rest, menu = stay_card(html)
    assert 'id="td-ride"' in menu and 'id="td-locate"' not in html and 'id="td-ride"' not in rest
