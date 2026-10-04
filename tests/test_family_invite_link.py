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


@pytest.mark.parametrize("path", VIEWS)
def test_admin_sees_an_invite_button_to_the_invite_form(crew, path):
    admin, _, _ = crew
    html = admin.get(path).text
    tag, text = _link(html, "ft-invite")
    assert tag and 'href="/family#invite"' in tag and text == "Invite"


@pytest.mark.parametrize("path", VIEWS)
@pytest.mark.parametrize("who", [1, 2])
def test_editor_and_viewer_get_a_link_to_see_who_is_in_the_family(crew, path, who):
    html = crew[who].get(path).text
    tag, text = _link(html, "ft-people")
    assert tag and 'href="/family"' in tag and text == "Who's in the family"
    assert _link(html, "ft-invite") == (None, None)


def test_the_invite_form_it_points_at_exists_for_the_admin(crew):
    admin, _, _ = crew
    assert 'id="invite"' in admin.get("/family").text
