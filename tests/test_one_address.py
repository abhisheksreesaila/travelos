"""F-078: in production every other host is sent to GITAWAY_PUBLIC_URL; nothing redirects locally."""
import pytest
from starlette.testclient import TestClient

NEW, OLD = "gitaway.me", "web-production-2d117.up.railway.app"


@pytest.fixture
def prod(monkeypatch):
    import main  # noqa: F401  imported before production is switched on (it needs a secret key then)
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", f"https://{NEW}")


def hit(method, path, host, **kw):
    from main import app
    c = TestClient(app, client=("127.0.0.1", 50000), base_url=f"http://{host}", follow_redirects=False)
    return c.request(method, path, **kw)


def test_old_host_get_redirects_with_path_and_query(prod):
    r = hit("GET", "/family?tab=x&y=1", OLD)
    assert r.status_code == 308
    assert r.headers["location"] == f"https://{NEW}/family?tab=x&y=1"


def test_old_host_post_redirects_permanently(prod):
    r = hit("POST", "/anything", OLD, data={"a": "b"})
    assert r.status_code == 308 and r.headers["location"] == f"https://{NEW}/anything"


def test_root_path(prod):
    assert hit("GET", "/", OLD).headers["location"] == f"https://{NEW}/"


def test_forwarded_host_is_never_used(prod):
    r = hit("GET", "/x", OLD, headers={"x-forwarded-host": "evil.example"})
    assert r.headers["location"] == f"https://{NEW}/x"


@pytest.mark.parametrize("path", ["/healthz", "/auth/callback"])
def test_exempt_paths_stay_on_the_old_host(prod, path):
    assert hit("GET", path, OLD).status_code != 308


def test_matching_host_untouched(prod):
    assert hit("GET", "/healthz", NEW).status_code == 200
    assert hit("GET", "/", NEW.upper()).status_code != 308


def test_not_production_no_redirect(monkeypatch):
    import main  # noqa: F401
    monkeypatch.delenv("GITAWAY_ENV", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", f"https://{NEW}")
    assert hit("GET", "/healthz", OLD).status_code == 200
    assert hit("GET", "/", OLD).status_code != 308


@pytest.mark.parametrize("url", ["", "http://gitaway.me", "https://gitaway.me/path", "https://127.0.0.1"])
def test_unset_or_invalid_url_no_redirect(monkeypatch, url):
    import main  # noqa: F401
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", url)
    assert hit("GET", "/", OLD).status_code != 308
