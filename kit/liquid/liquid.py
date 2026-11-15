"""Optional FastHTML helpers for the liquid kit (F-264). Nothing here is needed: the kit is plain CSS, JS and HTML, and index.html shows every class. These only save typing.

    from liquid import page_shell, sky, top_bar, sheet, glass_card, card

    @rt("/")
    def get():
        return page_shell(
            top_bar([("home", "Home", "/"), ("docs", "Docs", "/docs")], "home", {"initials": "AB", "name": "Ada Byron", "items": [("Settings", "/settings")], "signout": "/signout"}),
            Main(glass_card(H2("Hello")), card(P("Words people read sit on a card.")), cls="lq-main"),
            title="My site", mood="hills")

`base` is where you serve the kit's files (liquid.css, liquid.js, fonts/): in fh-saas, `app.static_route_exts` or a `StaticFiles` mount at "/liquid". Rules: glass only over the sky, a quiet sky
behind reading, kind colours only for kinds, 4.5:1, 48px targets, durations only from the tokens (README.md)."""

from fasthtml.common import A, Body, Button, Div, Form, Link, Meta, NotStr, Nav, Script, Span, Title

MOODS = ("shore", "snow", "hills", "party", "city")

# Runs in the head before the first paint: the remembered (or the system's) mode is on <html> at once, so a dark page never flashes light.
MODE_INIT = "try{var m=localStorage.getItem('lq-mode')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.setAttribute('data-mode',m)}catch(e){}"

SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'


def head(base: str = "/liquid") -> tuple:
    """The links and scripts a page needs: the stylesheet, the fonts' preload, the mode script (head, before paint) and liquid.js."""
    return (Link(rel="stylesheet", href=f"{base}/liquid.css"),
            Link(rel="preload", href=f"{base}/fonts/inter-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
            Link(rel="preload", href=f"{base}/fonts/newsreader-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
            Script(MODE_INIT), Script(src=f"{base}/liquid.js", defer=True))


def sky(mood: str = "shore", quiet: bool = False) -> Div:
    """The sky behind the page. `quiet=True` is the reading sky (no objects): use it behind anything people read. liquid.js draws the sun, moon, clouds and the mood's one object."""
    mood = mood if mood in MOODS else "shore"
    return Div(cls="lq-sky is-quiet" if quiet else "lq-sky", data_mood=mood, aria_hidden="true")


def glass_card(*content, **kw) -> Div:
    """A small widget of restrained frosted glass. Only directly over the sky: never over another card, never under a paragraph."""
    return Div(*content, cls=f"lq-card lq-glass {kw.pop('cls', '')}".strip(), **kw)


def card(*content, **kw) -> Div:
    """A near-opaque card: where words people read sit."""
    return Div(*content, cls=f"lq-card {kw.pop('cls', '')}".strip(), **kw)


def top_bar(sections: list, current: str = "", account: dict | None = None, brand=("Liquid", "/")) -> Div:
    """The top: brand, the sections pill (top on a laptop, floating at the foot of a phone), the light/dark button and the account.
    `sections` is [(key, label, href)]; `account` is {"initials", "name", "items": [(label, href)], "signout": url} or None."""
    pill = Nav(*[A(label, href=href, aria_current="page" if key == current else None) for key, label, href in sections], cls="lq-sections lq-glass", aria_label="Sections")
    mode = Button(Span(NotStr(MOON), cls="is-moon"), Span(NotStr(SUN), cls="is-sun"), type="button", cls="lq-round", data_lq_mode="1", aria_pressed="false", aria_label="Dark mode", title="Dark mode")
    parts = [A(brand[0], href=brand[1], cls="lq-brand"), Span(cls="sp"), pill, Span(cls="sp"), mode]
    if account:
        menu = Div(*[A(label, href=href, role="menuitem", tabindex="-1") for label, href in account.get("items", [])],
                   Form(Button("Sign out", type="submit", role="menuitem", tabindex="-1"), action=account.get("signout", "/signout"), method="post"),
                   id="lq-menu", cls="lq-menu lq-glass", role="menu", aria_label="Account", hidden=True)
        parts.append(Div(Button(Span(account["initials"]), type="button", cls="lq-round", data_lq_menu="1", aria_haspopup="menu", aria_expanded="false", aria_controls="lq-menu",
                                aria_label=f"{account['name']}: account menu", title=account["name"]), menu, cls="lq-account"))
    return Div(*parts, cls="lq-top")


def sheet(id: str, title: str, *content, drawer: bool = False) -> Div:
    """A sheet (a bottom sheet on a phone, a centred dialog on a laptop) or, with drawer=True, a panel at the right edge of a laptop. Open it with a button carrying data-lq-sheet="<id>"."""
    close = Button(NotStr('<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15"/></svg>'),
                   type="button", cls="lq-round", data_lq_close="1", aria_label="Close")
    return Div(Div(Span(title, cls="lq-display", style="font-size:1.625rem"), close, cls="lq-sheet-h"), *content, id=id, cls="lq-sheet is-drawer" if drawer else "lq-sheet", hidden=True, aria_label=title)


def page_shell(*content, title: str = "", mood: str = "shore", quiet: bool = False, base: str = "/liquid") -> tuple:
    """A whole page: head (title, viewport, the kit), the sky, then your content, all in <body class="lq">. Return it from a route. Put top_bar(...) first in `content`."""
    return (Title(title), Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"), *head(base), Body(sky(mood, quiet), *content, cls="lq"))
