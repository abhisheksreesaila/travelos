"""Headless-browser fixtures (F-029). Run with `pixi run test-browser`; `pixi run test` never collects this folder.

The app runs in a background thread on a free port for the whole session and is stopped at the end.
Each test gets a fresh browser context (fresh session cookie) with reduced motion, so animations never slow a wait.
"""
import socket
import threading
import time
from datetime import date

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    """The demo's sample trip is in October 2026; keep "today" before it (same as tests/conftest.py)."""
    from gitaway import catalog
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 9, 30), raising=False)


@pytest.fixture(scope="session")
def base_url():
    from main import app
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def open_plan(browser, base_url):
    """open_plan(query="", viewport=DESKTOP) -> a page on /plan, scripts bound. Contexts are closed after the test."""
    contexts = []

    def open_plan(query="", viewport=DESKTOP):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.goto(f"{base_url}/plan{('?' + query) if query else ''}")
        page.wait_for_selector("#ws-grid[data-focus]")  # the script sets this when it binds
        return page

    yield open_plan
    for c in contexts:
        c.close()
