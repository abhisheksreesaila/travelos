"""The two character sheets (1600 x 900), drawn from the shared cast symbols."""
from cast import fig, PAL, OUT

PAPER = "#FBF6EC"
LABEL = 'font-family="Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif" fill="#6b6157"'


def _label(x, y, text, size=17, anchor="middle", italic=True):
    st = ' font-style="italic"' if italic else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"{st} {LABEL}>{text}</text>'


def _swatches(x, y, cols):
    return "".join(f'<rect x="{x+i*30}" y="{y}" width="24" height="24" rx="6" fill="{c}" stroke="rgba(43,38,32,.15)"/>' for i, c in enumerate(cols))


def sheet(a, b, title, sub, home_lbl, travel_lbl, travel_outfit="travel"):
    out = [f'<rect width="1600" height="900" fill="{PAPER}"/>',
           '<path d="M800 40V860" stroke="#e7dcc8" stroke-width="2" stroke-dasharray="2 8"/>',
           f'<text x="70" y="92" font-size="40" {LABEL.replace("#6b6157", "#2b2620")} font-family="Iowan Old Style, Palatino, Georgia, serif">{title}</text>',
           _label(72, 124, sub, 18, "start")]
    out.append(_swatches(1240, 70, [PAL[a]["skin"], PAL[a]["hair"], OUT[(a, "home")]["top"], OUT[(a, travel_outfit)]["top"]]))
    out.append(_swatches(1240, 102, [PAL[b]["skin"], PAL[b]["hair"], OUT[(b, "home")]["top"], OUT[(b, travel_outfit)]["top"]]))
    out.append(_label(1372, 88, a.capitalize() if a != "tomas" else "Tomás", 15, "start"))
    out.append(_label(1372, 120, b.capitalize() if b != "tomas" else "Tomás", 15, "start"))
    # left page: home outfit, front and three-quarter
    s, ny = 1.72, 470
    xs = [150, 320, 500, 670]
    out.append(fig(a, "home", xs[0], ny, s, "stand", "front", "neutral", face=False))
    out.append(fig(a, "home", xs[1], ny, s, "stand", "3q", "smile", face=False))
    out.append(fig(b, "home", xs[2], ny, s, "stand", "front", "neutral", face=False))
    out.append(fig(b, "home", xs[3], ny, s, "stand", "3q", "smile", face=False))
    for x, t in zip(xs, ["front", "three-quarter", "front", "three-quarter"]):
        out.append(_label(x, 832, t, 16))
    out.append(_label(410, 868, home_lbl, 18))
    # right page, top: expressions
    hs, hy = 1.9, 300
    groups = [("puzzled", 960), ("delighted", 1190), ("smiling at each other", 1420)]
    out.append(f'<clipPath id="clip-{a}"><rect x="820" y="120" width="740" height="232"/></clipPath><g clip-path="url(#clip-{a})">')
    for g, cx in groups:
        if g.startswith("smiling"):
            out.append(fig(a, "home", cx - 52, hy, hs, "sit", "front", "smile", head_view="3q", arms=[], face=False))
            out.append(fig(b, "home", cx + 52, hy, hs, "sit", "front", "smile", head_view="3q", flip=True, arms=[], face=False))
        else:
            out.append(fig(a, "home", cx - 52, hy, hs, "sit", "front", g, arms=[], face=False))
            out.append(fig(b, "home", cx + 52, hy, hs, "sit", "front", g, arms=[], face=False))
    out.append('</g>')
    out.append('<path d="M840 352H1540" stroke="#e7dcc8" stroke-width="1.5"/>')
    for g, cx in groups:
        out.append(_label(cx, 380, g, 16))
    # right page, bottom: travel outfit
    ts, ty = 1.26, 585
    txs = [930, 1060, 1260, 1400]
    out.append(fig(a, travel_outfit, txs[0], ty, ts, "stand", "front", "delighted", face=False))
    out.append(fig(a, travel_outfit, txs[1], ty, ts, "stand", "3q", "smile", face=False))
    out.append(fig(b, travel_outfit, txs[2], ty, ts, "stand", "front", "delighted", face=False))
    out.append(fig(b, travel_outfit, txs[3], ty, ts, "stand", "3q", "smile", face=False))
    out.append(_label(1180, 868, travel_lbl, 18))
    return "".join(out)


def maya_sam():
    return sheet("maya", "sam", "Maya &amp; Sam", "early 30s · she is South Asian, he is Black · home and Lake Tahoe in winter",
                 "home: mustard knit sweater · heather-gray hoodie", "travel: rust puffer, cream beanie · forest parka, plaid scarf")


def rosa_tomas():
    return sheet("rosa", "tomas", "Rosa &amp; Tomás", "late 60s, Lisbon · silver bob, gold hoops · round tortoiseshell glasses",
                 "home: terracotta cardigan · navy cardigan", "beach: straw hat, coral sundress · linen shirt, panama")
