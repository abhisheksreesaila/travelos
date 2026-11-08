"""F-206: the signed-out landing is the cover story, rebuilt on the agreed story (D-354): why GitAway exists, booking with everything in view, the
planning tools, leave a trail; one made-up family's real Lake Tahoe trip, a plain headline per scene and a real screenshot of each feature, told
in real DOM text with the 3D Tahoe world showing through its windows.

What a stranger reads and in what order, where its buttons go, the screenshots behind each feature, what a search engine or a shared link sees,
and that a signed-in person keeps the landing they had. The world and the scroll are tested in a real browser: tests_browser/test_cover.py."""
import re
from pathlib import Path

import pytest

from gitaway import auth, icons
from gitaway.pages import cover
from tests.live_trips import live_trip
from tests import tahoe
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
TAGLINE = "Take a trip. Leave a trail."
# the story, scene by scene: (its eyebrow, its one headline)
STORY = (
    ("Why GitAway", "Planning a trip shouldn’t feel like homework."),
    ("One trip, start to finish", "Lena and Sam are taking the kids to Lake Tahoe."),
    ("1 · Book", "Book with everything in view."),
    ("2 · Plan together", "The whole trip on one line."),
    ("2 · Plan together", "Each day, to the hour."),
    ("2 · Plan together", "Change it by asking."),
    ("2 · Plan together", "The whole family, on the same page."),
    ("And then", "Then go. Be there."),
    ("3 · Leave a trail", "Home again, leave a trail."),
    ("3 · Leave a trail", "Someone follows it and makes it theirs."),
    ("Every trip here grew from another", "Take a trip. Leave a trail."),
)
FEATURES = {2: "plan", 3: "cockpit", 4: "day", 5: "ask", 6: "family", 8: "trail", 9: "creators"}      # scene -> its screenshot
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


def _scenes(html):
    return re.findall(r'(<section[^>]*data-scene="\d+".*?</section>)', html, re.S)


def test_the_story_runs_why_book_plan_trail_with_one_plain_headline_a_scene(client):
    html = _cover(client)
    assert 'class="cv-root' in re.search(r"<html[^>]*>", html).group(0)
    assert re.findall(r'data-scene="(\d+)"', html) == [str(i) for i in range(len(STORY))]
    scenes = _scenes(html)
    for k, ((act, headline), scene) in enumerate(zip(STORY, scenes)):
        heading = re.search(r"<h([12])[^>]*>(.*?)</h\1>", scene, re.S)
        assert _text(heading.group(2)).strip() == headline, k
        assert _text(re.search(r'<p class="cv-eyebrow">.*?</p>', scene, re.S).group(0)).strip() == act, k
        assert len(re.findall(r"<h[12]\b", scene)) == 1, k                   # one headline a scene
    assert re.search(r"<h1[^>]*>", scenes[0]) and "Fourteen tabs" in _text(scenes[0]) and "Too much information" in _text(scenes[0])
    assert STORY[-1][1] == TAGLINE and "Every trip here grew from another" in _text(scenes[-1]) and SUBHEAD in _text(scenes[-1])


def test_every_feature_is_shown_by_its_real_screenshot_for_phone_and_laptop_day_and_night(client):
    scenes = _scenes(_cover(client))
    assert [k for k, sc in enumerate(scenes) if "cv-shot" in sc] == sorted(FEATURES)
    for k, name in FEATURES.items():
        pic = re.search(r'<picture data-shot="([a-z]+)" class="cv-shot">(.*?)</picture>', scenes[k], re.S)
        assert pic and pic.group(1) == name, k
        files = re.findall(r'(/assets/cover/shots/[^" ,]+\.webp)', pic.group(2))
        for layout, widths in cover.SHOT_W.items():
            for mode in ("light", "dark"):
                for w in widths:
                    want = f"/assets/cover/shots/{name}-{layout}-{mode}-{w}.webp"
                    assert want in files, want
                    assert (ROOT / want.lstrip("/")).is_file(), want
        img = re.search(r"<img [^>]*>", pic.group(2)).group(0)
        assert 'loading="lazy"' in img and 'width="1440"' in img and 'height="900"' in img       # below the fold, and no jump when it loads
        assert re.search(r'alt="[^"]{40,}"', img), name                                          # a screenshot says what it shows
        sources = re.findall(r"<source [^>]*>", pic.group(2))
        assert any("prefers-color-scheme: dark" in t and "max-width: 720px" in t and "-phone-dark-" in t for t in sources)
        assert any(cover.PHONE_Q in t and "-phone-light-" in t for t in sources)


def test_the_screenshots_stay_light():
    """One visitor downloads one layout in one mode: seven phone screenshots, or seven laptop ones at the width their screen needs."""
    shots = ROOT / "assets/cover/shots"
    total = sum(f.stat().st_size for f in shots.glob("*.webp"))
    assert total <= 2_000_000, f"{total / 1024:.0f} KB"
    for layout, w, cap in (("phone", 600, 300_000), ("wide", 960, 250_000), ("wide", 1440, 450_000)):
        for mode in ("light", "dark"):
            one = sum((shots / f"{n}-{layout}-{mode}-{w}.webp").stat().st_size for n in FEATURES.values())
            assert one <= cap, (layout, w, mode, one)


def test_the_screenshots_show_only_the_made_up_family():
    """scripts/cover_shots.py renames every traveler of the founder's Tahoe trip to the story's made-up family and signs in with a made-up address."""
    from scripts import cover_shots
    names = re.findall(r"- name: (.+)", tahoe.TEMPLATE)
    renamed = {a.removeprefix("- name: "): b.removeprefix("- name: ") for a, b in cover_shots.TEMPLATE_NAMES}
    assert sorted(renamed) == sorted(names) and set(renamed.values()) == {"Lena", "Sam", "Noa", "Theo"}
    assert cover_shots.EMAIL.endswith("@example.com")


def test_each_window_plays_a_stretch_of_the_worlds_own_timeline(client):
    """The world (cover3d/src) keeps its seven chapters (chapter c at rest is 2c); a window names the stretch it plays (from, dwell, to), in order."""
    worlds = [tuple(map(float, w.split(","))) for w in re.findall(r'data-world="([\d.,]+)"', _cover(client))]
    assert len(worlds) == 4 and worlds[0] == (0, 0, 1) and worlds[-1][-1] == 13
    flat = [x for w in worlds for x in w]
    assert flat == sorted(flat) and all(0 <= x <= 13 for x in flat)


def test_the_world_is_decoration_and_the_words_are_real_text(client):
    html = _cover(client)
    assert 'aria-hidden="true"' in _tag(html, "cv-stage")                # the canvas, the poster and the stills say nothing to a screen reader
    assert 'aria-hidden="true"' in _tag(html, "cv-anchors")
    assert re.search(r"<canvas[^>]*>", html)
    assert 'href="#main"' in html and 'id="main"' in html                 # skip to the story
    assert 'aria-label="Scenes"' in _tag(html, "cv-rail", "nav")


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
    scenes = _scenes(_cover(client))
    assert "Lena" not in _text(scenes[0])
    first = _text(scenes[1])
    assert "Lena and Sam" in first and "made up" in first and "The places are real" in first


def test_short_screens_get_the_phone_layout_and_the_stylesheet_agrees():
    """A landscape phone (844 x 390) has no room for a card beside the world, so short screens get the phone layout: the world on top, a wide card
    below. cover.js reads the query from the page (data-phone) and the poster's <picture> is built from it; cover.css must use the very same one."""
    assert "(max-height: 520px)" in cover.PHONE_Q
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert cover.PHONE_Q in [q.strip() for q in re.findall(r"@media ([^{]+)\{", css)]


def test_the_cover_uses_the_sites_own_icons(client):
    """No hand-drawn copy of an icon gitaway/icons.py already has; the cover's own are the ones it lacks (a chevron down)."""
    assert not set(cover.ICONS.values()) & set(icons.PATHS.values())
    assert icons.PATHS["arrow-right"] in _cover(client)


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
