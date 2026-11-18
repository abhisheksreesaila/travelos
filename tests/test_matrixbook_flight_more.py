"""F-276: the pieces around the flight checkout (the drawer's words, a held room and its flight, the captain's count, the purge, what is never logged). The fixtures and helpers are those of
tests/test_matrixbook_flight.py."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N

from gitaway import bookingjobs, familydb, matrixbook as mb, session as ses
from gitaway.pages.matrixbook import _same_offers
from tests.test_matrixbook_flight import MATRIX, RETURN, flight_payments, flying, paid_flight, person, sheet, text, token  # noqa: F401 (flying is a fixture)


def test_the_squares_drawer_says_the_flight_books_here_too(flying, client):  # noqa: F811
    panel = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["drawer"]
    assert "The flight and the stay book here, each in its own payment form." in text(panel) and "airline’s site" not in panel


def test_a_held_room_is_used_only_with_the_flight_the_square_still_names():
    stay = N(offer_id="of-a", name="A", cents=1)
    held = lambda offer: N(rows=[N(part=stay)], flight=N(sample=False, soon=False, have=None, offer_id=offer))      # noqa: E731
    assert _same_offers(N(stays=[stay], flight=N(offer_id="fl-1")), held("fl-1"))
    assert not _same_offers(N(stays=[stay], flight=N(offer_id="fl-2")), held("fl-1"))      # the square was read again and names another flight: the hold is stale
    assert _same_offers(N(stays=[stay], flight=N(offer_id="")), N(rows=[N(part=stay)], flight=N(sample=True, soon=False, have=None, offer_id="")))


def test_a_held_room_is_found_by_its_token_only_for_the_family_that_holds_it(flying, client):  # noqa: F811
    tok = token(sheet(client).text)
    family = person()["tenant_id"]
    assert mb.held_by_token("another-family", tok) is None and mb.held_by_token("", tok) is None and mb.held_by_token(family, "no-such-token") is None
    held = mb.held_by_token(family, tok)
    assert held.flight.sample is False and held.flight.offer_id and held.rows


def test_a_flight_whose_booking_may_have_gone_through_is_counted_for_the_captain(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    flying.answers["book"] = (500, {"error": {"code": 1, "description": "boom"}})
    client.get(f"{RETURN}?token={tok}")
    assert flight_payments()[0]["status"] == "needs_help"
    assert bookingjobs.stuck_count(datetime.now(timezone.utc) + timedelta(minutes=30)) >= 1


def test_the_hourly_purge_drops_every_passenger_after_seven_days(flying, client):  # noqa: F811
    paid_flight(client)
    assert flight_payments()[0]["travellers"] != ""
    with ses.family(person()) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE matrix_flight_payments SET created_at = :t", t=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds"))
    bookingjobs._state["purged"] = None
    bookingjobs.run_once(datetime.now(timezone.utc))
    assert (flight_payments()[0]["travellers"], flight_payments()[0]["contact"]) == ("", "")


def test_no_log_line_of_the_flight_flow_holds_a_travellers_name_or_email(flying, client, caplog):  # noqa: F811
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    assert "okafor" not in caplog.text.lower() and "maya" not in caplog.text.lower()
