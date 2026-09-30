"""The stay detail panel's body (F-026): look around (photos and the lazy 3D explorer), title chips, rooms, add-ons, policy.

Everything is rendered from gitaway.catalog; the page JS only toggles and swaps server figures (see assets/js/workspace.js).
GET /plan/explore?h= returns the explorer fragment, fetched the first time the "Explore the area in 3D" tab opens.
"""

from fasthtml.common import Article, Button, Div, Figcaption, Figure, H2, H3, Img, Li, P, Span, Ul

from gitaway import catalog
from gitaway.icons import icon

CHIP_FILLS = ["fill-sun", "fill-sky", "fill-mint", "fill-bubble"]
FIT_FILL = {"full": "fill-mint-tint", "short": "fill-sun-tint", "none": "fill-bubble-tint"}
KIND = {  # kind -> (pin fill, icon, kicker)
    "hotel": ("ws-k-hotel", "hotel", "Your hotel"),
    "beach": ("fill-sun", "sun", "Beach"),
    "train": ("fill-sky", "train", "Getting around"),
    "park": ("fill-mint", "tree", "Park and play"),
    "food": ("fill-bubble", "food", "Food and shops"),
    "sight": ("fill-grape", "sight", "Sights"),
}
PHOTOS = "/assets/photos/"


def near_text(p):
    return "the beach" if p.label == "Beach" else p.name


def near_strip(d):
    return Span(*[Span(Span(p.walk, cls="ws-near-walk"), f" to {near_text(p)}", cls="ws-near-item") for p in d.near], cls="ws-near")


def _sample(label, photo, tint):
    caption = Figcaption(f"Sample photo · {label}")
    if photo:
        return Figure(Img(src=PHOTOS + photo, alt=f"Sample photo: {label} (not the hotel)", loading="lazy", width="400", height="300"),
                      caption, cls=f"ws-sample-tile {tint}", data_sample=label)
    return Figure(Span(icon("bed", 34, 2), aria_hidden="true"), caption, cls=f"ws-sample-tile ws-sample-blank {tint}", data_sample=label)


def photos_panel(o, d, stay_id):
    area = f"The area · {o.headline}"
    if o.area_photo:
        big = Figure(Img(src=f"{PHOTOS}{o.area_photo}", alt=f"{o.headline}, the neighbourhood (not the hotel)", loading="lazy", width="600", height="400"),
                     Figcaption(area), cls="ws-area-tile")
    else:
        big = Figure(Span(icon("pin", 40), aria_hidden="true"), Figcaption(area), cls="ws-area-tile ws-area-blank")
    tints = ["fill-bubble-tint", "fill-sky-tint", "fill-grape-tint", "fill-mint-tint"]
    tiles = [_sample(label, photo, tints[i % 4]) for i, (label, photo) in enumerate(d.samples)]
    return Div(big, *tiles, cls="ws-photo-grid", role="tabpanel", id=f"pnl-photos-{stay_id}", aria_labelledby=f"tab-photos-{stay_id}", data_panel="photos")


def look_around(o, d):
    sid = o.id
    tabs = Div(
        Button("Photos", type="button", role="tab", id=f"tab-photos-{sid}", aria_selected="true", aria_controls=f"pnl-photos-{sid}", data_tab="photos", cls="ws-tab"),
        Button(icon("pin", 16, 2.4), "Explore the area in 3D", type="button", role="tab", id=f"tab-explore-{sid}", aria_selected="false", tabindex="-1",
               aria_controls=f"pnl-explore-{sid}", data_tab="explore", cls="ws-tab"),
        role="tablist", aria_label="Look around", cls="ws-tabs",
    )
    return Div(
        Div(tabs, near_strip(d), cls="ws-look-head"),
        photos_panel(o, d, sid),
        Div(role="tabpanel", id=f"pnl-explore-{sid}", aria_labelledby=f"tab-explore-{sid}", hidden=True, data_panel="explore", cls="ws-explore-slot",
            data_map_src=f"/plan/explore?h={sid}"),
        cls="ws-look", data_look=sid,
    )


def title_row(o, d):
    chips = list(dict.fromkeys([*o.tags, *d.chips]))
    return Div(
        Div(
            H2(o.name, cls="ws-dtitle"),
            Span(f"{o.headline} · {o.rating}", cls="ws-drating"),
            Div(*[Span(t, cls=f"ws-sticker {CHIP_FILLS[i % 4]}") for i, t in enumerate(chips)], cls="ws-dchips"),
            P(f"{o.headline} · {o.detail}", cls="ws-dlead"),
            cls="ws-dhead",
        ),
        Ul(*[Li(icon("check", 18, 2.6), t) for t in d.highlights], cls="ws-highlights", aria_label="Highlights"),
        cls="ws-titlerow",
    )


def fit_badge(state):
    return Span(state.fit_text, cls=f"ws-fit {FIT_FILL[state.fit]}", data_fit=state.fit, role="status")


def room_card(r, n):
    photo = Img(src=PHOTOS + r.photo, alt="Sample photo of a hotel room (not this room)", loading="lazy", width="300", height="200") if r.photo else icon("bed", 30, 2)
    return Div(
        Div(photo, Span("Sample photo", cls="ws-room-cap"), Span(r.view, cls=f"ws-view{' ws-view-ocean' if r.view.startswith('Ocean') else ''}"),
            cls=f"ws-room-photo {r.tint}"),
        Div(Span(r.name, cls="ws-room-name"), Span(f"{r.beds} · sleeps {r.sleeps}", cls="ws-room-beds"), cls="ws-room-text"),
        Div(
            Span(catalog.money(r.price_cents), cls="ws-room-price"),
            Span(
                Button(icon("minus", 16, 3), type="button", cls="ws-step", aria_label=f"One fewer {r.name}", data_step="-1", disabled=n <= 0),
                Span(str(n), cls="ws-count", aria_live="polite"),
                Button(icon("plus", 16, 3), type="button", cls="ws-step ws-step-more", aria_label=f"One more {r.name}", data_step="1", disabled=n >= catalog.MAX_PER_ROOM),
                cls="ws-stepper",
            ),
            cls="ws-room-foot",
        ),
        cls="ws-room", data_room=r.id, data_count=str(n), data_max=str(catalog.MAX_PER_ROOM), aria_label=r.name,
    )


def rooms_seam(o, d, state):
    counts = state.counts
    return Div(
        Div(H3("Pick your rooms", cls="ws-h3"), Span("Prices are per room for all 4 nights, taxes in", cls="ws-h3-sub"), fit_badge(state), cls="ws-h3-row"),
        Div(*[room_card(r, counts[r.id]) for r in d.rooms], cls="ws-room-grid"),
        cls="ws-rooms",
    )


def addon_pill(a, on):
    return Button(
        Span(icon("check", 16, 3) if on else "", cls="ws-dot", aria_hidden="true"),
        a.name, " ", Span(f"+{catalog.money(a.price_cents)}", cls="ws-addon-price"),
        type="button", cls="ws-addon", data_addon=a.id, aria_pressed="true" if on else "false",
    )


def addons_seam(state):
    return Div(H3("Add-ons", cls="ws-h3"), Div(*[addon_pill(a, a.id in state.addons) for a in catalog.ADDONS], cls="ws-addon-row"), cls="ws-addons")


def policy_seam(d):
    return Div(icon("shield", 20, 2.2), Span(d.policy), cls="ws-policy")


def summary_text(state):
    return state.summary


def body(o, state):
    """The detail panel's scrolling content after the hero, in reading order. `state` is the StayPick shown in the editor."""
    d = catalog.stay_detail(o.id)
    return [
        Div(look_around(o, d), data_seam="look-around", cls="ws-seam"),
        title_row(o, d),
        Div(rooms_seam(o, d, state), data_seam="rooms", cls="ws-seam"),
        Div(Div(addons_seam(state), data_seam="addons", cls="ws-seam"), Div(policy_seam(d), data_seam="policy", cls="ws-seam"), cls="ws-addon-policy"),
    ]


# ---- the lazy 3D explorer ----------------------------------------------------------------------------------------

def _pin(i, p, selected):
    fill, ic, _ = KIND[p.kind]
    label = f"{p.name}, {p.walk}" if p.walk else p.name
    return Button(
        Span(Span(icon(ic, 14, 2.6), cls="ws-pin-ico", aria_hidden="true"), p.label, cls=f"ws-pin-bub {fill}"),
        Span(cls="ws-pin-stem", aria_hidden="true"),
        type="button", cls="ws-pin", style=f"left:{p.x}%;top:{p.y}%", aria_label=label, aria_pressed="true" if selected else "false",
        data_poi=str(i), data_tx=str(50 - p.x), data_ty=str(50 - p.y),
    )


def _poi_card(i, p, selected):
    _, _, kicker = KIND[p.kind]
    return Div(
        Span(kicker + (f" · {p.walk}" if p.walk else ""), cls="ws-poi-kicker"),
        Span(p.name, cls="ws-poi-name"),
        Span(p.note, cls="ws-poi-note"),
        cls=f"ws-poi-card{' ws-poi-home' if p.kind == 'hotel' else ''}", data_poi_card=str(i), **({} if selected else {"hidden": True}),
    )


def _poi_row(i, p, selected):
    fill, _, _ = KIND[p.kind]
    return Button(Span(cls=f"ws-poi-dot {fill}", aria_hidden="true"), Span(p.name, cls="ws-poi-rowname"), Span(p.walk or "Home base", cls="ws-poi-walk"),
                  type="button", cls="ws-poi-row", aria_pressed="true" if selected else "false", data_poi=str(i), data_tx=str(50 - p.x), data_ty=str(50 - p.y))


def explore(stay_id):
    """The explorer fragment: a CSS-3D tilted plane with standing pins, the point list and the selected point's card."""
    o = catalog.offer(stay_id)
    d = catalog.stay_detail(stay_id)
    home = d.pois[0]
    plane = Div(
        Div(cls="ws-streets"),
        Div(cls="ws-sea") if d.coast else "",
        Div(cls="ws-shore") if d.coast else "",
        Div(cls="ws-park"),
        *[_pin(i, p, i == 0) for i, p in enumerate(d.pois)],
        cls="ws-plane",
    )
    aerial = Div(
        plane,
        Span("Illustrated map · not to scale", cls="ws-map-note"),
        Span(
            Button(icon("target", 18, 2.4), type="button", cls="ws-mapbtn", aria_label="Back to the hotel", data_recenter=""),
            Button(icon("rotate", 18, 2.4), type="button", cls="ws-mapbtn", aria_label="Turn the view", data_spin=""),
            cls="ws-mapbtns",
        ),
        cls="ws-aerial", role="group", aria_label=f"Aerial view around {o.name}", data_tx=str(50 - home.x), data_ty=str(50 - home.y), data_spin_deg="0",
    )
    side = Div(*[_poi_card(i, p, i == 0) for i, p in enumerate(d.pois)], *[_poi_row(i, p, i == 0) for i, p in enumerate(d.pois)], cls="ws-poi-side")
    return Div(aerial, side, cls="ws-explore")
