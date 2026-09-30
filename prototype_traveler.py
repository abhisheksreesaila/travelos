"""Three traveler-journey layout studies, switched by ?variant=A/B/C."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode


VARIANTS = {"A": "Sunny fieldnotes", "B": "Route atlas", "C": "Family postcard"}
PAGES = {"home", "discover", "signin", "plans", "workspace", "search"}
DEFAULT_SLUG = "granada-after-dark"

PLANS = (
    {
        "slug": DEFAULT_SLUG,
        "title": "Granada, at kid speed",
        "city": "Granada, Spain",
        "duration": "3 days",
        "tags": ("Family-friendly", "Walkable", "Food", "Slow pace"),
        "note": "Courtyard pauses, a storybook fortress, and room for one more churro.",
    },
)

DAYS = (
    {
        "title": "Arrive, exhale, find the plaza",
        "area": "CENTRO · EASY FIRST DAY",
        "time": "3:30 PM",
        "place": "Plaza Nueva & a shady gelato stop",
        "copy": "Drop bags, stretch your legs, and let the first evening stay wonderfully open.",
        "kid": "Make the plaza the destination: gelato first, a short fountain wander after.",
        "symbol": "01",
        "tone": "sun",
    },
    {
        "title": "A palace day with a soft landing",
        "area": "ALHAMBRA · BOOK AHEAD",
        "time": "9:00 AM",
        "place": "Alhambra gardens & story break",
        "copy": "An early visit leaves a slow lunch and a quiet hour back near your stay.",
        "kid": "Turn the gardens into a color hunt; keep the palace visit short and snack breaks frequent.",
        "symbol": "02",
        "tone": "plum",
    },
    {
        "title": "Lookout views, then choose your own ending",
        "area": "ALBAICÍN · FLEXIBLE FINALE",
        "time": "10:30 AM",
        "place": "Mirador loop & tiny craft shops",
        "copy": "Take the gentler uphill route, pause for the view, and skip any stop that feels like one too many.",
        "kid": "Ride up for the view, then choose one small shop or a park stop on the way down.",
        "symbol": "03",
        "tone": "mint",
    },
)


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _url(page: str, variant: str, *, slug: str = DEFAULT_SLUG, query: str = "", fork: bool = False) -> str:
    path = f"/plans/{slug}" if page == "plans" else "/" if page == "home" else f"/{page}"
    params = {"variant": variant}
    if query.strip() and page == "discover":
        params["q"] = query.strip()
    if fork:
        params["fork"] = "1"
        params["slug"] = slug
    return f"{path}?{urlencode(params)}"


def _chip(text: str, tone: str = "sun") -> str:
    return f'<span class="p-chip is-{_e(tone)}">{_e(text)}</span>'


def _button(label: str, href: str, tone: str = "primary", extra: str = "") -> str:
    style = {"primary": "is-primary", "secondary": "is-secondary", "ghost": "is-ghost"}[tone]
    return f'<a class="p-button {style} {extra}" href="{_e(href)}">{label}</a>'


def _picture(scene: str, *, label: str = "A sunny illustrated view of Granada") -> str:
    """Local vector scene: no image/font services and no travel-provider content."""
    return f'''<svg class="p-illustration scene-{_e(scene)}" viewBox="0 0 560 360" role="img" aria-label="{_e(label)}" xmlns="http://www.w3.org/2000/svg">
      <rect width="560" height="360" rx="26" fill="#F7C95E"/>
      <circle cx="446" cy="74" r="39" fill="#FFF0B2"/>
      <path d="M0 257 112 147l82 92 86-125 119 145 79-77 82 96v82H0Z" fill="#70C6A2"/>
      <path d="m66 267 145-171 117 171Z" fill="#7357D8"/>
      <path d="m113 267 98-117 80 117Z" fill="#F0643D"/>
      <path d="M0 280q129-28 280 3t280-1v78H0Z" fill="#63C7E7"/>
      <path d="M152 267v-61q0-40 58-40t58 40v61" fill="#FFDDA0"/>
      <path d="M191 267v-45q0-20 19-20t19 20v45" fill="#202B39"/>
      <path d="M0 319q94-30 176 0t192-2 192 2" fill="none" stroke="#fffdf7" stroke-width="7" stroke-linecap="round"/>
      <path d="M391 219q23-19 45 0" fill="none" stroke="#202B39" stroke-width="5" stroke-linecap="round"/>
      <circle cx="400" cy="230" r="7" fill="#F0643D"/><circle cx="431" cy="230" r="7" fill="#7357D8"/>
    </svg>'''


def _route_art() -> str:
    return '''<svg class="p-route-art" viewBox="0 0 520 240" role="img" aria-label="Illustrated three-stop route through Granada" xmlns="http://www.w3.org/2000/svg">
      <path d="M47 169c75-77 103-70 153-43s92 48 130 14 81-54 144-10" fill="none" stroke="#202B39" stroke-width="5" stroke-linecap="round" stroke-dasharray="2 12"/>
      <circle cx="54" cy="164" r="18" fill="#FFD257" stroke="#202B39" stroke-width="3"/><circle cx="226" cy="145" r="18" fill="#76D7B1" stroke="#202B39" stroke-width="3"/><circle cx="469" cy="132" r="18" fill="#63C7E7" stroke="#202B39" stroke-width="3"/>
      <path d="M0 215q120-34 234 0t286-8v33H0Z" fill="#F0643D" opacity=".18"/><path d="M305 72q20-22 41 0" fill="none" stroke="#7357D8" stroke-width="5" stroke-linecap="round"/><circle cx="326" cy="79" r="7" fill="#7357D8"/>
      <text x="29" y="206">CENTRO</text><text x="189" y="190">ALHAMBRA</text><text x="421" y="178">ALBAICÍN</text>
    </svg>'''


def _variant_bar(page: str, variant: str, slug: str, query: str) -> str:
    names = {"A": "Sunny fieldnotes", "B": "Route atlas", "C": "Family postcard"}
    options = "".join(
        f'<a class="p-layout-link{" is-selected" if key == variant else ""}" href="{_e(_url(page, key, slug=slug, query=query))}" aria-current="{"page" if key == variant else "false"}"><b>{key}</b><span>{name}</span></a>'
        for key, name in names.items()
    )
    return f'''<nav class="p-variant-bar" aria-label="Compare traveler layouts"><span class="p-variant-caption">Layout study <b>{variant}</b></span><div class="p-variant-options">{options}</div><span class="p-variant-hint">Prototype only</span></nav>'''


def _footer(variant: str) -> str:
    return f'''<footer class="p-traveler-footer"><span>TRAVELOS / A GOOD TRIP STARTS WITH A GOOD PLAN</span><div><a href="{_url('discover', variant)}">Find a plan</a><a href="/creators?variant={variant}">Share a route</a></div><small>Illustrative trip details · nothing here is a booking or live forecast.</small></footer>'''


def _plan_teaser(plan: dict, variant: str, index: int) -> str:
    tones = ("sun", "mint", "sky")
    slug = plan["slug"]
    return f'''<article class="p-discovery-card teaser-{tones[index % len(tones)]}"><a class="p-teaser-image" href="{_url('plans', variant, slug=slug)}">{_picture(f'card-{index}', label=f"Illustrated trip idea: {plan['city']}")}<span class="p-teaser-index">0{index + 1}</span></a><div class="p-teaser-body"><div class="p-teaser-meta"><span>{_e(plan['city'])}</span><span>{_e(plan['duration'])}</span></div><h3><a href="{_url('plans', variant, slug=slug)}">{_e(plan['title'])}</a></h3><p>{_e(plan['note'])}</p><div class="p-chip-row">{''.join(_chip(tag, tones[index % 3]) for tag in plan['tags'])}</div></div></article>'''


def _home(variant: str) -> str:
    cards = "".join(_plan_teaser(plan, variant, index) for index, plan in enumerate(PLANS))
    from search_fixtures import SEARCHABLE_CITIES
    city_options = "".join(f'<option value="{_e(city)}">{_e(city)}</option>' for city in SEARCHABLE_CITIES)
    search_form = f'''<form class="p-search-form" action="/search" method="get" role="search"><input type="hidden" name="variant" value="{variant}"><datalist id="home-cities">{city_options}</datalist><label><span>⌕</span><input class="p-input" name="destination" placeholder="Where to?" autocomplete="off" list="home-cities"></label><label><input type="date" name="checkin" aria-label="Check-in"></label><label><input type="date" name="checkout" aria-label="Check-out"></label><label><input class="p-input" name="travelers" placeholder="Travelers" aria-label="Travelers"></label><button class="p-button is-primary" type="submit">Search</button></form>'''
    if variant == "B":
        hero = f'''<section class="p-home-hero p-home-b"><div class="p-hero-copy"><span class="p-eyebrow">A LITTLE MORE GO, A LITTLE LESS SCROLL</span><h1 class="p-title">Good trips<br>are <em>shared.</em></h1><p class="p-lede">Borrow a local's route. Make it yours. Keep the room for a detour.</p><div class="p-hero-actions">{search_form}</div><div class="p-hero-stats"><span><b>03</b> days to start</span><span><b>01</b> family-ready route</span></div></div><div class="p-home-map">{_route_art()}<div class="p-map-label label-one">01 · PLAZA NUEVA</div><div class="p-map-label label-two">02 · PALACE GARDENS</div><div class="p-map-label label-three">03 · HILLTOP VIEW</div><span class="p-map-sticker">YOUR NEXT<br>GOOD IDEA</span></div></section>'''
    elif variant == "C":
        hero = f'''<section class="p-home-hero p-home-c"><div class="p-family-art">{_picture('family', label='Colorful illustrated Granada skyline with a path for a family trip')}<span class="p-stamp">MADE FOR<br>THE WHOLE CREW</span><span class="p-art-caption">FIELD NOTE 01 / GRANADA</span></div><div class="p-hero-copy"><span class="p-eyebrow">TRAVEL PLANS WITH PEOPLE IN THEM</span><h1 class="p-title">The best days<br>leave <em>wiggle room.</em></h1><p class="p-lede">Find a trip idea with the useful bits already thought through—then tune it for your people.</p><div class="p-hero-actions">{search_form}</div><div class="p-family-proof"><span class="p-avatar-stack"><i>A</i><i>R</i><i>+</i></span><span>Made for curious crews,<br>not perfect itineraries.</span></div></div></section>'''
    else:
        hero = f'''<section class="p-home-hero p-home-a"><div class="p-hero-copy"><span class="p-eyebrow">YOUR FRIENDLY FIELD GUIDE TO GETTING OUT THERE</span><h1 class="p-title">Less planning<br>spiral. More <em>story.</em></h1><p class="p-lede">Travel plans from people who know the place—ready for you to remix around your dates, your crew, your kind of day.</p><div class="p-hero-actions">{search_form}</div><div class="p-trust-line"><span>✳ FAMILY FRIENDLY</span><span>↗ MADE TO REMIX</span><span>☼ FIXTURE WEATHER</span></div></div><div class="p-hero-art">{_picture('home')}<span class="p-art-caption">A GOOD DAY, SOMEWHERE IN GRANADA</span><div class="p-postcard"><span>3 easy days</span><b>Granada<br>with room to roam</b><a href="{_url('plans', variant)}">Take a peek ↗</a></div><span class="p-sun-doodle">✳</span></div></section>'''
    layout = f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-home"><div class="p-container"><div class="p-page-intro"><span class="p-eyebrow">A TRIP STARTS SOMEWHERE</span><span class="p-intro-note">Discoverable plans. Yours to make your own.</span></div>{hero}<section class="p-section p-featured"><div class="p-section-head"><div><span class="p-eyebrow">GOOD PLACES, GOOD STARTS</span><h2 class="p-title p-title-small">Pick a plan. Leave room for you.</h2></div><a class="p-text-link" href="{_url('discover', variant)}">All trip ideas <span>↗</span></a></div><div class="p-grid p-teaser-grid">{cards}</div></section><section class="p-creator-invite"><div class="p-invite-mark">✳</div><div><span class="p-eyebrow">KNOW A PLACE BY HEART?</span><h2>Bring your route along.</h2><p>Start with a link to your existing travel story. Your guide should travel further than the scroll.</p></div>{_button('Share a route ↗', f"/creators?variant={variant}", 'secondary')}</section></div>{_footer(variant)}</main>'''
    return layout


def _discover(variant: str, query: str) -> str:
    needle = query.strip().casefold()
    found = [plan for plan in PLANS if not needle or needle in " ".join((plan["title"], plan["city"], plan["note"], *plan["tags"])).casefold()]
    cards = "".join(_plan_teaser(plan, variant, index) for index, plan in enumerate(found))
    empty = '' if found else '<section class="p-empty-state"><span class="p-empty-sun">⌕</span><h2>No route on that note yet.</h2><p>Try a city, “family”, or “slow”. There’s always another way in.</p><a class="p-button is-secondary" href="/discover?variant=' + variant + '">See every trip idea</a></section>'
    form = f'''<form class="p-search-form" action="/discover" method="get" role="search"><input type="hidden" name="variant" value="{variant}"><label class="p-sr-only" for="trip-search">Search destinations or trip moods</label><span aria-hidden="true">⌕</span><input class="p-input" id="trip-search" name="q" value="{_e(query)}" placeholder="Try Granada, family, slow…"><button class="p-button is-primary" type="submit">Find a plan</button></form>'''
    result_note = f'{len(found)} trip ideas' if not needle else f'{len(found)} ideas for “{_e(query)}”'
    if variant == "B":
        results = f'''<div class="p-atlas-layout"><aside class="p-atlas-side"><span class="p-eyebrow">A FEW GOOD STARTS</span>{_route_art()}<p>Every route is an editable starting point—not a schedule to obey.</p><div class="p-atlas-count">{len(found):02d}<span>plans in this little atlas</span></div></aside><div class="p-atlas-results"><div class="p-results-heading"><span>{result_note}</span><span>{_chip('LOCAL SAMPLE', 'sky')}</span></div><div class="p-grid p-teaser-grid">{cards}</div>{empty}</div></div>'''
    elif variant == "C":
        results = f'''<div class="p-results-heading"><span>{result_note}</span><span>Choose your own first day ↗</span></div>{empty}<div class="p-grid p-teaser-grid p-family-results">{cards}</div>'''
    else:
        results = f'''<div class="p-results-heading"><span>{result_note}</span><span>{_chip('CURATED STARTERS', 'mint')}</span></div>{empty}<div class="p-grid p-teaser-grid">{cards}</div>'''
    return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-discover"><div class="p-container"><section class="p-discover-head"><div><span class="p-eyebrow">THE TRIP IDEA SHELF</span><h1 class="p-title">Where do you<br>want to <em>begin?</em></h1><p class="p-lede">Borrow a thoughtful route from someone who’s been there. Keep the bits that fit.</p></div><div class="p-search-wrap">{form}<span class="p-search-help">Search a place, a pace, or a feeling.</span></div></section><div class="p-filter-row" aria-label="Popular trip moods"><span>GOOD STARTING POINTS</span>{_chip('Family-friendly', 'sun')}{_chip('Walkable', 'mint')}{_chip('Slow mornings', 'plum')}</div><section class="p-section p-discover-results">{results}</section><section class="p-creator-invite compact"><div class="p-invite-mark">↗</div><div><span class="p-eyebrow">HAVE A ROUTE OF YOUR OWN?</span><h2>Let someone else start here.</h2><p>Share an existing travel story; the prototype’s extraction is simulated.</p></div>{_button('For creators ↗', f"/creators?variant={variant}", 'ghost')}</section></div>{_footer(variant)}</main>'''




def _search(variant: str, params: dict) -> str:
    """Render the search-first page as a lightweight plan gateway."""
    from search_fixtures import SEARCHABLE_CITIES

    destination = params.get("destination", "")
    checkin = params.get("checkin", "")
    checkout = params.get("checkout", "")
    travelers = params.get("travelers", "2 travelers")
    empty = params.get("empty", False)

    city_options = "".join(f'<option value="{_e(city)}">{_e(city)}</option>' for city in SEARCHABLE_CITIES)
    search_form = f'''<form class="p-search-form" action="/search" method="get" role="search"><input type="hidden" name="variant" value="{variant}"><datalist id="searchable-cities">{city_options}</datalist><label><span>⌕</span><input class="p-input" name="destination" value="{_e(destination)}" placeholder="City, coast, or feeling" autocomplete="off" list="searchable-cities"></label><label><input type="date" name="checkin" value="{_e(checkin)}" aria-label="Check-in"></label><label><input type="date" name="checkout" value="{_e(checkout)}" aria-label="Check-out"></label><label><input class="p-input" name="travelers" value="{_e(travelers)}" placeholder="Travelers" aria-label="Travelers"></label><button class="p-button is-primary" type="submit">Search</button></form>'''

    if empty:
        return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-search"><div class="p-container"><section class="p-search-hero"><div><span class="p-eyebrow">SEARCH-FIRST TRAVEL</span><h1 class="p-title">Where would you<br>like to <em>go?</em></h1><p class="p-lede">Enter a city to find matching trip plans you can fork and customize.</p></div><div class="p-search-wrap">{search_form}<span class="p-search-help">Try Granada, Kyoto, Lisbon…</span></div></section></div>{_footer(variant)}</main>'''

    plans = params.get("plans", [])

    if plans:
        plan_teasers = "".join(
            f'''<article class="p-card p-plan-teaser"><a href="{_url("plans", variant, slug=p.get("slug", ""))}"><b>{_e(str(p.get("title", "")))}</b><div class="p-plan-meta"><span>{_e(str(p.get("destination", "")))}</span><span>{_e(str(p.get("days", "")))} days</span></div><small>by {_e(str(p.get("creator", "")))}</small></a></article>'''
            for p in plans
        )
    else:
        plan_teasers = '<div class="p-empty-note"><span>No matching plans for this city.</span></div>'
    plans_section = f'''<section class="p-section p-search-plans"><div class="p-section-head"><div><span class="p-eyebrow">MATCHING TRIP PLANS</span><h2 class="p-title p-title-small">Routes you can fork.</h2></div><span class="p-chip is-sky">{len(plans)} PLANS</span></div><div class="p-plans-grid">{plan_teasers}</div></section>'''

    return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-search"><div class="p-container"><section class="p-search-hero"><div><span class="p-eyebrow">EXPLORE {_e(destination.upper())}</span><h1 class="p-title">Your <em>{_e(destination)}</em><br>trip at a glance.</h1></div><div class="p-search-wrap">{search_form}</div></section>{plans_section}</div>{_footer(variant)}</main>'''


def _day_row(day: dict, index: int) -> str:
    return f'''<article class="p-day-row tone-{day['tone']}" data-day-card="{index}"><div class="p-day-marker"><span>{day['symbol']}</span><i aria-hidden="true"></i></div><div class="p-day-body"><div class="p-day-meta"><span>{day['area']}</span><time data-day-date="{index}">DAY {index + 1}</time></div><h3>{_e(day['title'])}</h3><div class="p-stop-line"><span class="p-stop-time">{day['time']}</span><span class="p-stop-dot"></span><span class="p-stop-name">{_e(day['place'])}</span></div><p class="p-day-copy" data-primary-copy>{_e(day['copy'])}</p><p class="p-day-copy p-kid-copy" data-kid-copy hidden>{_e(day['kid'])}</p></div><span class="p-day-stamp">{day['symbol']}</span></article>'''


def _pace_time_attrs(index: int, day: dict) -> str:
    easy = ("10:30 AM", "9:30 AM", "10:30 AM")[index]
    full = ("2:00 PM", "8:00 AM", "9:00 AM")[index]
    return f'data-time data-time-easy="{easy}" data-time-balanced="{_e(day["time"])}" data-time-full="{full}"'


def _share_days() -> str:
    return "".join(
        f'''<article class="p-share-day tone-{day['tone']}" data-share-itinerary="{i}"><div class="p-share-day-head"><span>DAY 0{i + 1} · {day['area']}</span><time data-share-date="{i}">OCT {9 + i:02d}</time></div><div class="p-share-day-time"><time {_pace_time_attrs(i, day)}>{day['time']}</time><span>◎ {_e(day['place'])}</span></div><h3>{_e(day['title'])}</h3><p data-primary-copy>{_e(day['copy'])}</p><p class="p-kid-copy" data-kid-copy hidden>{_e(day['kid'])}</p></article>'''
        for i, day in enumerate(DAYS)
    )


def _plan(variant: str, slug: str) -> str:
    plan = next((item for item in PLANS if item["slug"] == slug), PLANS[0])
    title = plan["title"]
    city = plan["city"]
    schedule = "".join(_day_row(day, i) for i, day in enumerate(DAYS))
    kid_toggle = '''<button class="p-kid-toggle" type="button" data-kid-toggle aria-pressed="false"><span>✳</span><span><b>Traveling with kids?</b><small>Show a few kid-friendly swaps</small></span><i>Show swaps <b aria-hidden="true">↗</b></i></button><p class="p-kid-feedback" data-kid-feedback role="status" aria-live="polite"></p>'''
    from search_fixtures import weather_for, top_places_for

    city_name = city.split(",")[0].strip()
    forecast = weather_for(city_name)
    places = top_places_for(city_name)

    if forecast:
        main_temp = f'{forecast[0]["high"]}°'
        main_condition = _e(str(forecast[0]["condition"]))
        main_icon = _e(str(forecast[0]["icon"]))
        forecast_days = "".join(
            f'<span><b>{_e(str(w["day"]))}</b>{_e(str(w["high"]))}° {_e(str(w["icon"]))}</span>'
            for w in forecast[:3]
        )
        weather = f'''<aside class="p-weather-card"><div class="p-weather-top"><span class="p-eyebrow">A LITTLE WEATHER CONTEXT</span><span class="p-weather-icon" aria-hidden="true">{main_icon}</span></div><strong>{main_condition} <i>{main_temp}</i></strong><p>Fixture forecast for {_e(city_name)}. A light layer earns its place.</p><div class="p-weather-days">{forecast_days}</div><small>FIXTURE DATA · not a live forecast</small></aside>'''
    else:
        weather = f'''<aside class="p-weather-card"><div class="p-weather-top"><span class="p-eyebrow">A LITTLE WEATHER CONTEXT</span><span class="p-weather-icon" aria-hidden="true">☀</span></div><strong>—° <i>Fixture forecast coming soon.</i></strong><p>Weather data is not yet available for {_e(city_name)}.</p><small>FIXTURE DATA · not a live forecast</small></aside>'''

    if places:
        place_cards = "".join(
            f'<article class="p-card"><span class="p-card-tone tone-{_e(str(p["tone"]))}">{_e(str(p["name"]))}</span><div class="p-card-body"><span class="p-card-eyebrow">{_e(str(p["category"]))}</span><p>{_e(str(p["description"]))}</p></div></article>'
            for p in places[:10]
        )
        places_html = f'''<div class="p-plan-places"><span class="p-eyebrow">TOP PLACES IN {_e(city_name.upper())}</span><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px">{place_cards}</div><small>SIMULATED · fixture data only</small></div>'''
    else:
        places_html = f'''<div class="p-plan-places"><span class="p-eyebrow">TOP PLACES IN {_e(city_name.upper())}</span><p class="p-empty-note"><span>Top places coming soon.</span></p></div>'''

    # Friend recommendations
    from search_fixtures import friend_recs_for
    friend_recs = friend_recs_for(city_name)
    if friend_recs:
        friend_cards = "".join(
            f'<article class="p-card p-friend-card"><span class="p-friend-avatar">{_e(str(f["avatar"]))}</span><div class="p-card-body"><b>{_e(str(f["friend_name"]))}</b><p>"{_e(str(f["note"]))}"</p><small>{_e(str(f["saved_places"]))} places saved in this area</small></div></article>'
            for f in friend_recs
        )
        friends_html = f'<div class="p-plan-friends"><span class="p-eyebrow">FRIENDS IN {_e(city_name.upper())}</span><div class="p-friends-grid">{friend_cards}</div><small>FIXTURE DATA · from your network</small></div>'
    else:
        friends_html = f'<div class="p-plan-friends"><span class="p-eyebrow">FRIENDS IN {_e(city_name.upper())}</span><p class="p-empty-note"><span>No friend recommendations yet.</span></p></div>'

    # Flights & stays stubs
    from search_fixtures import FLIGHT_STUB, HOTEL_STUB
    travel_stub_html = f'''<div class="p-plan-travel"><span class="p-eyebrow">FLIGHTS & STAYS</span><div class="p-travel-grid"><div class="p-card p-travel-card"><b>Flights to {_e(city_name)}</b><span class="p-travel-price">{_e(str(FLIGHT_STUB["price_range"]))}</span><small>{_e(str(FLIGHT_STUB["airlines"]))} · {_e(str(FLIGHT_STUB["note"]))}</small></div><div class="p-card p-travel-card"><b>Hotels in {_e(city_name)}</b><span class="p-travel-price">{_e(str(HOTEL_STUB["price_range"]))}</span><small>{_e(str(HOTEL_STUB["neighborhood"]))} · {_e(str(HOTEL_STUB["rating"]))} · {_e(str(HOTEL_STUB["note"]))}</small></div></div><small>SIMULATED · fixture data only</small></div>'''

    attribution = '''<aside class="p-source-note"><span class="p-source-avatar">SM</span><span><small>A ROUTE TO REMIX</small><b>Sofía & Mateo</b><i>Synthetic creator guide · family travel</i></span><span class="p-source-mark">↗</span></aside>'''
    if variant == "B":
        lead = f'''<section class="p-plan-atlas"><div class="p-plan-atlas-art">{_route_art()}<span class="p-atlas-badge">3 DAYS / EASY RHYTHM</span></div><div class="p-plan-atlas-copy"><span class="p-eyebrow">A LOCAL-INSPIRED STARTER · {city.upper()}</span><h1 class="p-title">{_e(title)}</h1><p class="p-lede">Three days, one lovely anchor at a time. Built to flex when a little person spots something better.</p><div class="p-chip-row">{''.join(_chip(tag, 'sun' if i == 0 else 'mint' if i == 1 else 'sky') for i, tag in enumerate(plan['tags']))}</div>{attribution}<div class="p-plan-actions">{_button('Make this trip ours ↗', _url('signin', variant, slug=plan['slug'], fork=True), 'primary')}{_button('See trip preview', '#trip-days', 'ghost')}</div></div></section>'''
        itinerary = f'''<section class="p-section p-plan-days" id="trip-days"><div class="p-section-head"><div><span class="p-eyebrow">THE ROUTE, IN THREE BEATS</span><h2 class="p-title p-title-small">A day at a time.</h2></div><span class="p-plan-date">OCT 09—11 · SAMPLE DATES</span></div>{kid_toggle}<div class="p-day-list">{schedule}</div></section>'''
    elif variant == "C":
        lead = f'''<section class="p-plan-family"><div class="p-family-plan-image">{_picture('family-plan', label=f"Illustrated trip scene for {city}")}<span class="p-image-label">FIELD GUIDE / 01</span><span class="p-family-sticker">A TRIP FOR<br>YOUR WHOLE CREW</span></div><div class="p-family-plan-copy"><span class="p-eyebrow">{city.upper()} · 3 EASY DAYS</span><h1 class="p-title">{_e(title)}</h1><p class="p-lede">{_e(plan['note'])} This is a thoughtful first draft—not a timed march.</p><div class="p-family-summary"><div><b>01</b><span>big thing<br>each day</span></div><div><b>∞</b><span>room for<br>snack stops</span></div><div><b>0</b><span>reservations<br>made here</span></div></div>{attribution}<div class="p-plan-actions">{_button('Make this trip ours ↗', _url('signin', variant, slug=plan['slug'], fork=True), 'primary')}{_button('Explore the route', '#trip-days', 'secondary')}</div></div></section>'''
        itinerary = f'''<section class="p-section p-plan-days p-family-days" id="trip-days"><div class="p-section-head"><div><span class="p-eyebrow">THE FAMILY-FRIENDLY FLOW</span><h2 class="p-title p-title-small">One good thing. Then another.</h2></div></div>{kid_toggle}<div class="p-day-list p-day-list-family">{schedule}</div></section>'''
    else:
        lead = f'''<section class="p-plan-hero"><div class="p-plan-hero-art">{_picture('plan', label=f"Illustrated trip scene for {city}")}<span class="p-art-caption">A SAMPLE ROUTE / MADE TO REMIX</span><span class="p-plan-sticker">YOUR OWN<br>PACE, PLEASE</span></div><div class="p-plan-intro"><span class="p-eyebrow">{city.upper()} <i>✳</i> 3 DAYS</span><h1 class="p-title">{_e(title)}</h1><p class="p-lede">{_e(plan['note'])} Think of it as a kind local’s notes, not a list to race through.</p><div class="p-chip-row">{''.join(_chip(tag, 'sun' if i == 0 else 'mint' if i == 1 else 'plum') for i, tag in enumerate(plan['tags']))}</div>{attribution}<div class="p-plan-actions">{_button('Make this trip ours ↗', _url('signin', variant, slug=plan['slug'], fork=True), 'primary')}{_button('Jump to the days ↓', '#trip-days', 'ghost')}</div><p class="p-muted p-small">No bookings made. This is a local sample plan.</p></div></section>'''
        itinerary = f'''<section class="p-section p-plan-days" id="trip-days"><div class="p-section-head"><div><span class="p-eyebrow">THREE DAYS WITH ROOM TO WANDER</span><h2 class="p-title p-title-small">A good rhythm, not a strict plan.</h2></div><span class="p-days-count">03 <i>DAY PLANS</i></span></div>{kid_toggle}<div class="p-day-list">{schedule}</div></section>'''
    return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-plan" data-trip-slug="{_e(plan['slug'])}"><div class="p-container"><nav class="p-breadcrumb" aria-label="Breadcrumb"><a href="{_url('discover', variant)}">Trip ideas</a><span>↗</span><span>{_e(city)}</span></nav>{lead}<div class="p-plan-content">{itinerary}    <aside class="p-plan-aside">{weather}{places_html}{friends_html}{travel_stub_html}<div class="p-source-preserve"><span class="p-eyebrow">KEEP THE GOOD SOURCE</span><p>The creator's point of view stays attached when you make a fork.</p>{attribution}</div><div class="p-disclaimer-card"><span>✳</span><p>Weather, timing, and stops are illustrative. Check local conditions and access before you go.</p></div></aside></div><section class="p-fork-banner"><div><span class="p-eyebrow">A GOOD PLACE TO START</span><h2>Make the route fit your crew.</h2><p>Choose dates, grown-ups, kids, and a pace that feels right.</p></div>{_button('Fork this trip ↗', _url('signin', variant, slug=plan['slug'], fork=True), 'primary')}</section></div>{_footer(variant)}</main>'''


def _signin(variant: str, slug: str) -> str:
    next_url = _url('workspace', variant, slug=slug, fork=True)
    if variant == "B":
        content = f'''<section class="p-signin-b"><div class="p-signin-heading"><span class="p-eyebrow">A GOOD TRIP, ALL YOURS</span><h1 class="p-title">One small step<br>to <em>your trip.</em></h1><p class="p-lede">No account needed for this prototype. Step into a sample workspace and see how it feels.</p>{_picture('signin', label='Illustrated sunny hilltop route')}</div><div class="p-signin-panel"><span class="p-demo-avatar">AR</span><span class="p-eyebrow">SAMPLE TRAVELER</span><h2>Ari Rivera</h2><p>Continue to a private, in-memory trip preview. Nothing is saved or sent anywhere.</p><a class="p-button is-primary p-signin-continue" href="{_e(next_url)}">Continue to my trip <span>↗</span></a><div class="p-signin-boundary"><span>NO PASSWORD</span><span>NO OAUTH</span><span>NO SERVER SAVE</span></div></div></section>'''
    elif variant == "C":
        content = f'''<section class="p-signin-c"><div class="p-signin-c-art">{_picture('welcome-family', label='A bright welcoming illustration for a family trip')}<span class="p-welcome-note">YOUR CREW,<br>YOUR RHYTHM.</span></div><div class="p-signin-c-copy"><span class="p-eyebrow">WELCOME, TRIP MAKER</span><h1 class="p-title">Ready when<br><em>you are.</em></h1><p class="p-lede">Meet Ari, our sample traveler, then head into a family trip you can shape right in the browser.</p><div class="p-persona-card"><span class="p-demo-avatar">AR</span><span><b>Ari Rivera</b><small>Sample traveler · not an account</small></span><span class="p-persona-spark">✳</span></div><a class="p-button is-primary p-signin-continue" href="{_e(next_url)}">Open the sample trip ↗</a><p class="p-muted p-small">No sign-up, email, or identity provider. Changes live only until reload.</p></div></section>'''
    else:
        content = f'''<section class="p-signin-a"><div class="p-signin-art">{_picture('welcome', label='Illustrated Granada skyline with bright sun')}<span class="p-welcome-note">A LITTLE<br>SPACE TO ROAM</span></div><div class="p-signin-copy"><span class="p-eyebrow">YOUR TRIP IS WAITING</span><h1 class="p-title">Make yourself<br><em>at home.</em></h1><p class="p-lede">For this local prototype, you can skip account setup and go straight to a sample trip.</p><div class="p-persona-card"><span class="p-demo-avatar">AR</span><span><b>Ari Rivera</b><small>Sample traveler · no account created</small></span><span class="p-persona-spark">✳</span></div><a class="p-button is-primary p-signin-continue" href="{_e(next_url)}">Continue as Ari →</a><div class="p-no-account"><span>01</span><p>No email or OAuth involved.</p><span>02</span><p>No database or local-storage changes.</p></div></div></section>'''
    return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-signin"><div class="p-container"><a class="p-back-link" href="{_url('plans', variant, slug=slug)}">← Back to your plan</a>{content}<div class="p-signin-footnote"><span>LOCAL PROTOTYPE / SAMPLE PERSONA</span><span>Nothing to sign up for. Just explore.</span></div></div>{_footer(variant)}</main>'''


def _workspace(variant: str, slug: str) -> str:
    source = next((plan for plan in PLANS if plan["slug"] == slug), PLANS[0])
    day_buttons = "".join(
        f'<button class="p-day-select{" is-active" if i == 0 else ""}" type="button" data-select-day="{i}" aria-pressed="{"true" if i == 0 else "false"}"><span>DAY 0{i + 1}</span><b>{_e(day["title"])}</b><small data-day-date="{i}">OCT {9 + i:02d}</small></button>'
        for i, day in enumerate(DAYS)
    )
    day_panels = "".join(
        f'''<article class="p-selected-day tone-{day['tone']}" data-day-panel="{i}"{" hidden" if i else ""}><span class="p-eyebrow">{day['area']}</span><div class="p-selected-time" {_pace_time_attrs(i, day)}>{day['time']} <i>✳</i></div><h3>{_e(day['title'])}</h3><div class="p-selected-stop"><span>◎</span><b>{_e(day['place'])}</b></div><p data-primary-copy>{_e(day['copy'])}</p><p class="p-kid-copy" data-kid-copy hidden>{_e(day['kid'])}</p><div class="p-kid-tag" data-kid-affordance>✳ EASY SWAP FOR KIDS</div><button class="p-day-action" type="button" data-kid-toggle aria-pressed="false"><span>Show kid-friendly swaps</span><b>↗</b></button></article>'''
        for i, day in enumerate(DAYS)
    )
    source_credit = f'''<div class="p-workspace-source"><span class="p-source-avatar">SM</span><span><small>FORKED FROM A SAMPLE GUIDE</small><b>Sofía & Mateo</b><i>{_e(source['title'])} · creator attribution stays with the plan</i></span><span class="p-chip is-plum">SOURCE KEPT</span></div>'''
    controls = '''<section class="p-trip-controls p-card" aria-labelledby="trip-controls-title"><div class="p-control-heading"><span class="p-eyebrow">YOUR PEOPLE, YOUR PACE</span><h2 id="trip-controls-title">Make it fit your crew.</h2><p>Try a change—your sample plan reshapes right here.</p></div><div class="p-control-grid"><label class="p-field p-field-date"><span>Start date</span><input class="p-input" type="date" name="start_date" value="2026-10-09" data-plan-input="start" required></label><label class="p-field"><span>Grown-ups</span><select class="p-input" name="adults" data-plan-input="adults">''' + ''.join(f'<option value="{n}"{" selected" if n == 2 else ""}>{n} {"grown-up" if n == 1 else "grown-ups"}</option>' for n in range(1, 9)) + '''</select></label><label class="p-field"><span>Kids</span><select class="p-input" name="kids" data-plan-input="kids">''' + ''.join(f'<option value="{n}"{" selected" if n == 1 else ""}>{n} {"kid" if n == 1 else "kids"}</option>' for n in range(7)) + '''</select></label><label class="p-field"><span>Youngest age</span><select class="p-input" name="youngest_age" data-plan-input="age">''' + ''.join(f'<option value="{n}"{" selected" if n == 7 else ""}>{n} {"year" if n == 1 else "years"}</option>' for n in range(18)) + '''</select></label><label class="p-field p-field-pace"><span>Day rhythm</span><select class="p-input" name="pace" data-plan-input="pace"><option value="easy">Easy & roomy</option><option value="balanced" selected>Balanced</option><option value="full">Full but flexible</option></select></label></div><p class="p-control-note" data-age-note>Kid-friendly swaps are written for a wide range of ages; adapt them to your family.</p></section>'''
    if variant == "B":
        trip_layout = f'''<section class="p-workspace-atlas"><div class="p-workspace-map">{_route_art()}<span class="p-weather-pin">☀ 22°</span><span class="p-map-leg">3 EASY DAYS / GRANADA</span></div>{source_credit}<div class="p-workspace-topline"><div><span class="p-eyebrow">YOUR TRIP / SAMPLE WORKSPACE</span><h1 class="p-title">Granada, <em>your way.</em></h1><p class="p-lede">A three-day family starter from a synthetic creator guide.</p></div><button class="p-button is-secondary" type="button" data-share-open>Preview a share ↗</button></div><div class="p-workspace-columns"><aside>{controls}<div class="p-weather-card"><span class="p-eyebrow">WEATHER FEEL</span><strong>Sunny-ish <i>22°</i></strong><p>Illustrative fixture, never a live forecast.</p></div></aside><section class="p-itinerary-board"><div class="p-section-head"><div><span class="p-eyebrow">PICK A DAY</span><h2 class="p-title p-title-small">Your trip, in beats.</h2></div><button class="p-kid-mode" type="button" data-global-kid-toggle aria-label="Show kid-friendly swaps" aria-pressed="false"><span data-kid-global-label>✳ Kid swaps</span> <span data-kid-switch-state>OFF</span></button></div><nav class="p-day-select-row" aria-label="Choose a trip day">{day_buttons}</nav>{day_panels}</section></div></section>'''
    elif variant == "C":
        trip_layout = f'''<section class="p-workspace-family"><div class="p-family-workspace-intro"><div><span class="p-eyebrow">A SAMPLE FAMILY TRIP / GRANADA</span><h1 class="p-title">A little plan<br>for <em>your people.</em></h1><p class="p-lede">Every day gets a little fresh air, a little wonder, and an easy-out option.</p></div><div class="p-family-workspace-scene">{_picture('workspace-family', label='Illustrated family trip scene')}</div></div>{source_credit}<div class="p-family-controls">{controls}<div class="p-weather-card"><span class="p-weather-icon" aria-hidden="true">☀</span><span class="p-eyebrow">A SUNNY-ISH SAMPLE</span><strong>22° <i>Granada</i></strong><p>Fixture-only weather. Check the forecast before you head out.</p></div></div><section class="p-section p-family-agenda"><div class="p-section-head"><div><span class="p-eyebrow">PICK TODAY'S LITTLE ADVENTURE</span><h2 class="p-title p-title-small">Choose a day.</h2></div><button class="p-button is-secondary" type="button" data-share-open>Preview a share ↗</button></div><nav class="p-day-select-row p-family-day-select" aria-label="Choose a trip day">{day_buttons}</nav><div class="p-selected-day-grid">{day_panels}</div></section></section>'''
    else:
        trip_layout = f'''<section class="p-workspace-overview"><div class="p-workspace-intro"><div><span class="p-eyebrow">YOUR TRIP / SAMPLE WORKSPACE</span><h1 class="p-title">Granada, <em>your way.</em></h1><p class="p-lede">A sample three-day plan, ready to bend around your people.</p></div><div class="p-workspace-weather"><span aria-hidden="true">☀</span><b>22°</b><small>SUNNY-ISH<br>FIXTURE ONLY</small></div></div>{source_credit}<div class="p-workspace-columns"><aside class="p-workspace-sidebar">{controls}<div class="p-weather-card"><div class="p-weather-top"><span class="p-eyebrow">FORECAST FEEL</span><span>☀</span></div><strong>Sunny-ish <i>22°</i></strong><p>Easy layers for the late hilltop breeze.</p><small>Illustrative sample, not live weather</small></div><button class="p-button is-secondary p-share-button" type="button" data-share-open>Preview a share ↗</button></aside><section class="p-itinerary-board"><div class="p-section-head"><div><span class="p-eyebrow">THE DAYS ARE YOURS</span><h2 class="p-title p-title-small">Pick a day to peek inside.</h2></div><button class="p-kid-mode" type="button" data-global-kid-toggle aria-label="Show kid-friendly swaps" aria-pressed="false"><span data-kid-global-label>✳ Kid swaps</span> <span data-kid-switch-state>OFF</span></button></div><nav class="p-day-select-row" aria-label="Choose a trip day">{day_buttons}</nav><div class="p-selected-day-grid">{day_panels}</div><div class="p-day-rail-art">{_route_art()}</div></section></div></section>'''
    state = '''<div class="p-live-state" role="status" aria-live="polite" data-trip-state>3 travelers · Oct 09–11 · Balanced rhythm · Day 1 of 3 · memory-only sample</div>'''
    return f'''<main id="main" class="traveler-prototype traveler-variant-{variant.lower()} traveler-workspace" data-workspace data-trip-slug="{_e(source['slug'])}"><div class="p-container"><div class="p-memory-ribbon"><span>IN-MEMORY SAMPLE</span><b>Nothing is saved. Changes disappear when this page reloads.</b><i aria-hidden="true">✳</i></div>{trip_layout}{state}<div class="p-workspace-footnote"><span>CREATOR CREDIT TRAVELS WITH THIS FORK</span><span>✳ Weather, stop times, and trip details are fixtures. No booking, fetching, or account.</span></div></div>{_footer(variant)}<dialog class="p-share-dialog" data-share-dialog aria-labelledby="share-title"><div class="p-share-dialog-head"><span class="p-eyebrow">READ-ONLY PREVIEW</span><button type="button" class="p-dialog-close" data-share-close aria-label="Close share preview">×</button></div><div class="p-share-preview"><span class="p-eyebrow">A SAMPLE TRIP BY ARI RIVERA</span><h2 id="share-title">Granada with room to roam</h2><p data-share-summary>3 travelers · Oct 09–11 · Balanced rhythm</p><div class="p-share-source">Inspired by Sofía & Mateo’s synthetic creator guide</div><div class="p-share-day-list">{_share_days()}</div><small>This is a preview on this device—not a public link or invite.</small></div><div class="p-share-actions"><button class="p-button is-secondary" type="button" data-share-print>Print / save as PDF</button><button class="p-button is-primary" type="button" data-share-close>Back to my trip</button></div></dialog></main>'''


def render_traveler(page: str, variant: str, slug: str = DEFAULT_SLUG, query: str = "", search_params: dict | None = None) -> str:
    """Render prototype page content only; shared header/document shell belongs to prototype_ui."""
    page = page if page in PAGES else "home"
    variant = variant.upper() if variant.upper() in VARIANTS else "A"
    slug = slug if any(item["slug"] == slug for item in PLANS) else DEFAULT_SLUG
    if page == "home":
        body = _home(variant)
    elif page == "discover":
        body = _discover(variant, query)
    elif page == "plans":
        body = _plan(variant, slug)
    elif page == "signin":
        body = _signin(variant, slug)
    elif page == "search":
        body = _search(variant, search_params or {})
    else:
        body = _workspace(variant, slug)
    return _variant_bar(page, variant, slug, query) + body
