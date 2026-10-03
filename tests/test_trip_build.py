"""F-055: the guided trip builder, through the HTTP seam: a few friendly questions build the same trip as the template, with the same
preview and the same save, and no YAML anywhere."""

import re
from html import unescape
from pathlib import Path

import pytest

from gitaway import importer, session as ses, tripbuild as tb, tripimport as ti
from tests.test_roles import crew  # noqa: F401 - a fixture: an admin, an editor and a viewer
from tests.test_signin import person, session_data, sign_in

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()
PATH = "/trips/build"


def draft_of(html):
    m = re.search(r"""name="draft" value=(?:"([^"]*)"|'([^']*)')""", html)
    return unescape(m.group(1) or m.group(2))


class Walk:
    """A person answering the builder one step at a time, the way the browser does: each post carries the draft the last page handed back."""

    def __init__(self, client):
        self.client, self.html, self.status = client, client.get(PATH).text, 200

    def post(self, step, nav="next", **fields):
        r = self.client.post(PATH, data={"draft": draft_of(self.html), "step": str(step), "nav": nav, **fields})
        self.html, self.status = r.text, r.status_code
        return r

    @property
    def text(self):
        return unescape(re.sub(r"<[^>]+>", " ", self.html))


WHERE = {"title": "LA with the kids", "destination": "Los Angeles"}
DATES = {"start": "2026-10-16", "end": "2026-10-20"}
WHO = {"adults": "2", "nkids": "2", "k1": "7", "k2": "4", "an1": "Abhi", "ae1": "you@gmail.com", "an2": "Priya", "ae2": "priya@gmail.com"}


def leg(i, **kw):
    return {f"leg{i}_{k}": v for k, v in kw.items()}


FLIGHTS = {"flying": "yes",
           **leg(0, airline="Alaska Airlines", number="AS 1234", **{"from": "SFO"}, to="LAX", depart_date="2026-10-16", depart_time="08:05", arrive_date="2026-10-16", arrive_time="09:32", confirmation="ABCDEF", seats="12A, 12B, 12C, 12D"),
           **leg(1, airline="Alaska Airlines", number="AS 1235", **{"from": "LAX"}, to="SFO", depart_date="2026-10-20", depart_time="14:10", arrive_date="2026-10-20", arrive_time="15:37", confirmation="ABCDEF")}
HOTEL = {"stay": "yes", "hotel0_name": "The Example Hotel Santa Monica", "hotel0_address": "123 Ocean Ave, Santa Monica, CA 90401", "hotel0_check_in_date": "2026-10-16", "hotel0_check_in_time": "15:00",
         "hotel0_check_out_date": "2026-10-20", "hotel0_check_out_time": "11:00", "hotel0_confirmation": "987654321", "hotel0_room": "2 Queen Beds, Ocean View", "hotel0_phone": "+1 310 555 0100"}
CAR = {"rent": "yes", "car_company": "Hertz", "car_pickup_place": "LAX", "car_pickup_date": "2026-10-16", "car_pickup_time": "10:00", "car_dropoff_place": "LAX",
       "car_dropoff_date": "2026-10-20", "car_dropoff_time": "12:00", "car_confirmation": "H1234567", "car_car": "Midsize SUV", "car_phone": "+1 310 555 0199"}
NOTES = {"notes": ti.parse(TEMPLATE).plan.notes, "booked_on": "Expedia", "itinerary": "7123456789012"}


def whole_trip(w, flights=FLIGHTS, hotel=HOTEL, car=CAR):
    for step, fields in enumerate((WHERE, DATES, WHO, flights, hotel, car, NOTES), 1):
        assert w.post(step, **fields).status_code == 200, (step, w.text[:400])
    return w


# ---- the same trip as the template ----------------------------------------------------------------------------------

def test_signed_out_goes_through_sign_in(client):
    for method, path in (("get", PATH), ("post", PATH), ("post", f"{PATH}/save")):
        r = getattr(client, method)(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin?next="), path


def test_the_questions_build_exactly_the_trip_the_template_does(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    assert "Check your trip" in w.text and 'id="ti-save"' in w.html  # the importer's own preview
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    built = importer.plan_of(person())
    assert built == ti.parse(TEMPLATE).plan  # flights, hotel, car, party, confirmation numbers: all of it
    trips = ses.trips(person())
    assert len(trips) == 1 and trips[0].source == "imported" and trips[0].title == "LA with the kids"


def test_the_preview_is_the_import_preview_with_confirmations_and_booked_elsewhere(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    for expected in ("LA with the kids", "Oct 16 – 20", "2 adults, 2 kids", "Alaska Airlines AS 1234 · SFO → LAX", "The Example Hotel Santa Monica", "Hertz", "ABCDEF", "987654321", "H1234567",
                     "6 booked items will go on your calendar", "Booked elsewhere · Expedia", "Save this trip"):
        assert expected in w.text, expected
    assert ses.trips(person()) == []  # a preview writes nothing
    import_preview = client.post("/trips/import", data={"text": TEMPLATE}).text
    for card in ("ti-flights", "ti-hotel", "ti-car", "ti-travelers", "ti-trip"):
        assert f'id="{card}"' in w.html and f'id="{card}"' in import_preview


def test_the_calendar_shows_the_same_blocks_as_an_imported_template(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    client.post(f"{PATH}/save", data={"draft": draft_of(w.html)})
    html = client.get("/calendar?view=days").text
    assert "Alaska Airlines AS 1234" in html and "booked elsewhere" in html
    assert 'data-block="b-out"' in html and 'data-block="b-in"' in html
    assert "ABCDEF" not in html  # confirmation numbers stay out of the page and its blocks


def test_no_yaml_anywhere_and_the_cookie_holds_only_the_sign_in(client):
    sign_in(client)
    w = Walk(client)
    before = set(session_data(client))
    pages = [w.html]
    for step, fields in enumerate((WHERE, DATES, WHO, FLIGHTS, HOTEL, CAR, NOTES), 1):
        w.post(step, **fields)
        pages.append(w.html)
    for html in pages:
        low = unescape(html).lower()
        assert "yaml" not in low and "trip:" not in low and "travelers:" not in low
        assert "<textarea" not in low or 'name="notes"' in low
    assert set(session_data(client)) == before  # nothing the builder keeps goes in the cookie


# ---- each step ------------------------------------------------------------------------------------------------------

def test_step_one_asks_where_and_has_a_step_indicator_and_labelled_fields(client):
    sign_in(client)
    html = client.get(PATH).text
    assert "Step 1 of 7" in html and 'aria-current="step"' in html and html.count("tb-dot") >= 7
    assert 'name="title"' in html and 'name="destination"' in html
    for name in re.findall(r'<input[^>]*name="(title|destination)"', html):
        assert re.search(rf'<label[^>]*>.*?name="{name}".*?</label>', html, re.S)


def test_every_step_checks_its_answers_with_friendly_messages_tied_to_the_field(client):
    sign_in(client)
    w = Walk(client)
    r = w.post(1, title="", destination="")
    assert r.status_code == 422 and "Step 1 of 7" in w.text
    assert "The trip name is needed." in w.text and 'aria-invalid="true"' in w.html and 'aria-describedby="tb-err-title"' in w.html and 'id="tb-err-title"' in w.html
    assert 'role="alert"' in w.html
    w.post(1, **WHERE)
    assert "Step 2 of 7" in w.text
    assert w.post(2, start="2026-10-20", end="2026-10-16").status_code == 422 and "come home before you leave" in w.text
    assert w.post(2, start="", end="").status_code == 422 and "Pick the day you leave." in w.text
    w.post(2, **DATES)
    assert w.post(3, adults="2", nkids="1", k1="", an1="", ae1="not an email", an2="", ae2="").status_code == 422
    assert "Pick an age from 0 to 17 for kid 1." in w.text and "does not look like an email address" in w.text
    w.post(3, **WHO)
    assert w.post(4, flying="yes", **leg(0, airline="", number="", **{"from": "nowhere"}, to="LAX", depart_date="2026-10-16", depart_time="", arrive_date="2026-10-16", arrive_time="09:00")).status_code == 422
    for message in ("airline is needed", "three-letter airport code", "Pick the flight 1 leaves time"):
        assert message in w.text, message
    bad = {**FLIGHTS, **leg(1, depart_date="2026-11-30", arrive_date="2026-11-30")}
    assert w.post(4, **bad).status_code == 422 and "outside your trip dates" in w.text
    w.post(4, **FLIGHTS)
    assert w.post(5, **{**HOTEL, "hotel0_check_out_date": "2026-10-16", "hotel0_check_out_time": "09:00"}).status_code == 422
    assert "Check-out has to be after check-in." in w.text
    assert w.post(5, **{**HOTEL, "hotel0_name": ""}).status_code == 422 and "The hotel’s name is needed." in w.text
    w.post(5, **HOTEL)
    assert w.post(6, **{**CAR, "car_company": ""}).status_code == 422 and "The car company is needed." in w.text
    assert w.post(6, **{**CAR, "car_dropoff_date": "2026-10-16", "car_dropoff_time": "08:00"}).status_code == 422
    w.post(6, **CAR)
    assert w.post(7, notes="x" * 3000).status_code == 422 and "too long" in w.text
    assert ses.trips(person()) == []


def test_back_and_next_keep_the_answers(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE)
    w.post(2, **DATES)
    w.post(3, **WHO)
    w.post(4, **FLIGHTS)
    r = w.post(5, nav="back", **{**HOTEL, "hotel0_name": "Half typed"})  # Back keeps this step's answers too, even unchecked
    assert "Step 4 of 7" in w.text and 'value="AS 1234"' in w.html and 'value="ABCDEF"' in w.html
    w.post(4, nav="back", **FLIGHTS)
    w.post(3, nav="back", **WHO)
    assert "Step 2 of 7" in w.text and 'value="2026-10-16"' in w.html and 'value="2026-10-20"' in w.html
    w.post(2, nav="back", **DATES)
    assert "Step 1 of 7" in w.text and 'value="LA with the kids"' in w.html and 'value="Los Angeles"' in w.html
    w.post(1, **WHERE), w.post(2, **DATES)
    assert "Step 3 of 7" in w.text and 'value="Abhi"' in w.html and 'value="priya@gmail.com"' in w.html
    w.post(3, **WHO)
    w.post(4, **FLIGHTS)
    assert "Step 5 of 7" in w.text and 'value="Half typed"' in w.html


def test_smart_defaults_come_from_the_dates_and_airports_are_suggested(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES), w.post(3, **WHO)
    assert w.status == 200 and "Step 4 of 7" in w.text
    # the flight home is on the return date, the arrival airport follows the destination, and common airports are suggested
    assert w.html.count('value="2026-10-20"') >= 2 and 'name="leg1_depart_date"' in w.html
    assert re.search(r'name="leg1_depart_date"[^>]*value="2026-10-20"|value="2026-10-20"[^>]*name="leg1_depart_date"', w.html)
    assert re.search(r'name="leg0_to"[^>]*value="LAX"|value="LAX"[^>]*name="leg0_to"', w.html)
    for code in ("SFO", "OAK", "SJC", "LAX", "BUR", "SNA", "LGB"):
        assert f'<option value="{code}"' in w.html or f"<option>{code}</option>" in w.html, code
    w.post(4, **FLIGHTS)
    assert re.search(r'name="hotel0_check_in_date"[^>]*value="2026-10-16"|value="2026-10-16"[^>]*name="hotel0_check_in_date"', w.html)
    assert re.search(r'name="hotel0_check_out_date"[^>]*value="2026-10-20"|value="2026-10-20"[^>]*name="hotel0_check_out_date"', w.html)


# ---- no flight, no hotel, two hotels --------------------------------------------------------------------------------

def saved(client, w):
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html)}, follow_redirects=False)
    assert r.status_code == 303, r.text[:500]
    return importer.plan_of(person())


def test_not_flying_is_fine(client):
    sign_in(client)
    plan = saved(client, whole_trip(Walk(client), flights={"flying": "no"}))
    assert plan.legs == () and len(plan.hotels) == 1 and plan.rental


def test_no_hotel_is_fine(client):
    sign_in(client)
    plan = saved(client, whole_trip(Walk(client), hotel={"stay": "no"}))
    assert plan.hotels == () and len(plan.legs) == 2


def test_two_hotels_are_fine_and_may_not_overlap(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES), w.post(3, **WHO), w.post(4, **FLIGHTS)
    w.post(5, nav="add", **HOTEL)
    assert 'name="hotel1_name"' in w.html and re.search(r'name="hotel1_check_in_date"[^>]*value="2026-10-20"|value="2026-10-20"[^>]*name="hotel1_check_in_date"', w.html)
    first = {**HOTEL, "hotel0_check_out_date": "2026-10-18"}
    second = {"hotel1_name": "The Second Example Inn Pasadena", "hotel1_address": "45 Colorado Blvd, Pasadena, CA 91101", "hotel1_check_in_date": "2026-10-17", "hotel1_check_in_time": "15:00",
              "hotel1_check_out_date": "2026-10-20", "hotel1_check_out_time": "11:00"}
    assert w.post(5, **first, **second).status_code == 422 and "Two stays cannot overlap" in w.text
    second.update(hotel1_check_in_date="2026-10-18")
    assert w.post(5, **first, **second).status_code == 200
    w.post(6, **CAR), w.post(7, **NOTES)
    plan = saved(client, w)
    assert [h.name for h in plan.hotels] == ["The Example Hotel Santa Monica", "The Second Example Inn Pasadena"]
    w2 = Walk(client)
    w2.post(1, **WHERE), w2.post(2, **DATES), w2.post(3, **WHO), w2.post(4, **FLIGHTS)
    w2.post(5, nav="add", **HOTEL)
    w2.post(5, nav="remove-1", **HOTEL, **second)
    assert 'name="hotel1_name"' not in w2.html


def test_nothing_booked_at_all_is_a_friendly_message(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES), w.post(3, **WHO), w.post(4, flying="no"), w.post(5, stay="no")
    assert w.post(6, rent="no").status_code == 422 and "nothing to put on the calendar" in w.text


def test_a_connection_is_two_legs_and_legs_can_be_added_and_removed(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES), w.post(3, **WHO)
    w.post(4, nav="add", **FLIGHTS)
    assert 'name="leg2_airline"' in w.html
    w.post(4, nav="remove-2", **FLIGHTS, **leg(2, airline="", number=""))
    assert 'name="leg2_airline"' not in w.html


# ---- the same path as the import ------------------------------------------------------------------------------------

def test_replace_existing_is_offered_like_an_import_and_keeps_one_trip(client):
    sign_in(client)
    assert client.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False).status_code == 303  # the template first
    w = Walk(client)
    for step, fields in enumerate((WHERE, DATES, WHO, FLIGHTS, HOTEL, CAR, NOTES), 1):
        w.post(step, **fields)
    assert 'id="ti-replace"' in w.html and "You already imported" in w.text  # the same itinerary number
    token = re.search(r'name="token" value="([0-9a-f]{12})"', w.html).group(1)
    replace = re.search(r'name="replace" value="([^"]+)"', w.html).group(1)
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html), "replace": replace}, follow_redirects=False)
    assert r.status_code == 303 and len(ses.trips(person())) == 1
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html), "token": token}, follow_redirects=False)  # "save as a new trip"
    assert r.status_code == 303 and len(ses.trips(person())) == 2


def test_saving_twice_with_the_same_token_makes_one_trip(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    token = re.search(r'name="token" value="([0-9a-f]{12})"', w.html).group(1)
    for _ in range(2):
        assert client.post(f"{PATH}/save", data={"draft": draft_of(w.html), "token": token}, follow_redirects=False).status_code == 303
    assert len(ses.trips(person())) == 1


def test_a_hand_edited_draft_is_checked_again_at_the_end(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    bad = draft_of(w.html).replace('"2026-10-20"', '"2027-01-01"', 1)
    r = client.post(f"{PATH}/save", data={"draft": bad}, follow_redirects=False)
    assert r.status_code == 422 and ses.trips(person()) == []
    assert client.post(f"{PATH}/save", data={"draft": "not json"}, follow_redirects=False).status_code == 422
    assert client.post(PATH, data={"draft": "{" * 50, "step": "9", "nav": "next"}).status_code in (200, 422)


def test_viewers_are_refused_and_editors_can_build(crew):
    admin, editor, viewer = crew
    assert viewer.get(PATH).status_code == 403 and "Only editors and admins" in viewer.get(PATH).text
    assert viewer.post(PATH, data={"step": "1", "nav": "next", **WHERE}, follow_redirects=False).status_code == 403
    assert viewer.post(f"{PATH}/save", data={"draft": "{}"}, follow_redirects=False).status_code == 403
    assert editor.get(PATH).status_code == 200
    w = Walk(editor)
    assert w.post(1, **WHERE).status_code == 200 and "Step 2 of 7" in w.text


# ---- the ways in ----------------------------------------------------------------------------------------------------

def test_the_first_run_welcome_and_the_import_page_link_to_the_builder(client):
    sign_in(client, "newcomer@example.com")
    html = client.get("/start").text
    assert 'href="/trips/build"' in html and "Answer a few questions" in html and "Paste the template" in html and 'href="/trips/import"' in html
    assert 'href="/trips/build"' in client.get("/trips/import").text


def test_every_step_has_unique_ids_and_every_input_has_a_label(client):
    sign_in(client)
    w = Walk(client)
    pages = [w.html]
    for step, fields in enumerate((WHERE, DATES, WHO, FLIGHTS, HOTEL, CAR, NOTES), 1):
        w.post(step, **fields)
        pages.append(w.html)
    for html in pages[:-1]:
        ids = re.findall(r'\bid="([^"]+)"', html)
        assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})
        for tag in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
            if 'type="hidden"' in tag or "tb-default" in tag:
                continue
            ident = re.search(r'\bid="([^"]+)"', tag)
            assert ident and (re.search(rf'for="{ident.group(1)}"', html) or re.search(rf"<label[^>]*>(?:(?!</label>).)*{re.escape(tag)}", html, re.S)), tag
