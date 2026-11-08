"""The weather each day of a trip shows (F-201), behind one small interface so the screens never care where it comes from.

    days(trip) -> [DayWx]    one per trip day, departure to return
    notes(trip) -> [(text, link or "")]    what a page must say under that weather (F-203: MET's credit, the typical-weather labels)

Since the merge with F-203 the days come from gitaway/weather.py: MET Norway's forecast where it reaches (`source` "Forecast · MET Norway"), else the place's
typical weather from NOAA climate normals, labelled "not a forecast yet" (`source` is that label), else `NO_CLAIM`, a plain sky with no number and no words.
Nothing is invented on a real trip, on the showcase or off it: only the showcase's own sample trip (`weather.sample`) shows the app's sample weather
(gitaway.context.WEATHER), and every such DayWx says so (`sample` True, `source` "Sample weather"). The cockpit's living skies (assets/js/wx.js) read
`kind`, `gust` and `ground`, the words read `word`, `hi`, `lo` and `source`. `weather.trip_weather` can wait on MET: call this from a plain `def` handler.
"""

from dataclasses import dataclass

from gitaway import context, weather

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
    """The showcase's own sample trip, whose weather is part of the sample (F-203's rule: never on the live site, never an imported trip)."""
    return weather.sample(trip)


def _sample_kind(w) -> str:
    sky = w.sky.lower()
    if "snow" in sky:
        return "flurry" if "light" in sky or "flurr" in sky else "snow"
    if "wind" in sky or "breez" in sky:
        return "wind"
    return "cloud" if w.icon == "cloud" else "sun"


def _kind(d) -> str:
    """A weather.Day's condition (sun, cloud, rain, snow, wind) as a sky wx.js can draw; rain has no sky of its own, so it is cloud."""
    if d.condition == "snow":
        return "flurry" if "light" in d.word.lower() else "snow"
    return {"sun": "sun", "wind": "wind"}.get(d.condition, "cloud")


def _day(d) -> DayWx:
    if d is None:
        return NO_CLAIM
    if d.kind == weather.NORMAL:
        return DayWx(hi=d.high_f, lo=d.low_f, word="Typical", kind=_kind(d), source=d.label or "Typical · not a forecast yet", sample=False)
    return DayWx(hi=d.high_f, lo=d.low_f, word=d.word, kind=_kind(d), gust=d.wind_mph or 0, source="Forecast · MET Norway", sample=False)


def source(trip) -> list:
    """Each day's weather: the sample trip's sample weather, else F-203's forecast or typical weather (None days claim nothing)."""
    if is_sample(trip):
        out = []
        for w in context.WEATHER:
            kind = _sample_kind(w)
            out.append(DayWx(hi=w.temp_f, lo=w.temp_f - 12, word=w.sky[:1].upper() + w.sky[1:], kind=kind, gust=18 if kind == "wind" else 0))
        return out
    return [_day(d) for d in weather.trip_weather(trip).days]


def notes(trip) -> list:
    """The lines a page shows under this weather (weather.notes: MET's credit with its link, the typical-weather labels); none for the sample trip,
    whose "Sample weather" chip says it."""
    return [] if is_sample(trip) else weather.notes(weather.trip_weather(trip))


def days(trip) -> list:
    """One DayWx per day of the trip (a long trip repeats the last known day rather than run out)."""
    n = (trip.return_ - trip.depart).days + 1
    got = source(trip) or [NO_CLAIM]
    return [got[i] if i < len(got) else got[-1] for i in range(n)]
