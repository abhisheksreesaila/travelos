"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route).
`retired` answers the addresses of the old app with a redirect into the journey (F-254).
"""

from gitaway.pages import admin, devart, blogbutton, guides, guidepage, guidesheet, crawlers, creatorclaim, creatordrafts, creatorimport, sharetarget, creatorsettings, creatorstats, creators, forcreators, report, family, home, legal, morning, passes, passkeys, partners, placeholders, planforme, pwa, signin, tab_help, tripbuild, tripimport, matrixbook, tripask, tripmatrix, tripshare, trips, planv2, chatwrites, booking, retired

SCREENS = [home, crawlers, blogbutton, tripimport, tripbuild, trips, tripask, tripmatrix, matrixbook, partners, signin, guides, guidepage, guidesheet, creatorclaim, creatorimport, sharetarget, creatorsettings,
           creatorstats, creatordrafts, creators, forcreators, report, admin, pwa, family, morning, passes, passkeys, planforme, tab_help, legal, tripshare, planv2, chatwrites, booking, devart, retired]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
