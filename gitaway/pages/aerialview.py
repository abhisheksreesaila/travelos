"""See it from above (F-284, D-905..D-909): the card in the opened square's hotel and the three routes behind it. Everything heavy waits for the tap (assets/js/aerial.js).

    card(h)                     the hotel's card (an element), from LiteAPI's HotelDetails with coordinates; "" when LiteAPI gave none. hotelview.rich puts it under the photos.
    sample_card(place_name)     the showcase's card for a sample square: it opens a recorded real hotel (Hilton Los Angeles Airport, or Hyatt Regency Lake Tahoe for Lake Tahoe), said to be a sample
    GET  /plan/matrix/aerial/pins?id=<signed token>     the truth pins as JSON, worked out here from OpenStreetMap (gitaway/aerial.py); a plain `def` (Overpass can take seconds)
    POST /plan/matrix/aerial/open  (id, view)           counts one satellite or photoreal open and hands the page its Google browser key; past GOOGLE_3D_A_DAY it says "Back tomorrow"

The page never sends a coordinate or a hotel id of its own: the card carries the id of a hotel the server drew, signed (hotelview.token), and the coordinates are read here, from LiteAPI's
own answer (kept), never from the request. A token for a sample hotel is only good on the showcase. Without GOOGLE_MAPS_API_KEY the card offers the map view only.
"""

from fasthtml.common import Button, Div, NotStr, Span
from starlette.responses import JSONResponse

from gitaway import aerial, liteapi, showcase
from gitaway.icons import icon
from gitaway.pages import hotelview

PATH = "/plan/matrix/aerial"
SAMPLE_PREFIX = "sample-"
KICKER = "Know this before you book"
SAMPLE_KICKER = "Sample view"
TITLE = "See it from above"
BACK = "Back tomorrow"
BACK_MORE = "Satellite and photoreal views are limited each day, because each one is billed to GitAway. The map view still works."
NO_PINS = "OpenStreetMap did not answer just now, so there are no pins to show. The map is still here."
HEADERS = {"Cache-Control": "no-store"}


def _thumb():
    """A drawn schematic (blocks, a road, a runway line), not imagery: the card never claims to show the hotel."""
    return NotStr('<svg viewBox="0 0 104 80" fill="none" aria-hidden="true"><path d="M0 62 C30 54 60 66 104 56 V80 H0Z" fill="var(--wx)" opacity=".3"/>'
                  '<path d="M78 0 L92 80" stroke="var(--tix)" stroke-width="6" opacity=".5"/><path d="M8 14 L98 34" stroke="var(--flight)" stroke-width="1.5" stroke-dasharray="3 3"/>'
                  '<path d="M30 52 L50 42 L70 52 L50 62Z" fill="var(--stay)" opacity=".55"/><path d="M30 52 V36 L50 26 V42Z" fill="var(--stay)" opacity=".8"/>'
                  '<path d="M70 52 V36 L50 26 V42Z" fill="var(--stay)" opacity=".6"/><path d="M30 36 L50 26 L70 36 L50 46Z" fill="var(--card-solid)" opacity=".9"/></svg>')


def _card(token: str, name: str, kicker: str, line: str):
    return Button(Span(_thumb(), cls="av-thumb"),
                  Span(Span(kicker, cls="av-k"), Span(TITLE, cls="av-t"), Span(line, cls="av-l"), cls="av-tx"),
                  Span(icon("arrow-right", 20, 2), cls="av-go", aria_hidden="true"),
                  type="button", cls="av-card", data_aerial=token, data_hotel=name, data_keyed="1" if aerial.offered() else "", aria_haspopup="dialog")


def card(h):
    """The card for a hotel LiteAPI described, with the heads-up line when its pins are already kept (never waiting on the network), else what the view shows."""
    if h.lat is None or h.lng is None:
        return ""
    return _card(hotelview.token(h.id), h.name, KICKER, aerial.teaser(h.id) or aerial.NEUTRAL)


def sample_card(place_name: str):
    """The showcase's card inside a sample square (its hotels are made up, with no place on a map): a recorded real hotel stands in, labelled a sample."""
    which = "tahoe" if "tahoe" in str(place_name).lower() else "lax"
    got = aerial.sample(which)
    if not showcase.on() or got is None:
        return ""
    return _card(hotelview.token(SAMPLE_PREFIX + which), got["name"], SAMPLE_KICKER, got["headline"])


def _hotel(tok: str, who: str):
    """(key, lat, lon, name, sample) of the hotel a signed token names, or None: a token this process did not sign, a sample off the showcase, a hotel LiteAPI has no place for."""
    key = hotelview.unsign(tok)
    if not key:
        return None
    if key.startswith(SAMPLE_PREFIX):
        got = aerial.sample(key[len(SAMPLE_PREFIX):]) if showcase.on() else None
        return (key, got["lat"], got["lon"], got["name"], got) if got else None
    h = liteapi.hotel(key, who)
    return (key, h.lat, h.lng, h.name, None) if h and h.lat is not None and h.lng is not None else None


def register(app):
    @app.get(PATH + "/pins")
    def aerial_pins(request, session, id: str = ""):
        from gitaway.pages import tripmatrix as mx
        found = _hotel(id, mx._who(request, session))
        if found is None:
            return JSONResponse({"ok": False, "message": NO_PINS}, status_code=404, headers=HEADERS)
        key, lat, lon, name, sample = found
        got = sample or aerial.pins(key, lat, lon, name)
        if got is None:
            return JSONResponse({"ok": False, "message": NO_PINS, "name": name, "lat": lat, "lon": lon, "pins": [], "keyed": aerial.offered()}, headers=HEADERS)      # the place is known: the map still shows, with no pins
        return JSONResponse({"ok": True, **got, "keyed": aerial.offered()}, headers=HEADERS)

    @app.post(PATH + "/open")
    def aerial_open(id: str = "", view: str = ""):
        if not hotelview.unsign(id) or view not in ("sat", "photo"):
            return JSONResponse({"ok": False}, status_code=400, headers=HEADERS)
        state, key = aerial.open_google()
        if state == "off":
            return JSONResponse({"ok": False, "message": "Satellite and photoreal are not switched on."}, status_code=404, headers=HEADERS)
        if state == "full":
            return JSONResponse({"ok": False, "full": True, "message": BACK, "more": BACK_MORE}, status_code=429, headers=HEADERS)
        return JSONResponse({"ok": True, "key": key}, headers=HEADERS)
