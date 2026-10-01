"""Forks list, apply preview and the Save heart (F-021), through the HTTP seam."""

import re

from gitaway import community, session as ses

from tests.test_calendar import add, book
from tests.test_signin import session_data, sign_in, stored_calendar, tid

TRIP = "sun-tacos-and-tide-pools"
OTHER = "la-for-two-slow-mornings"
SD = "san-diego-on-a-budget"


def fork(client, slug=TRIP):
    return client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False)


def plan_keys(html):
    """{plan key: (checked, disabled)} for the checkboxes in the preview."""
    out = {}
    for m in re.findall(r"<input[^>]*fk-check[^>]*>", html):
        out[re.search(r'data-plan="([^"]+)"', m).group(1)] = ("checked" in m.split(), "disabled" in m.split())
    return out


def apply(client, *keys, slug=TRIP):
    return client.post("/forks/apply", data={"slug": slug, "pick": list(keys)}, follow_redirects=False)


def activities(client):
    return [a for a in stored_calendar()["a"]]


def titles(client):
    return [a["t"] for a in activities(client)]


# ---- the list ------------------------------------------------------------------------------------------------------

def test_signed_out_forks_page_invites_sign_in_and_changes_nothing(client):
    r = client.get("/forks")
    assert r.status_code == 200 and "Sign in" in r.text and "fk-pick" not in r.text
    for path, data in [("/forks/apply", {"slug": TRIP, "pick": ["d1s2"]}), ("/forks/undo", {"ids": "a1"})]:
        r = client.post(path, data=data, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin")


def test_the_list_shows_any_number_of_forks_and_the_calendar_button_counts_them(client):
    book(client)
    assert "No forks yet" in client.get("/forks").text
    fork(client), fork(client, OTHER)
    html = client.get("/forks").text
    assert html.index("Sun, tacos") < html.index("LA for two") and html.count('class="fk-pick') == 2
    cal = client.get("/calendar").text
    assert re.search(r'href="/forks"[^>]*>Your forks<span[^>]*>2</span>', cal)
    assert "Your forks · 2" in client.get("/plan").text


def test_forking_twice_lists_it_once_and_a_vanished_trip_is_not_listed(client):
    book(client)
    fork(client), fork(client)
    client.post("/fork", data={"next": "/trips/nothing-here"}, follow_redirects=False)
    assert client.get("/forks").text.count('class="fk-pick') == 1
    assert re.search(r'href="/forks"[^>]*>Your forks<span[^>]*>1</span>', client.get("/calendar").text)


def test_a_hub_trip_can_be_forked_like_a_sample_itinerary(client):
    book(client)
    client.post("/share", follow_redirects=False)
    shared = community.rows(kind="shared", owner=tid("ari"))[0]["slug"]
    sign_in(client, "sam")
    assert fork(client, shared).status_code == 303
    html = client.get("/forks").text
    assert "LA with the kids" in html and f'/trips/{shared}"' in html
    assert ses.forks(session_data(client)) == [shared]


def test_the_trip_page_says_when_it_is_already_in_your_forks(client):
    sign_in(client)
    assert "Fork this trip" in client.get(f"/trips/{TRIP}").text
    fork(client)
    html = client.get(f"/trips/{TRIP}").text
    assert "In your forks" in html and 'href="/forks"' in html


# ---- the Save heart ------------------------------------------------------------------------------------------------

def test_signed_out_save_goes_through_sign_in_with_intent_save_and_lands_saved(client):
    page = client.get(f"/trips/{TRIP}").text
    assert 'action="/save"' in page and 'aria-pressed="false"' in page
    r = client.post("/save", data={"next": f"/trips/{TRIP}"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next=/trips/{TRIP}&intent=save"
    assert "save this trip" in client.get(r.headers["location"]).text
    r = sign_in(client, next=f"/trips/{TRIP}", intent="save")
    assert r.headers["location"] == f"/trips/{TRIP}"
    assert ses.saved(session_data(client)) == [TRIP]
    html = client.get(f"/trips/{TRIP}").text
    assert 'action="/unsave"' in html and 'aria-pressed="true"' in html


def test_a_plain_sign_in_on_a_trip_page_does_not_save_it(client):
    html = client.get(f"/signin?next=/trips/{TRIP}").text
    assert 'name="intent" value=""' in html
    sign_in(client, next=f"/trips/{TRIP}", intent="")
    assert ses.saved(session_data(client)) == []


def test_signed_in_save_and_unsave_are_idempotent_and_local_only(client):
    sign_in(client)
    for _ in range(2):
        r = client.post("/save", data={"next": f"/trips/{TRIP}"}, follow_redirects=False)
        assert r.headers["location"] == f"/trips/{TRIP}"
    assert ses.saved(session_data(client)) == [TRIP]
    assert client.post("/save", data={"next": "//evil.example"}, follow_redirects=False).headers["location"] == "/community"
    assert client.post("/save", data={"next": "/plan"}, follow_redirects=False).headers["location"] == "/community"
    for _ in range(2):
        assert client.post("/unsave", data={"next": f"/trips/{TRIP}"}, follow_redirects=False).status_code == 303
    assert ses.saved(session_data(client)) == []


def test_saved_trips_show_beside_forks_and_a_forked_trip_is_not_listed_twice(client):
    sign_in(client)
    for slug in (TRIP, OTHER):
        client.post("/save", data={"next": f"/trips/{slug}"})
    fork(client)
    html = client.get("/forks").text
    assert html.count('class="fk-pick') == 2  # one fork and one saved
    saved = html[html.index("Saved"):]
    assert "LA for two" in saved and "Sun, tacos" not in saved
    assert re.search(r'<form[^>]*action="/fork"', saved)  # a saved trip can be forked from the list


# ---- the preview ---------------------------------------------------------------------------------------------------

def test_preview_lists_the_plans_checked_by_default_and_marks_the_ones_that_clash(client):
    book(client)
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    keys = plan_keys(html)
    assert keys["d1s2"] == (True, False) and keys["d1s3"] == (True, False)  # pier and tacos on the arrival day
    assert "Apply 12 plans" in html or f"Apply {sum(c for c, _ in keys.values())} plans" in html
    assert 'data-key="d1s2"' in html and "fk-draft" in html
    assert "Your bookings and your crew" in html
    assert titles_on_calendar(client) == []  # previewing changes nothing


def titles_on_calendar(client):
    cal = session_data(client).get("cal", {}).get("ari", {})
    return [a["t"] for a in cal.get("a", [])]


def test_a_plan_over_a_booked_block_clashes_and_cannot_be_checked(client):
    book(client)
    fork(client, SD)
    html = client.get(f"/forks?open={SD}").text
    keys = plan_keys(html)
    assert keys["d1s0"] == (False, True) and keys["d1s1"] == (False, True)  # over the flight and over the check in
    assert "Clashes with Skylark Air 214" in html and "Clashes with Check in" in html
    assert 'data-key="d1s0"' not in html  # a plan that can never fit has no draft on the calendar


def test_a_friends_plan_makes_a_fork_plan_clash_and_it_starts_unchecked(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Mom"})
    client.post("/calendar/live")
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    keys = plan_keys(html)
    assert keys["d3s0"] == (False, False)  # Travel Town on Sunday 10:00, where Mom's steam trains already are
    assert "Clashes with Mom&#x27;s Travel Town steam trains" in html or "Clashes with Mom's Travel Town steam trains" in html
    assert 'data-key="d3s0"' in html and re.search(r'data-key="d3s0"[^>]*hidden', html)  # its draft stays off the calendar until ticked


def test_apply_adds_only_the_picked_plans_then_shows_what_was_added(client):
    book(client)
    fork(client)
    r = apply(client, "d1s2", "d2s0")
    assert r.status_code == 303 and r.headers["location"].startswith("/forks?applied=a1,a2&src=" + TRIP)
    assert titles(client) == ["Santa Monica Pier & Pacific Park", "Venice Canals stroll"]
    assert all(a["b"] == "Maya & Theo" for a in activities(client))
    html = client.get(r.headers["location"]).text
    assert "Added 2 plans from Maya &amp; Theo" in html and "Undo" in html and 'action="/forks/undo"' in html
    assert html.count("fk-pop") >= 3  # the banner and both new blocks
    assert "Santa Monica Pier" in client.get("/calendar?view=days").text


def test_unchecked_plans_are_not_added(client):
    book(client)
    fork(client)
    apply(client, "d1s3")
    assert titles(client) == ["Tacos at Mariscos La Ola"]


def test_applying_the_same_picks_again_or_refreshing_adds_nothing(client):
    book(client)
    fork(client)
    first = apply(client, "d1s2", "d1s3")
    again = apply(client, "d1s2", "d1s3")
    assert again.status_code == 303 and "applied=" not in again.headers["location"]
    for _ in range(3):
        client.get(first.headers["location"])
    assert titles(client) == ["Santa Monica Pier & Pacific Park", "Tacos at Mariscos La Ola"]
    assert "Already on your calendar" in client.get(f"/forks?open={TRIP}").text
    assert plan_keys(client.get(f"/forks?open={TRIP}").text)["d1s2"] == (False, True)


def test_a_plan_over_a_booked_block_is_ignored_even_if_posted(client):
    book(client)
    fork(client)
    fork(client, SD)
    apply(client, "d1s0", "d1s1", slug=SD)
    assert titles_on_calendar(client) == []


def test_undo_takes_the_applied_plans_back_out(client):
    book(client)
    fork(client)
    add(client, id="a1", title="Mine")
    r = apply(client, "d1s2", "d1s3")
    ids = re.search(r"applied=([a0-9,]+)", r.headers["location"]).group(1)
    assert ids == "a2,a3"
    assert client.post("/forks/undo", data={"ids": ids, "src": TRIP}, follow_redirects=False).headers["location"] == "/forks"
    assert titles(client) == ["Mine"]  # only the traveler's own is left
    client.post("/forks/undo", data={"ids": "a1;DROP"})  # junk ids do nothing
    assert titles(client) == ["Mine"]


def test_apply_is_refused_for_a_trip_not_in_the_list_and_without_a_booking(client):
    sign_in(client)
    r = apply(client, "d1s2")
    assert r.status_code == 409 and "not in your list" in r.text
    fork(client)
    r = apply(client, "d1s2")
    assert r.status_code == 409 and "Book a trip first" in r.text
    assert not stored_calendar()["a"]


def test_forks_list_without_a_booking_explains_and_does_not_preview(client):
    sign_in(client)
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    assert "Your calendar fills in once you book" in html and "fk-check" not in html and 'href="/plan"' in html


def test_a_full_calendar_refuses_the_apply_and_changes_nothing(client, monkeypatch):
    from gitaway import tripcal
    monkeypatch.setattr(tripcal, "MAX_ACTIVITIES", 5)
    book(client)
    fork(client)
    n = 0
    while add(client, id=f"a{n + 1}", day=str(n % 3 + 1), start=f"{8 + n:02d}:00", end=f"{8 + n:02d}:30", title=f"Plan {n}").status_code == 303:
        n += 1
        assert n < 80
    before = titles(client)
    r = apply(client, "d1s2")
    assert r.status_code == 409 and "a lot planned" in r.text
    assert titles(client) == before


def test_preview_only_opens_trips_in_your_list(client):
    book(client)
    html = client.get(f"/forks?open={TRIP}").text
    assert "fk-check" not in html and "No forks yet" in html


def test_the_fork_undo_button_takes_focus_after_apply(client):
    book(client)
    fork(client)
    html = client.get(apply(client, "d1s2", "d1s3").headers["location"]).text
    btn = re.search(r"<button[^>]*fk-undo[^>]*>", html).group(0)
    assert "autofocus" in btn.split() and "aria-describedby=\"fk-done-text\"" in btn and "id=\"fk-done-text\"" in html
