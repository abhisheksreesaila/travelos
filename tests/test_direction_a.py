"""F-200: Direction A's tokens in one place, for light and dark, and the rules that keep both modes honest. Read from the real files.
The browser side (every main page in both modes, contrast, targets, type) is tests_browser/test_direction_a_pages.py; the accent and the kinds are tests/test_accent.py."""
import re
from pathlib import Path

from fasthtml.common import to_xml

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
TOKENS = (CSS / "tokens.css").read_text(encoding="utf-8")


def declarations(start):
    i = TOKENS.index(start)
    return re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", TOKENS[i:TOKENS.index("}", i)])


def test_light_is_the_grey_canvas_with_white_cards_and_ink():
    light = dict(declarations("/* ---------- light (the default) ---------- */"))
    assert (light["--paper"], light["--card"], light["--ink"], light["--accent"]) == ("#F2F2F5", "#FFFFFF", "#0B0B0D", "#0B0B0D")


def test_dark_is_black_with_the_same_values_whether_the_system_or_the_person_chose_it():
    by_system = declarations(":root:not([data-mode=\"light\"]) {")
    by_choice = declarations(":root[data-mode=\"dark\"] {")
    assert by_system == by_choice, "the two dark blocks must stay the same"
    dark = dict(by_choice)
    assert (dark["--paper"], dark["--card"], dark["--ink"], dark["--accent"]) == ("#000000", "#1C1C1F", "#F5F5F7", "#F5F5F7")
    assert "@media (prefers-color-scheme: dark)" in TOKENS
    light_names = {k for k, _ in declarations("/* ---------- light (the default) ---------- */")}
    assert light_names == set(dark), f"every colour has a light and a dark value: {light_names ^ set(dark)}"


def test_the_old_names_point_at_direction_a_and_the_orange_sand_is_gone():
    for old in ("#FFF8EE", "#FF7352", "#C9431F", "#1E1A2E", "#FFC93C", "#48D1A0", "#5AB0FF", "#C3B2FF", "#FF8CC6", "#F4F9FF"):
        assert old.lower() not in TOKENS.lower(), old
    for name in ("--coral", "--sun", "--mint", "--sky", "--grape", "--bubble", "--shadow-sm", "--shadow-lg", "--brand-orange"):
        assert re.search(rf"{name}:\s*var\(--", TOKENS), f"{name} is mapped onto a Direction A token"
    omxqua = (CSS / "omxqua.css").read_text()
    assert "#c0401c" not in omxqua and "#f4f0e9" not in omxqua, "Coast's orange and sand are gone"
    assert not re.search(r"--oq-(surface|ink|accent)[\w-]*:\s*#", omxqua), "Coast's surfaces, ink and accent are Direction A tokens"


def test_the_type_scale_on_the_phone_and_on_the_desktop():
    phone = TOKENS[TOKENS.index("@media (max-width: 720px)"):]
    phone = dict(re.findall(r"(--t-[\w-]+):\s*([\d.]+)rem", phone[:phone.index("} }")]))
    desk = dict(re.findall(r"(--t-[\w-]+):\s*([\d.]+)rem", TOKENS[:TOKENS.index("@media (max-width: 720px)")]))
    px = lambda rem, root: round(float(rem) * root)
    assert {k: px(v, 16) for k, v in phone.items() if k in ("--t-body", "--t-2", "--t-fine", "--t-label")} == {"--t-body": 17, "--t-2": 16, "--t-fine": 14, "--t-label": 13}
    assert px(desk["--t-body"], 12) == 16 and px(desk["--t-label"], 12) == 12
    assert "--text-min: 16px" in TOKENS and "--label-min: 13px" in TOKENS     # on a phone: words 16px or more, an all-caps label 13
    assert "--text-min: 12px" in TOKENS and "--label-min: 12px" in TOKENS     # on a laptop: nothing under 12
    assert "font-size: var(--t-body)" in (CSS / "base.css").read_text()


def test_no_glass_or_blur_anywhere():
    for path in CSS.glob("*.css"):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        assert "backdrop-filter" not in css and "blur(" not in css, path.name


ALLOWED_WHITE = re.compile(r"figcaption|ws-room-cap|knob")


def test_white_and_old_ink_are_never_written_where_dark_mode_would_lose_them():
    """White text or a white surface written as a colour, and the old ink with alpha, do not change with the mode: text on ink is --on-ink, a white surface --card (a photo's
    caption and a switch's knob stay white). The lesson of F-200: these were the parts that went white on white in dark mode."""
    for path in CSS.glob("*.css"):
        if path.name == "tokens.css":
            continue
        for rule in re.findall(r"[^{}]+\{[^{}]*\}", re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)):
            if ALLOWED_WHITE.search(rule):
                continue
            assert not re.search(r"(?<![\w-])color:\s*(#fff\b|#ffffff\b|white\b)", rule, re.I), f"{path.name}: {rule.strip()[:90]}"
            assert not re.search(r"background(-color)?:\s*(#fff\b|#ffffff\b|white\b)", rule, re.I), f"{path.name}: {rule.strip()[:90]}"
            assert "rgba(30, 26, 46" not in rule and "rgba(30,26,46" not in rule, f"{path.name}: {rule.strip()[:90]}"


def test_every_page_loads_the_mode_script_before_paint_and_names_both_bar_colours(client):
    html = client.get("/start").text
    head = html.split("</head>")[0]
    script = re.search(r'<script src="/assets/js/mode\.js[^"]*"></script>', head)
    assert script, "mode.js without defer or async, in the head: it runs before the body is drawn"
    assert re.search(r'name="theme-color" content="#F2F2F5" media="\(prefers-color-scheme: light\)"', head)
    assert re.search(r'name="theme-color" content="#000000" media="\(prefers-color-scheme: dark\)"', head)


def test_light_by_default_and_one_button_for_dark(client):
    """D-460 (founder, 2026-11-13: "a simple button to switch between light and dark … for a joyful site it has to be light by default"): every
    page starts light whatever the system says (html[data-mode="light"], which tokens.css's system-dark block steps aside for), and the footer
    has one button, pressed when dark (mode.js keeps the choice on this device: tests_browser/test_direction_a_pages.py)."""
    html = client.get("/start").text
    assert re.search(r'<html[^>]*data-mode="light"', html)
    switch = re.search(r'<button[^>]*data-mode-toggle[^>]*>.*?</button>', html, re.S).group(0)
    assert 'aria-pressed="false"' in switch and 'aria-label="Dark mode"' in switch and "data-mode-pick" not in html


def test_the_mark_is_one_svg_with_three_coloured_nodes():
    from gitaway.layout import brand
    html = to_xml(brand())
    assert html.count("<circle") == 3 and all(f'class="mk-{n}"' in html for n in "abc") and 'class="mk-l"' in html
    base = (CSS / "base.css").read_text()
    for part, token in (("mk-l", "--mark-line"), ("mk-a", "--mark-a"), ("mk-b", "--mark-b"), ("mk-c", "--mark-c")):
        assert re.search(rf"\.ga-mark \.{part} \{{ stroke: var\({token}\); \}}", base), part


PREVIEW = re.compile(r'<details class="ga-preview">\s*<summary class="ga-preview-sum"><span class="ga-preview-pill">Early preview</span></summary>.*?</details>', re.S)


def preview_on(html):
    m = PREVIEW.search(html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(0))).strip() if m else ""


def test_the_early_preview_label_is_in_the_shell_signed_out_and_signed_in(client):
    """The brief's "What" 1: an honest "Early preview" label, small, in the shell: the site header, sign-in, the booking workspace, and once signed in the top bar
    and the phone's trip screens. It opens one short line."""
    from tests.test_calendar import book
    line = "Early preview GitAway is new. Things will change; tell us what breaks."
    for path in ("/", "/signin?next=%2Fstart", "/start", "/creators", "/for-creators", "/plan-for-me", "/plan?to=la&d=2027-03-05&r=2027-03-09&a=2"):
        assert preview_on(client.get(path).text) == line, path
    book(client)
    for path in ("/start", "/family", "/trip/canvas", "/trip/canvas?day=1", "/trip/family", "/trip/ask"):
        html = client.get(path).text
        assert preview_on(html) == line, path
    canvas = client.get("/trip/canvas").text
    assert len(PREVIEW.findall(canvas)) == 2      # the laptop's top bar and the phone's row; topbar.css and phone.css show one per width
    assert 'class="ph-preview"' in canvas


def test_tell_us_what_breaks_writes_to_the_contact_address_only_when_there_is_one(client, monkeypatch):
    monkeypatch.delenv("GITAWAY_CONTACT_EMAIL", raising=False)
    assert "mailto:" not in PREVIEW.search(client.get("/start").text).group(0)
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "hello@gitaway.example")
    label = PREVIEW.search(client.get("/start").text).group(0)
    assert '<a href="mailto:hello@gitaway.example?subject=GitAway%20early%20preview">tell us what breaks</a>' in label
