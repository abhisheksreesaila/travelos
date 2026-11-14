"""F-227, the cover rebuilt (one stage: docs/decisions.md D-426 on): the signed-out landing tells the brief's story (docs/briefs/unified-booking.md
"The cover tells this story"): "Compare the whole trip. Choose it together.", then three parts beside one product frame (1 Compare, 2 Plan it
together, 3 Leave a trail others can follow, "Bloggers and vloggers welcome"), then the line again, Start a trip and "Booking opens soon".

What a stranger reads and in what order, what the frame draws for each part (and that every number in it is the sample's own, the find's $50
included, and the weather NOAA's), where its doors go, the honesty about what is made up, the place art, that the script can only pick a part
(no scroll handler, no transform, no layout read) and that a signed-in person keeps the landing they had. The film itself (the pinned frame, the
Liquid swap, reduced motion, the still, phone and laptop, light and dark, frame rate) is tested in a real browser: tests_browser/test_cover.py."""
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from gitaway import icons, weather
from gitaway.pages import cover
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
LINE = "Compare the whole trip. Choose it together."
PARTS = (("01 · Compare", "Every place, every date. One total each."),
         ("02 · Plan it together", "Hearts, not group texts. One person decides."),
         ("03 · Leave a trail", "Leave a trail others can follow."))
OLD = ("Take a trip. Leave a trail.", "Book with everything in view", "blank page", "comes with you", "Things a search", "You already wrote",
       "cv-shot", "<picture", "/assets/cover/shots", "data-scene", "data-stage", "Lena", "Okafor", "Tahoe in three days")


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace(" .", ".").replace(" ,", ",").replace(" ?", "?").strip()


def _cover(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _el(html, tag, cls):
    """The whole element (tag ... /tag, nested same tags counted) that carries a class."""
    m = re.search(rf'<{tag}\b[^>]*class="[^"]*\b{cls}\b[^"]*"[^>]*>', html)
    assert m, cls
    depth, i = 1, m.end()
    for t in re.finditer(rf"<(/?){tag}\b[^>]*>", html[i:]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return html[m.start():i + t.end()]
    raise AssertionError(cls)


def _layer(html, n):
    return _el(html, "figure", f"cv-L{n}")


def _part(html, n):
    return _el(html, "div", f"cv-ch{n}")


def _links(html):
    return re.findall(r'<a [^>]*href="([^"]+)"', html)


def test_the_story_is_the_line_three_parts_and_the_line_again(client):
    html = _cover(client)
    assert 'class="cv-root' in re.search(r"<html[^>]*>", html).group(0)
    assert re.findall(r"<h1\b", html) and len(re.findall(r"<h1\b", html)) == 1
    assert _text(re.search(r"<h1[^>]*>.*?</h1>", html, re.S).group(0)) == LINE
    assert _text(_el(html, "p", "cv-lede")) == cover.LEDE
    for n, (number, headline) in enumerate(PARTS, 1):
        part = _part(html, n)
        assert _text(re.search(r'<p class="cv-n">.*?</p>', part).group(0)) == number
        assert _text(re.search(r"<h2[^>]*>.*?</h2>", part, re.S).group(0)) == headline
    assert "Bloggers and vloggers welcome" in _text(_part(html, 3))
    close = _el(html, "section", "cv-close")
    assert _text(re.search(r"<h2[^>]*>.*?</h2>", close, re.S).group(0)) == LINE
    assert _text(close).endswith("Start a trip")
    order = [_text(html).index(t) for t in (LINE, PARTS[0][1], PARTS[1][1], PARTS[2][1])] + [_text(html).rindex(LINE)]
    assert order == sorted(order)


def test_the_old_stages_left_the_cover(client):
    html = _cover(client)
    for gone in OLD:
        assert gone not in html, gone


def test_one_stage_one_frame_three_screens_beside_three_parts(client):
    html = _cover(client)
    stage = _el(html, "section", "cv-stage")
    assert len(re.findall(r'class="cv-stage"', html)) == 1 and re.search(r'<section[^>]*data-part="1"', stage)     # part 1 shows from the first paint
    frame = _el(stage, "div", "cv-frame")
    figures = re.findall(r"<figure\b[^>]*>", frame)
    assert [(re.search(r'data-n="(\d)"', f).group(1), re.search(r'class="cv-L cv-L(\d)"', f).group(1)) for f in figures] == [("1", "1"), ("2", "2"), ("3", "3")]
    parts = re.findall(r'<div\b[^>]*class="cv-ch cv-ch\d"[^>]*>', stage)
    assert [(re.search(r'data-n="(\d)"', p).group(1), re.search(r"cv-ch(\d)", p).group(1)) for p in parts] == [("1", "1"), ("2", "2"), ("3", "3")]
    assert stage.index("cv-frame") < stage.index("cv-chs")       # the frame first: on a phone it pins at the top and the parts pass under it


def test_part_one_types_the_sentence_and_lights_the_find(client):
    """The sentence, the matrix (four places, three dates, one total a square), the square that lights up and the find under it; the $50 is the
    sample's own arithmetic (LA + San Diego minus San Diego alone, the same dates)."""
    layer = _layer(_cover(client), 1)
    assert _text(_el(layer, "p", "cv-sent")) == "A family of 4, from SFO, somewhere warm, Dec 12 to 16, give or take a day."
    words = re.findall(r'<span class="cv-w( k)?" style="--w:(\d+)">', layer)
    assert [int(k) for _, k in words] == list(range(len(words))) and sum(bool(k) for k, _ in words) >= 6
    cells = re.findall(r'<span class="cv-c( lit)?" style="--i:(\d+)">(\$[\d,]+)', layer)
    assert len(cells) == 12 and [int(i) for _, i, _ in cells] == list(range(12))
    assert [c for lit, _, c in cells if lit] == ["$2,190"]
    totals = {rid: t for rid, _, _, t in cover.ROWS}
    assert totals["lasd"][1] - totals["sd"][1] == 50 and "$50 more than San Diego alone" in cover.FIND_LINE
    lit = _el(layer, "span", "lit")
    assert _text(lit) == "$2,190 +$50"
    disc = _el(layer, "div", "cv-disc")
    assert "LA + San Diego, $50 more than San Diego alone." in _text(disc) and "$2,190" in _text(_el(disc, "span", "cv-num"))
    assert [_text(h) for h in re.findall(r'<span class="cv-wide">(.*?)</span>', layer)] == ["Dec 11–15", "Dec 12–16", "Dec 13–17"]


def test_the_calendar_wears_san_diegos_real_typical_weather(client):
    """Each day is NOAA's normal for San Diego (gitaway/normals.json): never invented, and said to be typical, not a forecast. Weekdays come from
    the real 2026 calendar (docs/lessons.md 2026-11-12)."""
    layer = _layer(_cover(client), 1)
    st = weather.station(weather.CATALOG_STATIONS["sd"])
    days = re.findall(r'<span class="cv-day( in)?"><span>(\w+)</span><b>(\d+)</b>.*?<span>(\d+)°</span>', layer, re.S)
    assert [int(d) for _, _, d, _ in days] == list(range(11, 18))
    for inside, dow, d, high in days:
        day = date(2026, 12, int(d))
        assert dow == f"{day:%a}" and int(high) == weather.normal_day(st, day).high_f
        assert bool(inside) == (12 <= day.day <= 16)
    assert "not a forecast yet" in _text(_el(layer, "small", "cv-typ")) and st.name in _text(_el(layer, "small", "cv-typ"))


def test_part_two_lands_hearts_with_faces_beside_the_thread_and_the_owners_this_one(client):
    layer = _layer(_cover(client), 2)
    hearts = re.findall(r'<span class="cv-hf" style="--h:(\d)"><span class="cv-face( guest)?" title="([^"]+)"', layer)
    assert [(h, t) for h, _, t in hearts] == [("0", "Ana"), ("1", "Leela"), ("2", "Dev"), ("3", "Sam (guest)")]
    assert [g for _, g, _ in hearts] == ["", "", "", " guest"]                     # a guest is an outlined initial, not a drawn face
    no_faces = re.sub(r'<span class="cv-face[^"]*" title="[^"]*">.*?</span>', "", layer, flags=re.S)
    assert [_text(b) for b in re.findall(r'<div class="cv-bub" style="--b:\d">(.*?)</div>', no_faces, re.S)] == [
        "Leela The beach!!", "Dev Two hours of coast is fine.", "Sam We could join for the LA part."]
    assert _text(_el(layer, "span", "cv-pill")) == "This one" and "Ana decides." in _text(layer)


def test_part_three_makes_the_card_to_post_and_a_creators_matrix(client):
    html = _cover(client)
    layer = _layer(html, 3)
    assert "LA + San Diego" in _text(_el(layer, "div", "cv-ig")) and "Maya’s Tahoe trip" in _text(layer)
    assert [_text(s) for s in re.findall(r'<span(?: class="lit")?>(\$[\d,]+)</span>', _el(layer, "div", "cv-mini"))] == ["$1,640", "$1,520", "$1,710"]
    part = _part(html, 3)
    assert re.search(r'<a [^>]*href="/for-creators"[^>]*>For creators', part)


def test_the_frame_is_a_drawing_nothing_in_it_can_be_pressed(client):
    html = _cover(client)
    for n in "123":
        layer = _layer(html, n)
        assert "<a " not in layer and "<button" not in layer and "<input" not in layer, n
        assert re.search(r'aria-label="An illustration[^"]*made-up', layer), n
        assert re.search(r'<span class="cv-sample">Sample \w+</span>', layer), n       # each screen says it is a sample, on its own bar


def test_the_made_up_parts_are_said_where_the_first_of_them_shows(client):
    """D-270, D-383, D-429: the made-up families, prices and trips show in production too, as an illustration. The first part's words say so, beside
    the first screen (sample prices, no family yet); the made-up family and creator show only on the second and third screens; the footer says it
    again."""
    html = _cover(client)
    assert cover.DISCLOSURE in _text(_part(html, 1))
    first = _text(re.sub(r'aria-label="[^"]*"', "", _layer(html, 1)))
    assert not re.search(r"\b(Ana|Leela|Dev|Sam|Maya)\b", first) and "Sample prices" in first
    assert "Ana" in _text(_layer(html, 2)) and "Maya" in _text(_layer(html, 3))
    assert "made up" in _text(_el(html, "footer", "cv-foot"))


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_every_door_lands_on_a_real_page(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    html = _cover(client)
    hero = _el(html, "section", "cv-hero")
    door = "/signin?next=%2Fstart"      # D-458: Start a trip and Plan a trip are one door: sign in, then Where to? (showcase or not)
    assert _links(hero) == [door, "#compare"] and 'id="compare"' in html
    assert _links(_el(html, "section", "cv-close")) == [door]
    assert _links(_el(html, "header", "cv-top")) == ["/", "/for-creators", "/community", door, "/signin"]
    for href in sorted(set(_links(html))):
        if href.startswith(("#", "http", "mailto:")):
            continue
        assert client.get(href).status_code == 200, href


def test_the_cover_sells_one_thing_start_a_trip(client, monkeypatch):
    """D-458 (founder, 2026-11-13: "start a trip is start a trip; there's no plan it for me, no booking opens soon"): even when Plan it for me is
    offered, the cover's close is the line and Start a trip, nothing else."""
    from gitaway import planforme
    monkeypatch.setattr(planforme, "offered", lambda: True)
    html = _cover(client)
    assert 'id="plan-for-me"' not in html and "/assets/css/planforme.css" not in html
    assert "Booking opens soon" not in html and "booking opens" not in html.lower()


def test_a_signed_in_visitor_keeps_the_landing_they_had(client):
    sign_in(client)
    html = client.get("/").text
    assert "cv-root" not in html and "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html
    assert "Fork a" in html and "getaway." in html and "/assets/css/landing.css" in html


def test_only_the_cover_loads_the_cover(client):
    for path in ("/start", "/signin", "/for-creators", "/privacy", "/community"):
        html = client.get(path).text
        assert "/assets/js/cover.js" not in html and "/assets/css/cover.css" not in html and "cv-root" not in html, path


def test_a_search_result_and_a_shared_link_show_the_line(client):
    html = _cover(client)
    assert f"<title>GitAway · {LINE}</title>" in html
    meta = dict(re.findall(r'<meta (?:name|property)="([^"]+)" content="([^"]*)"', html))
    assert meta["description"] == cover.LEDE and meta["og:title"] == f"GitAway · {LINE}" and meta["og:type"] == "website"
    assert meta["og:image"].startswith("http") and meta["og:image"].endswith(cover.OG_IMAGE) and (ROOT / cover.OG_IMAGE.lstrip("/")).is_file()
    assert "noindex" not in html


def test_the_page_follows_the_sites_light_and_dark(client):
    """The cover is Direction A: tokens.css's palettes, the remembered choice applied by mode.js before the first paint, the footer's switch."""
    html = _cover(client)
    head = html.split("</head>")[0]
    assert re.search(r'<script src="/assets/js/mode\.js[^"]*"></script>', head)
    assert re.search(r'name="theme-color" content="#F2F2F5" media="\(prefers-color-scheme: light\)"', head)
    assert re.search(r'name="theme-color" content="#000000" media="\(prefers-color-scheme: dark\)"', head)
    assert "data-mode-toggle" in _el(html, "footer", "cv-foot") and re.search(r'<html[^>]*data-mode="light"', html)      # D-460: light by default, one button
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert "cv-dark" not in css and "--cv-bg" not in css                       # no palette of its own any more


def test_the_first_paint_knows_film_or_still(client):
    """A tiny inline script marks the film (html.cv-film) before anything is drawn, unless ?still; should cover.js not run, the still stays."""
    html = _cover(client)
    boot = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    assert "cv-film" in boot and "still" in boot and "GA_COVER" in boot and len(boot.encode()) < 1024
    assert html.index(boot) < html.index("<main")


def test_the_script_only_picks_a_part():
    """No jitter by construction (D-427): cover.js watches the parts with an IntersectionObserver and sets data-part and .go. It has no scroll
    handler, asks for no frames, reads no layout and writes no style; every move is cover.css's, on the --motion-* tokens."""
    js = re.sub(r"//.*", "", (ROOT / "assets/js/cover.js").read_text(encoding="utf-8"))
    assert "IntersectionObserver" in js and "dataset.part" in js and "'go'" in js
    for banned in ("scroll", "requestAnimationFrame", "getBoundingClientRect", "offsetTop", "offsetHeight", "scrollY", ".style", "transform", "animate("):
        assert banned not in js, banned


def test_the_stylesheet_pins_with_sticky_and_moves_nothing_with_the_scroll():
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "assets/css/cover.css").read_text(encoding="utf-8"), flags=re.S)
    for banned in ("animation-timeline", "view-timeline", "scroll-timeline", "timeline-scope", "will-change"):
        assert banned not in css, banned
    assert "position: sticky" in css and "position: fixed" not in css
    film = css[css.index("@media (min-height: 600px)"):css.index("@keyframes cv-in")]
    assert "prefers-reduced-motion: no-preference" in film and "cv-settle" in film        # the Liquid swap, and only with motion allowed
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"@keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css))
    hidden = [sel.strip() for sel, body in rules if re.search(r"(?<![\w-])opacity:\s*0\s*;", body)]
    assert hidden and all(".cv-film" in s for s in hidden), hidden                     # nothing is hidden outside the film


def test_the_phone_query_is_the_stylesheets(client):
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert cover.PHONE_Q in [q.strip() for q in re.findall(r"@media ([^{]+)\{", css)]
    assert f'data-phone="{cover.PHONE_Q}"' in _cover(client)


def test_every_place_drawn_has_its_art_in_both_modes(client):
    """The place art (scripts/cover_art.py, from the F-221 drawings): the sprite is inlined once, every <use> names a symbol in it, every place has a
    day palette and a night one (for the system's dark and for the person's), and nothing in the drawings is a fixed colour of their own."""
    html = _cover(client)
    sprite = (ROOT / "assets/cover/art.svg").read_text(encoding="utf-8")
    assert html.count('class="pa-sprite"') == 1
    symbols = set(re.findall(r'<symbol id="pa-([\w-]+)"', sprite))
    used = set(re.findall(r'<use href="#pa-([\w-]+)"', html))
    assert used == symbols == set(cover.ART)
    assert re.findall(r'<span data-art="([\w-]+)" data-wx="(\w+)" class="pa"', _el(html, "div", "cv-band")) == list(cover.BAND)
    assert "class=" not in sprite.split(">", 1)[1] and not re.search(r'fill="#|stroke="#|url\(#', sprite)
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    block = css[css.index("/* art:begin"):css.index("/* art:end */")]
    for place in cover.ART:
        assert block.count(f'.pa[data-art="{place}"]') == 3, place                   # day, the person's dark, the system's dark


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_art_is_built_from_the_approved_drawings():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/cover_art.py"), "--check"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_screens_have_a_seam_for_the_real_matrix():
    """Until F-222 ships the frame's screens are drawn here; each part has one drawer in SCREENS, to swap for a real screenshot then."""
    assert list(cover.SCREENS) == ["1", "2", "3"] and all(callable(f) for f in cover.SCREENS.values())
    assert "F-222" in cover.__doc__ and "SCREENS" in cover.__doc__


def test_the_cover_uses_the_sites_own_icons(client):
    html = _cover(client)
    for name in ("arrow-right", "heart", "check", "sun"):
        assert icons.PATHS[name] in html, name


def test_the_words_are_real_text_and_the_story_is_skippable_to(client):
    html = _cover(client)
    assert 'href="#main"' in html and 'id="main"' in html
    assert re.search(r'<section[^>]*aria-label="How it works"', html)


def test_the_decisions_record_the_cover(client):
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    assert re.search(r"^- D-383 · .*D-270", decisions, re.M)
    for n in (426, 427, 428, 429, 443, 444):
        assert re.search(rf"^- D-{n} · F-227", decisions, re.M), n
