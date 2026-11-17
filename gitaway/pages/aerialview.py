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

import hashlib
import hmac
import time

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
TOKEN_AGE = 6 * 3600       # seconds a card's token is good for the pins and the key: a token scraped from a page stops working
SIGN_IN = "Fly around the hotel in 3D"      # F-289: the immersive view is a reason to sign in, said as an invitation
SIGN_IN_MORE = "Sign in to see the real rooftops, the pool, the parking and what is next door, in satellite and photoreal 3D. The map works without it."
BUSY_WORDS = "Pins are busy, try again in a moment"
LIMIT_WORDS = "You have looked at a lot of places today. Try again tomorrow, or come back to this one: its pins are kept."


def sign(key: str, now: float | None = None) -> str:
    """The card's token: the hotel's key, the time it was issued and a signature of both (this process's secret, hotelview's), so the routes here answer only a card drawn in the last
    TOKEN_AGE seconds. The hotel view's own token (hotelview.token) is unchanged."""
    at = str(int(time.time() if now is None else now))
    return f"{key}.{at}.{hmac.new(hotelview._KEY, f'aerial|{key}|{at}'.encode(), hashlib.sha256).hexdigest()[:24]}"


def unsign(tok: str, now: float | None = None) -> str:
    """The hotel key inside a fresh token of `sign`, or "" when it is forged, malformed or older than TOKEN_AGE."""
    head, _, sig = str(tok or "").rpartition(".")
    key, _, at = head.rpartition(".")
    if not key or not at.isdigit() or not hmac.compare_digest(sig, hmac.new(hotelview._KEY, f"aerial|{key}|{at}".encode(), hashlib.sha256).hexdigest()[:24]):
        return ""
    return key if 0 <= (time.time() if now is None else now) - int(at) <= TOKEN_AGE else ""


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
                  type="button", cls="av-card", data_aerial=token, data_av_name=name, data_keyed="1" if aerial.offered() else "", data_sri_maplibre=aerial.SRI["maplibre"], data_sri_cesium=aerial.SRI["cesium"], aria_haspopup="dialog")


def card(h):
    """The card for a hotel LiteAPI described, with the heads-up line when its pins are already kept (never waiting on the network), else what the view shows."""
    if h.lat is None or h.lng is None:
        return ""
    return _card(sign(h.id), h.name, KICKER, aerial.teaser(h.id) or aerial.NEUTRAL)


def sample_card(place_name: str):
    """The showcase's card inside a sample square (its hotels are made up, with no place on a map): a recorded real hotel stands in, labelled a sample."""
    if not showcase.on():
        return ""
    which = "tahoe" if "tahoe" in str(place_name).lower() else "lax"
    got = aerial.sample(which)
    if got is None:
        return ""
    return _card(sign(SAMPLE_PREFIX + which), got["name"], SAMPLE_KICKER, got["headline"])


def _hotel(tok: str, who: str):
    """(key, lat, lon, name, sample) of the hotel a signed token names, or None: a token this process did not sign, a sample off the showcase, a hotel LiteAPI has no place for."""
    key = unsign(tok)
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
        got = sample or aerial.pins(key, lat, lon, name, mx._who(request, session))
        if got is None or got is aerial.BUSY or got is aerial.LIMIT:
            words = BUSY_WORDS if got is aerial.BUSY else LIMIT_WORDS if got is aerial.LIMIT else NO_PINS
            return JSONResponse({"ok": False, "message": words, "name": name, "lat": lat, "lon": lon, "pins": [], "keyed": aerial.offered()}, headers=HEADERS)      # the place is known: the map still shows, with no pins
        return JSONResponse({"ok": True, **got, "keyed": aerial.offered()}, headers=HEADERS)

    @app.post(PATH + "/open")
    def aerial_open(request, session, id: str = "", view: str = ""):
        who = str((session or {}).get("user_id") or "")
        if not who:      # the Google views are for signed-in people, like Save, Book and Plan (D-761): nobody signed out can draw the key or the day's count down
            from gitaway import session as ses
            back = request.headers.get("referer", "")
            here = back.split(str(request.base_url).rstrip("/"), 1)[1] if back.startswith(str(request.base_url).rstrip("/")) else None      # back to the same page after signing in, only ever our own path
            return JSONResponse({"ok": False, "signin": True, "message": SIGN_IN, "more": SIGN_IN_MORE, "href": ses.signin_href(here if here and here.startswith("/") and not here.startswith("//") else "/")},
                                status_code=401, headers=HEADERS)
        if not unsign(id) or view not in ("sat", "photo"):
            return JSONResponse({"ok": False}, status_code=400, headers=HEADERS)
        state, key = aerial.open_google(who)
        if state == "person":
            return JSONResponse({"ok": False, "full": True, "message": BACK, "more": "You have used today's satellite and 3D views. The map view still works."}, status_code=429, headers=HEADERS)
        if state == "off":
            return JSONResponse({"ok": False, "message": "Satellite and photoreal are not switched on."}, status_code=404, headers=HEADERS)
        if state == "full":
            return JSONResponse({"ok": False, "full": True, "message": BACK, "more": BACK_MORE}, status_code=429, headers=HEADERS)
        return JSONResponse({"ok": True, "key": key}, headers=HEADERS)
