"""The accent and the kinds' colours (Direction A, F-200; this was test_orange.py, D-60/D-62: the brief dropped "orange everywhere"). The accent is ink, a black pill in light
and a white one in dark, so the only colour on a screen is a kind's; text on the accent reads; the accent never doubles as a data colour; the kinds stay apart and read on their tints.
Reads the real stylesheet, so a changed token is judged by the numbers, not by eye."""
import colorsys
import re
from pathlib import Path

TOKENS = (Path(__file__).resolve().parent.parent / "assets" / "css" / "tokens.css").read_text(encoding="utf-8")
KINDS = ("flight", "stay", "car", "tix", "wx", "food", "see", "ride")


def block(start):
    """The declarations of the block that begins at `start` in tokens.css, as {name: value}."""
    i = TOKENS.index(start)
    body = TOKENS[i:TOKENS.index("}", i)]
    return {k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body)}


LIGHT = block("/* ---------- light (the default) ---------- */")
DARK = block(":root[data-mode=\"dark\"] {")
BASE = block(":root {\n  /* THE SCALE.")


def luminance(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def hsv(hex_):
    return colorsys.rgb_to_hsv(*(int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def test_the_accent_is_ink_black_in_light_and_white_in_dark():
    assert LIGHT["--accent"] == LIGHT["--ink"] == "#0B0B0D"
    assert DARK["--accent"] == DARK["--ink"] == "#F5F5F7"
    for mode in (LIGHT, DARK):
        channels = [int(mode["--accent"][i:i + 2], 16) for i in (1, 3, 5)]
        assert max(channels) - min(channels) <= 4, "a neutral, not a colour"


def test_text_on_the_accent_reads_at_4_5_to_1_in_both_modes():
    for mode in (LIGHT, DARK):
        assert contrast(mode["--accent"], mode["--on-accent"]) >= 4.5
        assert contrast(mode["--ink"], mode["--on-ink"]) >= 4.5


def test_the_accent_reads_as_text_on_the_canvas_and_on_cards():
    for mode in (LIGHT, DARK):
        for surface in ("--paper", "--card", "--card-2", "--paper-2"):
            assert contrast(mode["--accent"], mode[surface]) >= 7, surface


def test_secondary_and_caption_text_read_on_every_surface():
    for mode in (LIGHT, DARK):
        for text in ("--ink-2", "--ink-3"):
            for surface in ("--paper", "--card", "--card-2", "--paper-2"):
                assert contrast(mode[text], mode[surface]) >= 4.5, (text, surface)


def test_the_mark_is_an_ink_tile_with_the_three_nodes_in_kind_colours():
    for mode in (LIGHT, DARK):
        assert mode["--mark-bg"] == mode["--ink"]                       # an ink tile in light, a white one in dark
        assert contrast(mode["--mark-bg"], mode["--mark-line"]) >= 4.5   # the fork's line reads on it
        nodes = [mode[f"--mark-{n}"] for n in "abc"]
        assert len(set(nodes)) == 3 and all(hsv(n)[1] > 0.3 for n in nodes)   # three colours, all colourful
        assert all(contrast(n, mode["--mark-bg"]) >= 3 for n in nodes)        # each node shows on the tile


def test_the_accent_is_never_a_data_colour():
    for kind in KINDS:
        fill = BASE[f"--k-{kind}"]
        assert fill.upper() not in (LIGHT["--accent"], DARK["--accent"])
        assert hsv(fill)[1] > 0.5, f"{kind} is a colour, the accent a neutral"


def test_the_kinds_stay_distinct():
    hues = sorted(hsv(BASE[f"--k-{k}"])[0] * 360 for k in KINDS)
    gaps = [b - a for a, b in zip(hues, hues[1:])] + [360 - hues[-1] + hues[0]]
    assert min(gaps) >= 12, f"two kinds are too close in hue: {hues}"
    assert len({BASE[f"--k-{k}"] for k in KINDS}) == len(KINDS)


def test_text_on_every_kind_fill_reads():
    for kind in KINDS:
        on = BASE["--k-ride-on"] if kind == "ride" else BASE["--k-on"]
        assert contrast(BASE[f"--k-{kind}"], on) >= 5, kind


def test_every_kinds_ink_reads_on_its_tint_and_on_a_card_in_both_modes():
    for mode in (LIGHT, DARK):
        for kind in KINDS:
            assert contrast(mode[f"--k-{kind}-i"], mode[f"--k-{kind}-t"]) >= 7, kind
            assert contrast(mode[f"--k-{kind}-i"], mode["--card"]) >= 7, kind
            assert contrast(mode["--ink"], mode[f"--k-{kind}-t"]) >= 7, kind     # ink text on a kind's tint (a plan block)
