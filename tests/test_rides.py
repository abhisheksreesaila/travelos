"""F-038: schedule an Uber through the app: the rides card, the flow, the status timeline, the calendar, /booked, storage."""
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import catalog, rides, session as ses
from tests.test_signin import session_data, sign_in

PICK = "f=f1&h=h1&c=none"
LEG = "leg=arrive&" + PICK
GUEST = {"first": "Ari", "last": "Rivera", "phone": "(310) 555-0123"}
SIM = "Simulated: no real ride is booked"
PHONE_DIGITS = "3105550123"


def new_page(client, leg="arrive", pick=PICK, p=""):
    return client.get(f"/rides/new?leg={leg}&{pick}" + (f"&p={p}" if p else ""))


def schedule(client, leg="arrive", pick=PICK, p="x", **guest):
    """Walk the real flow: choose a ride, read its fare id from the confirm form, post the guest."""
    html = new_page(client, leg, pick, p).text
    fare = re.search(r'name="fare" value="([^"]+)"', html).group(1)
    form = {k: v[0] for k, v in parse_qs(pick).items()} | {"leg": leg, "p": p, "fare": fare} | {**GUEST, **guest}
    return client.post("/rides", data=form, follow_redirects=False)


def book(client, pick="f=f1&h=h1&c=none"):
    return client.post("/pay", data={k: v[0] for k, v in parse_qs(pick).items()}, follow_redirects=False)


def visible(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


# ---- the rides card ----------------------------------------------------------------------------------------------

def test_with_no_car_the_rides_card_offers_schedule_an_uber_for_arrival_and_departure(client):
    html = client.get(f"/plan?{PICK}").text
    card = html[html.index('id="ws-rides-card"'):]
    assert card.count("Schedule an Uber") >= 2
    assert 'href="/rides/new?leg=arrive&amp;f=f1&amp;h=h1&amp;c=none"' in card
    assert 'href="/rides/new?leg=depart&amp;f=f1&amp;h=h1&amp;c=none"' in card


def test_the_links_carry_the_trip(client):
    html = client.get(f"/plan?{PICK}&d=2026-10-20&r=2026-10-24&a=2").text
    assert "d=2026-10-20&amp;r=2026-10-24&amp;a=2" in html[html.index('id="ws-rides-card"'):]


def test_the_ledger_json_carries_the_same_links(client):
    card = client.get(f"/plan/quote?{PICK}").json()["ledger"]["rides_html"]
    assert "/rides/new?leg=arrive" in card and "Schedule an Uber" in card


def test_with_a_car_there_is_no_rides_card_and_no_ride_to_schedule(client):
    assert "Schedule an Uber" not in client.get("/plan?f=f1&h=h1&c=c1").text
    sign_in(client)
    html = new_page(client, pick="f=f1&h=h1&c=c1").text
    assert "rental car" in html and "data-product" not in html


def test_driving_there_has_no_airport_to_ride_from(client):
    sign_in(client)
    assert "no airport" in visible(new_page(client, pick="f=none&h=h1&c=none").text)


# ---- the flow ----------------------------------------------------------------------------------------------------

def test_signed_out_goes_to_sign_in_with_the_ride_intent_and_comes_back(client):
    r = client.get(f"/rides/new?{LEG}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Frides%2Fnew%3Fleg%3Darrive") and r.headers["location"].endswith("&intent=ride")
    assert "schedule an Uber" in client.get(r.headers["location"]).text
    assert client.get("/rides/r1", follow_redirects=False).status_code == 303


def test_a_bad_leg_is_a_friendly_refusal_not_a_crash(client):
    sign_in(client)
    r = client.post("/rides", data={**GUEST, "leg": "sideways", "f": "f1", "h": "h1", "c": "none", "p": "x", "fare": "x"})
    assert r.status_code == 422 and "arrival or the departure" in visible(r.text)
    assert not rides.list_rides(_Session(client))


def test_step_one_lists_the_products_with_price_and_time_and_is_labelled_simulated(client):
    sign_in(client)
    html = new_page(client).text
    for key, name in (("x", "UberX"), ("c", "Comfort"), ("xl", "UberXL")):
        card = re.search(rf'<li[^>]*data-product="{key}".*?</li>', html, re.S).group(0)
        assert name in card and "min trip" in card and "$" in card
    assert SIM in visible(html)
    assert "Pickup Fri Oct 16 · 10:02 AM" in visible(html)
    assert "Uber Reserve" in visible(html)  # the airport pickup is a Reserve-style booking


def test_the_departure_pickup_leaves_in_time_for_the_flight(client):
    sign_in(client)
    text = visible(new_page(client, "depart").text)
    assert "Pickup Tue Oct 20 · 11:45 AM" in text and "2:10 PM" in text


def test_five_travelers_can_only_pick_the_xl(client):
    sign_in(client)
    html = new_page(client, pick=f"{PICK}&d=2026-10-16&r=2026-10-20&a=3&k=5,6").text
    assert 'data-choose="xl"' in html and 'data-choose="x"' not in html and 'data-choose="c"' not in html
    assert "needs an XL" in html


def test_the_uber_app_link_is_a_separate_option_that_prefills_the_trip(client):
    sign_in(client)
    html = new_page(client).text
    href = unescape(re.search(r'id="rd-app"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*id="rd-app"', html).group(1) or "")
    href = href or unescape(re.search(r'href="(https://m\.uber\.com[^"]+)"', html).group(1))
    assert href.startswith("https://m.uber.com/looking?") and "product_id" not in href and "pickup=" in href
    assert PHONE_DIGITS not in href and "Open in Uber app" in html


def test_step_two_confirms_pickup_and_dropoff_and_asks_who_is_riding(client):
    sign_in(client)
    text = visible(new_page(client, p="x").text)
    assert "Los Angeles International Airport (LAX)" in text and "The Tidewater" in text
    assert "Confirm pickup and dropoff" in text and "Who's riding?" in text and SIM in text
    html = new_page(client, p="x").text
    assert 'name="first"' in html and 'name="phone"' in html and 'name="fare"' in html


def test_scheduling_creates_the_ride_and_shows_it_scheduled(client):
    sign_in(client)
    r = schedule(client)
    assert r.status_code == 303 and r.headers["location"] == "/rides/r1"
    html = client.get("/rides/r1").text
    assert re.search(r'data-status="scheduled"', html)
    text = visible(html)
    assert SIM in text and "UberX" in text and "Ari Rivera" in text and "sim_" in text
    assert "(310) 555-0123" in text
    assert 'id="rd-step"' in html and 'id="rd-cancel"' in html


def test_the_timeline_steps_through_the_documented_statuses_then_completes(client):
    sign_in(client)
    schedule(client)
    seen = []
    for _ in range(4):
        assert client.post("/rides/r1/step", follow_redirects=False).headers["location"] == "/rides/r1"
        html = client.get("/rides/r1").text
        seen.append(re.search(r'data-status="(\w+)"', html).group(1))
    assert seen == ["accepted", "arriving", "in_progress", "completed"]
    assert 'id="rd-step"' not in html and 'id="rd-cancel"' not in html
    assert "Marisol" in html or "plate" in html  # the driver and the car
    assert client.post("/rides/r1/step").status_code == 409


def test_the_timeline_lists_the_five_friendly_steps(client):
    sign_in(client)
    schedule(client)
    html = client.get("/rides/r1").text
    labels = re.findall(r'data-tl="(\w+)"', html)
    assert labels == ["scheduled", "accepted", "arriving", "in_progress", "completed"]
    for words in ("Scheduled", "Driver assigned", "Arriving", "On trip", "Completed"):
        assert words in visible(html)


def test_cancel_marks_the_ride_cancelled_and_nothing_can_follow(client):
    sign_in(client)
    schedule(client)
    assert client.post("/rides/r1/cancel", follow_redirects=False).status_code == 303
    html = client.get("/rides/r1").text
    assert re.search(r'data-status="rider_canceled"', html) and "Cancelled" in html and 'id="rd-step"' not in html
    assert "Nothing was charged" not in html
    assert client.post("/rides/r1/cancel").status_code == 409


def test_a_ride_cannot_be_cancelled_once_the_driver_is_arriving(client):
    sign_in(client)
    schedule(client)
    for _ in range(2):  # accepted, then arriving
        client.post("/rides/r1/step")
    html = client.get("/rides/r1").text
    assert 'id="rd-cancel"' not in html
    r = client.post("/rides/r1/cancel")
    assert r.status_code == 409 and "can't be cancelled" in visible(r.text)


def test_a_second_ride_for_the_same_leg_is_not_allowed_until_the_first_is_cancelled(client):
    sign_in(client)
    schedule(client)
    assert new_page(client).status_code == 200 and new_page(client).url.path == "/rides/r1"  # the flow lands on the live ride
    client.post("/rides/r1/cancel")
    r = schedule(client, p="c")
    assert r.status_code == 303 and r.headers["location"] == "/rides/r2"
    assert [x.id for x in rides.list_rides(_Session(client))] == ["r2"]


def test_the_departure_ride_is_a_separate_ride(client):
    sign_in(client)
    schedule(client, "arrive")
    assert schedule(client, "depart").headers["location"] == "/rides/r2"


def test_a_ride_that_is_not_yours_is_a_404(client):
    sign_in(client)
    assert client.get("/rides/r9").status_code == 404 and client.post("/rides/r9/cancel").status_code == 404
    assert client.get("/rides/%3Cscript%3E").status_code == 404


# ---- validation --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad,words", [({"phone": "12345"}, "phone"), ({"phone": ""}, "phone"), ({"first": ""}, "first name"), ({"last": "R<b>"}, "last name")])
def test_a_bad_guest_re_shows_the_form_with_the_reason_and_stores_nothing(client, bad, words):
    sign_in(client)
    r = schedule(client, **bad)
    assert r.status_code == 422
    text = visible(r.text)
    assert words in text
    assert not rides.list_rides(_Session(client))
    html = client.post("/rides", data={**GUEST, **bad, "leg": "arrive", "f": "f1", "h": "h1", "c": "none", "p": "x", "fare": "x"}).text
    assert 'id="rd-error"' in html


def test_a_stale_fare_is_refused_and_asks_to_choose_again(client):
    sign_in(client)
    r = client.post("/rides", data={**GUEST, "leg": "arrive", "f": "f1", "h": "h1", "c": "none", "p": "x", "fare": "fare_stale"})
    assert r.status_code == 422 and "price has changed" in visible(r.text)
    assert not rides.list_rides(_Session(client))


def test_the_phone_number_is_kept_in_the_session_and_never_in_a_link(client):
    sign_in(client)
    schedule(client)
    for url in ("/rides/r1", "/plan?" + PICK, "/calendar"):
        html = client.get(url).text
        assert not [h for h in re.findall(r'href="([^"]+)"', html) if PHONE_DIGITS in h or "555" in h]


# ---- the calendar and /booked ------------------------------------------------------------------------------------

def test_a_scheduled_ride_is_a_block_on_the_trip_calendar(client):
    sign_in(client)
    book(client)
    assert "Uber · UberX · LAX → The Tidewater" not in client.get("/calendar?view=days").text
    schedule(client, "arrive")
    html = client.get("/calendar?view=days").text
    assert "Uber · UberX · LAX → The Tidewater" in unescape(html)
    block = re.search(r'<a[^>]*data-block="r1"[^>]*>', html).group(0)
    assert 'href="/rides/r1"' in block and 'data-day="0"' in block and f'data-start="{602}"' in block and f'data-end="{602 + 25}"' in block


def test_the_whole_trip_view_lists_the_ride(client):
    sign_in(client)
    book(client)
    schedule(client, "depart")
    text = visible(client.get("/calendar").text)
    assert "Uber · UberX · The Tidewater → LAX" in text and "11:45 AM" in text


def test_before_a_ride_the_calendar_offers_to_schedule_one_and_a_scheduled_leg_stops_offering(client):
    sign_in(client)
    book(client)
    html = client.get("/calendar?view=days").text
    assert 'href="/rides/new?leg=arrive&amp;f=f1&amp;h=h1&amp;c=none"' in html and 'href="/rides/new?leg=depart&amp;f=f1&amp;h=h1&amp;c=none"' in html
    schedule(client, "arrive")
    html = client.get("/calendar?view=days").text
    assert "leg=arrive" not in html and "leg=depart" in html


def test_a_cancelled_ride_leaves_the_calendar_and_the_offer_comes_back(client):
    sign_in(client)
    book(client)
    schedule(client)
    client.post("/rides/r1/cancel")
    html = client.get("/calendar?view=days").text
    assert 'data-block="r1"' not in html and "leg=arrive" in html


def test_a_ride_scheduled_before_booking_appears_once_the_same_trip_is_booked(client):
    sign_in(client)
    schedule(client)  # from the workspace, before paying
    assert "once this trip is booked" in visible(client.get("/rides/r1").text)
    book(client)
    assert 'data-block="r1"' in client.get("/calendar?view=days").text


def test_a_ride_for_other_picks_does_not_show_on_this_trips_calendar(client):
    sign_in(client)
    schedule(client, pick="f=f2&h=h2&c=none")
    book(client)  # f1 / h1
    assert 'data-block="r1"' not in client.get("/calendar?view=days").text


def test_a_flight_only_trip_rides_to_the_city_centre_and_shows_on_the_calendar(client):
    sign_in(client)
    pick = "f=f1&h=none&c=none"
    assert "Los Angeles city centre" in visible(new_page(client, pick=pick).text)
    book(client, pick)
    assert schedule(client, pick=pick).status_code == 303
    assert "Uber · UberX · LAX → Los Angeles city centre" in unescape(client.get("/calendar?view=days").text)
    assert "Los Angeles city centre" in visible(client.get("/booked").text)


def test_booked_lists_the_scheduled_rides_and_offers_the_rest(client):
    sign_in(client)
    book(client)
    text = visible(client.get("/booked").text)
    assert "Schedule an Uber" in text
    schedule(client, "arrive")
    html = client.get("/booked").text
    text = visible(html)
    assert "UberX" in text and "LAX → The Tidewater" in text and "Fri Oct 16" in text and "Simulated" in text
    assert 'href="/rides/r1"' in html and "leg=depart" in html and "leg=arrive" not in html


def test_a_booking_with_a_car_has_no_ride_blocks_or_offers(client):
    sign_in(client)
    book(client, "f=f1&h=h1&c=c1")
    html = client.get("/calendar?view=days").text
    assert "/rides/new" not in html and "Schedule an Uber" not in client.get("/booked").text


# ---- storage -----------------------------------------------------------------------------------------------------

class _Session(dict):
    """The signed session of a test client, as the storage functions see it."""

    def __init__(self, client):
        super().__init__(session_data(client))


def test_the_storage_functions_round_trip_and_replace(client):
    sign_in(client)
    schedule(client)
    s = _Session(client)
    [r] = rides.list_rides(s)
    assert rides.get_ride(s, "r1") == r and r.leg == "arrive" and r.guest.phone == "+13105550123"
    c = rides.cancel_ride(s, "r1")
    assert c.canceled and rides.list_rides(s)[0].canceled
    with pytest.raises(rides.RideError):
        rides.cancel_ride(s, "r7")


def test_a_family_with_too_many_rides_is_refused_politely(client, monkeypatch):
    monkeypatch.setattr(rides, "MAX_RIDES", 1)
    sign_in(client)
    book(client)
    assert schedule(client, "arrive").status_code == 303
    r = schedule(client, "depart")
    assert r.status_code == 422 and "1 rides already" in visible(r.text)
    assert [x.leg for x in rides.list_rides(_Session(client))] == ["arrive"]


def test_rides_are_stored_in_the_family_database_and_the_cookie_holds_only_the_sign_in(client):
    from gitaway import session as ses
    sign_in(client)
    book(client)
    before = len(client.cookies.get("session_"))
    assert schedule(client, "arrive").status_code == 303
    assert schedule(client, "depart").status_code == 303
    assert len(rides.list_rides(_Session(client))) == 2
    assert set(session_data(client)) <= set(ses.AUTH_KEYS) and len(client.cookies.get("session_")) <= before + 40


def test_every_member_of_the_family_sees_the_rides_on_a_trip():
    from gitaway import session as ses
    from tests.test_signin import person
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", None))
    from tests.test_family_storage import add_member
    with add_member("sam", to="ari") as sam:
        ses.switch_trip(sam, ses.trips(sam)[0].id)
        s = _stub_ride(ari)
        assert [r.id for r in rides.list_rides(sam)] == [s.id] and rides.get_ride(sam, s.id) == s
        rides.cancel_ride(sam, s.id)  # either member can act on it
        assert rides.list_rides(ari)[0].canceled


def _stub_ride(session):
    """Schedule the arrival ride of the open trip's booking straight through the model."""
    b = ses.booking(session)
    t, flight, stay = cal_trip(b)
    plan = rides.leg_plan("arrive", flight, stay, t)
    est = rides.provider().estimates(plan)[0]
    req = rides.ScheduleRequest(plan, rides.validate_guest("Ari", "Rivera", "(310) 555-0123"), est.product_id, est.fare_id, rides.next_ride_id(session), rides.booking_key(b))
    return rides.schedule_ride(session, req)


def cal_trip(b):
    from gitaway import tripcal
    return tripcal.trip_of(b), tripcal.flight_of(b), tripcal.stay_of(b)


def test_only_real_ids_and_legs_are_accepted(client):
    sign_in(client)
    assert "Pick the arrival or the departure" in visible(client.get("/rides/new?leg=sideways&" + PICK).text)
    assert client.post("/rides", data={**GUEST, "leg": "arrive", "f": "f1", "h": "h1", "c": "none", "p": "bogus", "fare": "x"}).status_code in (409, 422)


def test_one_cancel_rule_in_every_place_it_is_worded(client):
    sign_in(client)
    schedule(client)
    pages = visible(new_page(client, "depart").text) + visible(client.get("/rides/r1").text)
    assert "1 hour" not in pages and "until your driver arrives" in pages
