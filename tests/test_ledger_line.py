"""F-031: the cost ledger is one slim line in the top bar, with a breakdown popover and a pill state."""
import re

from gitaway import catalog


def bar_html(client, url="/plan"):
    h = client.get(url).text
    start = h.index('class="ws-bar"')
    return h[start:h.index('id="ws-grid"')]


def test_ledger_lives_in_the_top_bar_and_the_old_band_is_gone(client):
    h = client.get("/plan").text
    bar = bar_html(client)
    assert 'class="ws-ledger"' in bar and 'id="ws-book"' in bar and 'id="ws-total"' in bar
    assert h.count('class="ws-ledger"') == 1
    assert 'id="ws-details"' not in h and "ws-details-toggle" not in h  # the phone's expand toggle is replaced by the popover


def test_line_shows_flight_stay_car_and_the_total_on_their_own_elements(client):
    bar = bar_html(client)
    for lane, cents in (("flight", "$1,236"), ("stay", "$1,540"), ("car", "$312")):
        assert re.search(r'data-line-price="%s"[^>]*>%s<' % (lane, re.escape(cents)), bar)
    assert re.search(r'id="ws-total"[^>]*>\$3,088<', bar)


def test_total_is_a_button_that_controls_a_closed_popover(client):
    bar = bar_html(client)
    total = re.search(r"<button[^>]*id=\"ws-total\"[^>]*>", bar).group(0)
    assert 'aria-expanded="false"' in total and 'aria-controls="ws-pop"' in total and 'aria-haspopup="dialog"' in total
    pop = re.search(r"<div[^>]*id=\"ws-pop\"[^>]*>", bar).group(0)
    assert "hidden" in pop and 'role="dialog"' in pop


def test_popover_has_the_itemized_lines_the_stay_sub_line_and_the_hint(client):
    bar = bar_html(client)
    pop = bar[bar.index('id="ws-pop"'):]
    assert 'data-slot="flight"' in pop and 'data-slot-price="car"' in pop
    assert re.search(r'data-slot-sub="stay"[^>]*>[^<]+<', pop)  # rooms and add-ons, from the server
    assert re.search(r'id="ws-delta"[^>]*>\$916 more than the cheapest combo<', pop)
    cheap = bar_html(client, "/plan?f=f4&h=h3&c=c1")
    assert re.search(r'id="ws-delta"[^>]*>The cheapest combination<', cheap)


def test_stay_sub_line_follows_rooms_and_addons_in_the_url(client):
    st = catalog.stay_pick("h1", "ok2", "bf")
    bar = bar_html(client, "/plan?h=h1&rooms=ok2&add=bf")
    assert st.summary in bar
    assert catalog.money(catalog.quote("f1", "h1", "c1", st).total_cents) in bar


def test_book_link_keeps_signin_and_pay_hrefs(client):
    assert 'href="/signin?next=' in bar_html(client)


def test_css_reclaims_the_band_and_pill_respects_reduced_motion():
    css = open("assets/css/workspace.css").read()
    assert ".ws-ledger.is-pill" in css
    reduced = css[css.rindex("prefers-reduced-motion"):]
    assert ".ws-ledger" in reduced and "transition: none" in reduced
    assert not re.search(r"\.ws-ledger \{[^}]*min-height: 7\.25rem", css)


def test_script_swaps_figures_and_never_adds_them():
    js = open("assets/js/workspace.js").read()
    assert "data-line-price" in js and "is-pill" in js and "ws-pop" in js
    assert not re.search(r"parseFloat|parseInt|Number\(\s*[^)]*(price|total)", js, re.I)


def test_line_tooltips_name_the_picked_offers_and_the_script_keeps_them_current(client):
    assert 'title="Skylark Air 214"' in bar_html(client)
    assert 'title="Skylark Air 902"' in bar_html(client, "/plan?f=f4")
    assert ".title = s.name" in open("assets/js/workspace.js").read()  # a pick updates the tooltip too


def test_total_changes_are_announced_by_a_live_region(client):
    bar = bar_html(client)
    assert re.search(r'<span[^>]*id="ws-total-live"[^>]*aria-live="polite"|<span[^>]*aria-live="polite"[^>]*id="ws-total-live"', bar)
    assert re.search(r'id="ws-total-live"[^>]*>[^<]*\$3,088', bar)
    assert "ws-total-live" in open("assets/js/workspace.js").read()


def test_pill_state_relabels_the_total_button():
    js = open("assets/js/workspace.js").read()
    assert "Show cost line" in js and "aria-haspopup" in js
