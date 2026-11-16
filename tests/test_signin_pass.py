"""F-052, F-200: the sign-in trip card (the boarding pass before Direction A) fills from where the traveler came from."""
import re
from html import unescape as html_unescape
from urllib.parse import quote

import pytest

from gitaway import signin_context as sc

SEARCH = "/plan?f=f1&h=h1&c=none&d=2026-10-16&r=2026-10-20&a=2&k=4,7"
FORK = "/trips/sun-tacos-and-tide-pools"


def get(client, next_path, intent="save"):
    return client.get(f"/signin?next={quote(next_path, safe='/')}&intent={intent}").text


def stub(html):
    return re.search(r'class="si-stub".*?</div>', html, re.S).group(0)


def test_generic_pass_without_context(client):
    html = get(client, "/")
    assert 'data-pass="cold"' in html and "Your next trip starts here." in html and "Anywhere" in html and "You pick" in html
    assert "SFO" in html and "LAX" in html  # the fallback route codes on the sky


def test_fork_pass_has_the_trip_and_no_creator(client):
    for intent in ("fork", "save", "publish"):
        html = get(client, FORK, intent)
        assert 'data-pass="fork"' in html and "Los Angeles in 5 days." in html and "5 days" in stub(html)
        assert "Maya" not in html and "Theo" not in html


def test_a_trip_page_that_is_not_a_fork_intent_is_generic(client):
    assert 'data-pass="cold"' in get(client, FORK, "invite")


@pytest.mark.parametrize("bad", ["/trips/does-not-exist", "/plan?d=junk&r=nope", "/plan?d=2026-10-20&r=2026-10-16", "/trips/a/b", "//evil.example/x",
                                 "https://evil.example/plan?d=2026-10-16&r=2026-10-20", "/creators/finish"])
def test_a_bad_or_unknown_next_falls_back_to_the_generic_pass(client, bad):
    r = client.get("/signin", params={"next": bad, "intent": "fork"})
    assert r.status_code == 200 and 'data-pass="cold"' in r.text


def test_context_is_escaped(monkeypatch):
    from fasthtml.common import to_xml
    import gitaway.pages.signin as si
    evil = sc.Pass(**{**sc.GENERIC.__dict__, "head": "<script>alert(1)</script>", "s1": "<b>x</b>"})
    monkeypatch.setattr(si, "context", lambda n, i: evil)
    card, sky = si.dialog("/", "save")
    out = to_xml(card) + to_xml(sky)
    assert "<script>alert" not in out and "&lt;script&gt;" in out and "<b>x</b>" not in out


def test_the_dev_form_is_hidden_in_production(client, monkeypatch):
    assert "Local dev sign-in" in get(client, "/")
    monkeypatch.setenv("GITAWAY_ENV", "production")
    html = get(client, "/")
    assert "Local dev sign-in" not in html and 'id="si-dev-form"' not in html and "isn't set up" in html


def test_google_button_only_with_keys(client, monkeypatch):
    assert "Continue with Google" not in get(client, SEARCH)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    html = get(client, SEARCH, "pay")
    assert "Continue with Google" in html and 'id="si-google"' in html and "/login?next=" in html


def test_the_half_beside_the_card_is_decorative_and_has_the_route_codes(client):
    html = get(client, FORK, "fork")      # F-200: one route widget on the laptop's left half (the old sky drew two stages)
    assert 'class="si-sky"' in html and 'aria-hidden="true"' in html and html.count('class="si-code"') == 2


def test_the_google_button_wears_googles_own_g_hidden_from_the_accessible_name(client, monkeypatch):
    """The founder (2026-11-13): the button had a plain letter, not Google's mark, so it did not read as Google. Its four colours are Google's
    (the brand guidelines' G, the same in light and dark), and the accessible name stays "Continue with Google"."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    g = re.search(r'<span(?=[^>]*aria-hidden="true")(?=[^>]*class="si-g")[^>]*>(.*?)</span>', get(client, "/"), re.S).group(1)
    assert "<svg" in g and all(c in g for c in ("#4285F4", "#34A853", "#FBBC05", "#EA4335")), g


def test_fork_stickers_are_the_first_two_day_titles(client):
    from gitaway import itineraries
    days = itineraries.get("sun-tacos-and-tide-pools").days
    html = get(client, FORK, "fork")
    stickers = re.findall(r'class="si-stick si-stick\d"[^>]*>(.*?)</span>', html)
    assert [html_unescape(s) for s in stickers[:2]] == [days[0].title, days[1].title]


@pytest.mark.parametrize("intent,words", [("fork", "your forks"), ("save", "saved trips"), ("publish", "publish")])
def test_the_fork_pass_wording_follows_the_intent(client, intent, words):
    html = get(client, FORK, intent)
    desc = re.search(r'id="si-desc">(.*?)</p>', html, re.S).group(1)
    assert words in desc
    if intent != "fork":
        assert "your forks" not in desc


def test_the_stub_says_stay_signed_in(client):
    assert ">STAY SIGNED IN<" in get(client, "/")


def test_the_dev_summary_has_a_chevron(client):
    assert re.search(r'<summary class="si-sum">.*?<svg', get(client, "/"), re.S)


def test_the_page_is_the_v2_shell_with_the_cover_s_sky_and_the_things_it_kept(client):
    """F-272: the sign-in wears the cover's language: the v2 stylesheets and wrapper, the sky (sun, moon, clouds), the bar with Early preview, light/dark and Cancel; no sections pill."""
    html = get(client, "/", "save")
    assert '/assets/css/v2-tokens.css' in html and '/assets/css/v2.css' in html and 'class="ga-page v2 si-page"' in html and 'class="v2-bg"' in html
    assert "Early preview" in html and 'id="ga-mode-v2"' in html and 'class="v2-sections' not in html
    assert re.search(r'<a [^>]*href="/"[^>]*id="si-cancel"|<a [^>]*id="si-cancel"[^>]*href="/"', html) and 'href="/terms"' in html and 'href="/privacy"' in html
    assert "passkeys.css" not in html and "Direction A" not in html


def test_cancel_goes_back_to_where_the_person_was(client):
    assert 'id="si-cancel"' in get(client, FORK, "fork") and f'href="{FORK}"' in re.search(r'<a [^>]*id="si-cancel"[^>]*>|<a [^>]*href="[^"]*"[^>]*id="si-cancel"', get(client, FORK, "fork")).group(0)
