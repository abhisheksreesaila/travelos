"""Fixture data for the TravelOS search results page.

All simulated data lives here so the search page can render deterministically
without calling any travel providers. This module reads PUBLIC_TRIPS from
data.py but does not modify it.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Searchable cities
# ---------------------------------------------------------------------------

SEARCHABLE_CITIES = [
    "London",
    "Granada",
    "Kyoto",
    "Lisbon",
    "Copenhagen",
    "Oaxaca",
    "Cape Town",
]

# ---------------------------------------------------------------------------
# 2. Top places (10 per city)
# ---------------------------------------------------------------------------

TOP_PLACES: dict[str, list[dict[str, str]]] = {
    "granada": [
        {
            "name": "Alhambra",
            "category": "Historic Site",
            "description": "A sprawling hilltop palace-fortress where carved plaster, reflecting pools, and the Sierra Nevada backdrop create a morning that stays with you.",
            "tone": "plum",
        },
        {
            "name": "Albaicín",
            "category": "Neighborhood",
            "description": "Wind uphill through whitewashed lanes and tiled courtyards until the city spreads out beneath you like a postcard.",
            "tone": "sun",
        },
        {
            "name": "Sacromonte",
            "category": "Neighborhood",
            "description": "Cave homes carved into the hillside, flamenco that starts after midnight, and views that make you forget the climb.",
            "tone": "plum",
        },
        {
            "name": "Generalife",
            "category": "Garden",
            "description": "The sultans' summer escape—a cascade of water channels, cypress arches, and rose gardens just above the Alhambra.",
            "tone": "mint",
        },
        {
            "name": "Granada Cathedral",
            "category": "Landmark",
            "description": "A vast Renaissance interior of white and gold that feels unexpectedly airy after the narrow streets outside.",
            "tone": "sky",
        },
        {
            "name": "Parque de las Ciencias",
            "category": "Museum",
            "description": "An interactive science park with a butterfly house, planetarium, and exhibits that pull kids and adults into the same curiosity.",
            "tone": "sky",
        },
        {
            "name": "Sierra Nevada",
            "category": "Park",
            "description": "Drive forty minutes from orange trees to snow-dusted peaks, where hiking trails and mountain silence reset your clock.",
            "tone": "mint",
        },
        {
            "name": "Baños Árabes",
            "category": "Historic Site",
            "description": "A candlelit 11th-century bathhouse where the steam rises under star-pierced vaults and time softens.",
            "tone": "plum",
        },
        {
            "name": "Calle Navas Tapas Crawl",
            "category": "Food",
            "description": "The famous tapas street where every drink comes with a small plate and each bar competes to surprise you.",
            "tone": "sun",
        },
        {
            "name": "Mirador de San Nicolás",
            "category": "Viewpoint",
            "description": "The postcard terrace where guitar players gather at sunset and the Alhambra glows pink across the valley.",
            "tone": "sun",
        },
    ],
    "kyoto": [
        {
            "name": "Fushimi Inari Taisha",
            "category": "Historic Site",
            "description": "Thousands of vermilion torii gates snake up the mountainside, best walked at dawn when the light filters through like stained glass.",
            "tone": "plum",
        },
        {
            "name": "Arashiyama Bamboo Grove",
            "category": "Park",
            "description": "A narrow path through towering green stalks that creak and sway in the wind like a living instrument.",
            "tone": "mint",
        },
        {
            "name": "Kinkaku-ji",
            "category": "Historic Site",
            "description": "The Golden Pavilion floats above a mirror pond, every inch of its top two stories covered in gold leaf.",
            "tone": "sun",
        },
        {
            "name": "Gion District",
            "category": "Neighborhood",
            "description": "Wooden machiya townhouses, stone-paved lanes, and the chance of spotting a geiko hurrying to an evening appointment.",
            "tone": "plum",
        },
        {
            "name": "Nishiki Market",
            "category": "Market",
            "description": "Kyoto's kitchen—a covered arcade of pickle stalls, fresh mochi, knife shops, and skewers grilling over binchotan charcoal.",
            "tone": "sun",
        },
        {
            "name": "Philosopher's Path",
            "category": "Park",
            "description": "A stone walkway along a cherry-tree-lined canal that invites slow thinking, especially in early April or late November.",
            "tone": "mint",
        },
        {
            "name": "Ryoan-ji",
            "category": "Historic Site",
            "description": "Japan's most famous rock garden—fifteen stones on raked white gravel, arranged so you can never see all of them at once.",
            "tone": "sky",
        },
        {
            "name": "Nijo Castle",
            "category": "Historic Site",
            "description": "A shogun's residence with nightingale floors that chirp underfoot and sliding doors painted with tigers and pine.",
            "tone": "plum",
        },
        {
            "name": "Pontocho Alley",
            "category": "Food",
            "description": "A narrow lantern-lit lane along the Kamo River where tiny restaurants seat six and the kaiseki courses keep coming.",
            "tone": "sun",
        },
        {
            "name": "Kurama Onsen",
            "category": "Historic Site",
            "description": "A mountain hot spring an hour north of the city where you soak outdoors under cedar trees and forget what day it is.",
            "tone": "sky",
        },
    ],
    "lisbon": [
        {
            "name": "Belém Tower",
            "category": "Landmark",
            "description": "A stone fortress rising from the Tagus River like carved lace, guarding the harbor where explorers once departed.",
            "tone": "sun",
        },
        {
            "name": "Alfama",
            "category": "Neighborhood",
            "description": "A labyrinth of steep alleys, laundry lines, and sudden viewpoints where fado drifts from open windows.",
            "tone": "plum",
        },
        {
            "name": "Jerónimos Monastery",
            "category": "Historic Site",
            "description": "Manueline stonework so detailed it looks like spun sugar, housing Vasco da Gama's tomb beneath vaulted ceilings.",
            "tone": "sky",
        },
        {
            "name": "LX Factory",
            "category": "Market",
            "description": "A former industrial complex turned creative village with bookshops, rooftop bars, and the smell of fresh pastéis.",
            "tone": "mint",
        },
        {
            "name": "Tram 28",
            "category": "Landmark",
            "description": "The rickety yellow tram that rattles through the oldest quarters, hanging on tight corners and offering the city's best rolling tour.",
            "tone": "sun",
        },
        {
            "name": "Time Out Market",
            "category": "Food",
            "description": "A vaulted food hall where the city's best chefs serve everything from salt cod fritters to chocolate cake under one roof.",
            "tone": "sun",
        },
        {
            "name": "São Jorge Castle",
            "category": "Landmark",
            "description": "A hilltop Moorish castle with peacocks strolling the ramparts and a panoramic sweep from the bridge to the Atlantic.",
            "tone": "plum",
        },
        {
            "name": "Oceanário de Lisboa",
            "category": "Museum",
            "description": "Europe's largest indoor aquarium, centered on a massive central tank where sunfish and sharks glide past in slow motion.",
            "tone": "sky",
        },
        {
            "name": "Pink Street",
            "category": "Food",
            "description": "A vivid stretch of painted pavement lined with late-night bars where the party doesn't start until midnight.",
            "tone": "plum",
        },
        {
            "name": "Miradouro da Senhora do Monte",
            "category": "Viewpoint",
            "description": "The highest natural lookout in Lisbon, where locals bring wine at sunset and the city tiles turn gold below.",
            "tone": "sun",
        },
    ],
    "copenhagen": [
        {
            "name": "Nyhavn",
            "category": "Landmark",
            "description": "A candy-colored 17th-century waterfront where tall ships bob beside canal-side tables and the herring plates arrive cold and perfect.",
            "tone": "sun",
        },
        {
            "name": "Tivoli Gardens",
            "category": "Garden",
            "description": "The amusement park that inspired Disney, where fairy lights, wooden roller coasters, and flower beds feel timeless.",
            "tone": "mint",
        },
        {
            "name": "Christiania",
            "category": "Neighborhood",
            "description": "A self-governing freetown of handmade houses, murals, and vegetarian cafés where creativity runs entirely on its own rules.",
            "tone": "plum",
        },
        {
            "name": "Rosenborg Castle",
            "category": "Museum",
            "description": "A Dutch Renaissance palace holding the crown jewels in a treasury beneath turreted towers and the King's Garden.",
            "tone": "sky",
        },
        {
            "name": "The Round Tower",
            "category": "Landmark",
            "description": "A 17th-century observatory with a spiral ramp instead of stairs, leading to a rooftop view over copper spires and red tile.",
            "tone": "sky",
        },
        {
            "name": "Reffen Street Food",
            "category": "Food",
            "description": "An open-air market on Refshaleøen where shipping containers house kitchens from every continent and fires burn by the waterfront.",
            "tone": "sun",
        },
        {
            "name": "Designmuseum Denmark",
            "category": "Museum",
            "description": "A recently renovated temple of Danish chairs, lamps, and textiles that explains why the whole city looks the way it does.",
            "tone": "sky",
        },
        {
            "name": "Assistens Cemetery",
            "category": "Park",
            "description": "A park-like burial ground in Nørrebro where locals picnic beside Kierkegaard's grave and the cherry trees bloom in spring.",
            "tone": "mint",
        },
        {
            "name": "Louisiana Museum",
            "category": "Museum",
            "description": "A coastal museum thirty minutes north where sculpture gardens meet the sea and the Giacometti room stops you in your tracks.",
            "tone": "sky",
        },
        {
            "name": "Torvehallerne",
            "category": "Market",
            "description": "Two glass market halls near Nørreport filled with smørrebrød counters, fresh berries, pour-over coffee, and Danish pastries.",
            "tone": "sun",
        },
    ],
    "london": [
        {
            "name": "Tower of London",
            "category": "Historic Site",
            "description": "A medieval fortress on the Thames where Beefeaters tell stories of ravens, crowns, and prisoners who never left.",
            "tone": "plum",
        },
        {
            "name": "British Museum",
            "category": "Museum",
            "description": "The Great Court's glass roof floods the world's collected history in daylight—the Rosetta Stone is only the beginning.",
            "tone": "sky",
        },
        {
            "name": "Borough Market",
            "category": "Market",
            "description": "A thousand-year-old food market under railway arches where raclette scrapes onto potatoes and the doughnuts sell out by noon.",
            "tone": "sun",
        },
        {
            "name": "Sky Garden",
            "category": "Viewpoint",
            "description": "A free indoor garden on the 35th floor of the Walkie-Talkie with 360-degree views and a bar that opens at sunset.",
            "tone": "mint",
        },
        {
            "name": "Camden Lock",
            "category": "Market",
            "description": "Canalside chaos of vintage stalls, neon signs, street-food smoke, and the sound of a bass line drifting from a nearby venue.",
            "tone": "plum",
        },
        {
            "name": "Hyde Park",
            "category": "Park",
            "description": "London's green lung—row a boat on the Serpentine, argue at Speaker's Corner, or just lie in the grass until the city fades.",
            "tone": "mint",
        },
        {
            "name": "Southbank Centre",
            "category": "Landmark",
            "description": "A riverside stretch of concrete brutalism and culture where skateboarders roll under the Queen Elizabeth Hall and the book market tempts on weekends.",
            "tone": "sky",
        },
        {
            "name": "Columbia Road Flower Market",
            "category": "Market",
            "description": "A Sunday-only explosion of blooms, barrow-boy calls, and shopfronts selling espresso and vinyl behind jungles of greenery.",
            "tone": "sun",
        },
        {
            "name": "St Dunstan in the East",
            "category": "Garden",
            "description": "A bombed-out medieval church turned secret garden where vines climb Gothic windows and city workers eat lunch among the ruins.",
            "tone": "mint",
        },
        {
            "name": "Greenwich",
            "category": "Neighborhood",
            "description": "A riverside village of maritime time, the Prime Meridian, and a park hill where the skyline stretches from Canary Wharf to St Paul's.",
            "tone": "sky",
        },
    ],
    "oaxaca": [
        {
            "name": "Monte Albán",
            "category": "Historic Site",
            "description": "A Zapotec city flattened atop a mountain, where the plaza stretches wide and the valley drops away in every direction.",
            "tone": "plum",
        },
        {
            "name": "Hierve el Agua",
            "category": "Park",
            "description": "Petrified waterfalls cascading down a cliffside, with mineral pools perched on the edge like an infinity bath above the valley.",
            "tone": "sky",
        },
        {
            "name": "Mercado Benito Juárez",
            "category": "Market",
            "description": "A sensory overload of chapulines, chocolate grinding stones, fresh memelas, and stalls that sell everything from leather to candles.",
            "tone": "sun",
        },
        {
            "name": "Templo de Santo Domingo",
            "category": "Historic Site",
            "description": "A baroque church with an interior of gold leaf so dazzling that first-time visitors stand silent in the doorway.",
            "tone": "plum",
        },
        {
            "name": "Mitla",
            "category": "Historic Site",
            "description": "Zapotec ruins famous for intricate geometric mosaics set into the walls without mortar, a pattern language still undeciphered.",
            "tone": "plum",
        },
        {
            "name": "Museo Textil de Oaxaca",
            "category": "Museum",
            "description": "A quiet courtyard museum celebrating the region's weaving traditions, with looms, indigo dyes, and rotating exhibitions.",
            "tone": "sky",
        },
        {
            "name": "Jalatlaco",
            "category": "Neighborhood",
            "description": "Cobblestone streets lined with brightly painted walls and murals, where art galleries and cafés hide behind bougainvillea.",
            "tone": "sun",
        },
        {
            "name": "Mercado 20 de Noviembre",
            "category": "Food",
            "description": "The pasillo de humo—a smoky corridor of grill counters where you point at meats and they land sizzling on your plate.",
            "tone": "sun",
        },
        {
            "name": "Árbol del Tule",
            "category": "Park",
            "description": "A cypress with the stoutest trunk on earth, standing in a churchyard in Santa María del Tule for over two thousand years.",
            "tone": "mint",
        },
        {
            "name": "Taller de Alebrijes",
            "category": "Museum",
            "description": "A family workshop in San Martín Tilcajete where fantastical carved creatures come alive under tiny paintbrushes and copal wood shavings.",
            "tone": "plum",
        },
    ],
    "cape town": [
        {
            "name": "Table Mountain",
            "category": "Landmark",
            "description": "A flat-topped giant that dominates the skyline—ride the cable car up for a view that stretches from Robben Island to the Cape of Good Hope.",
            "tone": "sky",
        },
        {
            "name": "Boulders Beach",
            "category": "Beach",
            "description": "A sheltered cove where African penguins waddle across the boardwalk and swim alongside you in turquoise water.",
            "tone": "sun",
        },
        {
            "name": "Bo-Kaap",
            "category": "Neighborhood",
            "description": "Rows of candy-bright houses on cobbled slopes, with the call to prayer drifting over streets that smell of cape Malay curry.",
            "tone": "plum",
        },
        {
            "name": "V&A Waterfront",
            "category": "Market",
            "description": "A working harbour turned leisure hub where ferries depart, buskers perform, and the food market runs from biltong to oysters.",
            "tone": "sun",
        },
        {
            "name": "Kirstenbosch Botanical Garden",
            "category": "Garden",
            "description": "A garden set against the eastern slopes of Table Mountain with a canopy walkway suspended above fynbos and ancient cycads.",
            "tone": "mint",
        },
        {
            "name": "Cape Point",
            "category": "Viewpoint",
            "description": "The dramatic tip of the Cape Peninsula where cliffs plunge into the meeting place of two oceans and baboons patrol the car park.",
            "tone": "sky",
        },
        {
            "name": "Chapman's Peak Drive",
            "category": "Viewpoint",
            "description": "A coastal road carved into sheer cliffs with pull-offs that demand you stop, breathe, and take the photo.",
            "tone": "sky",
        },
        {
            "name": "Woodstock Exchange",
            "category": "Market",
            "description": "A converted industrial building with design studios, a Saturday market, and arguably the best flat white in the city.",
            "tone": "mint",
        },
        {
            "name": "Muizenberg",
            "category": "Beach",
            "description": "A long stretch of sand with brightly painted beach huts and gentle waves where first-time surfers find their balance.",
            "tone": "sun",
        },
        {
            "name": "Robben Island",
            "category": "Museum",
            "description": "A ferry ride to the prison island where Nelson Mandela spent eighteen years, now a museum guided by former political prisoners.",
            "tone": "plum",
        },
    ],
}

# ---------------------------------------------------------------------------
# 3. Friend recommendations (3 per city)
# ---------------------------------------------------------------------------

FRIEND_RECOMMENDATIONS: dict[str, list[dict[str, object]]] = {
    "granada": [
        {
            "friend_name": "Maya K.",
            "note": "The tapas on Calle Navas are still free with every drink. Go hungry and don't plan dinner.",
            "avatar": "MK",
            "saved_places": 12,
        },
        {
            "friend_name": "James L.",
            "note": "Book the Alhambra Nasrid Palaces at least three weeks out. The morning slot sells first.",
            "avatar": "JL",
            "saved_places": 8,
        },
        {
            "friend_name": "Sofia R.",
            "note": "Walk up to San Nicolás around 7pm. The guitar player makes the whole terrace feel like a film.",
            "avatar": "SR",
            "saved_places": 15,
        },
    ],
    "kyoto": [
        {
            "friend_name": "Hana T.",
            "note": "Fushimi Inari at 6am is empty and magical. By 9am you can't move. Set an alarm.",
            "avatar": "HT",
            "saved_places": 14,
        },
        {
            "friend_name": "David C.",
            "note": "Skip the bamboo grove crowds and walk up to Okochi-Sanso Villa instead. Totally worth the tea.",
            "avatar": "DC",
            "saved_places": 10,
        },
        {
            "friend_name": "Priya N.",
            "note": "Nishiki Market is best before 11am. Grab a warm yuba skin skewer and walk slowly.",
            "avatar": "PN",
            "saved_places": 12,
        },
    ],
    "lisbon": [
        {
            "friend_name": "André M.",
            "note": "Tram 28 is worth it before 8am. After that you queue longer than the ride. Walk the Alfama instead.",
            "avatar": "AM",
            "saved_places": 11,
        },
        {
            "friend_name": "Clara F.",
            "note": "Skip the pastéis de nata queue in Belém—go to Manteigaria in Chiado. Hot, flaky, perfect.",
            "avatar": "CF",
            "saved_places": 9,
        },
        {
            "friend_name": "Ravi P.",
            "note": "The miradouros are free and the sunsets last forever. Senhora do Monte beats every rooftop bar.",
            "avatar": "RP",
            "saved_places": 13,
        },
    ],
    "copenhagen": [
        {
            "friend_name": "Freja L.",
            "note": "Rent a bike from day one—it's how the city works. Download the Donkey Republic app.",
            "avatar": "FL",
            "saved_places": 8,
        },
        {
            "friend_name": "Oscar N.",
            "note": "Christiania is fascinating but don't take photos on Pusher Street. Read the signs.",
            "avatar": "ON",
            "saved_places": 12,
        },
        {
            "friend_name": "Ingrid V.",
            "note": "Reffen is open from lunch until late in summer. Every container is a different country. Go hungry.",
            "avatar": "IV",
            "saved_places": 10,
        },
    ],
    "london": [
        {
            "friend_name": "Sam P.",
            "note": "The Sky Garden is free but you need to book a slot online about three weeks ahead.",
            "avatar": "SP",
            "saved_places": 15,
        },
        {
            "friend_name": "Lucy W.",
            "note": "Borough Market on a Saturday is a sport. Go Friday afternoon instead and you'll actually see the stalls.",
            "avatar": "LW",
            "saved_places": 11,
        },
        {
            "friend_name": "Rohan D.",
            "note": "Columbia Road flower market opens at 8am sharp on Sundays. The plant shops stay open all week though.",
            "avatar": "RD",
            "saved_places": 9,
        },
    ],
    "oaxaca": [
        {
            "friend_name": "Elena G.",
            "note": "The Mercado 20 de Noviembre pasillo de humo is the best dinner you'll ever point at. Bring cash.",
            "avatar": "EG",
            "saved_places": 14,
        },
        {
            "friend_name": "Diego C.",
            "note": "Monte Albán first thing in the morning—the light is perfect and you have the plaza nearly to yourself.",
            "avatar": "DC",
            "saved_places": 12,
        },
        {
            "friend_name": "Naomi S.",
            "note": "Jalatlaco is where locals actually hang out. Murals everywhere and a tiny café called Cafebrería that's worth the walk.",
            "avatar": "NS",
            "saved_places": 10,
        },
    ],
    "cape town": [
        {
            "friend_name": "Thabo M.",
            "note": "Check the Table Mountain cable car website before you go—it closes for wind with no warning.",
            "avatar": "TM",
            "saved_places": 13,
        },
        {
            "friend_name": "Alice V.",
            "note": "Kirstenbosch on a Sunday afternoon with a picnic blanket and a bottle of local Chenin is peak Cape Town.",
            "avatar": "AV",
            "saved_places": 11,
        },
        {
            "friend_name": "Ben K.",
            "note": "Chapman's Peak Drive at golden hour is mandatory. Pull over at every viewpoint—you'll regret the ones you skip.",
            "avatar": "BK",
            "saved_places": 15,
        },
    ],
}

# ---------------------------------------------------------------------------
# 4. Weather forecast (5-day, October-realistic temperatures)
# ---------------------------------------------------------------------------

WEATHER_FORECAST: dict[str, list[dict[str, object]]] = {
    "granada": [
        {"day": "Mon", "high": 24, "low": 11, "icon": "☀️", "condition": "Sunny"},
        {"day": "Tue", "high": 26, "low": 12, "icon": "☀️", "condition": "Sunny"},
        {"day": "Wed", "high": 23, "low": 10, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Thu", "high": 22, "low": 9, "icon": "🌤️", "condition": "Clear"},
        {"day": "Fri", "high": 20, "low": 8, "icon": "☁️", "condition": "Overcast"},
    ],
    "kyoto": [
        {"day": "Mon", "high": 21, "low": 14, "icon": "🌧️", "condition": "Light rain"},
        {"day": "Tue", "high": 22, "low": 13, "icon": "☁️", "condition": "Overcast"},
        {"day": "Wed", "high": 20, "low": 12, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Thu", "high": 23, "low": 15, "icon": "🌤️", "condition": "Clear"},
        {"day": "Fri", "high": 19, "low": 11, "icon": "🌧️", "condition": "Light rain"},
    ],
    "lisbon": [
        {"day": "Mon", "high": 23, "low": 15, "icon": "🌤️", "condition": "Clear"},
        {"day": "Tue", "high": 24, "low": 16, "icon": "☀️", "condition": "Sunny"},
        {"day": "Wed", "high": 22, "low": 14, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Thu", "high": 21, "low": 13, "icon": "☁️", "condition": "Overcast"},
        {"day": "Fri", "high": 23, "low": 15, "icon": "🌤️", "condition": "Clear"},
    ],
    "copenhagen": [
        {"day": "Mon", "high": 12, "low": 7, "icon": "☁️", "condition": "Overcast"},
        {"day": "Tue", "high": 11, "low": 6, "icon": "🌧️", "condition": "Light rain"},
        {"day": "Wed", "high": 13, "low": 8, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Thu", "high": 10, "low": 5, "icon": "🌧️", "condition": "Light rain"},
        {"day": "Fri", "high": 14, "low": 9, "icon": "🌤️", "condition": "Clear"},
    ],
    "london": [
        {"day": "Mon", "high": 15, "low": 9, "icon": "☁️", "condition": "Overcast"},
        {"day": "Tue", "high": 14, "low": 8, "icon": "🌧️", "condition": "Light rain"},
        {"day": "Wed", "high": 16, "low": 10, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Thu", "high": 13, "low": 7, "icon": "🌧️", "condition": "Light rain"},
        {"day": "Fri", "high": 15, "low": 9, "icon": "🌤️", "condition": "Clear"},
    ],
    "oaxaca": [
        {"day": "Mon", "high": 27, "low": 13, "icon": "☀️", "condition": "Sunny"},
        {"day": "Tue", "high": 28, "low": 14, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Wed", "high": 26, "low": 12, "icon": "🌤️", "condition": "Clear"},
        {"day": "Thu", "high": 27, "low": 13, "icon": "☀️", "condition": "Sunny"},
        {"day": "Fri", "high": 25, "low": 11, "icon": "⛅", "condition": "Partly cloudy"},
    ],
    "cape town": [
        {"day": "Mon", "high": 21, "low": 12, "icon": "⛅", "condition": "Partly cloudy"},
        {"day": "Tue", "high": 22, "low": 13, "icon": "🌤️", "condition": "Clear"},
        {"day": "Wed", "high": 19, "low": 11, "icon": "☁️", "condition": "Overcast"},
        {"day": "Thu", "high": 23, "low": 14, "icon": "☀️", "condition": "Sunny"},
        {"day": "Fri", "high": 20, "low": 12, "icon": "🌤️", "condition": "Clear"},
    ],
}

# ---------------------------------------------------------------------------
# 5. Flight stub
# ---------------------------------------------------------------------------

FLIGHT_STUB: dict[str, str] = {
    "origin": "Your nearest airport",
    "price_range": "$380 – $920 round trip",
    "airlines": "Multiple carriers",
    "note": "Simulated — no live pricing",
}

# ---------------------------------------------------------------------------
# 6. Hotel stub
# ---------------------------------------------------------------------------

HOTEL_STUB: dict[str, str] = {
    "sample_name": "Sample properties in city center",
    "neighborhood": "City center & nearby",
    "rating": "4.2 – 4.8",
    "price_range": "$95 – $340 per night",
    "note": "Simulated — no live availability",
}

# ---------------------------------------------------------------------------
# 7. Helper functions
# ---------------------------------------------------------------------------


def searchable_cities() -> list[str]:
    """Return the list of searchable city names."""
    return list(SEARCHABLE_CITIES)


def matching_plans(
    city: str, public_trips: list[dict] | None = None, *, include_generated: bool = True
) -> list[dict]:
    """Return plans whose destination contains *city* (case-insensitive).

    When *public_trips* is not supplied, lazily imports ``PUBLIC_TRIPS`` from
    ``data``.  When *include_generated* is True (default), also includes any
    runtime-generated trips registered via ``data._generated_trips``.

    Each returned dict includes only the display-relevant keys:
    ``title``, ``destination``, ``slug``, ``days``, ``creator``.
    """
    if public_trips is not None:
        trips = public_trips
    else:
        from data import PUBLIC_TRIPS  # lazy import – avoids top-level fh_saas dependency

        trips = list(PUBLIC_TRIPS)

        if include_generated:
            from data import _generated_trips

            trips.extend(_generated_trips)

    city_lower = city.strip().lower()
    matches: list[dict] = []
    for trip in trips:
        if city_lower in trip.get("destination", "").lower():
            matches.append(
                {
                    "title": trip["title"],
                    "destination": trip["destination"],
                    "slug": trip["slug"],
                    "days": trip["days"],
                    "creator": trip["creator"],
                }
            )
    return matches


def top_places_for(city: str) -> list[dict[str, str]]:
    """Return the top 10 places for *city*, or an empty list if unknown."""
    return TOP_PLACES.get(city.strip().lower(), [])


def friend_recs_for(city: str) -> list[dict]:
    """Return friend recommendations for *city*, or an empty list if unknown."""
    return FRIEND_RECOMMENDATIONS.get(city.strip().lower(), [])


def weather_for(city: str) -> list[dict]:
    """Return a 5-day forecast for *city*, or an empty list if unknown."""
    return WEATHER_FORECAST.get(city.strip().lower(), [])


def resolve_city(query: str) -> str | None:
    """Case-insensitive city match.  ``'granada'`` → ``'Granada'``.  Returns ``None`` if no match."""
    q = query.strip().lower()
    for city in SEARCHABLE_CITIES:
        if city.lower() == q:
            return city
    return None