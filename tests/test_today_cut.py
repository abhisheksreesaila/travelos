"""F-092: Today is the day view. The Today tab (/trip) opens today's day in the canvas; on today the day starts with what is happening now or up next; the centre Ask
is the one way to change the day (no extra buttons on the day or the block); the week has no zoom control; the morning plan switch and the Face ID card live on the family page (F-093).
The demo trip is Fri Oct 16 to Tue Oct 20 in Los Angeles."""

import re
from datetime import datetime, timezone

import pytest

from gitaway import catalog
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_trip_canvas import bare, tag, trip  # noqa: F401 - fixtures


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


def where(client, url):
    r = client.get(url, follow_redirects=False)
    assert r.status_code in (302, 303, 307), (url, r.status_code)
    return bare(r.headers["location"])


# ---- the Today tab opens today's day -------------------------------------------------------------------------------------------

def test_the_today_tab_opens_todays_day_during_the_trip(trip, monkeypatch):
    at(monkeypatch, datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc))     # Monday 10:00 AM in Los Angeles: day 4
    assert where(trip, "/trip") == "/trip/canvas?day=3"


def test_before_the_trip_it_opens_the_first_day_and_after_it_the_last(trip, monkeypatch):
    assert where(trip, "/trip") == "/trip/canvas?day=0"          # the tests' today is Sep 30
    at(monkeypatch, datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc))
    assert where(trip, "/trip") == "/trip/canvas?day=4"


def test_the_old_today_page_is_still_there_for_its_tabs(trip):
    r = trip.get("/trip?tab=today")
    assert r.status_code == 200 and 'id="tp-panel-today"' in r.text


def test_signed_out_and_no_trip_still_go_to_sign_in_and_start(client):
    from tests.test_signin import sign_in
    assert client.get("/trip", follow_redirects=False).headers["location"].startswith("/signin")
    sign_in(client)
    assert client.get("/trip", follow_redirects=False).headers["location"] == "/start"


# ---- on today, what is happening now ------------------------------------------------------------------------------------------

def test_today_starts_with_whats_happening_now_and_other_days_do_not(trip, monkeypatch):
    at(monkeypatch, datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc))     # Saturday 11:00 AM: Universal is on
    page = bare(trip.get("/trip/canvas?day=1").text)
    assert 'id="tp-up"' in page and "HAPPENING NOW" in page and "Universal Studios Hollywood" in page
    assert page.index('id="cz-dpills"') < page.index('id="tp-up"') < page.index('id="cz-grid"')
    assert 'id="tp-up"' not in bare(trip.get("/trip/canvas?day=3").text)


def test_before_the_trip_no_day_has_a_now_card(trip):
    assert 'id="tp-up"' not in trip.get("/trip/canvas?day=0").text


# ---- one way to change the day ---------------------------------------------------------------------------------------------------

def test_the_day_and_the_block_have_no_extra_change_buttons(trip):
    day = trip.get("/trip/canvas?day=1").text
    assert 'id="cz-say"' not in day and "ak-open" not in day
    block = re.search(r'href="(/trip/canvas\?block=[^"&]+)', day).group(1)
    assert "ak-open" not in trip.get(block).text


def test_an_empty_day_still_offers_talk_and_paste(trip):
    page = bare(trip.get("/trip/canvas?day=2").text)
    assert 'id="cz-say-talk"' in page and 'id="cz-say-paste"' in page


# ---- the week -----------------------------------------------------------------------------------------------------------------

def test_the_week_and_the_day_have_one_day_week_toggle_and_no_pinch(trip):
    week, day = trip.get("/trip/canvas").text, bare(trip.get("/trip/canvas?day=2").text)
    assert 'aria-current="page"' in tag(week, "cz-z-week") and 'href="/trip/canvas?day=0"' in bare(tag(week, "cz-z-day")) and 'data-zoom="in"' in tag(week, "cz-z-day")
    assert 'aria-current="page"' in tag(day, "cz-z-day") and 'href="/trip/canvas"' in tag(day, "cz-z-week") and 'data-zoom="out"' in tag(day, "cz-z-week")
    assert 'id="cz-z-today"' not in week and "Pinch" not in week and "Pinch" not in day



def test_the_week_marks_today(trip, monkeypatch):
    at(monkeypatch, datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc))
    page = trip.get("/trip/canvas").text
    row = re.search(r'<div[^>]*data-day="3"[^>]*>', page).group(0)
    assert "is-today" in row and page.count('class="cz-today"') == 1


# ---- the family page carries the morning plan and Face ID (F-093: they left Help) ---------------------------------------------------

def test_the_family_page_has_the_morning_plan_switch_when_push_is_set_up(trip, monkeypatch):
    assert 'id="tp-morning"' not in trip.get("/family").text
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    html = trip.get("/family").text
    assert 'id="tp-morning"' in html and "/assets/js/morning.js" in html and "morning.css" in html
    assert 'id="tp-morning"' not in trip.get("/trip/help").text


def test_the_family_page_offers_face_id_to_someone_without_a_passkey(trip):
    html = trip.get("/family").text
    assert 'id="pk-card"' in html and 'id="this-phone"' in html and "/assets/js/passkeys.js" in html
    assert 'id="pk-card"' not in trip.get("/trip/help").text


def test_the_now_card_ends_with_its_buttons_and_a_booking_title_opens_its_sheet(trip, monkeypatch):
    at(monkeypatch, datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc))     # Saturday 11:00 AM: Universal is on
    card = re.search(r'<div[^>]*id="tp-up".*?</div>\s*</div>', trip.get("/trip/canvas?day=1").text, re.S).group(0)
    assert "tp-up-compact" in card and ">Details<" not in card and "data-up-details" not in card
    at(monkeypatch, datetime(2026, 10, 16, 21, 0, tzinfo=timezone.utc))     # Friday 2:00 PM: check-in at 3:00 is up next
    page = bare(trip.get("/trip/canvas?day=0").text)
    link = re.search(r'<a[^>]*id="tp-up-open"[^>]*>', page)
    assert link and "booked=" in link.group(0), "a booking up next opens its sheet from its title"
    href = re.search(r'href="([^"]+)"', link.group(0)).group(1)
    lines = [re.search(r'href="([^"]+)"', a).group(1) for a in re.findall(r'<a\b[^>]*class="cz-bk[^"]*"[^>]*>', page)]
    assert href in lines      # the same sheet its booking line opens
    assert trip.get(href.replace("&amp;", "&")).status_code == 200
