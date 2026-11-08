"""The "Where to?" trip start at /start (F-035).

GET /start                          the form, prefilled with the sample trip (or with the trip in ?d=&r=&a=&k=)
GET /start?go=1&to=&d=&r=&a=&n=&k1=  validates; a good trip redirects to the workspace /plan with the trip in its URL,
                                    a bad one shows the same form again (422) with a friendly message on each field

Any place (F-210): off the showcase (and whenever `place=` is given) the four sample cities are a "Where" box that takes any place, and a good trip goes to /plan's
booking lanes for it (gitaway/pages/plan_search.py); no sample prices, no sample party. "Make this a trip" posts the same fields to /trip/new (gitaway/pages/tripnew.py),
which makes the family's trip and opens the cockpit. On the showcase the sample cities stay.

It is a plain GET form, so it works without JavaScript and the result is a link: reload, share, back. Real inputs and
labels throughout (date pickers, selects), so a phone needs no typing. start.js only shows one age picker per kid.
"""

from dataclasses import replace
from urllib.parse import parse_qs, urlencode

from fasthtml.common import A, Button, Div, Fieldset, Form, H1, Input, Label, Legend, Link, Option, P, Script, Select, Span
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import affiliate, catalog, firstrun, pickers, session as ses, showcase, tripcal, tripday, tripstart
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan, plan_search
from gitaway.partners import places

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/start.css"), Script(src="/assets/js/start.js", defer=True))
MAX_KIDS = catalog.MAX_TRAVELERS - 1
CHIP_FILLS = {"la": "fill-sun", "sd": "fill-sky-tint", "hi": "fill-mint-tint", "nyc": "fill-grape-tint"}
TILTS = (-2, 1.5, -1, 2)


def _options(values, current):
    return [Option(label, value=str(v), **({"selected": True} if str(v) == str(current) else {})) for v, label in values]


def _age_label(n):
    return "Under 1" if n == 0 else str(n)


def _field(label, name, control, error="", hidden=False, extra=None):
    return Label(
        Span(label, cls="st-label"), control,
        Span(error, cls="st-error", id=f"st-err-{name}") if error else "",
        cls="st-field", data_field=name, **({"hidden": True} if hidden else {}), **(extra or {}),
    )


def _control(tag, name, errors, *content, **attrs):
    bad = {"aria_invalid": "true", "aria_describedby": f"st-err-{name}"} if name in errors else {}
    return tag(*content, name=name, id=f"st-{name}", **attrs, **bad)


def _chips(vals, errors):
    chips = []
    for d in catalog.DESTINATIONS:
        chips.append(Label(
            Input(type="radio", name="to", value=d.key, **({"checked": True} if vals["to"] == d.key else {})),
            Span(icon("pin", 18, 2.4), Span(d.name), cls=f"st-face {CHIP_FILLS[d.key]}"),
            cls="st-chip", style=f"--tilt:{TILTS[catalog.DESTINATIONS.index(d)]}deg",
        ))
    err = errors.get("to")
    return Fieldset(
        Legend("Pick where you want to go", cls="st-legend"),
        Div(*chips, cls="st-chips"),
        Span(err, cls="st-error", id="st-err-to", role="alert") if err else "",
        cls="st-where", **({"aria_invalid": "true", "aria_describedby": "st-err-to"} if err else {}),
    )


def _place(vals, errors):
    """Where: any place, typed (F-210)."""
    return Div(_field("Where", "place", _control(Input, "place", errors, type="text", value=vals["place"], maxlength=str(places.MAX_NAME), placeholder="Lisbon, Lake Tahoe, anywhere",
                                                 autocomplete="off", required=True), error=errors.get("place", "")), cls="st-place")


def place_mode(q) -> bool:
    """The "Where" box instead of the sample cities: always off the showcase, and on it whenever a place was typed."""
    return not showcase.on() or bool((q.get("place") or "").strip())


def _form(vals, errors):
    n = vals["n"]
    summary = Div(
        *[A(msg, href=f"#st-{field}", cls="st-error-link") for field, msg in errors.items()],
        role="alert", cls="st-errors", id="st-errors",
    ) if errors else ""
    ages = Div(
        Span("Kids' ages", cls="st-label st-ages-label"),
        *[_field(f"Kid {i + 1} age", f"k{i + 1}",
                 _control(Select, f"k{i + 1}", errors, Option("Pick age", value=""), *_options([(a, _age_label(a)) for a in range(catalog.MAX_KID_AGE + 1)], vals["ages"][i] if i < len(vals["ages"]) else ""),
                          data_ga="chips", data_ga_label=f"Kid {i + 1} age"),
                 error=errors.get(f"k{i + 1}", ""), hidden=i >= n, extra={"data_age": str(i + 1)})
          for i in range(MAX_KIDS)],
        cls="st-ages", id="st-ages", **({"hidden": True} if n == 0 else {}),
    )
    return Form(
        summary,
        _place(vals, errors) if vals.get("place") is not None else _chips(vals, errors),
        Div(
            _field("From", "from", _control(Input, "from", errors, type="text", value=vals["from"], maxlength="3", placeholder="Any, we'll ask", autocomplete="off", autocapitalize="characters", spellcheck="false",
                                            aria_label="Flying from (airport code, optional)"), error=errors.get("from", "")),
            _field("Leaving", "d", _control(Input, "d", errors, type="date", value=vals["d"], required=True, min=catalog.today().isoformat(), data_ga_range="trip", data_ga_label="Leaving"), error=errors.get("d", "")),
            _field("Back", "r", _control(Input, "r", errors, type="date", value=vals["r"], required=True, min=catalog.today().isoformat(), data_ga_range="trip", data_ga_end="", data_ga_label="Back"), error=errors.get("r", "")),
            _field("Adults", "a", _control(Select, "a", errors, *_options([(i, str(i)) for i in range(1, catalog.MAX_TRAVELERS + 1)], vals["a"]), data_ga="stepper", data_ga_label="Adults", data_ga_hint="18 and over"), error=errors.get("a", "")),
            _field("Kids", "n", _control(Select, "n", errors, *_options([(i, str(i)) for i in range(MAX_KIDS + 1)], vals["n"]), data_ga="stepper", data_ga_label="Kids", data_ga_hint="under 18")),
            cls="st-row",
        ),
        ages,
        Input(type="hidden", name="go", value="1"),
        Input(type="hidden", name="focus", value=vals["focus"]) if vals["focus"] else "",      # a Disneyland trip stays one (F-195)
        Input(type="hidden", name="via", value=vals["via"]) if vals["via"] else "",            # and a reader from a creator's trip stays on the honest page (F-195)
        Div(Button("Find my trip", icon("arrow-right", 22, 2.6), type="submit", cls="btn btn-ink st-go"),
            Button(icon("plus", 22, 2.6), "Make this a trip", type="submit", formaction="/trip/new", formmethod="post", cls="btn st-go st-make", id="st-make"),
            cls="st-actions"),
        P("Find my trip shows where to book. Make this a trip keeps it as your family's trip, with a plan for each day.", cls="st-note") if vals.get("place") is not None
        else P("Sample prices for Los Angeles. More places are on the way.", cls="st-note"),
        action="/start", method="get", cls="st-card", id="st-form", novalidate=True, aria_label="Plan a trip",
    )


def continue_card(session, phone=False):
    """"Continue LA with the kids": the booked trip (opens its days) or the picks the traveler left in the workspace."""
    if not ses.current_traveler(session):
        return ""
    b = ses.booking(session)
    if b:
        # F-054: on a phone the booked trip opens on the phone trip view
        t, href, tail = tripcal.trip_of(b), "/trip", ("booked elsewhere" if tripcal.is_imported(b) else f"booked, {catalog.money(b['total_cents'])}")
    elif (saved := ses.remembered_plan(session)):
        p = {k: v[0] for k, v in parse_qs(saved).items()}
        t, href, tail = catalog.trip_from_url(p.get("d"), p.get("r"), p.get("a"), p.get("k"), p.get("to")), f"/plan?{saved}", "your picks are saved"
    else:
        return ""
    return A(
        Span(icon("plane", 22, 2.2), cls="st-continue-ico fill-mint", aria_hidden="true"),
        Span(Span(f"Continue {t.title}", cls="st-continue-title"), Span(f"{t.date_label} · {t.summary} · {tail}", cls="st-continue-sub"), cls="st-continue-text"),
        Span(icon("arrow-right", 20, 2.6), cls="st-continue-go", aria_hidden="true"),
        href=href, cls="st-continue",
    )


def values_of(trip, via="", place=None):
    return {"place": place, "to": trip.key, "from": trip.home, "d": trip.depart.isoformat(), "r": trip.return_.isoformat(), "a": trip.adults, "n": len(trip.kid_ages), "ages": list(trip.kid_ages),
            "focus": trip.focus, "via": via}


def _submitted(q):
    """(form values as typed, TripSearch or None, errors {field: message}) from a submitted GET."""
    def whole(text, default=0):
        return int(text) if text.isascii() and text.isdigit() else default

    n = min(whole(q.get("n", "0")), MAX_KIDS)
    raw_ages = [q.get(f"k{i}", "") for i in range(1, n + 1)]
    typed = " ".join(q.get("place", "").split()) or (plan_search.place_text(q.get("to"), q.get("focus")) if q.get("to") else "")     # an old link's sample city is its city's name
    vals = {"place": typed if place_mode(q) else None, "to": q.get("to", "la"), "from": (q.get("from") or q.get("home") or "").strip().upper(), "focus": q.get("focus", ""), "via": affiliate.valid_via(q.get("via")), "d": q.get("d", ""), "r": q.get("r", ""), "a": q.get("a", "2"), "n": n,
            "ages": [whole(a, "") if a.isascii() and a.isdigit() else "" for a in raw_ages]}
    errors = {}
    for i, a in enumerate(raw_ages, 1):
        if not (a.isascii() and a.isdigit() and int(a) <= catalog.MAX_KID_AGE):
            errors[f"k{i}"] = f"Pick an age from 0 to {catalog.MAX_KID_AGE} for kid {i}."
    if vals["place"] is not None and not vals["place"]:
        errors["place"] = tripstart.PLACE_MISSING
    try:
        trip = catalog.parse_trip(vals["from"], "la" if vals["place"] is not None else vals["to"], vals["d"], vals["r"], vals["a"], ",".join(map(str, vals["ages"])), check_past=True, focus=vals["focus"])
    except catalog.TripError as e:
        trip = None
        for field, msg in e.errors:
            if field == "k":  # already reported on the kid that is wrong
                continue
            else:
                errors.setdefault(field, msg)
    return vals, (None if errors else trip), errors


def start_page(session, vals, errors=None, status=200, phone=False):
    body = page(
        "Where to?",
        Div(
            Div(
                Div(Span("PLAN A TRIP", cls="eyebrow"), H1("Where to?"), Span("Plan it together.", cls="ga-h-two"),
                    P("Pick a place, your dates and who is coming. We line up where to book flights, a stay and a car, with your dates and party filled in."),
                    A(icon("ledger", 16, 2.4), "Import a booked trip", href=firstrun.IMPORT, cls="btn btn-sm st-import", id="st-import"),
                    cls="st-hero"),
                continue_card(session, phone),
                firstrun.welcome("Welcome aboard", "Your family has no trips yet, so this is the fun part. Start one below, bring in a trip you already booked" + (", or see what other travelers shared." if showcase.on() else "."), "#st-form") if firstrun.is_new(session) else "",
                cls="st-left"),  # F-146: the left column of the laptop layout (display: contents below 1020px)
            _form(vals, errors or {}),
            cls="st ga-wrap",
        ),
        current="/start", head=HEAD,
    )
    return body if status == 200 else _with_status(body, status)


def _with_status(body, status):
    return FtResponse(body, status_code=status)


def register(app):
    @app.get("/start")
    def start(session, request):
        q = request.query_params
        if q.get("go"):
            vals, trip, errors = _submitted(q)
            if trip and vals["place"] is not None:      # any place: the booking lanes for it (F-210)
                search, _ = plan_search.search_from(vals["place"], "", trip.depart.isoformat(), trip.return_.isoformat(), str(trip.adults), ",".join(map(str, trip.kid_ages)), "", trip.home)
                if search is None:      # text with nothing to look up (",,", control characters)
                    return start_page(session, vals, {"place": tripstart.PLACE_MISSING}, status=422)
                return RedirectResponse("/plan?" + urlencode(plan_search.query(search, vals["via"])), status_code=303)
            if trip:
                query = "&".join(filter(None, (catalog.trip_query(trip), f"via={vals['via']}" if vals["via"] else "")))     # via is not a cookie: D-125 stands
                return RedirectResponse("/plan" + (f"?{query}" if query else ""), status_code=303)
            return start_page(session, vals, errors, status=422)
        trip = catalog.trip_from_url(q.get("d"), q.get("r"), q.get("a"), q.get("k"), q.get("to"), q.get("home"), q.get("focus"))
        place = None
        if place_mode(q):      # any place (F-210): what was typed (an old city link names its city), dates ahead, and no sample family
            place = (q.get("place") or "").strip() or (plan_search.place_text(q.get("to"), q.get("focus")) if q.get("to") else "")
            trip = plan_search.ahead(trip if q.get("k") or q.get("a") else replace(trip, kid_ages=()))
        return start_page(session, values_of(trip, affiliate.valid_via(q.get("via")), place), phone=tripday.is_phone(request.headers.get("user-agent")))
