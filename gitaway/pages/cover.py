"""The cover (F-266, cover v3 "one postcard": docs/briefs/cover-v3.md, the approved prototype docs/design/cover-v3/postcard.html, drawn in the Stage look by F-296, docs/design/palette-bo/cover.html): what a signed-out visitor sees at /.

One postcard travels the whole story. It starts as a wish (the search), becomes the matrix (compare), the opened square (book), the calendar (plan together), the trip
itself (go), the guide (share), the Instagram post, and someone else's wish (pass it on), then round again. Eight beats on one sticky stage:

    the card         one card that reshapes between beats; its eight faces crossfade (no turning: the founder found a turning card dizzy)
    the words        a bold caption per beat, rolling with the story (the real text of the story: every caption is in the page)
    the ring         eight bold words (Wish, Compare, Book ...) round the card, turning one word per beat
    the gallery      other families' postcards drifting nearer, one step per beat
    the stage        an Apple-grey ground (F-296, the Stage look); on Go a fine snow drifts across it; light and dark follow the site's mode (assets/js/mode.js)
    the close        "Go somewhere, together.", Start a trip and Browse postcards

The first face is a real form (D-761: visitors search without an account): the visitor types a wish and "Show me every way" posts `q` to POST /plan/ask, which opens their own
matrix. The sample sentence is the placeholder. Nothing here is autofocused.

No jitter by construction (D-427, kept): the stage is CSS sticky and assets/js/cover.js only watches eight markers with an IntersectionObserver and sets attributes and one
custom property (the beat); the ring, the gallery and the card's sizes are CSS (calc, sin, cos, mod). No scroll handler, no requestAnimationFrame, no layout read, no
transform from script (tests/test_cover.py reads the script). Under reduced motion, with ?still, without the script or on a screen under 560 px tall, every beat is a still
card with its words under it.

Every face is drawn here as HTML (aria-hidden decoration; the captions are the text alternative). The families, places, prices and counts on the faces are made up and say so
(D-270, D-383, D-429).
"""

import math
from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, Button, Div, Em, Footer, Form, H1, H2, Header, Li, Link, Main, Nav, NotStr, Ol, P, Script, Section, Span, Textarea, Title

from gitaway import session
from gitaway.icons import icon
from gitaway.layout import NAV, brand, plan_href, preview, seo_meta, styles
from gitaway.pages import coverwhy

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Every trip starts as a wish"
LEDE = "Say it the way you'd tell a friend. GitAway turns one sentence into every way to go, then plans it with your people and passes it on as a postcard."
OG_IMAGE = "/assets/cover/og.jpg"
ASK = "/plan/ask"
LABEL = "Where would you like to go? Say it the way you'd tell a friend."
SAMPLE_WISH = "Somewhere warm, then snow, for 4 of us, mid-December."
DISCLOSURE = "Every family, place, price, temperature and count on this page is made up, to show how it works."

# the eight beats: (the word on the ring, the caption's label, its headline, its soft words, what it says)
BEATS = (
    ("Wish", "GitAway · one trip, passed along", "Every trip starts as", "a wish.",
     "Say it the way you'd tell a friend. GitAway turns one sentence into every way to go."),
    ("Compare", "Compare", "Every way to go,", "on one card.",
     "Places down, days across. Each square is the whole trip for four: flights, stays, one total. The best one lights up."),
    ("Book", "Book", "Tap a square.", "That's the trip.", "The flight, both stays and the sky, in one view. Book it in one go."),
    ("Plan", "Plan", "Everyone", "gets a pen.",
     "Your people add the zoo, the tacos, the sled hill to one calendar. A creator's postcard adds the tip that saves a morning."),
    ("Go", "Go", "Then you", "just go.", "Beach on day one, snow by day four. The plan, the weather and the bookings ride along."),
    ("Share", "Share", "Every traveller", "becomes a creator.", "Your trip comes home as a postcard: your days, your tips, your words. Nothing invented; prices and bookings stay private."),
    ("Post", "Post", "Give it", "to the world.", "One card for Instagram, one link back to the whole trip."),
    ("Pass it on", "Pass it on", "And someone else's", "trip begins.",
     "The Riveras in Austin made it theirs in one tap, and every postcard brings the next traveller."),
)

# other families' postcards in the gallery: (what it says, its gradient)
PLACES = ("Lisbon in 48 hours", "Tahoe ski week", "Kyoto in autumn", "Maui with toddlers", "New York at New Year", "Banff by train", "Mexico City, to eat", "Iceland ring road",
          "Amalfi, slowly", "Zion and Bryce", "Paris for four", "Big Sur drive", "Austin long weekend", "Vancouver Island", "Charleston food trip", "Oaxaca for Day of the Dead")
HUES = tuple(f"var(--pl-{n})" for n in ("sd", "la", "lt", "pink", "teal", "sun"))      # saturated colour cards: the places' own colours (cover.css)

# the drawings the faces share (ART: San Diego's coast and Big Bear's snow; WISH: a harbour at morning), drawn once in a hidden sprite and used by <use>
SPRITE = (
    '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
    '<g id="cv-art" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="118" cy="110" r="28"/><circle cx="118" cy="110" r="42" stroke-opacity=".4"/>'
    '<path d="M210 176 L292 70 L374 176Z"/><path d="M292 70 L274 94 L284 90 L292 102 L302 88 L312 96Z"/><path d="M300 176 L352 112 L410 176" stroke-opacity=".7"/>'
    '<path d="M0 168 Q60 158 120 166 T240 166 L250 260 H0Z" fill="#000" fill-opacity=".1" stroke="none"/>'
    '<path d="M0 214 Q80 200 160 210 T260 206 L262 260 H0Z" fill="#000" fill-opacity=".18" stroke="none"/><path d="M226 200 Q300 182 400 192 V260 H232Z" fill="#fff" fill-opacity=".28" stroke="none"/>'
    '<g transform="translate(330 214) scale(1.6)"><path d="M0 0 Q2 -14 6 -28"/><path d="M6 -28q-10-3-15 4M6 -28q10-4 15 3M6 -28q-5-9-13-8M6 -28q4-10 12-9"/></g>'
    '</g>'
    '<g id="cv-wish" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="290" cy="96" r="30"/><circle cx="290" cy="96" r="46" stroke-opacity=".4"/>'
    '<path d="M0 190 Q100 172 200 186 T400 182 V260 H0Z" fill="#000" fill-opacity=".18" stroke="none"/>'
    '<path d="M0 190 Q100 172 200 186 T400 182"/><path d="M0 214 Q120 198 240 210 T400 206" stroke-opacity=".7"/><path d="M0 238 Q140 226 280 236 T400 232" stroke-opacity=".5"/>'
    '<path d="M150 178 l40 0 l-6 9 h-28z"/><path d="M170 178 V140 l18 34z"/><path d="M168 178 V146 l-14 30z" stroke-opacity=".7"/></g>'
    '</defs></svg>')


def art(which="art"):
    return f'<svg class="art" viewBox="0 0 400 260" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"><use href="#cv-{which}"/></svg>'


STAMP = ('<svg class="pm" viewBox="0 0 80 80" aria-hidden="true" focusable="false"><circle cx="40" cy="40" r="30" fill="none" stroke="currentColor" stroke-width="2.5"/>'
         '<circle cx="40" cy="40" r="22" fill="none" stroke="currentColor" stroke-width="1.5"/>'
         '<text x="40" y="37" text-anchor="middle" font-family="Inter, sans-serif" font-weight="800" font-size="9" fill="currentColor">SAMPLE</text>'
         '<text x="40" y="49" text-anchor="middle" font-family="Inter, sans-serif" font-weight="700" font-size="8" fill="currentColor">DEC 2026</text></svg>')
# small drawings the faces use (fixed colours that read on the white card and on the dark one)
I = {
    "arrow": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "sun": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5" fill="#FFB547"/></svg>',
    "snow": '<svg viewBox="0 0 24 24" fill="none" stroke="#5B7DB8" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 4v16M5 8l14 8M5 16l14-8"/></svg>',
    "mix": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="10" r="4.5" fill="#FFB547"/><path d="M8 19a3.5 3.5 0 0 1 .4-7 4.8 4.8 0 0 1 9.2 1.3A2.9 2.9 0 0 1 17 19z" fill="#9AA6C4"/></svg>',
    "cloud": '<svg viewBox="0 0 24 24" fill="#9AA6C4" aria-hidden="true"><path d="M7 18a4 4 0 0 1 .5-8 5.5 5.5 0 0 1 10.6 1.5A3.3 3.3 0 0 1 17.5 18z"/></svg>',
    "plane": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21 15.5v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V8.5l-8 5v2l8-2.5V18l-2 1.5V21l3.5-1 3.5 1v-1.5L13 18v-5z"/></svg>',
    "bed": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 18V7M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="1.6" fill="currentColor"/></svg>',
    "lock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    "heart": '<svg class="heart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20s-7-4.4-9-9a4.8 4.8 0 0 1 9-3 4.8 4.8 0 0 1 9 3c-2 4.6-9 9-9 9z"/></svg>',
    "talk": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4A8 8 0 1 1 20 12z"/></svg>',
    "send": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M21 3L3 10.5l7 3 3 7z"/><path d="M10 13.5L21 3"/></svg>',
    "cur": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3l16 7-7 2-3 7z" fill="var(--bd)" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>',
}


DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M6 13l6 6 6-6"/></svg>'


# ---------- the eight faces (the prototype's, drawn here as HTML) ----------

def _sentence(words):
    return " ".join(f'<span class="w" style="--i:{i}">{w}</span>' for i, w in enumerate(words))


def face_wish():
    """Face 0 and the real form: the card's writing is a textarea the visitor types in, and the pill posts it. The demo sentence writes itself over the empty box (aria-hidden)
    until the box is focused or has words; the same sentence is the placeholder."""
    demo = _sentence(("Somewhere warm,", "then snow,", "for 4 of us,", "mid-December."))
    return (f'<div class="f wish"><div class="artbox" aria-hidden="true">{art("wish")}<div class="ttl"><small>Greetings from</small><b>somewhere?</b></div>'
            '<div class="sig">The Patels · San Diego</div></div>'
            f'<form class="write cv-wish" action="{ASK}" method="post"><div class="stampbox" aria-hidden="true"><i></i></div>{STAMP}'
            f'<div class="dear" aria-hidden="true">Dear GitAway,</div>'
            f'<div class="sent-box"><textarea class="sent-in" name="q" rows="4" maxlength="80" required autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" '
            f'aria-label="{LABEL}" placeholder="{SAMPLE_WISH}"></textarea>'
            f'<p class="sent" aria-hidden="true">{demo}<span class="caret"></span></p></div>'
            f'<button class="go" type="submit">Show me every way {I["arrow"]}</button></form></div>')


def face_wish_again():
    """Face 7: someone else's wish, begun from the Patels' guide (a drawing; the form is face 0's)."""
    words = _sentence(("Coast to snow,", "like the Patels,", "for 5 of us,", "in March."))
    return (f'<div class="f wish"><div class="artbox">{art("wish")}<div class="ttl"><small>Greetings from</small><b>somewhere?</b></div>'
            f'<div class="from">{I["check"]}From the Patels\' postcard</div><div class="sig">The Riveras · Austin</div></div>'
            f'<div class="write"><div class="stampbox"><i></i></div>{STAMP}<div class="dear">Dear GitAway,</div><p class="sent">{words}<span class="caret"></span></p>'
            f'<div class="go">Show me every way {I["arrow"]}</div></div></div>')


DAYS = (("Fri", 11), ("Sat", 12), ("Sun", 13), ("Mon", 14), ("Tue", 15))
ROWS = (("San Diego", "5 nights", (2410, 2290, 2180, 2240, 2350), "sun"), ("Big Bear", "5 nights", (2620, 2480, 2390, 2440, 2710), "snow"),
        ("Coast + snow", "2 + 3 nights", (2260, 2110, 1940, 2050, 2380), "mix"))


def face_matrix():
    h = ['<div class="f mx"><header><b>Coast to snow, for 4</b><span>Each square: flights + stays, taxes in<br>Sample prices</span></header><div class="g"><span></span>']
    for i, (d, n) in enumerate(DAYS):
        h.append(f'<span class="h c{i + 1}">{d}<b>Dec {n}</b></span>')
    k = 0
    for ri, (name, nights, prices, kind) in enumerate(ROWS):
        h.append(f'<span class="pl">{name}<small>{nights}</small></span>')
        for i, p in enumerate(prices):
            pick = ri == 2 and i == 2
            cls = f'sq c{i + 1}{" pick" if pick else ""}{" over" if p > 2600 else ""}'
            h.append(f'<span class="{cls}" style="--i:{k}">{I[kind]}${p:,}{"<small>Our pick</small><i class=tap></i>" if pick else ""}</span>')
            k += 1
    h.append("</div></div>")
    return "".join(h)


def face_square():
    colours = ("var(--pl-sd)", "var(--pl-sun)", "var(--pl-lt)", "var(--pl-pink)", "var(--pl-la)", "var(--pl-teal)", "var(--pl-sun)", "var(--pl-sd)", "var(--pl-lt)", "var(--pl-pink)")
    conf = "".join(f'<i style="--c:{c};--x:{round(math.cos(i / len(colours) * math.tau) * 110)}px;--y:{round(math.sin(i / len(colours) * math.tau) * 70 - 40)}px"></i>'
                   for i, c in enumerate(colours))
    return (f'<div class="f sqr"><div class="artbox">{art()}<div class="ttl"><small>Sun Dec 13 · 5 nights · 4 of us</small><b>Coast + snow</b></div></div><div class="body">'
            f'<div class="row" style="--i:0"><span class="ic" style="--ic:var(--pl-sd)">{I["plane"]}</span><span><b>Flights to San Diego</b><small>4 seats, there and back</small></span><span class="p">$612</span></div>'
            f'<div class="row" style="--i:1"><span class="ic" style="--ic:var(--pl-la)">{I["bed"]}</span><span><b>Hotel by the cove</b><small>2 nights · coast</small></span><span class="p">$544</span></div>'
            f'<div class="row" style="--i:2"><span class="ic" style="--ic:var(--pl-lt)">{I["bed"]}</span><span><b>Lodge in the pines</b><small>3 nights · snow</small></span><span class="p">$784</span></div>'
            '<div class="tot"><span>Whole trip, for 4</span><b>$1,940</b></div>'
            f'<div class="book"><span class="b1">Book this trip</span><span class="b2">{I["check"]}Booked</span><span class="confetti">{conf}</span></div><div class="fine">Sample prices</div></div></div>')


def _blk(cls, c, n, t, hh, bd, body, i=None, far=False):
    return (f'<div class="blk {cls}{" far" if far else ""}" style="--c:{c};--n:{n};--t:{t}%;--hh:{hh}%;--bd:{bd}{f";--i:{i}" if i is not None else ""}">{body}</div>')


def face_calendar():
    by = lambda who: f"<small>{who}</small>"      # noqa: E731
    days = ("Sun <b>13</b>", "Mon <b>14</b>", "Tue <b>15</b>", "Wed <b>16</b>", "Thu <b>17</b>")
    people = (("M", "var(--pl-pink)"), ("S", "var(--pl-sd)"), ("A", "var(--pl-lt)"), ("P", "var(--pl-la)"))
    who = "".join(f'<i class="av" style="--i:{i};--a:{a}">{ch}</i>' for i, (ch, a) in enumerate(people))
    cur = lambda bd, d, fx, fy, tx, ty, name: (f'<div class="cur" style="--bd:{bd};--d:{d};--fx:{fx};--fy:{fy};--tx:{tx};--ty:{ty}">{I["cur"]}<span>{name}</span></div>')      # noqa: E731
    return ('<div class="f cal"><header><b>Coast to snow · Dec 13–18</b>' f'<span class="who">{who}</span><span class="creator">+ Maya\'s postcard</span></header>'
            '<div class="days">' + "".join(f'<span{" class=far" if i > 2 else ""}>{d}</span>' for i, d in enumerate(days)) + '</div><div class="grid">'
            + _blk("lock", 0, 1, 3, 17, "var(--pl-sd)", f'Land SAN 10:40<small>{I["lock"]}Booked</small>')
            + _blk("lock", 0, 2, 84, 12, "var(--pl-la)", "Hotel by the cove")
            + _blk("lock", 2, 3, 84, 12, "var(--pl-lt)", "Lodge in the pines")
            + _blk("plan guide", 1, 1, 4, 27, "var(--pc-ink-2)", "<em>Maya's postcard</em>La Jolla Cove at 9, before the crowds", 0)
            + _blk("plan", 0, 1, 52, 26, "var(--pl-pink)", "Tacos at the market" + by("Sam"), 1)
            + _blk("plan", 1, 1, 38, 28, "var(--pl-lt)", "Zoo after lunch" + by("Mum"), 2)
            + _blk("plan", 2, 1, 6, 24, "var(--pc-ink-2)", "Drive up to Big Bear" + by("Dad"), 3)
            + _blk("plan", 2, 1, 38, 26, "var(--pl-lt)", "Sled hill!" + by("Ava, 9"), 4)
            + _blk("plan", 3, 1, 12, 26, "var(--pl-lt)", "Lake walk" + by("Mum"), 5, True)
            + _blk("plan", 4, 1, 30, 22, "var(--pc-ink-2)", "Drive home" + by("Dad"), 6, True)
            + cur("var(--pl-pink)", "600ms", "220%", "30%", "115%", "330%", "Mum") + cur("var(--pl-sd)", "900ms", "-10%", "20%", "30%", "450%", "Sam") + "</div></div>")


def face_go():
    chips = (("sun", "71°", "Coast"), ("sun", "70°", "Zoo"), ("cloud", "52°", "Drive"), ("snow", "28°", "Snow"), ("snow", "31°", "Home"))
    spans = "".join(f'<span style="--i:{i}">{I[k]}{t}<em>&nbsp;{w}</em></span>' for i, (k, t, w) in enumerate(chips))
    return (f'<div class="f go"><div class="artbox">{art()}<div class="flakes"></div><div class="ttl"><small>Greetings from</small><b>San Diego</b><b>&amp; Big Bear</b></div>'
            '<span class="smp">Sample weather</span><div class="stamp s1">Day 1 · Coast · 71°</div><div class="stamp s2">Day 4 · Snow · 28°</div>'
            f'<div class="chips">{spans}</div></div></div>')


def face_guide():
    lines = (("Day 1", "Tacos at the market, night one. Go hungry.", "", ""), ("Day 2", "The cove at 9, before the crowds. Sea lions, guaranteed.", "From Maya's postcard", ""),
             ("Day 3", "Chains in the boot for the drive up, just in case.", "", "opt"), ("Day 4", "The sled hill behind the lodge. Ava's favourite day.", "", ""),
             ("Day 5", "Pancakes in the village before the drive home.", "", "opt"))
    ol = "".join(f'<li style="--i:{i}"{f" class={o}" if o else ""}><b>{d}</b><span><q>{t}</q>{f"<small>{s}</small>" if s else ""}</span></li>' for i, (d, t, s, o) in enumerate(lines))
    return (f'<div class="f guide"><div class="artbox">{art()}</div><div class="body"><h3>Coast to snow in five days</h3><div class="by">The Patels · 4 of us · December · sample</div><ol>{ol}</ol>'
            f'<div class="foot"><span>{I["lock"]}Prices and bookings stay private</span><span class="pub"><span class="b1">Publish</span><span class="b2">Published</span></span></div></div></div>')


def face_post():
    hearts = (("30%", "1.5s", "-20px"), ("48%", "1.8s", "14px"), ("64%", "2.1s", "-8px"), ("40%", "2.5s", "22px"))
    fl = "".join(f'<i style="--x:{x};--d:{d};--dx:{dx}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-9-9a4.8 4.8 0 0 1 9-3 4.8 4.8 0 0 1 9 3c-2 4.6-9 9-9 9z"/></svg></i>' for x, d, dx in hearts)
    return (f'<div class="f post"><header><i>P</i><b>@thepatels</b><span>· on GitAway</span></header><div class="artbox">{art()}<div class="ttl"><small>Greetings from</small><b>San Diego</b><b>&amp; Big Bear</b></div></div>'
            f'<h3>Coast to snow in five days</h3><div class="acts">{I["heart"]}{I["talk"]}{I["send"]}<span class="likes">2,418 likes · sample</span></div><div class="link">gitaway.me/trips/coast-to-snow</div>'
            f'<div class="float">{fl}</div></div>')


FACES = (face_wish, face_matrix, face_square, face_calendar, face_go, face_guide, face_post, face_wish_again)
# each card's size in drawing units (1 unit = --u): wide and phone (cover.css holds the same table for the beat the stage is on)


def _side(k):
    return Div(NotStr(FACES[k]()), cls="side" + (" on live" if k == 0 else ""), data_k=str(k), style=f"--k:{k}", **({} if k == 0 else {"aria_hidden": "true"}))


# ---------- the stage ----------

def _ring():
    """The ring of words: eight words on a circle, which turns one word per beat (cover.css rotates it by the beat); the beat's own word is inked."""
    rr = 440
    parts = ['<defs><path id="cv-rp" d="M500 60 A440 440 0 1 1 500 940 A440 440 0 1 1 500 60"/></defs>', f'<circle class="track" cx="500" cy="500" r="{rr + 46}"/>']
    for k, (word, *_rest) in enumerate(BEATS):
        parts.append(f'<text class="w{" now" if k == 0 else ""}" dy="20"><textPath href="#cv-rp" startOffset="{k * 12.5 + 6.25}%" text-anchor="middle">{word}</textPath></text>')
        a = k * math.pi / 4
        parts.append(f'<circle class="dot" r="7" cx="{500 + rr * math.sin(a):.1f}" cy="{500 - rr * math.cos(a):.1f}"/>')
    return Div(NotStr(f'<svg viewBox="0 0 1000 1000" focusable="false">{"".join(parts)}</svg>'), cls="ring", aria_hidden="true")


def _gallery():
    cards = "".join(f'<i style="--i:{i};--g:{HUES[(i * 5) % len(HUES)]}"><b>{label}</b></i>' for i, label in enumerate(PLACES))
    return Div(Div(NotStr(cards), cls="gal-spin"), cls="gal", aria_hidden="true")


def _caps():
    caps = []
    for k, (_word, label, head, soft, text) in enumerate(BEATS):
        tag = H1 if k == 0 else H2
        lab = Div(label, cls="label") if k == 0 else Div(NotStr(f"<i>{k}</i>{label}"), cls="label")
        extra = ()
        if k == 0:
            extra = (Div(A("Start a trip", href=plan_href(), cls="btn"), Span(NotStr(DOWN), "Follow the postcard", cls="hint"), cls="acts cv-ctas"), P(DISCLOSURE, cls="note"))
        if k == 7:
            extra = (Div(A("Start a trip", href=plan_href(), cls="btn"), A("Browse postcards", href="/guides", cls="btn soft"), cls="acts cv-ctas"),)
        caps.append(Article(lab, tag(head, " ", Em(soft)), P(text), *extra, cls="cap now" if k == 0 else "cap", data_k=str(k), style=f"--k:{k}"))
    return Div(*caps, cls="caps")


def _pager():
    return Nav(*[Button(Span(word), type="button", data_k=str(k), aria_label=word, **({"aria_current": "step"} if k == 0 else {})) for k, (word, *_r) in enumerate(BEATS)],
               cls="pager", aria_label="The story")


TWINS = (("t1", "var(--pl-pink)", "The Okafors · Chicago"), ("t2", "var(--pl-teal)", "Lena &amp; Jo · Denver"))


def _story():
    twins = "".join(f'<div class="twin {c}" style="--g:{g}" aria-hidden="true"><div><b>{who}</b></div></div>' for c, g, who in TWINS)
    rig = Div(NotStr(twins), Div(Div(*[_side(k) for k in range(8)], cls="pc"), cls="bob"), Div(NotStr("Made theirs by 214 families<small>sample</small>"), cls="saved", aria_hidden="true"), cls="rig")
    stage = Div(_gallery(), _ring(), rig, _caps(), _pager(), cls="stage", data_beat="0", style="--k:0")
    markers = Div(*[NotStr(f'<i style="--k:{k}"></i>') for k in range(8)], cls="beats", aria_hidden="true")
    return Section(stage, markers, id="story", aria_label="One trip, passed along")


def _sky():
    """The stage: the grey ground behind everything; on Go a fine snow drifts across it (cover.css, assets/js/cover.js sets data-mood)."""
    return Div(cls="cv-sky", data_mood="shore", aria_hidden="true")


def _close():
    return Section(Div(P("Find · Book · My trip · Postcards", cls="label"), H2("Go somewhere, ", Em("together.")),
                       P("Choose the whole trip in one view, plan it with your people, and pass it on as a postcard."),
                       Div(A("Start a trip", icon("arrow-right", 18, 2.2), href=plan_href(), cls="btn"), A("Browse postcards", href="/guides", cls="btn soft"), cls="acts cv-ctas"),
                       P(DISCLOSURE, cls="small"), cls="endcard"), cls="cv-close end", id="your-turn")


def _footer(links):
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        P("Choose the whole trip together. You book on each booking site, under its terms; GitAway never takes payment."),
        Nav(*[A(label, href=href) for label, href in [*links, ("Privacy", "/privacy"), ("Terms", "/terms")]], aria_label="More"),
        P(f"Early preview · {DISCLOSURE} The drawings are GitAway's own.", cls="cv-fine ga-fine"),
        cls="cv-foot",
    )


def _mode():
    return Button(icon("moon", 20, 2), icon("sun", 20, 2), type="button", cls="round cv-mode", data_mode_toggle="1", aria_pressed="false", aria_label="Dark mode", title="Dark mode")


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def page(footer_links):
    """The whole cover document. `footer_links` are the landing's (home.footer_links)."""
    head = styles(Link(rel="stylesheet", href="/assets/css/v2-tokens.css"), Link(rel="stylesheet", href="/assets/css/cover.css"), Link(rel="stylesheet", href="/assets/css/cover_why.css"),
                  Link(rel="preload", href="/assets/fonts/inter-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
                  Link(rel="preload", href="/assets/fonts/newsreader-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
                  *seo_meta(f"GitAway · {TITLE}", LEDE, OG_IMAGE),
                  Script(NotStr(_boot())), Script(src="/assets/js/cover.js", defer=True), Script(src="/assets/js/cover_why.js", defer=True))
    return (
        Title(f"GitAway · {TITLE}"),
        *head,
        Div(
            NotStr(SPRITE),
            _sky(),
            A("Skip to the story", href="#main", cls="ga-skip"),
            Header(brand(), Div(preview(), cls="cv-tag"),
                   Nav(*[A(label, href=plan_href() if href == NAV[-1][1] else href) for label, href in NAV], cls="cv-nav", aria_label="Main"),
                   _mode(), A("Sign in", href=session.signin_href(), cls="btn soft sm"), cls="cv-top"),
            Main(_story(), coverwhy.section(), _close(), id="main"),
            _footer(footer_links),
            cls="v2 cv3"),
    )
