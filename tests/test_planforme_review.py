"""F-197 the founder check: with PLAN_FOR_ME_REVIEW on (the default) a built plan waits on /admin for the captain's "Send to family" before the buyer sees anything of it. The buyer's
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


def test_the_check_is_on_unless_the_setting_is_0(monkeypatch):
    monkeypatch.delenv("PLAN_FOR_ME_REVIEW", raising=False)
    assert pfm.review_on()
    for value, on in (("1", True), ("0", False), (" 0 ", False), ("yes", True), ("", True)):
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
