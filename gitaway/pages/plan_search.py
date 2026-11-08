"""The booking lanes (F-195, F-198): what /plan shows for a real trip. Any destination by name, links only.

The workspace behind /plan is an invented catalog (airlines, hotels and prices that do not exist), so in production every visitor gets this page instead, and anywhere a place is
typed (`place=`). It has no offers of its own: one card per lane (flights, stays, a car, tickets and things to do, and at a snow place lift tickets and ski school bought direct),
each a search at the site gitaway/partners/registry.py picks for this place, these dates and this party, where the site shows today's real prices. A plain link says "No commission";
a paying partner says "We may earn a commission". The flight card shows a real cached price when the Aviasales Data API has one (gitaway/partners/prices.py), never an invented one.
Every button goes through /book/<lane> (gitaway/pages/partners.py), which logs the click and sends the family on. Drawn by `plan.py`'s route, not registered on its own.
"""

from dataclasses import replace
from urllib.parse import urlencode

from fasthtml.common import A, Button, Div, Form, H1, H2, Input, Label, Li, Link, Main, Option, P, Script, Section, Select, Span, Ul

from gitaway import catalog, pickers
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_widgets
from gitaway.partners import links, places, prices, registry

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/plansearch.css"), plan_widgets.CSS, Script(src="/assets/js/plansearch.js", defer=True))
ICONS = {"flight": "plane", "stay": "bed", "car": "car", "todo": "ticket", "direct": "star"}
FINE = "Every booking happens on the partner's site, under their terms and their support. GitAway never takes payment and never handles a change or a refund."
BAD_IATA = "Use a three-letter airport code, like RNO, or leave it empty."


def ahead(trip):
    """`trip` with its dates moved to the next ones worth searching, the same length, when they have passed (a stale link, or a bare /plan with the sample's old dates): a search for the past books nothing."""
    if trip.depart >= catalog.today():
        return trip
    from gitaway import publish  # here, not at the top: publish reads the community database
    depart, ret = publish.sample_dates(trip.nights + 1)
    return replace(trip, depart=depart, return_=ret)


def place_text(to="", focus="", place=""):
    """The place a request names: `place` as typed, else the catalog destination of a `to=` key (Disneyland for its focus), else ""."""
    if (place or "").strip():
        return place
    dest = next((x for x in catalog.DESTINATIONS if x.key == (to or "").strip().lower()), None)
    if not dest:
        return ""
    return "Disneyland" if focus == "disney" and dest.key == "la" else dest.name


def search_from(place="", iata="", d="", r="", a="", k="", to="", home="", focus=""):
    """(Search or None, {field: problem}) from a request's words. Dates and party as catalog.trip_from_url reads them (anything bad is the sample's, moved ahead); a bad airport
    code is a problem said on the page and kept out of every link."""
    errors = {}
    if (home or "").strip() and not catalog.clean_home(home):
        errors["home"] = catalog.BAD_HOME
    if (iata or "").strip() and not places.clean_iata(iata):
        errors["iata"] = BAD_IATA
    if (place or "").strip() and any((d, r, a, k)):      # typed in the form: a mistake is said, never silently swapped for the sample's dates and party
        try:
            catalog.parse_trip("", "la", d or "", r or "", a or "", k or "")
        except catalog.TripError as e:
            errors["trip"] = " ".join(dict.fromkeys(m for _, m in e.errors))
    trip = ahead(catalog.trip_from_url(d, r, a, k, to or "la", home, focus))
    spot = places.resolve(place_text(to, focus, place), iata)
    return (links.Search(spot, trip.depart, trip.return_, trip.adults, trip.kid_ages, trip.home) if spot else None), errors


def query(search, via="", iata=""):
    """The address words that carry a search to /book and back to /plan."""
    q = {"place": search.place.name, "d": search.depart.isoformat(), "r": search.return_.isoformat(), "a": search.adults}
    if search.kid_ages:
        q["k"] = ",".join(map(str, search.kid_ages))
    if search.home:
        q["home"] = search.home
    if iata:
        q["iata"] = iata
    if via:
        q["via"] = via
    return q


def summary(search) -> str:
    kids = len(search.kid_ages)
    return f"{search.adults} adult{'s' if search.adults != 1 else ''}" + (f", {kids} kid{'s' if kids != 1 else ''}" if kids else "")


def date_label(search) -> str:
    a, b = search.depart, search.return_
    return f"{a:%b} {a.day} – " + (f"{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{b:%b} {b.day}")


def _href(link, q):
    return f"/book/{link.lane}?" + urlencode({"site": link.site, **q})


def _go(link, q, label):
    return A(icon(ICONS[link.lane], 20, 2.2), label, href=_href(link, q), cls="btn btn-ink ps-go", rel="sponsored noopener" if link.paid else "noopener",
             data_lane=link.lane, data_site=link.site)


def _also(found, q):
    rest = found[1:]
    if not rest:
        return ""
    return P(Span("Also on ", cls="ps-label"), *[A(x.name, href=_href(x, q), cls="ps-also", rel="sponsored noopener" if x.paid else "noopener", data_lane=x.lane, data_site=x.site)
                                               for x in rest], cls="ps-alsos")


def _note(link):
    return Span(link.note, cls="ps-note" + (" is-paid" if link.paid else ""), data_note=link.site)


def _hidden(q, *skip):
    return [Input(type="hidden", name=n, value=str(v)) for n, v in q.items() if n not in skip]


def _airport_form(search, q, raw, errors):
    """Where the family flies from, and the destination's airport when we do not know it: one small GET form back to this page."""
    def field(name, label, value, hint, error):
        bad = {"aria_invalid": "true", "aria_describedby": f"ps-err-{name}"} if error else {}
        return Label(Span(label, cls="ps-label"), Input(name=name, value=value, type="text", maxlength="3", placeholder=hint, autocomplete="off", autocapitalize="characters",
                                                        spellcheck="false", **bad), cls="ps-field")
    errs = [Span(e, id=f"ps-err-{n}" if n != "home" else "ps-err", role="alert", cls="ps-error") for n, e in errors.items() if n in ("home", "iata")]
    ask_iata = not search.place.iata or "iata" in raw or "iata" in errors
    return Form(*_hidden(q, "home", "iata"),
                field("home", "Flying from (optional)", raw.get("home") or search.home, "e.g. SFO", errors.get("home")),
                field("iata", "Nearest airport", raw.get("iata") or (search.place.iata if "iata" in raw else ""), search.place.iata or "e.g. RNO", errors.get("iata")) if ask_iata else "",
                Button("Update", type="submit", cls="btn btn-sm"), *errs, action="/plan", method="get", cls="ps-from")


def _card(lane, name, line, blurb, *rest):
    return Section(Span(icon(ICONS[lane], 26, 2.1), cls=f"ps-tile ps-k-{lane}", aria_hidden="true"),
                   Div(H2(name, cls="ps-name"), P(line, cls="ps-what") if line else "", P(blurb, cls="ps-blurb") if blurb else "", *rest, cls="ps-text"),
                   cls=f"ps-card ps-{lane}", aria_label=name, id=f"ps-{lane}")


def cards(search, q, raw=None, errors=None):
    raw, errors = raw or {}, errors or {}
    found = registry.lanes(search)
    p, out = search.place, []
    flight = found["flight"]
    price = prices.flight_from(search.home, p.iata, search.depart, search.return_) if flight and search.home and p.known else None      # only a place of our table (F-198 review)
    out.append(_card("flight", f"Search flights to {p.name}", price.label() if price else (f"Into {p.iata}" if p.iata else ""),
                     f"{flight[0].name} shows today's fares for {date_label(search)}, {summary(search)}." + ("" if search.home else " Leave the airport empty and it asks.")
                     if flight else "Tell us the nearest airport to search flights.",
                     *([_go(flight[0], q, f"Search on {flight[0].name}"), _note(flight[0])] if flight else []), _airport_form(search, q, raw, errors)))
    stay = found["stay"]
    if stay:
        out.append(_card("stay", f"Find stays near {p.city}", "", f"Hotels, cabins and homes for {date_label(search)}, {summary(search)}. The site keeps your booking.",
                         _go(stay[0], q, f"Find stays on {stay[0].name}"), _note(stay[0]), _also(stay, q)))
    car = found["car"]
    if car:
        gear = "An SUV with snow chains and a ski rack, for a winter mountain trip. " if search.winter_snow else ""
        out.append(_card("car", f"Rent a car at {p.iata}" if p.iata else f"Rent a car near {p.city}", "", f"{gear}Pick up {search.depart:%b} {search.depart.day}, drop off {search.return_:%b} {search.return_.day}.",
                         _go(car[0], q, f"Find cars on {car[0].name}"), _note(car[0])))
    todo = found["todo"]
    if todo:
        first = todo[0]
        line = "Disneyland Resort tickets" if p.focus == "disney" else f"{p.name} attractions"
        label = ("See tickets on Klook" if p.focus == "disney" else "Things to do on Klook") if first.site == "klook" else f"Things to do on {first.name}"
        out.append(_card("todo", "Tickets and things to do", line, "Tours, tickets and lessons, sold and kept by the site.", _go(first, q, label), _note(first), _also(todo, q)))
    direct = found["direct"]
    if direct:
        out.append(_card("direct", "Lift tickets and ski school", "", "Sold by the resorts themselves. Buy direct: no partner, no commission.",
                         Ul(*[Li(A(x.name, href=_href(x, q), cls="ps-resort", rel="noopener", data_lane="direct", data_site=x.site)) for x in direct], cls="ps-resorts"),
                         _note(direct[0])))
    return out


def _trip_form(search, q, place_raw, typed=None):
    """Where, when and who: one GET form back to this page. Any place by name. `typed` keeps what was typed when it was refused."""
    v = {**(q if search else {}), **(typed or {})}
    return Form(*_hidden({k: q[k] for k in ("home", "iata", "via") if k in q}),
                Label(Span("Where", cls="ps-label"), Input(name="place", value=place_raw or (search.place.name if search else ""), type="text", maxlength=str(places.MAX_NAME),
                                                            placeholder="Lake Tahoe", autocomplete="off", required=True, cls="ps-wide"), cls="ps-field ps-field-wide"),
                Label(Span("From", cls="ps-label"), Input(name="d", type="date", value=v.get("d", "")), cls="ps-field"),
                Label(Span("To", cls="ps-label"), Input(name="r", type="date", value=v.get("r", "")), cls="ps-field"),
                Label(Span("Adults", cls="ps-label"), Select(*[Option(str(n), value=str(n), selected=str(n) == str(v.get("a", 2)) or None) for n in range(1, catalog.MAX_TRAVELERS + 1)],
                                                             name="a", data_ga="stepper", data_ga_label="Adults", data_ga_hint="18 and over"), cls="ps-field"),
                *_kids(v.get("k", "")),
                Button("Search", type="submit", cls="btn btn-sm"), action="/plan", method="get", cls="ps-from ps-trip", id="ps-trip")


MAX_KIDS = catalog.MAX_TRAVELERS - 1


def kids_from(n, ages) -> str:
    """The `k` words for a trip from the form's kid count and one age picker per kid (F-198 review: a phone's number pad has no comma). An age not picked is "?", which the trip's
    own check refuses with its sentence; nothing typed, nothing given."""
    count = int(n) if str(n).isascii() and str(n).isdigit() else 0
    picked = [str(a).strip() for a in ages[:min(count, MAX_KIDS)]]
    return ",".join(a if a else "?" for a in picked)


def _kids(k):
    """A kid count and one age picker per kid, like /start's (plansearch.js shows one per kid; without it the server reads only the first `n`)."""
    ages = [a.strip() for a in str(k).split(",") if a.strip()]
    n = len(ages)
    pickers_ = [Label(Span(f"Kid {i + 1} age", cls="ps-label"),
                      Select(Option("Pick age", value=""), *[Option("Under 1" if a == 0 else str(a), value=str(a), selected=i < n and ages[i] == str(a) or None) for a in range(catalog.MAX_KID_AGE + 1)],
                             name=f"k{i + 1}", data_ga="chips", data_ga_label=f"Kid {i + 1} age", disabled=i >= n or None),
                      cls="ps-field ps-age", data_age=str(i + 1), hidden=i >= n or None) for i in range(MAX_KIDS)]
    return (Label(Span("Kids", cls="ps-label"), Select(*[Option(str(i), value=str(i), selected=i == n or None) for i in range(MAX_KIDS + 1)], name="n", data_ga="stepper",
                                                       data_ga_label="Kids", data_ga_hint="under 18"), cls="ps-field"), *pickers_)


def search_page(search, via="", raw=None, errors=None):
    """The lanes for `search` (None: nobody has said where yet, the form only). `via` is the creator handle to keep; `raw` and `errors` are mistyped airport codes and what is wrong."""
    raw = raw or {}
    if search is None:
        return page("Book a trip", Main(Div(Span("BOOK A TRIP", cls="eyebrow"), H1("Where are you going?", cls="ps-title"),
                                            P("Any place works. We show no prices of our own: the partners show today's.", cls="ps-fine"),
                                            _trip_form(None, {"via": via} if via else {}, raw.get("place", "")), cls="ps ga-wrap"), id="plan-search"), head=HEAD)
    q = query(search, via, places.clean_iata(raw.get("iata", "")))
    if errors and "trip" in errors:
        return page("Book a trip", Main(Div(Span("BOOK A TRIP", cls="eyebrow"), H1(f"Book your trip to {search.place.name}", cls="ps-title"),
                                            _trip_form(search, q, raw.get("place", ""), raw), P(errors["trip"], role="alert", cls="ps-error", id="ps-err-trip"),
                                            cls="ps ga-wrap"), id="plan-search"), head=HEAD)
    found = cards(search, q, raw, errors)
    paid = any(x.paid for lane in registry.lanes(search).values() for x in lane)
    return page("Plan this trip", Main(
        Div(Span("PLAN THIS TRIP", cls="eyebrow"), H1(f"Book your trip to {search.place.name}", cls="ps-title"),
            P(f"{date_label(search)} · {summary(search)}" + (f" · flying from {search.home}" if search.home else ""), cls="ps-lede", id="ps-lede"),
            P("The dates are a starting guess. We show no prices of our own: the partners show today's.", cls="ps-fine"),
            _trip_form(search, q, ""),
            plan_widgets.beside(search, Div(*found, cls="ps-cards")),      # F-210: weather, money and the drive beside the lanes
            P(FINE + (" We may earn a commission where a link says so." if paid else ""), cls="ps-fine", id="ps-fine"),
            cls="ps ga-wrap"), id="plan-search"), head=HEAD)
