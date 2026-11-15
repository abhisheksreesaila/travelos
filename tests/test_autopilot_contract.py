"""Autopilot contract (GOAL.md M1-M4, M6). Written before the work; never edited to pass. Test names start with the milestone."""
import re
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_signin import sign_in

PLACES = {"la": "Los Angeles", "sd": "San Diego", "hi": "Honolulu", "nyc": "New York"}
TRIP = "d=2027-03-05&r=2027-03-09&a=2"


def plan(client, to):
    return client.get(f"/plan?to={to}&{TRIP}")


def go_links(html):
    return re.findall(r'href="(/go/[^"]+)"', html.replace("&amp;", "&"))


# M1 four places --------------------------------------------------------------

@pytest.mark.parametrize("to", PLACES)
def test_m1_each_place_has_its_own_plan(client, to):
    r = plan(client, to)
    assert r.status_code == 200
    assert PLACES[to] in r.text


def test_m1_search_offers_all_four_places(client):
    for to, name in PLACES.items():      # F-231: an old Where to? link for each sample city opens the matrix for it
        assert name in client.get(f"/start?to={to}").text, to


def test_m1_catalog_is_deterministic(client):
    assert plan(client, "hi").text.count("$") == plan(client, "hi").text.count("$")
    a = re.findall(r"\$[\d,]+", plan(client, "nyc").text)
    b = re.findall(r"\$[\d,]+", plan(client, "nyc").text)
    assert a == b


# M2 partner seam -------------------------------------------------------------

def test_m2_unknown_offer_is_404(client):
    assert client.get(f"/go/nope-not-real?to=la&{TRIP}", follow_redirects=False).status_code == 404


# M3 the loop closes ----------------------------------------------------------

def _complete_sandbox(client, to="hi"):
    link = go_links(plan(client, to).text)[0]
    loc = client.get(link, follow_redirects=False).headers["location"]
    page = client.get(loc).text
    action = re.search(r'<form[^>]*action="([^"]+)"', page).group(1)
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    return client.post(action, data=fields, follow_redirects=True)


def test_m3_partners_needs_sign_in(client):
    r = client.get("/partners", follow_redirects=False)
    assert r.status_code in (302, 303, 401, 403)


# M4 creators -----------------------------------------------------------------

def test_m4_creators_lists_four_creators(client):
    html = client.get("/creators").text
    handles = set(re.findall(r'href="/creators/([a-z0-9_-]+)"', html)) - {"draft", "finish", "done"}
    assert len(handles) >= 4


def test_m4_unknown_creator_404(client):
    assert client.get("/creators/nobody-here-xyz").status_code == 404


# M6 production stays honest ----------------------------------------------------
