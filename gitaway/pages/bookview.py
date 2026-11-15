"""The drawings and icons the creator pages share (F-253, F-262): the icon set (`ico`), a drawn scene (`drawing`, labelled as an illustration), a kind's tile (`kt`) and the Save heart.
The book that used to live here is retired: a creator's trip is a guide now (gitaway/pages/guideview.py). Honest by construction: a photo is only ever the creator's own pick, labelled; a drawing is labelled "Illustration".
"""

import itertools
from html import escape

from fasthtml.common import Button, Div, NotStr, Span

from gitaway import creatorbook as cb, placeart

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


def heart_button(saved: bool, slug: str, signed: bool) -> Div:
    return Button(ico("heart"), Span("Saved" if saved else "Save", cls="t"), type="button", cls="heartb", id="heartBtn", aria_pressed="true" if saved else "false", data_slug=slug,
                  data_signed="1" if signed else "0", aria_label="Saved. Tap to take it off your saved trips" if saved else "Save this trip")
