"""The hotel's own page inside the opened square (F-275, D-860..D-865): what the hotel says about itself and what guests say about it, drawn from LiteAPI's /data/hotel and
/data/reviews (gitaway/liteapi.py `hotel`, `reviews`; asked when a square is opened, never for every square).

    GET /plan/matrix/hotel?id=<LiteAPI hotel id>&pt=<traveller type>    the fragment as JSON {html} for assets/js/v2drawer.js, which puts it in the hotel's slot; a plain `def` (the call can wait)
    rich(h, rv)                                      the fragment as an element: the photo mosaic ("The hotel's own photos", a lightbox from "See all N photos"), a compact dashboard (F-290:
                                                     score, the last-100 strip with one streak line, short category bars, one "Read the reviews"), the fine print up front under a "Heads up" line
                                                     (F-291), the hotel's rooms with their photos, and the drawer that holds everything long (pages/reviewdrawer.py)
    sample_slides()                                  the showcase's gallery: generic CC0 hotel pictures, each captioned "Sample photo · ..." (assets/photos/CREDITS.md); never reviews, off a real hotel

Everything from LiteAPI is a guest's or a hotel's own text: it is escaped (FastHTML does) and never trusted as markup; a photo is https only (liteapi `_https`). The AI summary is LiteAPI's
reading of the reviews and says so. Nothing here is invented: no reviews off a real hotel's answer, none at all on the showcase.
"""

import hashlib
import hmac
import json
import secrets

from fasthtml.common import Button, Details, Div, H4, Img, P, Small, Span, Summary, to_xml
from starlette.responses import JSONResponse

from pathlib import Path

from gitaway import aerial, liteapi, reviewtrend, showcase
from gitaway.icons import icon

PATH = "/plan/matrix/hotel"
OWN = "The hotel’s own photos"
AI_NOTE = "Summary written by AI from the guest reviews"
_KEY = secrets.token_bytes(32)      # signs the hotel ids this process drew into squares: the route answers only those, so a made-up id spends nobody's allowance
MOSAIC = 5                # photos in the mosaic; the rest wait behind "See all"
PHOTOS_MAX = 40           # photos kept in the fragment (a hotel can have a hundred)
FACILITIES_SHOWN = 8
SAMPLE_SLIDES = (("lobby-front-desk.jpg", "Hotel lobby"), ("room-bed-lamp.jpg", "Hotel room"), ("pool-courtyard.jpg", "Hotel pool"), ("breakfast-buffet.jpg", "Hotel breakfast"),
                 ("room-balcony-view.jpg", "Hotel room with a view"))
TYPES = {"couple": "Couple", "extended_group": "Group", "solo_traveller": "Solo", "family_with_children": "Family", "friends": "Friends", "business": "Business"}
TYPE_LOWER = {"family_with_children": "families", "couple": "couples", "solo_traveller": "solo travellers", "extended_group": "groups", "friends": "friends", "business": "business travellers"}
COUNTRIES = {"us": "United States", "au": "Australia", "ca": "Canada", "gb": "United Kingdom", "de": "Germany", "fr": "France", "br": "Brazil", "mx": "Mexico", "nl": "Netherlands", "es": "Spain",
             "it": "Italy", "ie": "Ireland", "nz": "New Zealand", "jp": "Japan", "in": "India", "se": "Sweden", "ch": "Switzerland", "ae": "United Arab Emirates", "sg": "Singapore", "cn": "China"}


def token(hotel_id: str) -> str:
    """The hotel's id signed for the slot that asks for its page ("lp1b8e6.3fa9..."): only this process makes it, so only a hotel a square really showed can be asked for."""
    return f"{hotel_id}.{hmac.new(_KEY, hotel_id.encode(), hashlib.sha256).hexdigest()[:24]}"


def unsign(tok: str) -> str:
    """The hotel id inside a token, or "" when it is not one this process signed."""
    hotel_id, _, sig = str(tok or "").partition(".")
    return hotel_id if hotel_id and hmac.compare_digest(token(hotel_id), f"{hotel_id}.{sig}") else ""


def rating_word(score) -> str:
    return "" if score is None else "Exceptional" if score >= 9 else "Very good" if score >= 8 else "Good" if score >= 7 else "Okay" if score >= 6 else "Mixed"


def score_text(v) -> str:
    return f"{v:g}" if v is not None else ""


def sample_slides() -> list:
    """The showcase's gallery: generic hotel pictures, each said to be a sample (assets/photos/CREDITS.md), never the hotel."""
    return [(f"/assets/photos/{f}", f"Sample photo · {label}") for f, label in SAMPLE_SLIDES]


def _photo(i: int, url: str, caption: str, alt: str, shown: bool, cls=""):
    inner = [Img(src=url, alt=alt or caption or "Hotel photo", loading="lazy", referrerpolicy="no-referrer")] if shown else []
    if shown and caption:
        inner.append(Span(caption, cls="dr-pcap"))
    return Button(*inner, type="button", cls=f"dr-ph {cls}".strip(), data_lb=str(i), data_src=url, data_cap=caption, hidden=not shown, aria_label=f"Open photo {i + 1}: {caption or alt}")


def mosaic(photos, name: str, own: bool = True):
    """The photo grid: one large and four small, "See all N photos" over the last; every photo (to PHOTOS_MAX) is in the page for the lightbox, but only the mosaic's are loaded."""
    photos = list(photos)[:PHOTOS_MAX]
    if not photos:
        return ""
    tiles = []
    for i, (url, cap) in enumerate(photos):
        tiles.append(_photo(i, url, cap, f"{name}: {cap}" if cap else name, i < MOSAIC, "is-big" if i == 0 else ""))
    more = Span(icon("image", 16, 2.2), f"See all {len(photos)} photos", cls="dr-all") if len(photos) > MOSAIC else ""
    return Div(Div(*tiles, more, cls=f"dr-mos n{min(len(photos), MOSAIC)}"), Span(OWN if own else "Sample photos", cls="dr-own"), cls="dr-photos", data_count=str(len(photos)))


def _paragraphs(h):
    first = h.paragraphs[:2]
    rest = h.paragraphs[2:]
    def para(p):
        return P(Span(p.lead, cls="dr-lead") if p.lead else "", " " if p.lead and p.text else "", p.text, cls="dr-para")
    return Div(*[para(p) for p in first], Details(Summary("More about the hotel"), *[para(p) for p in rest], cls="dr-more") if rest else "", cls="dr-about")


def _rating(h, rv):
    """The score with its words and count: a button that opens the review drawer when LiteAPI gave reviews (F-282). The AI's pros and cons are in the drawer (F-290)."""
    if h.rating is None:
        return ""
    count = rv.total if rv and rv.total else h.review_count
    head = [Span(score_text(h.rating), cls="dr-score num"), Div(Span(rating_word(h.rating), cls="dr-word"), Small(f"{count:,} reviews"), cls="dr-rt")]
    if rv and rv.items:
        return Div(Button(*head, Span(icon("chev-right", 18, 2.2), cls="dr-go", aria_hidden="true"), type="button", cls="dr-rate dr-scorebtn", data_rv_open="all",
                          aria_label=f"Rated {score_text(h.rating)} out of 10, {rating_word(h.rating)}, from {count:,} reviews. Read the guests’ reviews"), cls="dr-rating")
    return Div(Div(*head, cls="dr-rate"), cls="dr-rating")


def _bars(rv):
    """The categories as short bars with their numbers and no paragraphs (F-290); the AI's paragraph for each is in the drawer (reviewdrawer.summary)."""
    if not rv or not rv.categories:
        return ""
    return Div(H4("What guests rate", cls="dr-sub"),
               Div(*[Div(Span(c.name, cls="dr-cn"), Div(Span(style=f"width:{max(0, min(100, round((c.rating or 0) * 10)))}%"), cls="dr-bar", role="img", aria_label=f"{c.name} {score_text(c.rating)} out of 10"),
                         Span(score_text(c.rating), cls="num dr-cv"), cls="dr-cat") for c in rv.categories], cls="dr-cats"), cls="dr-sent")


def _review(r):
    meta = " · ".join(x for x in (TYPES.get(r.type, r.type.replace("_", " ").capitalize()) if r.type else "", COUNTRIES.get(r.country.lower(), r.country.upper()) if r.country else "", r.date) if x)
    return Div(Div(Span((r.name or "G")[:1].upper(), cls="dr-av", aria_hidden="true"), Div(Span(r.name or "A guest", cls="dr-rn"), Small(meta)), Span(f"{score_text(r.score)}/10" if r.score is not None else "", cls="dr-rs num"), cls="dr-rh"),
               H4(r.headline, cls="dr-rhead") if r.headline else "",
               P(icon("check", 15, 2.4), r.pros, cls="dr-rp") if r.pros else "", P(icon("flag", 15, 2.2), r.cons, cls="dr-rc") if r.cons else "", cls="dr-rev")


SHAPES = {"good": "8 or more", "mixed": "6 or 7", "poor": "5 or less"}      # the strip's legend: a shape and a colour for each, so it reads without colour


def _strip(t):
    """The last reviews as dots, oldest to newest (F-278): a circle for a score of 8 or more, a diamond for 6 or 7, a triangle for 5 or less, each also a colour, with ONE line of words the server
    computed (reviewtrend): the streak, else the recent average against the hotel's rating (F-290). Every dot is aria-hidden; the strip says its counts once."""
    n = len(t.dots)
    said = f"The last {n} reviews, oldest to newest: {t.good} good, {t.mixed} mixed, {t.poor} poor"
    dots = Div(*[Span(cls=f"tr-d is-{d.kind}", title=f"{score_text(d.score)}/10" + (f" · {d.date}" if d.date else ""), aria_hidden="true") for d in t.dots], cls="tr-dots", role="img", aria_label=said, data_rv_open="all")
    legend = Div(*[Span(Span(cls=f"tr-d is-{k}", aria_hidden="true"), f"{SHAPES[k]} · {getattr(t, k)}", cls="tr-key") for k in SHAPES], cls="tr-legend")
    line = t.streak or t.recent
    return Div(H4(f"Last {n} reviews" + (f" · {t.span}" if t.span else ""), cls="dr-sub"), dots, Div(Span("Oldest"), Span("Newest"), cls="tr-ends", aria_hidden="true"), legend,
               P(line, cls="tr-w") if line else "", cls="tr-strip")


def source_line(rv) -> str:
    named = reviewtrend.source_name(rv.items)
    return f"Reviews from {named} (LiteAPI)" if named else "Reviews from LiteAPI"


def _trend(rv, overall=None):
    """The strip with its streak line, right under the rating (a number alone says little); "" when no review has a score."""
    t = reviewtrend.trend(rv.items, overall) if rv and rv.items else None
    return _strip(t) if t else ""


def _rooms(h):
    if not h.rooms:
        return ""
    cards = []
    for r in h.rooms:
        facts = " · ".join(x for x in (", ".join(r.beds), f"{r.size_m2:g} m²" if r.size_m2 else "", f"Sleeps {r.sleeps}" if r.sleeps else "") if x)
        cards.append(Div(Div(Img(src=r.photos[0], alt=f"{r.name}, the hotel’s own photo", loading="lazy", referrerpolicy="no-referrer"), cls="dr-rphoto") if r.photos else Div(cls="dr-rphoto is-none"),
                         Span(r.name, cls="dr-rname"), Small(facts) if facts else "", cls="dr-hroom"))
    return Div(H4("Rooms at this hotel", cls="dr-sub"), Div(*cards, cls="dr-hrooms"), P(f"{OWN} of each room. The price above is for the room you choose there.", cls="dr-fine"), cls="dr-rms")


def room_photos(h) -> dict:
    """{lower-case room name: its first photo}: assets/js/v2drawer.js puts it on the room you can choose, when the offer and the hotel call the room the same."""
    return {r.name.lower(): r.photos[0] for r in h.rooms if r.photos}


def dashboard(h, rv):
    """The compact dashboard (F-290): the score with its words and count, the last-100 strip with its streak line, the category bars, and one "Read the reviews". Beside the photos on a laptop,
    under them on a phone. Everything long (the AI's paragraphs, what guests like and watch for, the reviews) waits in the drawer."""
    parts = [_rating(h, rv), _trend(rv, h.rating), _bars(rv)]
    if not any(parts):
        return ""
    way_in = Button("Read the reviews", icon("arrow-right", 16, 2.2), type="button", cls="tr-read", data_rv_open="all") if rv and rv.items else ""
    return Div(*parts, way_in, cls="dr-dash")


def heads_up():
    """F-291: the one quiet line of the fine print's "Heads up" rows, as chips that open their row. It starts empty and hidden: assets/js/hotelfine.js fills it from the rows that are on the page
    (the hotel's own costs and conditions, the chosen room's and flight's, the pins), so it says only what the fine print says and nothing when there is nothing."""
    return Div(Span("Heads up", cls="hu-k"), Div(cls="hu-chips"), cls="hu", data_hu="1", hidden=True, role="group", aria_label="Heads up: what to know before you book")


def rich(h, rv=None, ptype=""):
    """The fragment: everything the hotel and its guests say, as one element for the hotel's slot. `h` is liteapi.HotelDetails, `rv` liteapi.HotelReviews or None.
    The "Heads up" line, then the photos (and what the hotel says under them) and the compact dashboard side by side, then the fine print up front (with F-284's "See it from above" card), the rooms,
    and the drawer. `ptype` is kept for the route's sake (the party's own average is in the fine print, F-282)."""
    from gitaway.pages import aerialview, fineprint, reviewdrawer      # the card, the fine print and the drawer are their own modules (F-284, F-282)
    mos = mosaic([(p.url, p.caption) for p in h.photos], h.name)
    dash = dashboard(h, rv)
    top = Div(Div(mos, Div(_paragraphs(h), cls="dr-info"), cls="dr-left"), dash, cls="dr-top" + (" has-dash" if dash else ""))
    return Div(heads_up(), top, fineprint.section(h, rv, aerialview.card(h)), _rooms(h),
               Span(json.dumps(room_photos(h), ensure_ascii=False), cls="dr-roomphotos", hidden=True, data_json="1"), reviewdrawer.drawer(h, rv), cls="dr-richin")


SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "liteapi_hotel"
SAMPLE_NOTE = ("Sample: this is a real hotel’s recorded data (Hilton Los Angeles Airport, from LiteAPI on 16 Nov 2026), shown so you can try the view. "
               "The hotels in this square are made up, so their prices, rooms and photos are samples.")


SAMPLE_DASH = "Sample: these scores and reviews are a real hotel’s (Hilton Los Angeles Airport), shown so you can see how it reads"


def sample_fragment(place_name: str = ""):
    """The showcase's dashboard and fine print: Hilton Los Angeles Airport's recorded LiteAPI answers (tests/fixtures/liteapi_hotel), said to be a sample in the section itself; "" off the showcase
    or when the recording is not there. Its "See it from above" card is the sample card (aerialview.sample_card), and its pins are the recorded ones."""
    if not showcase.on():
        return ""
    try:
        h = liteapi.read_hotel(json.loads((SAMPLE_DIR / "hotel.json").read_text(encoding="utf-8")))
        rv = liteapi.read_reviews(json.loads((SAMPLE_DIR / "reviews100.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return ""
    if h is None:
        return ""
    from gitaway.pages import aerialview, fineprint, reviewdrawer
    return Div(P(SAMPLE_DASH, cls="fp-sample"), heads_up(), Div(dashboard(h, rv), cls="dr-top"), fineprint.section(h, rv, aerialview.sample_card(place_name), SAMPLE_NOTE), reviewdrawer.drawer(h, rv), cls="dr-richin dr-sample")


def fragment(hotel_id: str, family: str = "", ptype: str = ""):
    """(the element, or None when LiteAPI has nothing for this id) for the hotel's slot. Both calls go through the gate and are kept; either may be missing."""
    h = liteapi.hotel(hotel_id, family)
    if h is None:
        return None
    if h.lat is not None and h.lng is not None and not showcase.on():      # the showcase's hotels are made up: nothing to look down on
        aerial.warm(h.id, h.lat, h.lng, h.name, family)      # F-286: its pins are asked in the background, so they are kept by the time the card is tapped
    return rich(h, liteapi.reviews(hotel_id, family), ptype)


def register(app):
    @app.get(PATH)
    def hotel_fragment(request, session, id: str = "", pt: str = ""):
        from gitaway.pages import tripmatrix as mx
        hotel_id = unsign(id)
        el = fragment(hotel_id, mx._who(request, session), pt if pt in TYPES else "") if hotel_id else None      # an id we did not draw is nothing: no call, no budget spent
        if el is None:
            return JSONResponse({"html": ""}, headers={"Cache-Control": "no-store"})
        return JSONResponse({"html": to_xml(el)}, headers={"Cache-Control": "no-store"})
