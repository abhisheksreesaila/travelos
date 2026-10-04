"""F-084: the phone Family tab reaches the invite form (admin) or the member list (everyone else), in Chat and Photos."""

import re

import pytest

from tests.test_roles import crew  # noqa: F401 - fixture: admin client, editor, viewer
from tests.test_signin import sign_in

VIEWS = ["/trip/family", "/trip/family?view=photos"]


def _link(html):
    m = re.search(r'<a[^>]*id="fam-invite"[^>]*>', html)
    return m.group(0) if m else None


@pytest.mark.parametrize("path", VIEWS)
def test_admin_sees_an_invite_button_to_the_invite_form(crew, path):
    admin, _, _ = crew
    html = admin.get(path).text
    tag = _link(html)
    assert tag and 'href="/family#invite"' in tag
    assert "Invite" in html[html.index('id="fam-invite"'):][:900]


@pytest.mark.parametrize("path", VIEWS)
@pytest.mark.parametrize("who", [1, 2])
def test_editor_and_viewer_get_a_link_to_see_who_is_in_the_family(crew, path, who):
    html = crew[who].get(path).text
    tag = _link(html)
    assert tag and 'href="/family"' in tag and "#invite" not in tag
    assert "Invite" not in html[html.index('id="fam-invite"'):][:900]
    assert "Who's in the family" in html


def test_the_invite_form_it_points_at_exists_for_the_admin(crew):
    admin, _, _ = crew
    assert 'id="invite"' in admin.get("/family").text
