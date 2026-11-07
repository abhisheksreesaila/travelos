"""F-198 (4): bookings know where they live. Every booking in a trip says "Booked on <partner>" and has a "Change or cancel" button to the partner's own manage-booking page;
GitAway never handles a change. Also the per-booking partner and the tickets section of the trip template."""

import re
from datetime import datetime
from html import unescape

import pytest

from gitaway import session as ses, tripcal as cal, tripimport as ti
from gitaway.partners import manage
from tests.test_signin import person, sign_in

TRIP = """trip:
  title: Tahoe with the kids
  destination: Lake Tahoe
  start: 2026-12-19
  end: 2026-12-26
  booked_on: Expedia
travelers:
  - name: Ari
  - name: Sam
  - name: Kid 1
    age: 8
  - name: Kid 2
    age: 11
flights:
  - airline: Alaska Airlines
    number: AS 1480
    from: SFO
    to: RNO
    depart: 2026-12-19 08:00
    arrive: 2026-12-19 09:10
    confirmation: QWERTY
    booked_on: Aviasales
  - airline: United
    number: UA 5411
    from: RNO
    to: SFO
    depart: 2026-12-26 17:00
    arrive: 2026-12-26 18:15
hotels:
  - name: Lakeside Cabin
    address: 1 Lake Ave, South Lake Tahoe, CA 96150
    check_in: 2026-12-19 16:00
    check_out: 2026-12-26 10:00
    confirmation: "HMAB12CD34"
    booked_on: Airbnb
car:
  company: Enterprise
  pickup: RNO, 2026-12-19 10:00
  dropoff: RNO, 2026-12-26 15:00
  confirmation: "1234567890"
  car: Standard SUV
  booked_on: Enterprise
tickets:
  - name: Snowmobile tour
    place: Zephyr Cove, NV
    start: 2026-12-21 10:00
    end: 2026-12-21 12:00
    confirmation: GYG8XKQ2P
    booked_on: GetYourGuide
"""


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


# ---- the manage pages -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, site, url", [
    ("Expedia", "Expedia", "https://www.expedia.com/trips"),
    ("expedia.com", "Expedia", "https://www.expedia.com/trips"),
    ("Booking.com", "Booking.com", "https://secure.booking.com/mytrips.html"),
    ("Airbnb", "Airbnb", "https://www.airbnb.com/trips"),
    ("Vrbo", "Vrbo", "https://www.vrbo.com/trips"),
    ("HomeAway", "Vrbo", "https://www.vrbo.com/trips"),
    ("Klook", "Klook", "https://www.klook.com/bookings/"),
    ("GetYourGuide", "GetYourGuide", "https://www.getyourguide.com/"),
    ("Aviasales", "Aviasales", "https://www.aviasales.com/faq/i-want-to-return-or-exchange-my-ticket-how-do-i-do-that"),
    ("Enterprise Rent-A-Car", "Enterprise", "https://www.enterprise.com/en/reserve/view-modify-cancel.html"),
    ("Hertz", "Hertz", "https://www.hertz.com/us/en"),
    ("Avis", "Avis", "https://www.avis.com/en/reservation/view-modify-cancel"),
    ("Budget", "Budget", "https://www.budget.com/en/reservation/view-modify-cancel"),
    ("National Car Rental", "National", "https://www.nationalcar.com/en/reserve/view-modify-cancel.html"),
    ("Alamo", "Alamo", "https://www.alamo.com/en/reserve/view-modify-cancel.html"),
    ("Sixt", "Sixt", "https://www.sixt.com/account/#/manage-booking"),
    ("Alaska Airlines", "Alaska Airlines", "https://www.alaskaair.com/booking/reservation-lookup"),
    ("United", "United", "https://www.united.com/en/us/manageres/mytrips"),
    ("Delta Air Lines", "Delta", "https://www.delta.com/my-trips/search"),
    ("Southwest", "Southwest", "https://www.southwest.com/air/manage-reservation/"),
    ("JetBlue", "JetBlue", "https://www.jetblue.com/manage-trips"),
])
def test_each_partner_has_its_own_manage_page(name, site, url):
    m = manage.find(name)
    assert (m.name, m.url) == (site, url)
    assert m.url.startswith("https://")


def test_unknown_partners_have_no_button():
    assert manage.find("elsewhere") is None and manage.find("") is None and manage.find("my aunt") is None
    assert manage.find("Expediaa") is None      # whole words only


def test_a_flight_from_aviasales_is_changed_with_the_airline_and_a_car_with_its_company():
    leg = ti.Leg("Alaska Airlines", "AS 1", "SFO", "RNO", datetime(2026, 12, 19, 8), datetime(2026, 12, 19, 9))
    assert manage.for_booking("leg", leg, "Aviasales") == ("Aviasales", manage.SITES["alaska"])
    odd = ti.Leg("Tiny Air", "TA 1", "SFO", "RNO", datetime(2026, 12, 19, 8), datetime(2026, 12, 19, 9))
    assert manage.for_booking("leg", odd, "Aviasales") == ("Aviasales", manage.SITES["aviasales"])
    car = ti.Rental("Hertz", "RNO", datetime(2026, 12, 19, 10), "RNO", datetime(2026, 12, 26, 10))
    assert manage.for_booking("pickup", car, "") == ("Hertz", manage.SITES["hertz"])
    assert manage.for_booking("pickup", car, "Expedia") == ("Expedia", manage.SITES["expedia"])      # booked through Expedia: changed there


# ---- the template keeps each booking's partner, and tickets ---------------------------------------------------------

def test_the_template_reads_each_bookings_partner_and_tickets():
    plan = ti.parse(TRIP).plan
    assert [l.booked_on for l in plan.legs] == ["Aviasales", ""] and plan.hotels[0].booked_on == "Airbnb" and plan.rental.booked_on == "Enterprise"
    t = plan.tickets[0]
    assert (t.name, t.place, t.start, t.end, t.confirmation, t.booked_on) == ("Snowmobile tour", "Zephyr Cove, NV", datetime(2026, 12, 21, 10), datetime(2026, 12, 21, 12), "GYG8XKQ2P", "GetYourGuide")
    assert ti.from_doc(ti.to_doc(plan)) == plan


def test_a_ticket_alone_is_a_trip_and_its_checks_say_what_is_wrong():
    only = TRIP.split("flights:")[0] + "tickets:" + TRIP.split("tickets:")[1]
    assert ti.parse(only).plan.tickets
    with pytest.raises(ti.ImportProblem) as e:
        ti.parse(only.replace("2026-12-21 10:00", "2027-01-05 10:00").replace("2026-12-21 12:00", "2027-01-05 12:00"))
    assert "outside your trip dates" in " ".join(e.value.errors)
    with pytest.raises(ti.ImportProblem) as e:
        ti.parse(only.replace("end: 2026-12-21 12:00", "end: 2026-12-21 09:00"))
    assert "has to end after it starts" in " ".join(e.value.errors)
    no_end = ti.parse(only.replace("    end: 2026-12-21 12:00\n", "")).plan.tickets[0]
    assert no_end.end == datetime(2026, 12, 21, 12)       # two hours when no end is given


def test_a_trip_rebuilt_in_the_guided_builder_keeps_partners_and_tickets():
    from gitaway import tripbuild
    plan = ti.parse(TRIP).plan
    again = tripbuild.build(tripbuild.load(tripbuild.dump(tripbuild.from_plan(plan))))
    assert again.tickets == plan.tickets and again.hotels[0].booked_on == "Airbnb" and again.legs[0].booked_on == "Aviasales" and again.rental.booked_on == "Enterprise"
    forged = tripbuild.from_plan(plan)
    forged["tickets"][0]["start"] = "not a time"
    assert tripbuild.build(tripbuild.load(tripbuild.dump(forged))).tickets == ()


# ---- on the trip -----------------------------------------------------------------------------------------------------

def imported(client):
    sign_in(client, "ari")
    assert client.post("/trips/import/save", data={"text": TRIP}, follow_redirects=False).status_code == 303


def test_every_block_says_where_it_was_booked(client):
    imported(client)
    b = ses.booking(person())
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip("", b))}
    assert blocks["b-out"].tag == "Booked on Aviasales" and blocks["b-back"].tag == "Booked on Expedia"      # its own partner, else the trip's
    assert blocks["b-in"].tag == "Booked on Airbnb" and blocks["b-car-pick"].tag == "Booked on Enterprise"
    tix = blocks["b-tix1"]
    assert (tix.day, tix.start, tix.end, tix.title, tix.icon, tix.tag) == (2, 600, 720, "Snowmobile tour", "ticket", "Booked on GetYourGuide")


def test_a_trip_booked_in_many_places_says_elsewhere_for_a_booking_it_cannot_place():
    plan = ti.parse(TRIP.replace("booked_on: Expedia", "booked_on: Expedia, Klook")).plan
    assert cal.booked_on(plan, plan.legs[1]) == "" and cal.booked_tag(plan, plan.legs[1]) == "Booked elsewhere · Expedia, Klook"
    assert cal.booked_on(plan, plan.hotels[0]) == "Airbnb"


@pytest.mark.parametrize("block, partner, url", [
    ("b-in", "Airbnb", "https://www.airbnb.com/trips"),
    ("b-out", "Aviasales", "https://www.alaskaair.com/booking/reservation-lookup"),
    ("b-back", "Expedia", "https://www.expedia.com/trips"),
    ("b-car-pick", "Enterprise", "https://www.enterprise.com/en/reserve/view-modify-cancel.html"),
    ("b-tix1", "GetYourGuide", "https://www.getyourguide.com/"),
])
def test_each_bookings_sheet_has_change_or_cancel_at_the_partner(client, block, partner, url):
    imported(client)
    day = {"b-in": 0, "b-out": 0, "b-back": 7, "b-car-pick": 0, "b-tix1": 2}[block]
    html = client.get(f"/trip/canvas?day={day}&booked={block}").text
    where = re.search(r'<div id="bk-where" class="bk-where">(.*?)</div>', html, re.S)
    assert where, block
    assert f"Booked on {partner}" in words(where.group(1))
    link = re.search(r'<a[^>]*class="tp-btn tp-btn-white bk-manage"[^>]*>', where.group(1)).group(0)
    assert f"Change or cancel on {manage.find(partner if block != 'b-out' else 'Alaska').name}" in link
    assert f'href="{url}"' in link and 'target="_blank"' in link and 'rel="noopener"' in link and "Change or cancel" in where.group(1)


def test_the_details_page_has_a_change_or_cancel_for_every_booking(client):
    imported(client)
    html = client.get("/trip/details").text
    assert html.count('class="tp-btn tp-btn-white bk-manage"') == 4      # the Aviasales flight (changed with Alaska), the cabin, the car, the snowmobile
    head = re.search(r'<div[^>]*id="ti-where"[^>]*>(.*?)</div>', html, re.S).group(1)
    assert "Booked on Expedia" in words(head) and 'href="https://www.expedia.com/trips"' in head      # the flight home was booked where the trip was: said once, at the top
    assert "Tickets and activities" in words(html) and "Snowmobile tour" in words(html)
