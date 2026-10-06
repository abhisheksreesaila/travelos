"""F-108: there is one toast. Every page loads its stylesheet and script, no other pop-up component is left (the canvas's dark bar, the Ask sheet's, the calendar's and the old Today page's
had their own looks), and the ones the server draws with a page use the shared classes. The look and motion are checked in the browser (tests_browser/test_toast.py)."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def test_every_page_loads_the_one_toast(client):
    for path in ("/", "/community", "/start"):
        html = client.get(path).text
        assert "/assets/css/toast.css" in html and "/assets/js/toast.js" in html, path


def test_the_other_toasts_are_gone_from_the_styles_and_scripts():
    for sub in ("css", "js"):
        for f in (ASSETS / sub).glob("*"):
            if f.name in ("toast.css", "toast.js"):
                continue
            text = f.read_text(encoding="utf-8")
            for old in (".cz-toast", ".ak-toast", "ak-toast", "cz-toast", ".tp-toast {", ".cal-toast {"):
                assert old not in text, (f.name, old)


def test_the_one_toast_has_the_calm_look_and_motion():
    css = (ASSETS / "css" / "toast.css").read_text(encoding="utf-8")
    assert "var(--motion-dur)" in css and "var(--motion-ease)" in css and "translate: 0 -0.75rem" in css and "max-width: min(22rem" in css
    assert "backdrop-filter" in css and "linear-gradient(180deg" in css and "prefers-reduced-motion: reduce" in css
    js = (ASSETS / "js" / "toast.js").read_text(encoding="utf-8")
    assert "4500" in js and "9000" in js and "aria-live" in js and "'status'" in js


def test_the_calendars_server_drawn_toasts_use_the_shared_classes():
    from gitaway.pages import calendar as calui
    from fasthtml.common import to_xml
    html = to_xml(calui.toast("error", "Nope", tid="t"))
    assert 'class="ga-toast ga-toast-static cal-toast cal-toast-error"' in html and 'role="alert"' in html and 'id="t"' in html
