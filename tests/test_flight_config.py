"""F-027: flight legs, fare types and checked bags, priced by the catalog and carried through the pick URL, ledger, pay and calendar."""
import re
from urllib.parse import parse_qs, urlparse

import pytest

from gitaway import catalog
from tests.test_signin import session_data, sign_in

DONE = "f=f1&h=h1&c=c1&fare=main&bags=2"  # Skylark 214, Main fare, 2 bags
T5 = catalog.trip_from_url("2026-10-16", "2026-10-20", "3", "4,7")  # 3 adults + 2 kids = 5 travelers
T5Q = "d=2026-10-16&r=2026-10-20&a=3&k=4,7"


def ws_total(html):
    return re.search(r'id="ws-total"[^>]*>([^<]*)<', html).group(1)


def quote_json(client, qs):
    r = client.get("/plan/quote?" + qs)
    assert r.status_code == 200
    return r.json()


# ---- catalog ---------------------------------------------------------------------------------------------------

def test_every_flight_has_legs_with_stops_and_an_aircraft():
    for f in catalog.offers("flight"):
        assert f.aircraft and f.stops
    f1, f4 = catalog.offer("f1"), catalog.offer("f4")
    assert (f1.aircraft, f1.stops) == ("Airbus A320", "Nonstop")
    assert (f4.aircraft, f4.stops) == ("Embraer 175", "1 stop · SJC")


def test_the_three_fares_scale_per_traveler_and_carry_four_perks_each():
    fares = catalog.fares()
    assert [(f.id, f.name, f.extra_cents) for f in fares] == [("basic", "Basic", 0), ("main", "Main", 24_000), ("xl", "Extra legroom", 56_000)]
    assert all(len(f.perks) == 4 for f in fares)
    assert [f.included_bags for f in fares] == [0, 0, 4]
    five = catalog.fares(T5)
    assert [f.extra_cents for f in five] == [0, 30_000, 70_000] and five[2].included_bags == 5


def test_the_default_flight_pick_keeps_todays_totals():
    p = catalog.flight_pick("f1")
    assert (p.fare, p.bags, p.cents, p.query, p.summary) == ("basic", 0, 123_600, "", "Basic fare")
    assert catalog.quote("f1", "h1", "c1").total_cents == 308_800


def test_main_fare_and_two_bags_is_the_done_means_flight():
    p = catalog.flight_pick("f1", "main", "2")
    assert p.cents == 123_600 + 24_000 + 14_000 == 161_600 and catalog.money(p.cents) == "$1,616"
    assert p.summary == "Main fare + 2 checked bags" and p.short == "Main fare · 2 bags"
    q = catalog.quote("f1", "h1", "c1", flight=p)
    assert q.total_cents == 346_800 and catalog.money(q.total_cents) == "$3,468"
    assert q.lane_cents("flight") == 161_600
    assert [(i.name, i.qty, i.cents) for i in q.items if i.lane == "flight"] == [("Skylark Air 214", 1, 123_600), ("Main fare", 1, 24_000), ("Checked bag", 2, 14_000)]


@pytest.mark.parametrize("fare,bags", [("zz", "x"), ("MAIN", "-1"), ("main ", "9"), ("", ""), ("xl;", "02x"), ("basic", "99"), (None, None), ("main", "٣")])
def test_bad_values_fall_back_to_basic_and_no_bags(fare, bags):
    p = catalog.flight_pick("f1", fare, bags)
    assert p.bags == 0 and (p.fare == "main" if fare == "main" else p.fare == "basic")
    assert catalog.flight_pick("f1", "junk", bags).fare == "basic" and catalog.flight_pick("f1", fare, "junk").bags == 0


def test_the_cap_is_two_bags_per_traveler():
    assert catalog.flight_pick("f1", None, "8").bags == 8 and catalog.flight_pick("f1", None, "9").bags == 0
    assert catalog.flight_pick("f1").max_bags == 8
    assert catalog.flight_pick("f1", None, "10", T5).bags == 10 and catalog.flight_pick("f1", None, "11", T5).bags == 0


def test_extra_legroom_includes_one_checked_bag_per_traveler():
    p = catalog.flight_pick("f1", "xl", "4")
    assert p.cents == 123_600 + 56_000 and p.summary == "Extra legroom fare + 4 checked bags"
    assert [i.name for i in p.items] == ["Skylark Air 214", "Extra legroom fare"]  # no $0 bag line
    five = catalog.flight_pick("f1", "xl", "6")
    assert [(i.name, i.qty, i.cents) for i in five.items][-1] == ("Checked bag", 2, 14_000)  # 4 included on the sample trip
    assert catalog.flight_pick("f1", "xl", "5").cents == 123_600 + 56_000 + 7_000
    assert catalog.flight_pick("f1", "main", "4").cents == 123_600 + 24_000 + 28_000


def test_codes_are_compact_and_the_default_is_empty():
    assert catalog.flight_pick("f1", "main", "2").query == "&fare=main&bags=2"
    assert catalog.flight_pick("f1", "xl").query == "&fare=xl"
    assert catalog.flight_pick("f1", None, "1").query == "&bags=1"
    assert catalog.flight_pick("f1", "basic", "0").query == ""


def test_fares_follow_the_trip_like_flights_do():
    p = catalog.flight_pick("f1", "main", "2", T5)
    base = catalog.offer("f1", T5).price_cents
    assert base == 123_600 // 4 * 5 and p.cents == base + 30_000 + 14_000  # bags are per bag, not per traveler
    assert catalog.flight_pick("f1", "xl", None, T5).cents == base + 70_000


def test_a_quote_refuses_a_pick_for_another_flight_or_trip():
    with pytest.raises(KeyError):
        catalog.quote("f1", "h1", "c1", flight=catalog.flight_pick("f2", "main"))
    with pytest.raises(ValueError):
        catalog.quote("f1", "h1", "c1", flight=catalog.flight_pick("f1", "main", trip=T5))


# ---- the plan page and the quote route ---------------------------------------------------------------------------

def test_done_means_total_on_the_plan_page_and_through_reload(client):
    html = client.get(f"/plan?{DONE}").text
    assert ws_total(html) == "$3,468"
    assert re.search(r'data-line-price="flight"[^>]*>\$1,616<', html)
    assert re.search(r'data-slot-price="flight"[^>]*>\$1,616<', html) and "Main fare + 2 checked bags" in html
    assert 'data-detail="f1"' in html and 'data-fare="main"' in html and 'data-bags="2"' in html
    assert ws_total(client.get(f"/plan?{DONE}").text) == "$3,468"
    assert ws_total(client.get("/plan?f=f1&h=h1&c=c1").text) == "$3,088"


def test_the_flight_panel_shows_legs_fares_and_bags_with_the_trips_dates(client):
    html = client.get(f"/plan?{DONE}&x=flights").text
    panel = html[html.index('data-detail="f1"'):html.index('data-detail="f2"')]
    assert "Out · Fri Oct 16" in panel and "Back · Tue Oct 20" in panel
    assert "Airbus A320" in panel and "Nonstop" in panel and "1h 27m" in panel
    assert 'role="radiogroup"' in panel and panel.count('role="radio"') == 3
    assert re.search(r'data-fare-pick="main"[^>]*aria-checked="true"', panel) or re.search(r'aria-checked="true"[^>]*data-fare-pick="main"', panel)
    assert "+$240" in panel and "+$560" in panel and "$1,476" in panel and "$1,796" in panel  # each fare's price for this flight
    assert panel.count("ws-perk") >= 12
    assert "$70 per bag, round trip" in panel
    assert re.search(r'ws-bag-count"[^>]*>2<', panel)
    f4 = html[html.index('data-detail="f4"'):html.index('data-detail="f5"')]
    assert "1 stop · SJC" in f4 and "Embraer 175" in f4


def test_the_flight_legs_use_the_trips_real_dates(client):
    html = client.get(f"/plan?f=f1&h=h1&c=c1&d=2026-11-02&r=2026-11-07&a=2&k=4,7&x=flights").text
    assert "Out · Mon Nov 2" in html and "Back · Sat Nov 7" in html


def test_a_bigger_party_scales_fares_cap_and_included_bags_on_the_page(client):
    html = client.get(f"/plan?f=f1&h=h1&c=c1&fare=xl&{T5Q}&x=flights").text
    panel = html[html.index('data-detail="f1"'):html.index('data-detail="f2"')]
    assert "+$300" in panel and "+$700" in panel and 'data-max="10"' in panel and "5 included with Extra legroom" in panel
    j = quote_json(client, f"f=f1&h=h1&c=c1&fare=main&bags=2&{T5Q}")
    assert j["flight"]["price"] == catalog.money(catalog.flight_pick("f1", "main", "2", T5).cents)
    assert j["ledger"]["url"].endswith(f"&fare=main&bags=2&{T5Q}")


def test_quote_route_returns_the_flight_figures_and_urls(client):
    j = quote_json(client, DONE)
    assert j["ledger"]["total"] == "$3,468"
    assert j["ledger"]["slots"]["flight"] == {"name": "Skylark Air 214", "price": "$1,616", "sub": "Main fare + 2 checked bags"}
    assert j["ledger"]["url"] == "/plan?f=f1&h=h1&c=c1&fare=main&bags=2"
    assert "fare%3Dmain%26bags%3D2" in j["ledger"]["book"]
    assert j["ledger"]["pick"]["fare"] == "main" and j["ledger"]["pick"]["bags"] == "2"
    fl = j["flight"]
    assert (fl["id"], fl["fare"], fl["fare_code"], fl["bags"], fl["bags_code"], fl["max"]) == ("f1", "main", "main", 2, "2", 8)
    assert fl["summary"] == "Main fare + 2 checked bags" and fl["price"] == "$1,616" and fl["bag_note"] == "$70 per bag, round trip"
    sign_in(client)
    assert quote_json(client, DONE)["ledger"]["book"] == "/plan/pay?f=f1&h=h1&c=c1&fare=main&bags=2"


def test_quote_route_defaults_and_ignores_junk_fares(client):
    j = quote_json(client, "f=f1&h=h1&c=c1&fare=zz&bags=99")
    assert j["ledger"]["total"] == "$3,088" and j["ledger"]["url"] == "/plan?f=f1&h=h1&c=c1"
    assert j["ledger"]["slots"]["flight"]["sub"] == "" and j["flight"]["fare"] == "basic" and j["flight"]["bags"] == 0
    assert quote_json(client, "f=f2&fare=xl")["flight"]["bag_note"] == "4 included with Extra legroom, then $70 each, round trip"


def test_quote_route_totals_match_the_catalog_for_every_fare_and_bag_count(client):
    for fare in ("basic", "main", "xl"):
        for n in range(0, 9):
            j = quote_json(client, f"f=f3&h=h2&c=c3&fare={fare}&bags={n}")
            assert j["flight"]["price"] == catalog.money(catalog.flight_pick("f3", fare, str(n)).cents)


def test_another_flights_pick_starts_from_basic_and_no_bags(client):
    html = client.get("/plan?f=f2&h=h1&c=c1&fare=main&bags=1&x=flights").text
    p2 = html[html.index('data-detail="f2"'):html.index('data-detail="f3"')]
    assert 'data-fare="main"' in p2
    p1 = html[html.index('data-detail="f1"'):html.index('data-detail="f2"')]
    assert 'data-fare=""' in p1 and 'data-bags=""' in p1


# ---- pay ---------------------------------------------------------------------------------------------------

def test_the_pay_sheet_itemizes_the_fare_and_bags(client):
    sign_in(client)
    html = client.get(f"/plan/pay?{DONE}").text
    items = re.findall(r'<li class="pay-item">\s*<span class="pay-item-name">([^<]*)</span>\s*<span class="pay-item-price">([^<]*)</span>', html)
    assert items[:3] == [("Skylark Air 214", "$1,236"), ("Main fare", "$240"), ("Checked bag ×2", "$140")]  # the flight lane first, then the stay's
    assert re.search(r'pay-name">Skylark Air 214</span>.*?class="pay-price">\$1,616<', html, re.S)
    assert "Pay $3,468" in html
    assert 'name="fare" value="main"' in html and 'name="bags" value="2"' in html
    assert 'href="/plan?f=f1&amp;h=h1&amp;c=c1&amp;fare=main&amp;bags=2"' in html


def test_default_pay_sheet_has_no_fare_params_or_flight_items(client):
    sign_in(client)
    html = client.get("/plan/pay?f=f1&h=h1&c=c1").text
    assert "Pay $3,088" in html and 'name="fare"' not in html and 'name="bags"' not in html and "Skylark Air 214, itemized" not in html


def test_paying_records_the_fare_and_recomputes_the_total(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "main", "bags": "2", "total_cents": "1"})
    b = session_data(client)["bookings"]["ari"]
    assert b["total_cents"] == 346_800 and b["fare"] == "main" and b["bags"] == "2"
    assert "Main fare + 2 checked bags" in client.get("/booked").text


def test_paying_with_junk_fares_books_the_default(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "zz", "bags": "99"})
    b = session_data(client)["bookings"]["ari"]
    assert b["total_cents"] == 308_800 and "fare" not in b and "bags" not in b


def test_paying_a_different_fare_replaces_the_booking(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    first = session_data(client)["bookings"]["ari"]
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "xl"})
    second = session_data(client)["bookings"]["ari"]
    assert second["id"] != first["id"] and second["total_cents"] == 123_600 + 56_000 + 154_000 + 31_200
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "bags": "1"})
    assert session_data(client)["bookings"]["ari"]["id"] not in (first["id"], second["id"])


def test_pay_scales_the_fare_with_the_trip(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "main", "bags": "2", "d": "2026-10-16", "r": "2026-10-20", "a": "3", "k": "4,7"})
    b = session_data(client)["bookings"]["ari"]
    assert b["total_cents"] == catalog.quote("f1", "h1", "c1", trip=T5, flight=catalog.flight_pick("f1", "main", "2", T5)).total_cents


def test_signed_out_pay_keeps_the_fare_through_sign_in(client):
    r = client.get(f"/plan/pay?{DONE}", follow_redirects=False)
    nxt = parse_qs(urlparse(r.headers["location"]).query)["next"][0]
    assert nxt == f"/plan/pay?{DONE}"
    r = sign_in(client, next=nxt, intent="pay")
    assert "Pay $3,468" in client.get(r.headers["location"]).text


# ---- calendar and /booked ----------------------------------------------------------------------------------------

def test_the_calendar_flight_blocks_name_the_fare_and_bags(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "main", "bags": "2"})
    html = client.get("/calendar?view=days").text
    assert "Skylark Air 214 · SFO → LAX · Main fare · 2 bags" in html
    assert "Skylark Air 214 · LAX → SFO · Main fare · 2 bags" in html
    assert re.search(r'class="cal-tripline"[^>]*>[^<]*\$3,468<', html)


def test_a_default_booking_keeps_the_calendar_block_text(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    html = client.get("/calendar?view=days").text
    assert "Skylark Air 214 · SFO → LAX<" in html or "Skylark Air 214 · SFO → LAX\"" in html
    assert "Basic fare" not in html


def test_booked_names_the_fare_and_bags(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "xl", "bags": "5"})
    html = client.get("/booked").text
    assert "Extra legroom fare + 5 checked bags" in html


def test_an_old_booking_without_a_fare_still_reads(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    assert session_data(client)["bookings"]["ari"]["total_cents"] == 308_800
    assert client.get("/booked").status_code == 200 and client.get("/calendar").status_code == 200


# ---- page script contract (string checks; the behaviour was walked in a browser) -----------------------------------

def test_the_script_treats_flight_edits_as_drafts_like_stays(client):
    js = client.get("/assets/js/workspace.js").text
    for needle in ("editFlight", "applyFlight", "fare=", "bags="):
        assert needle in js


def test_every_quote_request_the_editors_build_carries_the_trip(client):
    """Without the trip a stay or flight edit on a bigger or longer trip was priced as the sample trip."""
    js = client.get("/assets/js/workspace.js").text
    for fn in ("function editStay", "function editFlight", "function resetPanel"):
        body = js[js.index(fn):]
        call = body[body.index("getQuote("):]
        call = call[:call.index(".then(")]
        assert "tripq" in call, fn


def test_a_full_cookie_refuses_the_booking_with_a_friendly_message_and_keeps_the_old_one(client, monkeypatch):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    before = session_data(client)["bookings"]["ari"]
    monkeypatch.setattr("gitaway.session.BUDGET", 10)
    r = client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "main", "bags": "2"}, follow_redirects=False)
    assert r.status_code == 200 and "can&#x27;t hold another booking" in r.text or "can't hold another booking" in r.text
    assert "Back to my picks" in r.text
    assert session_data(client)["bookings"]["ari"] == before


def test_a_default_booking_leaves_out_empty_fare_and_bags(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    b = session_data(client)["bookings"]["ari"]
    assert "fare" not in b and "bags" not in b and "trip" not in b
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "fare": "main"})
    b = session_data(client)["bookings"]["ari"]
    assert b["fare"] == "main" and "bags" not in b
