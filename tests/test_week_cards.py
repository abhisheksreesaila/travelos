"""F-163: the phone week's day card, through HTTP and on its pieces. The look (white cards, kind tiles, the bar's segments at their times, 44px rows, a tap opening the day) is pinned in a real browser:
tests_browser/test_week_cards.py. Here: what the markup says, and the mini hour bar's hours, which need a booking outside 7 AM to 10 PM (a plan cannot be made there)."""
import re
from types import SimpleNamespace

from fasthtml.common import to_xml

from gitaway.pages import tripcanvas as tc
from tests.test_canvas import azure  # noqa: F401 - fixture
from tests.test_trip_canvas import bare, text, trip  # noqa: F401 - fixtures


def view(*blocks):
    return {"dates": [0], "acts": [], "plan": {}, "blocks": [SimpleNamespace(day=0, id=f"b{n}", icon="plane", **b) for n, b in enumerate(blocks)]}


def bar(v):
    return to_xml(tc._bar(v, 0, tc.entries(v, 0)))


def test_the_bar_is_the_day_grids_hours_with_a_label_every_three(trip):
    html = bare(trip.get("/trip/canvas").text)
    labels = re.findall(r'class="cz-mb-h(?: is-\w+)?"[^>]*>([^<]+)</span>', html.split('id="cz-week"')[1].split('id="cz-wk"')[0])
    assert labels[:6] == ["7 AM", "10 AM", "1 PM", "4 PM", "7 PM", "10 PM"]


def test_the_bar_widens_for_an_early_or_a_late_booking_and_each_segment_has_its_start_and_length():
    html = bar(view(dict(title="Early flight", start=6 * 60, end=6 * 60 + 30), dict(title="Late flight", start=23 * 60, end=23 * 60 + 45)))
    assert re.findall(r'class="cz-mb-h(?: is-\w+)?"[^>]*>([^<]+)<', html) == ["6 AM", "9 AM", "12 PM", "3 PM", "6 PM", "9 PM", "12 AM"]      # 6 AM to midnight, every three hours
    assert 'style="--span:1080"' in html
    assert re.findall(r'class="cz-mb-seg[^"]*"[^>]*style="(--s:\d+;--l:\d+)"', html) == ["--s:0;--l:30", "--s:1020;--l:45"]      # left and width in minutes of the bar's 1080
    assert 'class="cz-mb-h is-start"' in html and 'class="cz-mb-h is-end"' in html


def test_a_booking_with_no_length_is_drawn_fifteen_minutes_long():
    assert 'style="--s:480;--l:15"' in bar(view(dict(title="Pass", start=15 * 60, end=15 * 60)))      # 3 PM on a bar that starts at 7 AM


def test_a_booking_is_its_own_link_and_a_plan_is_not(trip):
    week = bare(trip.get("/trip/canvas").text).split('id="cz-week"')[1].split('id="cz-wk"')[0]
    assert len(re.findall(r'<a\b[^>]*class="cz-wcard cz-simple is-booked"', week)) == 4      # Fri's flight and hotel, Tue's check out and flight home
    assert 'class="cz-wcard cz-simple cz-k-' in week and not re.search(r'<a\b[^>]*cz-k-', week)      # a plan's row is not a link of its own: the card's link opens the day
    assert "9:00 AM Universal Studios Hollywood 14 steps Plan" in text(week)
