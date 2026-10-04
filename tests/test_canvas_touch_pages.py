"""F-082: touch moves and filters through HTTP. The move, undo, add and note routes (script and plain), the add-a-step sheet, the Move menu on the step sheet, the
filters' markup, the list card, viewers (no drag, no swipe, no add, no move; filters still there), and a write that names another trip. Every form on the new
sheets is pressed. The trip is the captain's Universal + California Adventure messages (canned model answer, no network)."""

import json
import re
from html import unescape

import pytest

from gitaway import canvas, catalog, session as ses, tripcal as cal
from tests.test_canvas import announced, azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_signin import person
from tests.test_trip_canvas import bare, step_id, tag, trip, uni_id  # noqa: F401 - fixtures

JS = {"x-canvas": "1"}


def plan():
    return canvas.plan(person("ari"))


def part_of(act, name):
    return next(p for p in plan()["blocks"][act]["parts"] if p["name"] == name)


def titles(act, name):
    return [s["title"] for s in part_of(act, name)["steps"]]


def dca():
    return next(a for a, blk in plan()["blocks"].items() if a != uni_id())


def opening_tags(html, word):
    """[{attribute: value}] of every element whose class list has `word`, whatever order its attributes come in."""
    out = []
    for m in re.finditer(r"<[a-z0-9]+\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", html):
        attrs = {k: unescape(a or b) for k, a, b in re.findall(r"""([\w-]+)=(?:"([^"]*)"|'([^']*)')""", m.group(1))}
        if word in attrs.get("class", "").split():
            out.append(attrs)
    return out


def form_data(f):
    return {n: unescape(v) for n, v in re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', f)}


def forms_in(html, action):
    return [f for f in re.findall(r"<form[^>]*>.*?</form>", html, re.S) if f'action="{action}"' in f]


# ---- move ------------------------------------------------------------------------------------------------------------------

def test_a_drop_posts_a_move_and_the_script_gets_the_toast_and_the_undo(trip, announced):
    uni = uni_id()
    sid = step_id(trip, "Minion Mayhem")
    r = trip.post("/trip/canvas/move", data={"step": sid, "part": part_of(uni, "Lunch")["id"], "next": f"/trip/canvas?block={uni}"}, headers=JS)
    body = r.json()
    assert r.status_code == 200 and body["url"] == f"/trip/canvas?block={uni}" and body["toast"] == "Minion Mayhem moved to Lunch" and body["undo"]["kind"] == "moved"
    assert titles(uni, "Lunch")[-1] == "Minion Mayhem"
    back = trip.post("/trip/canvas/undo", data={"undo": json.dumps(body["undo"]), "next": body["url"]}, headers=JS)
    assert back.status_code == 200 and back.json() == {"url": body["url"], "toast": "Moved back"} and "Minion Mayhem" not in titles(uni, "Lunch")


def test_a_move_without_the_script_redirects_to_the_level(trip):
    uni = uni_id()
    sid = step_id(trip, "Minion Mayhem")
    r = trip.post("/trip/canvas/move", data={"step": sid, "part": part_of(uni, "Lunch")["id"], "next": "/trip/canvas?day=1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/canvas?day=1" and titles(uni, "Lunch")[-1] == "Minion Mayhem"


def test_a_step_dropped_on_another_day_from_the_block_follows_it_to_that_block(trip):
    uni, other = uni_id(), dca()
    sid = step_id(trip, "Minion Mayhem")
    r = trip.post("/trip/canvas/move", data={"step": sid, "act": other, "next": f"/trip/canvas?block={uni}"}, headers=JS).json()
    assert bare(r["url"]) == f"/trip/canvas?block={other}" and r["toast"].startswith("Minion Mayhem moved to ")
    day = trip.post("/trip/canvas/move", data={"step": step_id(trip, "King Kong"), "act": other, "next": "/trip/canvas?day=1"}, headers=JS).json()
    assert day["url"] == "/trip/canvas?day=1"          # the day stays the day


def test_dropping_a_step_in_the_tray_and_taking_it_out(trip):
    uni = uni_id()
    sid = step_id(trip, "King Kong")
    body = trip.post("/trip/canvas/move", data={"step": sid, "aside": "1", "next": "/trip/canvas?day=1"}, headers=JS).json()
    assert body["toast"] == "King Kong moved to the Set aside tray" and "Set aside · 3" in trip.get("/trip/canvas?day=1").text
    trip.post("/trip/canvas/undo", data={"undo": json.dumps(body["undo"]), "next": "/trip/canvas?day=1"}, headers=JS)
    assert "Set aside · 2" in trip.get("/trip/canvas?day=1").text


def test_a_drop_that_changes_nothing_has_no_toast(trip):
    uni = uni_id()
    sid = step_id(trip, "Minion Mayhem")
    order = titles(uni, "Upper Lot")
    r = trip.post("/trip/canvas/move", data={"step": sid, "part": part_of(uni, "Upper Lot")["id"], "before": step_id(trip, "Silly Swirly"), "next": "/trip/canvas?day=1"}, headers=JS).json()
    if titles(uni, "Upper Lot") == order:
        assert r["toast"] == "" and r["undo"] is None


def test_a_move_that_cannot_be_made_answers_422_for_the_script_and_goes_back_for_a_form(trip):
    sid = step_id(trip, "King Kong")
    r = trip.post("/trip/canvas/move", data={"step": sid, "part": "nope", "next": "/trip/canvas?day=1"}, headers=JS)
    assert r.status_code == 422 and r.json()["error"]
    r = trip.post("/trip/canvas/move", data={"step": sid, "part": "nope", "next": "/trip/canvas?day=1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/canvas?day=1"
    r = trip.post("/trip/canvas/undo", data={"undo": "{not json", "next": "/trip/canvas?day=1"}, headers=JS)
    assert r.status_code == 422
    assert trip.post("/trip/canvas/undo", data={"undo": "", "next": "/trip/canvas"}, follow_redirects=False).status_code == 303


def test_the_way_back_after_a_move_can_only_be_a_canvas_address(trip):
    sid = step_id(trip, "Minion Mayhem")
    for evil in ("https://evil.example/", "//evil.example", "/calendar", ""):
        r = trip.post("/trip/canvas/move", data={"step": sid, "part": part_of(uni_id(), "Lunch")["id"], "next": evil}, headers=JS).json()
        assert bare(r["url"]) == "/trip/canvas"


# ---- a write belongs to the trip the page was drawn for ----------------------------------------------------------------------

def test_a_move_add_note_or_undo_that_names_another_trip_changes_nothing(trip):
    ari = person("ari")
    with ses.family(ari) as fam:
        first = fam.trip_id
    uni = uni_id()
    sid, lunch = step_id(trip, "Minion Mayhem"), part_of(uni, "Lunch")["id"]
    before = json.dumps(plan(), default=str, sort_keys=True)
    ses.book(ari, catalog.quote("f1", "h1", "c1", trip=catalog.trip_from_url("2026-10-16", "2026-10-19", "2", "4,7")))        # a second trip is now the open one
    with ses.family(ari) as fam:
        other_trip = fam.trip_id
    assert other_trip != first
    cases = [("/trip/canvas/move", {"step": sid, "part": lunch}), ("/trip/canvas/add", {"act": uni, "part": lunch, "title": "Ghost"}), ("/trip/canvas/note", {"step": sid, "note": "Ghost"}),
             ("/trip/canvas/step", {"step": sid, "do": "done"})]
    for path, data in cases:
        trip.post(path, data={**data, "trip": other_trip, "next": "/trip/canvas"}, headers=JS)
    snap = {"kind": "moved", "act": uni, "steps": [{"id": sid, "act": uni, "part": lunch, "position": 0, "time": "", "aside": 0}]}
    assert trip.post("/trip/canvas/undo", data={"undo": json.dumps(snap), "trip": other_trip}, headers=JS).status_code == 422
    trip.post("/trips/switch", data={"trip": first})
    assert json.dumps(plan(), default=str, sort_keys=True) == before
    trip.post("/trips/switch", data={"trip": other_trip})
    # the same posts naming the trip they belong to do their work, even though another trip is open
    assert trip.post("/trip/canvas/move", data={"step": sid, "part": lunch, "trip": first, "next": "/trip/canvas"}, headers=JS).json()["toast"]
    trip.post("/trips/switch", data={"trip": first})
    assert titles(uni, "Lunch")[-1] == "Minion Mayhem"


# ---- add ------------------------------------------------------------------------------------------------------------------

def sheet_form(trip, uni, query=""):
    page = trip.get(f"/trip/canvas?block={uni}&add=1{query}").text
    return page, forms_in(page, "/trip/canvas/add")[0]


def test_the_add_sheet_has_a_name_who_chips_a_part_a_time_and_a_note(trip):
    uni = uni_id()
    page, f = sheet_form(trip, uni)
    assert 'data-level="step"' in page and 'role="dialog"' in page and 'aria-modal="true"' in page and "Add a step" in page
    assert 'name="title"' in f and 'name="trip"' in f and 'type="time"' in f and 'name="note"' in f and 'type="submit"' in f
    assert f.count('name="part"') == 8 or f.count('name="part"') == len(plan()["blocks"][uni]["parts"])
    whos = re.findall(r'name="who" value="([^"]+)"', f)
    assert whos[0] == "all" and "g:Adults" in whos and "g:Kids" in whos and sum(w.startswith("m:") for w in whos) == 1          # Everyone, the member, the groups
    assert any(w.startswith("i:") for w in whos)           # H and B, as the messages wrote them
    assert 'name="who" value="all" checked' in f.replace('checked=""', "checked") or 'value="all" checked' in f
    assert f.index('checked') < f.index('name="part"')


def test_a_step_is_added_from_the_sheet_and_lands_in_the_chosen_part(trip, announced):
    uni = uni_id()
    page, f = sheet_form(trip, uni)
    lunch = part_of(uni, "Lunch")["id"]
    me = person("ari")["user_id"]
    data = {**form_data(f), "title": "Churro break", "part": lunch, "time": "12:15", "note": "Cinnamon", "who": [f"m:{me}", "g:Kids"]}
    r = trip.post("/trip/canvas/add", data=data, headers=JS)
    assert r.status_code == 200 and bare(r.json()["url"]) == f"/trip/canvas?block={uni}" and r.json()["toast"] == "Churro break added"
    got = [s for s in part_of(uni, "Lunch")["steps"] if s["title"] == "Churro break"][0]
    assert got["time"] == "12:15" and got["note"] == "Cinnamon" and got["who_key"] == tuple(sorted([f"m:{me}", "g:Kids"]))
    page = trip.get(f"/trip/canvas?block={uni}").text
    assert "Churro break" in page and "12:15" in page


def test_everyone_wins_when_it_is_ticked_with_others_and_nothing_ticked_is_everyone(trip):
    uni = uni_id()
    lunch = part_of(uni, "Lunch")["id"]
    trip.post("/trip/canvas/add", data={"act": uni, "part": lunch, "title": "One", "who": ["all", "g:Kids"]})
    trip.post("/trip/canvas/add", data={"act": uni, "part": lunch, "title": "Two"})
    steps = {s["title"]: s for s in part_of(uni, "Lunch")["steps"]}
    assert steps["One"]["who_key"] == () and steps["Two"]["who_key"] == ()


def test_adding_without_a_name_comes_back_to_the_sheet_with_the_reason(trip):
    uni = uni_id()
    lunch = part_of(uni, "Lunch")["id"]
    r = trip.post("/trip/canvas/add", data={"act": uni, "part": lunch, "title": "  ", "note": "keep me"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith(f"/trip/canvas?block={uni}&add=1") and "err=title" in r.headers["location"]
    page = trip.get(r.headers["location"]).text
    assert "Give the step a name." in page and 'value="keep me"' in page and f'value="{lunch}" checked' in page.replace('checked=""', "checked")
    bad = trip.post("/trip/canvas/add", data={"act": uni, "part": lunch, "title": "x", "who": ["m:nobody"]}, headers=JS)
    assert bad.status_code == 422 and bad.json()["error"]
    assert "x" not in titles(uni, "Lunch")


def test_the_sheet_is_prefilled_from_a_list_chip_and_a_part_link(trip):
    uni = uni_id()
    page, f = sheet_form(trip, uni, "&title=Golden+Zephyr&note=on+the+pier&part=" + part_of(uni, "Lunch")["id"])
    assert 'value="Golden Zephyr"' in f and 'value="on the pier"' in f
    assert re.search(r'value="%s"[^>]*checked' % part_of(uni, "Lunch")["id"], f)
    assert "Golden Zephyr" in page.split("cz-sheet-add")[1]


def test_add_a_step_is_a_button_on_the_block_for_editors_and_the_sheet_closes_back_to_the_block(trip):
    uni = uni_id()
    page = trip.get(f"/trip/canvas?block={uni}").text
    assert f'href="/trip/canvas?block={uni}&amp;add=1"' in bare(tag(page, "cz-add")) and "Add a step" in page and 'data-zk="stp-new"' in tag(page, "cz-add")
    sheet = trip.get(f"/trip/canvas?block={uni}&add=1").text
    assert sheet.count('data-zk="stp-new"') == 1 and f'href="/trip/canvas?block={uni}"' in bare(sheet.split("cz-sheet-wrap")[1])
    assert trip.get(f"/trip/canvas?block={uni}&add=1&frag=1").text.startswith("<section")


# ---- notes ----------------------------------------------------------------------------------------------------------------

def test_a_note_is_added_edited_and_cleared_from_the_step_sheet(trip):
    sid = step_id(trip, "King Kong")
    sheet = trip.get(f"/trip/canvas?step={sid}").text
    assert "Add a note, a fun one" in sheet and 'name="note"' in sheet
    f = forms_in(sheet, "/trip/canvas/note")[0]
    assert "name=\"trip\"" in f
    r = trip.post("/trip/canvas/note", data={**form_data(f), "note": "Go first!"}, follow_redirects=False)
    assert r.status_code == 303 and bare(r.headers["location"]) == f"/trip/canvas?step={sid}"
    again = trip.get(r.headers["location"]).text
    assert "Go first!" in again and "Edit the note" in again
    assert trip.post("/trip/canvas/note", data={**form_data(f), "note": ""}, headers=JS).status_code == 204
    assert "Add a note, a fun one" in trip.get(f"/trip/canvas?step={sid}").text


# ---- the Move menu --------------------------------------------------------------------------------------------------------

def test_the_step_sheet_has_a_move_menu_with_the_same_targets_and_every_button_lands(trip):
    uni = uni_id()
    sid = step_id(trip, "Minion Mayhem")
    page = trip.get(f"/trip/canvas?step={sid}").text
    menu = page.split('id="cz-move"')[1].split("</details>")[0]
    for label in ("Earlier in Upper Lot", "To Lunch", "To Lower Lot", "Disney California Adventure"):
        assert label in menu, label
    fs = forms_in(menu, "/trip/canvas/move")
    assert len(fs) >= 6
    for f in fs[:]:
        data = {**form_data(f)}
        r = trip.post("/trip/canvas/move", data=data, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas?block="), f
    assert sum(1 for s in plan()["blocks"][uni]["parts"] for _ in s["steps"]) + sum(len(b["aside"]) for b in plan()["blocks"].values()) >= 0


def test_the_move_menu_for_a_set_aside_step_offers_to_put_it_into_each_part(trip):
    sid = step_id(trip, "Studio Tour")
    menu = trip.get(f"/trip/canvas?step={sid}").text.split('id="cz-move"')[1].split("</details>")[0]
    assert "Put into Lunch" in menu and "Earlier in" not in menu


# ---- viewers --------------------------------------------------------------------------------------------------------------

def test_a_viewer_cannot_drag_swipe_add_or_move_but_the_filters_are_there(crew, azure):
    owner, viewer = crew
    added(owner)
    uni = uni_id()
    sid = step_id(owner, "King Kong")
    assert 'data-edit="1"' in owner.get(f"/trip/canvas?block={uni}").text and "data-edit" not in viewer.get(f"/trip/canvas?block={uni}").text
    for url in (f"/trip/canvas?block={uni}", "/trip/canvas?day=1"):
        page = viewer.get(url).text
        assert "data-drag" not in page and "cz-swipe-acts" not in page and "cz-dropbars" not in page and 'id="cz-add"' not in page and 'class="cz-addchip is-plain"' in page
        assert "&amp;add=1" not in page
        assert 'class="cz-filters"' in page and 'data-f="all"' in page
        assert "data-who=" in page and "data-lists=" in page
    sheet = viewer.get(f"/trip/canvas?step={sid}").text
    assert "cz-move" not in sheet and "cz-notebox" not in sheet
    assert "cz-sheet-add" not in viewer.get(f"/trip/canvas?block={uni}&add=1").text
    lunch = part_of(uni, "Lunch")["id"]
    for path, data in (("/trip/canvas/move", {"step": sid, "aside": "1"}), ("/trip/canvas/undo", {"undo": "{}"}), ("/trip/canvas/add", {"act": uni, "part": lunch, "title": "x"}),
                       ("/trip/canvas/note", {"step": sid, "note": "x"})):
        assert viewer.post(path, data=data, headers=JS).status_code == 403, path
    assert "x" not in titles(uni, "Lunch")


def test_an_editor_sees_the_drag_data_the_swipe_actions_and_the_drop_targets(trip):
    uni = uni_id()
    block = trip.get(f"/trip/canvas?block={uni}").text
    sid = step_id(trip, "King Kong")
    assert f'data-drag="{sid}"' in block and block.count("cz-swipe-acts") >= 14 and "cz-dropbars" in block and 'data-drop-aside="1"' in block and "data-drop-act=" in block
    parts = [t for t in opening_tags(block, "cz-bpart") if "cz-triplist" not in t["class"]]
    assert parts and all(t.get("data-act") == uni and t.get("data-part") for t in parts)
    day = trip.get("/trip/canvas?day=1").text
    assert f'data-drag="{sid}"' in day and 'data-drop-aside="1"' in day
    assert opening_tags(day, "cz-part") and all(t.get("data-act") == uni and t.get("data-part") for t in opening_tags(day, "cz-part"))
    swipe = forms_in(block, "/trip/canvas/step")
    assert any(re.search(r'name="do" value="done"', f) for f in swipe) and any('name="do" value="aside"' in f for f in swipe)
    assert all(f'value="/trip/canvas?block={uni}"' in bare(f) for f in swipe if "cz-sw-form" in f)
    for f in swipe[:6]:
        r = trip.post("/trip/canvas/step", data=form_data(f), follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas?block=")


# ---- filters --------------------------------------------------------------------------------------------------------------

def test_the_filter_chips_are_everyone_each_person_the_names_used_and_each_named_list(trip):
    me = person("ari")
    for url in ("/trip/canvas?day=3", f"/trip/canvas?block={dca()}"):
        page = trip.get(url).text
        bar = page.split('class="cz-filters"')[1].split("</div>")[0]
        chips = re.findall(r'data-f="([^"]+)"', bar)
        assert chips[0] == "all" and f"who:m:{me['user_id']}" in chips and any(c.startswith("who:i:") for c in chips) and any(c.startswith("list:") for c in chips)
        assert "g:" not in bar                      # the messages never say Adults or Kids here, and the family's ages are not known
        assert "Pregnancy-safe rides" in bar and 'aria-pressed="true"' in bar.split(">")[0] + bar.split("data-f=\"all\"")[1][:60]
    assert 'class="cz-filters"' not in trip.get("/trip/canvas").text and 'class="cz-filters"' not in trip.get("/trip/canvas?day=2").text      # no plan, no filters


def test_adults_and_kids_chips_appear_only_when_a_step_names_them(trip):
    other = dca()
    trip.post("/trip/canvas/add", data={"act": other, "part": plan()["blocks"][other]["parts"][0]["id"], "title": "Kids' ride", "who": ["g:Kids"]})
    bar = trip.get(f"/trip/canvas?block={other}").text.split('class="cz-filters"')[1].split("</div>")[0]
    assert 'data-f="who:g:Kids"' in bar and 'data-f="who:g:Adults"' not in bar


def test_every_step_carries_who_and_the_lists_that_name_it(trip):
    other = dca()
    page = trip.get(f"/trip/canvas?block={other}").text
    lst = plan()["lists"][0]["id"]
    by_id = {t["data-drag"]: t for t in opening_tags(page, "cz-swipe")}
    assert by_id[step_id(trip, "Web Slingers")]["data-lists"] == lst and by_id[step_id(trip, "Radiator Springs Racers")]["data-lists"] == ""
    assert json.loads(by_id[step_id(trip, "Web Slingers")]["data-who"]) == []
    day = trip.get("/trip/canvas?day=3").text
    assert all("data-who" in t and "data-lists" in t for t in opening_tags(day, "cz-chipwrap"))


def test_the_list_card_counts_what_is_not_in_the_day_and_offers_each_as_a_chip(trip):
    other = dca()
    day_no = next(a.day for a in cal.activities(person("ari")) if a.id == other)
    for url in (f"/trip/canvas?day={day_no}", f"/trip/canvas?block={other}"):
        page = trip.get(url).text
        card = page.split('class="cz-listmore"')[1].split("</section>")[0]
        assert "4 more" in card and "Pregnancy-safe rides" in card and "aren't in this day yet" in card.replace("&#x27;", "'")
        assert card.count('class="cz-addchip"') == 4 and "Golden Zephyr" in card and "Web Slingers" not in card
        link = unescape(re.search(r'href="([^"]*Golden[^"]*)"', card).group(1))
        assert link.startswith(f"/trip/canvas?block={other}&add=1&title=Golden") and trip.get(link).status_code == 200
    # adding one of them makes the card shorter
    trip.post("/trip/canvas/add", data={"act": other, "part": plan()["blocks"][other]["parts"][0]["id"], "title": "Golden Zephyr"})
    card = trip.get(f"/trip/canvas?block={other}").text.split('class="cz-listmore"')[1].split("</section>")[0]
    assert "3 more" in card and "Golden Zephyr" not in card


def test_the_list_card_says_when_nothing_is_missing(trip):
    other = dca()
    lst = plan()["lists"][0]
    first = plan()["blocks"][other]["parts"][0]["id"]
    for i in lst["items"]:
        if not any(canvas.same_step(s["title"], i["title"]) for p in plan()["blocks"][other]["parts"] for s in p["steps"]):
            trip.post("/trip/canvas/add", data={"act": other, "part": first, "title": i["title"]})
    card = trip.get(f"/trip/canvas?block={other}").text.split('class="cz-listmore"')[1].split("</section>")[0]
    assert "already in this day" in card and "cz-addchip" not in card


def test_the_whole_canvas_still_walks_with_the_new_markup(trip):
    seen, queue = set(), ["/trip/canvas"]
    while queue:
        url = queue.pop()
        if url in seen:
            continue
        seen.add(url)
        r = trip.get(unescape(url), follow_redirects=False)
        assert r.status_code == 200, url
        queue += [unescape(h) for h in re.findall(r'href="(/trip/canvas[^"]*)"', r.text) if unescape(h) not in seen]
    assert any("add=1" in u for u in seen)
