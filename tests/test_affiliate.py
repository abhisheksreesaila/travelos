"""F-184: a creator keeps their affiliate links. Through the HTTP seam, in both showcase modes; no test reaches the network."""

import re
import socket
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import affiliate, community
from gitaway.community import HubError
from gitaway.partners import travelpayouts
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_partners import FakeApi, TRIP, nokeys  # noqa: F401 (the fixture)
from tests.test_signin import sign_in, tid


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture(params=["1", "0"], ids=["showcase", "live"])
def mode(request, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", request.param)
    return request.param


@pytest.fixture
def keys(nokeys, monkeypatch):
    """Our Travelpayouts keys, and a fake partner-links API that records what it was asked."""
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    return api


def seen_on(handle, slug=None):
    """The headers of a click on "Plan this trip" on the creator's own page (their profile, or one of their trips): the Referer our page makes the browser send."""
    return {"referer": f"http://testserver/trips/{slug}" if slug else f"http://testserver/creators/{handle}"}


def flight_marker(client, offer="hif1"):
    loc = client.get(f"/go/{offer}?to=hi&{TRIP}", follow_redirects=False).headers["location"]
    assert urlsplit(loc).netloc == "www.aviasales.com", loc
    return parse_qs(urlsplit(loc).query)["marker"][0]


# ---- the marker: digits only ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,saved", [("801445", "801445"), ("  801445 ", "801445"), ("123", "123"), ("1234567890", "1234567890"), ("", ""), ("   ", "")])
def test_a_marker_is_digits_or_nothing(value, saved):
    assert affiliate.clean_marker(value) == saved


@pytest.mark.parametrize("value", ["12", "12345678901", "80144x", "801445.5", "801 445", "-801445", "٨٠١٤٤٥", "801445\n7", "<b>1</b>", "marker=801445"])
def test_anything_else_is_refused_with_the_rule_in_words(value):
    with pytest.raises(HubError) as e:
        affiliate.clean_marker(value)
    assert str(e.value) == "A marker is digits only, 3 to 10 of them, like 801445. Find yours in Travelpayouts under Profile."


# ---- the settings page ----------------------------------------------------------------------------------------------

def test_settings_asks_a_signed_out_visitor_to_sign_in_and_comes_back(client, mode):
    r = client.get("/creators/settings", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=/creators/settings")
    assert client.post("/creators/settings", data={"marker": "801445"}, follow_redirects=False).status_code == 303


def test_a_creator_saves_a_marker_and_sees_what_it_does(client, mode):
    sign_in(client)
    page = client.get("/creators/settings").text
    assert 'name="marker"' in page and "Add your Travelpayouts marker and flights booked from your trips carry it, so Aviasales pays you. Stays and things to do support GitAway for now." in page
    r = client.post("/creators/settings", data={"marker": " 555111 "})
    assert r.status_code == 200 and 'id="st-saved"' in r.text and 'value="555111"' in r.text
    assert affiliate.marker_of(tid()) == "555111"
    assert "Flights booked from your trips carry your Travelpayouts marker, so Aviasales pays you. Stays and things to do support GitAway for now." in r.text


def test_a_bad_marker_is_refused_and_the_old_one_stays(client, mode):
    sign_in(client)
    client.post("/creators/settings", data={"marker": "555111"})
    r = client.post("/creators/settings", data={"marker": "abc"})
    assert r.status_code == 422 and "digits only, 3 to 10 of them" in r.text and 'value="abc"' in r.text
    assert affiliate.marker_of(tid()) == "555111"


def test_an_empty_marker_goes_back_to_gitaways(client, mode):
    sign_in(client)
    client.post("/creators/settings", data={"marker": "555111"})
    assert 'id="st-saved"' in client.post("/creators/settings", data={"marker": ""}).text
    assert affiliate.marker_of(tid()) == ""


def test_the_settings_page_exists_in_production_before_anyone_has_published(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert not community.has_real()
    sign_in(client)
    assert client.get("/creators/settings").status_code == 200


def test_a_cross_site_post_is_refused(client, mode):
    sign_in(client)
    r = client.post("/creators/settings", data={"marker": "555111"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and affiliate.marker_of(tid()) == ""


def test_settings_is_not_taken_for_a_creators_name(mode):
    community.claim_creator("u1", "Settings")
    assert community.creator("settings") is None and community.creator("settings-2")["name"] == "Settings"


# ---- /plan remembers whose trip, /go uses their marker --------------------------------------------------------------

def test_plan_from_a_creators_trip_remembers_the_creator_for_30_days_and_only_that(client, keys, mode):
    _, handle, _ = live_trip()
    r = client.get(f"/plan?to=la&{TRIP}&via={handle}", headers=seen_on(handle))
    cookie = r.headers["set-cookie"].lower()
    assert f"ga_via={handle}" in cookie and "max-age=2592000" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie and "secure" not in cookie
    assert "ga_via" not in client.get(f"/plan?to=la&{TRIP}&via=nobody", headers=seen_on("nobody")).headers.get("set-cookie", "")
    assert "ga_via" not in client.get(f"/plan?to=la&{TRIP}").headers.get("set-cookie", "")
    assert "ga_via" not in client.get(f"/plan?to=la&{TRIP}&via=" + "a" * 500, headers=seen_on("a" * 500)).headers.get("set-cookie", "")


def test_the_cookie_is_https_only_in_production(client, keys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_SECRET_KEY", "k" * 40)
    _, handle, _ = live_trip()
    assert "secure" in client.get(f"/plan?to=la&{TRIP}&via={handle}", headers=seen_on(handle)).headers["set-cookie"].lower()


def test_a_flight_booked_from_a_creators_trip_carries_their_marker_and_the_click_is_counted(client, keys, mode):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    first = flight_marker(client)
    assert first.startswith("555111.")
    assert first.split(".", 1)[1] == f"anon_hi_270305_flight_{handle.replace('-', '_')}"       # the SubID is still ours: family hash, place, day, lane, and now whose trip (F-195)
    assert affiliate.clicks_by_creator() == {handle: (1, 1)}


def test_stays_and_cars_still_go_through_our_account(client, keys, mode):
    """D-101: whether the partner-links API takes another account's marker with our token is not verified, so Klook never carries the creator's."""
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    loc = client.get(f"/go/hih1?to=hi&{TRIP}", follow_redirects=False).headers["location"]
    assert loc.startswith("https://klook.tpx.lv/x?sub=")
    (call,) = keys.calls
    assert call[2]["marker"] == 801445 and call[2]["trs"] == 596534 and "555111" not in str(call[2])
    assert affiliate.clicks_by_creator() == {handle: (1, 0)}      # a click, but not one that paid the creator


def test_without_a_marker_or_a_cookie_or_with_a_made_up_one_the_marker_is_gitaways(client, keys, mode):
    _, handle, owner = live_trip()
    assert flight_marker(client).startswith("801445.")                        # nobody planned from a trip
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    assert flight_marker(client).startswith("801445.")                        # the creator has no marker
    affiliate.set_marker(owner["user_id"], "555111")
    client.cookies.set("ga_via", "not-a-creator")
    assert flight_marker(client).startswith("801445.")                        # a cookie naming nobody
    client.cookies.set("ga_via", "x" * 80)
    assert flight_marker(client).startswith("801445.")                        # not even shaped like a handle
    assert affiliate.clicks_by_creator() == {handle: (1, 0)}


def test_a_creator_who_removes_their_marker_stops_being_paid_at_the_next_click(client, keys, mode):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    assert flight_marker(client).startswith("555111.")
    affiliate.set_marker(owner["user_id"], "")
    assert flight_marker(client).startswith("801445.")


def test_a_signed_out_click_still_pays_the_creator(client, keys, mode):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    marker = flight_marker(client)
    assert marker.startswith("555111.") and marker.split(".", 1)[1].startswith("anon_")


def test_the_cookie_is_set_only_when_the_click_came_from_that_creators_own_page(client, keys, mode):
    """F-182 L1: any link anywhere to /plan?via=<handle> used to set a 30-day cookie, so a pasted link could make a stranger's later bookings count for a creator."""
    row, handle, _ = live_trip()
    other, other_handle, _ = live_trip("lee@example.com", "Lee Park", "Two days in San Diego")
    url = f"/plan?to=la&{TRIP}&via={handle}"
    nowhere = [{}, {"referer": "https://evil.example/trips/" + row["slug"]}, {"referer": f"http://testserver/trips/{other['slug']}"}, {"referer": f"http://testserver/creators/{other_handle}"},
               {"referer": f"http://testserver/community"}, {"referer": f"http://testserver/creators/{handle}/x"}, {"referer": f"http://evil.example/creators/{handle}"}, {"referer": "not a url"}]
    for headers in nowhere:
        assert "ga_via" not in client.get(url, headers=headers).headers.get("set-cookie", ""), headers
    assert f"ga_via={handle}" in client.get(url, headers=seen_on(handle)).headers["set-cookie"]                           # their profile
    assert f"ga_via={handle}" in client.get(url, headers=seen_on(handle, row["slug"])).headers["set-cookie"]               # one of their trips
    assert "ga_via" not in client.get(url, headers=seen_on(handle, other["slug"])).headers.get("set-cookie", "")           # someone else's trip does not vouch for them


def test_clicks_are_counted_per_person_or_address_an_hour_so_one_script_cannot_inflate_a_creator(client, keys, mode, monkeypatch):
    monkeypatch.setattr(affiliate, "VIA_PER_WINDOW", 3)
    _, handle, _ = live_trip()
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    for _ in range(8):
        assert flight_marker(client)                                  # every click still goes through to the partner
    assert affiliate.clicks_by_creator() == {handle: (3, 0)}          # but at most 3 an hour from one address count


def test_a_signed_in_person_has_their_own_allowance_not_the_addresss(client, keys, mode, monkeypatch):
    monkeypatch.setattr(affiliate, "VIA_PER_WINDOW", 2)
    _, handle, _ = live_trip()
    sign_in(client, "ari")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    for _ in range(5):
        flight_marker(client)
    assert affiliate.clicks_by_creator() == {handle: (2, 0)}
    sign_in(client, "sam")
    client.cookies.set("ga_via", handle)
    for _ in range(5):
        flight_marker(client)
    assert affiliate.clicks_by_creator() == {handle: (4, 0)}


# ---- the trip page says who earns -----------------------------------------------------------------------------------

def test_the_trip_page_says_plainly_who_earns_with_and_without_a_marker(client, mode):
    row, handle, owner = live_trip()
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert re.search(r'id="who-earns"[^>]*>Bookings from this trip support GitAway\.<', page)
    affiliate.set_marker(owner["user_id"], "555111")
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert re.search(r'id="who-earns"[^>]*>Flights booked from this trip support Maya Chen\. Stays and things to do support GitAway for now\.<', page)
    assert "555111" not in page            # the marker itself is not shown to readers


def test_plan_this_trip_names_the_creator_in_its_link(client, mode):
    row, handle, _ = live_trip()
    page = client.get(f"/trips/{row['slug']}").text.replace("&amp;", "&")
    assert f"&via={handle}" in re.search(r'<a[^>]*id="plan-this"[^>]*>', page).group(0) or f"&via={handle}" in re.search(r'<a[^>]*href="/plan[^"]*"[^>]*id="plan-this"', page).group(0)


def test_a_sample_trip_makes_no_claim_about_who_earns(client):
    from gitaway import itineraries
    page = client.get(f"/trips/{next(iter(itineraries.ITINERARIES))}").text
    assert "who-earns" not in page


# ---- F-195: the creator's handle is in the SubID, and a Tickets click on their own page counts for them ------------------------

def test_the_creators_handle_is_in_the_subid_of_flights_and_of_klook_clicks(client, keys, mode):
    _, handle, _ = live_trip(name="Maya Chen")
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    flight = flight_marker(client).split(".", 1)[1]
    client.get(f"/go/hih1?to=hi&{TRIP}", follow_redirects=False)
    stay = keys.calls[-1][2]["links"][0]["sub_id"]
    assert flight == f"anon_hi_270305_flight_{handle.replace('-', '_')}" and stay == f"anon_hi_270305_stay_{handle.replace('-', '_')}"
    assert handle == "maya-chen" and len(stay) < 100


def test_the_longest_handle_still_fits_travelpayouts_subid():
    from gitaway import catalog
    from gitaway.partners import log
    trip = catalog.sample_trip("hi")
    assert len(log.sub_id({"tenant_id": "t"}, trip, catalog.offer("hif1", trip), "a" * 40)) <= 100       # Travelpayouts allows 4096; we stay readable


def test_a_subid_uses_only_digits_letters_and_underscores_as_travelpayouts_asks():
    """F-195 review: their help says SubIDs may hold digits, Latin letters and `_` only, so a hyphenated handle must not be sent as it is."""
    from gitaway import catalog
    from gitaway.partners import log
    trip = catalog.sample_trip("hi")
    assert log.sub_id({"tenant_id": "t"}, trip, catalog.offer("hif1", trip), "maya-chen-2") == log.sub_id({"tenant_id": "t"}, trip, catalog.offer("hif1", trip)) + "_maya_chen_2"
    assert re.fullmatch(r"[0-9a-zA-Z_]+", log.sub_id({"tenant_id": "t"}, trip, catalog.offer("hif1", trip), "maya-chen-2"))


def test_no_creator_means_no_handle_in_the_subid(client, keys, mode):
    assert flight_marker(client).split(".", 1)[1] == "anon_hi_270305_flight"


def test_a_tickets_click_on_a_creators_own_page_counts_for_them_and_remembers_them(client, keys, mode):
    row, handle, _ = live_trip()
    url = f"/go/search-todo?to=la&{TRIP}&focus=disney&via={handle}"
    r = client.get(url, headers=seen_on(handle, row["slug"]), follow_redirects=False)
    assert r.status_code == 302 and f"ga_via={handle}" in r.headers["set-cookie"]
    assert keys.calls[0][2]["links"][0]["sub_id"] == f"anon_la_270305_todo_{handle.replace('-', '_')}"
    assert affiliate.clicks_by_creator() == {handle: (1, 0)}      # Klook pays GitAway (D-101), so not "with their marker"


def test_a_pasted_tickets_link_names_nobody(client, keys, mode):
    row, handle, _ = live_trip()
    r = client.get(f"/go/search-todo?to=la&{TRIP}&via={handle}", headers={"referer": "https://evil.example/x"}, follow_redirects=False)
    assert "set-cookie" not in r.headers and keys.calls[0][2]["links"][0]["sub_id"] == "anon_la_270305_todo"
    assert affiliate.clicks_by_creator() == {}


# ---- F-195: the Tickets and things to do card on a creator's trip page, and what "Plan this trip" carries --------------------

def todo_link(html):
    m = re.search(r'<a[^>]*href="(/go/search-todo[^"]*)"[^>]*>', html)
    return m.group(1).replace("&amp;", "&") if m else None


def test_a_creators_trip_page_has_an_honest_tickets_card(client, mode, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    row, handle, _ = live_trip(name="Maya Chen")
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    link = todo_link(page)
    assert link and link.startswith("/go/search-todo?to=la&d=") and link.endswith(f"&a=2&via={handle}") and "focus" not in link
    words = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    assert "Tickets and things to do" in words and "Los Angeles attractions" in words and "Things to do on Klook" in words
    assert "This link supports GitAway, not Maya" in words      # Klook does not carry a creator's marker (D-101)


def test_a_disneyland_trip_page_offers_disneyland_tickets(client, mode, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    row, handle, _ = live_trip(title="Three days at Disneyland with a toddler")
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert "&focus=disney&via=" in todo_link(page) and "Disneyland Resort tickets" in page and "See tickets on Klook" in page
    plan = re.search(r'<a[^>]*id="plan-this"[^>]*href="([^"]+)"|<a[^>]*href="([^"]+)"[^>]*id="plan-this"', page)
    assert "focus=disney" in (plan.group(1) or plan.group(2))


def test_no_tickets_card_where_there_is_nowhere_to_send_anyone(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")                       # production without a marker: no /go/ link anywhere
    row, _, _ = live_trip()
    assert "/go/" not in client.get(f"/trips/{row['slug']}").text


def test_a_place_we_cannot_plan_has_no_tickets_card(client, mode, monkeypatch):
    from dataclasses import replace
    from gitaway import community, itinerary_view
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    row, _, _ = live_trip()
    trip = community.trip_of(row)
    assert "Tickets and things to do" in without_bar(client.get(f"/trips/{row['slug']}").text)               # the plannable one has it
    from fasthtml.common import to_xml
    assert "Tickets and things to do" not in to_xml(itinerary_view.itinerary_body(replace(trip, plan_to="")))    # Tahoe, Maui: nothing to plan, nothing to link


def test_plan_this_trip_names_the_place_the_focus_and_the_creator_and_leaves_the_party_to_the_honest_page():
    from gitaway import hub
    row, handle, _ = live_trip(title="Disneyland for little ones")
    from gitaway import community
    trip = community.trip_of(row)
    q = parse_qs(urlsplit(hub.plan_href(trip)).query)
    assert (q["to"], q["a"], q["focus"], q["via"]) == (["la"], ["2"], ["disney"], [handle]) and not {"k", "home"} & set(q)
    assert "focus" not in parse_qs(urlsplit(hub.plan_href(community.trip_of(live_trip("lee@example.com", "Lee Park", "Two days in San Diego")[0]))).query)


@pytest.mark.parametrize("title,place,focus", [("Disneyland with toddlers", "Los Angeles, California", "disney"), ("Anaheim and the parks", "Anaheim, California", "disney"),
                                               ("Walt Disney World with kids", "Los Angeles, California", ""), ("Disneyland Paris in winter", "Los Angeles, California", ""),
                                               ("Three days in Santa Monica", "Los Angeles, California", ""),
                                               ("A day at Walt Disney Concert Hall", "Los Angeles, California", ""), ("Disney Hall and the Broad", "Los Angeles, California", ""),
                                               ("Disneyland day with the kids", "Los Angeles, California", "disney"), ("Disney Land, the easy way", "Los Angeles, California", "disney")])
def test_a_trip_is_a_disneyland_trip_only_when_it_says_so_and_is_in_california(title, place, focus):
    from gitaway import hub
    from gitaway.itineraries import Itinerary
    trip = Itinerary(slug="x", title=title, headline=title, accent="", place=place, lede="", days=[], plan_to="la", plan_days=3)
    assert hub.focus_of(trip) == focus
    assert hub.focus_of(Itinerary(slug="x", title=title, headline=title, accent="", place=place, lede="", days=[], plan_to="hi")) == ""


# ---- F-195: forking a creator's trip remembers them too ---------------------------------------------------------------------

def fork(client, slug):
    return client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=True)


def test_a_family_that_forks_a_creators_trip_books_for_them_not_only_one_that_tapped_plan_this_trip(client, keys, mode):
    row, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    sign_in(client, "ari")
    assert "ga_via" not in client.cookies and "ga_via" not in client.get(f"/trips/{row['slug']}").headers.get("set-cookie", "")        # reading is not forking
    fork(client, row["slug"])
    assert client.cookies.get("ga_via") == handle
    assert flight_marker(client).startswith("555111.")
    assert affiliate.clicks_by_creator() == {handle: (1, 1)}


def test_forking_from_signed_out_goes_through_sign_in_and_still_remembers_them(client, keys, mode):
    row, handle, _ = live_trip()
    r = client.get(f"/signin?next=/trips/{row['slug']}&intent=fork")
    assert r.status_code == 200 and "ga_via" not in client.cookies
    sign_in(client, "ari", next=f"/trips/{row['slug']}", intent="fork")
    client.get(f"/trips/{row['slug']}")
    assert client.cookies.get("ga_via") == handle


def test_the_fork_cookie_is_the_same_cookie_30_days_http_only(client, keys, mode):
    row, handle, _ = live_trip()
    sign_in(client, "ari")
    client.post("/fork", data={"next": f"/trips/{row['slug']}"}, follow_redirects=False)
    cookie = client.get(f"/trips/{row['slug']}").headers["set-cookie"].lower()
    assert f"ga_via={handle}" in cookie and "max-age=2592000" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie


def test_forking_a_sample_trip_remembers_nobody(client, keys):
    sign_in(client, "ari")
    r = client.post("/fork", data={"next": "/trips/sun-and-tacos"}, follow_redirects=True)
    assert "ga_via" not in client.cookies


# ---- F-194 audit: the captain's check is per trip, not per creator ----------------------------------------------------------------

@pytest.fixture(params=["pending", "unverified"])
def state(request):
    """The two ways a trip waits for the captain: a claim by someone not at the post's site, and an open import whose owner is unchecked."""
    return request.param


def two_trips(state="pending"):
    """One creator with a marker, an approved trip and a trip still waiting for the captain."""
    approved, handle, owner = live_trip()
    waiting, _, _ = live_trip(title="Two days in Santa Barbara")
    affiliate.set_marker(owner["user_id"], "555111")
    community.set_review(waiting["slug"], state)
    return approved, waiting, handle


def test_a_booking_from_a_trip_waiting_for_approval_never_carries_the_creators_marker_even_with_an_approved_one(client, keys, mode, state):
    approved, waiting, handle = two_trips(state)
    url = f"/plan?to=hi&{TRIP}&via={handle}"
    r = client.get(url, headers=seen_on(handle, waiting["slug"]))
    assert "ga_via" not in r.headers.get("set-cookie", "")
    assert flight_marker(client).startswith("801445.")                                    # ours: the trip it came from is not checked yet
    client.get(url, headers=seen_on(handle, approved["slug"]))
    assert flight_marker(client).startswith("555111.")                                    # the same creator's approved trip pays them


def test_tapping_plan_on_a_waiting_trip_forgets_an_earlier_cookie_from_the_creators_approved_one(client, keys, mode, state):
    approved, waiting, handle = two_trips(state)
    url = f"/plan?to=hi&{TRIP}&via={handle}"
    client.get(url, headers=seen_on(handle, approved["slug"]))
    assert client.cookies.get("ga_via") == handle
    client.get(url, headers=seen_on(handle, waiting["slug"]))
    assert "ga_via" not in client.cookies
    assert flight_marker(client).startswith("801445.")


def test_a_tickets_click_on_a_waiting_trip_pays_nobody_and_is_not_counted_for_the_creator(client, keys, mode, state):
    approved, waiting, handle = two_trips(state)
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle, approved["slug"]))
    loc = client.get(f"/go/hif1?to=hi&{TRIP}&via={handle}", headers=seen_on(handle, waiting["slug"]), follow_redirects=False).headers["location"]
    assert parse_qs(urlsplit(loc).query)["marker"][0].startswith("801445.")
    assert "ga_via" not in client.cookies and affiliate.clicks_by_creator() == {}


def test_forking_a_waiting_trip_remembers_nobody(client, keys, mode, state):
    approved, waiting, handle = two_trips(state)
    sign_in(client, "ari")
    fork(client, waiting["slug"])
    assert "ga_via" not in client.cookies
    fork(client, approved["slug"])
    assert client.cookies.get("ga_via") == handle
    fork(client, waiting["slug"])                                           # forking a trip that waits forgets the cookie an approved one left
    assert "ga_via" not in client.cookies


def test_the_page_of_a_waiting_trip_says_bookings_support_gitaway_and_the_approved_ones_say_the_creator(client, mode, state):
    approved, waiting, _ = two_trips(state)
    says = lambda row: re.search(r'id="who-earns"[^>]*>([^<]*)<', without_bar(client.get(f"/trips/{row['slug']}").text)).group(1)      # noqa: E731
    assert says(waiting) == "Bookings from this trip support GitAway."
    assert says(approved) == "Flights booked from this trip support Maya Chen. Stays and things to do support GitAway for now."


def test_a_creator_whose_only_trips_wait_earns_nothing_even_from_their_profile(client, keys, mode, state):
    row, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    community.set_review(row["slug"], state)
    client.get(f"/plan?to=hi&{TRIP}&via={handle}", headers=seen_on(handle))
    assert flight_marker(client).startswith("801445.")
    community.set_review(row["slug"], "approved")
    assert flight_marker(client).startswith("555111.")
