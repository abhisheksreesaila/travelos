"""The desktop week on one time axis (F-145, F-162; frame ct-week-desk of docs/design/colour-timeline/restrained, docs/design/colour-timeline.md, docs/trip-canvas.md "The desktop week").

`columns(v, editor)` draws the whole trip as one column per day on ONE shared hour axis (`<div id="cz-wk">`; CSS shows it from 1020px up and hides the phone's rows `#cz-week` there; below that nothing
changes). The axis (`.cz-wax`) is the first column and holds the hour labels; every plan and booking is a white card at its start and as tall as it lasts, coloured by its kind only (the tile and the 3px
edge, the same classes and look as the day, F-159). A day's header is neutral (weekday, date, the day's title, a grey Day N pill, "Today" in ink) and is the link that opens the day; an empty day is a soft
dashed Free day slot with Say the plan (editors only). Items that overlap in time sit side by side in lanes. A plan's card opens its day with the plan selected (`?day=N&plan=<id>`); a booking's opens its
sheet. Every link is the existing liquid zoom (`data-zoom="in"`). Nothing here is invented: a summary shows only the steps and messages the plan has.

The axis is the same for every day, 7 AM to 10 PM unless an item is earlier or later, so the same time is the same height in every column. The card's top and height are percentages of the axis
(`--s`, `--l` over `--span` minutes), so the hour height is whatever makes the whole axis fit the window. A plan or booking under WEEK_MIN minutes is drawn WEEK_MIN tall: a line of text needs that much.
"""
from types import SimpleNamespace

from fasthtml.common import A, Div, Span

from gitaway import tripcal as cal
from gitaway.icons import icon

WEEK_MIN = 30      # minutes of axis a card takes at least (a 15 minute plan is drawn 30 tall, its top is still its start)
SHORT, TIGHT = 60, 90      # a card under SHORT minutes is one row (title and start); under TIGHT it is the title and the time, a tile; from TIGHT it also carries the PLAN / BOOKED pill and the summary


def summary(v, blk, x):
    """"3 steps · 1 done · 2 messages", only the parts that are true."""
    from gitaway.pages import tripcanvas as tc
    bits = []
    if blk is not None:
        n, done = tc._counts(blk)
        if n:
            bits.append(tc._count(n, "step", "steps") + (f" · {done} done" if done else ""))
    msgs = sum(c["n"] for k, c in v["talk"].items() if k[0] == x.id)
    if msgs:
        bits.append(tc._count(msgs, "message", "messages"))
    return " · ".join(bits)


def _drawn(x, hi):
    """(start, end) of the card on the axis: at least WEEK_MIN minutes tall (a line of text needs that), never past the axis's end. A short plan at the very end of the axis moves its top up to keep
    the floor (its label still says its true time); a drawn-only length never widens the axis."""
    s = min(x.start, hi - WEEK_MIN)
    return s, min(max(x.end, s + WEEK_MIN), hi)


def axis_range(v, days=None):
    """(first, last) minute of the shared axis: 7 AM to 10 PM, wider for an earlier or later item in any day (or in `days` only: the phone's day card, F-163), on whole hours."""
    from gitaway.pages import tripcanvas as tc
    items = [x for i in (range(len(v["dates"])) if days is None else days) for _, x in tc.entries(v, i)]
    lo = min([cal.DEFAULT_START, *(x.start for x in items)]) // 60 * 60
    hi = max([cal.GRID_END, *(x.end for x in items)])      # the true ends: the 30 minute floor of a short card is drawn inside this, it never makes the axis longer
    return lo, min(-(-hi // 60) * 60, 24 * 60)


def _row(v, i, kind, x, lo, hi, lane, lanes):
    from gitaway.pages import tripcanvas as tc
    title = v["dates"][i].strftime("%A")
    attrs = tc.kind_attrs(v, kind, x)
    s, e = _drawn(x, hi)
    mins = e - s
    size = ("is-short" if mins < SHORT else "is-tight" if mins < TIGHT else "is-tall") + (" is-lane" if lanes > 1 else "")      # is-lane: side by side with another card, so half a column wide: the start time only, no tile
    brief = mins < SHORT or lanes > 1      # the start time alone
    pos = f"--s:{s - lo};--l:{mins};--lane:{lane};--lanes:{lanes}"
    if kind == "booked":
        at = x.label_start if getattr(x, "label_start", None) is not None else x.start
        full = tc.span_label(x.start, x.end) if getattr(x, "label_start", None) is None else cal.fmt_time(at)
        when = tc.compact_time(at) if brief else full
        name = " · ".join(x.title.split(" · ")[:2])
        return A(Span(icon(getattr(x, "icon", "") or "pin", 18, 2.4), cls="cz-wi-ico", aria_hidden="true"),
                 Span(Span(name, cls="cz-wi-t"), Span(when, cls="cz-wi-time"), Span("Booked", cls="cz-wi-tag"), cls="cz-wi-body"),
                 href=tc.curl(day=i, booked=x.id), cls=f"cz-wi is-booked {size} {tc.booking_class(x)}", data_zoom="in", data_title=title, title=x.title, style=pos, data_s=str(x.start), data_e=str(x.end),
                 aria_label=f"{x.title}, {cal.fmt_time(at)}, booked: details", **attrs)
    k = x.kind if x.kind in tc.KIND_TINT else "fun"
    blk = v["plan"].get(x.id) if kind == "block" else None
    full = tc.span_label(x.start, x.end)
    when = tc.compact_time(x.start) if brief else full
    text = summary(v, blk, x)
    return A(Span(icon(tc.KIND_ICON[k], 18, 2.2), cls="cz-wi-ico", aria_hidden="true"),
             Span(Span(x.title, cls="cz-wi-t"), Span(when, cls="cz-wi-time"), Span("Plan", cls="cz-wi-tag"), Span(text, cls="cz-wi-s") if text else "", cls="cz-wi-body"),
             href=tc.curl(day=i, plan=x.id), cls=f"cz-wi is-plan {size} cz-k-{k}", data_zoom="in", data_title=title, style=pos, data_s=str(x.start), data_e=str(x.end),
             aria_label=f"{x.title}, {full}" + (f", {text}" if text else "") + ": open the day", data_wk_act=x.id, **attrs)      # (F-157: the mouse lifts a plan card by this id; a booking has none)


def _column(v, i, editor, lo, hi):
    from gitaway.pages import tripcanvas as tc
    s = v["summaries"][i]
    ents = tc.entries(v, i)
    today = i == v["today_idx"]
    label = f"{v['dates'][i].strftime('%A %b')} {s.num}"
    pill = Span("Today", cls="cz-wh-today") if today else Span(f"Day {i + 1}", cls="cz-wh-no")
    head = A(Div(Span(f"{s.dow.title()} {s.num}", cls="cz-wh-day"), pill, cls="cz-wh-key"), Span(s.head.replace(" · ", ", "), cls="cz-wh-head"),
             href=tc.curl(day=i), cls="cz-wh cz-wopen", data_zoom="in", data_title=v["dates"][i].strftime("%A"), aria_label=f"Open the day: {label}, {s.head}")
    if ents:
        lanes = _lanes(ents, hi)
        body = Div(*[_row(v, i, kind, x, lo, hi, *lanes[f"{kind}:{x.id}"]) for kind, x in ents], Span("", cls="cz-wnone"), cls="cz-wlist")
    else:
        say = A(icon("mic", 18, 2.4), "Say the plan", href=f"/trip/ask?day={i}&mode=talk", cls="cz-desk-btn is-coral cz-wsay", id=f"cz-wsay-{i}") if editor else ""
        body = Div(Div(Span("Free day", cls="cz-wfree-t"), Span("Nothing planned yet", cls="cz-wfree-s"), say, cls="cz-wfree"), cls="cz-wlist")
    return Div(head, body, cls=f"cz-wcol{' is-today' if today else ''}", data_zk=f"day-{i}", data_day=str(i), role="group", aria_label=f"{label}: {s.head}" + (", today" if today else ""))


def _lanes(ents, hi):
    """{kind:id: (lane, lanes)}: the day's cards side by side where they overlap on the axis (drawn heights, so a 15 minute plan's 30 minutes count)."""
    from gitaway.pages import dayshared as calui
    items = [SimpleNamespace(id=f"{kind}:{x.id}", start=_drawn(x, hi)[0], end=_drawn(x, hi)[1]) for kind, x in ents]
    return calui.lanes(items)


def _axis(lo, hi):
    from gitaway.pages import tripcanvas as tc
    labels = [Span(tc.hour_label(h % 24), cls="cz-wax-h", style=f"--s:{h * 60 - lo}", data_h=str(h * 60)) for h in range(lo // 60, hi // 60 + 1)]
    return Div(Div(cls="cz-wax-top"), Div(*labels, cls="cz-wlist"), cls="cz-wax", aria_hidden="true")


def columns(v, editor):
    n = len(v["dates"])
    lo, hi = axis_range(v)
    return Div(_axis(lo, hi), *[_column(v, i, editor, lo, hi) for i in range(n)], id="cz-wk", cls=f"cz-wk{' is-long' if n > 5 else ''}", style=f"--days:{n};--span:{hi - lo};--hours:{(hi - lo) / 60:g}")
