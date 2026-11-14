"""The trip card (F-234): the picture a family posts to Instagram, 1080 x 1350 (Instagram's 4:5), drawn on the server as a PNG.

    Card(title, place, route, when, days, names, link, art_slug)    everything the picture says; nothing else can reach it
    render(card) -> bytes                                           the PNG

Why the server and not a canvas in the page (D-490): the same picture is the download, the share sheet's file and the public page's preview image, so it
must not depend on the viewer's browser, fonts or screen, and a test can open the bytes and read them. The place's art is placeart.art's SVG, drawn by
CairoSVG after its CSS custom properties are written out (CairoSVG does not read `var()`); the words are Pillow with Geist (gitaway/fonts, the
variable font made a TrueType file once from assets/fonts/geist-variable.woff2); all of it is plain wheels or conda packages, no browser and no system fonts,
so it draws the same on a laptop and in Railway's image (tests/test_dockerfile.py keeps gitaway/fonts in it).

A Card has no field for a booking, a price, an email or an address: what the picture can show is only what is in this dataclass, and tripshare.py decides
what goes in (never those). Colours are fixed here: it is an image, not a page, so it does not follow the mode.
"""

import io
import re
from dataclasses import dataclass
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from gitaway import placeart

W, H = 1080, 1350
ART_H = 700                     # the place's art fills the top; the paper panel rises over its foot
FONT = Path(__file__).resolve().parent / "fonts" / "geist-variable.ttf"
INK, INK2, PAPER, WHITE = "#17171C", "#5A5A66", "#FBF8F3", "#FFFFFF"
KINDS = ("#4338CA", "#8B2FC9", "#15803D", "#C92A5E", "#C2410C", "#0F766E")      # the kinds' colours (tokens.css --k-flight ... --k-see): the card's confetti and chips
FALLBACK_SKY = ("#7FB8FF", "#FFC2D6", "#FFE08A")      # a place with no art: a soft dawn


@dataclass(frozen=True)
class Card:
    title: str
    place: str                  # "South Lake Tahoe"
    route: tuple = ()           # ("SFO", "South Lake Tahoe"): where from, where to
    when: str = ""              # "December 2026" or, when the family chose it, "Dec 19 - 26, 2026"
    days: int = 0
    names: str = ""             # "Ari and Maya": only when the family chose to say them
    link: str = ""              # "gitaway.me/s/..." as the picture prints it
    art_slug: str = ""          # "laketahoe": placeart's key, "" for a place with no art


def font(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_axes([weight])
    return f


def _plain(svg: str) -> str:
    """The art's SVG with every `var(--pa-x)` written as the colour the <svg> sets for it, and its night set dropped: CairoSVG reads no custom properties."""
    root = re.search(r'style="([^"]*)"', svg).group(1)
    vals = dict(re.findall(r"--(pa-[a-z0-9-]+):([^;]+)", root))
    return re.sub(r"var\(--(pa-[a-z0-9-]+)\)", lambda m: vals[m.group(1)], svg)


def _art(slug: str, size: tuple) -> Image.Image:
    svg = placeart.art(slug, fit="xMidYMax slice") if slug else None
    if svg is None:
        base = Image.new("RGB", size, FALLBACK_SKY[0])
        d = ImageDraw.Draw(base)
        for i, c in enumerate(FALLBACK_SKY[1:], 1):
            d.ellipse((size[0] * (i * .35 - .3), size[1] * (.1 + i * .12), size[0] * (i * .35 + .7), size[1] * (1.6)), fill=c)
        return base
    svg = _plain(svg).replace('<svg ', f'<svg width="{size[0]}" height="{size[1]}" ', 1)
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert("RGB")


def _mark(px: int) -> Image.Image:
    """GitAway's mark: an ink tile with the fork's three nodes in kind colours (layout.MARK, drawn with fixed colours)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="{INK}"/>'
           '<g transform="translate(4 4)" fill="none" stroke-width="2.4" stroke-linecap="round"><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3" stroke="#FFFFFF"/>'
           f'<circle cx="6" cy="6" r="2.6" stroke="{KINDS[0]}" fill="{KINDS[0]}"/><circle cx="18" cy="6" r="2.6" stroke="{KINDS[2]}" fill="{KINDS[2]}"/>'
           f'<circle cx="12" cy="18" r="2.6" stroke="{KINDS[3]}" fill="{KINDS[3]}"/></g></svg>')
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert("RGBA")


def _wrap(text: str, f, width: int, lines: int) -> list:
    """`text` broken at spaces into at most `lines` lines no wider than `width`; a last line that still does not fit is cut at a word and ends in "..."."""
    out, cur, words = [], "", []
    for word in text.split():      # a word wider than the line (an unspaced title) is broken inside, so nothing runs off the card
        while f.getlength(word) > width and len(word) > 1:
            n = len(word) - 1
            while n > 1 and f.getlength(word[:n]) > width:
                n -= 1
            words.append(word[:n])
            word = word[n:]
        words.append(word)
    for word in words:
        trial = f"{cur} {word}".strip()
        if f.getlength(trial) <= width or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        last = out[-1]
        while last and f.getlength(last + "...") > width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        out[-1] = last + "..."
    return out


def _fit(text: str, f, width: int) -> str:
    """`text` on one line: cut to end in "..." when it is wider than `width`."""
    while text and f.getlength(text) > width:
        text = text[:-1].rstrip()
        if f.getlength(text + "...") <= width:
            return text + "..."
    return text


def _pill(d: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, f, room: int = 520) -> int:
    """A rounded chip with white text at (x, y), at most `room` wide; returns the x where it ends."""
    text = _fit(text, f, room - 56)
    w = int(f.getlength(text)) + 56
    d.rounded_rectangle((x, y, x + w, y + 72), radius=36, fill=fill)
    d.text((x + 28, y + 36), text, font=f, fill=WHITE, anchor="lm")
    return x + w


def render(card: Card) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    img.paste(_art(card.art_slug, (W, ART_H)), (0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((0, ART_H - 70, W, H + 80), radius=70, fill=PAPER)      # the paper rises over the art's foot with a soft round top
    seg = (W - 168) // len(KINDS)
    for i, c in enumerate(KINDS):      # a ribbon of the kinds' colours, one bar each
        d.rounded_rectangle((84 + i * seg + 4, ART_H - 38, 84 + (i + 1) * seg - 4, ART_H - 28), radius=5, fill=c)
    x, y = 84, ART_H - 6
    if card.days:
        _pill(d, x, y - 150, f"{card.days} day{'s' if card.days != 1 else ''}", KINDS[0], font(34, 650))
    title_f = font(112, 700)
    for n in (104, 92, 80, 70):                  # the title as large as two lines allow
        title_f = font(n, 700)
        lines = _wrap(card.title, title_f, W - 2 * x, 2)
        if len(lines) <= 2 and not lines[-1].endswith("..."):
            break
    for i, ln in enumerate(lines):
        d.text((x, y + i * int(title_f.size * 1.08)), ln, font=title_f, fill=INK)
    y += len(lines) * int(title_f.size * 1.08) + 18
    sub = " · ".join(p for p in (card.place, card.when) if p)
    d.text((x, y), _fit(sub, font(46, 560), W - 2 * x), font=font(46, 560), fill=INK2)
    y += 92
    stops = [s for s in card.route if s]
    px = x
    for i, s in enumerate(stops):
        px = _pill(d, px, y, s, KINDS[1 + i % 3 * 2 if i % 3 else 1], font(36, 640), (W - 2 * x - 56 * (len(stops) - 1)) // len(stops))
        if i < len(stops) - 1:
            d.text((px + 28, y + 36), "→", font=font(40, 600), fill=INK2, anchor="mm")
            px += 56
    if card.names:
        d.text((x, y + 120), _fit(f"With {card.names}", font(40, 560), W - 2 * x), font=font(40, 560), fill=INK, anchor="lm")
    mark = _mark(76)
    img.paste(mark, (x, H - 150), mark)
    d.text((x + 100, H - 112), "GitAway", font=font(40, 700), fill=INK, anchor="lm")
    if card.link:
        d.text((W - x, H - 112), _fit(card.link, font(36, 560), 600), font=font(36, 560), fill=INK2, anchor="rm")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
