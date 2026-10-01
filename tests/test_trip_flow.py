"""F-035: the trip lives in the URL through the workspace, sign-in, pay, booking and the calendar."""
import html as htmllib
import re
from datetime import date
from urllib.parse import quote, urlsplit, parse_qs

from gitaway import catalog
from tests.test_signin import session_data, sign_in, tid

SAMPLE = catalog.SAMPLE_TRIP
THREE_NIGHTS = "d=2026-10-16&r=2026-10-19&a=2&k=4,7"
THREE_ADULTS = "d=2026-10-16&r=2026-10-20&a=3&k=4,7"
T3 = catalog.trip_from_url("2026-10-16", "2026-10-19", "2", "4,7")
T5 = catalog.trip_from_url("2026-10-16", "2026-10-20", "3", "4,7")
PICK = "f=f1&h=h1&c=c1"


def ws_total(html):
    return re.search(r'id="ws-total"[^>]*>([^<]*)<', html).group(1)


def money(trip, f="f1", h="h1", c="c1", **kw):
    return catalog.money(catalog.quote(f, h, c, trip=trip, **kw).total_cents)


def hrefs(html):
    return [htmllib.unescape(h) for h in re.findall(r'href="([^"]*)"', html)]


def test_the_sample_trip_is_still_3088_and_urls_stay_clean(client):
    html = client.get(f"/plan?{PICK}").text
    assert ws_total(html) == "$3,088"
    assert "d=2026" not in html


def test_three_nights_change_the_workspace_total_and_header(client):
    html = client.get(f"/plan?{PICK}&{THREE_NIGHTS}").text
    assert ws_total(html) == money(T3) and ws_total(html) != "$3,088"
    assert "Fri Oct 16 – Mon Oct 19" in html
    assert "2 adults, 2 kids" in html


def test_a_third_adult_changes_the_total_and_the_header(client):
    html = client.get(f"/plan?{PICK}&{THREE_ADULTS}").text
    assert ws_total(html) == money(T5) and ws_total(html) != "$3,088"
    assert "3 adults, 2 kids" in html
    assert "5 people" in html


def test_cards_show_trip_prices(client):
    html = client.get(f"/plan?{PICK}&{THREE_NIGHTS}").text
    assert catalog.money(catalog.offer("c2", T3).price_cents) in html
    assert catalog.money(catalog.offer("h2", T3).price_cents) in html
    assert "3 nights" in html


def test_bad_trip_params_fall_back_to_the_sample_trip(client):
    for qs in ["d=nope&r=2026-10-20&a=2", "d=2026-10-16&r=2026-10-15&a=2", "d=2026-10-16&r=2026-10-20&a=0", "d=2026-10-16&r=2026-12-31&a=2",
               "d=2026-10-16&r=2026-10-20&a=9", "d=2026-10-16&r=2026-10-20&a=2&k=x"]:
        html = client.get(f"/plan?{PICK}&{qs}").text
        assert ws_total(html) == "$3,088", qs


def test_links_carry_the_trip(client):
    html = client.get(f"/plan?{PICK}&{THREE_NIGHTS}").text
    book = re.search(r'id="ws-book"[^>]*href="([^"]*)"|href="([^"]*)"[^>]*id="ws-book"', html)
    link = htmllib.unescape(book.group(1) or book.group(2))
    assert link.startswith(f"/signin?next={quote('/plan/pay?' + PICK + '&' + THREE_NIGHTS, safe='')}")
    j = client.get(f"/plan/quote?{PICK}&{THREE_NIGHTS}").json()
    assert j["ledger"]["total"] == money(T3)
    assert j["ledger"]["url"] == f"/plan?{PICK}&{THREE_NIGHTS}"
    assert quote(THREE_NIGHTS, safe="") in j["ledger"]["book"]
    assert '"tripq": "d=2026-10-16&r=2026-10-19&a=2&k=4,7"' in html


def test_the_workspace_data_has_no_trip_query_for_the_sample_trip(client):
    assert '"tripq": ""' in client.get(f"/plan?{PICK}").text


def test_rooms_follow_the_party_in_the_workspace(client):
    j = client.get(f"/plan/quote?{PICK}&d=2026-10-16&r=2026-10-20&a=4&k=1,2,3,4").json()
    big = catalog.trip_from_url("2026-10-16", "2026-10-20", "4", "1,2,3,4")
    assert j["stay"]["fit_text"] == "Room for all 8"
    assert j["ledger"]["total"] == money(big)
    short = client.get(f"/plan/quote?{PICK}&rooms=ok1&d=2026-10-16&r=2026-10-20&a=4&k=1,2,3,4").json()
    assert short["stay"]["fit_text"] == "Sleeps 2 of 8 · add a room" and short["stay"]["fits"] is False


def test_pay_sheet_follows_the_trip(client):
    sign_in(client)
    html = client.get(f"/plan/pay?{PICK}&{THREE_NIGHTS}").text
    assert re.search(r'id="pay-total"[^>]*>%s<' % re.escape(money(T3)), html)
    assert "LA, Oct 16 – 19" in html and "3 nights" in html and "4 travelers" in html
    for k, v in [("d", "2026-10-16"), ("r", "2026-10-19"), ("a", "2"), ("k", "4,7")]:
        assert re.search(r'name="%s"[^>]*value="%s"|value="%s"[^>]*name="%s"' % (k, v, v, k), html), k


def test_pay_sheet_for_the_sample_trip_has_no_trip_fields(client):
    sign_in(client)
    html = client.get(f"/plan/pay?{PICK}").text
    assert 'name="d"' not in html and "LA, Oct 16 – 20" in html


def test_signed_out_pay_goes_through_sign_in_and_back_with_the_trip(client):
    r = client.get(f"/plan/pay?{PICK}&{THREE_NIGHTS}", follow_redirects=False)
    assert r.headers["location"] == f"/signin?next={quote('/plan/pay?' + PICK + '&' + THREE_NIGHTS, safe='')}&intent=pay"
    nxt = parse_qs(urlsplit(r.headers["location"]).query)["next"][0]
    done = sign_in(client, next=nxt, intent="pay")
    assert done.headers["location"] == nxt
    assert money(T3) in client.get(nxt).text


def test_booking_keeps_the_trip_and_the_calendar_follows_it(client):
    sign_in(client)
    r = client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-19", "a": "2", "k": "4,7"}, follow_redirects=False)
    assert r.headers["location"] == "/booked"
    b = session_data(client)["bookings"][tid("ari")]
    assert b["total_cents"] == catalog.quote("f1", "h1", "c1", trip=T3).total_cents
    assert "3 nights" in client.get("/booked").text
    cal = client.get("/calendar").text
    assert "Oct 16 – 19" in cal and money(T3) in cal
    days = client.get("/calendar?view=days").text
    assert len(re.findall(r'data-chip="\d"', days)) == 4  # 3 nights is 4 days


def test_booking_the_same_picks_for_another_trip_is_a_different_booking(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    first = session_data(client)["bookings"][tid("ari")]["id"]
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-19", "a": "2", "k": "4,7"})
    assert session_data(client)["bookings"][tid("ari")]["id"] != first


def test_sample_booking_has_no_trip_field_and_the_same_id_as_before(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    b = session_data(client)["bookings"][tid("ari")]
    assert "trip" not in b and b["total_cents"] == 308_800


def test_a_one_night_trip_still_works_on_the_calendar(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-17", "a": "1"})
    assert client.get("/calendar").status_code == 200
    assert client.get("/calendar?view=days").status_code == 200
    client.post("/calendar/friends", data={"name": "Mom"})
    assert client.post("/calendar/live", follow_redirects=False).status_code == 303


def test_workspace_change_link_returns_to_start_with_the_trip(client):
    html = client.get(f"/plan?{PICK}&{THREE_NIGHTS}").text
    assert f"/start?{THREE_NIGHTS}" in [h.replace("&amp;", "&") for h in hrefs(html)]
    assert "/start" in hrefs(client.get("/plan").text)


def test_a_three_adult_booking_shows_two_rooms_on_booked_and_the_calendar(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-20", "a": "3", "k": "4,7"})
    assert "City-view Double Queen ×2" in client.get("/booked").text
    cal = client.get("/calendar").text
    assert cal.count("City-view Double Queen ×2") >= 2  # check-in block and the "Booked!" note
    assert "City-view Double Queen)" not in cal


def test_long_demo_never_returns_before_departing():
    from gitaway import tripcal
    late = catalog.TripSearch("SFO", "San Francisco", "Los Angeles", ("LAX",), date(2026, 12, 1), date(2026, 12, 3), 2, ())
    t = tripcal.trip("long", {"trip": catalog.trip_query(late)})
    assert t.return_ > t.depart


def test_a_booked_trip_stays_itself_after_its_departure_passes(client, monkeypatch):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-17", "r": "2026-10-20", "a": "3", "k": "4,7"})
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 12, 1))
    booked = client.get("/booked").text
    assert "City-view Double Queen ×2" in booked and "3 nights" in booked
    cal = client.get("/calendar").text
    assert "Oct 17 – 20" in cal and "City-view Double Queen ×2" in cal
