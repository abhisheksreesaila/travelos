"""The trip canvas (F-081): the whole trip as one surface that zooms. Week, then a day, then a block (a park day with its parts and steps), then one step.

GET  /trip/canvas                 the week: every day as a row, park days showing their parts, free days with a +
GET  /trip/canvas?day=N           one day: its blocks in time order, a park block with its parts and steps as chips, the day's Set aside tray
GET  /trip/canvas?block=a3        one block: parts as sections, steps in time order, lanes when people split up
GET  /trip/canvas?step=<id>       one step, as a bottom sheet over its block: note, who is going, Mark done, Set aside / Put back
POST /trip/canvas/step            Mark done, Not done, Set aside, Put back (the writes are F-080's gitaway.canvas; editors only, gated by gitaway.access)

Every level is drawn by the server and has its own address, so it works without script, the back button works, and a link opens a level directly. With
script (assets/js/trip_canvas.js) a tap or the Day | Week toggle fetches the next level as a fragment (`?frag=1`, no page around it) and swaps it inside a View
Transition: the element that was tapped (a day row, a block card, a step chip) is the one that grows into the next level's header or sheet, and shrinks back on
zoom out. Where View Transitions are missing it is a short scale and fade; with reduced motion it is an instant swap. A write from the sheet (`X-Canvas: 1`)
answers 204 and `X-Canvas-Url`, the level to zoom out to.

The Today tab is the day view on today (F-092: a bare /trip redirects here); the centre Ask changes the day being looked at. On a laptop the same markup is a
wide day view: the week as a strip across the top, the day's parts as lanes, the Set aside tray at the side.
"""

import json
from urllib.parse import urlencode

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, H3, Header, Input, Label, Link, Main, Nav, P, Section, Span, Summary, Template, to_xml
from starlette.responses import RedirectResponse, Response

from gitaway import access, canvas, catalog, geo, members, passes, phone, pickers, plantalk, planedit, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import avatar, join_note, trip_field
from gitaway.pages import booked, calendar as calui, passes as passes_ui   # passes: on a flight day the now card is the flight with everyone's passes (F-092)
from gitaway.pages.around_ui import around_url
from gitaway.pages.plantalk import talk_badge   # F-091: the chat badge on a plan and on a part

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/help.css"), *passes_ui.HEAD, Link(rel="stylesheet", href="/assets/css/trip_canvas.css"), Link(rel="stylesheet", href="/assets/css/day_grid.css"), Link(rel="stylesheet", href="/assets/css/plantalk.css"), Link(rel="stylesheet", href="/assets/css/day_card.css"))   # pickers: the add-a-step sheet has a time field (F-082)
SCRIPTS = ("/assets/js/vendor/idiomorph.js", "/assets/js/trip_canvas.js", "/assets/js/day_grid.js", "/assets/js/day_menu.js", "/assets/js/day_new.js", "/assets/js/day_fold.js", "/assets/js/day_card.js")
RANK = {"week": 0, "day": 1, "block": 2, "step": 3}
PART_TINTS = ("sky", "sun", "grape", "bubble", "mint")
MAX_FACES = 5


def curl(day=None, block="", step="", add=False, part="", title="", note="", err="", booked="", sos=False):
    """The address of a level: the week with nothing, else a day, a block or a step. `add` opens the add-a-step sheet over a block (with the part, title and note
    it starts with, and the reason the last try was refused). `booked` opens a booking's sheet over its day (F-093), `sos` the emergency sheet over the day or the week."""
    q = {"step": step} if step else {"block": block} if block else {"day": day} if day is not None else {}
    if booked:
        q = {"day": day if day is not None else 0, "booked": booked}
    elif sos:
        q = {**q, "sos": "1"}
    if add and block:
        q = {"block": block, "add": "1", **{k: v for k, v in (("part", part), ("title", title), ("note", note), ("err", err)) if v}}
    if (trip := ses.open_trip_id()):
        q["trip"] = trip      # a tab left open on one trip stays on it after the family opens another
    return "/trip/canvas" + (f"?{urlencode(q)}" if q else "")


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


# ---- reading --------------------------------------------------------------------------------------------------------------

def load(session):
    """Everything any level draws, read once (a trip holds a few hundred rows at most)."""
    who, b = ses.current_traveler(session), ses.booking(session)
    t = cal.trip("", b)
    dates = cal.days(t)
    acts = cal.activities(session)
    notes = cal.notes(session)
    pl = canvas.plan(session)
    blocks = [x for x in cal.booked_blocks(b, t) + cal.ride_blocks(session, b, t) if x.kind != "ride"]
    for f in passes.flights(session):                    # a flight an editor added by hand is a booking line on its day, with a sheet (F-093)
        at = (f["date"] - t.depart).days
        if f["source"] == "added" and 0 <= at < len(dates):
            blocks.append(cal.Block("fl-" + f["id"][:12], at, f["depart_min"], min(f["depart_min"] + 60, 24 * 60 - 1), f"{f['name']} · {f['origin']} → {f['dest']}", "booked", True, "plane"))
    zone = ses.trip_zone(session)
    clock = td.clock_zone(cal.plan_of(b) if cal.is_imported(b) else None, zone)
    ph, n = td.phase(t, catalog.today_in(clock))
    today_idx = n if ph == "during" else None
    people = {f.name.casefold(): f for f in ses.friends(session)}
    family = members.family_people(session)
    note_of = lambda x: (calui.note_writer(x, who, people, family)[0], x.text)  # noqa: E731
    act_notes = {}
    for x in notes:
        if x.act:
            act_notes.setdefault(x.act, []).append(note_of(x))
    v = dict(session=session, who=who, b=b, t=t, dates=dates, acts=acts, blocks=blocks, plan=pl["blocks"], lists=pl["lists"], act_notes=act_notes, today_idx=today_idx,
             role=access.request_role(), crew=members.crew(session), summaries=td.day_summaries(dates, blocks, acts, today_idx))
    v["by_id"] = {a.id: a for a in acts}
    v["zone"] = zone
    v["clock"] = clock
    v["people"] = canvas.family_people(session)
    v["talk"] = plantalk.counts(session)                 # F-091: messages per plan and part, for the chat badges
    for blk in v["plan"].values():                       # which of the trip's lists name each step, for the filters
        for s in [*_all_steps(blk), *blk["aside"]]:
            s["lists"] = canvas.list_hits(s["title"], v["lists"])
    return v


def entries(v, day):
    """What happens on a day, in time order: ("block", activity) for a plan with parts and steps, ("plan", activity), ("booked", block)."""
    out = [(a.start, "block" if a.id in v["plan"] else "plan", a) for a in v["acts"] if a.day == day]
    out += [(x.start, "booked", x) for x in v["blocks"] if x.day == day]
    return [(kind, x) for _, kind, x in sorted(out, key=lambda e: (e[0], e[1] != "booked"))]


def has_block(v, act_id):
    """A block exists when it has parts, its activity is live and its day is inside the trip."""
    a = v["by_id"].get(act_id)
    return bool(a) and act_id in v["plan"] and 0 <= a.day < len(v["dates"])


def find_step(v, step_id):
    for act_id, blk in v["plan"].items():
        if not has_block(v, act_id):
            continue
        for p in blk["parts"]:
            for s in p["steps"]:
                if s["id"] == step_id:
                    return s, act_id, p["name"], p["time_of_day"]
        for s in blk["aside"]:
            if s["id"] == step_id:
                return s, act_id, s["part_name"], ""
    return None


def today_url(session, day=""):
    """Where the Today tab goes (F-092): the day asked for, else today during the trip, the first day before it and the last day after it."""
    b = ses.booking(session)
    t = cal.trip("", b)
    last = len(cal.days(t)) - 1
    if day.isdigit() and int(day) <= last:
        return curl(day=int(day))
    zone = td.clock_zone(cal.plan_of(b) if cal.is_imported(b) else None, ses.trip_zone(session))
    ph, n = td.phase(t, catalog.today_in(zone))
    return curl(day=n if ph == "during" else 0 if ph == "before" else last)


def now_card(v, day):
    """On today (F-092): what is happening now or up next, with Directions and Uber, or on a flight day the flight with everyone's passes. Drawn by Today's own code."""
    if day != v["today_idx"]:
        return ""
    from gitaway.pages import trip as trippage
    with geo.cache_scope(v["session"]):        # Leave by and the Uber link read the family's map cache (gitaway.geo), as on Today
        tv = trippage.load(v["session"], str(day), v.get("ua", ""))
        flights, calm, _titles = passes_ui.flight_cards(tv)
        return Div(flights or trippage.up_card(tv, compact=True), calm, cls="cz-now", id="cz-now", data_kind="now")


def _count(n, one, many):
    return f"{n} {one if n == 1 else many}"


def person_face(p, cls="cz-av"):
    """A person as a small round badge: a member in their colour, a name nobody matched in plain, initials nobody matched dashed, a group as words."""
    if p["kind"] == "group":
        return Span(p["name"], cls="cz-group")
    colour = f" fill-{p['color']}" if p["kind"] == "member" and p["color"] else ""
    return Span(p["initials"], cls=f"{cls} cz-av-{p['kind']}{colour}", title=p["name"], aria_label=p["name"] if p["kind"] != "initials" else f"{p['name']} (not matched to a person)")


def faces_of(steps, limit=MAX_FACES):
    seen, out = set(), []
    for s in steps:
        for p in s["people"]:
            key = (p["kind"], p["name"])
            if key not in seen:
                seen.add(key)
                out.append(p)
    shown = [person_face(p) for p in out[:limit]]
    return Div(*shown, Span(f"+{len(out) - limit}", cls="cz-av cz-av-more") if len(out) > limit else "", cls="cz-faces") if shown else ""


def sticker(text, who="", cls=""):
    return Span(Span(text, cls="cz-sticker-text"), Span(who, cls="cz-sticker-by") if who else "", cls=f"cz-sticker {cls}".strip())


def _all_steps(blk):
    return [s for p in blk["parts"] for s in p["steps"]]


def _counts(blk):
    steps = _all_steps(blk)
    return len(steps), sum(1 for s in steps if s["done"])


def day_title(v, day):
    d = v["dates"][day]
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def sos_link(url, ident=True):
    """The small always-there emergency button in the heading (F-093): opens the emergency sheet over whatever is showing. The folded bar's copy has no id (F-103)."""
    return A(icon("life", 18, 2.4), Span("SOS"), href=url, cls="cz-sos", aria_label="Emergency: call 911 and your people", data_zoom="in", **({"id": "cz-sos", "data_zk": "sos-open"} if ident else {}))


def map_link(day, ident=True):
    """The small map button in a day's heading (F-096, replaces the Map tab): opens that day's map. A plain link, so the page changes; it is not a zoom."""
    return A(icon("map", 20, 2.4), href=f"/trip/map?day={day}", cls="cz-mapbtn", aria_label="Map of this day", **({"id": "cz-mapbtn"} if ident else {}))


def head(v, kicker, title, key="", back=None, back_label="", faces=None, sos="", mapday=None, switch=None):
    """The heading every level starts with. Week: plain. Deeper: a dark card with the way back, which is what the tapped element grows into. The week and the day carry
    the small Day | Week switch inside it (F-103), between the words and the buttons."""
    inner = [Div(Span(*kicker if isinstance(kicker, tuple) else (kicker,), cls="cz-head-k"), H1(title, id="cz-title", tabindex="-1"), cls="cz-head-text")]
    if back:
        inner.insert(0, A(icon("chev-left", 22, 2.6), href=back, cls="cz-back", aria_label=back_label, data_zoom="out"))
    if switch is not None:      # the switch, map and SOS travel together: on the narrowest phone they wrap as one group under the words
        inner.append(Div(switch, *([map_link(mapday)] if mapday is not None else []), *([sos_link(sos)] if sos else []), cls="cz-head-ctl"))
    else:
        if mapday is not None:
            inner.append(map_link(mapday))
        if sos:
            inner.append(sos_link(sos))
    if faces:
        inner.append(faces)
    return Header(*inner, cls=f"cz-head{' is-deep' if back else ''}{' has-switch' if switch is not None else ''}", **({"data_zk": key} if key else {}))


def view(level, body, zout="", title="", **attrs):
    """One level. `zout` names the element in it that shrinks back into the level above (its heading or sheet): data-zk marks that element, data-zout says which."""
    return Section(*body, cls=f"cz-view cz-level-{level}", data_level=level, data_title=title, tabindex="-1", **({"data_zout": zout} if zout else {}), **attrs)


# ---- touch: what a step carries for the script, the filters, the drop targets (F-082) ------------------------------------------

def step_data(s, edit):
    """The data a step's element carries: who and which lists (for the filters, every role), and, for editors, what the script needs to pick it up."""
    out = {"data_who": json.dumps(list(s["who_key"]), separators=(",", ":")), "data_lists": " ".join(s.get("lists") or [])}
    if edit:
        out.update(data_drag=s["id"], data_act=s["act"], data_aside="1" if s["aside"] else "0", data_time=s["time"])
    return out


def who_options(v, groups_always=False):
    """Every way to name who a step is for, as (token, label, person to draw): the family's members, names and initials the trip already uses, then Adults and Kids
    (only when a step uses them, since the family's ages are not known here; `groups_always` offers them anyway, for a new step)."""
    seen = []
    for blk in v["plan"].values():
        for s in [*_all_steps(blk), *blk["aside"]]:
            seen += [t for t in s["who_key"] if t not in seen]
    tokens = [f"m:{p['user_id']}" for p in v["people"]] + [t for t in seen if t.startswith(("n:", "i:"))] + [g for g in ("g:Adults", "g:Kids") if groups_always or g in seen]
    out = []
    for tok in tokens:
        p = canvas._person(tok, v["people"])
        out.append((tok, p["name"], p))
    return out


def filter_bar(v, compact=False):
    """Chips that highlight the steps that match and dim the rest: Everyone (no filter), each person, Adults and Kids when used, each named list of the trip."""
    chips = [Button("Everyone", type="button", cls="cz-fchip", data_f="all", aria_pressed="true")]
    for tok, label, p in who_options(v):
        face = "" if p["kind"] == "group" else Span(person_face(p), cls="cz-fchip-face", aria_hidden="true")
        chips.append(Button(face, label, type="button", cls="cz-fchip", data_f=f"who:{tok}", aria_pressed="false", **({"aria_label": f"{label} (not matched to a person)"} if p["kind"] == "initials" else {})))
    for lst in v["lists"]:
        chips.append(Button(icon("shield", 16, 2.4), lst["name"], type="button", cls="cz-fchip cz-fchip-list", data_f=f"list:{lst['id']}", aria_pressed="false"))
    return Div(*chips, cls="cz-filters", role="group", aria_label="Show", **({"data_compact": "1"} if compact else {}))


KINDS = (("all", "All"), ("plan", "Plans"), ("hotel", "Hotels"), ("flight", "Flights"), ("car", "Car"), ("chat", "Chats"))
KIND_OF_ICON = {"bed": "hotel", "hotel": "hotel", "plane": "flight", "car": "car"}


def kind_attrs(v, kind, x):
    """What the Plans | Hotels | Flights | Car | Chats filter reads off an entry of a day (F-093): its kind, and whether it has messages (a block: on it or on any part)."""
    if kind == "booked":
        return {"data_kind": KIND_OF_ICON.get(getattr(x, "icon", ""), "booking")}
    chat = any(k[0] == x.id for k in v["talk"])
    return {"data_kind": "plan", **({"data_chat": "1"} if chat else {})}


def kinds_bar():
    """The quiet filter row on the week and the day (F-093): one choice at a time. Hidden until the script is there to use it."""
    return Div(*[Button(label, type="button", cls="cz-kchip", data_k=k, aria_pressed="true" if k == "all" else "false") for k, label in KINDS], cls="cz-kinds", role="group", aria_label="Show only", hidden=True)


def dropbars(v):
    """What shows while a step is held (editors): the days that have a plan across the top, the Set aside tray along the bottom. Hidden until the script lifts a step."""
    days = sorted(((a.day, a) for a in (v["by_id"].get(i) for i in v["plan"]) if a), key=lambda e: (e[0], e[1].start))
    cells = [Span(Span(v["summaries"][d].dow, cls="cz-dd-dow"), Span(str(v["summaries"][d].num), cls="cz-dd-num"), cls="cz-dd", data_drop_act=a.id) for d, a in days]
    return Div(Div(Span("Move to another day", cls="cz-dd-t"), Div(*cells, cls="cz-dd-cells"), cls="cz-dropdays") if len(cells) > 1 else "",
               Div(icon("tray", 20, 2.4), Span("Drop to set aside"), cls="cz-dropaside", data_drop_aside="1"), cls="cz-dropbars", aria_hidden="true")


def listmore(v, a):
    """For each named list: the items that are not yet a step anywhere in this block's day, as chips to tap (or drag into a part) to add. Shown when that list is the filter."""
    editor = access.can_edit(v["role"])
    day_steps = [s for aid, blk in v["plan"].items() if v["by_id"].get(aid) and v["by_id"][aid].day == a.day for s in _all_steps(blk)]
    out = []
    for lst in v["lists"]:
        missing = [i for i in lst["items"] if not any(canvas.same_step(s["title"], i["title"]) for s in day_steps)]
        chips = []
        for i in missing:
            data = {"data_add_title": i["title"], "data_add_note": i["note"] or "", "data_act": a.id}
            chips.append(A(icon("plus", 14, 2.8), i["title"], href=curl(block=a.id, add=True, title=i["title"], note=i["note"] or ""), cls="cz-addchip", data_zoom="in", **data) if editor else Span(i["title"], cls="cz-addchip is-plain"))
        head = (Span(Span(_count(len(missing), "more", "more"), cls="cz-lm-n"), f" from your {lst['name']} list", Span(" aren't in this day yet.", cls="cz-lm-s")) if missing
                else Span(f"Everything on your {lst['name']} list is already in this day."))
        out.append(Section(P(head, cls="cz-lm-t"), Div(*chips, cls="cz-lm-chips") if chips else "", cls="cz-listmore", data_list=lst["id"], aria_label=f"More from {lst['name']}", hidden=True))      # shown by the script when this list is the filter
    return out


def swipe_buttons(s):
    """The two actions behind a swiped step: Done (or Not done) and Set aside. Each is a form, so it works the same as the sheet's buttons."""
    def one(do, label, ico, cls):
        return Form(_hidden("step", s["id"]), _hidden("do", do), _hidden("next", curl(block=s["act"])), trip_field(), Button(icon(ico, 18, 2.6), label, type="submit", cls=f"cz-sw-btn {cls}"),
                    action="/trip/canvas/step", method="post", data_cz_form="", data_cz_stay="", cls="cz-sw-form")
    return Div(one("undone" if s["done"] else "done", "Not done" if s["done"] else "Done", "x" if s["done"] else "check", "cz-sw-done"), one("aside", "Set aside", "tray", "cz-sw-aside"), cls="cz-swipe-acts")


# ---- week -------------------------------------------------------------------------------------------------------------------

def _mini_part(p, k):
    n, done = len(p["steps"]), sum(1 for s in p["steps"] if s["done"])
    when = p["time_of_day"] or ""
    return Span(Span(p["name"], cls="cz-mini-name"), Span(_count(n, "ride", "rides") if n else (when or "Plan"), cls="cz-mini-sub"), Span(f"{done} done", cls="cz-mini-done") if done else "", cls=f"cz-mini cz-pt-{PART_TINTS[k % 5]}")


def week_body(v, i, editor):
    """One day's row in the week. Plans are one link to the day; each booking is a link of its own that opens its sheet on that day (F-093)."""
    s = v["summaries"][i]
    ents = entries(v, i)
    today = Span("Today", cls="cz-today") if i == v["today_idx"] else ""
    badge = Span(Span(s.dow, cls="cz-dow"), Span(str(s.num), cls=f"cz-num ink-{s.tint}"), today, cls=f"cz-badge tp-t-{s.tint}")
    key = f"day-{i}"
    label = f"{v['dates'][i].strftime('%A %b')} {s.num}"
    thin = Span("", cls="cz-thin-t")
    if not ents:
        add = A(icon("plus", 20, 2.6), href=f"/trip?add=1&day={i}", cls="cz-plus", aria_label=f"Add something to {label}") if editor else ""
        return Div(badge, A(Span("Free day", cls="cz-free-t"), Span("Nothing planned yet", cls="cz-sub"), thin, href=curl(day=i), cls="cz-row-link cz-free", data_zoom="in", aria_label=f"{label}: free day"), add,
                   cls="cz-row is-free", data_zk=key, data_day=str(i))
    plans, bookings = [], []
    for n, (kind, x) in enumerate(ents):
        attrs = {**kind_attrs(v, kind, x), "data_n": str(n)}
        if kind == "block":
            blk = v["plan"][x.id]
            cnt, done = _counts(blk)
            notes = v["act_notes"].get(x.id) or [(None, st["note"]) for st in _all_steps(blk) if st["note"]][:1]
            note = sticker(notes[0][1], cls="cz-sticker-week") if notes else ""
            plans.append(Div(Div(Span(icon("sight", 18, 2.4), cls="cz-ico"), Span(x.title, cls="cz-card-t"), Span(f"{done}/{cnt}" if done else _count(cnt, "step", "steps"), cls="cz-pill"), cls="cz-card-h"),
                             Div(*[_mini_part(p, k) for k, p in enumerate(blk["parts"])], cls="cz-minis"), note, cls="cz-wcard cz-park", **attrs))
        elif kind == "booked":
            ico = getattr(x, "icon", "") or "pin"
            when = cal.fmt_time(x.label_start if getattr(x, "label_start", None) is not None else x.start)
            bookings.append(A(Span(icon(ico, 18, 2.4), cls="cz-ico"), Span(x.title, cls="cz-card-t"), Span(when, cls="cz-sub"), href=curl(day=i, booked=x.id), cls="cz-wcard cz-simple is-booked", data_zoom="in", data_zk=f"bkg-{x.id}",
                              aria_label=f"{x.title}, {when}: details", **attrs))
        else:
            ico = getattr(x, "icon", "") or "pin"
            plans.append(Div(Span(icon(ico, 18, 2.4), cls="cz-ico"), Span(x.title, cls="cz-card-t"), Span(cal.fmt_time(x.start), cls="cz-sub"), cls="cz-wcard cz-simple", **attrs))
    more = Span(f"and {len(ents) - 3} more", cls="cz-sub cz-more", hidden=True) if len(ents) > 3 else ""      # the script shows three entries and this line; with a filter on, every match
    openday = Span("Open the day", icon("chev-right", 16, 2.6), cls="cz-sub cz-openday") if not plans else ""
    link = A(*plans, more, openday, thin, href=curl(day=i), cls="cz-row-link", data_zoom="in", aria_label=f"{label}: {s.head}")
    return Div(badge, Div(link, *bookings, cls="cz-row-main"), cls=f"cz-row{' is-today' if i == v['today_idx'] else ''}", data_zk=key, data_day=str(i))


def toggle(v, current, day=None, ids=True):
    """Day | Week (F-092): the one way between the two views (pinch is gone). Day opens the day being looked at, else today (the first day before the trip). F-103: a small
    switch inside the heading; the folded bar has a second one without ids (`ids=False`)."""
    if day is None:
        day = v["today_idx"] if v["today_idx"] is not None else (len(v["dates"]) - 1 if v["dates"] and catalog.today_in(v["zone"]) > v["dates"][-1] else 0)   # the last day once the trip is over, like the Today tab
    links = [A(Span("Day"), href=curl(day=day), cls="cz-seg", aria_current="page" if current == "day" else None, **({"id": "cz-z-day"} if ids else {}), **({} if current == "day" else {"data_zoom": "in"})),
             A(Span("Week"), href=curl(), cls="cz-seg", aria_current="page" if current == "week" else None, **({"id": "cz-z-week"} if ids else {}), **({} if current == "week" else {"data_zoom": "out"}))]
    return Nav(*links, cls="cz-segs cz-toggle", aria_label="Day or week")


def week_view(v, sos=False):
    t = v["t"]
    editor = access.can_edit(v["role"])
    faces = Div(avatar(v["who"], "cz-av"), *[avatar(f, "cz-av") for f in v["crew"]], cls="cz-faces")
    kicker = f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}"
    rows = [week_body(v, i, editor) for i in range(len(v["dates"]))]
    body = [head(v, kicker, "The trip", faces=faces, sos=curl(sos=True), switch=toggle(v, "week")), Div(kinds_bar(), cls="cz-bar"), Div(*rows, cls="cz-week", id="cz-week", style=f"--days:{min(len(rows), 7)}")]
    body.append(sos_sheet(v, curl(), curl(sos=True)) if sos else sos_template(v, curl(), curl(sos=True)))
    return view("step" if sos else "week", body, zout="sos-open" if sos else "", title="The trip")


# ---- day --------------------------------------------------------------------------------------------------------------------

def _tray(steps, edit, ident="cz-tray", open_id=""):
    if not steps:
        return ""
    chips = [A(icon("undo", 14, 2.4), Span(s["title"], cls="cz-chip-t"), href=curl(step=s["id"]), cls="cz-chip cz-chip-aside", data_zoom="in", **({"data_zk": f"stp-{s['id']}"} if s["id"] != open_id else {}), **step_data(s, edit)) for s in steps]
    return Section(Div(H3(icon("tray", 16, 2.4), f"Set aside · {len(steps)}", cls="cz-tray-t"), Span("still in the trip", cls="cz-sub"), cls="cz-tray-h"), Div(*chips, cls="cz-tray-chips"), cls="cz-tray", id=ident, aria_label="Set aside")


def strip(v, day):
    """The week across the top (a laptop only): one card per day with a bar segment per part, the open day marked."""
    cards = []
    for i, s in enumerate(v["summaries"]):
        ents = entries(v, i)
        segs = []
        for kind, x in ents:
            if kind == "block":
                segs += [Span(cls=f"cz-seg-bar cz-pt-{PART_TINTS[k % 5]}") for k, _ in enumerate(v["plan"][x.id]["parts"])]
            else:
                segs.append(Span(cls="cz-seg-bar is-plain"))
        cards.append(A(Div(Span(s.dow, cls="cz-strip-dow"), Span(str(s.num), cls=f"cz-strip-num ink-{s.tint}")), Span(s.head, cls="cz-strip-head"), Div(*segs[:8], cls="cz-bars", aria_hidden="true"),
                       href=curl(day=i), cls=f"cz-strip-day{' is-open' if i == day else ''}", aria_current="date" if i == day else None, data_zoom="side", aria_label=f"{v['dates'][i].strftime('%A %b')} {s.num}: {s.head}"))
    return Nav(*cards, cls="cz-strip", aria_label="Days of the trip", style=f"--days:{min(len(cards), 7)}")


def booked_line(v, x):
    """A booking on the day (F-090): a quiet grey line behind the family's plans, with its time. A tap opens its sheet over the day (F-093): address, Directions, Call, times, confirmation, passes."""
    when = cal.fmt_time(x.label_start if getattr(x, "label_start", None) is not None else x.start)
    return A(Span(when, cls="cz-bk-time"), Span(icon(getattr(x, "icon", "") or "lock", 16, 2.4), cls="cz-bk-ico", aria_hidden="true"), Span(x.title, cls="cz-bk-t"),
             Span("Booked", cls="cz-bk-tag"), href=curl(day=x.day, booked=x.id), cls="cz-bk", data_zoom="in", data_zk=f"bkg-{x.id}", **kind_attrs(v, "booked", x))


def day_pills(v, day):
    """A phone's dates across the top (F-090): the whole trip one tap out, then every day (the open one marked, today ringed, a dot when the family planned something)."""
    items = []
    for i, s in enumerate(v["summaries"]):
        planned = any(kind != "booked" for kind, _ in entries(v, i))
        cls = "cz-dp" + (" is-open" if i == day else "") + (" is-today" if i == v["today_idx"] else "") + (" has-plans" if planned else "")
        label = f"{v['dates'][i].strftime('%A %b')} {s.num}" + (", today" if i == v["today_idx"] else "") + ("" if planned else ", nothing planned")
        items.append(A(Span(s.dow, cls="cz-dp-dow"), Span(str(s.num), cls="cz-dp-num"), Span(cls="cz-dp-dot", aria_hidden="true"),
                       href=curl(day=i), cls=cls, aria_current="date" if i == day else None, aria_label=label, data_zoom="side"))
    return Nav(*items, cls="cz-dpills", id="cz-dpills", aria_label="Days of the trip")


def say_bar_compact(day):
    """F-101: on a blank day the editor's grid is there to hold, so Talk / Paste shrink to one row above it (same ids and links as `say_bar`)."""
    return Div(A(icon("mic", 20, 2.4), "Say the plan", href=f"/trip/ask?day={day}&mode=talk", id="cz-say-talk", cls="tp-btn tp-btn-coral cz-say-go"),
               A(icon("note", 18, 2.4), "Paste a plan", href=f"/trip/ask?day={day}&mode=paste", id="cz-say-paste", cls="tp-btn tp-btn-white cz-say-go"),
               cls="cz-empty cz-say-empty cz-say-compact", id="cz-empty")


def say_bar(day):
    """A day with nothing planned (F-090): the two ways in, talk and paste, opening Ask on this day (F-087). Any other day is changed from the centre Ask (F-092)."""
    return Div(Span(icon("mic", 30, 2.2), cls="cz-say-ico", aria_hidden="true"), P("Nothing planned yet", cls="cz-say-h"),
               P("Say the plan for this day, or paste it from a message. GitAway lays it out and asks if something is unclear.", cls="cz-sub"),
               Div(A(icon("mic", 20, 2.4), "Say the plan for this day", href=f"/trip/ask?day={day}&mode=talk", id="cz-say-talk", cls="tp-btn tp-btn-coral cz-say-go"),
                   A(icon("note", 18, 2.4), "Paste a plan", href=f"/trip/ask?day={day}&mode=paste", id="cz-say-paste", cls="tp-btn tp-btn-white cz-say-go"), cls="cz-say-acts"),
               cls="cz-empty cz-say-empty", id="cz-empty")


# ---- the day as a time grid (F-097) -------------------------------------------------------------------------------------------

BOOKING_ROOM = 40       # minutes of grid a booking line takes (its 2.75rem tap target): a booking close after another slides below it, its label still says its true time
KIND_TINT = {"fun": "bubble", "food": "sun", "outdoors": "mint", "culture": "grape", "travel": "sky"}


def hour_label(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def span_label(s, e):
    """"12:00 – 1:30 PM": the meridiem once when both ends share it."""
    a, b = cal.fmt_time(s), cal.fmt_time(e)
    return f"{a.rsplit(' ', 1)[0]} – {b}" if a[-2:] == b[-2:] else f"{a} – {b}"


def grid_bookings(booked):
    """[(booking, the minute its line is drawn at)]: in time order, a line that would sit on the one above slides down below it."""
    out, floor = [], -BOOKING_ROOM
    for x in sorted(booked, key=lambda b: (b.start, b.id)):
        top = max(x.start, floor + BOOKING_ROOM)
        out.append((x, top))
        floor = top
    return out


def grid_range(plans, lines):
    """(first, last) minute the day's grid shows: 7 AM to 10 PM, wider for an earlier or later booking or plan, on whole hours."""
    lo = min([cal.DEFAULT_START, *(a.start for a in plans), *(t for _, t in lines)]) // 60 * 60
    hi = max([cal.GRID_END, *(a.end for a in plans), *(t + BOOKING_ROOM for _, t in lines)])
    return lo, min(-(-hi // 60) * 60, 24 * 60)


def _union_who(steps):
    """The who a block carries for the filters: nobody in particular when any step is for everyone (it then matches each person), else everyone named."""
    keys = [s["who_key"] for s in steps]
    if not keys or any(not k for k in keys):
        return []
    return sorted({t for k in keys for t in k})


def short_title(title):
    """The first part of a booking's title ("Check in · Hotel Maya · 2 rooms" -> "Check in"): what a slim pill has room for."""
    return title.split(" · ")[0].strip() or title


def compact_time(m):
    """"11 AM", "11:30 AM": a time with no ":00", for a pill."""
    t = cal.fmt_time(m)
    return t.replace(":00", "", 1)


def note_preview(v, act):
    """The one line of a block's note: every note on the plan, in order, joined (the card shows them in full)."""
    return " · ".join(text for _, text in v["act_notes"].get(act, []))


def grid_block(v, a, lane, lanes, lo, edit, inset=False):
    """One plan as a block: its place and size are its time (CSS reads --s and --l), side by side with the plans it overlaps (--lane of --lanes). The block shows its title, its time,
    one line of its note (it fades at the end, F-106) and how much was said in its chat; a tap anywhere on it opens its card (day_card.js), which has the whole note and the chat. Without
    script the tap is a link: a park block's goes to its block level, a plan's to its chat page (F-097, F-106). `inset` makes room at the left for a booking pill (F-106)."""
    park = has_block(v, a.id)
    blk = v["plan"][a.id] if park else None
    steps = [*_all_steps(blk), *blk["aside"]] if park else []
    k = a.kind if a.kind in KIND_TINT else "fun"
    chat = any(c[0] == a.id for c in v["talk"])
    n = sum(m["n"] for key, m in v["talk"].items() if key[0] == a.id)
    voice = any(m["voice"] for key, m in v["talk"].items() if key[0] == a.id)
    attrs = {**kind_attrs(v, "block" if park else "plan", a), "data_act": a.id, "data_s": str(a.start), "data_e": str(a.end), "data_day": str(a.day), "data_title": a.title,
             "data_steps": str(len(steps))}
    if edit:
        attrs["data_talk"] = plantalk.url(a.id, "", ses.open_trip_id())          # the hold menu's Chat (F-098); data-chat is the filter's "has messages"
    if park:
        attrs.update(data_who=json.dumps(_union_who(_all_steps(blk)), separators=(",", ":")), data_lists=" ".join(sorted({x for s in steps for x in (s.get("lists") or [])})), data_zk=f"blk-{a.id}")
    when = span_label(a.start, a.end)
    said = f"{n} message{'' if n == 1 else 's'}" + (", with a voice note" if voice else "")
    preview = note_preview(v, a.id)
    inner = [Span(Span(a.title, cls="cz-gb-t", id=f"cz-t-{a.id}"), Span(when, cls="cz-gb-when"), cls="cz-gb-head"),      # F-110: the title and the time stay in view at the top of a tall block (sticky)
             Span(preview, cls="cz-gb-note") if preview else "",
             Span(*[Span(p["name"], cls="cz-gb-part", data_part=p["id"], data_act=a.id) for p in blk["parts"]], cls="cz-gb-parts") if park else "",
             Span(icon("chat", 14, 2.4), Span(str(n), cls="pt-n"), icon("mic", 13, 2.4) if voice else "", cls="cz-gb-chat", aria_hidden="true") if chat else ""]
    link = A(href=curl(block=a.id) if park else plantalk.url(a.id, "", ses.open_trip_id()), cls="cz-gb-open", data_card="1",
             aria_label=f"Open {a.title}, {when}" + (f", {said}" if chat else ""), **({"data_zoom": "in"} if park else {}))
    extra = [link]
    if edit:
        extra += [Button(f"Change {a.title}", type="button", cls="sr-only cz-gb-menubtn")]
    cls = f"cz-gb cz-k-{k}" + (" is-park" if park else "") + (" is-short" if a.end - a.start < 45 else " is-tight" if a.end - a.start < 75 and not park else "") + (" has-chat" if chat else "") + (" is-inset" if inset else "")
    style = f"--s:{a.start - lo};--l:{a.end - a.start};--lane:{lane};--lanes:{lanes}"
    return Div(Div(*inner, cls="cz-gb-in cz-cs"), *extra, cls=cls, style=style, **({"tabindex": "-1"} if park else {}), **attrs)


PILL_SPAN = 60       # a plan within this many minutes below a booking's line is "over" it: the booking then draws as a pill beside the plan (F-106)


def booking_pill(v, x, top, lo):
    """A booking that a plan overlaps (F-106): a slim pill at the left edge of the grid, in the lane the plan leaves free: the time and the icon on top, the short name wrapped below (words are
    never cut; the full title is the label a screen reader reads and the booking's sheet shows). Still a link to the sheet."""
    at = x.label_start if getattr(x, "label_start", None) is not None else x.start
    return A(Span(Span(compact_time(at), cls="cz-bk-time"), icon(getattr(x, "icon", "") or "lock", 14, 2.4), cls="cz-bk-row"), Span(short_title(x.title), cls="cz-bk-t"),
             href=curl(day=x.day, booked=x.id), cls="cz-bk cz-gbk is-pill", data_zoom="in", data_zk=f"bkg-{x.id}", style=f"--s:{top - lo}", aria_label=f"{x.title}, {cal.fmt_time(at)}, booked", **kind_attrs(v, "booked", x))


def overlap_groups(plans):
    """The plans split into groups that overlap one another, directly or through a third (they share lanes, so they must all keep the same left edge)."""
    out = []
    for a in sorted(plans, key=lambda p: (p.start, p.id)):
        if out and a.start < max(p.end for p in out[-1]):
            out[-1].append(a)
        else:
            out.append([a])
    return out


def time_grid(v, day, ents):
    """The day's plans as blocks on an hour grid sized by their length (overlaps side by side), its bookings as quiet lines at their times, today's now line."""
    edit = access.can_edit(v["role"])
    plans = [x for kind, x in ents if kind != "booked"]
    lines = grid_bookings([x for kind, x in ents if kind == "booked"])
    lo, hi = grid_range(plans, lines)
    hours = list(range(lo // 60, hi // 60 + 1))
    lane = calui.lanes(plans)
    gutter = [Span(hour_label(h % 24 if h < 24 else 0), cls="cz-g-hour cz-cs", style=f"--s:{h * 60 - lo}") for h in hours]
    rules = [Span(cls=f"cz-g-line cz-cs{' is-half' if m else ''}", style=f"--s:{h * 60 + m - lo}") for h in hours[:-1] for m in (0, 30)] + [Span(cls="cz-g-line cz-cs", style=f"--s:{hi - lo}")]
    covered = {x.id: [a for a in plans if a.start < top + PILL_SPAN and a.end > top] for x, top in lines}      # the plans over each booking line (F-106)
    over = {a.id for under in covered.values() for a in under}
    inset = {a.id for group in overlap_groups(plans) if any(a.id in over for a in group) for a in group}      # plans that share lanes share a left edge: one inset, all inset
    bk = [booking_pill(v, x, top, lo) if covered[x.id] else
          A(Span(icon(getattr(x, "icon", "") or "lock", 16, 2.4), Span(cal.fmt_time(x.label_start if getattr(x, "label_start", None) is not None else x.start), cls="cz-bk-time"), Span(x.title, cls="cz-bk-t"),
              Span("Booked", cls="cz-bk-tag"), cls="cz-gbk-in cz-cs"), href=curl(day=x.day, booked=x.id), cls="cz-bk cz-gbk", data_zoom="in", data_zk=f"bkg-{x.id}", style=f"--s:{top - lo}", **kind_attrs(v, "booked", x))
          for x, top in lines]
    blocks = [grid_block(v, a, *lane[a.id], lo, edit, a.id in inset) for a in plans]
    now = ""
    if day == v["today_idx"] and lo <= (nm := td.now_minute(v["clock"])) <= hi:
        now = Span(Span(cls="cz-now-dot"), cls="cz-nowline", id="cz-nowline", data_m=str(nm), style=f"--s:{nm - lo}", aria_label="Now", role="img")
    plane = Div(*rules, *bk, *blocks, now, cls="cz-g-plane")
    nxt = {"data_next": cal.next_id(v["session"])} if edit else {}      # the calendar's next number: a new plan made here carries its own id (a retry after a lost reply adds nothing twice)
    return Div(Div(*gutter, plane, cls="cz-g-zoom"), cls=f"cz-grid{' has-bk' if lines else ''}{' has-pill' if inset else ''}", id="cz-grid", data_lo=str(lo), data_hi=str(hi), data_day=str(day), **nxt, style=f"--n:{(hi - lo) / 60:g}", role="group", aria_label="The day, hour by hour")


def fold_bar(v, day):
    """F-103: the day's heading, filters and dates folded into one compact bar (the day's name, the small switch, map, SOS). It is in the page from the start but takes no room
    (a zero-height sticky box, so showing it never moves anything) and is hidden and inert; day_fold.js shows it once the top of the day has scrolled away, and a tap on it scrolls back up."""
    return Div(Div(Button(Span(day_title(v, day)), type="button", cls="cz-fold-name", aria_label="Show the top of the day"), toggle(v, "day", day, ids=False), map_link(day, ident=False), sos_link(curl(day=day, sos=True), ident=False), cls="cz-fold-bar"),
               cls="cz-fold", inert=True, aria_hidden="true")


def day_view(v, day, booked=None, sos=False):
    editor = access.can_edit(v["role"])
    d = v["dates"][day]
    ents = entries(v, day)
    planned = [(kind, x) for kind, x in ents if kind != "booked"]
    cards = [time_grid(v, day, ents)] if planned or editor else [booked_line(v, x) for _, x in ents]      # a blank day: an editor gets the grid too (hold empty time, F-101); a viewer the booking lines
    aside = [s for kind, x in ents if kind == "block" for s in v["plan"][x.id]["aside"]]
    if not planned:
        empty = say_bar_compact(day) if editor else Div(P("Nothing planned yet", cls="cz-say-h"), P("Nobody has planned this day yet.", cls="cz-sub"), cls="cz-empty cz-say-empty", id="cz-empty", data_kind="empty")
        cards = [empty, *cards]
    kicker = (f"{d.strftime('%a %b').upper()} {d.day}", Span(f" · DAY {day + 1} OF {len(v['dates'])}", cls="cz-k-day"))      # the day count drops out on a phone (F-103: the heading is one row)
    first =next((x for kind, x in ents if kind == "block"), None)
    body = [fold_bar(v, day), head(v, kicker, d.strftime("%A"), key=f"day-{day}", back=curl(), back_label="Zoom out to the week", sos=curl(day=day, sos=True), mapday=day, switch=toggle(v, "day", day)), Div(kinds_bar(), cls="cz-bar"), day_pills(v, day), strip(v, day),
            now_card(v, day),      # F-092: the centre Ask changes the day; on today the day starts with what is happening now
            *([filter_bar(v, True)] if first else []), *([dropbars(v)] if first and editor else []),
            Div(Div(*cards, *(listmore(v, first) if first else []), P("Nothing here for this filter.", cls="cz-sub cz-kind-none", hidden=True), cls="cz-day-main"), Div(_tray(aside, editor), cls="cz-day-side"), cls="cz-day-body")]
    if booked:
        body.append(booking_sheet(v, day, booked))
    elif sos:
        body.append(sos_sheet(v, curl(day=day), curl(day=day, sos=True)))
    else:
        body.append(sos_template(v, curl(day=day), curl(day=day, sos=True)))
    near = {"data_prev": curl(day=day - 1)} if day > 0 else {}
    if day < len(v["dates"]) - 1:
        near["data_next"] = curl(day=day + 1)
    if booked or sos:
        return view("step", body, zout=f"bkg-{booked[0].id}" if booked else "sos-open", title=day_title(v, day), data_day=str(day))
    return view("day", body, zout=f"day-{day}", title=day_title(v, day), data_day=str(day), **near)


# ---- block ------------------------------------------------------------------------------------------------------------------

def slots(steps):
    """A part's steps grouped into runs that share a time. A run where people split up (two or more steps at the same time for different people, "Everyone" being
    the empty set) is drawn as side-by-side lanes; everything else runs full width. -> [(split, [steps])]"""
    runs = []
    for s in steps:
        if runs and s["time"] and runs[-1][0]["time"] == s["time"]:
            runs[-1].append(s)
        else:
            runs.append([s])
    return [(len({x["who_key"] for x in r}) > 1, r) for r in runs]


def lane_label(s):
    if not s["people"]:
        return Span("Everyone", cls="cz-lane-who")
    return Span(*[person_face(p) for p in s["people"][:4]], Span(", ".join(p["name"] for p in s["people"]), cls="cz-lane-names"), cls="cz-lane-who")


def _row(s, hero, edit):
    ring = Span(icon("check", 16, 3) if s["done"] else "", cls="cz-ring", aria_hidden="true")
    link = A(ring, Div(Div(Span(s["time"], cls="cz-time") if s["time"] else "", Span(s["title"], cls="cz-step-t"), cls="cz-step-line"), sticker(s["note"], cls="cz-sticker-step") if s["note"] else "", cls="cz-step-main"),
             faces_of([s], 3), Span("Done", cls="sr-only") if s["done"] else "", href=curl(step=s["id"]), cls=f"cz-step{' is-done' if s['done'] else ''}", data_zoom="in", data_step=s["id"], **({"data_zk": f"stp-{s['id']}"} if hero else {}))
    return Div(swipe_buttons(s) if edit else "", link, cls="cz-swipe", **step_data(s, edit))


MEALS = ("breakfast", "lunch", "dinner", "snack")


def ideas_button(day, ident):
    """"Ideas" on a meal (F-073): opens Around you on that day with the vegetarian food chip picked."""
    return A(icon("spark", 14, 2.4), "Ideas", href=around_url(day=day, cat="veg"), cls="btn btn-sm tp-edit ar-ideas", id=ident, title="Ideas for this meal near you")


def block_view(v, act_id, open_step=None, adding=None, sos=False):
    a = v["by_id"][act_id]
    blk = v["plan"][act_id]
    d = v["dates"][a.day]
    editor = access.can_edit(v["role"])
    n, done = _counts(blk)
    open_id = open_step[0]["id"] if open_step else ""
    allsteps = _all_steps(blk)
    notes = [sticker(text, by) for by, text in v["act_notes"].get(a.id, [])]
    sections, lanes_used = [], False
    for k, p in enumerate(blk["parts"]):
        items = []
        for split, run in slots(p["steps"]):
            if split:
                lanes_used = True
                items.append(Div(*[Div(lane_label(s), _row(s, s["id"] != open_id, editor), cls="cz-lane") for s in run], cls="cz-lanes", data_lanes=str(len(run))))
            else:
                items += [_row(s, s["id"] != open_id, editor) for s in run]
        pn, pd = len(p["steps"]), sum(1 for s in p["steps"] if s["done"])
        ideas = ideas_button(a.day, f"ar-ideas-{p['id']}") if p["name"].casefold() in MEALS else ""
        sections.append(Section(Div(H2(p["name"]), Span(p["time_of_day"], cls="cz-when") if p["time_of_day"] else "", Span(f"{pd} of {pn} done" if pn else "", cls="cz-part-n"), ideas, talk_badge(v["talk"], a.id, p["id"]), cls="cz-part-h"),
                                *(items or [P("Nothing here yet.", cls="cz-sub")]), cls=f"cz-bpart cz-pt-{PART_TINTS[k % 5]}", data_part=p["id"], data_act=a.id))
    lists = [Section(Div(H3(lst["name"]), Span(f"for {lst['for']}", cls="cz-when") if lst["for"] else "", cls="cz-part-h"),
                     Div(*[Span(i["title"], cls="cz-list-i") for i in lst["items"]], cls="cz-list"), cls="cz-bpart cz-triplist", data_list=lst["id"]) for lst in v["lists"]]
    legend = Div(Span(icon("users", 14, 2.4), "Lanes: people who split up at the same time", cls="cz-sub"), cls="cz-legend") if lanes_used else ""
    add_btn = ""
    if editor and blk["parts"]:
        add_btn = A(icon("plus", 18, 2.6), "Add a step", href=curl(block=a.id, add=True), id="cz-add", cls="tp-btn tp-btn-ink cz-add", data_zoom="in", **({} if adding else {"data_zk": "stp-new"}))
    kicker = f"{d.strftime('%a %b').upper()} {d.day} · {cal.fmt_time(a.start)} – {cal.fmt_time(a.end)}"
    body = [head(v, kicker, a.title, key=f"blk-{a.id}", back=curl(day=a.day), back_label="Zoom out to the day", faces=faces_of(allsteps, 4), sos=curl(block=a.id, sos=True)),
            Div(*notes, cls="cz-notes") if notes else "", Div(Span(f"{done} of {n} done", cls="cz-prog"), legend, add_btn, talk_badge(v["talk"], a.id), cls="cz-block-meta"),
            filter_bar(v), *([dropbars(v)] if editor else []),
            Div(*sections, cls="cz-bparts"), *listmore(v, a), Div(_tray(blk["aside"], editor, open_id=open_id), cls="cz-block-side"), *lists]
    if open_step:
        body.append(sheet(v, open_step, a))
    elif adding is not None:
        body.append(add_sheet(v, a, adding))
    elif sos:
        body.append(sos_sheet(v, curl(block=a.id), curl(block=a.id, sos=True)))
    else:
        body.append(sos_template(v, curl(block=a.id), curl(block=a.id, sos=True)))
    return view("step" if open_step or adding is not None or sos else "block", body, zout=f"stp-{open_id}" if open_step else "stp-new" if adding is not None else "sos-open" if sos else f"blk-{a.id}", title=a.title, data_day=str(a.day), data_block=a.id)


# ---- step -------------------------------------------------------------------------------------------------------------------

def _post_form(action, fields, *content, cls="cz-act-form", **attrs):
    """A form that posts to the canvas: hidden fields, the trip this page was drawn for, then its fields and button."""
    return Form(*[_hidden(k, val) for k, val in fields.items()], trip_field(), *content, action=action, method="post", data_cz_form="", cls=cls, **attrs)


def sheet(v, found, a):
    s, act_id, part, tod = found
    editor = access.can_edit(v["role"])
    d = v["dates"][a.day]
    where = f"{d.strftime('%a %b')} {d.day}" + (f" · {tod.lower()}" if tod else "")
    close = curl(block=act_id)
    who = Div(*[Span(person_face(p), Span(p["name"], cls="cz-who-n"), cls="cz-who") for p in s["people"]], cls="cz-whos") if s["people"] else Div(Span(icon("users", 16, 2.4), Span("Everyone", cls="cz-who-n"), cls="cz-who"), cls="cz-whos")
    state = "Done" if s["done"] else "Set aside · still in the trip" if s["aside"] else ""
    buttons, more = "", ""
    if editor:
        def post(do, label, cls, ico):
            return _post_form("/trip/canvas/step", {"step": s["id"], "do": do, "next": close}, Button(icon(ico, 18, 2.6), label, type="submit", cls=cls))
        main = post("undone", "Not done", "tp-btn tp-btn-white cz-act cz-act-main", "x") if s["done"] else post("done", "Mark done", "tp-btn tp-btn-coral cz-act cz-act-main", "check")
        side = post("back", "Put back", "tp-btn tp-btn-white cz-act", "undo") if s["aside"] else ""      # F-121: no Set aside here (a swipe still has it); a step already set aside can be put back
        buttons = Div(main, side, cls="cz-acts")
        sheet_url = curl(step=s["id"])
        note_form = _post_form("/trip/canvas/note", {"step": s["id"], "next": sheet_url},
                               Input(type="text", name="note", value=s["note"], maxlength=str(canvas.MAX_NOTE), placeholder="+ Add a note", aria_label="Note", cls="cz-note-in cz-note-sticky", enterkeyhint="done"),
                               Button("Save note", type="submit", cls="sr-only cz-save"), cls="cz-note-form", data_cz_stay="")
        # F-121: the note is the sticky itself: tap it and write; it saves when the keyboard goes (trip_canvas.js). No Move here: the calendar is where things move.
        more = Div(note_form, cls="cz-more", id="cz-notebox")
    else:
        buttons = P("You can look at this step but not change it.", cls="cz-sub cz-viewer", id="cz-viewer")
    return Div(A(href=close, cls="cz-scrim", aria_label="Close", tabindex="-1", data_zoom="out"),
               Div(Div(cls="cz-grab", aria_hidden="true"),
                   Div(Div(*[Span(x, cls="cz-pill") for x in (part, where) if x], cls="cz-pills"), A(icon("x", 20, 2.6), href=close, cls="cz-close", aria_label="Close", data_zoom="out"), cls="cz-sheet-top"),
                   H2(s["title"], id="cz-sheet-title", tabindex="-1"), Span(state, cls="cz-state", id="cz-state") if state else "",
                   more if editor else sticker(s["note"], "Note", cls="cz-sticker-sheet") if s["note"] else "",
                   Div(Span("Who's going", cls="cz-label"), who), buttons,
                   cls="cz-sheet", role="dialog", aria_modal="true", aria_labelledby="cz-sheet-title", data_zk=f"stp-{s['id']}", data_step=s["id"]), cls="cz-sheet-wrap")


def sheet_wrap(close, pills, title, *body, zk, cls="", **attrs):
    """A bottom sheet over the level (the step sheet's look): scrim and close both go to `close`."""
    return Div(A(href=close, cls="cz-scrim", aria_label="Close", tabindex="-1", data_zoom="out"),
               Div(Div(cls="cz-grab", aria_hidden="true"),
                   Div(Div(*[Span(x, cls="cz-pill") for x in pills], cls="cz-pills"), A(icon("x", 20, 2.6), href=close, cls="cz-close", aria_label="Close", data_zoom="out"), cls="cz-sheet-top"),
                   H2(title, id="cz-sheet-title", tabindex="-1"), *body,
                   cls=f"cz-sheet {cls}".strip(), role="dialog", aria_modal="true", aria_labelledby="cz-sheet-title", data_zk=zk, **attrs), cls="cz-sheet-wrap")


def booking_sheet(v, day, booked_block):
    """A booking's sheet over its day (F-093): `booked_block` is (the block, what it is). Everything Help showed for it, drawn by gitaway.pages.booked."""
    x, found = booked_block
    pills, title, body = booked.sheet(v, found, v.get("ua", ""), curl(day=x.day, booked=x.id), curl(day=x.day))
    return sheet_wrap(curl(day=day), pills, title, booked.problem(v.get("err", "")), *body, zk=f"bkg-{x.id}", cls="cz-sheet-bk", data_booked=x.id)


def sos_sheet(v, close, back=""):
    """The emergency sheet (F-093): 911, tonight's front desk, the rental counter, the family's numbers, and a way to "This phone"."""
    return sheet_wrap(close, ["Emergency"], "Who to call", booked.problem(v.get("err", "")), *booked.sos(v, v.get("ua", ""), back or close), zk="sos-open", cls="cz-sheet-sos")


def sos_template(v, close, back=""):
    """The emergency sheet again, inert, in every week and day page: the script opens it from here without the network, so SOS works with no signal once the page is open (Help promised that)."""
    return Template(sos_sheet(v, close, back), id="cz-sos-tpl")


ADD_ERRORS = {"title": "Give the step a name.", "time": "That time is not one we can read.", "other": "That step could not be added. Check it and try again."}


def add_sheet(v, a, adding):
    """The add-a-step sheet over a block (Plan-Steps frame 4): a name, who it is for, which part, an optional time, a note."""
    blk = v["plan"][a.id]
    close = curl(block=a.id)
    title, note, want = adding.get("title", ""), adding.get("note", ""), adding.get("part", "")
    chosen = want if any(p["id"] == want for p in blk["parts"]) else blk["parts"][0]["id"]
    people = [Label(Input(type="checkbox", name="who", value="all", checked=True, cls="cz-pick-in"), Span(icon("users", 16, 2.4), "Everyone", cls="cz-pick-t"), cls="cz-pick cz-pick-all")]
    for tok, label, p in who_options(v, groups_always=True):
        face = "" if p["kind"] == "group" else Span(person_face(p), cls="cz-pick-face", aria_hidden="true")
        people.append(Label(Input(type="checkbox", name="who", value=tok, cls="cz-pick-in"), face, Span(label, cls="cz-pick-t"), cls="cz-pick", **({"title": f"{label} (not matched to a person)"} if p["kind"] == "initials" else {})))
    parts = [Label(Input(type="radio", name="part", value=p["id"], checked=p["id"] == chosen, cls="cz-pick-in"), Span(p["name"], cls="cz-pick-t"), cls="cz-pick cz-pick-part") for p in blk["parts"]]
    error = ADD_ERRORS.get(adding.get("err", ""), "")
    form = Form(_hidden("act", a.id), _hidden("next", close), trip_field(),
                Label(Span("What", cls="cz-label"), Input(type="text", name="title", value=title, maxlength="80", required=True, placeholder="Churro break", id="cz-add-title", cls="cz-field"), cls="cz-fieldwrap"),
                Div(Span("Who", cls="cz-label"), Div(*people, cls="cz-picks", role="group", aria_label="Who is this step for"), cls="cz-fieldwrap"),
                Div(Span("Where in the day", cls="cz-label"), Div(*parts, cls="cz-picks", role="group", aria_label="Which part of the day"), cls="cz-fieldwrap"),
                Label(Span("When (optional)", cls="cz-label"), Input(type="time", name="time", step="900", data_ga_label="When", cls="cz-field", id="cz-add-time"), cls="cz-fieldwrap"),
                Label(Span("Note (optional)", cls="cz-label"), Input(type="text", name="note", value=note, maxlength=str(canvas.MAX_NOTE), placeholder="A fun one", id="cz-add-note", cls="cz-field"), cls="cz-fieldwrap"),
                P(error, role="alert", cls="cz-error", id="cz-form-error"),
                Button(icon("plus", 18, 2.6), "Add step", type="submit", cls="tp-btn tp-btn-coral cz-act cz-act-main", id="cz-add-go"),
                action="/trip/canvas/add", method="post", data_cz_form="", cls="cz-add-form", id="cz-add-form")
    return Div(A(href=close, cls="cz-scrim", aria_label="Close", tabindex="-1", data_zoom="out"),
               Div(Div(cls="cz-grab", aria_hidden="true"),
                   Div(Span("Add a step", cls="cz-pill"), A(icon("x", 20, 2.6), href=close, cls="cz-close", aria_label="Close", data_zoom="out"), cls="cz-sheet-top"),
                   H2(a.title, id="cz-sheet-title", tabindex="-1"), form,
                   cls="cz-sheet cz-sheet-add", role="dialog", aria_modal="true", aria_labelledby="cz-sheet-title", data_zk="stp-new"), cls="cz-sheet-wrap")


# ---- the page and the routes ---------------------------------------------------------------------------------------------

def resolve(v, day="", block="", step="", add=None, booked_id="", sos=False):
    """(level, the view) for the address, or None when it names something that is not there (the caller goes back to the week). `add`: the add-a-step sheet's
    starting values, shown over the block when asked for (editors only)."""
    if booked_id:
        x = next((b for b in v["blocks"] if b.id == booked_id[:20] and b.kind == "booked"), None)
        found = booked.find(v, x.id) if x else None
        return ("step", day_view(v, x.day, booked=(x, found))) if found else None
    if sos and not (block or step):
        if day.isdigit() and int(day) < len(v["dates"]):
            return "step", day_view(v, int(day), sos=True)
        if not day:
            return "step", week_view(v, sos=True)
    if step:
        found = find_step(v, step[:40])
        return ("step", block_view(v, found[1], found)) if found else None
    if block:
        if not has_block(v, block[:8]):
            return None
        opening = add if add is not None and access.can_edit(v["role"]) and v["plan"][block[:8]]["parts"] else None
        if sos and opening is None and not step:
            return "step", block_view(v, block[:8], sos=True)
        return ("step" if opening is not None else "block", block_view(v, block[:8], adding=opening))
    if day:
        return ("day", day_view(v, int(day))) if day.isdigit() and int(day) < len(v["dates"]) else None
    return "week", week_view(v)


def fragment(frag):
    return Response(to_xml(frag), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})


def _guard(session, path="/trip/canvas"):
    return phone.guard(session, path)


def safe_next(url):
    """Only a canvas address may be the way back after a write."""
    if isinstance(url, str) and url.startswith("/trip/canvas") and not url.startswith("//") and len(url) < 200 and "\n" not in url:
        return url
    return curl()


def _json(data, status=200):
    return Response(json.dumps(data, separators=(",", ":")), status_code=status, media_type="application/json", headers={"Cache-Control": "no-store"})


def _script(request):
    return request.headers.get("x-canvas") == "1"


def _field(form, name, cap=80):
    return str(form.get(name) or "")[:cap]


def _minutes(form, name):
    """A start or end the script sent as whole minutes after midnight (None when it sent none)."""
    raw = str(form.get(name) or "").strip()
    if not raw:
        return None
    if not raw.isdigit() or len(raw) > 4:
        raise cal.CalendarError("That time is not one we can read.")
    return int(raw)


def plan_write(session, op, act, form):
    """One write of the day grid -> the JSON the script gets: the toast's words, the snapshot Undo posts back, and the plan as it is now."""
    if op == "delete":
        gone = planedit.delete(session, act)
        more = f" and its {_count(gone['steps'], 'step', 'steps')}" if gone["steps"] else ""
        return {"toast": f"{gone['title']}{more} deleted", "undo": {"deleted": act}}
    if op == "undo":
        try:
            snap = json.loads(_field(form, "undo", 2000) or "null")
        except ValueError:
            snap = None
        if isinstance(snap, dict) and snap.get("added"):
            gone = planedit.unadd(session, snap)
            return {"toast": f"{gone.title} removed"}
        if isinstance(snap, dict) and snap.get("deleted"):
            a = planedit.undelete(session, str(snap["deleted"])[:20])
            return {"toast": f"{a.title} is back", "plan": {"act": a.id, "start": a.start, "end": a.end, "title": a.title}}
        a = planedit.restore(session, snap)
        return {"toast": "Put back", "plan": {"act": a.id, "start": a.start, "end": a.end, "title": a.title}}
    if op == "add":      # F-101: a plan made by touching empty time; the script sends the day, the start and the end in minutes, and the title
        start, end, day = _minutes(form, "start"), _minutes(form, "end"), _field(form, "day", 3)
        if start is None or end is None:
            raise cal.CalendarError("That time is not one we can read.")
        got = planedit.add(session, day=day, start=start, end=end, title=str(form.get("title") or "")[:200], id=_field(form, "id", 8) or None)
        a = got["act"]
        return {"toast": f"{a.title} added", "undo": got["undo"], "plan": {"act": a.id, "start": a.start, "end": a.end, "title": a.title}}
    if op != "edit":
        raise cal.CalendarError("That did not work.")
    title = form.get("title")
    got = planedit.change(session, act, start=_minutes(form, "start"), end=_minutes(form, "end"), title=None if title is None else str(title)[:200])
    a, was = got["act"], got["undo"]
    if not got["changed"]:
        toast = ""
    elif a.title != was["title"]:
        toast = f"Renamed to {a.title}"
    elif a.start != was["start"] and a.end == was["end"]:
        toast = f"{a.title} now starts {cal.fmt_time(a.start)}"      # F-110: the top knob changed the start alone
    elif a.start != was["start"]:
        toast = f"{a.title} moved to {cal.fmt_time(a.start)}"
    else:
        toast = f"{a.title} now ends {cal.fmt_time(a.end)}"
    return {"toast": toast, "undo": got["undo"] if got["changed"] else None, "plan": {"act": a.id, "start": a.start, "end": a.end, "title": a.title}}


def register(app):
    @app.get("/trip/canvas")
    def canvas_page(request, session, day: str = "", block: str = "", step: str = "", frag: str = "", add: str = "", part: str = "", title: str = "", note: str = "", err: str = "", booked: str = "", sos: str = ""):
        if (r := _guard(session)):
            return r
        v = load(session)
        v["ua"] = request.headers.get("user-agent", "")
        v["err"] = err[:20]       # the now card's Directions open Apple Maps on Apple devices
        adding = {"part": part[:40], "title": title[:80], "note": note[:canvas.MAX_NOTE], "err": err[:8]} if add == "1" else None
        got = resolve(v, day[:3], block, step[:40], adding, booked[:20], sos == "1")
        if got is None:
            if frag == "1":
                return Response("not found", status_code=404, media_type="text/plain")   # the script then loads the address as a page, which goes to the week
            return RedirectResponse(curl(), status_code=303)
        level, vw = got
        if frag == "1":
            return fragment(vw)
        edit = access.can_edit(v["role"])
        stage = Div(vw, id="cz", cls="cz-stage", data_trip=ses.open_trip_id(), data_me=session.get("user_id") or "", **({"data_edit": "1"} if edit else {}))
        return phone.shell("today", join_note(), Main(stage, id="main", cls="ph-main cz"), title="The trip", head=HEAD, scripts=SCRIPTS, id="cz-app", data_canvas="1")

    @app.post("/trip/canvas/step")
    async def canvas_step(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        sid = (form.get("step") or "")[:40]
        do = form.get("do") or ""
        nxt = safe_next(form.get("next"))
        try:
            if do in ("done", "undone"):
                canvas.set_done(session, sid, do == "done")
            elif do in ("aside", "back"):
                canvas.set_aside(session, sid, do == "aside")
        except canvas.CanvasError:
            pass       # a step someone else just removed: show where we were
        if _script(request):
            return Response(status_code=204, headers={"X-Canvas-Url": nxt, "Cache-Control": "no-store"})
        return RedirectResponse(nxt, status_code=303)

    @app.post("/trip/canvas/move")
    async def canvas_move(request, session):
        """Drop a step on a part (before another step or at the end), on another day, or in the Set aside tray. The script gets JSON: the level to show, the toast's words
        and the snapshot Undo posts back."""
        if (r := _guard(session)):
            return r
        form = await request.form()
        nxt = safe_next(form.get("next"))
        try:
            r = canvas.move_step(session, _field(form, "step", 40), part=_field(form, "part", 40), before=_field(form, "before", 40), act=_field(form, "act", 20), aside=form.get("aside") == "1")
        except canvas.CanvasError as e:
            return _json({"error": str(e)}, 422) if _script(request) else RedirectResponse(nxt, status_code=303)
        url = curl(block=r["act"]) if r["act"] != r["undo"]["act"] and nxt.startswith("/trip/canvas?block=") else nxt
        if not _script(request):
            return RedirectResponse(url, status_code=303)
        return _json({"url": url, "toast": f"{r['title']} moved to {r['where']}" if r["changed"] else "", "undo": r["undo"] if r["changed"] else None})

    @app.post("/trip/canvas/undo")
    async def canvas_undo(request, session):
        """Put a move back exactly. The snapshot comes from the page, so the model checks every id in it against this trip."""
        if (r := _guard(session)):
            return r
        form = await request.form()
        nxt = safe_next(form.get("next"))
        try:
            raw = _field(form, "undo", 30000)
            canvas.restore(session, json.loads(raw) if raw else None)
        except (canvas.CanvasError, ValueError):
            return _json({"error": "There is nothing to undo."}, 422) if _script(request) else RedirectResponse(nxt, status_code=303)
        return _json({"url": nxt, "toast": "Moved back"}) if _script(request) else RedirectResponse(nxt, status_code=303)

    @app.post("/trip/canvas/plan")
    async def canvas_plan(request, session):
        """The day grid's writes (F-097, F-098): `op` is edit (any of start, end as minutes, title), undo (the snapshot an edit returned) or delete. The script gets
        JSON {toast, undo, plan}; a refusal is 422 {error} in the calendar's own words. Editors only, by gitaway.access."""
        if (r := _guard(session)):
            return r
        form = await request.form()
        op, act, nxt = _field(form, "op", 8), _field(form, "act", 20), safe_next(form.get("next"))
        try:
            got = plan_write(session, op, act, form)
        except cal.CalendarError as e:
            return _json({"error": str(e)}, 422) if _script(request) else RedirectResponse(nxt, status_code=303)
        return _json(got) if _script(request) else RedirectResponse(nxt, status_code=303)

    @app.post("/trip/canvas/add")
    async def canvas_add(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        act, nxt = _field(form, "act", 20), safe_next(form.get("next"))
        picked = [str(x)[:60] for x in form.getlist("who")[:12]]
        who = [] if "all" in picked else picked
        try:
            canvas.add_step(session, act, _field(form, "part", 40), _field(form, "title", 200), _field(form, "time", 10), who, _field(form, "note", 400))
        except canvas.CanvasError as e:
            msg = str(e)
            if _script(request):
                return _json({"error": msg}, 422)
            code = "title" if "name" in msg else "time" if "time" in msg else "other"
            return RedirectResponse(curl(block=act, add=True, part=_field(form, "part", 40), title=_field(form, "title"), note=_field(form, "note", canvas.MAX_NOTE), err=code), status_code=303)
        title = " ".join(_field(form, "title", 200).split())[:80]
        return _json({"url": nxt, "toast": f"{title} added"}) if _script(request) else RedirectResponse(nxt, status_code=303)

    @app.post("/trip/canvas/note")
    async def canvas_note(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        nxt = safe_next(form.get("next"))
        try:
            canvas.set_note(session, _field(form, "step", 40), _field(form, "note", 400))
        except canvas.CanvasError:
            pass
        if _script(request):
            return Response(status_code=204, headers={"X-Canvas-Url": nxt, "Cache-Control": "no-store"})
        return RedirectResponse(nxt, status_code=303)
