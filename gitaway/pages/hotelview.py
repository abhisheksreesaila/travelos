"""The hotel's own page inside the opened square (F-275, D-860..D-865): what the hotel says about itself and what guests say about it, drawn from LiteAPI's /data/hotel and
/data/reviews (gitaway/liteapi.py `hotel`, `reviews`; asked when a square is opened, never for every square).

    GET /plan/matrix/hotel?id=<LiteAPI hotel id>    the fragment as JSON {html} for assets/js/v2drawer.js, which puts it in the hotel's slot; a plain `def` (the call can wait)
    rich(h, rv)                                      the fragment as an element: the photo mosaic ("The hotel's own photos", a lightbox from "See all N photos"), the rating and
                                                     the hotel's words, its facilities and check-in times, the guests' sentiment by category and the newest reviews, and the hotel's rooms with their photos
    sample_slides()                                  the showcase's gallery: generic CC0 hotel pictures, each captioned "Sample photo · ..." (assets/photos/CREDITS.md); never reviews, off a real hotel

Everything from LiteAPI is a guest's or a hotel's own text: it is escaped (FastHTML does) and never trusted as markup; a photo is https only (liteapi `_https`). The AI summary is LiteAPI's
reading of the reviews and says so. Nothing here is invented: no reviews off a real hotel's answer, none at all on the showcase.
"""

import json

from fasthtml.common import Button, Details, Div, H4, Img, Li, P, Small, Span, Summary, Ul, to_xml
from starlette.responses import JSONResponse

from gitaway import liteapi
from gitaway.icons import icon

PATH = "/plan/matrix/hotel"
OWN = "The hotel’s own photos"
AI_NOTE = "Summary written by AI from the guest reviews"
MOSAIC = 5                # photos in the mosaic; the rest wait behind "See all"
PHOTOS_MAX = 40           # photos kept in the fragment (a hotel can have a hundred)
FACILITIES_SHOWN = 8
REVIEWS_SHOWN = 4
SAMPLE_SLIDES = (("lobby-front-desk.jpg", "Hotel lobby"), ("room-bed-lamp.jpg", "Hotel room"), ("pool-courtyard.jpg", "Hotel pool"), ("breakfast-buffet.jpg", "Hotel breakfast"),
                 ("room-balcony-view.jpg", "Hotel room with a view"))
TYPES = {"couple": "Couple", "extended_group": "Group", "solo_traveller": "Solo", "family_with_children": "Family", "friends": "Friends", "business": "Business"}
COUNTRIES = {"us": "United States", "au": "Australia", "ca": "Canada", "gb": "United Kingdom", "de": "Germany", "fr": "France", "br": "Brazil", "mx": "Mexico", "nl": "Netherlands", "es": "Spain",
             "it": "Italy", "ie": "Ireland", "nz": "New Zealand", "jp": "Japan", "in": "India", "se": "Sweden", "ch": "Switzerland", "ae": "United Arab Emirates", "sg": "Singapore", "cn": "China"}


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


def _facilities(h):
    if not h.facilities:
        return ""
    head, tail = h.facilities[:FACILITIES_SHOWN], h.facilities[FACILITIES_SHOWN:]
    return Div(H4("Facilities", cls="dr-sub"), Ul(*[Li(f) for f in head], cls="dr-fac"),
               Details(Summary(f"All {len(h.facilities)} amenities"), Ul(*[Li(f) for f in tail], cls="dr-fac"), cls="dr-more") if tail else "", cls="dr-facs")


def _rating(h, rv):
    if h.rating is None:
        return ""
    count = rv.total if rv and rv.total else h.review_count
    pros = Ul(*[Li(icon("check", 15, 2.4), t) for t in rv.pros[:4]], cls="dr-pros") if rv and rv.pros else ""
    cons = Ul(*[Li(icon("flag", 15, 2.2), t) for t in rv.cons[:4]], cls="dr-cons") if rv and rv.cons else ""
    return Div(Div(Span(score_text(h.rating), cls="dr-score num"), Div(Span(rating_word(h.rating), cls="dr-word"), Small(f"{count:,} reviews" + (f" · {AI_NOTE.lower()}" if pros or cons else "")), cls="dr-rt"), cls="dr-rate"),
               Div(pros, cons, cls="dr-pc") if pros or cons else "", cls="dr-rating")


def _categories(rv):
    if not rv or not rv.categories:
        return ""
    return Div(H4(f"What guests say · {AI_NOTE.lower()}", cls="dr-sub"),
               Div(*[Div(Div(Span(c.name), Span(score_text(c.rating), cls="num"), cls="dr-ch"),
                         Div(Span(style=f"width:{max(0, min(100, round((c.rating or 0) * 10)))}%"), cls="dr-bar", role="img", aria_label=f"{c.name} {score_text(c.rating)} out of 10"),
                         P(c.description) if c.description else "", cls="dr-cat") for c in rv.categories], cls="dr-cats"), cls="dr-sent")


def _review(r):
    meta = " · ".join(x for x in (TYPES.get(r.type, r.type.replace("_", " ").capitalize()) if r.type else "", COUNTRIES.get(r.country.lower(), r.country.upper()) if r.country else "", r.date) if x)
    return Div(Div(Span((r.name or "G")[:1].upper(), cls="dr-av", aria_hidden="true"), Div(Span(r.name or "A guest", cls="dr-rn"), Small(meta)), Span(f"{score_text(r.score)}/10" if r.score is not None else "", cls="dr-rs num"), cls="dr-rh"),
               H4(r.headline, cls="dr-rhead") if r.headline else "",
               P(icon("check", 15, 2.4), r.pros, cls="dr-rp") if r.pros else "", P(icon("flag", 15, 2.2), r.cons, cls="dr-rc") if r.cons else "",
               P("Left a score, no words.", cls="dr-rnone") if not (r.headline or r.pros or r.cons) else "", cls="dr-rev")


def _reviews(rv):
    if not rv or not rv.items:
        return ""
    shown, rest = rv.items[:REVIEWS_SHOWN], rv.items[REVIEWS_SHOWN:]
    return Div(H4(f"Newest of {rv.total:,} reviews" if rv.total else "Newest reviews", cls="dr-sub"), Div(*[_review(r) for r in shown], cls="dr-revs"),
               Details(Summary("Read more reviews"), Div(*[_review(r) for r in rest], cls="dr-revs"), cls="dr-more") if rest else "", cls="dr-reviews")


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


def rich(h, rv=None):
    """The fragment: everything the hotel and its guests say, as one element for the hotel's slot. `h` is liteapi.HotelDetails, `rv` liteapi.HotelReviews or None."""
    mos = mosaic([(p.url, p.caption) for p in h.photos], h.name)
    times = P(Span(icon("calendar", 15, 2), f"Check-in from {h.checkin}") if h.checkin else "", Span(icon("calendar", 15, 2), f"Check-out by {h.checkout}") if h.checkout else "", cls="dr-times") if h.checkin or h.checkout else ""
    info = Div(Div(_paragraphs(h), _facilities(h), times, cls="dr-ic-l"), Div(_rating(h, rv), cls="dr-ic-r"), cls="dr-info")
    return Div(mos, info, _categories(rv), _reviews(rv), _rooms(h), Span(json.dumps(room_photos(h), ensure_ascii=False), cls="dr-roomphotos", hidden=True, data_json="1"), cls="dr-richin")


def fragment(hotel_id: str, family: str = ""):
    """(the element, or None when LiteAPI has nothing for this id) for the hotel's slot. Both calls go through the gate and are kept; either may be missing."""
    h = liteapi.hotel(hotel_id, family)
    if h is None:
        return None
    return rich(h, liteapi.reviews(hotel_id, family))


def register(app):
    @app.get(PATH)
    def hotel_fragment(request, session, id: str = ""):
        from gitaway.pages import tripmatrix as mx
        el = fragment(id, mx._who(request, session))
        if el is None:
            return JSONResponse({"html": ""}, headers={"Cache-Control": "no-store"})
        return JSONResponse({"html": to_xml(el)}, headers={"Cache-Control": "no-store"})
