"""F-178: where runs are kept right by script after the first draw: the plan pane's own chat (day_dock.js, day_family.js), "Earlier messages", a failed send's state line, and a plan change
line ending a run. Helpers and fixtures are test_bubbles.py's."""
from playwright.sync_api import expect

from tests_browser.helpers import seed_plan
from tests_browser.test_bubbles import CORAL_DEEP, contrast, desk, page_colour, runs, say, seen, shot  # noqa: F401 - fixtures
from tests_browser.test_day_grid import open_day
from tests_browser.test_family_panel import SATURDAY, dock, mates, open_family, park, thread  # noqa: F401 - fixtures
from tests_browser.test_thread import pair  # noqa: F401 - fixture
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures


def open_plan_pane(desk):
    open_day(desk, SATURDAY)
    act = park(desk)
    b = desk.locator(f'.cz-gb[data-act="{act}"]')
    b.scroll_into_view_if_needed()
    box = b.bounding_box()
    desk.mouse.click(box["x"] + box["width"] * 0.7, box["y"] + min(box["height"] * 0.6, 90))
    expect(desk.locator("#cz-pp-msgs")).to_be_visible()
    return act, desk.locator("#cz-pp-msgs")


def test_the_plan_panes_own_chat_groups_runs_for_polled_and_sent_messages(desk, mates):
    mate = mates(desk)
    act, th = open_plan_pane(desk)
    for i, t in enumerate(("Plan one", "Plan two", "Plan three"), 1):
        mate.say(t, act=act)
        expect(th.locator(".ft-bub")).to_have_count(i, timeout=9000)                     # polled in one at a time
    assert runs(th) == ["ft-first", "", "ft-last"]
    assert [s["name"] for s in seen(th.locator(".ft-msg"))] == [True, False, False]
    for t in ("Mine one", "Mine two"):
        desk.locator("#cz-dock .cz-pp-text").fill(t)
        desk.locator("#cz-dock .cz-pp-send").click()
        expect(th.get_by_text(t)).to_be_visible()
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first", "ft-last"]
    st = seen(th.locator(".ft-me"))
    assert [s["tail"] for s in st] == [False, True] and [s["time"] for s in st] == [False, True], st
    assert [s["avatar"] for s in seen(th.locator(".ft-msg:not(.ft-me)"))] == [False, False, True]
    shot(desk, "plan-pane-1440.png")


def test_earlier_messages_from_the_same_person_regroup_without_the_view_jumping(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    for i in range(1, 71):
        mate.say(f"Message {i:02d}")
    open_day(desk, SATURDAY)
    open_family(desk)
    th = thread(desk)
    expect(th.locator(".ft-bub")).to_have_count(30)
    th.evaluate("e => { e.scrollTop = 0; }")                                                  # reading the oldest one shown
    first = th.locator(".ft-msg").first
    n = first.get_attribute("data-n")
    top = th.bounding_box()["y"]
    before = first.locator(".ft-bub").bounding_box()["y"] - top
    dock(desk).locator("#ft-older").click()
    expect(th.locator(".ft-bub")).to_have_count(60)
    after = th.locator(f'.ft-msg[data-n="{n}"] .ft-bub').bounding_box()["y"] - th.bounding_box()["y"]
    assert [s["name"] for s in seen(th.locator(".ft-msg"))].count(True) == 1               # one run of sixty: the name once, at the very first
    r = runs(th)
    assert r[0] == "ft-first" and r[-1] == "ft-last" and r.count("ft-first") == 1
    assert abs(after - before) < 2, (before, after)                                           # what was being read has not moved


def test_a_failed_send_shows_its_state_line_under_the_bubble(pair, base_url):
    ari, mate = pair()
    ari.route("**/trip/family/message", lambda route: route.abort())
    ari.locator("#ft-text").fill("This will not go")
    ari.locator("#ft-send").click()
    bubble = ari.locator("#ft-thread .ft-me.is-failed")
    expect(bubble.locator(".ft-state")).to_have_text("Not sent")
    b, s = bubble.locator(".ft-bub").bounding_box(), bubble.locator(".ft-state").bounding_box()
    assert s["y"] >= b["y"] + b["height"] - 1, (b, s)                                       # the line sits under the bubble, not inside it
    fg = bubble.locator(".ft-state").evaluate("e => getComputedStyle(e).color.match(/[\\d.]+/g).slice(0, 3).map(Number)")
    assert fg == CORAL_DEEP and contrast(fg, page_colour(bubble.locator(".ft-state"))) >= 4.5
    expect(bubble.get_by_role("button", name="Retry")).to_be_visible()


def test_a_plan_change_line_ends_a_run_so_the_next_message_has_the_name_and_tail_again(pair, base_url):
    ari, mate = pair()
    th = ari.locator("#ft-thread")
    say(mate.context, base_url, "Before one")
    say(mate.context, base_url, "Before two")
    expect(th.locator(".ft-msg")).to_have_count(2, timeout=9000)
    seed_plan(ari.context.request, base_url, **{"id": "a1", "day": "1", "start": "10:00", "end": "11:00", "title": "Griffith Observatory", "kind": "culture"})
    expect(th.locator(".ft-sys")).to_have_count(1, timeout=9000)
    say(mate.context, base_url, "After the change")
    expect(th.locator(".ft-msg")).to_have_count(3, timeout=9000)
    assert runs(th) == ["ft-first", "ft-last", "ft-first+ft-last"]
    st = seen(th.locator(".ft-msg"))
    assert [s["name"] for s in st] == [True, False, True] and [s["tail"] for s in st] == [False, True, True], st
    ari.reload()
    assert runs(th) == ["ft-first", "ft-last", "ft-first+ft-last"]                          # the server draws the same
