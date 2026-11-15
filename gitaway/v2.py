"""The v2 page chrome (F-250, D-610): the sky behind the page (a sun, clouds, the shore), the top bar (the mark, the sample label, the light/dark round button, the account)
and the stylesheets and script a v2 page loads. `layout.page(v2=True)` uses it; a page opts in by that one flag, which puts the class `v2` on its wrapper.
Reference: docs/design/booking-v2/index.html (type pairing C, Newsreader with Inter); the tokens are assets/css/v2-tokens.css."""

from fasthtml.common import A, Button, Div, Link, NotStr, Script, Span

from gitaway import session, showcase
from gitaway.icons import icon

HEAD = (Link(rel="stylesheet", href="/assets/css/v2-tokens.css"), Link(rel="stylesheet", href="/assets/css/v2.css"),
        Link(rel="preload", href="/assets/fonts/inter-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
        Link(rel="preload", href="/assets/fonts/newsreader-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
        Script(src="/assets/js/v2.js", defer=True))

CLOUD = '<path d="M20 44a16 16 0 0 1 2-32 22 22 0 0 1 40-4 18 18 0 0 1 32 10 13 13 0 0 1 6 26z"/>'
MARK = ('<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="12" fill="#4338CA"/><circle cx="26" cy="15" r="6" fill="#FFD43B"/>'
        '<path d="M5 27c5-4 9-4 14 0s9 4 16 0v8a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5z" fill="#fff"/><path d="M5 31c5-3 9-3 14 0s9 3 16 0" fill="none" stroke="#C92A5E" stroke-width="2.5"/></svg>')


def _palm(x, y, s=1.0, c="#1F8A5B", t="#7A4E26") -> str:
    return (f'<g transform="translate({x} {y}) scale({s})"><path d="M0 0 Q2 -14 6 -28" fill="none" stroke="{t}" stroke-width="2.4" stroke-linecap="round"/><g fill="{c}">'
            '<path d="M6 -28q-10-3-15 4 8-3 15-4z"/><path d="M6 -28q10-4 15 3-8-3-15-3z"/><path d="M6 -28q-5-9-13-8 8 2 13 8z"/><path d="M6 -28q4-10 12-9-8 2-12 9z"/></g></g>')


def _shore() -> str:
    """The landing's foot: hills, a sea, a pier, a sailboat, a beach and palms (the cover's scene, redrawn as the prototype draws it)."""
    piles = "".join(f'<rect x="{130 + i * 24}" y="134" width="4" height="40" fill="#2B3A4A"/>' for i in range(16))
    palms = "".join(_palm(x, y, s) for x, y, s in ((1180, 214, 2.1), (1240, 220, 1.6), (1320, 212, 2.4), (70, 222, 1.8)))
    return ('<path d="M0 120 Q160 70 330 110 T700 96 T1060 108 T1440 92 V260 H0Z" fill="#C9B9D9" opacity=".55"/>'
            '<path d="M0 150 Q240 132 480 146 T960 140 T1440 148 V260 H0Z" fill="#A7D3EE"/><path d="M0 176 Q240 160 480 172 T960 166 T1440 174 V260 H0Z" fill="#78B8E3"/>'
            f'<rect x="120" y="128" width="380" height="6" fill="#2B3A4A"/>{piles}<rect x="456" y="104" width="40" height="24" rx="2" fill="#E4572E"/><path d="M450 104h52l-26-14z" fill="#2B3A4A"/>'
            '<path d="M0 214 Q300 190 640 206 T1440 200 V260 H0Z" fill="#F4D9A0"/>' + palms +
            '<g transform="translate(860 150)"><path d="M0 0 h60 l-8 10 h-44z" fill="#C2410C"/><path d="M28 0 V-46 L56 -4z" fill="#FFD43B"/><path d="M26 -2 V-38 L6 -4z" fill="#fff"/></g>')


def bg() -> Div:
    cloud = lambda style: NotStr(f'<svg class="cloud" style="{style}" viewBox="0 0 120 50">{CLOUD}</svg>')      # noqa: E731
    return Div(Div(cls="sunball"), cloud("left:6%;top:9%;width:170px"), cloud("left:58%;top:22%;width:120px;animation-duration:80s"), cloud("left:28%;top:44%;width:200px;animation-duration:95s"),
               NotStr(f'<svg class="shore" viewBox="0 0 1440 260" preserveAspectRatio="xMidYMax slice">{_shore()}</svg>'), cls="v2-bg", aria_hidden="true")


def top() -> Div:
    """The brand, a label saying the prices are samples (on the showcase), the light/dark button and the account: an avatar for a signed-in person, Sign in otherwise."""
    traveler = session.request_traveler()
    account = A(Span(traveler.initials), href="/family", cls="v2-round", aria_label="Your family and who is in it", title=traveler.name) if traveler \
        else A("Sign in", href=session.signin_href(), cls="v2-signin")
    mode = Button(Span(icon("moon", 20), cls="ga-mode-moon"), Span(icon("sun", 20), cls="ga-mode-sun"), type="button", cls="v2-round", id="ga-mode-v2", data_mode_toggle="1",
                  aria_pressed="false", aria_label="Dark mode", title="Dark mode")
    from gitaway.layout import preview      # here: layout imports this module
    return Div(A(NotStr(MARK), "GitAway", href="/", cls="v2-brand", aria_label="GitAway"), preview(), Span(cls="sp"),
               Span("Sample prices", cls="v2-pill") if showcase.on() else "", mode, account, cls="v2-top")
