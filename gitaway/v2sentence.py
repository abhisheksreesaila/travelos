"""The v2 sentence (F-250, D-611..): the search as one sentence whose every part is a word you tap, never a box you type in. Used by the landing (/plan/ask) and the results
(/plan/matrix), the same words in the same order:

    A family of 4 from SFO to San Diego, or nearby, around Sat, Dec 12, give or take 2 days, for 4 nights, under $2,300, into beaches & vegetarian.

    spec_of(s, picked)       the sentence's state as one JSON-ready dict: the values, the options each picker offers and the limits (assets/js/v2.js reads it)
    words(spec)              each word's text, and `sentence(spec)` the sentence drawn on the server, so the page reads right before (and without) the script
    address(form)            what the words say as the matrix's real search parameters, or the problem in words: the one place words become `to home d r a k x nb b`
    word_text(...)           assets/js/v2.js `text` says the same words: change one, change the other (tests_browser/test_v2_sentence.py compares them)

The words map onto gitaway/pages/tripmatrix.py's `State` (place, home, depart, return, adults, kid_ages, flex, nearby, budget); the interests are kept for the family by
gitaway/interests.py (not a search parameter: nothing prices by them yet). No free typing anywhere: every option is a button, a stepper, a calendar day or a slider.
"""

import json
from datetime import date, timedelta

from fasthtml.common import Div, Form, Input, NotStr, Script, Span, to_xml

from gitaway import catalog, gridsource, interests, showcase, tripmatrix as tm
from gitaway.partners import places

WORD_KEYS = ("who", "from", "where", "start", "flex", "nights", "budget", "into")
LABEL = {"who": "Who is going", "from": "Flying from", "where": "Where to", "start": "Around which day", "flex": "How flexible", "nights": "How many nights",
         "budget": "All in, under", "into": "You are into"}
AIRPORTS = (("SFO", "San Francisco"), ("OAK", "Oakland"), ("SJC", "San José"), ("LAX", "Los Angeles"), ("SAN", "San Diego"), ("SEA", "Seattle"), ("PDX", "Portland"), ("DEN", "Denver"),
            ("PHX", "Phoenix"), ("LAS", "Las Vegas"), ("ORD", "Chicago"), ("DFW", "Dallas"), ("JFK", "New York"), ("BOS", "Boston"), ("ATL", "Atlanta"), ("MIA", "Miami"))
ADULTS = (1, 6)
KIDS = (0, 5)
NIGHTS = (2, 7)
BUDGET = (1_000, 8_000, 100)       # the slider's ends and step, in dollars; "any budget" is its own switch
ASK_DAYS = 330                    # the calendar reaches this far ahead
DEFAULT_KID_AGE = 8
PATH = "/plan/ask"


def known_places() -> list:
    """Where to: the known places a search can price. On the showcase only those the sample catalog can; elsewhere every known place with an airport (LiteAPI prices them)."""
    return [p for p in places.known() if p.iata and (not showcase.on() or gridsource.has_sample(p))]


def where_options(current) -> list:
    names = [p.name for p in known_places()]
    return [{"n": n, "near": bool(places.nearby(places.resolve(n)))} for n in dict.fromkeys([*names, current.name])]


def spec_of(s, picked=()) -> dict:
    """The sentence's state for a search `s` (pages/tripmatrix.py State) and the family's picked interests."""
    today = catalog.today()
    return {
        "adults": s.adults, "kids": list(s.kid_ages), "home": s.home, "to": s.place.name, "nearby": bool(s.nearby and places.nearby(s.place)),
        "depart": s.depart.isoformat(), "nights": s.nights, "flex": s.flex, "budget": s.budget_cents // 100 if s.budget_cents else 0, "into": list(interests.clean(picked)),
        "places": where_options(s.place), "airports": [list(a) for a in dict.fromkeys([*AIRPORTS, *(((s.home, s.home),) if s.home else ())])],
        "interests": [[k, label, ico, kind] for k, label, ico, kind in interests.LIST],
        "today": today.isoformat(), "last": (today + timedelta(days=ASK_DAYS)).isoformat(),
        "limits": {"adults": list(ADULTS), "kids": list(KIDS), "nights": [min(NIGHTS[0], s.nights), max(NIGHTS[1], s.nights)], "flex": [0, tm.MAX_FLEX],
                   "budget": list(BUDGET), "travelers": catalog.MAX_TRAVELERS, "kidAge": catalog.MAX_KID_AGE, "defaultAge": DEFAULT_KID_AGE},
        "labels": LABEL, "action": PATH,
    }


# ---- the words ------------------------------------------------------------------------------------------------------

def money(dollars: int) -> str:
    return f"${dollars:,}"


def day_words(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%a}, {d:%b} {d.day}"


def who_words(adults: int, kids) -> str:
    n = adults + len(kids)
    if kids:
        return f"A family of {n}"
    return "Just me" if adults == 1 else ("The two of us" if adults == 2 else f"{adults} adults")


def into_words(keys) -> str:
    label = {k: lb for k, lb, *_ in interests.LIST}
    names = [label[k].lower() for k in keys if k in label]
    return "anything" if not names else (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1])


def words(spec: dict) -> dict:
    """{word key: its text}. assets/js/v2.js `text` says the same."""
    n, f = spec["nights"], spec["flex"]
    return {"who": who_words(spec["adults"], spec["kids"]), "from": spec["home"] or "anywhere", "where": spec["to"] + (", or nearby" if spec["nearby"] else ""),
            "start": day_words(spec["depart"]), "flex": "on the dot" if f == 0 else f"give or take {f} day{'' if f == 1 else 's'}",
            "nights": f"{n} night{'' if n == 1 else 's'}", "budget": money(spec["budget"]) if spec["budget"] else "any budget", "into": into_words(spec["into"])}


def fills(spec: dict) -> dict:
    """The plain words between the tapped ones (the budget's changes with it: "under $2,300", "with any budget")."""
    return {"from": "from", "where": "to", "start": ", around", "flex": ",", "nights": ", for", "budget": ", under" if spec["budget"] else ", with", "into": ", into", "end": "."}


def sentence(spec: dict, cls="v2-sent", id="v2-sent") -> Span:
    """The sentence drawn on the server: each word a button that opens its picker (assets/js/v2.js)."""
    w, f = words(spec), fills(spec)

    def word(k):
        return Span(w[k], role="button", tabindex="0", cls="v2-w", data_k=k, aria_haspopup="dialog", aria_expanded="false", aria_label=f"{LABEL[k]}: {w[k]}")

    gap = lambda k: Span(f[k], cls="fill")      # noqa: E731
    parts = [word("who"), " ", gap("from"), " ", word("from"), " ", gap("where"), " ", word("where"), gap("start"), " ", word("start"), gap("flex"), " ", word("flex"), gap("nights"), " ",
             word("nights"), gap("budget"), " ", word("budget"), gap("into"), " ", word("into"), gap("end")]
    return NotStr(f'<h1 class="{cls}" id="{id}" aria-live="polite">' + "".join(to_xml(p) if not isinstance(p, str) else p for p in parts) + "</h1>")


def data_json(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False).replace("<", "\\u003c")


# ---- the words as a search ------------------------------------------------------------------------------------------

def address(form) -> tuple:
    """(the matrix's address, "") for what the words said, or ("", the problem in words). `form` gives `to home d n a k x nb b` (n: nights); nothing is typed, but a form
    can say anything, so each part is read as the matrix's own `state` reads an address, and a problem there is said here."""
    get = lambda n: str(form.get(n) or "").strip()      # noqa: E731
    try:
        depart = date.fromisoformat(get("d"))
        nights = int(get("n") or NIGHTS[0])
    except ValueError:
        return "", "Pick a start day and how many nights."
    if nights < 1:
        return "", "Pick how many nights."
    from gitaway.pages import tripmatrix as page      # here, not at the top: the page imports this module
    s = page.state(get("to"), get("home"), depart.isoformat(), (depart + timedelta(days=nights)).isoformat(), get("a"), get("k"), get("x"), get("nb"), get("b"))
    if s.problems:
        return "", " ".join(s.problems)
    return page.href(s), ""


# ---- suggestions: the sentence with one word changed (F-275, D-861) ------------------------------------------------------------------------------------------

NEAR_AIRPORTS = {"SFO": "OAK", "OAK": "SFO", "SJC": "SFO", "LAX": "SNA", "SNA": "LAX"}      # the other airport a family may fly from
SUGGEST_MAX = 5


def _form_of(spec: dict) -> dict:
    return {"to": spec["to"], "home": spec["home"], "d": spec["depart"], "n": spec["nights"], "a": spec["adults"], "k": ",".join(map(str, spec["kids"])), "x": spec["flex"],
            "nb": "" if spec["nearby"] else "0", "b": spec["budget"] or ""}


def suggestions(spec: dict) -> list:
    """[(label, the matrix's address)] for a few one-word changes to the sentence, the nudges under it for people who do not know the words are buttons: a week later, a place
    they may not have thought of, a budget, a shorter stay, another airport. Each is read through `address`, so one that cannot be searched is not offered."""
    base = _form_of(spec)
    here = address(base)[0]
    depart = date.fromisoformat(spec["depart"])
    later = depart + timedelta(days=7)
    nights, lo = spec["nights"], spec["limits"]["nights"][0]
    near = {p.name for p in places.nearby(places.resolve(spec["to"]))}
    other = [n["n"] for n in spec["places"] if n["n"] != spec["to"] and n["n"] not in near][:1]
    cap = max(1_000, -(-(spec["adults"] + len(spec["kids"])) * 600 // 500) * 500)      # about $600 a person, to the next $500
    shorter = nights - 1 if nights - 1 >= lo else nights + 1
    tries = [("A week later", {"d": later.isoformat()} if later <= date.fromisoformat(spec["last"]) else None)]
    tries += [(name, {"to": name}) for name in other]
    tries += [(f"Under {money(cap)}", {"b": cap}) if not spec["budget"] else ("Any budget", {"b": ""}), (f"{shorter} nights", {"n": shorter})]
    if spec["home"] in NEAR_AIRPORTS:
        tries.append((f"From {NEAR_AIRPORTS[spec['home']]}", {"home": NEAR_AIRPORTS[spec["home"]]}))
    out = []
    for label, change in tries:
        got, problem = address({**base, **change}) if change is not None else ("", "")
        if got and not problem and got != here:
            out.append((label, got))
    return out[:SUGGEST_MAX]


def form_el(spec: dict, *inside) -> Form:
    """The form the words fill (assets/js/v2.js keeps its hidden fields as the sentence changes): it posts to /plan/ask, which reads the words as a search (`address`) and keeps the
    interests. `inside` is what the page puts in it: the sentence, and on the landing the Search button. Works without script as a plain form."""
    hidden = [Input(type="hidden", name=n, value=str(v)) for n, v in (("to", spec["to"]), ("home", spec["home"]), ("d", spec["depart"]), ("n", spec["nights"]), ("a", spec["adults"]),
                                                                  ("k", ",".join(map(str, spec["kids"]))), ("x", spec["flex"]), ("nb", "" if spec["nearby"] else "0"), ("b", spec["budget"] or ""))]
    hidden += [Input(type="hidden", name="i", value=k) for k in spec["into"]]
    return Form(*hidden, *inside, id="v2-form", action=spec["action"], method="post", cls="v2-form")


def machinery(spec: dict) -> tuple:
    """What the script needs beside the sentence: the spec as JSON, the picker (a popover or a sheet) and its scrim."""
    return (Script(NotStr(data_json(spec)), type="application/json", id="v2-data"), Div(id="v2-pop", cls="v2-pop", role="dialog", hidden=True), Div(id="v2-scrim", cls="v2-scrim"))
