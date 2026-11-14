"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route).
"""

from gitaway.pages import admin, devart, blogbutton, cockpit, calendar, communitytrips, crawlers, creatorclaim, creatordrafts, creatorimport, sharetarget, creatorsettings, creatorstats, creators, forcreators, report, daycard, family, familydock, forks, home, legal, morning, passes, passkeys, partners, pay, phone_tabs, placeholders, plan, planforme, plantalk, publish, pwa, rides, share, signin, tab_help, tripadd, tripbuild, tripbook, tripcanvas, tripgrid, tripimport, matrixbook, tripmatrix, tripnew, tripshare, trips, trip

SCREENS = [home, crawlers, blogbutton, tripimport, tripbuild, trips, tripgrid, tripmatrix, matrixbook, plan, tripbook, pay, rides, signin, calendar, communitytrips, share, creatorclaim, creatorimport, sharetarget, creatorsettings, creatorstats, creatordrafts, creators, forcreators, report, admin, forks, pwa, family, trip, morning, passes, passkeys, planforme, partners, phone_tabs, tab_help, tripadd, tripcanvas, daycard, familydock, plantalk, publish, legal, cockpit, tripnew, tripshare, devart]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
