"""Made-up creators for the showcase (M4): one per place, each with a channel and a few trips. Sample content: the routes sit under /creators, which showcase.HIDDEN 404s when off."""

from dataclasses import dataclass
from urllib.parse import urlencode

PHOTOS = {"la": ("/assets/photos/venice-beach-los-angeles-hero.jpg", "Venice Beach, Los Angeles")}  # the only CC0 area photo we have; other places show none
STICKERS = {"kid": "Kid friendly", "pet": "Pet friendly", "couple": "Couple friendly"}


@dataclass(frozen=True)
class Trip:
    title: str
    place: str      # plan code: la, sd, hi, nyc
    days: int
    stickers: tuple
    forks: int
    depart: str     # future dates, 2027
    ret: str
    adults: int = 2

    def plan_href(self):
        return "/plan?" + urlencode({"to": self.place, "d": self.depart, "r": self.ret, "a": self.adults})


@dataclass(frozen=True)
class Creator:
    handle: str
    name: str
    place: str
    place_name: str
    bio: str
    channel: str
    channel_label: str
    trips: tuple


CREATORS = (
    Creator("sunny-ines", "Ines Ocampo", "la", "Los Angeles", "Mum of two filming slow beach weeks in Los Angeles. No queues if she can help it.",
            "https://www.youtube.com/@sunnyines", "YouTube",
            (Trip("Our LA family week", "la", 5, ("kid",), 128, "2027-03-05", "2027-03-10"),
             Trip("Venice to Santa Monica on foot", "la", 3, ("couple", "pet"), 41, "2027-05-14", "2027-05-17"))),
    Creator("harbor-hal", "Hal Brenner", "sd", "San Diego", "Retired sailor and his beagle, Biscuit. Sea lions, tacos and ferry rides.",
            "https://www.youtube.com/@harborhal", "YouTube",
            (Trip("San Diego with a dog", "sd", 4, ("pet",), 77, "2027-04-09", "2027-04-13"),
             Trip("Coronado for little kids", "sd", 3, ("kid",), 52, "2027-06-18", "2027-06-21"))),
    Creator("aloha-mei", "Mei Tanabe", "hi", "Honolulu", "Travels Oahu with her partner and a tiny notebook. Sunrise hikes, shave ice, long lunches.",
            "https://www.instagram.com/aloha.mei/", "Instagram",
            (Trip("Honolulu slow honeymoon", "hi", 7, ("couple",), 203, "2027-02-12", "2027-02-19"),
             Trip("Oahu with toddlers", "hi", 6, ("kid",), 96, "2027-09-03", "2027-09-09"))),
    Creator("gotham-gus", "Gus Delaney", "nyc", "New York", "Born in Queens, still finds new blocks. Short city breaks that fit a stroller.",
            "https://www.instagram.com/gotham.gus/", "Instagram",
            (Trip("New York in four days with kids", "nyc", 4, ("kid",), 164, "2027-10-08", "2027-10-12"),
             Trip("A quiet New York for two", "nyc", 3, ("couple",), 38, "2027-11-05", "2027-11-08"))),
)

PLACE_NAMES = {c.place: c.place_name for c in CREATORS}


def get(handle):
    return next((c for c in CREATORS if c.handle == handle), None)
