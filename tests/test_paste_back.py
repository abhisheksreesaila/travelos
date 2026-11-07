"""F-198 (5): paste-back. A pasted confirmation from Booking.com, Airbnb, Vrbo, GetYourGuide, Klook or a car-rental company lands as booked blocks with its partner recorded,
from the import page and from the Ask box. The samples are synthetic (tests/confirmation_samples.py)."""

import re
from datetime import datetime
from html import unescape

import pytest

from gitaway import confirmations as cf, session as ses, tripcal as cal, tripimport as ti
from tests.confirmation_samples import AIRBNB, ALL, BOOKING, CAR, GETYOURGUIDE, KLOOK, VRBO
from tests.test_booking_lanes import TAHOE_TRIP
from tests.test_signin import person, sign_in


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


# ---- reading each partner's confirmation ---------------------------------------------------------------------------

def test_booking_com():
    b = cf.read(BOOKING)
    h = b.item
    assert (b.partner, b.kind, b.destination, b.adults, b.kids) == ("Booking.com", "stay", "South Lake Tahoe, CA", 2, (8, 11))
    assert (h.name, h.address, h.check_in, h.check_out, h.confirmation, h.booked_on) == (
        "Lakeside Lodge Tahoe", "123 Lake Tahoe Blvd, South Lake Tahoe, CA 96150", datetime(2026, 12, 19, 16), datetime(2026, 12, 26, 10), "4021.889.317", "Booking.com")


def test_airbnb():
    b = cf.read(AIRBNB)
    h = b.item
    assert (b.partner, b.kind, b.destination, b.adults, b.kids) == ("Airbnb", "stay", "South Lake Tahoe, CA", 2, (None, None))
    assert (h.name, h.address, h.check_in, h.check_out, h.confirmation, h.booked_on) == (
        "Cozy A-Frame Cabin near Heavenly", "45 Pine Ridge Rd, South Lake Tahoe, CA 96150", datetime(2026, 12, 19, 16), datetime(2026, 12, 26, 10), "HMAB12CD34", "Airbnb")


def test_vrbo():
    b = cf.read(VRBO)
    h = b.item
    assert (b.partner, b.destination, h.name, h.address, h.check_in, h.check_out, h.confirmation, h.booked_on) == (
        "Vrbo", "Tahoe City, CA", "Cedar Ridge Cabin with Hot Tub", "88 Cedar Ridge Dr, Tahoe City, CA 96145", datetime(2026, 12, 19, 16), datetime(2026, 12, 26, 10), "HA-7Q2K9P", "Vrbo")


def test_getyourguide():
    b = cf.read(GETYOURGUIDE)
    t = b.item
    assert (b.partner, b.kind, b.destination) == ("GetYourGuide", "ticket", "Zephyr Cove, NV")
    assert (t.name, t.place, t.start, t.end, t.confirmation, t.booked_on) == (
        "Lake Tahoe: Guided Snowmobile Tour with Sierra Views", "Zephyr Cove Resort, 760 US-50, Zephyr Cove, NV 89448", datetime(2026, 12, 21, 10), datetime(2026, 12, 21, 12), "GYG8XKQ2P", "GetYourGuide")


def test_klook():
    b = cf.read(KLOOK)
    t = b.item
    assert (b.partner, b.kind, t.name, t.place, t.start, t.end, t.confirmation, t.booked_on) == (
        "Klook", "ticket", "Lake Tahoe Snowshoe Rental and Self-Guided Tour", "Tahoe City, CA", datetime(2026, 12, 22, 9), datetime(2026, 12, 22, 11), "KLK-55821934", "Klook")


def test_a_car_rental():
    b = cf.read(CAR)
    c = b.item
    assert (b.partner, b.kind, c.company, c.pickup_place, c.pickup, c.dropoff_place, c.dropoff, c.confirmation, c.car, c.booked_on) == (
        "Enterprise", "car", "Enterprise", "RNO", datetime(2026, 12, 19, 10), "RNO", datetime(2026, 12, 26, 15), "1234567890", "Standard SUV", "Enterprise")


@pytest.mark.parametrize("name", list(ALL))
def test_no_price_pin_or_card_digits_are_ever_copied(name):
    out = cf.convert(ALL[name]).yaml
    for secret in ("$", "US$", "USD", "4242", "7741", "4471", "2,940", "1,060", "612.40", "PIN"):
        assert secret not in out, (name, secret)


@pytest.mark.parametrize("name", list(ALL))
def test_each_one_is_a_template_the_normal_reader_accepts(name):
    converted = cf.convert(ALL[name])
    plan = ti.parse(converted.yaml).plan
    assert plan.booked_on == converted.partner and plan.start.isoformat() >= "2026-12-19"
    items = [*plan.hotels, *plan.tickets, *([plan.rental] if plan.rental else [])]
    assert len(items) == 1 and items[0].booked_on == converted.partner


def test_ages_given_are_kept_and_missing_ones_are_said():
    assert [t.age for t in cf.plan_for(cf.read(BOOKING))[0].travelers] == [None, None, 8, 11]
    plan, warnings, _ = cf.plan_for(cf.read(AIRBNB))
    assert [t.age for t in plan.travelers] == [None, None, cf.CHILD_AGE, cf.CHILD_AGE] and any("doesn't give children's ages" in w for w in warnings)


def test_text_that_is_no_confirmation_is_not_read():
    for text in ("", "Move lunch to 1:30", "Booking.com is a website", "Hertz is a car company. " * 3, None):
        assert cf.read(text) is None
    from tests.expedia_samples import PLAIN as ITINERARY
    assert cf.read(ITINERARY) is None and cf.partner_of(ITINERARY) == "Expedia"
    assert cf.partner_of(AIRBNB) == "Airbnb"


def test_a_confirmation_inside_the_open_trip_is_added_to_it():
    base = ti.parse(TAHOE_TRIP).plan
    plan, warnings, merged = cf.plan_for(cf.read(GETYOURGUIDE), base)
    assert merged and plan.title == base.title and plan.start == base.start and plan.hotels == base.hotels and plan.travelers == base.travelers
    assert [t.booked_on for t in plan.tickets] == ["GetYourGuide"] and "Added to Tahoe with the kids." in warnings
    again, _, _ = cf.plan_for(cf.read(GETYOURGUIDE), plan)
    assert len(again.tickets) == 1       # the same ticket pasted twice is one ticket


def test_a_new_stay_on_the_same_nights_replaces_the_old_one_and_says_so():
    base = ti.parse(TAHOE_TRIP).plan
    plan, warnings, _ = cf.plan_for(cf.read(AIRBNB), base)
    assert [h.name for h in plan.hotels] == ["Cozy A-Frame Cabin near Heavenly"] and "It replaces Lakeside Cabin on the same nights." in warnings


def test_a_confirmation_for_other_dates_is_a_trip_of_its_own():
    base = ti.parse(TAHOE_TRIP.replace("2026-12-19", "2027-02-10").replace("2026-12-26", "2027-02-14").replace("2026-12-19 16:00", "2027-02-10 16:00")).plan
    plan, _, merged = cf.plan_for(cf.read(BOOKING), base)
    assert not merged and plan.title == "South Lake Tahoe trip" and plan.destination == "South Lake Tahoe, CA"


# ---- through the import page and the Ask box --------------------------------------------------------------------------

def hidden(html, name):
    m = re.search(rf"""name="{name}" value=(?:"([^"]*)"|'([^']*)')""", html)
    return unescape(m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def import_tahoe(client):
    sign_in(client, "ari")
    assert client.post("/trips/import/save", data={"text": TAHOE_TRIP}, follow_redirects=False).status_code == 303


def test_pasting_an_airbnb_confirmation_into_the_import_page_lands_it_in_the_open_trip(client):
    import_tahoe(client)
    r = client.post("/trips/import", data={"text": AIRBNB})
    assert r.status_code == 200
    text = words(r.text)
    assert "Read from your Airbnb confirmation." in text and "Added to Tahoe with the kids." in text and "Cozy A-Frame Cabin near Heavenly" in text
    yaml, replace_id = hidden(r.text, "text"), hidden(r.text, "replace")          # the preview offers to correct the open trip in place
    assert client.post("/trips/import/save", data={"text": yaml, "replace": replace_id}, follow_redirects=False).status_code == 303
    b = ses.booking(person())
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip("", b))}
    assert blocks["b-in"].title == "Check in · Cozy A-Frame Cabin near Heavenly" and blocks["b-in"].tag == "Booked on Airbnb"
    assert len(ses.trips(person())) == 1


@pytest.mark.parametrize("name, block, tag", [("getyourguide", "b-tix1", "Booked on GetYourGuide"), ("klook", "b-tix1", "Booked on Klook"),
                                              ("car", "b-car-pick", "Booked on Enterprise"), ("vrbo", "b-in", "Booked on Vrbo"), ("booking", "b-in", "Booked on Booking.com")])
def test_every_partner_lands_as_a_booked_block(client, name, block, tag):
    import_tahoe(client)
    r = client.post("/trips/import", data={"text": ALL[name]})
    yaml, replace_id = hidden(r.text, "text"), hidden(r.text, "replace")
    assert replace_id and client.post("/trips/import/save", data={"text": yaml, "replace": replace_id}, follow_redirects=False).status_code == 303
    b = ses.booking(person())
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip("", b))}
    assert blocks[block].tag == tag and blocks[block].locked


def test_the_ask_box_hands_a_pasted_confirmation_to_the_import(client):
    """The structure the Ask scripts need (the real taps are tests_browser/test_paste_handoff.py): the page is the Ask tab with ask.css; a sheet fragment is #ak-sheet-body; the form navigates."""
    import_tahoe(client)
    r = client.post("/trip/ask/propose", data={"text": BOOKING})
    assert r.status_code == 200 and "/assets/css/ask.css" in r.text and "This looks like a Booking.com confirmation" in words(r.text)
    form = re.search(r'<form[^>]*action="/trips/import"[^>]*>(.*?)</form>', r.text, re.S)
    assert form and 'data-navigate="1"' in form.group(0) and "Lakeside Lodge Tahoe" in unescape(form.group(1))
    sheet = client.post("/trip/ask/propose", data={"text": GETYOURGUIDE}, headers={"X-Ask": "1"})
    assert sheet.status_code == 200 and sheet.text.startswith('<div id="ak-sheet-body">') and "This looks like a GetYourGuide confirmation" in words(sheet.text)


def test_a_plan_written_as_the_template_reads_back_the_same():
    from tests.test_booking_manage import TRIP
    plan = ti.parse(TRIP).plan
    assert ti.parse(ti.to_yaml(plan)).plan == plan
    tricky = ti.parse(TRIP.replace('"HMAB12CD34"', '"0012"').replace("name: Lakeside Cabin", """name: 'Cabin "Yes": no'""")).plan
    assert tricky.hotels[0].name == 'Cabin "Yes": no' and tricky.hotels[0].confirmation == "0012"
    assert ti.parse(ti.to_yaml(tricky)).plan == tricky


def test_a_huge_or_hostile_paste_is_read_quickly():
    import time as clock
    text = "Booking.com\n" + ("Check-in " + "Mon, " * 2000 + "\n") * 20 + "a" * 50_000
    began = clock.monotonic()
    assert cf.read(text) is None
    assert clock.monotonic() - began < 2
