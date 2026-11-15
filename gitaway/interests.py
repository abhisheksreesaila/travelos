"""What the family is after (F-241, D-560..): the interests picked on /plan/ask, kept for the whole family in `family_prefs` (key `interests`, the picked keys in LIST's order,
comma-separated). Planning reads them later (F-243: vegetarian food, seafood places). The list is fixed; anything else a form sends is dropped, never stored.

    LIST            [(key, label, icon, kind)] the chips, in the order they are drawn
    clean(values)   the picked keys that are in LIST, once each, in LIST's order
    get(session)    the family's stored keys (() with no family or none picked)
    save(session, values) -> tuple    store `clean(values)` and return it
"""

from gitaway import familydb, session as ses

KEY = "interests"
LIST = (
    ("vegetarian", "Vegetarian", "leaf", "k-car"),
    ("seafood", "Seafood", "food", "k-food"),
    ("cafes", "Cafes", "coffee", "k-tix"),
    ("beaches", "Beaches", "waves", "k-wx"),
    ("museums", "Museums", "sight", "k-stay"),
    ("hikes", "Hikes", "tree", "k-see"),
    ("cycling", "Cycling", "bike", "k-flight"),
    ("nightlife", "Nightlife", "moon", "k-stay"),
    ("kids", "With kids", "users", "k-tix"),
)
KEYS = tuple(k for k, *_ in LIST)


def clean(values) -> tuple:
    want = {str(v).strip().lower() for v in (values or ())}
    return tuple(k for k in KEYS if k in want)


def get(session) -> tuple:
    with familydb.using(session) as db:
        if db is None:
            return ()
        r = familydb.row(db, "SELECT value FROM family_prefs WHERE key = :k", k=KEY)
        return clean((r["value"] if r else "").split(","))


def save(session, values) -> tuple:
    picked = clean(values)
    with ses.family(session) as fam:
        if fam is not None:
            with familydb.transaction(fam.db):
                familydb.run(fam.db, "INSERT OR REPLACE INTO family_prefs (key, value) VALUES (:k, :v)", k=KEY, v=",".join(picked))
    return picked
