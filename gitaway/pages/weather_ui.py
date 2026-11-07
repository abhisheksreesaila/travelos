"""How a page shows a trip's weather (F-203): a day's icon and tint, and the lines under it (gitaway/weather.py `notes`): MET Norway's credit, linked
to their licence page, wherever a forecast shows, and the "Typical late December · not a forecast yet" label wherever typical weather shows."""

from fasthtml.common import A, Span

from gitaway import weather

_ICONS = {"sun": "sun", "cloud": "cloud", "rain": "rain", "snow": "snow", "wind": "wind"}


def icon_name(day) -> str:
    return _ICONS.get(day.condition, "cloud")


def tint(day) -> str:
    """Colour means a kind, never a day: the sun's tint on a sunny day, the weather blue on every other."""
    return "sun" if day.condition == "sun" else "sky"


def describe(day) -> str:
    """The day in words for a screen reader (and a title): "Sat 19: high 42°, low 18°, typical, not a forecast"."""
    what = "typical, not a forecast" if day.kind == weather.NORMAL else day.word
    return f"{day.date:%a} {day.date.day}: high {day.high_f}°, low {day.low_f}°, {what}"


def notes(tw, cls):
    """The lines under a trip's weather, as Spans with class `cls`; the source's name links its licence page."""
    out = []
    for text, href in weather.notes(tw):
        if href and "MET Norway" in text:
            before, after = text.split("MET Norway", 1)
            out.append(Span(before, A("MET Norway", href=href, rel="noopener"), after, cls=cls))
        else:
            out.append(Span(text, cls=cls))
    return out
