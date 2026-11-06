"""Autopilot M2/M3: the partner seam, /go, the sandbox checkout, the conversion, /partners. Everything through the HTTP seam, in both showcase modes.

The contract tests (test_autopilot_contract.py) say the loop works; these pin the exact figures, the SubID, the roles and the production rules.
"""

import re
import socket
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import catalog, partners
from gitaway.partners import travelpayouts, uber_deep_link
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in

TRIP = "d=2027-03-05&r=2027-03-09&a=2"
HI = f"to=hi&{TRIP}"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test in this file may open a socket: every real client is a stub (the real keys are set in some tests on purpose)."""
    def refuse(*a, **k):
        raise AssertionError("a partner code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture
def nokeys(monkeypatch):
    travelpayouts._CACHE.clear()
    for name in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS", "KLOOK_FALLBACK_URL"):
        monkeypatch.delenv(name, raising=False)


def text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def sandbox_of(client, offer, query=HI):
    r = client.get(f"/go/{offer}?{query}", follow_redirects=False)
    assert r.status_code == 302, r.text[:200]
    return r.headers["location"]


def complete(client, offer, query=HI):
    page = client.get(sandbox_of(client, offer, query)).text
    action = re.search(r'<form[^>]*action="([^"]+)"', page).group(1)
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    return client.post(action, data=fields, follow_redirects=False)


def trip_for(to="hi", home="", kids="", focus="", adults="2"):
    return catalog.parse_trip(home, to, "2027-03-05", "2027-03-09", adults, kids, focus=focus)


# ---- the seam -----------------------------------------------------------------------------------------------------

def test_each_lane_has_its_partner():
    assert [(p.lanes, p.name) for p in partners.PARTNERS] == [(("flight",), "Aviasales"), (("stay", "car", "todo"), "Klook"), (("ride",), "Uber")]


def test_commission_estimates_per_partner():
    assert partners.for_lane("flight").estimate_cents(106_400) == 1_170     # about 1.1%
    assert partners.for_lane("stay").estimate_cents(292_000) == 14_600      # Klook about 5%
    assert partners.for_lane("car").estimate_cents(46_400) == 2_320         # Klook about 5%
    assert partners.for_lane("ride").estimate_cents(5_000) == 0


def test_partner_links_request_has_the_documented_fields(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    body = travelpayouts.links_request([("https://www.klook.com/en-US/search/result/?query=x", "ab12cd-hi-270305-stay")])
    # Numbers, not text: the live API answers 400 "invalid body" to "596534"/"801445" as strings (probed 2026-11-05).
    assert body == {"trs": 596534, "marker": 801445, "shorten": False, "links": [{"url": "https://www.klook.com/en-US/search/result/?query=x", "sub_id": "ab12cd-hi-270305-stay"}]}


def test_no_partner_links_call_without_a_numeric_project_id(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    for trs in ("", "abc"):
        monkeypatch.setenv("TRAVELPAYOUTS_TRS", trs)
        assert travelpayouts.links_request([("https://www.klook.com/", "s")]) is None


class FakeApi:
    """Stands in for the partner-links API: records calls, answers like the docs."""
    def __init__(self, answer=None, error=None):
        self.calls, self.answer, self.error = [], answer, error

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.error:
            raise self.error
        if self.answer is not None:
            return self.answer
        link = body["links"][0]
        return {"code": 200, "result": {"links": [{"url": link["url"], "code": "success", "partner_url": f"https://klook.tpx.lv/x?sub={link['sub_id']}"}]}}


KLOOK_HI = "https://www.klook.com/en-US/search/result/?query=Honolulu%20hotels"


def test_klook_link_calls_the_api_once_with_a_short_timeout_and_caches_it(nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    for _ in range(2):
        assert travelpayouts.klook_link(KLOOK_HI, "ab12cd-hi-270305-stay") == "https://klook.tpx.lv/x?sub=ab12cd-hi-270305-stay"
    assert len(api.calls) == 1
    url, headers, body, timeout = api.calls[0]
    assert (url, headers, timeout) == ("https://api.travelpayouts.com/links/v1/create", {"X-Access-Token": "tok"}, 2)
    assert body["links"] == [{"url": KLOOK_HI, "sub_id": "ab12cd-hi-270305-stay"}] and body["marker"] == 801445 and body["trs"] == 596534
    travelpayouts.klook_link(KLOOK_HI, "other-sub")      # another SubID is another link
    assert len(api.calls) == 2


@pytest.mark.parametrize("api", [FakeApi(error=TimeoutError("slow")), FakeApi(answer={"code": 200, "result": {"links": [{"code": "error", "partner_url": ""}]}}),
                                 FakeApi(answer={"unexpected": 1})])
def test_klook_link_falls_back_when_the_api_fails(nokeys, monkeypatch, api):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    monkeypatch.setattr(travelpayouts, "_post", api)
    assert travelpayouts.klook_link(KLOOK_HI, "s") == "https://klook.tpx.lv/s1rIcwCA"
    assert travelpayouts._CACHE == {}       # a failure is not remembered
    monkeypatch.setenv("KLOOK_FALLBACK_URL", "https://klook.example/mine")
    assert travelpayouts.klook_link(KLOOK_HI, "s") == "https://klook.example/mine"


def test_klook_link_without_a_token_never_calls_the_api(nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    assert travelpayouts.klook_link(KLOOK_HI, "s") == "https://klook.tpx.lv/s1rIcwCA" and api.calls == []


def test_uber_deep_link():
    assert uber_deep_link("SFO", "Waikiki") == "https://m.uber.com/ul/?action=setPickup&pickup[formatted_address]=SFO&dropoff[formatted_address]=Waikiki"


# ---- /plan links ----------------------------------------------------------------------------------------------------

def test_plan_links_every_offer_to_its_partner(client, nokeys):
    html = client.get(f"/plan?{HI}").text.replace("&amp;", "&")
    links = re.findall(r'<a[^>]*href="(/go/[^"]+)"[^>]*data-partner="([a-z]+)"[^>]*>(?:<svg.*?</svg>)?Book on ([A-Za-z]+)</a>', html)
    assert len(links) == 4 + 3 + 2    # four flights, three stays, two cars in Honolulu
    assert {(p, name) for _, p, name in links} == {("aviasales", "Aviasales"), ("klook", "Klook")}
    assert f"/go/hif1?to=hi&d=2027-03-05&r=2027-03-09&a=2" in [h for h, _, _ in links]
    assert "we may earn a commission" in html


def test_plan_has_no_partner_links_in_production_without_a_marker(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    html = client.get(f"/plan?{HI}").text
    assert "Book on" not in html and "/go/" not in html


def test_plan_links_in_production_with_a_marker(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    assert "Book on Aviasales" in text(client.get(f"/plan?{HI}").text)


# ---- /go ------------------------------------------------------------------------------------------------------------

def test_go_flight_with_a_marker_goes_to_an_aviasales_search_with_marker_and_subid(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    sign_in(client, "ari")
    loc = client.get(f"/go/hif1?{HI}", follow_redirects=False).headers["location"]
    base, _, query = loc.partition("?")
    assert base == "https://www.aviasales.com/"      # the reader has not said where they fly from: Aviasales asks, with the rest of the search filled in
    assert parse_qs(query)["destination_iata"] == ["HNL"] and parse_qs(query)["adults"] == ["2"]
    marker = parse_qs(query)["marker"][0]
    assert re.fullmatch(r"801445\.[0-9a-f]{6}-hi-270305-flight", marker)
    assert "ari" not in marker


def test_go_stay_with_a_token_goes_to_the_tracked_klook_link(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    sign_in(client, "ari")
    r = client.get(f"/go/hih1?{HI}", follow_redirects=False)
    assert r.status_code == 302 and re.fullmatch(r"https://klook\.tpx\.lv/x\?sub=[0-9a-f]{6}-hi-270305-stay", r.headers["location"])
    assert api.calls[0][2]["links"][0]["url"] == "https://www.klook.com/en-US/search/result/?query=Honolulu%20hotels"


def test_go_car_without_a_token_goes_to_the_klook_fallback(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    r = client.get(f"/go/hic1?{HI}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://klook.tpx.lv/s1rIcwCA"


def test_the_plan_page_never_calls_the_partner_api(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    assert client.get(f"/plan?{HI}").status_code == 200 and api.calls == []


def test_the_subid_names_the_family_and_nobody_else(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    monkeypatch.setattr(travelpayouts, "_post", FakeApi())

    def sub(c, offer):
        loc = c.get(f"/go/{offer}?{HI}", follow_redirects=False).headers["location"]
        return parse_qs(urlsplit(loc).query)["marker"][0].split(".", 1)[1] if "aviasales" in loc else loc.split("sub=")[1]
    sign_in(client, "ari")
    a, b = sub(client, "hif1"), sub(client, "hih1")
    other = browser(client)
    sign_in(other, addr("lee"))
    c = sub(other, "hif1")
    assert a.split("-")[0] == b.split("-")[0] and a.split("-")[0] != c.split("-")[0]
    assert b.endswith("-hi-270305-stay")


def test_a_signed_out_click_still_redirects_and_logs_nothing(client, nokeys):
    assert sandbox_of(client, "hif1").startswith("/sandbox/aviasales/")
    sign_in(client, "ari")
    assert "No clicks yet" in text(client.get("/partners").text)


def test_go_uses_the_offers_own_place(client, nokeys):
    assert "o=nycf1" in sandbox_of(client, "nycf1", "to=la&" + TRIP) and "to=nyc" in sandbox_of(client, "nycf1", "to=la&" + TRIP)


def test_go_unknown_offer_is_404(client, nokeys):
    assert client.get("/go/zzz", follow_redirects=False).status_code == 404


# ---- the sandbox ------------------------------------------------------------------------------------------------------

def test_sandbox_page_shows_the_partner_the_offer_and_its_price(client, nokeys):
    page = text(client.get(sandbox_of(client, "hif1")).text)
    for want in ("Aviasales", "Aloha Pacific 12", "$1,064", "Complete booking on Aviasales", "Mar 5 – Mar 9", "2 travelers"):
        assert want in page, want
    assert "<form" in client.get(sandbox_of(client, "hif1")).text


def test_sandbox_page_for_a_stay_names_its_own_partner(client, nokeys):
    page = text(client.get(sandbox_of(client, "hih1")).text)
    assert "Complete booking on Klook" in page and "Waikiki Tide Resort" in page and "$2,920" in page


def test_a_forged_sandbox_address_is_404(client, nokeys):
    good = sandbox_of(client, "hif1")
    assert client.get(good.replace("/aviasales/", "/klook/")).status_code == 404     # that partner does not sell flights
    assert client.get(good.replace("o=hif1", "o=nope")).status_code == 404
    assert client.get(good.replace("/aviasales/", "/nobody/")).status_code == 404
    assert client.get("/sandbox/aviasales/not-a-click?o=hif1").status_code == 404


def test_booking_signed_out_asks_to_sign_in_first(client, nokeys):
    loc = sandbox_of(client, "hif1")
    page = client.get(loc).text
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    r = client.post(loc.split("?")[0], data=fields, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Fsandbox%2Faviasales%2F")


# ---- the conversion and /partners -----------------------------------------------------------------------------------------

def test_a_booking_records_the_conversion_and_the_family_sees_no_commission(client, nokeys):
    sign_in(client, "ari")
    r = complete(client, "hif1")
    assert r.status_code == 303 and re.fullmatch(r"/sandbox/aviasales/[0-9a-f]{10}/done", r.headers["location"])
    done = text(client.get(r.headers["location"]).text)
    assert "Booked elsewhere · Aviasales" in done and "$1,064" in done and "Estimated commission" not in done
    page = text(client.get("/partners").text)
    assert "1 click · 1 booked" in page and "$11.70" not in page and "estimated commission" not in page.lower()
    assert "Aviasales Booked Aloha Pacific 12" in page
    assert re.search(r"SubID [0-9a-f]{6}-hi-270305-flight Price at the partner \$1,064 Partner status processing", page)


def test_the_partners_page_lists_every_lane_without_commission(client, nokeys):
    sign_in(client, "ari")
    for offer in ("hif1", "hih1", "hic1"):
        assert complete(client, offer).status_code == 303
    page = text(client.get("/partners").text)
    assert "3 clicks · 3 booked" in page and "$180.90" not in page
    for fragment in ("Klook Booked Waikiki Tide Resort", "Klook Booked Island Drive Rentals"):
        assert fragment in page


def test_a_click_that_was_not_booked_is_listed_as_clicked(client, nokeys):
    sign_in(client, "ari")
    sandbox_of(client, "hic1")
    page = text(client.get("/partners").text)
    assert "1 click · 0 booked" in page
    assert re.search(r"Klook Clicked Island Drive Rentals SubID [0-9a-f]{6}-hi-270305-car Price at the partner –", page)


def test_booking_twice_changes_nothing(client, nokeys):
    sign_in(client, "ari")
    loc = sandbox_of(client, "hif1")
    page = client.get(loc).text
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    for _ in range(2):
        assert client.post(loc.split("?")[0], data=fields, follow_redirects=False).status_code == 303
    assert "1 click · 1 booked" in text(client.get("/partners").text)


def test_the_booking_lands_in_the_trip_and_a_second_lane_joins_it(client, nokeys):
    sign_in(client, "ari")
    first = text(client.get(complete(client, "hif1").headers["location"]).text)
    assert "Booked elsewhere · Aviasales" in first
    trip = text(client.get("/trip/details").text)
    assert "Honolulu trip" in trip and "Aloha Pacific 12" in trip
    complete(client, "hih1")
    trip = text(client.get("/trip/details").text)
    assert "Aloha Pacific 12" in trip and "Waikiki Tide Resort" in trip     # one trip: the hotel joined the flight
    done = text(client.get(complete(client, "hic1").headers["location"]).text)
    assert "Booked elsewhere · Klook" in done    # a click's own page names its own partner


def test_a_trip_booked_on_two_partners_is_labelled_with_both(client, nokeys):
    from gitaway import importer
    from tests.test_signin import person
    sign_in(client, "ari")
    for offer in ("hif1", "hih1", "hic1"):
        complete(client, offer)
    assert importer.plan_of(person("ari")).booked_on == "Aviasales, Klook"      # Klook sold the stay and the car: listed once


def test_a_long_label_collapses_to_a_count():
    from gitaway.partners import log
    assert log._origin("Aviasales, Klook", "Skyscanner Flights Direct") == "3 partners"


def test_a_viewer_cannot_book_but_can_click_and_read(client, nokeys):
    from tests.test_calendar import book
    book(client)
    viewer_mail = addr("vi")
    invite(client, viewer_mail, "viewer")
    viewer = browser(client)
    sign_in(viewer, viewer_mail)
    r = complete(viewer, "hif1")
    assert r.status_code == 403 and "Only editors can change that" in r.text
    assert "1 click · 0 booked" in text(viewer.get("/partners").text)


def test_partners_needs_sign_in_and_goes_back_after(client, nokeys):
    r = client.get("/partners", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Fpartners"


def test_one_family_never_sees_anothers_clicks(client, nokeys):
    sign_in(client, "ari")
    complete(client, "hif1")
    other = browser(client)
    sign_in(other, addr("lee"))
    assert "No clicks yet" in text(other.get("/partners").text)


def test_a_booked_click_id_cannot_be_reused_for_another_offer(client, nokeys):
    sign_in(client, "ari")
    loc = sandbox_of(client, "hif1")
    click = loc.split("/")[3].split("?")[0]
    page = client.get(f"/sandbox/klook/{click}?o=hih1&{HI}").text
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    complete(client, "hif1")   # an unrelated booking
    client.post(f"/sandbox/aviasales/{click}", data={**fields, "o": "hif1"}, follow_redirects=False)
    r = client.post(f"/sandbox/klook/{click}", data=fields, follow_redirects=False)
    assert r.status_code == 404


# ---- production stays honest ----------------------------------------------------------------------------------------------------

def test_off_the_showcase_sandbox_and_go_are_404_without_keys(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    sign_in(client, "ari")
    assert client.get("/go/hif1?" + HI, follow_redirects=False).status_code == 404
    assert client.get("/sandbox/aviasales/0123456789?o=hif1&" + HI).status_code == 404
    assert client.get("/partners").status_code == 404


def test_off_the_showcase_a_marker_still_sends_people_to_the_real_partner(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    r = client.get("/go/hif1?" + HI, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("https://www.aviasales.com/?destination_iata=HNL&depart_date=2027-03-05&return_date=2027-03-09&adults=2&marker=123456.")
    r = client.get("/go/hif1?" + HI + "&home=jfk", follow_redirects=False)      # the reader's airport rides in the click's address
    assert r.headers["location"].startswith("https://www.aviasales.com/search/JFK0503HNL09032?marker=123456.")
    assert client.get("/sandbox/aviasales/0123456789?o=hif1&" + HI).status_code == 404    # the stand-in never exists with the showcase off


def test_off_the_showcase_a_token_opens_partners_with_a_note_that_statistics_are_not_live(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    sign_in(client, "ari")
    client.get("/go/hif1?" + HI, follow_redirects=False)
    page = text(client.get("/partners").text)
    assert "Live statistics are not connected yet" in page and "1 click · 0 booked" in page and "Sample data" not in page


def test_no_page_links_to_a_hidden_partner_page_when_the_showcase_is_off(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    sign_in(client, "ari")
    for path in ("/", "/start", f"/plan?{HI}", "/trip"):
        html = client.get(path).text
        assert 'href="/sandbox' not in html and 'href="/partners' not in html and 'href="/go/' not in html, path


# ---- F-195: the link points at the reader's real trip ---------------------------------------------------------------------

def flight_url(trip):
    return partners.for_lane("flight").target_url(catalog.offer(f"{trip.key if trip.key != 'la' else ''}f1", trip), trip)


def test_a_flight_link_asks_where_from_when_the_reader_has_not_said():
    assert flight_url(trip_for()) == "https://www.aviasales.com/?destination_iata=HNL&depart_date=2027-03-05&return_date=2027-03-09&adults=2"
    assert "SFO" not in flight_url(trip_for(kids="4,7"))


def test_a_flight_link_leaves_from_the_readers_own_airport():
    assert flight_url(trip_for(home="jfk")) == "https://www.aviasales.com/search/JFK0503HNL09032"
    assert flight_url(trip_for(home="SFO")) == "https://www.aviasales.com/search/SFO0503HNL09032"      # only when they chose it


def test_adults_children_and_infants_go_to_aviasales_apart():
    assert flight_url(trip_for(home="JFK", kids="4,7")) == "https://www.aviasales.com/search/JFK0503HNL090322"        # 2 adults, 2 children
    assert flight_url(trip_for(home="JFK", kids="1")) == "https://www.aviasales.com/search/JFK0503HNL0903201"          # 2 adults, 0 children, 1 infant
    assert flight_url(trip_for(home="JFK", kids="1,4,15")) == "https://www.aviasales.com/search/JFK0503HNL0903311"  # the 15-year-old flies as an adult: 3 adults, 1 child, 1 infant
    assert flight_url(trip_for(kids="4,7")) == "https://www.aviasales.com/?destination_iata=HNL&depart_date=2027-03-05&return_date=2027-03-09&adults=2&children=2"
    assert flight_url(trip_for(kids="1,4")).endswith("&adults=2&children=1&infants=1")


def klook_url(kind, trip):
    return partners.for_lane(kind).target_url(catalog.search_offer(kind, trip), trip)


def test_a_disneyland_trip_gets_disneyland_tickets_and_other_trips_get_their_attractions():
    assert klook_url("todo", trip_for("la", focus="disney")) == "https://www.klook.com/en-US/destination/p50042790-disneyland-resort/"
    assert klook_url("todo", trip_for("la")) == "https://www.klook.com/en-US/search/result/?query=Los%20Angeles%20attractions"
    assert klook_url("todo", trip_for("hi")) == "https://www.klook.com/en-US/search/result/?query=Honolulu%20attractions"
    assert klook_url("todo", trip_for("nyc")) == "https://www.klook.com/en-US/search/result/?query=New%20York%20attractions"


def test_a_disneyland_stay_is_in_anaheim_not_los_angeles():
    assert klook_url("stay", trip_for("la", focus="disney")) == "https://www.klook.com/en-US/search/result/?query=Anaheim%20hotels"
    assert klook_url("stay", trip_for("la")) == "https://www.klook.com/en-US/search/result/?query=Los%20Angeles%20hotels"
    assert partners.for_lane("stay").target_url(catalog.offer("h1", trip_for("la", focus="disney")), trip_for("la", focus="disney")).endswith("Anaheim%20hotels")


def test_search_offers_say_what_they_are_and_never_carry_a_price():
    t = trip_for("la", home="JFK", focus="disney")
    offers = [catalog.search_offer(k, t) for k in ("flight", "stay", "todo")]
    assert [o.name for o in offers] == ["Search flights to Los Angeles", "Find stays near Anaheim", "Tickets and things to do"]
    assert [o.price_cents for o in offers] == [0, 0, 0] and [o.id for o in offers] == ["search-flight", "search-stay", "search-todo"]
    assert offers[0].airport == "LAX"
    assert catalog.search_offer("stay", trip_for("hi")).name == "Find stays near Honolulu"
    with pytest.raises(KeyError):
        catalog.search_offer("car", t)


# ---- F-195: /go with the reader's airport, the party, tickets and the honest search offers ------------------------------------

def test_go_carries_the_readers_airport_and_party_to_aviasales(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    loc = client.get(f"/go/hif1?{HI}&k=4,7&home=jfk", follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/search/JFK0503HNL090322?marker=801445.")
    loc = client.get(f"/go/hif1?{HI}&k=1,4", follow_redirects=False).headers["location"]
    assert "adults=2&children=1&infants=1&marker=801445." in loc and "SFO" not in loc


def test_go_search_flight_is_one_aviasales_search_without_an_invented_offer(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    sign_in(client, "ari")
    loc = client.get("/go/search-flight?to=la&d=2027-03-05&r=2027-03-09&a=2&home=ord", follow_redirects=False).headers["location"]
    base, _, query = loc.partition("?")
    assert base == "https://www.aviasales.com/search/ORD0503LAX09032"
    assert re.fullmatch(r"801445\.[0-9a-f]{6}-la-270305-flight", parse_qs(query)["marker"][0])
    assert "Search flights to Los Angeles" in text(client.get("/partners").text)


def test_go_search_todo_asks_klook_for_disneyland_tickets_through_the_partner_api(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    sign_in(client, "ari")
    r = client.get(f"/go/search-todo?to=la&{TRIP}&focus=disney", follow_redirects=False)
    assert r.status_code == 302 and re.fullmatch(r"https://klook\.tpx\.lv/x\?sub=[0-9a-f]{6}-la-270305-todo", r.headers["location"])
    assert api.calls[0][2]["links"][0]["url"] == "https://www.klook.com/en-US/destination/p50042790-disneyland-resort/"
    r = client.get(f"/go/search-todo?to=sd&{TRIP}", follow_redirects=False)
    assert api.calls[1][2]["links"][0]["url"] == "https://www.klook.com/en-US/search/result/?query=San%20Diego%20attractions"
    assert "Tickets and things to do" in text(client.get("/partners").text)


def test_a_disneyland_stay_click_asks_klook_for_anaheim(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    client.get(f"/go/h1?to=la&{TRIP}&focus=disney", follow_redirects=False)
    client.get(f"/go/h1?to=la&{TRIP}", follow_redirects=False)
    assert [c[2]["links"][0]["url"] for c in api.calls] == ["https://www.klook.com/en-US/search/result/?query=Anaheim%20hotels", "https://www.klook.com/en-US/search/result/?query=Los%20Angeles%20hotels"]


def test_without_a_marker_a_search_click_goes_straight_to_the_partner_since_there_is_no_stand_in_checkout(client, nokeys):
    r = client.get(f"/go/search-todo?to=hi&{TRIP}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://www.klook.com/en-US/search/result/?query=Honolulu%20attractions"
    r = client.get(f"/go/search-flight?to=hi&{TRIP}", follow_redirects=False)
    assert r.headers["location"].startswith("https://www.aviasales.com/?destination_iata=HNL&")
    assert client.get("/sandbox/klook/0123456789?o=search-todo&to=hi&" + TRIP).status_code == 404


def test_only_the_three_search_lanes_exist(client, nokeys):
    for bad in ("search-car", "search-ride", "search-", "search-todo2", "SEARCH-todo"):
        assert client.get(f"/go/{bad}?to=hi&{TRIP}", follow_redirects=False).status_code == 404, bad


# ---- F-195: the Tickets and things to do card on /plan ---------------------------------------------------------------------

def todo_cards(html):
    return re.findall(r'<a[^>]*href="(/go/search-todo[^"]*)"[^>]*>(.*?)</a>', html.replace("&amp;", "&"), re.S)


def test_plan_has_one_tickets_card_that_goes_to_klook(client, nokeys):
    html = client.get(f"/plan?{HI}").text
    ((href, label),) = todo_cards(html)
    assert href == "/go/search-todo?to=hi&d=2027-03-05&r=2027-03-09&a=2" and "Klook" in text(label)
    assert "Tickets and things to do" in text(html) and "Honolulu attractions" in text(html)


def test_a_disneyland_trip_offers_disneyland_tickets_and_keeps_its_focus_in_every_link(client, nokeys):
    html = client.get("/plan?to=la&d=2027-03-05&r=2027-03-09&a=2&k=4,7&home=JFK&focus=disney").text
    ((href, _),) = todo_cards(html)
    assert href == "/go/search-todo?to=la&d=2027-03-05&r=2027-03-09&a=2&k=4%2C7&home=JFK&focus=disney"
    assert "Disneyland Resort tickets" in text(html)
    assert "/go/h1?to=la&d=2027-03-05&r=2027-03-09&a=2&k=4%2C7&home=JFK&focus=disney" in html.replace("&amp;", "&")      # so does a stay's: it will ask Klook for Anaheim


def test_an_ordinary_los_angeles_trip_is_not_a_disneyland_one(client, nokeys):
    html = client.get("/plan?to=la&d=2027-03-05&r=2027-03-09&a=2").text
    assert "Disneyland" not in html and "Los Angeles attractions" in text(html)


def test_the_tickets_card_follows_the_same_rules_as_the_book_links_in_production(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert todo_cards(client.get(f"/plan?{HI}").text) == []           # no marker: nowhere to send anyone, so no card and no /go/ link at all
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    assert len(todo_cards(client.get(f"/plan?{HI}").text)) == 1
