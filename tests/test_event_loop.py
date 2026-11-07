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
BLOCKING = re.compile(r"^(ai\.(call_json|transcribe)|safefetch\.fetch|importsource\.(gather|offline)|robots\.check|blogscan\.(discover|sample)|(dj|draftjobs)\.\w+|(pfm|planforme)\.\w+|intake_page|stripe\.[\w.]+|(cd|creatordraft)\.\w+|(cc|creatorclaim)\.draft|admin\.admin_page|expedia\.pdf_text|geo\.\w+|(gp|geopack)\.(build|fetch_shapes|fetch_dem|terrarium|transport|render|ensure|drain|trip_points|needed)|weather\.(forecast|trip_weather)|(plan\.)?(workspace|weather_pane)|calendar_view|forks_page|photos\.\w+|time\.sleep|requests\.\w+|urllib\.\w+|httpx\.\w+|_read)$")
# One-row reads and writes in the local SQLite file are fine on the loop; these are the only listed calls that are.
FINE = {("gitaway/pages/creatorimport.py", "cd.get"), ("gitaway/pages/creatordrafts.py", "cd.mode"), ("gitaway/pages/creatordrafts.py", "dj.remaining"), ("gitaway/pages/planforme.py", "pfm.standin"), ("gitaway/pages/planforme.py", "pfm.offered")}      # (standin, offered: environment checks, no database)


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


def test_the_checker_flags_what_can_wait_on_met_and_only_that(tmp_path, monkeypatch):
    """F-203: asking MET Norway is a network call, and so is drawing a page that shows a trip's weather; weather's pure helpers are not."""
    bad = tmp_path / "gitaway"
    (bad / "pages").mkdir(parents=True)
    calls = ["weather.forecast(1, 2)", "weather.trip_weather(r)", "weather_pane(r)", "plan.weather_pane(r)", "calendar_view(r)", "forks_page(r)", "workspace(r)",
             "plan.workspace(r)", "weather.sample(r)", "weather.notes(r)", "weather.normal_day(r, r)"]
    src = "".join(f"async def h{i}(r):\n    return {c}\n\n" for i, c in enumerate(calls)) + "async def ok(r):\n    return await run_in_threadpool(lambda: weather.trip_weather(r))\n"
    (bad / "pages" / "x.py").write_text(src)
    monkeypatch.setattr(sys.modules[__name__], "ROOT", bad)
    assert [o.split(" calls ")[1] for o in _offenders()] == [c.split("(")[0] for c in calls[:8]]


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


def test_healthz_answers_at_once_while_a_slow_forecast_is_asked_for_the_plan_page(live, monkeypatch):
    """F-203: the /plan weather pane may wait on MET Norway (a plain def handler, so in the thread pool): the site answers meanwhile."""
    from gitaway import weather
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    asked = []

    def slow(url, headers, timeout):
        asked.append(url)
        time.sleep(2.0)
        raise OSError("slow, then down")
    monkeypatch.setattr(weather, "TRANSPORT", slow)
    result = {}
    t = threading.Thread(target=lambda: result.update(r=httpx.get(live + "/plan?d=2026-10-02&r=2026-10-04&a=2", timeout=20)))   # two days after "today" (conftest)
    t.start()
    time.sleep(0.5)
    started = time.monotonic()
    ok = httpx.get(live + "/healthz", timeout=10)
    quick = time.monotonic() - started
    t.join(15)
    assert asked and ok.status_code == 200 and quick < 0.5, f"/healthz took {quick:.2f}s while a forecast was being asked for"
    assert result["r"].status_code == 200 and "Typical early October · not a forecast yet" in result["r"].text    # MET down: typical weather, labelled
