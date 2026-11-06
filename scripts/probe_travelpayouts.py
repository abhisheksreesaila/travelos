"""One real partner-links call (F-179): `pixi run probe-tp`.

Needs TRAVELPAYOUTS_TOKEN and TRAVELPAYOUTS_MARKER (and TRAVELPAYOUTS_TRS, the project id) in the environment. Turns one Klook page into a tracked
link with a probe SubID and prints it, plus the Aviasales link for a sample trip and the Klook links of F-195 (Disneyland tickets, Anaheim stays, attractions). Never prints the token. Without a token it says so and exits 1.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitaway import catalog                      # noqa: E402
from gitaway.partners import for_lane, travelpayouts as tp   # noqa: E402

SUB = "probe-hi-270305-stay"


def main() -> int:
    if not (tp.token() and tp.marker()):
        print("TRAVELPAYOUTS_TOKEN and TRAVELPAYOUTS_MARKER must be set (the token is never printed).")
        return 1
    trip = catalog.sample_trip("hi")
    flight, stay = catalog.offers("flight", trip)[0], catalog.offers("stay", trip)[0]
    print("Aviasales:", tp.link_for(for_lane("flight"), flight, trip, SUB))
    url = for_lane("stay").target_url(stay, trip)
    try:
        link = tp.create_link(url, SUB)
    except Exception as e:
        print(f"Klook: the partner-links API did not give a link ({type(e).__name__}: {e}); /go would use {tp.klook_fallback()}")
        return 2
    print("Klook page:", url)
    print("Klook tracked link:", link)
    # F-195: the Klook pages the Tickets and Anaheim stay links use (D-160 could not open them: Klook answers 403 to the machine that built them)
    la = catalog.parse_trip("", "la", "2027-03-05", "2027-03-09", "2", "4,7", focus="disney")
    status = 0
    for what, kind, where in (("Disneyland tickets", "todo", la), ("Anaheim stays", "stay", la), ("Honolulu attractions", "todo", trip)):
        page = for_lane(kind).target_url(catalog.search_offer(kind, where), where)
        try:
            print(f"{what}: {page}\n   -> {tp.create_link(page, SUB)}")
        except Exception as e:
            print(f"{what}: the partner-links API did not give a link for {page} ({type(e).__name__}: {e})")
            status = 2
    return status


if __name__ == "__main__":
    sys.exit(main())
