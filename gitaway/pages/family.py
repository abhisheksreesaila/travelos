"""Your family (F-039, F-043): who is signed in, who is in the family, invites, and the invite link people join through.

GET  /family                  members with role and joined date, pending invites with copy-link and revoke, the invite form, the family switcher
POST /family/invite           (admin) invite an email as editor or viewer; the invite is a link to copy (email sending comes later)
POST /family/invite/revoke    (admin) take a pending invite back
POST /family/role             (admin) change a member's role
POST /family/remove           (admin) remove a member (or leave, for the owner while another admin remains); the last admin cannot go
POST /family/switch           work in another of my families (any member)
GET  /join/<token>            an invite link: sign in first if needed, then join (the signed-in email must match the invite)
POST /join/<token>            join the family

Who may call what is gitaway.access's rule (admin-only and open routes are listed there); the model is gitaway.members.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H1, H2, Input, Label, Li, Link, Option, P, Script, Section, Select, Span, Ul, to_xml
from starlette.responses import RedirectResponse, Response

from gitaway import familydb, members, session as ses
from gitaway.layout import avatar, page

log = logging.getLogger("gitaway.family")

HEAD = (Link(rel="stylesheet", href="/assets/css/family.css"), Script(src="/assets/js/family.js", defer=True))
PRIVATE = ("/family",)  # paths main.py's auth beforeware protects; everything else is public


def _date(iso):
    try:
        d = datetime.fromisoformat(iso)
        return f"{d:%b} {d.day}, {d.year}"
    except (TypeError, ValueError):
        return ""


def _days_left(iso):
    try:
        left = (datetime.fromisoformat(iso) - datetime.now(timezone.utc)).days
    except (TypeError, ValueError):
        return ""
    return "expires today" if left <= 0 else "expires tomorrow" if left == 1 else f"expires in {left} days"


def link_for(request, token):
    return f"{str(request.base_url).rstrip('/')}/join/{token}"


def _role_select(current, choices, name="role", label="Role"):
    return Select(*[Option(members.ROLE_WORDS[r], value=r, selected=r == current) for r in choices], name=name, aria_label=label, cls="fam-select")


def _member_row(m, me, my_role, tenant_id):
    is_me, admin = m["user_id"] == me, my_role == "admin"
    owner = m["raw"] == "owner"
    who = [Span(Span(m["name"], cls="fam-name"), Span(" (you)", cls="fam-you") if is_me else "", cls="fam-nameline"), Span(m["email"], cls="fam-email")]
    actions = []
    if admin and (not owner or is_me):
        actions.append(Form(Input(type="hidden", name="user", value=m["user_id"]), _role_select(m["role"], members.ROLES, label=f"Role of {m['name']}"),
                            Button("Change", type="submit", cls="btn btn-sm fam-btn"), action="/family/role", method="post", cls="fam-inline"))
        actions.append(Form(Input(type="hidden", name="user", value=m["user_id"]),
                            Button("Leave" if is_me else "Remove", type="submit", cls="btn btn-sm fam-btn fam-remove", data_confirm=f"{'Leave this family' if is_me else 'Remove ' + m['name']}?"),
                            action="/family/remove", method="post", cls="fam-inline"))
    return Li(avatar(ses.Friend(m["name"], m["initials"], m["color"]), "ga-avatar fam-av"),
              Div(*who, cls="fam-who"),
              Div(Span(members.ROLE_WORDS[m["role"]], cls="tag fam-role-tag", data_role=m["role"]), Span(f"Joined {_date(m['joined'])}", cls="fam-joined"), cls="fam-meta"),
              Div(*actions, cls="fam-actions") if actions else "",
              cls="fam-member", data_user=m["user_id"])


def _invite_row(inv, request):
    link = link_for(request, inv["token"])
    return Li(Div(Span(inv["email"], cls="fam-name"), Span(members.ROLE_WORDS[inv["role"]], cls="tag fam-role-tag", data_role=inv["role"]),
                  Span(_days_left(inv["expires_at"]), cls="fam-joined"), cls="fam-invhead"),
              Div(Input(type="text", value=link, readonly=True, aria_label=f"Invite link for {inv['email']}", cls="fam-link", data_link=""),
                  Button("Copy link", type="button", data_copy=link, cls="btn btn-sm fam-btn"),
                  Form(Input(type="hidden", name="id", value=inv["id"]), Button("Revoke", type="submit", cls="btn btn-sm fam-btn fam-remove"),
                       action="/family/invite/revoke", method="post", cls="fam-inline"), cls="fam-linkrow"),
              cls="fam-invite", id=f"inv-{inv['id']}", data_invite=inv["id"])


def family_page(request, session, error="", status=200, email="", role="editor"):
    user, tid = request.state.user, session["tenant_id"]
    me, my_role = user["user_id"], request.state.family_role
    crew, pending = members.members(tid), (members.pending_invites(tid) if my_role == "admin" else [])
    mine = members.families_of(me)
    switcher = Section(H2("Your families", id="fam-switch-h"),
                       Ul(*[Li(Span(f["label"], cls="fam-name"), Span(members.ROLE_WORDS[f["role"]], cls="tag fam-role-tag", data_role=f["role"]),
                               Span("Working here", cls="fam-here") if f["tenant_id"] == tid else
                               Form(Input(type="hidden", name="tenant", value=f["tenant_id"]), Button("Switch", type="submit", cls="btn btn-sm fam-btn"), action="/family/switch", method="post", cls="fam-inline"),
                               cls="fam-fam", aria_current="true" if f["tenant_id"] == tid else None) for f in mine], cls="fam-list"),
                       aria_labelledby="fam-switch-h", id="fam-switcher", cls="fam-sec") if len(mine) > 1 else ""
    invite_form = Section(
        H2("Invite family", id="fam-invite-h"),
        P("Type the Gmail address they sign in with. You get a link to send them; when they sign in with that address they join.", cls="fam-sub"),
        Div(error, role="alert", id="fam-error", cls="fam-error") if error else "",
        Form(Label(Span("Email", cls="fam-label"), Input(type="email", name="email", id="fam-email", value=email, required=True, placeholder="sam@gmail.com", autocomplete="off",
                                                         **({"aria_invalid": "true", "aria_describedby": "fam-error"} if error else {})), cls="fam-field"),
             Label(Span("Can", cls="fam-label"), Select(Option("Edit the plans", value="editor", selected=role == "editor"), Option("Only look", value="viewer", selected=role == "viewer"),
                                                          name="role", id="fam-role-pick"), cls="fam-field fam-field-role"),
             Button("Create invite link", type="submit", cls="btn btn-primary fam-go"), action="/family/invite", method="post", id="fam-invite-form", cls="fam-inviteform"),
        aria_labelledby="fam-invite-h", id="invite", cls="fam-sec") if my_role == "admin" else ""
    waiting = Section(H2("Waiting to join", id="fam-wait-h"), Ul(*[_invite_row(i, request) for i in pending], cls="fam-list", id="fam-pending"),
                      aria_labelledby="fam-wait-h", cls="fam-sec") if pending else ""
    note = P("Only a family admin can invite people or change who is in the family.", cls="fam-sub", id="fam-note") if my_role != "admin" else ""
    out = page("Your family", Div(
        H1("Your family"),
        P(f"Signed in as {user['email']}.", id="fam-who"),
        P(f"Role: {my_role}.", id="fam-role"),
        P(f"{members.family_label(tid)} · family space {tid}", id="fam-tenant", cls="fam-small"),
        switcher,
        Section(H2("Who is in", id="fam-members-h"), Ul(*[_member_row(m, me, my_role, tid) for m in crew], cls="fam-list", id="fam-members"),
                note, aria_labelledby="fam-members-h", cls="fam-sec"),
        waiting, invite_form,
        cls="fam",
    ), head=HEAD)
    return out if status == 200 else Response(to_xml(out), status_code=status, media_type="text/html")


def _join_page(title, *body, status=200):
    out = page(title, Div(H1(title), *body, cls="fam fam-join", id="join"), head=HEAD)
    return out if status == 200 else Response(to_xml(out), status_code=status, media_type="text/html")


def _problem_page(problem, signed_in):
    again = A("Back to GitAway", href="/", cls="btn btn-primary") if not signed_in else A("Your family", href="/family", cls="btn btn-primary")
    status = {"unknown": 404, "expired": 410, "revoked": 410, "accepted": 410, "mismatch": 403, "unverified": 403}.get(problem.kind, 400)
    return _join_page("This invite did not work", P(str(problem), id="join-problem"), again, status=status)


def register(app):
    def _admin_action(request, session, action, **form):
        """Run a model change for the signed-in admin; the family page again, with the message when the model refuses."""
        try:
            action()
        except members.MemberError as e:
            return family_page(request, session, error=str(e), status=409, **form)
        return RedirectResponse("/family", status_code=303)

    @app.get("/family")
    def family(request, session):
        familydb.family_db(request).conn.close()  # opens the family database (checks membership, makes sure the tables exist)
        return family_page(request, session)

    @app.post("/family/invite")
    def invite(request, session, email: str = "", role: str = ""):
        user = request.state.user
        try:
            inv = members.invite(session["tenant_id"], user["user_id"], email, role)
        except members.MemberError as e:
            return family_page(request, session, error=str(e), status=409, email=email, role=role if role in members.INVITE_ROLES else "editor")
        return RedirectResponse(f"/family#inv-{inv['id']}", status_code=303)

    @app.post("/family/invite/revoke")
    def revoke(request, session, id: str = ""):
        return _admin_action(request, session, lambda: members.revoke(session["tenant_id"], request.state.user["user_id"], id))

    @app.post("/family/role")
    def role(request, session, user: str = "", role: str = ""):
        return _admin_action(request, session, lambda: members.change_role(session["tenant_id"], request.state.user["user_id"], user, role))

    @app.post("/family/remove")
    def remove(request, session, user: str = ""):
        return _admin_action(request, session, lambda: members.remove(session["tenant_id"], request.state.user["user_id"], user))

    @app.post("/family/switch")
    def switch(request, session, tenant: str = "", next: str = ""):
        """Work in another family. The membership is checked here, never trusted from the form: a family that is not mine changes nothing."""
        members.set_active(session, tenant)
        session.pop("note", None)
        return RedirectResponse(ses.safe_next(next, "/family"), status_code=303)

    @app.post("/family/stay")
    def stay(session, next: str = ""):
        """Dismiss the "you joined" notice and keep working where I am."""
        session.pop("note", None)
        return RedirectResponse(ses.safe_next(next, "/family"), status_code=303)

    @app.get("/join/{token}")
    def join(session, token: str):
        uid, email = session.get("user_id"), session.get("email") or ""
        inv = members.find_invite(token)
        here = f"/join/{token}"
        if not inv:
            return _problem_page(members.InviteProblem("unknown", "That invite link is not one we know. Ask for a new one."), bool(uid))
        family = members.family_label(inv["tenant_id"])
        if inv["state"] == "accepted" and uid and inv["accepted_by"] == uid and members.role_in(uid, inv["tenant_id"]):
            members.set_active(session, inv["tenant_id"])  # signing in through this link already joined them; take them in
            return RedirectResponse("/calendar", status_code=303)
        if inv["state"] != "pending":
            return _problem_page(members.InviteProblem(inv["state"], {"expired": "That invite has expired. Ask the family admin for a new one.", "revoked": "That invite was taken back. Ask the family admin for a new one.",
                                                                       "accepted": "That invite was already used."}[inv["state"]]), bool(uid))
        what = P(f"You are invited to {family} as {members.ROLE_WORDS[inv['role']].lower()}. {members.ROLE_HELP[inv['role']]}", id="join-what")
        for_who = P(f"This invite is for {members.mask_email(inv['email'])}. Sign in with that address.", id="join-for", cls="fam-small")
        if uid and not session.get("verified"):
            return _problem_page(members.InviteProblem("unverified", members.UNVERIFIED), True)
        if not uid:
            return _join_page(f"Join {family}", what, for_who, A("Sign in to join", href=f"/signin?next={quote(here, safe='')}&intent=join", cls="btn btn-primary", id="join-signin"))
        if members.match_key(email) != inv["email_key"]:
            log.warning("invite %s (for %s) was opened by user %s signed in as %s: the email does not match", inv["id"], members.mask_email(inv["email"]), uid, members.mask_email(email))
            return _join_page("This invite is for someone else",
                              P(f"You are signed in as {email}, but this invite is for {members.mask_email(inv['email'])}. Sign out, then sign in with the address it was sent to.", id="join-problem"),
                              Form(Button("Sign out", type="submit", cls="btn btn-primary"), action="/signout", method="post"), status=403)
        return _join_page(f"Join {family}", what, Form(Button(f"Join {family}", type="submit", cls="btn btn-primary", id="join-go"), action=here, method="post"))

    @app.post("/join/{token}")
    def join_now(session, token: str):
        uid, email = session.get("user_id"), session.get("email") or ""
        if not uid:
            return RedirectResponse(f"/signin?next={quote(f'/join/{token}', safe='')}&intent=join", status_code=303)
        try:
            joined = members.accept_token(uid, email, token, verified=bool(session.get("verified")))
        except members.InviteProblem as e:
            return _problem_page(e, True)
        members.set_active(session, joined["tenant_id"])
        return RedirectResponse("/calendar", status_code=303)
