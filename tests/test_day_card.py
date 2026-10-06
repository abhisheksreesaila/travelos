"""F-106: tap a plan, and its note and its chat open right there as a card over the day. The server side: the note's write (an editor edits a note of their own or adds one), the
card's fragment (the sticky, the latest few messages with "Earlier", the composer, "Rides" on a park block), the older messages, the grid's one-line note preview and chat count,
and bookings that a plan overlaps becoming slim pills in a lane of their own. The trip is the demo booking plus the plain plans each test adds (Sunday, day 2, is free)."""

import re
from html import unescape

import pytest

from gitaway import plantalk, tripcal as cal
from tests.test_canvas import azure  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_day_grid import blocks, day, plan, style
from tests.test_signin import person
from tests.test_trip_canvas import bare, tag, text, trip, uni_id  # noqa: F401 - fixtures


def ari():
    return person("ari")


def card(client, act, **q):
    from urllib.parse import urlencode
    return client.get("/trip/canvas/card?" + urlencode({"act": act, **q}), headers={"X-Canvas": "1"})


def note(client, act, text, id=""):
    return client.post("/trip/canvas/actnote", data={"act": act, "text": text, "note": id}, headers={"X-Canvas": "1"})


def say(act, n, part=""):
    for i in range(n):
        plantalk.post_message(ari(), act, part, f"message {i + 1}")


# ---- the note's write -------------------------------------------------------------------------------------------------------

def test_a_person_can_edit_a_note_of_their_own_and_nobody_elses(trip):
    me = ari()
    a = plan(me, "Pool", 10 * 60, 11 * 60)
    mine = cal.add_note(me, "H and B play", act=a.id)
    assert cal.edit_note(me, mine.id, "  H and B   play.  Back at four ").text == "H and B play. Back at four"
    assert [n.text for n in cal.notes(me) if n.act == a.id] == ["H and B play. Back at four"]
    for bad, words in (("", "Write something first."), ("x" * (cal.MAX_NOTE + 1), "Keep notes to")):
        with pytest.raises(cal.CalendarError, match=words):
            cal.edit_note(me, mine.id, bad)
    with pytest.raises(cal.CalendarError, match="not here"):
        cal.edit_note(me, "n999", "hello")
    with pytest.raises(cal.CalendarError, match="not here"):
        cal.edit_note(me, "bogus", "hello")


def test_the_card_note_route_adds_a_note_and_then_edits_it_in_place(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    r = note(trip, a.id, "Bring towels")
    got = r.json()
    assert r.status_code == 200 and got["note"]["text"] == "Bring towels" and got["note"]["id"].startswith("n")
    again = note(trip, a.id, "Bring two towels", got["note"]["id"]).json()
    assert again["note"]["id"] == got["note"]["id"] and [n.text for n in cal.notes(ari()) if n.act == a.id] == ["Bring two towels"]


def test_the_card_note_route_says_plainly_what_it_refuses(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    for act, said, id_, words in ((a.id, "", "", "Write something first."), (a.id, "x" * 141, "", "Keep notes to"), ("a999", "ok", "", "gone"), (a.id, "ok", "n999", "not here")):
        r = note(trip, act, said, id_)
        assert r.status_code == 422 and words in r.json()["error"], (act, said, id_)
    assert [n for n in cal.notes(ari()) if n.act == a.id] == []


def test_a_viewer_cannot_write_a_note(crew, azure):
    owner, viewer = crew
    added(owner)
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    assert viewer.post("/trip/canvas/actnote", data={"act": a.id, "text": "hi"}, headers={"X-Canvas": "1"}).status_code == 403
    assert [n for n in cal.notes(ari()) if n.act == a.id] == []


# ---- the card's fragment ----------------------------------------------------------------------------------------------------

def test_the_card_shows_the_note_in_full_as_a_sticky_and_an_editor_can_edit_theirs(trip):
    me = ari()
    a = plan(me, "Pool", 10 * 60, 11 * 60)
    long = "H and B play; King King; Fast and Furious and then a very long afternoon of everything else that the family wants to do today"[:cal.MAX_NOTE]
    mine = cal.add_note(me, long, act=a.id)
    html = card(trip, a.id).text
    assert long in unescape(html) and f'data-note="{mine.id}"' in html and 'data-mine="1"' in html and 'class="cz-card-note' in html
    assert "Add a note" in html                     # one quiet line for another note
    assert "Open chat" in html and f'href="/trip/talk?act={a.id}' in unescape(html)
    assert "Rides" not in html                       # a plain plan has no block level


def test_an_empty_note_is_an_add_a_note_placeholder_for_an_editor_and_nothing_for_a_viewer(crew, azure):
    owner, viewer = crew
    added(owner)
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    assert "Add a note" in card(owner, a.id).text and 'class="cz-card-note' in card(owner, a.id).text
    seen = card(viewer, a.id).text
    assert "Add a note" not in seen and "cz-card-note" not in seen and 'id="ft-compose"' in seen        # a viewer may still talk


def test_a_viewer_reads_the_note_and_cannot_edit_it(crew, azure):
    owner, viewer = crew
    added(owner)
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    cal.add_note(ari(), "Bring towels", act=a.id)
    html = card(viewer, a.id).text
    assert "Bring towels" in html and "data-note=" in html and 'data-mine="1"' not in html and "Add a note" not in html


def test_the_card_has_the_chat_the_latest_few_with_earlier_and_the_composer(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    say(a.id, 12)
    html = card(trip, a.id).text
    assert "message 12" in html and "message 5" in html and "message 4<" not in html and "message 1<" not in html
    assert 'data-more="1"' in html and "Earlier" in html
    for ident in ("ft", "ft-thread", "ft-compose", "ft-text", "pt-mic", "pt-photo", "pt-rec", "ft-error"):
        assert f'id="{ident}"' in html, ident
    assert 'data-poll-url="/trip/talk/items?act=' in html and 'name="act"' in html
    few = plan(ari(), "Ice cream", 15 * 60, 16 * 60)
    say(few.id, 3)
    assert 'data-more="0"' in card(trip, few.id).text and "Earlier" not in card(trip, few.id).text


def test_earlier_messages_come_back_in_pages_oldest_first(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    say(a.id, 16)
    first = int(re.search(r'data-first="(\d+)"', card(trip, a.id).text).group(1))
    r = trip.get(f"/trip/talk/items?act={a.id}&before={first}&limit=5")
    got = re.findall(r"message (\d+)<", r.text)
    assert r.status_code == 200 and got == ["4", "5", "6", "7", "8"] and r.headers["x-thread-more"] == "1" and int(r.headers["x-thread-first"]) < first
    rest = trip.get(f"/trip/talk/items?act={a.id}&before={r.headers['x-thread-first']}&limit=5")
    assert re.findall(r"message (\d+)<", rest.text) == ["1", "2", "3"] and rest.headers["x-thread-more"] == "0"


def test_a_park_block_card_has_rides_and_a_part_chat_is_not_in_the_plans(trip):
    uni = uni_id()
    html = unescape(card(trip, uni).text)
    assert re.search(r'<a [^>]*href="/trip/canvas\?block=%s[^"]*"[^>]*>(?:(?!</a>).)*Rides' % uni, html, re.S)
    assert 'data-zoom="in"' in html


def test_the_card_for_a_plan_that_is_gone_is_a_404_and_signed_out_goes_to_sign_in(trip):
    assert card(trip, "a999").status_code == 404
    from tests.test_members import browser
    assert browser(trip).get("/trip/canvas/card?act=a1", follow_redirects=False).status_code in (303, 401)


def test_the_card_is_for_the_open_trip_only(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    assert card(trip, a.id, trip="deadbeef").status_code == 409
