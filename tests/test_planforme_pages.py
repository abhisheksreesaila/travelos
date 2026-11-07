"""F-193 Plan it for me: the screens, through the HTTP seam. The intake, who may order, the order's states, who may see it, the local stand-in checkout, the booking links, and the cards that
lead here. Stripe and the model are fakes (`planforme.CHECKOUT`, tests/creator_import_support.py `Model`); the whole flow runs once from the card to the trip on the calendar."""

import re
from html import unescape

import pytest

from gitaway import ai, auth, planforme as pfm
from gitaway.partners import travelpayouts
from tests.creator_import_support import Model
from tests.live_trips import live_trip
from tests.test_members import addr, browser, invite
from tests.test_planforme import GOOD, buyer
from tests.test_planforme_build import ANSWER
from tests.test_signin import person, sign_in

FORM = {k: v for k, v in GOOD.items()}


def text_of(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


def order(who="ari", status=None, **fields):
    uid, tenant, email = buyer(who)
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    if status:
        with pfm._db() as db:
            from sqlalchemy import text
            db.conn.execute(text("UPDATE plan_orders SET status = :s, trip_id = :t, sample = :x WHERE id = :i"), {"s": status, "t": fields.get("trip_id", ""), "x": fields.get("sample", 0), "i": o["id"]})
            db.conn.commit()
    return pfm.get(o["id"], uid)


# ---- for sale, or not --------------------------------------------------------------------------------------------

def test_the_intake_is_there_signed_out_with_the_price_and_the_promise(client):
    html = client.get("/plan-for-me/start").text
    t = text_of(html)
    assert re.search(r'id="pf-price"[^>]*>\s*\$29 once', html) and "Not useful? Email us within 7 days for a full refund." in t
    for name in ("where", "start", "end", "home", "adults", "nkids", "budget", "pace", "must"):
        assert f'name="{name}"' in html, name
    assert 'value="Disneyland, California"' in html and 'value="Los Angeles"' in html and "You will sign in first" in t
    assert 'name="price"' not in html and 'name="amount"' not in html


def test_the_price_on_the_page_is_the_settings(client, monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", "4900")
    assert re.search(r'id="pf-price"[^>]*>\s*\$49 once', client.get("/plan-for-me/start").text)


def test_in_production_without_a_stripe_key_nothing_is_for_sale(client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    sign_in(client)
    for path in ("/plan-for-me", "/plan-for-me/0123456789abcdef", "/sandbox/plan-for-me/0123456789abcdef"):
        assert client.get(path).status_code == 404, path
    assert client.post("/plan-for-me", data=FORM).status_code == 404
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    assert client.get("/plan-for-me").status_code == 404          # the key alone is not enough: see the next test


def test_in_production_it_is_for_sale_only_with_the_key_the_webhook_secret_and_an_ai_key(client, monkeypatch):
    """Without the webhook secret every payment would be taken and never believed; without an AI key every buyer would pay and then be refunded."""
    from tests.test_calendar import book
    book(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "")
    cards = lambda: 'id="ga-tb-planforme"' in client.get("/trip").text
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    assert (pfm.offered(), client.get("/plan-for-me").status_code, client.post("/plan-for-me", data=FORM).status_code, cards()) == (False, 404, 404, False)      # no webhook secret
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    assert (pfm.offered(), client.get("/plan-for-me").status_code, client.post("/plan-for-me", data=FORM).status_code, cards()) == (False, 404, 404, False)      # no AI key
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "")
    assert (pfm.offered(), client.get("/plan-for-me").status_code) == (False, 404)      # a refund is promised: nowhere to write to
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "hello@gitaway.me")
    assert (pfm.offered(), client.get("/plan-for-me").status_code) == (True, 200)
    assert cards()
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")
    assert (pfm.offered(), client.get("/plan-for-me").status_code) == (False, 404)


def test_on_a_local_copy_a_stripe_key_without_the_webhook_secret_sells_nothing(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")
    sign_in(client)
    r = client.post("/plan-for-me", data=FORM, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("?err=off")      # an order, no payment page: nothing is charged
    assert "Plan it for me is not for sale here yet. Nothing was charged." in text_of(client.get(r.headers["location"]).text)
    assert pfm.offered() is False


def test_the_stand_in_checkout_is_not_there_in_production_even_with_the_showcase_on(client, monkeypatch):
    sign_in(client)
    o = order()
    assert client.get(f"/sandbox/plan-for-me/{o['id']}").status_code == 200
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    assert client.get(f"/sandbox/plan-for-me/{o['id']}").status_code == 404
    assert client.post(f"/sandbox/plan-for-me/{o['id']}").status_code == 404
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"


def test_with_a_stripe_key_there_is_no_stand_in_even_on_a_local_copy(client, monkeypatch):
    sign_in(client)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    o = order()
    assert client.get(f"/sandbox/plan-for-me/{o['id']}").status_code == 404


# ---- ordering ----------------------------------------------------------------------------------------------------

def test_signed_out_goes_through_sign_in_and_nothing_is_ordered(client):
    r = client.post("/plan-for-me", data=FORM, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=/plan-for-me/start"
    with pfm._db() as db:
        from sqlalchemy import text
        assert db.conn.execute(text("SELECT COUNT(*) FROM plan_orders")).scalar() == 0


def test_a_form_with_mistakes_comes_back_with_the_words_and_what_was_typed(client):
    sign_in(client)
    r = client.post("/plan-for-me", data={**FORM, "where": "", "end": "2027-03-01", "must": "keep this text"}, follow_redirects=False)
    assert r.status_code == 422
    t = text_of(r.text)
    assert "Where you are going is needed." in t and "You come home before you leave." in t
    assert "keep this text" in r.text and 'value="2027-03-12"' in r.text and 'aria-invalid="true"' in r.text


def test_a_good_form_makes_an_order_at_the_servers_price_and_goes_to_the_stand_in_checkout_locally(client):
    sign_in(client)
    r = client.post("/plan-for-me", data={**FORM, "price": "1", "amount_cents": "1", "currency": "eur"}, follow_redirects=False)
    assert r.status_code == 303
    oid = r.headers["location"].rsplit("/", 1)[1]
    assert r.headers["location"] == f"/sandbox/plan-for-me/{oid}"
    o = pfm.get(oid, person()["user_id"])
    assert (o["status"], o["amount_cents"], o["tenant_id"]) == ("awaiting_payment", 2900, person()["tenant_id"])
    page = client.get(r.headers["location"])
    assert "Pay $29 (simulated)" in text_of(page.text) and "Nothing is charged" in text_of(page.text)


def test_with_stripe_the_order_goes_to_checkout_and_the_session_carries_the_orders_price(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    made = []
    monkeypatch.setattr(pfm, "CHECKOUT", lambda params: made.append(params) or {"id": "cs_test_7", "url": "https://checkout.stripe.test/c/pay/cs_test_7"})
    sign_in(client)
    r = client.post("/plan-for-me", data={**FORM, "price": "1", "amount": "1"}, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "https://checkout.stripe.test/c/pay/cs_test_7")
    (p,) = made
    assert p["line_items"][0]["price_data"]["unit_amount"] == 2900 and p["success_url"].startswith("http://testserver/plan-for-me/") and p["success_url"].endswith("?paid=1")


def test_a_stripe_failure_leaves_the_order_to_pay_again_and_says_nothing_was_charged(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")

    def down(params):
        raise OSError("stripe is down")
    monkeypatch.setattr(pfm, "CHECKOUT", down)
    sign_in(client)
    r = client.post("/plan-for-me", data=FORM, follow_redirects=False)
    assert r.status_code == 303 and re.fullmatch(r"/plan-for-me/[0-9a-f]{16}\?err=1", r.headers["location"])
    t = text_of(client.get(r.headers["location"]).text)
    assert "We could not open the payment page just now. Nothing was charged." in t and "Pay $29" in t
    monkeypatch.setattr(pfm, "CHECKOUT", lambda params: {"id": "cs_test_8", "url": "https://checkout.stripe.test/c/pay/cs_test_8"})
    again = client.post(r.headers["location"].split("?")[0] + "/pay", follow_redirects=False)
    assert again.headers["location"] == "https://checkout.stripe.test/c/pay/cs_test_8"


def test_a_viewer_cannot_order_and_is_told_why(client):
    sign_in(client)
    viewer_email = addr("vera")
    invite(client, viewer_email, "viewer")
    other = browser(client)
    sign_in(other, viewer_email)
    t = text_of(other.get("/plan-for-me/start").text)
    assert "Only a family editor or admin can order" in t and "disabled" in other.get("/plan-for-me/start").text
    assert other.post("/plan-for-me", data=FORM, follow_redirects=False).status_code == 403
    with pfm._db() as db:
        from sqlalchemy import text
        assert db.conn.execute(text("SELECT COUNT(*) FROM plan_orders")).scalar() == 0


def test_a_cross_site_form_is_refused(client):
    sign_in(client)
    assert client.post("/plan-for-me", data=FORM, headers={"Origin": "https://evil.example"}, follow_redirects=False).status_code == 403
    o = order()
    assert client.post(f"/plan-for-me/{o['id']}/pay", headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False).status_code == 403
    assert client.post(f"/sandbox/plan-for-me/{o['id']}", headers={"Origin": "https://evil.example"}, follow_redirects=False).status_code == 404


# ---- who may see an order ----------------------------------------------------------------------------------------

def test_only_the_buyer_opens_an_order_not_a_stranger_not_a_member_of_the_family(client):
    sign_in(client, "ari")
    o = order("ari")
    assert client.get(f"/plan-for-me/{o['id']}").status_code == 200
    teammate = addr("zed")
    invite(client, teammate, "editor")
    for who in (browser(client), browser(client)):
        sign_in(who, teammate)
        for path in (f"/plan-for-me/{o['id']}", f"/plan-for-me/{o['id']}/status", f"/plan-for-me/{o['id']}/go/stay"):
            assert who.get(path).status_code == 404, path
        assert who.post(f"/plan-for-me/{o['id']}/pay", follow_redirects=False).status_code == 404
        assert who.get(f"/sandbox/plan-for-me/{o['id']}").status_code == 404
        assert who.post(f"/sandbox/plan-for-me/{o['id']}", follow_redirects=False).status_code == 404
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"


def test_a_signed_out_visitor_is_sent_to_sign_in_and_a_made_up_order_is_a_404(client):
    o = order()
    r = client.get(f"/plan-for-me/{o['id']}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next=/plan-for-me/{o['id']}"
    assert client.get(f"/plan-for-me/{o['id']}/status").status_code == 404
    sign_in(client)
    for bad in ("0123456789abcdef", "not-an-order", "..%2F..%2Fetc"):
        assert client.get(f"/plan-for-me/{bad}").status_code == 404


# ---- the order's states ------------------------------------------------------------------------------------------

def test_each_state_says_what_is_going_on_and_what_to_do(client):
    sign_in(client)
    unpaid = text_of(client.get(f"/plan-for-me/{order()['id']}").text)
    assert "Almost there" in unpaid and "Pay $29" in unpaid and "Disneyland, California · Mar 12 – 15, 2027 · 2 adults, 2 kids" in unpaid
    back = client.get(f"/plan-for-me/{order()['id']}?paid=1")
    assert "Confirming your payment" in text_of(back.text) and "Pay $29" not in text_of(back.text) and 'data-pf-poll="/plan-for-me/' in back.text
    building = client.get(f"/plan-for-me/{order(status='building')['id']}")
    assert "Building your trip" in text_of(building.text) and 'data-status="building"' in building.text and 'aria-current="step"' in building.text
    paid = text_of(client.get(f"/plan-for-me/{order(status='paid')['id']}").text)
    assert "Payment received" in paid and "An agent is about to start" in paid


def test_a_ready_order_links_to_the_trip_and_a_failed_one_promises_the_refund(client):
    sign_in(client)
    ready = client.get(f"/plan-for-me/{order(status='ready', trip_id='abc123def456')['id']}")
    assert 'href="/trip?trip=abc123def456"' in ready.text and "Your trip is ready" in text_of(ready.text) and "data-pf-poll" not in ready.text and "sample trip" not in text_of(ready.text)
    sample = text_of(client.get(f"/plan-for-me/{order(status='ready', trip_id='abc123def456', sample=1)['id']}").text)
    assert "This is a sample trip" in sample
    o = order(status="failed")
    failed = client.get(f"/plan-for-me/{o['id']}")
    t = text_of(failed.text)
    assert "We couldn't finish your trip" in t and "We'll refund you in full." in t and o["id"] in t and "Pay $29" not in t and "Open your trip" not in t and "data-pf-poll" not in failed.text
    assert "Not useful? Email us within 7 days for a full refund." in t


def test_the_status_route_is_what_the_page_polls(client):
    sign_in(client)
    o = order(status="building")
    r = client.get(f"/plan-for-me/{o['id']}/status")
    assert (r.status_code, r.json(), r.headers["cache-control"]) == (200, {"status": "building"}, "no-store")


# ---- the stand-in checkout ---------------------------------------------------------------------------------------

def test_paying_at_the_stand_in_marks_the_order_paid_the_way_a_stripe_event_does(client):
    sign_in(client)
    r = client.post("/plan-for-me", data=FORM, follow_redirects=False)
    oid = r.headers["location"].rsplit("/", 1)[1]
    done = client.post(r.headers["location"], follow_redirects=False)
    assert (done.status_code, done.headers["location"]) == (303, f"/plan-for-me/{oid}")
    o = pfm.get(oid, person()["user_id"])
    assert o["status"] == "paid" and o["stripe_session"] == f"standin_{oid}"
    again = client.post(r.headers["location"], follow_redirects=False)       # paying twice is one payment
    assert (again.status_code, again.headers["location"]) == (303, f"/plan-for-me/{oid}") and pfm.get(oid, person()["user_id"])["status"] == "paid"
    with pfm._db() as db:
        from sqlalchemy import text
        assert db.conn.execute(text("SELECT COUNT(*) FROM plan_order_events")).scalar() == 1


# ---- booking links -------------------------------------------------------------------------------------------------

@pytest.fixture
def ready(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    sign_in(client)
    return order(status="ready", trip_id="abc123def456")


def test_the_flight_link_carries_our_marker_and_the_order_id_as_the_subid(client, ready):
    r = client.get(f"/plan-for-me/{ready['id']}/go/flight", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"https://www.aviasales.com/search/SFO1203LAX15034?marker=801445.{ready['id']}&sub_id={ready['id']}"


def test_the_stay_and_things_to_do_links_go_through_the_partner_links_call_with_the_order_id(client, ready, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    asked = []

    def post(url, headers, body, timeout):
        asked.append(body["links"][0])
        return {"code": 200, "result": {"links": [{"code": "success", "partner_url": f"https://klook.tpx.lv/x{len(asked)}"}]}}
    monkeypatch.setattr(travelpayouts, "_post", post)
    travelpayouts._CACHE.clear()
    stay = client.get(f"/plan-for-me/{ready['id']}/go/stay", follow_redirects=False)
    todo = client.get(f"/plan-for-me/{ready['id']}/go/activity", follow_redirects=False)
    assert (stay.headers["location"], todo.headers["location"]) == ("https://klook.tpx.lv/x1", "https://klook.tpx.lv/x2")
    assert asked == [{"url": "https://www.klook.com/en-US/search/result/?query=Disneyland%2C%20California%20hotels", "sub_id": ready["id"]},
                     {"url": "https://www.klook.com/en-US/search/result/?query=Disneyland%2C%20California%20things%20to%20do", "sub_id": ready["id"]}]


def test_the_order_page_draws_the_links_only_with_a_marker_and_a_flight_only_with_an_airport_we_know(client, ready, monkeypatch):
    html = client.get(f"/plan-for-me/{ready['id']}").text
    assert all(f'id="pf-go-{lane}"' in html for lane in ("flight", "stay", "activity")) and 'rel="sponsored nofollow noopener"' in html and "We may earn a commission" in text_of(html)
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "")
    quiet = client.get(f"/plan-for-me/{ready['id']}").text
    assert "pf-book" not in quiet and client.get(f"/plan-for-me/{ready['id']}/go/stay").status_code == 404
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    uid, tenant, email = buyer()
    paris = pfm.create_order(uid, tenant, email, {**pfm.read_intake(GOOD)[0], "where": "Paris, France"})
    with pfm._db() as db:
        from sqlalchemy import text
        db.conn.execute(text("UPDATE plan_orders SET status = 'ready' WHERE id = :i"), {"i": paris["id"]})
        db.conn.commit()
    html = client.get(f"/plan-for-me/{paris['id']}").text
    assert 'id="pf-go-stay"' in html and 'id="pf-go-flight"' not in html
    assert client.get(f"/plan-for-me/{paris['id']}/go/flight").status_code == 404 and client.get(f"/plan-for-me/{ready['id']}/go/bogus").status_code == 404


def test_no_link_before_the_trip_is_ready(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    sign_in(client)
    assert client.get(f"/plan-for-me/{order(status='building')['id']}/go/stay").status_code == 404


# ---- the cards that lead here ------------------------------------------------------------------------------------

def test_a_creators_trip_offers_it_and_the_intake_starts_from_their_trip(client):
    row, _, _ = live_trip()
    html = client.get(f"/trips/{row['slug']}").text
    t = text_of(html)
    assert "Want this trip built around your family?" in t and f'href="/plan-for-me?from={row["slug"]}"' in html
    assert f'href="/plan-for-me/start?from={row["slug"]}"' in client.get(f"/plan-for-me?from={row['slug']}").text      # the offer carries it on to the intake (F-197)
    intake = client.get(f"/plan-for-me/start?from={row['slug']}")
    assert 'value="Los Angeles, California"' in intake.text and "Starting from “Three easy days in Santa Monica”." in text_of(intake.text)
    assert "Starting from" not in text_of(client.get("/plan-for-me/start?from=not-a-real-trip").text)


def test_the_card_is_not_on_a_trip_page_when_the_offer_is_off(client, monkeypatch):
    row, _, _ = live_trip()
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert "Want this trip built around your family?" not in text_of(client.get(f"/trips/{row['slug']}").text)


def test_the_signed_out_landing_has_a_card_and_a_signed_in_one_does_not(client):
    html = client.get("/").text
    assert 'id="plan-for-me"' in html and 'href="/plan-for-me"' in html and "$29" in text_of(html)
    sign_in(client)
    assert 'id="plan-for-me"' not in client.get("/").text


def test_the_landing_has_no_card_when_the_offer_is_off(client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert 'id="plan-for-me"' not in client.get("/").text


def test_the_trip_menu_has_a_line_for_an_editor_and_none_for_a_viewer(client):
    from tests.test_calendar import book
    book(client)
    assert 'id="ga-tb-planforme"' in client.get("/trip").text
    viewer_email = addr("vic")
    invite(client, viewer_email, "viewer")
    other = browser(client)
    sign_in(other, viewer_email)
    assert 'id="ga-tb-planforme"' not in other.get("/trip").text


# ---- the whole thing -----------------------------------------------------------------------------------------------

def test_from_the_card_to_a_trip_on_the_calendar(client, monkeypatch):
    """A stranger reads a creator's trip, taps the card, signs in, fills the form, pays at the stand-in, the worker builds it, and the trip is on their calendar."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(ANSWER, usage=(6000, 1500)))
    row, _, _ = live_trip()
    card = client.get(f"/trips/{row['slug']}").text
    assert f'/plan-for-me?from={row["slug"]}' in card
    assert client.post("/plan-for-me", data={**FORM, "from": row["slug"]}, follow_redirects=False).headers["location"] == "/signin?next=/plan-for-me/start"
    sign_in(client, next=f"/plan-for-me/start?from={row['slug']}")
    r = client.post("/plan-for-me", data={**FORM, "from": row["slug"]}, follow_redirects=False)
    oid = r.headers["location"].rsplit("/", 1)[1]
    assert client.post(r.headers["location"], follow_redirects=False).status_code == 303
    assert 'data-status="paid"' in client.get(f"/plan-for-me/{oid}").text
    assert pfm.run_pending() == 1
    page = client.get(f"/plan-for-me/{oid}")
    trip = pfm.get(oid, person()["user_id"])["trip_id"]
    assert "Your trip is ready" in text_of(page.text) and f'href="/trip?trip={trip}"' in page.text
    assert pfm.get(oid, person()["user_id"])["intake"]["like"] == "Three easy days in Santa Monica"
    day = text_of(client.get(f"/trip?trip={trip}").text)
    assert "Disneyland with a four and a seven year old" in day and "3:00 PM TRAVEL Check in and rest" in re.sub(r"\s+", " ", day)
    assert "Let the kids splash in the pool." in day and "Tip: Bring a stroller for the seven year old." in day


def test_what_a_buyer_types_is_never_markup_on_their_order_page_or_the_captains(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client)
    evil = '"><script>alert(1)</script>'
    r = client.post("/plan-for-me", data={**FORM, "where": evil, "must": evil}, follow_redirects=False)
    oid = r.headers["location"].rsplit("/", 1)[1]
    assert "<script>alert(1)" not in client.get(f"/plan-for-me/{oid}").text
    assert "&lt;script&gt;alert(1)" in client.get(f"/plan-for-me/{oid}").text
    assert "<script>alert(1)" not in client.get("/admin").text
    bad = client.post("/plan-for-me", data={**FORM, "where": evil, "end": "2020-01-01"}, follow_redirects=False)
    assert bad.status_code == 422 and "<script>alert(1)" not in bad.text and "&lt;script&gt;" in bad.text


# ---- the refund promise says how to ask -------------------------------------------------------------------------

def test_the_promise_says_how_to_ask_and_the_offer_the_intake_and_a_ready_order_show_the_address(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "hello@gitaway.me")
    sign_in(client)
    ready = order(status="ready", trip_id="abc123def456")
    assert pfm.PROMISE == "Not useful? Email us within 7 days for a full refund."
    for path in ("/plan-for-me", "/plan-for-me/start", f"/plan-for-me/{ready['id']}"):
        html = client.get(path).text
        m = re.search(r'<p[^>]*id="pf-promise".*?</p>', html, re.S)
        assert m, path
        assert re.sub(r"\s+", " ", text_of(m.group(0))).strip() == "Not useful? Email us within 7 days for a full refund. hello@gitaway.me", path
        assert 'href="mailto:hello@gitaway.me"' in m.group(0), path
