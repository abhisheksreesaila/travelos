"""The guide page, drawn (F-262, D-710..): the prototype's run sheet (docs/design/guides-v2/index.html) of a creator's trip, from the data in gitaway/guide.py.

At-a-glance tiles (only what the guide knows), a sticky day strip, and for each day a time rail of stop cards: the time in the post's words (the stop's number when the post gives none), its kind, the
creator's one line about it, a cost only if their sentence says one, a Tip badge only if one of their tips names the stop, and their own link labelled as theirs. A card opens its details: a side panel
beside the sheet on a laptop, a sheet over it on a phone (assets/js/guide.js), with the creator's words, the facts, the tip, and their link with "GitAway adds nothing to the price". Without script every
card shows its details under it. Honest by construction: a drawing is labelled "Illustration" and a photo is only ever the creator's own pick.
Reader: Plan this trip, Add to my plan, Save. Owner (the draft, or their live guide): fix a word in place, edit the details, Publish.
"""

from urllib.parse import quote

from fasthtml.common import A, Aside, Blockquote, Button, Div, H1, H2, H3, I, Img, Li, Link, Ol, P, Pre, Script, Section, Small, Span, Template

from gitaway import guide as gd
from gitaway.icons import icon
from gitaway.itinerary_view import _from_gitaway
from gitaway.pages import bookview

HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/guides.css"),
        Script("document.documentElement.classList.add('g-js')"), Script(src="/assets/js/guide.js", defer=True))
KIND_ICON = {"see": "see", "food": "food", "tix": "tix", "ride": "ride", "show": "show", "walk": "walk"}
ADD_NOTE = {"signin": "Sign in to add this to your plan.", "trip": "You need a trip first: add stops to its calendar from here.", "viewer": "Only editors of the family can change its plan."}


def kt(kind: str) -> Span:
    return Span(bookview.ico(KIND_ICON[kind]), cls=f"kt{' dark' if kind == 'ride' else ''}", style=f"--k:var(--bk-{kind})", aria_hidden="true")


def tile(t: gd.Tile):
    box = Div(icon(t.icon, 22, 2), Small(t.label), Span(t.value, cls="gl-v"), Span(t.by, cls="src-by") if t.by else "", Span(t.sub, cls="gl-s") if t.sub else "", cls="gl")
    if not t.href:
        return box
    return A(box, href=_from_gitaway(t.href), rel="noopener", referrerpolicy="origin", target="_blank", cls="src-link")      # the origin, not the page: the creator sees GitAway traffic (F-196)


def maps_href(stop: gd.GStop, place: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(f'{stop.name}, {place}')}"


def details(g: gd.Guide, s: gd.GStop) -> Div:
    """What a stop's panel says: the creator's words, when and what it costs (only if they said), their tip, where, and their own link. Moved into the panel by the script; inline without it."""
    facts = [Div(Small("When"), Span(s.time), cls="g-fact") if s.time else "", Div(Small("Cost"), Span(s.cost), cls="g-fact") if s.cost else ""]
    return Div(
        Blockquote(Small(bookview.ico("quote"), f"In {g.poss} words" if not g.sample else "In the sample creator's words"), P(s.why), cls="g-words") if s.why else "",
        P(s.note, cls="g-extra") if s.note else "",
        Div(*[f for f in facts if f], cls="g-facts") if any(facts) else "",
        Div(Span(icon("spark", 18, 2), cls="g-ti"), Small(f"{g.Poss} tip"), P(s.tip), cls="g-tipbox") if s.tip else "",
        Div(icon("pin", 20, 2), Div(Small("Where"), Span(f"{s.name}, {g.place}")), A("Maps", href=maps_href(s, g.place), target="_blank", rel="noopener noreferrer", cls="g-maps"), cls="g-where"),
        Div(Small(f"{g.Poss} link"), A(bookview.ico("link"), f"{g.Poss} link", Span(s.link_host, cls="g-host") if s.link_host else "", href=s.link, target="_blank", rel="sponsored noopener", cls="g-linkrow"),
            P("This is the creator's own link. GitAway adds nothing to the price.", cls="g-fine"), cls="g-link") if s.link else "",
        cls="g-more")


def inplace_details(g: gd.Guide, s: gd.GStop, ident: str, add: str) -> Div:
    """A stop's details opening in place, inside the card (F-263: in a sheet there is no second sheet): the same details, in a box that folds open under the stop, with Add to my plan when the
    person can (the sheet over planning). Folded, it is out of the reading order and the tab order (`inert`) until the card opens."""
    adder = Button(icon("plus", 20, 2.4), "Add to my plan", type="button", cls="go", data_add=s.key) if add == "yes" else ""
    return Div(Div(details(g, s), adder, cls="g-fold"), cls="g-inplace", id=ident, inert=True)


def stop_li(g: gd.Guide, s: gd.GStop, last: bool, owner: bool, add: str, inplace: bool = False) -> Li:
    badges = [Span(s.cost, cls="bdg cost") if s.cost else "", Span(icon("spark", 14, 2.2), "Tip", cls="bdg tip") if s.tip else "",
              A(bookview.ico("link"), f"{g.Poss} link", href=s.link, target="_blank", rel="sponsored noopener", cls="bdg lnk", aria_label=f"{g.Poss} link for {s.name}, opens their site") if s.link else ""]
    name = Span(s.name, cls="ed", data_k=f"d{s.day - 1}.s{s.n - 1}", title="Tap to fix the name") if owner else Span(s.name, cls="g-nm")
    more = f"gm-{s.key}"
    cover = "" if owner else Button(Span(f"Open {s.name}", cls="v2-sr"), type="button", cls="g-open g-cover", aria_expanded="false", aria_controls=more if inplace else "g-panel", data_k=s.key)      # the whole card is the press
    sub = " · ".join(x for x in (s.label, f"stop {s.n} of {s.of}") if x)
    side = [Button(icon("plus", 20, 2.4), type="button", cls="g-plus", data_add=s.key, aria_label=f"Add {s.name} to my plan") if add == "yes" else "",
            Button(icon("chev-right", 20, 2.2), type="button", cls="g-open g-chev", aria_expanded="false", aria_controls="g-panel", data_k=s.key, aria_label=f"Open {s.name}") if owner else Span(icon("chev-right", 20, 2.2), cls="g-chev", aria_hidden="true")]
    return Li(
        Div(Span(s.time or str(s.n), cls="g-tmv"), cls="g-tm"), Div(I(), cls="g-ln"),
        Div(cover, kt(s.kind), Div(name, Span(sub, cls="sub"), P(s.why, cls="g-why") if s.why else "", Div(*[b for b in badges if b], cls="g-badges") if any(badges) else "", inplace_details(g, s, more, add) if inplace else details(g, s), cls="g-t"),
            Div(*[x for x in side if x], cls="g-side"),
            cls="g-card", data_k=s.key, data_name=s.name, data_kind=s.kind, data_label=s.label, data_day=str(s.day), data_n=str(s.n), data_of=str(s.of)),
        cls="g-stop" + (" last" if last else ""), style=f"--k:var(--bk-{s.kind})", id=f"g-{s.key}")


def day_section(g: gd.Guide, d: gd.GDay, owner: bool, add: str, inplace: bool = False) -> Section:
    n = len(d.stops)
    head = Span(d.title, cls="ed", data_k=f"d{d.n - 1}.head") if owner else d.title
    return Section(Div(Span(f"Day {d.n}", cls="g-eyebrow"), H2(head), P(f"{n} stop{'s' if n != 1 else ''}" + (f" · {d.note}" if d.note else ""), cls="g-dsub"), cls="g-dh"),
                   Ol(*[stop_li(g, s, i == n - 1, owner, add, inplace) for i, s in enumerate(d.stops)], cls="g-rail"), cls="g-day", id=f"g-day{d.n}", data_day=str(d.n), aria_label=f"Day {d.n}: {d.title}")


def strip(g: gd.Guide) -> Div:
    """The sticky day strip: each day's number, its title and a line of its stops' kinds (the colour timeline: colour is for kinds only). A button scrolls to its day."""
    return Div(*[Button(Span(f"Day {d.n}", cls="dn"), Span(d.title, cls="dt"), Span(*[I(style=f"left:{(100 * (i + .5) / len(d.kinds)):.1f}%;--k:var(--bk-{k})") for i, k in enumerate(d.kinds)], cls="tl", aria_hidden="true"),
                        type="button", cls="dbtn", aria_pressed="true" if d.n == 1 else "false", data_day=str(d.n)) for d in g.days],
               cls="g-strip v2-glass", role="group", aria_label="Days", style=f"--nd:{len(g.days)}")


def art(g: gd.Guide, short: bool = False) -> Div:
    """The guide's picture: the creator's own photo or a drawing, each said so. `short` (the sheet's small picture) says it in one word."""
    if g.photo:
        return Div(Img(src=g.photo[0], alt=g.photo[1], referrerpolicy="no-referrer"), Span("Photo" if short else "Photo from the post", cls="g-cap"), cls="g-art")
    return Div(bookview.drawing(g.scene, f"A drawing of {g.place}, not a photograph"), Span("Drawing" if short else "Illustration", cls="g-cap"), cls="g-art")


def panel() -> Aside:
    return Aside(Div(Div(Span(cls="g-pk"), Span(cls="g-po"), Span(cls="sp"), Button(icon("up", 20, 2.4), type="button", cls="v2-round", id="g-prev", aria_label="Previous stop"),
                         Button(icon("up", 20, 2.4), type="button", cls="v2-round down", id="g-next", aria_label="Next stop"), Button(icon("x", 20, 2.4), type="button", cls="v2-round", id="g-close", aria_label="Close"),
                         cls="g-pt"), Div(id="g-pbody", cls="g-pbody"), Div(id="g-pact", cls="g-pact"), cls="g-pin"),
                 id="g-panel", cls="g-panel", role="complementary", aria_label="Stop details", hidden=True)


def _actions(g: gd.Guide, mode: str, state: dict) -> Div:
    add = state.get("add", "no")
    plan = A(icon("target", 20, 2.2), "Plan this trip", href=gd.plan_href(g.place, g.nights), cls="go", id="g-plan", data_plan="1")
    if mode == "owner":
        return Div(A(icon("pencil", 20, 2.2), "Edit details", href=state["editor"], cls="tonal", id="detailsBtn"), cls="g-act")
    heart = bookview.heart_button(state.get("saved", False), g.slug, state.get("signed", False))
    share = Button(icon("share", 20, 2.2), type="button", cls="v2-round", id="g-share", aria_label="Copy this guide's link", title="Copy link")
    if add == "yes":
        adder = Button(icon("plus", 20, 2.4), "Add to my plan", type="button", cls="tonal", id="g-add", data_add="day")
    elif add == "signin":
        adder = A(icon("plus", 20, 2.4), "Add to my plan", href=state["signin"], cls="tonal", id="g-add")
    elif add == "trip":
        adder = A(icon("plus", 20, 2.4), "Add to my plan", href=state["start"], cls="tonal", id="g-add")
    else:
        adder = ""
    return Div(plan, adder, Div(heart, share, cls="g-round"), P(ADD_NOTE[add], cls="g-note", id="g-note") if add in ADD_NOTE else "", cls="g-act")


def owner_bar(g: gd.Guide, state: dict) -> Div:
    """The creator's own bar: what state the guide is in, what stays private, Edit details and Publish."""
    live = state.get("live")
    tag = (Span(I(), "Published", Span(f" · {state['where']}", cls="long") if state.get("where") else "", cls="tag live") if live else Span(I(), "Draft · only you can see it", cls="tag"))
    private = (Span(icon("lock", 16, 2.2), f"{len(g.private)} booking{'s' if len(g.private) != 1 else ''} kept private", cls="g-priv", title="Your flights and stays are never published", id="g-priv")
               if g.private else "")
    publish = (Button(icon("share", 20, 2.2), "Share", type="button", cls="go", id="shareBtn", aria_label="Share") if live else Button("Publish", type="button", cls="go", id="pubBtn"))
    return Div(tag, private, Span("Tap any underlined word to fix it", cls="g-hint"), Div(publish, cls="g-pub"), cls="g-own", id="bookTop")


def share_template() -> Template:
    """The share panel's text, filled by the script from the publish answer: the guide's link, the Instagram card, the blog badge."""
    from gitaway import blogbutton
    return Template(Div(Span(I(), "Published", cls="kicker"), H2("Your guide is out"), P("People can read it, save it, add its stops to their plan and plan the trip from it.", cls="sh-lede"),
                        Div(H3("Its link"), Div(Span(id="shLink", cls="linkout"), Button(bookview.ico("copy"), "Copy", type="button", cls="tonal", data_copy="link"), cls="linkrow"), cls="sh-sec"),
                        Div(H3("For Instagram"), Img(src="", alt="The guide's card for Instagram: its title, its place and its length", id="shCard", cls="g-card-img", width="270", height="338"),
                            Div(A(bookview.ico("share"), "Download the card", href="#", id="shDown", cls="tonal", download="guide-card.png"), Button(bookview.ico("share"), "Share", type="button", cls="tonal", id="shNative", hidden=True), cls="sh-foot g-left"),
                            cls="sh-sec sh-ig"),
                        Div(H3("A badge for your post"), Div(Img(src=blogbutton.LIGHT, alt=blogbutton.ALT, width="248", height="56"), cls="badge-pic"), Pre("", id="shCode", cls="code"),
                            Button(bookview.ico("copy"), "Copy the code", type="button", cls="tonal", data_copy="code"), cls="sh-sec"),
                        Div(A(bookview.ico("shelf"), "See it in Guides", href="/guides", cls="go"), cls="sh-foot"), P("", id="shFine", cls="sh-fine")), id="t-share")


def trust(g: gd.Guide, st: dict) -> Div:
    """What is true about the money and the words, in plain sentences (F-184, F-185, F-196): who earns from Plan this trip (affiliate.earning_line, the one place those words live), that a stop's link is the
    creator's own and may earn them a commission and that GitAway adds nothing to its price, and Report this trip for a guide that is live."""
    from gitaway import affiliate      # here: affiliate reads the community database
    if g.sample:
        return Div(P("A sample guide: the people and prices in it are made up so you can see how it reads.", cls="g-disclose"), cls="g-trust")
    own = f"{g.author}'s" if g.author else g.poss
    has_links = any(s.link for d in g.days for s in d.stops)
    return Div(P(f"The words, the times and the links are {g.poss} own. GitAway adds nothing to the price of their links.", cls="g-disclose"),
               P(affiliate.earning_line(g.author, False, bool(st.get("plannable", True))), id="who-earns", cls="g-disclose"),
               P(f"Links on a stop are {own} own. They may earn them a commission.", id="own-links", cls="g-disclose") if has_links else "",
               A(icon("flag", 18, 2.2), "Report this guide", href=f"/report?trip={g.slug}", cls="tonal", id="report-this") if st.get("report") else "", cls="g-trust")


def kicker(g: gd.Guide) -> Div:
    sample = Span("Sample guide", Span(": made up so you can see the guides", cls="long2"), cls="smp") if g.sample else ""
    return Div(Span(f"{g.place} · Guide", cls="g-kick"), sample, cls="g-kr")


def byline(g: gd.Guide) -> Div:
    return Div(Span((g.author or g.by)[:1].upper() or "?", cls="g-av", aria_hidden="true"), (A(f"By {g.author or g.by}", href=f"/creators/{g.handle}", cls="by g-by") if g.handle else Span(f"By {g.author or g.by}", cls="g-by")),
               Span(f"Published {g.stamped}", cls="g-host2") if g.stamped else "", cls="g-byline")


def guide_markup(g: gd.Guide, *, mode: str, state: dict | None = None):
    """The page's content. mode "reader" (Plan this trip, Add to my plan, Save) or "owner" (their draft or live guide: fix a word in place, Edit details, Publish)."""
    st = state or {}
    owner = mode == "owner"
    add = st.get("add", "no") if not owner else "no"
    head = Div(art(g), Div(kicker(g), H1(Span(g.title, cls="ed", data_k="title") if owner else g.title), byline(g), cls="g-hmain"), _actions(g, mode, {**st, "add": add}), cls="g-head")
    back = A(icon("chev-left", 18, 2.4), "Guides", href="/guides", cls="g-back")
    privates = (Div(icon("lock", 18, 2.2), Div(Small("Kept private, never published"), Span(" · ".join(f"{p[1]}" for p in g.private[:6]))), cls="g-private", role="note") if owner and g.private else "")
    days = [day_section(g, d, owner, add) for d in g.days]
    disclose = trust(g, st)
    main = Div(back, head, owner_bar(g, st) if owner else "", privates, Div(*[tile(t) for t in g.tiles], cls="g-tiles"), strip(g), *days, disclose, cls="g-main")
    return [Section(main, panel(), cls="gpage", id="gpage", data_slug=g.slug, data_mode=mode, data_can=add, data_place=g.place, data_plan=gd.plan_href(g.place, g.nights), data_title=g.title,
                    data_days=str(len(g.days)), data_stops=str(g.stops), data_by=g.by, data_host=g.host, data_live="1" if st.get("live") else "0", data_first=g.first, data_post=st.get("post", ""), data_sample="1" if g.sample else "0", data_signed="1" if st.get("signed") else "0"),
            share_template() if owner else "", Div(id="scrim", cls="scrim"), Div(id="sheet", cls="sheet", role="dialog", aria_modal="true", hidden=True), Div(id="toast", cls="toast", role="status", aria_live="polite"),
            Aside(id="sharep", cls="sharep v2-glass", hidden=True, aria_label="Share your guide")]
