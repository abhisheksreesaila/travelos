"""How a page shows a trip's weather (F-203): a day's tint and words, and the lines under it (gitaway/weather.py `notes`): MET Norway's credit, a link
as a whole line to their licence page, wherever a forecast shows, and the "Typical late December · not a forecast yet" label wherever typical
weather shows. A day's icon is its condition (sun, cloud, rain, snow, wind are all gitaway.icons names)."""

from fasthtml.common import A, Span

from gitaway import weather


def tint(day) -> str:
    """Colour means a kind, never a day: the sun's tint on a sunny day, the weather blue on every other."""
    return "sun" if day.condition == "sun" else "sky"


def describe(day) -> str:
    """The day in words for a screen reader (and a title): "Sat 19: high 42°, low 18°, typical, not a forecast"."""
    what = "typical, not a forecast" if day.kind == weather.NORMAL else day.word
    return f"{day.date:%a} {day.date.day}: high {day.high_f}°, low {day.low_f}°, {what}"


def notes(tw, cls, link_cls):
    """The lines under a trip's weather as elements of class `cls`; a line with a link (MET's credit) is one link, the whole line, with `link_cls` too,
    so on a phone the whole line is the tap target."""
    return [A(text, href=href, rel="noopener", cls=f"{cls} {link_cls}") if href else Span(text, cls=cls) for text, href in weather.notes(tw)]
