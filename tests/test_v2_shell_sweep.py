"""F-272, D-800: every parameter-free GET page, signed out and signed in, wears the v2 shell (the v2 stylesheet and the `ga-page v2` wrapper).
The cover has its own shell; PENDING_F272 names the pages another builder converts in the same ticket (empty it once merged)."""
import pytest

from tests.test_signin import sign_in

OWN_SHELL = {"/"}      # the cover (its own shell, tests/test_cover.py)
NOT_PAGES = {"/auth/callback", "/logout", "/healthz", "/manifest.webmanifest", "/sw.js", "/robots.txt", "/sitemap.xml", "/trips/import/template", "/plan/explore", "/plan/quote",
             "/badge/plan-this-trip.svg", "/badge/plan-this-trip-dark.svg", "/trip/family/thread", "/trip/talk/items", "/trip/family/list", "/trip/family/panel", "/trip/cockpit/map",
             "/plan/matrix/tile", "/plan/matrix/rail", "/guides/sheet", "/plan/ask/suggest"}      # fragments, JSON, files, the OAuth return
PENDING_F272: set[str] = set()      # empty since parts A and C merged (F-272); a page still in Direction A would be listed here, with the reason


def v2_shell(html: str) -> bool:
    return "/assets/css/v2-tokens.css" in html and 'class="ga-page v2' in html


def paths(app):
    found = {r.path for r in app.routes if "GET" in (getattr(r, "methods", None) or ()) and "{" not in r.path}
    return sorted((found - NOT_PAGES) | {"/trips/no-such-trip"})


@pytest.mark.parametrize("signed_in", [False, True], ids=["out", "in"])
def test_every_page_wears_the_v2_shell(client, signed_in):
    from main import app
    if signed_in:
        sign_in(client, "ari")
    seen, wrong = 0, []
    for path in paths(app):
        r = client.get(path, follow_redirects=False)
        if not r.headers.get("content-type", "").startswith("text/html") or r.status_code in (301, 302, 303, 307, 308):
            continue
        if path in OWN_SHELL and not signed_in:
            continue
        seen += 1
        if not v2_shell(r.text) and path not in PENDING_F272:
            wrong.append(f"{path} ({r.status_code})")
        elif path not in OWN_SHELL and 'class="v2-top"' not in r.text and "v2-top" not in r.text:
            wrong.append(f"{path} ({r.status_code}, no v2 top bar)")
    assert seen >= 12
    assert not wrong, f"pages still in Direction A: {wrong}"


def test_the_pending_list_names_only_pages_that_are_not_v2_yet(client):
    """When a page moves, it leaves the list: a stale entry would hide a page that went back."""
    stale = [p for p in sorted(PENDING_F272) if (r := client.get(p, follow_redirects=False)).headers.get("content-type", "").startswith("text/html") and v2_shell(r.text)]
    assert not stale, f"PENDING_F272 can drop: {stale}"


def test_a_quiet_page_ends_with_privacy_and_terms_except_where_it_has_its_own_foot(client):
    """The v2 bar carries no legal links, so every quiet page's foot does; the cover, the matrix (its About card) and a guide (studio.foot) keep their own."""
    for path in ("/privacy", "/offline", "/no-such-page", "/guides/make"):
        html = client.get(path).text
        assert html.count('class="pg-foot"') + html.count("cb-foot") == 1 and 'href="/privacy"' in html and 'href="/terms"' in html, path
    assert 'class="pg-foot"' not in client.get("/plan/matrix").text


def test_an_unknown_page_is_the_v2_nothing_here_but_a_missing_asset_is_a_plain_404(client):
    page = client.get("/no-such-page")
    assert page.status_code == 404 and "Nothing here" in page.text and v2_shell(page.text)
    for path in ("/assets/css/no-such.css", "/api/nope"):
        r = client.get(path)
        assert r.status_code == 404 and r.headers["content-type"].startswith("text/plain") and len(r.content) < 100, path
    assert client.get("/healthz").status_code == 200
