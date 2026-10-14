"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route).
"""

from gitaway.pages import calendar, communitytrips, creators, daycard, family, familydock, forks, home, legal, morning, passes, passkeys, pay, phone_tabs, placeholders, plan, plantalk, pwa, rides, share, signin, start, tab_help, tripadd, tripbuild, tripcanvas, tripimport, trips, trip

SCREENS = [home, tripimport, tripbuild, trips, plan, pay, rides, signin, calendar, communitytrips, share, start, creators, forks, pwa, family, trip, morning, passes, passkeys, phone_tabs, tab_help, tripadd, tripcanvas, daycard, familydock, plantalk, legal]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
