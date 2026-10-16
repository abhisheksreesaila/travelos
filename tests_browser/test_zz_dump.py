from tests_browser.helpers import PHONE
from tests_browser.test_topbar import signed_in  # noqa: F401
from tests_browser.test_week_cards import cards, week


def test_dump(signed_in):
    page = week(signed_in, PHONE)
    for c in cards(page):
        print("CARD", c["day"], c["free"], c["headText"], [r["text"] for r in c["rows"]], c["rect"]["h"])
    print(page.evaluate("document.querySelector('#cz-week').innerHTML")[:3000])
