"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route). `planforme` is before `partners`: /sandbox/{partner}/{click} would answer /sandbox/plan-for-me/<order>.
`retired` answers the addresses of the old app with a redirect into the journey (F-254).
"""

from gitaway.pages import admin, devart, blogbutton, guides, guidepage, guidesheet, crawlers, creatorclaim, creatordrafts, creatorimport, sharetarget, creatorsettings, creatorstats, creators, forcreators, report, family, home, legal, morning, passes, passkeys, partners, placeholders, planforme, pwa, signin, tab_help, tripbuild, tripimport, matrixbook, staycancel, flightcancel, walletpass, tripask, tripmatrix, hotelview, aerialview, tripshare, trips, planv2, chatwrites, booking, today, retired, trust

SCREENS = [home, crawlers, blogbutton, tripimport, tripbuild, trips, tripask, tripmatrix, hotelview, aerialview, matrixbook, staycancel, flightcancel, walletpass, planforme, partners, signin, guides, guidepage, guidesheet, creatorclaim, creatorimport, sharetarget, creatorsettings,
           creatorstats, creatordrafts, creators, forcreators, report, admin, pwa, family, morning, passes, passkeys, tab_help, legal, tripshare, planv2, chatwrites, booking, today, devart, trust, retired]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
