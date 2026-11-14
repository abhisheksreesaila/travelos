"""F-035, F-231: the picks a traveler left in the booking workspace are remembered in the family's database (the rides page's "Back to my picks" reads them), never in the cookie."""
from gitaway import session as ses
from tests.test_signin import person, session_data, sign_in


def test_remembered_picks_live_in_the_family_database_not_the_cookie(client):
    sign_in(client)
    client.get("/plan?f=f2&h=h3&c=c1&rooms=cy1&add=bf&d=2026-10-16&r=2026-10-19&a=3&k=4,7")
    assert "plan" not in session_data(client) and "f=f2&h=h3&c=c1" in ses.remembered_plan(person())


def test_remembering_picks_ignores_an_absurdly_long_query():
    s = person()
    ses.remember_plan(s, "f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=3&k=4,7")
    ses.remember_plan(s, "x=" + "y" * ses.MAX_PLAN_QUERY)
    assert ses.remembered_plan(s) == "f=f2&h=h3&c=c1&d=2026-10-16&r=2026-10-19&a=3&k=4,7"
