"""The ride link on Today. Everything else the partner seam did (Travelpayouts, Aviasales, Klook, /go, /book, the sandbox checkout) is gone (F-297, D-971): tests/test_no_affiliate.py holds that."""

from gitaway.partners import uber_deep_link


def test_uber_deep_link():
    assert uber_deep_link("SFO", "Waikiki") == "https://m.uber.com/ul/?action=setPickup&pickup[formatted_address]=SFO&dropoff[formatted_address]=Waikiki"


def test_uber_deep_link_without_a_pickup_starts_from_where_the_rider_is():
    assert uber_deep_link("", "Waikiki") == "https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=Waikiki"
