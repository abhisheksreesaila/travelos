"""F-025: Flights and Stays expand into a list sidebar plus a detail panel (server-rendered, JS only toggles)."""
import re

from gitaway import catalog


def _article(html, offer_id):
    m = re.search(r'<article[^>]*data-detail="%s"[^>]*>.*?</article>' % offer_id, html, re.S)
    assert m, offer_id
    return m.group(0)


def test_every_stay_and_flight_has_a_detail_panel_but_no_car_does(client):
    h = client.get("/plan").text
    for o in catalog.offers("stay") + catalog.offers("flight"):
        assert _article(h, o.id)
    assert 'data-detail="c1"' not in h


def test_stay_detail_shows_what_the_catalog_knows(client):
    h = client.get("/plan").text
    a = _article(h, "h1")
    o = catalog.offer("h1")
    for text in (o.name, o.headline, o.detail, o.rating, *o.tags, catalog.money(o.price_cents)):
        assert text in a, text
    assert "The area · Santa Monica" in a
    assert "santa-monica-beach-pier.jpg" in a
    assert "not the hotel" in a  # alt text says it is the area


def test_stay_without_an_area_photo_has_no_image_but_keeps_the_label(client):
    a = _article(client.get("/plan").text, "h3")
    assert "<img" not in a and "The area · Downtown" in a


def test_flight_detail_shows_out_and_back_times_from_minutes(client):
    a = _article(client.get("/plan").text, "f1")
    for t in ("8:05 AM", "9:32 AM", "2:10 PM", "3:37 PM"):
        assert t in a, t
    assert "SFO" in a and "LAX" in a and "Fri Oct 16" in a and "Tue Oct 20" in a
    assert "Skylark Air 214" in a and "Best nonstop" in a
    assert "1h 27m" in a


def test_detail_panels_leave_seams_for_the_next_tickets(client):
    h = client.get("/plan").text
    stay = _article(h, "h2")
    for seam in ("look-around", "rooms", "addons", "policy"):
        assert f'data-seam="{seam}"' in stay
    flight = _article(h, "f2")
    for seam in ("fares", "bags"):
        assert f'data-seam="{seam}"' in flight


def test_choose_bar_labels_follow_the_pick(client):
    h = client.get("/plan").text
    picked = _article(h, "h1")
    other = _article(h, "h2")
    assert re.search(r'data-choose="h1"[^>]*>\s*Chosen', picked)
    assert re.search(r'data-choose="h2"[^>]*>\s*Choose this stay', other)
    assert re.search(r'data-choose="f3"[^>]*>\s*Choose this flight', _article(h, "f3"))
    h2 = client.get("/plan?h=h2").text
    assert re.search(r'data-choose="h2"[^>]*>\s*Chosen', _article(h2, "h2"))


def test_list_cards_mark_your_pick(client):
    h = client.get("/plan").text
    assert h.count("ws-pickpill") >= 2  # one pill per expandable lane's card set
    assert 'aria-current' not in h  # nothing is open while the workspace is tiled


def test_tiled_by_default_keeps_old_urls_working(client):
    h = client.get("/plan?f=f4&h=h3&c=c3").text
    assert "data-expanded" not in h.split('id="ws-grid"')[1].split(">")[0]
    assert 'aria-expanded="false"' in h and 'aria-expanded="true"' not in h.split('class="ws-ledger"')[0]


def test_x_param_opens_the_split_view_on_the_current_pick(client):
    h = client.get("/plan?h=h2&x=stays").text
    grid = re.search(r'<div[^>]*id="ws-grid"[^>]*>', h).group(0)
    assert 'data-expanded="stays"' in grid
    assert re.search(r'data-expand="stays"[^>]*aria-expanded="true"|aria-expanded="true"[^>]*data-expand="stays"', h)
    assert "hidden" not in re.search(r'<article[^>]*data-detail="h2"[^>]*>', h).group(0)
    assert "hidden" in re.search(r'<article[^>]*data-detail="h1"[^>]*>', h).group(0)
    assert re.search(r'<button[^>]*data-pick="h2"[^>]*aria-current="true"|<button[^>]*aria-current="true"[^>]*data-pick="h2"', h)


def test_v_param_views_another_offer_without_changing_the_pick(client):
    h = client.get("/plan?x=flights&v=f3").text
    assert "hidden" not in re.search(r'<article[^>]*data-detail="f3"[^>]*>', h).group(0)
    assert "hidden" in re.search(r'<article[^>]*data-detail="f1"[^>]*>', h).group(0)
    assert "$3,088" in h  # f1/h1/c1 still the pick


def test_bad_x_or_v_is_ignored(client):
    g = lambda h: re.search(r'<div[^>]*id="ws-grid"[^>]*>', h).group(0)
    assert "data-expanded" not in g(client.get("/plan?x=cars").text)  # only flights and stays split
    assert "data-expanded" not in g(client.get("/plan?x=nope").text)
    h = client.get("/plan?x=stays&v=f1").text  # a flight id in the stays lane
    assert "hidden" not in re.search(r'<article[^>]*data-detail="h1"[^>]*>', h).group(0)


def test_expanded_panes_show_the_collapse_hint_and_button(client):
    h = client.get("/plan").text
    assert "back to workspace" in h
    assert 'aria-keyshortcuts="Escape"' in h


def test_js_and_css_contract(client):
    js = client.get("/assets/js/workspace.js").text
    css = open("assets/css/workspace.css").read()
    assert "prefers-reduced-motion" in js and "Escape" in js and "data-choose" in js.replace("dataset.choose", "data-choose")
    reduced = css[css.rindex("prefers-reduced-motion"):]
    assert "ws-detail-panel" in reduced and "animation: none" in reduced  # reduced motion swaps instantly
    assert "340px" in css


def test_phone_screen_is_list_until_an_offer_is_named(client):
    pane = lambda h: re.search(r'<section[^>]*data-pane="stays"[^>]*>', h).group(0)
    assert 'data-screen="list"' in pane(client.get("/plan?x=stays").text)
    assert 'data-screen="detail"' in pane(client.get("/plan?x=stays&v=h2").text)
