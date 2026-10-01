"""F-042: import a trip booked elsewhere, through the HTTP seam: paste, preview, save, the calendar, privacy, sharing, rides, a restart."""

import re
from datetime import datetime
from html import unescape
from pathlib import Path

import pytest

from gitaway import familydb, rides, session as ses, share, tripcal as cal
from tests.test_calendar import tag
from tests.test_signin import person, session_data, sign_in, tid

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()
SECRETS = ("ABCDEF", "987654321", "H1234567", "7123456789012")  # the template's confirmation numbers and itinerary number


def no_car(text=TEMPLATE):
    return re.sub(r"\ncar:.*?(?=\nnotes:)", "", text, flags=re.S)


def visible(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


def imported(client, text=TEMPLATE, traveler="ari"):
    sign_in(client, traveler)
    return client.post("/trips/import/save", data={"text": text}, follow_redirects=False)


# ---- the page, the preview, the save ---------------------------------------------------------------------------------

def test_signed_out_goes_through_sign_in(client):
    for method, path in (("get", "/trips/import"), ("post", "/trips/import"), ("post", "/trips/import/save"), ("get", "/trip/details")):
        r = getattr(client, method)(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin?next="), path


def test_the_import_page_has_a_paste_box_and_the_template_to_download(client):
    sign_in(client)
    html = client.get("/trips/import").text
    assert "<textarea" in html and 'name="text"' in html and 'id="ti-preview"' in html
    assert 'href="/trips/import/template"' in html and "Download the template" in html
    r = client.get("/trips/import/template")
    assert r.text == TEMPLATE and "attachment" in r.headers["content-disposition"]


def test_preview_shows_exactly_what_will_be_saved_and_saves_nothing(client):
    sign_in(client)
    r = client.post("/trips/import", data={"text": TEMPLATE})
    assert r.status_code == 200
    text = visible(r.text)
    for expected in ("LA with the kids", "Los Angeles", "Oct 16 – 20", "Expedia", "2 adults, 2 kids", "Alaska Airlines AS 1234 · SFO → LAX", "Alaska Airlines AS 1235 · LAX → SFO",
                     "The Example Hotel Santa Monica", "123 Ocean Ave, Santa Monica, CA 90401", "Hertz", "Midsize SUV", "ABCDEF", "987654321", "H1234567", "Save this trip"):
        assert expected in text, expected
    assert "6 booked items will go on your calendar" in text  # 2 flights, check in and out, car pickup and dropoff
    assert 'id="ti-save"' in r.text
    assert ses.trips(person()) == []  # a preview writes nothing


def test_bad_templates_get_friendly_line_specific_errors_and_keep_the_text(client):
    sign_in(client)
    bad = TEMPLATE.replace("from: SFO", "from: nowhere")
    r = client.post("/trips/import", data={"text": bad})
    assert r.status_code == 422
    n = next(i for i, line in enumerate(TEMPLATE.splitlines(), 1) if "from: SFO" in line)
    assert f"Line {n}:" in r.text and "three-letter airport code" in r.text and 'role="alert"' in r.text
    assert "from: nowhere" in unescape(r.text)  # their text is still in the box
    assert client.post("/trips/import", data={"text": ""}).status_code == 422
    assert client.post("/trips/import", data={"text": "x: " + "a" * 60_000}).status_code == 422
    assert client.post("/trips/import/save", data={"text": bad}, follow_redirects=False).status_code == 422
    assert ses.trips(person()) == []


def test_save_opens_the_calendar_on_the_imported_trip(client):
    r = imported(client)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    trips = ses.trips(person())
    assert len(trips) == 1 and trips[0].source == "imported" and trips[0].current and trips[0].title == "LA with the kids"
    assert "2 adults, 2 kids" in trips[0].detail and "Oct 16 – 20" in trips[0].detail
    html = client.get("/calendar?view=days").text
    assert "LA with the kids" in html and "Oct 16 – 20" in html and "booked elsewhere · Expedia" in html


def test_pressing_save_twice_makes_one_trip_with_a_random_id(client):
    sign_in(client)
    html = client.post("/trips/import", data={"text": TEMPLATE}).text
    token = re.search(r'name="token" value="([0-9a-f]{12})"', html).group(1)
    assert token != re.search(r'name="token" value="([0-9a-f]{12})"', client.post("/trips/import", data={"text": TEMPLATE}).text).group(1)
    for _ in range(2):
        assert client.post("/trips/import/save", data={"text": TEMPLATE, "token": token}, follow_redirects=False).status_code == 303
    assert [t.id for t in ses.trips(person())] == [token]
    assert client.post("/trips/import/save", data={"text": TEMPLATE, "token": "not-a-token"}, follow_redirects=False).status_code == 409


def test_a_template_with_the_same_itinerary_number_offers_to_replace_and_keeps_the_plans(client, clock):
    imported(client, no_car())
    p = person()
    old_id = ses.trips(p)[0].id
    cal.add_activity(p, day=1, start="10:00", end="11:00", title="Griffith Observatory")
    cal.add_note(p, "Bring jackets")
    b = ses.booking(p)
    plan = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_for(b, "arrive"), cal.trip_of(b))
    rides.schedule_ride(p, rides.ScheduleRequest(plan, rides.validate_guest("Ari", "Rivera", "(310) 555-0123"), rides.provider().estimates(plan)[0].product_id,
                                                  rides.provider().estimates(plan)[0].fare_id, rides.next_ride_id(p), rides.booking_key(b)))
    corrected = no_car().replace("end: 2026-10-20", "end: 2026-10-21").replace("title: LA with the kids", "title: LA with the kids (fixed)")
    corrected = corrected.replace("check_out: 2026-10-20 11:00", "check_out: 2026-10-21 11:00").replace("depart: 2026-10-20 14:10", "depart: 2026-10-21 14:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 15:37")
    html = client.post("/trips/import", data={"text": corrected}).text
    assert 'id="ti-replace"' in html and "Replace the existing trip" in html and "LA with the kids" in visible(html)
    assert 'id="ti-replace"' not in client.post("/trips/import", data={"text": no_car().replace("7123456789012", "999").replace("title: LA with the kids", "title: Other").replace("start: 2026-10-16", "start: 2026-10-16")}).text
    r = client.post("/trips/import/save", data={"text": corrected, "replace": old_id}, follow_redirects=False)
    assert r.status_code == 303
    trips = ses.trips(person())
    assert [t.id for t in trips] == [old_id] and trips[0].title == "LA with the kids (fixed)" and "Oct 16 – 21" in trips[0].detail
    assert [a.title for a in cal.activities(person())] == ["Griffith Observatory"] and [n.text for n in cal.notes(person())] == ["Bring jackets"]
    live = [x for x in rides.list_rides(person()) if not x.canceled]
    assert len(live) == 1 and live[0].key == rides.booking_key(ses.booking(person()))  # the ride still belongs to the (corrected) trip
    assert client.post("/trips/import/save", data={"text": corrected, "replace": "nosuchtrip1"}, follow_redirects=False).status_code == 409


def test_the_same_title_and_start_date_also_count_as_the_same_trip(client):
    imported(client)
    html = client.post("/trips/import", data={"text": TEMPLATE.replace('itinerary_number: "7123456789012"', 'itinerary_number: "1"')}).text
    assert 'id="ti-replace"' in html


def test_only_admins_delete_a_trip_and_everything_on_it_goes(client, clock):
    imported(client, no_car())
    p = person()
    trip_id = ses.trips(p)[0].id
    cal.add_activity(p, day=1, start="10:00", end="11:00", title="Griffith Observatory")
    assert 'id="ti-delete"' in client.get("/trip/details").text
    assert client.get(f"/trip/delete?trip={trip_id}").status_code == 200 and "Delete" in client.get(f"/trip/delete?trip={trip_id}").text
    from gitaway.pages import tripimport
    assert tripimport.can_delete({"tenant_role": "admin"}) and not tripimport.can_delete({"tenant_role": "editor"}) and not tripimport.can_delete({"tenant_role": "viewer"})
    assert client.post("/trip/delete", data={"trip": "nosuchtrip1"}, follow_redirects=False).status_code == 404
    assert client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303
    assert ses.trips(person()) == []
    with familydb.using(person()) as db:
        for table, col in (("trip_imports", "trip_id"), ("activities", "trip_id"), ("cal_state", "trip_id"), ("trips", "id")):
            assert familydb.row(db, f"SELECT COUNT(*) AS n FROM {table}")["n"] == 0, table
    assert client.get("/trip/details").status_code == 404


def test_a_viewer_cannot_import():
    from gitaway.pages import tripimport
    assert tripimport.can_import({"tenant_role": "viewer"}) is False
    assert tripimport.can_import({"tenant_role": "editor"}) and tripimport.can_import({"tenant_role": "admin"}) and tripimport.can_import({})


def test_the_trip_limit_is_a_friendly_message(client, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(familydb, "MAX_TRIPS", 1)
    assert client.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False).status_code == 303
    r = client.post("/trips/import/save", data={"text": TEMPLATE.replace("LA with the kids", "Another")}, follow_redirects=False)
    assert r.status_code == 409 and "1 trips already" in r.text


# ---- the calendar ----------------------------------------------------------------------------------------------------

def test_imported_flights_hotel_and_car_are_booked_blocks_marked_booked_elsewhere(client):
    imported(client)
    p = person()
    b = ses.booking(p)
    t = cal.trip("", b)
    blocks = {x.id: x for x in cal.booked_blocks(b, t)}
    assert set(blocks) == {"b-out", "b-back", "b-in", "b-out2", "b-car-pick", "b-car-drop"}
    assert all(x.locked and x.tag == "Booked elsewhere · Expedia" and x.kind == "booked" for x in blocks.values())
    assert (blocks["b-out"].day, blocks["b-out"].start, blocks["b-out"].end) == (0, 8 * 60 + 5, 9 * 60 + 32)
    assert (blocks["b-back"].day, blocks["b-back"].start, blocks["b-back"].end) == (4, 14 * 60 + 10, 15 * 60 + 37)
    assert (blocks["b-in"].day, blocks["b-in"].start) == (0, 15 * 60) and (blocks["b-out2"].day, blocks["b-out2"].start) == (4, 11 * 60)
    assert (blocks["b-car-pick"].day, blocks["b-car-pick"].start, blocks["b-car-drop"].day) == (0, 10 * 60, 4)
    assert blocks["b-out"].title == "Alaska Airlines AS 1234 · SFO → LAX" and blocks["b-in"].title == "Check in · The Example Hotel Santa Monica"
    assert blocks["b-car-pick"].title == "Pick up Hertz car · LAX"
    html = client.get("/calendar?view=days").text
    for bid in blocks:
        node = tag(html, "data-block", bid)
        assert node is not None and "cal-booked" in node["class"], bid
    assert html.count("Booked elsewhere · Expedia") >= 6
    whole = visible(client.get("/calendar").text)
    assert "Booked elsewhere · Expedia" in whole and "Alaska Airlines AS 1234" in whole


def test_the_flight_window_follows_the_real_first_arrival_and_last_departure(client):
    imported(client)
    p = person()
    with pytest.raises(cal.CalendarError, match="You land at 9:32 AM"):
        cal.add_activity(p, day=0, start="07:00", end="08:00", title="Too early")
    with pytest.raises(cal.CalendarError, match="Your flight home leaves at 2:10 PM. Finish by 12:10 PM"):
        cal.add_activity(p, day=4, start="12:30", end="13:30", title="Too late")
    assert cal.add_activity(p, day=0, start="16:30", end="18:00", title="Dinner").id
    assert cal.add_activity(p, day=4, start="08:00", end="09:30", title="Breakfast").id
    with pytest.raises(cal.CalendarError, match="overlaps"):
        cal.add_activity(p, day=0, start="15:00", end="16:00", title="In the check-in")  # the hotel's check-in is a block too


def test_a_connection_uses_the_real_arrival_at_the_destination(client):
    text = TEMPLATE.replace("""  - airline: Alaska Airlines
    number: AS 1235""", """  - airline: Alaska Airlines
    number: AS 99
    from: LAX
    to: DEN
    depart: 2026-10-20 06:00
    arrive: 2026-10-20 09:30
  - airline: Alaska Airlines
    number: AS 1235""").replace("    from: LAX\n    to: SFO\n    depart: 2026-10-20 14:10\n    arrive: 2026-10-20 15:37", "    from: DEN\n    to: SFO\n    depart: 2026-10-20 14:10\n    arrive: 2026-10-20 15:37")
    imported(client, text)
    b = ses.booking(person())
    assert [x.id for x in cal.booked_blocks(b, cal.trip("", b)) if x.id.startswith("b-leg") or x.id in ("b-out", "b-back")] == ["b-out", "b-back", "b-leg3"]
    p = person()
    with pytest.raises(cal.CalendarError, match="You land at 9:32 AM"):
        cal.add_activity(p, day=0, start="07:00", end="08:00", title="Early")


def test_the_trip_switcher_lists_the_imported_trip(client):
    from tests.test_calendar import book
    book(client)
    imported(client)
    html = client.get("/calendar").text
    assert "2 trips" in html and "LA with the kids" in html and 'data-trip="' in html
    assert "booked elsewhere" not in tag(html, "class", "cal-trips-sum").get("class", "")


def test_voice_forks_and_notes_work_on_an_imported_trip(client):
    imported(client)
    p = person()
    assert cal.add_note(p, "Pack sunscreen").text == "Pack sunscreen"
    from gitaway import voice
    assert voice.preview(p, None, "") is not None
    placed = cal.preview_plans(p, [cal.Plan("d1s1", 1, 10 * 60, 12 * 60, "Griffith Observatory", "culture")])
    assert placed[0].state == "free"
    added, _ = cal.apply_plans(p, [cal.Plan("d1s1", 1, 10 * 60, 12 * 60, "Griffith Observatory", "culture")], ["d1s1"], by="Mom")
    assert [a.title for a in added] == ["Griffith Observatory"]
    assert client.get("/forks").status_code == 200 and client.get("/calendar?voice=1").status_code == 200


# ---- confirmation numbers: family only ---------------------------------------------------------------------------------

def test_confirmation_numbers_show_on_the_booking_detail_and_the_details_page_only(client):
    imported(client)
    calendar = client.get("/calendar?view=days").text
    whole = client.get("/calendar").text
    for secret in SECRETS:
        assert secret not in calendar and secret not in whole, secret  # not in the calendar itself, nor in any link or meta
    detail = client.get("/calendar?detail=b-out")
    assert "ABCDEF" in detail.text and 'id="cal-confirmation"' in detail.text and "Alaska Airlines AS 1234" in visible(detail.text)
    assert "987654321" in client.get("/calendar?detail=b-in").text and "H1234567" in client.get("/calendar?detail=b-car-pick").text
    assert "nothing" not in client.get("/calendar?detail=b-nope").text and "ABCDEF" not in client.get("/calendar?detail=b-nope").text
    full = visible(client.get("/trip/details").text)
    for secret in SECRETS:
        assert secret in full, secret
    for href in re.findall(r'href="([^"]*)"', calendar + client.get("/trip/details").text):
        assert not any(s in href for s in SECRETS), href


def test_other_families_and_signed_out_visitors_never_see_them(client):
    imported(client)
    client.cookies.clear()
    assert client.get("/calendar?detail=b-out", follow_redirects=False).status_code == 303
    assert client.get("/trip/details", follow_redirects=False).status_code == 303
    sign_in(client, "sam")  # another person: their own family, with no imported trip
    other = client.get("/calendar?detail=b-out").text
    assert all(s not in other for s in SECRETS)
    r = client.get("/trip/details")
    assert r.status_code == 404 and all(s not in r.text for s in SECRETS)


def test_the_share_snapshot_the_offline_meta_and_the_cookie_never_hold_them(client):
    from gitaway import community
    imported(client)
    assert client.post("/share", data={"custom": "1"}, follow_redirects=False).status_code in (200, 303)
    rows = community.rows(kind="shared")
    assert len(rows) == 1
    page = client.get(f"/trips/{rows[0]['slug']}").text
    snapshot = repr(rows[0])
    client.cookies.clear()
    public = client.get(f"/trips/{rows[0]['slug']}").text
    for secret in SECRETS:
        assert secret not in snapshot and secret not in page and secret not in public, secret
    assert "Booked elsewhere" not in public and "Alaska Airlines AS 1234" in public  # the plans show, the family's marker and numbers do not
    sign_in(client)
    for path in ("/calendar", "/start", "/trips/import", "/offline"):
        html = client.get(path).text
        metas = " ".join(re.findall(r"<meta[^>]*>", html))
        assert all(s not in metas for s in SECRETS), path
    assert not any(s in str(session_data(client)) for s in SECRETS)


# ---- sharing uses the trip's real dates ---------------------------------------------------------------------------------

def test_a_shared_trip_uses_the_trips_real_dates_and_length(client):
    imported(client, TEMPLATE.replace("end: 2026-10-20", "end: 2026-10-22").replace("check_out: 2026-10-20 11:00", "check_out: 2026-10-22 11:00")
             .replace("depart: 2026-10-20 14:10", "depart: 2026-10-22 14:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-22 15:37").replace("dropoff: LAX, 2026-10-20 12:00", "dropoff: LAX, 2026-10-22 12:00"))
    built = share.build(person())
    assert len(built.days) == 7 and built.stats[0] == ("7 days", "Oct 16 – 22")
    assert built.title == "LA with the kids" and built.days[0].stops[0].title.startswith("Alaska Airlines AS 1234")
    assert built.days[-1].date == "THU, OCT 22" and built.days[0].date == "FRI, OCT 16"


def test_a_shared_demo_trip_uses_its_own_dates_too(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "none", "d": "2026-11-02", "r": "2026-11-05", "a": "2", "k": "5"}, follow_redirects=False)
    b = ses.booking(person())
    assert b and "2026-11-02" in b["trip"]
    built = share.build(person())
    assert len(built.days) == 4 and built.stats[0] == ("4 days", "Nov 2 – 5")
    assert built.days[0].date == "MON, NOV 2" and built.days[-1].date == "THU, NOV 5"


# ---- rides on an imported trip -----------------------------------------------------------------------------------------

GUEST = {"first": "Ari", "last": "Rivera", "phone": "(310) 555-0123"}


@pytest.fixture
def clock(monkeypatch):
    """A fixed 'now' a week before the trip, so the simulator's lead-time rules do not depend on the day the tests run."""
    from datetime import timezone
    fixed = datetime(2026, 10, 9, 12, 0, tzinfo=rides.TZ)
    monkeypatch.setattr(rides, "now", lambda demo=False: fixed)
    return fixed


def test_a_trip_with_a_car_has_no_rides(client):
    imported(client)
    b = ses.booking(person())
    assert cal.rides_of(b) is None and cal.ride_offers(person(), b, cal.trip("", b)) == []


def test_rides_run_from_the_real_arrival_airport_to_the_hotel_address(client, clock):
    imported(client, no_car())
    p = person()
    b = ses.booking(p)
    t = cal.trip("", b)
    offers = {o.id: o for o in cal.ride_offers(p, b, t)}
    assert set(offers) == {"ro-arrive", "ro-depart"}
    assert offers["ro-arrive"].day == 0 and offers["ro-arrive"].start == 9 * 60 + 32 + 30  # landing + the curb time
    assert offers["ro-arrive"].title == "Schedule an Uber · LAX → The Example Hotel Santa Monica"
    html = client.get("/calendar?view=days").text
    href = re.search(r'href="(/rides/new\?[^"]*leg=arrive[^"]*)"', html).group(1)
    assert "trip=" in href
    new = client.get(unescape(href))
    assert new.status_code == 200 and "LAX" in new.text and "UberX" in new.text and "Simulated: no real ride is booked" in new.text
    choose = re.search(r'href="(/rides/new\?[^"]*p=x[^"]*)"', new.text).group(1)
    confirm = client.get(unescape(choose)).text
    assert "123 Ocean Ave, Santa Monica, CA 90401" in unescape(confirm) and "The Example Hotel Santa Monica" in confirm
    form = {m[0]: unescape(m[1]) for m in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', confirm)}
    r = client.post("/rides", data={**form, **GUEST}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/rides/r")
    ride = rides.list_rides(p)[0]
    assert (ride.leg, ride.airport, ride.pickup_time.strftime("%Y-%m-%d %H:%M"), ride.party) == ("arrive", "LAX", "2026-10-16 10:02", 4)
    assert ride.plan.dropoff.address == "123 Ocean Ave, Santa Monica, CA 90401" and ride.plan.pickup.area == "LAX"
    page = client.get(r.headers["location"]).text
    assert "Santa Monica" in page and "Shown on your trip calendar." in page
    on_cal = client.get("/calendar?view=days").text
    assert tag(on_cal, "data-block", ride.id) and "Uber · UberX · LAX → The Example Hotel Santa Monica" in unescape(on_cal)
    assert "ro-arrive" not in on_cal and "ro-depart" in on_cal  # the arrival is scheduled; the departure is still offered


def test_the_departure_ride_leaves_in_time_for_the_real_flight_home(client, clock):
    imported(client, no_car())
    p = person()
    b = ses.booking(p)
    plan = rides.leg_plan("depart", cal.flight_of(b), cal.stay_of(b), cal.trip_of(b))
    assert plan.pickup_time.strftime("%Y-%m-%d") == "2026-10-20" and plan.pickup.name == "The Example Hotel Santa Monica" and plan.dropoff.area == "LAX"
    assert plan.pickup_time.hour * 60 + plan.pickup_time.minute <= 14 * 60 + 10 - 120 - 30  # at the airport two hours before takeoff


def test_a_party_of_five_rides_in_an_xl(client, clock):
    five = no_car().replace("  - name: Kid 2\n    age: 4\n", "  - name: Kid 2\n    age: 4\n  - name: Gran\n")
    imported(client, five)
    p = person()
    b = ses.booking(p)
    plan = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_of(b), cal.trip_of(b))
    ests = {e.key: e for e in rides.provider().estimates(plan)}
    assert plan.party == 5 and not ests["x"].fits and ests["xl"].fits


def test_other_airports_have_no_rides(client):
    imported(client, no_car().replace("to: LAX", "to: JFK").replace("from: LAX", "from: JFK"))
    b = ses.booking(person())
    assert cal.rides_of(b) is None and cal.ride_offers(person(), b, cal.trip("", b)) == []


def test_a_ride_for_another_trip_is_refused(client, clock):
    imported(client, no_car())
    r = client.get("/rides/new?leg=arrive&f=imp-nothere&h=imp-nothere&c=none&trip=zzz")
    assert "not the one open" in r.text


# ---- storage -----------------------------------------------------------------------------------------------------------

def test_it_survives_a_restart_and_is_stored_only_in_the_family_database(client):
    imported(client)
    before = client.get("/calendar?view=days").text
    familydb.forget_schema_cache()  # what a server restart forgets
    from main import app
    from starlette.testclient import TestClient
    fresh = TestClient(app, client=("127.0.0.1", 50000))
    fresh.cookies.update(client.cookies)
    after = fresh.get("/calendar?view=days").text
    assert tag(after, "data-block", "b-out") == tag(before, "data-block", "b-out") and "booked elsewhere · Expedia" in after
    assert "ABCDEF" in fresh.get("/calendar?detail=b-out").text and "ABCDEF" in fresh.get("/trip/details").text
    assert not any(s in str(session_data(fresh)) for s in SECRETS)  # the cookie holds only the sign-in
    with familydb.using(person()) as db:
        row = familydb.row(db, "SELECT t.source, i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id")
    assert row["source"] == "imported" and "ABCDEF" in row["doc"]
