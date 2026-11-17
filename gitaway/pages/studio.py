"""The creator's studio parts shared by /for-creators and /creators/import (F-253, D-640..): the paste form's pieces and the magic import's stage, drawn as docs/design/creators-v2.

The stage is empty until assets/js/creatorimport.js fills it from the NDJSON the import answers (F-235): the post's card grows with its title and picture, its own sentences arrive highlighted and
tagged with the stop they name, the days and stops land under the story line, then "Your book is ready". Nothing it shows is invented: every word is the post's or the draft's.
"""

from fasthtml.common import A, Button, Div, Footer, H2, H3, I, Img, Li, Link, Ol, P, Script, Section, Span

from gitaway import showcase
from gitaway.pages import bookview

HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/placeart.css"), Script(src="/assets/js/creatorimport.js", defer=True))
EXAMPLE = ("https://theplanetd.com/48-hours-in-lisbon-itinerary/", "The Planet D · 48 Hours in Lisbon", "P")      # the real post the recorded test fixture is (tests/fixtures/creator_import)
STEPS = ("Reading your post", "Finding days and stops", "Laying out your guide")


def example_chips(link=True) -> Div:
    """"Try one" fills the box with a real post's link; `link` False (no AI key, so a link is not read) leaves only "write it yourself"."""
    url, label, fav = EXAMPLE
    return Div(Span("Try one:") if link else "", Button(Span(fav, cls="fav", style="background:var(--k-wx)"), label, type="button", cls="ex", id="fc-example-chip", data_fill=url) if link else "",
               Button("Or write it yourself", type="submit", name="do", value="manual", form="fc-paste", formnovalidate=True, cls="ex", id="fc-manual"), cls="examples")


def points(*more) -> Div:
    return Div(Span(Span(bookview.ico("quote"), cls="ic", style="--k:var(--bk-food)"), "Your words, never ours", cls="point v2-glass"),
               Span(Span(bookview.ico("plan"), cls="ic", style="--k:var(--bk-see)"), "Families plan and book from it", cls="point v2-glass"), *more, cls="points")


def art() -> Div:
    """The landing's picture: the example post's card, drawn (the Lisbon post the tests record)."""
    card = Div(Div(Span(), Span(), Span(), cls="bar"), Div(bookview.drawing(("bookart", "lisbon"), "A drawing of Lisbon, not a photograph"), cls="ph"), Span("48 Hours in Lisbon, Itinerary", cls="t"),
               Span("theplanetd.com", cls="s"), Span(cls="ln"), Span(cls="ln s"), cls="postcard")
    return Div(card, Span("An example post", cls="smp art-note"), cls="land-art", aria_hidden="true")


def stage() -> Section:
    """The import's view: the post's card on the left, its trip on the right. Hidden until the script starts it."""
    steps = Ol(*[Li(Span(bookview.ico("check"), cls="tick"), t) for t in STEPS], cls="steps", id="steps")
    head = Div(Div(Span(cls="dot"), Span("Opening your post", id="story", aria_live="polite"), cls="story", id="storyRow"), Div(I(id="progBar"), cls="prog"), steps, cls="imp-head")
    post = Div(Div(Span("", cls="fav", id="postFav"), Span("", id="postSite", cls="site"), Span(bookview.ico("check"), "robots.txt allows reading it", cls="ok", id="postOk"), cls="post-site"),
               Div(Div(Img(alt="", id="postImg", referrerpolicy="no-referrer"), Span("Picture from the post", cls="cap"), cls="post-pic"),
                   Div(H2(Span(cls="sk"), id="postT", cls="post-t disp"), P(Span(cls="sk", style="width:40%"), id="postBy", cls="post-by"), cls="post-text"), cls="post-main"),
               Div("In the post's own words", cls="river-h"), Div(id="river", cls="river"), cls="post", id="postCard")
    itin = Section(Div(H3("Your trip, as the post tells it"), Span("0 stops", id="itinCount"), cls="itin-h"), Div(id="days"),
                   Div(Div(Span("Your guide is ready", cls="b"), Span("", id="readyLine"), A("Edit the details first", href="#", cls="ready-edit", id="readyEdit"), cls="t"),
                       A("Open your guide", bookview.ico("arrow"), href="#", cls="go", id="openBook"), cls="ready", id="ready", hidden=True),
                   cls="itin v2-glass", id="itin", aria_live="polite")
    return Section(Div(head, Div(post, itin, cls="imp-grid"), P("", id="impNote", cls="imp-note", hidden=True), P("", role="status", cls="v2-sr", id="cm-live"), cls="imp"), id="imp", hidden=True, aria_label="Reading your post")


def foot() -> Footer:
    """The creator pages' foot: the legal pages, and what the sample books are."""
    return Footer(A("Privacy", href="/privacy"), A("Terms", href="/terms"), Span("Sample guides are made up so you can see how they read; real ones carry a creator's name and a link to their post.") if showcase.on() else "", cls="cb-foot")
