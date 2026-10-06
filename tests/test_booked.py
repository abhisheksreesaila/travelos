"""F-093: bookings open in place; filters; Help leaves the tab bar. A tap on a booking line (hotel check in or out, flight, car pick up or drop off) opens a sheet over the
day at /trip/canvas?day=N&booked=<block id>, with everything Help showed for it; the week's bookings open the same sheet; the Plans | Hotels | Flights | Car | Chats row
is on the week and the day; Help is off the tab bar and SOS in the heading opens the emergency sheet. The trip is the template import (Fri Oct 16 to Tue Oct 20 in Los
Angeles: flights, the Santa Monica hotel, a Hertz car) and, for the demo cases, the sample booking."""

import re
from html import unescape

import pytest

from gitaway import passes, phones
from tests.test_calendar import book
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_members import addr, browser, invite
from tests.test_passes import add_pass, pdf
from tests.test_signin import person, sign_in
from tests.test_trip_import import imported
from tests.test_trip_canvas import bare, tag, text


@pytest.fixture
def trip(client):
    imported(client)
    return client


@pytest.fixture
def crew(trip):
    ed_mail, vi_mail = addr("ed"), addr("vi")
    invite(trip, ed_mail, "editor"), invite(trip, vi_mail, "viewer")
    ed, vi = browser(trip), browser(trip)
    sign_in(ed, ed_mail), sign_in(vi, vi_mail)
    return trip, ed, vi


def sheet_of(html):
    """The booking sheet's markup (from its wrapper to the end of the section)."""
    return html[html.index('class="cz-sheet cz-sheet-bk'):]


def opened(client, bid, day=0):
    r = client.get(f"/trip/canvas?day={day}&booked={bid}")
    assert r.status_code == 200
    return bare(r.text)


def first_leg_key(session):
    return passes.flights(session)[0]["key"]


# ---- the booking lines open the sheet -------------------------------------------------------------------------------------------

def test_every_booking_line_on_the_day_opens_its_sheet_in_place_and_no_line_goes_to_help(trip):
    page = bare(trip.get("/trip/canvas?day=0").text)
    lines = re.findall(r'<a\b[^>]*class="cz-bk[ "][^>]*>', page)
    assert len(lines) == 3
    for a in lines:
        assert re.search(r'href="/trip/canvas\?day=0&amp;booked=b-[a-z-]+"', a) and 'data-zoom="in"' in a and "/trip/help" not in a
        assert re.search(r'data-zk="bkg-b-[a-z-]+"', a)
    assert "/trip/help" not in re.sub(r'<a[^>]*id="sos[^>]*>', "", "".join(lines))


def test_the_sheet_is_a_level_over_the_day_and_a_fragment_for_the_script(trip):
    full = opened(trip, "b-in")
    assert 'data-level="step"' in full and 'data-day="0"' in full and 'class="cz-sheet-wrap"' in full and 'id="cz-app"' in full
    assert "Friday" in text(full)                                   # the day is still behind it
    frag = bare(trip.get("/trip/canvas?day=0&booked=b-in&frag=1").text)
    assert frag.startswith("<section") and 'class="cz-sheet cz-sheet-bk' in frag and "<html" not in frag
    assert 'data-zk="bkg-b-in"' in frag and 'data-zout="bkg-b-in"' in frag


def test_a_booking_the_trip_does_not_have_goes_back_to_the_week(trip):
    r = trip.get("/trip/canvas?day=0&booked=b-nope", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas")
    assert trip.get("/trip/canvas?day=0&booked=b-nope&frag=1").status_code == 404


def test_the_sheet_opens_on_the_day_of_the_booking_even_with_another_day_in_the_address(trip):
    page = bare(trip.get("/trip/canvas?day=2&booked=b-out2").text)
    assert 'data-day="4"' in page and "Hotel" in text(sheet_of(page)) or "Example Hotel" in text(sheet_of(page))


# ---- hotel -----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bid,day,word", [("b-in", 0, "Check in"), ("b-out2", 4, "Check out")])
def test_the_hotel_sheet_has_what_help_showed(trip, bid, day, word):
    sheet = sheet_of(opened(trip, bid, day))
    t = text(sheet)
    assert "The Example Hotel Santa Monica" in t and "123 Ocean Ave, Santa Monica, CA 90401" in t and word in t
    assert "3:00 PM" in t and "11:00 AM" in t                           # check in and check out times
    assert 'href="tel:+13105550100"' in sheet and "Front desk" in t
    assert "maps" in unescape(tag(sheet, "hp-directions")) and "Directions" in t
    assert re.search(r"<details[^>]*hp-conf", sheet) and "987654321" in sheet   # the number is in the page but behind a tap
    assert "Passes" not in t


def test_an_editor_can_add_or_fix_the_hotel_phone_from_the_sheet_and_comes_back_to_it(trip):
    sheet = sheet_of(opened(trip, "b-in"))
    form = re.search(r'<form[^>]*action="/trip/help/phone".*?</form>', sheet, re.S).group(0)
    back = re.search(r'name="next" value="([^"]+)"', form).group(1)
    assert unescape(back) == "/trip/canvas?day=0&booked=b-in"
    r = trip.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "+1 310 555 0177", "next": unescape(back)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == unescape(back)
    assert 'href="tel:+13105550177"' in opened(trip, "b-in")
    r = trip.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "+1 310 555 0100", "next": "https://evil.example/x"}, follow_redirects=False)
    assert r.headers["location"] == "/trip/help"                         # only a canvas address is a way back
    r = trip.post("/trip/help/phone", data={"kind": "hotel", "index": "0", "phone": "nope", "next": unescape(back)}, follow_redirects=False)
    assert r.headers["location"] == unescape(back) + "&err=phone"      # review: a refused number goes back to the sheet with the reason


# ---- car -------------------------------------------------------------------------------------------------------------------------

def test_the_car_sheet_has_the_company_counter_directions_and_call(trip):
    sheet = sheet_of(opened(trip, "b-car-pick"))
    t = text(sheet)
    assert "Hertz" in t and "Pick up" in t and "Counter" in t
    assert 'href="tel:+13105550199"' in sheet and "maps" in unescape(tag(sheet, "hp-car-directions"))
    assert re.search(r"<details[^>]*hp-conf", sheet)
    drop = sheet_of(opened(trip, "b-car-drop", 4))
    assert "Drop off" in text(drop) and 'id="bk-counter"' in drop and "Drop off:" in text(drop)


# ---- flight ----------------------------------------------------------------------------------------------------------------------

def test_the_flight_sheet_has_route_times_and_the_passes_with_an_editor_form(trip):
    sheet = sheet_of(opened(trip, "b-out"))
    t = text(sheet)
    assert "SFO → LAX" in t and "Alaska Airlines AS 1234" in t and "LEAVES" in t and "ARRIVES" in t
    assert "Passes & documents" in t and "No passes added yet" in t and "Add a pass" in t
    assert "Show everyone's passes" not in t
    assert re.search(r'<form[^>]*action="/trip/help/pass"', sheet) and 'name="next"' in sheet


def test_a_pass_added_in_the_sheet_shows_there_with_the_full_screen_gate_link(trip):
    key = first_leg_key(person("ari"))
    r = add_pass(trip, key, "Abhi", seat="21a", grp="3", gate="71b", next="/trip/canvas?day=0&booked=b-out")
    assert r.status_code == 303 and r.headers["location"] == "/trip/canvas?day=0&booked=b-out"
    r = add_pass(trip, key, "Sam", next="https://evil.example/")
    assert r.headers["location"] == "/trip/help#hp-passes"
    sheet = sheet_of(opened(trip, "b-out"))
    t = text(sheet)
    assert "Abhi" in t and "21A" in t and "71B" in t and "Sam" in t
    show = tag(sheet, "bk-show-passes")
    assert "Show everyone's passes" in t and f"/trip/passes/gate?flight=" in unescape(show)
    assert trip.get(unescape(re.search(r'href="([^"]+)"', show).group(1))).status_code == 200      # the existing full-screen gate view
    assert "Fix this pass" in t and "Remove" in t                                                  # an editor fixes and removes there


def test_removing_a_pass_in_the_sheet_returns_to_the_sheet(trip):
    key = first_leg_key(person("ari"))
    add_pass(trip, key, "Abhi")
    p = passes.listing(person("ari"))[key][0]
    r = trip.post("/trip/help/pass/remove", data={"pass_id": p["id"], "next": "/trip/canvas?day=0&booked=b-out"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/canvas?day=0&booked=b-out"
    assert passes.listing(person("ari")).get(key, []) == []


# ---- viewers ---------------------------------------------------------------------------------------------------------------------

def test_a_viewer_reads_every_sheet_and_sees_no_edit_controls(crew):
    owner, ed, vi = crew
    add_pass(owner, first_leg_key(person("ari")), "Abhi")
    for bid, day in (("b-in", 0), ("b-out2", 4), ("b-car-pick", 0), ("b-car-drop", 4), ("b-out", 0), ("b-back", 4)):
        sheet = sheet_of(opened(vi, bid, day))
        assert "<form" not in sheet and "<input" not in sheet and "hp-fix" not in sheet, bid
        assert text(sheet)
    t = text(sheet_of(opened(vi, "b-out")))
    assert "Abhi" in t and "Show everyone's passes" in t and "Add a pass" not in t
    assert "Front desk" in text(sheet_of(opened(vi, "b-in")))
    assert "Add a pass" in text(sheet_of(opened(ed, "b-out")))


# ---- the demo trip ---------------------------------------------------------------------------------------------------------------

def test_the_sample_trip_has_a_sheet_for_its_stay_and_its_flight(client):
    book(client)
    stay = sheet_of(bare(client.get("/trip/canvas?day=0&booked=b-in").text))
    assert "Check in" in text(stay) and "Directions" in text(stay) and "maps" in unescape(tag(stay, "hp-directions"))
    out = sheet_of(bare(client.get("/trip/canvas?day=0&booked=b-out").text))
    assert "Flight" in text(out)
    assert client.get("/trip/canvas?day=1&booked=b-zzz", follow_redirects=False).status_code == 303


# ---- the week --------------------------------------------------------------------------------------------------------------------

def test_the_weeks_bookings_are_links_to_the_same_sheet_and_nothing_nests_a_link(trip):
    page = bare(trip.get("/trip/canvas").text)
    cards = re.findall(r'<a\b[^>]*class="cz-wcard cz-simple is-booked"[^>]*>', page)
    assert len(cards) == 6
    for a in cards:
        assert re.search(r'href="/trip/canvas\?day=\d&amp;booked=b-[a-z0-9-]+"', a) and 'data-zoom="in"' in a
    assert re.search(r'href="/trip/canvas\?day=4&amp;booked=b-out2"', page) and re.search(r'href="/trip/canvas\?day=0&amp;booked=b-in"', page)
    depth = 0
    for m in re.finditer(r"<(/?)a\b", page):
        depth += -1 if m.group(1) else 1
        assert depth in (0, 1)                                          # an anchor is never inside another


def test_the_week_still_has_a_link_to_each_day_even_for_a_row_of_only_bookings(trip):
    page = bare(trip.get("/trip/canvas").text)
    for d in range(5):
        row = page.split('data-zk="day-%d"' % d)[1].split('data-zk="day-')[0]
        assert re.search(r'<a\b[^>]*href="/trip/canvas\?day=%d"[^>]*class="cz-row-link' % d, row), d


# ---- the filter row --------------------------------------------------------------------------------------------------------------

def kinds(page):
    row = re.search(r'<div[^>]*class="cz-kinds"[^>]*>.*?</div>', page, re.S).group(0)
    return re.findall(r'<button[^>]*data-k="([a-z]+)"[^>]*>([^<]+)</button>', row), row


def test_the_week_and_the_day_have_the_kind_filter_in_order_and_one_is_pressed(trip):
    for url in ("/trip/canvas", "/trip/canvas?day=0", "/trip/canvas?day=1"):
        got, row = kinds(bare(trip.get(url).text))
        assert got == [("all", "All"), ("plan", "Plans"), ("hotel", "Hotels"), ("flight", "Flights"), ("car", "Car"), ("chat", "Chats")]
        assert row.count('aria-pressed="true"') == 1 and "hidden" in row.split(">")[0]        # the script shows it; without script it would do nothing


def test_every_entry_of_the_day_says_what_kind_it_is(trip):
    page = bare(trip.get("/trip/canvas?day=0").text)
    lines = re.findall(r'<a\b[^>]*class="cz-bk[ "][^>]*>', page)
    kinds_seen = sorted(re.search(r'data-kind="([a-z]+)"', a).group(1) for a in lines)
    assert kinds_seen == ["car", "flight", "hotel"]
    week = bare(trip.get("/trip/canvas").text)
    assert sorted(set(re.findall(r'data-kind="([a-z]+)"[^>]*class="cz-wcard cz-simple is-booked"', week))) == ["car", "flight", "hotel"]


def test_the_who_and_list_filters_stay_and_the_kind_row_comes_first(client, azure):
    from tests.test_canvas_pages import added
    book(client)
    added(client)
    page = bare(client.get("/trip/canvas?day=1").text)
    assert 'class="cz-filters"' in page and page.index('class="cz-kinds"') < page.index('class="cz-filters"')
    assert re.search(r'<div[^>]*data-kind="plan"[^>]*class="cz-gb ', page)      # F-097: a plan is a block on the grid

# ---- Help leaves the tab bar, SOS opens the emergency sheet ------------------------------------------------------------------------

def test_the_tab_bar_is_today_ask_family_and_the_centre_is_ask(trip):
    nav = re.search(r'<nav[^>]*class="ph-tabs".*?</nav>', trip.get("/trip/canvas").text, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', nav) == ["/trip", "/trip/ask", "/trip/family"] and "Help" not in text(nav)
    assert "ph-ask" in tag(nav, "ph-tab-ask")


def test_help_still_works_for_old_links(trip):
    r = trip.get("/trip/help")
    assert r.status_code == 200 and "The Example Hotel Santa Monica" in r.text and 'id="hp-passes"' in r.text and 'id="hp-911"' in r.text


def test_the_heading_has_an_sos_button_on_the_week_and_the_day(trip):
    for url in ("/trip/canvas", "/trip/canvas?day=2"):
        page = bare(trip.get(url).text)
        a = tag(page, "cz-sos")
        assert "SOS" in text(page) and "sos=1" in a and 'data-zoom="in"' in a


def test_the_sos_sheet_has_911_tonights_front_desk_the_counter_and_the_family(trip):
    phones.set_member_phone(person("ari"), "+1 310 555 0111")
    for url in ("/trip/canvas?sos=1", "/trip/canvas?day=1&sos=1"):
        page = bare(trip.get(url).text)
        sheet = page[page.index('class="cz-sheet cz-sheet-sos'):]
        assert 'href="tel:911"' in sheet and "Call 911" in text(sheet)
        assert 'href="tel:+13105550100"' in sheet and "The Example Hotel Santa Monica" in text(sheet)     # tonight's front desk
        assert 'href="tel:+13105550199"' in sheet and "Hertz" in text(sheet)                              # the rental counter
        assert 'href="tel:+13105550111"' in sheet                                                        # the family
        assert 'href="/family#this-phone"' in sheet
        assert 'data-level="step"' in page
    assert 'class="cz-sheet cz-sheet-sos' in bare(trip.get("/trip/canvas?day=1&sos=1&frag=1").text)


def test_the_sos_sheet_points_to_the_morning_plan_when_push_is_set_up(trip, monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    assert 'href="/family#morning-plan"' in tag(bare(trip.get("/trip/canvas?sos=1").text), "sos-phone")
    assert 'id="tp-morning"' in trip.get("/family").text


def test_every_week_and_day_page_carries_the_sos_sheet_inert_so_it_opens_offline(trip):
    for url in ("/trip/canvas", "/trip/canvas?day=2", "/trip/canvas?day=1&frag=1"):
        page = bare(trip.get(url).text)
        tpl = page[page.index('<template id="cz-sos-tpl">'):].split("</template>")[0]
        assert 'href="tel:911"' in tpl and 'href="tel:+13105550100"' in tpl and "cz-sheet-sos" in tpl
    sos = bare(trip.get("/trip/canvas?day=1&sos=1").text)
    assert "cz-sos-tpl" not in sos                                                  # when the sheet is the level it is not drawn twice


def test_the_sos_sheet_is_for_every_role_and_asks_for_a_number_when_nobody_has_one(crew):
    owner, ed, vi = crew
    page = bare(vi.get("/trip/canvas?sos=1").text)
    sheet = page[page.index('class="cz-sheet cz-sheet-sos'):]
    assert 'href="tel:911"' in sheet and "<form" not in sheet and "Add your number" in text(sheet)


def test_the_sos_sheet_on_the_sample_trip_says_when_there_is_no_number(client):
    book(client)
    sheet = bare(client.get("/trip/canvas?day=0&sos=1").text)
    sheet = sheet[sheet.index('class="cz-sheet cz-sheet-sos'):]
    assert 'href="tel:911"' in sheet and "No phone number yet" in text(sheet)
