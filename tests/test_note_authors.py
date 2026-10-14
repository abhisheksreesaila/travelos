"""F-046: a note shows who wrote it (name and avatar); "You" only on the writer's own screen."""
import re

import pytest

from tests.test_calendar import book
from tests.test_crew_calendar import named
from tests.test_members import browser, invite
from tests.test_signin import sign_in


def metas(html):
    """[(meta line, avatar name)] for each note in the Notes tab's feed, oldest first (the tab shows the newest on top)."""
    out = []
    for chunk in re.split(r'<div[^>]*class="tp-note"', html.split('id="tp-panel-notes"')[1])[1:]:
        meta = re.search(r'class="tp-notemeta">([^<]*)<', chunk)
        who = re.search(r'title="([^"]*)"', chunk)
        out.append((meta.group(1), who.group(1) if who else ""))
    return out[::-1]


@pytest.fixture
def pair(client):
    book(client)
    sam = named("sam.kim")
    invite(client, sam, "editor")
    other = browser(client)
    sign_in(other, sam)
    return client, other


def test_a_note_names_its_writer_on_every_members_screen(pair):
    ari, sam = pair
    ari.post("/trip/notes", data={"id": "n1", "text": "Ari's note"})
    sam.post("/trip/notes", data={"id": "n2", "text": "Sam's note"})
    from_ari, from_sam = metas(ari.get("/trip?tab=notes").text)[1:], metas(sam.get("/trip?tab=notes").text)[1:]
    assert from_ari == [("You · whole trip", "Ari Rivera"), ("Sam Kim · whole trip", "Sam Kim")]
    assert from_sam == [("Ari Rivera · whole trip", "Ari Rivera"), ("You · whole trip", "Sam Kim")]


def test_the_first_note_is_from_whoever_booked_the_trip(pair):
    ari, sam = pair
    first_ari, first_sam = metas(ari.get("/trip?tab=notes").text)[0], metas(sam.get("/trip?tab=notes").text)[0]
    assert first_ari == ("You · whole trip", "Ari Rivera")
    assert first_sam == ("Ari Rivera · whole trip", "Ari Rivera")


def test_a_removed_members_note_reads_former_member(pair):
    from gitaway import members
    from tests.test_signin import tid
    ari, sam = pair
    sam.post("/trip/notes", data={"id": "n1", "text": "Sam was here"})
    from tests.test_members import tenant
    assert members.remove(tenant(ari), tid("ari"), tid(next(m["email"] for m in members.members(tenant(ari)) if m["email"] != "ari.rivera@example.com"))) is None
    assert ("Former member · whole trip", "Former member") in metas(ari.get("/trip?tab=notes").text)


def test_an_author_name_is_escaped_in_the_feed():
    from gitaway import session as ses
    from gitaway.pages import dayshared, trip as page
    from gitaway.tripcal import Note
    from fasthtml.common import to_xml
    evil = ses.Friend("<script>alert(1)</script>", "XS", "sun")
    me = ses.Traveler("me", "Me", "ME", "", "sky")
    name, author = dayshared.note_writer(Note("n1", "hi", None, "", "u2"), me, {}, {"u2": evil})
    html = to_xml(page._slip(author, f"{name} · whole trip", "hi", 1, "n1"))
    assert "<script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt; · whole trip" in html
