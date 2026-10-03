"""Who may change what in a family (F-043): one beforeware that every request passes through.

Roles (fh-saas): admin > editor > viewer. Admins invite people, change roles and remove members. Editors change everything a
family plans: trips, the calendar, rides, forks, saves and sharing. Viewers read and change nothing.

The rule is central, not per route, so a new route is safe by default: any request that is not a read (GET, HEAD, OPTIONS)
needs the editor role, unless its path is listed below as open to every member or as admin-only. tests/test_roles.py walks every
POST route in the app and fails when a route is neither refused for a viewer nor on the open list below, so adding an open
route is a decision someone has to make in two places.

The role is read from the host database on every request (gitaway.members.role_in), never from the cookie: removing a member or
changing a role takes effect on their next request. A person whose family no longer has them is moved to another of their
families, or signed out when they have none.
"""

from contextvars import ContextVar

from starlette.responses import RedirectResponse, Response

from gitaway import members, session as ses
from gitaway.layout import page

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
# Writes that do not touch a family's plans, so any member (viewers too) may make them.
OPEN_POSTS = (
    "/signin", "/logout", "/signout",      # signing in and out
    "/trips/switch",                       # which trip I am looking at (my own `members.trip_id`)
    "/family/switch", "/family/stay",      # which of my families I am working in; dismissing the "you joined" notice
    "/creators", "/creators/draft", "/creators/finish",   # a creator draft is a person's own, published to the community, not a family's
    "/trip/morning", "/trip/morning/time", "/trip/morning/off", "/trip/morning/status",   # my own phone's morning plan reminder (F-066): every member, viewers too
    "/trip/family/message", "/trip/family/quiet",   # a message in the family thread and my own Quiet switch (F-070): every member, viewers too (a viewer cannot change a plan, so never causes a change card)
)
OPEN_PREFIXES = ("/join/",)                # using an invite link: the person is joining another family
ADMIN_POSTS = ("/family/invite", "/family/invite/revoke", "/family/role", "/family/remove", "/trip/delete")  # deleting an imported trip (F-042) is an admin's

_role = ContextVar("gitaway_family_role", default=None)

VIEWER_MESSAGE = "You can look at this family's plans but not change them. Ask a family admin to make you an editor."
EDITOR_MESSAGE = "Only a family admin can invite people, change roles or remove members."


def request_role():
    """The signed-in person's role in the family for this request ("admin", "editor", "viewer"), or None when signed out."""
    return _role.get()


def can_edit(role) -> bool:
    return role in ("admin", "editor")


def needed(method, path) -> str | None:
    """The role a request needs: None (any member, or nobody: a read), "editor" or "admin"."""
    if method in SAFE_METHODS or path in OPEN_POSTS or path.startswith(OPEN_PREFIXES):
        return None
    return "admin" if path in ADMIN_POSTS else "editor"


def allows(role, need) -> bool:
    return need is None or (role == "admin") or (need == "editor" and role == "editor")


def refusal(request, session, role):
    """The friendly page a refused person gets (403). Calendar writes get the calendar back with the message on it, since its soft navigation swaps that page in."""
    message = EDITOR_MESSAGE if role != "viewer" else VIEWER_MESSAGE
    if request.url.path.startswith("/calendar"):
        try:
            from gitaway.pages.calendar import calendar_page
            return calendar_page(session, notice=message, status=403)
        except Exception:  # no booking to show, say: the plain page below
            pass
    from fasthtml.common import A, Div, H1, P, Section, to_xml
    body = page("Not allowed", Section(Div(H1("Only editors can change that"), P(message, id="refusal"),
                                            A("Back to the calendar", href="/calendar", cls="btn btn-primary"), cls="ga-wrap"), cls="ga-soon ga-wrap"))
    return Response(to_xml(body), status_code=403, media_type="text/html")


def _build_note(sess, uid, active):
    """The notice a sign-in left in the session, as the layout shows it; None (and forgotten) when it no longer applies."""
    kind = sess.get("note")
    if kind == "unverified":
        return {"kind": kind, "text": members.UNVERIFIED, "tenant": "", "switch": False}
    if isinstance(kind, str) and kind.startswith("joined:"):
        tid = kind.split(":", 1)[1]
        if members.role_in(uid, tid):
            return {"kind": "joined", "text": f"You joined {members.family_label(tid)}.", "tenant": tid, "switch": tid != active}
    sess.pop("note", None)
    return None


async def guard(req, sess):
    """Beforeware: find the person's role in their active family, repair a lost membership, and refuse writes the role does not allow.

    Async on purpose, like session.bind: a ContextVar set in a sync beforeware is lost in its threadpool copy of the context.
    """
    # Not supported yet: a system-admin session has no family (fh-saas gives it no tenant_id). Such a session is treated as having lost its
    # family below and is signed out; GitAway has no system admins today.
    uid = sess.get("user_id")
    ses._request_note.set(None)
    ses._request_tenant.set(None)
    if not uid:
        _role.set(None)
        return None
    tid = sess.get("tenant_id")
    found = members.membership_row(uid, tid)
    if found is None:  # removed from this family (or never in it): their next request is in another family of theirs, or signed out
        found = members.preferred_family(uid)
        if found:
            members.apply_active(sess, found["tenant_id"], found["role"])
            req.state.moved = True
        else:
            ses.sign_out(sess)
            _role.set(None)
            return None
    elif sess.get("tenant_role") != found["role"]:  # a role changed since the cookie was made: keep fh-saas's copy true too
        members.apply_active(sess, found["tenant_id"], found["role"])
    role = members.effective_role(found["role"])
    _role.set(role)
    ses._request_tenant.set(found["tenant_id"])
    ses._request_note.set(_build_note(sess, uid, found["tenant_id"]))
    req.state.family_role = role
    need = needed(req.method, req.url.path)
    if not allows(role, need):
        req.scope[ses.PRIVATE_SCOPE_KEY] = True  # F-062: session.bind never runs for a refusal, and it can show the family's calendar
        return refusal(req, sess, role)
    return None
