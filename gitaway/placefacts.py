"""Fun facts about a place (F-222, F-223): what the matrix tells while its squares load, a short hand-written list per place, like planfacts.py.

    facts(place) -> tuple[Fact, ...]    3 to 5 facts for one of the ten places with art (gitaway/placeart.py), () for any other place
    SLUGS                               the places that have facts, keyed like places.py's `Place.slug`; a name or "san-diego" finds them too

Every fact was checked on the page in its `source` on 2026-11-12 (docs/research/place-facts.md keeps the sentence it rests on). Nothing here is written
by a model, at runtime or ever: add a fact only with a page that says it, and record it in the research doc (tests/test_placefacts.py checks both).
Left out on purpose: anything that changes fast (prices, counts of animals, rankings) or is disputed (the swallows of Capistrano).
"""

import re
from dataclasses import dataclass

CHECKED = "2026-11-12"


@dataclass(frozen=True)
class Fact:
    text: str      # one short sentence in plain words
    source: str    # the https page that says it


F = Fact
_FACTS = {
    "sandiego": (
        F("San Diego has about 70 miles of coastline, lined with one beach town after another.",
          "https://www.sandiego.org/coastal-neighborhoods"),
        F("Juan Rodriguez Cabrillo led the first European trip along the West Coast and sailed into San Diego Bay.",
          "https://www.nps.gov/cabr/learn/historyculture/juan-rodriguez-cabrillo.htm"),
        F("Gray whales swim past San Diego mostly in late December to February, at about 5 miles per hour.",
          "https://www.nps.gov/cabr/learn/nature/whale-watching.htm"),
        F("Balboa Park began in 1868, when city leaders set aside 1,400 acres of land for a park.",
          "https://www.balboapark.org/about/"),
    ),
    "losangeles": (
        F("The Hollywood Sign first read HOLLYWOODLAND, an ad for new houses, and was meant to last only a year and a half.",
          "https://en.wikipedia.org/wiki/Hollywood_Sign"),
        F("Griffith Park began in 1896 as a Christmas gift to the people of LA: 3,015 acres of land.",
          "https://griffithobservatory.lacity.gov/visit/griffith-park/"),
        F("Griffith Park has a 53-mile network of trails, fire roads and bridle paths to explore.",
          "https://griffithobservatory.lacity.gov/visit/griffith-park/"),
        F("At the La Brea Tar Pits, scientists dig up Ice Age fossils every day, right in the middle of the city.",
          "https://tarpits.org/la-brea-tar-pits-history"),
    ),
    "newyork": (
        F("To reach the Statue of Liberty's crown from the ground, you climb 377 steps.",
          "https://www.nps.gov/stli/learn/statue-of-liberty-facts.htm"),
        F("The Statue of Liberty is made of copper. It turned green all by itself as the metal aged in the air.",
          "https://www.nps.gov/stli/learn/statue-of-liberty-facts.htm"),
        F("The Empire State Building went up in just 13 months, from 1930 to 1931.",
          "https://www.esbnyc.com/about/facts-figures"),
        F("Central Park has 843 acres, about 10,000 benches, and more than 210 kinds of birds visit each year.",
          "https://www.centralparknyc.org/your-park"),
    ),
    "laketahoe": (
        F("Lake Tahoe is 1,645 feet deep at its deepest point.",
          "https://www.fs.usda.gov/r05/laketahoebasin/about-area"),
        F("Tahoe holds enough water to cover all of California, if it were flat, about 14 inches deep.",
          "https://www.keeptahoeblue.org/abouttahoe"),
        F("Lake Tahoe is the second deepest lake in America, after Oregon's Crater Lake.",
          "https://www.keeptahoeblue.org/abouttahoe"),
        F("Tahoe is 22 miles long and 12 miles wide, with 72 miles of shoreline to drive around.",
          "https://www.fs.usda.gov/r05/laketahoebasin/about-area"),
    ),
    "orlando": (
        F("Downtown's Lake Eola began as a sinkhole on cattle rancher Jacob Summerlin's land in the 1870s.",
          "https://orlando.gov/Parks-the-Environment/Directory/Lake-Eola-Park/Lake-Eola-History"),
        F("The tiered fountain in the middle of Lake Eola was built in 1957.",
          "https://orlando.gov/Parks-the-Environment/Directory/Lake-Eola-Park/Lake-Eola-History"),
        F("Gatorland, the \"Alligator Capital of the World,\" opened as a roadside attraction in 1949.",
          "https://www.blogs.gatorland.com/about.shtml"),
        F("Gatorland is home to rare white alligators, called leucistic, among thousands of gators and crocs.",
          "https://www.blogs.gatorland.com/about.shtml"),
    ),
    "palmsprings": (
        F("The Palm Springs Aerial Tramway has the world's largest rotating tram car. It spins as you ride.",
          "https://visitpalmsprings.com/media/media-kit/"),
        F("The tram's mountain station sits at 8,516 feet, about 30 degrees cooler than the desert floor.",
          "https://visitpalmsprings.com/media/media-kit/"),
        F("Palm Canyon is considered the world's largest California fan palm oasis.",
          "https://visitpalmsprings.com/media/media-kit/"),
        F("The Cahuilla people have lived in Tahquitz Canyon for at least 5,000 years.",
          "https://visitpalmsprings.com/media/media-kit/"),
    ),
    "santabarbara": (
        F("Stearns Wharf was finished in 1872 and is California's oldest working wharf.",
          "https://santabarbaraca.com/businesses/stearns-wharf/"),
        F("The Santa Barbara Mission, founded in 1786, is nicknamed the \"Queen of the Missions\" for its beauty.",
          "https://santabarbaraca.com/businesses/old-mission-santa-barbara/"),
        F("Each year artists cover the Mission's plaza in giant chalk paintings at the I Madonnari festival.",
          "https://santabarbaraca.com/businesses/old-mission-santa-barbara/"),
        F("Offshore, the Channel Islands' island fox is about the size of a house cat and lives nowhere else on Earth.",
          "https://www.nps.gov/chis/learn/nature/island-fox.htm"),
    ),
    "orangecounty": (
        F("Disneyland opened on July 17, 1955, the only Disney park built under Walt Disney's own watch.",
          "https://en.wikipedia.org/wiki/Disneyland"),
        F("The boysenberry was bred by Walter Knott's friend Rudolph Boysen, and named after him.",
          "https://www.nps.gov/home/learn/historyculture/walter-knott.htm"),
        F("George Freeth, the Father of Modern Surfing, surfed Huntington Beach the day its concrete pier opened in 1914.",
          "https://www.surfcityusa.com/history/"),
        F("Huntington Beach's nickname Surf City comes from a 1960s hit song by Jan and Dean.",
          "https://www.surfcityusa.com/history/"),
    ),
    "honolulu": (
        F("Iolani Palace in Honolulu is the only official royal residence in the United States.",
          "https://www.iolanipalace.org/"),
        F("Diamond Head got its name from sailors who thought they found diamonds. They were shiny calcite crystals.",
          "https://www.gohawaii.com/islands/oahu/regions/honolulu/leahi-diamond-head"),
        F("Diamond Head's Hawaiian name is Le'ahi, meaning \"brow of the tuna\" in English.",
          "https://www.gohawaii.com/islands/oahu/regions/honolulu/leahi-diamond-head"),
        F("The Diamond Head summit trail, built in 1908, climbs 560 feet and passes through a lit 225-foot tunnel.",
          "https://dlnr.hawaii.gov/dsp/hiking/oahu/diamond-head-summit-trail/"),
    ),
    "yosemite": (
        F("Yosemite Falls drops 2,425 feet in three parts, making it one of the world's tallest waterfalls.",
          "https://www.nps.gov/yose/planyourvisit/waterfalls.htm"),
        F("El Capitan rises over 3,000 feet above the valley floor, and Half Dome nearly 5,000.",
          "https://www.nps.gov/yose/planyourvisit/formations.htm"),
        F("In mid to late February, Horsetail Fall can glow orange at sunset, as if the waterfall were on fire.",
          "https://www.nps.gov/yose/planyourvisit/waterfalls.htm"),
        F("Mariposa Grove has over 500 giant sequoias, including the Grizzly Giant, about 3,000 years old.",
          "https://www.nps.gov/yose/planyourvisit/mg.htm"),
    ),
}
SLUGS = tuple(_FACTS)


def facts(place) -> tuple:
    """The place's facts in a fixed order, or () for a place without any."""
    return _FACTS.get(re.sub(r"[^a-z0-9]", "", str(place or "").lower())[:20], ())
