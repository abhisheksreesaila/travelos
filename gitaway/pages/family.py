"""Your family space (F-039): who is signed in and which family tenant they belong to. The one page that needs sign-in.

F-040 builds the trips on top of this. It uses require_tenant_access, so it also proves the family database opens.
"""

from fasthtml.common import Div, H1, Link, P
from fh_saas.utils_auth import require_tenant_access

from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/family.css"),)
PRIVATE = ("/family",)  # paths main.py's auth beforeware protects; everything else is public


def register(app):
    @app.get("/family")
    def family(request):
        user = request.state.user
        require_tenant_access(request).conn.close()  # opens the family database (and checks membership)
        return page("Your family", Div(
            H1("Your family"),
            P(f"Signed in as {user['email']}.", id="fam-who"),
            P(f"Role: {user['role']}.", id="fam-role"),
            P(f"Family space: {user['tenant_id']}", id="fam-tenant"),
            cls="fam",
        ), head=HEAD)
