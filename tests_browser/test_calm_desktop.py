"""F-156: the laptop is calm. From 1020px up (not the installed app) GA.motion.calm() makes every open, close and settle a short fade. The old canvas's frame-recording tests went with F-254;
this keeps the rule that matters on what is left: only the scripts named here may keep the liquid motion on a laptop."""

# The pages that keep the liquid motion on a laptop, each by name and decision: a page joins only by setting data-liquid on <html> in its own script, and this list is the only place that allows it.
LIQUID_EXCEPTIONS = {"tripmatrix.js": "D-439: the trip matrix, /plan/matrix (the founder: \"experience is the key … it has to be liquidy\")"}


def test_only_the_named_exceptions_keep_the_liquid_motion_on_a_laptop():
    """GA.motion.calm() is false only where <html> carries data-liquid, and only the scripts in LIQUID_EXCEPTIONS set it (tests_browser/test_tripmatrix.py checks the matrix
    opens liquid at 1440 and /plan stays calm)."""
    import re
    from pathlib import Path
    js = Path(__file__).resolve().parent.parent / "assets" / "js"
    setters = sorted(p.name for p in js.glob("*.js") if re.search(r"setAttribute\(\s*['\"]data-liquid", p.read_text(encoding="utf-8")))
    assert setters == sorted(LIQUID_EXCEPTIONS)
    assert "hasAttribute('data-liquid')" in (js / "motion.js").read_text(encoding="utf-8")
