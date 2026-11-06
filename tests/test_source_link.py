"""F-196 item 8: the card that links a trip back to the creator's post tells the creator's site where the reader came from: the origin as the referrer and utm_source=gitaway."""

import re

import pytest

from tests.live_trips import live_trip


def link_of(client, slug):
    html = client.get(f"/trips/{slug}").text
    m = re.search(r'<a [^>]*class="src-link"[^>]*>', html)
    assert m, "no source link"
    return m.group(0)


@pytest.mark.parametrize("post,sent", [("https://blog.example.com/santa-monica", "https://blog.example.com/santa-monica?utm_source=gitaway"),
                                       ("https://blog.example.com/p?id=7&page=2", "https://blog.example.com/p?id=7&page=2&utm_source=gitaway"),
                                       ("https://blog.example.com/p?utm_source=newsletter", "https://blog.example.com/p?utm_source=newsletter"),
                                       ("https://blog.example.com/p#day-2", "https://blog.example.com/p?utm_source=gitaway#day-2"),
                                       ("https://youtu.be/abc123", "https://youtu.be/abc123?utm_source=gitaway")], ids=["plain", "query", "own-utm", "fragment", "youtube"])
def test_the_source_link_carries_utm_source_and_sends_the_origin(client, post, sent):
    row, _, _ = live_trip(source_url=post)
    tag = link_of(client, row["slug"])
    assert f'href="{sent}"' in tag.replace("&amp;", "&")
    assert 'referrerpolicy="origin"' in tag and 'rel="noopener"' in tag and "noreferrer" not in tag and 'target="_blank"' in tag


def test_a_link_that_is_not_http_is_still_never_drawn(client):
    row, _, _ = live_trip(source_url="javascript:alert(1)")
    assert 'class="src-link"' not in client.get(f"/trips/{row['slug']}").text
