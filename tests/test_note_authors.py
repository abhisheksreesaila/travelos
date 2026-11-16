"""F-046: a note shows who wrote it (name and avatar); "You" only on the writer's own screen."""
import re

import pytest

from tests.test_calendar import book
from tests.test_crew_calendar import named
from tests.test_members import browser, invite
from tests.test_signin import sign_in


def metas(html):
    """[(meta line, avatar name)] for each note in the Notes tab's feed, oldest first (the tab shows the newest on top)."""
    out = []
    for chunk in re.split(r'<div[^>]*class="tp-note"', html.split('id="tp-panel-notes"')[1])[1:]:
        meta = re.search(r'class="tp-notemeta">([^<]*)<', chunk)
        who = re.search(r'title="([^"]*)"', chunk)
        out.append((meta.group(1), who.group(1) if who else ""))
    return out[::-1]


@pytest.fixture
def pair(client):
    book(client)
    sam = named("sam.kim")
    invite(client, sam, "editor")
    other = browser(client)
    sign_in(other, sam)
    return client, other

