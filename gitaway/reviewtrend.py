"""What the last hundred reviews of a hotel say as a trend, not a number (F-278, D-871): plain functions on LiteAPI's reviews (gitaway/liteapi.py `reviews`, asked once with limit=100 and kept
a day), computed on the server so the page only draws them. No framework, no network.

    kind(score)                       "good" (8 or more), "mixed" (6 up to 8) or "poor" (under 6: 5 or less)
    trend(items, overall, ptype)      Trend: the dots oldest to newest, the counts, and the plain words (recent against overall, a streak, travellers like you), each "" when there is nothing to say
    party_type(adults, kid_ages)      LiteAPI's traveller type for a party: family with children when kids are in it, solo, couple, else group
    order(items, ptype)               the cards: only reviews with words, the party's own traveller type first, then newest, the first good and the first critical put near the top
    source_name(items)                where LiteAPI says the reviews are from, as it labels them ("Nuitée"), never a source it did not name

Nothing is guessed: a trend word needs enough reviews (10 for the recent average, 6 for a streak, 5 of the party's type) and, for the recent one, a difference that matters (RECENT_GAP).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date

GOOD, MIXED, POOR = 8, 6, 0      # a score from GOOD up is good, from MIXED up mixed, below that poor
RECENT_N = 10                    # the "last 10" the recent average is over
RECENT_GAP = 0.5                 # the recent average must differ from the hotel's rating by this much to be said
STREAK_N = 6                     # "the last 6 were all 8 or more" / "3 of the last 6 were poor"
POOR_OF_LAST = 3
TYPE_MIN = 5                     # reviews of the party's own type needed to say their average
TYPE_WORDS = {"family_with_children": "Families with children", "couple": "Couples", "solo_traveller": "Solo travellers", "extended_group": "Groups", "friends": "Friends", "business": "Business travellers"}
SOURCES = {"nuitee": "Nuitée"}   # LiteAPI's own label for its reviews, written the way the company writes its name


@dataclass(frozen=True)
class Dot:
    score: float
    kind: str
    date: str


@dataclass(frozen=True)
class Trend:
    dots: tuple              # every scored review of the answer, oldest to newest
    good: int
    mixed: int
    poor: int
    span: str                # "Nov 3 to Nov 16", or ""
    recent: str              # "The last 10 averaged 9.1, above the hotel’s 8.7.", or ""
    streak: str              # "The last 6 were all 8 or more." / "3 of the last 6 were poor (5 or less).", or ""
    like_you: str            # "Families with children: 8.4 on average, from 8 of the last 100 reviews.", or ""


def kind(score) -> str:
    return "good" if score >= GOOD else "mixed" if score >= MIXED else "poor"


def party_type(adults: int, kid_ages) -> str:
    """LiteAPI's traveller type for a party: family with children when kids are in it, solo for one adult, couple for two, else a group."""
    return "family_with_children" if kid_ages else "solo_traveller" if adults <= 1 else "couple" if adults == 2 else "extended_group"


def _oldest_first(items) -> list:
    """The scored reviews, oldest to newest. LiteAPI answers newest first; a stable sort on the date keeps a day's own order reversed the same way."""
    return sorted((r for r in reversed(list(items)) if r.score is not None), key=lambda r: r.date or "")


def _md(d: str) -> str:
    try:
        x = date.fromisoformat(d)
        return f"{x:%b} {x.day}"
    except ValueError:
        return ""


def _span(rs) -> str:
    a, b = (_md(rs[0].date), _md(rs[-1].date)) if rs else ("", "")
    return "" if not a or not b else a if a == b else f"{a} to {b}"


def _g(v: float) -> str:
    return f"{v:.1f}"


def recent_words(rs, overall) -> str:
    """The last RECENT_N average against the hotel's rating, only when the two differ by RECENT_GAP or more."""
    if overall is None or len(rs) < RECENT_N:
        return ""
    last = [r.score for r in rs[-RECENT_N:]]
    avg = sum(last) / len(last)
    gap = round(avg - overall, 2)
    if abs(gap) < RECENT_GAP:
        return ""
    return f"The last {RECENT_N} averaged {_g(avg)}, {'above' if gap > 0 else 'below'} the hotel’s {overall:g}."


def streak_words(rs) -> str:
    """"The last 6 were all 8 or more" when the newest run of good scores is that long, else "3 of the last 6 were poor" when that many of the newest six were."""
    if len(rs) < STREAK_N:
        return ""
    run = 0
    for r in reversed(rs):
        if kind(r.score) != "good":
            break
        run += 1
    if run >= STREAK_N:
        return f"The last {run} were all {GOOD} or more."
    poor = sum(kind(r.score) == "poor" for r in rs[-STREAK_N:])
    return f"{poor} of the last {STREAK_N} were poor ({MIXED - 1} or less)." if poor >= POOR_OF_LAST else ""


def like_you_words(rs, ptype) -> str:
    own = [r.score for r in rs if r.type == ptype]
    if len(own) < TYPE_MIN or ptype not in TYPE_WORDS:
        return ""
    return f"{TYPE_WORDS[ptype]}: {_g(sum(own) / len(own))} on average, from {len(own)} of the last {len(rs)} reviews."


def trend(items, overall=None, ptype="") -> Trend | None:
    """The strip and its words for LiteAPI's newest reviews; None when no review has a score."""
    rs = _oldest_first(items)
    if not rs:
        return None
    kinds = Counter(kind(r.score) for r in rs)
    return Trend(tuple(Dot(r.score, kind(r.score), r.date) for r in rs), kinds["good"], kinds["mixed"], kinds["poor"], _span(rs), recent_words(rs, overall), streak_words(rs), like_you_words(rs, ptype))


def source_name(items) -> str:
    """The source LiteAPI names on its reviews, the commonest one, in its own spelling ("nuitee" is Nuitée); "" when it names none. Never a source it did not name."""
    named = Counter(r.source.strip().lower() for r in items if getattr(r, "source", "").strip())
    if not named:
        return ""
    raw = named.most_common(1)[0][0]
    return SOURCES.get(raw, raw.capitalize())
