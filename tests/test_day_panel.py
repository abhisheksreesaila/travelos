"""F-141: a clicked plan opens in the panel, through HTTP. `?day=N&plan=<id>` draws the day with the panel in plan mode (the plan's card: who, note, steps, chat and compose) and the plan's
block ringed, so a reload shows it again; `GET /trip/canvas/card?act=&panel=1` is the same pane as a fragment (the phone's card is unchanged without `panel`). Whether a click, Esc and
the steps work is checked in a real browser: tests_browser/test_day_panel.py."""
import re

from gitaway import plantalk, tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_day_dock import dock
from tests.test_signin import person
from tests.test_trip_canvas import bare, step_id, text, trip, uni_id  # noqa: F401 - fixtures


def open_plan(client, act, day=1):
    r = client.get(f"/trip/canvas?day={day}&plan={act}")
    assert r.status_code == 200
    return bare(r.text)


def pane(page):
    m = re.search(r'<section\b[^>]*data-pane="plan".*?</section>', dock(page), re.S)
    assert m, "the panel has no plan pane"
    return m.group(0)


def test_without_a_plan_the_panel_is_idle_and_has_no_plan_pane(trip):
    d = dock(bare(trip.get("/trip/canvas?day=1").text))
    assert 'data-mode="idle"' in d and 'data-pane="plan"' not in d and "is-ringed" not in d


def test_a_plan_in_the_address_opens_in_the_panel_and_rings_its_block(trip):
    act = uni_id()
    page = open_plan(trip, act)
    d = dock(page)
    assert 'data-mode="plan"' in d and f'data-act="{act}"' in pane(page)
    assert re.search(rf'<div[^>]*class="[^"]*\bis-ringed\b[^"]*"[^>]*data-act="{act}"|<div[^>]*data-act="{act}"[^>]*class="[^"]*\bis-ringed\b', page)
    assert page.count("is-ringed") == 1
    assert 'aria-selected="true"' in re.findall(r"<(?:a|button)\b[^>]*>", re.search(r'role="tablist".*?</nav>', d, re.S).group(0))[0]
    assert 'data-pane="idle"' in d        # Up next is still there: Esc only shows it again


def test_the_pane_has_who_note_steps_chat_and_compose(trip):
    act = uni_id()
    cal.add_note(person("ari"), "kids want the ferris wheel", act=act)
    plantalk.post_message(person("ari"), act, "", "Churros after, deal")
    page = open_plan(trip, act)
    p, t = pane(page), text(pane(page))
    assert "Plan · Sat" in t
    assert "Universal" in t and "kids want the ferris wheel" in t and "Churros after, deal" in t
    assert "Steps" in t and "Add a step" in t and "Chat on this plan" in t and "Open plan" in t
    assert p.count("data-step=") >= 3 and 'class="cz-ring"' in p
    foot = re.search(r'<form\b[^>]*class="cz-pp-foot".*?</form>', dock(page), re.S).group(0)
    assert 'action="/trip/talk/message"' in foot and 'name="text"' in foot and f'value="{act}"' in foot
    assert 'aria-label="Close the plan"' in p and ">esc<" in p


def test_a_plan_with_no_steps_has_no_steps_section(trip):
    me = person("ari")
    a = cal.add_activity(me, day=2, start=10 * 60, end=11 * 60, title="Slow breakfast", kind="food")
    t = text(pane(open_plan(trip, a.id, day=2)))
    assert "Slow breakfast" in t and "Add a step" not in t and "Steps" not in t and "Chat on this plan" in t


def test_a_plan_from_another_day_or_one_that_is_not_there_is_ignored(trip):
    act = uni_id()
    for q in (f"day=0&plan={act}", "day=1&plan=zzz", "day=1&plan="):
        d = dock(bare(trip.get(f"/trip/canvas?{q}").text))
        assert 'data-mode="idle"' in d and 'data-pane="plan"' not in d


def test_the_card_route_gives_the_panel_pane_and_foot_only_when_asked(trip):
    act = uni_id()
    phone = trip.get(f"/trip/canvas/card?act={act}", headers={"X-Canvas": "1"}).text
    wide = trip.get(f"/trip/canvas/card?act={act}&panel=1", headers={"X-Canvas": "1"}).text
    assert 'data-pane="plan"' not in phone and "cz-card-inner" in phone
    assert 'data-pane="plan"' in wide and 'class="cz-pp-foot"' in wide and "cz-card-notes" in wide        # the same note markup as the phone card


def test_an_editor_can_tick_add_and_set_aside_a_viewer_only_reads(crew, azure):
    ari, viewer = crew
    added(ari)
    act = uni_id()
    mine, theirs = pane(open_plan(ari, act)), pane(open_plan(viewer, act))
    assert 'class="cz-ring"' in mine and 'name="do"' in mine and 'name="title"' in mine and "Add a step" in text(mine) and "cz-card-add" in mine
    assert "cz-ring" in theirs                       # the circle shows done or not, for everyone
    assert 'name="do"' not in theirs and 'name="title"' not in theirs and "Add a step" not in text(theirs) and "cz-card-add" not in theirs
    assert 'class="cz-pp-foot"' in dock(open_plan(viewer, act))        # talking changes no plan: a viewer may


def test_a_step_added_from_the_pane_shows_in_it_and_set_aside_moves_it_to_the_aside_list(trip):
    act = uni_id()
    form = re.search(r'<form\b[^>]*action="/trip/canvas/add".*?</form>', pane(open_plan(trip, act)), re.S).group(0)
    nxt = re.search(r'name="next" value="([^"]+)"', form).group(1).replace("&amp;", "&")
    assert f"plan={act}" in nxt
    part = re.search(r'name="part"[^>]*value="([^"]+)"|<option value="([^"]+)"', form)
    data = {"act": act, "next": nxt, "title": "Pretzel stop", "who": "all", "part": part.group(1) or part.group(2)}
    r = trip.post("/trip/canvas/add", data=data, headers={"X-Canvas": "1", "X-Canvas-Level": "1"})
    assert r.status_code == 200 and "Pretzel stop" in pane(bare(r.json()["level"]))
    before = int(re.search(r"Set aside \((\d+)\)", text(pane(open_plan(trip, act)))).group(1))
    sid = step_id(trip, "Pretzel stop")
    r = trip.post("/trip/canvas/step", data={"step": sid, "do": "aside", "next": nxt}, headers={"X-Canvas": "1", "X-Canvas-Level": "1"})
    level = bare(r.json()["level"])
    aside = re.search(r"id=\"cz-pp-aside\".*?</section>", pane(level) + "</section>", re.S).group(0)
    assert "Pretzel stop" in aside and 'value="back"' in aside and f"Set aside ({before + 1})" in text(pane(level))
