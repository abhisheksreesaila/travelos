"""F-217: the trip grid's pages. /plan/grid draws every flight against every stay from the source (the sample catalog on the showcase); /plan/grid/trip is the
square that was chosen, booked on the partner's site. Both are plain links first, and neither exists off the showcase until there is a real source."""
import json
import re
from html import unescape

import pytest

from gitaway import catalog, weather
from gitaway.pages import tripgrid as page

GRID = "/plan/grid"
LA = catalog.sample_trip("la")


def cells(html):
    """{(flight id, stay id): (tone, total, small line)} as drawn."""
    found = re.findall(r'<a href="[^"]*" data-cell="([^|"]+)\|([^"]+)"[^>]*class="tg-cell is-(\w+)"[^>]*>\s*<span class="tg-total">([^<]+)</span>\s*<span class="tg-sub">([^<]+)</span>', html)
    return {(f, h): (tone, total, unescape(sub)) for f, h, tone, total, sub in found}


def data(html):
    return json.loads(re.search(r'<script type="application/json" id="tg-data">(.*?)</script>', html, re.S).group(1))


def slot(html, name):
    return unescape(re.search(rf'data-slot="{name}"[^>]*>([^<]*)<', html).group(1))


def test_a_square_for_every_flight_and_stay_with_the_two_prices_added(client):
    html = client.get(GRID).text
    drawn = cells(html)
    flights, stays = catalog.offers("flight", LA), catalog.offers("stay", LA)
    assert len(drawn) == len(flights) * len(stays) == 15
    for f in flights:
        for h in stays:
            assert drawn[(f.id, h.id)][1] == catalog.money(f.price_cents + h.price_cents)
    low = min(((f.price_cents + h.price_cents, f.id, h.id) for f in flights for h in stays))
    assert [k for k, v in drawn.items() if v[0] == "best"] == [(low[1], low[2])] and drawn[(low[1], low[2])][2] == "lowest"
    assert "Preview: sample prices, nothing is booked." in html
    assert "never takes payment" in html


def test_the_panel_starts_on_the_lowest_square_and_on_the_pick_once_there_is_one(client):
    html = client.get(GRID).text
    low = min(c["c"] for c in data(html)["cells"].values())
    assert slot(html, "title") == "Lowest · all in" and slot(html, "total") == catalog.money(low)
    html = client.get(GRID + "?f=f3&h=h1").text
    assert cells(html)[("f3", "h1")][0] == "mine" and cells(html)[("f3", "h1")][2] == "your pick"
    assert slot(html, "title") == "Your pick · all in" and slot(html, "total") == catalog.money(catalog.offer("f3").price_cents + catalog.offer("h1").price_cents)
    assert 'href="/plan/grid/trip?to=la' in html and "f=f3&amp;h=h1" in html


def test_picking_only_a_flight_shows_its_cheapest_square_and_marks_its_column(client):
    html = client.get(GRID + "?f=f3").text
    assert "mine" not in {v[0] for v in cells(html).values()}
    assert slot(html, "flight").startswith("11:15 AM")
    assert re.search(r'data-f="f3"[^>]*aria-current="true"', html) or re.search(r'aria-current="true"[^>]*data-f="f3"', html)
    assert client.get(GRID + "?f=nope&h=h1").status_code == 200      # an id the source does not have is dropped, not an error


def test_a_budget_greys_the_squares_over_it_and_says_by_how_much(client):
    html = client.get(GRID + "?b=2500").text
    drawn = cells(html)
    for key, c in data(html)["cells"].items():
        tone, _, sub = drawn[tuple(key.split("|"))]
        if c["c"] > 250_000:
            assert tone == "bad" and sub == f"over by {catalog.money(c['c'] - 250_000)}"
        else:
            assert tone in ("best", "plain")
    assert "under $2,500" in html
    assert "any budget" in client.get(GRID + "?b=12").text            # not a budget the slider has: none


def test_ease_ranks_by_the_first_day_of_whoever_is_going(client):
    html = client.get(GRID + "?lens=ease").text                        # the sample family has kids
    drawn = cells(html)
    best = [k for k, v in drawn.items() if v[0] == "best"]
    assert len(best) == 1 and drawn[best[0]][2].startswith("easiest · ")
    assert all(v[2].endswith("day") for v in drawn.values())
    assert slot(html, "title") == "Easiest · all in" and slot(html, "k0") == "Up at"
    html = client.get(GRID + "?lens=ease&who=pet&pet=dog&senior=Grandma").text
    assert slot(html, "k0") == "Stay" and "The dog’s day" in html and "Grandma’s day" in html
    assert "with Grandma and the dog," in html


def test_with_nobody_to_ease_the_day_for_there_is_no_ease(client):
    html = client.get(GRID + "?a=2&d=2026-10-16&r=2026-10-20&lens=ease").text
    assert "data-lens=\"ease\"" not in html.replace('data-lens="price"', "") or 'id="tg-grid" data-lens="price"' in html
    assert "tg-seg" not in html and "tg-daycard" not in html
    assert {v[0] for v in cells(html).values()} <= {"best", "plain"}


def test_the_strip_of_days_moves_the_trip_and_never_into_the_past(client):
    html = client.get(GRID + "?d=2026-10-02&r=2026-10-06&a=2&k=4,7").text
    days = re.findall(r'class="tg-day[^"]*"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="tg-day', html)
    hrefs = [unescape(a or b) for a, b in days]
    assert len(hrefs) == page.DAYS_SHOWN
    assert "d=2026-09-30&r=2026-10-04" in hrefs[0]                     # today (fixed in tests), the same four nights
    assert not any("d=2026-09-2" in h for h in hrefs)
    assert "One night more" in html and "r=2026-10-07" in html and "One night fewer" in html and "r=2026-10-05" in html


def test_a_shown_temperature_always_comes_with_its_source(client):
    html = unescape(client.get(GRID).text)
    s = page.state()
    tw = page.strip_weather(s, page.strip_days(s))
    assert any(tw.days) and "tg-deg" in html                           # NOAA's normals for Los Angeles ship with the app
    notes = weather.notes(tw)
    assert notes and all(text in html for text, _ in notes)
    assert "not a forecast yet" in html


def test_a_retyped_sentence_lands_on_its_plain_address(client):
    r = client.get(GRID, params={"q": "A family of 4 with Grandma and the dog, SFO to San Diego, Oct 16 to 20, under $3,000."}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/plan/grid?to=sd&d=2026-10-16&r=2026-10-20&a=2&k=8%2C8&home=SFO&senior=Grandma&pet=dog&b=3000"
    html = client.get(r.headers["location"]).text
    assert "A family of 4" in html and "with Grandma and the dog," in html and "SFO to San Diego," in html and "under $3,000" in html


def test_a_place_the_sample_has_no_offers_for_goes_to_the_honest_lanes(client):
    r = client.get(GRID, params={"q": "2 adults to Lisbon, Oct 16 to 20"}, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/plan?place=Lisbon&d=2026-10-16&r=2026-10-20&a=2")


@pytest.mark.parametrize("words, said", [("somewhere warm next month", "Say where to"), ("to San Diego soon", "Say when"), ("to San Diego, Oct 1 to Oct 3 <b>", None)])
def test_a_sentence_it_cannot_read_says_what_is_missing_and_keeps_the_words(client, words, said):
    r = client.get(GRID, params={"q": words}, follow_redirects=False)
    if said is None:
        assert r.status_code == 303 and "<" not in r.headers["location"]
        return
    assert r.status_code == 200 and said in r.text and 'aria-invalid="true"' in r.text
    assert f'value="{words}"' in r.text


def test_words_from_the_address_are_cleaned_and_escaped(client):
    html = client.get(GRID, params={"senior": "<script>alert(1)</script>", "pet": "dragon", "near": '"><img src=x>', "mi": "9999"}).text
    body = html.split("<main", 1)[1]                                   # the shell's own tags repeat the address, escaped
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "with script alert script," in body and "dragon" not in body and "9999" not in body


def test_the_chosen_trip_is_booked_on_the_partners_sites(client):
    html = client.get(GRID + "/trip?f=f1&h=h2&pet=dog").text
    assert 'href="/go/f1?to=la"' in html and "Book on Aviasales" in html
    assert 'href="/go/h2?to=la"' in html and "Book on Klook" in html
    assert catalog.money(catalog.offer("f1").price_cents + catalog.offer("h2").price_cents) in html
    assert "Takes pets" in html and "Kids’ day" in html
    assert "Back to the grid" in html and 'href="/plan/grid?to=la' in html
    swaps = re.findall(r'class="tg-swap-s">([^<]+)<', html)
    cheapest = min(o.price_cents for o in catalog.offers("flight", LA))
    assert swaps and swaps[0] == f"{catalog.money(catalog.offer('f1').price_cents - cheapest)} less"


def test_the_cheapest_trip_has_nothing_cheaper_to_swap(client):
    flights, stays = catalog.offers("flight", LA), catalog.offers("stay", LA)
    f, h = min(flights, key=lambda o: o.price_cents), min(stays, key=lambda o: o.price_cents)
    assert "Nothing cheaper on these dates." in client.get(f"{GRID}/trip?f={f.id}&h={h.id}").text


def test_a_trip_page_without_a_real_square_goes_back_to_the_grid(client):
    r = client.get(GRID + "/trip?f=f1&h=nope&b=3000", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/plan/grid?") and "nope" not in r.headers["location"] and "b=3000" in r.headers["location"]


@pytest.mark.parametrize("path", [GRID, GRID + "/trip?f=f1&h=h1", GRID + "?q=to+San+Diego,+Oct+16+to+20"])
def test_off_the_showcase_there_is_no_grid(client, monkeypatch, path):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get(path, follow_redirects=False).status_code == 404


def test_the_page_hands_the_script_the_same_squares_it_drew(client):
    html = client.get(GRID + "?senior=Grandma&b=2600").text
    d, drawn = data(html), cells(html)
    assert set(d["cells"]) == {"|".join(k) for k in drawn}
    assert d["budget"] == 260_000 and d["lens"] == "price" and d["whos"] == ["kids", "senior"] and d["who"] == "kids"
    assert drawn[tuple(d["low"].split("|"))][0] == "best"
    assert all(set(c["d"]) == {"kids", "senior"} for c in d["cells"].values())
    assert "</script" not in json.dumps(d)


@pytest.mark.parametrize("query", ["?b=²", "?b=1²00", "?near=x&mi=²", "/trip?f=f1&h=h1&b=²", "?a=²&k=²&d=²", "?b=%00&senior=%00&to=%00"])
def test_digits_that_are_not_ascii_are_just_not_a_number(client, query):
    assert client.get(GRID + query).status_code == 200


def test_the_panel_names_what_its_square_is_the_lowest_of(client):
    assert slot(client.get(GRID + "?f=f3").text, "title") == "Lowest for this flight · all in"
    assert slot(client.get(GRID + "?h=h1&lens=ease").text, "title") == "Easiest for this stay · all in"


def test_sample_prices_are_called_sample_on_the_grid_itself_and_on_the_trip(client):
    html = client.get(GRID).text
    assert html.count(page.SAMPLE) == 2 and 'class="tg-corner"><span class="tg-sample">' in html.replace("\n", "").replace("  ", "")
    assert page.SAMPLE in client.get(GRID + "/trip?f=f1&h=h1").text


def test_a_party_too_big_to_book_is_said(client):
    r = client.get(GRID, params={"q": "family of 12 to San Diego, Oct 16 to 20"}, follow_redirects=False)
    assert r.status_code == 200 and "up to 8 travelers" in r.text and 'aria-invalid="true"' in r.text


def test_whose_day_is_marked_for_a_screen_reader_in_both_places(client):
    html = client.get(GRID + "?senior=Grandma&who=senior").text
    marked = re.findall(r'<a [^>]*data-who="(\w+)"[^>]*aria-current="true"|<a [^>]*aria-current="true"[^>]*data-who="(\w+)"', html)
    assert [a or b for a, b in marked] == ["senior", "senior"]
