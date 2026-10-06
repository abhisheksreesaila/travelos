"""Talk to plan (F-024) through the HTTP seam: the mic, the question, the preview, apply, undo and refresh."""

import re
from pathlib import Path

from tests.test_calendar import FORM, add, book, tag
from tests.test_signin import session_data, sign_in, stored_calendar, tid

ROOT = Path(__file__).resolve().parent.parent
TWO_NIGHTS = {"d": "2026-10-21", "r": "2026-10-23", "a": "2"}
LIMIT = 3600


def cookie_size(client):
    return len(client.cookies.get("session_") or "")


def activities(client):
    return stored_calendar()["a"]


def notes(client):
    return stored_calendar()["n"]


def drafts(html):
    """{plan key: attributes} for the dashed draft blocks in the grid."""
    out = {}
    for m in re.findall(r'<div[^>]*cal-draft[^>]*>', html):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', m))
        out[a["data-key"]] = a
    return out


def rows(html):
    """{plan key: (checked, disabled)} for the checkboxes in the panel."""
    out = {}
    for m in re.findall(r"<input[^>]*vo-check[^>]*>", html):
        out[re.search(r'data-plan="([^"]+)"', m).group(1)] = ("checked" in m.split(), "disabled" in m.split())
    return out


def apply(client, night, *keys, **extra):
    return client.post("/calendar/voice/apply", data={"night": str(night), "pick": list(keys), **extra}, follow_redirects=False)


def applied_ids(r):
    return re.search(r"voiced=([^&]+)", r.headers["location"]).group(1)


# ---- the mic -------------------------------------------------------------------------------------------------------

def test_the_calendar_has_a_mic_in_both_views_and_it_opens_talk_to_plan(client):
    book(client)
    for view in ("whole", "days"):
        html = client.get(f"/calendar?view={view}").text
        m = re.search(r'<a[^>]*vo-open[^>]*>', html)
        assert m and "voice=1" in m.group(0) and "hear=1" in m.group(0) and "view=days" in m.group(0)
        assert "Talk to plan" in html
    assert "vo-panel" not in html and "cal-draft" not in html


def test_no_audio_is_ever_captured():
    """The scripted Talk to plan (F-024) captures nothing. The one place that listens is Ask GitAway's hold-to-talk (F-072, assets/js/ask.js): the browser's own
    speech recognition fills the text box, the page never records or keeps audio, and no other file may touch speech recognition.
    The one exception is a plan's chat (F-091, assets/js/plantalk.js): a person taps the mic to leave a voice note, which is recorded only until Send or Cancel."""
    for path in [*(ROOT / "assets/js").glob("*.js"), *(ROOT / "gitaway").rglob("*.py")]:
        text = path.read_text(encoding="utf-8")
        if path.name not in ("plantalk.js", "ask.js"):      # F-102: Ask's mic records too, where the browser has no speech recognition (tap, Stop or Cancel; never kept)
            assert "getUserMedia" not in text.replace("never call getUserMedia", ""), path.name
            assert "MediaRecorder" not in text, path.name
        if path.name != "ask.js":
            assert "SpeechRecognition" not in text, path.name


def test_signed_out_and_unbooked_cannot_use_voice(client):
    assert client.get("/calendar?voice=1", follow_redirects=False).status_code == 303
    for path, data in [("/calendar/voice/apply", {"night": "0", "pick": ["v1"]}), ("/calendar/voice/undo", {"ids": "a1", "night": "0"})]:
        r = client.post(path, data=data, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin")
    sign_in(client)
    assert "Your calendar starts with a trip" in client.get("/calendar?voice=1").text
    r = client.post("/calendar/voice/apply", data={"night": "0", "pick": ["v1"]}, follow_redirects=False)
    assert r.status_code == 303 and "session_" in client.cookies and not activities(client)


# ---- listening, the question and the preview -------------------------------------------------------------------------

def test_the_panel_shows_the_sentence_and_waits_for_the_one_question(client):
    book(client)
    before = cookie_size(client)
    html = client.get("/calendar?voice=1&hear=1").text
    assert 'data-hear="1"' in html and "Tacos for dinner" in html and "beach walk on our last day" in html
    assert "Tacos on which night?" in html and "Fri 16, 6:30 PM" in html and "Sat 17, 6:30 PM" in html
    got = rows(html)
    assert set(got) == {"v1", "v2", "v3"} and all(c and not d for c, d in got.values())   # three plans so far, ticked
    assert "Waiting for your answer" in html
    btn = tag(html, "id", "vo-apply")
    assert "disabled" in html[html.index('id="vo-apply"') - 200:html.index('id="vo-apply"') + 300]
    assert set(drafts(html)) == {"v1", "v2", "v3"}                                          # drafts in the grid, nothing saved
    assert cookie_size(client) == before and not activities(client)


def test_the_animation_only_plays_when_the_mic_was_tapped(client):
    book(client)
    assert 'data-hear="1"' not in client.get("/calendar?voice=1&night=0").text
    assert 'data-hear="1"' not in client.get("/calendar?voice=1").text


def test_answering_the_question_adds_the_tacos_and_a_different_answer_moves_them(client):
    book(client)
    one = client.get("/calendar?voice=1&night=0").text
    assert set(drafts(one)) == {"v0", "v1", "v2", "v3"} and drafts(one)["v0"]["data-day"] == "0"
    assert "Waiting for your answer" not in one and len(rows(one)) == 4
    two = client.get("/calendar?voice=1&night=1").text
    assert drafts(two)["v0"]["data-day"] == "1" and drafts(two)["v0"]["data-key"] == "v0"
    assert chips(two) == {"Fri 16, 6:30 PM": False, "Sat 17, 6:30 PM": True}                  # the chosen chip is marked
    assert chips(one) == {"Fri 16, 6:30 PM": True, "Sat 17, 6:30 PM": False}
    assert "disabled" not in html_of_button(two)


def chips(html):
    """{chip label: picked} for the question chips."""
    return {re.sub(r"<[^>]+>", "", body): 'aria-current="true"' in attrs for attrs, body in re.findall(r"<a([^>]*vo-chip[^>]*)>(.*?)</a>", html)}


def html_of_button(html):
    i = html.index('id="vo-apply"')
    return html[html.rfind("<button", 0, i):html.index(">", i)]


def test_a_bad_answer_is_treated_as_no_answer(client):
    book(client)
    for bad in ("9", "-1", "x", "1.5", "99999999999999999999"):
        html = client.get(f"/calendar?voice=1&night={bad}").text
        assert "Waiting for your answer" in html and set(drafts(html)) == {"v1", "v2", "v3"}


def test_the_plans_sit_in_the_right_slots_around_the_bookings(client):
    book(client)
    d = drafts(client.get("/calendar?voice=1&night=0").text)
    assert [(d[k]["data-day"], d[k]["data-start"], d[k]["data-end"]) for k in ("v0", "v1", "v2", "v3")] == [
        ("0", "1110", "1200"), ("2", "1020", "1170"), ("3", "540", "690"), ("4", "540", "630")]


def test_a_plan_over_the_familys_plan_is_ticked_and_tagged_and_applies(client):
    book(client)
    add(client, id="a1", day="2", start="17:00", end="18:00", title="Sunset picnic")
    html = client.get("/calendar?voice=1&night=0").text
    assert rows(html)["v1"] == (True, False) and "Overlaps Sunset picnic" in html
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    assert r.status_code == 303
    assert "Griffith Observatory at sunset" in [a["t"] for a in activities(client)] and "Sunset picnic" in [a["t"] for a in activities(client)]


# ---- apply, notes, refresh, undo ---------------------------------------------------------------------------------------

def test_apply_drops_the_plans_in_and_logs_a_trip_note(client):
    book(client)
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    assert r.status_code == 303 and r.headers["location"].startswith("/calendar?") and "view=days" in r.headers["location"]
    acts = activities(client)
    assert [a["t"] for a in acts] == ["Tacos at Mariscos La Ola", "Griffith Observatory at sunset", "Pool time at The Tidewater", "Beach walk before the flight home"]
    assert [(a["d"], a["s"]) for a in acts] == [(0, 1110), (2, 1020), (3, 540), (4, 540)] and all("b" not in a for a in acts)
    assert len(notes(client)) == 1 and notes(client)[0]["t"].startswith("Planned by voice: Tacos Fri, Observatory Sun")
    html = client.get(r.headers["location"]).text
    assert "Planned by voice: Tacos Fri" in html and "cal-pop" in html and "Added 4 plans by voice" in html
    for a in acts:
        assert a["t"] in html


def test_posting_the_same_apply_again_adds_nothing(client):
    book(client)
    apply(client, 0, "v0", "v1", "v2", "v3")
    first, note_count = list(activities(client)), len(notes(client))
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    assert r.status_code == 303 and activities(client) == first and len(notes(client)) == note_count
    html = client.get("/calendar?voice=1&night=0").text
    assert "Already on your calendar" in html and all(c is False and d is True for c, d in rows(html).values())


def test_apply_needs_the_answer_and_only_adds_real_plan_keys(client):
    book(client)
    r = client.post("/calendar/voice/apply", data={"pick": ["v1"]}, follow_redirects=False)
    assert r.status_code == 409 and "Pick a night" in r.text and not activities(client)
    r = apply(client, 0, "v1", "v9", "<script>", "a1")
    assert [a["t"] for a in activities(client)] == ["Griffith Observatory at sunset"]
    assert apply(client, 7, "v1").status_code == 409                                       # not one of the offered nights


def test_nothing_ticked_adds_nothing_and_no_note(client):
    book(client)
    r = apply(client, 0)
    assert r.status_code == 303 and not activities(client)


def test_undo_takes_back_only_what_that_apply_added(client):
    book(client)
    add(client, id="a1", day="1", start="10:00", end="11:30", title="Venice Canals stroll")
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    ids = applied_ids(r)
    nid = re.search(r"vnote=(n\d+)", r.headers["location"]).group(1)
    assert len(activities(client)) == 5
    undo = client.post("/calendar/voice/undo", data={"ids": ids, "night": "0", "nid": nid}, follow_redirects=False)
    assert undo.status_code == 303
    assert [a["t"] for a in activities(client)] == ["Venice Canals stroll"] and notes(client) == []


def test_undo_cannot_remove_the_travelers_own_plans_or_other_notes(client):
    book(client)
    add(client, id="a1", day="1", start="10:00", end="11:30", title="Venice Canals stroll")
    client.post("/calendar/notes", data={"id": "n2", "text": "Planned by voice: a lookalike on a plan", "act": "a1"})
    client.post("/calendar/notes", data={"id": "n3", "text": "Bring sunscreen"})
    client.post("/calendar/voice/undo", data={"ids": "a1", "night": "0", "nid": "n3"})
    client.post("/calendar/voice/undo", data={"ids": "a1", "night": "0", "nid": "n2"})
    assert [a["t"] for a in activities(client)] == ["Venice Canals stroll"] and len(notes(client)) == 2
    client.post("/calendar/voice/undo", data={"ids": "a99,x,<b>", "night": "0"})
    assert len(activities(client)) == 1


def test_the_undo_toast_goes_away_once_undone(client):
    book(client)
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    ids, loc = applied_ids(r), r.headers["location"]
    assert 'action="/calendar/voice/undo"' in client.get(loc).text
    client.post("/calendar/voice/undo", data={"ids": ids, "night": "0"})
    assert 'action="/calendar/voice/undo"' not in client.get(loc).text


# ---- trips of any shape ----------------------------------------------------------------------------------------------

def book_two_nights(client):
    sign_in(client, "ari")
    return client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", **TWO_NIGHTS}, follow_redirects=False)


def test_a_two_night_trip_uses_its_middle_day_and_says_so(client):
    book_two_nights(client)                                                  # Wed 21 .. Fri 23
    html = client.get("/calendar?voice=1&night=0").text
    d = drafts(html)
    assert [d[k]["data-day"] for k in ("v0", "v1", "v2", "v3")] == ["0", "1", "1", "2"]
    assert "No Sunday on this trip, so Thu 22" in html and "No Monday on this trip, so Thu 22" in html
    assert list(chips(html)) == ["Wed 21, 6:30 PM"]                          # Thu evening is the observatory's
    assert set(rows(html).values()) == {(True, False)}
    assert apply(client, 0, "v0", "v1", "v2", "v3").status_code == 303 and len(activities(client)) == 4


def test_a_two_day_trip_shows_overlaps_with_the_flight_home_and_nothing_crashes(client):
    sign_in(client, "ari")
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-21", "r": "2026-10-22", "a": "2"})
    html = client.get("/calendar?voice=1&night=0").text
    assert client.get("/calendar?voice=1&night=0").status_code == 200
    assert rows(html)["v1"] == (True, False)                                 # the observatory runs into the flight home: kept (F-086)
    assert apply(client, 0, "v0", "v1", "v2", "v3").status_code == 303
    assert "Griffith Observatory at sunset" in [a["t"] for a in activities(client)]


def test_a_trip_with_its_own_sunday_uses_it(client):
    sign_in(client, "ari")
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-23", "r": "2026-10-28", "a": "2"})   # Fri 23 .. Wed 28
    d = drafts(client.get("/calendar?voice=1&night=0").text)
    assert d["v1"]["data-day"] == "2" and d["v2"]["data-day"] == "3"                     # Sun 25, Mon 26


def test_the_long_fixture_works_too(client):
    book(client)
    html = client.get("/calendar?voice=1&night=0&demo=long").text
    assert client.get("/calendar?voice=1&night=0&demo=long").status_code == 200 and "vo-panel" in html


# ---- the cookie budget -------------------------------------------------------------------------------------------------

def fill(client):
    for i in range(300):
        r = add(client, id=f"a{i + 1}", day=str(1 + i % 3), start=f"{8 + i % 12:02d}:00", end=f"{8 + i % 12:02d}:30", title="x" * 40)
        if r.status_code == 409:
            return
    raise AssertionError("never full")


def test_a_full_calendar_refuses_the_apply_with_a_friendly_message_and_changes_nothing(client, monkeypatch):
    from gitaway import tripcal
    monkeypatch.setattr(tripcal, "MAX_ACTIVITIES", 5)
    book(client)
    fill(client)
    before = [dict(a) for a in activities(client)]
    r = apply(client, 0, "v0", "v1", "v2", "v3")
    assert r.status_code == 409 and "a lot planned" in r.text and "vo-panel" in r.text
    assert activities(client) == before and notes(client) == []


def test_an_apply_writes_to_the_database_and_leaves_the_cookie_alone(client):
    book(client)
    before = cookie_size(client)
    apply(client, 0, "v0", "v1", "v2", "v3")
    assert len(activities(client)) == 4 and notes(client) and cookie_size(client) <= before + 40


# ---- motion ---------------------------------------------------------------------------------------------------------

def test_reduced_motion_turns_off_every_voice_animation():
    css = (ROOT / "assets/css/voice.css").read_text()
    block = css[css.index("prefers-reduced-motion"):]
    for name in ("is-listening .vo-mic", "vo-bar", "vo-pop", "is-applying"):
        assert name in block, name
    js = (ROOT / "assets/js/voice.js").read_text()
    assert "prefers-reduced-motion" in js


# ---- review fixes: the mic, announcements, double clicks --------------------------------------------------------------

def test_the_mic_in_the_panel_is_a_real_button_that_still_works_without_scripts(client):
    book(client)
    html = client.get("/calendar?voice=1&night=0").text
    m = re.search(r'<form[^>]*vo-micform[^>]*>.*?</form>', html, re.S)
    assert m and 'method="get"' in m.group(0) and 'action="/calendar"' in m.group(0)
    assert re.search(r'<button[^>]*vo-mic[^>]*>', m.group(0)) and 'type="submit"' in m.group(0)
    for name, value in (("voice", "1"), ("hear", "1"), ("view", "days")):
        assert f'name="{name}" value="{value}"' in m.group(0)
    assert not re.search(r'<a[^>]*vo-mic', html)


def test_there_is_a_polite_live_region_for_the_transcript(client):
    book(client)
    html = client.get("/calendar?voice=1&hear=1").text
    m = re.search(r'<div[^>]*vo-live[^>]*>', html)
    assert m and 'role="status"' in m.group(0) and "sr-only" in m.group(0)
    assert re.search(r'<div[^>]*vo-live[^>]*></div>', html)                  # empty until the sentence has been heard


def test_the_script_finishes_hearing_the_same_way_with_and_without_motion():
    js = (ROOT / "assets/js/voice.js").read_text()
    assert "function finish" in js and js.count("finish(") >= 3               # defined, and called on the typed and the reduced-motion paths
    assert "Play the demo sentence again" in js and "vo-live" in js
    assert "disabled = true" in js                                           # a double click cannot post twice
    assert "calSwap" in js and "calSwap" in (ROOT / "assets/js/calendar.js").read_text()


def test_the_helpers_calendar_uses_are_public():
    from gitaway.pages import voice as ui
    assert ui.parse_ids("a1,b2,a22") == ["a1", "a22"] and ui.note_id("n5") == "n5" and ui.note_id("x") == ""


# ---- book any mix (F-033): bookings with a lane skipped -----------------------------------------------------------------

def book_mix(client, **pick):
    sign_in(client, "ari")
    return client.post("/pay", data=pick, follow_redirects=False)


def test_a_flight_only_booking_has_no_pool_plan_and_still_applies(client):
    book_mix(client, f="f1", h="none", c="none")
    html = client.get("/calendar?voice=1&night=0").text
    assert client.get("/calendar?voice=1&night=0").status_code == 200
    assert set(drafts(html)) == {"v0", "v1", "v3"} and "Pool time" not in html
    r = apply(client, 0, "v0", "v1", "v3")
    assert r.status_code == 303 and len(activities(client)) == 3
    assert "Beach walk before the flight home" in [a["t"] for a in activities(client)]


def test_the_panel_says_the_sentence_that_matches_the_plans(client):
    book(client)
    assert "pool time Monday morning" in client.get("/calendar?voice=1").text
    sign_in(client, "sam")
    client.post("/pay", data={"f": "f1", "h": "none", "c": "none"})
    html = client.get("/calendar?voice=1").text
    assert "Tacos for dinner" in html and "pool" not in html.lower() and "a beach walk on our last day." in html


def test_a_stay_only_booking_has_no_flight_window_and_a_plain_beach_walk(client):
    book_mix(client, f="none", h="h1", c="none")
    html = client.get("/calendar?voice=1&night=0").text
    assert set(drafts(html)) == {"v0", "v1", "v2", "v3"} and all(c for c, d in rows(html).values())    # nothing clashes with a flight that is not there
    apply(client, 0, "v0", "v1", "v2", "v3")
    titles = [a["t"] for a in activities(client)]
    assert "Beach walk" in titles and "Beach walk before the flight home" not in titles and "Pool time at The Tidewater" in titles
    assert activities(client)


def test_a_car_only_booking_does_not_crash(client):
    book_mix(client, f="none", h="none", c="c1")
    r = client.get("/calendar?voice=1&night=0")
    assert r.status_code == 200 and set(drafts(r.text)) == {"v0", "v1", "v3"}
    assert apply(client, 0, "v0", "v1", "v3").status_code == 303 and len(activities(client)) == 3
    assert client.post("/calendar/voice/undo", data={"ids": "a1,a2,a3", "night": "0"}, follow_redirects=False).status_code == 303


# ---- F-037: focus after Apply, and the booked note ---------------------------------------------------------------------

def test_the_voice_undo_toast_takes_focus_when_the_calendar_loads(client):
    book(client)
    html = client.get(apply(client, 0, "v0", "v1").headers["location"]).text
    undo = re.search(r"<button[^>]*cal-undo[^>]*>", html).group(0)
    assert "autofocus" in undo.split() and "aria-describedby=\"cal-toast-text\"" in undo
    assert re.search(r"id=\"cal-toast-text\"[^>]*>Added 2 plans by voice", html)

