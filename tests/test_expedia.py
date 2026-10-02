"""F-056: an Expedia itinerary (pasted, or its PDF) becomes the trip template, then goes through the normal reader."""

import re
from datetime import datetime
from html import unescape

import pytest
import yaml

from gitaway import expedia, session as ses, tripimport as ti
from tests.expedia_samples import CAR_PLAIN, FOOTER, LAYOUT, PLAIN, PYPDF, STAY1_PLAIN, STAY2_PLAIN, pdf_of
from tests.test_roles import crew  # noqa: F401 - the fixture
from tests.test_signin import person, sign_in

ORDERS = pytest.mark.parametrize("text", [PLAIN, LAYOUT, PYPDF], ids=["plain", "layout", "pypdf"])


def doc(text):
    return yaml.safe_load(expedia.convert(text).yaml)


def hidden_text(html):
    """The preview's hidden `text` field (the generated template), unescaped."""
    tag = next(t for t in re.findall(r"<input[^>]*>", html) if 'name="text"' in t and 'type="hidden"' in t)
    m = re.search(r'value=(?:"([^"]*)"|\'([^\']*)\')', tag)
    return unescape(m.group(1) if m.group(1) is not None else m.group(2))


def visible(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


# ---- the converter ----------------------------------------------------------------------------------------------------

@ORDERS
def test_two_stays_and_a_car_in_any_text_order(text):
    c = expedia.convert(text)
    d = yaml.safe_load(c.yaml)
    assert (c.stays, c.cars) == (2, 1)
    assert d["trip"] == {"title": "Valencia trip", "destination": "Valencia, CA", "start": "2026-10-04", "end": "2026-10-10", "booked_on": "Expedia"}
    h1, h2 = d["hotels"]
    assert h1 == {"name": "Maple Grove Inn & Suites", "address": "1 Example Road, Valencia, CA, 91355", "check_in": "2026-10-04 15:00", "check_out": "2026-10-06 11:00",
                  "confirmation": "055512345", "room": "Standard Room, 2 Queen Beds, Non Smoking, Refrigerator & Microwave"}
    assert (h2["name"], h2["check_in"], h2["check_out"], h2["room"]) == ("Sample Suites Burbank Airport", "2026-10-06 15:00", "2026-10-07 11:00", "Studio, 2 Double Beds, Non Smoking")
    assert d["car"] == {"company": "Avis", "pickup": "BUR, 2026-10-04 18:30", "dropoff": "BUR, 2026-10-10 11:30", "confirmation": "Q123X456789", "car": "Fullsize, Nissan Altima or similar"}
    assert c.warnings == ("Expedia doesn't give children's ages, so each child is set to 10; change the ages.",)


@ORDERS
def test_the_party_is_the_largest_across_bookings_with_the_named_person_first(text):
    names = [(t["name"], t.get("age")) for t in doc(text)["travelers"]]
    # the booker (proper-cased), the car's driver in the next adult slot, one more adult, then the child
    assert names == [("Jordan Testerson", None), ("Casey Driverson", None), ("Adult 3", None), ("Child 1", 10)]


@ORDERS
def test_it_goes_through_the_normal_reader(text):
    parsed = ti.parse(expedia.convert(text).yaml)
    plan = parsed.plan
    assert (plan.start.isoformat(), plan.end.isoformat(), plan.booked_on) == ("2026-10-04", "2026-10-10", "Expedia")
    assert len(plan.hotels) == 2 and plan.rental.pickup_place == "BUR" and plan.party_text == "3 adults, 1 kid"
    assert [h.confirmation for h in plan.hotels] == ["055512345", "8754000011"]


def test_confirmation_numbers_are_kept_exactly_and_the_hash_dropped():
    d = doc(PLAIN)
    assert d["car"]["confirmation"] == "Q123X456789" and "#" not in expedia.convert(PLAIN).yaml.replace("# Read from", "")
    assert d["hotels"][0]["confirmation"] == "055512345"  # a leading zero survives (quoted)
    assert 'confirmation: "055512345"' in expedia.convert(PLAIN).yaml


def test_no_prices_card_digits_itinerary_numbers_or_support_text_in_the_output():
    out = expedia.convert(PLAIN).yaml
    for leak in ("$", "4242", "Visa", "Paid", "70000000000001", "Expedia support", "555-010", "Important", "liability", "Mention your", "VIP", "Silver", "Hours of operation"):
        assert leak not in out, leak


def test_a_stay_only_itinerary():
    c = expedia.convert(STAY1_PLAIN + "\x0c" + FOOTER)
    d = yaml.safe_load(c.yaml)
    assert (c.stays, c.cars) == (1, 0) and "car" not in d and len(d["hotels"]) == 1
    assert [t["name"] for t in d["travelers"]] == ["Jordan Testerson", "Adult 2", "Adult 3", "Child 1"]


def test_a_car_only_itinerary():
    c = expedia.convert(CAR_PLAIN + FOOTER)
    d = yaml.safe_load(c.yaml)
    assert (c.stays, c.cars) == (0, 1) and "hotels" not in d
    assert [t["name"] for t in d["travelers"]] == ["Casey Driverson"]
    assert d["trip"]["destination"] == "Burbank" and ti.parse(c.yaml).plan.rental.company == "Avis"


def test_a_missing_checkout_time_is_named_and_a_default_used():
    text = STAY2_PLAIN.replace("\n\n3 PM\n\n11 AM\n", "\n\n3 PM\n")
    c = expedia.convert(STAY1_PLAIN + text)
    assert "We couldn't read the check-out time for Stay in Burbank; 11:00 was used." in c.warnings
    assert not any("Valencia" in w for w in c.warnings)
    assert yaml.safe_load(c.yaml)["hotels"][1]["check_out"] == "2026-10-07 11:00"


def test_a_missing_checkin_time_falls_back_on_the_starts_at_line_and_pypdf_order_reads_the_one_time_it_has():
    plain = STAY2_PLAIN.replace("\n\n3 PM\n\n11 AM\n", "\n")
    assert yaml.safe_load(expedia.convert(plain).yaml)["hotels"][0]["check_in"] == "2026-10-06 15:00"  # from "Check-in time starts at 3 PM"
    pypdf = STAY2_PLAIN.replace("Check in\n\nCheck out\n\nTue, Oct 6\n\nWed, Oct 7\n\n3 PM\n\n11 AM\n", "Check in\nTue, Oct 6\nCheck out\nWed, Oct 7\n11 AM\n").replace("Check-in time starts at 3 PM\n", "")
    c = expedia.convert(pypdf)
    assert any("check-in time for Stay in Burbank" in w for w in c.warnings) and yaml.safe_load(c.yaml)["hotels"][0]["check_out"] == "2026-10-07 11:00"


def test_a_range_that_crosses_new_year():
    text = PLAIN.replace("Oct 4, 2026 - Oct 6, 2026", "Dec 30, 2026 - Jan 2, 2027").replace("Sun, Oct 4", "Wed, Dec 30").replace("Tue, Oct 6\n\nWed, Oct 7", "Sat, Jan 2\n\nSun, Jan 3") \
        .replace("Oct 6, 2026 - Oct 7, 2026", "Jan 2, 2027 - Jan 3, 2027").replace("Oct 4, 2026 - Oct 10, 2026", "Dec 30, 2026 - Jan 5, 2027").replace("Sat, Oct 10", "Tue, Jan 5")
    text = text.replace("Check out\n\nWed, Dec 30\n\nSat, Jan 2", "Check out\n\nWed, Dec 30\n\nSat, Jan 2")
    d = doc(text)
    assert d["hotels"][0]["check_in"].startswith("2026-12-30") and d["hotels"][0]["check_out"].startswith("2027-01-02")
    assert d["trip"]["end"] == "2027-01-05"


def test_times_in_every_spelling():
    for token, want in (("6:30pm", "18:30"), ("11:30am", "11:30"), ("3 PM", "15:00"), ("11:00 AM", "11:00"), ("11 AM", "11:00"), ("12 AM", "00:00"), ("12 PM", "12:00")):
        assert expedia._clock(token).strftime("%H:%M") == want


def test_a_car_driving_somewhere_other_than_an_airport_keeps_the_address_and_a_drop_off_place_is_read():
    text = CAR_PLAIN.replace("1 Sample Way Hollywood-Burbank Airport, 100 Test Road 1st Floor", "9 Elm Street").replace("Hours of operation", "Drop-off location\nAvis\n5 Oak Street\nGlendale 91201\n\nHours of operation")
    car = doc(text + FOOTER)["car"]
    assert car["pickup"].startswith("9 Elm Street, Burbank 91505,") and car["dropoff"].startswith("5 Oak Street, Glendale 91201,")


def test_a_flight_section_is_named_not_guessed():
    c = expedia.convert("Flight to Los Angeles\nOct 4, 2026 - Oct 4, 2026\n\nSome Air 12\n\n" + PLAIN)
    assert "We found a flight but couldn't read it yet; add it under flights:" in c.warnings
    assert "flights" not in yaml.safe_load(c.yaml)


def test_the_text_is_recognised_only_when_it_is_an_itinerary():
    assert expedia.looks_like_expedia(PLAIN) and expedia.looks_like_expedia(LAYOUT) and expedia.looks_like_expedia(PYPDF)
    assert not expedia.looks_like_expedia("") and not expedia.looks_like_expedia("trip:\n  title: x\n")
    assert not expedia.looks_like_expedia("Stay in the loop\nOur newsletter")


# ---- the PDF ----------------------------------------------------------------------------------------------------------

def test_the_text_of_a_pdf_reads_back_through_the_converter():
    c = expedia.convert(expedia.pdf_text(pdf_of(PLAIN)))
    assert (c.stays, c.cars) == (2, 1)


@pytest.mark.parametrize("data", [b"", b"hello", b"%PDF-1.4 garbage"])
def test_not_a_pdf_is_a_friendly_error(data):
    with pytest.raises(ValueError) as e:
        expedia.pdf_text(data)
    assert "PDF" in str(e.value)


# ---- the routes -------------------------------------------------------------------------------------------------------

def test_pasting_an_itinerary_previews_the_trip_and_saves_nothing(client):
    sign_in(client)
    r = client.post("/trips/import", data={"text": PLAIN})
    assert r.status_code == 200
    text = visible(r.text)
    for expected in ("Valencia trip", "Oct 4 – 10", "Expedia", "3 adults, 1 kid", "Maple Grove Inn", "Sample Suites Burbank Airport", "Avis", "BUR", "Confirmation 055512345", "Confirmation Q123X456789",
                     "Read from an Expedia itinerary", "Expedia doesn't give children's ages"):
        assert expected in text, expected
    assert ses.trips(person()) == []
    hidden = hidden_text(r.text)
    assert hidden.startswith("# Read from an Expedia itinerary") and yaml.safe_load(hidden)["hotels"]  # "Change something" edits the YAML
    assert "$" not in r.text and "4242" not in r.text


def test_the_preview_names_what_it_could_not_read(client):
    sign_in(client)
    text = STAY1_PLAIN + STAY2_PLAIN.replace("\n\n3 PM\n\n11 AM\n", "\n\n3 PM\n")
    assert "We couldn't read the check-out time for Stay in Burbank" in visible(client.post("/trips/import", data={"text": text}).text)


def test_the_generated_yaml_saves_like_any_template(client):
    sign_in(client)
    html = client.post("/trips/import", data={"text": PLAIN}).text
    generated = hidden_text(html)
    assert client.post("/trips/import/save", data={"text": generated}, follow_redirects=False).status_code == 303
    saved = ses.trips(person())
    assert len(saved) == 1
    assert saved[0].source == "imported" and saved[0].title == "Valencia trip" and "3 adults, 1 kid" in saved[0].detail
    html = client.get("/trip/details").text
    assert "Q123X456789" in html and "055512345" in html and "Burbank" in html


def test_uploading_the_pdf_fills_the_preview(client):
    sign_in(client)
    r = client.post("/trips/import", files={"file": ("itinerary.pdf", pdf_of(PLAIN), "application/pdf")})
    assert r.status_code == 200 and "Maple Grove Inn" in visible(r.text) and "Avis" in visible(r.text)
    assert ses.trips(person()) == []


def test_a_pasted_text_beats_no_file_and_a_non_pdf_file_is_a_friendly_error(client):
    sign_in(client)
    r = client.post("/trips/import", files={"file": ("notes.txt", b"just words", "text/plain")})
    assert r.status_code == 422 and "not a PDF" in visible(r.text) and "<textarea" in r.text
    big = client.post("/trips/import", files={"file": ("big.pdf", b"%PDF-1.4" + b"0" * 5_100_000, "application/pdf")})
    assert big.status_code == 422 and "too large" in visible(big.text)


def test_the_form_takes_a_file(client):
    sign_in(client)
    html = client.get("/trips/import").text
    assert 'enctype="multipart/form-data"' in html and 'type="file"' in html and 'accept=".pdf,application/pdf"' in html and 'name="file"' in html


def test_something_that_is_not_an_itinerary_still_goes_through_the_template_reader(client):
    sign_in(client)
    r = client.post("/trips/import", data={"text": "trip:\n  title: x\n"})
    assert r.status_code == 422 and "Line 1:" in visible(r.text) and 'id="ti-expedia"' not in r.text


def test_a_viewer_cannot_upload_an_itinerary_but_an_editor_can(crew):
    _, editor, viewer = crew
    files = {"file": ("itinerary.pdf", pdf_of(PLAIN), "application/pdf")}
    assert viewer.post("/trips/import", files=files, follow_redirects=False).status_code == 403
    assert editor.post("/trips/import", files=files, follow_redirects=False).status_code == 200
