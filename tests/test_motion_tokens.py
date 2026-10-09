"""F-109: one liquid motion. The tokens live in tokens.css and assets/js/motion.js (GA.motion) is the only helper that opens, folds and settles things; every sheet, menu, popover, toast and screen
move (and the new bubbles and blocks) takes its duration and easing from those tokens and writes none of its own. Browser checks of the frames: tests_browser/test_motion.py."""
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# F-109: EVERY stylesheet and script under assets/ (nothing is skipped); tokens.css is where the durations live.
CSS = sorted(p.name for p in (ASSETS / "css").glob("*.css") if p.name != "tokens.css")
JS = sorted(p.name for p in (ASSETS / "js").glob("*.js"))
# What may keep a literal time, and why. None of these is a sheet, menu, popover, toast or screen move.
ALLOWED_FILES = {
    "landing.css": "the marketing page's hero and feature illustrations (a demo that plays on hover: staggered delays, a drawn line, a cursor); not part of the app",
}
ALLOWED_CSS = (
    "infinite",              # every looping decoration: the held block's wiggle, the recording dot, the mic pulse, presence dots, the plane and clouds on sign-in, bobbing stickers, shimmer
    "ak-ink 0.5s",           # the typed words fading in
    "ak-fresh 1.6s",         # the glow on what Apply changed: a few seconds of attention, not a move
    "cal-ring 2s",           # the ring on a live calendar item (three pulses)
    "pay-fall 1.8s",         # the confetti on the payment page
    "si-stick",              # the sign-in stickers' staggered start (a loop)
)
TIME = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b")


def lines(path):
    return (ASSETS / path).read_text(encoding="utf-8").splitlines()


def test_the_tokens_are_the_cards_spring_and_one_set():
    css = (ASSETS / "css" / "tokens.css").read_text(encoding="utf-8")
    for token, value in (("--motion-spring-dur", "520ms"), ("--motion-spring", "cubic-bezier(.3, 1.12, .4, 1)"), ("--motion-dur", "240ms"), ("--motion-out", "cubic-bezier(.4, 0, .8, .4)"),
                         ("--motion-settle-dur", "280ms"), ("--motion-quick", "160ms"), ("--motion-fade", "120ms"), ("--motion-wiggle", "420ms")):
        assert re.search(rf"{re.escape(token)}:\s*{re.escape(value)}", css), token
    canvas = (ASSETS / "css" / "trip_canvas.css").read_text(encoding="utf-8")
    assert ":root { --cz-dur: var(--motion-spring-dur); --cz-ease: var(--motion-ease); }" in canvas      # the canvas's levels (Day | Week, sheets) glide with the calm ease, no overshoot (F-114)


def test_no_animation_or_transition_duration_is_written_outside_the_tokens():
    bad = []
    for name in CSS:
        if name in ALLOWED_FILES:
            continue
        for n, line in enumerate(lines(f"css/{name}"), 1):
            if not re.search(r"transition|animation|duration|delay", line) or line.lstrip().startswith(("/*", "*", "//")):
                continue
            code = re.sub(r"/\*.*?\*/", "", line)
            for m in TIME.finditer(code):
                if m.group(1) in ("0", "0.0") or any(a in code for a in ALLOWED_CSS):
                    continue
                bad.append(f"{name}:{n}: {code.strip()[:110]}")
    assert not bad, "\n".join(bad)


def test_no_script_gives_an_animation_a_duration_of_its_own():
    bad = []
    pat = re.compile(r"(duration|delay)\s*:\s*[\d.]+|\.animate\([^)]*\b\d{2,}\b|transition\s*=\s*['\"][^'\"]*\d|animation\s*=\s*['\"][^'\"]*\d")
    for name in JS:
        for n, line in enumerate(lines(f"js/{name}"), 1):
            code = line.split("//")[0]
            if pat.search(code):
                bad.append(f"{name}:{n}: {line.strip()[:110]}")
    assert not bad, "\n".join(bad)


def test_every_sheet_menu_popover_toast_and_card_goes_through_the_helper():
    for name, calls in (("ask_sheet.js", ("MO.open(", "MO.close(", "MO.spring(")), ("day_card.js", ("MO.open(", "MO.close(", "MO.spring(", "MO.flip(")), ("day_menu.js", ("MO.open(", "MO.close(")),
                        ("ask.js", ("MO.open(", "MO.close(", "MO.reflow(")), ("toast.js", ("MO.open(", "MO.close(")), ("canvas_sos.js", ("GA.motion.open(", "GA.motion.close(")),
                        ("pickers.js", ("MO.open(", "MO.close(")), ("workspace.js", ("MO.open(", "MO.close(", "MO.flip("))):
        text = (ASSETS / "js" / name).read_text(encoding="utf-8")
        for call in calls:
            assert call in text, (name, call)
        assert "cubic-bezier" not in text and ".animate(" not in text, name           # no easing or hand-made animation of its own


def test_the_stand_in_for_the_helper_is_defined_once_and_no_script_carries_a_copy():
    """F-110: a page whose motion.js did not load gets instant changes, never an error: from ONE stand-in (motion_fallback.js, loaded right after motion.js), not seven pasted copies."""
    stand_in = (ASSETS / "js" / "motion_fallback.js").read_text(encoding="utf-8")
    assert "GA.motion = {" in stand_in and "if (GA.motion) return;" in stand_in               # it yields to the real helper
    for name in ("day_card.js", "ask_sheet.js", "day_menu.js", "ask.js", "toast.js", "pickers.js", "workspace.js"):
        text = (ASSETS / "js" / name).read_text(encoding="utf-8")
        assert "var MO = window.GA.motion" in text, name
    copies = [p.name for p in (ASSETS / "js").glob("*.js") if "reflow: function" in p.read_text(encoding="utf-8")]
    assert copies == ["motion_fallback.js"], copies


def test_the_wiggle_of_a_held_block_and_of_its_knobs_is_one_token():
    grid = (ASSETS / "css" / "day_grid.css").read_text(encoding="utf-8")
    assert grid.count("animation: cz-wiggle var(--motion-wiggle)") == 2 and "cz-wiggle 0." not in grid


def test_the_helper_is_on_every_page_before_the_toast():
    from gitaway.layout import styles
    html = "".join(str(x) for x in styles())
    assert "/assets/js/motion.js" in html and html.index("/assets/js/motion.js") < html.index("/assets/js/toast.js")
    assert html.index("/assets/js/motion.js") < html.index("/assets/js/motion_fallback.js") < html.index("/assets/js/toast.js")      # the stand-in is after the helper, before every user of it


def test_the_screen_moves_use_the_spring_tokens():
    base = (ASSETS / "css" / "base.css").read_text(encoding="utf-8")
    assert "animation-duration: var(--motion-dur); animation-timing-function: var(--motion-ease)" in base          # the page changes (F-099): a quick calm cross-fade (F-114, F-116)
    canvas = (ASSETS / "css" / "trip_canvas.css").read_text(encoding="utf-8")
    assert "::view-transition-group(cz-hero) { animation-duration: var(--cz-dur); animation-timing-function: var(--cz-ease)" in canvas      # the tapped thing grows into the next level
    assert "animation: cz-come-in var(--cz-dur) var(--cz-ease) both" in canvas                                                               # Day | Week
    grid = (ASSETS / "css" / "day_grid.css").read_text(encoding="utf-8")
    assert "animation: cz-pop var(--motion-settle-dur) var(--motion-spring)" in grid      # a new block (a moved one is GA.motion.land, F-112)
    assert "GA.motion.land" in (ASSETS / "js" / "day_grid.js").read_text(encoding="utf-8")
