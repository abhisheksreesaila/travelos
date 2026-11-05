"""The orange accent on Coast (D-60, D-62): the captain wants GitAway orange everywhere, white text on it must read, and the accent never doubles as a data colour.
Reads the real stylesheets, so a changed token is judged by the numbers, not by eye."""
import colorsys
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
OMXQUA = (CSS / "omxqua.css").read_text(encoding="utf-8")
TOKENS = (CSS / "tokens.css").read_text(encoding="utf-8")


def block(selector):
    """The declarations of the rule that starts with `selector` in omxqua.css, as {name: value}."""
    start = OMXQUA.index(selector + " {")
    body = OMXQUA[start:OMXQUA.index("}", start)]
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))


COAST = block(".oq-family-travel.oq-light")


def luminance(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def hue(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def test_the_accent_is_orange_not_teal():
    accent = COAST["--oq-accent"].strip()
    assert accent == "#c0401c"
    assert 10 <= hue(accent) <= 25, "an orange-red hue, the brand coral's family"


def test_white_on_the_accent_reads_at_4_5_to_1():
    assert COAST["--oq-on-accent"].strip() == "#ffffff"
    assert round(contrast("#c0401c", "#ffffff"), 2) == 5.26


def test_the_accent_reads_as_text_on_every_surface():
    for name, expected in (("--oq-surface-0", 4.63), ("--oq-surface-1", 5.18), ("--oq-surface-2", 5.26)):
        assert round(contrast("#c0401c", COAST[name].strip()), 2) == expected, name


def test_the_logo_tile_is_the_brand_coral_with_a_dark_fork():
    assert re.search(r"--brand-orange:\s*#FF7352", TOKENS)
    assert round(contrast("#FF7352", "#1E1A2E"), 2) == 6.3            # the fork on the tile; white on it would be 2.68
    assert round(contrast("#FF7352", "#FFFFFF"), 2) == 2.68            # why the fork is not white


def test_no_data_colour_is_the_accent_or_close_to_it():
    accent_hue = hue("#c0401c")
    for n in range(1, 7):
        colour = COAST[f"--oq-data-{n}"].strip()
        assert colour != "#c0401c"
        gap = abs(hue(colour) - accent_hue)
        gap = min(gap, 360 - gap)
        # brown (data-6) is a neutral and amber (data-4) sits 40 degrees off; nothing is nearer than that
        assert gap >= 25 or n == 6, f"data-{n} {colour} is {gap:.0f} degrees from the accent"


def test_food_is_rose_and_the_five_kinds_stay_distinct():
    assert COAST["--oq-data-2"].strip() == "#b0306f"
    kinds = {}
    for kind, data in (("flight", 3), ("stay", 5), ("car", 4), ("food", 2), ("see", 1)):
        assert re.search(rf"--oq-k-{kind}: var\(--oq-data-{data}\)", OMXQUA), kind
        kinds[kind] = COAST[f"--oq-data-{data}"].strip()
    assert len(set(kinds.values())) == 5
    hues = sorted(hue(c) for c in kinds.values())
    gaps = [b - a for a, b in zip(hues, hues[1:])] + [360 - hues[-1] + hues[0]]
    assert min(gaps) >= 25, f"two kinds are too close in hue: {kinds}"


def test_every_data_colour_reads_on_its_own_tint():
    for n in range(1, 7):
        colour = COAST[f"--oq-data-{n}"].strip()
        assert contrast(colour, COAST["--oq-surface-1"].strip()) >= 3, f"data-{n}"
