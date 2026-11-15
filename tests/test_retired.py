"""The old app is gone (F-254): every address of a page the v2 journey replaced redirects into the journey, and nothing links to one of them.

Where each one goes is gitaway/pages/retired.py (RETIRED): the trip's pages to /trip/plan, the ways in to /plan/ask, forks and the old share to /guides.
"""

import re
from pathlib import Path

import pytest

from gitaway.pages import retired
from tests.test_calendar import book
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
CASES = [(path, target) for target, group in retired.RETIRED.items() for path in group]


def concrete(path):
    return re.sub(r"\{[a-z_]+\}", "x", path)


@pytest.mark.parametrize("path,target", CASES)
def test_a_retired_address_redirects_a_family_into_the_journey(client, path, target):
    book(client)
    r = (client.post if path in retired.POST_ONLY else client.get)(concrete(path), follow_redirects=False)
    assert r.status_code == (301 if path in retired.PERMANENT else 303), path
    assert r.headers["location"] == target, path


@pytest.mark.parametrize("path,target", CASES)
def test_a_retired_address_sends_a_stranger_to_sign_in_or_the_journey(client, path, target):
    r = (client.post if path in retired.POST_ONLY else client.get)(concrete(path), follow_redirects=False)
    assert r.status_code == (301 if path in retired.PERMANENT and target != retired.TRIP else 303), path
    assert r.headers["location"] == ("/signin?next=%2Ftrip%2Fplan" if target == retired.TRIP else target), path


def test_a_family_without_a_trip_is_sent_to_the_way_in_not_an_empty_calendar(client):
    sign_in(client)
    for path in ("/trip", "/trip/cockpit", "/trip/canvas", "/calendar"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/plan/ask", path


def test_the_old_calendar_keeps_a_day_it_was_asked_for(client):
    book(client)
    assert client.get("/calendar?day=2", follow_redirects=False).headers["location"] == "/trip/plan?day=2"
    assert client.get("/trip?day=banana", follow_redirects=False).headers["location"] == "/trip/plan"


def test_an_old_form_post_lands_on_the_plan_and_writes_nothing(client):
    book(client)
    for path in ("/trip/canvas/move", "/trip/plans", "/pay", "/forks/apply", "/rides"):
        r = client.post(path, data={"title": "Nope"}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] in ("/trip/plan", "/plan/ask", "/guides"), path


def test_the_guides_hub_still_takes_the_old_community_addresses(client):
    for path in ("/community", "/discover", "/for-creators"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 301 and r.headers["location"].startswith("/guides"), path


def test_the_kept_routes_under_a_retired_prefix_are_not_swallowed(client):
    """/trip/family/message, /trip/talk/message, /trip/help/phone, /trip/plan/* and /trip/share* live on, so the exact retired paths must not shadow them."""
    book(client)
    for path in ("/trip/plan", "/trip/plan/together", "/trip/share"):
        assert client.get(path, follow_redirects=False).status_code == 200, path
    assert client.post("/trip/family/message", data={"text": "hello"}, headers={"x-fragment": "1"}).status_code == 204
    assert client.post("/trip/talk/message", data={"act": "a1", "text": "hello"}, headers={"x-fragment": "1"}).status_code in (204, 400)


# ---- nothing links to a retired address -------------------------------------------------------------------------------

ADDRESSES = sorted({concrete(p) for p, _ in CASES if "{" not in p} | {"/community", "/discover", "/for-creators"}, key=len, reverse=True)
LINK = re.compile(r"""["'`(=](?:%s)(?=["'`?#&)\s]|$)""" % "|".join(re.escape(a) for a in ADDRESSES))
# files that name a retired address on purpose: the redirects themselves, and the guide hub's redirect of the three it took over in F-262
ALLOWED = {"gitaway/pages/retired.py", "gitaway/pages/guides.py"}
# a prefix test or a table of prefixes is not a link: `startswith("/plan")` asks where a path is, it does not send anyone there
PREFIX = re.compile(r"startswith\(|SKINS =|_under\(|OPEN_PREFIXES")


def test_no_page_script_or_email_links_to_a_retired_address():
    hits = []
    for folder, suffixes in (("gitaway", (".py", ".md", ".txt", ".html")), ("assets", (".js", ".webmanifest", ".html"))):
        for f in (ROOT / folder).rglob("*"):
            rel = str(f.relative_to(ROOT))
            if f.suffix not in suffixes or "vendor" in f.parts or rel in ALLOWED:
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if LINK.search(line) and not PREFIX.search(line):
                    hits.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not hits, "\n".join(hits)


def test_the_retired_pages_code_is_gone():
    for gone in ("gitaway/pages/cockpit.py", "gitaway/pages/tripcanvas.py", "gitaway/pages/trip.py", "gitaway/pages/plan.py", "gitaway/pages/tripgrid.py", "gitaway/pages/forks.py", "gitaway/pages/pay.py",
                 "gitaway/pages/phone_tabs.py", "gitaway/pages/publish.py", "gitaway/pages/share.py", "gitaway/cockpit.py", "gitaway/geopack.py", "gitaway/say.py",
                 "assets/css/trip_canvas.css", "assets/css/cockpit.css", "assets/css/workspace.css", "assets/js/canvas_core.js", "assets/js/cockpit.js", "assets/js/workspace.js"):
        assert not (ROOT / gone).exists(), gone


def test_every_script_and_stylesheet_a_page_loads_exists():
    """A page that links an asset that was deleted would load a 404: every /assets/js and /assets/css address named in the code is a file."""
    named = set()
    for f in (ROOT / "gitaway").rglob("*.py"):
        named |= set(re.findall(r"/assets/(?:js|css)/[A-Za-z0-9_.\-/]+\.(?:js|css)", f.read_text(encoding="utf-8")))
    assert not [n for n in sorted(named) if not (ROOT / n.lstrip("/")).exists()]
