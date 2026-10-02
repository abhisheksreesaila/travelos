"""F-055 review round 1: tampered posts, save problems, the nothing-booked link, awkward characters, and the page without scripts."""

import re
from html import unescape

from gitaway import familydb, importer, tripbuild as tb
from tests.test_signin import person, sign_in
from tests.test_trip_build import (CAR, DATES, FLIGHTS, HOTEL, NOTES, PATH, WHERE, WHO, Walk, draft_of, leg, whole_trip)


def test_a_tampered_step_or_nav_never_crashes(client):
    sign_in(client)
    w = whole_trip(Walk(client))
    for nav in ("add", "remove-0", "remove-99", "back", "next", "bogus"):
        for step in ("8", "9", "0", "-3", "x"):
            r = client.post(PATH, data={"draft": draft_of(w.html), "step": step, "nav": nav})
            assert r.status_code in (200, 422), (step, nav, r.status_code)
    r = client.post(PATH, data={"draft": draft_of(w.html), "step": "8", "nav": "add"})
    assert "Check your trip" in unescape(re.sub(r"<[^>]+>", " ", r.text))


def test_save_problems_are_a_page_message_not_a_field_error(client, monkeypatch):
    sign_in(client)
    w = whole_trip(Walk(client))
    monkeypatch.setattr(familydb, "MAX_TRIPS", 0)
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html)})
    assert r.status_code == 409 and "trips already" in r.text
    assert 'role="alert"' in r.text and 'id="tb-notice"' in r.text
    assert 'aria-invalid="true"' not in r.text
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html), "token": "nope"})
    assert r.status_code == 409 and "out of date" in r.text and 'aria-invalid="true"' not in r.text


def test_the_nothing_booked_error_links_to_a_real_field(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES), w.post(3, **WHO), w.post(4, flying="no"), w.post(5, stay="no")
    w.post(6, rent="no")
    assert w.status == 422
    target = re.search(r'<a href="#(tb-[^"]+)">You said no', w.html).group(1)
    assert f'id="{target}"' in w.html


NASTY = "it's \"quoted\" <b>&amp; </script><script>alert(1)</script>\nsecond line"


def test_awkward_characters_survive_every_step_and_the_save(client):
    sign_in(client)
    w = Walk(client)
    flights = {**FLIGHTS, **leg(0, confirmation="A'B\"C<&>")}
    hotel = {**HOTEL, "hotel0_confirmation": "H'1\"<&>", "hotel0_room": NASTY.replace("\n", " ")}
    for step, fields in enumerate(({"title": "Tom's \"trip\" <&>", "destination": "Los Angeles"}, DATES, WHO, flights, hotel, CAR, {**NOTES, "notes": NASTY}), 1):
        assert w.post(step, **fields).status_code == 200
    assert "<script>alert(1)" not in w.html and "</script><script>" not in w.html
    r = client.post(f"{PATH}/save", data={"draft": draft_of(w.html)}, follow_redirects=False)
    assert r.status_code == 303
    plan = importer.plan_of(person())
    assert plan.title == "Tom's \"trip\" <&>" and plan.notes == NASTY
    assert plan.legs[0].confirmation == "A'B\"C<&>" and plan.hotels[0].confirmation == "H'1\"<&>"
    w.post(8, nav="back")  # from the preview back to the notes step: the same text in its field
    assert "</script><script>" not in w.html
    assert unescape(re.search(r"<textarea[^>]*>(.*?)</textarea>", w.html, re.S).group(1)).strip() == NASTY


def test_the_kid_age_fields_are_in_the_page_without_scripts(client):
    sign_in(client)
    w = Walk(client)
    w.post(1, **WHERE), w.post(2, **DATES)
    assert "Step 3 of 7" in w.text
    assert all(f'name="k{i}"' in w.html for i in range(1, 9))
    assert not re.search(r'data-row="k1"[^>]*hidden|hidden[^>]*data-row="k1"', w.html) and 'id="tb-ages" hidden' not in w.html
    w.post(3, adults="1", nkids="3", k1="5", k2="6", k3="7", k4="9")  # only the first 3 count
    assert "Step 4 of 7" in w.text and tb.load(draft_of(w.html))["kids"] == ["5", "6", "7"]
