"""F-054: the phone trip view's pure model (gitaway.tripday): phases, countdowns, states, directions, phones."""

from datetime import date

from gitaway import catalog, tripcal as cal, tripday as td

T = catalog.SAMPLE_TRIP  # Oct 16 - 20, 2026


def act(id_, day, start, end, title, kind="fun", by=""):
    return cal.Activity(id_, day, start, end, title, kind, by)


def test_phase_before_during_after():
    assert td.phase(T, date(2026, 10, 12)) == ("before", 4)
    assert td.phase(T, date(2026, 10, 16)) == ("during", 0)
    assert td.phase(T, date(2026, 10, 20)) == ("during", 4)
    assert td.phase(T, date(2026, 10, 23)) == ("after", 3)
    assert td.starts_in(1) == "Trip starts tomorrow" and td.starts_in(4) == "Trip starts in 4 days"


def test_countdown_words():
    assert [td.until(m) for m in (0, -5, 1, 40, 60, 130)] == ["now", "now", "in 1 min", "in 40 min", "in 1 h", "in 2 h 10 min"]


def test_a_time_span_names_the_meridiem_once_unless_it_crosses_noon():
    assert td.span_label(17 * 60, 19 * 60 + 30) == "5:00 – 7:30 PM"
    assert td.span_label(11 * 60 + 30, 13 * 60) == "11:30 AM – 1:00 PM"


def test_the_timeline_marks_done_now_and_next_and_orders_by_time():
    acts = [act("a1", 1, 17 * 60, 19 * 60 + 30, "Griffith Observatory"), act("a2", 1, 9 * 60, 10 * 60, "Breakfast", "food"), act("a3", 1, 20 * 60, 21 * 60, "Tacos", "food"),
            act("a4", 2, 9 * 60, 10 * 60, "Other day")]
    items = td.timeline(1, [], acts, [], "Los Angeles", now=16 * 60 + 20)
    assert [(x.title, x.state) for x in items] == [("Breakfast", "done"), ("Griffith Observatory", "next"), ("Tacos", "later")]
    mid = td.timeline(1, [], acts, [], "Los Angeles", now=18 * 60)
    assert [x.state for x in mid] == ["done", "now", "next"]
    assert {x.state for x in td.timeline(1, [], acts, [], "Los Angeles", past=True)} == {"done"}
    assert {x.state for x in td.timeline(1, [], acts, [], "Los Angeles")} == {"later"}


def test_up_next_counts_down_and_picks_the_first_thing_ahead():
    acts = [act("a1", 1, 17 * 60, 19 * 60 + 30, "Griffith Observatory"), act("a2", 1, 9 * 60, 10 * 60, "Breakfast", "food")]
    items = td.timeline(1, [], acts, [], "Los Angeles", now=16 * 60 + 20)
    up = td.up_next(items, 16 * 60 + 20)
    assert up.kicker == "UP NEXT · IN 40 MIN" and up.item.title == "Griffith Observatory" and up.detail == "5:00 – 7:30 PM"
    items = td.timeline(1, [], acts, [], "Los Angeles", now=18 * 60)
    assert td.up_next(items, 18 * 60).kicker == "HAPPENING NOW · ENDS IN 1 H 30 MIN"
    over = td.timeline(1, [], acts, [], "Los Angeles", now=22 * 60)
    assert td.up_next(over, 22 * 60).item is None and td.up_next(over, 22 * 60).kicker == "ALL DONE TODAY"


def test_directions_use_apple_maps_on_apple_devices_and_google_maps_elsewhere_and_carry_only_the_place():
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    assert td.maps_url("Griffith Observatory, Los Angeles", iphone) == "https://maps.apple.com/?q=Griffith+Observatory%2C+Los+Angeles"
    assert td.maps_url("Griffith Observatory", "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36").startswith("https://www.google.com/maps/search/?api=1&query=")
    assert td.maps_url("x", "").startswith("https://www.google.com/")


def test_phones_are_told_apart_from_tablets_and_desktops():
    assert td.is_phone("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
    assert td.is_phone("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36")
    assert not td.is_phone("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
    assert not td.is_phone("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
    assert not td.is_phone("testclient") and not td.is_phone(None)


def test_day_summaries_say_fly_in_and_fly_home_and_wide_open():
    dates = cal.days(T)
    blocks = [cal.Block("b-out", 0, 485, 572, "Skylark Air 214 · SFO → LAX", "booked", True, "plane"), cal.Block("b-in", 0, 900, 990, "Check in · The Tidewater", "booked", True, "bed"),
              cal.Block("b-back", 4, 800, 900, "Skylark Air 215 · LAX → SFO", "booked", True, "plane")]
    days = td.day_summaries(dates, blocks, [act("a1", 1, 600, 660, "Pier"), act("a2", 1, 700, 760, "Tacos", "food")], today_index=1)
    assert [d.head for d in days] == ["Fly in · check in", "Pier", "Wide open", "Wide open", "Fly home"]
    assert days[1].line == "Pier · Tacos" and days[2].line == "Nothing planned yet"
    assert [d.state for d in days] == ["done", "today", "later", "later", "later"]
    assert days[0].num == 16 and days[0].dow == "FRI" and days[1].tint == "mint"
