"""F-044: GitAway installs on an iPhone: manifest, icons, Apple tags and a small, safe service worker."""
import json
import re
import shutil
import struct
import subprocess
import textwrap
from pathlib import Path

import pytest

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
    paths -= {"/plan/explore", "/plan/quote", "/manifest.webmanifest", "/sw.js"}
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
        assert 'name="theme-color"' in html, path
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


@pytest.mark.skipif(not shutil.which("node"), reason="node is needed to run the worker's routing rules")
def test_service_worker_never_caches_posts_or_the_auth_routes():
    script = textwrap.dedent(f"""
        const src = require('fs').readFileSync({json.dumps(str(ROOT / 'assets/sw.js'))}, 'utf8');
        const self_ = {{ addEventListener() {{}}, location: {{ origin: 'https://gitaway.test' }} }};
        const route = new Function('self', src + '; return routeFor;')(self_);
        const r = (method, path, mode = 'navigate', origin = 'https://gitaway.test') => route({{ method, mode, url: origin + path }});
        console.log(JSON.stringify({{
          post: r('POST', '/plan'), postAsset: r('POST', '/assets/x.css', 'cors'),
          login: r('GET', '/login'), auth: r('GET', '/auth/callback?code=1'), logout: r('GET', '/logout'),
          signin: r('GET', '/signin?next=/plan'), signout: r('GET', '/signout'),
          asset: r('GET', '/assets/css/base.css', 'no-cors'), page: r('GET', '/discover'), trip: r('GET', '/trips/x'),
          cross: r('GET', '/foo', 'navigate', 'https://fonts.googleapis.com'),
          xhr: r('GET', '/plan/quote', 'cors'), sw: r('GET', '/sw.js', 'cors'),
        }}));
    """)
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for k in ("post", "postAsset", "login", "auth", "logout", "signin", "signout", "cross", "xhr", "sw"):
        assert out[k] == "skip", k
    assert out["asset"] == "asset"
    assert out["page"] == "page" and out["trip"] == "page"
