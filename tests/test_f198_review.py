"""F-198/F-199 review and security-audit fixes, each pinned by a test that failed before the fix. Through the HTTP seam and the modules' own functions; no test reaches the network
(the one local HTTP server below answers on 127.0.0.1 only)."""

import http.server
import logging
import re
import socket
import threading
from datetime import date
from html import unescape

import pytest
from sqlalchemy import text

from gitaway import affiliate, confirmations as cf, planforme as pfm, tripimport as ti
from gitaway.partners import links, manage, places, prices, travelpayouts
from tests.confirmation_samples import AIRBNB, BOOKING
from tests.live_trips import live_trip
from tests.test_affiliate import seen_on
from tests.test_booking_lanes import TAHOE, TAHOE_TRIP, book_links
from tests.test_planforme import GOOD, buyer
from tests.test_signin import person, sign_in

KEYS = ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS", "PARTNER_TRACKED", "PARTNER_STAY")


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    travelpayouts._CACHE.clear()
    prices.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": []})
    yield
    prices.clear()


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def hidden(html, name):
    m = re.search(rf"""name="{name}" value=(?:"([^"]*)"|'([^']*)')""", html)
    return unescape(m.group(1) if m.group(1) is not None else m.group(2)) if m else None


# ---- 1. an emoji in a pasted title -----------------------------------------------------------------------------------------

EMOJI = AIRBNB.replace("Cozy A-Frame Cabin near Heavenly", "Cozy \U0001F3D4 A-Frame Cabin")


def test_an_emoji_round_trips_through_the_template_and_control_characters_go():
    plan = ti.parse(TAHOE_TRIP.replace("Lakeside Cabin", "Lakeside \U0001F3D4 Cabin")).plan
    assert ti.parse(ti.to_yaml(plan)).plan == plan
    weird = ti.Plan(**{**plan.__dict__, "title": "Tahoe\u2028with\x07 kids \U0001F3D4"})
    assert ti.parse(ti.to_yaml(weird)).plan.title == "Tahoe with kids \U0001F3D4"


def test_an_airbnb_title_with_an_emoji_previews_on_the_import_page(client):
    sign_in(client, "ari")
    r = client.post("/trips/import", data={"text": EMOJI})
    assert r.status_code == 200 and "Cozy \U0001F3D4 A-Frame Cabin" in words(r.text)


# ---- 3. a confirmation row on one line, or split by tabs -------------------------------------------------------------------

ONE_LINE = BOOKING.replace("Booking number: 4021.889.317\nPIN code: 7741", "Booking number: 4021.889.317 PIN code: 7741")
TABBED = AIRBNB.replace("Confirmation code\nHMAB12CD34\nTotal (USD) $3,112.50", "Confirmation code\tHMAB12CD34\tTotal (USD)\t$3,112.50")
JOINED = AIRBNB.replace("Confirmation code\nHMAB12CD34\nTotal (USD) $3,112.50", "Confirmation code HMAB12CD34 Total USD 3112.50")
CARD_ABOVE = BOOKING.replace("Lakeside Lodge Tahoe\n123 Lake", "Lakeside Lodge Tahoe\nPaid with Visa ending 4242\n123 Lake")


@pytest.mark.parametrize("sample, conf", [(ONE_LINE, "4021.889.317"), (TABBED, "HMAB12CD34"), (JOINED, "HMAB12CD34")], ids=["one-line", "tabs", "joined"])
def test_only_the_confirmation_number_is_kept_from_a_row(sample, conf):
    b = cf.read(sample)
    assert b.item.confirmation == conf
    out = cf.convert(sample).yaml
    for secret in ("7741", "PIN", "3112", "3,112", "Total", "USD", "$"):
        assert secret not in out, secret


def test_a_card_line_is_never_taken_for_a_name():
    b = cf.read(CARD_ABOVE)
    assert b.item.name == "Lakeside Lodge Tahoe" and "4242" not in cf.convert(CARD_ABOVE).yaml


def test_a_pin_is_never_stored(client):
    sign_in(client, "ari")
    r = client.post("/trips/import", data={"text": ONE_LINE})
    assert "7741" not in r.text
    assert client.post("/trips/import/save", data={"text": hidden(r.text, "text")}, follow_redirects=False).status_code == 303
    assert "7741" not in client.get("/trip/details").text


# ---- 4. an old unpaid order is never charged while plans are free ----------------------------------------------------------

def unpaid_order(monkeypatch, who="ari"):
    monkeypatch.setenv("PLAN_FOR_ME_PAID", "1")
    uid, tenant, email = buyer(who)
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    assert o["status"] == "awaiting_payment" and o["amount_cents"] > 0
    monkeypatch.delenv("PLAN_FOR_ME_PAID")
    return o


def test_a_leftover_unpaid_order_is_made_free_and_never_sent_to_stripe(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_not_real")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(pfm, "CHECKOUT", lambda params: pytest.fail("Stripe was asked for a payment page while plans are free"))
    sign_in(client, "ari")
    o = unpaid_order(monkeypatch)
    r = client.post(f"/plan-for-me/{o['id']}/pay", follow_redirects=False)
    assert r.status_code == 303 and "stripe" not in r.headers["location"]
    page = words(client.get(f"/plan-for-me/{o['id']}").text)
    assert "Pay $" not in page and "Request received" in page
    got = pfm.get(o["id"], person()["user_id"])
    assert (got["status"], got["amount_cents"]) == ("paid", 0)
    with pytest.raises(pfm.NotSold):
        pfm.start_checkout(got, "http://testserver")


def test_a_leftover_order_over_the_cap_is_expired_not_charged(client, monkeypatch):
    sign_in(client, "ari")
    o = unpaid_order(monkeypatch)
    uid, tenant, email = buyer("ari")
    for _ in range(2):
        pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    page = words(client.get(f"/plan-for-me/{o['id']}").text)
    got = pfm.get(o["id"], uid)
    assert (got["status"], got["amount_cents"], got["error"]) == ("failed", 0, "expired") and "Nothing was charged" in page and "Pay $" not in page


# ---- 5. the daily caps hold under a burst ----------------------------------------------------------------------------------

def test_twenty_simultaneous_orders_make_only_the_cap(monkeypatch):
    monkeypatch.delenv("PLAN_FOR_ME_PAID", raising=False)
    real = pfm.daily_cap

    def slow():        # reading the cap takes a moment, as a busy server does between a count and an insert: the window the audit's burst hit
        import time
        time.sleep(0.05)
        return real()
    monkeypatch.setattr(pfm, "daily_cap", slow)
    uid, tenant, email = buyer("ari")
    intake = pfm.read_intake(GOOD)[0]
    gate, made, refused, broke = threading.Barrier(20), [], [], []

    def one():
        gate.wait()
        try:
            made.append(pfm.create_order(uid, tenant, email, intake)["id"])
        except pfm.TooMany:
            refused.append(1)
        except Exception as e:      # noqa: BLE001 - a database error in a thread must fail the test, not vanish
            broke.append(repr(e))
    threads = [threading.Thread(target=one) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with pfm._db() as db:
        n = db.conn.execute(text("SELECT COUNT(*) FROM plan_orders WHERE owner_user = :o"), {"o": str(uid)}).scalar()
    assert broke == [] and (len(made), len(refused), n) == (2, 18, 2)


# ---- 6. anonymous pages cannot spend the Data API ---------------------------------------------------------------------------

def test_prices_are_looked_up_only_for_known_places_and_within_a_budget(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    calls = []
    monkeypatch.setattr(prices, "TRANSPORT", lambda url, headers, timeout: calls.append(url) or {"success": True, "data": []})
    client.get("/plan?place=Bend%2C+Oregon&iata=RDM&d=2027-03-05&r=2027-03-09&a=2&home=SFO")
    assert calls == []                                        # a place we do not know: no lookup with our token
    homes = [a + b + c for a in "ABCDEFGH" for b in "XYZ" for c in "PQ"][:60]
    for h in homes:
        client.get(f"/plan?place=Lake+Tahoe&d=2027-03-05&r=2027-03-09&a=2&home={h}")
    assert len(calls) == prices.BUDGET_PER_MINUTE == 20       # past the budget: no price, no call


def test_the_cache_drops_the_oldest_not_everything(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setattr(prices, "BUDGET_PER_MINUTE", 10_000)
    monkeypatch.setattr(prices, "_CACHE_MAX", 5)
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": [{"price": 100}]})
    for h in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"):
        prices.flight_from(h, "RNO", date(2027, 3, 5), date(2027, 3, 9))
    assert len(prices._CACHE) == 5 and ("AAA", "RNO", date(2027, 3, 5), date(2027, 3, 9)) not in prices._CACHE and ("FFF", "RNO", date(2027, 3, 5), date(2027, 3, 9)) in prices._CACHE


# ---- 8. a partner's button only for the partner's own name --------------------------------------------------------------------

@pytest.mark.parametrize("name", ["American Express Travel", "Budget Travel", "Tahoe Booking Co", "Expedia Cruises Inc", "National Park Lodge", "The Dollar Store", "Delta Lodge"])
def test_a_name_that_only_contains_a_partners_word_has_no_button(name):
    assert manage.find(name) is None


@pytest.mark.parametrize("name, site", [("Expedia", "Expedia"), ("expedia.com", "Expedia"), ("Booking.com", "Booking.com"), ("Enterprise Rent-A-Car", "Enterprise"),
                                        ("Delta Air Lines", "Delta"), ("Alaska Airlines", "Alaska Airlines"), ("American Airlines", "American Airlines"), ("Hertz", "Hertz")])
def test_a_partners_own_name_still_finds_it(name, site):
    assert manage.find(name).name == site


# ---- 9. a typed state that is not the table's is the person's own place --------------------------------------------------------

@pytest.mark.parametrize("typed, iata", [("Portland, ME", ""), ("Portland, Maine", ""), ("Jackson, NH", ""), ("Vail, AZ", ""), ("Portland, OR", "PDX"), ("Jackson, WY", "JAC"),
                                         ("Lake Tahoe, NV", "RNO"), ("Lake Tahoe, CA", "RNO")])
def test_the_state_typed_decides(typed, iata):
    p = places.resolve(typed)
    assert p.iata == iata and p.known == bool(iata)
    if not iata:
        assert p.name == typed and p.city == typed.split(",")[0]


# ---- 11. a failed free plan is no refund ------------------------------------------------------------------------------------

def test_a_failed_free_plan_is_not_a_refund_due(client, monkeypatch, caplog):
    monkeypatch.delenv("PLAN_FOR_ME_PAID", raising=False)
    uid, tenant, email = buyer("ari")
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    with caplog.at_level(logging.WARNING, logger="gitaway.planforme"):
        pfm._fail(o["id"], "refusal")
    assert "refund due" not in caplog.text
    assert pfm.totals(pfm.admin_rows())["refunds"] == 0
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    page = client.get("/admin").text
    assert 'id="refund-' not in page and re.search(r'id="ad-refunds"[^>]*>([^<]*)<', page).group(1) == "0 · $0"


# ---- 12. /book keeps the creator rules /go has -----------------------------------------------------------------------------------

@pytest.fixture
def marker(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")


def flight(client):
    html = client.get(TAHOE).text
    return client.get(next(h for h in book_links(html) if "/book/flight" in h), follow_redirects=False)


def test_a_flight_from_a_creators_trip_carries_their_marker_and_counts(client, marker):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-09&a=2&via={handle}", headers=seen_on(handle))
    loc = flight(client).headers["location"]
    assert "marker=555111.anon_laketahoe_261219_flight_" + handle.replace("-", "_") in loc
    assert affiliate.clicks_by_creator() == {handle: (1, 1)}


def test_a_plain_link_counts_for_the_creator_but_carries_no_marker(client, marker):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-09&a=2&via={handle}", headers=seen_on(handle))
    html = client.get(TAHOE).text
    loc = client.get(next(h for h in book_links(html) if "site=airbnb" in h), follow_redirects=False).headers["location"]
    assert "marker" not in loc and "555111" not in loc
    assert affiliate.clicks_by_creator() == {handle: (1, 0)}


def test_a_click_on_a_waiting_trip_pays_nobody_and_forgets_the_cookie(client, marker):
    _, handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-09&a=2&via={handle}", headers=seen_on(handle))
    waiting, _, _ = live_trip("lee@example.com", "Lee Park", "Two days in San Diego")
    from gitaway import community
    community.set_review(waiting["slug"], "pending")
    html = client.get(TAHOE).text
    r = client.get(next(h for h in book_links(html) if "/book/flight" in h), headers={"referer": f"http://testserver/trips/{waiting['slug']}"}, follow_redirects=False)
    assert "marker=801445." in r.headers["location"] and 'ga_via=""' in r.headers.get("set-cookie", "").replace("ga_via=;", 'ga_via="";')


def test_a_cross_site_click_is_sent_on_but_not_logged(client):
    sign_in(client, "ari")
    html = client.get(TAHOE).text
    href = next(h for h in book_links(html) if "site=vrbo" in h)
    assert client.get(href, headers={"sec-fetch-site": "cross-site"}, follow_redirects=False).status_code == 302
    from gitaway.partners import log
    assert log.clicks(person()) == []
    client.get(href, headers={"sec-fetch-site": "same-origin"}, follow_redirects=False)
    assert len(log.clicks(person())) == 1


# ---- 17. no redirect carries the token, and no log line keeps part of it --------------------------------------------------------

class _Hop(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        _Hop.seen.append((self.path, self.headers.get("X-Access-Token")))
        if self.path.startswith("/first"):
            self.send_response(302)
            self.send_header("Location", "/second")
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"success": true, "data": [{"price": 1}]}')

    def log_message(self, *a):
        pass


def test_a_redirect_is_refused_and_the_token_goes_nowhere_else():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Hop)
    threading.Thread(target=server.handle_request, daemon=True).start()
    _Hop.seen.clear()
    with pytest.raises(Exception):
        prices._get(f"http://127.0.0.1:{server.server_port}/first", {"X-Access-Token": "secret-token"}, 2)
    server.server_close()
    assert [p for p, _ in _Hop.seen] == ["/first"]
    assert travelpayouts._opener.handlers and any(type(h).__name__ == "NoRedirect" for h in travelpayouts._opener.handlers)


@pytest.mark.parametrize("pad", [140, 150, 155, 159])
def test_the_token_is_redacted_before_the_log_line_is_cut(monkeypatch, caplog, pad):
    token = "tok_" + "s" * 40
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", token)

    def boom(*a):
        raise TimeoutError("x" * pad + token)
    monkeypatch.setattr(prices, "TRANSPORT", boom)
    with caplog.at_level(logging.WARNING):
        prices.flight_from("SFO", "RNO", date(2027, 3, 5), date(2027, 3, 9))
        travelpayouts._failed(TimeoutError("x" * pad + token), "plain link")
    assert "tok_s" not in caplog.text and "sssss" not in caplog.text


# ---- nits --------------------------------------------------------------------------------------------------------------------------

def test_the_ask_card_says_an_airbnb(client):
    sign_in(client, "ari")
    assert client.post("/trips/import/save", data={"text": TAHOE_TRIP}, follow_redirects=False).status_code == 303
    assert "This looks like an Airbnb confirmation" in words(client.post("/trip/ask/propose", data={"text": AIRBNB}).text)
    assert "This looks like a Booking.com confirmation" in words(client.post("/trip/ask/propose", data={"text": BOOKING}).text)


def test_the_partner_log_names_the_site_not_its_key(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    sign_in(client, "ari")
    html = client.get(TAHOE).text
    client.get(next(h for h in book_links(html) if "site=airbnb" in h), follow_redirects=False)
    page = client.get("/partners").text
    assert re.search(r'class="pt-who">Airbnb<', page) and 'class="pt-who">airbnb<' not in page


def test_the_footer_does_not_say_never_takes_payment_while_plans_are_sold(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("PLAN_FOR_ME_PAID", "1")
    assert "never takes payment" not in client.get("/plan").text
    monkeypatch.setenv("PLAN_FOR_ME_PAID", "0")
    assert "never takes payment" in client.get("/plan").text


def test_the_details_page_says_where_once_not_twice(client):
    sign_in(client, "ari")
    assert client.post("/trips/import/save", data={"text": TAHOE_TRIP}, follow_redirects=False).status_code == 303
    t = words(client.get("/trip/details").text)
    assert "Booked on Expedia" in t and "Booked elsewhere · Expedia" not in t
    today = words(client.get("/trip").text)
    assert "Booked elsewhere · Expedia" not in today


def test_admin_counts_plain_link_clicks_per_lane(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    html = client.get(TAHOE).text
    for site in ("airbnb", "vrbo", "getyourguide"):
        client.get(next(h for h in book_links(html) if f"site={site}" in h), follow_redirects=False)
    card = re.search(r'id="ad-plain"(.*?)</section>|id="ad-plain"(.*?)</div>\s*</div>', client.get("/admin").text, re.S)
    assert card and "stay 2" in words(card.group(0)) and "todo 1" in words(card.group(0))


# ---- 18. body limits on the paste routes ------------------------------------------------------------------------------------------

def test_the_paste_routes_refuse_a_body_past_their_limit(client):
    from main import BodyLimit
    from gitaway import expedia, say
    assert BodyLimit.LIMITS["/trips/import"] == expedia.MAX_PDF_BYTES + 100_000 and BodyLimit.LIMITS["/trip/ask/propose"] >= 4 * say.LIMIT
    sign_in(client, "ari")

    def chunks():      # no Content-Length: only the counted body can stop it
        for _ in range(40):
            yield b"text=" + b"a" * 20_000
    r = client.post("/trip/ask/propose", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413


# ---- 7. no copy sells the removed workspace -----------------------------------------------------------------------------------------

def test_no_page_promises_a_running_total_or_shows_an_unlabelled_price(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    for path in ("/", "/trips/import", "/plan"):
        page = client.get(path).text
        t = words(page).lower()
        for claim in ("one honest total", "running cost ledger", "cheapest combo", "one running total"):
            assert claim not in t, (path, claim)
        assert "$1,912 total" not in page, path
    sign_in(client, "ari")
    t = words(client.get("/trips/import").text).lower()
    assert "one honest total" not in t


# ---- 10. kids' ages are pickers, one per kid --------------------------------------------------------------------------------------

def test_the_lanes_form_has_a_kid_count_and_an_age_picker_per_kid(client):
    page = client.get(TAHOE).text
    form = re.search(r'<form[^>]*id="ps-trip".*?</form>', page, re.S).group(0)
    assert 'name="k"' not in form and re.search(r'<select[^>]*name="n"', form) and re.search(r'<select[^>]*name="k1"', form)
    assert re.search(r'<option value="2" selected>2</option>', re.search(r'<select[^>]*name="n".*?</select>', form, re.S).group(0))
    picked = client.get("/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&n=2&k1=8&k2=11&k3=5")
    assert "Dec 19 – 26 · 2 adults, 2 kids" in words(picked.text) and all("k=8%2C11" in h or "k=8,11" in h for h in book_links(picked.text))
    missing = client.get("/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&n=2&k1=8&k2=")
    assert "Pick an age from 0 to 17" in words(missing.text) and book_links(missing.text) == []
