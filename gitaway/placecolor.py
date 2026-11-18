"""Each place's own vivid colour (F-296, D-959; docs/design/palette-bo, look C "Stage"). The Stage is neutral grey, so colour comes only from content: a place's lane tile, the opened square's band
and the cover's postcard wear the colour of the place, and the words on it the ink that passes.

    of(place) -> (fill, on)    the place's colour and the colour of words on it (4.5:1 or more, tests/test_placecolor.py); a neutral grey and white for a place with no colour of its own
    style(place) -> str        "--pc:#0071E3;--pc-on:#FFFFFF", the inline style an element carries so its stylesheet can say var(--pc) and var(--pc-on)
    skyline(place) -> str      a small flat skyline in shades of the place's colour (a sun, two hills): the lane tile's picture; its colours are --pc in assets/css/placeart.css

No place is orange or yellow-orange (orange is the Heads up signal). This is the one place the colours are written; a place is found by its name or its slug ("Lake Tahoe", "laketahoe").
"""
import re

INK, WHITE = "#1D1D1F", "#FFFFFF"
NEUTRAL = ("#6E6E73", WHITE)
_COLOURS = {
    "sandiego": ("#0071E3", WHITE), "carlsbad": ("#00A6A6", INK), "anaheim": ("#D41F62", WHITE), "orangecounty": ("#D41F62", WHITE), "losangeles": ("#7D4CF0", WHITE),
    "temecula": ("#FFC300", INK), "palmsprings": ("#FFC300", INK), "laketahoe": ("#17834A", WHITE), "tahoecity": ("#17834A", WHITE), "newyork": ("#C8102E", WHITE),
    "orlando": ("#D41F62", WHITE), "santabarbara": ("#00779A", WHITE), "honolulu": ("#5AC8FA", INK), "yosemite": ("#2E7D32", WHITE), "sanfrancisco": ("#C8102E", WHITE),
    "napa": ("#7A3E9D", WHITE), "monterey": ("#00A6A6", INK),
}


def _slug(place) -> str:
    return re.sub(r"[^a-z0-9]", "", str(getattr(place, "name", place) or "").lower())[:20]


def of(place) -> tuple:
    return _COLOURS.get(_slug(place), NEUTRAL)


def style(place) -> str:
    fill, on = of(place)
    return f"--pc:{fill};--pc-on:{on}"


def skyline(place) -> str:
    """The lane tile's picture: the place's colour for the sky, a lighter hill and a darker one, a white sun. Deterministic (the hills sit where the place's letters put them)."""
    n = sum(map(ord, _slug(place)))
    y, z = 24 + n % 7, 34 + n % 5
    return (f'<svg class="pc-sk" viewBox="0 0 48 48" preserveAspectRatio="xMidYMax slice" aria-hidden="true"><rect class="pc-sky" width="48" height="48"/><circle class="pc-sun" cx="34" cy="15" r="6"/>'
            f'<path class="pc-hill" d="M0 {y + 7} Q12 {y} 24 {y + 6} T48 {y + 4} V48 H0Z"/><path class="pc-far" d="M0 {z + 4} Q14 {z - 1} 26 {z + 4} T48 {z + 3} V48 H0Z"/></svg>')
