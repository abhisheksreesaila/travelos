"""F-066: the morning plan push. The text is a pure function; the subscriptions live in the family database; a clock you pass in
drives the sender, with a fake push service. Nothing here talks to a real push service."""

import json
import os
import re
from datetime import datetime, timezone

import pytest

from gitaway import morning, tripday as td
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in
from tests.test_trip_import import SECRETS, imported

EP = "https://push.example.com/send/abc123"
KEYS = {"p256dh": "BPubKeyPubKeyPubKey", "authkey": "AuthSecret12"}


def utc(day, hh, mm=0):
    """An instant in October 2026 (UTC). The sample trip is Oct 16-20, in Los Angeles (UTC-7)."""
    return datetime(2026, 10, day, hh, mm, tzinfo=timezone.utc)


def la(day, hh, mm=0):
    """The same instant given as Los Angeles wall-clock time."""
    return utc(day, hh + 7, mm) if hh + 7 < 24 else utc(day + 1, hh + 7 - 24, mm)


class FakePush:
    """Stands in for the push service: records what was sent and answers with a status code."""

    def __init__(self, status=201):
        self.status, self.sent = status, []

    def __call__(self, sub, payload):
        self.sent.append((sub["endpoint"], payload))
        return self.status


def subscribe(client, endpoint=EP, time="07:30", **keys):
    return client.post("/trip/morning", data={"endpoint": endpoint, "time": time, **(keys or KEYS)}, follow_redirects=False)


def plan(client, id="a1", day="1", start="09:00", end="10:00", title="Griffith Observatory"):
    return client.post("/calendar/activities", data={"id": id, "day": day, "start": start, "end": end, "title": title, "kind": "culture"}, follow_redirects=False)


@pytest.fixture
def ari(client):
    """Ari with the sample trip (Oct 16-20, Los Angeles) booked and one plan on its second day (Oct 17)."""
    book(client)
    plan(client)
    return client


# ---- the text (pure) ------------------------------------------------------------------------------------------------------

def test_the_message_names_the_first_plans_with_times():
    m = morning.message("Los Angeles", "during", [(9 * 60, "Griffith Observatory"), (12 * 60 + 30, "Tacos"), (15 * 60, "Beach")])
    assert m == {"title": "Today's plan · Los Angeles", "body": "9:00 AM Griffith Observatory · 12:30 PM Tacos · 3:00 PM Beach", "url": "/trip"}


def test_a_long_day_shows_three_plans_and_counts_the_rest():
    plans = [(h * 60, f"Plan {h}") for h in (8, 9, 10, 11, 12)]
    assert morning.message("Maui", "during", plans)["body"] == "8:00 AM Plan 8 · 9:00 AM Plan 9 · 10:00 AM Plan 10 · +2 more"


def test_an_empty_trip_day_still_gets_a_nudge():
    assert "Nothing planned yet" in morning.message("Maui", "during", [])["body"]


@pytest.mark.parametrize("phase", ["before", "after", None])
def test_nothing_outside_the_trip_days(phase):
    assert morning.message("Maui", phase, [(540, "Beach")]) is None


def test_prices_and_long_titles_are_cleaned_from_the_text():
    body = morning.message("Maui", "during", [(540, "Luau $85.00 per person"), (600, "x" * 80)])["body"]
    assert "$" not in body and "85" not in body and "x" * 50 not in body


# ---- the card and the keys -------------------------------------------------------------------------------------------------

def test_without_keys_nothing_is_offered_and_nothing_starts(monkeypatch):
    for k in ("GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    assert not morning.configured() and morning.start() is None


def test_the_keys_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "pub"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "priv"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    assert morning.configured() and morning.vapid() == {"public": "pub", "private": "priv", "subject": "mailto:a@b.co"}


def test_the_generated_keys_sign_a_real_push_request():
    from pywebpush import webpush
    from scripts import vapid_keys
    pair = vapid_keys.make_pair()
    # a real subscription's keys (a throwaway browser key pair), so pywebpush can encrypt; curl=True builds the request without sending it
    from cryptography.hazmat.primitives.asymmetric import ec
    import base64
    k = ec.generate_private_key(ec.SECP256R1())
    raw = k.public_key().public_numbers()
    p256dh = base64.urlsafe_b64encode(b"\x04" + raw.x.to_bytes(32, "big") + raw.y.to_bytes(32, "big")).rstrip(b"=").decode()
    out = webpush({"endpoint": EP, "keys": {"p256dh": p256dh, "auth": "dGVzdC1hdXRoLTEyMzQ1Ng"}}, data="{}", vapid_private_key=pair["private"], vapid_claims={"sub": "mailto:a@b.co"}, curl=True)
    assert "vapid" in out and pair["public"] in out  # the Authorization header carries the public key it was signed for


def test_the_card_shows_only_when_push_is_set_up(ari, monkeypatch):
    monkeypatch.delenv("GITAWAY_VAPID_PUBLIC", raising=False)
    assert 'id="tp-morning"' not in ari.get("/trip").text
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    html = ari.get("/trip").text
    assert 'id="tp-morning"' in html and 'data-key="BPublicKey"' in html
    assert "Add GitAway to your Home Screen to get a morning plan" in html and "/assets/js/morning.js" in html and 'id="tp-morning-time"' in html
    assert "data-private" not in html and "GITAWAY_VAPID_PRIVATE" not in html


# ---- subscribing, changing the time, turning off -----------------------------------------------------------------------------

def test_turning_it_on_saves_the_device_with_the_default_time(ari):
    r = subscribe(ari)
    assert r.status_code == 200 and r.json() == {"on": True, "time": "07:30"}
    s = ari.post("/trip/morning/status", data={"endpoint": EP}).json()
    assert s == {"on": True, "time": "07:30"}


def test_a_device_that_never_subscribed_is_off(ari):
    assert ari.post("/trip/morning/status", data={"endpoint": EP}).json() == {"on": False, "time": "07:30"}


def test_subscribing_again_updates_the_one_row(ari):
    subscribe(ari, time="08:00"), subscribe(ari, time="08:15", p256dh="NewKey123456", authkey="NewAuth12345")
    assert ari.post("/trip/morning/status", data={"endpoint": EP}).json() == {"on": True, "time": "08:15"}
    assert morning.count_all() == 1


def test_the_time_can_be_changed(ari):
    subscribe(ari)
    r = ari.post("/trip/morning/time", data={"endpoint": EP, "time": "06:45"})
    assert r.status_code == 200 and r.json() == {"on": True, "time": "06:45"}
    assert ari.post("/trip/morning/status", data={"endpoint": EP}).json()["time"] == "06:45"


def test_a_time_that_is_not_a_time_is_refused(ari):
    subscribe(ari)
    for bad in ("", "25:00", "7:30am", "07:60"):
        assert ari.post("/trip/morning/time", data={"endpoint": EP, "time": bad}).status_code == 400
    assert subscribe(ari, endpoint="http://insecure.example.com/x").status_code == 400
    assert subscribe(ari, endpoint="https://x.example.com/" + "a" * 3000).status_code == 400
    assert subscribe(ari, p256dh="").status_code == 400


def test_turning_it_off_deletes_the_subscription(ari):
    subscribe(ari)
    r = ari.post("/trip/morning/off", data={"endpoint": EP})
    assert r.status_code == 200 and r.json() == {"on": False, "time": "07:30"}
    assert morning.count_all() == 0
    assert ari.post("/trip/morning/off", data={"endpoint": EP}).status_code == 200  # twice is fine


def test_signed_out_gets_a_401_not_a_page(client):
    for path in ("/trip/morning", "/trip/morning/time", "/trip/morning/off", "/trip/morning/status"):
        assert client.post(path, data={"endpoint": EP, "time": "07:30", **KEYS}, follow_redirects=False).status_code == 401


def test_a_viewer_manages_their_own_reminder_but_not_anyone_elses(ari):
    viewer_mail = addr("vi")
    invite(ari, viewer_mail, "viewer")
    viewer = browser(ari)
    sign_in(viewer, viewer_mail)
    assert subscribe(viewer, endpoint="https://push.example.com/send/viewer").status_code == 200
    assert viewer.post("/trip/morning/status", data={"endpoint": "https://push.example.com/send/viewer"}).json()["on"] is True
    subscribe(ari)
    # the viewer cannot switch off Ari's device by knowing its address
    viewer.post("/trip/morning/off", data={"endpoint": EP})
    assert ari.post("/trip/morning/status", data={"endpoint": EP}).json()["on"] is True
    assert viewer.post("/trip/morning/off", data={"endpoint": "https://push.example.com/send/viewer"}).status_code == 200
    assert viewer.post("/trip/morning/status", data={"endpoint": "https://push.example.com/send/viewer"}).json()["on"] is False


def test_the_card_works_for_a_viewer_too(ari, monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    viewer_mail = addr("vi")
    invite(ari, viewer_mail, "viewer")
    viewer = browser(ari)
    sign_in(viewer, viewer_mail)
    assert 'id="tp-morning"' in viewer.get("/trip").text


# ---- the sender ------------------------------------------------------------------------------------------------------------

def test_it_sends_once_each_trip_morning_at_the_chosen_time(ari):
    subscribe(ari)
    push = FakePush()
    assert morning.run_once(la(17, 7, 29), push) == [] and push.sent == []              # a minute early
    assert len(morning.run_once(la(17, 7, 30), push)) == 1
    endpoint, payload = push.sent[0]
    assert endpoint == EP and payload["title"] == "Today's plan · Los Angeles" and payload["url"] == "/trip/canvas?day=1"      # Oct 17 is day 2 of the trip: the push opens its day plan (F-090)
    assert "9:00 AM Griffith Observatory" in payload["body"]
    morning.run_once(la(17, 7, 31), push), morning.run_once(la(17, 8, 0), push)
    assert len(push.sent) == 1                                                          # not again the same day
    morning.run_once(la(18, 7, 30), push)
    assert len(push.sent) == 2 and "Griffith" not in push.sent[1][1]["body"]            # tomorrow's plan, not today's


def test_it_uses_the_time_the_person_chose(ari):
    subscribe(ari, time="09:15")
    push = FakePush()
    morning.run_once(la(17, 7, 30), push)
    assert push.sent == []
    morning.run_once(la(17, 9, 15), push)
    assert len(push.sent) == 1


def test_a_missed_minute_is_made_up_for_within_the_hour_but_not_later(ari):
    subscribe(ari)
    push = FakePush()
    morning.run_once(la(17, 8, 20), push)                       # the process was down at 7:30
    assert len(push.sent) == 1
    morning.run_once(la(18, 9, 0), push)                        # an hour and a half late: the morning is gone
    assert len(push.sent) == 1


def test_nothing_is_sent_before_or_after_the_trip(ari):
    subscribe(ari)
    push = FakePush()
    morning.run_once(la(15, 7, 30), push)                       # the day before it starts
    morning.run_once(la(21, 7, 30), push)                       # the day after it ends
    assert push.sent == []
    morning.run_once(la(16, 7, 30), push), morning.run_once(la(20, 7, 30), push)   # first and last day
    assert len(push.sent) == 2


def test_nothing_is_sent_when_the_family_has_no_trip(client):
    sign_in(client)
    subscribe(client)
    push = FakePush()
    morning.run_once(la(17, 7, 30), push)
    assert push.sent == [] and morning.count_all() == 1         # the reminder is kept for when a trip is planned


def test_the_chosen_time_is_in_the_trip_time_zone(ari):
    from fh_saas.db_tenant import get_or_create_tenant_db
    from sqlalchemy import text
    s = person()
    db = get_or_create_tenant_db(s["tenant_id"])
    db.conn.execute(text("UPDATE trips SET timezone = 'America/New_York'")), db.conn.commit(), db.conn.close()
    subscribe(ari)
    push = FakePush()
    morning.run_once(la(17, 7, 30), push)                       # 10:30 AM in New York: the 7:30 there passed three hours ago
    assert push.sent == []
    morning.run_once(utc(17, 11, 30), push)                     # 7:30 AM EDT
    assert len(push.sent) == 1


def test_turning_it_on_after_the_time_has_passed_waits_for_tomorrow(ari):
    morning.subscribe(person(), EP, KEYS["p256dh"], KEYS["authkey"], 7 * 60 + 30, now=la(17, 7, 40))
    push = FakePush()
    morning.run_once(la(17, 7, 41), push)
    assert push.sent == []
    morning.run_once(la(18, 7, 30), push)
    assert len(push.sent) == 1


def test_changing_the_time_to_a_later_one_still_sends_today(ari):
    morning.subscribe(person(), EP, KEYS["p256dh"], KEYS["authkey"], 7 * 60 + 30, now=la(17, 6, 0))
    push = FakePush()
    morning.set_time(person(), EP, 8 * 60, now=la(17, 7, 45))
    morning.run_once(la(17, 8, 0), push)
    assert len(push.sent) == 1


def test_an_expired_subscription_is_dropped_quietly(ari, caplog):
    for status in (404, 410):
        subscribe(ari)
        morning.run_once(la(17, 7, 30), FakePush(status))
        assert morning.count_all() == 0
    assert not [r for r in caplog.records if r.levelname in ("WARNING", "ERROR")]


def test_another_failure_keeps_the_subscription_and_logs(ari, caplog):
    subscribe(ari)
    push = FakePush(500)
    with caplog.at_level("WARNING"):
        morning.run_once(la(17, 7, 30), push)
    assert morning.count_all() == 1 and any("morning" in r.getMessage().lower() for r in caplog.records)
    assert EP not in caplog.text                                  # the address is a capability: never in logs
    push.status = 201
    morning.run_once(la(17, 7, 31), push)                         # it was not marked as sent: the next minute tries again
    assert len(push.sent) == 2


def test_a_sender_that_raises_is_treated_as_a_failure(ari):
    subscribe(ari)

    def boom(sub, payload):
        raise RuntimeError("network down")
    morning.run_once(la(17, 7, 30), boom)
    assert morning.count_all() == 1


def test_a_removed_member_stops_getting_pushes(ari):
    from gitaway import members
    mail = addr("ed")
    invite(ari, mail, "editor")
    editor = browser(ari)
    sign_in(editor, mail)
    subscribe(editor, endpoint="https://push.example.com/send/editor")
    uid = person(mail)["user_id"]
    ari.post("/family/remove", data={"user": uid}, follow_redirects=False)
    push = FakePush()
    morning.run_once(la(17, 7, 30), push)
    assert push.sent == [] and morning.count_all() == 0


def test_the_message_holds_no_confirmation_numbers_or_prices(client):
    imported(client)
    subscribe(client)
    push = FakePush()
    for day in range(16, 21):
        morning.run_once(la(day, 7, 30), push)
    assert push.sent
    blob = json.dumps([p for _, p in push.sent])
    assert not any(s in blob for s in SECRETS) and "$" not in blob


def test_it_survives_a_restart_because_it_lives_in_the_family_database(ari):
    from gitaway import familydb
    subscribe(ari)
    familydb.forget_schema_cache()                                # a new process knows nothing in memory
    push = FakePush()
    morning.run_once(la(17, 7, 30), push)
    assert len(push.sent) == 1


def test_the_sender_thread_starts_once_and_only_with_keys(monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "p"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "k"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    monkeypatch.setattr(morning, "_thread", None)
    started = []
    monkeypatch.setattr(morning, "_loop", lambda *a, **k: started.append(1))
    t = morning.start()
    t.join(2)
    assert morning.start() is t and started == [1]
    monkeypatch.setattr(morning, "_thread", None)


def test_the_text_the_sender_builds_is_the_same_the_today_view_shows(ari):
    s = person()
    msg = morning.todays_message(s, la(17, 7, 30))
    assert msg["title"] == "Today's plan · Los Angeles" and td is not None
    assert re.search(r"9:00 AM Griffith Observatory", msg["body"])


# ---- pixi run vapid-keys ---------------------------------------------------------------------------------------------------

def test_vapid_keys_writes_the_env_file_without_printing_the_private_key(tmp_path, monkeypatch, capsys):
    from scripts import vapid_keys
    env = tmp_path / ".env"
    env.write_text("GOOGLE_CLIENT_ID=keepme\n")
    monkeypatch.setattr(vapid_keys, "ENV", env)
    assert vapid_keys.main(["mailto:a@b.co"]) == 0
    values = dict(line.split("=", 1) for line in env.read_text().splitlines())
    assert values["GOOGLE_CLIENT_ID"] == "keepme" and values["GITAWAY_VAPID_SUBJECT"] == "mailto:a@b.co"
    assert len(values["GITAWAY_VAPID_PUBLIC"]) == 87 and len(values["GITAWAY_VAPID_PRIVATE"]) == 43
    shown = capsys.readouterr()
    assert values["GITAWAY_VAPID_PRIVATE"] not in shown.out + shown.err and (os.name == "nt" or oct(env.stat().st_mode)[-3:] == "600")   # Windows has no Unix file modes


def test_vapid_keys_will_not_replace_keys_without_force_and_needs_a_contact(tmp_path, monkeypatch):
    from scripts import vapid_keys
    env = tmp_path / ".env"
    monkeypatch.setattr(vapid_keys, "ENV", env)
    assert vapid_keys.main([]) == 2 and not env.exists()
    vapid_keys.main(["mailto:a@b.co"])
    before = env.read_text()
    with pytest.raises(SystemExit):
        vapid_keys.main(["mailto:a@b.co"])
    assert env.read_text() == before
    vapid_keys.main(["mailto:a@b.co", "--force"])
    assert env.read_text() != before and env.read_text().count("GITAWAY_VAPID_PRIVATE=") == 1


# ---- review follow-ups -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status,kept", [(400, False), (401, False), (403, False), (404, False), (410, False), (429, True), (500, True), (503, True)])
def test_any_permanent_4xx_drops_the_subscription_but_a_busy_or_broken_service_does_not(ari, status, kept):
    subscribe(ari)
    morning.run_once(la(17, 7, 30), FakePush(status))
    assert (morning.count_all() == 1) is kept


def test_a_phone_in_two_families_is_told_once(ari):
    from gitaway import members
    mail = addr("two")
    invite(ari, mail, "editor")
    sam = browser(ari)
    sign_in(sam, mail)                                        # joins Ari's family; Sam also has a family of their own
    uid = person(mail)["user_id"]
    mine = [f["tenant_id"] for f in members.families_of(uid)]
    assert len(mine) == 2
    sessions = [{"user_id": uid, "tenant_id": t, "email": mail} for t in mine]
    morning.subscribe(sessions[0], EP, KEYS["p256dh"], KEYS["authkey"])
    morning.subscribe(sessions[1], EP, KEYS["p256dh"], KEYS["authkey"])
    assert morning.count_all() == 1
    assert [t for t in mine if morning._subscriptions(t)] == [mine[1]]   # the family it was last turned on in keeps it


def test_the_day_is_recorded_before_sending_so_a_failed_write_cannot_repeat_the_push(ari, monkeypatch):
    subscribe(ari)
    push = FakePush()

    def broken(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(morning, "_write", broken)
    assert morning.run_once(la(17, 7, 30), push) == [] and push.sent == []    # no record, no push


def test_a_failed_send_gives_the_day_back_for_one_retry(ari):
    subscribe(ari)
    push = FakePush(503)
    morning.run_once(la(17, 7, 30), push)
    push.status = 201
    morning.run_once(la(17, 7, 31), push), morning.run_once(la(17, 7, 32), push)
    assert len(push.sent) == 2


def test_the_loop_survives_a_failing_minute():
    import threading
    stop, calls = threading.Event(), []

    def clock():
        calls.append(1)
        if len(calls) >= 3:
            stop.set()
        raise RuntimeError("boom")
    t = threading.Thread(target=morning._loop, args=(stop, 0.01, None, clock), daemon=True)
    t.start(), t.join(3)
    assert not t.is_alive() and len(calls) >= 3


def test_due_on_a_fall_back_day_and_a_spring_forward_day():
    z = "America/Los_Angeles"
    fall = datetime(2026, 11, 1, 15, 30, tzinfo=timezone.utc)         # 7:30 PST, the morning after the clocks went back
    assert morning.due(fall, z, 450, "") == "2026-11-01" and morning.due(fall.replace(hour=14), z, 450, "") is None
    assert morning.due(datetime(2026, 11, 1, 14, 30, tzinfo=timezone.utc), z, 390, "") == "2026-11-01"   # 6:30 PST
    spring = datetime(2026, 3, 8, 14, 30, tzinfo=timezone.utc)        # 7:30 PDT, the morning the clocks went forward
    assert morning.due(spring, z, 450, "") == "2026-03-08" and morning.due(spring, z, 450, "2026-03-08") is None


def test_a_late_evening_time_is_sent_that_evening_and_never_twice(ari):
    subscribe(ari, time="23:30")
    push = FakePush()
    morning.run_once(la(17, 23, 29), push)
    assert push.sent == []
    morning.run_once(la(17, 23, 30), push), morning.run_once(la(17, 23, 59), push), morning.run_once(la(18, 0, 5), push)
    assert len(push.sent) == 1


def test_the_off_switch_colour_is_a_token():
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "assets" / "css" / "morning.css").read_text()
    assert "#D9D4E4" not in css


def test_vapid_keys_accept_the_site_address_as_the_contact(tmp_path, monkeypatch):
    """Web push allows an https address as the contact, so no one's personal email has to go to the push services."""
    from scripts import vapid_keys
    env = tmp_path / ".env"
    monkeypatch.setattr(vapid_keys, "ENV", env)
    assert vapid_keys.main(["https://gitaway.example"]) == 0
    assert "GITAWAY_VAPID_SUBJECT=https://gitaway.example" in env.read_text()
    assert vapid_keys.main(["http://insecure.example", "--force"]) == 2
