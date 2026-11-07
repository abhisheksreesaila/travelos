"""F-193: the captain's view of Plan it for me on /admin: every order with its status, what it brought in, what the agent cost, and the failed ones flagged as refunds due (the captain
refunds in Stripe, GitAway never does). Nobody else sees any of it."""

import re
from html import unescape

import pytest
from sqlalchemy import text

from gitaway import planforme as pfm
from tests.test_planforme import GOOD, buyer
from tests.test_signin import sign_in


def text_of(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def make(who, status, error="", cost=0, tin=0, tout=0, amount=2900, where="Disneyland, California"):
    uid, tenant, email = buyer(who)
    o = pfm.create_order(uid, tenant, email, {**pfm.read_intake(GOOD)[0], "where": where})
    paid_at = "" if status == "awaiting_payment" else "2026-11-06T10:00:00+00:00"
    with pfm._db() as db:
        db.conn.execute(text("UPDATE plan_orders SET status = :s, error = :e, ai_cost_micros = :c, ai_tokens_in = :ti, ai_tokens_out = :to, amount_cents = :a, paid_at = :p, ai_model = 'claude-sonnet-5-5' WHERE id = :i"),
                        {"s": status, "e": error, "c": cost, "ti": tin, "to": tout, "a": amount, "p": paid_at, "i": o["id"]})
        db.conn.commit()
    return o["id"]


@pytest.fixture
def admin(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    return client


def test_the_summary_counts_what_was_kept_what_must_be_refunded_and_what_the_agent_cost(admin):
    make("ari", "ready", cost=27_000, tin=6000, tout=1500)
    make("sam", "building", cost=0)
    make("ari", "failed", error="refusal", cost=12_600, tin=5000, tout=250)
    make("sam", "failed", error="amount_mismatch", amount=100)         # the wrong amount was paid: a refund is due too
    make("ari", "awaiting_payment")                                        # no money yet: not revenue
    html = admin.get("/admin").text
    t = text_of(html)
    assert re.search(r'id="ad-pfm"[^>]*>\s*2 paid · \$58', html)           # the ready and the building one: $29 each
    assert re.search(r'id="ad-refunds"[^>]*>\s*2 · \$30', html)            # $29 and $1
    assert re.search(r'id="ad-pfm-cost"[^>]*>\s*\$0\.040', html)           # 27,000 + 12,600 millionths of a dollar


def test_every_order_is_listed_with_its_status_amount_and_agent_cost(admin):
    ok = make("ari", "ready", cost=27_000, tin=6000, tout=1500)
    bad = make("sam", "failed", error="refusal", cost=12_600)
    new = make("ari", "awaiting_payment")
    html = admin.get("/admin").text
    row = lambda oid: text_of(re.search(rf'<li[^>]*id="pfm-{oid[:8]}".*?</li>', html, re.S).group(0))
    assert "Ready" in row(ok) and "$29" in row(ok) and "agent $0.027" in row(ok) and "6,000 in, 1,500 out" in row(ok) and "claude-sonnet-5-5" in row(ok) and "ari.rivera@example.com" in row(ok)
    assert "Refund due" in row(bad) and "refusal" in row(bad) and "agent $0.013" in row(bad)
    assert "Waiting for payment" in row(new) and "Refund due" not in row(new)
    assert "Disneyland, California" in row(ok)


def test_no_orders_says_so(admin):
    assert "No orders yet." in text_of(admin.get("/admin").text)


def test_nobody_but_an_admin_sees_any_of_it(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "someone.else@example.com")
    sign_in(client, "ari")
    oid = make("ari", "ready", cost=27_000)
    r = client.get("/admin")
    assert r.status_code == 404 and oid[:8] not in r.text and "Plan it for me orders" not in r.text


def test_a_paid_twice_payment_and_a_payment_for_a_gone_order_are_listed_as_refunds_due_and_counted(admin, client, monkeypatch):
    from tests.test_planforme_pay import SECRET, event, hook
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    ok = make("ari", "awaiting_payment")
    assert hook(client, event(ok, session="cs_a", eid="evt_a")).text == "paid"
    assert hook(client, event(ok, session="cs_b", eid="evt_b")).text == "double"
    assert hook(client, event("0" * 16, session="cs_c", eid="evt_c", amount=2900)).text == "unknown"
    html = admin.get("/admin").text
    t = text_of(html)
    assert re.search(r'id="ad-refunds"[^>]*>\s*2 · \$58', html)
    assert "Paid twice: the order was already paid" in t and "Checkout session cs_b" in t
    assert "Paid for an order that no longer exists" in t and "Checkout session cs_c" in t
    assert html.count("Refund due") >= 2 and 'id="refund-evt-evt_b"' in html and 'id="refund-evt-evt_c"' in html
