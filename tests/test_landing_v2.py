"""F-060: Landing v2. One door (Plan a trip), forking as one quiet line, a header with only the brand and Sign in."""
import re

from gitaway import itineraries
from tests.test_signin import sign_in


def _get(client, path="/"):
    r = client.get(path)
    assert r.status_code == 200
    return r.text


def _tag(h, name, cls):
    m = re.search(rf'<{name}[^>]*class="[^"]*\b{cls}\b[^"]*"[^>]*>(.*?)</{name}>', h, re.S)
    assert m, f"no <{name}> with class {cls}"
    return m.group(1)


def _hrefs(fragment):
    return re.findall(r'href="([^"]*)"', fragment)


def test_landing_header_has_only_the_brand_and_sign_in(client):
    header = _tag(_get(client), "header", "ga-header")
    assert "ga-nav" not in header
    assert _hrefs(header) == ["#main", "/", "/signin"]
    assert "Community trips" not in header and "For creators" not in header and "Plan a trip" not in header


def test_other_pages_keep_their_header_nav(client):
    for path in ["/community", "/creators", "/signin"]:
        header = _tag(_get(client, path), "header", "ga-header")
        assert "/community" in header and "/creators" in header and "/start" in header, path


def test_footer_carries_the_links_that_left_the_header(client):
    footer = _tag(_get(client), "footer", "ga-footer")
    assert _hrefs(footer) == ["/community", "/creators", "/signin"]
    other = _tag(_get(client, "/community"), "footer", "ga-footer")
    assert "/creators" not in other  # only the landing gets the extra links


def test_signed_in_visitor_sees_their_account_and_no_sign_in_link(client):
    sign_in(client)
    h = _get(client)
    header = _tag(h, "header", "ga-header")
    assert "ga-account" in header and 'href="/family"' in header and "Sign out" in header
    assert "ga-nav" not in header
    footer = _tag(h, "footer", "ga-footer")
    assert _hrefs(footer) == ["/community", "/creators"]


def test_headline_is_fork_a_getaway_with_the_gloss(client):
    h = _get(client)
    assert "Fork a" in h and "getaway." in h
    gloss = re.sub(r"<[^>]+>", " ", _tag(h, "p", "gloss"))
    assert " ".join(gloss.split()) == "fork verb copy a trip someone really took, then make it yours"


def test_one_wide_primary_door_to_plan_a_trip(client):
    h = _get(client)
    assert "DOOR ONE" not in h and "DOOR TWO" not in h and "No plans yet?</h2>" not in h
    assert "Let’s book it." in h and "We’re going." in h
    forms = re.findall(r"<form[^>]*>", h)
    assert len(forms) == 1 and 'action="/start"' in forms[0] and 'method="get"' in forms[0]
    assert len(re.findall(r'<button[^>]*type="submit"[^>]*>[^<]*Plan a trip', h)) == 1
    assert h.count("btn-ink") == 1


def test_forking_is_one_quiet_line_that_leads_to_community_trips(client):
    h = _get(client)
    line = _tag(h, "div", "forkline")
    assert "No plans yet?" in line and "Fork a trip a real family took" in line
    assert _hrefs(line) == ["#community-trips"]
    assert re.search(r'<section[^>]*id="community-trips"', h)


def test_community_section_shows_three_real_trips_and_browse_link(client):
    h = _get(client)
    sec = re.search(r'<section[^>]*id="community-trips".*?</section>', h, re.S).group(0)
    assert "Not sure where yet? Borrow a trip that worked." in sec
    trips = list(itineraries.ITINERARIES.values())[:3]
    for t in trips:
        assert t.title in sec.replace("&amp;", "&") or t.title.replace("&", "&amp;") in sec
        assert f'href="/trips/{t.slug}"' in sec
        assert f"{t.forks} forks" in sec
    assert 'href="/community"' in sec and "Browse all community trips" in sec
    assert 'src="/assets/photos/venice-beach-los-angeles-hero.jpg"' in sec  # a real area photo, never a hotel


def test_each_community_card_opens_a_page(client):
    h = _get(client)
    for slug in re.findall(r'href="(/trips/[^"]+)"', h):
        assert client.get(slug).status_code == 200, slug


def test_four_feature_tiles_each_with_an_animation(client):
    h = _get(client)
    assert "Not just a booking site" in h
    tiles = re.findall(r'<article[^>]*class="feature"[^>]*>', h)
    assert len(tiles) == 4 and all('tabindex="0"' in t for t in tiles)
    for cls in ["a-panes", "a-total", "a-together", "a-fork"]:
        assert f"anim {cls}" in h


def test_creators_copy_is_about_inspiring_others_not_followers(client):
    h = _get(client)
    sec = re.search(r'<section[^>]*aria-labelledby="cr-h".*?</section>', h, re.S).group(0)
    assert "Been somewhere wonderful? Leave a trail." in sec
    assert "make someone’s first time there a little easier" in sec
    assert "Attributed to Saint Augustine" in sec
    assert "follower" not in h.lower() and "subscriber" not in h.lower()
    assert 'href="/creators"' in sec and "Share a trip you loved" in sec


def test_calendar_has_four_people_three_days_and_booked_items_with_a_lock(client):
    h = _get(client)
    cal = re.search(r'id="cal".*?</section>', h, re.S).group(0)
    assert len(re.findall(r'data-s="s\d"', cal)) == 7  # the seven plans people add
    assert cal.count("item booked") == 2 and cal.count("lock") >= 2
    assert re.findall(r'class="day">([^<]+)<', cal) == ["FRI 16", "SAT 17", "SUN 18"]
    assert "4 planning now" in h and "Watch it again" in h
    assert "/assets/js/landing.js" in h
