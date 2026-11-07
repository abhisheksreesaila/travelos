"""F-197 the founding price: the first PLAN_FOR_ME_FOUNDING_LIMIT (10) families who pay get PLAN_FOR_ME_PRICE_CENTS ($29), everyone after them PLAN_FOR_ME_FULL_PRICE_CENTS ($49). The server
picks the price when the order is made and the webhook holds the buyer to it; the browser never says. No former or struck-through price is shown anywhere: the offer says "$29 for the first 10
families, then $49" and how many founding spots are left (FTC former-price rules: $49 has never been charged)."""

import re
from html import unescape

import pytest
from sqlalchemy import text

from gitaway import planforme as pfm
from tests.test_planforme import GOOD, buyer


def text_of(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def paid_orders(n, status="ready", who="ari"):
    uid, tenant, email = buyer(who)
    for _ in range(n):
        o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
        with pfm._db() as db:
            db.conn.execute(text("UPDATE plan_orders SET status = :s, paid_at = '2026-11-06T10:00:00+00:00' WHERE id = :i"), {"s": status, "i": o["id"]})
            db.conn.commit()


@pytest.fixture(autouse=True)
def defaults(monkeypatch):
    for name in ("PLAN_FOR_ME_PRICE_CENTS", "PLAN_FOR_ME_FULL_PRICE_CENTS", "PLAN_FOR_ME_FOUNDING_LIMIT"):
        monkeypatch.delenv(name, raising=False)


def test_the_defaults_are_10_founding_families_at_29_then_49():
    assert (pfm.founding_limit(), pfm.founding_price_cents(), pfm.full_price_cents()) == (10, 2900, 4900)
    assert pfm.founding_left() == 10 and pfm.price_cents() == 2900


def test_each_paid_family_takes_a_spot_and_the_eleventh_order_is_made_at_the_full_price():
    paid_orders(9)
    assert pfm.founding_left() == 1 and pfm.price_cents() == 2900
    paid_orders(1, status="paid")
    assert pfm.founding_left() == 0 and pfm.price_cents() == 4900
    uid, tenant, email = buyer("sam")
    assert pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])["amount_cents"] == 4900


@pytest.mark.parametrize("status", ["paid", "building", "review", "ready"])
def test_every_kept_order_counts(status):
    paid_orders(1, status=status)
    assert pfm.founding_left() == 9


def test_an_unpaid_or_a_failed_and_refunded_order_takes_no_spot():
    uid, tenant, email = buyer()
    pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])        # awaiting payment
    paid_orders(2, status="failed")
    assert pfm.founding_left() == 10


def test_an_order_keeps_the_price_it_was_made_at_even_when_the_spots_run_out_before_it_is_paid():
    uid, tenant, email = buyer("sam")
    early = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    paid_orders(10)
    assert pfm.price_cents() == 4900
    pfm.set_session(early["id"], "cs_1")
    assert pfm.mark_paid(early["id"], "evt_early", "cs_1", 2900, "usd") == "paid"         # the webhook holds them to the order's own amount


def test_a_founding_price_payment_on_a_full_price_order_is_refused():
    paid_orders(10)
    uid, tenant, email = buyer("sam")
    late = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    pfm.set_session(late["id"], "cs_2")
    assert pfm.mark_paid(late["id"], "evt_late", "cs_2", 2900, "usd") == "mismatch"


def test_the_settings_move_the_limit_and_both_prices(monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_FOUNDING_LIMIT", "2")
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", "1900")
    monkeypatch.setenv("PLAN_FOR_ME_FULL_PRICE_CENTS", "5900")
    paid_orders(1)
    assert (pfm.founding_left(), pfm.price_cents()) == (1, 1900)
    paid_orders(1)
    assert (pfm.founding_left(), pfm.price_cents()) == (0, 5900)


@pytest.mark.parametrize("bad", ["", "abc", "-1", "2.5", "100000"])
def test_a_nonsense_limit_falls_back_to_10(monkeypatch, bad):
    monkeypatch.setenv("PLAN_FOR_ME_FOUNDING_LIMIT", bad)
    assert pfm.founding_limit() == 10


def test_a_limit_of_0_means_no_founding_price(monkeypatch, client):
    monkeypatch.setenv("PLAN_FOR_ME_FOUNDING_LIMIT", "0")
    assert (pfm.founding_left(), pfm.price_cents()) == (0, 4900)
    t = text_of(client.get("/plan-for-me").text)
    assert "first" not in t.lower().split("founding")[0] or "founding" not in t.lower()
    assert "$49" in t and "$29" not in t


@pytest.mark.parametrize("bad", ["", "abc", "5", "99999999"])
def test_a_nonsense_full_price_falls_back_to_49(monkeypatch, bad):
    monkeypatch.setenv("PLAN_FOR_ME_FULL_PRICE_CENTS", bad)
    assert pfm.full_price_cents() == 4900


def test_the_offer_says_the_founding_terms_and_the_spots_left_never_a_former_price(client):
    paid_orders(3)
    html = client.get("/plan-for-me").text
    t = text_of(html)
    assert "$29 for the first 10 families, then $49" in t
    assert re.search(r'id="pf-spots"[^>]*>\s*7 of 10 founding spots left', html)
    assert not re.search(r"normally|was \$|regular(ly)? \$|\$49 value", t, re.I) and "<s>" not in html and "<del" not in html and "line-through" not in html


def test_one_spot_left_is_said_in_the_singular(client):
    paid_orders(9)
    assert re.search(r'id="pf-spots"[^>]*>\s*1 of 10 founding spots left|id="pf-spots"[^>]*>\s*Last founding spot', client.get("/plan-for-me").text)


def test_when_the_spots_are_gone_the_page_shows_the_full_price_only(client):
    paid_orders(10)
    html = client.get("/plan-for-me").text
    t = text_of(html)
    assert "$49" in t and "$29" not in t and 'id="pf-spots"' not in html and "founding" not in t.lower()
    assert "$49" in text_of(client.get("/plan-for-me/start").text)


def test_the_price_on_the_intake_button_follows_the_spots(client):
    from tests.test_signin import sign_in
    sign_in(client)
    assert "Plan it for me · $29" in text_of(client.get("/plan-for-me/start").text)
    paid_orders(10, who="sam")
    assert "Plan it for me · $49" in text_of(client.get("/plan-for-me/start").text)


def test_a_price_in_the_form_still_changes_nothing(client):
    from tests.test_signin import sign_in
    sign_in(client)
    paid_orders(10, who="sam")
    client.post("/plan-for-me", data={**GOOD, "price": "100", "amount_cents": "2900", "founding": "1"}, follow_redirects=False)
    with pfm._db() as db:
        amounts = [r[0] for r in db.conn.execute(text("SELECT amount_cents FROM plan_orders WHERE status = 'awaiting_payment'"))]
    assert amounts == [4900]
