"""F-091: talk on the block, through HTTP: the chat page, the three posts (script and no script), what is refused, viewers, the audio's address (family only, byte
ranges for iPhone), the Family tab's labels and the canvas badges. Fixtures and the park day are in tests/test_plantalk.py."""

import re
from html import unescape

import pytest

from gitaway import familythread as ft, plantalk, tripcal as cal, voicenotes
from tests.photo_files import image
from tests.test_canvas import announced, azure  # noqa: F401 - fixtures
from tests.test_members import addr, browser, invite
from tests.test_plantalk import ari, ids, trip  # noqa: F401 - fixtures and helper
from tests.test_signin import person, sign_in
from tests.voice_files import voice


def up(client, kind, data, act, part="", name=None, **fields):
    field, mime = ("voice", "audio/webm") if kind == "voice" else ("photo", "image/jpeg")
    return client.post(f"/trip/talk/{kind}", files={field: (name or f"x.{field}", data, mime)}, data={"act": act, "part": part, **fields}, headers={"X-Fragment": "1"}, follow_redirects=False)


@pytest.fixture
def crew(trip):
    """Ari (admin, with the trip), a viewer, and a stranger with a family of their own, each in a browser."""
    vi_mail = addr("vi")
    invite(trip, vi_mail, "viewer")
    vi, other = browser(trip), browser(trip)
    sign_in(vi, vi_mail)
    sign_in(other, addr("stranger"))
    return trip, vi, other


def test_the_chat_page_names_the_plan_and_part_and_goes_back_to_its_day(trip, ari):
    act, lunch, stroll = ids(ari)
    r = trip.get(f"/trip/talk?act={act}&part={lunch}")
    assert r.status_code == 200
    html = unescape(r.text)
    assert "Lunch" in html and "Universal" in html and 'id="ft-compose"' in html and 'id="pt-mic"' in html and 'id="pt-photo"' in html
    day = cal.get_activity(ari, act).day
    assert f'href="/trip/canvas?day={day}' in html and 'data-poll-url="/trip/talk/items?act=' in html
    assert 'name="act"' in html and f'value="{lunch}"' in html
    assert trip.get(f"/trip/talk?act={stroll}").status_code == 200


def test_a_chat_for_a_plan_that_is_not_here_goes_to_the_canvas_and_signed_out_to_sign_in(trip):
    assert trip.get("/trip/talk?act=a999", follow_redirects=False).headers["location"] == "/trip/canvas"
    assert browser(trip).get("/trip/talk?act=a1", follow_redirects=False).headers["location"].startswith("/signin")


def test_a_message_voice_note_and_photo_are_posted_and_come_back_as_a_fragment(trip, ari):
    act, lunch, _ = ids(ari)
    r = trip.post("/trip/talk/message", data={"act": act, "part": lunch, "text": "Mario Kart after lunch"}, headers={"X-Fragment": "1"})
    assert r.status_code == 200 and "Mario Kart after lunch" in r.text and r.headers["x-thread-last"]
    r = up(trip, "voice", voice("mp4"), act, lunch, secs="75", since=r.headers["x-thread-last"])
    assert r.status_code == 200 and 'class="vn"' in r.text and "1:15" in r.text and "/trip/talk/voice/" in r.text and "Mario Kart" not in r.text
    r = up(trip, "photo", image("jpeg"), act, lunch, since=r.headers["x-thread-last"])
    assert r.status_code == 200 and "/trip/photos/" in r.text
    assert [i["kind"] for i in plantalk.items(ari, act, lunch)] == ["message", "voice", "photo"]


def test_without_script_a_post_redirects_to_the_chat(trip, ari):
    act, lunch, _ = ids(ari)
    r = trip.post("/trip/talk/message", data={"act": act, "part": lunch, "text": "hi"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/talk?act=") and f"part={lunch}" in r.headers["location"]


def test_refused_uploads_get_a_plain_message(trip, ari):
    act, _, _ = ids(ari)
    cases = [(up(trip, "voice", b"", act, secs="5"), 400, "empty"), (up(trip, "voice", image("jpeg"), act, secs="5"), 415, "not a voice note"),
             (up(trip, "voice", voice(), act, secs="500"), 413, "up to 3 minutes"), (up(trip, "voice", voice(), act), 400, "no length"),
             (up(trip, "voice", voice("webm", voicenotes.MAX_BYTES + 10), act, secs="5"), 413, "too large"),
             (up(trip, "photo", b"", act), 400, "empty"), (up(trip, "photo", b"%PDF-1.7", act), 415, "Only JPEG"),
             (up(trip, "voice", voice(), "a999", secs="5"), 400, "plan is not here"),
             (trip.post("/trip/talk/message", data={"act": act, "text": "  "}, headers={"X-Fragment": "1"}), 400, "Write something")]
    for r, status, words in cases:
        assert r.status_code == status and words in r.text, (status, words, r.status_code, r.text[:80])
    assert plantalk.counts(person("ari")) == {}


def test_a_photo_over_the_cap_is_refused_before_it_is_read(trip, ari):
    act, _, _ = ids(ari)
    r = up(trip, "photo", b"\xff\xd8\xff" + b"\x00" * (15 * 1024 * 1024 + 200_000), act)
    assert r.status_code == 413 and "too large" in r.text


def test_viewers_may_talk_but_the_plan_stays_theirs_to_read(crew, ari):
    _, vi, _ = crew
    act, lunch, _ = ids(ari)
    assert vi.post("/trip/talk/message", data={"act": act, "text": "can I come?"}, headers={"X-Fragment": "1"}).status_code == 200
    assert up(vi, "voice", voice(), act, lunch, secs="3").status_code == 200
    assert up(vi, "photo", image("png"), act).status_code == 200
    assert vi.get(f"/trip/talk?act={act}").status_code == 200
    assert len(plantalk.items(ari, act)) == 2 and len(plantalk.items(ari, act, lunch)) == 1


def test_a_voice_note_is_played_by_the_family_with_byte_ranges_and_nobody_else(crew, ari):
    trip, vi, other = crew
    act, lunch, _ = ids(ari)
    up(trip, "voice", voice("mp4", 1000), act, lunch, secs="4")
    [it] = plantalk.items(ari, act, lunch)
    path = f"/trip/talk/voice/{it['id']}"
    for who in (trip, vi):
        r = who.get(path)
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4" and len(r.content) == 1000 and r.headers["accept-ranges"] == "bytes"
        assert "private" in r.headers["cache-control"] and r.headers["x-content-type-options"] == "nosniff"
    part = trip.get(path, headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and len(part.content) == 10 and part.headers["content-range"] == "bytes 10-19/1000"
    assert other.get(path).status_code == 404                              # another family's file is not served
    assert browser(trip).get(path).status_code == 401
    assert trip.get("/trip/talk/voice/..%2F..%2Fx").status_code == 404 and trip.get("/trip/talk/voice/" + "a" * 32).status_code == 404


def test_another_family_cannot_talk_on_this_familys_plan(crew, ari):
    _, _, other = crew
    act, _, _ = ids(ari)
    r = other.post("/trip/talk/message", data={"act": act, "text": "hi"}, headers={"X-Fragment": "1"})
    assert r.status_code in (400, 403, 409)
    assert plantalk.counts(ari) == {}


def test_the_family_tab_shows_each_message_labelled_with_its_plan_and_plays_voice(trip, ari):
    act, lunch, stroll = ids(ari)
    plantalk.post_message(ari, act, lunch, "Mario Kart after lunch")
    plantalk.post_voice(ari, stroll, "", voice(), 9)
    html = unescape(trip.get("/trip/family").text)
    assert "on Lunch · " in html and "on Venice Canals stroll" in html and f"/trip/talk?act={act}&part={lunch}" in html
    assert 'class="vn"' in html and "0:09" in html and "voicenote.js" in html
    assert "on Venice Canals stroll" in unescape(trip.get("/trip/family/thread?since=0").text)


def test_the_canvas_shows_a_small_badge_and_a_quiet_start_on_plain_plans_only(trip, ari):
    act, lunch, stroll = ids(ari)
    day = cal.get_activity(ari, stroll).day
    uni_day = cal.get_activity(ari, act).day
    html = unescape(trip.get(f"/trip/canvas?day={day}").text)
    assert html.count("pt-badge-new") >= 1 and f"/trip/talk?act={stroll}" in html           # "+ chat" on the plain plan's card
    park = unescape(trip.get(f"/trip/canvas?day={uni_day}").text)
    assert f"/trip/talk?act={act}" in park and f"part={lunch}" not in park                    # no chat badge on a part until something was said
    plantalk.post_message(ari, act, lunch, "yes")
    plantalk.post_voice(ari, act, lunch, voice(), 3)
    plantalk.post_message(ari, stroll, "", "hi")
    park = unescape(trip.get(f"/trip/canvas?day={uni_day}").text)
    m = re.search(r'<a [^>]*href="/trip/talk\?act=%s&part=%s[^"]*"[^>]*>(.*?)</a>' % (act, lunch), park, re.S)
    assert m and ">2<" in m.group(1) and "<rect" in m.group(1)                              # the count, and the mic icon for the voice note
    assert "2 messages, with a voice note" in park
    assert f"part={lunch}" in unescape(trip.get(f"/trip/canvas?block={act}").text)
    plain = unescape(trip.get(f"/trip/canvas?day={day}").text)
    assert "1 message" in plain


def test_a_plan_message_pushes_the_family_with_the_plan_named(trip, ari, monkeypatch):
    from tests.test_thread import FakePush, subscribe
    fake = FakePush()
    monkeypatch.setattr(ft, "SENDER", fake)
    act, lunch, _ = ids(ari)
    mate_mail = addr("mate")
    invite(trip, mate_mail, "editor")
    mate = browser(trip)
    sign_in(mate, mate_mail)
    subscribe(mate, "https://push.example.com/send/mate")
    trip.post("/trip/talk/message", data={"act": act, "part": lunch, "text": "Mario Kart after lunch"}, headers={"X-Fragment": "1"})
    ft.drain()
    [(endpoint, payload)] = fake.sent
    assert endpoint.endswith("/mate") and payload["title"] == "Ari" and payload["body"].startswith("on Lunch · ") and "Mario Kart" in payload["body"]
