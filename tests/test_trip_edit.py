"""F-061: "Edit trip" opens the guided builder filled with the saved trip, and saving replaces it in place."""

import re
from html import unescape

from gitaway import rides, session as ses, tripcal as cal
from tests.test_import_edit import _Fields, walk_from
from tests.test_roles import crew  # noqa: F401 - a fixture: an admin, an editor and a viewer
from tests.test_signin import person, sign_in
from tests.test_trip_import import TEMPLATE, clock, imported, no_car, visible  # noqa: F401 - clock is a fixture


def trip_ids():
    return [t.id for t in ses.trips(person()) if t.source == "imported"]


def edit_url(trip_id):
    return f"/trips/build/edit?trip={trip_id}"


def walk_to_preview(client, trip_id, change=None):
    """Press Edit trip, then Next through all seven steps (sending exactly what each form shows); `change(step, values)` may alter a step's values."""
    w = walk_from(client, client.get(edit_url(trip_id)).text)
    for step in range(1, 8):
        f = _Fields()
        f.feed(w.html)
        if change:
            change(step, f.values)
        w.post(step, **f.values, **hidden_of(w.html, "tb-next", keep=("edit", "trip")))
    return w


def hidden_of(html, button_id, keep=None):
    """The hidden fields of the form that holds the button `button_id`, as a browser would post them."""
    form = re.search(rf'<form[^>]*>(?:(?!</form>).)*?id="{button_id}".*?</form>', html, re.S).group(0)
    found = {m.group(1): unescape(m.group(2) or m.group(3)) for m in re.finditer(r"""<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value=(?:"([^"]*)"|'([^']*)')""", form)}
    return {k: v for k, v in found.items() if keep is None or k in keep}


def test_the_details_page_has_an_edit_button_that_opens_the_builder_filled(client):
    imported(client)
    [trip_id] = trip_ids()
    details = client.get("/trip/details").text
    assert 'id="ti-edit-trip"' in details and f'href="/trips/build/edit?trip={trip_id}"' in details
    r = client.get(edit_url(trip_id))
    assert r.status_code == 200 and 'id="tb-form"' in r.text and 'value="LA with the kids"' in r.text and "EDIT TRIP" in r.text
    assert f'name="edit" value="{trip_id}"' in r.text and f'name="trip" value="{trip_id}"' in r.text
    w = walk_to_preview(client, trip_id)
    assert w.status == 200 and 'id="ti-preview-body"' in w.html
    for expected in ("Abhi", "Priya", "ABCDEF", "987654321", "H1234567", "7123456789012", "Expedia", "Hertz", "The Example Hotel Santa Monica", "AS 1234", "age 7"):
        assert expected in visible(w.html), expected


def test_the_calendar_trip_bar_and_the_phone_view_have_the_button_for_a_saved_trip_and_not_for_the_demo(client):
    sign_in(client)
    assert 'id="cal-edit-trip"' not in client.get("/calendar").text  # a sample trip has no stored plan
    imported(client)
    [trip_id] = trip_ids()
    assert 'id="cal-edit-trip"' in client.get(f"/calendar?trip={trip_id}").text
    phone = client.get(f"/trip?trip={trip_id}").text
    assert 'id="tp-edit-trip"' in phone and f'href="/trips/build/edit?trip={trip_id}"' in phone


def test_the_preview_in_edit_mode_offers_only_save_changes_and_change_something(client):
    imported(client)
    [trip_id] = trip_ids()
    html = walk_to_preview(client, trip_id).html
    assert 'id="ti-save-changes"' in html and 'id="ti-save"' not in html and 'id="ti-replace"' not in html
    assert "Save as a new trip" not in html and "Save this trip" not in html
    assert "in place" in visible(html) and "plans, notes and rides stay" in visible(html)
    assert hidden_of(html, "ti-save-changes")["replace"] == trip_id
    # "Change something" goes back to an editable builder that is still editing this trip
    r = client.post("/trips/build", data=hidden_of(html, "ti-edit"))
    assert r.status_code == 200 and 'id="tb-form"' in r.text and f'name="edit" value="{trip_id}"' in r.text


def test_saving_replaces_the_trip_in_place_and_keeps_plans_notes_and_moves_rides(client, clock):
    imported(client, no_car())
    p = person()
    [trip_id] = trip_ids()
    cal.add_activity(p, day=1, start="12:00", end="13:00", title="Tacos", id="a1")
    cal.add_note(p, "Bring sunscreen", id="n1")
    b = ses.booking(p)
    plan = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_for(b, "arrive"), cal.trip_of(b))
    est = next(e for e in rides.provider().estimates(plan) if e.key == "x")
    ride = rides.schedule_ride(p, rides.ScheduleRequest(plan, rides.validate_guest("Ari", "Rivera", "(310) 555-0123"), est.product_id, est.fare_id, rides.next_ride_id(p), rides.booking_key(b)))
    assert ride.pickup_time.strftime("%H:%M") == "10:02"

    def change(step, v):
        if step == 4:  # flights: the first leg lands later
            v["leg0_depart_time"], v["leg0_arrive_time"] = "09:45", "11:15"
        if step == 5:
            v["hotel0_name"] = "The Corrected Inn"
    w = walk_to_preview(client, trip_id, change)
    assert 'id="ti-moves"' in w.html and "1 scheduled Uber ride will move" in w.text
    before = len(ses.trips(person()))
    r = client.post("/trips/build/save", data=hidden_of(w.html, "ti-save-changes"), follow_redirects=False)
    assert r.status_code == 303
    assert len(ses.trips(person())) == before and trip_ids() == [trip_id]
    assert [a.title for a in cal.activities(person())] == ["Tacos"] and [n.text for n in cal.notes(person())] == ["Bring sunscreen"]
    moved = [x for x in rides.list_rides(person()) if not x.canceled][0]
    assert moved.id == ride.id and moved.pickup_time.strftime("%H:%M") == "11:45"
    details = visible(client.get("/trip/details").text)
    assert "The Corrected Inn" in details and "The Example Hotel Santa Monica" not in details
    assert "9:45 AM" in details or "09:45" in details


def test_viewers_see_no_button_and_cannot_open_or_save(crew):
    owner, editor, viewer = crew
    owner.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False)
    [trip_id] = [t.id for t in ses.trips(person()) if t.source == "imported"]
    for who in (owner, editor):
        assert 'id="ti-edit-trip"' in who.get(f"/trip/details?trip={trip_id}").text
        assert who.get(edit_url(trip_id)).status_code == 200
    html = viewer.get(f"/trip/details?trip={trip_id}").text
    assert 'id="ti-edit-trip"' not in html and 'id="cal-edit-trip"' not in viewer.get(f"/calendar?trip={trip_id}").text and 'id="tp-edit-trip"' not in viewer.get(f"/trip?trip={trip_id}").text
    assert viewer.get(edit_url(trip_id)).status_code == 403
    for path in ("/trips/build", "/trips/build/save"):
        assert viewer.post(path, data={"edit": trip_id, "trip": trip_id, "replace": trip_id}, follow_redirects=False).status_code == 403, path


def test_a_forged_or_stale_trip_id_is_refused_and_changes_nothing(client):
    imported(client)
    [trip_id] = trip_ids()
    w = walk_to_preview(client, trip_id)
    good = hidden_of(w.html, "ti-save-changes")
    for forged in ("deadbeef0000", "x" * 12):
        assert client.get(edit_url(forged)).status_code == 404
        assert client.post("/trips/build/save", data={**good, "edit": forged, "trip": forged, "replace": forged}, follow_redirects=False).status_code == 404
        assert client.post("/trips/build", data={**good, "edit": forged, "trip": forged, "step": "8", "nav": "next"}).status_code == 404
    # edit says one trip, replace another: refused
    assert client.post("/trips/build/save", data={**good, "replace": "deadbeef0000"}, follow_redirects=False).status_code == 404
    # a stale tab for a trip that was deleted
    assert client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303
    assert client.post("/trips/build/save", data=good, follow_redirects=False).status_code == 404
    assert client.get(edit_url(trip_id)).status_code == 404
    assert trip_ids() == []


def test_a_stale_tab_edits_only_the_trip_it_opened(client):
    imported(client)
    [first] = trip_ids()
    w = walk_to_preview(client, first)
    good = hidden_of(w.html, "ti-save-changes")
    other = TEMPLATE.replace("title: LA with the kids", "title: Second trip").replace("2026-10-16", "2026-11-16").replace("2026-10-20", "2026-11-20").replace("itinerary: 7123456789012", "itinerary: 999")
    client.post("/trips/import/save", data={"text": other}, follow_redirects=False)  # now the second trip is the open one
    [second] = [i for i in trip_ids() if i != first]
    assert client.post("/trips/build/save", data=good, follow_redirects=False).status_code == 303
    titles = {t.id: t.title for t in ses.trips(person())}
    assert titles[first] == "LA with the kids" and titles[second] == "Second trip" and len(titles) == 2


def test_tampered_fields_are_still_rechecked_on_save(client):
    imported(client)
    [trip_id] = trip_ids()
    w = walk_to_preview(client, trip_id)
    good = hidden_of(w.html, "ti-save-changes")
    r = client.post("/trips/build/save", data={**good, "draft": "{not json"}, follow_redirects=False)
    assert r.status_code == 422 and 'id="tb-form"' in r.text and f'name="edit" value="{trip_id}"' in r.text
    assert [t.title for t in ses.trips(person()) if t.id == trip_id] == ["LA with the kids"]
