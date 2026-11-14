"""F-234: the trip card picture (gitaway/sharecard.py): 1080 x 1350, the place's art on top, the words below, nothing a Card does not hold."""

import io
from dataclasses import fields, replace

from PIL import Image

from gitaway import sharecard
from gitaway.sharecard import Card, render

TAHOE = Card("Tahoe at Christmas", "South Lake Tahoe", ("SFO", "South Lake Tahoe"), "December 2026", 8, "", "gitaway.me/s/abc", "laketahoe")


def png(card) -> Image.Image:
    return Image.open(io.BytesIO(render(card)))


def test_the_card_is_instagrams_four_by_five_png():
    img = png(TAHOE)
    assert (img.format, img.size, img.mode) == ("PNG", (1080, 1350), "RGB")


def test_the_top_is_the_places_art_not_a_flat_fill():
    img = png(TAHOE)
    assert img.getpixel((540, 2)) == (214, 233, 247)         # Lake Tahoe's day sky, #D6E9F7, at the very top
    assert img.getpixel((540, 450)) != img.getpixel((540, 2))     # the lake and mountains lower down


def test_a_place_with_no_art_gets_a_soft_dawn_not_a_blank():
    img = png(Card("Day out", "Nowhere in particular", (), "June 2027", 2))
    assert img.getpixel((5, 5)) == (127, 184, 255)       # the fallback sky #7FB8FF
    assert img.getpixel((5, 5)) != png(TAHOE).getpixel((5, 5))


def test_the_words_are_drawn_below_the_art():
    plain = png(Card("", "", (), "", 0, "", "", "laketahoe"))
    titled = png(TAHOE)
    below = (0, 760, 1080, 1350)
    assert plain.crop(below).tobytes() != titled.crop(below).tobytes()
    assert plain.crop((0, 0, 1080, 520)).tobytes() == titled.crop((0, 0, 1080, 520)).tobytes()      # the art above is the same


def test_names_show_only_when_given():
    withnames = replace(TAHOE, names="Ari and Maya")
    assert render(withnames) != render(TAHOE)
    box = (84, 1110, 700, 1180)       # where the names line sits: empty paper without them
    assert len(png(TAHOE).crop(box).getcolors(10**6)) == 1
    assert len(png(withnames).crop(box).getcolors(10**6)) > 1


def test_a_long_title_is_cut_at_a_word_with_dots_not_off_the_edge():
    f = sharecard.font(80, 700)
    lines = sharecard._wrap("The very long summer we drove everywhere and ate everything on the coast", f, 700, 2)
    assert len(lines) == 2 and lines[-1].endswith("...")
    assert all(f.getlength(x) <= 700 for x in lines)
    assert sharecard._wrap("Tahoe at Christmas", f, 2000, 2) == ["Tahoe at Christmas"]


def test_a_card_can_hold_no_booking_price_or_email():
    assert {f.name for f in fields(Card)} == {"title", "place", "route", "when", "days", "names", "link", "art_slug"}


def test_the_font_and_the_art_renderer_ship_in_the_docker_image():
    """gitaway/ is copied whole by the Dockerfile; the font must not be dropped by .dockerignore, and cairo must load from the conda environment."""
    from tests.test_dockerfile import _ignored
    assert sharecard.FONT.exists() and not _ignored("gitaway/fonts/geist-variable.ttf")
    assert sharecard._art("laketahoe", (120, 60)).size == (120, 60)


def test_a_title_with_no_spaces_is_broken_inside_the_word_and_stays_on_the_card():
    f = sharecard.font(80, 700)
    lines = sharecard._wrap("A" * 80, f, 700, 2)
    assert len(lines) == 2 and all(f.getlength(x) <= 700 for x in lines)
    assert lines[-1].endswith("...") and set(lines[0]) == {"A"}
    img = png(Card("W" * 80, "P" * 80, ("Q" * 60, "R" * 60), "S" * 80, 3, "N" * 80, "L" * 80, "laketahoe"))
    assert len(img.crop((1020, 700, 1080, 1250)).getcolors(10**6)) == 1      # nothing is drawn into the paper's right margin: the words stop inside the card
