"""M4: creator profiles at /creators/<handle> (showcase only)."""
import re

from gitaway import creator_profiles as cp


def test_roster_links_every_creator(client):
    html = client.get("/creators").text
    for c in cp.CREATORS:
        assert f'href="/creators/{c.handle}"' in html
    assert "every stop sends viewers back to your video" in html
    assert 'action="/creators"' in html  # the paste box stays


def test_profile_shows_bio_channel_and_trips(client):
    h = client.get("/creators/aloha-mei").text
    assert "Mei Tanabe" in h and "Honolulu slow honeymoon" in h and "203 forks" in h and "Couple friendly" in h
    assert 'href="https://www.instagram.com/aloha.mei/"' in h
    assert 'href="/plan?to=hi&amp;d=2027-02-12&amp;r=2027-02-19&amp;a=2"' in h


def test_each_place_has_a_creator():
    assert {c.place for c in cp.CREATORS} == {"la", "sd", "hi", "nyc"}
    assert all(re.match(r"https://www\.(youtube|instagram)\.com/", c.channel) for c in cp.CREATORS)


def test_unknown_handle_404(client):
    assert client.get("/creators/nobody-here").status_code == 404


def test_draft_route_not_shadowed(client):
    r = client.get("/creators/draft", follow_redirects=False)
    assert r.status_code in (200, 303) and "Mei Tanabe" not in r.text


def test_hidden_when_showcase_off(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/creators/sunny-ines").status_code == 404
    assert client.get("/creators").status_code == 404
