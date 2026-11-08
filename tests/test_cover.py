"""F-206, cover v4 (D-400 on, over v3's D-380 to D-392): the signed-out landing is v3's sales story filmed as a camera over the app: "Take a trip.
Leave a trail." and one button, then the three promises (book with everything in view; a head start, then it comes with you; leave a trail), each
a stage painted with the app's real screens and, where the feature is not built yet, a drawn card that says it is made up; then the line again over
a beach, the doors and the footer.

What a stranger reads and in what order, where its buttons go, the screenshots behind each part, the booking stage's beats, spotlights, numbers
and partners, the disclosure, what a search engine or a shared link sees, and that a signed-in person keeps the landing they had. The film itself
(the pinned stages, the camera, the moments, touch scroll, the stills) is tested in a real browser: tests_browser/test_cover.py."""
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
LEDE = "Everything you need to decide, a head start on the plan, and the people who’ve been there."
# the story, scene by scene: (its eyebrow or None, its one headline)
STORY = (
    (None, "Take a trip. Leave a trail."),
    ("1 · Book with everything in view", "See the whole trip before you pay for any of it."),
    ("2 · A head start, then it comes with you", "Don’t start from a blank page."),
    (None, "Then the plan comes with you."),
    (None, "Things a search won’t tell you."),
    ("3 · Leave a trail", "Home again? Leave a trail."),
    ("For travel writers", "You already wrote the post."),
)
BEATS = ("A cheaper flight, a pricier cabin? See both at once and decide.",
         "The weather for your dates and the drive from the airport, right where you book.",
         "Book on the sites you trust. Your bookings stay yours.")
FEATURES = {"cockpit": "Every day on one line.", "day": "Each day, to the hour.", "ask": "Change it by asking.", "family": "Everyone on the same page."}
# scene -> its screenshots, in order (the opening and the tools that come with you draw a laptop and a phone: each shows its own layout)
SHOTS = {0: ["cockpit", "cockpit"], 1: ["book"], 2: ["trail"], 3: ["cockpit", "day", "ask", "family"] * 2, 6: ["creators"]}
SHARED = r'<a [^>]*href="/community"[^>]*>See trips people shared'
DISCLOSURE = "This trip is an example: the families, trips and tips in this story are made up. The places are real."


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace(" .", ".").replace(" ,", ",").replace(" ?", "?")


def _cover(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _close(html):
    return re.search(r'<div[^>]*class="cv-close".*?</footer>', html, re.S).group(0)


def _tag(html, cls, tag="div"):
    return re.search(rf'<{tag}\b[^>]*class="{cls}"[^>]*>', html).group(0)


def _links(html):
    return re.findall(r'<a [^>]*href="([^"]+)"', html)


def _scenes(html):
    return re.findall(r'(<section[^>]*data-scene="\d+".*?</section>)(?=\s*<section[^>]*data-scene|\s*</main>)', html, re.S)


def test_the_story_opens_on_the_line_and_runs_through_the_three_promises(client):
    html = _cover(client)
    assert 'class="cv-root' in re.search(r"<html[^>]*>", html).group(0)
    scenes = _scenes(html)
    assert len(scenes) == len(STORY)
    for k, ((act, headline), scene) in enumerate(zip(STORY, scenes)):
        heading = re.search(r"<h([12])[^>]*>(.*?)</h\1>", scene, re.S)
        assert _text(heading.group(2)).strip() == headline, k
        assert len(re.findall(r"<h[12]\b", scene)) == 1, k                   # one headline a scene
        eyebrow = re.search(r'<p class="cv-eyebrow">.*?</p>', scene, re.S)
        assert (_text(eyebrow.group(0)).strip() if eyebrow else None) == act, k
    assert re.search(r"<h1[^>]*>", scenes[0]) and len(re.findall(r"<h1\b", html)) == 1
    assert LEDE in _text(scenes[0])
    assert _text(re.search(r"<h2[^>]*>.*?</h2>", _close(html), re.S).group(0)).strip() == TAGLINE      # and it closes on the line again


def test_the_opening_has_one_door_plan_a_trip(client):
    opening = _scenes(_cover(client))[0]
    assert re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', opening, re.S) and [h for h in _links(opening)] == ["/start"]
    assert "Plan a trip" in _text(opening)
    assert "cv-tabs" not in opening and "Fourteen tabs" not in opening and "homework" not in _text(opening)    # the fourteen tabs are gone (D-381)


def test_the_booking_scene_is_three_beats_and_a_pullback_over_one_screenshot(client):
    """One screen; the camera keys (flight beside stay, weather, drive) and the spotlights sit on the crop; the numbers that pop are the screen's own
    (43°F highs, the 83 min drive: "1 h 23 min"); the partners' chips are the sites the booking buttons and links name."""
    scene = _scenes(_cover(client))[1]
    beats = re.findall(r'<p data-beat="(\w+)" class="cv-beat[^"]*">(.*?)</p>', scene, re.S)
    assert [b for b, _ in beats] == ["0", "1", "all", "2"]
    assert [_text(t).strip() for b, t in beats if b != "all"] == list(BEATS) and _text(beats[2][1]).strip() == "Everything in one view."
    assert len(re.findall(r'<picture\b', scene)) == 1                     # one screen; the camera moves over it
    spots = re.findall(r'<span data-spot="(\w+)" class="cv-spot" style="left:([\d.]+)%;top:([\d.]+)%;width:([\d.]+)%;height:([\d.]+)%"', scene)
    rings = re.findall(r'<span class="cv-ring" style="left:([\d.]+)%;top:([\d.]+)%;width:([\d.]+)%;height:([\d.]+)%"', scene)
    assert [k for k, *_ in spots] == ["fs", "wx", "drive"] and len(rings) == 4         # the four booking buttons glow
    for x, y, w, h in [b for _, *b in spots] + rings:
        assert 0 <= float(x) and float(x) + float(w) <= 100.01 and 0 <= float(y) and float(y) + float(h) <= 100.01
    lens = re.search(r'<div[^>]*class="cv-lens"[^>]*>', scene).group(0)
    for k in ("fs", "fs-phone", "wx", "drive"):
        z = [float(v) for v in re.search(rf'data-cam-{k}="([^"]+)"', lens).group(1).split(",")]
        assert len(z) == 4 and z[0] + z[2] <= 1.001 and z[1] + z[3] <= 1.001, k
    nums = re.findall(r'<span data-to="(\d+)" class="cv-count">', scene)
    assert nums == ["43", "83"] and "Highs 43°F" in cover.ALT["book"].replace("typical weather", "Highs 43°F") and "1 h 23 min" in cover.ALT["book"]
    chips = [_text(c).strip() for c in re.findall(r'<li data-from="[^"]+" class="cv-chip[^"]*">(.*?)</li>', scene, re.S)]
    assert chips == ["Aviasales", "Expedia", "Airbnb", "Vrbo", "Expedia", "GetYourGuide"]


def test_every_screenshot_is_real_on_disk_for_its_layout_and_mode(client):
    scenes = _scenes(_cover(client))
    for k, names in SHOTS.items():
        assert re.findall(r'<picture data-shot="([a-z]+)"', scenes[k]) == names, k
    for k in set(range(len(scenes))) - set(SHOTS):
        assert "<picture" not in scenes[k], k                              # the drawn cards carry no screenshot
    for pic in re.findall(r'<picture data-shot="[a-z]+".*?</picture>', _cover(client), re.S):
        name = re.search(r'data-shot="([a-z]+)"', pic).group(1)
        files = set(re.findall(r'(/assets/cover/shots/[^" ,]+\.webp)', pic))
        fixed = re.search(r'data-layout="(\w+)"', pic)                     # a device's screen shows its own layout whatever the window
        layouts = ("wide",) if name == "book" else (fixed.group(1),) if fixed else ("phone", "wide")
        for layout in layouts:
            for mode in ("light", "dark"):
                for src in cover.shot_srcs(name, layout, mode):
                    assert src in files, src
                    assert (ROOT / src.lstrip("/")).is_file(), src
        assert not fixed or all(f"-{fixed.group(1)}-" in f for f in files), files
        for attr in ("data-light-phone", "data-dark-phone", "data-light-wide", "data-dark-wide"):      # what cover.js swaps in when the site's own switch differs
            assert re.search(rf'{attr}="/assets/cover/shots/{name}-', pic), (name, attr)
        img = re.search(r"<img [^>]*>", pic).group(0)
        assert re.search(r'width="\d+"', img) and re.search(r'height="\d+"', img)                                # no jump when it loads
        assert 'loading="lazy"' in img or ('fetchpriority="high"' in img and name == "cockpit"), name           # only the opening's phone loads at once
        assert re.search(r'alt="[^"]{40,}"', img) or 'aria-hidden="true"' in img, name                       # a screenshot says what it shows (the twin is hidden)
        if name != "book" and not fixed:
            sources = re.findall(r"<source [^>]*>", pic)
            assert any("prefers-color-scheme: dark" in t and cover.PHONE_Q in t and "-phone-dark-" in t for t in sources)
            assert any(f'media="{cover.PHONE_Q}"' in t and "-phone-light-" in t for t in sources)


def test_the_screenshots_stay_light():
    """One visitor downloads one layout in one mode: on a phone the booking crop and six phone screenshots; on a laptop the crop, the laptop's
    screens (at 1440 on a sharp screen), the phone beside it and the close's beach."""
    shots = ROOT / "assets/cover/shots"
    phone_set = ("cockpit", "trail", "day", "ask", "family", "creators")
    wide_set = ("cockpit", "trail", "day", "ask", "family", "creators")
    beach = (ROOT / cover.CLOSE_PHOTO[0].lstrip("/")).stat().st_size
    for mode in ("light", "dark"):
        book = (shots / f"book-wide-{mode}-1600.webp").stat().st_size
        phone = book + sum((shots / f"{n}-phone-{mode}-600.webp").stat().st_size for n in phone_set) + beach
        assert phone <= 650_000, (mode, phone)
        for w, cap in ((960, 700_000), (1440, 1_000_000)):
            wide = phone + sum((shots / f"{n}-wide-{mode}-{w}.webp").stat().st_size for n in wide_set) - (shots / f"trail-phone-{mode}-600.webp").stat().st_size - (shots / f"creators-phone-{mode}-600.webp").stat().st_size
            assert wide <= cap, (w, mode, wide)


def test_the_screenshots_show_only_the_made_up_family():
    """scripts/cover_shots.py renames every traveler of the founder's Tahoe trip to the story's made-up family and signs in with a made-up address;
    the booking shot's airport drive is the router's real answer, kept in the script, so no service is asked."""
    from scripts import cover_shots
    names = re.findall(r"- name: (.+)", tahoe.TEMPLATE)
    renamed = {a.removeprefix("- name: "): b.removeprefix("- name: ") for a, b in cover_shots.TEMPLATE_NAMES}
    assert sorted(renamed) == sorted(names) and set(renamed.values()) == {"Lena", "Sam", "Noa", "Theo"}
    assert cover_shots.EMAIL.endswith("@example.com")
    assert cover_shots.DRIVE == ("RNO", "South Lake Tahoe, California", 83) and cover_shots.CROP == {"book": "#pw"}


def test_the_made_up_parts_are_drawn_in_the_apps_look_and_say_so(client):
    """The trips others took and the local tips are not built yet (D-381, D-382): they are drawn, never a link, and the story says the families,
    trips and tips are made up where they first appear (D-383), before any made-up family or tip shows."""
    html = _cover(client)
    scenes = _scenes(html)
    head = scenes[2]
    assert "Trips others took to Lake Tahoe" in _text(head) and len(re.findall(r'<span class="cv-fb-a">', head)) == 3
    assert DISCLOSURE in _text(head)
    assert _text(html).index(DISCLOSURE) < _text(html).index("Tips for your Tahoe trip")
    assert all(n not in _text(s) for s in scenes[:2] for n in ("Okafor", "Lena", "Priya", "Garcí"))     # no made-up family before the head start
    tips = _text(scenes[4])
    for tip in ("Echo Summit", "Emerald Bay Rd closes in heavy snow", "Stagecoach lot fills by 8:30", "sledding at Spooner, free"):
        assert tip in tips, tip
    for s in (scenes[2], scenes[4], scenes[5], scenes[6]):
        for fig in re.findall(r"<figure.*?</figure>", s, re.S):
            assert "<a " not in fig and "<button" not in fig                    # a drawing: nothing in it can be pressed
            assert re.search(r'aria-label="An illustration: [^"]*made-up', fig)


def test_the_tools_that_come_with_you_each_have_a_headline_and_a_screen(client):
    scene = _scenes(_cover(client))[3]
    arts = re.findall(r'<article data-feat="([a-z]+)" class="cv-feat">\s*<h3>(.*?)</h3>', scene, re.S)
    assert [(n, _text(h).strip()) for n, h in arts] == list(FEATURES.items())
    for name in FEATURES:                                                  # each on the laptop's screen and the phone's
        assert len(re.findall(rf'<div data-layer="{name}" class="cv-layer">', scene)) == 2, name
    assert cover.ASK_SAYS in _text(scene)                                  # the request Ask types, whole without the film
    for who, line in cover.CHAT:
        assert line in _text(scene)


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_the_doors_go_to_pages_that_exist(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    html = _cover(client)
    close = _close(html)
    assert re.search(r'<a [^>]*href="/start"[^>]*>Plan a trip', close)
    assert bool(re.search(SHARED, close)) == (mode == "1")                   # nobody has published here: off the showcase there are no shared trips to see
    assert re.search(r'<a [^>]*href="/for-creators"[^>]*>Bring your post', _scenes(html)[6])
    for href in _links(close) + ["/for-creators"]:
        if not href.startswith("http"):
            assert client.get(href).status_code == 200, href


def test_the_live_site_opens_the_door_to_shared_trips_once_a_real_one_is_published(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert not re.search(SHARED, _close(_cover(client)))
    live_trip()
    assert re.search(SHARED, _close(_cover(client)))
    assert client.get("/community").status_code == 200


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_every_link_on_the_cover_lands_on_a_real_page(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    html = _cover(client)
    for href in sorted(set(_links(html))):
        if href.startswith(("#", "http", "mailto:")):
            continue
        assert client.get(href).status_code == 200, href


def test_the_plan_it_for_me_card_closes_the_story_only_when_offered(client, monkeypatch):
    from gitaway import planforme
    monkeypatch.setattr(planforme, "offered", lambda: True)
    assert 'id="plan-for-me"' in _close(_cover(client))
    monkeypatch.setattr(planforme, "offered", lambda: False)
    html = _cover(client)
    assert 'id="plan-for-me"' not in html and "/assets/css/planforme.css" not in html


def test_a_signed_in_visitor_keeps_the_landing_they_had(client):
    sign_in(client)
    html = client.get("/").text
    assert "cv-root" not in html and "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html
    assert "Fork a" in html and "getaway." in html and "/assets/css/landing.css" in html


def test_a_search_result_and_a_shared_link_show_the_line(client):
    html = _cover(client)
    assert re.search(r"<title>GitAway · Take a trip\. Leave a trail\.</title>", html)
    meta = dict(re.findall(r'<meta (?:name|property)="([^"]+)" content="([^"]*)"', html))
    assert meta["description"] == LEDE.replace("’", "’")
    assert meta["og:title"] == "GitAway · Take a trip. Leave a trail." and meta["og:description"] == meta["description"]
    assert meta["og:type"] == "website" and meta["og:url"].endswith("/")
    assert meta["og:image"].startswith("http") and meta["og:image"].endswith(cover.OG_IMAGE)
    assert (ROOT / cover.OG_IMAGE.lstrip("/")).is_file()
    assert "noindex" not in html


def test_the_words_are_real_text_and_the_story_is_skippable_to(client):
    html = _cover(client)
    assert 'href="#main"' in html and 'id="main"' in html                 # skip to the story
    assert "data-world" not in html and "cv-anchors" not in html          # no world, no world's labels (D-380)
    assert 'aria-live="polite"' in _tag(html, "cv-beats")                 # a screen reader hears the beat change
    assert re.search(r'<div aria-hidden="true" class="cv-rail">', html)    # the progress rail is a drawing, not a control


def test_only_the_cover_loads_the_cover(client):
    for path in ("/start", "/signin", "/for-creators", "/privacy", "/community"):
        html = client.get(path).text
        assert "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html and "cv-root" not in html, path


def test_the_first_paint_already_knows_day_or_night(client):
    """A tiny inline script picks day or night (and calm under reduced motion) before anything is drawn, so the page never flashes the wrong one."""
    html = _cover(client)
    boot = re.search(r"<script>(.*?)</script>", html, re.S)
    assert boot and "cv-dark" in boot.group(1) and "prefers-color-scheme" in boot.group(1) and "prefers-reduced-motion" in boot.group(1)
    assert len(boot.group(1).encode()) < 2048
    assert html.index(boot.group(0)) < html.index('<main')


def test_the_map_data_in_the_screens_is_credited(client):
    """The screenshots show OpenStreetMap data (the cockpit's paper map, the airport drive) and AWS Terrain Tiles relief: the footer credits both,
    linking OpenStreetMap's copyright page as its attribution guidelines ask; and says the story is made up."""
    footer = re.search(r"<footer.*?</footer>", _cover(client), re.S).group(0)
    assert "© OpenStreetMap contributors" in _text(footer) and "USGS 3DEP" in _text(footer)
    assert re.search(r'<a [^>]*href="https://www\.openstreetmap\.org/copyright"[^>]*>OpenStreetMap contributors</a>', footer)
    assert "the families, trips, tips and thanks in this story are made up" in _text(footer)


def test_the_decisions_record_the_covers_exceptions():
    """The cover shows made-up families, trips and tips in production (an illustration, never presented as real activity), shows OpenStreetMap
    data, and since v3 loads no 3D world."""
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    assert re.search(r"^- D-\d+ · F-206.*showcase\.on\(\).*illustration", decisions, re.M)
    assert re.search(r"^- D-\d+ · F-206.*ODbL.*openstreetmap\.org/copyright", decisions, re.M)
    assert re.search(r"^- D-383 · .*D-270.*tips", decisions, re.M)
    assert re.search(r"^- D-380 · .*three\.js", decisions, re.M)
    assert re.search(r"^- D-40\d · .*calm desktop", decisions, re.M)      # the cover's laptop zooms: an exception to the calm laptop, for this page only


def test_the_phone_query_is_the_stylesheets(client):
    """cover.js reads the phone query from the page (data-phone) and every <picture> is built from it; cover.css must use the very same one."""
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert cover.PHONE_Q in [q.strip() for q in re.findall(r"@media ([^{]+)\{", css)]
    assert f'data-phone="{cover.PHONE_Q}"' in _cover(client)


def test_the_cover_uses_the_sites_own_icons(client):
    html = _cover(client)
    for name in ("arrow-right", "fork", "heart", "snow"):
        assert icons.PATHS[name] in html, name


def test_the_browser_bar_takes_the_openings_sky_by_day_and_night_by_night(client):
    metas = re.findall(r'<meta name="theme-color"[^>]*>', _cover(client))
    assert len(metas) == 2, metas
    assert any('content="#E6EEF9"' in m and 'media="(prefers-color-scheme: light)"' in m for m in metas)
    assert any('content="#070B14"' in m and 'media="(prefers-color-scheme: dark)"' in m for m in metas)
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert "--t-hero: #E6EEF9" in css and "--t-hero: #070B14" in css      # the same colours as the opening's tint


def test_only_off_production_does_the_page_turn_on_the_review_switch(client, monkeypatch):
    """?scene=N&p=0.5 holds a stage at a point for the review tools; cover.js honours ?p only when <main> says data-debug="1"."""
    assert 'data-debug="1"' in re.search(r"<main\b[^>]*>", _cover(client)).group(0)
    monkeypatch.setattr(auth, "production", lambda: True)
    assert "data-debug" not in re.search(r"<main\b[^>]*>", _cover(client)).group(0)
