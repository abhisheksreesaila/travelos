"""F-033: any mix of flight, stay and car through the URL, the ledger, the pay sheet, the booking and the calendar."""
import html as htmllib
import json
import re
from urllib.parse import quote as q

import pytest

from gitaway import catalog, session as ses, tripcal as cal
from gitaway.pages import plan
from tests.test_signin import session_data, sign_in

SAMPLE = "f=f1&h=h1&c=c1"
NO_CAR = "f=f1&h=h1&c=none"
STAY_ONLY = "f=none&h=h1&c=none"
FLIGHT_ONLY = "f=f1&h=none&c=none"
NOTHING = "f=none&h=none&c=none"


def data_of(html):
    return json.loads(re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', html, re.S).group(1))


def bar(client, url):
    h = client.get(url).text
    return h[h.index('class="ws-bar"'):h.index('id="ws-grid"')]


def pane(html, key):
    return htmllib.unescape(re.search(r'<section[^>]*data-pane="%s".*?</section>' % key, html, re.S).group(0))


def total(html):
    return re.search(r'id="ws-total"[^>]*>([^<]+)<', html).group(1)


# ---- URL and validation --------------------------------------------------------------------------------------------

def test_none_skips_a_lane_and_nothing_else_does():
    assert plan.resolve_pick("none", "none", "none") == (None, None, None)
    assert plan.resolve_pick("none", "h2", "c2") == (None, "h2", "c2")
    for bad in ("None", "NONE", " none", "no", "", None, "f9", "h1"):  # only the exact word skips; anything else is a bad id and gets the default
        assert plan.resolve_pick(bad, "h1", "c1")[0] == "f1", bad
    assert plan.resolve_pick("f1", "h1", "c3") == ("f1", "h1", None)  # the old "No car" link is the skip now
    assert plan.resolve_pick("f1", "c3", "c1")[1] == "h1"  # c3 is only ever a car


def test_urls_spell_a_skipped_lane_as_none_and_round_trip():
    assert plan.plan_path(None, "h1", None) == "/plan?f=none&h=h1&c=none"
    assert plan.pay_path("f1", None, "c2") == "/plan/pay?f=f1&h=none&c=c2"
    st = catalog.stay_pick("h1", "ok2", "bf")
    assert plan.plan_path(None, "h1", None, st) == "/plan?f=none&h=h1&c=none&rooms=ok2&add=bf"
    assert plan.plan_path("f1", None, None, None, catalog.SAMPLE_TRIP, catalog.flight_pick("f1", "main", "2")) == "/plan?f=f1&h=none&c=none&fare=main&bags=2"
    for lane, picks in (("a", (None, "h1", None)), ("b", ("f1", None, "c1")), ("c", (None, None, "c2"))):
        url = plan.plan_path(*picks)
        qs = dict(p.split("=") for p in url.split("?")[1].split("&"))
        assert plan.resolve_pick(qs["f"], qs["h"], qs["c"]) == picks


def test_the_workspace_reads_skips_from_the_url_on_reload(client):
    h = client.get(f"/plan?{STAY_ONLY}").text
    assert data_of(h)["pick"]["f"] == "none" and data_of(h)["pick"]["c"] == "none"
    assert data_of(h)["base"] == "/plan?f=none&h=h1&c=none"
    assert total(h) == catalog.money(catalog.quote(None, "h1", None).total_cents)


def test_bad_ids_never_skip_and_a_stay_skip_ignores_room_params(client):
    assert total(client.get("/plan?f=zzz&h=bogus&c=bogus").text) == "$3,088"
    h = client.get("/plan?f=f1&h=none&c=c1&rooms=ok2&add=bf").text
    assert total(h) == catalog.money(catalog.quote("f1", None, "c1").total_cents)
    assert data_of(h)["base"] == "/plan?f=f1&h=none&c=c1"  # the room code is dropped with the stay


def test_the_old_no_car_link_means_no_car(client):
    h = client.get("/plan?f=f1&h=h1&c=c3").text
    assert data_of(h)["pick"]["c"] == "none" and "Uber and Lyft from LAX" in h


def test_remembered_plan_keeps_the_skips(client):
    sign_in(client)
    client.get(f"/plan?{STAY_ONLY}")
    assert session_data(client)["plan"]["ari"] == "f=none&h=h1&c=none"
    assert "f=none&amp;h=h1&amp;c=none" in client.get("/start").text


# ---- the slim ledger line and the popover --------------------------------------------------------------------------

@pytest.mark.parametrize("url,lanes", [(SAMPLE, ["flight", "stay", "car"]), (NO_CAR, ["flight", "stay", "rides"]), (STAY_ONLY, ["stay"]),
                                       (FLIGHT_ONLY, ["flight", "rides"]), ("f=none&h=none&c=c2", ["car"]), ("f=f2&h=none&c=c2", ["flight", "car"]),
                                       ("f=none&h=h3&c=c1", ["stay", "car"])])
def test_the_line_and_popover_have_one_item_per_picked_lane_and_no_zero_lines(client, url, lanes):
    html = bar(client, "/plan?" + url)
    assert re.findall(r'data-line-price="(\w+)"', html) == lanes
    assert re.findall(r'data-slot="(\w+)"', html) == lanes
    assert "$0<" not in html and "$0 " not in html
    line = html[html.index('class="ws-lines"'):html.index('id="ws-total"')]
    assert line.count('class="ws-op"') == len(lanes) and line.count(">=<") == 1  # "a + b = total"


def test_nothing_picked_shows_no_items_and_book_waits(client):
    html = bar(client, "/plan?" + NOTHING)
    assert 'data-line-price' not in html and 'data-slot=' not in html
    assert total(html) == "$0" and "Pick a flight, a stay or a car" in html
    book = re.search(r'<a[^>]*id="ws-book"[^>]*>', html).group(0)
    assert 'aria-disabled="true"' in book and "href" not in book


def test_the_rides_line_is_labelled_as_an_estimate_in_the_line_and_the_popover(client):
    html = bar(client, "/plan?" + NO_CAR)
    r = catalog.quote("f1", "h1", None)
    assert re.search(r'data-line-price="rides"[^>]*>%s<' % re.escape(catalog.money(r.rides.cents)), html)
    assert "Rides, estimated" in html and "Uber and Lyft from LAX" in html and "Estimate, not charged" in html
    assert re.search(r'id="ws-total"[^>]*>%s<' % re.escape(catalog.money(r.total_cents)), html)


def test_done_means_the_totals_on_the_sample_trip(client):
    flight, stay = 123_600, 154_000
    assert total(client.get("/plan").text) == "$3,088"
    rides = catalog.quote("f1", "h1", None).rides.cents
    assert total(client.get(f"/plan?{NO_CAR}").text) == catalog.money(flight + stay + rides)
    assert total(client.get(f"/plan?{STAY_ONLY}").text) == catalog.money(stay)
    assert total(client.get("/plan?" + SAMPLE).text) == "$3,088"


def test_quote_json_for_each_mix(client):
    j = client.get("/plan/quote?" + NO_CAR).json()
    L = j["ledger"]
    r = catalog.quote("f1", "h1", None)
    assert L["total"] == catalog.money(r.total_cents) and L["skipped"] == {"flight": False, "stay": False, "car": True}
    assert list(L["slots"]) == ["flight", "stay", "rides"] and L["slots"]["rides"]["price"] == catalog.money(r.rides.cents)
    assert L["url"] == "/plan?f=f1&h=h1&c=none" and L["pick"]["c"] == "none" and L["empty"] is False
    assert "Uber and Lyft from LAX" in L["rides_html"] and 'data-line-price="rides"' in L["line_html"] and 'data-slot="rides"' in L["slots_html"]
    assert L["book"].startswith("/signin?next=" + q("/plan/pay?f=f1&h=h1&c=none", safe=""))
    s = client.get("/plan/quote?" + STAY_ONLY).json()
    assert s["flight"] is None and s["ledger"]["skipped"] == {"flight": True, "stay": False, "car": True} and s["ledger"]["rides_html"] == ""
    assert s["ledger"]["pick"] == {"f": "none", "h": "h1", "c": "none", "rooms": "cq1", "add": "", "fare": "", "bags": ""}
    n = client.get("/plan/quote?" + NOTHING).json()
    assert n["stay"] is None and n["flight"] is None and n["ledger"]["empty"] is True and n["ledger"]["book"] == "" and n["ledger"]["slots"] == {}
    assert n["ledger"]["pick"]["rooms"] is None and n["ledger"]["total"] == "$0"


def test_the_stay_editor_still_quotes_while_the_stay_is_picked_in_another_lane_mix(client):
    j = client.get("/plan/quote?f=none&h=h2&c=none&rooms=gs2").json()
    assert j["stay"]["rooms"]["gs"] == 2 and j["ledger"]["slots"]["stay"]["name"] == "Casa Palmera"


# ---- the panes: skip choices, slim rows, undo, rides card ------------------------------------------------------------

def test_every_lane_has_a_light_skip_choice_and_nothing_is_skipped_by_default(client):
    h = client.get("/plan").text
    for lane, label in (("flights", "I'll drive"), ("stays", "Staying with friends"), ("cars", "No car")):
        p = pane(h, lane)
        assert 'class="ws-skip"' in p and label in p and "data-skipped" not in p.split(">")[0] + p.split(">")[1]
    assert h.count("data-skipped=") == 0 or 'data-skipped="1"' not in h
    assert h.count('data-skip="') == 3 and h.count('data-undo="') == 3  # the slim rows are in the page, hidden until a lane is skipped


def test_a_skipped_lane_collapses_to_a_slim_friendly_row_with_undo(client):
    h = client.get("/plan?f=none&h=none&c=none").text
    for key, words in (("flights", "You're driving there. No flight needed."), ("stays", "Staying with friends. No hotel needed."),
                       ("cars", "No car needed.")):
        p = pane(h, key)
        assert 'data-skipped="1"' in p.split(">")[0] and words in p and 'class="ws-undo"' in p
    assert "Uber and Lyft" not in pane(h, "cars").split('class="ws-skipped"')[1].split('class="ws-undo"')[0]  # no flight, so no airport rides
    only = client.get("/plan?" + NO_CAR).text
    assert 'data-skipped="1"' in pane(only, "cars").split(">")[0] and 'data-skipped="1"' not in pane(only, "flights").split(">")[0]
    assert "No car. We'll estimate Uber and Lyft rides instead." in pane(only, "cars")


def test_a_skipped_lane_cannot_be_expanded_from_the_url(client):
    h = client.get("/plan?f=none&h=h1&c=c1&x=flights&v=f2").text
    assert "data-expanded" not in h.split('id="ws-grid"')[1].split(">")[0]
    ok = client.get("/plan?f=none&h=h1&c=c1&x=stays").text
    assert 'data-expanded="stays"' in ok


def test_no_car_shows_the_rides_card_from_the_flights_airport_to_the_stays_area(client):
    h = client.get("/plan?" + NO_CAR).text
    card = pane(h, "cars")
    r = catalog.quote("f1", "h1", None).rides
    assert "Uber and Lyft from LAX" in card and "LAX → Santa Monica" in card and "Santa Monica → LAX" in card
    assert "Uber" in card and "Lyft" in card and "Sample fares" in card and "Rides, estimated" in card
    assert catalog.money(r.cents) in card and "Lands 9:32 AM" in card
    assert "Uber and Lyft" not in pane(client.get("/plan?" + SAMPLE).text, "cars").split('id="ws-rides"')[1].split("</div>")[0]
    bur = pane(client.get("/plan?f=f5&h=h3&c=none").text, "cars")
    assert "Uber and Lyft from BUR" in bur and "BUR → Downtown" in bur


def test_with_no_stay_the_rides_go_to_the_city(client):
    card = pane(client.get("/plan?" + FLIGHT_ONLY).text, "cars")
    assert "LAX → Los Angeles" in card and "Los Angeles → LAX" in card


def test_a_party_of_five_or_more_is_priced_as_xl_and_the_card_says_so(client):
    t = "&d=2026-10-16&r=2026-10-20&a=5"
    card = pane(client.get(f"/plan?f=f1&h=h1&c=none{t}").text, "cars")
    assert "XL" in card and "Five or more travelers ride in an XL" in card
    four = pane(client.get(f"/plan?{NO_CAR}").text, "cars")
    assert "Standard" in four and "XL" not in four


def test_the_map_has_no_hotel_pin_when_staying_with_friends(client):
    h = client.get("/plan?f=f1&h=none&c=c1").text
    m = pane(h, "map")
    assert "ws-nostay" in m and "Staying with friends: no hotel pin." in m
    assert "ws-nostay" not in pane(client.get("/plan").text, "map")


def test_the_embedded_data_carries_the_defaults_for_undo(client):
    d = data_of(client.get("/plan?" + NOTHING).text)
    assert d["defaults"] == {"flight": "f1", "stay": "h1", "car": "c1"}
    assert d["pick"] == {"f": "none", "h": "none", "c": "none", "rooms": None, "add": None, "fare": "", "bags": ""}


def test_the_explore_route_survives_a_skipped_stay(client):
    assert client.get("/plan/explore?h=none").status_code == 200


# ---- the pay sheet ---------------------------------------------------------------------------------------------------

def sheet(client, url):
    """The pay sheet's own markup (the workspace behind it is not part of what is paid)."""
    sign_in(client)
    html = client.get("/plan/pay?" + url).text
    return html[html.index('id="pay-dialog"'):] if 'id="pay-dialog"' in html else html


def test_the_pay_sheet_for_each_mix_has_only_the_picked_lanes(client):
    stay = sheet(client, STAY_ONLY)
    assert "The Tidewater" in stay and "Skylark" not in stay and "Breeze" not in stay and "Rides, estimated" not in stay
    assert f"Pay {catalog.money(154_000)}" in stay and "rides later" not in stay
    assert re.search(r'id="pay-total"[^>]*>\$1,540<', stay)
    assert stay.count('class="pay-line"') == 1
    flight = sheet(client, FLIGHT_ONLY)
    assert "Skylark Air 214" in flight and "The Tidewater" not in flight
    car = sheet(client, "f=none&h=none&c=c2")
    assert "Coastline Cars" in car and "Pay $398" in car
    assert 'name="f" value="none"' in car and 'name="h" value="none"' in car and 'name="c" value="c2"' in car


def test_the_rides_estimate_is_shown_on_pay_as_not_charged(client):
    r = catalog.quote("f1", "h1", None)
    html = sheet(client, NO_CAR)
    assert f"Pay {catalog.money(r.paid_cents)} now · about {catalog.money(r.rides.cents)} in rides later" in html
    assert re.search(r'id="pay-total"[^>]*>%s<' % re.escape(catalog.money(r.paid_cents)), html)  # the total is what is charged
    row = html[html.index('id="pay-rides"'):]
    assert "Rides, estimated" in row and "not charged" in row and f"about {catalog.money(r.rides.cents)}" in row
    assert 'name="c" value="none"' in html


def test_pay_sheet_with_nothing_picked_is_refused_with_a_friendly_message(client):
    html = sheet(client, NOTHING)
    html = htmllib.unescape(html)
    assert "We couldn't book that" in html and "Pick at least one thing to book" in html
    assert 'id="pay-go"' not in html and 'href="/plan?f=none&h=none&c=none"' in html


def test_the_pay_sheet_signed_out_sends_a_skip_through_sign_in_and_back(client):
    r = client.get("/plan/pay?" + STAY_ONLY, follow_redirects=False)
    assert r.headers["location"] == f"/signin?next={q('/plan/pay?' + STAY_ONLY, safe='')}&intent=pay"
    back = sign_in(client, next="/plan/pay?" + STAY_ONLY, intent="pay")
    assert "Pay $1,540" in client.get(back.headers["location"]).text


# ---- booking ---------------------------------------------------------------------------------------------------------

def post(client, url):
    return client.post("/pay", data=dict(p.split("=") for p in url.split("&")), follow_redirects=False)


def test_booking_with_nothing_picked_is_refused_and_books_nothing(client):
    sign_in(client)
    r = post(client, NOTHING)
    assert r.status_code == 200 and "Pick at least one thing to book" in r.text
    assert "bookings" not in session_data(client)
    with pytest.raises(ses.BookingError):
        ses.book({"traveler": "ari"}, catalog.quote(None, None, None))


def test_a_stay_only_booking_stores_nulls_and_what_is_charged(client):
    sign_in(client)
    assert post(client, STAY_ONLY).headers["location"] == "/booked"
    b = session_data(client)["bookings"]["ari"]
    assert b["flight"] is None and b["car"] is None and b["stay"] == "h1" and b["total_cents"] == 154_000
    assert "rides" not in b and "fare" not in b and "bags" not in b


def test_a_no_car_booking_charges_flight_and_stay_only(client):
    sign_in(client)
    post(client, NO_CAR)
    b = session_data(client)["bookings"]["ari"]
    assert b["car"] is None and b["total_cents"] == 123_600 + 154_000
    assert cal.rides_of(b).cents == catalog.quote("f1", "h1", None).rides.cents


def test_every_mix_books_and_celebrates_in_matching_words(client):
    words = {STAY_ONLY: ("The Tidewater", "hotel is on the trip calendar"), FLIGHT_ONLY: ("Skylark Air 214", "flights are on the trip calendar"),
             "f=none&h=none&c=c2": ("Coastline Cars", "car booking is on the trip calendar"), NO_CAR: ("about $", "flights and hotel are on the trip calendar"),
             SAMPLE: ("The Tidewater", "flights and hotel are on the trip calendar")}
    for url, (pill, sentence) in words.items():
        sign_in(client)
        post(client, url)
        html = client.get("/booked").text
        assert pill in html and sentence in html, url
    assert "Rides, estimated" in (post(client, NO_CAR) and client.get("/booked").text)


def test_booking_ids_differ_per_mix_and_paying_a_mix_twice_is_one_booking(client):
    sign_in(client)
    post(client, STAY_ONLY)
    first = session_data(client)["bookings"]["ari"]
    post(client, STAY_ONLY)
    assert session_data(client)["bookings"]["ari"] == first
    post(client, SAMPLE)
    assert session_data(client)["bookings"]["ari"]["id"] != first["id"]
    assert ses.booking_id("ari", "f1", "h1", "c1") == "GA-" + __import__("hashlib").sha256(b"ari|f1|h1|c1").hexdigest()[:8].upper()  # the default id is unchanged


def test_a_full_cookie_refuses_a_mix_booking_with_the_friendly_message(client, monkeypatch):
    sign_in(client)
    post(client, SAMPLE)
    before = session_data(client)["bookings"]["ari"]
    monkeypatch.setattr("gitaway.session.BUDGET", 10)
    r = post(client, STAY_ONLY)
    assert r.status_code == 200 and "can&#x27;t hold another booking" in r.text.replace("can't", "can&#x27;t")
    assert session_data(client)["bookings"]["ari"] == before


def test_the_skip_booking_record_stays_inside_the_cookie_budget(client):
    sign_in(client)
    post(client, STAY_ONLY)
    s = session_data(client)
    assert len(json.dumps(s)) < ses.BUDGET
    big = catalog.quote("f1", "h1", "c1", catalog.stay_pick("h1", "cq1ok1fs1", "bflcpk"), flight=catalog.flight_pick("f1", "xl", "8"))
    ses.book(s2 := {"traveler": "ari"}, big)
    assert len(json.dumps(s2)) <= ses.BUDGET


def test_an_old_booking_with_the_retired_no_car_id_still_reads(client):
    b = {"id": "GA-OLD", "flight": "f1", "stay": "h1", "car": "c3", "total_cents": 295_600}
    assert cal.car_of(b) is None and cal.flight_of(b).id == "f1"
    assert [x.id for x in cal.booked_blocks(b, cal.trip_of(b))] == ["b-out", "b-in", "b-out2", "b-back"]
    assert cal.rides_of(b) is not None  # it was "no car", so it reads as rides


# ---- the calendar ----------------------------------------------------------------------------------------------------

def blocks_of(client, url):
    sign_in(client)
    post(client, url)
    html = client.get("/calendar?view=days").text
    return re.findall(r'data-block="([\w-]+)"', html), html


@pytest.mark.parametrize("url,expected", [(SAMPLE, ["b-out", "b-in", "b-out2", "b-back"]), (NO_CAR, ["b-out", "b-in", "b-out2", "b-back"]),
                                          (STAY_ONLY, ["b-in", "b-out2"]), (FLIGHT_ONLY, ["b-out", "b-back"]),
                                          ("f=none&h=none&c=c1", []), ("f=none&h=h2&c=c2", ["b-in", "b-out2"])])
def test_the_calendar_has_blocks_only_for_what_was_booked(client, url, expected):
    found, html = blocks_of(client, url)
    assert sorted(set(found)) == sorted(expected)


def test_stay_only_has_check_in_and_check_out_but_no_flight_blocks(client):
    found, html = blocks_of(client, STAY_ONLY)
    assert "Check in · The Tidewater" in html and "Check out · The Tidewater" in html
    assert "Skylark" not in html and "SFO →" not in html and "→ SFO" not in html


def test_flight_only_has_flight_blocks_but_no_check_in_or_check_out(client):
    found, html = blocks_of(client, FLIGHT_ONLY)
    assert "Skylark Air 214 · SFO → LAX" in html and "Check in" not in html and "Check out" not in html


def test_the_calendar_welcome_note_fits_the_mix(client):
    _, html = blocks_of(client, STAY_ONLY)
    assert "Booked! Your stay at The Tidewater (" in html and "flights" not in html.split("Booked! Your")[1].split("on the calendar")[0]
    _, html = blocks_of(client, SAMPLE)
    assert "Booked! Your flights and The Tidewater" in html


def test_a_car_only_booking_still_opens_a_calendar_with_no_booked_blocks(client):
    found, html = blocks_of(client, "f=none&h=none&c=c1")
    assert found == [] and client.get("/calendar").status_code == 200
    assert "Breeze Rentals" in html  # named in the welcome note


# ---- the flight window (F-021) does not apply without a flight ------------------------------------------------------

def day_blocks(url_picks):
    s = {}
    ses.sign_in(s, "ari")
    ses.book(s, catalog.quote(*url_picks))
    b = ses.booking(s)
    return b, cal.booked_blocks(b, cal.trip_of(b))


def test_no_flight_means_no_window_and_a_flight_still_has_one():
    _, none = day_blocks((None, "h1", None))
    assert cal.day_window(none, 0) == (cal.DEFAULT_START, cal.GRID_END) and cal.day_window(none, 4) == (cal.DEFAULT_START, cal.GRID_END)
    assert cal.window_problem(none, 0, 7 * 60, 8 * 60) is None and cal.window_problem(none, 4, 13 * 60, 21 * 60) is None
    _, full = day_blocks(("f1", "h1", None))
    assert cal.window_problem(full, 0, 7 * 60, 8 * 60) == ("land", 572)
    assert cal.window_problem(full, 4, 12 * 60, 13 * 60)[0] == "home"


def test_activities_before_landing_and_near_the_flight_home_are_allowed_with_no_flight(client):
    sign_in(client)
    post(client, STAY_ONLY)
    ok_first = client.post("/calendar/activities", data={"id": "a1", "day": "0", "start": "07:30", "end": "08:30", "title": "Early breakfast", "kind": "food"}, follow_redirects=False)
    ok_last = client.post("/calendar/activities", data={"id": "a2", "day": "4", "start": "17:00", "end": "18:00", "title": "Last dinner", "kind": "food"}, follow_redirects=False)
    assert ok_first.status_code in (200, 303) and ok_last.status_code in (200, 303)
    html = client.get("/calendar?view=days").text
    assert "Early breakfast" in html and "Last dinner" in html


def test_the_window_still_refuses_with_a_flight(client):
    sign_in(client)
    post(client, FLIGHT_ONLY)
    r = client.post("/calendar/activities", data={"id": "a1", "day": "0", "start": "07:00", "end": "07:45", "title": "Early breakfast", "kind": "food"}, follow_redirects=False)
    assert r.status_code == 409 and "You land at 9:32 AM" in r.text
