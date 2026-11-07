"""F-197 the offer that sells: /plan-for-me is the offer (the parent's outcome, the founding price, what you get, a founder note, the refund promise, four questions, the examples, one
button), the intake moved to /plan-for-me/start, three example plans at /plan-for-me/example/<slug> drawn like a delivered trip with "What to book and when", the checklist on a ready
order and in the delivered trip, and no "in minutes" anywhere while a person checks every plan."""

import re
from datetime import date, timedelta
from html import unescape

import pytest

from gitaway import catalog, planexamples as px, planfacts, planforme as pfm, tripcal
from tests.live_trips import live_trip
from tests.test_planforme import GOOD, buyer
from tests.test_signin import person, sign_in

OFFER = "/plan-for-me"


def text_of(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


# ---- the offer -------------------------------------------------------------------------------------------------------

def test_the_offer_sells_the_outcome_with_everything_a_parent_needs_to_decide(client, monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "1")
    html = client.get(OFFER).text
    t = text_of(html)
    assert re.search(r"<h1[^>]*>.*calm Disneyland trip.*kids", html, re.S)
    assert "$29 for the first 10 families, then $49" in t
    for line in ("Day-by-day plan in your family's shared planner", "Ride order and rest breaks matched to your kids' ages and heights", "What to book and when", "Booking links"):
        assert line in t, line
    assert "We just did Disneyland with our kids" in t and "I check every plan before it reaches you" in t
    assert pfm.PROMISE in t
    assert html.count('class="pf-q"') == 4
    for slug in px.EXAMPLES:
        assert f'href="/plan-for-me/example/{slug}"' in html, slug
    assert "See an example plan" in t


def test_the_offer_has_one_clear_button_to_the_intake(client):
    html = client.get(OFFER).text
    assert len(re.findall(r'class="[^"]*\bbtn-primary\b', html)) == 1
    assert re.search(r'<a[^>]*href="/plan-for-me/start"[^>]*id="pf-cta"|<a[^>]*id="pf-cta"[^>]*href="/plan-for-me/start"', html)


def test_a_creators_trip_carries_through_the_offer_to_the_intake(client):
    row, _, _ = live_trip()
    html = client.get(f"{OFFER}?from={row['slug']}").text
    assert "Starting from “Three easy days in Santa Monica”." in text_of(html)
    assert f'href="/plan-for-me/start?from={row["slug"]}"' in html
    assert 'href="/plan-for-me/start"' in client.get(f"{OFFER}?from=not-a-real-trip").text


def test_with_the_founder_check_on_nothing_promises_minutes(client, monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "1")
    row, _, _ = live_trip()
    pages = [client.get(OFFER).text, client.get(f"{OFFER}/start").text, client.get(f"/trips/{row['slug']}").text, client.get("/").text,
             *[client.get(f"{OFFER}/example/{s}").text for s in px.EXAMPLES]]
    sign_in(client)
    uid, tenant, email = buyer()
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    for status in ("paid", "building", "review"):
        with pfm._db() as db:
            from sqlalchemy import text
            db.conn.execute(text("UPDATE plan_orders SET status = :s WHERE id = :i"), {"s": status, "i": o["id"]})
            db.conn.commit()
        pages.append(client.get(f"{OFFER}/{o['id']}").text)
    for html in pages:
        assert not re.search(r"\bminutes?\b", text_of(html), re.I), re.search(r".{60}\bminutes?\b.{20}", text_of(html), re.I).group(0)
    assert "checked by a person, usually within a few hours" in text_of(pages[0])


def test_with_the_founder_check_off_the_offer_says_minutes_and_makes_no_check_promise(client, monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "0")
    t = text_of(client.get(OFFER).text)
    assert "in minutes" in t and "I check every plan" not in t and "checked by a person" not in t


def test_the_offer_and_the_examples_are_not_there_when_nothing_is_for_sale(client, monkeypatch):
    from gitaway import auth
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    for path in (OFFER, f"{OFFER}/start", f"{OFFER}/example/disneyland"):
        assert client.get(path).status_code == 404, path


# ---- the intake, moved -----------------------------------------------------------------------------------------------

def test_the_intake_is_at_start_and_signing_in_comes_back_to_it(client):
    html = client.get(f"{OFFER}/start").text
    assert 'id="pf-form"' in html and 'action="/plan-for-me"' in html
    r = client.post(OFFER, data=GOOD, follow_redirects=False)
    assert r.headers["location"] == "/signin?next=/plan-for-me/start"


def test_the_intake_asks_each_kids_height_and_it_is_optional(client):
    html = client.get(f"{OFFER}/start?nkids=2").text
    assert 'name="h1"' in html and 'name="h2"' in html and ">Not sure<" in html
    intake, errors = pfm.read_intake({**GOOD, "h1": "38", "h2": ""})
    assert errors == {} and intake["heights"] == [38, None]
    assert pfm.read_intake({**GOOD, "h1": "900", "h2": "abc"})[0]["heights"] == [None, None]


def test_an_old_order_without_heights_still_reads(client):
    from gitaway.pages import planview
    assert planview.kid_words({"kids": [4, 7]}) == ["4", "7"]


# ---- the examples ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("slug", list(px.EXAMPLES))
def test_an_example_is_written_to_pass_the_agents_own_filters_whole(slug):
    """An example goes through `planforme.validate` like a paid plan; not one note, tip or stop of it may be dropped, so what the offer shows is what a family can get."""
    e = px.EXAMPLES[slug]
    p = px.plan(e, catalog.today())
    assert len(p["days"]) == len(e.answer["days"]) and p["summary"] == e.answer["summary"] and p["tips"] == e.answer["tips"]
    for raw, out in zip(e.answer["days"], p["days"]):
        assert len(raw["stops"]) == len(out["stops"])
        for r, o in zip(raw["stops"], out["stops"]):
            assert o["note"] == r["note"]
            assert o["title"] in {f"{r['what']} · {r['place']}", r["place"], r["what"]}
            assert o["start"] is not None and tripcal.DEFAULT_START <= o["start"] < o["end"] <= tripcal.GRID_END
    for d in p["days"]:
        starts = [s["start"] for s in d["stops"]]
        assert starts == sorted(starts)


@pytest.mark.parametrize("slug,days,where", [("disneyland", 3, "Disneyland"), ("new-york-city", 4, "New York City"), ("oahu", 5, "Oahu")])
def test_an_example_page_shows_the_whole_plan_read_only_with_what_to_book(client, slug, days, where):
    r = client.get(f"{OFFER}/example/{slug}")
    assert r.status_code == 200
    html, t = r.text, text_of(r.text)
    e = px.EXAMPLES[slug]
    assert e.answer["title"] in t and "Example plan" in t
    assert html.count('class="pv-day"') == days
    assert 'id="pv-book"' in html and "What to book and when" in t and "official sites" in t
    assert "<form" not in html.split('id="pv-plan"')[1].split("</main>")[0] if 'id="pv-plan"' in html else False
    assert re.search(r'<a[^>]*id="pf-cta"[^>]*href="/plan-for-me/start\?where=', html) or re.search(r'href="/plan-for-me/start\?where=[^"]*"[^>]*id="pf-cta"', html)
    for stop in px.plan(e, catalog.today())["days"][0]["stops"]:
        assert stop["title"] in t


def test_the_disneyland_example_counts_its_dates_back_from_its_first_day(client):
    i = px.intake(px.EXAMPLES["disneyland"], catalog.today())
    start = date.fromisoformat(i["start"])
    assert (start - catalog.today()).days >= px.LEAD and start.weekday() == 0
    dining = start - timedelta(days=60)
    html = client.get(f"{OFFER}/example/disneyland").text
    assert f"Opens {dining:%a}, {dining:%b} {dining.day}" in text_of(html)
    assert "Kids 3 (38 in) and 7 (48 in)" in text_of(html) or "kids 3 (38 in) and 7 (48 in)" in text_of(html)


def test_an_unknown_example_is_a_404(client):
    assert client.get(f"{OFFER}/example/paris").status_code == 404


# ---- the checklist reaches the family --------------------------------------------------------------------------------

def test_a_ready_order_shows_what_to_book_and_the_trip_has_it_as_notes(client, monkeypatch):
    from tests.test_planforme_build import calendar, model, paid
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "0")
    model(monkeypatch)
    o = paid("ari")
    pfm.run_pending()
    sign_in(client)
    html = client.get(f"{OFFER}/{o['id']}").text
    assert 'id="pv-book"' in html and "Dining reservations" in text_of(html)
    notes = {n.text for n in tripcal.notes(person("ari"))}
    start = date.fromisoformat(o["intake"]["start"])
    want = [planfacts.note_text(i) for i in planfacts.checklist(o["intake"]["where"], start, catalog.today())]
    assert want and all(w in notes for w in want)
    pfm.write_trip(pfm._row(o["id"]), pfm._row(o["id"])["result"])          # written again: no second copy
    assert sum(n.text in want for n in tripcal.notes(person("ari"))) == len(want)
