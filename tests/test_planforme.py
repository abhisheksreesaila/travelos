"""F-193 Plan it for me: the rules (gitaway/planforme.py). The price is the server's, the intake is checked, an order moves only the way the state machine allows, and only its buyer sees it.
The screens are tests/test_planforme_pages.py; the money and the trip are tests/test_planforme_pay.py and tests/test_planforme_build.py."""

import pytest

from gitaway import planforme as pfm
from tests.test_signin import person

GOOD = {"where": "Disneyland, California", "start": "2027-03-12", "end": "2027-03-15", "home": "SFO", "adults": "2", "nkids": "2", "k1": "4", "k2": "7",
        "budget": "comfortable", "must": "Space Mountain and a quiet beach morning", "pace": "relaxed"}


def buyer(who="ari"):
    s = person(who)
    return s["user_id"], s["tenant_id"], s["email"]


# ---- the price is the server's ---------------------------------------------------------------------------------------

def test_the_price_is_29_dollars_unless_the_setting_says_otherwise(monkeypatch):
    monkeypatch.delenv("PLAN_FOR_ME_PRICE_CENTS", raising=False)
    assert pfm.price_cents() == 2900
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", "3500")
    assert pfm.price_cents() == 3500


@pytest.mark.parametrize("bad", ["", "abc", "-5", "5", "29.00", "99999999", "0"])
def test_a_nonsense_price_setting_falls_back_to_29_dollars(monkeypatch, bad):
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", bad)
    assert pfm.price_cents() == 2900


# ---- the intake ------------------------------------------------------------------------------------------------------

def test_a_good_form_becomes_an_intake_with_exactly_these_fields():
    intake, errors = pfm.read_intake(GOOD)
    assert errors == {}
    assert intake == {"where": "Disneyland, California", "start": "2027-03-12", "end": "2027-03-15", "home": "SFO", "adults": 2, "kids": [4, 7],
                      "budget": "comfortable", "must": "Space Mountain and a quiet beach morning", "pace": "relaxed", "like": ""}


def test_a_price_or_an_amount_in_the_form_is_not_part_of_the_intake():
    intake, errors = pfm.read_intake({**GOOD, "price": "1", "amount": "1", "amount_cents": "1", "currency": "eur", "status": "paid"})
    assert errors == {} and set(intake) == {"where", "start", "end", "home", "adults", "kids", "budget", "must", "pace", "like"}


def test_the_form_says_what_is_wrong_in_plain_words():
    _, errors = pfm.read_intake({**GOOD, "where": "", "start": "2027-03-15", "end": "2027-03-12", "adults": "0", "k1": "18"})
    assert errors["where"] == "Where you are going is needed."
    assert errors["end"] == "You come home before you leave. Check the two days."
    assert errors["adults"] == "Choose 1 to 12 adults."
    assert errors["k1"] == "Pick an age from 0 to 17 for kid 1."


def test_a_trip_in_the_past_or_longer_than_two_weeks_is_refused():
    _, errors = pfm.read_intake({**GOOD, "start": "2020-01-01", "end": "2020-01-03"})
    assert errors["start"] == "Pick a day that has not happened yet."
    _, errors = pfm.read_intake({**GOOD, "start": "2027-03-01", "end": "2027-03-20"})
    assert errors["end"] == "A planned trip can be at most 14 days long."


def test_a_home_airport_must_be_three_letters_or_empty():
    _, errors = pfm.read_intake({**GOOD, "home": "San Francisco"})
    assert errors["home"] == "Use the three-letter code, like SFO, or leave it empty."
    intake, errors = pfm.read_intake({**GOOD, "home": "sfo "})
    assert errors == {} and intake["home"] == "SFO"
    intake, errors = pfm.read_intake({**GOOD, "home": ""})
    assert errors == {} and intake["home"] == ""


def test_an_unknown_budget_or_pace_becomes_the_middle_choice_and_the_free_text_is_cut_and_cleaned():
    intake, _ = pfm.read_intake({**GOOD, "budget": "unlimited", "pace": "frantic", "must": "x" * 900 + "\x00\x07 end"})
    assert intake["budget"] == "comfortable" and intake["pace"] == "balanced"
    assert intake["must"] == "x" * pfm.MAX_MUST and "\x00" not in intake["must"]


def test_kids_are_counted_from_nkids_and_the_party_has_a_ceiling():
    intake, errors = pfm.read_intake({**GOOD, "adults": "2", "nkids": "0"})
    assert errors == {} and intake["kids"] == []
    _, errors = pfm.read_intake({**GOOD, "adults": "12", "nkids": "2", "k1": "3", "k2": "5"})
    assert errors["nkids"] == "That is more than 12 travelers. Keep it to the people on the booking."


def test_a_trip_that_a_creator_inspired_carries_their_trip_title_not_what_the_browser_says():
    from gitaway import community
    from tests.live_trips import live_trip
    slug = live_trip(title="Santa Monica with toddlers")[0]["slug"]
    intake, _ = pfm.read_intake({**GOOD, "from": slug, "like": "FORGED TITLE"})
    assert intake["like"] == community.get(slug)["title"] and intake["like"] != "FORGED TITLE"
    intake, _ = pfm.read_intake({**GOOD, "from": "not-a-real-slug", "like": "FORGED TITLE"})
    assert intake["like"] == ""


# ---- an order ------------------------------------------------------------------------------------------------------

def test_an_order_keeps_the_price_it_was_made_at_and_starts_awaiting_payment(monkeypatch):
    uid, tenant, email = buyer()
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", "2900")
    order = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    monkeypatch.setenv("PLAN_FOR_ME_PRICE_CENTS", "9900")
    got = pfm.get(order["id"], uid)
    assert (got["status"], got["amount_cents"], got["owner_user"], got["tenant_id"], got["email"]) == ("awaiting_payment", 2900, uid, tenant, "ari.rivera@example.com")
    assert len(order["id"]) == 16 and got["intake"]["where"] == "Disneyland, California"


def test_only_the_buyer_can_read_an_order():
    uid, tenant, email = buyer("ari")
    order = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    other, _, _ = buyer("sam")
    assert pfm.get(order["id"], uid) is not None
    assert pfm.get(order["id"], other) is None
    assert pfm.get(order["id"], "") is None
    assert pfm.get("../../etc/passwd", uid) is None and pfm.get("nope", uid) is None


def test_a_person_can_have_five_unpaid_orders_and_the_oldest_goes_when_they_start_a_sixth():
    uid, tenant, email = buyer()
    made = [pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])["id"] for _ in range(6)]
    assert pfm.get(made[0], uid) is None
    assert [pfm.get(i, uid) is not None for i in made] == [False, True, True, True, True, True]


def test_a_paid_order_is_never_the_one_that_goes_when_unpaid_ones_are_trimmed():
    uid, tenant, email = buyer()
    first = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])["id"]
    pfm.set_session(first, "cs_a")
    assert pfm.mark_paid(first, "evt_a", "cs_a", 2900, "usd") == "paid"
    for _ in range(6):
        pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    assert pfm.get(first, uid)["status"] == "paid"
