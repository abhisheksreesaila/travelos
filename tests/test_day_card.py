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


# ---- the grid: a one-line note, a chat count, bookings that stay in view --------------------------------------------------------

def block_html(page, act):
    """The markup of one plan's block: from its opening tag to where the next block, booking line or the now line starts."""
    tags = [m for m in re.finditer(r'<div\b[^>]*\bclass="cz-gb[ "][^>]*>', page)]
    (m,) = [t for t in tags if f'data-act="{act}"' in t.group(0)]
    rest = page[m.end():]
    end = re.search(r'<div\b[^>]*\bclass="cz-gb[ "]|<span[^>]*class="cz-nowline|</div>\s*</div>\s*</div>', rest)
    return m.group(0) + rest[:end.start() if end else len(rest)]


def test_a_block_shows_a_one_line_note_preview_and_no_sticky(trip):
    me = ari()
    a = plan(me, "Universal Lower Lot", 9 * 60 + 30, 11 * 60 + 30)
    cal.add_note(me, "H and B play. You can go on the big slide twice", act=a.id)
    cal.add_note(me, "Bring snacks", act=a.id)
    page = day(trip, 2)
    mine = block_html(page, a.id)
    assert re.search(r'<span class="cz-gb-note">H and B play\. You can go on the big slide twice · Bring snacks</span>', mine)
    assert "cz-sticker" not in mine and "cz-gb-notes" not in mine           # the full note is the card's, not the block's
    plain = plan(me, "Lunch", 12 * 60, 13 * 60)
    assert "cz-gb-note" not in block_html(day(trip, 2), plain.id)


def test_a_block_shows_how_much_was_said_and_a_mic_when_one_was_a_voice_note(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    assert "cz-gb-chat" not in block_html(day(trip, 2), a.id)
    say(a.id, 3)
    chip = chat_chip(day(trip, 2), a.id)
    assert text(chip) == "3" and chip.count("<svg") == 1
    from tests.voice_files import voice
    plantalk.post_voice(ari(), a.id, "", voice("mp4"), "9")
    chip = chat_chip(day(trip, 2), a.id)
    assert text(chip) == "4" and chip.count("<svg") == 2


def chat_chip(page, act):
    """The small chat count on a block: the markup from its span to the end of the block's words."""
    mine = block_html(page, act)
    at = mine.rindex("<span", 0, mine.index('class="cz-gb-chat"'))
    return mine[at:mine.index("</div>")]


def test_every_block_opens_the_card_with_a_link_that_still_works_without_script(trip):
    me = ari()
    a = plan(me, "Pool", 10 * 60, 11 * 60)
    page = day(trip, 2)
    assert re.search(r'<a [^>]*href="/trip/talk\?act=%s[^"]*"[^>]*data-card="1"[^>]*class="cz-gb-open"' % a.id, unescape(block_html(page, a.id)))
    park = block_html(day(trip, 1), uni_id())
    assert f'href="/trip/canvas?block={uni_id()}"' in unescape(park) and 'data-card="1"' in park


def lines(page):
    return re.findall(r'<a\b[^>]*class="cz-bk cz-gbk[^"]*"[^>]*>.*?</a>', page, re.S)


def test_a_booking_a_plan_overlaps_becomes_a_pill_in_its_own_lane_and_the_plan_makes_room(trip):
    """The captain's day: a 9:30 to 11:30 block over the 11 AM line. The booking stays whole, as a link to its sheet."""
    me = ari()
    over = plan(me, "Universal Lower Lot", 9 * 60 + 30, 11 * 60 + 30, day=0)
    clear = plan(me, "Beach walk", 17 * 60, 18 * 60, day=0)
    page = day(trip, 0)
    flight, hotel = lines(page)
    assert "is-pill" not in flight and "is-pill" not in hotel            # 8:05 and 3:00 PM have no plan over them: the quiet full-width lines stay

    cal.update_activity(me, over.id, start=8 * 60, end=9 * 60)           # now the plan starts under the 8:05 flight line
    page = day(trip, 0)
    flight, hotel = lines(page)
    assert "is-pill" in flight and "is-pill" not in hotel
    assert 'href="/trip/canvas?day=0&amp;booked=b-out"' in flight and "8:05 AM" in text(flight) and "--s:65" in flight
    assert 'aria-label="' in flight and "booked" in flight.lower()
    assert "is-inset" in block_html(page, over.id) and "is-inset" not in block_html(page, clear.id)
    assert "has-pill" in tag(page, "cz-grid")


def test_the_short_name_of_a_pill_is_the_first_part_of_the_booking_title(trip):
    from gitaway.pages import tripcanvas as tc
    assert tc.short_title("Check in · Hotel Maya · 2 rooms") == "Check in"
    assert tc.short_title("Delta 123 · SFO → LAX") == "Delta 123"
    assert tc.short_title("Airport") == "Airport"


# ---- review fixes ---------------------------------------------------------------------------------------------------------------

def note_texts(act):
    return [n.text for n in cal.notes(ari()) if n.act == act]


def test_the_note_route_needs_a_plan_and_a_retry_with_the_same_id_adds_nothing_twice(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    r = trip.post("/trip/canvas/actnote", data={"text": "Bring towels"}, headers={"X-Canvas": "1"})
    assert r.status_code == 422 and "plan" in r.json()["error"] and [n for n in cal.notes(ari()) if n.text == "Bring towels"] == []
    nid = f"n{cal.next_id(ari())}"
    first = trip.post("/trip/canvas/actnote", data={"act": a.id, "text": "Bring towels", "id": nid}, headers={"X-Canvas": "1"}).json()
    again = trip.post("/trip/canvas/actnote", data={"act": a.id, "text": "Bring towels", "id": nid}, headers={"X-Canvas": "1"}).json()
    assert first["note"]["id"] == again["note"]["id"] == nid and note_texts(a.id) == ["Bring towels"]


def test_the_card_carries_the_calendars_next_number_for_a_new_note(trip):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    assert f'data-next="{cal.next_id(ari())}"' in card(trip, a.id).text


def test_changing_a_note_takes_the_calendars_write_lock_like_every_other_update(trip, monkeypatch):
    a = plan(ari(), "Pool", 10 * 60, 11 * 60)
    mine = cal.add_note(ari(), "Bring towels", act=a.id)
    seen = []
    real = cal._begin
    monkeypatch.setattr(cal, "_begin", lambda *args, **kw: (seen.append(1), real(*args, **kw))[1])
    cal.edit_note(ari(), mine.id, "Bring two towels")
    assert seen


def test_plans_that_share_lanes_are_inset_together_when_any_of_them_is_over_a_booking(trip):
    me = ari()
    a = plan(me, "Long afternoon", 13 * 60, 16 * 60 + 30, day=0)       # over the 3 PM check-in line
    b = plan(me, "Late swim", 16 * 60 + 5, 17 * 60 + 30, day=0)        # shares a lane row with it, but starts after the line's reach
    c = plan(me, "Dinner", 19 * 60, 20 * 60, day=0)                    # a different row: needs no room
    page = day(trip, 0)
    assert "is-inset" in block_html(page, a.id) and "is-inset" in block_html(page, b.id) and "is-inset" not in block_html(page, c.id)


def test_a_pill_shows_the_time_and_icon_on_top_and_the_short_name_below_with_the_full_title_for_a_screen_reader(trip):
    me = ari()
    plan(me, "Long afternoon", 14 * 60, 16 * 60, day=0)
    pill = [x for x in lines(day(trip, 0)) if "is-pill" in x][0]
    top = pill[:pill.index('class="cz-bk-t"')]
    assert "<svg" in top and "3 PM" in text(top)                                          # the time and the icon come first, in one row
    assert text(pill).index("3 PM") < text(pill).index("Check in") and "Tidewater" not in text(pill) and re.search(r'aria-label="Check in · [^"]+, 3:00 PM, booked"', unescape(pill))
