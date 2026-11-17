"""Today: the next thing, on the day (F-287, D-926..D-930; docs/briefs/trip-day.md). The logic is gitaway/today.py; this is the page and the card the planner shows while the trip is near.

GET /trip/today[?day=YYYY-MM-DD]   what the family's open trip holds right now: before (a countdown, when flight check-in opens, packing weather), a travel day (the next thing first:
                                   the flight with a labelled "leave by" estimate, then the hotel with its address, check-in, code, directions, a ride, the weather and who to call), during
                                   (today's plans, the hotel and its check-out) and after ("How was it?" and Share to Instagram). Signed out or with no trip it goes where /trip/plan goes.
                                   `?day=` previews another date, on the showcase only; it is the page's own morning (6 AM) of that day.

"Use my location" (assets/js/today.js) works only on a tap, in the page: the browser's position becomes a straight-line distance to the hotel's coordinates (the map cache's, when it has
them). Nothing is sent to the server or kept. Once opened the page is in the service worker's cache (assets/sw.js keeps every page a person opens), and the planner asks the worker to
keep it ahead of time. The route is a plain `def`: it can wait on the airport drive and the forecast.
"""

from datetime import date, datetime, time

from fasthtml.common import A, B, Div, H1, H2, Link, P, Script, Section, Span, Small

from gitaway import access, airportdrive, catalog, geo, phone, phones, planv2 as pv, session as ses, showcase, today as td, tripcal as cal, tripday as tday, tripgeo, v2
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import booking, tripshare
from gitaway.partners import uber_deep_link

PATH = "/trip/today"
HEAD = (Link(rel="stylesheet", href="/assets/css/today.css"), *tripshare.HEAD, Script(src="/assets/js/today.js", defer=True), *[Script(src=s, defer=True) for s in tripshare.SCRIPTS])
PREVIEW_AT = time(6, 0)
WX_ICON = {"sun": "sun", "cloud": "cloud", "rain": "rain", "snow": "snow", "wind": "wind"}


def href(day="") -> str:
    return f"{PATH}?day={day}" if day else PATH


def clock(session, day="") -> tuple:
    """(now at the trip, the previewed date or None). `day` (YYYY-MM-DD) moves the clock to that morning, on the showcase only; anything else is ignored."""
    if day and showcase.on():
        try:
            d = date.fromisoformat(day)
        except ValueError:
            d = None
        if d:
            return datetime.combine(d, PREVIEW_AT), d
    return td.local_now(ses.trip_zone(session)), None


def _t(dt) -> str:
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def _d(dt) -> str:
    return f"{dt:%a %b} {dt.day}"


def _when(dt) -> str:
    return f"{_d(dt)}, {_t(dt)}"


def _ft(dt) -> str:
    """A flight's time on its airport's own clock, with the zone: "Fri Oct 16, 8:05 AM PDT"."""
    return f"{_when(dt)} {dt.tzname()}" if dt.tzinfo else _when(dt)


def _place(stay, trip) -> str:
    """What Directions and the ride look up: the stay's name and address (the sample's: its name and the place)."""
    return f"{stay.name}, {stay.address}" if stay.address else f"{stay.name}, {trip.place}"


# ---- the cards ---------------------------------------------------------------------------------------------------------------------------

def _tag(text, cls=""):
    return Span(text, cls="td-tag" + (f" {cls}" if cls else ""))


def _code(label, code):
    return Div(Span(label, cls="td-k"), Span(code, cls="td-code"), cls="td-row") if code else ""


def _flight(i, first, trip):
    f = i.flight
    rows = [Div(Span("Leaves", cls="td-k"), Span(_ft(f.depart), cls="td-v"), cls="td-row"), Div(Span("Lands", cls="td-k"), Span(_ft(f.arrive), cls="td-v"), cls="td-row")]
    leave = (Div(icon("bell", 20, 2.2), Div(B(f"Leave by about {_t(i.leave.at)}"), Small(i.leave.words()), cls="td-lv-t"), cls="td-leave", id="td-leave") if i.leave and not i.past else "")
    return Section(Div(_tag("Next", "is-next") if first else _tag("In the air") if i.airborne else _tag("Done") if i.past else "", Span(icon("plane", 22, 2.2), cls="td-ic k-flight"),
                       Div(H2(f"{f.origin} → {f.dest}"), Span(f.name, cls="td-sub"), cls="td-ht"), cls="td-head"),
                   *rows, leave, _code("Confirmation", f.confirmation), cls="td-card td-flight" + (" is-next" if first else ""), id="td-flight")


def _call(stay):
    """The hotel's own number as a button beside Directions (a `tel:` link), or "" when the booking has none: then `_contact` says so at the foot of the card. Never a number we were not given."""
    n = phones.tel(stay.phone)
    return A(icon("phone", 18, 2.4), "Call the hotel", href=f"tel:{n}", cls="td-btn", id="td-call") if n else ""


def _contact(stay):
    """No number from the hotel: the booking's own way instead, the code, where it was booked and Who to call (nothing here when the hotel has a number, `_call`)."""
    if phones.tel(stay.phone):
        return ""
    said = f" Quote code {stay.confirmation}." if stay.confirmation else ""
    where = f" Booked on {stay.booked_on}." if stay.booked_on else ""
    return Div(P(f"No phone number from the hotel yet.{said}{where}", cls="td-none", id="td-nophone"), A(icon("phone", 18, 2.4), "Who to call", href=booking.href(sos=True), cls="td-btn"), cls="td-contact")


def wallet_rows(booking=None, family: str = ""):
    """The stay's "Add to Apple Wallet" and "Save to Google Wallet" rows for its More menu (F-288, `walletpass.buttons`): none for a sample stay, without the family, or while neither vendor is set up."""
    if booking is None or not family:
        return []
    from gitaway import walletpass
    try:
        return walletpass.buttons(booking, family, **v2.ITEM)
    except Exception:      # noqa: BLE001 - a pass that cannot be offered never breaks the day's page
        return []


def _locate(coords):
    """"Use my location" (F-293: a row of the hotel's More menu, with its privacy note) and where the answer is read, on the card (`#td-near`)."""
    if not coords:
        return "", ""
    row = A(icon("nav", 18, 2.4), Span("Use my location"), href="#td-locate", id="td-locate", data_lat=f"{coords[0]:.6f}", data_lon=f"{coords[1]:.6f}", **v2.ITEM)
    return row, Small("Only when you tap. Your position is used on this page to measure to the hotel and goes nowhere else.", cls="td-fine td-menu-note")


def _stay(stay, trip, ua, phase, coords, b=None, past=False, first=False, dated=False, family=""):
    place = _place(stay, trip)
    when = {"checkin": ("Check in", stay.check_in), "checkout": ("Check out", stay.check_out)}.get(phase)
    if phase == "staying":
        when, dated = ("Check out", stay.check_out), True
    rows = [Div(Span(when[0], cls="td-k"), Span(_when(when[1]) if dated else _t(when[1]), cls="td-v"), cls="td-row", id="td-when")] if when else []
    addr = Div(Span("Address", cls="td-k"), Span(stay.address, cls="td-v"), cls="td-row", id="td-addr") if stay.address else Div(Span("Area", cls="td-k"), Span(stay.area, cls="td-v"), cls="td-row") if stay.area else ""
    near, note = _locate(coords)
    more = v2.more(near, *wallet_rows(stay.confirmation or None, family), note, ident="td-more", cls="td-more", compact=True)
    acts = Div(A(icon("nav", 18, 2.4), "Directions", href=tday.maps_url(place, ua), cls="td-btn is-main", id="td-directions"),
               A(icon("car", 18, 2.4), "Get a ride", href=uber_deep_link("", place), rel="noopener", cls="td-btn", id="td-ride"), _call(stay), cls="td-acts")      # F-293 review: a ride is core to the travel day (docs/briefs/trip-day.md), so it stays in view
    return Section(Div(_tag("Next", "is-next") if first else _tag("Done") if past else "", Span(icon("bed", 22, 2.2), cls="td-ic k-stay"),
                       Div(H2(stay.name), Span("Where you are staying" if phase == "staying" else "Your hotel", cls="td-sub"), cls="td-ht"), more, cls="td-head"),
                   acts, *rows, addr, _code("Confirmation", stay.confirmation), P("", cls="td-near", id="td-near", role="status", aria_live="polite") if coords else "", _contact(stay),
                   cls="td-card td-stay" + (" is-next" if first else ""), id="td-stay")


def _wx_line(w):
    if not w.cond:
        return ""
    temps = f"{w.hi}°/{w.lo}°" if w.hi is not None else ""
    kind = "Sample weather" if w.sample else "Typical weather, not a forecast yet" if w.typical else "Forecast"
    return Div(Span(icon(WX_ICON.get(w.cond, "cloud"), 26, 2), cls="td-wxi"), Div(B(f"{w.word} {temps}".strip()), Small(kind), cls="td-wxt"), cls="td-wx")


def _weather(days, notes, idx, title="Today's weather"):
    w = days[idx] if 0 <= idx < len(days) else None
    if not w or not w.cond:
        return ""
    return Section(H2(title), _wx_line(w), *[Small(t, cls="td-fine") if not h else A(t, href=h, rel="noopener", cls="td-fine") for t, h in notes if not t.startswith("Typical ")], cls="td-card td-weather", id="td-weather")


def _packing(trip, days, notes):
    """Before the trip: each day's sky across the trip, so the bag can be packed for it. Only days something is known about."""
    known = [(d, w) for d, w in zip((trip.start.fromordinal(trip.start.toordinal() + k) for k in range(len(days))), days) if w.cond]
    if not known:
        return ""
    wet = [d for d, w in known if w.wet]
    note = P(f"Rain is forecast on {', '.join(f'{d:%A}' for d in wet)}. Pack for it.", cls="td-nudge") if wet else ""
    rows = [Div(Span(f"{d:%a}", cls="td-wd"), Span(icon(WX_ICON.get(w.cond, "cloud"), 20, 2), cls="td-wxi"), Span(f"{w.hi}°" if w.hi is not None else "", cls="td-hi"), Span(f"/{w.lo}°" if w.lo is not None else "", cls="td-lo"),
                Span("typical" if w.typical else "sample" if w.sample else "forecast", cls="td-src"), cls="td-day") for d, w in known]
    return Section(H2("What to pack for"), *rows, note, *[Small(t, cls="td-fine") if not h else A(t, href=h, rel="noopener", cls="td-fine") for t, h in notes if not t.startswith("Typical ")], cls="td-card td-pack", id="td-pack")


def _checkin_card(i):
    f = i.flight
    link = A(icon("ticket", 18, 2.4), f"Open {f.airline}'s check-in", href=i.checkin_url, target="_blank", rel="noopener", cls="td-btn td-checkin") if i.checkin_url else ""
    return Section(Div(Span(icon("plane", 22, 2.2), cls="td-ic k-flight"), Div(H2(f"Flight check-in opens {_ft(i.opens)}"), Span(f"{f.name} · {f.origin} → {f.dest}, leaves {_ft(f.depart)}", cls="td-sub"), cls="td-ht"), cls="td-head"),
                   P("Online check-in usually opens 24 hours before a flight.", cls="td-fine"), link, cls="td-card td-opens", id="td-opens")


def _plans(t):
    if not t.plans:
        return Section(H2("Today's plans"), P("Nothing planned for today yet.", cls="td-none"), A("Plan the day", href="/trip/plan", cls="td-btn"), cls="td-card td-plans", id="td-plans")
    return Section(H2("Today's plans"), *[Div(Span(tday.span_label(p.start, p.end), cls="td-time"), B(p.title), cls="td-plan") for p in t.plans], A("Open My trip", href="/trip/plan", cls="td-link"), cls="td-card td-plans", id="td-plans")


# ---- the page -----------------------------------------------------------------------------------------------------------------------------

def _heading(t, trip, now, preview):
    if t.state == "before":
        return "Your trip is coming", Div(B(str(t.to_go), cls="num"), Span(" day to go" if t.to_go == 1 else " days to go"), cls="td-count")
    if t.state == "after":
        return "How was it?", P(f"{trip.title} ended {_d(datetime.combine(trip.end, time()))}.", cls="td-lede")
    n = (trip.end - trip.start).days + 1
    return ("Travel day" if t.state == "travel" else "Today"), P(f"Day {t.day + 1} of {n} · {_d(now)}", cls="td-lede")


def _drives(trip, t) -> dict:
    """The drive minutes (airportdrive's, from OpenStreetMap's router) for the flights leaving today: {airport: minutes}. Can wait on the network, so only a plain `def` handler asks."""
    out = {}
    for i in t.items:
        if isinstance(i, td.FlightItem) and not i.past:
            stay = next((s for s in trip.stays if s.check_in.date() <= i.flight.depart.date() <= s.check_out.date()), None)
            town = td.drive_town(trip, i.flight, stay)
            found = (airportdrive.drive(i.flight.origin, town) or (airportdrive.drive(i.flight.origin, trip.place) if stay and stay.address else None)) if town else None
            if found:
                out[i.flight.origin] = found.minutes
    return out


def _coords(session, trip, stay):
    if not stay:
        return None
    with geo.cache_scope(session):
        return geo.cached_coords(_place(stay, trip))


def draw(session, request, day=""):
    """The page's body for the open trip, or None when there is no booking."""
    b = ses.booking(session)
    fam = str((session or {}).get("tenant_id") or "")      # F-288: the wallet buttons are this family's own
    trip = td.from_booking(session, b)
    now, preview = clock(session, day)
    t = td.build(trip, now)
    if t.state == "travel":
        t = td.build(trip, now, _drives(trip, t))
    ua = request.headers.get("user-agent", "")
    days, notes = pv.sky(cal.trip("", b))
    if t.state in ("travel", "during"):
        tripgeo.warm(session)
    title, lead = _heading(t, trip, now, preview)
    tags = [_tag("Sample trip: made-up flight and hotel", "is-sample")] if trip.sample else []
    if preview:
        tags.append(_tag(f"Preview of {preview:%a, %b} {preview.day}", "is-preview"))
    saved = Div(id="td-saved", cls="td-saved", hidden=True, data_saved="0", data_at=catalog.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"), role="status")      # sw.js flips data-saved to 1 in a copy it serves from its cache; today.js then says so
    head = Section(saved, Div(*tags, cls="td-tags") if tags else "", H1(title, cls="td-h1 disp"), lead, cls="td-top", id="td-top")
    body = []
    if t.state == "before":
        nxt = next((i for i in t.flights if not i.past), None)
        body += [_checkin_card(nxt) if nxt else "", _packing(trip, days, notes)]
        if t.stay:
            body.append(_stay(t.stay, trip, ua, "checkin", _coords(session, trip, t.stay), b, dated=True, family=fam))
    elif t.state == "travel":
        first = True
        for i in t.items:
            if isinstance(i, td.FlightItem):
                body.append(_flight(i, first and not i.past, trip))
            else:
                body.append(_stay(i.stay, trip, ua, i.phase, _coords(session, trip, i.stay), b, past=i.past, first=first and not i.past, family=fam))
            first = first and i.past
        body.append(_weather(days, notes, t.day))
    elif t.state == "during":
        body += [_plans(t), _stay(t.stay, trip, ua, "staying", _coords(session, trip, t.stay), b, family=fam) if t.stay else "", _weather(days, notes, t.day)]
    else:
        body.append(Section(H2("Share the trip"), P("Make a card of it for Instagram. It never shows a booking, a price or an email.", cls="td-fine"), tripshare.open_button(access.request_role()) or "", cls="td-card td-share", id="td-share"))
    return Div(head, *[x for x in body if x != ""], Div(A(icon("chev-left", 16, 2.6), "Back to My trip", href="/trip/plan", cls="td-link"), cls="td-foot"), cls="td-wrap", data_state=t.state)


def card(session, day=""):
    """The planner's Today card while the trip is near or under way, else "": one line of what is next, and the way in. No network: the drive and the forecast wait for the page."""
    b = ses.booking(session)
    if not b:
        return ""
    trip = td.from_booking(session, b)
    now, preview = clock(session, day)
    if not td.near(trip, now):
        return ""
    t = td.build(trip, now)
    if t.state == "before":
        line = f"Your trip starts in {t.to_go} day{'s' if t.to_go != 1 else ''}" if t.to_go else "Your trip starts today"
        first = next((i for i in t.flights), None)
        sub = f"Flight check-in opens {_when(first.opens)}" if first else ""
    elif t.state == "travel":
        line = "Travel day"
        nxt = next((i for i in t.items if not i.past), None)
        sub = ("Next: " + (f"{nxt.flight.name} leaves at {_t(nxt.at)}" if isinstance(nxt, td.FlightItem) else f"{'Check in' if nxt.phase == 'checkin' else 'Check out'} at {nxt.stay.name}, {_t(nxt.at)}")) if nxt else "Everything for today is done"
    else:
        line = "Today"
        n = len(t.plans)
        sub = f"{n} plan{'s' if n != 1 else ''} today" + (f", first {t.plans[0].title} at {tday.span_label(t.plans[0].start, t.plans[0].end).split(' ')[0]}" if n else "") if n else "Nothing planned for today yet"
    return Section(Span(icon("spark", 20, 2.2), cls="td-ic"), Div(B(line, cls="td-card-h"), Span(sub, cls="td-card-s"), cls="td-card-t"),
                   A("Open Today", icon("arrow-right", 16, 2.6), href=href(preview.isoformat() if preview else ""), cls="td-btn td-open", id="td-open"),
                   Script(src="/assets/js/today.js", defer=True), Link(rel="stylesheet", href="/assets/css/today.css"), cls="td-minicard", id="td-card", data_today=href(preview.isoformat() if preview else ""), aria_label="Today")


def register(app):
    @app.get(PATH)
    def today(session, request, day: str = ""):
        if (r := phone.guard(session, PATH)):
            return r
        return page("Today", draw(session, request, day), current="trip", head=HEAD, noindex=True, footer=False, v2=True, quiet=True)
