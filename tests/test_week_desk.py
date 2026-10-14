"""F-145: the desktop week, through HTTP. The week's markup carries a column per day (`#cz-wk`): a day-colour header, compact rows (time, title, kind icon), plans with their step and
message summary, a dashed Free day card with Say the plan (editors only), today outlined, and Open the day at the foot. Where it sits (columns across a laptop, sideways scroll inside the
week area on a long trip, no page scroll) is checked in a real browser: tests_browser/test_week_desk.py. The sample trip: Fri 16 fly in, Sat 17 Universal, Sun 18 free."""
import re
from datetime import datetime, timezone

from gitaway import catalog, plantalk, tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_signin import person
from tests.test_trip_canvas import bare, text, trip  # noqa: F401 - fixtures

SAT_NOON = datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc)      # Saturday 12:40 PM in Los Angeles: day 1


def week(client):
    r = client.get("/trip/canvas")
    assert r.status_code == 200
    page = bare(r.text)
    m = re.search(r'<div\b[^>]*\bid="cz-wk".*?<template|<div\b[^>]*\bid="cz-wk".*', page, re.S)
    assert m, "the week has no desktop columns"
    return m.group(0)


def columns(wk):
    return re.findall(r'<div\b[^>]*class="cz-wcol[ "][^>]*>.*?(?=<div\b[^>]*class="cz-wcol[ "]|\Z)', wk, re.S)


def test_one_column_per_day_with_a_colour_header_and_open_the_day(trip):
    cols = columns(week(trip))
    assert len(cols) == 5
    assert [c for c in re.findall(r'cz-wt-(sun|mint|grape|sky|bubble)', "".join(re.findall(r'<div\b[^>]*class="cz-wcol[^"]*"', "".join(cols))))] == ["sun", "mint", "grape", "sky", "bubble"]
    for i, c in enumerate(cols):
        assert re.search(rf'<a [^>]*href="/trip/canvas\?day={i}"[^>]*>[^<]*(?:<[^>]+>[^<]*)*Open the day', c, re.S), i
        assert 'data-zoom="in"' in re.search(rf'<a [^>]*href="/trip/canvas\?day={i}"[^>]*>', c).group(0)
    assert text(cols[0]).startswith("01 FRI 16") and text(cols[1]).startswith("02 SAT 17")      # F-158: the numbered key first


def test_rows_show_time_title_and_a_kind_icon(trip):
    c = columns(week(trip))[0]
    r = re.findall(r'<a\b[^>]*class="cz-wi[ "][^>]*>.*?</a>', c, re.S)
    assert r, "no rows"
    first = r[0]
    assert re.search(r"\d{1,2}:\d\d (?:AM|PM)", text(first)) and "<svg" in first and 'class="cz-wi-t"' in first
    assert all("<svg" in x and 'class="cz-wi-time"' in x for x in r)


def test_a_plan_shows_its_steps_and_messages_and_links_to_the_day_with_the_plan(trip):
    c = columns(week(trip))[1]
    plan = next(x for x in re.findall(r'<a\b[^>]*class="cz-wi[ "][^>]*>.*?</a>', c, re.S) if "Universal Studios" in x)
    assert re.search(r"\d+ steps · \d+ done|\d+ steps", text(plan))
    href = re.search(r'href="([^"]+)"', plan).group(1).replace("&amp;", "&")
    assert href.startswith("/trip/canvas?day=1&plan=a") and 'data-zoom="in"' in plan


def test_messages_are_counted_only_when_there_are_some(trip):
    me = person("ari")
    a = cal.add_activity(me, day=1, start=19 * 60, end=20 * 60, title="Dinner at CityWalk", kind="food")
    row = lambda: next(x for x in re.findall(r'<a\b[^>]*class="cz-wi[ "][^>]*>.*?</a>', columns(week(trip))[1], re.S) if "Dinner at CityWalk" in x)
    assert "message" not in text(row())
    plantalk.post_message(me, a.id, "", "Let's book the table")
    plantalk.post_message(me, a.id, "", "Said 7:30")
    assert "2 messages" in text(row())


def test_a_booking_row_opens_its_sheet(trip):
    c = columns(week(trip))[0]
    b = next(x for x in re.findall(r'<a\b[^>]*class="cz-wi[ "][^>]*>.*?</a>', c, re.S) if "is-booked" in x)
    assert "booked=" in re.search(r'href="([^"]+)"', b).group(1)


def test_a_free_day_is_a_dashed_card_with_say_the_plan(trip):
    c = columns(week(trip))[2]
    assert 'class="cz-wfree"' in c and "Free day" in text(c) and "Nothing planned yet" in text(c)
    say = re.search(r'<a [^>]*>[^<]*(?:<[^>]+>[^<]*)*Say the plan', c, re.S).group(0)
    assert "/trip/ask?day=2&amp;mode=talk" in say


def test_a_viewer_sees_the_free_day_but_no_say_the_plan(crew, azure):
    ari, viewer = crew
    wk = week(viewer)
    assert "Free day" in text(wk) and "Say the plan" not in text(wk)


def test_today_is_outlined(trip, monkeypatch):
    monkeypatch.setattr(catalog, "now_utc", lambda: SAT_NOON)
    monkeypatch.setattr(catalog, "today", lambda: SAT_NOON.astimezone(catalog.TZ).date())
    cols = columns(week(trip))
    assert [i for i, c in enumerate(cols) if "is-today" in re.match(r'<div\b[^>]*>', c).group(0)] == [1]


def test_the_desktop_week_keeps_the_old_rows_for_the_tablet_and_the_phone(trip):
    page = bare(trip.get("/trip/canvas").text)
    assert 'id="cz-week"' in page and 'id="cz-wk"' in page


def test_a_long_booking_title_is_shortened_on_the_row_and_whole_in_its_tooltip(trip):
    c = columns(week(trip))[0]
    b = next(x for x in re.findall(r'<a\b[^>]*class="cz-wi[ "][^>]*>.*?</a>', c, re.S) if "Check in" in x)
    assert text(b).count("·") <= 1 and "title=" in b
