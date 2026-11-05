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
from tests.test_signin import sign_in, tid

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
    for name in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS"):
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


# ---- the seam -----------------------------------------------------------------------------------------------------

def test_each_lane_has_its_partner():
    assert [(p.lane, p.name) for p in partners.PARTNERS] == [("flight", "Aviasales"), ("stay", "Hotellook"), ("car", "DiscoverCars"), ("ride", "Uber")]


def test_commission_estimates_per_partner():
    assert partners.for_lane("flight").estimate_cents(106_400) == 1_170     # about 1.1%
    assert partners.for_lane("stay").estimate_cents(292_000) == 14_600      # about 5%
    assert partners.for_lane("car").estimate_cents(46_400) == 1_800         # $18 flat
    assert partners.for_lane("ride").estimate_cents(5_000) == 0


def test_partner_links_request_has_the_documented_fields(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "99")
    body = travelpayouts.links_request([("https://www.aviasales.com/search/x", "ab12cd-hi-270305-flight")])
    assert body == {"trs": "99", "marker": "123456", "shorten": True, "links": [{"url": "https://www.aviasales.com/search/x", "sub_id": "ab12cd-hi-270305-flight"}]}
    answer = travelpayouts.SyntheticLinks().create(body, partners.for_lane("flight"))
    assert answer["code"] == 200 and answer["result"]["links"][0]["code"] == "success"
    assert answer["result"]["links"][0]["partner_url"].startswith("https://tp.media/r?marker=123456&trs=99&p=4114&u=https%3A%2F%2Fwww.aviasales.com%2Fsearch%2Fx")


def test_uber_deep_link():
    assert uber_deep_link("SFO", "Waikiki") == "https://m.uber.com/ul/?action=setPickup&pickup[formatted_address]=SFO&dropoff[formatted_address]=Waikiki"


# ---- /plan links ----------------------------------------------------------------------------------------------------

def test_plan_links_every_offer_to_its_partner(client, nokeys):
    html = client.get(f"/plan?{HI}").text.replace("&amp;", "&")
    links = re.findall(r'<a[^>]*href="(/go/[^"]+)"[^>]*data-partner="([a-z]+)"[^>]*>(?:<svg.*?</svg>)?Book on ([A-Za-z]+)</a>', html)
    assert len(links) == 4 + 3 + 2    # four flights, three stays, two cars in Honolulu
    assert {(p, name) for _, p, name in links} == {("aviasales", "Aviasales"), ("hotellook", "Hotellook"), ("discovercars", "DiscoverCars")}
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

def test_go_with_a_marker_sends_a_signed_in_family_to_a_tracked_link_with_its_subid(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    sign_in(client, "ari")
    loc = client.get(f"/go/hif1?{HI}", follow_redirects=False).headers["location"]
    q = parse_qs(urlsplit(loc).query)
    assert loc.startswith("https://tp.media/r?") and q["marker"] == ["123456"] and q["p"] == ["4114"]
    assert q["u"] == ["https://www.aviasales.com/search/SFO0503HNL09032"]
    assert re.fullmatch(r"[0-9a-f]{6}-hi-270305-flight", q["sub_id"][0])
    assert "ari" not in q["sub_id"][0]


def test_the_subid_names_the_family_and_nobody_else(client, nokeys, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    sign_in(client, "ari")
    a = parse_qs(urlsplit(client.get(f"/go/hif1?{HI}", follow_redirects=False).headers["location"]).query)["sub_id"][0]
    b = parse_qs(urlsplit(client.get(f"/go/hih1?{HI}", follow_redirects=False).headers["location"]).query)["sub_id"][0]
    other = browser(client)
    sign_in(other, addr("lee"))
    c = parse_qs(urlsplit(other.get(f"/go/hif1?{HI}", follow_redirects=False).headers["location"]).query)["sub_id"][0]
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
    assert "Complete booking on Hotellook" in page and "Waikiki Tide Resort" in page and "$2,920" in page


def test_a_forged_sandbox_address_is_404(client, nokeys):
    good = sandbox_of(client, "hif1")
    assert client.get(good.replace("/aviasales/", "/hotellook/")).status_code == 404     # that partner does not sell flights
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

def test_a_booking_records_the_conversion_with_the_estimated_commission(client, nokeys):
    sign_in(client, "ari")
    r = complete(client, "hif1")
    assert r.status_code == 303 and re.fullmatch(r"/sandbox/aviasales/[0-9a-f]{10}/done", r.headers["location"])
    done = text(client.get(r.headers["location"]).text)
    assert "Booked elsewhere · Aviasales" in done and "$1,064" in done and "$11.70" in done
    page = text(client.get("/partners").text)
    assert "1 click · 1 booked · estimated commission $11.70" in page
    assert "Aviasales Booked Aloha Pacific 12" in page
    assert re.search(r"SubID [0-9a-f]{6}-hi-270305-flight Estimated commission \$11\.70 Partner status processing", page)


def test_commission_per_lane_on_the_partners_page(client, nokeys):
    sign_in(client, "ari")
    for offer in ("hif1", "hih1", "hic1"):
        assert complete(client, offer).status_code == 303
    page = text(client.get("/partners").text)
    assert "3 clicks · 3 booked · estimated commission $175.70" in page     # $11.70 + $146.00 + $18.00
    for fragment in ("Hotellook Booked Waikiki Tide Resort", "DiscoverCars Booked Island Drive Rentals"):
        assert fragment in page


def test_a_click_that_was_not_booked_is_listed_as_clicked_with_no_commission(client, nokeys):
    sign_in(client, "ari")
    sandbox_of(client, "hic1")
    page = text(client.get("/partners").text)
    assert "1 click · 0 booked · estimated commission $0" in page
    assert re.search(r"DiscoverCars Clicked Island Drive Rentals SubID [0-9a-f]{6}-hi-270305-car Estimated commission –", page)


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
    assert "Booked elsewhere · DiscoverCars" in done    # a click's own page names its own partner


def test_a_trip_with_three_partners_has_a_short_label(client, nokeys):
    from gitaway import importer
    from tests.test_signin import person
    sign_in(client, "ari")
    for offer in ("hif1", "hih1", "hic1"):
        complete(client, offer)
    s = person("ari")
    assert importer.plan_of(s).booked_on == "3 partners"


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
    page = client.get(f"/sandbox/hotellook/{click}?o=hih1&{HI}").text
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    complete(client, "hif1")   # an unrelated booking
    client.post(f"/sandbox/aviasales/{click}", data={**fields, "o": "hif1"}, follow_redirects=False)
    r = client.post(f"/sandbox/hotellook/{click}", data=fields, follow_redirects=False)
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
    assert r.status_code == 302 and r.headers["location"].startswith("https://tp.media/r?marker=123456")
    assert client.get("/sandbox/aviasales/0123456789?o=hif1&" + HI).status_code == 404    # the stand-in never exists with the showcase off


def test_off_the_showcase_a_token_opens_partners_with_a_note_that_statistics_are_not_live(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
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
