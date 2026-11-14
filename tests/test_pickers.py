"""F-051: themed pickers. The page keeps the real date, select and time inputs (forms work without JavaScript and the server still
validates); pickers.js dresses them. The look and the keyboard are tested in tests_browser/test_pickers.py."""
import re

from tests.test_calendar import book
from tests.test_planforme import GOOD
from tests.test_signin import sign_in


def tags(html, name):
    """Every <input|select> with this name, as attribute dicts (attribute order is not part of the contract)."""
    found = re.findall(r'<(?:input|select)\b[^>]*\bname="%s"[^>]*>' % re.escape(name), html)
    return [dict(re.findall(r'([\w-]+)="([^"]*)"', t)) | {"_raw": t} for t in found]


# F-231: the range, steppers and age chips were on the Where to? form (/start); the trip builder and Plan it for me's intake keep them.

def test_plan_it_for_me_keeps_the_native_date_inputs_and_marks_them_as_one_range(client):
    html = client.get("/plan-for-me/start").text
    d, r = tags(html, "start")[0]["_raw"], tags(html, "end")[0]["_raw"]
    assert 'type="date"' in d and 'type="date"' in r
    assert 'data-ga-range="trip"' in d and 'data-ga-range="trip"' in r and "data-ga-end" in r and "data-ga-end" not in d
    assert 'min="2026-09-30"' in d  # past days are disabled from the server's today, not the visitor's clock


def test_plan_it_for_me_marks_ages_as_chips_and_adults_and_kids_as_steppers(client):
    html = client.get("/plan-for-me/start?nkids=2").text
    assert 'data-ga="chips"' in tags(html, "k1")[0]["_raw"]
    assert 'data-ga="stepper"' in tags(html, "adults")[0]["_raw"] and 'data-ga="stepper"' in tags(html, "nkids")[0]["_raw"]
    assert "<select" in html and 'type="date"' in html  # the native controls are still in the page


def test_plan_it_for_me_still_validates_on_the_server_when_the_picker_never_ran(client):
    sign_in(client)
    r = client.post("/plan-for-me", data={**GOOD, "start": "2026-09-01", "end": "2026-09-03"}, follow_redirects=False)
    assert r.status_code == 422 and 'aria-invalid="true"' in r.text


def test_the_pages_with_pickers_load_the_picker_script_and_styles(client):
    book(client)
    for url in ("/plan-for-me/start", "/family", "/calendar?add=1&at=11:00"):
        html = client.get(url).text
        assert "/assets/js/pickers.js" in html and "/assets/css/pickers.css" in html, url
        assert html.index("/assets/css/pickers.css") > html.index("/assets/css/base.css"), url


def test_every_page_with_a_select_or_a_date_or_time_field_loads_the_pickers(client):
    """A new page with such a field must add *pickers.HEAD, or its browser-default widgets show."""
    book(client)
    paths = ["/", "/plan-for-me/start", "/discover", "/plan", "/calendar", "/trip?add=1&day=2&at=11:00", "/family", "/trips", "/creators", "/trips/import", "/rides", "/pay", "/trip?tab=today"]
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if "GET" in (getattr(route, "methods", None) or set()) and "{" not in path and path not in paths and not path.startswith(("/assets", "/auth", "/logout", "/healthz")):
            paths.append(path)
    found = []
    for path in paths:
        r = client.get(path)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            continue
        if re.search(r'<select\b|<input\b[^>]*type="(date|time)"', r.text):
            found.append(path)
            assert "/assets/js/pickers.js" in r.text and "/assets/css/pickers.css" in r.text, f"{path} has a select, date or time field but no pickers.HEAD"
    assert "/plan-for-me/start" in found and "/family" in found and "/trip?tab=today" in found  # the walk really reached pages with fields


def test_the_add_sheet_keeps_native_time_fields(client):
    book(client)
    html = client.get("/trip?add=1&day=2&at=11:00").text
    assert re.search(r'<input[^>]*type="time"[^>]*name="start"', html) or re.search(r'<input[^>]*name="start"[^>]*type="time"', html)
    assert 'value="11:00"' in html
