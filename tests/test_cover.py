"""F-266, cover v3, "one postcard" (docs/briefs/cover-v3.md, docs/design/cover-v3/postcard.html; D-762): the signed-out landing is one postcard that travels eight beats (Wish,
Compare, Book, Plan, Go, Share, Post, Pass it on). What a stranger reads, the wish form (D-761: a visitor searches without an account), what is said to be a sample, the doors,
the drawings' text alternative, and the rules of the script and the stylesheet (no scroll handler, no layout read, no transform written from script; the stage is CSS sticky).
The film itself (the pinned stage, the beats changing on scroll, still mode, no sideways scroll, dark) is tested in a real browser: tests_browser/test_cover.py."""
import re
from pathlib import Path

import pytest

from gitaway import layout
from gitaway.pages import cover
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent
HEADLINES = ("Every trip starts as a wish.", "Every way to go, on one card.", "Tap a square. That's the trip.", "Everyone gets a pen.", "Then you just go.",
             "Every traveller becomes a creator.", "Give it to the world.", "And someone else's trip begins.")
RING = ("Wish", "Compare", "Book", "Plan", "Go", "Share", "Post", "Pass it on")
SAMPLE_WISH = "Somewhere warm, then snow, for 4 of us, mid-December."


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace(" .", ".").replace(" ,", ",").strip()


def _tag(html, tag, cls):
    m = re.search(rf'<{tag}[^>]*class="{cls}[ "][^>]*>.*?</{tag}>', html, re.S)
    assert m, (tag, cls)
    return m.group(0)


def _opens(html, cls):
    """The opening tags of every div that has the class `cls`."""
    return re.findall(rf'<div[^>]*\bclass="(?:[^"]* )?{cls}(?: [^"]*)?"[^>]*>', html)


def _caps(html):
    return re.findall(r'<article data-k="(\d)" class="cap[^"]*"[^>]*>(.*?)</article>', html, re.S)


def test_a_stranger_gets_eight_beats_one_line_each_in_order(client):
    html = client.get("/").text
    caps = _caps(html)
    assert [k for k, _ in caps] == list("01234567")
    assert [_text(re.search(r"<h[12][^>]*>(.*?)</h[12]>", body, re.S).group(1)) for _, body in caps] == list(HEADLINES)
    assert len(re.findall(r"<h1[ >]", html)) == 1      # one h1: the wish
    assert [re.search(r'data-k="(\d)"', t).group(1) for t in _opens(html, "side")] == list("01234567")      # one drawn face per beat, drawn by the server
    ring = re.findall(r'<textPath[^>]*>([^<]+)</textPath>', html)
    assert ring == list(RING)
    assert re.findall(r'<button type="button" data-k="(\d)" aria-label="([^"]+)"', html) == [(str(k), w) for k, w in enumerate(RING)]      # the pager names every stop
    assert html.count('<i style="--k:') == 8 and 'data-beat="0"' in html      # eight markers for the observer; the stage starts on the wish
    assert len(re.findall(r'<i style="--i:\d+;--g:', html)) == 16      # the gallery: sixteen other families' postcards


def test_the_captions_are_the_stories_text_and_the_drawings_are_decoration(client):
    html = client.get("/").text
    body = _text(" ".join(b for _, b in _caps(html)))
    for said in ("Say it the way you'd tell a friend. GitAway turns one sentence into every way to go.", "Places down, days across.", "The flight, both stays and the sky, in one view.",
                 "Your people add the zoo, the tacos, the sled hill to one calendar.", "Beach on day one, snow by day four.", "Nothing invented; prices and bookings stay private.",
                 "One card for Instagram, one link back to the whole trip.", "The Riveras in Austin made it theirs in one tap, and every postcard brings the next traveller.", "Your trip comes home as a postcard: your days, your tips, your words."):
        assert said in body
    faces = _opens(html, "side")
    assert [re.search(r'data-k="(\d)"', t).group(1) for t in faces if "aria-hidden" not in t] == ["0"]      # only the first face holds something to use: the wish form
    for part in ("ring", "gal", "beats", "twin", "saved"):
        assert all('aria-hidden="true"' in t for t in _opens(html, part)), part
    assert 'aria-hidden="true"' in _opens(html, "cv-sky")[0]


def test_the_first_card_is_a_real_wish_form_that_posts_to_the_ask(client):
    html = client.get("/").text
    form = re.search(r'<form class="write cv-wish"[^>]*>.*?</form>', html, re.S).group(0)
    assert 'action="/plan/ask"' in form and 'method="post"' in form
    area = re.search(r"<textarea[^>]*>", form).group(0)
    assert 'name="q"' in area and f'placeholder="{SAMPLE_WISH}"' in area and "required" in area and 'maxlength="80"' in area
    assert 'aria-label="Where would you like to go? Say it the way you\'d tell a friend."' in area
    assert re.search(r'<button class="go" type="submit">Show me every way', form)
    assert "autofocus" not in html.lower()      # nothing takes the keyboard from a visitor
    assert _text(form).count("Somewhere warm, then snow, for 4 of us, mid-December.") == 1      # the sentence that writes itself over the box (the placeholder is an attribute)


def test_submitting_a_wish_lands_on_the_visitors_own_matrix(client):
    """The ask reads the sentence: a place it can price and a time opens the matrix; nothing is guessed (D-761, F-257). No sign-in first."""
    r = client.post("/plan/ask", data={"q": "San Diego Dec 12 to 16"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/plan/matrix?to=San+Diego&") and "&a=2" in r.headers["location"]
    assert client.get(r.headers["location"]).status_code == 200      # their own matrix opens for a visitor
    r = client.post("/plan/ask", data={"q": "San Diego"}, follow_redirects=False)      # a place with no time: the matrix opens on the default window (F-268)
    assert r.status_code == 303 and r.headers["location"].startswith("/plan/matrix?to=San+Diego&") and "&x=2" in r.headers["location"]
    r = client.post("/plan/ask", data={"q": "Nowhere Land"}, follow_redirects=False)
    assert r.status_code == 200 and "We don&#x27;t know that place yet." in r.text or "We don't know that place yet." in r.text


def test_every_sample_says_it_is_one(client):
    html = client.get("/").text
    assert html.count(cover.DISCLOSURE) == 3      # the first caption, the close and the foot
    text = _text(html)
    for said in ("Sample prices", "The Patels · 4 of us · December · sample", "Sample weather", "2,418 likes · sample", "Made theirs by 214 families sample", ">SAMPLE<"):
        assert said in text or said in html, said
    foot = _tag(html, "footer", "cv-foot")
    assert "Early preview" in foot and cover.DISCLOSURE in foot


@pytest.mark.parametrize("mode", ["1", "0"], ids=["showcase", "production"])
def test_the_doors_open_real_pages(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    html = client.get("/").text
    door = layout.plan_href()
    ctas = re.findall(r'<div class="acts cv-ctas">(.*?)</div>', html, re.S)
    assert len(ctas) == 3      # the first caption, the last caption, the close
    for block in ctas:
        assert f'<a href="{door}" class="btn">Start a trip' in block
    assert html.count('href="/guides"') >= 3      # the bar, the last caption, the close (and the foot)
    for href in (door, "/guides", "/privacy", "/terms", "/signin"):
        assert client.get(href, follow_redirects=False).status_code in (200, 303), href


def test_a_signed_in_visitor_never_gets_the_cover(client):
    sign_in(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] != "/"


def test_the_page_follows_the_sites_light_and_dark(client):
    html = client.get("/").text
    assert re.search(r'<html[^>]*data-mode="light"', html) and re.search(r'<html[^>]*class="cv-root"', html)      # the server draws light; mode.js applies the person's remembered choice
    assert "/assets/js/mode.js" in html.split("</head>")[0]
    switch = re.search(r"<button[^>]*data-mode-toggle[^>]*>", html).group(0)
    assert 'aria-pressed="false"' in switch and 'aria-label="Dark mode"' in switch
    assert "cv3-mode" not in html and "prefers-color-scheme" not in (ROOT / "assets/css/cover.css").read_text()      # the site's choice (ga-mode), not a second one of the cover's


def test_only_the_cover_loads_the_cover(client):
    assert "/assets/css/cover.css" in client.get("/").text and "/assets/js/cover.js" in client.get("/").text
    for path in ("/guides", "/signin", "/privacy"):
        page = client.get(path).text
        assert "cover.css" not in page and "cover.js" not in page, path


def test_the_first_paint_knows_film_or_still(client):
    html = client.get("/").text
    boot = (ROOT / "assets/js/cover_boot.js").read_text(encoding="utf-8").strip()
    assert boot in html and html.index(boot) < html.index('class="v2 cv3"')      # inlined ahead of the page's markup: the class is on <html> before anything is drawn
    assert "still" in boot and "prefers-reduced-motion: reduce" in boot and "cv-film" in boot and "cv-flip" in boot


def test_the_script_only_names_the_beat():
    """No scroll handler, no frame loop, no layout read and no transform from script (D-427, kept): an IntersectionObserver on eight markers, attributes, classes and one custom property."""
    js = (ROOT / "assets/js/cover.js").read_text(encoding="utf-8")
    code = "\n".join(line.split("//")[0] for line in js.splitlines())
    assert "IntersectionObserver" in code and "setProperty('--k'" in code and "dataset.beat" in code
    for banned in ("'scroll'", '"scroll"', "onscroll", "requestAnimationFrame", "getBoundingClientRect", "getComputedStyle", "offsetTop", "offsetHeight", "scrollY", "pageYOffset", "innerHeight",
                   ".style.transform", "transform", "translate", ".animate(", "scrollTo(", "wheel", "touchmove"):
        assert banned not in code, banned
    assert re.findall(r"setProperty\('([^']+)'", code) == ["--k"]


def test_the_stylesheet_pins_with_sticky_turns_nothing_with_the_scroll_and_has_no_blur():
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    assert "position: sticky" in css
    for banned in ("scroll-timeline", "animation-timeline", "view-timeline", "backdrop-filter", "blur(", "rotateY", "backface-visibility"):      # no turning card (the founder found it dizzy), nothing scroll-linked
        assert banned not in css, banned
    film = css[css.index("@media (prefers-reduced-motion: no-preference) and (min-height: 35rem)"):]
    assert "position: sticky" in film.split("/* ============ the faces")[0]      # the film, and only under motion allowed
    assert "position: sticky" not in css[:css.index("@media (prefers-reduced-motion: no-preference) and (min-height: 35rem)")]
    for word in ("mod(var(--i) - var(--k) + 16, 16)", "cos(var(--a))", "sin(var(--a))"):      # the gallery's slots and the ring's turn are CSS, from --k
        assert word in css, word
    assert "rotate: calc(-22.5deg - var(--k) * 45deg)" in css


def test_every_beats_card_has_its_size_in_both_layouts():
    css = (ROOT / "assets/css/cover.css").read_text(encoding="utf-8")
    sizes = {int(k): (int(w), int(h)) for k, w, h in re.findall(r'\.side\[data-k="(\d)"\]\) \{ --w: (\d+); --h: (\d+); \}', css)[:7]}
    assert sizes == {1: (640, 400), 2: (380, 425), 3: (660, 430), 4: (540, 350), 5: (400, 545), 6: (400, 500), 7: (520, 340)}
    assert re.search(r'\.stage\[data-beat="3"\] \.pc, \.side\[data-k="3"\]\) \{ --w: 660; --h: 430; \}', css)      # one rule sets both: the film's card and the still's


def test_the_old_story_left_the_cover(client):
    html = client.get("/").text
    for old in ("Compare the whole trip. Choose it together.", "cv-frame", "cv-hero", "cv-band", "data-part", "Leave a trail", "Plan it together", "Booking opens soon"):
        assert old not in html, old
    for gone in ("assets/cover/art.svg", "scripts/cover_art.py", "scripts/cover_fps.py", "scripts/cover_film_report.py"):
        assert not (ROOT / gone).exists(), gone


def test_the_faces_use_the_sprite_once_and_no_duplicate_ids(client):
    html = client.get("/").text
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    assert html.count('id="cv-art"') == 1 and html.count('href="#cv-art"') == 4 and html.count('href="#cv-wish"') == 2


# ---------- F-299: "Why another travel site?" (the flip) ----------
WHY_CARDS = ("The catch, up front", "Reviews, read for you", "One grid", "Book here", "Plan together", "Today")
WHY_OLD = ("$189 a night*", "★ 8.7 · 4,182 reviews", "Two tabs and a spreadsheet", "Off to a site you've never heard of", "The group chat", "Searching the inbox at the gate")


def _why(html):
    m = re.search(r'<section[^>]*id="why"[^>]*>.*?</section>', html, re.S)
    assert m
    return m.group(0)


def _why_cards(html):
    return re.findall(r'<div class="wy-card[^"]*"[^>]*>(.*?)</div></div>\s*(?=<div class="wy-card|</div>\s*<div class="wy-band)', _why(html), re.S)


def test_the_cover_asks_why_another_travel_site_after_the_story(client):
    html = client.get("/").text
    why = _why(html)
    assert html.index('id="story"') < html.index('id="why"') < html.index('id="your-turn"')
    text = _text(why)
    assert "Fair question" in text and "Why another travel site?" in text
    assert "Because you know what the others feel like. Here's what changes." in text
    assert len(re.findall(r'<h2[ >]', why)) == 1
    assert len(re.findall(r'class="wy-card[ "]', why)) == 6
    assert [_text(m) for m in re.findall(r'<span class="wy-lab"><b[^>]*>.*?</b>(.*?)</span>', why, re.S)] == list(WHY_CARDS)


def test_each_card_keeps_the_old_way_as_one_struck_line_and_the_grey_face_is_hidden_from_readers(client):
    why = _why(client.get("/").text)
    assert re.findall(r'<span class="wy-was">Elsewhere: <s>(.*?)</s></span>', why) == list(WHY_OLD)
    assert why.count('class="wy-face wy-e" aria-hidden="true"') == 6
    assert why.count('class="wy-face wy-g"') == 6 and "aria-hidden" not in re.search(r'class="wy-face wy-g"[^>]*>', why).group(0)
    assert "Watch again" in why and "<button" in why


def test_the_band_under_the_cards_sends_the_visitor_to_the_postcards(client):
    why = _why(client.get("/").text)
    band = why[why.index('class="wy-band'):]
    assert "Every traveller becomes a creator." in _text(band)
    assert "Postcards from people who went: follow their path, or take your own. Then send yours." in _text(band)
    assert re.search(r'<a [^>]*href="/guides"[^>]*>\s*Find a trip', band)


def test_flights_say_soon_until_they_are_live_and_the_wallet_pass_says_soon(client, monkeypatch):
    from gitaway import liteapi
    monkeypatch.setattr(liteapi, "flights_live", lambda: False)
    why = _text(_why(client.get("/").text))
    assert "Stays today, flights Soon" in why and "Wallet pass Soon" in why
    monkeypatch.setattr(liteapi, "flights_live", lambda: True)
    why = _text(_why(client.get("/").text))
    assert "Stays and flights" in why and "flights Soon" not in why and "Wallet pass Soon" in why


def test_the_prices_in_the_cards_say_they_are_samples(client):
    why = _text(_why(client.get("/").text))
    assert why.count("Sample") >= 3 and cover_why_note() in why


def cover_why_note():
    from gitaway.pages import coverwhy
    return coverwhy.NOTE


def test_the_flip_script_only_watches_with_an_observer():
    """F-299: the flip's trigger is one IntersectionObserver on the cards (no scroll handler, no frame loop, no layout read, no transform written from script)."""
    js = (ROOT / "assets/js/cover_why.js").read_text(encoding="utf-8")
    code = "\n".join(line.split("//")[0] for line in js.splitlines())
    assert "IntersectionObserver" in code and "threshold: .6" in code
    for banned in ("'scroll'", "onscroll", "requestAnimationFrame", "getBoundingClientRect", "getComputedStyle", "offsetTop", "offsetHeight", ".style.", "transform", ".animate("):
        assert banned not in code, banned
    css = (ROOT / "assets/css/cover_why.css").read_text(encoding="utf-8")
    for banned in ("backdrop-filter", "blur(", "backface-visibility", "rotateY", "scroll-timeline"):
        assert banned not in css, banned
    assert "cubic-bezier(.34, 1.4, .64, 1)" in (ROOT / "assets/css/v2-tokens.css").read_text(encoding="utf-8")
    assert "--cvt-flip" in css and "var(--cvt-800)" in css and "var(--cvt-110)" in css
