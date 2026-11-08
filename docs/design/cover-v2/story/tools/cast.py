"""The cast as reusable SVG symbols, built on prototype E's construction (round head, dot eyes, blush,
flat fills, thick stroke arms) and refined: ears, nose, brows, expressions, real hair, outfits.

Coordinates: a head is drawn around its face centre (0, 0), face radius about 22. A body is drawn from the
neck base (0, 0) downward; the head sits at (0, -32) on it. fig() composes a body, arms and a head.
"""

# ---------------------------------------------------------------- palettes
PAL = {
    "maya": dict(skin="#C68A60", shade="#A9714C", blush="#E0745E", hair="#22171A", hair_hi="#4A3530", hair_lo="#170F11",
                 eye="#1C1311", brow="#22171A", mline="#8A3E33", lw=1.9, hairstyle="maya"),
    "sam": dict(skin="#8A5536", shade="#6C3F27", blush="#C0533C", hair="#171110", hair_hi="#3A2D29", eye="#140D0B",
                brow="#171110", mline="#E8C2A8", beard="#1D1513", lw=2.5, hairstyle="sam"),
    "rosa": dict(skin="#E2B38E", shade="#C48F6A", blush="#E8836E", hair="#D6D3DA", hair_hi="#F4F2F6", hair_lo="#AEA8B4",
                 eye="#2A1E1A", brow="#9F98A5", mline="#A24A40", lw=1.8, hairstyle="rosa", age=True),
    "tomas": dict(skin="#D79F7B", shade="#B98461", blush="#DE7C66", hair="#C6C2CA", hair_hi="#E9E7EC", eye="#2A1E1A",
                  brow="#D3D0D6", mline="#7A4234", beard="#ECEAEE", lw=2.3, hairstyle="tomas", age=True, glasses=True),
    # extra travellers for the last page (front view only)
    "dad": dict(skin="#EBC7A2", shade="#D2A982", blush="#E8907A", hair="#1E1B1E", hair_hi="#3C3840", eye="#1C1311",
                brow="#1E1B1E", mline="#9A4B40", lw=2.3, hairstyle="short"),
    "mom": dict(skin="#EFCDAB", shade="#D7B08C", blush="#EC8E7C", hair="#231C1E", hair_hi="#463A3C", hair_lo="#150F11",
                eye="#1C1311", brow="#231C1E", mline="#A64A42", lw=1.8, hairstyle="bob"),
    "kid1": dict(skin="#EBC7A2", shade="#D2A982", blush="#EE8A78", hair="#231C1E", hair_hi="#463A3C", hair_lo="#150F11",
                 eye="#1C1311", brow="#231C1E", mline="#A64A42", lw=1.6, hairstyle="pigtails"),
    "hik1": dict(skin="#F1CFB4", shade="#D9AE8F", blush="#EE8A78", hair="#B5522E", hair_hi="#D2744A", hair_lo="#8E3E22",
                 eye="#2A1E1A", brow="#9A4426", mline="#A64A42", lw=1.8, hairstyle="ponytail"),
    "hik2": dict(skin="#B9825C", shade="#9C6A47", blush="#D06A52", hair="#241A16", hair_hi="#46362E", eye="#1C1311",
                 brow="#241A16", mline="#7E3A30", lw=2.3, hairstyle="curly"),
    "city1": dict(skin="#D6A27C", shade="#BB875F", blush="#E07E66", hair="#3B6F8F", hair_hi="#5A8DAA", hair_lo="#2C5670",
                  eye="#1C1311", brow="#2A1E1A", mline="#9A4A40", lw=1.8, hairstyle="hijab"),
    "city2": dict(skin="#C9946C", shade="#AD7B55", blush="#D8765E", hair="#1E1716", hair_hi="#3E302C", eye="#1C1311",
                  brow="#1E1716", mline="#E2B79A", beard="#1E1716", lw=2.3, hairstyle="sam"),
    "gma": dict(skin="#7E4A30", shade="#633823", blush="#B4513A", hair="#E4E1E6", hair_hi="#FFFFFF", hair_lo="#C2BDC6",
                eye="#140D0B", brow="#CFCBD2", mline="#E0B39A", lw=1.8, hairstyle="curly", age=True),
    "kid2": dict(skin="#8A5536", shade="#6C3F27", blush="#C0533C", hair="#171110", hair_hi="#3A2D29", eye="#140D0B",
                 brow="#171110", mline="#E8C2A8", lw=1.6, hairstyle="puffs"),
}

# outfits: torso colour, its dark and light, sleeve, legs, shoes, kind
OUT = {
    ("maya", "home"): dict(top="#DE9E36", dark="#C0852A", light="#EDB65A", sleeve="#D3952F", legs="#45618F", legs2="#364D74", shoe="#EDE6DA", kind="sweater"),
    ("maya", "travel"): dict(top="#B4452F", dark="#923521", light="#CB5A41", sleeve="#A63F2A", legs="#2E3550", legs2="#232940", shoe="#6E4B33", cuff="#EFE4CF", kind="puffer"),
    ("sam", "home"): dict(top="#A1A5AD", dark="#868A93", light="#B9BDC4", sleeve="#969AA2", legs="#2F3447", legs2="#252938", shoe="#E9E4DA", kind="hoodie"),
    ("sam", "travel"): dict(top="#2F5B45", dark="#224434", light="#3D7058", sleeve="#2A5240", legs="#2E3036", legs2="#232429", shoe="#4A3A2E", kind="parka"),
    ("rosa", "home"): dict(top="#BE5A3B", dark="#9F4730", light="#D06E4E", sleeve="#B3533A", inner="#F3E8D5", legs="#4B4558", legs2="#3C3747", shoe="#5A3B30", kind="cardigan"),
    ("rosa", "travel"): dict(top="#EF7A61", dark="#D5614A", light="#F6957F", sleeve=None, legs="#EF7A61", legs2="#D5614A", shoe="#8A5A3A", kind="sundress"),
    ("tomas", "home"): dict(top="#2D3C60", dark="#22304E", light="#3B4C74", sleeve="#283757", inner="#DCE7F2", legs="#6A6157", legs2="#57504A", shoe="#3A2A22", kind="cardiganm"),
    ("tomas", "travel"): dict(top="#A9CBE8", dark="#8DB2D4", light="#C2DCF1", sleeve="#9DC0E0", legs="#E6D9BC", legs2="#D3C4A3", shoe="#8A6040", kind="linen", rolled=True),
    ("dad", "beach"): dict(top="#2E9C8F", dark="#227A70", light="#45B5A7", sleeve="#2A9083", legs="#E6D9BC", legs2="#D3C4A3", shoe="#8A6040", kind="tee", rolled=True),
    ("mom", "beach"): dict(top="#F4C24A", dark="#DCA932", light="#F8D370", sleeve="#EAB63E", legs="#3E5A86", legs2="#2E4569", shoe="#E9E4DA", kind="tee", rolled=True),
    ("kid1", "beach"): dict(top="#E2506A", dark="#C53D57", light="#EE6F86", sleeve="#D9485F", legs="#3E5A86", legs2="#2E4569", shoe="#E9E4DA", kind="tee", rolled=True),
    ("hik1", "hike"): dict(top="#5250E0", dark="#3F3DBF", light="#6E6CEC", sleeve="#4A48D2", legs="#3A3F4F", legs2="#2C303D", shoe="#6B4A33", kind="parka"),
    ("hik2", "hike"): dict(top="#E58A2B", dark="#C4721E", light="#F0A04A", sleeve="#D97F25", legs="#3A3F4F", legs2="#2C303D", shoe="#6B4A33", kind="parka"),
    ("city1", "city"): dict(top="#A445D8", dark="#8634B8", light="#B964E4", sleeve="#9A3ECC", legs="#2E3550", legs2="#232940", shoe="#3A2A22", kind="tee"),
    ("city2", "city"): dict(top="#F2EBDD", dark="#D9CFBC", light="#FFFFFF", sleeve="#E8E0D0", legs="#45618F", legs2="#364D74", shoe="#3A2A22", kind="tee"),
    ("gma", "city"): dict(top="#087F7B", dark="#06615E", light="#1A9A95", sleeve="#077370", inner="#F3E8D5", legs="#4B4558", legs2="#3C3747", shoe="#5A3B30", kind="cardigan"),
    ("kid2", "city"): dict(top="#F59A2E", dark="#D9821C", light="#F8B356", sleeve="#EC9128", legs="#2F3447", legs2="#252938", shoe="#E9E4DA", kind="tee", rolled=True),
}

EXPRS = ["neutral", "tired", "puzzled", "delighted", "smile", "grin", "surprised"]
MOUTH_DARK = "#5B2522"
GOLD = "#D9A73A"


# ---------------------------------------------------------------- face parts
def _eye(ex, ey, w, kind, c, skin, look=(0, 0)):
    lx, ly = look
    if kind == "happy":
        return f'<path d="M{ex-3.1*w:.2f} {ey+1.2:.2f}Q{ex:.2f} {ey-3.4:.2f} {ex+3.1*w:.2f} {ey+1.2:.2f}" stroke="{c}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
    if kind == "tired":
        return (f'<path d="M{ex-2.5*w:.2f} {ey:.2f}Q{ex:.2f} {ey+3.6:.2f} {ex+2.5*w:.2f} {ey:.2f}Z" fill="{c}"/>'
                f'<path d="M{ex-3*w:.2f} {ey-0.3:.2f}Q{ex:.2f} {ey-1.6:.2f} {ex+3*w:.2f} {ey-0.3:.2f}" stroke="{c}" stroke-width="1.5" fill="none" stroke-linecap="round"/>')
    rx, ry, hl = (2.6, 3.4, 1.0) if kind == "wide" else (2.3, 2.9, 0.8)
    s = (f'<ellipse cx="{ex+lx:.2f}" cy="{ey+ly:.2f}" rx="{rx*w:.2f}" ry="{ry:.2f}" fill="{c}"/>'
         f'<circle cx="{ex+lx+0.8*w:.2f}" cy="{ey+ly-1.1:.2f}" r="{hl:.2f}" fill="#fff" opacity=".9"/>')
    if kind == "smile":
        s += f'<path d="M{ex-3.2*w:.2f} {ey+3.4:.2f}Q{ex:.2f} {ey+1.5:.2f} {ex+3.2*w:.2f} {ey+3.4:.2f}" stroke="{skin}" stroke-width="1.9" fill="none"/>'
    return s


def _brow(ex, ey, w, side, lo, li, arch, c, lw):
    # side -1 = the eye on the viewer's left (its outer end is further left)
    ox, ix = ex + side * 4.3 * w, ex - side * 4.3 * w
    oy, iy = ey - 7.2 - lo, ey - 7.2 - li
    cx, cy = (ox + ix) / 2, min(oy, iy) - 1.6 - arch
    return f'<path d="M{ox:.2f} {oy:.2f}Q{cx:.2f} {cy:.2f} {ix:.2f} {iy:.2f}" stroke="{c}" stroke-width="{lw:.2f}" fill="none" stroke-linecap="round"/>'


def _mouth(mx, my, w, kind, c):
    if kind in ("delighted", "grin"):
        return (f'<path d="M{mx-6*w:.2f} {my-1.5:.2f}Q{mx:.2f} {my-0.4:.2f} {mx+6*w:.2f} {my-1.5:.2f}Q{mx+5*w:.2f} {my+7.6:.2f} {mx:.2f} {my+7.6:.2f}Q{mx-5*w:.2f} {my+7.6:.2f} {mx-6*w:.2f} {my-1.5:.2f}Z" fill="{MOUTH_DARK}"/>'
                f'<path d="M{mx-5*w:.2f} {my-1.1:.2f}Q{mx:.2f} {my-0.2:.2f} {mx+5*w:.2f} {my-1.1:.2f}L{mx+4.5*w:.2f} {my+1.3:.2f}Q{mx:.2f} {my+2.2:.2f} {mx-4.5*w:.2f} {my+1.3:.2f}Z" fill="#fff"/>'
                f'<ellipse cx="{mx:.2f}" cy="{my+5.6:.2f}" rx="{3*w:.2f}" ry="1.5" fill="#D4655A"/>')
    if kind == "surprised":
        return f'<ellipse cx="{mx:.2f}" cy="{my+1.6:.2f}" rx="{2.5*w:.2f}" ry="3.2" fill="{MOUTH_DARK}"/>'
    d = {
        "neutral": f"M{mx-3.6*w:.2f} {my:.2f}Q{mx:.2f} {my+1.4:.2f} {mx+3.6*w:.2f} {my:.2f}",
        "tired": f"M{mx-3.6*w:.2f} {my+0.8:.2f}Q{mx:.2f} {my-0.6:.2f} {mx+3.6*w:.2f} {my+0.8:.2f}",
        "puzzled": f"M{mx-4*w:.2f} {my+0.6:.2f}q{1.4*w:.2f} -1.7 {2.8*w:.2f} 0t{2.8*w:.2f} 0t{2.6*w:.2f} -0.8",
        "smile": f"M{mx-5.2*w:.2f} {my-1.2:.2f}Q{mx:.2f} {my+4.6:.2f} {mx+5.2*w:.2f} {my-1.2:.2f}",
    }[kind]
    return f'<path d="{d}" stroke="{c}" stroke-width="2" fill="none" stroke-linecap="round"/>'


# ---------------------------------------------------------------- hair
def _hair(style, view, p, layer):
    h, hi, lo = p["hair"], p.get("hair_hi", p["hair"]), p.get("hair_lo", p["hair"])
    F = view == "front"
    if style == "maya":
        if layer == "back":
            if F:
                return (f'<path d="M-23 6Q-26 -27 0 -27.5Q26 -27 23 6Q22 16 15 19L-15 19Q-22 16 -23 6Z" fill="{h}"/>'
                        f'<circle cx="-17" cy="18" r="8.5" fill="{h}"/><path d="M-21 15q4 -3 7 1" stroke="{hi}" stroke-width="1.3" fill="none"/>')
            return (f'<path d="M-24 6Q-26 -26 1 -27Q23 -26 21 -2L-4 18Q-18 20 -24 6Z" fill="{h}"/>'
                    f'<circle cx="-22.5" cy="13" r="9.6" fill="{h}"/><path d="M-27 10q5 -4 9 1M-25 17q4 2 7 -1" stroke="{hi}" stroke-width="1.3" fill="none"/>')
        if F:
            return (f'<path d="M-21.5 7Q-25 -25 -2 -25.5Q24 -25.5 21.8 6Q19.5 -7 11 -12.5Q3 -16 -5 -12Q-11 -9 -16 -9Q-20 -3 -21.5 7Z" fill="{h}"/>'
                    f'<path d="M-12 -19Q-2 -24 9 -21" stroke="{hi}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
                    f'<path d="M-20.5 0Q-24 9 -20.5 16Q-18.5 21 -21 25M20.8 -1Q23.5 7 20.5 14" stroke="{h}" stroke-width="1.9" fill="none" stroke-linecap="round"/>')
        return (f'<path d="M-22 9Q-25 -24 1 -25.5Q21 -25 21.5 0Q18 -10 10 -13Q1 -15 -4 -10Q-8 -5 -8 2Q-9 7 -12 9Q-17 11 -22 9Z" fill="{h}"/>'
                f'<path d="M-10 -20Q2 -25 13 -19" stroke="{hi}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
                f'<path d="M19.2 -5Q23 4 19.6 11M-10 4Q-12.5 11 -9.5 17" stroke="{h}" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    if style in ("sam", "short"):
        if layer == "back":
            return ""
        if F:
            s = (f'<path d="M-20.6 0Q-21.5 -24 0 -24.5Q21.5 -24 20.6 0Q19.5 -9 14 -12.5Q6 -15.5 0 -15Q-6 -15.5 -14 -12.5Q-19.5 -9 -20.6 0Z" fill="{h}"/>'
                 f'<path d="M-12 -19Q0 -23 12 -19" stroke="{hi}" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
            if style == "sam":
                s += f'<path d="M-20.6 -1L-19.8 9L-17.4 9L-17.8 -1ZM20.6 -1L19.8 9L17.4 9L17.8 -1Z" fill="{h}"/>'
            else:
                s += f'<path d="M-20 -8Q-12 -21 4 -19Q-8 -16 -12 -10Z" fill="{h}"/>'
            return s
        return (f'<path d="M-19.6 4Q-22.5 -23 1 -25Q21 -24.5 21 -2Q19 -11 12 -14Q3 -16.5 -3 -14Q-9 -10 -9.5 -2L-10 2Q-15 1 -19.6 4Z" fill="{h}"/>'
                f'<path d="M-4.6 -3L-3.4 6L-1.8 6L-2.8 -3Z" fill="{h}"/>'
                f'<path d="M-8 -20Q4 -24 14 -18" stroke="{hi}" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
    if style in ("rosa", "bob"):
        if layer == "back":
            if F:
                return f'<path d="M-25.5 15Q-30 -28 0 -28.5Q30 -28 25.5 15Q25 20.5 19 20.5L-19 20.5Q-25 20.5 -25.5 15Z" fill="{lo}"/>'
            return f'<path d="M-26.5 15Q-30 -27 1 -28Q26 -27 23.5 8L23 15Q12 22 -8 21.5Q-24 21 -26.5 15Z" fill="{lo}"/>'
        if F:
            return (f'<path d="M-24.5 16Q-27 -27 2 -27Q27 -26 24.5 16Q21.5 18.5 18 16.5Q19.5 4 17 -6Q9 -13 -2 -12.5Q-12 -11 -16.5 -3Q-19 6 -18 16.5Q-21.5 18.5 -24.5 16Z" fill="{h}"/>'
                    f'<path d="M-17 -3Q-10 -17 6 -15Q14 -13 17.5 -6Q8 -12 -2 -9Q-10 -7 -17 -3Z" fill="{h}"/>'
                    f'<path d="M-16 -16Q-4 -24.5 12 -19.5M-21.5 0Q-23 8 -21.5 14" stroke="{hi}" stroke-width="2" fill="none" stroke-linecap="round"/>')
        return (f'<path d="M-25.5 16Q-28 -26 3 -26.5Q24 -25.5 22.5 4Q19 -8 10 -12Q0 -13 -4 -6Q-7 4 -7 16.5Q-16 19.5 -25.5 16Z" fill="{h}"/>'
                f'<path d="M-4 -6Q2 -17 14 -15Q20 -12 22.5 -2Q15 -11 6 -10Q0 -9 -4 -6Z" fill="{h}"/>'
                f'<path d="M-14 -19Q0 -25.5 14 -19M-22 0Q-24 8 -22 14" stroke="{hi}" stroke-width="2" fill="none" stroke-linecap="round"/>')
    if style == "tomas":
        if layer == "back":
            return ""
        if F:
            return (f'<path d="M-20.8 3Q-22 -23 0 -24Q22 -23 20.8 3Q20 -6 17 -10Q13 -15.5 6 -16.5Q0 -15 -6 -16.5Q-13 -15.5 -17 -10Q-20 -6 -20.8 3Z" fill="{h}"/>'
                    f'<path d="M-12 -18.5Q-2 -22.5 10 -19.5M-15 -14Q-6 -19 4 -18" stroke="{hi}" stroke-width="1.4" fill="none" stroke-linecap="round"/>')
        return (f'<path d="M-22 8Q-24 -23 1 -24.5Q21 -24 21 0Q19.5 -8 16 -12Q10 -16.5 3 -17Q-5 -16 -8 -10Q-10 -3 -10 6Q-16 5 -22 8Z" fill="{h}"/>'
                f'<path d="M-10 -19Q2 -23.5 13 -18M-14 -12Q-4 -18.5 6 -17.5" stroke="{hi}" stroke-width="1.4" fill="none" stroke-linecap="round"/>')
    if style == "pigtails":
        if layer == "back":
            return f'<circle cx="-24" cy="4" r="7" fill="{h}"/><circle cx="24" cy="4" r="7" fill="{h}"/><circle cx="-19" cy="-2" r="2" fill="#E2506A"/><circle cx="19" cy="-2" r="2" fill="#E2506A"/>'
        return (f'<path d="M-21 6Q-24 -25 0 -25.5Q24 -25 21 6Q19 -8 10 -11Q0 -8 -10 -11Q-19 -8 -21 6Z" fill="{h}"/>'
                f'<path d="M-10 -19Q0 -23 10 -19" stroke="{hi}" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
    if style == "ponytail":
        if layer == "back":
            return f'<path d="M14 -16Q34 -14 30 10Q28 22 34 30Q22 28 22 14Q22 -2 12 -8Z" fill="{h}"/>'
        return (f'<path d="M-21 6Q-24 -25 0 -25.5Q24 -25 21 6Q19 -8 12 -12Q2 -15 -6 -12Q-15 -10 -21 6Z" fill="{h}"/>'
                f'<path d="M-12 -19Q0 -24 12 -19" stroke="{hi}" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    if style in ("curly", "puffs"):
        if layer == "back":
            if style == "puffs":
                return f'<circle cx="-20" cy="-17" r="10" fill="{h}"/><circle cx="20" cy="-17" r="10" fill="{h}"/>'
            pts = [(-20, -14), (-12, -22), (-2, -26), (9, -24), (18, -17), (23, -7), (-24, -4), (24, 3), (-25, 5)]
            return "".join(f'<circle cx="{x}" cy="{y}" r="9" fill="{lo}"/>' for x, y in pts)
        if style == "puffs":
            return f'<path d="M-20.6 0Q-21.5 -24 0 -24.5Q21.5 -24 20.6 0Q19.5 -9 14 -12.5Q0 -16 -14 -12.5Q-19.5 -9 -20.6 0Z" fill="{h}"/>'
        pts = [(-16, -16), (-7, -21), (3, -22), (12, -19), (18, -12), (-20, -7), (21, -3)]
        return ("".join(f'<circle cx="{x}" cy="{y}" r="7.5" fill="{h}"/>' for x, y in pts)
                + f'<path d="M-6 -24q3 -2 6 0M8 -22q3 -1 5 1" stroke="{hi}" stroke-width="1.4" fill="none" stroke-linecap="round"/>')
    if style == "hijab":
        if layer == "back":
            return f'<path d="M-27 4Q-30 -30 0 -31Q30 -30 27 4Q27 24 18 34L-18 34Q-27 24 -27 4Z" fill="{h}"/>'
        return (f'<path d="M-25 8Q-26 -27 0 -28Q26 -27 25 8Q22 -4 17 -10Q8 -15 0 -15Q-8 -15 -17 -10Q-22 -4 -25 8Z" fill="{h}"/>'
                f'<path d="M-24 10Q-20 22 -12 26M24 10Q20 22 12 26" stroke="{h}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                f'<path d="M-14 -21Q0 -26 14 -21" stroke="{hi}" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    return ""


def _beard(view, p, trim):
    b = p.get("beard")
    if not b:
        return ""
    if view == "front":
        if trim:
            return f'<path d="M-19.5 6Q-18 21.5 0 24.5Q18 21.5 19.5 6Q17 12 12.5 12.6Q7.5 9.6 0 9.9Q-7.5 9.6 -12.5 12.6Q-17 12 -19.5 6Z" fill="{b}"/>'
        return f'<path d="M-19.8 5Q-18.5 22 0 25.5Q18.5 22 19.8 5Q17.5 13 13 13.5Q8 9.6 0 9.8Q-8 9.6 -13 13.5Q-17.5 13 -19.8 5Z" fill="{b}"/>'
    return f'<path d="M-3.6 4L-3 10Q-0.5 23 10 25.5Q19 23.5 21.2 9Q19.8 12.6 17 13Q12.5 9.6 8 10Q3 10 0.5 13Q-1.6 9 -1.8 4Z" fill="{b}"/>'


def _hat(kind, view, F=None):
    F = view == "front"
    dx = 0 if F else 1.5
    if kind in ("beanie-cream", "beanie-char"):
        c, c2, rib = ("#EEE5D2", "#DCD0B7", "#C8BBA0") if kind == "beanie-cream" else ("#474A52", "#36393F", "#2A2C31")
        ribs = "".join(f'M{x+dx:.1f} -9.5v9' for x in range(-21, 23, 4))
        return (f'<path d="M{-23.5+dx} 0Q{-25+dx} -32 {dx} -32.5Q{25+dx} -32 {23.5+dx} 0Z" fill="{c}"/>'
                f'<path d="M{-14+dx} -26Q{-4+dx} -31 {8+dx} -29" stroke="#fff" stroke-opacity=".35" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
                f'<path d="M{-24.5+dx} -9.5Q{dx} -13 {24.5+dx} -9.5L{24.5+dx} 0.8Q{dx} -2.6 {-24.5+dx} 0.8Z" fill="{c2}"/>'
                f'<path d="{ribs}" stroke="{rib}" stroke-width="1.1"/>')
    if kind == "straw":
        rot = "" if F else ' transform="rotate(-5 0 -13)"'
        return (f'<g{rot}><ellipse cx="{dx}" cy="-12.5" rx="43" ry="9.5" fill="#E2C07A"/>'
                f'<ellipse cx="{dx}" cy="-12.5" rx="43" ry="9.5" fill="none" stroke="#C9A35A" stroke-width="1.2"/>'
                f'<path d="M{-19+dx} -14Q{-20.5+dx} -38 {dx} -38.5Q{20.5+dx} -38 {19+dx} -14Q{dx} -10 {-19+dx} -14Z" fill="#EBCD8C"/>'
                f'<path d="M{-19.4+dx} -18.5Q{dx} -15 {19.4+dx} -18.5L{19.2+dx} -13.5Q{dx} -10 {-19.2+dx} -13.5Z" fill="#E8735C"/>'
                f'<path d="M{-30+dx} -9l4 -1.6M{-18+dx} -6.5l4 -1M{14+dx} -6.5l4 -1M{26+dx} -9l4 -1.6M{-10+dx} -30l3 -1M{4+dx} -33l3 0" stroke="#C9A35A" stroke-width="1.1" stroke-linecap="round"/>'
                f'<rect x="{-15+dx}" y="-28" width="12" height="7.5" rx="3.5" fill="#2A2A31"/><rect x="{3+dx}" y="-28" width="12" height="7.5" rx="3.5" fill="#2A2A31"/>'
                f'<path d="M{-3+dx} -25.5h6" stroke="#2A2A31" stroke-width="1.6"/></g>')
    if kind == "panama":
        return (f'<ellipse cx="{dx}" cy="-14" rx="33" ry="7.5" fill="#E6D8BA"/>'
                f'<path d="M{-17.5+dx} -15Q{-19+dx} -35 {dx} -35.5Q{19+dx} -35 {17.5+dx} -15Q{dx} -11.5 {-17.5+dx} -15Z" fill="#F1E7CF"/>'
                f'<path d="M{-17.8+dx} -19.5Q{dx} -16 {17.8+dx} -19.5L{17.6+dx} -15Q{dx} -11.5 {-17.6+dx} -15Z" fill="#3B3330"/>'
                f'<path d="M{-6+dx} -34Q{dx} -29.5 {6+dx} -34" stroke="#D3C3A0" stroke-width="1.4" fill="none"/>')
    return ""


HATS = {"maya": "beanie-cream", "sam": "beanie-char", "rosa": "straw", "tomas": "panama"}

EXPR_SPEC = {  # eyes, brows (lift outer, lift inner, arch) for viewer-left and viewer-right, mouth
    "neutral": ("open", (0, 0, 0), (0, 0, 0), "neutral"),
    "tired": ("tired", (-1, 1.4, 0), (-1, 1.4, 0), "tired"),
    "puzzled": ("open", (2.6, 3.4, 1.4), (-0.6, -1.6, 0), "puzzled"),
    "delighted": ("happy", (2, 2, 0.6), (2, 2, 0.6), "delighted"),
    "smile": ("smile", (1, 1, 0.4), (1, 1, 0.4), "smile"),
    "grin": ("open", (1.4, 0.6, 0.3), (1.4, 0.6, 0.3), "grin"),
    "surprised": ("wide", (3.2, 3.2, 1), (3.2, 3.2, 1), "surprised"),
}


def head(name, view, expr, hat=None, look=(0, 0)):
    p = PAL[name]
    F = view == "front"
    style = p["hairstyle"]
    eye_kind, bl, br, mouth = EXPR_SPEC[expr]
    out = [_hair(style, view, p, "back")]
    if F:
        out.append(f'<ellipse cx="-20.4" cy="3" rx="3.8" ry="5.2" fill="{p["shade"]}"/><ellipse cx="20.4" cy="3" rx="3.8" ry="5.2" fill="{p["shade"]}"/>')
        out.append(f'<ellipse cx="0" cy="0.5" rx="20" ry="22.5" fill="{p["skin"]}"/>')
        eyes, mx, my, mw = [(-7.5, 2, 1.0, -1), (7.5, 2, 1.0, 1)], 0, 12, 1.0
    else:
        out.append(f'<ellipse cx="1.5" cy="0.5" rx="19.5" ry="22.5" fill="{p["skin"]}"/>')
        out.append(f'<path d="M19.4 -1Q25.2 6.4 20.4 8.8L18.6 8.8Z" fill="{p["skin"]}"/>')
        eyes, mx, my, mw = [(4.2, 2, 1.0, -1), (14.6, 2, 0.8, 1)], 11, 12, 0.86
    # shading under the hairline / jaw for depth (the one soft shade)
    out.append(f'<path d="M{-14 if F else -10} 17Q{0 if F else 4} 24.5 {14 if F else 18} 17Q{0 if F else 5} 22 {-14 if F else -10} 17Z" fill="{p["shade"]}" opacity=".35"/>')
    hs = p["hairstyle"]
    out.append(_hair(style, view, p, "front"))
    ear3q = (not F) and hs not in ("hijab",)
    if hs == "hijab":
        out.append(_hair("hijab", view, p, "front"))
    # blush
    if F:
        out.append(f'<circle cx="-11.5" cy="9.5" r="3.7" fill="{p["blush"]}" opacity=".3"/><circle cx="11.5" cy="9.5" r="3.7" fill="{p["blush"]}" opacity=".3"/>')
    else:
        out.append(f'<circle cx="1.5" cy="9.5" r="3.7" fill="{p["blush"]}" opacity=".3"/><circle cx="17.6" cy="9.5" r="2.6" fill="{p["blush"]}" opacity=".3"/>')
    out.append(_beard(view, p, name == "tomas"))
    if ear3q:
        out.append(f'<ellipse cx="-6.6" cy="3.5" rx="3.6" ry="5" fill="{p["skin"]}"/><path d="M-7.6 1.2q2 1.6 0 4.4" stroke="{p["shade"]}" stroke-width="1.2" fill="none"/>')
    for (ex, ey, w, side), b in zip(eyes, (bl, br)):
        out.append(_eye(ex, ey, w, eye_kind, p["eye"], p["skin"], look))
        out.append(_brow(ex, ey, w, side, b[0], b[1], b[2], p["brow"], p["lw"]))
    if F:
        out.append(f'<path d="M0.6 3.6Q3 7.8 -1.2 8.6" stroke="{p["shade"]}" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
    else:
        out.append(f'<path d="M19.4 7.6q-1.2 .5 -2.2 -.3" stroke="{p["shade"]}" stroke-width="1.2" fill="none" stroke-linecap="round"/>')
    if p.get("age"):
        if F:
            out.append(f'<path d="M-13.6 0.6l-2.2 -1.3M-13.7 3.2l-2.3 .5M13.6 0.6l2.2 -1.3M13.7 3.2l2.3 .5M-5.4 8.8Q-7.4 11.8 -6 14.6M5.4 8.8Q7.4 11.8 6 14.6" stroke="{p["shade"]}" stroke-width="1.05" fill="none" stroke-linecap="round" opacity=".8"/>')
        else:
            out.append(f'<path d="M-0.6 0.6l-2.2 -1.3M-0.7 3.2l-2.3 .5M5.6 9Q4 12 5.2 14.6" stroke="{p["shade"]}" stroke-width="1.05" fill="none" stroke-linecap="round" opacity=".8"/>')
    out.append(_mouth(mx, my, mw, mouth, p["mline"]))
    if p.get("glasses"):
        g1, g2 = "#6B3F1D", "#C08442"
        if F:
            out.append(f'<path d="M-14.6 1L-20.6 0M14.6 1L20.6 0" stroke="{g1}" stroke-width="1.8"/>'
                       f'<g fill="#fff" fill-opacity=".14" stroke="{g1}" stroke-width="2.3"><circle cx="-8" cy="2" r="6.5"/><circle cx="8" cy="2" r="6.5"/></g>'
                       f'<g fill="none" stroke="{g2}" stroke-width="2.3" stroke-dasharray="2.2 3.4"><circle cx="-8" cy="2" r="6.5"/><circle cx="8" cy="2" r="6.5"/></g>'
                       f'<path d="M-1.6 1.2Q0 -0.8 1.6 1.2" stroke="{g1}" stroke-width="1.8" fill="none"/>')
        else:
            out.append(f'<path d="M-1.6 1.6L-6.4 1" stroke="{g1}" stroke-width="1.8"/>'
                       f'<g fill="#fff" fill-opacity=".14" stroke="{g1}" stroke-width="2.2"><circle cx="4" cy="2" r="5.7"/><ellipse cx="15.2" cy="2" rx="4.4" ry="5.9"/></g>'
                       f'<g fill="none" stroke="{g2}" stroke-width="2.2" stroke-dasharray="2.2 3.4"><circle cx="4" cy="2" r="5.7"/><ellipse cx="15.2" cy="2" rx="4.4" ry="5.9"/></g>'
                       f'<path d="M9.7 1.4Q10.2 0 10.8 1.4" stroke="{g1}" stroke-width="1.6" fill="none"/>')
    if name in ("maya",):
        out.append(f'<circle cx="{-21 if F else -7}" cy="9.6" r="1.7" fill="{GOLD}"/>' + (f'<circle cx="21" cy="9.6" r="1.7" fill="{GOLD}"/>' if F else ""))
    if name in ("rosa",):
        out.append(f'<g fill="none" stroke="{GOLD}" stroke-width="1.5"><circle cx="{-19.8 if F else -6.4}" cy="18.6" r="3.3"/>' + ('<circle cx="19.8" cy="18.6" r="3.3"/>' if F else "") + '</g>')
    if hat:
        out.append(_hat(hat, view))
    return "".join(out)


# ---------------------------------------------------------------- bodies
def _legs(o, pose):
    L, L2, S = o["legs"], o["legs2"], o["shoe"]
    if pose == "sit":
        s = (f'<rect x="-27" y="104" width="21" height="56" rx="9" fill="{L2}"/><rect x="6" y="104" width="21" height="56" rx="9" fill="{L2}"/>'
             f'<rect x="-31.5" y="84" width="63" height="34" rx="16" fill="{L}"/><path d="M0 92v24" stroke="{L2}" stroke-width="1.4"/>')
        if o["kind"] == "sundress":
            s = (f'<rect x="-26" y="108" width="19" height="52" rx="8" fill="#E2B38E"/><rect x="7" y="108" width="19" height="52" rx="8" fill="#E2B38E"/>'
                 f'<path d="M-36 82L36 82L40 120Q0 126 -40 120Z" fill="{L}"/>')
        s += f'<ellipse cx="-16.5" cy="162" rx="14" ry="6.5" fill="{S}"/><ellipse cx="16.5" cy="162" rx="14" ry="6.5" fill="{S}"/>'
        return s
    # stand
    k = o["kind"]
    if k == "sundress":
        return (f'<rect x="-21" y="120" width="16" height="68" rx="7" fill="#E2B38E"/><rect x="5" y="120" width="16" height="68" rx="7" fill="#E2B38E"/>'
                f'<path d="M-24 186h20M4 186h20" stroke="{S}" stroke-width="5" stroke-linecap="round"/>')
    s = (f'<rect x="-25" y="86" width="22" height="102" rx="9" fill="{L}"/><rect x="3" y="86" width="22" height="102" rx="9" fill="{L}"/>'
         f'<path d="M-3 96v88" stroke="{L2}" stroke-width="1.4"/>')
    if o.get("rolled") and k == "linen":
        s = (f'<rect x="-24" y="160" width="20" height="28" rx="8" fill="#D79F7B"/><rect x="4" y="160" width="20" height="28" rx="8" fill="#D79F7B"/>'
             f'<rect x="-25" y="86" width="22" height="80" rx="9" fill="{L}"/><rect x="3" y="86" width="22" height="80" rx="9" fill="{L}"/>'
             f'<rect x="-26" y="156" width="24" height="9" rx="4" fill="{L2}"/><rect x="2" y="156" width="24" height="9" rx="4" fill="{L2}"/>')
    if k in ("puffer", "parka"):
        s += f'<rect x="-27" y="164" width="25" height="26" rx="7" fill="{S}"/><rect x="2" y="164" width="25" height="26" rx="7" fill="{S}"/>'
        if o.get("cuff"):
            s += f'<rect x="-28" y="160" width="27" height="9" rx="4" fill="{o["cuff"]}"/><rect x="1" y="160" width="27" height="9" rx="4" fill="{o["cuff"]}"/>'
        return s
    return s + f'<ellipse cx="-15" cy="190" rx="15" ry="6.5" fill="{S}"/><ellipse cx="15" cy="190" rx="15" ry="6.5" fill="{S}"/>'


def _torso(name, o):
    p = PAL[name]
    k, T, D, Lt = o["kind"], o["top"], o["dark"], o["light"]
    wide = name in ("sam", "tomas", "dad", "hik2", "city2")
    a = 30 if wide else 27
    base = f"M-{a} 20Q-{a} 3 -13 1L13 1Q{a} 3 {a} 20L{a+3} 94L-{a+3} 94Z"
    if k == "sweater":
        return (f'<path d="{base}" fill="{T}"/><path d="M-9 1Q0 9.5 9 1" stroke="{D}" stroke-width="3.6" fill="none"/>'
                f'<path d="M-6 16l3 6-3 6 3 6-3 6 3 6-3 6 3 6-3 6 3 6M6 16l-3 6 3 6-3 6 3 6-3 6 3 6-3 6 3 6-3 6" stroke="{D}" stroke-width="1.3" fill="none" opacity=".55"/>'
                f'<rect x="-{a+3}" y="85" width="{2*a+6}" height="9" rx="3" fill="{D}"/>')
    if k == "puffer":
        q = "".join(f'M-{a+4} {y}Q0 {y+5} {a+4} {y}' for y in (26, 46, 66, 86))
        return (f'<path d="M-{a+4} 22Q-{a+4} 2 -13 -1L13 -1Q{a+4} 2 {a+4} 22L{a+7} 104L-{a+7} 104Z" fill="{T}"/>'
                f'<path d="{q}" stroke="{D}" stroke-width="1.7" fill="none"/><path d="M0 8V104" stroke="{D}" stroke-width="1.5"/>'
                f'<path d="M-13 -3Q0 -7 13 -3L12 9Q0 12 -12 9Z" fill="{Lt}"/><path d="M-12 3Q0 6 12 3" stroke="{D}" stroke-width="1.2" fill="none"/>')
    if k == "hoodie":
        return (f'<path d="{base}" fill="{T}"/>'
                f'<path d="M-17 -1Q0 13 17 -1Q15 -7 0 -7Q-15 -7 -17 -1Z" fill="{D}"/><path d="M-11 -1Q0 7 11 -1" stroke="{Lt}" stroke-width="1.5" fill="none"/>'
                f'<path d="M-5 6L-6 27M5 6L6 25" stroke="{Lt}" stroke-width="1.7" stroke-linecap="round"/>'
                f'<path d="M-18 62L18 62L22 85L-22 85Z" stroke="{D}" stroke-width="1.7" fill="none"/>'
                f'<rect x="-{a+3}" y="86" width="{2*a+6}" height="8" rx="3" fill="{D}"/>')
    if k == "parka":
        sc = "" if name != "sam" else (
            f'<path d="M-15 -4Q0 6 15 -4L16 6Q0 16 -16 6Z" fill="#B5382E"/>'
            f'<path d="M-15 0Q0 9 15 0M-15.5 4Q0 13 15.5 4M-8 -1V12M2 2V14M10 -1V10" stroke="#2B2B33" stroke-width="1.1" fill="none" opacity=".7"/>'
            f'<path d="M-6 -1V13M6 0V12" stroke="#E8C547" stroke-width=".9" opacity=".8"/>'
            f'<path d="M5 8L14 9L12 44L4 42Z" fill="#B5382E"/><path d="M6 18L13 19M5.5 28L12.6 29M5 38L12 39M8 9L7 43" stroke="#2B2B33" stroke-width="1.1" opacity=".7"/>'
            f'<path d="M4 42l1 4M7 42.5l.6 4M10 43l.4 4" stroke="#B5382E" stroke-width="1.2"/>')
        return (f'<path d="M-24 2Q-26 -12 0 -13Q26 -12 24 2Z" fill="{D}"/>'
                f'<path d="M-{a+4} 22Q-{a+4} 2 -13 -1L13 -1Q{a+4} 2 {a+4} 22L{a+6} 106L-{a+6} 106Z" fill="{T}"/>'
                f'<path d="M0 6V106" stroke="{D}" stroke-width="1.6"/>'
                f'<rect x="-{a}" y="66" width="18" height="14" rx="3" fill="{D}" opacity=".55"/><rect x="{a-18}" y="66" width="18" height="14" rx="3" fill="{D}" opacity=".55"/>'
                f'<rect x="-{a+6}" y="98" width="{2*a+12}" height="8" rx="3" fill="{D}"/>' + sc)
    if k in ("cardigan", "cardiganm"):
        inner = o["inner"]
        s = f'<path d="{base}" fill="{T}"/><path d="M-10 1L10 1L5 94L-5 94Z" fill="{inner}"/>'
        s += f'<path d="M-10 1L-5 94M10 1L5 94" stroke="{D}" stroke-width="1.8"/>'
        if k == "cardiganm":
            s += (f'<path d="M-10 0L-2 10L-8 13ZM10 0L2 10L8 13Z" fill="#F5F8FB"/>'
                  f'<g fill="#C9A66B"><circle cx="-6.6" cy="40" r="1.9"/><circle cx="-6" cy="56" r="1.9"/><circle cx="-5.4" cy="72" r="1.9"/></g>')
        else:
            s += f'<path d="M-6 4Q0 12 6 4" stroke="{GOLD}" stroke-width="1" fill="none"/><circle cx="0" cy="11.6" r="1.6" fill="{GOLD}"/>'
        return s + f'<rect x="-{a+3}" y="87" width="{2*a+6}" height="7" rx="3" fill="{D}"/>'
    if k == "sundress":
        return (f'<path d="M-{a} 20Q-{a} 3 -12 1L12 1Q{a} 3 {a} 20L{a-1} 32L-{a-1} 32Z" fill="{p["skin"]}"/>'
                f'<path d="M-21 12Q-20 8 -12 9Q0 13 12 9Q20 8 21 12L24 66L-24 66Z" fill="{T}"/>'
                f'<path d="M-14 9L-15 1M14 9L15 1" stroke="{T}" stroke-width="2.6" stroke-linecap="round"/>'
                f'<path d="M-24 64L24 64L40 150Q0 158 -40 150Z" fill="{T}"/>'
                f'<path d="M-12 74L-20 148M0 74L0 154M12 74L20 148" stroke="{D}" stroke-width="1.3" opacity=".7"/>'
                f'<rect x="-25" y="60" width="50" height="8" rx="3" fill="{D}"/>')
    if k == "linen":
        return (f'<path d="{base}" fill="{T}"/><path d="M-10 0L0 15L10 0Z" fill="{p["skin"]}"/>'
                f'<path d="M-11 -1L-3 10L-9 15ZM11 -1L3 10L9 15Z" fill="{Lt}"/>'
                f'<path d="M0 15V94" stroke="{D}" stroke-width="1.4"/><g fill="#F5F8FB"><circle cx="0" cy="34" r="1.5"/><circle cx="0" cy="52" r="1.5"/><circle cx="0" cy="70" r="1.5"/></g>'
                f'<rect x="-{a+8}" y="18" width="16" height="16" rx="3" fill="{D}" opacity="0"/>')
    # tee
    return (f'<path d="{base}" fill="{T}"/><path d="M-9 1Q0 10 9 1" stroke="{D}" stroke-width="3" fill="none"/>')


def body(name, outfit, pose, view):
    o = OUT[(name, outfit)]
    p = PAL[name]
    neck = f'<rect x="-6.5" y="-16" width="13" height="22" rx="5" fill="{p["shade"]}"/>'
    inner = (neck + _torso(name, o) + _legs(o, pose)) if pose == "sit" else (_legs(o, pose) + neck + _torso(name, o))
    if view == "3q":
        inner = f'<g transform="scale(.9 1)">{inner}</g>'
    return inner


# ---------------------------------------------------------------- symbols and composition
HEAD_VB = (-50, -60, 100, 116)
BODY_VB = (-60, -20, 120, 240)
_used = set()


def head_id(name, view, expr, hat, look=(0, 0)):
    return f"h-{name}-{view}-{expr}" + ("-hat" if hat else "") + (f"-l{look[0]}" if look != (0, 0) else "")


def body_id(name, outfit, pose, view):
    return f"b-{name}-{outfit}-{pose}-{view}"


SYMS = {}


def ensure_head(name, view, expr, hat, look=(0, 0)):
    i = head_id(name, view, expr, hat, look)
    if i not in SYMS:
        hk = HATS.get(name) if hat else None
        SYMS[i] = (HEAD_VB, head(name, view, expr, hk, look))
    return i


def ensure_body(name, outfit, pose, view):
    i = body_id(name, outfit, pose, view)
    if i not in SYMS:
        SYMS[i] = (BODY_VB, body(name, outfit, pose, view))
    return i


def symbol_svg(i):
    vb, inner = SYMS[i]
    return f'<symbol id="{i}" viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}" overflow="visible">{inner}</symbol>'


def sleeve_of(name, outfit):
    return OUT[(name, outfit)]["sleeve"]


def _split(p0, p1, p2, t=.55):
    a = (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
    b = (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)
    m = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return a, m


def arm(name, outfit, pts, w=None, finger=None, fist=False, hand=True):
    """A thick stroked arm from shoulder through an elbow control point to the hand, as in E."""
    o, p = OUT[(name, outfit)], PAL[name]
    k = o["kind"]
    w = w or (19 if k in ("puffer", "parka") else 17 if name in ("sam", "tomas", "dad", "hik2", "city2") else 15)
    (x0, y0), (x1, y1), (x2, y2) = pts
    d = f"M{x0} {y0}Q{x1} {y1} {x2} {y2}"
    s = ""
    if o["sleeve"] is None:  # bare arms
        s += f'<path d="{d}" stroke="{p["skin"]}" stroke-width="{w-3}" fill="none" stroke-linecap="round"/>'
    elif o.get("rolled"):
        a, m = _split((x0, y0), (x1, y1), (x2, y2))
        s += f'<path d="{d}" stroke="{p["skin"]}" stroke-width="{w-3}" fill="none" stroke-linecap="round"/>'
        s += f'<path d="M{x0} {y0}Q{a[0]:.1f} {a[1]:.1f} {m[0]:.1f} {m[1]:.1f}" stroke="{o["sleeve"]}" stroke-width="{w+1}" fill="none" stroke-linecap="round"/>'
    else:
        s += f'<path d="{d}" stroke="{o["sleeve"]}" stroke-width="{w}" fill="none" stroke-linecap="round"/>'
        if k in ("puffer", "parka", "sweater", "hoodie"):
            # cuff
            dx, dy = x2 - x1, y2 - y1
            n = max((dx * dx + dy * dy) ** .5, 1)
            cx, cy = x2 - dx / n * 6, y2 - dy / n * 6
            s += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{w/2+.5:.1f}" fill="{o["dark"]}"/>'
    if hand:
        r = 7 if w >= 17 else 6.4
        if finger:
            fx, fy = finger
            s += f'<path d="M{x2} {y2}l{fx} {fy}" stroke="{p["skin"]}" stroke-width="4.2" stroke-linecap="round"/>'
        s += f'<circle cx="{x2}" cy="{y2}" r="{r + (1 if fist else 0)}" fill="{p["skin"]}"/>'
        if fist:
            s += f'<path d="M{x2-4} {y2-2}h8M{x2-4} {y2+1.5}h8" stroke="{p["shade"]}" stroke-width="1"/>'
    return s


def use(i, vb, x=0, y=0):
    return f'<use href="#{i}" x="{vb[0]+x}" y="{vb[1]+y}" width="{vb[2]}" height="{vb[3]}"/>'


def default_arms(name, outfit, view="front"):
    a = 31 if name in ("sam", "tomas", "dad", "hik2", "city2") else 28
    if OUT[(name, outfit)]["kind"] in ("puffer", "parka"):
        a += 3
    if view == "3q":
        return [dict(pts=[(-a * .9 + 3, 10), (-a * .9 - 2, 52), (-a * .9 + 1, 92)]), dict(pts=[(a * .9 - 1, 10), (a * .9 + 5, 52), (a * .9 + 4, 92)])]
    return [dict(pts=[(-a, 10), (-a - 6, 52), (-a - 3, 92)]), dict(pts=[(a, 10), (a + 6, 52), (a + 3, 92)])]


def fig(name, outfit="home", x=0, y=0, s=1.0, pose="sit", view="front", expr="neutral", flip=False,
        arms=None, head_view=None, hat=None, head_rot=0, mid="", back="", face=True, look=(0, 0), who=None, lean=0, front=""):
    """One character. (x, y) is the neck base in scene units; s is the scale (head radius 22*s)."""
    hv = head_view or view
    if hat is None:
        hat = outfit == "travel"
    hid = ensure_head(name, hv, expr, hat, look)
    bid = ensure_body(name, outfit, pose, view)
    arms = default_arms(name, outfit, view) if arms is None else arms
    sx = -s if flip else s
    parts = [back, use(bid, BODY_VB), mid]
    for a in arms:
        parts.append(arm(name, outfit, a["pts"], a.get("w"), a.get("finger"), a.get("fist", False), a.get("hand", True)))
    hg = use(hid, HEAD_VB, 0, -32)
    top = -42 if not hat else -50
    anchor = (f'<rect data-face="{who or name}" x="-25" y="{-32+top}" width="50" height="{-top+26}" fill="none" stroke="none"/>' if face else "")
    if head_rot:
        parts.append(f'<g transform="rotate({head_rot} 0 -10)">{hg}{anchor}</g>')
    else:
        parts.append(hg + anchor)
    parts.append(front)
    inner = "".join(parts)
    if lean:
        inner = f'<g transform="rotate({lean} 0 100)">{inner}</g>'
    return f'<g transform="translate({x} {y}) scale({sx} {s})">{inner}</g>'
