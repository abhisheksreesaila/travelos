"""What is true about the money, in one place (F-297, D-971): GitAway has no affiliate links of any kind. Whatever you book here (stays; flights once GITAWAY_LIVE_FLIGHTS is on) is booked and paid through Nuitée (LiteAPI), the merchant.

The legal page, the trust page, For creators, the claim page, the outreach message and a guide's own page all say it with these words; tests pin each place to them."""

PAID = "GitAway has no affiliate links. Whatever you book here is booked and paid through Nuitée (LiteAPI), the merchant."
LINKS_YOURS = "Your own links stay yours: GitAway never changes them and earns nothing from them."
NOTHING_TO_BOOK = "Nothing on this page can be booked, so nobody earns from it."


def earning_line(plannable=True) -> str:
    """Who earns when someone plans from a creator's trip, in plain words. A trip at a place GitAway cannot plan has no booking."""
    return NOTHING_TO_BOOK if not plannable else "Nobody earns from this page: GitAway has no affiliate links. Anything booked from it is paid through Nuitée (LiteAPI)."
