"""F-274 in a real browser: Book this trip with LiteAPI's payment form. The form's script is stubbed (a page.route answers LiteAPI's one script address with a stand-in that draws a "Pay"
button where the real form would put its card fields): success (the browser returns to GitAway, the stay is booked once with the transaction id and the pass shows), the form failing to load,
a card declined, a price that moved before paying, a code applied and a code refused, a double press. The server side is the recordings of tests/fixtures/liteapi_pay. Nothing real is paid.

What stays for a human (the card itself): LiteAPI's real form in a real browser, the sandbox test card 4242 4242 4242 4242, and the redirect back from LiteAPI's processor."""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi, matrixbook as mb
from tests.test_liteapi_pay import LIVE
from tests.test_matrixbook_live import BOOK, Live, PREBOOK
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_matrixbook_sheet import BookStand, _no_presses_yet, open_square, to_review  # noqa: F401 (the autouse fixture)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SDK = liteapi.PAYMENT_SDK
STUB = """
window.LiteAPIPayment = class {
  constructor(config) { this.config = config; window.__pay = { config: config, loaded: true, paid: 0 }; }
  handlePayment() {
    var el = document.querySelector(this.config.targetElement), cfg = this.config;
    el.innerHTML = '<button type="button" id="stub-pay">Pay with the stub</button><p id="stub-msg"></p>';
    el.querySelector('#stub-pay').addEventListener('click', function () {
      window.__pay.paid += 1;
      if (window.__declined) { el.querySelector('#stub-msg').textContent = 'Your card was declined.'; return; }
      location.href = cfg.returnUrl + '&redirect_status=succeeded';
    });
  }
};
"""


@pytest.fixture
def live(monkeypatch, stand):  # noqa: F811
    """A live key where real booking is on, the squares' stays carrying offers, LiteAPI answering from the recordings (the shown stay $1,540 with its $120 fee at the hotel)."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "1")
    box = Live()
    box.shown = 1540.0
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    monkeypatch.setattr(gridsource, "SQUARE", BookStand())
    mb.forget()
    return box


def shot(page, name):
    """F274_SHOTS=<folder> writes the sheet's states there (for looking at, not asserted)."""
    if os.environ.get("F274_SHOTS"):
        Path(os.environ["F274_SHOTS"]).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(os.environ["F274_SHOTS"]) / f"f274-{name}.png"))


def with_stub(page, fail=False):
    """LiteAPI's script address answered by the stand-in (or by nothing); every request to another site than ours is recorded."""
    page.outside = []
    page.on("request", lambda r: page.outside.append(r.url) if not re.match(r"http://(127\.0\.0\.1|localhost)", r.url) and not r.url.startswith("data:") else None)
    page.route(SDK, lambda route: route.abort() if fail else route.fulfill(status=200, content_type="application/javascript", body=STUB))


def guest(page, email="anne@example.com", phone="+1 415 555 0100"):
    page.fill("#mxb-first", "Anne-Marie")
    page.fill("#mxb-last", "O’Neil")
    page.click("[data-cont]")
    page.fill("#mxb-email", email)
    page.fill("#mxb-phone", phone)
    page.click("[data-cont]")
    page.click("[data-req='Quiet room']")
    page.click("[data-cont]")


def review(page, viewport):
    panel = open_square(page, viewport)
    panel.locator(".dr-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    guest(page)
    expect(page.locator(".mxb-f")).to_have_attribute("data-step", "3")
    return sheet


def book_calls(box):
    return [c for c in box.asked if c[0] == BOOK]


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_review_says_who_sells_it_and_the_refund_rules_then_the_form_pays_and_the_stay_is_booked_once(matrix, live, viewport):  # noqa: F811
    page = matrix(viewport, motion=True, signed_in=True)
    with_stub(page)
    sheet = review(page, viewport)
    expect(sheet.locator(".mxb-sandbox")).to_have_text("Sold by Nuitée through LiteAPI. Your card is charged when you pay")
    expect(sheet.locator(".mxb-policy")).to_contain_text("Non-refundable: if you cancel, nothing comes back.")
    expect(sheet.locator(".mxb-policy")).to_contain_text("Sold by Nuitée through LiteAPI. Nuitée charges your card; GitAway never sees it.")
    expect(sheet.locator(".mxb-codebox")).to_contain_text("Have a code?")
    expect(sheet.locator(".mxb-go")).to_be_disabled()                      # the tick is required
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $1,540")
    expect(sheet.locator("[data-moved]")).to_be_empty()                    # the price is the square's: nothing moved
    page.wait_for_timeout(700)
    shot(page, f"{viewport['width']}-review")
    assert live.calls(BOOK) == [] and page.outside == []                   # nothing booked, nothing of another site yet
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(sheet.locator("#stub-pay")).to_be_visible()                     # LiteAPI's form (the stand-in) is in our sheet
    assert page.outside == [SDK]                                           # the one address of another site, and only now
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-pay")
    config = page.evaluate("() => window.__pay.config")
    assert (config["publicKey"], config["secretKey"], config["targetElement"]) == ("live", "[secretKey]", "#mxb-pay-el")
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+/plan/matrix/book/return\?token=[A-Za-z0-9_-]+", config["returnUrl"])
    expect(sheet.locator("[data-pay-root]")).not_to_have_attribute("data-secret", re.compile(".+"))      # the key is not left in the page
    expect(sheet.locator(".mxb-total")).to_have_text("$1,420")                                          # what the card is charged now (the $120 fee is paid at the hotel)
    assert page.locator("input[autocomplete^='cc-'], input[name*='card' i]").count() == 0               # no card field of ours
    assert live.calls(BOOK) == [] and len(live.calls(PREBOOK)) == 1
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/return**")
    expect(page.locator("body")).to_contain_text("You’re booked")
    page.wait_for_timeout(1200)
    shot(page, f"{viewport['width']}-booked")
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    expect(page.locator("body")).to_contain_text("Charged by Nuitée through LiteAPI. GitAway never saw your card.")
    sent = live.calls(BOOK)
    assert len(sent) == 1 and sent[0]["payment"]["method"] == "TRANSACTION_ID" and "ACC_CREDIT_CARD" not in json.dumps(live.asked)
    page.reload()                                                          # a reload shows the same booking and books nothing again
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    assert len(live.calls(BOOK)) == 1 and page.errors == []


def test_the_payment_form_failing_to_load_says_so_and_nothing_is_booked(matrix, live):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page, fail=True)
    review(page, DESKTOP)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator("[data-pay-wait]")).to_contain_text("did not load. Nothing was charged.")
    assert live.calls(BOOK) == [] and page.locator("[data-pay-root]").count() == 1


def test_a_card_declined_keeps_the_person_in_the_form_and_books_nothing(matrix, live):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    page.evaluate("window.__declined = true")
    review(page, DESKTOP)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    page.click("#stub-pay")
    expect(page.locator("#stub-msg")).to_have_text("Your card was declined.")
    assert live.calls(BOOK) == [] and "/book/return" not in page.url


def test_a_price_that_moved_since_the_square_is_said_before_paying(matrix, live):  # noqa: F811
    live.shown = 1580.0                                                    # the prebook now answers $1,580 for the room the square showed at $1,540
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    sheet = review(page, DESKTOP)
    expect(sheet.locator("[data-moved]")).to_contain_text("The price moved: it was $1,540 on the square and is $1,580 now.")
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $1,580")


def test_a_code_is_applied_in_the_checkout_and_a_wrong_one_is_refused(matrix, live):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    sheet = review(page, DESKTOP)
    expect(sheet.locator(".mxb-off")).to_be_hidden()                       # the public price shows no code
    page.fill("#mxb-code", "NOSUCHCODE")
    page.click("[data-apply]")
    expect(page.locator("[data-code-msg]")).to_have_text("That code is not valid. Check it, or book without one.")
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $1,540")
    page.fill("#mxb-code", "F274SANDBOX")
    page.press("#mxb-code", "Enter")                                       # Enter applies the code, it does not move on or book
    expect(page.locator("[data-code-msg]")).to_have_text("Code F274SANDBOX applied.")
    expect(sheet.locator(".mxb-off")).to_be_visible()
    expect(sheet.locator("[data-sum='discount']")).to_have_text("−$142")
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $1,398")
    assert live.calls(BOOK) == [] and page.locator(".mxb-f").get_attribute("data-step") == "3"
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator("#stub-pay")).to_be_visible()
    expect(page.locator(".mxb-total")).to_have_text("$1,278")                # the card pays the discounted stay: $1,420 less 10%
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/return**")
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    assert live.calls(BOOK)[0]["prebookId"] == "3JH4qYGIc"


def test_pressing_continue_twice_opens_one_form_and_books_nothing(matrix, live):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    review(page, DESKTOP)
    page.click(".mxb-agree")
    page.dblclick(".mxb-go")
    expect(page.locator("#stub-pay")).to_have_count(1)
    assert len(live.calls(PREBOOK)) == 1 and live.calls(BOOK) == []
