"""The booking workspace at /plan: server-rendered ledger, URL-held picks, catalog-derived totals."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent

from gitaway import catalog
from gitaway.pages import placeholders, plan


def test_default_ledger_shows_the_default_pick_total(client):
    r = client.get("/plan")
    assert r.status_code == 200
    assert catalog.money(catalog.quote("f1", "h1", "c1").total_cents) == "$3,088"
    assert "$3,088" in r.text
    assert "$1,236" in r.text and "$1,540" in r.text and "$312" in r.text


def test_cheapest_combination_from_the_url(client):
    r = client.get("/plan?f=f4&h=h3&c=c1")
    assert "$2,172" in r.text and "The cheapest flight, stay and car" in r.text


def test_default_total_is_flagged_as_more_than_cheapest(client):
    assert "$916 more than the cheapest flight, stay and car" in client.get("/plan").text


def test_bad_or_wrong_lane_ids_fall_back_to_the_default(client):
    assert "$3,088" in client.get("/plan?f=nope&h=zzz&c=").text
    assert "$3,088" in client.get("/plan?f=h1&h=c2&c=f3").text  # ids from the wrong lane
    assert plan.resolve_pick("f4", "bogus", "c2") == ("f4", "h1", "c2")  # a good lane keeps its pick
    assert plan.resolve_pick(None, None, None) == ("f1", "h1", "c1")
    assert re.search(r'id="ws-total"[^>]*>\$2,906<', client.get("/plan?f=f4&h=bogus&c=c2").text)


def test_every_offer_renders_with_its_catalog_price(client):
    h = client.get("/plan").text
    assert len(re.findall(r'data-lane="flight"', h)) == 5
    assert len(re.findall(r'data-lane="stay"', h)) == 3
    assert len(re.findall(r'data-lane="car"', h)) == 2
    assert h.count('aria-pressed="true" data-lane') == 3
    for o in [*catalog.offers("flight"), *catalog.offers("stay"), *catalog.offers("car")]:
        assert o.name.replace("&", "&amp;") in h
        assert catalog.money(o.price_cents) in h


def test_stays_show_the_area_photo_captioned_as_the_area(client):
    h = client.get("/plan").text
    assert "/assets/photos/santa-monica-beach-pier.jpg" in h
    assert "Santa Monica area" in h and "Venice area" in h
    assert "Tidewater</figcaption>" not in h


def test_burbank_flight_is_shown(client):
    h = client.get("/plan").text
    assert "Pacific Hop 312" in h and "Lands BUR" in h


def test_book_link_carries_next_and_pay_intent(client):
    h = client.get("/plan?f=f2&h=h2&c=c2").text
    href = re.search(r'id="ws-book"[^>]*href="(/signin\?[^"]+)"', h) or re.search(r'href="(/signin\?[^"]+)"[^>]*id="ws-book"', h)
    href = href.group(1).replace("&amp;", "&")
    qs = parse_qs(urlparse(href).query)
    assert qs["intent"] == ["pay"]
    assert qs["next"] == ["/plan/pay?f=f2&h=h2&c=c2"]
    assert "%2Fplan%2Fpay" in href  # url-encoded


def test_quote_route_matches_catalog_for_every_combination(client):
    from itertools import product
    combos = list(product(*(catalog.offers(k) for k in ("flight", "stay", "car"))))
    assert len(combos) == 30
    for f, s, c in combos:
        entry = client.get(f"/plan/quote?f={f.id}&h={s.id}&c={c.id}").json()["ledger"]
        q = catalog.quote(f.id, s.id, c.id)
        assert entry["total"] == catalog.money(q.total_cents)
        assert (entry["delta"] == "The cheapest flight, stay and car") == (q.above_cheapest_cents == 0)
        assert entry["book"].startswith("/signin?next=%2Fplan%2Fpay%3Ff%3D") and entry["book"].endswith("&intent=pay")
        assert entry["url"] == f"/plan?f={f.id}&h={s.id}&c={c.id}"


def test_the_page_embeds_no_combination_table(client):
    raw = re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', client.get("/plan").text, re.S).group(1)
    assert "quotes" not in json.loads(raw)


def test_placeholder_is_gone_and_brand_is_gitaway(client):
    assert "/plan" not in placeholders.PLACEHOLDERS
    h = client.get("/plan").text
    assert "TravelOS" not in h and "Opening soon" not in h
    assert "/assets/css/workspace.css" in h and "/assets/js/workspace.js" in h
    assert client.get("/assets/js/workspace.js").status_code == 200
    assert client.get("/assets/css/workspace.css").status_code == 200
    assert "workspace.css" not in client.get("/").text


def _pane(h, key):
    m = re.search(r'<section[^>]*data-pane="%s".*?</section>' % key, h, re.S)
    assert m, key
    return m.group(0)


def test_context_column_has_four_numbered_panes(client):
    h = client.get("/plan").text
    assert 'data-pane="context"' not in h
    for key, num, title in [("weather", 4, "Weather"), ("map", 5, "Map"), ("news", 6, "Happening &amp; news"),
                            ("community", 7, "Trips others loved")]:
        pane = _pane(h, key)
        assert re.search(rf'<kbd[^>]*class="ws-key[^>]*>{num}</kbd>', pane)
        assert f'data-focus="{key}"' in pane and f'data-expand="{key}"' in pane and title in pane
        assert f'aria-keyshortcuts="{num}"' in pane


def test_hint_and_key_map_cover_seven_panes(client):
    h = client.get("/plan").text
    assert "Press 1–7 to focus a pane" in h and "1–3 to focus" not in h
    js = client.get("/assets/js/workspace.js").text
    for name in ("weather", "map", "news", "community"):
        assert name in js


def test_weather_shows_the_five_trip_days_in_fahrenheit(client):
    pane = _pane(client.get("/plan").text, "weather")
    assert re.findall(r'class="ws-temp"[^>]*>(\d+)°', pane) == ["75", "73", "70", "72", "77"]
    assert "Fri 16" in pane and "Tue 20" in pane and "Sample" in pane


def test_news_pane_lists_sample_events_and_local_news(client):
    pane = _pane(client.get("/plan").text, "news")
    assert 2 <= pane.count('class="ws-event"') <= 3
    assert 1 <= pane.count('class="ws-news"') <= 2
    assert "Sample" in pane


def test_community_pane_forks_the_sample_itinerary(client):
    pane = _pane(client.get("/plan").text, "community")
    assert "Sun, tacos &amp; tide pools" in pane and "312 forks" in pane
    assert 'href="/signin?next=/trips/sun-tacos-and-tide-pools&amp;intent=fork"' in pane
    assert "Fork" in pane


def test_map_shows_area_pin_airports_and_landmark(client):
    m = _pane(client.get("/plan").text, "map")
    assert "data-map-pin" in m and "Santa Monica" in m
    for label in ("LAX", "BUR", "Griffith Park"):
        assert label in m
    assert "3 min walk to the beach" in m and "The Tidewater" in m
    assert "schematic" in m.lower()


def test_changing_the_stay_moves_the_map_pin(client):
    m = _pane(client.get("/plan?h=h2").text, "map")
    assert "data-map-pin" in m and "Venice" in m and "Casa Palmera" in m
    assert "8 min walk to the beach" in m and "Tidewater" not in m


def test_map_data_for_every_stay_is_embedded(client):
    h = client.get("/plan").text
    raw = re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', h, re.S).group(1)
    maps = json.loads(raw)["map"]
    assert set(maps) == {"h1", "h2", "h3"}
    for m in maps.values():
        assert {"x", "y", "bx", "by", "label", "caption"} <= set(m)
    assert "Casa Palmera" in maps["h2"]["caption"] and maps["h2"]["label"] == "Venice"


def test_context_colours_are_tokens():
    css = open(ROOT / "assets/css/workspace.css").read()
    ctx = css[css.index("/* Context panes */"):css.index("/* Tablet")]
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", ctx)


def test_tablet_shows_context_below_lanes_instead_of_hiding_it():
    css = open(ROOT / "assets/css/workspace.css").read()
    tablet = css[css.index("/* Tablet"):css.index("/* Phone")]
    assert ".ws-context { display: none" not in tablet


def test_every_pick_has_offer_data_and_the_current_pick(client):
    h = client.get("/plan").text
    raw = re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', h, re.S).group(1)
    data = json.loads(raw)
    picks = re.findall(r'data-pick="([^"]+)"', h)
    assert len(picks) == 10 and set(picks) <= set(data["offers"])
    assert data["pick"] == {"f": "f1", "h": "h1", "c": "c1", "rooms": "cq1", "add": "", "fare": "", "bags": ""} and data["base"] == "/plan?f=f1&h=h1&c=c1"


def test_workspace_is_a_main_landmark_the_skip_link_targets(client):
    h = client.get("/plan").text
    assert h.count('id="main"') == 1
    assert re.search(r'<main[^>]*id="main"', h) and 'href="#main"' in h


def test_json_is_escaped_against_script_breakout():
    from gitaway.pages.plan import script_json
    out = script_json({"x": "</script><b>"})
    assert "<" not in out
    assert json.loads(out) == {"x": "</script><b>"}


PANE_KEYS = ("flights", "stays", "cars", "weather", "map", "news", "community")


def test_expanded_rule_makes_every_pane_full_width():
    css = open(ROOT / "assets/css/workspace.css").read()
    for key in PANE_KEYS:
        rule = re.search(r'[^{}]*\[data-expanded="%s"\][^{}]*\{\s*grid-template-columns:\s*1fr;\s*\}' % key, css)
        assert rule, key


def test_key_map_in_js_is_exact(client):
    js = client.get("/assets/js/workspace.js").text
    m = re.search(r"var PANES = \{([^}]*)\}", js).group(1)
    got = dict(re.findall(r"(\d)\s*:\s*'(\w+)'", m))
    assert got == {str(i + 1): k for i, k in enumerate(PANE_KEYS)}


def test_no_sample_prefix_in_titles_but_one_caption_per_pane(client):
    from gitaway import context
    for e in context.EVENTS:
        assert "sample" not in e.title.lower()
    for n in context.NEWS:
        assert "sample" not in n.title.lower()
    h = client.get("/plan").text
    for key in ("weather", "news"):
        assert _pane(h, key).count('class="ws-sample"') == 1


def test_weather_matches_itinerary_days():
    from gitaway import context, itineraries
    t = itineraries.get("sun-tacos-and-tide-pools")
    temps = [int(d.weather.split("°")[0]) for d in t.days]
    assert temps == [w.temp_f for w in context.WEATHER]


def test_map_data_has_pin_coordinates_for_every_stay(client):
    h = client.get("/plan").text
    raw = re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', h, re.S).group(1)
    maps = json.loads(raw)["map"]
    for o in catalog.offers("stay"):
        m = maps[o.id]
        assert all(isinstance(m[k], int) and 0 <= m[k] <= 320 for k in ("x", "bx"))
        assert all(isinstance(m[k], int) and 0 <= m[k] <= 150 for k in ("y", "by"))
    js = client.get("/assets/js/workspace.js").text
    for k in ("m.x", "m.y", "m.bx", "m.by", "m.label", "m.caption"):
        assert k in js


def test_context_column_is_one_fr_and_tip_gap_removed_on_tablet():
    css = open(ROOT / "assets/css/workspace.css").read()
    for sel in ('.ws-grid {', '.ws-grid[data-focus="stays"] {', '.ws-grid[data-focus="cars"] {'):
        line = css[css.index(sel):].split("\n")[0]
        assert re.search(r"minmax\(0, 1fr\);", line.split("grid-template-columns:")[1]), sel
    first = re.search(r"\.ws-grid \{[^}]*grid-template-columns: ([^;]*);", css).group(1)
    assert first.split(" minmax")[-1].strip() == "(0, 1fr)"
    tablet = css[css.index("/* Tablet"):css.index("/* Phone")]
    assert ".ws-tip" in tablet and "margin-top: 0" in tablet


def test_fork_link_uses_the_itinerary_view_helper():
    src = open(ROOT / "gitaway/pages/plan.py").read()
    assert "fork_href" in src and "intent=fork" not in src


def test_tablet_ledger_takes_its_own_row_and_never_truncates():
    css = open(ROOT / "assets/css/workspace.css").read()
    tablet = css[css.index("/* Tablet"):css.index("/* Phone")]
    assert re.search(r"\.ws-ledger \{[^}]*flex: 1 1 100%", tablet)
    assert not re.search(r"\.ws-slot-name \{[^}]*(nowrap|ellipsis)", css)
    assert re.search(r"\.ws-badge \{[^}]*white-space: nowrap", css)
    assert re.search(r"\.ws-row \.ws-price \{[^}]*order: 2", tablet)
