"""The captain's page (F-185): reports, creators, published trips and the orders.

GET  /admin                a summary, the reports, and every creator with their trips (take down / restore)
POST /admin/takedown       hide a published trip and its public photos
POST /admin/restore        bring it back
POST /admin/seen           mark the reports up to an id read (F-196): the "N new" count shows on /admin, in the account menu and in the header until then
GET  /admin/plan-for-me/<order>        a built plan waiting for the founder check (F-197): every stop's title and note, the summary and tips, editable, and "Send to family"
POST /admin/plan-for-me/edit    (order, the fields) keep the quick edit (cleaned like the model's answer: no prices, no opening hours)
POST /admin/plan-for-me/send    (order) write it into the buyer's family: only now does the buyer see it

Who is an admin: the sign-in emails listed in GITAWAY_ADMIN_EMAILS (comma or space separated, any case), never one written in code. For everyone else, signed in or
not, every address here answers 404 as if there were no such page. Both POSTs also check the request came from our own page (reports.same_site), on top of the
SameSite=Lax session cookie. They change no family plan, so gitaway/access.py lists them as open to every role: the check is here.
"""

import logging
import os
import re

from fasthtml.common import A, Button, Div, Form, H1, H2, H3, Input, Label, Li, Link, P, Section, Span, Textarea, Ul
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import bookingjobs, catalog, community, creatordraft as cd, liteapi, members, planforme as pfm, reports, showcase, stats
from gitaway.icons import icon
from gitaway.layout import reading
from gitaway.pages import creatorclaim as claims

GOAL = 150
logger = logging.getLogger(__name__)
HEAD = (Link(rel="stylesheet", href="/assets/css/admin.css"), *claims.HEAD)


def admin_emails() -> set:
    return {e.lower() for e in re.split(r"[,\s;]+", os.getenv("GITAWAY_ADMIN_EMAILS", "")) if e}


def is_admin(session) -> bool:
    email = str((session or {}).get("email") or "").strip().lower()
    return bool(email) and email in admin_emails() and (session or {}).get("verified") == 1   # a Google address Google has not verified is not proof of who you are (members.after_sign_in sets the flag)


def _button(action, slug, label, cls):
    return Form(Input(type="hidden", name="slug", value=slug), Button(label, type="submit", cls=f"btn btn-sm {cls}"), action=f"/admin/{action}", method="post", cls="ad-inline")


def _trip_row(row):
    down = community.is_down(row["slug"])
    return Li(Div(A(row["title"], href=f"/trips/{row['slug']}", cls="ad-link"), Span("Taken down" if down else "Live", cls="ad-state " + ("is-down" if down else "is-live"), id=f"state-{row['slug']}")),
              _button("restore", row["slug"], "Restore", "") if down else _button("takedown", row["slug"], "Take down", "ad-danger"), cls="ad-trip", id=row["slug"])


WAITS = {"pending": ("Unlisted until you approve it", "claimed"), "unverified": ("Byline waits for your approval", "published")}


def _waiting(w):
    """One trip waiting for the captain (F-194): what is held back, who published it and whose site the post is on, and the two buttons."""
    row, (what, verb) = w["row"], WAITS[w["state"]]
    return Li(Div(A(row["title"], href=f"/trips/{w['slug']}", cls="ad-link"), Span(what, cls="ad-state is-down", id=f"wait-state-{w['slug']}")),
              P(f"{verb} by {members.email_of(row['owner_user']) or 'someone'} · the post is on {w['host']}", cls="ad-meta"),
              Div(_button("approve", w["slug"], "Approve", ""), _button("takedown", w["slug"], "Take down", "ad-danger"), cls="cc-acts"), cls="ad-trip", id=f"wait-{w['slug']}")


def _creator(c, trips):
    return Li(Div(A(c["name"], href=f"/creators/{c['handle']}", cls="ad-link ad-name"),
                  Span(f"{(n := stats.readers_all_time(t['slug'] for t in trips))} reader{'s' if n != 1 else ''}", cls="ad-meta")),
              Ul(*[_trip_row(t) for t in trips], cls="ad-trips") if trips else P("No trips.", cls="ad-meta"), cls="ad-creator", id=f"c-{c['handle']}")


def _report(r):
    trip = community.get(r["target"], hidden=True) if r["kind"] == "trip" else None
    name = trip["title"] if trip else r["target"]
    href = f"/trips/{r['target']}" if r["kind"] == "trip" else f"/creators/{r['target']}"
    return Li(Div(Span(reports.REASONS.get(r["reason"], r["reason"]), cls="ad-reason"), Span("New", cls="ad-new-chip") if not r["seen"] else "", Span(r["created_at"][:16].replace("T", " "), cls="ad-meta")),
              P(A(name, href=href, cls="ad-link"), f" ({'trip' if r['kind'] == 'trip' else 'creator'})", cls="ad-meta"),
              P(r["note"], cls="ad-note") if r["note"] else "", P(f"Reply to: {r['email']}", cls="ad-meta") if r["email"] else "",
              (_button("restore", r["target"], "Restore", "") if community.is_down(r["target"]) else _button("takedown", r["target"], "Take down", "ad-danger")) if trip else "",
              cls="ad-report", id=f"report-{r['id']}")


def new_reports(session) -> int:
    """How many reports the captain has not marked read: 0 for anyone who is not an admin, and when the count cannot be read (a page must not fail for a badge)."""
    if not is_admin(session):
        return 0
    try:
        return reports.unseen()
    except Exception:  # noqa: BLE001
        logger.exception("could not count the new reports")
        return 0


STATUS_WORDS = {"awaiting_payment": "Waiting for payment", "paid": "Paid", "building": "Building", "review": "Check it", "sending": "Sending", "ready": "Ready", "failed": "Failed"}


def _dollars(micros) -> str:
    return f"${micros / 1_000_000:.3f}"


def _order(o):
    """One Plan it for me order (F-193): who, where, status, what it brought in and what the agent cost; a failed one that was paid is a refund due."""
    owed = pfm.refund_due(o)
    i = o["intake"]
    return Li(Div(Span(f"#{o['id'][:8]}", cls="ad-name"), Span(STATUS_WORDS[o["status"]], cls="ad-state " + ("is-down" if o["status"] == "failed" else "is-live" if o["status"] == "ready" else "")),
                  Span("Refund due", cls="ad-state is-down", id=f"refund-{o['id'][:8]}") if owed else "", Span(o["email"], cls="ad-meta")),
              P(f"{i['where']} · {i['start']} to {i['end']} · {i['adults']} adults, {len(i['kids'])} kids", cls="ad-meta"),
              P(f"{catalog.money(o['amount_cents'])} · agent {_dollars(o['ai_cost_micros'])} · {o['ai_tokens_in']:,} in, {o['ai_tokens_out']:,} out" + (f" · {o['ai_model']}" if o["ai_model"] else "")
                + (f" · {o['error']}" if o["error"] else ""), cls="ad-meta"),
              _check(o) if o["status"] == "review" else "",
              cls="ad-report", id=f"pfm-{o['id'][:8]}")


def _check(o):
    """The founder check (F-197): one tap sends the built plan to the family; the edit link opens every stop first."""
    return Div(Form(Button(icon("check", 18, 2.4), "Send to family", type="submit", cls="btn btn-primary", id=f"pfm-send-{o['id'][:8]}"), Input(type="hidden", name="order", value=o["id"]), action="/admin/plan-for-me/send", method="post", cls="ad-inline"),
               A("Look and edit first", href=f"/admin/plan-for-me/{o['id']}", cls="ad-link", id=f"pfm-edit-{o['id'][:8]}"), cls="ad-actions")


def check_page(o):
    """A built plan waiting for the check: the family's words on top, then every day's stops with their title and note in fields, the summary and the tips. Save keeps the edit; Send to family
    delivers it as it stands."""
    from gitaway.pages import planview
    i, r = o["intake"], o["result"]
    field = lambda name, value, label, rows=None: Label(Span(label, cls="ad-k"), Textarea(value, name=name, rows=str(rows), cls="ad-field") if rows else Input(type="text", name=name, value=value, cls="ad-field"), cls="ad-fieldset")
    days = [Section(H3(planview.day_label(i, d)), *[Div(Span(f"{planview.clock(st['start'])} · {st['kind']}", cls="ad-meta"), field(f"s{d}-{j}-title", st["title"], "Title"), field(f"s{d}-{j}-note", st["note"], "Note", 2), cls="ad-stop")
                                                   for j, st in enumerate(day["stops"])], cls="ad-sec") for d, day in enumerate(r["days"])]
    kids = ", ".join(planview.kid_words(i))
    return reading("Check a plan", Div(Div(
        H1("Check a plan", cls="ad-title"), P(f"#{o['id'][:8]} · {o['email']} · {i['where']} · {i['start']} to {i['end']} · {i['adults']} adults" + (f" · kids {kids}" if kids else "")
                                             + f" · {i['pace']} · {i['budget']}", cls="ad-meta"),
        P(f"Must-dos: {i['must']}", cls="ad-note") if i["must"] else "",
        Form(field("summary", r["summary"], "Summary", 2), *days, Section(H2("Tips"), *[field(f"tip{k}", r["tips"][k] if k < len(r["tips"]) else "", f"Tip {k + 1}") for k in range(pfm.MAX_TIPS)], cls="ad-sec"),
             Div(Button("Save the edit", type="submit", cls="btn", id="pfm-save"), A("Back to admin", href=f"/admin#pfm-{o['id'][:8]}", cls="ad-link"), cls="ad-actions"),
             Input(type="hidden", name="order", value=o["id"]), action="/admin/plan-for-me/edit", method="post", cls="ad-sec", id="pfm-check"),
        Form(Button(icon("check", 18, 2.4), "Send to family", type="submit", cls="btn btn-primary", id="pfm-send"), Input(type="hidden", name="order", value=o["id"]), action="/admin/plan-for-me/send", method="post", cls="ad-inline"),
        cls="ad-card"), id="admin", cls="ad-stage"), wide=True, head=HEAD)


PAID_TWICE = {"double": "Paid twice: the order was already paid", "unknown": "Paid for an order that no longer exists"}


def _owed(p):
    """A payment no order can be built from (F-193): the captain refunds it in Stripe, found by the Checkout session."""
    return Li(Div(Span(f"#{p['order_id'][:8] or 'none'}", cls="ad-name"), Span("Refund due", cls="ad-state is-down", id=f"refund-evt-{p['event_id'][-12:]}"), Span(PAID_TWICE[p["outcome"]], cls="ad-meta")),
              P(f"{catalog.money(p['amount_cents'])} · Checkout session {p['session_id']} · {p['at'][:10]}", cls="ad-meta"), cls="ad-report", id=f"owed-{p['event_id'][-12:]}")


def admin_page(drafted=()):
    people = community.real_creators()
    waiting = [w for w in community.waiting() if w["row"]]
    every = community.creators_all()
    live = sum(len(c["trips"]) for c in people)
    rep = reports.all_reports()
    orders = pfm.admin_rows()
    owed = pfm.refunds_due()
    pt = pfm.totals(orders, owed)
    searches = liteapi.searches_today()
    cards = (("Creators", f"{len(people)} of {GOAL}", "ad-goal"), ("Live trips", str(live), "ad-live"), ("Reports", str(len(rep)), "ad-reports"),              ("Plan it for me", f"{pt['paid']} paid · {catalog.money(pt['revenue_cents'])}", "ad-pfm"), ("Refunds due", f"{pt['refunds']} · {catalog.money(pt['refund_cents'])}", "ad-refunds"),
             ("Agent cost", _dollars(pt["ai_cost_micros"]), "ad-pfm-cost"),
             ("LiteAPI", f"{liteapi.mode()} · {searches} search{'es' if searches != 1 else ''} today", "ad-liteapi"),     # F-220: the key's kind, never the key
             ("Paid, not booked (10+ min)", str(bookingjobs.stuck_count()), "ad-stuck"))     # F-274: a guest paid in LiteAPI's form and the stay is not booked yet: the worker keeps trying (D-848)
    fresh = sum(1 for r in rep if not r["seen"])
    return reading("Admin", Div(
        Div(H1("Admin", cls="ad-title"),
            Div(*[Div(Span(label, cls="ad-k"), Span(value, cls="ad-v", id=i)) for label, value, i in cards], cls="ad-cards"),
            Div(Span(cls="ad-bar-fill", style=f"width:{min(100, round(100 * len(people) / GOAL))}%"), cls="ad-bar", role="img", aria_label=f"{len(people)} of {GOAL} creators"),
            Section(H2("Plan it for me orders"), P("Refunds are yours, by hand in Stripe: a failed order that was paid, and a payment that paid an order twice or one that is gone, say Refund due.", cls="ad-meta"),
                    Ul(*[_owed(p) for p in owed], *[_order(o) for o in orders], cls="ad-list", id="ad-orders") if orders or owed else P("No orders yet.", cls="ad-meta", id="ad-no-orders"), cls="ad-sec"),
            _needs_a_look(),
            _flights_to_match(),
            claims.section(drafted),
            Section(H2("Waiting for your approval"), P("A trip claimed or published by someone whose email is not at the post's own site. Check it is theirs, then approve it.", cls="ad-meta"),
                    Ul(*[_waiting(w) for w in waiting], cls="ad-list", id="ad-waiting"), cls="ad-sec", id="ad-waiting-sec") if waiting else "",
            Section(H2("Reports", Span(f"{fresh} new", cls="ad-badge", id="ad-new") if fresh else ""),
                    Form(Input(type="hidden", name="upto", value=str(rep[0]["id"])), Button("Mark all as read", type="submit", cls="btn btn-sm"), action="/admin/seen", method="post", cls="ad-inline", id="ad-seen") if fresh else "", Ul(*[_report(r) for r in rep], cls="ad-list", id="ad-report-list") if rep else P("No reports.", cls="ad-meta", id="ad-no-reports"), cls="ad-sec"),
            Section(H2("Creators and trips"),
                    Ul(*[_creator(c, community.rows(kind="scrapbook", owner=c["owner_user"], hidden=True)) for c in every], cls="ad-list", id="ad-creators") if every else P("Nobody has published yet.", cls="ad-meta"),
                    cls="ad-sec"),
            cls="ad-card"), id="admin", cls="ad-stage"), wide=True, head=HEAD)


def _needs_a_look():
    """F-274 (D-852): the stays a guest may have paid for that the booking worker could not book after an hour and LiteAPI did not say were unpaid. Kept whole until the captain resolves each
    (refunded in LiteAPI's dashboard, or booked by hand). Listed by token prefix, when, LiteAPI's transaction id and our booking reference: the ids to look it up with."""
    rows = bookingjobs.needing_help()
    if not rows:
        return ""
    return Section(H2("Needs a look"), P("A guest may have paid and the stay is not booked. Find the payment in LiteAPI with the transaction id or the reference, refund or book it, then press Resolved.", cls="ad-meta"),
                   Ul(*[Li(Div(Span(f"{r['token'][:6]} · {r['created_at'][:16].replace('T', ' ')}", cls="ad-reason"), Span(f"Transaction {r['transaction_id']}", cls="ad-meta"), Span(f"Reference {r['reference']}", cls="ad-meta")),
                            Form(Input(type="hidden", name="family", value=r["family"]), Input(type="hidden", name="token", value=r["token"]), Button("Resolved", type="submit", cls="btn btn-sm"),
                                 action="/admin/payments/resolve", method="post", cls="ad-inline")) for r in rows], cls="ad-list", id="ad-needs-help"), cls="ad-sec", id="ad-needs-help-sec")


def _flights_to_match():
    """F-276 (D-980): flight payment forms opened and not finished, or a book that may have gone through, from the last 7 days. Nothing proves a flight was paid, so the captain matches each by
    LiteAPI's transaction id in its dashboard (booked by hand or refunded). Only the ids, the amount and the date: no traveller."""
    rows = bookingjobs.flights_to_match()
    if not rows:
        return ""
    return Section(H2("Flights to match"), P("A flight form was opened and left, or a flight booking may have gone through. Find the transaction in LiteAPI's dashboard: if it was paid and no flight exists, book it by hand or refund it.", cls="ad-meta"),
                   Ul(*[Li(Div(Span(f"{r['token'][:6]} · {r['created_at'][:16].replace('T', ' ')} · {r['status']}", cls="ad-reason"), Span(f"Transaction {r['transaction_id']}", cls="ad-meta"),
                               Span(catalog.money(r["charge_cents"]), cls="ad-meta"))) for r in rows], cls="ad-list", id="ad-flights-match"), cls="ad-sec", id="ad-flights-match-sec")


def register(app):
    @app.post("/admin/payments/resolve")
    async def admin_resolve_payment(request, session):
        if not is_admin(session) or not reports.same_site(request):
            return showcase.not_found()
        form = await request.form()
        family, token = str(form.get("family") or ""), str(form.get("token") or "")
        done = await run_in_threadpool(bookingjobs.resolve, family, token)
        logger.info("payment resolved by the captain: %s token %s… family %s… (%s)", (session or {}).get("email", "?"), token[:6], family[:6], "done" if done else "no change")   # F-274 audit: who resolved which row and when (the log has the time)
        return RedirectResponse("/admin", status_code=303)

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
            return RedirectResponse(f"/admin#{slug}" if await run_in_threadpool(fn, slug) else "/admin", status_code=303)   # only a slug that exists goes into the address
        handler.__name__ = f"admin_{name}"
        app.post(f"/admin/{name}")(handler)

    @app.post("/admin/seen")
    async def admin_seen(request, session):
        if not is_admin(session) or not reports.same_site(request):
            return showcase.not_found()
        upto = str((await request.form()).get("upto") or "")
        if upto.isdigit():
            reports.mark_seen(int(upto))
        return RedirectResponse("/admin", status_code=303)
    def _in_review(session, order_id):
        """The order behind a check address, for an admin only (None for anyone else, an unknown id or one that is not waiting for the check)."""
        if not is_admin(session) or not isinstance(order_id, str) or not pfm._ID.fullmatch(order_id):
            return None
        o = pfm._row(order_id)
        return o if o and o["status"] == "review" and o["result"] else None

    @app.get("/admin/plan-for-me/{order_id}")
    def plan_check(session, order_id: str):
        o = _in_review(session, order_id)
        return check_page(o) if o else showcase.not_found()

    @app.post("/admin/plan-for-me/edit")
    async def plan_edit(request, session):
        if not is_admin(session) or not reports.same_site(request):
            return showcase.not_found()
        form = await request.form()
        order_id = str(form.get("order") or "")
        ok = await run_in_threadpool(pfm.edit, order_id, {k: v for k, v in form.items() if isinstance(v, str)}) if pfm._ID.fullmatch(order_id) else False
        return RedirectResponse(f"/admin/plan-for-me/{order_id}" if ok else "/admin", status_code=303)

    @app.post("/admin/plan-for-me/send")
    async def plan_send(request, session):
        if not is_admin(session) or not reports.same_site(request):
            return showcase.not_found()
        order_id = str((await request.form()).get("order") or "")
        if pfm._ID.fullmatch(order_id):
            await run_in_threadpool(pfm.send, order_id)
        return RedirectResponse(f"/admin#pfm-{order_id[:8]}" if pfm._ID.fullmatch(order_id) else "/admin", status_code=303)

    _act("takedown", community.take_down)
    _act("restore", community.restore)
    _act("approve", cd.approve)      # F-194: the captain's yes to a trip that waits for him
