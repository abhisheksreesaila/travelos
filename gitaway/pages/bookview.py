"""The book, drawn (F-253, D-640..): the scrapbook pages of a creator's trip as HTML, from the data in gitaway/creatorbook.py. Reference: docs/design/creators-v2/index.html.

`faces(book, edit=...)` is the book's pages in order (cover, Before you go, the trip at a glance, a day's two pages for each day, tips, Plan this trip, back cover); `book_markup` is the stage the
script (assets/js/book.js) turns into leaves; the pages are also on the page as plain sections, so the words are there without script, to a search engine and to a screen reader. `mini_cover` is the
cover on the shelf. Honest by construction: a photo is only ever the creator's own pick, labelled; a drawing is labelled "Illustration"; a sentence in quotes is the post's own.
"""

import itertools
from html import escape

from fasthtml.common import A, Aside, B, Blockquote, Button, Cite, Div, Figcaption, Figure, I, Img, Li, NotStr, Ol, P, Pre, Section, Small, Span, Template, H2, H3

from gitaway import blogbutton, creatorbook as cb, placeart

_IDS = itertools.count(1)


def _svg(d, w=2):
    return NotStr(f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>')


ICON = {
    "l": ("M15 5l-7 7 7 7", 2.4), "r": ("M9 5l7 7-7 7", 2.4), "arrow": ("M5 12h14M13 6l6 6-6 6", 2.2),
    "heart": ('<path d="M12 20s-7.5-4.6-9.3-9.2C1.4 7.4 3.6 4 7 4c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.4 0 5.6 3.4 4.3 6.8C19.5 15.4 12 20 12 20z"/>', 2),
    "edit": ('<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>', 2), "check": ("M5 12l5 5 9-10", 3),
    "copy": ('<rect x="8" y="8" width="12" height="12" rx="3"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>', 2),
    "x": ("M6 6l12 12M18 6L6 18", 2.4),
    "shelf": ('<path d="M4 20h16"/><rect x="5" y="5" width="4" height="15" rx="1"/><rect x="10" y="7" width="4" height="13" rx="1"/><path d="M15.5 8.5l3.5-1 3 12.5"/>', 2),
    "share": ('<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>', 2),
    "plan": ('<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>', 2),
    "see": ("M3 21h18M5 21V10M19 21V10M9 21v-7M15 21v-7M3 10l9-6 9 6z", 2),
    "food": ('<path d="M7 3v8a2 2 0 0 0 2 2v8M11 3v8a2 2 0 0 1-2 2M7 3h4"/><path d="M17 21V3c-2 1-3 4-3 8h3"/>', 2),
    "tix": ('<path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4z"/><path d="M14 6v12" stroke-dasharray="2 2"/>', 2),
    "ride": ('<path d="M4 16V9a3 3 0 0 1 3-3h7l4 5h1a2 2 0 0 1 2 2v3"/><circle cx="7.5" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M4 11h14"/>', 2),
    "show": ('<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>', 2),
    "walk": ('<circle cx="13" cy="4" r="2"/><path d="M9 21l3-7 3 3v5M12 14l-1-5 4 2 3 1M11 9l-4 2v3"/>', 2),
    "quote": ("M7 7h4v4c0 3-2 5-4 6M15 7h4v4c0 3-2 5-4 6", 2), "link": ('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>', 2),
}


def ico(name):
    d, w = ICON[name]
    return _svg(d if d.startswith("<") else f'<path d="{d}"/>', w)


def drawing(scene, label="") -> NotStr:
    """A drawn scene as inline SVG: the prototype's (bookart.json), GitAway's own place art, or a plain generic one. `label` names it for a screen reader."""
    kind, key = scene
    if kind == "bookart":
        svg = cb.ART[key].replace("__G__", f"cb{next(_IDS)}")
        return NotStr(svg.replace('aria-hidden="true"', f'role="img" aria-label="{escape(label or "A drawing of the place")}"') if label else svg)
    if kind == "placeart":
        return NotStr(placeart.art(key) or "")
    g = f"cb{next(_IDS)}"
    return NotStr(f'<svg viewBox="0 0 160 100" preserveAspectRatio="xMidYMid slice" role="img" aria-label="{escape(label or "A drawing of a coast and hills")}"><defs><linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="#CFE6F7"/><stop offset="1" stop-color="#FCE1C6"/></linearGradient></defs><rect width="160" height="100" fill="url(#{g})"/><circle cx="124" cy="26" r="11" fill="#FFB547"/>'
                  '<path d="M0 62 Q40 36 84 50 T160 44 V100H0Z" fill="#7BA37E"/><path d="M0 74 Q60 56 160 66 V100H0Z" fill="#5E8F68"/><path d="M0 88 Q80 80 160 88 V100H0Z" fill="#E7D2AE"/></svg>')


def kt(kind, extra=""):
    return Span(ico(kind), cls=f"kt{' dark' if kind == 'ride' else ''} {extra}".strip(), style=f"--k:var(--bk-{kind})")


def foot(left, right):
    return Div(Span(left), Span(str(right)), cls="pg-foot")


def cover(b: cb.Book, mini=False, ed=False) -> Div:
    first, _, rest = b.sticker.partition(" ")
    sticker = (Span(first, NotStr("<br>"), rest, cls="stk") if rest else Span(first, cls="stk")) if b.sticker else ""
    return Div(sticker, Div(drawing(b.scene, f"A drawing of {b.place}, not a photograph"), cls="win"),
               Span(b.title, cls="ed h1" if ed else "h1", **({"data_k": "title"} if ed else {})), Div(f"by {b.by}", cls="by"),
               "" if mini else Div("A GitAway trip book · the cover is an illustration", cls="imprint"),
               Div("Published", Small(b.stamped), cls="stamp") if b.stamped and not mini else "", cls="cover", style=f"--cloth:{b.cloth}")


def mini_cover(b: cb.Book) -> Div:
    return Div(cover(b, mini=True), cls="mini")


def _quote(text, b):
    who = b.by + (" · sample words" if b.sample else ", in the post")
    return Blockquote(text, Cite(who), cls="quote")


def _plate(scene, caption, rot, tape, tc, photo=None):
    pic = Img(src=photo[0], alt=photo[1], referrerpolicy="no-referrer") if photo else drawing(scene)
    return Figure(Span(cls=f"tape {tape}", style=f"--tc:{tc}" if tc else None), Div(pic, cls="pic"), Figcaption(caption, Small("Photo from the post" if photo else "Illustration")),
                  cls="plate", style=f"--r:{rot}deg")


def _wrap(name, width=17, lines=3):
    """A place's name as at most `lines` short lines for the doodle's label: broken between words, never cut inside one."""
    out, line = [], ""
    for word in name.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return (out + [line])[:lines]


def _doodle(b):
    shown = b.days[:6]
    n = len(shown)
    pts = [(46 + (i * 208 // max(n - 1, 1) if n > 1 else 100), 138 - (i % 3) * 48, d.stops[0].name if d.stops else d.head, f"Day {i + 1}") for i, d in enumerate(shown)]
    path = " L".join(f"{x} {y}" for x, y, *_ in pts)
    dots = ""
    for i, (x, y, name, day) in enumerate(pts):
        right = x > 150
        tx, anchor = (x - 18 if right else x + 18), ("end" if right else "start")
        rows = "".join(f'<tspan x="{tx}" dy="{0 if j == 0 else 16}">{escape(t)}</tspan>' for j, t in enumerate(_wrap(name)))
        dots += (f'<circle cx="{x}" cy="{y}" r="12" fill="{["#0F766E", "#4338CA", "#C2410C"][i % 3]}"/><text x="{x}" y="{y + 4.5}" font-size="12" font-style="normal" font-family="Inter" font-weight="700" fill="#fff" '
                 f'text-anchor="middle">{i + 1}</text><text x="{tx}" y="{y - 4}" font-size="15" fill="#2A2420" text-anchor="{anchor}">{rows}</text>'
                 f'<text x="{tx}" y="{y + 12 + 16 * (len(_wrap(name)) - 1)}" font-size="12" fill="#574C42" text-anchor="{anchor}">{day}</text>')
    return NotStr(f'<svg class="doodle" viewBox="0 0 300 190" preserveAspectRatio="xMidYMid meet" role="img" aria-label="A doodle of the trip\'s places in order, not to scale">'
                  f'<path d="M{path}" stroke="#C92A5E" stroke-width="2.5" stroke-dasharray="6 6" fill="none" stroke-linecap="round"/>{dots}</svg>')


def faces(b: cb.Book, ed=False, lead=False) -> list:
    """[(label, markup)] of the book's pages. `ed`: the creator's own book, where a word can be fixed in place. `lead`: the owner may add the post's picture to the Before you go page."""
    out = [("Cover", cover(b, ed=ed))]
    photo = b.photo
    intro = Div(Span("Before you go", cls="eyebrow"),
                _plate(b.scene, f"{b.place}, from the post" if photo else b.place, -2, "tl", "rgb(201 42 94 / .35)", photo),
                _quote(b.quote, b) if b.quote else "",
                Button("Use the post's picture", type="button", cls="tonal", id="useLead") if lead and not photo else "",
                foot(b.title, 1), cls="pg")
    out.append(("Before you go", intro))
    legend = ("A sample book, made up so you can see the shelf." if b.sample else
              [f"Read the whole post at ", A(b.host, href=b.url, target="_blank", rel="noopener", cls="srcl"), ". The map is a doodle, not to scale."] if b.url else "The map is a doodle, not to scale.")
    out.append(("The trip at a glance", Div(
        Span("The trip at a glance", cls="eyebrow"), H3(f"{len(b.days)} day{'s' if len(b.days) != 1 else ''} in {b.place}"), _doodle(b),
        Div(Div(B(str(len(b.days))), Span("day" + ("s" if len(b.days) != 1 else ""))), Div(B(str(b.stops)), Span("stop" + ("s" if b.stops != 1 else ""))), Div(B(str(len(b.tips))), Span("tip" + ("s" if len(b.tips) != 1 else ""))), cls="facts"),
        P(*legend, cls="legend-p") if isinstance(legend, list) else P(legend, cls="legend-p"), foot("", 2), cls="pg")))
    tapes = ("rgb(255 212 59 / .62)", "rgb(45 212 191 / .45)", "rgb(192 132 252 / .45)")
    for i, d in enumerate(b.days):
        dense = " dense" if len(d.stops) > 5 else ""
        out.append((f"Day {i + 1}", Div(
            Span(f"Day {i + 1}", cls="eyebrow"), H2(d.head, cls="ed" if ed else "", **({"data_k": f"d{i}.head"} if ed else {})),
            _plate(d.scene, d.caption or b.place, 1.6 if i % 2 else -1.8, "tr" if i % 2 else "tl", tapes[i % 3]), _quote(d.quote, b) if d.quote else "", foot(b.title, 3 + i * 2), cls="pg")))
        cards = []
        for j, s in enumerate(d.stops):
            sub = [NotStr(f"<em>{escape(s.time)}</em> · ") if s.time else "", cb.KINDS[s.kind]]
            cards.append(Div(Span(cls="tape tc", style=f"--tc:{['rgb(255 212 59 / .6)', 'rgb(201 42 94 / .3)', 'rgb(67 56 202 / .28)'][j % 3]}") if j % 3 == 0 else "", kt(s.kind),
                             Span(s.name, cls="nm ed" if ed else "nm", **({"data_k": f"d{i}.s{j}"} if ed else {})), Span(*sub, cls="sub"), Span(s.note, cls="note") if s.note else "",
                             cls="sc", style=f"--r:{[-.8, .7, -.4, .9, -.6, .5, -.9][j % 7]}deg;--k:var(--bk-{s.kind})"))
        out.append((f"Day {i + 1}", Div(Span(f"Day {i + 1} · {len(d.stops)} stop{'s' if len(d.stops) != 1 else ''}", cls="eyebrow"), Div(*cards, cls="stops"),
                                        foot("Sample stops" if b.sample else "Times only where the post gives one", 4 + i * 2), cls=f"pg{dense}")))
    out.append(("Tips", Div(
        Span("Tips from the book" if b.sample else "Tips from the post", cls="eyebrow"), H3("Before you book"),
        Div(Span(cls="tape tc"), Ol(*[Li(t) for t in b.tips]), cls="notepad") if b.tips else P("The post gave no tips.", cls="legend-p"),
        P("Sample words." if b.sample else "Each one drawn from the post and checked by its creator.", cls="legend-p"), foot(b.title, 3 + len(b.days) * 2), cls="pg")))
    out.append(("Plan this trip", Div(
        Span("Your turn", cls="eyebrow"), H3("Take this trip"),
        Div(Div(cover(b, mini=True), cls="mini", style="width:44%"), A("Plan this trip", ico("arrow"), href=cb.plan_href(b.place), cls="go paper", data_act="plan"),
            P("Opens booking with this place. Change anything there."), cls="plan-cta"), foot("", 4 + len(b.days) * 2), cls="pg")))
    out.append(("Back cover", Div(NotStr('<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="12" fill="#F6E7C1"/><circle cx="26" cy="15" r="6" fill="#FFD43B"/>'
                                         '<path d="M5 27c5-4 9-4 14 0s9 4 16 0v8a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5z" fill="#fff"/></svg>'),
                                  P("A sample book, made up so you can see the shelf." if b.sample else f"Made with GitAway from {b.by}'s post. Drawings are illustrations" + ("; the photo is the post's own." if b.photo else ".")),
                                  cls="backc", style=f"--cloth:{b.cloth}")))
    return out


def stage(b: cb.Book, ed=False, lead=False) -> Div:
    """The book itself: `#pgs` holds every page as a plain section (what a reader without script sees, and what the script turns into leaves), `#book` is where the leaves go."""
    pages = faces(b, ed, lead)
    return Div(Div(Div(id="book", cls="book"), id="bookWrap", cls="book-wrap"), id="stage3d", cls="stage3d"), \
        Div(*[Section(page, cls="pf", data_lbl=label, aria_label=label) for label, page in pages], id="pgs", cls="pgs")


def heart_button(saved: bool, slug: str, signed: bool) -> Div:
    return Button(ico("heart"), Span("Saved" if saved else "Save", cls="t"), type="button", cls="heartb", id="heartBtn", aria_pressed="true" if saved else "false", data_slug=slug,
                  data_signed="1" if signed else "0", aria_label="Saved. Tap to take it off your saved trips" if saved else "Save this trip")


def share_templates() -> Template:
    """The share panel's text, filled by the script from the publish answer."""
    return Template(Div(Span(I(), "Published", cls="kicker"), H2("Your book is out"), P("Families can flip through it, save it and plan the trip from any page.", cls="sh-lede"),
                          Div(H3("Its link"), Div(Span(id="shLink", cls="linkout"), Button(ico("copy"), "Copy", type="button", cls="tonal", data_copy="link"), cls="linkrow"), cls="sh-sec"),
                          Div(H3("A badge for your post"), Div(Img(src=blogbutton.LIGHT, alt=blogbutton.ALT, width="248", height="56"), cls="badge-pic"), Pre("", id="shCode", cls="code"),
                              Button(ico("copy"), "Copy the code", type="button", cls="tonal", data_copy="code"), cls="sh-sec"),
                          Div(A(ico("shelf"), "See it on the shelf", href="/community", cls="go"), cls="sh-foot"), P("", id="shFine", cls="sh-fine")), id="t-share")


def book_markup(b: cb.Book, *, mode: str, owner_state: dict | None = None, saved=False, signed=False, lead=False) -> list:
    """The page's content. mode "creator" (the owner's draft or live book: Edit, Publish) or "reader" (Save, Plan this trip)."""
    creator = mode == "creator"
    st = owner_state or {}
    if creator:
        top = [Span(I(), "Published", Span(f" · {st.get('where', '')}", cls="long") if st.get("where") else "", cls="tag live") if st.get("live")
               else Span(I(), "Draft · only you can see it", cls="tag"),
               Span("Tap any underlined word to fix it", Button("Done", type="button", id="editDone"), cls="hint")]
        left = Button(ico("edit"), Span("Edit", cls="t"), type="button", cls="tonal", id="editBtn", aria_label="Edit the book", aria_pressed="false")
        right = (Button(ico("share"), Span("Share", cls="t"), type="button", cls="go", id="shareBtn", aria_label="Share") if st.get("live") else Button("Publish", type="button", cls="go", id="pubBtn"))
    else:
        top = [A(ico("l"), Span("Shelf", cls="t"), href="/community", cls="tonal"),
               Span("Sample book", Span(": made up so you can see the shelf", cls="long2"), cls="smp") if b.sample else Span(I(), f"From {b.host}" if b.host else "A creator's trip", cls="tag live")]
        left = heart_button(saved, b.slug, signed)
        right = A(ico("plan"), Span("Plan this trip", cls="t"), Span("Plan", cls="ph"), href=cb.plan_href(b.place), cls="go", id="planBtn")
    pager = Div(Button(ico("l"), type="button", id="prev", aria_label="Previous page"), Div(id="pageLbl", cls="lbl", aria_live="polite"), Button(ico("r"), type="button", id="next", aria_label="Next page"), cls="pager")
    return [Section(Div(*top, id="bookTop", cls="book-top"), *stage(b, ed=creator, lead=lead and creator),
                    Div(Div(left, id="barL", cls="l"), pager, Div(right, id="barR", cls="r"), id="bbar", cls="bbar"),
                    P("Use ← and → to turn pages", id="kbd", cls="kbd"), Aside(id="sharep", cls="sharep v2-glass", hidden=True, aria_label="Share your book"), id="bookv", cls="bookv",
                    data_mode=mode, data_slug=b.slug, data_title=b.title, data_days=str(len(b.days)), data_stops=str(b.stops), data_by=b.by, data_host=b.host, data_live="1" if st.get("live") else "0",
                    data_post=st.get("post", ""), data_auto="1" if st.get("auto") else "0"),
            share_templates() if creator else "", Div(id="scrim", cls="scrim"), Div(id="sheet", cls="sheet", role="dialog", aria_modal="true", hidden=True), Div(id="toast", cls="toast", role="status")]
