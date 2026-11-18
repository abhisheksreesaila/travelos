"""F-296 (D-959): each place's own vivid colour, and the words on it, pass 4.5:1; a place with no colour of its own is a neutral grey; the lane tile's skyline carries no colour of its own."""
import re

import pytest

from gitaway import placeart, placecolor
from gitaway.partners import places


def lum(h):
    v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("slug", sorted(placecolor._COLOURS))
def test_the_words_on_a_places_colour_read_4_5_to_1(slug):
    fill, on = placecolor.of(slug)
    assert ratio(fill, on) >= 4.5, (slug, fill, on)


def test_the_prototypes_set_and_the_neutral_default():
    assert placecolor.of("San Diego") == ("#0071E3", "#FFFFFF")
    assert placecolor.of("laketahoe") == ("#17834A", "#FFFFFF")
    assert placecolor.of("Temecula") == ("#FFC300", "#1D1D1F")
    assert placecolor.of("Nowhere") == placecolor.NEUTRAL == ("#6E6E73", "#FFFFFF")
    assert placecolor.style(places.resolve("Los Angeles")) == "--pc:#7D4CF0;--pc-on:#FFFFFF"


def test_every_place_with_art_has_a_colour_and_none_is_orange():
    for slug in placeart.SLUGS:
        fill, _ = placecolor.of(slug)
        assert fill != placecolor.NEUTRAL[0], slug
        r, g, b = (int(fill[i:i + 2], 16) for i in (1, 3, 5))
        assert not (r > 200 and 60 < g < 150 and b < 60), (slug, fill)      # orange is the Heads up signal


def test_the_skyline_is_the_same_each_time_and_has_no_colour_of_its_own():
    svg = placecolor.skyline("San Diego")
    assert svg == placecolor.skyline("san-diego")
    assert not re.search(r"#[0-9A-Fa-f]{3,8}|rgb\(|fill=|style=", svg)
