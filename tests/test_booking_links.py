"""F-198: any destination by name. The Lake Tahoe case is docs/research/booking-any-trip.md section 3. (The deep links each lane built went with the affiliate paths, F-297.)"""

import pytest

from gitaway.partners import places


# ---- places ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("typed", ["Lake Tahoe", "lake tahoe", "  Lake   Tahoe, CA ", "Tahoe", "South Lake Tahoe, California"])
def test_lake_tahoe_is_reno(typed):
    p = places.resolve(typed)
    assert (p.name, p.city, p.region, p.iata, p.known) == ("Lake Tahoe", "South Lake Tahoe", "California", "RNO", True)


def test_an_unknown_place_is_its_own_town_with_no_airport():
    p = places.resolve("Bend, Oregon")
    assert (p.name, p.city, p.region, p.iata, p.known) == ("Bend, Oregon", "Bend", "Oregon", "", False)


def test_a_typed_airport_wins_and_is_checked():
    assert places.resolve("Bend, Oregon", "rdm").iata == "RDM"
    assert places.resolve("Lake Tahoe", "sfo").iata == "SFO"
    assert places.resolve("Lake Tahoe", "RENO").iata == "RNO"      # not three letters: ignored, the table's airport stays
    assert places.clean_iata("r1o") == "" and places.clean_iata(" sea ") == "SEA"


def test_nothing_typed_is_no_place_and_control_characters_go():
    assert places.resolve("   ") is None and places.resolve(None) is None
    assert places.resolve("Bend\x00\x07, OR").name == "Bend, OR"
    assert len(places.resolve("x" * 500).name) == places.MAX_NAME


def test_slug_is_letters_and_digits():
    assert places.resolve("Lake Tahoe").slug == "laketahoe"
    assert places.resolve("Washington, DC").slug == "washingtondc"
    assert places.resolve("!!!").slug == "place"
