"""F-140: the desktop day, through HTTP. The day's markup carries what the laptop layout needs: the five day chips inside the ink header, Paste a plan and Say the plan in the
filters row, and the docked panel (`#cz-dock`, mode idle) with Up next, Later today and the Ask box, or "nothing up next" and Ask. Where things sit (two columns, only the grid and
the panel scroll, no page scroll at 1440x900 and 1280x800) is checked in a real browser: tests_browser/test_day_dock.py. The sample trip: Fri 16 fly in, Sat 17 Universal, Sun 18 free."""
import re
from datetime import datetime, timezone

from gitaway import catalog, tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_signin import person
from tests.test_trip_canvas import bare, tag, text, trip  # noqa: F401 - fixtures


def day(client, n):
    r = client.get(f"/trip/canvas?day={n}")
    assert r.status_code == 200
    return bare(r.text)


def dock(page):
    m = re.search(r'<aside\b[^>]*\bid="cz-dock".*?</aside>', page, re.S)
    assert m, "the day has no panel"
    return m.group(0)


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


SAT_NOON = datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc)      # Saturday 12:40 PM in Los Angeles: day 1, the Universal day


def test_the_header_carries_the_five_day_chips_and_the_day_switch(trip):
    page = day(trip, 1)
    head = re.search(r'<header [^>]*class="cz-head.*?</header>', page, re.S).group(0)
    chips = re.search(r'<nav [^>]*class="cz-hchips".*?</nav>', head, re.S).group(0)
    assert chips.count("<a ") == 5 and text(chips).startswith("FRI 16") and 'aria-current="date"' in re.findall(r"<a [^>]*>", chips)[1]
    assert all('data-zoom="side"' in a for a in re.findall(r"<a [^>]*>", chips))
    assert 'id="cz-z-day"' in head and 'id="cz-z-week"' in head and 'id="cz-mapbtn"' in head


def test_the_filters_row_has_paste_a_plan_and_say_the_plan_for_an_editor(trip):
    row = re.search(r'<div class="cz-bar">.*?cz-desk-say.*?</div>', day(trip, 1), re.S).group(0)
    assert "Paste a plan" in row and "Say the plan" in row
    assert "/trip/ask?day=1&amp;mode=paste" in row and "/trip/ask?day=1&amp;mode=talk" in row


def test_a_viewer_has_neither_the_two_buttons_nor_the_ask_box(crew, azure):
    ari, viewer = crew
    added(ari)
    page = bare(viewer.get("/trip/canvas?day=1").text)
    assert "Paste a plan" not in text(page) and 'class="cz-dock-ask"' not in dock(page) and "Ask or change something" not in text(dock(page))
    assert 'id="cz-dock"' in page


def test_the_panel_is_one_container_with_a_mode_and_three_tabs(trip):
    d = dock(day(trip, 1))
    assert 'data-mode="idle"' in d
    tabs = re.search(r'role="tablist".*?</nav>', d, re.S).group(0)
    assert [text(t) for t in re.findall(r"<(?:a|button)\b[^>]*>.*?</(?:a|button)>", tabs, re.S)] == ["Plan", "Family", "Ask"]
    assert 'aria-selected="true"' in re.findall(r"<(?:a|button)\b[^>]*>", tabs)[0]
    assert 'href="/trip/canvas?day=1&amp;panel=family' in tabs and "/trip/ask?day=1" in tabs      # F-143: Family opens the day's own panel (a page without script lands there too)


def test_during_the_trip_the_panel_shows_up_next_later_today_and_the_ask_box(trip, monkeypatch):
    me = person("ari")
    cal.add_activity(me, day=1, start=18 * 60, end=19 * 60, title="Dinner at CityWalk", kind="food")
    cal.add_activity(me, day=1, start=20 * 60, end=21 * 60, title="Late show", kind="fun")
    at(monkeypatch, SAT_NOON)
    d = dock(day(trip, 1))
    t = text(d)
    assert "HAPPENING NOW" in t and "Universal Studios" in t and "Directions" in t and "Open the plan" in t      # the park day is on now
    assert "Later today" in t and "Dinner at CityWalk" in t and "Late show" in t
    assert 'class="cz-dock-ask"' in d and "Ask or change something" in t


def test_up_next_says_who_and_leaves_out_a_drive_nobody_knows(trip, monkeypatch):
    me = person("ari")
    cal.add_activity(me, day=1, start=18 * 60, end=19 * 60, title="Dinner at CityWalk", kind="food")
    at(monkeypatch, SAT_NOON)
    d = dock(day(trip, 1))
    assert "min drive" not in d      # the offline test map knows no drive times: nothing is invented


def test_up_next_gives_the_drive_when_the_map_knows_it(trip, monkeypatch):
    from gitaway import geo
    me = person("ari")
    cal.add_activity(me, day=2, start=10 * 60, end=11 * 60, title="Slow breakfast", kind="food")
    monkeypatch.setattr(geo, "drive_minutes", lambda a, b: 12)
    assert "12 min drive" in text(dock(day(trip, 2)))


def test_up_next_counts_down_to_the_next_booking_on_a_travel_day(trip, monkeypatch):
    at(monkeypatch, datetime(2026, 10, 16, 19, 0, tzinfo=timezone.utc))      # Friday noon: the 3 PM check-in is next
    t = text(dock(day(trip, 0)))
    assert "UP NEXT" in t and "Check in" in t and "Open the plan" in t and "Later today" not in t


def test_with_nothing_up_next_the_panel_says_so_and_still_shows_ask(trip, monkeypatch):
    at(monkeypatch, SAT_NOON)
    d = dock(day(trip, 2))      # Sunday: nothing planned, nothing booked
    t = text(d)
    assert "Nothing up next" in t and "Directions" not in t and "Open the plan" not in t
    assert 'class="cz-dock-ask"' in d


def test_another_day_shows_its_first_plan_as_up_next(trip, monkeypatch):
    me = person("ari")
    cal.add_activity(me, day=2, start=10 * 60, end=11 * 60, title="Slow breakfast", kind="food")
    cal.add_activity(me, day=2, start=13 * 60, end=14 * 60, title="Pool", kind="fun")
    t = text(dock(day(trip, 2)))      # today is before the trip
    assert "FIRST UP" in t and "Slow breakfast" in t and "Pool" in t and "Later today" not in t and "Later on" in t


def test_a_booking_that_vanishes_mid_request_never_errors_the_panel(trip, monkeypatch):
    """F-155: the day read the booking, then the panel's own read (pages.trip.load) found it gone (a family deleted the trip meanwhile): a normal page, not a 500."""
    from gitaway import session as ses
    from gitaway.pages import trip as trippage
    real_booking, real_load, gone = ses.booking, trippage.load, []

    def load(*a, **kw):
        gone.append(1)                      # from here on this request's booking reads come back empty
        try:
            return real_load(*a, **kw)
        finally:
            gone.pop()

    monkeypatch.setattr(trippage, "load", load)
    monkeypatch.setattr(ses, "booking", lambda session: None if gone else real_booking(session))
    r = trip.get("/trip/canvas?day=1", follow_redirects=False)
    assert r.status_code in (200, 303), r.status_code
    if r.status_code == 303:
        assert r.headers["location"] == "/start"
    else:
        assert 'id="cz-dock"' in r.text
