"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route).
"""

from gitaway.pages import calendar, communitytrips, creators, family, forks, home, pay, placeholders, plan, pwa, rides, share, signin, start, tripbuild, tripimport, trips, trip, voice

SCREENS = [home, tripimport, tripbuild, trips, plan, pay, rides, signin, calendar, communitytrips, share, start, creators, forks, voice, pwa, family, trip]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
