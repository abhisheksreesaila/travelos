"""F-058: "Change something" on the import preview opens the guided builder filled with the whole previewed trip; "Edit as text" shows
the template text; the import button is where trips start."""

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from gitaway import tripbuild as tb, tripimport as ti
from tests.test_signin import sign_in
from tests.test_roles import crew  # noqa: F401 - a fixture: an admin, an editor and a viewer
from tests.test_trip_build import Walk, draft_of

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()
RICH = (TEMPLATE.replace("name: Kid 1", "name: Mia").replace("name: Kid 2", "name: Leo")
        .replace("  rooms: 1 ", "  rooms: 2 ").replace("  # timezone: Europe/Paris", "  timezone: America/Los_Angeles")
        .replace("    email: you@gmail.com ", "    age: 41\n    email: you@gmail.com "))


def visible(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


def plan_of(text):
    return ti.parse(text).plan


def walk_from(client, html):
    w = Walk(client)
    w.html = html
    return w


class _Fields(HTMLParser):
    """The values a browser would post from the builder's form as drawn."""

    def __init__(self):
        super().__init__()
        self.values, self._select, self._area = {}, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        name = a.get("name")
        if tag == "input" and name and a.get("type") not in ("submit", "hidden"):
            if a.get("type") in ("radio", "checkbox") and "checked" not in a:
                return
            self.values[name] = a.get("value") or ""
        elif tag == "select":
            self._select = name
        elif tag == "option" and self._select and "selected" in a:
            self.values[self._select] = a.get("value") or ""
        elif tag == "textarea":
            self._area, self.values[name] = name, ""

    def handle_endtag(self, tag):
        self._select, self._area = (None if tag == "select" else self._select), (None if tag == "textarea" else self._area)

    def handle_data(self, data):
        if self._area:
            self.values[self._area] += data


def next_step(w, step):
    """Press "Next" on the step as drawn, sending exactly the values the form shows."""
    f = _Fields()
    f.feed(w.html)
    return w.post(step, **f.values)


def test_a_plan_makes_a_draft_that_builds_the_same_plan():
    for text in (TEMPLATE, RICH):
        plan = plan_of(text)
        assert tb.build(tb.load(tb.dump(tb.from_plan(plan)))) == plan


def test_the_draft_keeps_what_the_builder_has_no_question_for():
    plan = plan_of(RICH)
    d = tb.from_plan(plan)
    assert plan.hotels[0].rooms == 2 and "Mia" in [t.name for t in plan.travelers]
    assert (d["booked_on"], d["itinerary"], d["title"]) == ("Expedia", "7123456789012", "LA with the kids")
    assert d["hotels"][0]["confirmation"] == "987654321" and d["car"]["confirmation"] == "H1234567" and d["legs"][0]["seats"] == "12A, 12B, 12C, 12D"


def test_change_something_opens_the_builder_filled_and_previews_the_same_trip(client):
    sign_in(client)
    preview = client.post("/trips/import", data={"text": RICH}).text
    form = re.search(r'<form[^>]*action="([^"]+)"[^>]*>(?:(?!</form>).)*?id="ti-edit"', preview, re.S)
    assert form and form.group(1) != "/trips/import"
    r = client.post(form.group(1), data={"text": RICH})
    assert r.status_code == 200 and 'id="tb-form"' in r.text and 'value="LA with the kids"' in r.text
    w = walk_from(client, r.text)
    for step in range(1, 8):
        next_step(w, step)
    assert w.status == 200 and 'id="ti-preview-body"' in w.html
    before, after = visible(preview), w.text
    for expected in ("Mia", "Leo", "age 41", "ABCDEF", "987654321", "H1234567", "7123456789012", "12A, 12B, 12C, 12D", "Expedia", "Hertz", "Midsize SUV", "2 rooms",
                     "Anything else: allergies, parking codes"):
        assert expected in before and expected in after, expected


def test_a_trip_with_two_hotels_keeps_both():
    two = re.sub(r"\nhotel:.*?(?=\ncar:)", """
hotels:
  - {name: First Inn, address: 1 A St, check_in: 2026-10-16 15:00, check_out: 2026-10-18 11:00, confirmation: AAA111}
  - {name: Second Inn, address: 2 B St, check_in: 2026-10-18 15:00, check_out: 2026-10-20 11:00, confirmation: BBB222}
""", TEMPLATE, flags=re.S)
    plan = plan_of(two)
    assert len(plan.hotels) == 2 and tb.build(tb.from_plan(plan)) == plan


def test_edit_as_text_shows_the_paste_page_with_the_text_in_the_box(client):
    sign_in(client)
    preview = client.post("/trips/import", data={"text": TEMPLATE}).text
    assert 'id="ti-edit-text"' in preview
    r = client.post("/trips/import/edit", data={"text": TEMPLATE})
    assert r.status_code == 200 and 'id="ti-text"' in r.text
    box = unescape(re.search(r'<textarea[^>]*id="ti-text"[^>]*>(.*?)</textarea>', r.text, re.S).group(1))
    assert "LA with the kids" in box and "ABCDEF" in box


def test_the_builders_own_preview_still_edits_the_builder(client):
    sign_in(client)
    w = walk_from(client, client.post("/trips/build/from-import", data={"text": TEMPLATE}).text)
    for step in range(1, 8):
        next_step(w, step)
    assert 'id="ti-edit"' in w.html and 'id="ti-edit-text"' not in w.html
    assert re.search(r'<form[^>]*action="/trips/build"[^>]*>(?:(?!</form>).)*?id="ti-edit"', w.html, re.S)


def test_a_text_that_does_not_read_goes_back_to_the_paste_page_with_the_problems(client):
    sign_in(client)
    r = client.post("/trips/build/from-import", data={"text": "trip: [nonsense"})
    assert r.status_code == 422 and 'id="ti-text"' in r.text and "nonsense" in r.text


def test_the_import_button_is_where_trips_start(client):
    sign_in(client)
    client.post("/trips/import/save", data={"text": TEMPLATE})
    for path in ("/start", "/calendar"):
        html = client.get(path).text
        assert re.search(r'<a [^>]*href="/trips/import"[^>]*>(?:(?!</a>).)*Import a booked trip', html, re.S), path
        assert re.search(r'<a [^>]*class="[^"]*\bbtn\b[^"]*"[^>]*href="/trips/import"|<a [^>]*href="/trips/import"[^>]*class="[^"]*\bbtn\b', html), path


def test_the_pdf_picker_is_a_styled_button_that_shows_the_file_name(client):
    sign_in(client)
    html = client.get("/trips/import").text
    assert re.search(r'<label[^>]*class="[^"]*\bbtn\b[^"]*"[^>]*>(?:(?!</label>).)*Choose the PDF', html, re.S)
    assert 'id="ti-file"' in html and 'id="ti-file-name"' in html and "No file chosen" in html


def test_kids_names_are_editable_in_the_who_step_and_blank_falls_back(client):
    sign_in(client)
    text = RICH.replace("name: Mia", "name: Child 1")
    w = walk_from(client, client.post("/trips/build/from-import", data={"text": text}).text)
    next_step(w, 1), next_step(w, 2)
    assert 'name="kn1"' in w.html and 'name="an1"' in w.html  # adults' names are editable too
    f = _Fields()
    f.feed(w.html)
    assert f.values["kn1"] == "Child 1" and f.values["kn2"] == "Leo"
    w.post(3, **{**f.values, "kn1": "Maya", "kn2": ""})
    for step in range(4, 8):
        next_step(w, step)
    assert "Maya" in w.text and "Kid 2" in w.text and "Child 1" not in w.text


# ---- review fixes: tampered ride-along fields, the time zone, big parties, viewers ------------------------------------------

def tampered_save(client, **changes):
    d = tb.from_plan(plan_of(TEMPLATE))
    for key, value in changes.items():
        if key == "hotel_rooms":
            d["hotels"][0]["rooms"] = value
        else:
            d[key] = value
    return client.post("/trips/build/save", data={"draft": tb.dump(d)}, follow_redirects=False)


def test_tampered_ride_along_fields_never_save_a_broken_trip(client):
    sign_in(client)
    for changes in ({"timezone": "Mars/Olympus"}, {"timezone": "x" * 150}, {"aages": ["999", "-5"]}, {"aages": ["5", "x"]}, {"hotel_rooms": "99"}, {"hotel_rooms": "0"}, {"hotel_rooms": "many"},
                    {"knames": ["x" * 90, ""]}):
        r = tampered_save(client, **changes)
        assert r.status_code in (303, 422), changes
        assert client.get("/trip?tab=today").status_code == 200, changes
        assert client.get("/calendar").status_code == 200, changes


def test_the_builder_rechecks_the_ride_along_fields():
    d = tb.from_plan(plan_of(TEMPLATE))
    d.update(timezone="Mars/Olympus", aages=["999", "17"])
    d["hotels"][0]["rooms"] = "99"
    plan = tb.build(d)
    assert plan.timezone == "America/Los_Angeles" and plan.hotels[0].rooms == 1
    assert [t.age for t in plan.travelers[:2]] == [None, None]
    d.update(aages=["41", "18"])
    d["hotels"][0]["rooms"] = "8"
    plan = tb.build(d)
    assert [t.age for t in plan.travelers[:2]] == [41, 18] and plan.hotels[0].rooms == 8


def test_a_time_zone_is_carried_only_when_the_text_set_it():
    assert tb.from_plan(plan_of(TEMPLATE))["timezone"] == ""
    assert tb.from_plan(plan_of(RICH))["timezone"] == ""  # the same zone the flights give anyway
    assert tb.from_plan(plan_of(RICH.replace("America/Los_Angeles", "America/Denver")))["timezone"] == "America/Denver"


def test_changing_the_flights_to_new_york_changes_the_zone(client):
    sign_in(client)
    w = walk_from(client, client.post("/trips/build/from-import", data={"text": TEMPLATE}).text)
    for step in range(1, 8):
        f = _Fields()
        f.feed(w.html)
        if step == 4:
            f.values.update({"leg0_to": "JFK", "leg1_from": "JFK"})
        w.post(step, **f.values)
    assert tb.build(tb.load(draft_of(w.html))).timezone == "America/New_York"


def test_ten_adults_open_intact():
    names = "\n".join(f"  - name: Person {i}\n    email: p{i}@example.com" for i in range(1, 11))
    text = re.sub(r"travelers:.*?(?=\nflights:)", "travelers:\n" + names + "\n", TEMPLATE, flags=re.S)
    plan = plan_of(text)
    assert plan.adults == 10 and tb.build(tb.load(tb.dump(tb.from_plan(plan)))) == plan


def test_viewers_do_not_see_the_calendar_import_button(crew):
    _, _, viewer = crew
    assert 'id="cal-import"' not in viewer.get("/calendar").text
