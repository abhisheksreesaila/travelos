"""Three example plans for the Plan it for me offer (F-197), written by hand as the agent's answer would be (`planforme.SCHEMA`), so they go through the same `planforme.validate()` a paid
plan does and look exactly like a delivered one. Every named place, ride and rule is from docs/research/plan-for-me-facts.md (checked on the official sites in November 2026); no prices,
no opening hours. The dates are the first matching weekday at least LEAD days from today, so the "What to book and when" dates are always ahead.

    EXAMPLES                 slug -> Example, in the order the offer shows them
    get(slug)                the Example or None
    intake(example, today)   the intake the plan was "ordered" with (dates computed from today)
    plan(example, today)     the validated plan
"""

from dataclasses import dataclass
from datetime import timedelta

LEAD = 80      # days from today to an example trip's first day: past the 75-day "where you stay" date, so every date on its checklist is still ahead


def S(time, minutes, kind, what, place="", note=""):
    return {"time": time, "minutes": minutes, "kind": kind, "what": what, "place": place, "place_sure": bool(place), "note": note}


@dataclass(frozen=True)
class Example:
    slug: str
    label: str           # the card's title on the offer
    blurb: str           # the card's one line
    where: str
    adults: int
    kids: tuple
    heights: tuple
    weekday: int         # 0 Monday: the day the trip starts
    pace: str
    answer: dict


DISNEYLAND = Example(
    "disneyland", "Disneyland Resort, 3 days", "Kids 3 and 7: rope drop, Rider Switch, a nap at midday.", "Disneyland, California", 2, (3, 7), (38, 48), 0, "balanced",
    {"title": "Disneyland with a 3- and a 7-year-old",
     "summary": "Three days built around a 3-year-old and a 7-year-old: rope drop for the little one's rides, a nap at midday and early nights.",
     "timezone": "America/Los_Angeles",
     "days": [
         {"stops": [S("10:00 AM", 90, "travel", "Arrive and check in", note="Leave the bags at the hotel and walk in light."),
                    S("11:45 AM", 60, "food", "Lunch", "Downtown Disney District", "Mobile Order in the Disneyland app saves a line with hungry kids."),
                    S("1:00 PM", 75, "fun", "Cars Land", "Mater's Junkyard Jamboree", "32 in: both kids ride. Luigi's Rollickin' Roadsters next door is 32 in too."),
                    S("2:30 PM", 60, "fun", "Big kid ride", "Radiator Springs Racers", "40 in: the 7-year-old rides with one adult, the other uses Rider Switch with the 3-year-old."),
                    S("3:45 PM", 90, "travel", "Rest at the hotel", note="The 3-year-old naps, everyone else recharges for the evening."),
                    S("5:30 PM", 75, "fun", "Pixar Pier", "Toy Story Midway Mania!", "No height minimum: everyone plays. Pixar Pal-A-Round has none either."),
                    S("7:00 PM", 60, "food", "Dinner near Pixar Pier", note="A light dinner now keeps bedtime on track."),
                    S("8:15 PM", 30, "travel", "Back to the hotel", note="Lay out tomorrow's clothes: day two starts at rope drop.")]},
         {"stops": [S("8:00 AM", 90, "fun", "Rope drop", "Fantasyland", "No height minimum: Peter Pan's Flight, Dumbo and Alice in Wonderland while the 3-year-old is fresh."),
                    S("9:45 AM", 60, "fun", "Big rides", "Space Mountain", "40 in: the 7-year-old rides, then Rider Switch. A Lightning Lane Multi Pass shortens this wait."),
                    S("11:00 AM", 60, "fun", "Fly the Falcon", "Millennium Falcon: Smugglers Run", "38 in: both kids can fly it, a rare big one for the 3-year-old."),
                    S("12:15 PM", 60, "food", "Lunch on Main Street, U.S.A.", note="The Baby Care Center is at the end of Main Street, U.S.A., next to First Aid."),
                    S("1:15 PM", 150, "travel", "Midday rest at the hotel", note="Nap, a swim, quiet time: the evening goes better for everyone."),
                    S("4:00 PM", 75, "fun", "Adventureland", "Jungle Cruise", "No height minimum. Pirates of the Caribbean is next door for a second ride."),
                    S("5:45 PM", 75, "food", "Dinner", "New Orleans Square", "A sit-down dinner: book it ahead, up to 60 days out."),
                    S("7:15 PM", 45, "fun", "Last ride", "Mickey & Minnie's Runaway Railway", "No height minimum, and a gentle last ride before bed.")]},
         {"stops": [S("8:00 AM", 75, "fun", "Rope drop", "Avengers Campus", "WEB SLINGERS first, with no height minimum. Guardians of the Galaxy is 40 in, for the 7-year-old."),
                    S("9:30 AM", 60, "fun", "Pixar Pier", "Incredicoaster", "48 in: only if your 7-year-old measures 48 in at the ride. Inside Out Emotional Whirlwind has no minimum."),
                    S("10:45 AM", 45, "fun", "Last ride", "Jessie's Critter Carousel", "No height minimum: the 3-year-old picks the last ride."),
                    S("11:45 AM", 60, "food", "Lunch", "Downtown Disney District", "Mobile Order again, then one last look at the shops."),
                    S("1:00 PM", 90, "travel", "Check out and head home", note="Snacks and a story for the trip back: the 3-year-old will likely sleep.")]}],
     "tips": ["Measure both kids in their park shoes before you go: their height decides which of the big rides they can do.",
              "Use Rider Switch at every ride the 3-year-old is too small for: both adults ride and nobody waits twice.",
              "Rain backup: Pirates of the Caribbean, Runaway Railway and Toy Story Midway Mania! are all indoors."]})

NYC = Example(
    "new-york-city", "New York City, 4 days", "Kids 8 and 11: dinosaurs, the Statue, the bridge, a sky deck.", "New York City", 2, (8, 11), (), 3, "balanced",
    {"title": "New York City with an 8- and an 11-year-old",
     "summary": "Four days for an 8- and an 11-year-old: one big sight each morning, a park or a walk each afternoon, and early dinners.",
     "timezone": "America/New_York",
     "days": [
         {"stops": [S("1:00 PM", 90, "travel", "Arrive and check in", note="Drop the bags and get the kids moving: fresh air beats a nap on day one."),
                    S("3:00 PM", 120, "outdoors", "Walk to Belvedere Castle", "Central Park", "Pass the Central Park Carousel and Bethesda Terrace on the way. Its fountain is off for restoration."),
                    S("6:00 PM", 75, "food", "Early dinner near the hotel", note="An early night: tomorrow is the big museum.")]},
         {"stops": [S("9:30 AM", 150, "culture", "Dinosaurs", "American Museum of Natural History", "Dinosaur halls on the 4th floor first, then the blue whale in the Milstein Hall of Ocean Life."),
                    S("12:15 PM", 60, "food", "Lunch near the museum"),
                    S("1:30 PM", 75, "culture", "Butterflies", "Gilder Center", "The insectarium and the butterfly vivarium are in the museum's Gilder Center."),
                    S("3:15 PM", 90, "outdoors", "Play time", "Heckscher Playground", "In Central Park: a good run-around after a morning of looking."),
                    S("5:45 PM", 60, "food", "Dinner"),
                    S("7:15 PM", 75, "fun", "City lights", "Top of the Rock", "Timed entry: book the evening with the clearest forecast.")]},
         {"stops": [S("8:30 AM", 30, "travel", "Subway to Battery Park", note="Tap a card, phone or watch on the OMNY reader."),
                    S("9:00 AM", 210, "culture", "Ferry", "Statue of Liberty", "Boats leave from Castle Clinton in Battery Park. Expect airport-style screening before you board."),
                    S("12:45 PM", 60, "food", "Lunch in Lower Manhattan"),
                    S("2:00 PM", 60, "culture", "Memorial plaza", "9/11 Memorial & Museum", "The plaza and its pools suit both kids. The museum says its main exhibition may not suit under-10s."),
                    S("3:30 PM", 75, "outdoors", "Walk", "Brooklyn Bridge", "Stay on the walkway: the bike lane is down on the road now."),
                    S("5:00 PM", 60, "fun", "Jane's Carousel", "Brooklyn Bridge Park", "In DUMBO, in a glass pavilion by the water."),
                    S("6:15 PM", 75, "food", "Dinner in DUMBO")]},
         {"stops": [S("9:00 AM", 60, "food", "Breakfast near the hotel"),
                    S("10:15 AM", 120, "culture", "Space shuttle", "Intrepid Museum", "The space shuttle Enterprise is in the Space Shuttle Pavilion."),
                    S("12:45 PM", 75, "outdoors", "Walk", "The High Line", "Start at 34th St and head south. Elevators at 30th, 23rd and 14th Sts for tired legs."),
                    S("2:15 PM", 60, "food", "Late lunch near the High Line"),
                    S("3:30 PM", 90, "travel", "Head to the airport", note="Pack snacks: the trip out of the city can be slow.")]}],
     "tips": ["The 9/11 Museum says its main exhibition may not suit visitors under 10, so the plaza is the stop for your 8-year-old.",
              "Rain backup: swap day two's playground for more of the museum, and day four's High Line for the Intrepid's indoor halls.",
              "Good shoes for everyone: this plan walks a lot, and the subway stairs add up."]})

OAHU = Example(
    "oahu", "Oahu, 5 days", "A toddler: calm lagoons, one outing a morning, a long nap.", "Oahu, Hawaii", 2, (2,), (), 2, "relaxed",
    {"title": "Oahu at a toddler's pace",
     "summary": "Five slow days around a two-year-old: one outing each morning, a long nap at midday, calm water and early dinners.",
     "timezone": "Pacific/Honolulu",
     "days": [
         {"stops": [S("2:00 PM", 90, "travel", "Pick up the car and check in", note="Hawaii law: a 2-year-old rides in a harnessed car seat. Ask for one when you book the car."),
                    S("4:30 PM", 75, "outdoors", "Sand time", "Waikiki", "Toes in the sand and an easy first evening."),
                    S("6:00 PM", 60, "food", "Early dinner in Waikiki")]},
         {"stops": [S("7:30 AM", 60, "travel", "Drive to Pearl Harbor", note="Bags stay out, and strollers stop before the boat: bring a carrier."),
                    S("8:30 AM", 150, "culture", "Boat", "USS Arizona Memorial", "Book on recreation.gov. Your toddler needs a reservation too: everyone over age 1 does."),
                    S("11:30 AM", 60, "food", "Lunch on the way back"),
                    S("1:00 PM", 120, "travel", "Nap at the hotel"),
                    S("3:30 PM", 90, "outdoors", "Calm water", "Magic Island lagoon", "In Ala Moana Regional Park: a protected lagoon, gentle for a toddler."),
                    S("5:30 PM", 60, "food", "Dinner near Ala Moana")]},
         {"stops": [S("8:30 AM", 90, "culture", "Reef fish", "Waikiki Aquarium", "Small enough to see before nap time."),
                    S("10:15 AM", 75, "outdoors", "Picnic", "Kapiolani Park", "Between the aquarium and the zoo."),
                    S("12:00 PM", 150, "travel", "Nap at the hotel"),
                    S("3:00 PM", 90, "fun", "Animals", "Honolulu Zoo", "In Kapiolani Park."),
                    S("5:30 PM", 60, "food", "Early dinner")]},
         {"stops": [S("8:00 AM", 30, "food", "Breakfast in the room"),
                    S("8:45 AM", 150, "outdoors", "Snorkel and sand", "Hanauma Bay", "Watch the video first: it is required. Sharp coral near shore, so hold the little one in the shallows."),
                    S("11:45 AM", 60, "food", "Lunch on the way back"),
                    S("1:00 PM", 120, "travel", "Nap at the hotel"),
                    S("4:00 PM", 90, "outdoors", "Beach afternoon", "Kailua Beach Park", "Sea turtles: stay at least 10 feet away, on the sand and in the water."),
                    S("6:00 PM", 60, "food", "Dinner in Kailua")]},
         {"stops": [S("8:00 AM", 45, "food", "Breakfast in the room"),
                    S("9:15 AM", 90, "fun", "Pineapples", "Dole Plantation", "On the way inland: pick up snacks for the flight."),
                    S("11:00 AM", 60, "food", "Early lunch"),
                    S("12:30 PM", 90, "travel", "Return the car and fly home", note="Swim things and the carrier go in the carry-on.")]}],
     "tips": ["Diamond Head is steep with stairs at the end: skip it with a toddler, or go with a carrier and reserve 30 days ahead.",
              "Pack mineral sunscreen: Hawaii bans selling ones with oxybenzone or octinoxate.",
              "Rain backup: the Waikiki Aquarium and a slow lunch, then a longer nap."]})

EXAMPLES = {e.slug: e for e in (DISNEYLAND, NYC, OAHU)}


def get(slug):
    return EXAMPLES.get(slug) if isinstance(slug, str) else None


def intake(example, today) -> dict:
    first = today + timedelta(days=LEAD)
    first += timedelta(days=(example.weekday - first.weekday()) % 7)
    days = len(example.answer["days"])
    return {"where": example.where, "start": first.isoformat(), "end": (first + timedelta(days=days - 1)).isoformat(), "home": "", "adults": example.adults, "kids": list(example.kids),
            "heights": list(example.heights) or [None] * len(example.kids), "budget": "comfortable", "must": "", "pace": example.pace, "like": ""}


def plan(example, today) -> dict:
    from gitaway import planforme      # here: planforme imports the pages' helpers
    return planforme.validate(example.answer, intake(example, today))
