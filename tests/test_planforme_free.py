"""F-199: Plan it for me is free. No Stripe is needed to offer it (PLAN_FOR_ME_PAID=0 is the default), a person may start PLAN_FOR_ME_DAILY plans a day (2) and the whole site
PLAN_FOR_ME_SITE_DAILY (100), the model is Claude Haiku 5.5 unless a setting says otherwise and each plan's cost is logged, the founder check is off unless asked for, and no page shows a
price or a refund promise while it is free. The Stripe path still works with PLAN_FOR_ME_PAID=1 (the older tests run that way, tests/conftest.py)."""

import logging
import re
from datetime import datetime, timedelta, timezone
from html import unescape

import pytest
from sqlalchemy import text

from gitaway import ai, auth, planforme as pfm
from tests.creator_import_support import Model
from tests.test_planforme import GOOD, buyer
from tests.test_planforme_build import ANSWER
from tests.test_signin import person, sign_in

PRICE = re.compile(r"\$\d|refund|Stripe|one time", re.I)


@pytest.fixture(autouse=True)
def free(monkeypatch):
    monkeypatch.delenv("PLAN_FOR_ME_PAID", raising=False)
    monkeypatch.delenv("PLAN_FOR_ME_REVIEW", raising=False)
    for name in ("PLAN_FOR_ME_DAILY", "PLAN_FOR_ME_SITE_DAILY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "GITAWAY_CONTACT_EMAIL"):
        monkeypatch.delenv(name, raising=False)


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def make(who="ari"):
    uid, tenant, email = buyer(who)
    return pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])


def backdate(order_id, hours):
    with pfm._db() as db:
        at = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="microseconds")
        db.conn.execute(text("UPDATE plan_orders SET created_at = :a WHERE id = :i"), {"a": at, "i": order_id})
        db.conn.commit()


# ---- the settings ------------------------------------------------------------------------------------------------------

def test_free_is_the_default_and_paid_is_a_setting(monkeypatch):
    assert not pfm.paid() and not pfm.review_on()
    assert (pfm.daily_cap(), pfm.site_daily_cap()) == (2, 100)
    monkeypatch.setenv("PLAN_FOR_ME_PAID", "1")
    assert pfm.paid()
    for bad in ("-1", "lots", "1e3", "100001"):
        monkeypatch.setenv("PLAN_FOR_ME_SITE_DAILY", bad)
        assert pfm.site_daily_cap() == 100, bad
    monkeypatch.setenv("PLAN_FOR_ME_DAILY", "5")
    assert pfm.daily_cap() == 5


def test_offered_needs_only_the_model_while_free(monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert not pfm.offered()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    assert pfm.offered() and not pfm.standin()         # no Stripe key, no webhook secret, no contact address: none needed while free


def test_the_model_is_haiku_and_a_setting_changes_it(monkeypatch):
    assert ai.deployment(pfm.JOB) == "claude-haiku-5-5"
    monkeypatch.setenv("GITAWAY_AI_MODEL_PLAN_FOR_ME", "claude-sonnet-5-5")
    assert ai.deployment(pfm.JOB) == "claude-sonnet-5-5"


# ---- a free order --------------------------------------------------------------------------------------------------------

def test_a_free_order_is_built_at_once_with_no_charge():
    o = make()
    assert (o["status"], o["amount_cents"], o["stripe_session"]) == ("paid", 0, "") and o["paid_at"]


def test_a_person_may_start_two_a_day_and_a_new_day_starts_again():
    first, second = make(), make()
    with pytest.raises(pfm.TooMany) as e:
        make()
    assert str(e.value) == "You have planned 2 trips today, the most for one day while plans are free. Come back tomorrow."
    for o in (first, second):
        backdate(o["id"], 30)       # yesterday's plans do not count today
    assert make()["status"] == "paid"
    assert pfm.free_left(person()["user_id"]) == 1


def test_a_failed_plan_still_counts_so_retries_cannot_run_up_the_bill():
    o = make()
    pfm._fail(o["id"], "error")
    make()
    with pytest.raises(pfm.TooMany):
        make()


def test_the_whole_site_has_a_daily_cap(monkeypatch, caplog):
    monkeypatch.setenv("PLAN_FOR_ME_SITE_DAILY", "3")
    make("ari"), make("ari"), make("sam")
    with caplog.at_level(logging.WARNING, logger="gitaway.planforme"), pytest.raises(pfm.TooMany) as e:
        make("sam")
    assert "Today's free plans are all taken" in str(e.value) and "daily cap of 3" in caplog.text


def test_the_cost_of_each_plan_is_kept_and_logged(monkeypatch, caplog):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(ANSWER, usage=(6000, 1500)))
    o = make()
    with caplog.at_level(logging.INFO, logger="gitaway.planforme"):
        assert pfm.run_pending() == 1
    got = pfm.get(o["id"], person()["user_id"])
    assert (got["status"], got["ai_model"], got["ai_cost_micros"]) == ("ready", "claude-haiku-5-5", 1_350)      # $0.00135: 6,000 in at $0.10 and 1,500 out at $0.50 a million
    assert f"plan order {o['id']} cost $0.0014 (claude-haiku-5-5, 6000 tokens in, 1500 out" in caplog.text
    assert "Disneyland" not in caplog.text       # no content in the log


# ---- the pages -----------------------------------------------------------------------------------------------------------

def test_no_page_shows_a_price_or_a_refund_while_it_is_free(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    pages = {path: words(client.get(path).text) for path in ("/plan-for-me", "/plan-for-me/start", "/plan-for-me/example/disneyland")}
    for path, page in pages.items():
        main = page.split("Privacy Terms")[0]
        assert not PRICE.search(main.replace("Free while GitAway is in early preview.", "")), (path, PRICE.search(main).group(0))
    assert "Free while GitAway is in early preview" in pages["/plan-for-me"] and "Up to 2 plans a day for each person." in pages["/plan-for-me"]
    assert re.search(r'id="pf-price"[^>]*>\s*Free', client.get("/plan-for-me/start").text)
    assert "A few minutes after you ask" in pages["/plan-for-me"]


def test_from_the_form_to_a_ready_trip_with_no_checkout(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(ANSWER, usage=(6000, 1500)))
    sign_in(client)
    start = client.get("/plan-for-me/start").text
    assert "Plan it for me · free" in words(start)
    r = client.post("/plan-for-me", data=GOOD, follow_redirects=False)
    assert r.status_code == 303 and re.fullmatch(r"/plan-for-me/[0-9a-f]{16}", r.headers["location"])        # straight to the order: no Stripe, no stand-in
    page = client.get(r.headers["location"]).text
    assert 'data-status="paid"' in page and "Request received" in words(page) and not PRICE.search(words(page).split("Privacy Terms")[0])
    assert client.post(r.headers["location"] + "/pay", follow_redirects=False).headers["location"] == r.headers["location"]
    assert pfm.run_pending() == 1
    assert "Your trip is ready" in words(client.get(r.headers["location"]).text)


def test_the_third_plan_of_the_day_is_refused_with_a_sentence(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    sign_in(client)
    for _ in range(2):
        assert client.post("/plan-for-me", data=GOOD, follow_redirects=False).status_code == 303
    r = client.post("/plan-for-me", data=GOOD)
    assert r.status_code == 429 and "the most for one day while plans are free" in words(r.text)


def test_a_failed_free_plan_says_nothing_was_charged(client, monkeypatch):
    sign_in(client)
    o = make()
    pfm._fail(o["id"], "refusal")
    t = words(client.get(f"/plan-for-me/{o['id']}").text)
    assert "Nothing was charged" in t and "refund" not in t.lower()


def test_privacy_and_terms_say_no_payment_is_taken(client):
    privacy, terms = words(client.get("/privacy").text), words(client.get("/terms").text)
    assert "GitAway takes no payment of any kind. Plan it for me is free while GitAway is in early preview" in terms
    assert "Stripe" not in privacy and "Stripe" not in terms and "the amount and Stripe's code" not in privacy
    assert "Anthropic (Claude Haiku) builds your trip when you ask for Plan it for me" in privacy
    assert "No commission opens their search" in privacy and "Change or cancel button" in terms
