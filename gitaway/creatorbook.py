"""What a creator's guide knows about the post (F-253, F-262): the kind a stop's name says it is, the drawn scene that names a place, and the post's own sentences laid against the stops they name
(`said`). Pure functions, no framework; the guide is gitaway/guide.py. Nothing here invents a word: a sentence is the post's own (creatordraft keeps them, `importsource.own_words`), and everything
else is a drawing, labelled as one.
"""

import json
import re
from pathlib import Path

from gitaway import placeart

KINDS = {"see": "Sight", "food": "Food", "tix": "Tickets", "ride": "Ride", "show": "Show", "walk": "Walk"}
_WORDS = (("show", r"\bshows?\b|concert|fado|theat|opera|musical|festival|lucha|performance|nightlife"),
          ("food", r"restaurant|caf[eé]|bakery|market|lunch|dinner|breakfast|brunch|past[eé]is|pastel|tacos?|pizza|bistro|\bbar\b|coffee|snack|ice cream|churros|supper|picnic|food|factory"),
          ("ride", r"tuk|tram|ferry|train|\bbus\b|taxi|\buber\b|\bride\b|cruise|gondola|boat|drive|metro|trajinera"),
          ("tix", r"ticket|castel|castle|ch[aâ]teau|palace|palacio|palazzo|admission|aquarium|\bzoo\b|quinta|theme park|\btour\b|cathedral"),
          ("walk", r"walk|hike|stroll|trail|lanes?\b|district|neighbou?rhood|alfama|street|loop|beach|promenade|boardwalk|\bsquare\b"))
ART = json.loads((Path(__file__).with_name("bookart.json")).read_text(encoding="utf-8"))
# a drawing for a day's plate or a cover, by the place or stop it is about: (words that name it) -> a scene of bookart.json
_SCENES = (("belem", r"bel[eé]m"), ("sintra", r"sintra|pena palace"), ("alfama", r"alfama"), ("lisbon", r"lisbon|lisboa"), ("kyoto", r"kyoto"), ("bigsur", r"big sur"), ("amalfi", r"amalfi|positano"),
           ("cdmx", r"mexico city|ciudad de m"), ("iceland", r"iceland"))


def kind_of(name: str) -> str:
    """The colour a stop gets: what the name says it is, "see" when it does not say."""
    low = (name or "").casefold()
    return next((k for k, pat in _WORDS if re.search(pat, low)), "see")


def scene_of(*texts):
    """("bookart", key) for a drawn scene that names this place, ("placeart", place) for GitAway's own place art, else ("generic", "")."""
    said = " ".join(t for t in texts if t).casefold()
    for key, pat in _SCENES:
        if re.search(pat, said):
            return "bookart", key
    for t in texts:
        if t and placeart.art(t) is not None:
            return "placeart", t
    return "generic", ""


# ---- the post's own sentences, laid against the stops they name -------------------------------------------------------------------------

def _fold(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").casefold()) if not unicodedata.combining(c))


def _names(sentence: str, name: str) -> bool:
    n = _fold(name).strip()
    return len(n) >= 4 and n != _fold("Unnamed stop") and n in _fold(sentence)


def said(words: list, names: list, used: set | None = None) -> list:
    """For each stop name, the post's own sentence that names it (the first one not already used), else "". `words` are sentences exactly as the post wrote them."""
    used = set() if used is None else used
    out = []
    for name in names:
        hit = next((s for s in words if s not in used and _names(s, name)), "")
        if hit:
            used.add(hit)
        out.append(hit)
    return out


def day_quote(words: list, names: list, used: set) -> str:
    """The sentence a day page quotes: the post's first sentence naming one of the day's stops (never one already quoted), "" when the post names none."""
    for name in names:
        for sentence in words:
            if sentence not in used and _names(sentence, name):
                used.add(sentence)
                return sentence
    return ""
