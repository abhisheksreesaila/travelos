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


def test_the_calendar_form_keeps_native_day_and_time_fields(client):
    book(client)
    html = client.get("/calendar?add=2&at=11:00").text
    assert re.search(r'<input[^>]*type="time"[^>]*name="start"', html) or re.search(r'<input[^>]*name="start"[^>]*type="time"', html)
    assert re.search(r'<select[^>]*name="day"', html)
