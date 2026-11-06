"""F-196 item 5: a fork lands something. A stop with no clock time gets a morning, afternoon or evening slot in order; a family with no trip gets one when it applies a fork (the place and the
length of the creator's trip); a fork for another place than the open trip's says so before it is applied."""

import re
from html import unescape

import pytest

from gitaway import catalog, community, familydb, session as ses, tripcal as cal
from gitaway.itineraries import Day, Itinerary, Stop
from tests.test_calendar import book
from tests.test_signin import person, sign_in, stored_calendar, tid


def start_times(*stops, booked=()):
    """The (key, start) of every plan a one-day fork of `stops` (time strings, "" for none) makes."""
    day = Day(1, "DAY 1", "A day", "", [Stop(t, f"Stop {i}", booked=i in booked) for i, t in enumerate(stops)])
    trip = Itinerary("x", "X", "X:", "x", "Somewhere", "lede", [day])
    return [(p.key, cal.fmt_time(p.start)) for p in cal.fork_plans(trip)]


# ---- slots for stops with no time ------------------------------------------------------------------------------------------------------

def test_one_untimed_stop_lands_in_the_morning():
    assert start_times("") == [("d1s0", "9:00 AM")]


def test_two_untimed_stops_land_in_the_morning_and_the_afternoon():
    assert start_times("", "") == [("d1s0", "9:00 AM"), ("d1s1", "1:00 PM")]


def test_three_untimed_stops_land_in_the_morning_the_afternoon_and_the_evening_in_order():
    assert start_times("", "", "") == [("d1s0", "9:00 AM"), ("d1s1", "1:00 PM"), ("d1s2", "6:00 PM")]


def test_more_stops_share_a_slot_one_after_the_other():
    assert start_times("", "", "", "") == [("d1s0", "9:00 AM"), ("d1s1", "11:00 AM"), ("d1s2", "1:00 PM"), ("d1s3", "6:00 PM")]


def test_a_stop_with_a_clock_time_keeps_it_and_only_the_untimed_ones_take_slots():
    assert start_times("10:30 AM", "", "", "5:00 PM") == [("d1s0", "10:30 AM"), ("d1s1", "9:00 AM"), ("d1s2", "1:00 PM"), ("d1s3", "5:00 PM")]


def test_a_time_that_is_not_a_clock_time_counts_as_no_time():
    assert start_times("Morning", "12:30") == [("d1s0", "9:00 AM"), ("d1s1", "1:00 PM")]


def test_an_authors_own_booking_is_still_left_out():
    assert start_times("", "", booked=(0,)) == [("d1s1", "9:00 AM")]


def test_a_crowded_day_never_runs_past_the_end_of_the_calendar():
    plans = cal.fork_plans(Itinerary("x", "X", "X:", "x", "S", "l", [Day(1, "DAY 1", "A", "", [Stop("", f"Stop {i}") for i in range(12)])]))
    assert len(plans) == 12 and all(p.end <= cal.GRID_END for p in plans)


def test_each_day_is_slotted_on_its_own():
    t = Itinerary("x", "X", "X:", "x", "S", "l", [Day(1, "DAY 1", "A", "", [Stop("", "a"), Stop("", "b")]), Day(2, "DAY 2", "B", "", [Stop("", "c")])])
    assert [(p.key, p.day, cal.fmt_time(p.start)) for p in cal.fork_plans(t)] == [("d1s0", 0, "9:00 AM"), ("d1s1", 0, "1:00 PM"), ("d2s0", 1, "9:00 AM")]


# ---- a published creator trip to fork -----------------------------------------------------------------------------------------------------

def publish_trip(slug="honolulu-kids-a1b2c3", place="Honolulu, Hawaii", plan_to="hi", days=3, stops=("Surfjack Hotel", "Pearl Harbor tour", "Hanauma Bay"), who="maya@example.com"):
    s = person(who)
    creator = community.claim_creator(s["user_id"], "Maya Chen")
    ds = [Day(n, f"DAY {n}", f"Day {n}", "", [Stop("", t) for t in stops], collapsed=False) for n in range(1, days + 1)]
    trip = Itinerary(slug=slug, title="Honolulu with kids", headline="Honolulu with kids:", accent="Maya's trip", place=place, lede="From the post.", days=ds, author="Maya Chen", real=True,
                     handle=creator["handle"], plan_to=plan_to, plan_days=days)
    community.publish(s, trip, kind="scrapbook", meta={"handle": creator["handle"], "name": "Maya Chen", "place": plan_to})
    return slug


def fork_it(client, slug):
    return client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False)


def rows(html):
    """[(plan title, when)] of the preview's rows."""
    return [(unescape(a), unescape(b)) for a, b in re.findall(r'<span class="fk-ptitle">([^<]*)</span><span class="fk-when">([^<]*)</span>', html)]


def test_a_forks_preview_gives_untimed_stops_their_slots(client):
    slug = publish_trip(days=1)
    book(client)
    fork_it(client, slug)
    html = client.get(f"/forks?open={slug}").text
    assert rows(html) == [("Surfjack Hotel", "Fri 16 · 9:00 AM – 11:00 AM"), ("Pearl Harbor tour", "Fri 16 · 1:00 PM – 3:00 PM"), ("Hanauma Bay", "Fri 16 · 6:00 PM – 8:00 PM")]


def test_applying_it_puts_them_on_the_calendar_at_those_times(client):
    slug = publish_trip(days=2)
    book(client)
    fork_it(client, slug)
    r = client.post("/forks/apply", data={"slug": slug, "pick": ["d1s0", "d1s1", "d1s2", "d2s0"]}, follow_redirects=False)
    assert r.status_code == 303
    got = [(a["d"], cal.fmt_time(a["s"]), a["t"]) for a in stored_calendar()["a"]]
    assert got == [(0, "9:00 AM", "Surfjack Hotel"), (0, "1:00 PM", "Pearl Harbor tour"), (0, "6:00 PM", "Hanauma Bay"), (1, "9:00 AM", "Surfjack Hotel")]


# ---- no trip yet ----------------------------------------------------------------------------------------------------------------------------

def trips_of(client):
    s = person("ari")
    with ses.family(s) as fam:
        return [(t["title"], t["depart"], t["return_on"]) for t in familydb.trips(fam.db)]


def test_a_family_with_no_trip_sees_what_applying_will_do(client):
    slug = publish_trip(days=3)
    sign_in(client)
    fork_it(client, slug)
    html = client.get(f"/forks?open={slug}").text
    assert len(rows(html)) == 9
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    assert "Applying this starts your trip" in text and "3 days in Honolulu, Hawaii" in text and "Your calendar fills in once you have a trip" not in text
    assert re.search(r'id="fk-apply"[^>]*>Start my trip with 9 plans<', html) and "Book a trip and you can drop" not in html


def test_applying_a_fork_with_no_trip_makes_one_with_the_creators_place_and_length_and_adds_the_plans(client):
    slug = publish_trip(days=3)
    sign_in(client)
    fork_it(client, slug)
    r = client.post("/forks/apply", data={"slug": slug, "pick": [f"d{d}s{i}" for d in (1, 2, 3) for i in (0, 1, 2)]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/forks?applied=") and f"src={slug}" in r.headers["location"]
    [(title, depart, back)] = trips_of(client)
    assert title == "Trip to Honolulu, Hawaii" and (cal.date.fromisoformat(back) - cal.date.fromisoformat(depart)).days + 1 == 3
    assert (cal.date.fromisoformat(depart) - cal.date.today()).days == 30
    t = cal.trip_of(ses.booking(person("ari")))
    assert t.destination_name == "Honolulu, Hawaii" and len(cal.days(t)) == 3
    assert len(stored_calendar()["a"]) == 9
    html = client.get(r.headers["location"]).text
    assert "Added 9 plans from Maya Chen" in html and "Undo" in html


def test_applying_again_does_not_make_a_second_trip(client):
    slug = publish_trip(days=1)
    sign_in(client)
    fork_it(client, slug)
    for _ in range(2):
        client.post("/forks/apply", data={"slug": slug, "pick": ["d1s0", "d1s1", "d1s2"]}, follow_redirects=False)
    assert len(trips_of(client)) == 1 and len(stored_calendar()["a"]) == 3


def test_a_family_that_already_has_a_trip_never_gets_another(client):
    slug = publish_trip(place="Los Angeles, California", plan_to="la", days=1)
    book(client)
    fork_it(client, slug)
    client.post("/forks/apply", data={"slug": slug, "pick": ["d1s0"]}, follow_redirects=False)
    assert len(trips_of(client)) == 1


def test_a_long_creator_trip_is_capped_at_the_most_days_a_trip_can_have(client):
    slug = publish_trip(days=14)
    sign_in(client)
    fork_it(client, slug)
    client.post("/forks/apply", data={"slug": slug, "pick": ["d1s0"]}, follow_redirects=False)
    [(_, depart, back)] = trips_of(client)
    assert (cal.date.fromisoformat(back) - cal.date.fromisoformat(depart)).days + 1 == 14


def test_no_trip_and_nothing_picked_makes_no_trip(client):
    slug = publish_trip(days=1)
    sign_in(client)
    fork_it(client, slug)
    r = client.post("/forks/apply", data={"slug": slug}, follow_redirects=False)
    assert r.status_code == 303 and trips_of(client) == []


# ---- another place ------------------------------------------------------------------------------------------------------------------------------

def warning(html):
    m = re.search(r'<div[^>]*id="fk-place"[^>]*>(.*?)</div>', html, re.S)
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1)))).strip() if m else None


def test_a_fork_for_another_place_says_so_and_offers_to_apply_anyway(client):
    slug = publish_trip(place="Honolulu, Hawaii", plan_to="hi", days=1)
    book(client)      # a trip to Los Angeles
    fork_it(client, slug)
    html = client.get(f"/forks?open={slug}").text
    assert warning(html) == "This trip is for Honolulu, Hawaii, but your trip is to Los Angeles. Its plans would land on days in the wrong place."
    assert re.search(r'id="fk-apply"[^>]*>Apply 3 plans anyway<', html) and 'role="alert"' in re.search(r'<div[^>]*id="fk-place"[^>]*>', html).group(0)


def test_a_fork_for_the_same_place_has_no_warning(client):
    slug = publish_trip(place="Los Angeles, California", plan_to="la", days=1)
    book(client)
    fork_it(client, slug)
    html = client.get(f"/forks?open={slug}").text
    assert warning(html) is None and re.search(r'id="fk-apply"[^>]*>Apply 3 plans<', html)


def test_a_place_the_catalog_does_not_know_is_compared_by_its_name(client):
    slug = publish_trip(slug="yosemite-a1b2c3", place="Yosemite National Park", plan_to="", days=1)
    book(client)
    fork_it(client, slug)
    assert warning(client.get(f"/forks?open={slug}").text) == "This trip is for Yosemite National Park, but your trip is to Los Angeles. Its plans would land on days in the wrong place."


@pytest.mark.parametrize("fork_place,mine", [("Los Angeles, California", "Los Angeles"), ("Anaheim, California", "Los Angeles"), ("Disneyland Resort, Anaheim", "Los Angeles"), ("Honolulu, Hawaii", "Honolulu"),
                                              ("Orlando, Florida", "Orlando")])
def test_the_same_place_by_any_name_is_not_a_mismatch(fork_place, mine):
    from gitaway import forks
    trip = Itinerary("x", "X", "X:", "x", fork_place, "l", [], plan_to="")
    assert forks.other_place(trip, mine, ()) == ""


@pytest.mark.parametrize("fork_place,mine,airports", [("Honolulu, Hawaii", "Los Angeles", ("LAX",)), ("New York City", "San Diego", ()), ("Yosemite National Park", "Los Angeles", ())])
def test_another_place_is_named_by_the_fork(fork_place, mine, airports):
    from gitaway import forks
    trip = Itinerary("x", "X", "X:", "x", fork_place, "l", [], plan_to="")
    assert forks.other_place(trip, mine, airports) == fork_place
