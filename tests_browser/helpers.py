"""Shared constants for the browser tests."""
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}


def seed_plan(request, base_url, id, day, start, end, title, kind="fun"):
    """A plan on the open trip, the way the app makes one (the add sheet's route runs an hour; the canvas then sets the end). `request` is a browser context's or page's `.request`."""
    request.post(f"{base_url}/trip/plans", form={"id": id, "day": str(day), "start": start, "title": title, "kind": kind}, max_redirects=0)
    h, m = map(int, end.split(":"))
    request.post(f"{base_url}/trip/canvas/plan", form={"op": "edit", "act": id, "end": str(h * 60 + m)}, max_redirects=0)


# F-200: Direction A's light values (assets/css/tokens.css), for the tests that read a colour off the page. The browser's default is light mode.
INK = "rgb(11, 11, 13)"            # text, and the accent: a black pill
ACCENT = INK
ON_INK = "rgb(255, 255, 255)"
INK_2 = "rgb(92, 92, 102)"
INK_3 = "rgb(98, 98, 107)"
CARD = "rgb(255, 255, 255)"
PAPER = "rgb(242, 242, 245)"        # the canvas
PAPER_2 = "rgb(237, 237, 241)"      # a quiet fill on a card
HAIRLINE = "rgb(227, 227, 232)"
HAIRLINE_2 = "rgb(215, 215, 222)"
# the kinds' tints (the old palette names: --sun is food's yellow, --mint outdoors' teal, --grape culture and stays' violet, --sky travel and flights' indigo, --bubble fun's rose)
SUN_TINT, MINT_TINT, GRAPE_TINT, SKY_TINT, BUBBLE_TINT = "rgb(255, 244, 194)", "rgb(217, 242, 239)", "rgb(241, 227, 250)", "rgb(228, 227, 251)", "rgb(251, 225, 234)"
SUN_INK, MINT_INK, GRAPE_INK, SKY_INK, BUBBLE_INK = "rgb(92, 67, 0)", "rgb(11, 77, 72)", "rgb(90, 23, 133)", "rgb(42, 33, 133)", "rgb(126, 21, 56)"
# the kinds' solid fills (a plan's coloured edge, a kind's dot): ride yellow, see teal, stay violet, flight indigo, food rose
SUN_FILL, MINT_FILL, GRAPE_FILL, SKY_FILL, BUBBLE_FILL = "rgb(255, 212, 59)", "rgb(15, 118, 110)", "rgb(139, 47, 201)", "rgb(67, 56, 202)", "rgb(201, 42, 94)"
