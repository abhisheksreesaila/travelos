"""F-035: the "Where to?" trip start at /start, and where sign-in and the landing page lead."""
import html as htmllib
import re
from urllib.parse import quote

from gitaway import catalog, session as ses
from tests.test_signin import person, session_data, sign_in, stored_booking

GOOD = {"go": "1", "from": "SFO", "to": "la", "d": "2026-10-16", "r": "2026-10-20", "a": "2", "n": "2", "k1": "4", "k2": "7"}


def submit(client, **over):
    return client.get("/start", params={**GOOD, **over}, follow_redirects=False)


def tags(html, name):
    """Every <input|select> with this name, as attribute dicts (attribute order is not part of the contract)."""
    found = re.findall(r'<(?:input|select)\b[^>]*\bname="%s"[^>]*>' % re.escape(name), html)
    return [{k: htmllib.unescape(v) for k, v in re.findall(r'([\w-]+)="([^"]*)"', t)} | {"_raw": t} for t in found]


def selected(html, name):
    m = re.search(r'<select\b[^>]*\bname="%s"[^>]*>(.*?)</select>' % name, html, re.S)
    return re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', m.group(1)).group(1) if m else None


# ---- the page ------------------------------------------------------------------------------------------------------

def test_start_asks_where_to_and_is_prefilled_with_the_sample_trip(client):
    r = client.get("/start")
    assert r.status_code == 200
    h = r.text
    assert "Where to?" in h and "Find my trip" in h
    form = re.search(r"<form[^>]*>", h).group(0)
    assert 'method="get"' in form and 'action="/start"' in form
    assert tags(h, "d")[0]["value"] == "2026-10-16" and tags(h, "r")[0]["value"] == "2026-10-20"
    assert tags(h, "d")[0]["type"] == "date" and tags(h, "r")[0]["type"] == "date"
    assert selected(h, "from") == "SFO" and selected(h, "a") == "2" and selected(h, "n") == "2"
    assert selected(h, "k1") == "4" and selected(h, "k2") == "7"


def test_every_field_has_a_label(client):
    h = client.get("/start").text
    for name, word in [("from", "From"), ("d", "Leaving"), ("r", "Back"), ("a", "Adults"), ("n", "Kids")]:
        assert re.search(r'<label[^>]*>(?:(?!</label>).)*%s(?:(?!</label>).)*name="%s"' % (word, name), h, re.S), name
    assert re.search(r"<label[^>]*>(?:(?!</label>).)*Kid 1 age", h, re.S)


def test_los_angeles_is_live_and_the_rest_are_coming_soon_and_cannot_be_submitted(client):
    h = client.get("/start").text
    chips = {re.search(r'value="(\w+)"', t["_raw"]).group(1): t for t in tags(h, "to")}
    assert set(chips) == {"la", "sd", "hi"}
    assert "disabled" not in chips["la"]["_raw"] and "checked" in chips["la"]["_raw"]
    assert "disabled" in chips["sd"]["_raw"] and "disabled" in chips["hi"]["_raw"]
    assert h.count("coming soon") + h.count("Coming soon") >= 2
    r = submit(client, to="sd")
    assert r.status_code == 422 and "coming soon" in r.text.lower()


def test_the_sample_trip_submits_to_the_plain_workspace(client):
    r = submit(client)
    assert r.status_code == 303 and r.headers["location"] == "/plan"
    assert "$3,088" in client.get(r.headers["location"]).text


def test_a_different_trip_submits_with_its_url_and_shows_its_prices(client):
    r = submit(client, r="2026-10-19")
    assert r.status_code == 303 and r.headers["location"] == "/plan?d=2026-10-16&r=2026-10-19&a=2&k=4,7"
    t = catalog.trip_from_url("2026-10-16", "2026-10-19", "2", "4,7")
    html = client.get(r.headers["location"]).text
    assert re.search(r'id="ws-total"[^>]*>%s<' % re.escape(catalog.money(catalog.quote("f1", "h1", "c1", trip=t).total_cents)), html)
    r = submit(client, a="3")
    assert r.headers["location"] == "/plan?d=2026-10-16&r=2026-10-20&a=3&k=4,7"


def test_no_kids_means_no_ages_in_the_url(client):
    r = submit(client, n="0", a="1")
    assert r.headers["location"] == "/plan?d=2026-10-16&r=2026-10-20&a=1"


def test_only_the_asked_for_kid_ages_count(client):
    r = submit(client, n="1", k1="9", k2="3")
    assert r.headers["location"].endswith("&k=9")


# ---- friendly server-side errors ----------------------------------------------------------------------------------

def test_errors_are_friendly_keep_the_form_and_mark_the_field(client):
    for over, words, name in [
        (dict(r="2026-10-15"), "must be after", "r"),
        (dict(r="2026-11-20"), "30 nights", "r"),
        (dict(a="0"), "at least 1 adult", "a"),
        (dict(a="7", n="2"), "more than 8", "a"),
        (dict(d="2026-02-31"), "valid depart date", "d"),
        (dict(r="soon"), "valid return date", "r"),
        (dict(k2=""), "age", "k2"),
    ]:
        r = submit(client, **over)
        assert r.status_code == 422, over
        h = r.text
        assert words in h, (over, words)
        assert 'role="alert"' in h
        assert tags(h, "d")[0]["value"] == over.get("d", "2026-10-16") or "d" in over
        bad = tags(h, name)[0]
        assert bad.get("aria-invalid") == "true", (over, name)


def test_a_bad_submit_keeps_what_was_typed(client):
    h = submit(client, r="2026-10-15", a="3").text
    assert tags(h, "r")[0]["value"] == "2026-10-15"
    assert selected(h, "a") == "3"
    assert selected(h, "k2") == "7"


def test_a_page_without_go_never_shows_errors(client):
    h = client.get("/start?d=junk").text
    assert 'role="alert"' not in h and tags(h, "d")[0]["value"] == "2026-10-16"


def test_start_prefills_from_a_trip_url_and_falls_back_for_a_bad_one(client):
    h = client.get("/start?d=2026-11-03&r=2026-11-06&a=3&k=9").text
    assert tags(h, "d")[0]["value"] == "2026-11-03" and selected(h, "a") == "3" and selected(h, "n") == "1" and selected(h, "k1") == "9"
    h = client.get("/start?d=2026-11-03&r=2026-11-02&a=3").text
    assert tags(h, "d")[0]["value"] == "2026-10-16" and selected(h, "a") == "2"


# ---- where the journey leads to /start ------------------------------------------------------------------------------

def test_sign_in_without_a_next_lands_on_start(client):
    page = client.get("/signin").text
    assert 'name="next" value="/start"' in page or 'value="/start" name="next"' in page
    r = client.post("/signin", data={"email": "ari.rivera@example.com"}, follow_redirects=False)
    assert r.headers["location"] == "/start"
    assert client.get("/signin", follow_redirects=False).headers["location"] == "/start"  # already signed in


def test_sign_in_with_a_specific_next_still_goes_there(client):
    assert client.post("/signin", data={"email": "ari.rivera@example.com", "next": "/plan?f=f2"}, follow_redirects=False).headers["location"] == "/plan?f=f2"
    assert sign_in(client, next="/").headers["location"] == "/"


def test_header_and_landing_doors_lead_to_start(client):
    for path in ["/community", "/start"]:  # the landing's header is only the brand and Sign in (F-060): its door is the form below
        h = client.get(path).text
        assert re.search(r'<nav[^>]*>.*?href="/start"[^>]*>Plan a trip', h, re.S), path
    land = client.get("/").text
    assert 'action="/start"' in land


def test_start_is_open_to_signed_out_visitors(client):
    assert client.get("/start").status_code == 200


# ---- returning travelers ---------------------------------------------------------------------------------------------

def test_no_continue_card_for_a_new_traveler(client):
    sign_in(client)
    assert "Continue" not in client.get("/start").text
    client.get("/plan")  # a bare visit is not picks
    assert "Continue" not in client.get("/start").text


def test_continue_picks_card_goes_back_to_the_picks_above_the_form(client):
    sign_in(client)
    client.get("/plan?f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=2&k=4,7")
    h = client.get("/start").text
    assert "Continue LA with the kids" in h
    link = re.search(r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*st-continue', h) or re.search(r'<a[^>]*class="[^"]*st-continue[^"]*"[^>]*href="([^"]*)"', h)
    assert htmllib.unescape(link.group(1)) == "/plan?f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=2&k=4,7"
    assert h.index("Continue LA") < h.index('id="st-form"')
    assert "Oct 16 – 19" in h


def test_continue_booked_card_opens_the_calendar_and_wins_over_picks(client):
    sign_in(client)
    client.get("/plan?f=f2&h=h3&c=c1")
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-19", "a": "2", "k": "4,7"})
    h = client.get("/start").text
    assert "Continue LA with the kids" in h and 'href="/calendar"' in h and "booked" in h
    assert h.index("Continue LA") < h.index('id="st-form"')


def test_the_continue_card_is_per_traveler_and_not_for_the_signed_out(client):
    sign_in(client, "ari")
    client.get("/plan?f=f2")
    client.post("/logout")
    assert "Continue" not in client.get("/start").text
    sign_in(client, "sam")
    assert "Continue" not in client.get("/start").text


def test_remembered_picks_live_in_the_family_database_not_the_cookie(client):
    sign_in(client)
    client.get("/plan?f=f2&h=h3&c=c1&rooms=cy1&add=bf&d=2026-10-16&r=2026-10-19&a=3&k=4,7")
    assert "plan" not in session_data(client) and "f=f2&h=h3&c=c1" in ses.remembered_plan(person())


def test_a_wrong_kid_age_marks_that_kid_not_the_first(client):
    for bad in ("", "99"):
        h = submit(client, k1="4", k2=bad).text
        assert tags(h, "k2")[0].get("aria-invalid") == "true"
        assert "aria-invalid" not in tags(h, "k1")[0]["_raw"]


def test_the_destination_group_is_marked_invalid_with_its_message(client):
    h = submit(client, to="sd").text
    fs = re.search(r"<fieldset[^>]*st-where[^>]*>", h).group(0)
    assert 'aria-invalid="true"' in fs and 'aria-describedby="st-err-to"' in fs
    assert "aria-invalid" not in re.search(r"<fieldset[^>]*st-where[^>]*>", client.get("/start").text).group(0)


def test_past_departures_are_refused_friendlily(client):
    r = submit(client, d="2026-09-01", r="2026-09-05")
    assert r.status_code == 422 and "today or later" in r.text


def test_remembering_picks_ignores_an_absurdly_long_query():
    s = person()
    ses.remember_plan(s, "f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=3&k=4,7")
    ses.remember_plan(s, "x=" + "y" * ses.MAX_PLAN_QUERY)
    assert ses.remembered_plan(s) == "f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=3&k=4,7"


def test_the_sample_dates_are_accepted_even_after_they_pass(client, monkeypatch):
    from datetime import date
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 11, 1))
    assert submit(client).status_code == 303
    assert submit(client, d="2026-10-17", r="2026-10-20").status_code == 422


def test_a_stale_pay_link_cannot_book_the_past(client, monkeypatch):
    from datetime import date
    sign_in(client)
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 11, 1))
    r = client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-17", "r": "2026-10-20", "a": "2"}, follow_redirects=False)
    assert r.headers["location"].startswith("/start?go=1")
    assert stored_booking() is None
    assert "today or later" in client.get(r.headers["location"]).text
