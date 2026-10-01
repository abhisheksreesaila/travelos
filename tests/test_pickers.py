"""F-051: themed pickers. The page keeps the real date, select and time inputs (forms work without JavaScript and the server still
validates); pickers.js dresses them. The look and the keyboard are tested in tests_browser/test_pickers.py."""
import re

from tests.test_calendar import book
from tests.test_start import submit, tags


def test_start_keeps_the_native_date_inputs_and_marks_them_as_one_range(client):
    html = client.get("/start").text
    d, r = tags(html, "d")[0]["_raw"], tags(html, "r")[0]["_raw"]
    assert 'type="date"' in d and 'type="date"' in r
    assert 'data-ga-range="trip"' in d and 'data-ga-range="trip"' in r and "data-ga-end" in r and "data-ga-end" not in d
    assert 'min="2026-09-30"' in d  # past days are disabled from the server's today, not the visitor's clock


def test_start_marks_ages_as_chips_and_adults_and_kids_as_steppers(client):
    html = client.get("/start?d=2026-10-17&r=2026-10-19&a=2&k=7,9").text
    assert 'data-ga="chips"' in tags(html, "k1")[0]["_raw"]
    assert 'data-ga="stepper"' in tags(html, "a")[0]["_raw"] and 'data-ga="stepper"' in tags(html, "n")[0]["_raw"]
    assert "<select" in html and 'type="date"' in html  # the native controls are still in the page


def test_start_still_validates_on_the_server_when_the_picker_never_ran(client):
    r = submit(client, d="2026-09-01", r="2026-09-03")
    assert r.status_code == 422 and 'aria-invalid="true"' in r.text


def test_the_pages_with_pickers_load_the_picker_script_and_styles(client):
    book(client)
    for url in ("/start", "/family", "/calendar?add=1&at=11:00"):
        html = client.get(url).text
        assert "/assets/js/pickers.js" in html and "/assets/css/pickers.css" in html, url
        assert html.index("/assets/css/pickers.css") > html.index("/assets/css/base.css"), url


def test_every_page_with_a_select_or_a_date_or_time_field_loads_the_pickers(client):
    """A new page with such a field must add *pickers.HEAD, or its browser-default widgets show."""
    book(client)
    paths = ["/", "/start", "/discover", "/plan", "/calendar?view=days", "/calendar?add=2&at=11:00", "/family", "/trips", "/creators", "/trips/import", "/rides", "/pay", "/trip"]
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
    assert "/start" in found and "/family" in found and "/trip" in found  # the walk really reached pages with fields


def test_the_calendar_form_keeps_native_day_and_time_fields(client):
    book(client)
    html = client.get("/calendar?add=2&at=11:00").text
    assert re.search(r'<input[^>]*type="time"[^>]*name="start"', html) or re.search(r'<input[^>]*name="start"[^>]*type="time"', html)
    assert re.search(r'<select[^>]*name="day"', html)
