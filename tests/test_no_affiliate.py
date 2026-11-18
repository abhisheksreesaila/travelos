"""F-297 (D-971): GitAway has no affiliate links. Travelpayouts, Aviasales and Klook are gone; hotels and flights are booked here through LiteAPI.

The old addresses redirect (tests/test_retired.py walks every one), no page sets the `ga_via` cookie, nothing writes the old tables, and no code names an affiliate program except where it must: the
reader of a pasted Klook confirmation, the creators' own-link allow-list, the partner's own change-or-cancel page, and the old tables that are kept, never dropped.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from gitaway import blogbutton, community
from tests.live_trips import live_trip
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = re.compile(r"travelpayouts|aviasales|klook|tp-em\.com|ga_via|creator_markers|via_clicks", re.I)
# Why each may still name one: a pasted Klook confirmation is read (confirmations), a creator's own link to klook.com is allowed (stoplinks), a booking made on Klook elsewhere has Klook's own
# manage page (partners/manage), a trip file may say it was bought on Klook (tripimport), the old tables stay and the forget-a-person list clears them (community, familydb_partners, forget_person),
# and the trust page's own notes say what was removed.
MAY_NAME = {"gitaway/confirmations.py", "gitaway/stoplinks.py", "gitaway/partners/manage.py", "gitaway/tripimport.py", "gitaway/community.py", "gitaway/familydb_partners.py",
            "gitaway/pages/trust.py", "scripts/forget_person.py"}


def test_no_code_names_an_affiliate_program_except_where_it_must():
    named = set()
    for base, patterns in (("gitaway", ("*.py",)), ("assets/js", ("*.js",)), ("scripts", ("*.py",)), (".", ("main.py", "pixi.toml", "Dockerfile"))):
        for pattern in patterns:
            for path in (ROOT / base).rglob(pattern) if base != "." else [ROOT / pattern]:
                if path.is_file() and PROGRAM.search(path.read_text(encoding="utf-8")):
                    named.add(str(path.relative_to(ROOT)))
    assert named <= MAY_NAME, sorted(named - MAY_NAME)


@pytest.mark.parametrize("path", ["/go/hif1?to=hi&d=2027-03-05&r=2027-03-09&a=2", "/book/flight?site=aviasales&place=Lake%20Tahoe", "/sandbox/klook/0123456789", "/sandbox/klook/0123456789/done"])
def test_an_old_partner_address_lands_on_the_search_not_a_404(client, path):
    r = client.get(path, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/plan/ask")


def test_a_booking_click_through_the_old_sandbox_writes_nothing_and_lands_on_the_search(client):
    sign_in(client)
    r = client.post("/sandbox/klook/0123456789", data={"o": "hih1"}, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/plan/ask")


def test_no_page_sets_the_old_creator_cookie(client):
    row, handle, _owner = live_trip()
    for path, headers in ((f"/plan/ask?to=Honolulu&via={handle}", {"referer": f"http://testserver/trips/{row['slug']}"}), (f"/trips/{row['slug']}?via={handle}", {"referer": f"http://testserver/creators/{handle}"})):
        r = client.get(path, headers=headers)
        assert r.status_code == 200 and "ga_via" not in r.headers.get("set-cookie", ""), path
    assert "ga_via" not in client.cookies


def test_the_blog_button_link_is_the_plain_trip_address():
    assert blogbutton.text_link("sun-tacos-and-tide-pools", "maya-chen").endswith("/trips/sun-tacos-and-tide-pools")
    assert "via" not in blogbutton.text_link("sun-tacos-and-tide-pools", "maya-chen")


def test_the_old_tables_are_kept_and_nothing_new_is_written_to_them(client):
    row, handle, _owner = live_trip()
    client.get(f"/trips/{row['slug']}?via={handle}", headers={"referer": f"http://testserver/creators/{handle}"})
    with community.connect() as db:
        for table in ("creator_markers", "via_clicks", "klook_failures"):
            assert db.conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 0, table
