"""The Tahoe trip in a browser (F-201): the founder's trip seeded the way the app makes one (the import page's route, the plans, the map cache through gitaway.geo,
the geo pack through gitaway.geopack), the clock at the design's "now", and a page opened on the cockpit at a viewport, light or dark."""

from datetime import date

from gitaway import catalog, familydb, geo, geopack, tripcal as cal, tripgeo
from tests import tahoe
from tests.test_signin import person
from tests_browser.helpers import DESKTOP

# What F-200 ships for the dark mode of the shared tokens (Direction A, docs/design/reskin/README.md): injected so the cockpit's dark mode can be checked before it merges.
DIRECTION_A_DARK = """:root { --paper: #000000; --card: #1C1C1F; --ink: #F5F5F7; --ink-2: #A1A1AA; --ink-3: #8E8E98; --line: #2E2E33; --hairline: rgba(255,255,255,.10);
  --hairline-2: rgba(255,255,255,.16); --paper-2: #2A2A2E; color-scheme: dark; } body { background: #000000; }"""


def seed(base_url, ctx, monkeypatch, *, pack=True, now=tahoe.NOW, plans=True):
    """Sign in as Ari, import the Tahoe trip, add its plans, fill the map cache and (with `pack`) build its geo pack; pin the clock to `now`."""
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    r = ctx.request.post(f"{base_url}/trips/import/save", form={"text": tahoe.TEMPLATE}, max_redirects=0)
    assert r.status in (302, 303), r.status
    me = person("ari")
    if plans:
        for day, s, e, title, kind in tahoe.PLANS:
            h1, m1 = map(int, s.split(":"))
            h2, m2 = map(int, e.split(":"))
            cal.add_activity(me, day=day, start=h1 * 60 + m1, end=h2 * 60 + m2, title=title, kind=kind)
    monkeypatch.setattr(geo, "fetch", tahoe.geo_fetch)
    with familydb.using(me) as db:
        for group in tripgeo.day_places(me):
            geo.warm(db, group, budget=30)
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    if pack:
        assert geopack.ensure(me) == "ready"
    else:
        monkeypatch.setattr(geopack, "TRANSPORT", lambda url, data=None, timeout=0: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(catalog, "now_utc", lambda: now)
    monkeypatch.setattr(catalog, "today", lambda: now.astimezone(catalog.TZ).date())
    return me


def open_cockpit(browser, base_url, monkeypatch, contexts, viewport=DESKTOP, dark=False, motion=False, path="/trip/cockpit", **kw):
    ctx = browser.new_context(viewport=viewport, reduced_motion="no-preference" if motion else "reduce", color_scheme="dark" if dark else "light")
    ctx.set_default_timeout(8000)
    contexts.append(ctx)
    seed(base_url, ctx, monkeypatch, **kw)
    page = ctx.new_page()
    if dark:
        page.add_init_script("document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.id = 'f200-dark'; s.textContent = %r; document.head.appendChild(s); });" % DIRECTION_A_DARK)
    page.goto(f"{base_url}{path}")
    page.wait_for_selector("#ck-paper[data-ready='1']")
    return page
