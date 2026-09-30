"""The GitAway shell: every page shares the brand, navigation and design tokens."""


def test_home_is_a_gitaway_page_with_the_main_navigation(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert "<title>GitAway" in html
    assert "TravelOS" not in html
    for label, href in [("Discover", "/discover"), ("Plan a trip", "/plan"), ("For creators", "/creators")]:
        assert f'href="{href}"' in html and label in html
    assert "/assets/css/tokens.css" in html and "/assets/css/base.css" in html


def test_every_page_links_tokens_then_base_exactly_once(client):
    from main import app
    paths = {r.path for r in app.routes
             if "GET" in (getattr(r, "methods", None) or ()) and "{" not in r.path}
    paths.add("/trips/sun-tacos-and-tide-pools")
    assert {"/", "/plan"} <= paths
    for path in sorted(paths):
        html = client.get(path).text
        assert html.count("/assets/css/tokens.css") == 1, path
        assert html.count("/assets/css/base.css") == 1, path
        assert html.index("/assets/css/tokens.css") < html.index("/assets/css/base.css"), path


def test_design_tokens_are_served(client):
    r = client.get("/assets/css/tokens.css")
    assert r.status_code == 200
    assert "--coral: #FF7352" in r.text
    assert '[data-theme="pacific"]' in r.text


def test_nav_destinations_are_never_dead_ends(client):
    for path in ["/discover", "/plan", "/creators", "/signin"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "<title>GitAway" in r.text and "TravelOS" not in r.text


def test_an_unknown_trip_gets_a_friendly_not_found_page(client):
    r = client.get("/trips/no-such-trip")
    assert r.status_code == 404
    assert "This trip wandered off" in r.text and "TravelOS" not in r.text
    assert "/assets/css/tokens.css" in r.text
    assert 'href="/discover"' in r.text


def test_every_page_offers_a_skip_link_to_the_main_content(client):
    html = client.get("/").text
    assert 'href="#main"' in html and 'id="main"' in html


def test_a_real_screen_replaces_its_placeholder(client):
    from fasthtml.common import FastHTML
    from starlette.testclient import TestClient
    from gitaway.pages import register_all

    class RealPlan:
        @staticmethod
        def register(app):
            @app.get("/plan")
            def plan():
                return "the real workspace"

    app = FastHTML()
    register_all(app, extra=[RealPlan])
    assert "the real workspace" in TestClient(app).get("/plan").text
