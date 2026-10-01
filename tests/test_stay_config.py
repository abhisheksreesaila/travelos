"""F-026: room types, add-ons and the pick URL, priced by the catalog (the page never does arithmetic)."""
import json
import re
from urllib.parse import parse_qs, quote as q, urlparse

import pytest

from gitaway import catalog
from tests.test_signin import session_data, sign_in, tid

DONE = "f=f1&h=h1&c=c1&rooms=ok2&add=bf"  # the done-means pick: The Tidewater, Ocean-view King x2 + breakfast


# ---- catalog ---------------------------------------------------------------------------------------------------

def test_every_stay_has_three_rooms_and_its_default_room_sleeps_the_party():
    for stay in catalog.offers("stay"):
        d = catalog.stay_detail(stay.id)
        assert len(d.rooms) == 3
        assert d.rooms[0].sleeps >= catalog.PARTY == 4
        assert d.rooms[0].price_cents == stay.price_cents  # the default room is the stay's list price
        assert d.chips and d.highlights and d.policy and len(d.samples) == 4 and d.pois


def test_the_default_stay_keeps_todays_totals():
    assert catalog.quote("f1", "h1", "c1").total_cents == 308_800
    assert catalog.stay_pick("h1").cents == 154_000
    assert catalog.stay_pick("h1").summary == "City-view Double Queen"


def test_ocean_view_king_twice_plus_breakfast_is_the_done_means_stay():
    pick = catalog.stay_pick("h1", "ok2", "bf")
    assert pick.cents == 244_000 and catalog.money(pick.cents) == "$2,440"
    assert pick.summary == "Ocean-view King ×2 + Breakfast"
    total = catalog.quote("f1", "h1", "c1", pick).total_cents
    assert catalog.money(total) == "$3,988" and total == 123_600 + 244_000 + 31_200


def test_the_quote_itemizes_rooms_and_add_ons_per_lane():
    q_ = catalog.quote("f1", "h1", "c1", catalog.stay_pick("h1", "ok2", "bfpk"))
    stay = [i for i in q_.items if i.lane == "stay"]
    assert [(i.name, i.qty, i.cents) for i in stay] == [
        ("Ocean-view King", 2, 212_000), ("Breakfast for 4", 1, 32_000), ("Parking, 4 nights", 1, 18_000)]
    assert sum(i.cents for i in q_.items) == q_.total_cents
    assert {i.lane for i in q_.items} == {"flight", "stay", "car"}
    assert q_.lane_cents("stay") == 262_000


@pytest.mark.parametrize("rooms,add,code,addcode", [
    ("", None, "", ""),                      # nothing given: the default
    (None, None, "", ""),
    ("zz9", None, "", ""),                   # junk
    ("ok5", None, "", ""),                   # count out of range
    ("ok0", None, "", ""),                   # no rooms at all
    ("ok1", None, "", ""),                   # sleeps 2 of 4: under capacity is repaired to the default
    ("cq1", "", "", ""),
    ("ok2", None, "ok2", ""),
    ("ok2fs1", None, "ok2fs1", ""),          # catalog order, two rooms types
    ("fs1ok2", None, "ok2fs1", ""),
    ("ok2ok1", None, "ok2", ""),             # the first count of a repeated room wins
    ("OK2", None, "", ""),                   # ids are lower case
    ("ok2", "bf", "ok2", "bf"),
    ("ok2", "pkbf", "ok2", "bfpk"),
    ("ok2", "bfbf", "ok2", "bf"),
    ("ok2", "xx", "ok2", ""),                # unknown add-on dropped
    ("ok2", "b", "ok2", ""),
    ("cq2", None, "cq2", ""),
    ("cq1", "lc", "", "lc"),
])
def test_bad_or_missing_picks_fall_back_to_the_default(rooms, add, code, addcode):
    p = catalog.stay_pick("h1", rooms, add)
    assert (p.rooms_code, p.add_code) == (code, addcode)
    assert p.fits


def test_a_room_of_another_stay_is_not_valid_here():
    assert catalog.stay_pick("h2", "ok2").rooms_code == ""  # ok is the Tidewater's Ocean-view King
    assert catalog.stay_pick("h2", "gs2").rooms_code == "gs2"


def test_an_under_capacity_choice_can_be_looked_at_but_never_priced_into_a_pick():
    raw = catalog.parse_stay("h1", "ok1", "")
    assert not raw.fits and raw.sleeps == 2 and raw.fit_text == "Sleeps 2 of 4 · add a room" and raw.fit == "short"
    none = catalog.parse_stay("h1", "", "")
    assert none.fit == "none" and none.fit_text == "Pick at least one room" and none.summary == "No room picked yet"
    assert catalog.parse_stay("h1", "ok2", "").fit_text == "Room for all 4"
    assert catalog.stay_pick("h1", "ok1").fits  # repaired


def test_quote_refuses_a_stay_pick_for_another_stay():
    with pytest.raises(KeyError):
        catalog.quote("f1", "h2", "c1", catalog.stay_pick("h1", "ok2"))


def test_quote_refuses_a_pick_that_sleeps_fewer_than_the_party():
    with pytest.raises(ValueError):
        catalog.quote("f1", "h1", "c1", catalog.parse_stay("h1", "ok1", ""))


def test_default_stay_pick_url_params_are_empty_and_others_compact():
    assert catalog.stay_pick("h1").query == ""
    assert catalog.stay_pick("h1", "ok2", "bf").query == "&rooms=ok2&add=bf"
    assert catalog.stay_pick("h1", "cq1", "lc").query == "&add=lc"
    assert catalog.stay_pick("h1", "cq2").query == "&rooms=cq2"


def test_the_cheapest_full_trip_is_flight_f4_stay_h3_and_car_c1():
    assert catalog.cheapest().total_cents == 217_200


# ---- /plan ----------------------------------------------------------------------------------------------------

def stay_article(html, stay_id):
    m = re.search(r'<article[^>]*data-detail="%s"[^>]*>.*?</article>' % stay_id, html, re.S)
    assert m
    return m.group(0)


def test_done_means_total_on_the_plan_page_and_through_reload(client):
    h = client.get(f"/plan?{DONE}").text
    assert re.search(r'id="ws-total"[^>]*>\$3,988<', h)
    assert re.search(r'data-slot-price="stay"[^>]*>\$2,440<', h)
    assert "Ocean-view King ×2 + Breakfast" in h
    a = stay_article(h, "h1")
    assert re.search(r'data-room="ok"[^>]*data-count="2"', a) and re.search(r'data-addon="bf"[^>]*aria-pressed="true"', a)
    assert re.search(r'data-addon="pk"[^>]*aria-pressed="false"', a)
    assert re.search(r'data-choose="h1"[^>]*>\s*Chosen', a)


def test_old_pick_urls_keep_working(client):
    h = client.get("/plan?f=f2&h=h3&c=c2").text
    assert re.search(r'id="ws-total"[^>]*>%s<' % re.escape(catalog.money(catalog.quote("f2", "h3", "c2").total_cents)), h)


def test_junk_rooms_on_plan_fall_back_to_the_default_room(client):
    for extra in ("&rooms=zz9", "&rooms=ok1", "&rooms=&add=xx", "&rooms=ok9&add=%3Cscript%3E"):
        h = client.get(f"/plan?f=f1&h=h1&c=c1{extra}").text
        assert re.search(r'id="ws-total"[^>]*>\$3,088<', h), extra
        assert "<script>" not in h.split('id="ws-data"')[0].split("ws-choosebar")[-1]


def test_stay_panels_show_rooms_add_ons_policy_photos_and_the_map_tab(client):
    a = stay_article(client.get("/plan").text, "h1")
    for text in ("Pick your rooms", "City-view Double Queen", "Ocean-view King", "Family suite", "2 queen beds", "1 king bed",
                 "sleeps 4", "sleeps 2", "sleeps 5", "$1,540", "$1,060", "$1,980", "Room for all 4", "Add-ons", "Breakfast for 4", "+$320",
                 "Late checkout, 2 PM", "+$40", "Parking, 4 nights", "+$180", "Free cancellation until Oct 13",
                 "Explore the area in 3D", "Photos", "Sample photo · Lobby", "Sample photo · Pool", "Sample photo · Room",
                 "Sample photo · Breakfast", "3 min walk", "Kids eat free at the pool café", "Sea view", "Crib available"):
        assert text in a, text
    assert 'role="tablist"' in a and a.count('role="tab"') == 2
    assert "Illustrated map · not to scale" not in a  # the explorer loads on first open only
    assert "Loading the aerial view" not in a
    assert 'data-map-src' in a  # where it loads from


def test_every_photo_referenced_exists_and_is_credited(client):
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "assets/photos"
    credits = (root / "CREDITS.md").read_text()
    html = client.get("/plan").text
    names = set(re.findall(r"/assets/photos/([\w.-]+\.jpg)", html))
    assert len(names) >= 6
    for n in names:
        assert (root / n).stat().st_size > 10_000 and n in credits, n
    for n in names:
        assert (root / n).stat().st_size < 300_000


def test_sample_photos_are_always_labelled_and_never_claim_to_be_the_hotel(client):
    html = client.get("/plan").text
    a = stay_article(html, "h1")
    for m in re.finditer(r'<figure[^>]*data-sample[^>]*>(.*?)</figure>', a, re.S):
        assert "Sample photo" in m.group(1)
    # a tile with no photo yet says so instead of claiming to be a sample photo
    kitchen = re.search(r'<figure[^>]*data-sample="Kitchen"[^>]*>(.*?)</figure>', stay_article(html, "h2"), re.S).group(1)
    assert "Photo coming · Kitchen" in kitchen and "Sample photo" not in kitchen and "<img" not in kitchen
    assert re.findall(r'alt="([^"]*)"', a)
    for alt in re.findall(r'<img[^>]*alt="([^"]*)"', a):
        assert "sample" in alt.lower() or "not the hotel" in alt.lower() or alt == ""


def test_the_explorer_fragment_loads_only_on_request(client):
    r = client.get("/plan/explore?h=h1")
    assert r.status_code == 200
    for text in ("Illustrated map · not to scale", "Back to the hotel", "Turn the view", "Santa Monica Beach", "Third Street Promenade",
                 "3 min walk", "Metro E Line"):
        assert text in r.text, text
    assert r.text.count("data-poi=") >= 12  # each point twice: standing pin and list row
    assert client.get("/plan/explore?h=zz").status_code == 200  # falls back to the default stay


# ---- /plan/quote ---------------------------------------------------------------------------------------------

def quote_json(client, qs):
    r = client.get("/plan/quote?" + qs)
    assert r.status_code == 200
    return r.json()


def test_quote_route_returns_the_ledger_figures_from_the_catalog(client):
    j = quote_json(client, DONE)
    assert j["ledger"]["total"] == "$3,988"
    assert j["ledger"]["slots"]["stay"] == {"name": "The Tidewater", "price": "$2,440", "sub": "Ocean-view King ×2 + Breakfast"}
    assert j["ledger"]["slots"]["flight"]["price"] == "$1,236" and j["ledger"]["slots"]["car"]["price"] == "$312"
    assert j["ledger"]["delta"] == "$1,816 more than the cheapest flight, stay and car" and j["ledger"]["cheapest"] is False
    assert j["ledger"]["url"] == "/plan?f=f1&h=h1&c=c1&rooms=ok2&add=bf"
    assert j["ledger"]["book"].startswith("/signin?next=")
    assert "rooms%3Dok2%26add%3Dbf" in j["ledger"]["book"]
    assert j["stay"]["summary"] == "Ocean-view King ×2 + Breakfast" and j["stay"]["price"] == "$2,440"
    assert j["stay"]["fits"] is True and j["stay"]["fit_text"] == "Room for all 4"
    assert j["stay"]["rooms"] == {"cq": 0, "ok": 2, "fs": 0} and j["stay"]["add"] == ["bf"]


def test_quote_route_signed_in_books_straight_to_the_sheet(client):
    sign_in(client)
    j = quote_json(client, DONE)
    assert j["ledger"]["book"] == "/plan/pay?f=f1&h=h1&c=c1&rooms=ok2&add=bf"


def test_quote_route_defaults_and_ignores_junk(client):
    j = quote_json(client, "f=zz&h=h1&c=c1&rooms=zz&add=xx")
    assert j["ledger"]["total"] == "$3,088" and j["ledger"]["url"] == "/plan?f=f1&h=h1&c=c1"
    assert j["stay"]["rooms"] == {"cq": 1, "ok": 0, "fs": 0}
    assert quote_json(client, "")["ledger"]["total"] == "$3,088"


def test_quote_route_describes_an_under_capacity_edit_but_keeps_the_ledger_on_a_real_pick(client):
    j = quote_json(client, "f=f1&h=h1&c=c1&rooms=ok1&add=bf")
    assert j["stay"]["fits"] is False and j["stay"]["fit_text"] == "Sleeps 2 of 4 · add a room" and j["stay"]["fit"] == "short"
    assert j["stay"]["summary"] == "Ocean-view King + Breakfast" and j["stay"]["price"] == "$1,380"
    assert j["ledger"]["total"] == "$3,408"  # the ledger prices what can be booked: the default room plus the add-on
    j = quote_json(client, "f=f1&h=h1&c=c1&rooms=&add=")
    assert j["stay"]["fit"] == "none" and j["stay"]["summary"] == "No room picked yet" and j["stay"]["price"] == "$0"


def test_quote_route_totals_match_the_catalog_for_every_room_count(client):
    for n in range(0, 5):
        j = quote_json(client, f"f=f3&h=h2&c=c2&rooms=gs{n}")
        want = catalog.parse_stay("h2", f"gs{n}" if n else "", "")
        assert j["stay"]["price"] == catalog.money(want.cents)


# ---- pay ---------------------------------------------------------------------------------------------------

def test_the_pay_sheet_itemizes_rooms_and_add_ons(client):
    sign_in(client)
    html = client.get(f"/plan/pay?{DONE}").text
    items = re.findall(r'<li class="pay-item">\s*<span class="pay-item-name">([^<]*)</span>\s*<span class="pay-item-price">([^<]*)</span>', html)
    assert items == [("Ocean-view King ×2", "$2,120"), ("Breakfast for 4", "$320")]
    assert re.search(r'pay-name">The Tidewater</span>.*?class="pay-price">\$2,440<', html, re.S)
    assert "Pay $3,988" in html
    assert 'name="rooms" value="ok2"' in html and 'name="add" value="bf"' in html
    assert 'href="/plan?f=f1&amp;h=h1&amp;c=c1&amp;rooms=ok2&amp;add=bf"' in html  # back to my picks keeps the rooms


def test_default_pay_sheet_has_no_extra_params(client):
    sign_in(client)
    html = client.get("/plan/pay?f=f1&h=h1&c=c1").text
    assert "Pay $3,088" in html and "City-view Double Queen" in html and 'value="ok2"' not in html


def test_paying_records_the_rooms_and_recomputes_the_total(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "rooms": "ok2", "add": "bf", "total_cents": "1"})
    b = session_data(client)["bookings"][tid("ari")]
    assert b["total_cents"] == 398_800 and b["rooms"] == "ok2" and b["add"] == "bf"
    assert "Ocean-view King ×2 + Breakfast" in client.get("/booked").text


def test_paying_refuses_under_capacity_by_repairing_to_the_default_room(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "rooms": "ok1", "add": "bf"})
    b = session_data(client)["bookings"][tid("ari")]
    assert b["total_cents"] == 308_800 + 32_000 and b["rooms"] == ""  # the short rooms became the default; the add-on stays


def test_paying_a_different_room_replaces_the_booking(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    first = session_data(client)["bookings"][tid("ari")]
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "rooms": "ok2"})
    second = session_data(client)["bookings"][tid("ari")]
    assert second["id"] != first["id"] and second["total_cents"] == 123_600 + 212_000 + 31_200


def test_signed_out_pay_keeps_the_rooms_through_sign_in(client):
    r = client.get(f"/plan/pay?{DONE}", follow_redirects=False)
    nxt = parse_qs(urlparse(r.headers["location"]).query)["next"][0]
    assert nxt == f"/plan/pay?{DONE}"
    r = sign_in(client, next=nxt, intent="pay")
    assert r.headers["location"] == f"/plan/pay?{DONE}"
    assert "Pay $3,988" in client.get(r.headers["location"]).text


# ---- calendar ------------------------------------------------------------------------------------------------

def test_the_calendar_respects_the_picked_rooms(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "rooms": "ok2", "add": "bf"})
    html = client.get("/calendar?view=days").text
    assert "Check in · The Tidewater · Ocean-view King ×2" in html
    assert re.search(r'class="cal-tripline"[^>]*>[^<]*\$3,988<', html)
    assert "Ocean-view King ×2 + Breakfast" in html  # the welcome note


# ---- page script contract (string checks; the behaviour was walked in a browser) -----------------------------------

def test_the_script_asks_the_server_for_figures_and_loads_the_explorer_lazily(client):
    js = client.get("/assets/js/workspace.js").text
    assert "/plan/quote?" in js and "data.quotes" not in js
    assert "loadExplore" in js and "dataset.mapSrc" in js and "Loading the aerial view" in js
    assert "still.matches" in js  # reduced motion: no skeleton wait
    assert "discardDrafts" in js  # edits that were not chosen do not outlive the split view


def test_reduced_motion_stops_the_fly_to_and_the_skeleton_sweep():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "assets/css"
    ws = (root / "workspace.css").read_text()
    assert "@media (prefers-reduced-motion: reduce) {\n  .ws-plane, .ws-pin, .ws-addon { transition: none; }" in ws
    base = (root / "base.css").read_text()
    assert "animation: none !important" in base[base.rindex("prefers-reduced-motion"):]  # the skeleton sweep


def test_the_choose_button_starts_enabled_for_a_default_room_and_every_stay_has_an_editor(client):
    html = client.get("/plan").text
    for stay in catalog.offers("stay"):
        a = stay_article(html, stay.id)
        assert "disabled" not in re.search(r'<button[^>]*data-choose="%s"[^>]*>' % stay.id, a).group(0)
        assert a.count('class="ws-room"') == 3 and a.count("data-addon=") == 3
        assert re.search(r'data-count="1"', a) and a.count('data-count="0"') == 2


# ---- map pins (measured in a browser at 1440-320; these keep the data inside what was measured) -----------------------

def test_map_points_keep_clear_of_each_other_and_of_the_view_edges():
    for stay in catalog.offers("stay"):
        pois = catalog.stay_detail(stay.id).pois
        for p in pois:
            assert 18 <= p.x <= 72 and 33 <= p.y <= 82, (stay.id, p.label)  # inside the view centred on the hotel
        for i, a in enumerate(pois):
            for b in pois[i + 1:]:
                assert abs(a.x - b.x) >= 16 or abs(a.y - b.y) >= 16, (stay.id, a.label, b.label)  # labels are ~15% wide and tall


def test_the_map_controls_sit_in_a_bar_under_the_view_not_over_the_pins(client):
    frag = client.get("/plan/explore?h=h1").text
    view, bar = frag.index('class="ws-viewport"'), frag.index('class="ws-mapbar"')
    assert view < bar and frag.index("ws-mapbtn") > bar and frag.index("Illustrated map") > bar
    assert frag.index("ws-pin") < bar  # the pins are in the view
    assert 'class="ws-pin-label"' in frag  # narrow maps show the pins as icons and keep the name for screen readers


def test_the_script_resets_the_stay_it_leaves_and_holds_choose_during_an_edit(client):
    js = client.get("/assets/js/workspace.js").text
    assert "resetPanel(pick.stay)" in js
    assert "panel.querySelector('.ws-choose').disabled = true" in js


def test_a_failed_price_request_frees_choose_and_says_so(client):
    js = client.get("/assets/js/workspace.js").text
    assert "quoteFailed" in js and "panel.dataset.fits" in js
    a = stay_article(client.get("/plan").text, "h1")
    assert re.search(r'data-cb-err[^>]*role="status"[^>]*aria-live="polite"[^>]*hidden', a)
    assert "Price didn&#x27;t load, try again" in a or "Price didn't load, try again" in a


def test_a_failed_price_request_puts_the_editor_back_to_the_last_confirmed_setup(client):
    js = client.get("/assets/js/workspace.js").text
    body = js[js.index("function quoteFailed"):]
    body = body[:body.index("data-cb-err")]
    assert "panel.dataset.rooms" in body and "panel.dataset.add" in body and "card.dataset.count" in body and "aria-pressed" in body
