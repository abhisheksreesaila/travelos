"""F-081: the trip canvas through HTTP. Week, day, block and step each have an address; every link and button on them is pressed; viewers read and cannot write; and
Today and the canvas lead to each other. The trip is the captain's Universal + California Adventure messages through the canned model answer (no network)."""

import json
import re
from html import unescape

import pytest

from gitaway import canvas, familydb, session as ses, tripcal as cal
from tests.test_canvas import announced, azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_signin import person, sign_in


@pytest.fixture
def trip(client, azure):
    from tests.test_calendar import book
    book(client)
    added(client)
    return client


def step_id(client, title):
    me = person("ari")
    block = canvas.plan(me)["blocks"]
    for blk in block.values():
        for s in [*[s for p in blk["parts"] for s in p["steps"]], *blk["aside"]]:
            if s["title"] == title:
                return s["id"]
    raise AssertionError(title)


def uni_id():
    return cal.activities(person("ari"))[0].id


def bare(s):
    """The page with the trip id taken off every address (the addresses carry it; most tests do not care which trip)."""
    return re.sub(r"(?:\?|&amp;|&)trip=[0-9a-f]+", "", s)


def text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def links(html, prefix="/trip/canvas"):
    return sorted({unescape(h) for h in re.findall(r'href="([^"]+)"', html) if h.startswith(prefix)})


def tag(html, ident):
    return re.search(r'<[a-z0-9]+\b[^>]*\bid="%s"[^>]*>' % ident, html).group(0)


def run(sql, **kw):
    me = person("ari")
    with ses.family(me) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, sql, **kw)


# ---- who can open it -------------------------------------------------------------------------------------------------------

def test_signed_out_goes_to_sign_in_and_a_family_with_no_trip_to_start(client):
    assert client.get("/trip/canvas", follow_redirects=False).headers["location"].startswith("/signin")
    sign_in(client)
    assert client.get("/trip/canvas", follow_redirects=False).headers["location"] == "/start"


def test_the_canvas_is_inside_the_phone_shell_with_today_current(trip):
    r = trip.get("/trip/canvas")
    assert r.status_code == 200 and 'class="ph-tabs"' in r.text and 'aria-current="page"' in tag(r.text, "ph-tab-today") and 'data-level="week"' in r.text
    assert 'src="/assets/js/trip_canvas.js' in r.text and "trip_canvas.css" in r.text and 'id="cz"' in r.text


# ---- the week --------------------------------------------------------------------------------------------------------------

def test_the_week_has_a_row_per_day_park_days_with_parts_and_free_days_with_a_plus(trip):
    page = trip.get("/trip/canvas").text
    rowsed = re.findall(r'data-day="\d" class="(cz-row[^"]*)"', page)
    assert len(rowsed) == 5 and sum("is-free" in r for r in rowsed) == 1        # the sample trip is five days; the two park days are the only plans, flights on the ends
    assert "Universal Studios Hollywood" in page and "Disney California Adventure" in page
    for part in ("Lower Lot", "Harry Potter world", "Pixar Pier", "Grizzly Peak"):
        assert part in page
    assert "4 rides" in page and "8 rides" in page      # Lower Lot, Upper Lot
    assert 'class="cz-sticker cz-sticker-week' in page and "roughest ride" in page       # a note rides along on the park day
    assert 'href="/trip/canvas?day=1"' in bare(page) and 'href="/trip/canvas?day=3"' in bare(page)
    assert 'class="cz-plus"' in page and 'href="/trip?add=1&amp;day=2"' in page
    assert "Pinch or tap to zoom" in page


def test_the_zoom_control_goes_to_today_week_and_day(trip):
    page = trip.get("/trip/canvas").text
    assert 'href="/trip"' in tag(page, "cz-z-today") and 'aria-current="page"' in tag(page, "cz-z-week")
    assert "/trip/canvas?day=1" in tag(page, "cz-z-day")     # the first park day, since the demo trip is before its dates
    day = trip.get("/trip/canvas?day=1").text
    assert 'aria-current="page"' in tag(day, "cz-z-day") and 'href="/trip/canvas"' in bare(tag(day, "cz-z-week"))


# ---- the day ---------------------------------------------------------------------------------------------------------------

def test_a_day_shows_its_block_with_parts_chips_stickers_who_and_the_set_aside_tray(trip):
    page = trip.get("/trip/canvas?day=1").text
    assert 'data-level="day"' in page and re.search(r'<h1[^>]*id="cz-title"[^>]*>(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)<', page)
    for part in ("Lower Lot", "Lunch", "Harry Potter world", "Upper Lot"):
        assert part in page
    assert page.count('class="cz-chip') >= 14 and "Revenge of the Mummy" in page
    assert "roughest ride" in page and 'cz-sticker cz-sticker-chip' in page         # notes stuck on their ride
    assert "Set aside · 2" in page and "Studio Tour" in page and "Simpsons" in page   # the day's tray
    me = person("ari")["user_id"]
    run("UPDATE block_steps SET who = :w WHERE title = 'Hippogriff'", w=json.dumps([f"m:{me}", "n:Bhoomija"]))
    hippo = next(c for c in trip.get("/trip/canvas?day=1").text.split('class="cz-chipwrap"') if "Hippogriff" in c.split("</a>")[0])
    assert 'aria-label="Bhoomija"' in hippo and "cz-av-named" in hippo and "cz-av-member" in hippo               # who, as avatars: a member, and a name nobody matched
    init = next(c for c in page.split('class="cz-chipwrap"') if "Hippogriff" in c.split("</a>")[0])
    assert "cz-av-initials" in init and "not matched to a person" in init               # H and B, as the messages wrote them, dashed
    assert f'href="/trip/canvas?block={uni_id()}"' in bare(page) and f'href="/trip/canvas?step={step_id(trip, "King Kong")}"' in bare(page)


def test_the_unmatched_initials_are_drawn_dashed(trip):
    page = trip.get("/trip/canvas?day=3").text
    assert "cz-av-initials" in page


def test_a_free_day_has_an_add_link_for_editors(trip):
    page = trip.get("/trip/canvas?day=2").text
    assert 'id="cz-empty"' in page and "Add something fun" in page and 'href="/trip?add=1&amp;day=2"' in page


def test_a_day_that_does_not_exist_goes_back_to_the_week(trip):
    for bad in ("?day=99", "?day=x", "?block=a99", "?step=nope"):
        r = trip.get("/trip/canvas" + bad, follow_redirects=False)
        assert r.status_code == 303 and bare(r.headers["location"]) == "/trip/canvas", bad


# ---- the block -------------------------------------------------------------------------------------------------------------

def test_a_block_shows_parts_as_sections_with_steps_and_the_tray(trip):
    page = trip.get(f"/trip/canvas?block={uni_id()}").text
    assert 'data-level="block"' in page and page.count("cz-bpart cz-pt-") >= 4 and "Pregnancy-safe rides" in page
    assert "Set aside · 2" in page and "0 of 14 done" in page and "cz-lanes" not in page    # nobody splits up in the messages
    assert f'href="/trip/canvas?day=1"' in bare(page) and 'aria-label="Zoom out to the day"' in page


def test_steps_at_the_same_time_for_different_people_become_lanes_and_nothing_else_does(trip):
    uni = uni_id()
    me = person("ari")["user_id"]
    run("UPDATE block_steps SET time = '13:00', who = :w WHERE title = 'Forbidden Journey'", w=json.dumps(["g:Adults"]))
    run("UPDATE block_steps SET time = '13:00' WHERE title = 'Hippogriff'")
    page = trip.get(f"/trip/canvas?block={uni}").text
    assert page.count('class="cz-lanes"') == 1 and page.count('class="cz-lane"') == 2 and "Lanes: people who split up" in page
    start = page.index('class="cz-lanes"')
    lanes = page[start:page.index("</section>", start)]
    assert "Forbidden Journey" in lanes and "Hippogriff" in lanes and "Adults" in lanes and lanes.index("Forbidden Journey") < lanes.index("Hippogriff")
    # the same time for the same people stays one run, full width
    run("UPDATE block_steps SET who = :w WHERE title = 'Forbidden Journey'", w=json.dumps(["n:Bhoomija", f"m:{me}"]))
    run("UPDATE block_steps SET who = :w WHERE title = 'Hippogriff'", w=json.dumps(["n:Bhoomija", f"m:{me}"]))
    assert "cz-lanes" not in trip.get(f"/trip/canvas?block={uni}").text
    # Everyone beside one person is a split too: "Everyone / per person"
    run("UPDATE block_steps SET who = '[]' WHERE title = 'Forbidden Journey'")
    again = trip.get(f"/trip/canvas?block={uni}").text
    assert 'class="cz-lanes"' in again and "Everyone" in again


def test_a_block_shows_the_calendar_notes_written_on_it(trip):
    uni = uni_id()
    cal.add_note(person("ari"), "Bring the stroller", act=uni)
    page = trip.get(f"/trip/canvas?block={uni}").text
    assert "Bring the stroller" in page and "cz-sticker" in page
    assert "Bring the stroller" in trip.get("/trip/canvas?day=1").text


# ---- the step --------------------------------------------------------------------------------------------------------------

def test_the_step_sheet_has_the_note_who_and_the_buttons(trip):
    sid = step_id(trip, "Hippogriff")
    page = trip.get(f"/trip/canvas?step={sid}").text
    assert 'data-level="step"' in page and 'role="dialog"' in page and 'aria-modal="true"' in page and "Hippogriff" in page
    assert "H and B walk" in page and "From your messages" in page and page.count("cz-av-initials") >= 2
    assert "Mark done" in page and "Set aside" in page and 'action="/trip/canvas/step"' in page and 'name="trip"' in page
    assert f'data-zk="stp-{sid}"' in page and page.count(f'data-zk="stp-{sid}"') == 1       # the open step is the sheet, never also its row
    assert f'href="/trip/canvas?block={uni_id()}"' in bare(page)
    aside = trip.get(f"/trip/canvas?step={step_id(trip, 'Studio Tour')}").text
    assert "Put back" in aside and "Mark done" in aside and "Set aside · still in the trip" in aside


def test_mark_done_from_the_sheet_zooms_back_to_the_block_with_the_step_done(trip, announced):
    sid = step_id(trip, "Revenge of the Mummy")
    r = trip.post("/trip/canvas/step", data={"step": sid, "do": "done", "next": f"/trip/canvas?block={uni_id()}"}, follow_redirects=False)
    assert r.status_code == 303 and bare(r.headers["location"]) == f"/trip/canvas?block={uni_id()}"
    page = trip.get(r.headers["location"]).text
    assert "1 of 14 done" in page and re.search(r'data-step="%s"[^>]*class="cz-step is-done"' % sid, page)
    assert "Not done" in trip.get(f"/trip/canvas?step={sid}").text
    assert any("finished Revenge of the Mummy" in c["text"] for c in rows(person("ari"), "SELECT * FROM thread"))      # the family hears about it


def test_set_aside_and_put_back_from_the_sheet(trip):
    sid = step_id(trip, "King Kong")
    trip.post("/trip/canvas/step", data={"step": sid, "do": "aside", "next": "/trip/canvas?day=1"})
    day = trip.get("/trip/canvas?day=1").text
    assert "Set aside · 3" in day and "Put back" in trip.get(f"/trip/canvas?step={sid}").text
    trip.post("/trip/canvas/step", data={"step": sid, "do": "back", "next": "/trip/canvas?day=1"})
    assert "Set aside · 2" in trip.get("/trip/canvas?day=1").text
    trip.post("/trip/canvas/step", data={"step": sid, "do": "done"})
    trip.post("/trip/canvas/step", data={"step": sid, "do": "undone"})
    assert "1 of 14" not in trip.get(f"/trip/canvas?block={uni_id()}").text


def test_a_write_from_the_script_answers_204_and_names_the_level_to_zoom_out_to(trip):
    sid = step_id(trip, "King Kong")
    r = trip.post("/trip/canvas/step", data={"step": sid, "do": "done", "next": "/trip/canvas?day=1"}, headers={"x-canvas": "1"}, follow_redirects=False)
    assert r.status_code == 204 and r.headers["x-canvas-url"] == "/trip/canvas?day=1"


def test_the_way_back_after_a_write_can_only_be_a_canvas_address(trip):
    sid = step_id(trip, "King Kong")
    for evil in ("https://evil.example/", "//evil.example", "/calendar", "", "/trip/canvasX\nSet-Cookie: a=b"):
        r = trip.post("/trip/canvas/step", data={"step": sid, "do": "done", "next": evil}, follow_redirects=False)
        assert r.headers["location"] in ("/trip/canvas",) or r.headers["location"].startswith("/trip/canvas"), evil
        assert not r.headers["location"].startswith("//")


def test_a_step_that_is_gone_is_not_an_error(trip):
    r = trip.post("/trip/canvas/step", data={"step": "nope", "do": "done", "next": "/trip/canvas"}, follow_redirects=False)
    assert r.status_code == 303


# ---- fragments -------------------------------------------------------------------------------------------------------------

def test_a_fragment_is_the_level_alone(trip):
    for q, level in (("", "week"), ("?day=1", "day"), (f"?block={uni_id()}", "block"), (f"?step={step_id(trip, 'King Kong')}", "step")):
        sep = "&" if q else "?"
        full = trip.get("/trip/canvas" + q).text
        frag = trip.get("/trip/canvas" + q + sep + "frag=1")
        assert frag.status_code == 200 and frag.text.startswith("<section") and f'data-level="{level}"' in frag.text
        assert "<html" not in frag.text and "ph-tabs" not in frag.text
        assert frag.text in full or text(frag.text) in text(full)
        assert "no-store" in frag.headers["cache-control"]


# ---- every link and button is pressed --------------------------------------------------------------------------------------

def test_every_link_on_every_level_lands(trip):
    seen, queue = set(), ["/trip/canvas"]
    while queue:
        url = queue.pop()
        if url in seen:
            continue
        seen.add(url)
        r = trip.get(url, follow_redirects=False)
        assert r.status_code == 200, url
        queue += [u for u in links(r.text) if u not in seen]
    assert len(seen) > 30         # the week, its days, 2 blocks and every step of them
    for level in ("week", "day", "block", "step"):
        assert any(trip.get(u).text.count(f'data-level="{level}"') for u in list(seen)[:60])


def test_every_button_on_the_sheet_lands_where_it_says(trip):
    sid = step_id(trip, "Minion Mayhem")
    page = trip.get(f"/trip/canvas?step={sid}").text
    forms = re.findall(r"<form[^>]*>.*?</form>", page, re.S)
    assert len(forms) == 2
    for f in forms:
        data = {n: unescape(v) for n, v in re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', f)}
        r = trip.post(unescape(re.search(r'action="([^"]+)"', f).group(1)), data=data, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas?block=")


def test_the_back_buttons_zoom_out_one_level(trip):
    uni = uni_id()
    assert 'href="/trip/canvas?day=1"' in bare(trip.get(f"/trip/canvas?block={uni}").text)
    assert 'aria-label="Zoom out to the week"' in trip.get("/trip/canvas?day=1").text
    sheet = trip.get(f"/trip/canvas?step={step_id(trip, 'King Kong')}").text
    assert bare(sheet).count(f'href="/trip/canvas?block={uni}"') >= 2       # the scrim and the close button


# ---- viewers ---------------------------------------------------------------------------------------------------------------

def test_a_viewer_reads_every_level_and_sees_no_buttons_and_no_plus(crew, azure):
    owner, viewer = crew
    added(owner)
    sid = step_id(owner, "King Kong")
    assert 'class="cz-plus"' not in viewer.get("/trip/canvas").text and 'class="cz-plus"' in owner.get("/trip/canvas").text
    for url in ("/trip/canvas", "/trip/canvas?day=1", f"/trip/canvas?block={uni_id()}"):
        assert viewer.get(url).status_code == 200
    sheet = viewer.get(f"/trip/canvas?step={sid}").text
    assert "King Kong" in sheet and "Mark done" not in sheet and "Set aside</button>" not in sheet and "look at this step but not change it" in sheet
    assert viewer.get("/trip/canvas?day=2").text.count("Add something fun") == 0
    r = viewer.post("/trip/canvas/step", data={"step": sid, "do": "done", "next": "/trip/canvas"}, follow_redirects=False)
    assert r.status_code == 403
    assert "1 of 14" not in owner.get(f"/trip/canvas?block={uni_id()}").text


# ---- Today and the canvas lead to each other ------------------------------------------------------------------------------

def test_today_has_a_week_view_link_for_every_role_and_the_canvas_links_to_today(crew, azure):
    owner, viewer = crew
    added(owner)
    for who in (owner, viewer):
        today = who.get("/trip").text
        assert 'href="/trip/canvas"' in bare(tag(today, "tp-open-canvas")) and "Week view" in today
        assert 'href="/trip"' in tag(who.get("/trip/canvas").text, "cz-z-today")
    assert 'id="tp-open-canvas"' not in owner.get("/trip?tab=notes").text


# ---- review fixes ----------------------------------------------------------------------------------------------------------

def test_a_step_whose_block_was_deleted_goes_back_to_the_week(trip):
    sid = step_id(trip, "King Kong")
    assert trip.get(f"/trip/canvas?step={sid}").status_code == 200
    cal.delete_activity(person("ari"), uni_id())
    r = trip.get(f"/trip/canvas?step={sid}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas")


def test_a_step_on_a_day_outside_the_trip_is_not_opened(trip):
    run("UPDATE activities SET day = 99 WHERE act_id = :a", a=uni_id())
    sid = step_id(trip, "King Kong")
    assert trip.get(f"/trip/canvas?step={sid}", follow_redirects=False).status_code == 303


def test_an_unknown_address_never_answers_a_fragment_with_a_whole_page(trip):
    for q in ("?day=99", "?block=a99", "?step=nope"):
        r = trip.get("/trip/canvas" + q + "&frag=1", follow_redirects=False)
        assert r.status_code == 404 and "<html" not in r.text, q


def test_the_open_aside_step_is_the_sheet_and_not_also_its_tray_chip(trip):
    sid = step_id(trip, "Studio Tour")
    page = trip.get(f"/trip/canvas?step={sid}").text
    assert page.count(f'data-zk="stp-{sid}"') == 1
    other = trip.get(f"/trip/canvas?step={step_id(trip, 'Simpsons')}").text
    assert f'data-zk="stp-{sid}"' in other      # the other steps keep theirs


def trip_of(html):
    return re.search(r"[?&]trip=([0-9a-f]+)", html).group(1)


def test_canvas_addresses_carry_the_trip_so_a_stale_tab_stays_on_its_trip(trip):
    from tests.test_calendar import book
    from tests.test_family_storage import THREE_NIGHTS
    week = trip.get("/trip/canvas").text
    old = trip_of(week)
    sid = step_id(trip, "King Kong")
    assert all(f"trip={old}" in h for h in links(week) if "?" in h and h != "/trip/canvas")
    book(trip, **THREE_NIGHTS)                                  # a second trip, now the open one
    assert "Universal" not in trip.get("/trip/canvas").text
    stale = trip.get(f"/trip/canvas?day=1&trip={old}").text
    assert "Universal Studios Hollywood" in stale and f"trip={old}" in stale
    sheet = trip.get(f"/trip/canvas?step={sid}&trip={old}").text
    assert f"trip={old}" in sheet and 'name="trip"' in sheet and f'value="{old}"' in sheet
    assert trip.get(f"/trip/block?id=a1&trip={old}", follow_redirects=False).headers["location"] == f"/trip/canvas?block=a1&trip={old}"


def test_week_view_links_in_today_keep_their_trip(trip):
    today = trip.get("/trip?day=1").text
    assert re.search(r'href="/trip/canvas\?block=a1&amp;trip=[0-9a-f]+"', today)
