"""The desktop week (F-145, frame A4 of docs/design/canvas/Web-Trip-v1.html; docs/trip-canvas.md "The desktop week").

`columns(v, editor)` draws the whole trip as one column per day (`<div id="cz-wk">`, CSS shows it from 1020px up and hides the phone's rows `#cz-week` there; below that nothing changes):
a day-colour header, compact rows (time, a title that wraps and is never cut, a kind icon), a plan's step and message summary under its title, a dashed Free day card with Say the plan
(editors only) and Open the day at the foot. A plan's row opens its day with the plan selected (`?day=N&plan=<id>`, F-141 reads `plan`); a booking's row opens its sheet; Open the day and the
column header's day open the day. Every link is the existing liquid zoom (`data-zoom="in"`). Nothing here is invented: a summary shows only the steps and messages the plan has.
"""
from fasthtml.common import A, Div, Span

from gitaway import share, tripcal as cal
from gitaway.icons import icon


def _summary(v, blk, x):
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


def _row(v, i, kind, x):
    from gitaway.pages import tripcanvas as tc
    title = v["dates"][i].strftime("%A")
    attrs = tc.kind_attrs(v, kind, x)
    if kind == "booked":
        when = tc.compact_time(x.label_start if getattr(x, "label_start", None) is not None else x.start)
        return A(Span(when, cls="cz-wi-time"), Span(Span(" · ".join(x.title.split(" · ")[:2]), cls="cz-wi-t"), cls="cz-wi-body"), Span(icon(getattr(x, "icon", "") or "pin", 18, 2.4), cls="cz-wi-ico", aria_hidden="true"),
                 href=tc.curl(day=i, booked=x.id), cls="cz-wi is-booked", data_zoom="in", data_title=title, title=x.title, aria_label=f"{x.title}, {when}: details", **attrs)
    blk = v["plan"].get(x.id) if kind == "block" else None
    ico = "sight" if kind == "block" else share.KIND_ICON.get(x.kind, "star")
    when = tc.compact_time(x.start)
    summary = _summary(v, blk, x)
    return A(Span(when, cls="cz-wi-time"), Span(Span(x.title, cls="cz-wi-t"), Span(summary, cls="cz-wi-s") if summary else "", cls="cz-wi-body"), Span(icon(ico, 18, 2.4), cls="cz-wi-ico", aria_hidden="true"),
             href=tc.curl(day=i, plan=x.id), cls="cz-wi is-plan", data_zoom="in", data_title=title, aria_label=f"{x.title}, {when}" + (f", {summary}" if summary else "") + ": open the day", **attrs)


def _column(v, i, editor):
    from gitaway.pages import tripcanvas as tc
    s = v["summaries"][i]
    ents = tc.entries(v, i)
    today = i == v["today_idx"]
    label = f"{v['dates'][i].strftime('%A %b')} {s.num}"
    head = Div(Span(s.dow, cls="cz-wh-dow"), Span(str(s.num), cls="cz-wh-num"), Span("Today", cls="cz-wh-today") if today else "", Span(s.head, cls="cz-wh-head"), cls="cz-wh")
    if ents:
        body = Div(*[_row(v, i, kind, x) for kind, x in ents], Span("", cls="cz-wnone"), cls="cz-wlist")
    else:
        say = A(icon("mic", 18, 2.4), "Say the plan", href=f"/trip/ask?day={i}&mode=talk", cls="cz-desk-btn is-coral cz-wsay", id=f"cz-wsay-{i}") if editor else ""
        body = Div(Div(Span("Free day", cls="cz-wfree-t"), Span("Nothing planned yet", cls="cz-wfree-s"), say, cls="cz-wfree"), cls="cz-wlist")
    foot = A("Open the day", icon("chev-right", 16, 2.6), href=tc.curl(day=i), cls="cz-wopen", data_zoom="in", data_title=v["dates"][i].strftime("%A"), aria_label=f"Open the day: {label}")
    return Div(head, body, Div(foot, cls="cz-wft"), cls=f"cz-wcol cz-wt-{s.tint}{' is-today' if today else ''}", data_zk=f"day-{i}", data_day=str(i), role="group", aria_label=f"{label}: {s.head}" + (", today" if today else ""))


def columns(v, editor):
    n = len(v["dates"])
    return Div(*[_column(v, i, editor) for i in range(n)], id="cz-wk", cls=f"cz-wk{' is-long' if n > 5 else ''}", style=f"--days:{n}")
