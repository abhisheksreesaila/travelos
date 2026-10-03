"""The Help tab (phone shell, F-067). A placeholder: replace content() and nothing else.

content(request, session) returns what sits between the heading and the tab bar. Optional module-level HEAD (stylesheet links) and
SCRIPTS (script paths) are added to the page. TITLE is the heading. The route and the shell are in gitaway/pages/phone_tabs.py.
"""

from gitaway import phone

TITLE = "Help"


def content(request, session):
    return phone.coming("Help", "Tonight's hotel, the car, 911 and the family's phone numbers in one tap.", "life")
