"""The captain's page (F-185): reports, creators, published trips, clicks, and what GitAway earns.

GET  /admin                a summary, the reports, every creator with their trips (take down / restore), and the commission figures (moved here from /partners)
POST /admin/takedown       hide a published trip and its public photos
POST /admin/restore        bring it back

Who is an admin: the sign-in emails listed in GITAWAY_ADMIN_EMAILS (comma or space separated, any case), never one written in code. For everyone else, signed in or
not, every address here answers 404 as if there were no such page. Both POSTs also check the request came from our own page (reports.same_site), on top of the
SameSite=Lax session cookie. They change no family plan, so gitaway/access.py lists them as open to every role: the check is here.
"""

import os
import re

from fasthtml.common import A, Button, Div, Form, H1, H2, Input, Li, Link, Main, P, Section, Span, Ul
from starlette.responses import RedirectResponse

from gitaway import affiliate, catalog, community, partners, planforme as pfm, reports, session as ses, showcase, stats
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import creatorclaim as claims
from gitaway.partners import log

GOAL = 150
HEAD = (Link(rel="stylesheet", href="/assets/css/admin.css"), *claims.HEAD)


def admin_emails() -> set:
    return {e.lower() for e in re.split(r"[,\s;]+", os.getenv("GITAWAY_ADMIN_EMAILS", "")) if e}


def is_admin(session) -> bool:
    email = str((session or {}).get("email") or "").strip().lower()
    return bool(email) and email in admin_emails() and (session or {}).get("verified") == 1   # a Google address Google has not verified is not proof of who you are (members.after_sign_in sets the flag)


def commission_summary(rows) -> list:
    """[(partner name, clicks, booked, estimated commission cents)] for every partner that has a click, plus the totals row's numbers via sum()."""
    out = []
    for p in partners.PARTNERS:
        mine = [r for r in rows if r["partner"] == p.key]
        if mine:
            booked = [r for r in mine if r["state"] == "booked"]
            out.append((p.name, len(mine), len(booked), sum(r["commission_cents"] for r in booked)))
    return out


def _button(action, slug, label, cls):
    return Form(Input(type="hidden", name="slug", value=slug), Button(label, type="submit", cls=f"btn btn-sm {cls}"), action=f"/admin/{action}", method="post", cls="ad-inline")


def _trip_row(row):
    down = community.is_down(row["slug"])
    return Li(Div(A(row["title"], href=f"/trips/{row['slug']}", cls="ad-link"), Span("Taken down" if down else "Live", cls="ad-state " + ("is-down" if down else "is-live"), id=f"state-{row['slug']}")),
              _button("restore", row["slug"], "Restore", "") if down else _button("takedown", row["slug"], "Take down", "ad-danger"), cls="ad-trip", id=row["slug"])


def _creator(c, trips, clicks):
    marker = affiliate.marker_of(c["owner_user"])
    all_, own = clicks.get(c["handle"], (0, 0))
    return Li(Div(A(c["name"], href=f"/creators/{c['handle']}", cls="ad-link ad-name"),
                  Span(f"marker {marker}" if marker else "no marker: GitAway's", cls="ad-chip"),
                  Span(f"{(n := stats.readers_all_time(t['slug'] for t in trips))} reader{'s' if n != 1 else ''} · {all_} click{'s' if all_ != 1 else ''} from their trips, {own} with their marker · bookings: not reported yet", cls="ad-meta")),
              Ul(*[_trip_row(t) for t in trips], cls="ad-trips") if trips else P("No trips.", cls="ad-meta"), cls="ad-creator", id=f"c-{c['handle']}")


def _report(r):
    trip = community.get(r["target"], hidden=True) if r["kind"] == "trip" else None
    name = trip["title"] if trip else r["target"]
    href = f"/trips/{r['target']}" if r["kind"] == "trip" else f"/creators/{r['target']}"
    return Li(Div(Span(reports.REASONS.get(r["reason"], r["reason"]), cls="ad-reason"), Span(r["created_at"][:16].replace("T", " "), cls="ad-meta")),
              P(A(name, href=href, cls="ad-link"), f" ({'trip' if r['kind'] == 'trip' else 'creator'})", cls="ad-meta"),
              P(r["note"], cls="ad-note") if r["note"] else "", P(f"Reply to: {r['email']}", cls="ad-meta") if r["email"] else "",
              (_button("restore", r["target"], "Restore", "") if community.is_down(r["target"]) else _button("takedown", r["target"], "Take down", "ad-danger")) if trip else "",
              cls="ad-report", id=f"report-{r['id']}")


STATUS_WORDS = {"awaiting_payment": "Waiting for payment", "paid": "Paid", "building": "Building", "ready": "Ready", "failed": "Failed"}


def _dollars(micros) -> str:
    return f"${micros / 1_000_000:.3f}"


def _order(o):
    """One Plan it for me order (F-193): who, where, status, what it brought in and what the agent cost; a failed one that was paid is a refund due."""
    owed = o["status"] == "failed" and o["paid_at"]
    i = o["intake"]
    return Li(Div(Span(f"#{o['id'][:8]}", cls="ad-name"), Span(STATUS_WORDS[o["status"]], cls="ad-state " + ("is-down" if o["status"] == "failed" else "is-live" if o["status"] == "ready" else "")),
                  Span("Refund due", cls="ad-state is-down", id=f"refund-{o['id'][:8]}") if owed else "", Span(o["email"], cls="ad-meta")),
              P(f"{i['where']} · {i['start']} to {i['end']} · {i['adults']} adults, {len(i['kids'])} kids", cls="ad-meta"),
              P(f"{catalog.money(o['amount_cents'])} · agent {_dollars(o['ai_cost_micros'])} · {o['ai_tokens_in']:,} in, {o['ai_tokens_out']:,} out" + (f" · {o['ai_model']}" if o["ai_model"] else "")
                + (f" · {o['error']}" if o["error"] else ""), cls="ad-meta"),
              cls="ad-report", id=f"pfm-{o['id'][:8]}")


def admin_page(drafted=()):
    people = community.real_creators()
    every = community.creators_all()
    clicks = affiliate.clicks_by_creator()
    live = sum(len(c["trips"]) for c in people)
    sheet, skipped = log.all_clicks()
    summary = commission_summary(sheet)
    total = sum(s[3] for s in summary)
    rep = reports.all_reports()
    orders = pfm.admin_rows()
    pt = pfm.totals(orders)
    cards = (("Creators", f"{len(people)} of {GOAL}", "ad-goal"), ("Live trips", str(live), "ad-live"), ("Reports", str(len(rep)), "ad-reports"), ("Estimated commission", catalog.money(total), "ad-commission"),
             ("Plan it for me", f"{pt['paid']} paid · {catalog.money(pt['revenue_cents'])}", "ad-pfm"), ("Refunds due", f"{pt['refunds']} · {catalog.money(pt['refund_cents'])}", "ad-refunds"),
             ("Agent cost", _dollars(pt["ai_cost_micros"]), "ad-pfm-cost"))
    return page("Admin", Main(
        Div(H1("Admin", cls="ad-title"),
            Div(*[Div(Span(label, cls="ad-k"), Span(value, cls="ad-v", id=i)) for label, value, i in cards], cls="ad-cards"),
            P(f"{skipped} {'family' if skipped == 1 else 'families'} could not be read, so {'its' if skipped == 1 else 'their'} clicks are not in these totals.", role="alert", cls="ad-meta", id="ad-skipped") if skipped else "",
            Div(Span(cls="ad-bar-fill", style=f"width:{min(100, round(100 * len(people) / GOAL))}%"), cls="ad-bar", role="img", aria_label=f"{len(people)} of {GOAL} creators"),
            Section(H2("Plan it for me orders"), P("Refunds are yours, by hand in Stripe: a failed order that was paid says Refund due.", cls="ad-meta"),
                    Ul(*[_order(o) for o in orders], cls="ad-list", id="ad-orders") if orders else P("No orders yet.", cls="ad-meta", id="ad-no-orders"), cls="ad-sec"),
            claims.section(drafted),
            Section(H2("Reports"), Ul(*[_report(r) for r in rep], cls="ad-list", id="ad-report-list") if rep else P("No reports.", cls="ad-meta", id="ad-no-reports"), cls="ad-sec"),
            Section(H2("Creators and trips"),
                    Ul(*[_creator(c, community.rows(kind="scrapbook", owner=c["owner_user"], hidden=True), clicks) for c in every], cls="ad-list", id="ad-creators") if every else P("Nobody has published yet.", cls="ad-meta"),
                    cls="ad-sec"),
            Section(H2("Commission"),
                    P("Estimates from the sandbox and from clicks (flights about 1.1%, stays and cars about 5%); the real figures come with the Travelpayouts statistics, which are not connected yet.", cls="ad-meta"),
                    Ul(*[Li(Span(n, cls="ad-name"), Span(f"{c} click{'s' if c != 1 else ''} · {b} booked · {catalog.money(cents)}", cls="ad-meta")) for n, c, b, cents in summary], cls="ad-list", id="ad-partners") if summary
                    else P("No partner clicks yet.", cls="ad-meta"), cls="ad-sec"),
            cls="ad-card"), id="admin", cls="ad-stage"), head=HEAD)


def register(app):
    @app.get("/admin")
    def admin(session):
        return admin_page() if is_admin(session) else showcase.not_found()

    def _act(name, fn):
        async def handler(request, session):
            if not is_admin(session):
                return showcase.not_found()
            if not reports.same_site(request):
                return showcase.not_found()
            slug = str((await request.form()).get("slug") or "")
            return RedirectResponse(f"/admin#{slug}" if fn(slug) else "/admin", status_code=303)   # only a slug that exists goes into the address
        handler.__name__ = f"admin_{name}"
        app.post(f"/admin/{name}")(handler)

    _act("takedown", community.take_down)
    _act("restore", community.restore)
