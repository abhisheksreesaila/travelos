"""The weather each day of a trip shows (F-201), behind one small interface so the screens never care where it comes from.

    days(trip) -> [DayWx]    one per trip day, departure to return

A real trip never shows invented weather (F-201 review): with the showcase off (production) a trip that is not the sample gets `NO_CLAIM` for every day, a
plain sky with no number and no words, until F-203's forecasts and climate normals (gitaway/weather.py: `trip_weather`, `notes`) plug in here at merge,
replacing `source()`. On the showcase, and for the sample trip, it is the app's existing per-day sample weather (gitaway.context.weather_for), and every
DayWx says so (`sample` True, `source` "Sample weather"). The cockpit's living skies (assets/js/wx.js) read `kind`, `gust` and `ground`, the words read
`word`, `hi`, `lo` and `source`.
"""

from dataclasses import dataclass

from gitaway import context, showcase

KINDS = ("sun", "cloud", "snow", "flurry", "wind", "plain")      # what the living sky can draw (assets/js/wx.js TYPES); "plain" claims nothing


@dataclass(frozen=True)
class DayWx:
    hi: int | None          # degrees F; None when nothing is known
    lo: int | None
    word: str               # "Sunny", "Some clouds", "Snow, 6-9 in"; "" when nothing is known
    kind: str               # one of KINDS
    gust: int = 0           # mph; a windy day leans the pines
    ground: float = 0.0     # 0 to 1: snow already lying (it stays after a snowy day)
    source: str = "Sample weather"
    sample: bool = True     # invented, not a forecast: the screens say so


NO_CLAIM = DayWx(hi=None, lo=None, word="", kind="plain", source="", sample=False)      # a plain sky: no number, no words, no weather drawn


def is_sample(trip) -> bool:
    """The sample trip (the catalog's Los Angeles days), whose weather is part of the sample."""
    return context._is_sample(trip)


def _kind(w) -> str:
    sky = w.sky.lower()
    if "snow" in sky:
        return "flurry" if "light" in sky or "flurr" in sky else "snow"
    if "wind" in sky or "breez" in sky:
        return "wind"
    return "cloud" if w.icon == "cloud" else "sun"


def source(trip) -> list:
    """The sample weather for each day (the showcase and the sample trip only). F-203 replaces this with real forecasts and climate normals."""
    out = []
    for w in context.weather_for(trip):
        kind = _kind(w)
        out.append(DayWx(hi=w.temp_f, lo=w.temp_f - 12, word=w.sky[:1].upper() + w.sky[1:], kind=kind, gust=18 if kind == "wind" else 0))
    return out


def days(trip) -> list:
    """One DayWx per day of the trip (a long trip repeats the last known day rather than run out); NO_CLAIM for each day of a real trip off the showcase."""
    n = (trip.return_ - trip.depart).days + 1
    if not showcase.on() and not is_sample(trip):
        return [NO_CLAIM] * n
    got = source(trip) or [NO_CLAIM]
    return [got[i] if i < len(got) else got[-1] for i in range(n)]
