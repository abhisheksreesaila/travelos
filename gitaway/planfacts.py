"""What we know for sure about a few places (F-197): the facts checked against official sites (docs/research/plan-for-me-facts.md, decisions D-173 and D-174), used three ways.

    place_for(where)                  the checked place a trip's "where" names (Disneyland Resort, New York City, Oahu), or None
    checklist(where, start, today)    "What to book and when": each thing to book, soonest first, with its date counted back from the trip's first day (a date already past is "Now");
                                      a place we have not checked gets GENERIC, which says so
    intro(where)                      the line over the checklist: where its facts come from
    note_text(item)                   one checklist item as a trip note (at most tripcal.MAX_NOTE characters), written into every delivered trip
    prompt_facts(where)               the checked facts the agent may rely on, for its user message (gitaway/planforme.py)

No price and no opening hours anywhere (tests/test_planfacts.py runs every line through the agent's own filter). Re-check before a busy season: parks rename and close rides.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

CHECKED = "November 2026"


@dataclass(frozen=True)
class Book:
    """One thing to book. `how`: "opens" (a booking window opens `days` before the first day), "by" (do it at the latest `days` before), "day" (on the day itself, at the place)."""
    how: str
    days: int
    title: str
    detail: str


@dataclass(frozen=True)
class Place:
    key: str
    name: str
    words: tuple       # any of these in the trip's "where" (lower case, apostrophes and the ʻokina removed) names this place
    unless: tuple      # ... unless one of these is there too
    timezone: str
    items: tuple
    facts: tuple       # for the agent
    sources: str       # where the facts are, for people


FLIGHTS = Book("by", 60, "Flights", "Use the flight link with your plan, or your usual airline.")

DISNEYLAND = Place(
    "disneyland", "Disneyland Resort", ("disneyland", "disney california adventure", "california adventure", "downtown disney", "anaheim"), ("disney world", "paris", "tokyo", "hong kong", "shanghai"),
    "America/Los_Angeles",
    (FLIGHTS,
     Book("by", 75, "Where you stay", "Disneyland Resort hotels add a Lightning Lane Entry Benefit, and a hotel close by makes a midday rest easy."),
     Book("by", 61, "Tickets and park reservations", "Everyone 3 and up needs a ticket and a park reservation for the same park and date."),
     Book("opens", 60, "Dining reservations", "Sit-down meals can be booked up to 60 days ahead, in the Disneyland app or on the website."),
     Book("opens", 7, "Lightning Lane Premier Pass (optional)", "Sold in the app at most a week ahead, in very limited numbers."),
     Book("by", 3, "The Disneyland app", "Download it and add your tickets: Mobile Order and Lightning Lane are bought there."),
     Book("day", 0, "Lightning Lane", "Multi Pass and Single Pass are bought in the app. Single Pass: Rise of the Resistance, Radiator Springs Racers."),
     Book("day", 0, "Rider Switch", "At a ride a child is too small for, ask a cast member: one adult rides, then the other, with no second wait.")),
    ("Parks: Disneyland Park, Disney California Adventure Park, Downtown Disney District. Hotels: Disneyland Hotel, Disney's Grand Californian Hotel & Spa, Pixar Place Hotel.",
     "Height minimums in inches: Space Mountain 40, Matterhorn Bobsleds 42, Big Thunder Mountain Railroad 40, Indiana Jones Adventure 46, Star Wars: Rise of the Resistance 40, "
     "Millennium Falcon: Smugglers Run 38, Tiana's Bayou Adventure 40, Chip 'n' Dale's GADGETcoaster 35, Autopia 32 (54 to drive alone), Incredicoaster 48, "
     "Guardians of the Galaxy – Mission: BREAKOUT! 40, Radiator Springs Racers 40, Soarin' Across America 40, Goofy's Sky School 42, Grizzly River Run 42, Jumpin' Jellyfish 40, "
     "Mater's Junkyard Jamboree 32, Luigi's Rollickin' Roadsters 32.",
     "No height minimum: Dumbo the Flying Elephant, King Arthur Carrousel, Peter Pan's Flight, Mad Tea Party, Casey Jr. Circus Train, Storybook Land Canal Boats, Alice in Wonderland, "
     "The Many Adventures of Winnie the Pooh, Buzz Lightyear Astro Blasters, Finding Nemo Submarine Voyage, Jungle Cruise, Pirates of the Caribbean, Mickey & Minnie's Runaway Railway, "
     "Toy Story Midway Mania!, Monsters, Inc. Mike & Sulley to the Rescue!, Jessie's Critter Carousel, Inside Out Emotional Whirlwind, WEB SLINGERS: A Spider-Man Adventure, "
     "The Little Mermaid ~ Ariel's Undersea Adventure, Pixar Pal-A-Round.",
     "Do not plan these (seasonal or closed): \"it's a small world\", Haunted Mansion, Redwood Creek Challenge Trail, Red Car Trolley. There is no early entry.",
     "Rider Switch: at a ride a child is too small for, one adult rides while the other waits with the child, then swaps without a second wait.",
     "Lightning Lane Multi Pass (in the app on the day, or ahead with tickets) and Lightning Lane Single Pass (on the day: Rise of the Resistance, Radiator Springs Racers). Mobile Order in the Disneyland app.",
     "Baby Care Centers: Disneyland Park at the end of Main Street, U.S.A., next to First Aid; California Adventure in San Fransokyo Square.",
     "Night shows on select nights only: Fantasmic!, World of Color – ONE, the fireworks. Write \"if it runs tonight\", never a time."),
    "disneyland.disney.go.com")

NYC = Place(
    "nyc", "New York City", ("new york city", "nyc", "manhattan", "brooklyn", "new york, ny", "new york ny"), ("new york state", "upstate"),
    "America/New_York",
    (FLIGHTS,
     Book("by", 60, "Where you stay", "Near a subway line you will use most saves small legs the most."),
     Book("by", 90, "Statue of Liberty crown", "Optional: it sells out about 90 days ahead. Children must be 42 in or taller."),
     Book("by", 30, "Statue of Liberty ferry", "Reserve with Statue City Cruises, the only official seller. Boats leave from Battery Park."),
     Book("by", 14, "Museum entry", "Reserve the American Museum of Natural History and the 9/11 Museum ahead, for a set entry window."),
     Book("by", 7, "Top of the Rock", "Timed entry for a set date and window: pick the evening with the clearest forecast."),
     Book("day", 0, "The subway", "Tap a card, phone or watch on the OMNY reader. MetroCards are no longer sold.")),
    ("Statue of Liberty and Ellis Island: Statue City Cruises is the only official seller; boats from Castle Clinton in Battery Park and Liberty State Park, NJ; airport-style screening. Crown: 162 steps, children 42 in or taller.",
     "American Museum of Natural History: dinosaur halls on the 4th floor, the blue whale in the Milstein Hall of Ocean Life, the Gilder Center's insectarium and butterfly vivarium.",
     "Central Park: Belvedere Castle, Bethesda Terrace (its fountain is off for restoration), Heckscher Playground, the Central Park Carousel, Central Park Zoo.",
     "The High Line runs from Gansevoort St to 34th St, with elevators at Gansevoort, 14th, 23rd and 30th Sts; no bikes or scooters.",
     "9/11 Memorial & Museum: the museum says its historical exhibition may not be right for visitors under 10; the memorial plaza outside is fine for all ages.",
     "Top of the Rock (Rockefeller Center): timed entry. Intrepid Museum: the space shuttle Enterprise. Brooklyn Bridge walk; Brooklyn Bridge Park; Jane's Carousel in DUMBO.",
     "Subway: tap a card, phone or watch on the OMNY reader; MetroCards are no longer sold."),
    "nps.gov/stli, statuecitycruises.com, amnh.org, centralparknyc.org, thehighline.org, 911memorial.org, rockefellercenter.com, intrepidmuseum.org, brooklynbridgepark.org, mta.info")

OAHU = Place(
    "oahu", "Oahu", ("oahu", "honolulu", "waikiki", "north shore, hawaii", "ko olina", "kailua, hawaii"), (),
    "Pacific/Honolulu",
    (FLIGHTS,
     Book("by", 60, "Where you stay", "Waikiki puts the beach, the zoo and the aquarium a stroller ride apart."),
     Book("opens", 56, "USS Arizona Memorial", "On recreation.gov eight weeks ahead, and again the day before. Everyone over age 1 needs one."),
     Book("opens", 30, "Diamond Head", "Visitors from out of state must reserve, up to 30 days ahead, at gostateparks.hawaii.gov."),
     Book("by", 30, "A car and a car seat", "Hawaii law: under 2 rear-facing, 2 to under 4 a harnessed seat. Ask when you book, or bring yours."),
     Book("by", 7, "Reef-safe sunscreen", "Hawaii bans selling sunscreen with oxybenzone or octinoxate. Pack a mineral one."),
     Book("opens", 2, "Hanauma Bay", "Visitors from out of state reserve two days ahead on the city's booking site. Check which days it is open."),
     Book("day", 0, "Pearl Harbor: no bags", "Bags stay out, and strollers stop before the boat: bring a carrier for the little one.")),
    ("Hanauma Bay Nature Preserve: reserve two days ahead. The educational video is required on each visit. It is shut some days of the week, so say \"check which days it is open\". Sharp coral near shore: watch children closely in shallow water.",
     "Diamond Head State Monument: reservation for visitors from out of state; 0.8 mile, steep, the last part all stairs and a tunnel; bring water, a hat, sunscreen. Hard with a toddler unless in a carrier.",
     "Pearl Harbor National Memorial: USS Arizona Memorial program tickets on recreation.gov; no bags; strollers stop at the pre-boarding area.",
     "Calm water for little kids: the Magic Island lagoon in Ala Moana Regional Park; the Ko Olina lagoons (no lifeguards). Kailua Beach Park. Waikiki Aquarium; Honolulu Zoo in Kapiolani Park.",
     "Also: Dole Plantation, Haleiwa town on the North Shore, Waimea Valley, Kualoa Ranch, Polynesian Cultural Center (closed some days each week).",
     "Sea turtles: stay at least 10 feet away, on land and in the water. Sunscreen without oxybenzone or octinoxate.",
     "Car seats by Hawaii law: under 2 rear-facing; 2 to under 4 a harnessed seat; 4 to under 10 a harnessed seat or a booster."),
    "honolulu.gov/dpr, gostateparks.hawaii.gov, dlnr.hawaii.gov, nps.gov/perl, recreation.gov, gohawaii.com, koolina.com, fisheries.noaa.gov, capitol.hawaii.gov")

PLACES = {p.key: p for p in (DISNEYLAND, NYC, OAHU)}

GENERIC = (FLIGHTS,
           Book("by", 45, "Where you stay", "Close to the places on your busiest days saves the most time with kids."),
           Book("by", 30, "Timed entry", "We have not checked this place: look up each big sight on its official site, as many sell timed entry."),
           Book("by", 14, "Car seats", "If you rent a car, ask for car seats when you book it, or bring your own."),
           Book("by", 2, "Offline maps", "Save the area's map on your phone for when the signal drops."))


def _plain(text) -> str:
    return re.sub(r"['’ʻ`]", "", str(text or "").lower())


def place_for(where) -> Place | None:
    t = _plain(where)
    for p in PLACES.values():
        if any(w in t for w in p.words) and not any(u in t for u in p.unless):
            return p
    return None


def _day(d) -> str:
    return f"{d:%a}, {d:%b} {d.day}"


def checklist(where, start, today) -> list:
    """The things to book for a trip to `where` starting on `start`, soonest first: [{"when": date or None (on the day), "label", "title", "detail", "now": the date has passed (it says
    "Now" and `when` is today)}]. A checked place gets its own list, any other place GENERIC."""
    p = place_for(where)
    out = []
    for b in (p.items if p else GENERIC):
        if b.how == "day":
            out.append({"when": None, "label": "On the day", "title": b.title, "detail": b.detail, "now": False})
            continue
        due = start - timedelta(days=b.days)
        now = due <= today
        out.append({"when": today if now else due, "label": "Now" if now else ("Opens " if b.how == "opens" else "By ") + _day(due), "title": b.title, "detail": b.detail, "now": now})
    return sorted(out, key=lambda i: (i["when"] is None, i["when"] or date.max))


def intro(where) -> str:
    p = place_for(where)
    if p:
        return f"From {p.name}'s official sites, checked in {CHECKED}. Dates count back from your first day."
    return "We have not checked this place's booking rules yet, so this is a general list. Dates count back from your first day."


def note_text(item, limit=140) -> str:
    """One checklist item as a trip note: "By Fri, Jan 15 · Flights: Use the flight link..." cut at a word to fit `limit` (tripcal.MAX_NOTE)."""
    text = f"{'Book now' if item['now'] else item['label']} · {item['title']}: {item['detail']}"
    if len(text) <= limit:
        return text
    return text[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,:;·-")


def prompt_facts(where) -> list:
    p = place_for(where)
    return list(p.facts) if p else []
