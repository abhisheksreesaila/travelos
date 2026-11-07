"""The weather each day of a trip shows (F-201), behind one small interface so the screens never care where it comes from.

    days(trip) -> [DayWx]    one per trip day, departure to return

Today it is the app's existing per-day weather (gitaway.context.weather_for: invented from each date, the sample trip's own for the sample trip), and every
DayWx says so (`sample` True, `source` "Sample weather"). F-203 (gitaway/weather.py: MET Norway forecasts, climate normals before the forecast window)
replaces `source()` and nothing else changes: the cockpit's living skies (assets/js/wx.js) read `kind`, `gust` and `ground`, the words read `word`, `hi`, `lo`
and `source`.
"""

from dataclasses import dataclass

from gitaway import context

KINDS = ("sun", "cloud", "snow", "flurry", "wind")      # what the living sky can draw (assets/js/wx.js TYPES)


@dataclass(frozen=True)
class DayWx:
    hi: int                 # degrees F
    lo: int
    word: str               # "Sunny", "Some clouds", "Snow, 6-9 in"
    kind: str               # one of KINDS
    gust: int = 0           # mph; a windy day leans the pines
    ground: float = 0.0     # 0 to 1: snow already lying (it stays after a snowy day)
    source: str = "Sample weather"
    sample: bool = True     # invented, not a forecast: the screens say so


def _kind(w) -> str:
    sky = w.sky.lower()
    if "snow" in sky:
        return "flurry" if "light" in sky or "flurr" in sky else "snow"
    if "wind" in sky or "breez" in sky:
        return "wind"
    return "cloud" if w.icon == "cloud" else "sun"


def source(trip) -> list:
    """The weather for each day, from where it comes today. F-203 replaces this one function."""
    out = []
    for w in context.weather_for(trip):
        kind = _kind(w)
        out.append(DayWx(hi=w.temp_f, lo=w.temp_f - 12, word=w.sky[:1].upper() + w.sky[1:], kind=kind, gust=18 if kind == "wind" else 0))
    return out


def days(trip) -> list:
    """One DayWx per day of the trip (a long trip repeats the last known day rather than run out)."""
    got = source(trip) or [DayWx(hi=0, lo=0, word="", kind="sun")]
    n = (trip.return_ - trip.depart).days + 1
    return [got[i] if i < len(got) else got[-1] for i in range(n)]
