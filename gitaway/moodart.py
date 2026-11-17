"""The foot of each mood's sky and the night's moon (F-260, D-690): one simple cartoon object per mood, drawn like the beach's shore (a 1440 x 260 inline SVG, decorative).
gitaway/moods.py chooses the mood; assets/css/v2-moods.css styles each mood's object at the foot (the ground itself is the Harbour gradient, F-281) and turns it down in the dark."""

import math

SHIFT = '<g transform="translate(-300 0)">'      # the objects sit near the middle, so a phone (which shows the middle 390 of the 1440) keeps them whole
SNOW = (SHIFT + '<path d="M820 214 L1040 36 L1260 214Z" fill="#8FA8C8"/><path d="M1040 36 L1260 214 L1130 214 L1066 96Z" fill="#7893B8"/>'
        '<path d="M1040 36 L994 76 L1016 70 L1040 94 L1062 68 L1086 80Z" fill="#FFFFFF"/>'
        '<path d="M1170 214 L1290 104 L1410 214Z" fill="#A9BCD6"/><path d="M1290 104 L1254 138 L1274 132 L1290 148 L1308 130 L1326 140Z" fill="#FFFFFF"/></g>'
        '<path d="M0 206 Q300 180 640 198 T1440 196 V260 H0Z" fill="#F7FAFE"/><path d="M0 232 Q320 212 700 228 T1440 222 V260 H0Z" fill="#E3ECF7"/>')

HIKE = ('<path d="M0 132 Q200 84 430 124 T900 104 T1440 122 V260 H0Z" fill="#BFD59B" opacity=".6"/>'
        + SHIFT + '<path d="M760 214 L1000 46 L1240 214Z" fill="#7BA568"/><path d="M1000 46 L1240 214 L1110 214 L1030 96Z" fill="#5F8F54"/></g>'
        '<path d="M0 196 Q360 164 720 188 T1440 180 V260 H0Z" fill="#E8D48A"/><path d="M0 234 Q360 214 760 230 T1440 224 V260 H0Z" fill="#D5BE6A"/>'
        + SHIFT + '<path d="M880 250 C 960 232, 940 214, 1004 200 S 1040 160, 1004 138 S 1020 100, 1000 74" fill="none" stroke="#FFF3C4" stroke-width="7" stroke-linecap="round" stroke-dasharray="2 14"/>'
        '<path d="M1000 74 V44 L1024 52 L1000 60" fill="#C92A5E" stroke="#C92A5E" stroke-width="2.5" stroke-linejoin="round"/></g>')


def _burst(cx, cy, r, colour, rays=12) -> str:
    out = []
    for i in range(rays):
        a = 2 * math.pi * i / rays
        x1, y1, x2, y2 = (cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45, cx + math.cos(a) * r, cy + math.sin(a) * r)
        out.append(f'<path d="M{x1:.0f} {y1:.0f} L{x2:.0f} {y2:.0f}" stroke="{colour}" stroke-width="4" stroke-linecap="round"/><circle cx="{x2 + math.cos(a) * 9:.0f}" cy="{y2 + math.sin(a) * 9:.0f}" r="3.5" fill="{colour}"/>')
    return f'<g>{"".join(out)}<circle cx="{cx}" cy="{cy}" r="6" fill="{colour}"/></g>'


def _star(x, y, s, colour) -> str:
    return f'<path transform="translate({x} {y}) scale({s})" d="M0 -10 L2.6 -2.6 L10 0 L2.6 2.6 L0 10 L-2.6 2.6 L-10 0 L-2.6 -2.6Z" fill="{colour}"/>'


CELEBRATION = (_burst(780, 96, 74, "#FFC83D") + _burst(570, 152, 42, "#FF7DA6", 10) + _burst(960, 150, 40, "#6FD8EE", 10)
               + _star(700, 90, 1.1, "#FFC83D") + _star(560, 160, 0.9, "#FF7DA6") + _star(1380, 70, 1.0, "#6FD8EE") + _star(300, 120, 0.8, "#FFFFFF") + _star(120, 70, 1.0, "#FFC83D")
               + '<path d="M0 228 Q360 216 720 226 T1440 222 V260 H0Z" fill="#3E2C72"/>')


def _skyline() -> str:
    back = [(0, 120), (90, 160), (170, 100), (260, 150), (350, 90), (440, 140), (520, 110), (620, 160), (720, 96), (820, 150), (910, 118), (1010, 164), (1100, 104), (1200, 148), (1290, 112), (1370, 150)]
    front = [(30, 70), (130, 110), (230, 60), (330, 100), (430, 84), (560, 120), (660, 66), (780, 104), (880, 76), (980, 112), (1080, 62), (1190, 100), (1280, 78), (1370, 108)]
    out = [f'<rect x="{x}" y="{260 - h}" width="{70 if h > 90 else 56}" height="{h}" fill="#AEB8D2" opacity=".6"/>' for x, h in back]
    for x, h in front:
        w = 64 if h > 80 else 52
        out.append(f'<rect x="{x}" y="{260 - h}" width="{w}" height="{h}" fill="#6D7899"/>')
        out += [f'<rect x="{x + 10 + wx * 20}" y="{260 - h + 12 + wy * 22}" width="9" height="11" rx="1.5" fill="#FBE9B0"/>'
                for wx in (0, 1) for wy in (0, 1, 2) if wy * 22 + 30 < h and (wx + wy + x // 10) % 3]
    out.append('<rect x="0" y="244" width="1440" height="16" fill="#56607F"/>')
    return "".join(out)


FEET = {"snow": SNOW, "hike": HIKE, "celebration": CELEBRATION, "city": _skyline()}

MOON = ('<svg class="moon" viewBox="0 0 100 100"><defs><mask id="v2-moon-cut"><rect width="100" height="100" fill="#fff"/><circle cx="73" cy="36" r="34" fill="#000"/></mask></defs>'
        '<circle cx="50" cy="50" r="42" fill="#F3EBD3" mask="url(#v2-moon-cut)"/>'
        '<path d="M19 57 q5 5 10 0" fill="none" stroke="#6B5B3A" stroke-width="2.4" stroke-linecap="round"/><path d="M21 69 q3.5 3 7 0" fill="none" stroke="#6B5B3A" stroke-width="2.2" stroke-linecap="round"/>'
        '<circle cx="15" cy="64" r="3.4" fill="#F4A9A0" opacity=".7"/>'
        '<g class="zz" fill="#F3EBD3" font-family="Newsreader, Georgia, serif" font-weight="600"><text x="80" y="28" font-size="13">z</text><text x="89" y="15" font-size="10">z</text></g></svg>')

_STARS = ((70, 40, 2.4), (160, 110, 1.8), (260, 30, 2.2), (330, 150, 1.6), (430, 70, 2.6), (520, 20, 1.8), (610, 120, 2.2), (700, 50, 1.6), (790, 140, 2.4), (880, 24, 1.8),
          (960, 96, 2.2), (1040, 170, 1.6), (1130, 40, 2.4), (1240, 120, 1.8), (1330, 60, 2.2), (1400, 150, 1.6))
STARS = ('<svg class="stars" viewBox="0 0 1440 220" preserveAspectRatio="xMidYMin slice">'
         + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" style="--i:{i}"/>' for i, (x, y, r) in enumerate(_STARS)) + "</svg>")
