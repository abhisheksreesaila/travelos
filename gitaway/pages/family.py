"""Your family space (F-039): who is signed in and which family tenant they belong to. The one page that needs sign-in.

The trips are on top of this (F-040). It opens the family database through gitaway.familydb, so it also proves it opens.
"""

from fasthtml.common import Div, H1, Link, P

from gitaway import familydb
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/family.css"),)
PRIVATE = ("/family",)  # paths main.py's auth beforeware protects; everything else is public


def register(app):
    @app.get("/family")
    def family(request):
        user = request.state.user
        familydb.family_db(request).conn.close()  # opens the family database (checks membership, makes sure the tables exist)
        return page("Your family", Div(
            H1("Your family"),
            P(f"Signed in as {user['email']}.", id="fam-who"),
            P(f"Role: {user['role']}.", id="fam-role"),
            P(f"Family space: {user['tenant_id']}", id="fam-tenant"),
            cls="fam",
        ), head=HEAD)
