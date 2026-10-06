"""The phone shell's pages besides the canvas (F-067; since F-096 only Ask and Family are tabs): /trip/map, /trip/ask, /trip/family and /trip/help.

Each route only builds the shell (heading, tab bar) and asks its own module for the content: gitaway/pages/tab_<name>.py `content(request, session)`.
Replace a tab by editing that module; nothing here changes. Every role can open a tab (a tab that writes adds its own POST route,
which gitaway.access gates by role).
"""

from fasthtml.common import Main

from gitaway import members, phone, session as ses, tripcal as cal
from gitaway.layout import avatar, join_note
from gitaway.pages import tab_ask, tab_family, tab_help, tab_map

TAB_MODULES = {"map": tab_map, "ask": tab_ask, "family": tab_family, "help": tab_help}


def tab_page(key, request, session):
    mod = TAB_MODULES[key]
    b = ses.booking(session)
    t = cal.trip("", b)
    kicker = f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}"
    faces = [avatar(ses.current_traveler(session), "tp-av"), *[avatar(f, "tp-av") for f in members.crew(session)]]
    return phone.shell(key, phone.header(kicker, mod.TITLE, faces, sos=key in ("ask", "family")), join_note(), Main(mod.content(request, session), id="main", cls="ph-main"),
                       title=mod.TITLE, head=getattr(mod, "HEAD", ()), scripts=getattr(mod, "SCRIPTS", ()))


def register(app):
    def make(key):
        def route(request, session):
            if (r := phone.guard(session, f"/trip/{key}")):
                return r
            if key == "ask" and tab_ask.wants_sheet(request):        # F-104: the sheet fetches the box alone
                return tab_ask.sheet_open(request, session)
            return tab_page(key, request, session)
        return route

    for key, mod in TAB_MODULES.items():
        app.get(f"/trip/{key}", name=f"trip_{key}")(make(key))
        if hasattr(mod, "register"):  # a tab with routes of its own (Family's thread, F-070) adds them here
            mod.register(app)
