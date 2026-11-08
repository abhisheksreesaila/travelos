"""F-197 the founder check: with PLAN_FOR_ME_REVIEW=1 (off by default since F-199) a built plan waits on /admin for the captain's "Send to family" before the buyer sees anything of it. The buyer's
order page says a person is checking it, their family has no trip yet, and nobody but an admin can look at, edit or send it. With 0 the trip is delivered at once, as F-193 did."""

import re
from html import unescape

import pytest

from gitaway import planforme as pfm, tripcal
from tests.test_planforme_build import ANSWER, calendar, model, paid
from tests.test_signin import person, sign_in

CHECKING = "Your plan is built and being checked by a person, usually within a few hours."


def text_of(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


@pytest.fixture(autouse=True)
def review_on(monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")


@pytest.fixture
def captain(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "sam.kim@example.com")
    sign_in(client, "sam")
    return client


def built(monkeypatch):
    model(monkeypatch)
    o = paid("ari")
    assert pfm.run_pending() == 1
    return pfm._row(o["id"])


def test_the_check_is_on_only_when_the_setting_is_1(monkeypatch):
    """F-199: the check stays, but is off by default now that plans are free."""
    monkeypatch.delenv("PLAN_FOR_ME_REVIEW", raising=False)
    assert not pfm.review_on()
    for value, on in (("1", True), (" 1 ", True), ("0", False), (" 0 ", False), ("yes", False), ("", False)):
        monkeypatch.setenv("PLAN_FOR_ME_REVIEW", value)
        assert pfm.review_on() is on, value


def test_a_built_plan_waits_for_the_check_and_the_buyers_family_has_no_trip_yet(monkeypatch):
    o = built(monkeypatch)
    assert o["status"] == "review" and o["trip_id"] == "" and o["result"]["days"]
    assert calendar("ari") == []


def test_the_buyer_sees_that_a_person_is_checking_it_and_nothing_of_the_plan(client, monkeypatch):
    o = built(monkeypatch)
    sign_in(client, "ari")
    html = client.get(f"/plan-for-me/{o['id']}").text
    t = text_of(html)
    assert CHECKING in t and 'id="pf-open"' not in html and "/trip?trip=" not in html
    assert "Rides before the crowds" not in t and o["result"]["title"] not in t
    assert client.get(f"/plan-for-me/{o['id']}/status").json() == {"status": "review"}
    assert 'data-pf-poll=' in html          # the page reloads itself when the captain sends it


def test_send_to_family_writes_the_trip_and_the_buyer_then_sees_it(client, captain, monkeypatch):
    o = built(monkeypatch)
    page = captain.get("/admin").text
    assert re.search(r'<form[^>]*action="/admin/plan-for-me/send"', page) and f'name="order" value="{o["id"]}"' in page and f'href="/admin/plan-for-me/{o["id"]}"' in page
    r = captain.post("/admin/plan-for-me/send", data={"order": o["id"]}, follow_redirects=False)
    assert r.status_code == 303
    after = pfm._row(o["id"])
    assert after["status"] == "ready" and after["trip_id"]
    assert [x[3] for x in calendar("ari")][:2] == ["Check in and rest", "Dinner · Downtown Disney District"]
    sign_in(client, "ari")
    assert f'href="/trip?trip={after["trip_id"]}"' in client.get(f"/plan-for-me/{o['id']}").text


def test_sending_twice_makes_one_trip(captain, monkeypatch):
    o = built(monkeypatch)
    captain.post("/admin/plan-for-me/send", data={"order": o["id"]})
    n = len(calendar("ari"))
    captain.post("/admin/plan-for-me/send", data={"order": o["id"]})
    assert len(calendar("ari")) == n and pfm._row(o["id"])["status"] == "ready"


def set_status(order_id, status):
    from sqlalchemy import text
    with pfm._db() as db:
        db.conn.execute(text("UPDATE plan_orders SET status = :s WHERE id = :i"), {"s": status, "i": order_id})
        db.conn.commit()


def test_several_taps_at_once_write_the_trip_once_and_one_send_wins(monkeypatch):
    import threading
    import time
    o = built(monkeypatch)
    real, writes = pfm.write_trip, []

    def slow(order, result):
        writes.append(order["id"])
        time.sleep(0.3)      # long enough for every other tap to arrive while this one is writing
        return real(order, result)
    monkeypatch.setattr(pfm, "write_trip", slow)
    gate, answers = threading.Barrier(4), []

    def tap():
        gate.wait()
        answers.append(pfm.send(o["id"]))
    taps = [threading.Thread(target=tap) for _ in range(4)]
    for t in taps:
        t.start()
    for t in taps:
        t.join()
    assert writes == [o["id"]] and answers.count("ready") == 1
    assert pfm._row(o["id"])["status"] == "ready" and len(calendar("ari")) == 6      # one trip, written once (a second write would double the days)


def test_a_send_cut_short_by_a_restart_is_waiting_for_the_check_again(monkeypatch):
    o = built(monkeypatch)
    set_status(o["id"], "sending")
    pfm.reset_running()
    assert pfm._row(o["id"])["status"] == "review"
    assert pfm.send(o["id"]) == "ready"


def test_while_it_is_being_sent_the_buyer_still_sees_a_person_checking_it_and_it_still_counts_as_paid(client, monkeypatch):
    o = built(monkeypatch)
    set_status(o["id"], "sending")
    sign_in(client, "ari")
    assert CHECKING in text_of(client.get(f"/plan-for-me/{o['id']}").text)
    assert client.get(f"/plan-for-me/{o['id']}/status").json() == {"status": "review"}      # the page polls this: it must not reload forever
    assert pfm.totals([pfm._row(o["id"])])["paid"] == 1 and pfm.founding_left() == 9


def heights_kept(order_id):
    return pfm._row(order_id)["intake"]["heights"]


def test_the_kids_heights_are_kept_while_the_plan_is_built_and_checked_and_deleted_once_it_is_delivered(monkeypatch):
    model(monkeypatch)
    o = paid("ari", heights=[38, 48])
    assert heights_kept(o["id"]) == [38, 48]
    assert pfm.run_pending() == 1 and pfm._row(o["id"])["status"] == "review"
    assert heights_kept(o["id"]) == [38, 48]
    assert pfm.send(o["id"]) == "ready"
    assert heights_kept(o["id"]) == [] and pfm._row(o["id"])["intake"]["kids"] == [4, 7]      # the ages stay, the heights go


def test_the_kids_heights_are_deleted_when_the_order_is_delivered_at_once_or_fails(monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "0")
    model(monkeypatch)
    delivered = paid("ari", heights=[38, 48])
    pfm.run_pending()
    failed = paid("sam", heights=[40, 50])
    pfm._fail(failed["id"], "empty")
    mismatch = paid("lee", heights=[41, 51])
    with pfm._db() as db:
        from sqlalchemy import text
        db.conn.execute(text("UPDATE plan_orders SET status = 'awaiting_payment' WHERE id = :i"), {"i": mismatch["id"]})
        db.conn.commit()
    assert pfm.mark_paid(mismatch["id"], "evt_x", "cs_1", 100, "usd") == "mismatch"
    assert [pfm._row(x["id"])["status"] for x in (delivered, failed, mismatch)] == ["ready", "failed", "failed"]
    assert [heights_kept(x["id"]) for x in (delivered, failed, mismatch)] == [[], [], []]


def test_the_check_page_with_the_whole_plan_is_never_stored_by_a_browser_or_proxy(captain, monkeypatch):
    o = built(monkeypatch)
    r = captain.get(f"/admin/plan-for-me/{o['id']}")
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"


def test_the_quick_edit_changes_what_the_family_gets(captain, monkeypatch):
    o = built(monkeypatch)
    page = captain.get(f"/admin/plan-for-me/{o['id']}").text
    assert 'name="s0-0-title"' in page and 'name="summary"' in page and "Check in and rest" in page
    form = {"summary": "Checked by a person: an easy first day.", "s0-0-title": "Check in, then the pool", "s0-0-note": "Swimsuits in the carry-on.", "tip0": "Bring a light jacket for the evening."}
    assert captain.post("/admin/plan-for-me/edit", data={"order": o["id"], **form}, follow_redirects=False).status_code == 303
    result = pfm._row(o["id"])["result"]
    assert result["summary"] == form["summary"] and result["days"][0]["stops"][0]["title"] == "Check in, then the pool" and result["days"][0]["stops"][0]["note"] == "Swimsuits in the carry-on."
    assert result["tips"][0] == "Bring a light jacket for the evening."
    captain.post("/admin/plan-for-me/send", data={"order": o["id"]})
    assert calendar("ari")[0][3] == "Check in, then the pool"
    notes = {n.text for n in tripcal.notes(person("ari"))}
    assert "Swimsuits in the carry-on." in notes and "Tip: Bring a light jacket for the evening." in notes


def test_an_edit_cannot_put_a_price_or_opening_hours_back_in(captain, monkeypatch):
    o = built(monkeypatch)
    captain.post("/admin/plan-for-me/edit", data={"order": o["id"], "s0-0-note": "Tickets cost $120 each.", "s0-0-title": "x" * 90})
    stop = pfm._row(o["id"])["result"]["days"][0]["stops"][0]
    assert stop["note"] == "" and len(stop["title"]) <= tripcal.MAX_TITLE


def test_nobody_but_an_admin_can_see_edit_or_send_it(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "someone.else@example.com")
    o = built(monkeypatch)
    sign_in(client, "ari")          # the buyer, and an admin of their own family
    assert client.get(f"/admin/plan-for-me/{o['id']}").status_code == 404
    assert client.post("/admin/plan-for-me/send", data={"order": o["id"]}).status_code == 404
    assert client.post("/admin/plan-for-me/edit", data={"order": o["id"], "summary": "mine"}).status_code == 404
    assert pfm._row(o["id"])["status"] == "review" and calendar("ari") == []


def test_only_a_plan_waiting_for_the_check_can_be_sent(captain, monkeypatch):
    model(monkeypatch)
    o = paid("ari")          # paid, not built yet
    captain.post("/admin/plan-for-me/send", data={"order": o["id"]})
    assert pfm._row(o["id"])["status"] == "paid" and calendar("ari") == []
    assert captain.get("/admin/plan-for-me/0123456789abcdef").status_code == 404


def test_a_buyer_who_left_the_family_before_the_send_gets_a_failed_order_not_a_trip(captain, monkeypatch):
    o = built(monkeypatch)
    from gitaway import members
    monkeypatch.setattr(members, "role_in", lambda uid, tenant: None)
    captain.post("/admin/plan-for-me/send", data={"order": o["id"]})
    assert pfm._row(o["id"])["status"] == "failed" and pfm._row(o["id"])["error"] == "left_family"


def test_a_plan_waiting_for_the_check_counts_as_paid_on_admin(captain, monkeypatch):
    built(monkeypatch)
    assert re.search(r'id="ad-pfm"[^>]*>\s*1 paid · \$29', captain.get("/admin").text)


def test_with_the_check_off_the_trip_is_delivered_at_once(monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "0")
    o = built(monkeypatch)
    assert o["status"] == "ready" and o["trip_id"] and calendar("ari")
