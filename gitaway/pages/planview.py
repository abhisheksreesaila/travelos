"""A Plan it for me plan, read-only (F-197): the days the family gets, drawn like the delivered trip's phone week (one white card per day, a mini hour bar, a row per plan in its
kind's colour, gitaway/pages/tripcanvas.py KIND_TINT and KIND_ICON), its summary and tips, and "What to book and when". The example plans (/plan-for-me/example/<slug>) and the
captain's founder check (/admin/plan-for-me/<order>) draw with it. A plan is `planforme.validate()`'s shape: {"title", "summary", "days": [{"stops": [{"start", "end", "title", "kind",
"note"}]}], "tips"}; the intake gives the dates and the party. Styles: assets/css/planforme.css (`.pv-*`)."""

from datetime import date, timedelta

from fasthtml.common import H2, H3, Div, Li, Ol, P, Section, Span, Ul

from gitaway import tripcal
from gitaway.icons import icon
from gitaway.pages.tripcanvas import KIND_ICON, KIND_TINT

BAR = (7 * 60, 22 * 60)      # the mini hour bar, like the week card's: 7 AM to 10 PM


def clock(m) -> str:
    return tripcal.fmt_time(m)


def day_of(intake, d) -> date:
    return date.fromisoformat(intake["start"]) + timedelta(days=d)


def day_label(intake, d) -> str:
    day = day_of(intake, d)
    return f"Day {d + 1} · {day:%a}, {day:%b} {day.day}"


def kid_words(intake) -> list:
    """Each kid as the plan reads them: "3" or "3 (39 in)" when a height was given."""
    heights = intake.get("heights") or []
    return [f"{a}" + (f" ({heights[i]} in)" if i < len(heights) and heights[i] else "") for i, a in enumerate(intake["kids"])]


def party(intake) -> str:
    n = intake["adults"]
    kids = kid_words(intake)
    days = (date.fromisoformat(intake["end"]) - date.fromisoformat(intake["start"])).days + 1
    who = f"{n} adult{'s' if n != 1 else ''}" + (f" · kid{'s' if len(kids) != 1 else ''} {' and '.join([', '.join(kids[:-1]), kids[-1]] if len(kids) > 1 else kids)}" if kids else "")
    return f"{who} · {days} day{'s' if days != 1 else ''}"


def _bar(stops):
    lo, hi = BAR
    span = hi - lo
    return Div(*[Span(cls=f"pv-seg k-{KIND_TINT.get(s['kind'], 'bubble')}", style=f"left:{100 * (max(s['start'], lo) - lo) / span:.2f}%;width:{max(1.0, 100 * (min(s['end'], hi) - max(s['start'], lo)) / span):.2f}%")
                 for s in stops if s["end"] > lo and s["start"] < hi], cls="pv-bar", aria_hidden="true")


def _stop(s):
    tint = KIND_TINT.get(s["kind"], "bubble")
    mins = s["end"] - s["start"]
    length = f"{mins // 60} h {mins % 60} min" if mins >= 60 and mins % 60 else f"{mins // 60} h" if mins >= 60 else f"{mins} min"
    return Li(Span(icon(KIND_ICON.get(s["kind"], "spark"), 18, 2.2), cls="pv-tile"),
              Div(Div(Span(clock(s["start"]), cls="pv-time"), Span(length, cls="pv-len"), cls="pv-when"), P(s["title"], cls="pv-title"), P(s["note"], cls="pv-note") if s["note"] else "", cls="pv-body"),
              cls=f"pv-stop k-{tint}", data_kind=s["kind"])


def days(plan, intake):
    return [Section(Div(H3(f"Day {d + 1}", cls="pv-dn"), Span(f"{day_of(intake, d):%A}, {day_of(intake, d):%B} {day_of(intake, d).day}", cls="pv-date"), cls="pv-dhead"),
                    _bar(day["stops"]), Ol(*[_stop(s) for s in day["stops"]], cls="pv-stops"), cls="pv-day", id=f"pv-day-{d + 1}")
            for d, day in enumerate(plan["days"])]


def tips(plan):
    return Section(H2("Tips for your family"), Ul(*[Li(icon("spark", 16, 2.2), Span(t)) for t in plan["tips"]], cls="pv-tips"), cls="pv-card", id="pv-tips") if plan["tips"] else ""


def checklist(items, intro=""):
    """ "What to book and when": the countdown, soonest first (gitaway/planfacts.py `checklist`)."""
    return Section(H2("What to book and when"), P(intro, cls="pv-hint") if intro else "",
                   Ol(*[Li(Span(it["label"], cls="pv-due" + (" is-now" if it["now"] else "")), Div(P(it["title"], cls="pv-ctitle"), P(it["detail"], cls="pv-cdetail"), cls="pv-body"), cls="pv-check")
                        for it in items], cls="pv-checks"), cls="pv-card", id="pv-book")
