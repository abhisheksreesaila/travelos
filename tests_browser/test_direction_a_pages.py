"""F-272, D-800 (the F-200 sweep, now in the v2 language): the family page, the admin, privacy and terms, a Not found page and the offline page, in a real browser at 390 and 1440, in light and
dark: no sideways scroll, every phone tap target at least 48px, running text at least 16px on the phone (fine print 14, all-caps labels 13), every piece of text at least 4.5:1 against what is
behind it, no glass or blur outside `.v2-glass`, and the one "Early preview" label in the shell. Dark is the person's choice in localStorage `ga-mode` (assets/js/mode.js), not the system's:
`context()` sets it and each page asserts `data-mode`. tests_browser/look.py says how each thing is measured. F272_SHOTS=1 writes docs/report/f272-{family,admin,privacy,offline}-{1440,390}.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SIGNED_OUT = (("privacy", "/privacy"), ("terms", "/terms"), ("not found", "/no-such-page"), ("no such trip", "/trips/no-such-trip"), ("offline", "/offline"))
SIGNED_IN = (("family", "/family"), ("family with an invitation", "/family#invite"), ("admin", "/admin"))
SHOTS = {"/family": "family", "/admin": "admin", "/privacy": "privacy", "/offline": "offline"}
REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"
ADMIN = "ari.rivera@example.com"


def context(browser, viewport, mode):
    phone = viewport is PHONE
    ctx = browser.new_context(viewport=viewport, color_scheme="light", reduced_motion="reduce", has_touch=phone, is_mobile=phone)
    ctx.set_default_timeout(15000)
    ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{mode}'); }} catch (e) {{}}")      # the site's dark is the person's choice, not the system's (F-252 lesson)
    return ctx


def sign_in(ctx, base_url):
    """Sign Ari in with the imported LA trip, and ask a second person along so the family page shows an invitation waiting."""
    ctx.request.post(f"{base_url}/signin", form={"email": ADMIN, "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
    ctx.request.post(f"{base_url}/family/invite", form={"email": "sam.rivera@example.com", "role": "editor"}, max_redirects=0)


@pytest.fixture(autouse=True)
def _ari_is_the_captain(monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", ADMIN)      # the admin page answers 404 to everyone else; the server runs in this process, so it reads this


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_every_page_in_this_ticket_reads_fits_and_is_easy_to_tap(browser, base_url, viewport, mode):
    signed_in, signed_out = context(browser, viewport, mode), context(browser, viewport, mode)
    try:
        sign_in(signed_in, base_url)
        problems = []
        for ctx, (name, path) in [(signed_out, p) for p in SIGNED_OUT] + [(signed_in, p) for p in SIGNED_IN]:
            page = ctx.new_page()
            page.goto(base_url + path, wait_until="networkidle")
            wearing = page.evaluate("() => [document.documentElement.dataset.mode, !!document.querySelector('.ga-page.v2 .pg, .ga-page.v2 .pgs'), document.querySelector('.v2-bg')?.dataset.sky]")
            seen = audit(page)
            labels = page.evaluate("() => [...document.querySelectorAll('.ga-preview-pill')].filter(e => e.getClientRects().length && getComputedStyle(e).visibility === 'visible').length")
            if os.getenv("F272_SHOTS") and mode == "light" and path in SHOTS and name != "family with an invitation":
                REPORT.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(REPORT / f"f272-{SHOTS[path]}-{viewport['width']}.png"), full_page=True)
            page.close()
            if wearing[0] != mode:
                problems.append(f"{name}: data-mode is {wearing[0]}, not {mode}")
            if wearing[2] != "quiet":
                problems.append(f"{name}: not the quiet reading sky ({wearing[2]})")
            if labels != 1:
                problems.append(f"{name}: {labels} Early preview labels on screen (one, in the shell)")
            if seen["wide"] > 1:
                problems.append(f"{name}: scrolls sideways by {seen['wide']}px")
            for key, what in (("small", "tap targets under 48px"), ("tiny", "text under the type scale"), ("low", "text under 4.5:1"), ("glass", "glass or blur outside .v2-glass")):
                if seen[key]:
                    problems.append(f"{name}: {len(seen[key])} {what}: {seen[key][:6]}")
        assert not problems, "\n".join(problems)
    finally:
        signed_in.close()
        signed_out.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_early_preview_label_opens_its_line_and_esc_closes_it(browser, base_url, viewport):
    signed_in, signed_out = context(browser, viewport, "light"), context(browser, viewport, "light")
    try:
        sign_in(signed_in, base_url)
        for ctx, path in ((signed_out, "/privacy"), (signed_in, "/family"), (signed_in, "/admin")):
            page = ctx.new_page()
            page.goto(base_url + path, wait_until="networkidle")
            label = page.locator(".ga-preview-sum:visible")
            line = page.locator(".ga-preview[open] .ga-preview-pop")
            label.click()
            expect(line).to_be_visible()
            expect(line).to_have_text("GitAway is new. Things will change; tell us what breaks.")
            box = line.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"], box      # the line stays on the screen
            page.keyboard.press("Escape")
            expect(page.locator(".ga-preview[open]")).to_have_count(0)
            page.close()
    finally:
        signed_in.close()
        signed_out.close()


def test_light_by_default_and_the_round_button_switches_to_dark_and_is_remembered_on_this_device(browser, base_url):
    """D-460: light whatever the system says; the v2 bar's round button turns dark on and off, remembered on this device before the first paint."""
    ctx = browser.new_context(viewport=DESKTOP, color_scheme="dark", reduced_motion="reduce")
    try:
        page = ctx.new_page()
        page.goto(f"{base_url}/privacy")
        toggle = page.locator("#ga-mode-v2")
        mode = "document.documentElement.dataset.mode"
        assert page.evaluate(mode) in ("light", None, "")      # the system says dark; the site is light
        assert toggle.get_attribute("aria-pressed") == "false"
        toggle.click()
        assert page.evaluate(mode) == "dark" and toggle.get_attribute("aria-pressed") == "true"
        page.goto(f"{base_url}/terms")                          # another page: still dark, chosen before the first paint
        assert page.evaluate(mode) == "dark"
        page.emulate_media(color_scheme="light")                # the system changes its mind; the person's choice stays
        page.reload()
        assert page.evaluate(mode) == "dark"
        page.locator("#ga-mode-v2").click()                     # and back
        assert page.evaluate(mode) == "light"
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_a_reading_page_ends_with_privacy_and_terms_within_reach(browser, base_url, viewport):
    """The v2 bar does not carry the legal links, so a reading page's foot does: two 48px targets, with the one sentence about booking and payment."""
    ctx = context(browser, viewport, "light")
    try:
        page = ctx.new_page()
        page.goto(f"{base_url}/offline")
        for name, href in (("Privacy", "/privacy"), ("Terms", "/terms")):
            link = page.locator(f'.pg-foot a[href="{href}"]')
            expect(link).to_have_text(name)
            box = link.bounding_box()
            assert min(box["width"], box["height"]) >= 47.5, (name, box)
    finally:
        ctx.close()
