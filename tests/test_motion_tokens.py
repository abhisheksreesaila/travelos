"""F-109: one liquid motion. The tokens live in tokens.css and assets/js/motion.js (GA.motion) is the only helper that opens, folds and settles things; every sheet, menu, popover, toast and screen
move (and the new bubbles and blocks) takes its duration and easing from those tokens and writes none of its own. Browser checks of the frames: tests_browser/test_motion.py."""
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CSS = ["day_grid.css", "day_card.css", "trip_canvas.css", "thread.css", "toast.css", "ask_sheet.css", "ask.css"]
JS = ["motion.js", "day_card.js", "ask_sheet.js", "ask.js", "day_menu.js", "toast.js", "thread.js", "day_grid.js", "day_new.js", "day_fold.js", "trip_canvas.js", "page_moves.js"]
# What may keep a literal time, and why. None of these is a sheet, menu, popover, toast or screen move.
ALLOWED_CSS = (
    "cz-wiggle 0.42s",       # the held block's looping wiggle (feedback while a finger holds it)
    "ak-fresh 1.6s",         # the glow on what Apply changed, a few seconds of attention, not a move
    "ak-ink 0.5s",           # the typed words fading in
    "ak-blink 1s", "ak-pulse 1.2s",   # the recording dot and the mic's pulse (infinite loops)
)
TIME = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b")


def lines(path):
    return (ASSETS / path).read_text(encoding="utf-8").splitlines()


def test_the_tokens_are_the_cards_spring_and_one_set():
    css = (ASSETS / "css" / "tokens.css").read_text(encoding="utf-8")
    for token, value in (("--motion-spring-dur", "380ms"), ("--motion-spring", "cubic-bezier(.3, 1.35, .5, 1)"), ("--motion-dur", "240ms"), ("--motion-out", "cubic-bezier(.4, 0, .8, .4)"),
                         ("--motion-settle-dur", "280ms"), ("--motion-quick", "160ms"), ("--motion-fade", "120ms")):
        assert re.search(rf"{re.escape(token)}:\s*{re.escape(value)}", css), token
    canvas = (ASSETS / "css" / "trip_canvas.css").read_text(encoding="utf-8")
    assert ":root { --cz-dur: var(--motion-spring-dur); --cz-ease: var(--motion-spring); }" in canvas      # the canvas's levels (Day | Week, sheets) are the same spring


def test_no_animation_or_transition_duration_is_written_outside_the_tokens():
    bad = []
    for name in CSS:
        for n, line in enumerate(lines(f"css/{name}"), 1):
            if not re.search(r"transition|animation|duration|delay", line) or line.lstrip().startswith(("/*", "*", "//")):
                continue
            code = re.sub(r"/\*.*?\*/", "", line)
            for m in TIME.finditer(code):
                if m.group(1) in ("0", "0.0") or any(a in code for a in ALLOWED_CSS):
                    continue
                bad.append(f"{name}:{n}: {code.strip()[:110]}")
    for n, line in enumerate(lines("css/base.css"), 1):          # the page changes (cross-document view transitions)
        if "view-transition" in line and TIME.search(re.sub(r"/\*.*?\*/", "", line)):
            bad.append(f"base.css:{n}: {line.strip()[:110]}")
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
    for name, calls in (("ask_sheet.js", ("MO.open(", "MO.close(", "MO.spring(")), ("day_card.js", ("MO.open(", "MO.close(", "MO.spring(")), ("day_menu.js", ("MO.open(", "MO.close(")),
                        ("ask.js", ("MO.open(", "MO.close(")), ("toast.js", ("GA.motion.open(", "GA.motion.close(")), ("trip_canvas.js", ("GA.motion.open(", "GA.motion.close("))):
        text = (ASSETS / "js" / name).read_text(encoding="utf-8")
        for call in calls:
            assert call in text, (name, call)
        assert "cubic-bezier" not in text and ".animate(" not in text, name           # no easing or hand-made animation of its own


def test_the_helper_is_on_every_page_before_the_toast():
    from gitaway.layout import styles
    html = "".join(str(x) for x in styles())
    assert "/assets/js/motion.js" in html and html.index("/assets/js/motion.js") < html.index("/assets/js/toast.js")


def test_the_screen_moves_use_the_spring_tokens():
    base = (ASSETS / "css" / "base.css").read_text(encoding="utf-8")
    assert "animation-duration: var(--motion-spring-dur); animation-timing-function: var(--motion-spring)" in base          # the page changes (F-099)
    canvas = (ASSETS / "css" / "trip_canvas.css").read_text(encoding="utf-8")
    assert "::view-transition-group(cz-hero) { animation-duration: var(--cz-dur); animation-timing-function: var(--cz-ease)" in canvas      # the tapped thing grows into the next level
    assert "animation: cz-come-in var(--cz-dur) var(--cz-ease) both" in canvas                                                               # Day | Week
    thread = (ASSETS / "css" / "thread.css").read_text(encoding="utf-8")
    assert "animation: ft-in var(--motion-settle-dur) var(--motion-spring)" in thread                                                        # a new chat bubble
    grid = (ASSETS / "css" / "day_grid.css").read_text(encoding="utf-8")
    assert "animation: cz-pop var(--motion-settle-dur) var(--motion-spring)" in grid and "transform var(--motion-settle-dur) var(--motion-spring)" in grid      # a new and a moved block
