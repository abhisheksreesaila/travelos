"""The Family tab (phone shell, F-067). A placeholder: replace content() and nothing else.

content(request, session) returns what sits between the heading and the tab bar. Optional module-level HEAD (stylesheet links) and
SCRIPTS (script paths) are added to the page. TITLE is the heading. The route and the shell are in gitaway/pages/phone_tabs.py.
"""

from gitaway import phone

TITLE = "Family"


def content(request, session):
    return phone.coming("Family", "One place for the family to talk, with photos and plan changes.", "users")
