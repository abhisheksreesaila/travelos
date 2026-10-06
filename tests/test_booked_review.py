"""F-093 review fixes: hand-added flights are booking lines with a sheet (pass cards, Fix and Remove for editors), Add a flight lives in the SOS sheet, SOS is on the plan, the
Family tab and the Ask page, a refused phone or pass goes back to the sheet with the reason, Help has a way back to the day, and the sample flight sheet links to where passes are added."""

import re
from html import unescape

from gitaway import passes
from tests.test_booked import crew, first_leg_key, opened, sheet_of, trip  # noqa: F401 - fixtures and helpers
from tests.test_calendar import book
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_passes import add_flight, add_pass
from tests.test_signin import person
from tests.test_trip_canvas import bare, tag, text


def added_flight_id(session):
    return next(f for f in passes.flights(session) if f["source"] == "added")["id"]


def test_a_hand_added_flight_is_a_booking_line_on_its_day_with_a_sheet(trip):
    assert add_flight(trip).status_code == 303                          # UA 1234 LAX to SFO, Sat Oct 17, 2:25 PM
    fid = added_flight_id(person("ari"))
    page = bare(trip.get("/trip/canvas?day=1").text)
    line = re.search(r'<a\b[^>]*class="cz-bk[ "][^>]*>', page).group(0)
    assert f"booked=fl-{fid[:12]}" in line and 'data-kind="flight"' in line
    assert "United 1234" in text(page) and "2:25 PM" in text(page)
    assert f"booked=fl-{fid[:12]}" in bare(trip.get("/trip/canvas").text)          # and in the week
    sheet = sheet_of(opened(trip, f"fl-{fid[:12]}", 1))
    t = text(sheet)
    assert "LAX → SFO" in t and "United 1234" in t and "Passes & documents" in t and "Add a pass" in t
    assert "Fix this flight" in t and "Remove this flight" in t
    assert 'action="/trip/help/flight"' in sheet and 'name="next"' in sheet


def test_a_pass_a_fix_and_a_removal_of_a_hand_added_flight_come_back_to_the_canvas(trip):
    add_flight(trip)
    p = person("ari")
    fid = added_flight_id(p)
    key, bid = f"f:{fid}", f"fl-{fid[:12]}"
    back = f"/trip/canvas?day=1&booked={bid}"
    r = add_pass(trip, key, "Abhi", next=back)
    assert r.headers["location"] == back
    assert "Abhi" in text(sheet_of(opened(trip, bid, 1))) and "Show everyone's passes" in text(sheet_of(opened(trip, bid, 1)))
    r = trip.post("/trip/help/flight", data={"flight_id": fid, "airline": "United", "number": "999", "from_code": "LAX", "to_code": "SFO", "fly_on": "2026-10-17", "time": "15:00", "next": back}, follow_redirects=False)
    assert r.headers["location"] == back and "United 999" in text(sheet_of(opened(trip, bid, 1)))
    r = trip.post("/trip/help/flight/remove", data={"flight_id": fid, "next": "/trip/canvas?day=1"}, follow_redirects=False)
    assert r.headers["location"] == "/trip/canvas?day=1" and not [f for f in passes.flights(p) if f["source"] == "added"]


def test_a_viewer_reads_a_hand_added_flights_sheet_with_no_forms(crew):
    owner, ed, vi = crew
    add_flight(owner)
    bid = f"fl-{added_flight_id(person('ari'))[:12]}"
    sheet = sheet_of(opened(vi, bid, 1))
    assert "United 1234" in text(sheet) and "<form" not in sheet and "Fix this flight" not in text(sheet)


def test_an_editor_can_add_a_flight_from_the_sos_sheet_and_come_back(trip):
    page = bare(trip.get("/trip/canvas?day=1&sos=1").text)
    sheet = page[page.index('class="cz-sheet cz-sheet-sos'):]
    form = re.search(r'<form[^>]*action="/trip/help/flight".*?</form>', sheet, re.S).group(0)
    assert unescape(re.search(r'name="next" value="([^"]+)"', form).group(1)) == "/trip/canvas?day=1&sos=1" and "Add a flight" in text(sheet)
    r = trip.post("/trip/help/flight", data={"airline": "United", "number": "1234", "from_code": "LAX", "to_code": "SFO", "fly_on": "2026-10-17", "time": "14:25", "next": "/trip/canvas?day=1&sos=1"}, follow_redirects=False)
    assert r.headers["location"] == "/trip/canvas?day=1&sos=1" and added_flight_id(person("ari"))


def test_a_viewer_has_no_add_a_flight_in_sos(crew):
    owner, ed, vi = crew
    assert "/trip/help/flight" not in bare(vi.get("/trip/canvas?sos=1").text)


def test_a_refused_phone_or_pass_goes_back_to_the_sheet_with_the_reason(trip):
    back = "/trip/canvas?day=0&booked=b-in"
    r = trip.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "nope", "next": back}, follow_redirects=False)
    assert r.headers["location"] == back + "&err=phone"
    sheet = sheet_of(bare(trip.get(back + "&err=phone").text))
    assert 'role="alert"' in sheet and "phone number" in text(sheet)
    key = first_leg_key(person("ari"))
    r = add_pass(trip, key, "", next="/trip/canvas?day=0&booked=b-out")
    assert r.headers["location"] == "/trip/canvas?day=0&booked=b-out&err=traveller"
    assert "Say who the pass is for" in text(sheet_of(bare(trip.get("/trip/canvas?day=0&booked=b-out&err=traveller").text)))
    r = add_pass(trip, key, "", next="https://evil.example/")
    assert r.headers["location"].startswith("/trip/help?err=traveller")


def test_help_has_a_quiet_way_back_to_the_day(trip):
    html = trip.get("/trip/help").text
    assert 'href="/trip"' in tag(html, "hp-back")


def test_sos_is_on_the_plan_the_family_tab_and_the_ask_page_and_not_the_map(client, azure):
    from tests.test_canvas_pages import added
    from tests.test_trip_canvas import uni_id
    book(client)
    added(client)
    page = bare(client.get(f"/trip/canvas?block={uni_id()}").text)
    assert "sos=1" in tag(page, "cz-sos") and 'id="cz-sos-tpl"' in page
    sheet = bare(client.get(f"/trip/canvas?block={uni_id()}&sos=1").text)
    assert 'class="cz-sheet cz-sheet-sos' in sheet and 'data-level="step"' in sheet and "cz-sos-tpl" not in sheet
    for path in ("/trip/family", "/trip/ask"):
        assert "/trip/canvas?sos=1" in unescape(tag(client.get(path).text, "ph-sos")), path
    assert 'id="ph-sos"' not in client.get("/trip/map").text


def test_the_sample_flight_sheet_links_editors_to_where_passes_are_added(client):
    book(client)
    sheet = sheet_of(bare(client.get("/trip/canvas?day=0&booked=b-out").text))
    assert 'href="/trip/help#hp-passes"' in sheet
