"""F-262 (docs/design/guides-v2): the guide hub (/guides), the guide page (the run sheet at /trips/<slug> and the owner's at /creators/import/<id>/guide), the retired book and community
addresses, the owner gates, "from my trip" (the calendar becomes a draft, flights and stays private) and Add to my plan. The post is The Planet D's "48 Hours in Lisbon" recorded through the app's
own fetcher (tests/fixtures/creator_import); nothing here reaches the network or a model."""
import json
import re
from html import unescape

import pytest

from gitaway import ai, community, creatordraft as cd, safefetch
from tests.creator_import_support import Model, recorded
from tests.test_calendar import add, book
from tests.test_roles import crew  # noqa: F401 - a fixture: Ari (admin), an editor and a viewer
from tests.test_signin import sign_in, tid

KEY = "sk-ant-not-a-real-key-0000"
MAGIC, BOOK = {"X-Magic": "1"}, {"X-Book": "1"}
BELEM = "We didn’t go inside Belém Tower but admired it from the outside."


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def stranger(client):
    return client.__class__(client.app, client=("127.0.0.1", 50000))


@pytest.fixture
def lisbon(client, monkeypatch):
    """The recorded post's draft for a signed-in creator, on the live site's rules (no samples): (client, the draft)."""
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": url}, headers=MAGIC)
    event = [json.loads(line) for line in r.text.splitlines() if line.strip()][-1]
    return client, cd.get(tid(), event["id"])


def publish(client, d):
    r = client.post(f"/creators/import/{d['id']}", data={"do": "publish", "own": "1", "name": "Maya"}, headers=BOOK)
    return r.json()


def named(client, d):
    """The draft needs the creator's name before it can be published (the editor's field)."""
    client.post(f"/creators/import/{d['id']}", data={**{k: v for k, v in _form(d).items()}, "name": "Maya Chen"})
    return cd.get(tid(), d["id"])


def _form(d):
    form = {"title": d["title"], "name": d["name"], "place": d["place"], "place_name": d["place_name"], "tip": d["tips"], "stickers": d["stickers"]}
    for i, day in enumerate(d["days"]):
        form[f"d{i}_title"], form[f"d{i}_note"] = day["title"], day["note"]
        for j, s in enumerate(day["stops"]):
            form[f"d{i}s{j}_name"], form[f"d{i}s{j}_time"], form[f"d{i}s{j}_note"], form[f"d{i}s{j}_link"] = s["name"], s["time"], s["note"], s.get("link", "")
    return form


# ---- the hub ------------------------------------------------------------------------------------------------------------------------

def titles(html):
    return re.findall(r"<h3>(.*?)</h3>", html)


def test_the_hub_lists_the_samples_labelled_and_filters_only_by_what_a_guide_knows(client):
    html = client.get("/guides").text
    assert titles(html) == ["Sun, tacos &amp; tide pools", "LA for two, slow mornings", "Dog-friendly Big Sur drive", "San Diego on a budget"]
    assert html.count(">Sample<") == 4
    for label in ("Families", "Couples", "With a pet", "A weekend", "3 to 4 days", "A week or more"):
        assert f">{label}<" in html
    for label in ("Budget", "Season", "Winter", "Summer"):      # a guide has no season or budget in its data, so the hub has no such filter
        assert f">{label}<" not in html
    assert titles(client.get("/guides?who=pet").text) == ["Sun, tacos &amp; tide pools", "Dog-friendly Big Sur drive"]
    assert titles(client.get("/guides?who=couple").text) == ["LA for two, slow mornings"]
    assert titles(client.get("/guides?len=short").text) == ["LA for two, slow mornings", "Dog-friendly Big Sur drive", "San Diego on a budget"]      # 3 and 4 days
    assert titles(client.get("/guides?len=week").text) == ["Sun, tacos &amp; tide pools"]
    assert titles(client.get("/guides?who=pet&len=short").text) == ["Dog-friendly Big Sur drive"]
    assert titles(client.get("/guides?q=big+sur").text) == ["Dog-friendly Big Sur drive"]
    assert "No guides match that" in client.get("/guides?q=atlantis").text
    assert "Be the first to share one" in html and "These are sample guides" in html      # until a real guide is published


def test_the_hub_has_the_search_with_autocomplete_and_make_a_guide_with_two_ways(client):
    html = client.get("/guides").text
    assert 'role="search"' in html and 'data-suggest="/plan/ask/suggest"' in html and 'id="gh-q"' in html
    assert re.search(r'<a [^>]*id="mk-paste"[^>]*href="/guides/make"|<a [^>]*href="/guides/make"[^>]*id="mk-paste"', html)
    assert 'id="mk-trip"' in html and "Make a guide" in html


def test_off_the_showcase_the_hub_says_so_before_anyone_has_published(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    r = client.get("/guides")
    assert r.status_code == 200 and "No guides yet" in r.text and ">Sample<" not in r.text


def test_the_old_community_and_creator_addresses_go_to_the_hub(client):
    for old, new in (("/community", "/guides"), ("/community?kid=1&q=tahoe", "/guides?who=kid&q=tahoe"), ("/discover", "/guides"), ("/for-creators", "/guides")):
        r = client.get(old, follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, new), old


def test_a_published_creator_guide_is_on_the_hub_with_its_creator_and_whose_drafts_are_listed_for_them(lisbon):
    client, d = lisbon
    d = named(client, d)
    assert publish(client, d)["ok"]
    html = client.get("/guides").text
    assert "48 hours in Lisbon" in html and f'href="/trips/{d["slug"]}"' in html and ">Sample<" not in html
    assert "Your guides" in html and f'href="/creators/import/{d["id"]}/guide"' in html and ">Published<" in html
    assert "Your guides" not in stranger(client).get("/guides").text


# ---- the guide page -------------------------------------------------------------------------------------------------------------------

def test_the_guide_is_the_run_sheet_of_the_posts_own_words(lisbon):
    client, d = lisbon
    d = named(client, d)
    assert publish(client, d)["ok"]
    html = stranger(client).get(f"/trips/{d['slug']}").text
    assert 'id="gpage"' in html and 'data-mode="reader"' in html
    assert 'data-sky="quiet"' in html      # F-261: a guide is a reading page, its sky quiet (review of F-261/F-262)
    assert [t for t in re.findall(r'<small>(Days|Suits|Tips|From[^<]*)</small><span class="gl-v">(.*?)</span>', html)] == [("Days", "3 days"), ("Tips", "4 tips"), ("From the blog", "theplanetd.com")]
    assert re.findall(r'<span class="dn">(Day \d)</span>', html) == ["Day 1", "Day 2", "Day 3"]      # the sticky day strip
    first = re.search(r'<li [^>]*id="g-d0s0"[^>]*>.*?</li>', html, re.S).group(0)
    assert "Belem Tower" in first and f'<p class="g-why">{BELEM}</p>' in unescape(first) and ">Tip<" in first
    assert 'class="g-more"' in html and "This is the creator's own link" not in html      # no stop of the Lisbon post carries a link of its own
    assert 'class="bdg cost"' not in html      # the post names no price, so no stop shows one
    assert "Season" not in html and "Budget" not in html and "min drive" not in html and "min walk" not in html      # nothing it does not know: no tile, no travel time between stops
    assert 'href="/plan/ask?to=' not in html      # Lisbon is not a place the booking search prices
    assert 'id="g-plan"' in html and 'href="/plan/ask"' in html
    assert "The words, the times and the links are the creator's own. GitAway adds nothing to the price of their links." in html


def test_a_creators_link_on_a_stop_is_labelled_as_theirs_and_adds_nothing_to_the_price(lisbon):
    client, d = lisbon
    form = _form(d)
    form["d0s0_link"], form["name"] = "https://www.viator.com/tours/Lisbon/Belem-Tower/d538-1", "Maya Chen"
    client.post(f"/creators/import/{d['id']}", data=form)
    d = cd.get(tid(), d["id"])
    assert d["days"][0]["stops"][0]["link"].startswith("https://www.viator.com/")
    assert publish(client, d)["ok"]
    html = client.get(f"/trips/{d['slug']}").text
    assert re.search(r"<a [^>]*class=\"bdg lnk\"[^>]*>(?:<svg.*?</svg>)?The creator's link</a>", html, re.S)      # nobody has vouched for the creator yet (D-189): the byline is the site, so it is "the creator's"
    assert 'rel="sponsored noopener"' in html and "This is the creator's own link. GitAway adds nothing to the price." in html
    assert 'href="https://www.viator.com/tours/Lisbon/Belem-Tower/d538-1"' in html


def test_a_stop_costs_what_the_creators_sentence_says_and_a_guide_without_tags_has_no_suits_tile(lisbon):
    client, d = lisbon
    form = _form(d)
    form["d0s2_note"], form["name"] = "Tickets are $12 for adults.", "Maya Chen"      # the post's own sentences name the other stops: this one has none, so the note is its line
    client.post(f"/creators/import/{d['id']}", data=form)
    assert publish(client, cd.get(tid(), d["id"]))["ok"]
    html = client.get(f"/trips/{d['slug']}").text
    assert re.findall(r'<span class="bdg cost">(.*?)</span>', html) == ["$12 for adults"]


def test_the_owners_guide_is_theirs_alone_and_says_what_stays_private(lisbon):
    client, d = lisbon
    path = f"/creators/import/{d['id']}/guide"
    html = client.get(path).text
    assert 'data-mode="owner"' in html and 'id="pubBtn"' in html and "Draft · only you can see it" in html and 'class="ed"' in html
    assert re.search(r'<a [^>]*id="detailsBtn"[^>]*href="/creators/import/%s"|<a [^>]*href="/creators/import/%s"[^>]*id="detailsBtn"' % (d["id"], d["id"]), html)
    assert "noindex" in html
    assert stranger(client).get(path, follow_redirects=False).headers["location"].startswith("/signin?next=")
    sign_in(stranger(client), "sam")
    other = stranger(client)
    sign_in(other, "sam")
    assert other.get(path).status_code == 404 and other.get(f"/trips/{d['slug']}").status_code == 404      # unpublished: no one else can read it


def test_the_book_addresses_are_retired_into_the_guide(lisbon):
    client, d = lisbon
    named_d = named(client, d)
    assert publish(client, named_d)["ok"]
    r = client.get(f"/trips/{d['slug']}/book", follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (301, f"/trips/{d['slug']}")
    r = client.get(f"/creators/import/{d['id']}/book", follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, f"/creators/import/{d['id']}/guide")


def test_the_instagram_card_of_a_published_guide_is_a_png_and_a_draft_has_none(lisbon):
    client, d = lisbon
    assert client.get(f"/trips/{d['slug']}/card.png").status_code == 404
    assert publish(client, named(client, d))["ok"]
    r = stranger(client).get(f"/trips/{d['slug']}/card.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_publishing_answers_with_the_guides_link_its_card_and_the_badge(lisbon):
    client, d = lisbon
    j = publish(client, named(client, d))
    assert j["ok"] and j["link"].endswith(f"/trips/{d['slug']}") and j["card"] == f"/trips/{d['slug']}/card.png" and "href=" in j["code"]


# ---- from my trip -------------------------------------------------------------------------------------------------------------------------

def test_make_a_guide_from_the_planned_trip_keeps_the_flights_and_stays_private(client):
    book(client)
    add(client, "a1", title="Taco lunch", start="12:00", end="13:00")
    r = client.post("/guides/make/trip", follow_redirects=False)
    assert r.status_code == 303 and re.fullmatch(r"/creators/import/[0-9a-f]{16}/guide", r.headers["location"])
    html = client.get(r.headers["location"]).text
    assert "Taco lunch" in html and "booking" in html and "kept private" in html
    did = r.headers["location"].split("/")[3]
    d = cd.get(tid(), did)
    assert d["private"] and d["name"]
    stops = [s["name"] for day in d["days"] for s in day["stops"]]
    assert stops == ["Taco lunch"]
    for p in d["private"]:
        assert f">{p['title']}<" not in html.split('id="g-day1"')[1]      # a flight or a hotel is no stop of the sheet, only a line saying it is kept
    d = named(client, d)
    pub = publish(client, d)
    assert pub["ok"], pub
    public = stranger(client).get(f"/trips/{cd.get(tid(), did)['slug']}").text
    assert "Taco lunch" in public and "kept private" not in public
    for p in d["private"]:
        assert p["title"] not in public      # review of F-262: a booking from the trip never reaches the published guide


def test_make_a_guide_from_a_trip_needs_something_planned_and_a_trip(client):
    assert client.post("/guides/make/trip", follow_redirects=False).headers["location"].startswith("/signin")
    book(client)
    r = client.post("/guides/make/trip")
    assert r.status_code == 422 and cd.NO_PLANS in r.text
    sign_in(client, "sam@example.com")      # a family with no trip is sent to start one
    assert client.post("/guides/make/trip", follow_redirects=False).headers["location"] == "/plan/ask"


def test_the_hub_offers_the_planned_trip_as_a_form_only_to_a_family_with_a_trip(client):
    assert 'id="mk-trip"' in client.get("/guides").text and '<form' not in re.search(r'<[a-z]+ [^>]*id="mk-trip"', client.get("/guides").text).group(0)
    book(client)
    assert re.search(r'<form[^>]*action="/guides/make/trip"[^>]*>', client.get("/guides").text)


# ---- Add to my plan ----------------------------------------------------------------------------------------------------------------------

def test_add_to_my_plan_drops_a_stop_into_a_free_hour_and_undo_takes_it_out(client):
    book(client)
    sample = "sun-tacos-and-tide-pools"
    r = client.post("/guides/add", data={"slug": sample, "k": ["d1s1"]})
    j = r.json()
    assert r.status_code == 200 and len(j["added"]) == 1 and j["added"][0]["title"] and re.fullmatch(r"\w{3} \d+ · \d+:\d\d [AP]M", j["added"][0]["when"])
    assert j["toast"] == f"{j['added'][0]['title']} added, {j['added'][0]['when']}"
    again = client.post("/guides/add", data={"slug": sample, "k": ["d1s1"]}).json()
    assert again["added"] == [] and again["toast"] == "Already in your plan."
    undone = client.post("/trip/plan/write", data={"op": "undo", "undo": json.dumps(j["added"][0]["undo"])})
    assert undone.status_code == 200
    assert client.post("/guides/add", data={"slug": sample, "k": ["d1s1"]}).json()["added"]      # it was taken out, so it fits again


def test_add_to_my_plan_for_a_whole_day_says_what_it_left_out(client):
    book(client)
    j = client.post("/guides/add", data={"slug": "sun-tacos-and-tide-pools", "k": [f"d0s{i}" for i in range(4)]}).json()
    assert len(j["added"]) + len(j["skipped"]) == 4 and j["added"]
    assert j["toast"].startswith(f"{len(j['added'])} stops added to your plan" if len(j["added"]) > 1 else j["added"][0]["title"])


def test_add_to_my_plan_is_an_editors_and_needs_a_guide_and_a_trip(crew, client):  # noqa: F811
    _, editor, viewer = crew
    assert viewer.post("/guides/add", data={"slug": "sun-tacos-and-tide-pools", "k": ["d0s0"]}).status_code == 403
    assert len(editor.post("/guides/add", data={"slug": "sun-tacos-and-tide-pools", "k": ["d0s0"]}).json()["added"]) == 1
    assert editor.post("/guides/add", data={"slug": "no-such-guide", "k": ["d0s0"]}).status_code == 404
    sign_in(stranger(client), "sam@example.com")


def test_the_page_says_why_add_to_my_plan_is_not_there_for_you(client):
    page = client.get("/trips/sun-tacos-and-tide-pools").text
    assert 'data-can="signin"' in page and "Sign in to add this to your plan." in page and 'class="g-plus"' not in page
    sign_in(client, "sam@example.com")
    page = client.get("/trips/sun-tacos-and-tide-pools").text
    assert 'data-can="trip"' in page and "You need a trip first" in page
    book(client)
    page = client.get("/trips/sun-tacos-and-tide-pools").text
    assert 'data-can="yes"' in page and page.count('class="g-plus"') == 16 and 'id="g-add"' in page


def test_the_family_trips_pages_still_use_their_own_page(client):
    html = client.get("/trips/la-for-two-slow-mornings").text
    assert 'id="gpage"' not in html      # a sample with no creator's source stays the trip page
