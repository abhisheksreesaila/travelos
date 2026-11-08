"""The 13 storyboard panels as 1600 x 900 SVG scenes, built from the shared cast symbols (cast.py).

Every panel function takes (P, mode): P prefixes its ids so 13 inline SVGs can share one page; mode is "page"
(index.html) or "file" (story/art/panel-NN.svg) and only changes the relative path of the Tahoe render.
Colour strategy: pages 1-3 are muted (a saturate filter), colour blooms on page 4 and stays.
"""
import base64
import math
import random
import re
from pathlib import Path

from cast import fig, SYMS, PAL

HERE = Path(__file__).resolve().parent
SANS = 'font-family="Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"'
SERIF = 'font-family="Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"'
INK = "#2b2620"
KIND = ["#D2401C", "#087F7B", "#A445D8", "#F59A2E", "#E0204E", "#0068D9", "#5250E0"]
STILL = {"page": "../../../../assets/cover/stills/a-3-wide-light.webp",
         "file": "../../../../../assets/cover/stills/a-3-wide-light.webp"}

# ---------------------------------------------------------------- icons (E's stroke icons, plus a few)
ICONS = {
    "i-snow": '<path d="M12 2v20M3.5 7l17 10M20.5 7l-17 10M9.5 3.5 12 5l2.5-1.5M9.5 20.5 12 19l2.5 1.5"/>',
    "i-flight": '<path d="M3 13l18-7-5 15-3.5-6.5z"/>',
    "i-stay": '<path d="M3 11 12 4l9 7v9H3zM10 20v-5h4v5"/>',
    "i-car": '<path d="M4 16v-4l2.2-5.2A2 2 0 0 1 8 5.5h8a2 2 0 0 1 1.8 1.3L20 12v4zM4 16v3M20 16v3M4 12h16M7.5 14h.01M16.5 14h.01"/>',
    "i-see": '<path d="M2 20 9 8l4 6 3-4 6 10z"/>',
    "i-trail": '<circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/><path d="M7 19c5 0 2-7 6-7s2-7 4-7"/>',
    "i-heart": '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"/>',
    "i-check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "i-pin": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "i-swap": '<path d="M4 8h14l-3-3M20 16H6l3 3"/>',
    "i-fork": '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M6 7v2a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V7M12 12v5"/>',
    "i-chain": '<rect x="2.5" y="8.5" width="10" height="7" rx="3.5"/><rect x="11.5" y="8.5" width="10" height="7" rx="3.5"/>',
    "i-coins": '<ellipse cx="9" cy="7" rx="6" ry="2.5"/><path d="M3 7v4c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V7M3 11v4c0 1.4 2.7 2.5 6 2.5 1.2 0 2.3-.1 3.2-.4M15 14h6M15 18h6M15 10h6"/>',
    "i-passport": '<rect x="5" y="2.5" width="14" height="19" rx="2"/><circle cx="12" cy="10" r="3.5"/><path d="M8.5 17h7"/>',
    "i-sun": '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
    "i-boot": '<path d="M6 3h6v8l6 3c1.7.8 3 2 3 4v2H3V12z"/><path d="M3 17h18"/>',
}
for k, v in ICONS.items():
    SYMS[k] = ((0, 0, 24, 24), v)


def icon(i, x, y, size, color="#fff", sw=2):
    return (f'<g stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round">'
            f'<use href="#{i}" x="{x}" y="{y}" width="{size}" height="{size}"/></g>')


def T(x, y, s, txt, size=24, weight=600, fill=INK, anchor="start", font=SANS, extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {font} {extra}>{txt}</text>'


def logo(x, y, s=1):
    return (f'<g transform="translate({x} {y}) scale({s})"><rect x="-12" y="-12" width="24" height="24" rx="7" fill="#D2401C"/>'
            '<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><circle cx="-5" cy="5" r="2.2"/><circle cx="5" cy="-5" r="2.2"/>'
            '<circle cx="-5" cy="-5" r="2.2"/><path d="M-3.2 3.4 3.2-3.4M-5-2.6v5.2"/></g></g>')


# ---------------------------------------------------------------- snapshots (photos), as symbols
def _snapshots():
    SYMS["ph-tahoe"] = ((0, 0, 160, 120), (
        '<linearGradient id="ph-tahoe-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9CC8EE"/><stop offset="1" stop-color="#E6F1FA"/></linearGradient>'
        '<rect width="160" height="120" fill="url(#ph-tahoe-sky)"/>'
        '<path d="M0 70 30 34l18 18 26-30 30 32 18-14 38 30v10H0z" fill="#8FA9CC"/>'
        '<path d="M30 34l-8 9 6-2 2 4 4-5zM74 22l-9 11 6-2 3 5 5-5 4 2zM122 40l-7 7 5-1 2 3 4-4z" fill="#fff"/>'
        '<rect y="70" width="160" height="50" fill="#1F6FC4"/><path d="M0 74h160" stroke="#5FA4E6" stroke-width="3"/>'
        '<path d="M20 92h30M70 100h40M110 86h24" stroke="#6CB1EE" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M6 72l7-18 7 18zM16 74l6-14 6 14zM140 72l7-20 7 20z" fill="#2F5D45"/>'))
    SYMS["ph-sled"] = ((0, 0, 160, 120), (
        '<rect width="160" height="120" fill="#BFDDF5"/><path d="M0 40q50-30 160 6v74H0z" fill="#F7FAFD"/>'
        '<path d="M0 70q60-26 160 10" stroke="#D6E4F2" stroke-width="5" fill="none"/>'
        '<path d="M120 46l8-22 8 22zM134 50l7-18 7 18zM12 34l6-18 6 18z" fill="#2F5D45"/>'
        '<path d="M120 30l8-6 8 6M12 22l6-5 6 5" stroke="#fff" stroke-width="2" fill="none"/>'
        '<path d="M48 92h52l6-6" stroke="#B4452F" stroke-width="4" fill="none" stroke-linecap="round"/>'
        '<circle cx="66" cy="74" r="8" fill="#C68A60"/><path d="M58 72q8-12 16 0" fill="#EEE5D2"/><rect x="58" y="80" width="16" height="12" rx="5" fill="#B4452F"/>'
        '<circle cx="84" cy="70" r="8" fill="#8A5536"/><path d="M76 68q8-12 16 0" fill="#474A52"/><rect x="76" y="76" width="16" height="15" rx="5" fill="#2F5B45"/>'
        '<path d="M30 96l14-2M24 88l16 0M34 80l10 2" stroke="#9FC2E4" stroke-width="2" stroke-linecap="round"/>'))
    SYMS["ph-pier"] = ((0, 0, 160, 120), (
        '<linearGradient id="ph-pier-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8E7BD0"/><stop offset=".6" stop-color="#F29A86"/><stop offset="1" stop-color="#FFD1A0"/></linearGradient>'
        '<rect width="160" height="120" fill="url(#ph-pier-sky)"/><circle cx="104" cy="62" r="12" fill="#FFE2B0"/>'
        '<path d="M0 66l24-14 20 10 30-18 26 16 24-10 36 16v8H0z" fill="#7A5A8C"/>'
        '<rect y="68" width="160" height="52" fill="#E99A8E"/><path d="M96 74h18M90 82h28M98 90h12" stroke="#FFE2B0" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M20 120l40-46h20l-20 46z" fill="#6E4B3A"/><path d="M60 74h20" stroke="#4E3428" stroke-width="2"/>'
        '<rect x="60" y="56" width="5" height="16" rx="2" fill="#2E2A36"/><circle cx="62.5" cy="53" r="3.5" fill="#2E2A36"/>'
        '<rect x="68" y="56" width="5" height="16" rx="2" fill="#2E2A36"/><circle cx="70.5" cy="53" r="3.5" fill="#2E2A36"/>'))
    SYMS["ph-cabin"] = ((0, 0, 160, 120), (
        '<rect width="160" height="120" fill="#CFE3F6"/><path d="M0 54l34-26 26 18 30-24 40 30 30-14v62H0z" fill="#A9BFDD"/>'
        '<path d="M34 28l-8 7 5-1 3 4 3-4 5 1zM90 22l-9 8 6-1 3 4 3-4 6 1z" fill="#fff"/>'
        '<rect y="70" width="160" height="50" fill="#F5F8FC"/><rect y="62" width="160" height="10" fill="#2D7CC8"/>'
        '<path d="M52 92V70l26-18 26 18v22z" fill="#8A5A3C"/><path d="M46 72l32-24 32 24" stroke="#F5F8FC" stroke-width="6" fill="none" stroke-linejoin="round"/>'
        '<rect x="70" y="76" width="16" height="16" rx="2" fill="#FFD27A"/><path d="M78 76v16M70 84h16" stroke="#8A5A3C" stroke-width="2"/>'
        '<rect x="92" y="40" width="7" height="14" fill="#6E4B3A"/><path d="M96 36q-4-6 2-10q-4-6 3-9" stroke="#fff" stroke-width="3" fill="none" opacity=".8"/>'
        '<path d="M12 92l9-26 9 26zM128 94l9-28 9 28z" fill="#2F5D45"/><path d="M12 80l9-6 9 6M128 82l9-6 9 6" stroke="#fff" stroke-width="2" fill="none"/>'))
    SYMS["ph-beach"] = ((0, 0, 160, 120), (
        '<rect width="160" height="120" fill="#9FD3F2"/><path d="M0 50l30-16 26 10 34-18 30 16 40-12v24H0z" fill="#8FB0CB"/>'
        '<rect y="52" width="160" height="22" fill="#1F7FC8"/><rect y="70" width="160" height="34" fill="#3CC6C0"/>'
        '<path d="M0 86q40 6 80 0t80 0v34H0z" fill="#9EEBDD"/><path d="M0 104q40 4 80-2t80 2v16H0z" fill="#EED9A8"/>'
        '<ellipse cx="34" cy="86" rx="20" ry="14" fill="#CFC6B6"/><ellipse cx="54" cy="92" rx="14" ry="10" fill="#BDB3A2"/><ellipse cx="126" cy="80" rx="22" ry="15" fill="#D6CEC0"/>'
        '<path d="M140 74l8-40 8 40zM146 70l6-30 6 30z" fill="#2F5D45"/>'))


_snapshots()


def polaroid(x, y, w, rot, ph, P, label=None):
    h = w * 1.06
    pw = w * .88
    s = (f'<g transform="translate({x} {y}) rotate({rot})" filter="url(#{P}sh)">'
         f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" rx="3" fill="#FFFDF8"/>'
         f'<use href="#{ph}" x="{-pw/2}" y="{-h/2 + w*.06}" width="{pw}" height="{pw*.75}"/>')
    if label:
        s += T(0, h / 2 - w * .07, 0, label, w * .085, 500, "#6b6157", "middle", SERIF, 'font-style="italic"')
    return s + '</g>'


# ---------------------------------------------------------------- shared defs and the paper page
def defs(P, mute=None, extra=""):
    m = (f'<filter id="{P}mute" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="{mute}"/>'
         f'<feComponentTransfer><feFuncR type="linear" slope=".94" intercept=".05"/><feFuncG type="linear" slope=".92" intercept=".045"/>'
         f'<feFuncB type="linear" slope=".88" intercept=".04"/></feComponentTransfer></filter>') if mute is not None else ""
    return (f'<defs><clipPath id="{P}pg"><rect x="34" y="34" width="1532" height="832" rx="10"/></clipPath>'
            f'<filter id="{P}sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#3c2814" flood-opacity=".22"/></filter>'
            f'<filter id="{P}grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="4" stitchTiles="stitch"/>'
            f'<feColorMatrix values="0 0 0 0 .42  0 0 0 0 .32  0 0 0 0 .2  0 0 0 .6 0"/></filter>'
            f'<linearGradient id="{P}gut" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3c2814" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#3c2814" stop-opacity=".09"/><stop offset="1" stop-color="#3c2814" stop-opacity="0"/></linearGradient>'
            f'{m}{extra}</defs>')


def page(P, scene, mute=None, extra_defs="", gutter=True):
    g = f'<rect x="770" y="34" width="60" height="832" fill="url(#{P}gut)"/>' if gutter else ""
    return (defs(P, mute, extra_defs) + '<rect width="1600" height="900" fill="#F4EBDB"/>'
            f'<g clip-path="url(#{P}pg)">{scene}{g}</g>'
            f'<rect x="34" y="34" width="1532" height="832" rx="10" fill="none" stroke="{INK}" stroke-opacity=".16" stroke-width="2"/>'
            f'<rect width="1600" height="900" filter="url(#{P}grain)" opacity=".13" style="mix-blend-mode:multiply" pointer-events="none"/>')


def muted(P, inner):
    return f'<g filter="url(#{P}mute)">{inner}</g>'


# ---------------------------------------------------------------- Maya and Sam's living room
ROOM = {
    "night": dict(wall="#7A84A2", wall2="#646E8E", floor="#8C6C55", rug="#8E7A70", trim="#C9C0B4", sky="#1E2A4C", sky2="#33426E"),
    "day": dict(wall="#F4DDC2", wall2="#EBCBA8", floor="#C99A6E", rug="#E3BE96", trim="#FBF1E4", sky="#A8D4F2", sky2="#E3F2FB"),
    "dusk": dict(wall="#EED2B6", wall2="#E0BC9B", floor="#B98B63", rug="#D9B08A", trim="#F8EBDB", sky="#7C6CC0", sky2="#F6A98A"),
}
SOFA = ("#1F8A80", "#18736B", "#26A094")


def ms_room(P, t="night", cx=800, frame=True, lamp=True, win=None):
    c = ROOM[t]
    wx = win if win is not None else max(90, cx - 650)
    s = [f'<linearGradient id="{P}wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["wall"]}"/><stop offset="1" stop-color="{c["wall2"]}"/></linearGradient>',
         f'<linearGradient id="{P}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["sky"]}"/><stop offset="1" stop-color="{c["sky2"]}"/></linearGradient>',
         f'<radialGradient id="{P}lamp"><stop offset="0" stop-color="#FFD79C" stop-opacity=".75"/><stop offset="1" stop-color="#FFB060" stop-opacity="0"/></radialGradient>',
         f'<rect width="1600" height="652" fill="url(#{P}wall)"/>',
         f'<rect y="640" width="1600" height="14" fill="{c["trim"]}"/>',
         f'<rect y="652" width="1600" height="260" fill="{c["floor"]}"/>',
         '<path d="M0 720H1600M0 800H1600" stroke="#000" stroke-opacity=".06" stroke-width="2"/>',
         f'<ellipse cx="{cx}" cy="790" rx="600" ry="74" fill="{c["rug"]}"/>']
    # window with the mountains outside (a quiet foreshadow, as in E)
    s.append(f'<rect x="{wx}" y="96" width="320" height="350" rx="14" fill="{c["trim"]}"/>'
             f'<rect x="{wx+16}" y="112" width="288" height="318" rx="4" fill="url(#{P}sky)"/>')
    if t == "night":
        s.append(f'<circle cx="{wx+230}" cy="172" r="24" fill="#F3EBCF"/><circle cx="{wx+240}" cy="166" r="22" fill="{c["sky"]}"/>'
                 + "".join(f'<circle cx="{wx+x}" cy="{y}" r="{r}" fill="#F3EBCF"/>' for x, y, r in [(60, 150, 2), (110, 200, 1.6), (170, 140, 2.2), (270, 240, 1.6), (90, 260, 1.4), (200, 230, 1.8)]))
        mt, mt2 = "#2E3A60", "#3E4C78"
    else:
        s.append(f'<circle cx="{wx+236}" cy="190" r="22" fill="#FFE2A8" opacity=".9"/>')
        mt, mt2 = ("#8EA8CF", "#A9BEDD") if t == "day" else ("#6E5A9E", "#8A72B4")
    s.append(f'<path d="M{wx+16} 360l60-70 40 34 56-62 54 56 40-30 38 36v86H{wx+16}z" fill="{mt2}"/>'
             f'<path d="M{wx+16} 386l44-44 46 36 50-48 56 52 50-34 46 36v46H{wx+16}z" fill="{mt}"/>'
             f'<path d="M{wx+172} 262l-14 16 9-3 5 7 7-7 9 3zM{wx+76} 290l-11 13 8-3 4 6 6-5z" fill="#F6F8FB" opacity=".9"/>'
             f'<rect x="{wx+157}" y="112" width="8" height="318" fill="{c["trim"]}"/><rect x="{wx+16}" y="268" width="288" height="7" fill="{c["trim"]}"/>'
             f'<rect x="{wx-10}" y="440" width="340" height="14" rx="6" fill="{c["trim"]}"/>')
    if frame:
        fx = cx + 380
        s.append(f'<rect x="{fx}" y="150" width="150" height="186" rx="6" fill="{c["trim"]}"/><rect x="{fx+12}" y="162" width="126" height="162" rx="2" fill="#FFF1DE"/>'
                 f'<circle cx="{fx+75}" cy="214" r="22" fill="#F59A2E"/><path d="M{fx+12} 290c26-30 50-34 74-16s34 6 52-6v56H{fx+12}z" fill="#087F7B"/>'
                 f'<path d="M{fx+12} 306c30-14 60-10 86 0s30 2 40 0v18H{fx+12}z" fill="#A445D8"/>')
    if lamp:
        lx = cx + 520
        s.append((f'<circle cx="{lx}" cy="330" r="300" fill="url(#{P}lamp)"/>' if t != "day" else "") +
                 f'<rect x="{lx-3}" y="330" width="6" height="320" fill="#3A3340"/><ellipse cx="{lx}" cy="652" rx="34" ry="8" fill="#3A3340"/>'
                 f'<path d="M{lx-46} 344h92l-18-62h-56z" fill="#F7B267"/><ellipse cx="{lx}" cy="344" rx="46" ry="6" fill="#FFE2B0"/>')
    # plant
    px = max(70, cx - 640) if win is None else cx + 640
    s.append(f'<g transform="translate({px} 0)">'
             '<path d="M0 520c-8-40 18-60 32-66-6 26 2 44-10 70zM28 560c-6-52 34-78 50-82-10 34-8 58-32 84zM10 586c-28-26-34-58-26-78 16 18 26 40 32 74zM44 598c6-44 40-62 58-62-16 26-20 44-48 66z" fill="#2F8F6B"/>'
             '<path d="M18 532c6-28 24-44 40-52-8 24-14 40-32 58zM2 572c-16-32-10-52 0-66 8 22 10 40 6 66z" fill="#45AD7F"/>'
             '<path d="M-6 604h76l-9 50H3z" fill="#E07A4F"/><rect x="-9" y="598" width="82" height="14" rx="5" fill="#C8643B"/></g>')
    # sofa
    a, b, cc = SOFA
    s.append(f'<ellipse cx="{cx}" cy="652" rx="390" ry="14" fill="#2a1408" opacity=".16"/>'
             f'<rect x="{cx-360}" y="392" width="720" height="190" rx="44" fill="{b}"/>'
             f'<rect x="{cx-332}" y="410" width="320" height="130" rx="32" fill="{a}"/><rect x="{cx+12}" y="410" width="320" height="130" rx="32" fill="{a}"/>'
             f'<rect x="{cx-344}" y="512" width="688" height="66" rx="20" fill="{cc}"/>'
             f'<rect x="{cx-352}" y="566" width="704" height="64" rx="16" fill="{b}"/>'
             f'<rect x="{cx-404}" y="470" width="104" height="164" rx="36" fill="{a}"/><rect x="{cx+300}" y="470" width="104" height="164" rx="36" fill="{a}"/>'
             f'<rect x="{cx-340}" y="628" width="16" height="22" rx="4" fill="#7A5236"/><rect x="{cx+324}" y="628" width="16" height="22" rx="4" fill="#7A5236"/>')
    return "".join(s)


def coffee_table(cx=800, y=700, depth=28, color="#B07A4E", edge="#8F5F3A"):
    return (f'<rect x="{cx-240}" y="{y+depth}" width="18" height="{150-depth}" rx="4" fill="{edge}"/><rect x="{cx+222}" y="{y+depth}" width="18" height="{150-depth}" rx="4" fill="{edge}"/>'
            f'<path d="M{cx-250} {y}h500l26 {depth}H{cx-276}z" fill="{color}"/><rect x="{cx-276}" y="{y+depth}" width="552" height="16" rx="3" fill="{edge}"/>'
            f'<ellipse cx="{cx}" cy="{y+164}" rx="270" ry="12" fill="#2a1408" opacity=".12"/>')


# ---------------------------------------------------------------- props
NOTE_COLORS = ["#F2C94C", "#EB5757", "#27AE60", "#2D9CDB", "#F2994A", "#BB6BD9", "#F2C94C", "#EB5757"]


def book(w=100, fat=True):
    """An open guidebook centred on (0, 0), seen from the front, width w."""
    k = w / 200
    lines = "".join(f'<path d="M{-86+i%2*4} {-14+i*6}q30-4 {70-(i*13)%22} 0" stroke="#B9AE9C" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
                    f'<path d="M{12} {-12+i*6}q30-4 {66-(i*7)%20} 2" stroke="#B9AE9C" stroke-width="2.2" fill="none" stroke-linecap="round"/>' for i in range(7))
    thick = '<path d="M-100 30Q-50 20 0 33Q50 20 100 30L100 42Q50 32 0 45Q-50 32 -100 42Z" fill="#E6D8BE"/><path d="M-98 36Q-50 26 0 39Q50 26 98 36" stroke="#CDBEA2" stroke-width="1" fill="none"/>' if fat else ""
    return (f'<g transform="scale({k})"><path d="M-106 44L106 44L98 -30L-98 -30Z" fill="#23324F"/>{thick}'
            '<path d="M-95 28Q-48 17 0 31L0 -24Q-46 -38 -91 -28Z" fill="#FFF9EE"/><path d="M95 28Q48 17 0 31L0 -24Q46 -38 91 -28Z" fill="#FFFDF6"/>'
            f'<path d="M0 -24V31" stroke="#DCCDB4" stroke-width="2.2"/>{lines}<rect x="-80" y="-24" width="40" height="5" rx="2" fill="#23324F"/></g>')


def book_notes(w=100, n=7, seed=1):
    k = w / 200
    rnd = random.Random(seed)
    xs = [-80, -58, -30, 18, 44, 70, 86][:n]
    s = ""
    for i, x in enumerate(xs):
        y = -46 + rnd.random() * 6 if abs(x) < 86 else -20
        s += f'<rect x="{x}" y="{y:.1f}" width="13" height="22" rx="2" fill="{NOTE_COLORS[i % 8]}" transform="rotate({rnd.uniform(-8, 8):.1f} {x+6} {y+20:.1f})"/>'
    s += f'<rect x="96" y="-6" width="20" height="12" rx="2" fill="{NOTE_COLORS[3]}"/><rect x="-114" y="4" width="20" height="12" rx="2" fill="{NOTE_COLORS[1]}"/>'
    return f'<g transform="scale({k})">{s}</g>'


def laptop(w=110):
    k = w / 200
    tabs = "".join(f'<path d="M{-89+i*12.6:.1f} -96l2-8h9l2 8z" fill="{"#FFFFFF" if i == 9 else "#B4BAC4"}" stroke="#8E95A1" stroke-width=".8"/>' for i in range(14))
    lines = "".join(f'<rect x="-80" y="{-74+i*10}" width="{60+(i*37)%90}" height="4" rx="2" fill="#C2C7CF"/>' for i in range(6))
    return (f'<g transform="scale({k})"><rect x="-98" y="-112" width="196" height="122" rx="9" fill="#2B2D33"/>'
            f'<rect x="-90" y="-104" width="180" height="106" rx="3" fill="#EEF1F5"/><rect x="-90" y="-104" width="180" height="8" fill="#DADEE5"/>{tabs}'
            f'<rect x="-84" y="-92" width="140" height="7" rx="3.5" fill="#fff"/>{lines}'
            '<rect x="20" y="-74" width="62" height="46" rx="3" fill="#D6DCE4"/>'
            '<path d="M-112 12h224l-10 14h-204z" fill="#9AA0AA"/><path d="M-30 12h60l-4 5h-52z" fill="#7C828C"/></g>')


def phone(x, y, w, h, rot=0, screen="", P="", body="#17161B", glow=False):
    r = w * .16
    g = f'<rect x="{-w/2-30}" y="{-h/2-30}" width="{w+60}" height="{h+60}" rx="{r+30}" fill="#FFF3D6" opacity=".45" filter="url(#{P}blur)"/>' if glow else ""
    return (f'<g transform="translate({x} {y}) rotate({rot})">{g}<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" rx="{r}" fill="{body}"/>'
            f'<rect x="{-w/2+w*.05}" y="{-h/2+w*.05}" width="{w*.9}" height="{h-w*.1}" rx="{r*.8}" fill="#FBF8F3"/>'
            f'<rect x="{-w*.16}" y="{-h/2+w*.08}" width="{w*.32}" height="{w*.07}" rx="{w*.035}" fill="{body}"/>'
            f'<g transform="translate({-w/2+w*.05} {-h/2+w*.05})">{screen}</g></g>')


def mug(x, y, c="#F4EFE6", band="#E0204E"):
    return (f'<g transform="translate({x} {y})"><path d="M18 8q14 0 14 12t-14 12" stroke="{c}" stroke-width="6" fill="none"/>'
            f'<rect x="-18" y="0" width="38" height="40" rx="8" fill="{c}"/><rect x="-18" y="10" width="38" height="7" fill="{band}"/>'
            f'<ellipse cx="1" cy="2" rx="17" ry="4" fill="#5A3A28"/></g>')


def notepad(x, y, rot=-8):
    sc = "".join(f'<path d="M{-40} {-22+i*12}q12-6 24 0t24 0t20 -2" stroke="#3D4D7A" stroke-width="2" fill="none" stroke-linecap="round"/>' for i in range(4))
    return (f'<g transform="translate({x} {y}) rotate({rot})"><rect x="-52" y="-38" width="104" height="76" rx="4" fill="#FFF8DC"/>'
            f'<rect x="-52" y="-38" width="104" height="10" fill="#E8D9A8"/>{sc}<path d="M10 22l40-12" stroke="#2B2D33" stroke-width="4" stroke-linecap="round"/></g>')


def folded_map(x, y, w=300, rot=-6):
    h = w * .42
    p = w / 3
    return (f'<g transform="translate({x} {y}) rotate({rot})">'
            f'<path d="M0 0l{p} -10l{p} 10l{p} -10v{h}l{-p} 10l{-p} -10l{-p} 10z" fill="#EFE6D0"/>'
            f'<path d="M{p} -10v{h}M{2*p} 0v{h}" stroke="#CDBE9E" stroke-width="2"/>'
            f'<path d="M20 {h*.6}q60 -50 120 -10t130 -30" stroke="#C98B3A" stroke-width="4" fill="none" stroke-dasharray="10 6"/>'
            f'<ellipse cx="{w*.62}" cy="{h*.45}" rx="34" ry="22" fill="#9DBFDB"/></g>')


def widget(P, x, y, w, h, color, ic, big, small, fg="#fff", big_size=34):
    sub = T(x + 86, y + h / 2 + 30, 0, small, 20, 500, fg, extra='opacity=".88"') if small else ""
    by = y + h / 2 + (2 if small else 12)
    return (f'<g filter="url(#{P}sh)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{color}"/></g>'
            f'<circle cx="{x+46}" cy="{y+h/2}" r="28" fill="#fff" opacity=".2"/>' + icon(ic, x + 30, y + h / 2 - 16, 32, fg, 2.2)
            + T(x + 86, by, 0, big, big_size, 750, fg) + sub)


def pop_marks(x, y, color=INK, rot=0):
    return (f'<g transform="translate({x} {y}) rotate({rot})" stroke="{color}" stroke-width="3" stroke-linecap="round" opacity=".55">'
            '<path d="M0 -14v-12M12 -8l9-8M-12 -8l-9-8"/></g>')


# ---------------------------------------------------------------- the dotted globe (E's land mask, ported)
def _mask():
    src = (HERE.parent.parent / "e.html").read_text()
    b64 = re.search(r"b64: '([A-Za-z0-9+/=]+)'", src).group(1)
    return base64.b64decode(b64)


_BITS = None


def _dots():
    global _BITS
    _BITS = _BITS or _mask()
    S, LAT0, ROWS, COLS = 1.5, -58.5, 96, 240
    out = []
    for r in range(ROWS):
        lat = LAT0 + r * S
        st = S / max(math.cos(math.radians(lat)), .12)
        lon = -180 + st / 2
        while lon < 180:
            c = min(COLS - 1, int((lon + 180) // S))
            i = r * COLS + c
            if (_BITS[i >> 3] >> (i & 7)) & 1:
                out.append(_vec(lon, lat))
            lon += st
    return out


def _vec(lon, lat):
    l, p = math.radians(lon), math.radians(lat)
    return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))


def _view(v, lon0, lat0):
    cl, sl = math.cos(math.radians(lon0)), math.sin(math.radians(lon0))
    cp, sp = math.cos(math.radians(lat0)), math.sin(math.radians(lat0))
    x1 = v[0] * cl + v[1] * sl
    y1 = -v[0] * sl + v[1] * cl
    z1 = v[2]
    return (y1, -x1 * sp + z1 * cp, x1 * cp + z1 * sp)


PLACES = {"tahoe": (-120, 39), "lisbon": (-9.1, 38.7), "banff": (-115.6, 51.2), "oaxaca": (-96.7, 17), "marrakech": (-8, 31.6),
          "reykjavik": (-21.9, 64.1), "capetown": (18.4, -33.9), "nyc": (-74, 40.7), "cusco": (-72, -13.5), "patagonia": (-73, -50),
          "nairobi": (36.8, -1.3), "oslo": (10.7, 59.9), "rio": (-43.2, -22.9), "paris": (2.35, 48.85), "rome": (12.5, 41.9),
          "cairo": (31.2, 30), "mexico": (-99.1, 19.4), "vancouver": (-123.1, 49.3), "havana": (-82.4, 23.1), "accra": (-0.2, 5.6),
          "athens": (23.7, 38), "edinburgh": (-3.2, 55.9), "zanzibar": (39.2, -6.2), "santiago": (-70.6, -33.4), "istanbul": (29, 41)}


def globe(P, cx, cy, r, lon0, lat0, arcs=(), pins=(), planes=()):
    dots = _dots()
    buckets = {0: [], 1: [], 2: []}
    for v in dots:
        q = _view(v, lon0, lat0)
        if q[2] <= .02:
            continue
        b = 0 if q[2] < .35 else 1 if q[2] < .7 else 2
        rr = r * .0098 * (.55 + .45 * q[2])
        x, y = cx + r * q[0], cy - r * q[1]
        buckets[b].append(f"M{x-rr:.1f} {y:.1f}a{rr:.1f} {rr:.1f} 0 1 0 {2*rr:.1f} 0a{rr:.1f} {rr:.1f} 0 1 0 {-2*rr:.1f} 0")
    s = [f'<radialGradient id="{P}oc" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#4A92E8"/><stop offset=".6" stop-color="#1F57B8"/><stop offset="1" stop-color="#0F2F72"/></radialGradient>'
         f'<radialGradient id="{P}halo"><stop offset=".78" stop-color="#fff" stop-opacity=".7"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
         f'<radialGradient id="{P}gsh" cx=".35" cy=".3" r=".75"><stop offset=".6" stop-color="#050f32" stop-opacity="0"/><stop offset="1" stop-color="#050f32" stop-opacity=".45"/></radialGradient>'
         f'<circle cx="{cx}" cy="{cy}" r="{r*1.24}" fill="url(#{P}halo)"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{P}oc)"/>']
    for b, op in ((0, .4), (1, .7), (2, .97)):
        s.append(f'<path d="{"".join(buckets[b])}" fill="#EAF2FF" opacity="{op}"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{P}gsh)"/>')

    def prj(lon, lat, h=1.0):
        q = _view(_vec(lon, lat), lon0, lat0)
        return cx + r * h * q[0], cy - r * h * q[1], q[2]

    for (a, b, col, w) in arcs:
        va, vb = _vec(*PLACES[a]), _vec(*PLACES[b])
        om = math.acos(max(-1, min(1, sum(i * j for i, j in zip(va, vb)))))
        so = math.sin(om) or 1
        pts = []
        for i in range(41):
            u = i / 40
            A, B = math.sin((1 - u) * om) / so, math.sin(u * om) / so
            v = [A * va[k] + B * vb[k] for k in range(3)]
            h = 1 + (.04 + .14 * om / math.pi) * math.sin(math.pi * u)
            q = _view(v, lon0, lat0)
            vis = q[2] > 0 or (q[0] ** 2 + q[1] ** 2) * h * h > 1.0005
            pts.append((cx + r * h * q[0], cy - r * h * q[1], vis))
        d, pen = "", False
        for x, y, vis in pts:
            if vis:
                d += f"{'L' if pen else 'M'}{x:.1f} {y:.1f}"
                pen = True
            else:
                pen = False
        s.append(f'<path d="{d}" stroke="{col}" stroke-width="{w}" fill="none" stroke-linecap="round" stroke-dasharray="{w*.2:.1f} {w*1.9:.1f}"/>')
    for (n, col, big) in pins:
        x, y, z = prj(*PLACES[n])
        if z < .05:
            continue
        R = r * (.034 if big else .022)
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{R*1.9:.1f}" fill="{col}" opacity=".25"/><circle cx="{x:.1f}" cy="{y:.1f}" r="{R:.1f}" fill="{col}" stroke="#fff" stroke-width="{R*.35:.1f}"/>')
    return "".join(s), prj


def paper_plane(x, y, s=1, rot=0):
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            '<path d="M-60 6L60 -30L-20 34Z" fill="#FFFFFF"/><path d="M-60 6L60 -30L-8 10Z" fill="#E9EEF4"/>'
            '<path d="M-8 10L60 -30L-20 34Z" fill="#D4DCE6"/><path d="M-8 10L-14 40L-2 16Z" fill="#B9C4D2"/>'
            f'<path d="M-60 6L60 -30L-20 34Z" fill="none" stroke="{INK}" stroke-opacity=".35" stroke-width="1.5" stroke-linejoin="round"/></g>')


def stamp(P, x, y, r, rot, color, name, sub, sid):
    return (f'<g transform="translate({x} {y}) rotate({rot})" filter="url(#{P}ink)" opacity=".9" style="mix-blend-mode:multiply">'
            f'<circle r="{r}" fill="none" stroke="{color}" stroke-width="9"/><circle r="{r-16}" fill="none" stroke="{color}" stroke-width="3"/>'
            f'<path id="{P}{sid}" d="M{-r+40} 0A{r-40} {r-40} 0 0 1 {r-40} 0" fill="none"/>'
            f'<text font-size="30" font-weight="800" letter-spacing="7" fill="{color}" {SANS}><textPath href="#{P}{sid}" startOffset="50%" text-anchor="middle">BOOKED ON</textPath></text>'
            f'<path d="M{-r+34} 16H{r-34}M{-r+34} 70H{r-34}" stroke="{color}" stroke-width="3"/>'
            + T(0, 56, 0, name, 46 if len(name) < 8 else 38, 850, color, "middle")
            + T(0, 104, 0, sub, 20, 700, color, "middle", extra='letter-spacing="2"')
            + "".join(f'<circle cx="{a}" cy="{b}" r="{c}" fill="{color}"/>' for a, b, c in [(r + 22, -30, 5), (r + 40, -10, 3), (-r - 18, 40, 4), (r * .6, r + 22, 3.5), (-r * .7, -r - 14, 3)])
            + '</g>')


def anchor_note(who, x, y, w, h):
    return f'<rect data-face="{who}" x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="none"/>'


# ================================================================= the panels
def p01(P, mode):
    cx = 800
    my = 370
    mb = book(150)
    maya = fig("maya", "home", cx - 115, my, 1.75, expr="tired", head_rot=5, mid=f'<g transform="translate(0 84)">{mb}</g>',
               arms=[dict(pts=[(-28, 10), (-42, 56), (-36, 82)]), dict(pts=[(28, 10), (42, 56), (36, 82)])])
    sam = fig("sam", "home", cx + 115, my, 1.75, expr="tired", head_rot=-4, mid=f'<g transform="translate(0 94)">{laptop(118)}</g>',
              arms=[dict(pts=[(-31, 10), (-44, 60), (-34, 96)]), dict(pts=[(31, 10), (44, 60), (34, 96)])])
    table = (coffee_table(cx) + mug(cx - 150, 662) + mug(cx + 40, 664, "#DCE6F0", "#3D4D7A") + notepad(cx + 170, 690, -6)
             + folded_map(150, 790, 330, -8))
    base = ms_room(P, "night", cx) + maya + sam + table
    night = '<rect width="1600" height="900" fill="#141a33" opacity=".22"/>'
    notes = (f'<g transform="translate({cx-115} {my}) scale(1.75) translate(0 84)">{book_notes(150, seed=3)}</g>'
             + "".join(f'<rect x="{x}" y="{y}" width="34" height="34" rx="3" fill="{c}" transform="rotate({a} {x+17} {y+17})"/>'
                       for x, y, c, a in [(cx - 90, 690, "#F2C94C", -12), (cx + 90, 700, "#EB5757", 8), (cx - 40, 712, "#2D9CDB", 4), (300, 760, "#27AE60", -6)]))
    return page(P, muted(P, base + night) + notes, mute=.2)


def p02(P, mode):
    rnd = random.Random(7)
    # the room behind, dim
    back = ms_room(P, "night", 800, frame=False) + '<rect width="1600" height="900" fill="#141a33" opacity=".25"/>'
    s = 3.1
    maya = fig("maya", "home", 360, 300 + 32 * s, s, view="front", head_view="3q", expr="puzzled", arms=[], head_rot=4)
    sam = fig("sam", "home", 1240, 300 + 32 * s, s, view="front", head_view="3q", expr="puzzled", flip=True, arms=[], head_rot=-3)
    pages = [f'<path d="M70 920L92 412Q440 360 800 404L800 920Z" fill="#FFF9EE"/>',
             f'<path d="M1530 920L1508 412Q1160 360 800 404L800 920Z" fill="#FFFDF6"/>',
             f'<path d="M58 930L80 400Q440 346 800 392Q1160 346 1520 400L1542 930" fill="none" stroke="#23324F" stroke-width="16"/>',
             f'<linearGradient id="{P}gut2" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8a7a60" stop-opacity="0"/><stop offset=".5" stop-color="#8a7a60" stop-opacity=".35"/><stop offset="1" stop-color="#8a7a60" stop-opacity="0"/></linearGradient>',
             f'<rect x="740" y="396" width="120" height="520" fill="url(#{P}gut2)"/>']
    txt = []
    for (x0, x1, y0) in [(140, 440, 520), (470, 760, 470), (850, 1130, 470), (1160, 1460, 680)]:
        y = y0
        while y < 820:
            w = (x1 - x0) * rnd.uniform(.72, 1)
            if rnd.random() < .08:
                w *= .4
            txt.append(f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="5" rx="2.5" fill="#A39A8C"/>')
            y += 15 if rnd.random() > .1 else 26
    txt.append(T(140, 470, 0, "Lake Tahoe", 46, 400, "#3a332b", font=SERIF))
    txt.append(T(142, 500, 0, "Getting there · When to go · Chains · Permits", 15, 400, "#6b6157", font=SERIF, extra='font-style="italic"'))
    txt.append(T(1160, 470, 0, "Where to stay", 26, 400, "#3a332b", font=SERIF))
    # a tiny map
    txt.append('<rect x="1160" y="490" width="300" height="168" rx="4" fill="#F1EADB" stroke="#B9AE9C" stroke-width="2"/>'
               '<path d="M1290 516q34 6 30 50t-26 74q-26-10-24-60t20-64z" fill="#C9D3DC" stroke="#8C9AA6" stroke-width="2"/>'
               '<path d="M1170 600q60-20 110-10M1330 560q60 10 120 -20M1300 640v20" stroke="#8C7F6A" stroke-width="2" stroke-dasharray="6 5" fill="none"/>'
               + "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="#6b6157"/>' for x, y in [(1200, 594), (1420, 548), (1300, 520), (1312, 640)]))
    txt.append(T(150, 846, 0, "¹ Chains may be required on US-50 and I-80 from November to April; check before you go.", 13, 400, "#8a8073", font=SERIF, extra='font-style="italic"'))
    txt.append(T(740, 846, 0, "214", 14, 400, "#8a8073", "end", font=SERIF) + T(860, 846, 0, "215", 14, 400, "#8a8073", font=SERIF))
    hands = "".join(f'<g transform="translate({x} {y}) rotate({a})">' + "".join(f'<rect x="{fx}" y="{fy}" width="13" height="30" rx="6.5" fill="{c}"/><path d="M{fx+3} {fy+22}h7" stroke="{d}" stroke-width="1.6" stroke-linecap="round"/>' for fx, fy in [(-28, -10), (-14, -14), (0, -14), (14, -10)]) + '</g>'
                    for x, y, a, c, d in [(250, 388, -6, PAL["maya"]["skin"], PAL["maya"]["shade"]), (520, 372, 4, PAL["maya"]["skin"], PAL["maya"]["shade"]),
                                          (1080, 372, -4, PAL["sam"]["skin"], PAL["sam"]["shade"]), (1350, 388, 6, PAL["sam"]["skin"], PAL["sam"]["shade"])])
    note = '<rect x="1468" y="560" width="40" height="60" rx="3" fill="#F2C94C" transform="rotate(4 1488 590)"/><rect x="1470" y="660" width="40" height="50" rx="3" fill="#EB5757" transform="rotate(-3 1490 685)"/>'
    return page(P, muted(P, back + maya + sam + "".join(pages) + "".join(txt) + hands) + note, mute=.18)


def p03(P, mode):
    cx, my = 800, 370
    gscreen = (f'<rect width="54" height="96" fill="#FBF8F3"/>{logo(27, 26, .9)}'
               + T(27, 52, 0, "Lake Tahoe", 7, 700, INK, "middle") + '<rect x="7" y="62" width="40" height="12" rx="6" fill="#D2401C"/>'
               + T(27, 70.5, 0, "Book it", 6, 700, "#fff", "middle"))
    ph = phone(0, 0, 60, 106, 0, gscreen)
    sam = fig("sam", "home", cx + 110, my, 1.75, expr="grin", head_rot=-6,
              mid=f'<g transform="translate(-22 40) rotate(-8) scale(.78)">{ph}</g>',
              arms=[dict(pts=[(-31, 10), (-46, 60), (-28, 66)]), dict(pts=[(31, 10), (46, 66), (-12, 38)], finger=(-6, -4))])
    maya = fig("maya", "home", cx - 120, my, 1.75, head_view="3q", expr="surprised", head_rot=10, lean=6,
               arms=[dict(pts=[(-28, 10), (-40, 56), (-24, 86)]), dict(pts=[(28, 10), (44, 50), (52, 70)])])
    bk = f'<g transform="translate({cx} 684)">{book(230, fat=True)}</g>'
    base = ms_room(P, "night", cx) + maya + sam + coffee_table(cx) + bk + mug(cx + 200, 664)
    night = '<rect width="1600" height="900" fill="#141a33" opacity=".2"/>'
    # ink lifting off the page, blushing into colour as it rises
    rib = [f'<linearGradient id="{P}rib" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#6b6157"/><stop offset=".55" stop-color="#5E8FB8"/><stop offset="1" stop-color="#3FA57D"/></linearGradient>']
    paths = [f"M{cx-60} 690C{cx-120} 640 {cx-260} 660 {cx-300} 600S{cx-250} 520 {cx-300} 500",
             f"M{cx-10} 684C{cx-30} 620 {cx+30} 600 {cx} 560S{cx-30} 500 {cx} 470",
             f"M{cx+40} 688C{cx+120} 650 {cx+230} 670 {cx+270} 610S{cx+250} 540 {cx+300} 520",
             f"M{cx+70} 692C{cx+160} 700 {cx+330} 690 {cx+380} 640S{cx+400} 570 {cx+440} 560"]
    for i, d in enumerate(paths):
        rib.append(f'<path d="{d}" stroke="url(#{P}rib)" stroke-width="{5-i%2}" fill="none" stroke-linecap="round"/>')
        rib.append(f'<path d="{d}" stroke="#fff" stroke-opacity=".5" stroke-width="1.4" fill="none" stroke-dasharray="3 10"/>')
    # what the ribbons turn into: mountains, a cabin, a lake with pines
    rib.append(f'<g transform="translate({cx-300} 470)" opacity=".95"><path d="M-60 30l34-44 20 20 26-34 40 58z" fill="#8FA9CC"/><path d="M-26 -14l-8 10 5-2 3 4 4-4zM20 -28l-9 11 6-2 3 5 5-5z" fill="#fff"/></g>')
    rib.append(f'<g transform="translate({cx} 440)"><path d="M-26 20V2l26-18 26 18v18z" fill="#A0704C"/><path d="M-32 4l32-24 32 24" stroke="#fff" stroke-width="5" fill="none"/><rect x="-6" y="6" width="12" height="12" fill="#FFD27A"/></g>')
    rib.append(f'<g transform="translate({cx+310} 500)"><ellipse rx="54" ry="16" fill="#5FA4E6"/><path d="M-60 0l10-30 10 30zM-44 2l8-22 8 22zM44 0l10-30 10 30z" fill="#3E8A62"/></g>')
    rib.append(f'<g transform="translate({cx+450} 540)"><path d="M0 0l12-36 12 36zM18 4l9-26 9 26z" fill="#3E8A62"/></g>')
    glow = (f'<radialGradient id="{P}pg2"><stop offset="0" stop-color="#FFF1C8" stop-opacity=".55"/><stop offset="1" stop-color="#FFF1C8" stop-opacity="0"/></radialGradient>'
            f'<circle cx="{cx+80}" cy="{my+60}" r="90" fill="url(#{P}pg2)"/>')
    return page(P, muted(P, base + night) + glow + "".join(rib), mute=.22)


def p04(P, mode):
    bg = (f'<radialGradient id="{P}bl"><stop offset="0" stop-color="#FFE4CC"/><stop offset="1" stop-color="#FFE4CC" stop-opacity="0"/></radialGradient>'
          f'<rect width="1600" height="900" fill="#FBF3E7"/><circle cx="800" cy="380" r="520" fill="url(#{P}bl)"/>'
          '<circle cx="260" cy="200" r="140" fill="#CFE3FA" opacity=".5"/><circle cx="1360" cy="210" r="150" fill="#D8F0E4" opacity=".55"/>'
          '<circle cx="1300" cy="520" r="120" fill="#FBE0D6" opacity=".6"/><circle cx="300" cy="520" r="120" fill="#FCEBC8" opacity=".6"/>')
    scr_w, scr_h = 300 * .9, 630 - 30
    screen = (T(24, 40, 0, "9:41", 15, 700, INK) + T(24, 92, 0, "Lake Tahoe", 34, 800, INK) + T(24, 120, 0, "Dec 12–16 · 4 nights · Maya &amp; Sam", 15, 500, "#6b6157")
              + '<rect x="16" y="138" width="238" height="300" rx="22" fill="#fff" stroke="#EDE5D8"/>'
              + '<svg x="16" y="138" width="238" height="170" viewBox="0 0 160 114.3" preserveAspectRatio="xMidYMid slice"><use href="#ph-cabin" width="160" height="120"/></svg>'
              + T(32, 340, 0, "Lakeside cabin", 22, 750, INK) + T(32, 364, 0, "Tahoe City · sleeps 4", 15, 500, "#6b6157")
              + '<rect x="32" y="384" width="206" height="40" rx="20" fill="#D2401C"/>' + T(135, 410, 0, "Book on Vrbo", 17, 700, "#fff", "middle")
              + '<rect x="16" y="456" width="112" height="44" rx="14" fill="#F3EDE3"/><rect x="142" y="456" width="112" height="44" rx="14" fill="#F3EDE3"/>'
              + T(72, 484, 0, "Day 1", 15, 700, INK, "middle") + T(198, 484, 0, "Day 2", 15, 700, INK, "middle")
              + '<rect x="16" y="514" width="238" height="44" rx="22" fill="#17161B"/>' + T(135, 542, 0, "Everything in view", 15, 700, "#fff", "middle"))
    ph = phone(800, 385, 300, 630, 0, screen, P)
    L, R = 170, 1080
    W = 350
    ws = [widget(P, L, 80, W, 130, "#2F7FE0", "i-snow", "28°F", "Snow · Saturday", big_size=44),
          widget(P, L, 245, W, 130, "#EE6A4C", "i-flight", "SFO → RNO", "$129 · Fri 8:05 am"),
          widget(P, L, 410, W, 130, "#F2B33D", "i-chain", "Chains required", "on US-50 · snow tonight", fg="#2b1a05", big_size=30),
          widget(P, R, 80, W, 130, "#138A72", "i-car", "2 h 10 min drive", "SFO to the cabin", big_size=30),
          widget(P, R, 245, W, 130, "#2F7A45", "i-trail", "6 trails nearby", "Eagle Falls · 1.2 mi", big_size=32),
          widget(P, R, 410, W, 130, "#C9402C", "i-stay", "Cabin $210/night", "4 nights · $840", big_size=30),
          widget(P, 560, 728, 480, 116, "#E39A2B", "i-coins", "$1,840 trip", "$368 a day for two", fg="#2b1a05")]
    # a tiny route map in the drive widget, and a mini bar chart in the money widget
    extra = ("".join(f'<rect x="{930+i*20}" y="{810-h}" width="12" height="{h}" rx="3" fill="#2b1a05" opacity=".55"/>' for i, h in enumerate([22, 34, 18, 44])))
    conns = "".join(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{INK}" stroke-opacity=".22" stroke-width="2.5" stroke-dasharray="2 8" stroke-linecap="round"/>'
                    for x1, y1, x2, y2 in [(520, 145, 650, 210), (520, 310, 650, 320), (520, 475, 650, 430), (1080, 145, 950, 210), (1080, 310, 950, 320), (1080, 475, 950, 430), (800, 728, 800, 700)])
    pops = pop_marks(176, 84, "#2F7FE0", -30) + pop_marks(1424, 84, "#138A72", 30) + pop_marks(1424, 414, "#C9402C", 40) + pop_marks(176, 414, "#F2B33D", -40) + pop_marks(566, 732, "#E39A2B", -30)
    s = 2.25
    maya = fig("maya", "home", 260, 815, s, head_view="3q", expr="delighted", head_rot=-12, arms=[dict(pts=[(28, 10), (52, -10), (60, -40)])])
    sam = fig("sam", "home", 1340, 815, s, head_view="3q", expr="delighted", head_rot=-12, flip=True, arms=[])
    return page(P, bg + conns + ph + "".join(ws) + extra + pops + maya + sam)


def p05(P, mode):
    cx, my = 800, 370
    scr = ('<rect width="54" height="96" fill="#FBF8F3"/>' + T(27, 22, 0, "Lake Tahoe", 7, 800, INK, "middle")
           + '<rect x="6" y="30" width="42" height="26" rx="5" fill="#2F7FE0"/><rect x="6" y="60" width="20" height="14" rx="4" fill="#EE6A4C"/><rect x="28" y="60" width="20" height="14" rx="4" fill="#C9402C"/>'
           + '<rect x="6" y="80" width="42" height="11" rx="5.5" fill="#D2401C"/>' + T(27, 88, 0, "Book", 6.5, 800, "#fff", "middle"))
    ph = phone(0, 0, 60, 106, 0, scr)
    maya = fig("maya", "home", cx - 115, my, 1.75, expr="grin", head_rot=4, mid=f'<g transform="translate(14 46) rotate(6) scale(.6)">{ph}</g>',
               arms=[dict(pts=[(-28, 10), (-36, 60), (8, 68)]), dict(pts=[(28, 10), (40, 56), (16, 50)], finger=(-3, -6))])
    sam = fig("sam", "home", cx + 115, my, 1.75, expr="delighted", head_rot=-5,
              arms=[dict(pts=[(-31, 10), (-44, 60), (-30, 92)]), dict(pts=[(31, 10), (70, 10), (62, -26)], fist=True)])
    folder = (f'<g transform="translate({cx-10} 700) rotate(-4)" filter="url(#{P}sh)"><path d="M-130 -40h90l12 -14h60l12 14h86v96h-260z" fill="#D9B98A"/>'
              '<g transform="rotate(-10 -40 -50)"><rect x="-110" y="-78" width="150" height="56" rx="6" fill="#fff"/><rect x="-110" y="-78" width="150" height="14" rx="6" fill="#2F7FE0"/>'
              + T(-35, -36, 0, "SFO → RNO", 17, 800, INK, "middle") + '</g>'
              '<g transform="rotate(14 70 -40)"><path d="M54 -70h44l10 12v40h-54z" fill="#C9402C"/><circle cx="66" cy="-58" r="5" fill="#D9B98A"/>'
              '<path d="M66 -58q-10 -24 4 -34" stroke="#8a7a60" stroke-width="2" fill="none"/></g>'
              '<path d="M-130 -26h260v82h-260z" fill="#E5C99C"/>' + T(0, 20, 0, "Lake Tahoe · Dec 12–16", 18, 700, "#5a4426", "middle") + '</g>')
    base = ms_room(P, "dusk", cx) + maya + sam + coffee_table(cx) + folder
    stamps = stamp(P, 290, 330, 150, -12, "#D2321E", "Aviasales", "SFO → RNO · 2 SEATS", "s1") + stamp(P, 1310, 330, 150, 10, "#1F4FC4", "Klook", "SLED HILL · SAT", "s2")
    ink = (f'<filter id="{P}ink" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="9" result="n"/>'
           f'<feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.6 1.55" result="m"/><feComposite in="SourceGraphic" in2="m" operator="in"/></filter>')
    return page(P, muted(P, base) + stamps, mute=.75, extra_defs=ink)


def p06(P, mode):
    deckle = (f'<filter id="{P}dk" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".018" numOctaves="3" seed="5"/>'
              f'<feDisplacementMap in="SourceGraphic" scale="46"/><feGaussianBlur stdDeviation="2"/></filter>'
              f'<mask id="{P}m"><rect x="100" y="84" width="1400" height="732" fill="#fff" filter="url(#{P}dk)"/></mask>'
              f'<filter id="{P}wash" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".012" numOctaves="2" seed="2"/>'
              f'<feDisplacementMap in="SourceGraphic" scale="70"/><feGaussianBlur stdDeviation="14"/></filter>')
    bg = (f'<rect width="1600" height="900" fill="#F6EEDF"/>'
          f'<rect x="80" y="64" width="1440" height="772" fill="#B9C9E6" opacity=".55" filter="url(#{P}wash)"/>'
          f'<rect x="120" y="100" width="1360" height="700" fill="#E9C9D8" opacity=".35" filter="url(#{P}wash)"/>')
    img = f'<image href="{STILL[mode]}" x="100" y="84" width="1400" height="732" preserveAspectRatio="xMidYMid slice" mask="url(#{P}m)"/>'
    # the sled-hill snapshot, drawn here so Maya and Sam are on model
    sx, sy, sw, sh = 80, 452, 420, 380
    sled = [f'<g transform="rotate(-5 {sx+sw/2} {sy+sh/2})" filter="url(#{P}sh)"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="4" fill="#FFFDF8"/></g>',
            f'<g transform="rotate(-5 {sx+sw/2} {sy+sh/2})"><clipPath id="{P}sl"><rect x="{sx+18}" y="{sy+18}" width="{sw-36}" height="{sh-80}"/></clipPath>',
            f'<g clip-path="url(#{P}sl)"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="#BFDDF5"/>'
            f'<path d="M{sx} {sy+120}q200-70 {sw} 10v{sh}H{sx}z" fill="#F7FAFD"/><path d="M{sx} {sy+190}q220-50 {sw} 30" stroke="#D6E4F2" stroke-width="8" fill="none"/>'
            f'<path d="M{sx+300} {sy+130}l18-60 18 60zM{sx+336} {sy+138}l15-48 15 48zM{sx+40} {sy+110}l16-56 16 56z" fill="#2F5D45"/>'
            f'<path d="M{sx+300} {sy+92}l18-12 18 12M{sx+40} {sy+76}l16-11 16 11" stroke="#fff" stroke-width="4" fill="none"/>'
            + fig("sam", "travel", sx + 268, sy + 156, 1.05, expr="delighted", head_rot=-6, arms=[dict(pts=[(-34, 12), (-50, 30), (-62, 14)]), dict(pts=[(34, 12), (56, -6), (60, -36)])])
            + fig("maya", "travel", sx + 160, sy + 172, 1.05, expr="delighted", head_rot=6, arms=[dict(pts=[(-31, 12), (-56, -8), (-58, -40)]), dict(pts=[(31, 12), (52, -6), (58, -36)])])
            + f'<path d="M{sx+92} {sy+268}h196q24 0 34 -26" stroke="#7A4E32" stroke-width="10" fill="none" stroke-linecap="round"/>'
            + f'<rect x="{sx+100}" y="{sy+236}" width="200" height="30" rx="10" fill="#C9402C"/><path d="M{sx+130} {sy+266}v-30M{sx+270} {sy+266}v-30" stroke="#7A4E32" stroke-width="6"/>'
            + f'<path d="M{sx+40} {sy+262}l44-4M{sx+30} {sy+234}l50 2M{sx+46} {sy+206}l34 6" stroke="#9FC2E4" stroke-width="5" stroke-linecap="round"/>'
            + f'<circle cx="{sx+330}" cy="{sy+252}" r="9" fill="#fff"/><circle cx="{sx+346}" cy="{sy+240}" r="6" fill="#fff"/><circle cx="{sx+352}" cy="{sy+258}" r="5" fill="#fff"/>'
            + '</g>' + T(sx + sw / 2, sy + sh - 22, 0, "sled hill, Saturday", 24, 400, "#6b6157", "middle", SERIF, 'font-style="italic"') + '</g>']
    pier = polaroid(1340, 230, 300, 5, "ph-pier", P, "the pier at sunset")
    tape = (f'<rect x="{sx+150}" y="{sy-22}" width="120" height="34" fill="#F3E6BE" opacity=".8" transform="rotate(-9 {sx+210} {sy-5})"/>'
            '<rect x="1290" y="58" width="110" height="32" fill="#F3E6BE" opacity=".8" transform="rotate(8 1345 74)"/>')
    return page(P, bg + img + "".join(sled) + pier + tape, extra_defs=deckle)


def p07(P, mode):
    cx, my = 800, 370
    scr = '<rect width="54" height="96" fill="#FBF8F3"/><use href="#ph-sled" x="4" y="8" width="46" height="34.5"/><use href="#ph-pier" x="4" y="46" width="46" height="34.5"/>'
    ph = phone(0, 0, 60, 106, 0, scr)
    sam = fig("sam", "home", cx + 95, my, 1.75, expr="delighted", head_rot=-9, mid=f'<g transform="translate(-34 50) rotate(-10) scale(.62)">{ph}</g>',
              arms=[dict(pts=[(-31, 10), (-46, 64), (-40, 70)]), dict(pts=[(31, 10), (44, 60), (-14, 62)])])
    maya = fig("maya", "home", cx - 95, my, 1.75, expr="delighted", head_rot=9, lean=5,
               arms=[dict(pts=[(-28, 10), (-40, 56), (-20, 88)]), dict(pts=[(28, 10), (46, 56), (60, 56)], finger=(6, -3))])
    photos = (polaroid(cx - 170, 716, 96, -14, "ph-tahoe", P) + polaroid(cx - 50, 724, 96, 8, "ph-sled", P)
              + polaroid(cx + 80, 716, 96, -6, "ph-pier", P) + polaroid(cx + 200, 728, 96, 12, "ph-cabin", P))
    wall = (polaroid(1220, 190, 110, -6, "ph-sled", P) + polaroid(1350, 220, 110, 7, "ph-pier", P) + polaroid(1260, 330, 100, 3, "ph-tahoe", P))
    wisp = (f'<linearGradient id="{P}wisp" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#2D7CC8"/><stop offset="1" stop-color="#7EC8E8" stop-opacity=".2"/></linearGradient>'
            f'<path d="M{cx+50} 470C{cx+150} 520 {cx+230} 560 {cx+300} 470S{cx+340} 300 {cx+470} 300" stroke="url(#{P}wisp)" stroke-width="30" fill="none" stroke-linecap="round" opacity=".8"/>'
            f'<path d="M{cx+70} 476C{cx+160} 520 {cx+230} 548 {cx+290} 468S{cx+340} 312 {cx+460} 306" stroke="#fff" stroke-width="3" fill="none" stroke-dasharray="14 10" opacity=".7"/>'
            f'<path d="M{cx+300} 470l8-24 8 24zM{cx+318} 440l7-20 7 20z" fill="#2F7A45" opacity=".85"/>'
            f'<path d="M{cx+360} 360l14-22 14 22z" fill="#fff" opacity=".9"/>')
    warm = '<rect width="1600" height="900" fill="#F7B267" opacity=".1"/>'
    base = ms_room(P, "day", cx, frame=False) + wall + maya + sam + coffee_table(cx, 690, 34) + photos
    return page(P, base + wisp + warm)


def p08(P, mode):
    cx, my = 560, 370
    scr = ('<rect width="54" height="96" fill="#FBF8F3"/>' + T(27, 20, 0, "Lake Tahoe", 6.5, 800, INK, "middle")
           + '<rect x="6" y="28" width="42" height="34" rx="5" fill="#CFE3F6"/><path d="M14 54q10-22 26-8" stroke="#D2401C" stroke-width="2" fill="none" stroke-dasharray="1 3"/>'
           + '<rect x="5" y="70" width="44" height="16" rx="8" fill="#138A72"/>' + T(27, 81, 0, "Leave a trail", 5.6, 800, "#fff", "middle"))
    ph = phone(0, 0, 60, 106, 0, scr)
    sam = fig("sam", "home", cx + 115, my, 1.75, expr="smile", head_rot=-6, mid=f'<g transform="translate(-40 44) rotate(-6) scale(.7)">{ph}</g>',
              arms=[dict(pts=[(-31, 10), (-50, 66), (-44, 70)]), dict(pts=[(31, 10), (40, 64), (-30, 60)], finger=(-6, -2))])
    maya = fig("maya", "home", cx - 115, my, 1.75, head_view="3q", expr="smile", head_rot=8,
               arms=[dict(pts=[(-28, 10), (-40, 56), (-24, 88)]), dict(pts=[(28, 10), (44, 58), (40, 86)])])
    base = ms_room(P, "day", cx, frame=False, win=90) + maya + sam + coffee_table(cx) + mug(cx - 120, 662) + mug(cx + 60, 664, "#DCE6F0", "#3D4D7A") + notepad(cx + 190, 690, 6)
    # the shared plan, floating up; names and faces wash out
    cx0, cy0 = 1180, 360
    blur = (f'<filter id="{P}bl" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="7"/></filter>'
            f'<radialGradient id="{P}smudge"><stop offset="0" stop-color="#9FC4E8" stop-opacity=".75"/><stop offset=".7" stop-color="#C6B8E8" stop-opacity=".45"/><stop offset="1" stop-color="#C6B8E8" stop-opacity="0"/></radialGradient>')
    card = [f'<g transform="translate({cx0} {cy0}) rotate(-3)">',
            f'<g filter="url(#{P}sh)"><rect x="-250" y="-250" width="470" height="500" rx="30" fill="#FFFDF8"/></g>',
            '<path d="M220 -250v110l-110 -110z" fill="#E7EDF5"/><path d="M220 -140l-110 -110" stroke="#C9D3DF" stroke-width="2"/>',
            f'<g filter="url(#{P}bl)"><circle cx="-208" cy="-206" r="22" fill="#F4D7B8"/><circle cx="-176" cy="-206" r="22" fill="#D9C4B0"/>'
            '<use href="#h-maya-front-smile" x="-250" y="-266" width="88" height="102"/><use href="#h-sam-front-smile" x="-218" y="-266" width="88" height="102"/>'
            + T(-140, -198, 0, "Maya &amp; Sam", 26, 700, INK) + '</g>',
            '<ellipse cx="-150" cy="-206" rx="140" ry="44" fill="url(#%ssmudge)"/>' % P,
            '<rect x="-230" y="-168" width="236" height="36" rx="18" fill="#17161B"/>' + icon("i-check", -218, -161, 22, "#fff", 2.4) + T(-190, -143, 0, "Shared anonymously", 17, 700, "#fff"),
            T(-230, -92, 0, "Lake Tahoe in December", 28, 800, INK) + T(-230, -64, 0, "4 days · a cabin, a sled hill, the pier", 17, 500, "#6b6157"),
            '<rect x="-230" y="-46" width="430" height="150" rx="18" fill="#E4F1E6"/>'
            '<path d="M-70 -30q46 6 44 56t-30 66q-34-8-34-60t20-62z" fill="#3C8CE6"/>'
            '<path d="M-150 80q40-90 80-110t110 20q30 30 100 10" stroke="#D2401C" stroke-width="4" fill="none" stroke-dasharray="2 9" stroke-linecap="round"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="10" fill="{c}" stroke="#fff" stroke-width="3"/>' for x, y, c in [(-150, 80, "#D2401C"), (-70, -30, "#087F7B"), (40, -10, "#A445D8"), (140, 0, "#F59A2E")]),
            ]
    rows = [("Day 1", "Sled hill, then cocoa", "#F59A2E"), ("Day 2", "Emerald Bay overlook", "#087F7B"), ("Day 3", "Pier at sunset", "#A445D8")]
    for i, (d, t, c) in enumerate(rows):
        y = 140 + i * 36
        card.append(f'<circle cx="-220" cy="{y-6}" r="7" fill="{c}"/>' + T(-202, y, 0, d, 17, 800, INK) + T(-136, y, 0, t, 17, 500, "#4a423a"))
    card.append('</g>')
    plane = paper_plane(1470, 120, .8, -18) + '<path d="M1400 168q-30 20 -60 14" stroke="#2b2620" stroke-opacity=".35" stroke-width="2.5" fill="none" stroke-dasharray="4 8"/>'
    trail = f'<path d="M{cx+40} 430Q{cx+220} 380 {cx0-260} 420" stroke="#138A72" stroke-width="3" fill="none" stroke-dasharray="2 10" stroke-linecap="round"/>'
    return page(P, base + trail + "".join(card) + plane, extra_defs=blur)


def p09(P, mode):
    bg = ('<rect width="1600" height="900" fill="#F6EEDF"/>'
          f'<radialGradient id="{P}w"><stop offset="0" stop-color="#CFE3FA"/><stop offset="1" stop-color="#CFE3FA" stop-opacity="0"/></radialGradient>'
          f'<circle cx="1020" cy="470" r="520" fill="url(#{P}w)"/>')
    g, prj = globe(P, 1020, 470, 340, -62, 24, arcs=[("tahoe", "lisbon", "#E0204E", 7)], pins=[("tahoe", "#D2401C", True), ("lisbon", "#E0204E", True)])
    motion = "".join(f'<path d="M{1020+r*math.cos(math.radians(a)):.0f} {470+r*math.sin(math.radians(a)):.0f}A{r} {r} 0 0 1 {1020+r*math.cos(math.radians(a+28)):.0f} {470+r*math.sin(math.radians(a+28)):.0f}" stroke="{INK}" stroke-opacity=".28" stroke-width="3" fill="none" stroke-linecap="round"/>'
                     for r, a in [(380, 200), (396, 230), (380, 20), (396, 50), (372, 120)])
    tx, ty, _ = prj(*PLACES["tahoe"], 1.0)
    trail = (f'<path d="M110 800C260 760 230 600 330 610S420 720 360 700 300 560 470 470" stroke="{INK}" stroke-opacity=".45" stroke-width="3" fill="none" stroke-dasharray="6 10" stroke-linecap="round"/>'
             f'<path d="M560 420Q{(560+tx)/2:.0f} 330 {tx-26:.0f} {ty-10:.0f}" stroke="#E0204E" stroke-opacity=".7" stroke-width="3" fill="none" stroke-dasharray="2 9" stroke-linecap="round"/>')
    sparks = "".join(f'<path d="M{x} {y-10}v20M{x-10} {y}h20" stroke="#F59A2E" stroke-width="3" stroke-linecap="round" opacity=".7"/>' for x, y in [(1440, 120), (560, 180), (1490, 760), (640, 800)])
    return page(P, bg + motion + g + trail + paper_plane(520, 440, 1.1, -24) + sparks)


# ---------------------------------------------------------------- Lisbon
LIS = dict(wall="#EBD5B8", wall2="#E0C29F", floor="#8E5F40", trim="#F4E9DA", sofa=("#46707A", "#375A63", "#55838D"))


def azulejo(P, y, h):
    return (f'<pattern id="{P}az" width="60" height="60" patternUnits="userSpaceOnUse"><rect width="60" height="60" fill="#F4F1EA"/>'
            '<rect x="1" y="1" width="58" height="58" fill="none" stroke="#B9C7DE" stroke-width="1"/>'
            '<circle cx="30" cy="30" r="9" fill="#2F5DA8"/><circle cx="30" cy="30" r="4" fill="#F4F1EA"/>'
            '<path d="M30 6q6 12 0 15q-6-3 0-15M30 54q6-12 0-15q-6 3 0 15M6 30q12 6 15 0q-3-6-15 0M54 30q-12 6-15 0q3-6 15 0" fill="#2F5DA8"/>'
            '<path d="M0 0l8 8M60 0l-8 8M0 60l8-8M60 60l-8-8" stroke="#2F5DA8" stroke-width="3"/></pattern>'
            f'<rect y="{y}" width="1600" height="{h}" fill="url(#{P}az)"/><rect y="{y-10}" width="1600" height="12" fill="{LIS["trim"]}"/>')


def lisbon_room(P, cx=720, sofa=True, window=True, shelf=True, wx=100):
    c = LIS
    s = [f'<linearGradient id="{P}lw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["wall"]}"/><stop offset="1" stop-color="{c["wall2"]}"/></linearGradient>',
         f'<rect width="1600" height="660" fill="url(#{P}lw)"/>', azulejo(P, 470, 180),
         f'<rect y="648" width="1600" height="12" fill="{c["trim"]}"/><rect y="660" width="1600" height="260" fill="{c["floor"]}"/>',
         '<path d="M0 730H1600M0 810H1600" stroke="#000" stroke-opacity=".08" stroke-width="2"/>',
         f'<ellipse cx="{cx}" cy="800" rx="560" ry="70" fill="#B5543A" opacity=".8"/><ellipse cx="{cx}" cy="800" rx="520" ry="58" fill="none" stroke="#E9C46A" stroke-width="4" opacity=".7"/>']
    if window:
        s.append(f'<linearGradient id="{P}ev" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7D6AB8"/><stop offset=".55" stop-color="#F09A7A"/><stop offset="1" stop-color="#FAD3A1"/></linearGradient>'
                 f'<rect x="{wx}" y="60" width="320" height="560" rx="10" fill="{c["trim"]}"/><rect x="{wx+16}" y="76" width="288" height="528" fill="url(#{P}ev)"/>'
                 f'<rect x="{wx+16}" y="420" width="288" height="44" fill="#6E8FC0"/><path d="M{wx+16} 430h288" stroke="#A9C1E2" stroke-width="3"/>'
                 + "".join(f'<rect x="{wx+16+x}" y="{y}" width="{w}" height="{560-y}" fill="{f}"/><path d="M{wx+16+x-4} {y}l{w/2+4} -20l{w/2+4} 20z" fill="#C8643B"/>'
                           for x, y, w, f in [(0, 470, 70, "#F3E6D3"), (66, 486, 80, "#F2D7B0"), (142, 462, 70, "#F3E6D3"), (208, 480, 80, "#EBC9A0")])
                 + f'<rect x="{wx+157}" y="76" width="7" height="528" fill="{c["trim"]}"/>'
                 f'<g stroke="#2A2626" stroke-width="5" fill="none"><path d="M{wx+10} 520h300M{wx+10} 606h300"/>'
                 + "".join(f'<path d="M{wx+20+i*24} 520v86"/>' for i in range(13))
                 + "".join(f'<circle cx="{wx+32+i*48}" cy="563" r="10"/>' for i in range(6)) + '</g>')
    if shelf:
        bx = 1250
        books = ""
        rnd = random.Random(3)
        for row, y in enumerate([300, 420, 540]):
            x = bx + 18
            while x < bx + 232:
                w = rnd.randint(14, 26)
                h = rnd.randint(70, 96)
                books += f'<rect x="{x}" y="{y-h}" width="{w}" height="{h}" rx="2" fill="{rnd.choice(["#2F5DA8", "#B5543A", "#E9C46A", "#46707A", "#8C5A3C", "#D9CBB0"])}"/>'
                x += w + 2
        s.append(f'<rect x="{bx}" y="190" width="250" height="460" rx="6" fill="#7A5236"/><rect x="{bx+12}" y="200" width="226" height="440" fill="#5E3E28"/>{books}'
                 + "".join(f'<rect x="{bx+8}" y="{y}" width="234" height="10" fill="#7A5236"/>' for y in (300, 420, 540))
                 + f'<rect x="{bx+30}" y="150" width="190" height="42" rx="6" fill="#8C5A3C"/><ellipse cx="{bx+110}" cy="150" rx="64" ry="9" fill="#1E1C20"/><ellipse cx="{bx+110}" cy="150" rx="18" ry="3" fill="#E0204E"/>'
                 f'<path d="M{bx+180} 140l-30 8" stroke="#C9C2B6" stroke-width="4" stroke-linecap="round"/>')
    if sofa:
        a, b, cc = c["sofa"]
        s.append(f'<ellipse cx="{cx}" cy="660" rx="370" ry="14" fill="#2a1408" opacity=".18"/>'
                 f'<path d="M{cx-340} 580V440Q{cx-340} 392 {cx-280} 386Q{cx} 360 {cx+280} 386Q{cx+340} 392 {cx+340} 440V580Z" fill="{b}"/>'
                 f'<rect x="{cx-330}" y="514" width="660" height="66" rx="20" fill="{cc}"/><rect x="{cx-340}" y="568" width="680" height="70" rx="16" fill="{b}"/>'
                 f'<rect x="{cx-392}" y="470" width="100" height="170" rx="40" fill="{a}"/><rect x="{cx+292}" y="470" width="100" height="170" rx="40" fill="{a}"/>'
                 + "".join(f'<circle cx="{cx+x}" cy="430" r="4" fill="{a}"/>' for x in range(-240, 260, 80))
                 + f'<path d="M{cx-370} 640l-6 22M{cx+370} 640l6 22" stroke="#4E3428" stroke-width="10" stroke-linecap="round"/>')
    return "".join(s)


def teapot(x, y):
    return (f'<g transform="translate({x} {y})"><path d="M-30 0q0-34 30-34t30 34z" fill="#F4F1EA"/><rect x="-32" y="-2" width="64" height="8" rx="4" fill="#E2DCCF"/>'
            '<path d="M28 -16q22-4 24-20" stroke="#F4F1EA" stroke-width="7" fill="none" stroke-linecap="round"/><path d="M-28 -20q-16 0-14 14" stroke="#F4F1EA" stroke-width="6" fill="none"/>'
            '<circle cy="-38" r="5" fill="#2F5DA8"/><path d="M-18 -14q18 8 36 0" stroke="#2F5DA8" stroke-width="3" fill="none"/></g>'
            f'<g transform="translate({x+70} {y})"><path d="M-14 -16h28l-4 16h-20z" fill="#F4F1EA"/><ellipse cy="0" rx="22" ry="5" fill="#E2DCCF"/><path d="M-10 -10h20" stroke="#2F5DA8" stroke-width="2"/></g>')


def p10(P, mode):
    cx, my = 720, 372
    paper = ('<g transform="translate(0 0)"><rect x="-46" y="22" width="92" height="74" rx="3" fill="#F2EEE4"/><path d="M0 22v74" stroke="#CFC8B8" stroke-width="1.5"/>'
             + T(0, 35, 0, "DIÁRIO", 10, 800, "#3a332b", "middle", font=SERIF)
             + "".join(f'<rect x="{-40 if i%2==0 else 5}" y="{44+(i//2)*7}" width="34" height="2.6" rx="1" fill="#A39A8C"/>' for i in range(14))
             + '</g>')
    tomas = fig("tomas", "home", cx - 110, my, 1.75, head_view="3q", expr="puzzled", head_rot=-4, mid=paper,
                arms=[dict(pts=[(-31, 10), (-56, 50), (-44, 40)]), dict(pts=[(31, 10), (56, 50), (44, 40)])])
    scr = ('<rect width="54" height="96" fill="#FBF8F3"/>' + logo(27, 30, .8) + '<rect x="6" y="50" width="42" height="20" rx="5" fill="#FFE9DD"/>')
    ph = phone(0, 0, 60, 106, 0, scr)
    rosa = fig("rosa", "home", cx + 110, my, 1.75, head_view="3q", expr="surprised", head_rot=-4,
               mid="", front=f'<g transform="translate(52 6) rotate(10) scale(.62)">{ph}</g>',
               arms=[dict(pts=[(-27, 10), (-36, 58), (-12, 86)]), dict(pts=[(27, 10), (56, 48), (48, 22)])])
    buzz = (f'<g stroke="{INK}" stroke-width="3" stroke-linecap="round" opacity=".6" fill="none">'
            f'<path d="M{cx+232} 360q8 -10 0 -20M{cx+246} 366q14 -18 0 -34M{cx+168} 362q-8 -10 0 -20"/></g>')
    note = (f'<g transform="translate({cx+260} 280) rotate(-2)"><g filter="url(#{P}sh)"><rect x="0" y="0" width="430" height="96" rx="24" fill="#FFFDF8"/></g>'
            + logo(40, 48, 1.5) + T(76, 38, 0, "GitAway · now", 16, 600, "#8a8073") + T(76, 68, 0, "A trail you'll love was just shared", 21, 750, INK) + '</g>')
    side = (f'<rect x="{cx+420}" y="560" width="120" height="14" rx="4" fill="#8C5A3C"/><rect x="{cx+472}" y="574" width="16" height="80" fill="#6E4630"/>'
            f'<ellipse cx="{cx+480}" cy="656" rx="44" ry="7" fill="#6E4630"/>'
            f'<path d="M{cx+452} 560l10-70h36l10 70z" fill="#E9C46A"/><rect x="{cx+474}" y="478" width="12" height="14" fill="#C9A35A"/>')
    table = coffee_table(cx, 700, 28, "#9C6B48", "#7A5236") + teapot(cx - 60, 698) + '<rect x="%d" y="690" width="70" height="10" rx="2" fill="#2F5DA8"/>' % (cx + 120)
    warm = '<rect width="1600" height="900" fill="#F09A7A" opacity=".08"/>'
    return page(P, lisbon_room(P, cx) + side + tomas + rosa + table + buzz + note + warm)


def p11(P, mode):
    back = (lisbon_room(P, 800, sofa=False, window=True, shelf=True) + '<rect width="1600" height="900" fill="#FBF3E7" opacity=".45"/>')
    s = 2.55
    rosa = fig("rosa", "home", 630, 480, s, head_view="3q", expr="smile", head_rot=-3,
               arms=[dict(pts=[(-27, 10), (-30, 70), (10, 92)])])
    tomas = fig("tomas", "home", 970, 480, s, head_view="3q", expr="smile", flip=True, head_rot=-3,
                arms=[dict(pts=[(-31, 10), (-40, 70), (-34, 96)]), dict(pts=[(31, 10), (48, 70), (40, 100)])])
    sofa = '<rect x="300" y="700" width="1000" height="240" rx="60" fill="#46707A"/><rect x="330" y="740" width="940" height="200" rx="40" fill="#55838D"/>'
    scr = ('<svg x="10" y="40" width="169" height="110" viewBox="0 0 160 104" preserveAspectRatio="xMidYMid slice"><use href="#ph-beach" width="160" height="120"/></svg>'
           + T(14, 26, 0, "Maya &amp; Sam's trail", 14, 700, "#8a8073") + T(14, 180, 0, "Lake Tahoe", 24, 800, INK) + T(14, 202, 0, "4 days · they went in winter", 13, 500, "#6b6157")
           + '<rect x="10" y="222" width="169" height="44" rx="22" fill="#D2401C"/>' + icon("i-fork", 24, 233, 22, "#fff", 2.2) + T(104, 250, 0, "Follow this trail", 16, 750, "#fff", "middle"))
    ph = phone(806, 724, 210, 380, 3, scr, P)
    tapx, tapy = 746, 790
    ripple = "".join(f'<circle cx="{tapx}" cy="{tapy}" r="{r}" fill="none" stroke="#D2401C" stroke-width="{4-i}" opacity="{.7-i*.2}"/>' for i, r in enumerate([22, 40, 60]))
    rs = PAL["rosa"]
    ripple += (f'<path d="M690 700Q690 800 {tapx-22} {tapy+40}" stroke="#B3533A" stroke-width="38" fill="none" stroke-linecap="round"/>'
               f'<path d="M{tapx-20} {tapy+36}l18 -32" stroke="{rs["skin"]}" stroke-width="11" stroke-linecap="round"/><circle cx="{tapx-22}" cy="{tapy+42}" r="17" fill="{rs["skin"]}"/>')
    W = 360
    ws = [widget(P, 100, 110, W, 120, "#2F5DA8", "i-passport", "ESTA needed", "for Portuguese passports", big_size=32),
          widget(P, 100, 470, W, 120, "#EE6A4C", "i-flight", "LIS → RNO", "1 stop · from €612"),
          widget(P, 1140, 110, W, 120, "#E39A2B", "i-swap", "€ → $", "1 € = $1.08", fg="#2b1a05", big_size=36),
          widget(P, 1140, 470, W, 120, "#F2C94C", "i-sun", "Sunny · 27°C", "July at the lake", fg="#2b1a05", big_size=32),
          (f'<g filter="url(#{P}sh)"><rect x="1180" y="640" width="280" height="170" rx="26" fill="#2BB5AD"/></g>'
           '<path d="M1380 676q40 6 38 52t-28 70q-30-8-30-56t20-66z" fill="#BDF3EC"/><circle cx="1404" cy="770" r="9" fill="#D2401C" stroke="#fff" stroke-width="3"/>'
           + T(1200, 696, 0, "Sand Harbor", 22, 800, "#fff") + T(1200, 722, 0, "beach · 1 mi", 16, 500, "#fff", extra='opacity=".9"'))]
    pops = pop_marks(106, 114, "#2F5DA8", -30) + pop_marks(1494, 114, "#E39A2B", 30) + pop_marks(1494, 474, "#F2C94C", 40)
    return page(P, back + sofa + rosa + tomas + ph + ripple + "".join(ws) + pops)


def beach(P):
    s = [f'<linearGradient id="{P}bs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7DC0EC"/><stop offset="1" stop-color="#DDF0FA"/></linearGradient>',
         f'<linearGradient id="{P}bw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1E8CC8"/><stop offset=".3" stop-color="#2BB5C0"/><stop offset="1" stop-color="#A6EDE1"/></linearGradient>',
         f'<rect width="1600" height="900" fill="url(#{P}bs)"/>',
         '<path d="M0 400l120-80 90 40 150-110 140 90 120-60 160 100 140-70 180 90 140-50 160 70v40H0z" fill="#9BB3C9"/>',
         '<path d="M360 250l-26 26 16-4 8 10 10-10 14 4zM640 290l-18 18 12-3 6 8 8-8 10 3z" fill="#fff" opacity=".8"/>',
         '<rect y="420" width="1600" height="60" fill="#1A6FB0"/>',
         f'<rect y="470" width="1600" height="430" fill="url(#{P}bw)"/>',
         '<path d="M0 560q160 18 320 0t320 0 320 0 320 0 320 0" stroke="#fff" stroke-opacity=".35" stroke-width="3" fill="none"/>',
         '<path d="M500 640q120 14 240 0M960 600q120 12 240 0M300 700q160 14 320 0" stroke="#fff" stroke-opacity=".4" stroke-width="3" fill="none"/>',
         '<ellipse cx="760" cy="640" rx="160" ry="30" fill="#22A68F" opacity=".35"/><ellipse cx="1300" cy="700" rx="200" ry="34" fill="#22A68F" opacity=".3"/>',
         '<path d="M0 820q300-30 700 0t900-20V900H0z" fill="#EED9A8"/><path d="M0 820q300-30 700 0t900-20" stroke="#F8EED6" stroke-width="6" fill="none"/>']
    # granite boulders
    for (x, y, rx, ry) in [(720, 560, 120, 70), (840, 600, 80, 50), (630, 620, 70, 40), (1460, 560, 150, 96), (1350, 640, 80, 46), (1540, 660, 90, 60)]:
        s.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#CFC6B6"/><path d="M{x-rx*.6} {y+ry*.2}q{rx*.6} {ry*.7} {rx*1.4} {-ry*.1}" stroke="#ADA393" stroke-width="{ry*.5:.0f}" fill="none" opacity=".7" stroke-linecap="round"/>'
                 f'<ellipse cx="{x-rx*.25}" cy="{y-ry*.4}" rx="{rx*.4}" ry="{ry*.2}" fill="#EAE4D8" opacity=".9"/>')
    # tall pines at the right edge
    for (x, h, c) in [(1490, 520, "#2F5D45"), (1560, 600, "#264E3A"), (1420, 420, "#3E7356")]:
        s.append(f'<rect x="{x-5}" y="{470-h*.2}" width="10" height="{h*.3}" fill="#5E3E28"/>'
                 + "".join(f'<path d="M{x-40+i*6} {470-h*.15-i*h*.2}l{40-i*6} {-h*.3}l{40-i*6} {h*.3}z" fill="{c}"/>' for i in range(4)))
    return "".join(s)


def p12(P, mode):
    wet = (f'<filter id="{P}wet" x="-10%" y="-10%" width="130%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".011 .018" numOctaves="3" seed="11"/>'
           f'<feDisplacementMap in="SourceGraphic" scale="170"/></filter>'
           f'<linearGradient id="{P}fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff"/><stop offset=".5" stop-color="#fff"/><stop offset=".72" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
           f'<mask id="{P}room" maskUnits="userSpaceOnUse" x="0" y="0" width="1600" height="900"><rect x="-100" y="-100" width="1000" height="1100" fill="url(#{P}fade)" filter="url(#{P}wet)"/></mask>'
           f'<filter id="{P}blob" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="2" seed="4"/><feDisplacementMap in="SourceGraphic" scale="34"/></filter>')
    room = lisbon_room(P, 400, sofa=True, window=True, shelf=False, wx=40)
    room_layer = f'<g mask="url(#{P}room)"><g filter="url(#{P}mute)">{room}</g></g>'
    # wet paint: blooms with darker rims where the room bleeds into the lake, and drips running down
    blooms = f'<g filter="url(#{P}blob)">' + "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" fill-opacity=".38" stroke="{c}" stroke-opacity=".55" stroke-width="3"/>'
        for x, y, r, c in [(735, 190, 64, "#E0C29F"), (790, 360, 44, "#B9C7DE"), (700, 520, 78, "#E0C29F"), (820, 610, 40, "#9EB3D2"), (760, 760, 56, "#C9A98A"), (860, 250, 26, "#E0C29F")]) + '</g>'
    drips = "".join(
        f'<path d="M{x-w/2} {y}Q{x} {y+l*.2} {x-w*.15} {y+l}Q{x} {y+l+w*.2} {x+w*.15} {y+l}Q{x} {y+l*.2} {x+w/2} {y}Z" fill="{c}" fill-opacity=".7"/><circle cx="{x}" cy="{y+l+w*.15}" r="{w*.42}" fill="{c}" fill-opacity=".75"/>'
        for x, y, l, w, c in [(712, 250, 110, 16, "#E0C29F"), (760, 432, 90, 12, "#B9C7DE"), (686, 590, 130, 18, "#C9A98A"), (812, 520, 70, 10, "#9EB3D2"), (742, 96, 90, 14, "#E0C29F")])
    s = 1.6
    rosa = fig("rosa", "travel", 1060, 456, s, pose="stand", expr="delighted", head_rot=4,
               arms=[dict(pts=[(-27, 10), (-58, -6), (-36, -56)]), dict(pts=[(27, 10), (46, 56), (53, 88)])])
    tomas = fig("tomas", "travel", 1230, 456, s, pose="stand", expr="delighted", head_rot=-4,
                arms=[dict(pts=[(-31, 10), (-48, 56), (-53, 88)]), dict(pts=[(31, 10), (64, 30), (70, 0)])])
    water = (f'<path d="M940 742q60-10 120 0t120 0 120 0 80 0V800H940z" fill="#7FE0D6" opacity=".55"/>'
             '<path d="M960 748q40-8 80 0M1110 748q40-8 80 0M1250 750q30-6 60 0" stroke="#fff" stroke-width="3" fill="none" opacity=".8" stroke-linecap="round"/>'
             '<path d="M1000 770q50 8 100 0M1160 772q60 8 120 0" stroke="#fff" stroke-width="2" fill="none" opacity=".5"/>')
    return page(P, beach(P) + rosa + tomas + water + room_layer + blooms + drips, mute=.45, extra_defs=wet)


def vignette(P, vid, x, y, w, h, bg, people, label):
    return (f'<clipPath id="{P}{vid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22"/></clipPath>'
            f'<g filter="url(#{P}sh)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="#FFFDF8"/></g>'
            f'<g clip-path="url(#{P}{vid})">{bg}{people}</g>'
            f'<rect x="{x+12}" y="{y+h-42}" width="{len(label)*8.6+24:.0f}" height="30" rx="15" fill="#FFFDF8" opacity=".92"/>'
            + T(x + 24, y + h - 21, 0, label, 15, 650, INK))


def p13(P, mode):
    bg = ('<rect width="1600" height="900" fill="#F6EEDF"/>'
          f'<radialGradient id="{P}w"><stop offset="0" stop-color="#FFE4CC"/><stop offset="1" stop-color="#FFE4CC" stop-opacity="0"/></radialGradient>'
          f'<circle cx="800" cy="470" r="560" fill="url(#{P}w)"/>')
    arcs = [("tahoe", "lisbon", "#E0204E", 7), ("lisbon", "marrakech", KIND[1], 5), ("lisbon", "paris", KIND[2], 5), ("tahoe", "banff", KIND[3], 5),
            ("tahoe", "oaxaca", KIND[5], 5), ("nyc", "reykjavik", KIND[6], 5), ("nyc", "edinburgh", KIND[0], 5), ("rio", "capetown", KIND[3], 5),
            ("cusco", "patagonia", KIND[1], 5), ("mexico", "havana", KIND[4], 5), ("accra", "lisbon", KIND[2], 5), ("paris", "rome", KIND[5], 5),
            ("rome", "athens", KIND[0], 5), ("oslo", "edinburgh", KIND[3], 5), ("santiago", "rio", KIND[6], 5), ("vancouver", "tahoe", KIND[1], 5),
            ("nairobi", "zanzibar", KIND[4], 5), ("cairo", "istanbul", KIND[5], 5), ("nyc", "lisbon", KIND[3], 5), ("havana", "rio", KIND[2], 5)]
    pins = [(n, KIND[i % 7], n in ("tahoe", "lisbon")) for i, n in enumerate(PLACES)]
    g, prj = globe(P, 800, 470, 330, -38, 22, arcs=arcs, pins=pins)
    hearts = "".join(icon("i-heart", x, y, 26, c, 2.4).replace('fill="none"', f'fill="{c}"') for x, y, c in
                     [(700, 150, "#E0204E"), (930, 210, "#F59A2E"), (620, 330, "#A445D8"), (1010, 380, "#E0204E"), (760, 560, "#087F7B"), (900, 640, "#E0204E")])
    planes = paper_plane(560, 160, .45, -20) + paper_plane(1060, 790, .4, -30) + paper_plane(1110, 170, .38, 10)
    L, R, W, H = 64, 1206, 330, 226
    ys = [112, 362, 612]
    snow = f'<rect x="{L}" y="{ys[0]}" width="{W}" height="{H}" fill="#D8E9F8"/><path d="M{L} {ys[0]+150}q160-40 {W} 0v80H{L}z" fill="#fff"/><path d="M{L+260} {ys[0]+150}l20-70 20 70z" fill="#2F5D45"/>'
    sea = lambda x, y: (f'<rect x="{x}" y="{y}" width="{W}" height="{H}" fill="#9FD3F2"/><rect x="{x}" y="{y+90}" width="{W}" height="80" fill="#3CC6C0"/>'
                        f'<rect x="{x}" y="{y+160}" width="{W}" height="70" fill="#EED9A8"/>')
    city = f'<rect x="{L}" y="{ys[2]}" width="{W}" height="{H}" fill="#F6D9C4"/><path d="M{L} {ys[2]+170}v-60h40v-30h40v50h30v-80h40v70h50v-40h60v60h70v30z" fill="#E7B9A0"/><path d="M{L+250} {ys[2]+110}l20-30 20 30h-8v20h-24v-20z" fill="#C8643B"/>'
    hills = f'<rect x="{R}" y="{ys[1]}" width="{W}" height="{H}" fill="#CDE6D6"/><path d="M{R} {ys[1]+170}l90-110 70 60 80-90 90 120v80H{R}z" fill="#7FB394"/><path d="M{R+240} {ys[1]+30}l-14 16 9-3 5 7 7-7 9 3z" fill="#fff"/>'
    park = f'<rect x="{R}" y="{ys[2]}" width="{W}" height="{H}" fill="#E4F1E6"/><circle cx="{R+280}" cy="{ys[2]+70}" r="50" fill="#7FB394"/><rect x="{R+274}" y="{ys[2]+110}" width="12" height="60" fill="#8C5A3C"/>'
    sc = 1.05
    wave = lambda side: [dict(pts=[(side * 30, 12), (side * 58, -6), (side * 62, -40)])]
    v = [vignette(P, "v1", L, ys[0], W, H, snow,
                  fig("maya", "travel", L + 120, ys[0] + 175, sc, expr="delighted", arms=wave(-1), head_rot=4) + fig("sam", "travel", L + 215, ys[0] + 172, sc, expr="delighted", arms=wave(1), head_rot=-4),
                  "Maya &amp; Sam · Tahoe"),
         vignette(P, "v2", L, ys[1], W, H, sea(L, ys[1]),
                  fig("dad", "beach", L + 100, ys[1] + 168, sc, expr="delighted", arms=[]) + fig("mom", "beach", L + 230, ys[1] + 168, sc, expr="smile", arms=[])
                  + fig("kid1", "beach", L + 165, ys[1] + 190, .72, expr="delighted", arms=wave(1)),
                  "the Parks · Oaxaca"),
         vignette(P, "v3", L, ys[2], W, H, city,
                  fig("city1", "city", L + 120, ys[2] + 172, sc, expr="smile", head_view="front", arms=[]) + fig("city2", "city", L + 215, ys[2] + 170, sc, expr="delighted", arms=[]),
                  "Leila &amp; Omar · New York"),
         vignette(P, "v4", R, ys[0], W, H, sea(R, ys[0]),
                  fig("rosa", "travel", R + 125, ys[0] + 182, sc, expr="delighted", arms=wave(-1)) + fig("tomas", "travel", R + 220, ys[0] + 182, sc, expr="delighted", arms=[]),
                  "Rosa &amp; Tomás · Tahoe"),
         vignette(P, "v5", R, ys[1], W, H, hills,
                  fig("hik1", "hike", R + 115, ys[1] + 168, sc, expr="delighted", arms=wave(-1)) + fig("hik2", "hike", R + 215, ys[1] + 166, sc, expr="delighted", arms=[]),
                  "friends · Banff"),
         vignette(P, "v6", R, ys[2], W, H, park,
                  fig("gma", "city", R + 125, ys[2] + 172, sc, expr="smile", arms=[]) + fig("kid2", "city", R + 205, ys[2] + 192, .72, expr="delighted", arms=wave(1)),
                  "Grandma Ada &amp; Kofi · Accra")]
    links = "".join(f'<path d="M{x1} {y1}L{x2:.0f} {y2:.0f}" stroke="{c}" stroke-width="2.5" stroke-dasharray="2 8" stroke-linecap="round" opacity=".7"/>'
                    for (x1, y1), n, c in [((L + W, ys[0] + 110), "tahoe", "#D2401C"), ((L + W, ys[1] + 110), "oaxaca", KIND[5]), ((L + W, ys[2] + 90), "nyc", KIND[2]),
                                           ((R, ys[0] + 110), "lisbon", "#E0204E"), ((R, ys[1] + 110), "banff", KIND[3]), ((R, ys[2] + 110), "accra", KIND[2])]
                    for x2, y2, _ in [prj(*PLACES[n])])
    return page(P, bg + g + links + hearts + planes + "".join(v))


PANELS = {
    "01": ("The couch", p01), "02": ("The book", p02), "03": ("Let's book it", p03), "04": ("Everything pops", p04),
    "05": ("Booked", p05), "06": ("Go", p06), "07": ("Home, happy", p07), "08": ("Leave a trail", p08),
    "09": ("The world spins", p09), "10": ("The nudge", p10), "11": ("Perfect", p11), "12": ("Couch to beach", p12),
    "13": ("The world keeps sharing", p13),
}
