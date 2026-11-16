"""F-070: the family thread. One thread per trip with messages, photos and automatic cards for plan changes; the poll fragment; roles; and the
pushes (everyone with the Morning plan on, not the author, not anyone on Quiet, at most one per person per two minutes). A fake push service
stands in for the real one; nothing here talks to the network."""

import re

import pytest

from gitaway import familythread as ft, morning, tripcal as cal
from tests.test_calendar import FORM, add, book
from tests.test_members import addr, browser, invite, tenant
from tests.test_signin import person, sign_in, tid

EP_ARI, EP_ED = "https://push.example.com/send/ari", "https://push.example.com/send/ed"
KEYS = {"p256dh": "BPubKeyPubKeyPubKey", "authkey": "AuthSecret12"}


class FakePush:
    def __init__(self, status=201):
        self.status, self.sent = status, []

    def __call__(self, sub, payload):
        self.sent.append((sub["endpoint"], payload))
        return self.status


@pytest.fixture
def push(monkeypatch):
    fake = FakePush()
    monkeypatch.setattr(ft, "SENDER", fake)
    return fake


@pytest.fixture
def crew(client):
    """Ari (admin, sample trip booked), an editor and a viewer, each in their own browser."""
    book(client)
    ed_mail, vi_mail = addr("ed"), addr("vi")
    invite(client, ed_mail, "editor"), invite(client, vi_mail, "viewer")
    ed, vi = browser(client), browser(client)
    sign_in(ed, ed_mail), sign_in(vi, vi_mail)
    ed.mail, vi.mail = ed_mail, vi_mail      # who each browser is, for the writes that go through the model
    return client, ed, vi


def tag(html, id_):
    """The opening tag of the element with this id (attributes in whatever order the page wrote them)."""
    import re
    return re.search(rf"<[^>]*\bid=\"{id_}\"[^>]*>", html).group(0)


def thread(client, since=0):
    """The trip's thread as the Together drawer reads it (F-254: /trip/plan/thread): .text is every message's words."""
    from types import SimpleNamespace
    r = client.get("/trip/plan/thread?key=trip")
    assert r.status_code == 200
    return SimpleNamespace(status_code=200, text=" ".join(i["text"] for i in r.json()["items"]))


def go_quiet(browser_, on=True):
    """My own Quiet switch (the drawer has none since F-254; the model keeps it): the browser's person, through familythread."""
    ft.set_quiet(person(browser_.mail), on)


def subscribe(client, endpoint):
    assert client.post("/trip/morning", data={"endpoint": endpoint, "time": "07:30", **KEYS}, follow_redirects=False).status_code == 200


def say(client, text, **extra):
    return client.post("/trip/family/message", data={"text": text, **extra}, headers={"X-Fragment": "1"}, follow_redirects=False)


# ---- the thread model ------------------------------------------------------------------------------------------------------

def test_a_message_is_kept_in_the_trips_thread_with_its_author(client):
    book(client)
    ari = person("ari")
    ft.post_message(ari, "  See you   at six  ")
    [it] = ft.items(ari)
    assert it["kind"] == "message" and it["text"] == "See you at six" and it["name"] == "Ari" and it["author"] == tid("ari")


def test_an_empty_or_huge_message_is_refused(client):
    book(client)
    ari = person("ari")
    for bad in ("", "   ", "x" * (ft.MAX_MESSAGE + 1)):
        with pytest.raises(ft.ThreadError):
            ft.post_message(ari, bad)
    assert ft.items(ari) == []


def test_each_trip_has_its_own_thread(client):
    from gitaway import session as ses
    book(client)
    ari = person("ari")
    ft.post_message(ari, "first trip")
    first = ses.trips(ari)[0].id
    book(client, f="f2")                    # another booking is another trip, and it is the one Ari has open now
    ari = person("ari")
    assert len(ses.trips(ari)) == 2 and ft.items(ari) == []
    ft.post_message(ari, "second trip")
    assert [i["text"] for i in ft.items(ari)] == ["second trip"]
    assert ses.switch_trip(ari, first) and [i["text"] for i in ft.items(ari)] == ["first trip"]


def test_items_come_oldest_first_and_since_returns_only_the_new_ones(client):
    book(client)
    ari = person("ari")
    for t in ("one", "two", "three"):
        ft.post_message(ari, t)
    its = ft.items(ari)
    assert [i["text"] for i in its] == ["one", "two", "three"] and its[0]["n"] < its[1]["n"] < its[2]["n"]
    assert [i["text"] for i in ft.items(ari, since=its[1]["n"])] == ["three"]


def test_a_photo_item_carries_an_image_address_and_only_a_safe_one(client):
    book(client)
    ari = person("ari")
    ft.post_photo(ari, "/assets/photos/la.jpg", "Beach!")
    for bad in ("javascript:alert(1)", "//evil.example.com/x.jpg", "http://plain.example.com/x.jpg", "", "relative.jpg"):
        with pytest.raises(ft.ThreadError):
            ft.post_photo(ari, bad)
    [it] = ft.items(ari)
    assert it["kind"] == "photo" and it["payload"]["url"] == "/assets/photos/la.jpg" and it["text"] == "Beach!"


def test_nobody_signed_in_has_no_thread(client):
    assert ft.items({}) == []


# ---- change cards from every plan write ----------------------------------------------------------------------------------

def cards(client):
    return [i["text"] for i in ft.items(person("ari")) if i["kind"] == "change"]


def test_adding_a_plan_writes_a_card_saying_who_what_and_when(client):
    book(client)
    add(client, id="a1", title="Griffith Observatory", day="1", start="10:00", end="11:00")
    [text] = cards(client)
    assert text.startswith("Ari added Griffith Observatory on ") and text.endswith(" 10:00 AM") and text.split(" on ")[1][:3] in ("Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri")


def test_moving_a_plan_writes_a_moved_card_with_the_new_time(client):
    book(client)
    add(client, id="a1", title="Griffith Observatory", day="1", start="10:00", end="11:00")
    cal.update_activity(person("ari"), "a1", day="2", start="14:30", end="15:30")
    assert cards(client)[-1].startswith("Ari moved Griffith Observatory to ") and cards(client)[-1].endswith(" 2:30 PM")


def test_resizing_a_plan_says_when_it_now_ends(client):
    book(client)
    add(client, id="a1", title="Beach", day="1", start="10:00", end="11:00")
    cal.update_activity(person("ari"), "a1", day="1", start="10:00", end="12:00")
    assert cards(client)[-1] == "Ari changed Beach to end at 12:00 PM"


def test_renaming_a_plan_writes_a_card_and_an_unchanged_save_writes_none(client):
    book(client)
    add(client, id="a1", title="Beach", day="1", start="10:00", end="11:00")
    cal.update_activity(person("ari"), "a1", day="1", start="10:00", end="11:00", title="Beach", kind="fun")
    assert len(cards(client)) == 1
    cal.update_activity(person("ari"), "a1", day="1", start="10:00", end="11:00", title="Surf lesson", kind="fun")
    assert cards(client)[-1] == "Ari renamed Beach to Surf lesson"


def test_deleting_and_undoing_write_cards(client):
    book(client)
    add(client, id="a1", title="Beach", day="1", start="10:00", end="11:00")
    cal.delete_activity(person("ari"), "a1")
    assert cards(client)[-1] == "Ari removed Beach"
    cal.undo_delete(person("ari"), "a1")
    assert cards(client)[-1] == "Ari put back Beach"


def test_applying_and_removing_a_forks_plans_write_one_card_each(client):
    from gitaway import tripcal as cal
    book(client)
    ari = person("ari")
    plans = [cal.Plan("d1s1", 1, 9 * 60, 10 * 60, "Pier walk", "fun"), cal.Plan("d1s2", 1, 12 * 60, 13 * 60, "Tacos", "food")]
    added, _ = cal.apply_plans(ari, plans, ["d1s1", "d1s2"], by="Maya")
    assert cards(client)[-1] == "Ari added Pier walk and Tacos"
    again, _ = cal.apply_plans(ari, plans, ["d1s1", "d1s2"], by="Maya")
    assert again == [] and len(cards(client)) == 1                      # nothing added, nothing said
    cal.remove_plans(ari, plans, [a.id for a in added], by="Maya")
    assert cards(client)[-1] == "Ari removed Pier walk and Tacos"


# ---- the page and the poll fragment ----------------------------------------------------------------------------------------

# ---- posting and pressing every button -----------------------------------------------------------------------------------

def test_an_empty_message_is_a_plain_error_the_page_can_show(client):
    book(client)
    r = say(client, "   ")
    assert r.status_code == 400 and "Write something first." in r.text


# ---- roles ----------------------------------------------------------------------------------------------------------------

# ---- pushes ---------------------------------------------------------------------------------------------------------------

def test_someone_who_never_turned_the_morning_plan_on_gets_no_push(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)                       # only the editor has it on
    say(ed, "hello")
    ft.drain()
    assert push.sent == []                     # the only subscriber is the author


def test_one_waiting_update_is_told_in_the_singular(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    t, mine = tenant(client), tid("ari")
    ft.notify(t, "trip", "Plan changed", "Ari added A", exclude_person=mine, now=5000)
    ft.notify(t, "trip", "Plan changed", "Ari added B", exclude_person=mine, now=5010)
    ft.flush_due(now=5000 + ft.WINDOW, send=push)
    assert push.sent[-1][1]["body"] == "1 more update on the trip"


def test_a_phone_the_push_service_refuses_for_good_is_forgotten(crew):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    gone = FakePush(410)
    ft.notify(tenant(client), "trip", "Plan changed", "Ari added A", exclude_person=tid("ari"), send=gone, now=10_000)
    assert morning.count_all() == 0


def test_a_failing_sender_does_not_break_the_change(crew, monkeypatch):
    client, ed, _ = crew
    subscribe(ed, EP_ED)

    def broken(sub, payload):
        raise OSError("push service down")
    monkeypatch.setattr(ft, "SENDER", broken)
    r = add(client, id="a1", title="Beach", day="1", start="10:00", end="11:00")
    ft.drain()
    assert r.status_code in (200, 303) and len(cards(client)) == 1 and morning.count_all() == 1


def test_a_removed_member_is_not_pushed(crew, push):
    from gitaway import members
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    ed_id = [m["user_id"] for m in members.members(tenant(client)) if members.role_in(m["user_id"], tenant(client)) == "editor"][0]
    assert client.post("/family/remove", data={"user": ed_id}, follow_redirects=False).status_code == 303
    assert members.role_in(ed_id, tenant(client)) is None
    ft.notify(tenant(client), "trip", "Plan changed", "x", exclude_person=tid("ari"), send=push, now=10_000)
    assert push.sent == []


def test_change_cards_and_their_pushes_carry_no_confirmation_numbers_and_the_push_no_prices(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    add(client, id="a1", title="Luau $85.00 per person", day="1", start="10:00", end="11:00")
    ft.drain()
    card = cards(client)[0]
    assert "Luau" in card and "GA-" not in card                      # the card is the app's own sentence about the plan
    assert "$" not in push.sent[0][1]["body"]
    from gitaway import session as ses
    b = ses.booking(person("ari"))
    assert b["id"] not in card and b["id"] not in push.sent[0][1]["body"]    # never the booking's confirmation number


def test_the_minute_loop_also_flushes_the_threads_waiting_updates(push, monkeypatch):
    from datetime import datetime, timezone
    seen = []
    monkeypatch.setattr(ft, "flush_due", lambda send=None, now=None: seen.append(send) or 0)

    class OneRound:
        def __init__(self):
            self.rounds = 0

        def wait(self, interval):
            self.rounds += 1
            return self.rounds > 1                  # false once (run a round), then true (stop)

    morning._loop(OneRound(), 0, push, lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert seen == [push]


# ---- review fixes ------------------------------------------------------------------------------------------------------

def test_deleting_an_imported_trip_deletes_its_thread(client):
    from gitaway import familydb, importer, session as ses
    from tests.test_trip_import import imported
    sign_in(client)
    assert imported(client).status_code == 303
    ari = person("ari")
    trip_id = ses.trips(ari)[0].id
    ft.post_message(ari, "before the delete")
    assert importer.delete(ari, trip_id)
    with familydb.using(ari) as db:
        assert familydb.row(db, "SELECT COUNT(*) AS n FROM thread WHERE trip_id = :t", t=trip_id)["n"] == 0


def test_saving_a_trip_again_unchanged_says_nothing_but_a_real_change_does(client):
    from dataclasses import replace
    from gitaway import importer, session as ses
    from tests.test_trip_import import imported
    sign_in(client)
    imported(client)
    ari = person("ari")
    trip_id = ses.trips(ari)[0].id
    plan = importer.plan_of(ari, trip_id)
    importer.save(ari, plan, None, trip_id)
    assert [i for i in ft.items(ari) if i["kind"] == "change"] == []
    importer.save(ari, replace(plan, title="A new name"), None, trip_id)
    [card] = [i for i in ft.items(ari) if i["kind"] == "change"]
    assert "A new name" in card["text"]


def test_a_push_is_queued_only_after_the_change_commits(client, monkeypatch):
    from gitaway import tripcal as cal
    book(client)
    queued = []
    monkeypatch.setattr(ft, "announce", lambda *a, **k: queued.append(a))
    monkeypatch.setattr(ft, "_sender", lambda send: object())
    ari = person("ari")
    real = cal._bump

    def fail_late(*a, **k):
        real(*a, **k)
        raise RuntimeError("write failed after the card was written")
    monkeypatch.setattr(cal, "_bump", fail_late)
    with pytest.raises(RuntimeError):
        cal.add_activity(ari, day=1, start="10:00", end="11:00", title="Never saved", id="a5")
    assert queued == [] and cards(client) == []        # rolled back: no card, and nobody was told
    monkeypatch.setattr(cal, "_bump", real)
    cal.add_activity(ari, day=1, start="10:00", end="11:00", title="Saved", id="a6")
    assert len(queued) == 1 and len(cards(client)) == 1


def test_one_family_cannot_read_anothers_thread(client):
    book(client)
    ft.post_message(person("ari"), "the Rivera family secret")
    other = browser(client)
    sign_in(other, addr("stranger"))
    assert "Rivera family secret" not in other.get("/trip/family", follow_redirects=True).text
    assert "Rivera family secret" not in other.get("/trip/family/thread?since=0").text
    assert "Rivera family secret" not in other.get("/trip/family/thread?since=0&trip=anything").text
    assert other.post("/trip/family/message", data={"text": "x"}, headers={"X-Fragment": "1"}).status_code in (400, 409)
    assert [i["text"] for i in ft.items(person("ari"))] == ["the Rivera family secret"]


def test_the_quiet_switch_turns_the_persons_pushes_off_and_on(client):
    book(client)
    ari = person("ari")
    assert not ft.quiet(ari)
    assert ft.set_quiet(ari, True) is True and ft.quiet(person("ari"))
    assert ft.set_quiet(ari, False) is False and not ft.quiet(person("ari"))


def test_a_viewer_may_talk_and_go_quiet_but_not_change_a_plan(crew):
    client, _, viewer = crew
    r = say(viewer, "Can I bring the dog?")
    assert r.status_code == 204 and "Can I bring the dog?" in thread(viewer).text
    go_quiet(viewer)
    assert ft.quiet(person(viewer.mail))
    refused = viewer.post("/trip/plan/write", data={"op": "add", "day": "1", "start": "600", "end": "660", "title": "Nope", "kind": "fun"}, follow_redirects=False)
    assert refused.status_code == 403
    assert [i["kind"] for i in ft.items(person("ari"))] == ["message"]     # the viewer's message is there; a refused change left no card


def test_everyone_in_the_family_sees_the_same_thread(crew):
    client, ed, viewer = crew
    say(ed, "from the editor")
    assert "from the editor" in thread(client).text and "from the editor" in thread(viewer).text


def test_a_message_pushes_everyone_with_the_morning_plan_on_but_not_the_author(crew, push):
    client, ed, viewer = crew
    subscribe(client, EP_ARI), subscribe(ed, EP_ED)
    say(client, "Dinner at 7 at Green Leaf")
    ft.drain()
    assert [e for e, _ in push.sent] == [EP_ED]
    payload = push.sent[0][1]
    assert payload["title"] == "Ari" and payload["body"] == "Dinner at 7 at Green Leaf" and payload["url"] == "/trip/plan" and payload["tag"] == "family-thread"


def test_a_plan_change_pushes_the_others_with_the_card_text(crew, push):
    client, ed, _ = crew
    subscribe(client, EP_ARI), subscribe(ed, EP_ED)
    add(ed, traveler=ed.mail, id="a1", title="Griffith Observatory", day="1", start="10:00", end="11:00")
    ft.drain()
    assert [e for e, _ in push.sent] == [EP_ARI]
    assert push.sent[0][1]["title"] == "Plan changed" and push.sent[0][1]["url"] == "/trip/plan"
    assert " added Griffith Observatory on " in push.sent[0][1]["body"] and not push.sent[0][1]["body"].startswith("Ari ")   # the editor added it, not Ari


def test_quiet_turns_pushes_off_for_that_person_only(crew, push):
    client, ed, _ = crew
    subscribe(client, EP_ARI), subscribe(ed, EP_ED)
    go_quiet(ed, True)
    say(client, "anyone?")
    ft.drain()
    assert push.sent == []
    go_quiet(ed, False)
    say(client, "again?")
    ft.drain()
    assert [e for e, _ in push.sent] == [EP_ED]


def test_a_burst_is_one_push_then_one_summary_when_the_window_ends(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    t = tenant(client)
    mine = tid("ari")
    for i in range(4):
        ft.notify(t, "trip", "Plan changed", f"Ari added Plan {i}", exclude_person=mine, now=1000 + i * 10)
    assert len(push.sent) == 1 and "Plan 0" in push.sent[0][1]["body"]            # the first goes at once; the other three wait
    assert ft.flush_due(now=1000 + 60, send=push) == 0 and len(push.sent) == 1     # the window (two minutes) has not ended
    assert ft.flush_due(now=1000 + ft.WINDOW + 1, send=push) == 1
    assert len(push.sent) == 2 and push.sent[1][1]["body"] == "3 more updates on the trip" and push.sent[1][1]["url"] == "/trip/plan"
    assert ft.flush_due(now=1000 + 10 * ft.WINDOW, send=push) == 0 and len(push.sent) == 2    # told once
    ft.notify(t, "trip", "Plan changed", "Ari added Later", exclude_person=mine, now=1000 + 10 * ft.WINDOW)
    assert len(push.sent) == 3                                                     # a quiet spell later, the next one goes at once


def test_going_quiet_drops_what_was_waiting(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    t, mine = tenant(client), tid("ari")
    ft.notify(t, "trip", "Plan changed", "Ari added A", exclude_person=mine, now=9000)
    ft.notify(t, "trip", "Plan changed", "Ari added B", exclude_person=mine, now=9010)
    go_quiet(ed, True)
    assert ft.flush_due(now=9000 + ft.WINDOW + 5, send=push) == 0 and len(push.sent) == 1


def test_a_message_is_the_persons_own_words_and_a_price_in_it_is_not_filtered_from_the_thread(crew, push):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    say(client, "Luau $85.00 per person")
    assert "$85.00" in thread(client).text          # what someone types stays as typed in the thread...
    ft.drain()
    assert "$" not in push.sent[0][1]["body"]       # ...but the lock screen never shows an amount


def test_without_push_keys_and_no_test_sender_nothing_is_sent_or_queued(crew, monkeypatch):
    client, ed, _ = crew
    subscribe(ed, EP_ED)
    monkeypatch.setattr(ft, "SENDER", None)
    assert not morning.configured()
    assert ft.notify(tenant(client), "trip", "t", "b", exclude_person="x", now=10_000) == 0 and ft.flush_due(now=10**6) == 0
    say(client, "still works")
    ft.drain()
    assert "still works" in thread(client).text


def test_text_is_escaped(client):
    book(client)
    ft.post_message(person("ari"), "<script>alert(1)</script>")
    r = client.get("/trip/plan/thread?key=trip")
    assert r.headers["content-type"].startswith("application/json")      # the drawer's thread is JSON, never markup the server wrote around someone's words...
    assert r.json()["items"][0]["text"] == "<script>alert(1)</script>"
    js = open(__import__("pathlib").Path(__file__).resolve().parent.parent / "assets" / "js" / "v2plan.js", encoding="utf-8").read()
    assert "b.appendChild(document.createTextNode(i.text))" in js and "innerHTML = i.text" not in js      # ...and the script adds every word as a text node, so it is shown, not run


def test_signed_out_gets_nothing(client):
    assert client.get("/trip/plan/thread?key=trip", follow_redirects=False).status_code == 303      # through sign-in
    assert client.post("/trip/family/message", data={"text": "hi"}, follow_redirects=False).status_code == 401
    assert client.post("/trip/talk/message", data={"act": "a1", "text": "hi"}, follow_redirects=False).status_code == 401


def test_a_message_names_its_trip_and_a_stale_tab_is_refused(client):
    from gitaway import session as ses
    book(client)
    first = ses.trips(person("ari"))[0].id
    book(client, f="f2")                                   # a second trip is opened; the old tab still shows the first
    add(client, id="a1")
    r = say(client, "into the old trip", trip=first)
    assert r.status_code == 204                            # it went to the trip the tab was drawn for
    assert [i for i in ft.items(person("ari")) if i["kind"] == "message"] == []      # not into the one open now
    ari = person("ari")
    second = ses.trips(ari)[0].id
    assert ses.switch_trip(ari, first) and [i["text"] for i in ft.items(ari)] == ["into the old trip"]
    ses.switch_trip(ari, second)
    gone = say(client, "nowhere", trip="no-such-trip")
    assert gone.status_code == 409 and "Reload" in gone.text and "Traceback" not in gone.text
    plan = client.post("/trip/talk/message", data={"act": "a1", "text": "nowhere", "trip": "no-such-trip"}, headers={"X-Fragment": "1"})
    assert plan.status_code in (400, 409) and "Traceback" not in plan.text and plan.text      # a plan of a trip the family does not have: refused in a sentence, nothing written
