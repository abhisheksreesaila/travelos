"""F-206: the signed-out landing is the cover story, a scroll through Lake Tahoe in December told in real DOM text over a 3D world.

What a stranger reads, where its buttons go, what a search engine or a shared link sees, and that a signed-in person keeps the landing they had.
The world itself is tested in a real browser: tests_browser/test_cover.py."""
import re
from pathlib import Path

import pytest

from gitaway import auth, icons
from gitaway.pages import cover
from tests.live_trips import live_trip
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
TAGLINE = "Take a trip. Leave a trail."
SHARED = r'<a [^>]*href="/community"[^>]*>See trips people shared'
SUBHEAD = "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _cover(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _cta_row(html):
    return re.search(r'<div class="cv-ctas">.*?</div>', html, re.S).group(0)


def _tag(html, cls, tag="div"):
    return re.search(rf'<{tag}\b[^>]*class="{cls}"[^>]*>', html).group(0)


def _links(html):
    return re.findall(r'<a [^>]*href="([^"]+)"', html)


def test_the_signed_out_landing_opens_on_the_hook_and_closes_on_the_line(client):
    html = _cover(client)
    assert 'class="cv-root' in re.search(r"<html[^>]*>", html).group(0)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1)
    assert _text(h1).strip() == "Don’t read about it. Go."
    last = re.search(r'<section[^>]*data-chapter="6".*?</section>', html, re.S).group(0)
    assert _text(re.search(r"<h2[^>]*>(.*?)</h2>", last, re.S).group(1)).strip() == TAGLINE
    assert "Every trip here grew from another" in _text(last) and SUBHEAD in _text(last)
    assert SUBHEAD in _text(html)
    chapters = re.findall(r'data-chapter="(\d)"', html)
    assert chapters == [str(i) for i in range(7)]                       # the hook, five beats of the story, the line
    for beat in ("A family shared their five days here.", "Make it yours.", "The whole trip on one screen.", "Then go.", "Someone’s next trip starts with yours."):
        assert beat in _text(html), beat


def test_the_world_is_decoration_and_the_words_are_real_text(client):
    html = _cover(client)
    assert 'aria-hidden="true"' in _tag(html, "cv-stage")                # the canvas, the poster and the stills say nothing to a screen reader
    assert 'aria-hidden="true"' in _tag(html, "cv-anchors")
    assert re.search(r"<canvas[^>]*>", html)
    assert 'href="#main"' in html and 'id="main"' in html                 # skip to the story
    assert 'aria-label="Chapters"' in _tag(html, "cv-rail", "nav")


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_the_three_calls_to_action_go_to_pages_that_exist(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    row = _cta_row(_cover(client))
    assert re.search(r'<a [^>]*href="/start"[^>]*>Start a trip</a>', row)
    assert re.search(r'<a [^>]*href="/for-creators"[^>]*>Leave a trail</a>', row)
    assert bool(re.search(SHARED, row)) == (mode == "1")                   # nobody has published here: off the showcase there are no shared trips to see
    for href in _links(row):
        assert client.get(href).status_code == 200, href


def test_the_live_site_opens_the_door_to_shared_trips_once_a_real_one_is_published(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert not re.search(SHARED, _cta_row(_cover(client)))
    live_trip()
    assert re.search(SHARED, _cta_row(_cover(client)))
    assert client.get("/community").status_code == 200


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_every_link_on_the_cover_lands_on_a_real_page(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    html = _cover(client)
    for href in sorted(set(_links(html))):
        if href.startswith(("#", "http")):
            continue
        assert client.get(href).status_code == 200, href


def test_a_signed_in_visitor_keeps_the_landing_they_had(client):
    sign_in(client)
    html = client.get("/").text
    assert "cv-root" not in html and "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html
    assert "Fork a" in html and "getaway." in html and "/assets/css/landing.css" in html


def test_a_search_result_and_a_shared_link_show_the_line(client):
    html = _cover(client)
    assert re.search(r"<title>GitAway · Take a trip\. Leave a trail\.</title>", html)
    meta = dict(re.findall(r'<meta (?:name|property)="([^"]+)" content="([^"]*)"', html))
    assert meta["description"] == SUBHEAD
    assert meta["og:title"] == "GitAway · Take a trip. Leave a trail." and meta["og:description"] == SUBHEAD
    assert meta["og:type"] == "website" and meta["og:url"].endswith("/")
    assert meta["og:image"].startswith("http") and meta["og:image"].endswith(cover.OG_IMAGE)
    assert (ROOT / cover.OG_IMAGE.lstrip("/")).is_file()
    assert "noindex" not in html


def test_the_world_is_never_in_the_page_itself(client):
    """The scene script, three.js and the terrain are fetched by cover.js only when the live world is wanted, so reduced motion, no WebGL and weak phones download none of it."""
    html = _cover(client)
    assert "/assets/js/cover.js" in html
    for heavy in ("/assets/vendor/three", "/assets/js/cover/world.js\"", "tahoe-"):
        assert not re.search(rf'<(script|link)[^>]*{re.escape(heavy)}', html), heavy
    assert re.search(r'data-world="/assets/js/cover/world\.js\?v=[0-9a-f]{10}"', html)


def test_only_the_cover_loads_the_cover(client):
    for path in ("/start", "/signin", "/for-creators", "/privacy", "/community"):
        html = client.get(path).text
        assert "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html and "cv-root" not in html, path


def test_every_poster_and_still_is_on_disk(client):
    html = _cover(client)
    posters = re.findall(r'(?:srcset|src)="(/assets/cover/stills/[^"]+\.webp)"', re.search(r'<picture class="cv-poster".*?</picture>', html, re.S).group(0))
    assert len(posters) == 4                                              # day and night, laptop and phone
    for i in range(7):
        for layout in ("wide", "phone"):
            for mode in ("light", "dark"):
                assert (ROOT / f"assets/cover/stills/a-{i}-{layout}-{mode}.webp").is_file(), (i, layout, mode)
    for p in posters:
        assert (ROOT / p.lstrip("/")).is_file(), p


def test_the_first_paint_already_knows_day_or_night(client):
    """A tiny inline script picks the day or night scene (and the calm stills under reduced motion) before anything is drawn, so the page never flashes the wrong one."""
    html = _cover(client)
    boot = re.search(r"<script>(.*?)</script>", html, re.S)
    assert boot and "cv-dark" in boot.group(1) and "prefers-color-scheme" in boot.group(1) and "prefers-reduced-motion" in boot.group(1)
    assert len(boot.group(1).encode()) < 2048
    assert html.index(boot.group(0)) < html.index(_tag(html, "cv-stage"))


def test_the_real_map_data_is_credited_where_it_shows(client):
    """The world's shorelines, roads and drives are OpenStreetMap data (ODbL): the page that shows them says so, and links to OpenStreetMap's
    copyright page as its attribution guidelines ask."""
    footer = re.search(r"<footer.*?</footer>", _cover(client), re.S).group(0)
    assert "© OpenStreetMap contributors" in _text(footer) and "USGS 3DEP" in _text(footer)
    assert re.search(r'<a [^>]*href="https://www\.openstreetmap\.org/copyright"[^>]*>OpenStreetMap contributors</a>', footer)


def test_the_decisions_record_the_covers_two_exceptions():
    """The cover shows a made-up family in production (an illustration, never presented as real activity), and bakes OpenStreetMap data (ODbL)."""
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    assert re.search(r"^- D-\d+ · F-206.*showcase\.on\(\).*illustration", decisions, re.M)
    assert re.search(r"^- D-\d+ · F-206.*ODbL.*openstreetmap\.org/copyright", decisions, re.M)


def test_the_story_says_its_family_is_made_up_where_the_family_appears(client):
    """Lena, Sam, their bookings and the thanks from Ana & Luis show in production too: the story says they are an example right where the family
    first appears, not only in the footer."""
    first = _text(re.search(r'<section[^>]*data-chapter="1".*?</section>', _cover(client), re.S).group(0))
    assert "Lena and Sam" in first and "made up" in first


def test_short_screens_get_the_phone_layout_and_the_stylesheet_agrees():
    """A landscape phone (844 x 390) has no room for a card beside the world, so short screens get the phone layout: the world on top, a wide card
    below. cover.js reads the query from the page (data-phone) and the poster's <picture> is built from it; cover.css must use the very same one."""
    assert "(max-height: 520px)" in cover.PHONE_Q
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert cover.PHONE_Q in [q.strip() for q in re.findall(r"@media ([^{]+)\{", css)]


def test_the_plans_widgets_are_a_named_group(client):
    tag = _tag(_cover(client), "cv-wds")
    assert 'role="group"' in tag and 'aria-label="The trip, planned"' in tag


def test_the_cover_uses_the_sites_own_icons(client):
    """No hand-drawn copy of an icon gitaway/icons.py already has; the cover's own are the ones it lacks (snow, a route, a chevron down)."""
    assert not set(cover.ICONS.values()) & set(icons.PATHS.values())
    html = _cover(client)
    for name in ("plane", "bed", "car", "ticket", "star", "ext", "arrow-right"):
        assert icons.PATHS[name] in html, name


def test_the_browser_bar_takes_the_covers_grey_by_day_and_black_by_night(client):
    metas = re.findall(r'<meta name="theme-color"[^>]*>', _cover(client))
    assert len(metas) == 2, metas
    assert any('content="#F2F2F5"' in m and 'media="(prefers-color-scheme: light)"' in m for m in metas)
    assert any('content="#000000"' in m and 'media="(prefers-color-scheme: dark)"' in m for m in metas)


def test_only_off_production_does_the_page_turn_on_the_tools_switches(client, monkeypatch):
    """?measure, ?capture, ?q and ?cam (the capture and measuring tools' switches) skip the weak-device check and the governor, and the world shows
    its insides on window.__cover: cover.js and the world honour them only when <main> says data-debug="1", which production never renders."""
    assert 'data-debug="1"' in re.search(r"<main\b[^>]*>", _cover(client)).group(0)
    monkeypatch.setattr(auth, "production", lambda: True)
    assert "data-debug" not in re.search(r"<main\b[^>]*>", _cover(client)).group(0)
