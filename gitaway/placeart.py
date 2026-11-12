"""The place art (F-223): one drawn set of ten places in one style, ported from the approved artboard (docs/design/trip-matrix/art.js, F-221).

    art(place, night=False, wx=None, fit=...) -> str | None    the place's drawing as inline SVG, or None for a place with no art (the page shows its plain tint)
    kind(place) -> str | None                                  "beach", "city", "snow", "park", "desert" or "hike"; None for a place with no art
    name(place) -> str | None                                  "San Diego"
    SLUGS                                                      the ten, keyed like places.py's `Place.slug` ("sandiego"); a name or "san-diego" finds them too

Flat paper-cut layers (sky, far, mid, near, ground), one landmark, no outlines, no words, no photos. Nothing is generated per visit: these are fixed
drawings and the same place always draws the same. Every colour is a CSS custom property set on the <svg> itself (`--pa-sky1` ...), so a drawing is
whole without a stylesheet: `night=False` carries the day palette and the night one beside it (`data-sky="auto"`), and assets/css/placeart.css swaps
to night in dark mode; `night=True` is always night. `wx` ("sun", "cloud", "rain", "snow") adds the weather layer; assets/css/placeart.css drifts the
clouds and lets rain and snow fall, all of it still under reduced motion. Only numbers from the tables below reach the SVG, never a caller's text.
"""

import itertools
import math
import re
from html import escape

W, H = 480, 240
VARS = ("sky1", "sky2", "sun", "far", "mid", "near", "water", "foam", "ground", "ground2", "line", "acc", "leaf", "snow", "cloud")
WX = ("sun", "cloud", "rain", "snow")
FITS = ("xMidYMax slice", "xMidYMid slice", "xMidYMid meet")

# (name, kind, what is drawn, day palette, night palette); a palette is the first fourteen VARS (the clouds' colour follows the weather, CLOUD)
_ART = {
    "sandiego": ("San Diego", "beach", "Ocean Beach pier and a lifeguard tower",
                 "#D9ECFA #FCEBD6 #FFB547 #A9C3D9 #7FA6C4 #2F6B4F #3F8FC2 #BFE0F2 #F0DDBA #E2C594 #2B3A4A #E4572E #2F7A55 #FFFFFF",
                 "#0A1830 #28365A #F3EBD3 #1E2E48 #24395A #0F2A1E #123A5A #2E6A93 #3A3328 #2C261E #070D16 #B5452A #14301F #E8EEF6"),
    "losangeles": ("Los Angeles", "city", "The observatory on the ridge, palms below",
                   "#E2EEF8 #FBE3CF #FF9F45 #C5CDD8 #C9A57E #3E6B4A #5B9BC6 #D5E8F4 #E9D3B0 #D6B98C #33363F #F2EEE6 #3B7550 #FFFFFF",
                   "#0C1428 #3A2C4E #F3EBD3 #252C40 #3A2E35 #13261A #1A3550 #2D5577 #2C2620 #221D18 #05080F #D8D2C4 #183022 #E8EEF6"),
    "newyork": ("New York", "city", "The Statue of Liberty and the skyline",
                "#DCE8F5 #F6E6D8 #FFB35C #9EAFC4 #7E93AD #4B5D73 #4F84B0 #C9DFF0 #B9C2AE #98A38D #3A4656 #5FA79A #3E6E52 #FFFFFF",
                "#081226 #1F2C4A #F3EBD3 #1B2740 #22314E #121A28 #0F2C48 #2A5578 #1D2620 #161D18 #04070D #3C7F73 #15281D #E8EEF6"),
    "laketahoe": ("Lake Tahoe", "snow", "Pines, snowy peaks and the lake",
                  "#D6E9F7 #EEF5FA #FFC861 #93AFC9 #6E8FB0 #2E5A44 #3D7FB0 #CFE5F4 #F5F8FB #DCE6EF #34404E #FFFFFF #2C5B43 #FFFFFF",
                  "#081428 #1C2B48 #F3EBD3 #1B2A44 #203250 #0F2219 #0D2B47 #2A5A80 #8C9AAD #6F7E92 #05080F #E6EDF5 #0F2519 #DDE6F0"),
    "orlando": ("Orlando", "park", "Lake Eola’s fountain and fireworks",
                "#E6E3F6 #FCE1D2 #FF8F5A #B9B6CF #8E9DB8 #2F6B4F #4B8EC0 #CFE4F3 #CDE4B8 #ABCB92 #323A48 #E9476B #2F7A55 #FFFFFF",
                "#0E0F2A #3B2448 #F3EBD3 #24233F #2A3150 #0F2419 #121F45 #33508A #1E2C1A #172314 #05070F #FF5C85 #14301F #E8EEF6"),
    "palmsprings": ("Palm Springs", "desert", "San Jacinto, wind farms and a mid-century house",
                    "#DCEBF8 #FCE6CB #FFAA3B #C9A98B #B48A6A #4F7A55 #69A9D6 #D9EEF8 #F1D9B2 #E0BE8C #3B3530 #F7F3EA #5B8A5E #FFFFFF",
                    "#0C1430 #40294A #F3EBD3 #3A2A2E #2E2226 #16261A #183A5A #2D5F87 #33291F #271F17 #06070C #D8D2C4 #1A3020 #E8EEF6"),
    "santabarbara": ("Santa Barbara", "beach", "The mission’s twin bell towers",
                     "#DBEBF8 #FBEBDC #FFB24E #9DB7A8 #7FA08F #3E6B4A #3F8FC2 #C6E2F3 #C9DDAE #A9C68B #3A3A44 #C8562E #3B7550 #FFFDF7",
                     "#0A1630 #2A3456 #F3EBD3 #1C2C2A #20302C #12241A #0F3150 #2A5A80 #1E2A1A #172113 #05080F #9C4426 #15281D #D9D4C8"),
    "orangecounty": ("Orange County", "beach", "The harbour’s Ferris wheel and sails",
                     "#D8EAF8 #FCE9D9 #FFB84F #B3C3CF #9AB2C2 #3E6B4A #3A8BC4 #C8E3F4 #F2E0BF #E3C899 #2E3A48 #F25C54 #2F7A55 #FFFFFF",
                     "#0A1530 #2A3256 #F3EBD3 #1D2A40 #22324A #11231A #0F3352 #2B5D84 #3A3328 #2C261E #05080F #FF6B63 #14301F #E8EEF6"),
    "honolulu": ("Honolulu", "beach", "Diamond Head and the surf",
                 "#D3ECF7 #F9EEDB #FFB23F #A7C7BE #6E9C7F #2E6E4C #2A93C6 #BFE6F5 #F4E3C1 #E6CB98 #2C3A44 #F2A33A #2F7A55 #FFFFFF",
                 "#081A30 #273A58 #F3EBD3 #183028 #1B3A2C #0E241A #0C3552 #27648C #3A3328 #2C261E #05080F #C27A20 #123020 #E8EEF6"),
    "yosemite": ("Yosemite", "hike", "Half Dome and the falls",
                 "#D9EAF7 #F2F2EC #FFC35A #A8B8C6 #8C9CAB #2E5A44 #4A8DBA #D3E8F5 #C7D9A8 #A6BF84 #3A4452 #FFFFFF #2C5B43 #FFFFFF",
                 "#081428 #1E2C46 #F3EBD3 #202C3C #26323F #0F2219 #0F2C47 #2A5A80 #1A2618 #141E12 #05080F #E6EDF5 #0F2519 #DDE6F0"),
}
SLUGS = tuple(_ART)
CLOUD = {"day": {"sun": "#FFFFFF", "cloud": "#FFFFFF", "rain": "#C9D3DE", "snow": "#E6ECF3"}, "night": "#3A4660"}
# how much of each weather layer shows: (light clouds, heavy clouds, rain, snow, the sun)
_LAYERS = {"sun": (.75, 0, 0, 0, 1), "cloud": (.92, .92, 0, 0, .45), "rain": (1, 1, .75, 0, 0), "snow": (.95, .95, 0, .95, 0)}
_IDS = itertools.count(1)


def _slug(place) -> str:
    """places.py's slug for a name or a slug: "San Diego", "san-diego" and "sandiego" are all "sandiego"."""
    return re.sub(r"[^a-z0-9]", "", str(place or "").lower())[:20]


def name(place) -> str | None:
    entry = _ART.get(_slug(place))
    return entry[0] if entry else None


def kind(place) -> str | None:
    entry = _ART.get(_slug(place))
    return entry[1] if entry else None


# ---- the shared drawing helpers (one style for every scene) ----------------------------------------------------------------

_FILL = {"fa": "far", "mi": "mid", "ne": "near", "wa": "water", "gr": "ground", "g2": "ground2", "ln": "line", "ac": "acc", "lf": "leaf", "sn": "snow", "fo": "foam"}


def _n(v) -> str:
    v = round(float(v), 2)
    return str(int(v)) if v == int(v) else f"{v:g}"


def _d(*parts) -> str:
    """A path's d from letters and numbers: _d("M", 0, 140, "L", 262, 152, "Z")."""
    return " ".join(p if isinstance(p, str) else _n(p) for p in parts).replace(" Z", "Z")


def P(d, c):
    return f'<path style="fill:var(--pa-{_FILL[c]})" d="{d}"/>'


def S(d, c, w=3):
    return f'<path style="stroke:var(--pa-{_FILL[c]});fill:none" d="{d}" stroke-width="{_n(w)}" stroke-linecap="round"/>'


def R(c, x, y, w, h, rx=None, extra=""):
    r = f' rx="{_n(rx)}"' if rx is not None else ""
    return f'<rect style="fill:var(--pa-{_FILL[c]})" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"{r}{extra}/>'


def C(c, cx, cy, r):
    return f'<circle style="fill:var(--pa-{_FILL[c]})" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"/>'


def palm(x, y, h, lean=1, c="lf"):
    tx, ty = x + lean * h * 0.22, y - h
    s = S(_d("M", x, y, "C", x + lean * 2, y - h * .45, tx - lean * 4, ty + h * .3, tx, ty), "ln", max(2.5, h / 22))
    f = h * 0.34
    for dx, dy in ((-1, .15), (-1, -.45), (1, -.4), (1, .2), (-.15, -1)):
        ex, ey = tx + dx * f, ty + dy * f * .55 + f * .32
        s += P(_d("M", tx, ty, "Q", tx + dx * f * .55, ty + dy * f * .55 - f * .2, ex, ey, "Q", tx + dx * f * .45, ty + dy * f * .3 + f * .02, tx, ty, "Z"), c)
    return s


def pine(x, y, h, c="lf"):
    w = h * .42
    s = R("ln", x - 1.5, y - h * .16, 3, h * .16)
    for i in range(3):
        top, bot, ww = y - h + i * h * .24, y - h * .14 - (2 - i) * h * .14, w * (.55 + i * .22)
        s += P(_d("M", x, top, "L", x + ww, bot, "L", x - ww, bot, "Z"), c)
    return s


def towers(x0, base, sizes, c):
    s, x = "", x0
    for w, h in sizes:
        s += R(c, x, base - h, w, h)
        x += w + 2
    return s


def waves(y, c="fo"):
    return "".join(S(_d("M", x, y + dy, "h", w), c, 2.5) for x, dy, w in ((18, 0, 54), (110, 8, 34), (196, 3, 48), (300, 10, 40), (398, 5, 58)))


def _polar(cx, cy, a, r):
    return cx + math.cos(a) * r, cy + math.sin(a) * r


# ---- the ten scenes (drawn on 480 x 240; the horizon is near y 150): (sun x, y, r), body -----------------------------------

def _san_diego():
    return (362, 112, 26), (
        P("M0 140 C60 124 122 126 172 137 C204 130 232 133 262 142 L262 152 L0 152Z", "fa") +
        P("M296 146 L480 143 L480 152 L296 152Z", "fa") +
        R("wa", 0, 150, W, 44) + waves(160) +
        R("ln", 250, 135, 230, 5) +
        "".join(S(_d("M", 258 + i * 16, 140, "V", 170 - i * .3), "ln", 2.4) for i in range(14)) +
        R("ac", 266, 123, 20, 12, 1) + P("M262 124 L276 116 L290 124Z", "ln") +
        P("M0 192 C120 180 260 184 480 172 L480 240 L0 240Z", "gr") + P("M0 214 C140 204 300 210 480 200 L480 240 L0 240Z", "g2") +
        S("M112 210 L118 188 M142 210 L136 188 M118 196 H136", "ln", 2.6) +
        R("ac", 108, 168, 36, 20, 2) + P("M103 169 L126 157 L149 169Z", "ln") + R("sn", 116, 173, 20, 7, 1) +
        palm(44, 214, 96, 1) + palm(452, 206, 70, -1) +
        R("ac", 196, 196, 5, 22, 2.5, ' transform="rotate(-12 198 207)"'))


def _los_angeles():
    return (108, 98, 24), (
        towers(26, 152, ((10, 36), (14, 58), (9, 44), (16, 72), (11, 50), (13, 62), (8, 30)), "fa") +
        P("M0 162 C80 142 140 130 200 118 C250 100 300 96 340 104 C392 112 432 124 480 132 L480 186 L0 186Z", "mi") +
        R("ac", 268, 90, 64, 10, 1) + P("M287 90 a13 13 0 0 1 26 0Z", "ln") +
        P("M268 90 a6 6 0 0 1 12 0Z", "ln") + P("M320 90 a6 6 0 0 1 12 0Z", "ln") + R("ln", 298, 72, 4, 6) +
        P("M0 192 C120 178 300 186 480 178 L480 240 L0 240Z", "ne") + R("g2", 0, 214, W, 26) +
        palm(52, 214, 132, .2) + palm(84, 214, 112, -.1) + palm(392, 214, 124, .15) + palm(430, 214, 140, -.05) + palm(464, 214, 104, .1))


def _new_york():
    return (404, 72, 20), (
        towers(196, 152, ((12, 40), (16, 66), (10, 52), (14, 84), (18, 58), (12, 46), (16, 76), (10, 38), (14, 62), (20, 54), (12, 70), (16, 44), (14, 34)), "fa") +
        R("mi", 318, 84, 22, 68) + R("mi", 322, 74, 14, 10) + R("mi", 326, 66, 6, 8) + S("M329 66 V46", "mi", 2) +
        P("M396 152 L402 62 L414 62 L420 152Z", "mi") + S("M408 62 V38", "mi", 2) +
        R("wa", 0, 150, W, 90) + waves(170) + waves(196) +
        P("M30 200 L182 200 L170 188 L44 188Z", "gr") + P("M68 188 L144 188 L136 178 L76 178Z", "g2") +
        R("g2", 90, 140, 32, 38) + R("gr", 86, 136, 40, 5) +
        P("M96 136 L100 98 C102 91 112 91 114 98 L118 136Z", "ac") + C("ac", 107, 88, 5.4) +
        S("M101 84 l-4 -6 M104.5 82 l-1 -7.5 M109.5 82 l1 -7.5 M113 84 l4 -6", "ac", 1.8) +
        P("M110 99 L117 70 L121 71 L115 101Z", "ac") + R("ac", 115, 63, 7, 8, 1) +
        '<ellipse style="fill:var(--pa-sun)" cx="118.5" cy="59" rx="3.4" ry="5"/>' + R("ac", 94, 104, 6, 13, 1))


def _lake_tahoe():
    peaks = ((50, 98), (122, 76), (212, 92), (302, 84), (402, 94))
    return (150, 80, 20), (
        P("M0 142 L50 98 L80 118 L122 76 L170 124 L212 92 L258 130 L302 84 L352 120 L402 94 L442 118 L480 104 L480 152 L0 152Z", "fa") +
        "".join(P(_d("M", x, y, "L", x - 13, y + 14, "L", x - 5, y + 11, "L", x + 1, y + 16, "L", x + 7, y + 11, "L", x + 13, y + 13, "Z"), "sn") for x, y in peaks) +
        P("M0 152 L70 128 L120 146 L190 122 L250 150Z", "mi") +
        R("wa", 0, 150, W, 40) + waves(162) +
        P("M0 190 C120 178 300 186 480 176 L480 240 L0 240Z", "gr") + P("M0 218 C160 208 320 214 480 206 L480 240 L0 240Z", "g2") +
        pine(30, 214, 92) + pine(64, 206, 70) + pine(96, 216, 54) + pine(392, 210, 78) + pine(428, 216, 104) + pine(462, 206, 66))


def _orlando():
    bursts = ""
    for k, (x, y, c) in enumerate(((118, 62, "ac"), (372, 50, "sn"), (300, 86, "ac"))):
        r1, r2 = 6 + k, 18 + k * 3
        rays = "".join(S(_d("M", *_polar(x, y, i * math.pi / 6, r1), "L", *_polar(x, y, i * math.pi / 6, r2)), c, 2) for i in range(12))
        bursts += f'<g class="pa-fw pa-fw{k + 1}">{rays}</g>'
    return (398, 132, 20), (
        bursts +
        towers(300, 152, ((10, 30), (14, 44), (9, 26), (16, 52), (11, 36), (12, 24)), "fa") + towers(30, 152, ((12, 22), (10, 34), (14, 26)), "fa") +
        R("wa", 0, 150, W, 56) + waves(176) +
        '<ellipse style="fill:var(--pa-line)" cx="240" cy="170" rx="46" ry="5"/>' + P("M204 168 Q240 158 276 168Z", "sn") +
        P("M218 160 Q240 146 262 160 L254 162 L226 162Z", "sn") + P("M228 150 Q240 140 252 150 L246 152 L234 152Z", "sn") + R("sn", 237, 136, 6, 16, 2) +
        S("M240 134 V86", "fo", 4) +
        S("M240 104 C226 96 212 104 206 122 M240 104 C254 96 268 104 274 122 M240 120 C230 116 222 122 218 140 M240 120 C250 116 258 122 262 140", "fo", 2.2) +
        C("sn", 240, 84, 3) +
        P("M0 204 C120 196 300 202 480 192 L480 240 L0 240Z", "gr") + P("M0 224 C160 216 320 222 480 214 L480 240 L0 240Z", "g2") +
        palm(40, 222, 100, .6) + palm(78, 222, 76, -.4) + palm(418, 218, 110, -.5) + palm(454, 220, 80, .3))


def _palm_springs():
    turbines = ""
    for i, (x, y) in enumerate(((372, 128), (410, 134), (448, 124))):
        hub = y - 46
        blades = "".join(S(_d("M", x, hub, "l", math.cos(math.radians(a - 90)) * 16, math.sin(math.radians(a - 90)) * 16), "sn", 2) for a in (0, 120, 240))
        turbines += S(_d("M", x, y, "V", hub), "sn", 2.2) + f'<g class="pa-tb pa-tb{i + 1}" style="transform-origin:{x}px {hub}px">{blades}</g>'
    agaves = "".join(S(_d("M", x, y, "l", math.sin(a) * 18, -math.cos(a) * 18), "lf", 3.2) for x, y in ((34, 222), (300, 220), (438, 218)) for a in (-.9, -.45, 0, .45, .9))
    return (300, 70, 26), (
        P("M0 152 L58 112 L120 62 L170 84 L230 50 L300 104 L360 92 L420 122 L480 114 L480 152Z", "fa") +
        P("M120 62 L150 100 L132 120 L170 84Z M230 50 L250 96 L224 118 L210 86Z", "mi") +
        turbines +
        P("M0 166 C120 150 300 160 480 150 L480 240 L0 240Z", "gr") + P("M0 214 C140 202 320 210 480 200 L480 240 L0 240Z", "g2") +
        R("ac", 66, 170, 96, 26) + P("M56 170 L114 164 L172 170 L172 174 L56 174Z", "ln") + R("wa", 80, 178, 40, 12) + R("ln", 130, 178, 12, 18) +
        palm(206, 214, 128, .05) + palm(232, 214, 106, -.08) + agaves)


def _santa_barbara():
    return (404, 92, 22), (
        P("M0 122 C80 98 160 106 240 96 C320 88 400 102 480 94 L480 152 L0 152Z", "fa") +
        R("wa", 0, 150, W, 28) + waves(160) +
        P("M0 176 C120 170 300 174 480 168 L480 240 L0 240Z", "gr") + P("M0 220 C160 212 320 218 480 210 L480 240 L0 240Z", "g2") +
        R("sn", 22, 140, 66, 34) + R("ac", 18, 134, 74, 7) +
        "".join(P(_d("M", x - 5, 174, "V", 158, "a", 5, 5, 0, 0, 1, 10, 0, "V", 174, "Z"), "ln") for x in (30, 46, 62, 78)) +
        R("sn", 90, 98, 28, 76) + R("sn", 160, 98, 28, 76) +
        P("M90 98 a14 10 0 0 1 28 0Z M160 98 a14 10 0 0 1 28 0Z", "ac") + R("ln", 99, 106, 10, 12, 5) + R("ln", 169, 106, 10, 12, 5) +
        R("sn", 118, 116, 42, 58) + P("M112 117 L139 96 L166 117Z", "sn") + P("M132 174 V152 a7 7 0 0 1 14 0 V174Z", "ln") + C("ln", 139, 132, 5) +
        palm(420, 214, 120, -.2) + palm(456, 214, 92, .1))


def _orange_county():
    spokes = "".join(S(_d("M", 346, 118, "l", math.cos(i * math.pi / 4) * 38, math.sin(i * math.pi / 4) * 38), "ln", 1.4) for i in range(8))
    cars = "".join(R("ac", 346 + math.cos(i * math.pi / 4 + .2) * 38 - 4, 118 + math.sin(i * math.pi / 4 + .2) * 38 - 1, 8, 8, 2) for i in range(8))
    sails = "".join(
        P(_d("M", x - 22 * s, y, "L", x + 24 * s, y, "L", x + 16 * s, y + 9 * s, "L", x - 16 * s, y + 9 * s, "Z"), "sn") + S(_d("M", x, y, "V", y - 50 * s), "ln", 1.8) +
        P(_d("M", x + 2, y - 48 * s, "L", x + 2, y - 4, "L", x + 30 * s, y - 4, "Z"), "sn") + P(_d("M", x - 2, y - 40 * s, "L", x - 2, y - 4, "L", x - 18 * s, y - 4, "Z"), "ac")
        for x, y, s in ((118, 182, 1), (196, 190, .8)))
    return (100, 84, 22), (
        P("M0 134 C100 118 200 124 300 116 C380 112 430 122 480 120 L480 152 L0 152Z", "fa") +
        R("wa", 0, 150, W, 62) + waves(186) +
        '<circle style="stroke:var(--pa-line);fill:none" cx="346" cy="118" r="38" stroke-width="2.6"/>' + spokes + cars +
        S("M346 118 L326 166 M346 118 L366 166", "ln", 3) + R("ln", 290, 164, 120, 6) + sails +
        P("M0 212 C140 206 320 210 480 202 L480 240 L0 240Z", "gr") + palm(450, 226, 96, -.2))


def _honolulu():
    return (128, 76, 24), (
        P("M0 136 C60 122 120 124 190 134 L190 152 L0 152Z", "fa") +
        P("M180 152 C214 118 252 94 300 90 C330 88 352 96 382 110 C412 122 444 134 480 138 L480 152Z", "mi") +
        S("M262 100 C280 110 310 108 330 98 M300 92 C300 104 304 118 312 130", "ne", 2) +
        R("wa", 0, 150, W, 54) + waves(184) +
        P("M20 166 C60 146 108 146 132 162 C114 156 96 158 86 170 C70 172 44 172 20 166Z", "fo") +
        P("M0 202 C120 194 300 200 480 190 L480 240 L0 240Z", "gr") + P("M0 224 C160 216 320 222 480 214 L480 240 L0 240Z", "g2") +
        R("ac", 168, 174, 9, 40, 4.5, ' transform="rotate(10 172 194)"') +
        palm(408, 220, 130, -.9) + palm(446, 222, 98, -.6))


def _yosemite():
    return (78, 70, 20), (
        P("M0 152 L0 58 C42 54 92 62 114 84 L132 152Z", "mi") +
        P("M188 152 C192 110 210 76 242 60 C268 48 302 48 320 58 L324 62 L324 152Z", "fa") + P("M320 58 L324 62 L324 152 L314 152 C318 120 318 88 320 58Z", "mi") +
        P("M322 152 L360 112 L420 128 L480 108 L480 152Z", "mi") +
        S("M106 80 C108 100 108 128 110 152", "sn", 4) + S("M110 92 C111 110 112 132 113 152", "fo", 1.6) +
        P("M0 152 L480 152 L480 240 L0 240Z", "gr") + S("M0 196 C80 186 150 206 240 194 C320 184 400 200 480 190", "wa", 7) +
        P("M0 226 C160 218 320 224 480 216 L480 240 L0 240Z", "g2") +
        pine(30, 216, 88) + pine(66, 208, 60) + pine(250, 214, 50) + pine(384, 212, 76) + pine(420, 218, 98) + pine(456, 208, 62))


_SCENES = {"sandiego": _san_diego, "losangeles": _los_angeles, "newyork": _new_york, "laketahoe": _lake_tahoe, "orlando": _orlando,
           "palmsprings": _palm_springs, "santabarbara": _santa_barbara, "orangecounty": _orange_county, "honolulu": _honolulu, "yosemite": _yosemite}


# ---- the weather layer: the same for every place --------------------------------------------------------------------------

def _cloud(x, y, s):
    return (f'<g transform="translate({_n(x)} {_n(y)}) scale({_n(s)})"><circle cx="0" cy="0" r="12"/><circle cx="14" cy="-6" r="15"/>'
            '<circle cx="30" cy="0" r="11"/><rect x="-6" y="0" width="42" height="11" rx="5.5"/></g>')


def _weather(wx):
    light, heavy, rain, snow, _ = _LAYERS[wx]
    out = '<g class="pa-wx" style="fill:var(--pa-cloud)">'
    if light:
        out += f'<g class="pa-cl" style="opacity:{_n(light)}">{_cloud(60, 52, 1.1)}{_cloud(250, 34, .8)}{_cloud(380, 62, 1.25)}</g>'
    if heavy:
        out += f'<g class="pa-cl2" style="opacity:{_n(heavy)}">{_cloud(150, 70, 1.4)}{_cloud(330, 40, 1.6)}{_cloud(10, 30, 1.2)}</g>'
    if rain:
        drops = "".join(f'<path d="M{(i * 53) % W} {(i * 37) % 150}l-5 12"/>' for i in range(36))
        out += f'<g class="pa-rn" style="opacity:{_n(rain)};stroke:var(--pa-water);stroke-width:2;stroke-linecap:round;fill:none">{drops}</g>'
    if snow:
        flakes = "".join(f'<circle cx="{(i * 47) % W}" cy="{(i * 29) % 170}" r="{_n(1.6 + (i % 3) * .5)}"/>' for i in range(36))
        out += f'<g class="pa-sn" style="opacity:{_n(snow)};fill:var(--pa-snow)">{flakes}</g>'
    return out + "</g>"


def _palette(slug, when, wx):
    entry = _ART[slug]
    values = (entry[3] if when == "day" else entry[4]).split()
    cloud = CLOUD["night"] if when == "night" else CLOUD["day"][wx or "sun"]
    return dict(zip(VARS, (*values, cloud)))


def art(place, night: bool = False, wx: str | None = None, fit: str = FITS[0]) -> str | None:
    """The place's drawing as inline SVG, or None when it has none. Day art follows the page's mode (night in dark mode, with assets/css/placeart.css);
    `night=True` is night in both. `wx` adds the weather layer; `fit` is its preserveAspectRatio (it fills its box, cut from the bottom up, by default)."""
    slug = _slug(place)
    if slug not in _ART:
        return None
    if wx is not None and wx not in WX:
        raise ValueError(f"weather is one of {WX}")
    if fit not in FITS:
        raise ValueError(f"fit is one of {FITS}")
    label, _, line = _ART[slug][:3]
    if night:
        style = ";".join(f"--pa-{k}:{v}" for k, v in _palette(slug, "night", wx).items())
    else:
        style = ";".join([*(f"--pa-{k}:{v}" for k, v in _palette(slug, "day", wx).items()),
                          *(f"--pa-n-{k}:{v}" for k, v in _palette(slug, "night", wx).items())])
    (sx, sy, sr), body = _SCENES[slug]()
    sun = _LAYERS[wx][4] if wx else 1
    gid = f"pa-{slug}-{next(_IDS)}"
    return (f'<svg class="pa-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="{fit}" role="img" '
            f'aria-label="{escape(f"{label}: {line}")}" data-sky="{"night" if night else "auto"}" data-place="{slug}"{f" data-wx={chr(34)}{wx}{chr(34)}" if wx else ""} style="{style}">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--pa-sky1)"/>'
            f'<stop offset=".72" style="stop-color:var(--pa-sky2)"/></linearGradient></defs>'
            f'<rect width="{W}" height="{H}" fill="url(#{gid})"/>'
            f'<circle class="pa-sun" style="fill:var(--pa-sun){";opacity:" + _n(sun) if sun != 1 else ""}" cx="{sx}" cy="{sy}" r="{sr}"/>'
            f'{_weather(wx) if wx else ""}{body}</svg>')
