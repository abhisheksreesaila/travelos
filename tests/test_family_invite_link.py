"""F-084: the phone Family tab reaches the invite form (admin) or the member list (everyone else), in Chat and Photos."""

import re

import pytest

from tests.test_roles import crew  # noqa: F401 - fixture: admin client, editor, viewer
from tests.test_signin import sign_in

VIEWS = ["/trip/family", "/trip/family?view=photos"]


def _link(html, id_):
    """(opening tag, link text) of the <a> with this id, or (None, None)."""
    m = re.search(rf'(<a[^>]*id="{id_}"[^>]*>)(.*?)</a>', html, re.S)
    return (m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()) if m else (None, None)


def test_the_invite_form_it_points_at_exists_for_the_admin(crew):
    admin, _, _ = crew
    assert 'id="invite"' in admin.get("/family").text
