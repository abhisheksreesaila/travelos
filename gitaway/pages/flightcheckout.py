"""The flight's parts of "Book this trip" (F-276, D-972..D-978): the travellers form, the flight's facts before paying, LiteAPI's payment form for the flight, and the flight on the pass.

The pieces are drawn into the checkout sheet by gitaway/pages/matrixbook.py (this module draws no route). Everything typed or from LiteAPI comes out through FastHTML's escaping; the travellers are
personal data: they are only ever echoed back to the person who typed them (a form with a mistake), never put in an address or a log.
"""

from datetime import date, timedelta

from fasthtml.common import Div, H3, Input, Label, Noscript, Option, P, Select, Span

from gitaway import catalog, flightbook as fb, liteapi, matrixbook as mb
from gitaway.icons import icon


def _err(name, errors):
    return P(errors[name], id=f"mxb-{name}-e", cls="mxb-err", role="alert") if errors.get(name) else ""


def _field(name, label, value, errors, **attrs):
    return Div(Label(label, fr=f"mxb-{name}", cls="mxb-l"),
               Input(id=f"mxb-{name}", name=name, value=value, required=True, aria_invalid="true" if errors.get(name) else None, aria_describedby=f"mxb-{name}-e" if errors.get(name) else None, **attrs),
               _err(name, errors), cls="mxb-field" + (" has-err" if errors.get(name) else ""))


def _select(name, label, options, value, errors):
    return Div(Label(label, fr=f"mxb-{name}", cls="mxb-l"),
               Select(*[Option(text, value=code, selected=code == value) for code, text in options], id=f"mxb-{name}", name=name, required=True, aria_invalid="true" if errors.get(name) else None,
                      aria_describedby=f"mxb-{name}-e" if errors.get(name) else None), _err(name, errors), cls="mxb-field mxb-sel" + (" has-err" if errors.get(name) else ""))


def born_range(kind: int, age, depart: date) -> tuple:
    """(earliest, latest) birth date the browser's date picker should offer: the server's rule (`flightbook.clean_travellers`) as a hint, the server still decides."""
    def back(years):
        try:
            return depart.replace(year=depart.year - years)
        except ValueError:      # Feb 29
            return depart.replace(year=depart.year - years, day=28)
    if kind == 0:
        return back(120), back(18)
    return back(age + 1) + timedelta(days=1), back(age)


def traveller_cards(adults: int, kid_ages, values: dict, errors: dict, abroad: bool, depart: date) -> list:
    """One card a seat, as an airline's form would ask: first and last name as on the ID, birth date, gender (M, F, X), nationality (United States unless changed), and for an international
    route the passport number, the issuing country and its expiry. The lead traveller's names are the stay's guest."""
    cards = []
    for i, (kind, age) in enumerate(fb.seats(adults, kid_ages)):
        get = lambda n, i=i: values.get(fb.field(i, n), "")      # noqa: E731
        low, high = born_range(kind, age, depart)
        who = "Lead traveller" if i == 0 else f"Traveller {i + 1}"
        what = "adult" if kind == 0 else f"kid, age {age}"
        body = [Div(Span(who, cls="mxb-tv-n"), Span(what, cls="mxb-tv-k"), cls="mxb-tv-h"),
                Div(_field(fb.field(i, "first"), "First name", get("first"), errors, autocomplete="given-name" if i == 0 else "off", maxlength=mb.NAME_MAX),
                    _field(fb.field(i, "last"), "Last name", get("last"), errors, autocomplete="family-name" if i == 0 else "off", maxlength=mb.NAME_MAX), cls="mxb-two"),
                Div(_field(fb.field(i, "dob"), "Birth date", get("dob"), errors, type="date", min=low.isoformat(), max=high.isoformat(), autocomplete="bday" if i == 0 else "off"),
                    _select(fb.field(i, "sex"), "Gender on ID", [("", "Choose"), *fb.GENDERS], get("sex"), errors), cls="mxb-two"),
                _select(fb.field(i, "nat"), "Nationality", [("", "Choose"), *[(c, n) for c, n in fb.country_options()]], get("nat") or "US", errors)]
        if abroad:
            body += [Div(_field(fb.field(i, "docno"), "Passport number", get("docno"), errors, autocomplete="off", maxlength=14, autocapitalize="characters"),
                         _field(fb.field(i, "docx"), "Passport expires", get("docx"), errors, type="date", autocomplete="off"), cls="mxb-two"),
                     _select(fb.field(i, "docc"), "Issued by", [("", "Choose"), *[(c, n) for c, n in fb.country_options()]], get("docc") or "US", errors)]
        cards.append(Div(*body, cls="mxb-tv", data_traveller=str(i)))
    return cards


def contact_fields(values: dict, errors: dict) -> list:
    """The lead traveller's email and mobile number (country code and number): where the airline reaches them."""
    return [_field("email", "Email", values.get("email", ""), errors, type="email", autocomplete="email", maxlength=mb.EMAIL_MAX, inputmode="email"),
            Div(_field("cc", "Country code", values.get("cc", "") or "1", errors, type="text", autocomplete="tel-country-code", maxlength=4, inputmode="numeric"),
                _field("phone", "Mobile number", values.get("phone", ""), errors, type="tel", autocomplete="tel-national", maxlength=mb.PHONE_MAX, inputmode="tel"), cls="mxb-two mxb-cc")]


def _lines(*ps):
    return [p for p in ps if p]


def rules(fp, *, ident="") -> Div:
    """The flight's facts from the offer, said before paying: the fare, what the bags carry, refundable and changeable, in plain words. Seats and bags for sale are not offered yet (D-975)."""
    v = fp.verified
    if v is None:
        return Div(Div(icon("plane", 16, 2.2), Span("The flight"), cls="mxb-pol-t"), P(fb.SAMPLE_WORDS + ".", cls="mxb-pol-h"), cls="mxb-policy mxb-frules", **({"id": ident} if ident else {}))
    inc, paid = fb.bags_words(v)
    return Div(Div(icon("plane", 16, 2.2), Span(f"The flight · {v.fare}" if v.fare else "The flight"), cls="mxb-pol-t"),
               *_lines(P(inc, cls="mx-r-s") if inc else "", P(paid, cls="mx-r-s") if paid else ""),
               P(fb.refund_words(v.refundable) + ".", cls="mxb-pol-h", data_refund="1"), P(fb.change_words(v.changeable) + ".", cls="mxb-pol-h", data_change="1"),
               P("Seats and bags are not sold here yet: the airline adds them.", cls="mxb-fine") if paid else "", cls="mxb-policy mxb-frules", **({"id": ident} if ident else {}))


def route_lines(segs) -> list:
    return [P(fb.seg_words(s), cls="mx-r-s") for s in segs]


def pay_pane(prep, secret: str, return_url: str, stay_charge_cents: int) -> Div:
    """The step after the travellers for a real flight: LiteAPI's payment form for the flight in our sheet. Two charges, said again: the flight now, the stay in its own form next."""
    fp = prep.flight
    sandbox = liteapi.mode() != "live"
    segs = fp.segments
    return Div(H3("Pay for your flight", cls="mxb-q"),
               P(f"{fb.route_words(segs)} · {fb.airline_words(segs)}", cls="mxb-lede"), *route_lines(segs),
               Div(Span("Charged now", cls="mxb-tl"), Span(catalog.money(fp.cents), cls="num mxb-total", data_charge="1"), cls="mxb-sum t"),
               P(f"Two charges from Nuitée: the flight {catalog.money(fp.cents)} now, then the stay {catalog.money(stay_charge_cents)} in its own payment form.", cls="mxb-fine", data_two="1"),
               rules(fp),
               P("Sandbox: use LiteAPI’s test card 4242 4242 4242 4242, any future date, any 3 digits. Nothing is charged.", cls="mxb-fine") if sandbox else "",
               Div(id="mxb-pay-el", cls="mxb-payel", data_pay_root="1", data_key="sandbox" if sandbox else "live", data_secret=secret, data_return=return_url, aria_label="Payment form for the flight"),
               P("Loading LiteAPI’s secure payment form…", cls="mxb-hint", data_pay_wait="1", role="status"),
               Noscript(P("LiteAPI’s payment form needs JavaScript. Turn it on for this page, then book again.", cls="mxb-note is-warn", role="alert")),
               cls="mxb-body mxb-paying", data_pay_pane="1", data_flight="1")


def _refs(row) -> list:
    """LiteAPI's short reference, and the airline's own record locator when it has given one."""
    pnrs = ", ".join(f"{a} {p}".strip() for a, p in fb.locators(row)) or row["pnr"]
    return _lines(P("Booking reference", cls="mxb-k"), P(Span(row["ref"] or row["booking_id"], cls="mxb-id", data_flight_ref=row["ref"] or row["booking_id"]), cls="mxb-code"),
                  P("Airline booking reference", cls="mxb-k") if pnrs else "", P(Span(pnrs, cls="mxb-id", data_flight_pnr=pnrs), cls="mxb-code") if pnrs else "")


def pass_row(row, *, charged: bool = True) -> Div:
    """The flight on the pass: where, both ways, the status in LiteAPI's honest words, the fare's rules, and what was paid."""
    segs = fb.segs_of(row)
    facts = fb.facts_of_row(row)
    pending = row["status"] == "PENDING_CONFIRMATION" and not row["sample"]
    return Div(P("Flight", cls="mxb-k"), P(f"{fb.route_words(segs)} · {fb.airline_words(segs)}", cls="mxb-pass-h"), *route_lines(segs),
               P(icon("bell" if pending else "check", 14, 2.4), fb.status_words(row), cls="mx-r-s mxb-fstatus" + (" is-wait" if pending else ""), data_status=row["status"], role="status"),
               P(f"{facts.get('fare')} · {fb.refund_words(facts.get('refundable') is True)}", cls="mx-r-s") if facts.get("fare") else "",
               P(f"Paid {catalog.money(row['total_cents'])} to Nuitée (LiteAPI).", cls="mx-r-s") if charged and not row["sample"] else "", cls="mxb-pass-row mxb-pass-flight")


def sample_pass_row(row) -> Div:
    return Div(P("Flight", cls="mxb-k"), P(f"{fb.route_words(fb.segs_of(row))} · {row['airline']}", cls="mxb-pass-h"), *route_lines(fb.segs_of(row)),
               P(icon("shield", 14, 2.2), fb.SAMPLE_WORDS, cls="mx-r-s", data_status="SAMPLE"), cls="mxb-pass-row mxb-pass-flight")


def flight_stub(row) -> Div:
    return Div(*_refs(row), cls="mxb-stub-i")
