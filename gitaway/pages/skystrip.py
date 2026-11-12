"""The sky strip (F-223): a row of days, each wearing its sky, for the matrix and the trip (design: docs/design/trip-matrix/weather.html).

    sky_strip(place, days, asked=None, first=None)  `days` is a weather.TripWeather (best: it carries the forecast's time for MET's credit) or a sequence of
                                                    weather.Day / None, one per day; `asked` = (first, last) marks the days the family asked for in ink
    weather_for(place, first, last) -> TripWeather  weather.trip_weather for a place's name and dates, no trip needed (it can wait on MET: call it from a
                                                    plain `def` handler or run_in_threadpool)

A forecast day is solid, a typical day dotted and labelled "Typical, not a forecast yet", a day GitAway knows nothing about shows its date and nothing
else. Rain and snow are words on the day ("Rain") and a line under the strip ("Tue Nov 23: Rain most of the day · 0.6 in"), never an icon alone.
weather.notes (MET's credit, the NOAA normals line) is always shown under it. Styles: assets/css/skystrip.css; the art: gitaway/placeart.py.
"""

from collections.abc import Sequence
from datetime import date
from types import SimpleNamespace

from fasthtml.common import A, B, Div, Li, NotStr, P, Section, Span, Ul

from gitaway import placeart, weather
from gitaway.icons import icon
from gitaway.pages import weather_ui

TYPICAL = "Typical, not a forecast yet"
NONE = "No weather for this place yet"
WORDS = {"sun": "Sunny", "cloud": "Clouds", "rain": "Rain", "snow": "Snow", "wind": "Windy"}
WET = ("rain", "snow")


def weather_for(place: str, first: date, last: date) -> weather.TripWeather:
    """The weather of a place's days from `first` to `last`, as weather.trip_weather reads it for a trip there."""
    trip = SimpleNamespace(depart=first, return_=last, destination_name=place, key="", focus="", tz="")
    return weather.trip_weather(trip)


def _md(d: date) -> str:
    return f"{d:%b} {d.day}"


def _span(first: date, last: date) -> str:
    """"Dec 20–24", "Nov 28–Dec 2", "Dec 20"."""
    if first == last:
        return _md(first)
    return f"{_md(first)}–{last.day}" if (first.year, first.month) == (last.year, last.month) else f"{_md(first)}–{_md(last)}"


def _tag(known):
    """What the strip's weather is, in words: a forecast, typical weather, where the forecast ends, or nothing."""
    fc = [d for d in known if d.kind == weather.FORECAST]
    if not known:
        return Span(NONE, cls="ss-tag ss-tag-none")
    if len(fc) == len(known):
        return Span(icon("cloud", 14), "Forecast", cls="ss-tag ss-tag-fc")
    if not fc:
        return Span(TYPICAL, cls="ss-tag ss-tag-typ")
    return Span(icon("cloud", 14), f"Forecast to {_md(fc[-1].date)} · then typical", cls="ss-tag ss-tag-fc")


def _day(d: date, wx, asked) -> Li:
    on = " ss-on" if asked and asked[0] <= d <= asked[1] else ""
    head = (Span(f"{d:%a}", cls="ss-dw"), Span(str(d.day), cls="ss-dn"))
    if wx is None:
        return Li(*head, cls=f"ss-day ss-none{on}", aria_label=f"{d:%a} {d.day}: no weather yet")
    kind = "ss-fc" if wx.kind == weather.FORECAST else "ss-typ"
    wet = " ss-wet" if wx.condition in WET else ""
    return Li(*head, icon(wx.condition if wx.condition in WORDS else "cloud", 20, cls="ss-i"),
              Span(f"{wx.high_f}°", Span(f"/{wx.low_f}°"), cls="ss-t"), Span(WORDS.get(wx.condition, ""), cls="ss-w"),
              cls=f"ss-day {kind}{wet}{on}", aria_label=weather_ui.describe(wx), title=wx.word)


def _wet_lines(known):
    """A forecast's wet days, said plainly: "Tue Nov 23: Rain most of the day · 0.6 in"."""
    out = []
    for d in known:
        if d.kind == weather.FORECAST and d.condition in WET:
            amount = f" · {d.precip_in:g} in" if d.precip_in else ""
            out.append(P(icon(d.condition, 18), f"{d.date:%a} {_md(d.date)}: {d.word}{amount}", cls="ss-wetline"))
    return out


def sky_strip(place: str, days, asked: tuple | None = None, first: date | None = None):
    """The strip for `place` (its name as people say it: "Lake Tahoe") over `days` (see the module's doc); `first` dates the days when none of them is
    known (a place without weather). Nothing is drawn that `days` does not say."""
    tw = days if isinstance(days, weather.TripWeather) else weather.TripWeather(tuple(days) if isinstance(days, Sequence) else tuple(days), place=place)
    known = [d for d in tw.days if d]
    dates = _dates(tw.days, first)
    art = placeart.art(place)
    notes = weather_ui.notes(tw, "ss-note", "ss-credit")
    if not tw.updated and any(d.kind == weather.FORECAST for d in known):    # a plain list of days has no forecast time, but the credit still shows
        notes.insert(0, A(f"Forecast for {tw.place or place}, based on data from MET Norway", href=weather.CREDIT_URL, rel="noopener", cls="ss-note ss-credit"))
    title = f"{place} · {_span(dates[0], dates[-1])}" if dates else place
    return Section(
        Div(Div(NotStr(art), cls="ss-art") if art else None, B(title, cls="ss-title"), _tag(known), cls="ss-head"),
        Ul(*(_day(d, wx, asked) for d, wx in zip(dates, tw.days)), cls="ss-days") if dates else None,
        *_wet_lines(known),
        Div(*notes, cls="ss-notes") if notes else None,
        cls="ss-strip", aria_label=f"Weather in {place}")


def _dates(days, first=None) -> list:
    """Each entry's date: from `first`, else from a known day (a None day is dated from its neighbours); with neither there are no dates."""
    known = [(0, first)] if first else [(i, d.date) for i, d in enumerate(days) if d][:1]
    if not known:
        return []
    i0, d0 = known[0]
    return [date.fromordinal(d0.toordinal() + i - i0) for i in range(len(days))]
