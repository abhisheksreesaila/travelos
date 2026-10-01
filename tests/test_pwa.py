"""F-044: GitAway installs on an iPhone: manifest, icons, Apple tags and a small, safe service worker."""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "assets/icons"


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", data[16:24])


def test_manifest_is_served_with_its_own_content_type_and_opens_at_start(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["name"] == "GitAway" and m["short_name"] == "GitAway"
    assert m["start_url"] == "/start" and m["scope"] == "/" and m["display"] == "standalone"
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", m["theme_color"]) and re.fullmatch(r"#[0-9A-Fa-f]{6}", m["background_color"])
    kinds = {(i["sizes"], i.get("purpose", "any")) for i in m["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= kinds
    for i in m["icons"]:
        assert i["type"] == "image/png"
        assert i["src"].startswith("/assets/icons/")


def test_every_manifest_icon_exists_with_the_declared_size(client):
    for i in client.get("/manifest.webmanifest").json()["icons"]:
        w, h = (int(n) for n in i["sizes"].split("x"))
        assert png_size(ROOT / i["src"].lstrip("/")) == (w, h), i["src"]
        assert client.get(i["src"]).status_code == 200


def test_apple_touch_icon_is_180():
    assert png_size(ICONS / "apple-touch-icon.png") == (180, 180)


def test_every_page_carries_the_install_tags(client):
    from main import app
    paths = {r.path for r in app.routes if "GET" in (getattr(r, "methods", None) or ()) and "{" not in r.path}
    paths -= {"/plan/explore", "/plan/quote", "/manifest.webmanifest", "/sw.js", "/auth/callback"}
    paths |= {"/trips/sun-tacos-and-tide-pools", "/trips/no-such-trip"}
    assert {"/", "/start", "/offline"} <= paths
    for path in sorted(paths):
        html = client.get(path).text
        assert html.count('rel="manifest" href="/manifest.webmanifest"') == 1, path
        assert 'rel="apple-touch-icon"' in html and "/assets/icons/apple-touch-icon.png" in html, path
        assert 'name="apple-mobile-web-app-capable" content="yes"' in html, path
        assert 'name="mobile-web-app-capable" content="yes"' in html, path
        assert 'name="apple-mobile-web-app-status-bar-style"' in html, path
        assert 'name="apple-mobile-web-app-title" content="GitAway"' in html, path
        assert 'name="theme-color" content="#' in html, path
        assert 'content="black-translucent"' not in html and 'name="apple-mobile-web-app-status-bar-style" content="default"' in html, path
        assert "viewport-fit=cover" in html, path
        assert "/assets/js/pwa.js" in html, path


def test_service_worker_is_served_from_the_root_scope(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["service-worker-allowed"] == "/"
    assert r.headers["cache-control"].startswith("no-cache")


def test_offline_page_is_a_gitaway_page(client):
    r = client.get("/offline")
    assert r.status_code == 200 and "<title>GitAway" in r.text and "offline" in r.text.lower()



def test_theme_colour_follows_the_pages_ground(client):
    from fasthtml.common import to_xml
    from gitaway.layout import page
    assert 'name="theme-color" content="#FFF8EE"' in client.get("/start").text
    assert 'name="theme-color" content="#F4F9FF"' in to_xml(page("x", theme="pacific"))


def test_asset_links_carry_a_content_hash(client):
    html = client.get("/start").text
    for name in ("css/tokens.css", "css/base.css", "css/start.css", "js/start.js", "js/pwa.js"):
        m = re.search(rf'/assets/{re.escape(name)}\?v=([0-9a-f]{{8}})"', html)
        assert m, name
        assert client.get(f"/assets/{name}?v={m.group(1)}").status_code == 200


def test_asset_hash_follows_the_file_contents(tmp_path, monkeypatch):
    from gitaway import assetver
    monkeypatch.setattr(assetver, "ASSETS_DIR", tmp_path)
    (tmp_path / "css").mkdir()
    f = tmp_path / "css" / "a.css"
    f.write_text("a{}")
    one = assetver.versioned("/assets/css/a.css")
    f.write_text("b{color:red}")
    two = assetver.versioned("/assets/css/a.css")
    assert one != two and one.startswith("/assets/css/a.css?v=")
    assert assetver.versioned("/assets/css/missing.css") == "/assets/css/missing.css"


def test_service_worker_version_changes_when_a_precached_file_changes(client, monkeypatch):
    from gitaway import assetver
    first = client.get("/sw.js").text
    m = re.search(r'const VERSION = "([0-9a-f]+)"', first)
    assert m and "__VERSION__" not in first and "__SHELL_URLS__" not in first
    assert re.search(r'"/assets/css/base.css\?v=[0-9a-f]{8}"', first) and '"/offline"' in first
    real = assetver.file_hash
    monkeypatch.setattr(assetver, "file_hash", lambda url: "ffffffff" if url.endswith("base.css") else real(url))
    second = client.get("/sw.js").text
    assert re.search(r'const VERSION = "([0-9a-f]+)"', second).group(1) != m.group(1)


def test_sign_out_asks_the_browser_to_forget_its_caches_and_storage(client):
    from tests.test_signin import sign_in
    sign_in(client)
    r = client.post("/signout", follow_redirects=False)
    assert r.headers["clear-site-data"] == '"cache", "storage"'


def test_pages_carry_a_non_secret_per_person_cache_key_only_when_signed_in(client):
    from tests.test_signin import sign_in
    key = r'<meta name="ga-user" content="([0-9a-f]{10})">'
    assert not re.search(key, client.get("/discover").text)
    sign_in(client, "ari")
    a = re.search(key, client.get("/discover").text).group(1)
    sign_in(client, "sam")
    b = re.search(key, client.get("/discover").text).group(1)
    assert a != b and "ari" not in a and "sam" not in b


def test_offline_page_never_shows_who_was_signed_in(client):
    from tests.test_signin import sign_in
    sign_in(client, "ari")
    html = client.get("/offline").text
    assert "Ari" not in html and 'name="ga-user"' not in html and "Sign in" in html


def test_cache_key_depends_on_the_server_secret_not_just_the_id(monkeypatch):
    import hashlib
    from gitaway import layout, session
    ari = session.sign_in({}, "u-ari", "ari.rivera@example.com")
    one = layout.cache_key(ari)
    assert one != hashlib.sha256(f"gitaway-pages:{ari.id}".encode()).hexdigest()[:10]
    monkeypatch.setattr(session, "cache_secret", lambda: b"another secret")
    assert layout.cache_key(ari) != one


def test_as_signed_out_hides_the_traveler_for_the_rest_of_the_request():
    from gitaway import session
    session._request_traveler.set(session.sign_in({}, "u-ari", "ari.rivera@example.com"))
    session.as_signed_out()
    assert session.request_traveler() is None
