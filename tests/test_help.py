"""F-069: the Help tab: tonight's hotel (address, phone, check-in/out, confirmation behind a tap, Directions), the car, 911, the family's own
numbers, adding and fixing numbers, and the car's phone through the template, the parser and the builder."""

import re
from datetime import date, datetime
from html import unescape

import pytest

from gitaway import catalog, phones, tripbuild as tb, tripday as td, tripimport as ti
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in
from tests.test_trip_edit import edit_url, trip_ids
from tests.test_trip_import import TEMPLATE, imported

TWO_HOTELS = TEMPLATE.replace("""hotel:
  name: The Example Hotel Santa Monica
  address: 123 Ocean Ave, Santa Monica, CA 90401
  check_in: 2026-10-16 15:00
  check_out: 2026-10-20 11:00
  confirmation: "987654321"
  room: 2 Queen Beds, Ocean View      # optional
  rooms: 1                            # optional
  phone: "+1 310 555 0100"           # optional
""", """hotels:
  - name: The Example Hotel Santa Monica
    address: 123 Ocean Ave, Santa Monica, CA 90401
    check_in: 2026-10-16 15:00
    check_out: 2026-10-18 11:00
    confirmation: "987654321"
    phone: "+1 310 555 0100"
  - name: The Second Example Inn Pasadena
    address: 45 Colorado Blvd, Pasadena, CA 91101
    check_in: 2026-10-18 15:00
    check_out: 2026-10-20 11:00
    confirmation: "123123123"
""")


@pytest.fixture
def at(monkeypatch):
    def pin(day, hhmm="12:00"):
        h, m = map(int, hhmm.split(":"))
        monkeypatch.setattr(catalog, "today", lambda *_: day)
        monkeypatch.setattr(td, "now_minute", lambda *_: h * 60 + m)
    return pin


def text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def tag(html, id_):
    return re.search(r"<[a-z]+\b[^>]*\bid=\"%s\"[^>]*>" % id_, html).group(0)


# ---- tonight's hotel ----------------------------------------------------------------------------------------------------

def hotels():
    return ti.parse(TWO_HOTELS).plan.hotels


@pytest.mark.parametrize("day, expect", [
    (date(2026, 10, 1), 0),    # before the trip: the first stay
    (date(2026, 10, 16), 0),   # the night of check-in
    (date(2026, 10, 17), 0),
    (date(2026, 10, 18), 1),   # check-out of the first and check-in of the second: tonight is the second
    (date(2026, 10, 19), 1),
    (date(2026, 10, 20), 1),   # the last day: nothing covers tonight, so the last stay
    (date(2026, 11, 5), 1),    # after the trip: the last stay
])
def test_tonights_hotel_across_dates(day, expect):
    assert phones.tonight(hotels(), day) == expect


def test_no_hotels_means_no_stay():
    assert phones.tonight((), date(2026, 10, 17)) is None


def test_help_shows_tonights_hotel_and_the_card_changes_with_the_date(client, at):
    imported(client, TWO_HOTELS)
    at(date(2026, 10, 17))
    html = client.get("/trip/help").text
    assert "The Example Hotel Santa Monica" in html and "Second Example Inn" not in html
    at(date(2026, 10, 19))
    html = client.get("/trip/help").text
    assert "The Second Example Inn Pasadena" in html and "Santa Monica" not in tag(html, "hp-hotel") + text(html.split('id="hp-hotel"')[1].split('id="hp-sos"')[0])


def test_help_has_the_hotel_address_phone_times_directions_and_the_confirmation_behind_a_tap(client, at):
    imported(client)
    at(date(2026, 10, 17))
    html = client.get("/trip/help").text
    card = html.split('id="hp-hotel"')[1].split('id="hp-sos"')[0]
    shown = text(card)
    assert "123 Ocean Ave, Santa Monica, CA 90401" in shown
    assert 'href="tel:+13105550100"' in card and "Front desk" in shown
    assert "Fri Oct 16, 3:00 PM" in text(card.split('id="hp-in"')[1]) and "Tue Oct 20, 11:00 AM" in text(card.split('id="hp-out"')[1])
    assert re.search(r"<details[^>]*data-confirm[^>]*>.*987654321.*</details>", card, re.S)  # the number sits inside a tap-to-open details
    assert not re.search(r"<details[^>]*data-confirm[^>]*\bopen\b", card)  # shut until tapped
    assert "Confirmation" in shown
    assert "maps" in tag(card, "hp-directions") and "Ocean+Ave" in tag(card, "hp-directions")


def test_help_has_the_car_911_and_no_secret_leaks_to_a_signed_out_visitor(client, at):
    imported(client)
    at(date(2026, 10, 17))
    html = client.get("/trip/help").text
    assert 'href="tel:911"' in html
    car = html.split('id="hp-car"')[1].split('id="hp-sos"')[0]
    assert "Hertz" in car and "LAX" in text(car) and 'href="tel:+13105550199"' in car
    client.cookies.clear()
    r = client.get("/trip/help", follow_redirects=False)
    assert r.status_code == 303 and "987654321" not in r.text


def test_help_without_a_phone_number_says_so_and_offers_to_add_it(client, at):
    imported(client, TEMPLATE.replace('  phone: "+1 310 555 0100"           # optional\n', ""))
    at(date(2026, 10, 17))
    html = client.get("/trip/help").text
    assert "No phone number yet" in html and "tel:+13105550100" not in html
    assert "Add the hotel number" in html


# ---- adding and fixing numbers ------------------------------------------------------------------------------------------

def test_a_hotel_number_can_be_fixed_right_on_help_and_edit_trip_shows_it(client, at):
    imported(client)
    at(date(2026, 10, 17))
    r = client.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "(310) 555-0123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/help"
    html = client.get("/trip/help").text
    assert 'href="tel:3105550123"' in html and "tel:+13105550100" not in html
    [trip_id] = trip_ids()
    assert "(310) 555-0123" in unescape(client.get(edit_url(trip_id)).text)  # Edit trip opens with the fixed number


def test_the_car_number_can_be_added_right_on_help(client, at):
    imported(client, TEMPLATE.replace('  phone: "+1 310 555 0199"            # optional: the rental counter, shown on Help\n', ""))
    at(date(2026, 10, 17))
    assert "No phone number yet" in client.get("/trip/help").text
    client.post("/trip/help/phone", data={"kind": "car", "index": "0", "phone": "+1 800 555 0145"})
    html = client.get("/trip/help").text
    assert 'href="tel:+18005550145"' in html.split('id="hp-car"')[1]


def test_a_bad_number_is_refused_and_changes_nothing(client, at):
    imported(client)
    at(date(2026, 10, 17))
    for bad in ("call me", "123", "1" * 31, "<script>12345678</script>"):
        r = client.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": bad}, follow_redirects=False)
        assert r.headers["location"] == "/trip/help?problem=phone"
    html = client.get("/trip/help?problem=phone").text
    assert "did not look right" in html and "tel:+13105550100" in html


def test_an_unknown_booking_is_refused(client, at):
    imported(client)
    for data in ({"kind": "hotel", "index": "7", "phone": "310 555 0100"}, {"kind": "flight", "index": "0", "phone": "310 555 0100"}, {"kind": "hotel", "index": "-1", "phone": "310 555 0100"}):
        assert client.post("/trip/help/phone", data=data, follow_redirects=False).headers["location"] == "/trip/help?problem=phone"


def test_clearing_a_number_removes_the_call_button(client, at):
    imported(client)
    at(date(2026, 10, 17))
    client.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": ""})
    assert "No phone number yet" in client.get("/trip/help").text


def test_editors_fix_numbers_and_viewers_cannot(client, at):
    imported(client)
    at(date(2026, 10, 17))
    editor_mail, viewer_mail = addr("hed"), addr("hvi")
    invite(client, editor_mail, "editor"), invite(client, viewer_mail, "viewer")
    ed, vi = browser(client), browser(client)
    sign_in(ed, editor_mail), sign_in(vi, viewer_mail)
    assert "Fix the hotel number" in ed.get("/trip/help").text
    page = vi.get("/trip/help").text
    assert "Fix the hotel number" not in page and "Add the hotel number" not in page and "tel:+13105550100" in page  # a viewer can still call
    assert vi.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "310 555 0111"}, follow_redirects=False).status_code == 403
    assert ed.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "310 555 0111"}, follow_redirects=False).status_code == 303
    assert 'href="tel:3105550111"' in vi.get("/trip/help").text


# ---- the family's numbers -----------------------------------------------------------------------------------------------

def test_a_member_adds_their_number_on_the_family_page_and_it_shows_on_help_for_everyone(client, at):
    imported(client)
    at(date(2026, 10, 17))
    assert "Add your number" in client.get("/trip/help").text
    r = client.post("/family/phone", data={"phone": "+1 415 555 0142"}, follow_redirects=False)
    assert r.status_code == 303
    assert 'value="+1 415 555 0142"' in client.get("/family").text
    help_html = client.get("/trip/help").text
    assert 'href="tel:+14155550142"' in help_html and "Add your number" not in help_html
    mail = addr("hfam")
    invite(client, mail, "viewer")
    vi = browser(client)
    sign_in(vi, mail)
    assert vi.post("/family/phone", data={"phone": "415 555 0143"}, follow_redirects=False).status_code == 303  # a viewer keeps their own number
    both = client.get("/trip/help").text
    assert 'href="tel:+14155550142"' in both and 'href="tel:4155550143"' in both


def test_a_member_cannot_set_somebody_elses_number_and_a_bad_number_is_explained(client):
    imported(client)
    r = client.post("/family/phone", data={"phone": "nope"})
    assert r.status_code == 422 and "Enter a phone number" in r.text and 'value="nope"' in r.text
    assert client.post("/family/phone", data={"phone": ""}, follow_redirects=False).status_code == 303  # empty clears it


def test_phone_checks():
    assert phones.clean(" +1 (310) 555-0100 x22 ") == ("+1 (310) 555-0100 x22", "")
    assert phones.clean("")[0] == "" and phones.clean(None) == ("", "")
    assert phones.clean("12345")[1] and phones.clean("abc 1234567")[1] and phones.clean("1" * 31)[1]
    assert phones.tel("+1 (310) 555-0100 x22") == "+13105550100"
    assert phones.tel("310.555.0100") == "3105550100" and phones.tel("call the desk") == "" and phones.tel("") == ""


# ---- the car's phone through the template, the parser and the builder ------------------------------------------------------

def test_the_car_phone_round_trips_through_the_parser_the_document_and_the_builder():
    plan = ti.parse(TEMPLATE).plan
    assert plan.rental.phone == "+1 310 555 0199"
    again = ti.from_doc(ti.to_doc(plan))
    assert again.rental.phone == "+1 310 555 0199"
    draft = tb.from_plan(plan)
    assert draft["car"]["phone"] == "+1 310 555 0199"
    assert tb.build(draft).rental.phone == "+1 310 555 0199"


def test_the_car_phone_is_read_as_raw_text_and_limited():
    raw = ti.parse(TEMPLATE.replace('"+1 310 555 0199"', "0123456789"))
    assert raw.plan.rental.phone == "0123456789"
    with pytest.raises(ti.ImportProblem) as e:
        ti.parse(TEMPLATE.replace('"+1 310 555 0199"', '"' + "5" * 31 + '"'))
    assert "phone" in str(e.value.args).lower()


def test_an_older_stored_trip_without_a_car_phone_still_opens():
    doc = ti.to_doc(ti.parse(TEMPLATE).plan)
    del doc["car"]["phone"]
    assert ti.from_doc(doc).rental.phone == ""


def test_the_car_phone_shows_in_the_booking_detail():
    plan = ti.parse(TEMPLATE).plan
    spec = next(s for s in ti.block_specs(plan) if s.kind == "pickup")
    assert ("Phone", "+1 310 555 0199") in ti.detail_rows(spec, plan)[1]
