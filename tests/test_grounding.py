"""F-194 (6): the model is trusted with nothing it cannot show in the post. A stop's name needs every one of its meaningful words in the post, as whole words (a word inside another
word, or one of several, is not enough); a clock time must be written in the post; a note or tip with a number or a dollar amount keeps it only if the post has the same one."""

import pytest

from gitaway import creatordraft
from tests.creator_import_support import ANSWER


def draft(post, stops=(), tips=(), notes=None):
    """validate() of an answer with one day of `stops` ((name, time, note) triples) and `tips`, against `post`."""
    answer = {**ANSWER, "place": "other", "place_name": "Somewhere", "tips": list(tips), "days": [{"stops": [{"name": n, "time": t, "note": o} for n, t, o in stops]}]}
    return creatordraft.validate(answer, post)


def names(got):
    return [s["name"] for d in got["days"] for s in d["stops"]]


# ---- names ---------------------------------------------------------------------------------------------------------------------

POST = "We spent two days at Disneyland. We rode Space Mountain, walked down Main Street, and saw the castle. Our hotel was a short walk from Disney California Adventure."


@pytest.mark.parametrize("name, kept", [
    ("Space Mountain", True), ("Main Street", True), ("Disneyland", True), ("Disney California Adventure", True),
    ("Cars Land", False),                                  # the post never says it
    ("Space Mountain Ranch", False),                       # one word of the name is in the post, the other is not
    ("Disney Springs", False),
    ("Main Street Electrical Parade", False),
    ("Mountain", True),
])
def test_every_meaningful_word_of_a_stop_name_must_be_in_the_post(name, kept):
    assert names(draft(POST, [(name, "", "")])) == ([name] if kept else ["Unnamed stop"])


def test_a_word_inside_another_word_is_not_in_the_post():
    assert names(draft("We had dinner at Pierre's bistro.", [("Pier", "", "")])) == ["Unnamed stop"]
    assert names(draft("We walked the Santa Monica Pier.", [("Santa Monica Pier", "", "")])) == ["Santa Monica Pier"]


def test_short_words_and_numbers_count_too():
    assert names(draft("We had lunch at Pier 39 and then sailed.", [("Pier 39", "", "")])) == ["Pier 39"]
    assert names(draft("We had lunch at Pier 40 and then sailed.", [("Pier 39", "", "")])) == ["Unnamed stop"]
    assert names(draft("We went to the Zoo in the morning.", [("San Diego Zoo", "", "")])) == ["Unnamed stop"]


def test_accents_and_punctuation_do_not_make_a_real_stop_unnamed():
    assert names(draft("Breakfast at Cafe du Monde, then Ka'anapali Beach.", [("Café du Monde", "", ""), ("Ka’anapali Beach", "", "")])) == ["Café du Monde", "Ka’anapali Beach"]


def test_a_name_written_as_one_word_in_the_post_is_still_the_same_place():
    assert names(draft("The best day was SeaWorld.", [("Sea World", "", "")])) == ["Sea World"]


def test_a_name_of_only_filler_words_is_not_held_against_the_post():
    assert names(draft("We had a lovely time.", [("Lunch at the beach", "", "")])) == ["Lunch at the beach"]


# ---- clock times ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("post, said, want", [
    ("Pier at 10:00 AM sharp.", "10:00 AM", "10:00 AM"), ("We got there at 9am.", "9am", "9:00 AM"), ("We got there at 9 a.m.", "9:00 AM", "9:00 AM"), ("Doors at 12:30 PM.", "12:30 PM", "12:30 PM"),
    ("The train left at 14:15.", "2:15 PM", "2:15 PM"), ("Dinner was at 6:30pm.", "6:30 PM", "6:30 PM"), ("Rope drop is 8:00.", "8am", "8:00 AM"), ("We left at 19:30 and ate.", "7:30 PM", "7:30 PM"),
    ("We spent 9 days there.", "9am", ""),                 # a 9 that is not a time
    ("We got there around lunch.", "12:30 PM", ""),        # nothing in the post says it
    ("Pier at 10:00 AM sharp.", "11:00 AM", ""),
    ("Pier at 10:30 AM sharp.", "10:00 AM", ""),
    ("We left at 9:30 and ate.", "1:30 PM", ""),
])
def test_a_clock_time_the_post_does_not_write_is_dropped(post, said, want):
    assert draft(post + " We visited the Pier.", [("Pier", said, "")])["days"][0]["stops"][0]["time"] == want


# ---- numbers in notes and tips -------------------------------------------------------------------------------------------------

POST2 = "Tickets were $25 each at the Pier and we parked for $15. Get there by 8:30, before 9, bring 2 jackets. The ride takes 10 minutes. Hotel was $1,200 for the week."


@pytest.mark.parametrize("note, kept", [
    ("Tickets were $25 each.", True), ("Tickets are $45 each.", False), ("Parking is $15.", True), ("Parking is 15 dollars.", True),
    ("Get there by 8:30.", True), ("Get there by 7:45.", False), ("Bring 2 jackets.", True), ("Bring 3 jackets.", False),
    ("It takes 10 minutes.", True), ("It takes 100 minutes.", False), ("The hotel was $1200.", True), ("The hotel was $12.", False),
    ("Bring two jackets.", True), ("Go early.", True),
])
def test_a_note_with_a_number_or_amount_the_post_lacks_is_dropped(note, kept):
    got = draft(POST2, [("Pier", "", note)])["days"][0]["stops"][0]["note"]
    assert got == (note if kept else "")


def test_a_dollar_amount_needs_dollars_in_the_post_not_just_the_same_digits():
    assert draft("The walk takes 45 minutes to the Pier.", [("Pier", "", "Tickets are $45.")])["days"][0]["stops"][0]["note"] == ""


def test_a_tip_with_a_number_the_post_lacks_is_dropped_and_the_others_stay():
    got = draft(POST2, [("Pier", "", "")], tips=["Park at the pier lot before 9.", "Rides cost $60 a head.", "Bring layers.", "It is 8:30 or never."])
    assert got["tips"] == ["Park at the pier lot before 9.", "Bring layers.", "It is 8:30 or never."]


def test_a_number_inside_a_decimal_is_not_found_by_its_whole_part():
    assert draft("It was 9.5 miles to the Pier.", [("Pier", "", "It is 9 miles.")])["days"][0]["stops"][0]["note"] == ""


# ---- the label -----------------------------------------------------------------------------------------------------------------

def test_the_page_does_not_say_the_stops_were_named_in_the_post():
    d = {**draft(POST, [("Space Mountain", "", ""), ("Main Street", "", "")]), "id": "0" * 16, "slug": "a-b2c3d4", "live": False, "name": "Maya Chen", "source": {}, "images": [], "picks": [], "copies": {}, "cover": ""}
    trip = creatordraft.build(d, lambda n: "")
    assert trip.stats == [("1 day", "from the post"), ("2 stops", "across the days")]


def test_what_the_model_invented_never_reaches_the_creators_editor(client, monkeypatch):
    """Through the paste page: a model that adds a made-up stop, time, price and tip gets them dropped or marked, and the editor shows only what the post says."""
    import re
    from html import unescape

    from gitaway import ai, safefetch
    from tests.creator_import_support import Model, Web, form_of, page
    from tests.test_signin import sign_in
    post = "https://blog.example.com/pier-day"
    body = "<html><head><title>A day at the pier</title></head><body><article><p>" + "We spent a happy day at Santa Monica Pier with the kids and rode the Ferris wheel at 10:00 AM. Tickets were $25. " * 4 + "</p></article></body></html>"
    answer = {**ANSWER, "days": [{"stops": [{"name": "Santa Monica Pier", "time": "10:00 AM", "note": "Tickets were $25."}, {"name": "Griffith Observatory", "time": "7:45 PM", "note": "Free parking after $9."}]}],
              "tips": ["Go early.", "Skip the $80 VIP pass."]}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({post: page(body)}))
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": post}, follow_redirects=False)
    did = re.search(r"/creators/import/([0-9a-f]{16})", r.headers["location"]).group(1)
    fields = form_of(unescape(client.get(f"/creators/import/{did}").text), f"/creators/import/{did}", "ci-edit")
    f = dict(fields)
    assert (f["d0s0_name"], f["d0s0_time"], f["d0s0_note"]) == ("Santa Monica Pier", "10:00 AM", "Tickets were $25.")
    assert (f["d0s1_name"], f["d0s1_time"], f["d0s1_note"]) == ("Unnamed stop", "", "")
    assert [v for k, v in fields if k == "tip" and v] == ["Go early."]
