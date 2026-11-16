"""F-274, opt-in: the whole payment-form path against LiteAPI's REAL sandbox in a real browser (not stubbed): a real search and prebook, LiteAPI's real card form (Stripe's, in frames
inside our sheet), the sandbox test card 4242 4242 4242 4242, the return to GitAway, the TRANSACTION_ID booking, then the cancel from the booking page.

Skipped unless F274_REAL_SANDBOX=1 and LITEAPI_KEY is a `sand_` key in the environment (it makes a real sandbox booking each run, calls LiteAPI and loads LiteAPI's and Stripe's scripts):
    set -a; . ~/.config/gitaway/liteapi-sandbox.env; set +a; F274_REAL_SANDBOX=1 pixi run python -m pytest tests_browser/test_matrixbook_real_sandbox.py -s
F274_CODE=<a sandbox voucher code> also applies a code first. F274_REC=<folder> records LiteAPI's booking-host answers there (the key and every `secretKey` scrubbed). The key is never printed.
LiteAPI's form was read and its hosts seen on 2026-11-16 (D-844): payment-wrapper.liteapi.travel, js.stripe.com, m.stripe.network, merchant-ui-api.stripe.com, r.stripe.com, b.stripecdn.com,
hcaptcha.com and newassets.hcaptcha.com (Stripe's captcha), apay-us.amazon.com (Amazon Pay and Klarna buttons it draws)."""
import json
import os

import pytest
from playwright.sync_api import expect

from gitaway import importer, liteapi, tripimport as ti
from tests.test_matrixbook_page import person, stays_booked
from tests_browser.helpers import DESKTOP

URL = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2&b=2300"

pytestmark = pytest.mark.skipif(os.environ.get("F274_REAL_SANDBOX") != "1" or not os.environ.get("LITEAPI_KEY", "").startswith("sand_"), reason="opt-in: F274_REAL_SANDBOX=1 and a sandbox key")


def recorder(monkeypatch, folder):
    """Wrap the transport so LiteAPI's booking-host answers are written (scrubbed) to `folder`."""
    real, counts = liteapi.TRANSPORT, {}
    os.makedirs(folder, exist_ok=True)

    def scrub(v):
        if isinstance(v, dict):
            return {k: ("[secretKey]" if k == "secretKey" and isinstance(x, str) else scrub(x)) for k, x in v.items()}
        return [scrub(x) for x in v] if isinstance(v, list) else v

    def record(url, headers, body, timeout, *method):
        status, ctype, raw = real(url, headers, body, timeout, *method)
        if "book.liteapi.travel" in url:
            what = "cancel" if "/bookings/" in url else url.rsplit("/", 1)[1]
            counts[what] = counts.get(what, 0) + 1
            try:
                doc = json.loads(raw.decode())
            except ValueError:
                doc = {"raw": "not json"}
            text = json.dumps({"status": status, "body": scrub(doc)}, indent=1).replace(os.environ["LITEAPI_KEY"], "[key]")
            open(f"{folder}/real_{what}_{counts[what]}.json", "w").write(text)
        return status, ctype, raw
    monkeypatch.setattr(liteapi, "TRANSPORT", record)


def test_a_real_sandbox_stay_is_paid_in_liteapis_form_booked_and_cancelled(browser, base_url, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("GITAWAY_SANDBOX_FORM", "1")
    if os.environ.get("F274_REC"):
        recorder(monkeypatch, os.environ["F274_REC"])
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    ctx.set_default_timeout(60000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(base_url + URL)
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'", timeout=120000)
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq").nth(2).click()
    page.locator("#mx-drawer .dr-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    page.click("[data-cont]")                       # the made-up guest, then the mobile number the booking needs
    page.fill("#mxb-phone", "+1 415 555 0100")
    page.click("[data-cont]")
    page.click("[data-cont]")
    page.click(".mxb-agree")
    review = sheet.locator(".mxb-go").inner_text()
    if os.environ.get("F274_CODE"):
        page.fill("#mxb-code", os.environ["F274_CODE"])
        page.click("[data-apply]")
        page.wait_for_function("() => !/Checking/.test(document.querySelector('[data-code-msg]').textContent)")
        assert "applied" in page.locator("[data-code-msg]").inner_text() and sheet.locator(".mxb-go").inner_text() != review
    page.click(".mxb-go")
    page.wait_for_selector("#mxb-pay-el iframe[title*='payment input']", timeout=60000)       # LiteAPI's real form is in our sheet
    assert page.locator("input[autocomplete^='cc-']").count() == 0                              # and no card field is ours
    card = page.frame_locator("#mxb-pay-el iframe[title*='payment input']").first
    card.get_by_placeholder("1234 1234 1234 1234").fill("4242424242424242")
    card.get_by_placeholder("MM / YY").fill("12 / 34")
    card.get_by_placeholder("CVC").fill("123")
    try:
        card.get_by_placeholder("12345").fill("94105", timeout=3000)
    except Exception:
        pass
    page.locator("#mxb-pay-el button[type=submit], #mxb-pay-el button").last.click()
    page.wait_for_url("**/plan/matrix/book/return**", timeout=90000)
    expect(page.locator("[data-booking-id]")).to_be_visible()
    row = stays_booked()[-1]
    assert (row["sample"], row["booking_id"]) == (0, page.locator("[data-booking-id]").inner_text())
    plan = importer.plan_of(person(), row["trip_id"])
    spec = next(x for x in ti.block_specs(plan) if x.kind == "checkin")
    page.goto(f"{base_url}/trip/booking?block={spec.id}")
    page.check("input[name=sure]")
    page.click("#bk-cancel-go")
    expect(page.locator("#bk-cancelled")).to_contain_text("Cancelled.")
    print("cancelled:", page.locator("#bk-cancelled").inner_text())
