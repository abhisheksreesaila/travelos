"""F-182 (H1): the app is one uvicorn process, so a blocking call inside an `async def` route handler freezes every visitor until it returns (a slow blog fetch froze the whole site).
Blocking network, AI, image and PDF work runs in `run_in_threadpool` or in a plain `def` handler. Two checks: the source never calls the known blocking functions straight from an
async function, and a real server answers /healthz at once while a creator's slow blog fetch is in flight."""

import ast
import re
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from tests.creator_import_support import Model, page
from tests.test_signin import EMAILS

ROOT = Path(__file__).resolve().parent.parent / "gitaway"
BLOCKING = re.compile(r"^(ai\.(call_json|transcribe)|safefetch\.fetch|importsource\.(gather|offline)|blogscan\.(discover|sample)|(dj|draftjobs)\.\w+|(pfm|planforme)\.\w+|stripe\.[\w.]+|(cd|creatordraft)\.\w+|(cc|creatorclaim)\.draft|admin\.admin_page|expedia\.pdf_text|geo\.\w+|photos\.\w+|time\.sleep|requests\.\w+|urllib\.\w+|httpx\.\w+|_read)$")
# One-row reads and writes in the local SQLite file are fine on the loop; these are the only listed calls that are.
FINE = {("gitaway/pages/creatorimport.py", "cd.get"), ("gitaway/pages/creatordrafts.py", "cd.mode"), ("gitaway/pages/creatordrafts.py", "dj.remaining"), ("gitaway/pages/planforme.py", "pfm.standin")}      # (standin: two environment checks, no database)


def _own_calls(fn):
    """The calls an async function makes itself: not inside a lambda or a nested plain def (those are what `run_in_threadpool` is given)."""
    todo = list(ast.iter_child_nodes(fn))
    while todo:
        n = todo.pop()
        if isinstance(n, (ast.Lambda, ast.FunctionDef)):
            continue
        if isinstance(n, ast.Call):
            yield n
        todo.extend(ast.iter_child_nodes(n))


def _offenders():
    out = []
    for path in sorted(ROOT.rglob("*.py")):
        for fn in ast.walk(ast.parse(path.read_text())):
            if isinstance(fn, ast.AsyncFunctionDef):
                for c in sorted(_own_calls(fn), key=lambda c: c.lineno):
                    name = ast.unparse(c.func)
                    rel = path.relative_to(ROOT.parent).as_posix()
                    if BLOCKING.match(name) and (rel, name) not in FINE:
                        out.append(f"{rel}:{c.lineno} {fn.name} calls {name}")
    return out


def test_no_async_route_handler_calls_a_blocking_function_directly():
    assert _offenders() == [], "run these in starlette.concurrency.run_in_threadpool (or make the handler a plain def)"


def test_the_checker_itself_catches_a_blocking_call(tmp_path, monkeypatch):
    """The scan must see a bad handler: it is run on a throwaway file."""
    bad = tmp_path / "gitaway"
    (bad / "pages").mkdir(parents=True)
    (bad / "pages" / "x.py").write_text("async def h(r):\n    return safefetch.fetch('u')\n")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", bad)
    assert _offenders() == ["gitaway/pages/x.py:2 h calls safefetch.fetch"]


@pytest.fixture
def live():
    from main import app
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


def test_healthz_answers_at_once_while_a_creators_slow_blog_is_being_fetched(live, monkeypatch):
    from gitaway import ai, safefetch
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model())
    monkeypatch.setattr(safefetch, "RESOLVER", lambda host: ["93.184.216.34"])

    def slow(url, ip, timeout, kind):
        time.sleep(2.0)
        return page()
    monkeypatch.setattr(safefetch, "TRANSPORT", slow)
    creator = httpx.Client(base_url=live, timeout=20)
    assert creator.post("/signin", data={"email": EMAILS["ari"], "next": "/", "intent": "save"}).status_code in (200, 303)
    result = {}
    t = threading.Thread(target=lambda: result.update(r=creator.post("/creators/import", data={"do": "draft", "link": "https://blog.example.com/p"}, follow_redirects=False)))
    t.start()
    time.sleep(0.5)       # the slow fetch is now in flight
    started = time.monotonic()
    ok = httpx.get(live + "/healthz", timeout=10)
    quick = time.monotonic() - started
    t.join(15)
    assert ok.status_code == 200 and quick < 0.5, f"/healthz took {quick:.2f}s while a fetch was in flight"
    assert result["r"].status_code == 303      # and the draft still came out


def test_healthz_answers_at_once_while_a_blogs_sitemap_is_being_fetched_for_the_batch_picker(live, monkeypatch):
    """F-190: scanning a blog's sitemap goes through the thread pool too."""
    from gitaway import ai, safefetch
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model())
    monkeypatch.setattr(safefetch, "RESOLVER", lambda host: ["93.184.216.34"])

    def slow(url, ip, timeout, kind):
        time.sleep(2.0)
        return 200, {"content-type": "application/xml"}, b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://blog.example.com/a-trip-guide</loc></url></urlset>'
    monkeypatch.setattr(safefetch, "TRANSPORT", slow)
    creator = httpx.Client(base_url=live, timeout=20)
    assert creator.post("/signin", data={"email": EMAILS["ari"], "next": "/", "intent": "save"}).status_code in (200, 303)
    result = {}
    t = threading.Thread(target=lambda: result.update(r=creator.post("/creators/drafts/scan", data={"site": "https://blog.example.com"})))
    t.start()
    time.sleep(0.5)
    started = time.monotonic()
    ok = httpx.get(live + "/healthz", timeout=10)
    quick = time.monotonic() - started
    t.join(15)
    assert ok.status_code == 200 and quick < 0.5, f"/healthz took {quick:.2f}s while a sitemap fetch was in flight"
    assert result["r"].status_code == 200 and "a-trip-guide" in result["r"].text
