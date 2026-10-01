"""One module per screen. Each exposes `register(app)`.

A new screen appends its module to SCREENS. Placeholders are registered last, as fallbacks,
so a real screen on the same path always wins (Starlette serves the first matching route).
"""

from gitaway.pages import calendar, creators, discover, family, forks, home, pay, placeholders, plan, pwa, share, signin, start, trips, voice

SCREENS = [home, trips, plan, pay, signin, calendar, discover, share, start, creators, forks, voice, pwa, family]


def register_all(app, extra=()):
    for screen in [*SCREENS, *extra]:
        screen.register(app)
    placeholders.register(app)
