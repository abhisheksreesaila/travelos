"""Creator link import (F-023): paste a link, answer a few questions, edit five spots, confirm, publish to the hub."""

import re

import pytest
from starlette.testclient import TestClient

from gitaway import creators, hub
from gitaway.itineraries import safe_href
from tests.test_signin import session_data, sign_in

YT = "https://www.youtube.com/watch?v=our-la-family-week"
IG = "https://www.instagram.com/reel/Cxyz123/"
OK = {"form": "1", "do": "submit", "ok1": "1", "ok2": "1"}


def paste(client, link=YT):
    return client.post("/creators", data={"link": link}, follow_redirects=False)


def save(client, **data):
    return client.post("/creators/draft", data={"form": "1", "do": "save", **data}, follow_redirects=False)


def submit(client, **data):
    return client.post("/creators/draft", data={**OK, **data}, follow_redirects=False)


def slug_of(client):
    return session_data(client)["hub"]["ari"][0]["s"]


def day_count(html):
    return len(re.findall(r'class="cr-day ', html))


@pytest.mark.parametrize("link", [
    "https://youtube.com/watch?v=abc", "http://www.youtube.com/watch?v=abc", "https://m.youtube.com/watch?v=abc",
    "https://youtu.be/abc123", "https://instagram.com/p/abc/", "https://www.instagram.com/reel/abc/", "  https://youtu.be/abc  "])
def test_good_links_are_accepted(link):
    assert creators.parse_link(link).url == link.strip()


BAD = [
    "", "   ", "youtube.com/watch?v=abc", "ftp://youtube.com/watch?v=abc", "javascript:alert(1)", "data:text/html,hi",
    "https://evil.example/watch?v=abc", "https://youtube.com.evil.example/watch?v=abc", "https://notyoutube.com/watch?v=abc",
    "https://youtube.com@evil.example/watch?v=abc", "https://www.tiktok.com/@x/video/1", "https://youtu.be", "https://youtu.be/",
    "https://youtu.be/a b", "https://youtu.be/abc\nhttps://evil.example", "https://youtu.be/" + "a" * 400]


@pytest.mark.parametrize("link", BAD)
def test_bad_links_get_a_friendly_message(link, client):
    with pytest.raises(creators.LinkError) as e:
        creators.parse_link(link)
    assert str(e.value)
    r = paste(client, link)
    assert r.status_code == 422 and 'role="alert"' in r.text
    assert "cr" not in session_data(client) if client.cookies.get("session_") else True


def test_creators_is_no_longer_a_placeholder(client):
    from gitaway.pages import placeholders
    assert "/creators" not in placeholders.PLACEHOLDERS
    html = client.get("/creators").text
    assert "Paste" in html and "about 5 minutes" in html and "Coming soon" not in html


def test_a_good_link_goes_to_the_draft_with_the_skeleton_first(client):
    r = paste(client)
    assert r.status_code == 303 and r.headers["location"] == "/creators/draft?new=1"
    html = client.get("/creators/draft?new=1").text
    assert 'data-new="1"' in html and 'aria-busy="true"' in html and "cr-skel" in html
    assert 'data-new="1"' not in client.get("/creators/draft").text


def test_no_draft_goes_back_to_paste(client):
    r = client.get("/creators/draft", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/creators"


def test_the_draft_has_the_source_card_questions_and_progress(client):
    paste(client)
    html = client.get("/creators/draft").text
    assert "YouTube" in html and "min" in html
    assert "about 3 minutes left" in html
    for q in ("Which days", "Who does it suit", "Best season"):
        assert q in html
    assert 'name="days"' in html and 'name="who"' in html and 'name="season"' in html
    assert "guessed" in html  # the transcript is not trusted blindly
    assert "/assets/css/creators.css" in html and "/assets/js/creators.js" in html


def test_the_same_link_always_makes_the_same_draft(client):
    from main import app
    paste(client)
    other = TestClient(app)
    paste(other)
    assert client.get("/creators/draft").text == other.get("/creators/draft").text
    assert creators.draft_for(YT).title == creators.draft_for(YT).title


def test_links_pick_among_the_fixtures_by_hash():
    picks = {creators.draft_for(f"https://youtu.be/clip{i}").fx.key for i in range(40)}
    assert len(picks) == len(creators.FIXTURES) >= 2
    assert creators.draft_for(IG).platform == "Instagram" and creators.draft_for(YT).platform == "YouTube"


def test_answers_change_the_draft(client):
    paste(client)
    base = client.get("/creators/draft").text
    assert day_count(base) == 3
    save(client, days=["0", "2"], who=["pet"], season="winter")
    html = client.get("/creators/draft").text
    book = html.split('id="cr-book"')[1]
    assert day_count(html) == 2 and "Best in winter" in book and "Pet friendly" in book
    d = creators.resolve({"u": YT, "a": {"d": "02", "w": "p", "s": "winter"}})
    assert d.tags == ("pet",) and len(d.kept) == 2 and d.season == "winter"
    save(client, days=["0", "1", "2"], who=["kid", "couple"], season="summer")
    book = client.get("/creators/draft").text.split('id="cr-book"')[1]
    assert "Pet friendly" not in book and "Kid friendly" in book and "Couple friendly" in book


def test_no_day_ticked_keeps_every_day(client):
    paste(client)
    save(client, who=["kid"])
    assert day_count(client.get("/creators/draft").text) == 3


def test_only_five_spots_can_be_edited(client):
    assert creators.FIELDS == ("title", "hl1", "hl2", "tip", "cover")
    paste(client)
    html = client.get("/creators/draft").text
    names = set(re.findall(r'<(?:input|textarea)\b[^>]*?\bname="(\w+)"', html))
    assert names <= {"form", "do", "days", "who", "season", "title", "hl1", "hl2", "tip", "cover", "ok1", "ok2"}
    assert {"title", "hl1", "hl2", "tip", "cover"} <= names
    typed = set(re.findall(r'<textarea\b[^>]*?\bname="(\w+)"', html))
    typed |= {m for tag in re.findall(r"<input\b[^>]*>", html) if 'type="text"' in tag for m in re.findall(r'name="(\w+)"', tag)}
    assert typed == {"title", "hl1", "hl2", "tip"}      # four typed spots plus the cover pick makes five


def test_every_editable_spot_has_a_real_label(client):
    paste(client)
    html = client.get("/creators/draft").text
    for name in ("title", "hl1", "hl2", "tip"):
        tag = re.search(rf'<(?:input|textarea)\b[^>]*?\bname="{name}"[^>]*>', html).group(0)
        ident = re.search(r'\bid="([^"]+)"', tag).group(1)
        assert f'for="{ident}"' in html
    assert 'role="radiogroup"' in html or 'role="group"' in html


def test_edits_stick_and_extra_fields_are_ignored(client):
    paste(client)
    r = save(client, title="My own title", hl1="Best bit", tip="Bring a hat", cover="venice", hl2="Second best",
             author="Mallory", url="https://evil.example/", lede="Hacked", slug="x", forks="9999", source="Hax", place="Mars", days_count="1")
    assert r.status_code == 303
    html = client.get("/creators/draft").text
    for v in ("My own title", "Best bit", "Bring a hat", "Second best"):
        assert v in html
    for v in ("Mallory", "Hacked", "9999", "Hax", "Mars", "evil.example"):
        assert v not in html
    rec = session_data(client)["cr"]
    assert set(rec["e"]) <= {"t", "h1", "h2", "p", "c"} and rec["u"] == YT and set(rec) <= {"u", "a", "e", "k"}


def test_edits_are_trimmed_and_capped(client):
    paste(client)
    save(client, title="  " + "x" * 300, tip="y" * 900, cover="not-a-photo")
    d = creators.resolve(session_data(client)["cr"])
    assert len(d.title) == creators.MAX["title"] and len(d.tip) == creators.MAX["tip"] and d.cover == creators.draft_for(YT).cover
    save(client, title="   ")
    assert creators.resolve(session_data(client)["cr"]).title == creators.draft_for(YT).title


def test_submit_needs_both_confirm_boxes(client):
    sign_in(client)
    paste(client)
    for data in ({"form": "1", "do": "submit"}, {"form": "1", "do": "submit", "ok1": "1"}, {"form": "1", "do": "submit", "ok2": "1"}):
        r = client.post("/creators/draft", data=data, follow_redirects=False)
        assert r.status_code == 422 and 'role="alert"' in r.text and "accurate" in r.text
        assert "hub" not in session_data(client)
    assert client.get("/creators/draft").status_code == 200


def test_signed_out_submit_goes_through_the_demo_sign_in(client):
    paste(client)
    r = submit(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Fcreators%2Ffinish")
    assert "hub" not in session_data(client)
    assert sign_in(client, next="/creators/finish").headers["location"] == "/creators/finish"
    r = client.get("/creators/finish", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/creators/done"
    assert slug_of(client)


def test_finish_without_confirming_goes_back_to_the_draft(client):
    sign_in(client)
    paste(client)
    assert client.get("/creators/finish", follow_redirects=False).headers["location"] == "/creators/draft"


def test_publish_puts_the_trip_in_the_hub_with_its_own_page(client):
    sign_in(client)
    paste(client)
    r = submit(client, title="Sun, tacos & tides")
    assert r.status_code == 303 and r.headers["location"] == "/creators/done"
    slug = slug_of(client)
    row = session_data(client)["hub"]["ari"][0]
    assert row["t"] == "Sun, tacos & tides" and row["k"] == "YouTube" and "m" not in row
    assert "cr" not in session_data(client)  # the draft is gone, the trip is published
    done = client.get("/creators/done").text
    assert f'href="/trips/{slug}"' in done and 'href="/discover"' in done and "live" in done.lower()
    hubhtml = client.get("/discover").text
    assert "Sun, tacos &amp; tides" in hubhtml and f'href="/trips/{slug}"' in hubhtml and "Your trip" in hubhtml
    assert "Sun, tacos &amp; tides" in client.get("/discover?src=creators").text
    page = client.get(f"/trips/{slug}")
    assert page.status_code == 200 and "Sun, tacos &amp; tides" in page.text and "From the vlog" in page.text
    assert 'id="day-1"' in page.text and "The whole trip on one board" in page.text


def test_the_trip_page_reflects_the_answers_and_edits(client):
    sign_in(client)
    paste(client)
    save(client, days=["1", "2"], who=["pet"], season="fall", hl1="Mine one")
    submit(client, form="1", days=["1", "2"], who=["pet"], season="fall", hl1="Mine one")
    html = client.get(f"/trips/{slug_of(client)}").text
    assert 'id="day-2"' in html and 'id="day-3"' not in html
    assert "Pet friendly" in html and "Best in fall" in html and "Mine one" in html
    assert session_data(client)["hub"]["ari"][0]["g"] == ["pet"] and session_data(client)["hub"]["ari"][0]["n"] == 2


def test_the_trip_page_links_back_to_the_creators_channel(client):
    sign_in(client)
    paste(client)
    submit(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    tag = next(t for t in re.findall(r"<a\b[^>]*>", html) if "src-link" in t)
    href = re.search(r'href="([^"]*)"', tag).group(1)
    assert href.startswith("https://www.youtube.com/@") and safe_href(href) == href
    assert 'rel="noopener noreferrer"' in tag and "Visit the channel" in html


def test_instagram_links_link_to_the_instagram_channel(client):
    sign_in(client)
    paste(client, IG)
    submit(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert 'href="https://www.instagram.com/' in html and "Instagram" in client.get("/discover").text


def test_every_channel_link_is_http_s_only():
    for fx in creators.FIXTURES:
        for platform in ("YouTube", "Instagram"):
            url = creators.channel_url(fx, platform)
            assert safe_href(url) == url and url.startswith("https://")


def test_creator_text_is_escaped_everywhere(client):
    sign_in(client)
    evil = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    paste(client)
    save(client, title=evil, hl1=evil, hl2=evil, tip=evil)
    draft = client.get("/creators/draft").text
    assert "<script>alert" not in draft and "<img src=x" not in draft and "&lt;script&gt;" in draft
    submit(client, title=evil, hl1=evil, hl2=evil, tip=evil)
    slug = slug_of(client)
    for url in (f"/trips/{slug}", "/discover", "/creators/done"):
        html = client.get(url).text
        assert "<script>alert" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in client.get(f"/trips/{slug}").text


def test_the_pasted_link_is_escaped_when_refused(client):
    r = paste(client, '"><script>alert(1)</script>')
    assert r.status_code == 422 and "<script>alert" not in r.text


def test_publishing_twice_replaces_and_extra_links_are_capped(client):
    sign_in(client)
    paste(client)
    submit(client)
    paste(client)
    submit(client, title="Again")
    rows = session_data(client)["hub"]["ari"]
    assert len(rows) == 1 and rows[0]["t"] == "Again"
    r = None
    for i in range(creators.MAX_TRIPS):
        paste(client, f"https://youtu.be/other{i}")
        r = submit(client)
    assert r.status_code == 409 and len(session_data(client)["crp"]["ari"]) == creators.MAX_TRIPS


def test_a_full_cookie_refuses_cleanly_and_changes_nothing():
    s = {"traveler": "ari", "cr": {"u": YT, "k": 1}, "pad": "x" * 2500}
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in s.items()}
    with pytest.raises(hub.HubError) as e:
        creators.publish(s)
    assert "full" in str(e.value) and s == before


def test_the_trip_is_served_to_this_browser_only(client):
    from main import app
    sign_in(client)
    paste(client)
    submit(client)
    slug = slug_of(client)
    client.post("/signout")
    assert client.get(f"/trips/{slug}").status_code == 200  # same browser: the demo community
    assert TestClient(app).get(f"/trips/{slug}").status_code == 404


def test_progress_line_gets_shorter(client):
    assert "about 5 minutes" in client.get("/creators").text
    paste(client)
    assert "about 3 minutes left" in client.get("/creators/draft").text
    save(client, who=["kid"])
    assert "about 2 minutes left" in client.get("/creators/draft").text


def test_the_stylesheet_is_motion_safe():
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "assets/css/creators.css").read_text()
    assert "prefers-reduced-motion" in css and "text-overflow" not in css
