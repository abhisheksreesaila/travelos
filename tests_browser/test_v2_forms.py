"""F-272 part C: the form and reading pages that were Direction A's (Plan it for me, import and build a trip, drafts, settings, stats, the sandbox checkout) wear design language v2.
In a real browser at 390 and 1440, light and dark (the site's own choice, localStorage ga-mode): the v2 shell (`.v2`, the quiet sky, the v2 top bar), no sideways scroll, every phone tap target
48px, running text 16px on the phone, every word 4.5:1 on what is painted behind it, no glass outside `.v2-glass`. Set F272_SHOTS=1 to save docs/report/f272-{planforme,import,creatordrafts}-{1440,390}.png."""
import os
from pathlib import Path

import pytest

from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
SIGNED_OUT = (("plan-for-me", "/plan-for-me"), ("plan-for-me-example", "/plan-for-me/example/disneyland"))
SIGNED_IN = (("plan-for-me-start", "/plan-for-me/start"), ("import", "/trips/import"), ("build", "/trips/build"), ("creatordrafts", "/creators/drafts"), ("creatorscan", "/creators/drafts/scan"),
             ("settings", "/creators/settings"), ("stats", "/creators/stats"))
SHOT_NAMES = {"plan-for-me": "planforme", "import": "import", "creatordrafts": "creatordrafts"}


def context(browser, viewport, mode):
    phone = viewport is PHONE
    ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=phone, is_mobile=phone)
    ctx.set_default_timeout(15000)
    ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{mode}'); }} catch (e) {{}}")
    return ctx


def sign_in(ctx, base_url):
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_form_pages_wear_v2_and_read_fit_and_tap(browser, base_url, viewport, mode):
    signed_in, signed_out = context(browser, viewport, mode), context(browser, viewport, mode)
    try:
        sign_in(signed_in, base_url)
        problems = []
        for ctx, (name, path) in [(signed_out, p) for p in SIGNED_OUT] + [(signed_in, p) for p in SIGNED_IN]:
            page = ctx.new_page()
            resp = page.goto(base_url + path, wait_until="networkidle")
            if resp.status != 200:
                problems.append(f"{name}: {resp.status}")
            if not page.evaluate("() => !!document.querySelector('.ga-page.v2 .v2-top') && !!document.querySelector('.v2-bg.is-quiet') && !document.querySelector('.ga-header')"):
                problems.append(f"{name}: not the v2 shell with the quiet sky")
            if page.evaluate("() => document.documentElement.getAttribute('data-mode')") != mode:
                problems.append(f"{name}: not drawn in {mode}")
            seen = audit(page)
            if os.getenv("F272_SHOTS") and mode == "light" and name in SHOT_NAMES:
                SHOTS.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SHOTS / f"f272-{SHOT_NAMES[name]}-{viewport['width']}.png"), full_page=True)
            page.close()
            if seen["wide"] > 1:
                problems.append(f"{name}: scrolls sideways by {seen['wide']}px")
            for key, what in (("small", "tap targets under 48px"), ("tiny", "text under the type scale"), ("low", "text under 4.5:1"), ("glass", "glass or blur")):
                if seen[key]:
                    problems.append(f"{name}: {len(seen[key])} {what}: {seen[key][:6]}")
        assert not problems, "\n".join(problems)
    finally:
        signed_in.close()
        signed_out.close()
