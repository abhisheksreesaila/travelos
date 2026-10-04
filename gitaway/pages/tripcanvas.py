"""The trip canvas (F-081): the whole trip as one surface that zooms. Week, then a day, then a block (a park day with its parts and steps), then one step.

GET  /trip/canvas                 the week: every day as a row, park days showing their parts, free days with a +
GET  /trip/canvas?day=N           one day: its blocks in time order, a park block with its parts and steps as chips, the day's Set aside tray
GET  /trip/canvas?block=a3        one block: parts as sections, steps in time order, lanes when people split up
GET  /trip/canvas?step=<id>       one step, as a bottom sheet over its block: note, who is going, Mark done, Set aside / Put back
POST /trip/canvas/step            Mark done, Not done, Set aside, Put back (the writes are F-080's gitaway.canvas; editors only, gated by gitaway.access)

Every level is drawn by the server and has its own address, so it works without script, the back button works, and a link opens a level directly. With
script (assets/js/trip_canvas.js) a tap or a two-finger pinch fetches the next level as a fragment (`?frag=1`, no page around it) and swaps it inside a View
Transition: the element that was tapped (a day row, a block card, a step chip) is the one that grows into the next level's header or sheet, and shrinks back on
zoom out. Where View Transitions are missing it is a short scale and fade; with reduced motion it is an instant swap. A write from the sheet (`X-Canvas: 1`)
answers 204 and `X-Canvas-Url`, the level to zoom out to.

Today (/trip) stays the first tab; its heading carries a "Week view" link here and the canvas has "Today" in its zoom control. On a laptop the same markup is a
wide day view: the week as a strip across the top, the day's parts as lanes, the Set aside tray at the side.
"""

import json
from urllib.parse import urlencode

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, H3, Header, Input, Label, Link, Main, Nav, P, Section, Span, Summary, to_xml
from starlette.responses import RedirectResponse, Response

from gitaway import access, canvas, catalog, members, phone, pickers, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import avatar, join_note, trip_field
from gitaway.pages import calendar as calui
from gitaway.pages.around_ui import around_url
from gitaway.pages.tab_ask import ask_button

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/trip_canvas.css"))   # pickers: the add-a-step sheet has a time field (F-082)
SCRIPTS = ("/assets/js/trip_canvas.js",)
RANK = {"week": 0, "day": 1, "block": 2, "step": 3}
PART_TINTS = ("sky", "sun", "grape", "bubble", "mint")
MAX_FACES = 5


def curl(day=None, block="", step="", add=False, part="", title="", note="", err=""):
    """The address of a level: the week with nothing, else a day, a block or a step. `add` opens the add-a-step sheet over a block (with the part, title and note
    it starts with, and the reason the last try was refused)."""
    q = {"step": step} if step else {"block": block} if block else {"day": day} if day is not None else {}
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
    zone = ses.trip_zone(session)
    ph, n = td.phase(t, catalog.today_in(td.clock_zone(cal.plan_of(b) if cal.is_imported(b) else None, zone)))
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
    v["people"] = canvas.family_people(session)
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


def default_day(v):
    """The day the zoom control's Day goes to: today when it is a trip day, else the first day with a park block, else the first day."""
    if v["today_idx"] is not None:
        return v["today_idx"]
    return next((a.day for a in sorted(v["acts"], key=lambda a: (a.day, a.start)) if a.id in v["plan"]), 0)


# ---- small pieces -----------------------------------------------------------------------------------------------------------

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


def head(v, kicker, title, key="", back=None, back_label="", faces=None):
    """The heading every level starts with. Week: plain. Deeper: a dark card with the way back, which is what the tapped element grows into."""
    inner = [Div(Span(kicker, cls="cz-head-k"), H1(title, id="cz-title", tabindex="-1"), cls="cz-head-text")]
    if back:
        inner.insert(0, A(icon("chev-left", 22, 2.6), href=back, cls="cz-back", aria_label=back_label, data_zoom="out"))
    if faces:
        inner.append(faces)
    return Header(*inner, cls=f"cz-head{' is-deep' if back else ''}", **({"data_zk": key} if key else {}))


def zoom_control(v, current):
    """Today | Week | Day: Today leaves the canvas, Week and Day zoom. Everything is also a plain link."""
    d = default_day(v)
    items = [("Today", "/trip", None, "cz-z-today"), ("Week", curl(), "out" if current == "day" else None, "cz-z-week"), ("Day", curl(day=d), "in" if current == "week" else None, "cz-z-day")]
    links = []
    for name, href, zoom, ident in items:
        here = (name == "Week" and current == "week") or (name == "Day" and current == "day")
        links.append(A(name, href=href, id=ident, cls="cz-seg", aria_current="page" if here else None, **({"data_zoom": zoom} if zoom and not here else {})))
    return Div(Nav(*links, cls="cz-segs", aria_label="Zoom"), Span(icon("expand", 14, 2.4), "Pinch or tap to zoom", cls="cz-pinch-hint"), cls="cz-zoom")


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


def filter_bar(v):
    """Chips that highlight the steps that match and dim the rest: Everyone (no filter), each person, Adults and Kids when used, each named list of the trip."""
    chips = [Button("Everyone", type="button", cls="cz-fchip", data_f="all", aria_pressed="true")]
    for tok, label, p in who_options(v):
        face = "" if p["kind"] == "group" else Span(person_face(p), cls="cz-fchip-face", aria_hidden="true")
        chips.append(Button(face, label, type="button", cls="cz-fchip", data_f=f"who:{tok}", aria_pressed="false", **({"aria_label": f"{label} (not matched to a person)"} if p["kind"] == "initials" else {})))
    for lst in v["lists"]:
        chips.append(Button(icon("shield", 16, 2.4), lst["name"], type="button", cls="cz-fchip cz-fchip-list", data_f=f"list:{lst['id']}", aria_pressed="false"))
    return Div(*chips, cls="cz-filters", role="group", aria_label="Show")


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
    """One day's row in the week."""
    s = v["summaries"][i]
    ents = entries(v, i)
    badge = Span(Span(s.dow, cls="cz-dow"), Span(str(s.num), cls=f"cz-num ink-{s.tint}"), cls=f"cz-badge tp-t-{s.tint}")
    key = f"day-{i}"
    label = f"{v['dates'][i].strftime('%A %b')} {s.num}"
    if not ents:
        add = A(icon("plus", 20, 2.6), href=f"/trip?add=1&day={i}", cls="cz-plus", aria_label=f"Add something to {label}") if editor else ""
        return Div(badge, A(Span("Free day", cls="cz-free-t"), Span("Nothing planned yet", cls="cz-sub"), href=curl(day=i), cls="cz-row-link cz-free", data_zoom="in", aria_label=f"{label}: free day"), add,
                   cls="cz-row is-free", data_zk=key, data_day=str(i))
    cards = []
    for kind, x in ents[:3]:
        if kind == "block":
            blk = v["plan"][x.id]
            n, done = _counts(blk)
            notes = v["act_notes"].get(x.id) or [(None, st["note"]) for st in _all_steps(blk) if st["note"]][:1]
            note = sticker(notes[0][1], cls="cz-sticker-week") if notes else ""
            cards.append(Div(Div(Span(icon("sight", 18, 2.4), cls="cz-ico"), Span(x.title, cls="cz-card-t"), Span(f"{done}/{n}" if done else _count(n, "step", "steps"), cls="cz-pill"), cls="cz-card-h"),
                             Div(*[_mini_part(p, k) for k, p in enumerate(blk["parts"])], cls="cz-minis"), note, cls="cz-wcard cz-park"))
        else:
            ico = getattr(x, "icon", "") or "pin"
            cards.append(Div(Span(icon(ico, 18, 2.4), cls="cz-ico"), Span(x.title, cls="cz-card-t"), Span(cal.fmt_time(x.start), cls="cz-sub"), cls=f"cz-wcard cz-simple{' is-booked' if kind == 'booked' else ''}"))
    more = Span(f"and {len(ents) - 3} more", cls="cz-sub") if len(ents) > 3 else ""
    return Div(badge, A(*cards, more, href=curl(day=i), cls="cz-row-link", data_zoom="in", aria_label=f"{label}: {s.head}"), cls=f"cz-row{' is-today' if i == v['today_idx'] else ''}", data_zk=key, data_day=str(i))


def week_view(v):
    t = v["t"]
    editor = access.can_edit(v["role"])
    faces = Div(avatar(v["who"], "cz-av"), *[avatar(f, "cz-av") for f in v["crew"]], cls="cz-faces")
    kicker = f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}"
    rows = [week_body(v, i, editor) for i in range(len(v["dates"]))]
    return view("week", [head(v, kicker, "The trip", faces=faces), zoom_control(v, "week"), Div(*rows, cls="cz-week", id="cz-week", style=f"--days:{min(len(rows), 7)}")], title="The trip")


# ---- day --------------------------------------------------------------------------------------------------------------------

def _chip(s, edit, hero=True):
    done = Span(icon("check", 14, 3), cls="cz-tick", aria_hidden="true") if s["done"] else ""
    face = faces_of([s], 3)
    kids = [done, Span(s["title"], cls="cz-chip-t"), Span(s["time"], cls="cz-chip-time") if s["time"] else "", face]
    return Span(A(*kids, Span(" (done)", cls="sr-only") if s["done"] else "", href=curl(step=s["id"]), cls=f"cz-chip{' is-done' if s['done'] else ''}", data_zoom="in", **({"data_zk": f"stp-{s['id']}"} if hero else {})),
                sticker(s["note"], cls="cz-sticker-chip") if s["note"] else "", cls="cz-chipwrap", data_step=s["id"], **step_data(s, edit))


def _tray(steps, edit, ident="cz-tray", open_id=""):
    if not steps:
        return ""
    chips = [A(icon("undo", 14, 2.4), Span(s["title"], cls="cz-chip-t"), href=curl(step=s["id"]), cls="cz-chip cz-chip-aside", data_zoom="in", **({"data_zk": f"stp-{s['id']}"} if s["id"] != open_id else {}), **step_data(s, edit)) for s in steps]
    return Section(Div(H3(icon("tray", 16, 2.4), f"Set aside · {len(steps)}", cls="cz-tray-t"), Span("still in the trip", cls="cz-sub"), cls="cz-tray-h"), Div(*chips, cls="cz-tray-chips"), cls="cz-tray", id=ident, aria_label="Set aside")


def _block_card(v, a):
    edit = access.can_edit(v["role"])
    blk = v["plan"][a.id]
    n, done = _counts(blk)
    notes = [sticker(text, by) for by, text in v["act_notes"].get(a.id, [])]
    parts = []
    for k, p in enumerate(blk["parts"]):
        steps = [Div(_chip(s, edit), cls="cz-chipcell") for s in p["steps"]]
        parts.append(Div(Div(Span(p["name"], cls="cz-part-t"), Span(p["time_of_day"], cls="cz-when") if p["time_of_day"] else "", Span(_count(len(p["steps"]), "ride", "rides"), cls="cz-part-n"), cls="cz-part-h"),
                          Div(*steps, cls="cz-chips") if steps else P("Nothing here yet.", cls="cz-sub"), cls=f"cz-part cz-pt-{PART_TINTS[k % 5]}", data_part=p["id"], data_act=a.id))
    return Div(A(Span(icon("sight", 22, 2.4), cls="cz-ico"), Div(Span(a.title, cls="cz-card-t"), Span(f"{cal.fmt_time(a.start)} – {cal.fmt_time(a.end)} · {done} of {n} done", cls="cz-sub"), cls="cz-card-text"),
                 Span(icon("chev-right", 20, 2.6), cls="cz-go"), href=curl(block=a.id), cls="cz-block-head", data_zoom="in", data_zk=f"blk-{a.id}"),
               Div(*notes, cls="cz-notes") if notes else "", Div(*parts, cls="cz-parts"), cls="cz-block", data_act=a.id)


def _simple(kind, x, v):
    ico = getattr(x, "icon", "") or ("pin" if kind == "plan" else "pin")
    notes = [sticker(text, by) for by, text in v["act_notes"].get(x.id, [])] if kind == "plan" else []
    return Div(Div(Span(icon(ico, 20, 2.4), cls="cz-ico"), Div(Span(x.title, cls="cz-card-t"), Span(f"{cal.fmt_time(x.start)}" + (f" – {cal.fmt_time(x.end)}" if x.end else ""), cls="cz-sub"), cls="cz-card-text"), cls="cz-simple-h"),
               Div(*notes, cls="cz-notes") if notes else "", cls=f"cz-block cz-plain{' is-booked' if kind == 'booked' else ''}")


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


def day_view(v, day):
    editor = access.can_edit(v["role"])
    d = v["dates"][day]
    ents = entries(v, day)
    cards = [(_block_card(v, x) if kind == "block" else _simple(kind, x, v)) for kind, x in ents]
    aside = [s for kind, x in ents if kind == "block" for s in v["plan"][x.id]["aside"]]
    if not cards:
        cards = [Div(Span("a free day", cls="cz-hand"), A("Add something fun", href=f"/trip?add=1&day={day}", cls="tp-btn tp-btn-ink") if editor else Span("Nothing planned yet.", cls="cz-sub"), cls="cz-empty", id="cz-empty")]
    kicker = f"{d.strftime('%a %b').upper()} {d.day} · DAY {day + 1} OF {len(v['dates'])}"
    first = next((x for kind, x in ents if kind == "block"), None)
    body = [head(v, kicker, d.strftime("%A"), key=f"day-{day}", back=curl(), back_label="Zoom out to the week"), zoom_control(v, "day"), ask_button(day, ident=f"ak-open-day-{day}") if editor else "", strip(v, day),
            *([filter_bar(v)] if first else []), *([dropbars(v)] if first and editor else []),
            Div(Div(*cards, *(listmore(v, first) if first else []), cls="cz-day-main"), Div(_tray(aside, editor), cls="cz-day-side"), cls="cz-day-body")]
    return view("day", body, zout=f"day-{day}", title=day_title(v, day), data_day=str(day))


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


def block_view(v, act_id, open_step=None, adding=None):
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
        sections.append(Section(Div(H2(p["name"]), Span(p["time_of_day"], cls="cz-when") if p["time_of_day"] else "", Span(f"{pd} of {pn} done" if pn else "", cls="cz-part-n"), ideas, cls="cz-part-h"),
                                *(items or [P("Nothing here yet.", cls="cz-sub")]), cls=f"cz-bpart cz-pt-{PART_TINTS[k % 5]}", data_part=p["id"], data_act=a.id))
    lists = [Section(Div(H3(lst["name"]), Span(f"for {lst['for']}", cls="cz-when") if lst["for"] else "", cls="cz-part-h"),
                     Div(*[Span(i["title"], cls="cz-list-i") for i in lst["items"]], cls="cz-list"), cls="cz-bpart cz-triplist", data_list=lst["id"]) for lst in v["lists"]]
    legend = Div(Span(icon("users", 14, 2.4), "Lanes: people who split up at the same time", cls="cz-sub"), cls="cz-legend") if lanes_used else ""
    add_btn = ""
    if editor and blk["parts"]:
        add_btn = A(icon("plus", 18, 2.6), "Add a step", href=curl(block=a.id, add=True), id="cz-add", cls="tp-btn tp-btn-ink cz-add", data_zoom="in", **({} if adding else {"data_zk": "stp-new"}))
    kicker = f"{d.strftime('%a %b').upper()} {d.day} · {cal.fmt_time(a.start)} – {cal.fmt_time(a.end)}"
    body = [head(v, kicker, a.title, key=f"blk-{a.id}", back=curl(day=a.day), back_label="Zoom out to the day", faces=faces_of(allsteps, 4)),
            ask_button(a.day, ident=f"ak-open-blk-{a.id}") if editor else "", Div(*notes, cls="cz-notes") if notes else "", Div(Span(f"{done} of {n} done", cls="cz-prog"), legend, add_btn, cls="cz-block-meta"),
            filter_bar(v), *([dropbars(v)] if editor else []),
            Div(*sections, cls="cz-bparts"), *listmore(v, a), Div(_tray(blk["aside"], editor, open_id=open_id), cls="cz-block-side"), *lists]
    if open_step:
        body.append(sheet(v, open_step, a))
    elif adding is not None:
        body.append(add_sheet(v, a, adding))
    return view("step" if open_step or adding is not None else "block", body, zout=f"stp-{open_id}" if open_step else "stp-new" if adding is not None else f"blk-{a.id}", title=a.title, data_day=str(a.day), data_block=a.id)


# ---- step -------------------------------------------------------------------------------------------------------------------

def _post_form(action, fields, *content, cls="cz-act-form", **attrs):
    """A form that posts to the canvas: hidden fields, the trip this page was drawn for, then its fields and button."""
    return Form(*[_hidden(k, val) for k, val in fields.items()], trip_field(), *content, action=action, method="post", data_cz_form="", cls=cls, **attrs)


def move_menu(v, s, act_id, part_id, close):
    """The same targets as dragging, as buttons (for a keyboard or a screen reader): earlier or later in its part, each other part of the block, each other day with a plan."""
    blk = v["plan"][act_id]
    items = []

    def go(label, ico, **fields):
        items.append(_post_form("/trip/canvas/move", {"step": s["id"], "next": close, **fields}, Button(icon(ico, 18, 2.4), label, type="submit", cls="tp-btn tp-btn-white cz-move-btn"), cls="cz-move-form"))

    here = next((p for p in blk["parts"] if p["id"] == part_id), None)
    if here and not s["aside"]:
        order = [x["id"] for x in here["steps"]]
        i = order.index(s["id"])
        if i > 0:
            go(f"Earlier in {here['name']}", "chev-left", part=here["id"], before=order[i - 1])
        if i < len(order) - 1:
            go(f"Later in {here['name']}", "chev-right", part=here["id"], before=order[i + 2] if i + 2 < len(order) else "")
    for p in blk["parts"]:
        if p["id"] != part_id or s["aside"]:
            go(f"{'Put into' if s['aside'] else 'To'} {p['name']}", "arrow-right", part=p["id"])
    for other_id, other in v["plan"].items():
        o = v["by_id"].get(other_id)
        if o and other_id != act_id and other["parts"]:
            go(f"To {v['dates'][o.day].strftime('%A')}, {o.title}", "calendar", act=other_id)
    return Details(Summary(icon("grip", 18, 2.4), "Move", cls="cz-move-sum"), Div(*items, cls="cz-move-items"), cls="cz-move", id="cz-move") if items else ""


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
        side = post("back", "Put back", "tp-btn tp-btn-white cz-act", "undo") if s["aside"] else post("aside", "Set aside", "tp-btn tp-btn-white cz-act", "tray")
        buttons = Div(main, side, cls="cz-acts")
        sheet_url = curl(step=s["id"])
        note_form = _post_form("/trip/canvas/note", {"step": s["id"], "next": sheet_url},
                               Input(type="text", name="note", value=s["note"], maxlength=str(canvas.MAX_NOTE), placeholder="Say it in a few words", aria_label="Note", cls="cz-note-in"),
                               Button("Save note", type="submit", cls="tp-btn tp-btn-ink cz-save"), cls="cz-note-form", data_cz_stay="")
        more = Div(Details(Summary(icon("pencil", 18, 2.4), "Edit the note" if s["note"] else "Add a note, a fun one", cls="cz-note-sum"), note_form, cls="cz-notebox", id="cz-notebox"),
                   move_menu(v, s, act_id, s["part"], close), cls="cz-more")
    else:
        buttons = P("You can look at this step but not change it.", cls="cz-sub cz-viewer", id="cz-viewer")
    return Div(A(href=close, cls="cz-scrim", aria_label="Close", tabindex="-1", data_zoom="out"),
               Div(Div(cls="cz-grab", aria_hidden="true"),
                   Div(Div(*[Span(x, cls="cz-pill") for x in (part, where) if x], cls="cz-pills"), A(icon("x", 20, 2.6), href=close, cls="cz-close", aria_label="Close", data_zoom="out"), cls="cz-sheet-top"),
                   H2(s["title"], id="cz-sheet-title", tabindex="-1"), Span(state, cls="cz-state", id="cz-state") if state else "",
                   sticker(s["note"], "Note", cls="cz-sticker-sheet") if s["note"] else "",
                   Div(Span("Who's going", cls="cz-label"), who), buttons, more,
                   cls="cz-sheet", role="dialog", aria_modal="true", aria_labelledby="cz-sheet-title", data_zk=f"stp-{s['id']}", data_step=s["id"]), cls="cz-sheet-wrap")


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

def resolve(v, day="", block="", step="", add=None):
    """(level, the view) for the address, or None when it names something that is not there (the caller goes back to the week). `add`: the add-a-step sheet's
    starting values, shown over the block when asked for (editors only)."""
    if step:
        found = find_step(v, step[:40])
        return ("step", block_view(v, found[1], found)) if found else None
    if block:
        if not has_block(v, block[:8]):
            return None
        opening = add if add is not None and access.can_edit(v["role"]) and v["plan"][block[:8]]["parts"] else None
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


def register(app):
    @app.get("/trip/canvas")
    def canvas_page(request, session, day: str = "", block: str = "", step: str = "", frag: str = "", add: str = "", part: str = "", title: str = "", note: str = "", err: str = ""):
        if (r := _guard(session)):
            return r
        v = load(session)
        adding = {"part": part[:40], "title": title[:80], "note": note[:canvas.MAX_NOTE], "err": err[:8]} if add == "1" else None
        got = resolve(v, day[:3], block, step[:40], adding)
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
