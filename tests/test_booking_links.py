"""F-198: any destination by name, and the exact deep links each lane builds. The Lake Tahoe case is docs/research/booking-any-trip.md section 3."""

from datetime import date

import pytest

from gitaway.partners import links, places

TAHOE = links.Search(places.resolve("Lake Tahoe"), date(2026, 12, 19), date(2026, 12, 26), 2, (8, 11), home="SFO")


# ---- places ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("typed", ["Lake Tahoe", "lake tahoe", "  Lake   Tahoe, CA ", "Tahoe", "South Lake Tahoe, California"])
def test_lake_tahoe_is_reno(typed):
    p = places.resolve(typed)
    assert (p.name, p.city, p.region, p.iata, p.snow, p.known) == ("Lake Tahoe", "South Lake Tahoe", "California", "RNO", True, True)
    assert [name for name, _ in p.resorts] == ["Heavenly", "Northstar", "Kirkwood", "Palisades Tahoe", "Sierra-at-Tahoe"]


def test_an_unknown_place_is_its_own_town_with_no_airport():
    p = places.resolve("Bend, Oregon")
    assert (p.name, p.city, p.region, p.iata, p.snow, p.known, p.klook) == ("Bend, Oregon", "Bend", "Oregon", "", False, False, False)


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


# ---- the Tahoe links, exactly --------------------------------------------------------------------------------------

def test_tahoe_flight_from_sfo():
    assert links.aviasales(TAHOE) == "https://www.aviasales.com/search/SFO1912RNO261222"


def test_tahoe_flight_without_a_home_airport_lets_aviasales_ask():
    s = links.Search(TAHOE.place, TAHOE.depart, TAHOE.return_, 2, (8, 11))
    assert links.aviasales(s) == "https://www.aviasales.com/?destination_iata=RNO&depart_date=2026-12-19&return_date=2026-12-26&adults=2&children=2"


def test_no_flight_link_without_a_destination_airport():
    s = links.Search(places.resolve("Bend, Oregon"), TAHOE.depart, TAHOE.return_, 2, (8, 11), home="SFO")
    assert links.aviasales(s) is None


def test_tahoe_stays():
    assert links.expedia_stay(TAHOE) == ("https://www.expedia.com/go/hotel/search/Destination/2026-12-19/2026-12-26?CityName=South%20Lake%20Tahoe"
                                         "&NumRoom=1&NumAdult-Room1=2&NumChild-Room1=2&Room1-Child1Age=8&Room1-Child2Age=11")
    assert links.airbnb_stay(TAHOE) == "https://www.airbnb.com/s/South-Lake-Tahoe--California/homes?checkin=2026-12-19&checkout=2026-12-26&adults=2&children=2"
    assert links.vrbo_stay(TAHOE) == ("https://www.vrbo.com/search?destination=South%20Lake%20Tahoe%2C%20California&startDate=2026-12-19&endDate=2026-12-26"
                                      "&adults=2&children=1_8%2C1_11")
    assert links.booking_stay(TAHOE) == ("https://www.booking.com/searchresults.html?ss=South+Lake+Tahoe%2C+California&checkin=2026-12-19&checkout=2026-12-26"
                                         "&group_adults=2&group_children=2&age=8&age=11&no_rooms=1&lang=en-us&selected_currency=USD")


def test_tahoe_car_is_an_suv_with_chains_and_a_ski_rack():
    assert links.expedia_car(TAHOE) == ("https://www.expedia.com/go/car/search/Airport/2026-12-19/2026-12-26?PickUpLoc=RNO&DiffDropLoc=0"
                                        "&PickUpTime=11AM&DropTime=11AM&Class=SUV&Equipment=W,S")


def test_a_summer_snow_place_and_a_city_get_no_winter_gear():
    summer = links.Search(TAHOE.place, date(2027, 7, 3), date(2027, 7, 10), 2, ())
    assert links.expedia_car(summer).endswith("&Class=NoPreference")
    city = links.Search(places.resolve("Seattle"), TAHOE.depart, TAHOE.return_, 2, (8, 11))
    assert "Equipment" not in links.expedia_car(city) and "Class=NoPreference" in links.expedia_car(city)


def test_a_big_party_gets_a_minivan():
    s = links.Search(places.resolve("Orlando"), date(2027, 4, 1), date(2027, 4, 6), 2, (3, 5, 8, 10))
    assert "Class=MiniVan" in links.expedia_car(s)


def test_a_car_with_no_airport_searches_near_the_town():
    s = links.Search(places.resolve("Bend, Oregon"), TAHOE.depart, TAHOE.return_, 2, ())
    assert links.expedia_car(s) == ("https://www.expedia.com/go/car/search/Place/2026-12-19/2026-12-26?PickUpLoc=Bend%2C%20Oregon&Distance=10"
                                    "&PickUpTime=11AM&DropTime=11AM&Class=NoPreference")


def test_tahoe_things_to_do_keep_the_full_days():
    assert links.getyourguide(TAHOE) == "https://www.getyourguide.com/s/?q=Lake%20Tahoe&date_from=2026-12-20&date_to=2026-12-25"
    one_night = links.Search(TAHOE.place, date(2026, 12, 19), date(2026, 12, 20), 2, ())
    assert links.getyourguide(one_night).endswith("date_from=2026-12-19&date_to=2026-12-20")


def test_party_bands_per_site():
    """A 14-year-old is an adult on Aviasales and Airbnb, a child with an age on Expedia, Vrbo and Booking.com; a baby is an infant."""
    s = links.Search(places.resolve("San Diego"), date(2027, 3, 5), date(2027, 3, 9), 2, (0, 6, 14), home="SFO")
    assert links.aviasales(s) == "https://www.aviasales.com/search/SFO0503SAN0903311"
    assert links.airbnb_stay(s).endswith("adults=3&children=1&infants=1")
    assert "NumChild-Room1=3&Room1-Child1Age=0&Room1-Child2Age=6&Room1-Child3Age=14" in links.expedia_stay(s)
    assert links.vrbo_stay(s).endswith("adults=2&children=1_0%2C1_6%2C1_14")


def test_klook_pages():
    disney = links.Search(places.resolve("Disneyland"), TAHOE.depart, TAHOE.return_, 2, (5,))
    assert links.klook_todo(disney) == "https://www.klook.com/en-US/destination/p50042790-disneyland-resort/"
    assert links.klook_stay(disney) == "https://www.klook.com/en-US/search/result/?query=Anaheim%20hotels"
    honolulu = links.Search(places.resolve("Oahu"), TAHOE.depart, TAHOE.return_, 2, ())
    assert links.klook_todo(honolulu) == "https://www.klook.com/en-US/search/result/?query=Honolulu%20attractions"
    assert links.klook_stay(TAHOE) is None and links.klook_todo(TAHOE) is None     # Klook is thin at Tahoe: plain links take over (D-221)


def test_no_link_carries_an_affiliate_parameter():
    for build in (links.aviasales, links.expedia_stay, links.airbnb_stay, links.vrbo_stay, links.booking_stay, links.expedia_car, links.getyourguide):
        url = build(TAHOE)
        assert not any(k in url.lower() for k in ("marker", "affid", "aid=", "affcid", "partner_id", "sub_id", "mdpcid")), url
