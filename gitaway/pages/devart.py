"""GET /dev/placeart (F-223): every place's art by day (it follows the mode) and by night, the four weather layers, and sky strips in their three
states, for a designer's eye. Showcase only: /dev is in showcase.HIDDEN, so it 404s in production."""

from datetime import date, timedelta

from fasthtml.common import Div, H1, H2, Link, NotStr, P, Section, Span

from gitaway import placeart, weather
from gitaway.layout import page
from gitaway.pages import skystrip

HEAD = (Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/skystrip.css"),
        Link(rel="stylesheet", href="/assets/css/devart.css"))


def _tile(svg, label):
    return Div(Div(NotStr(svg), cls="da-art"), Span(label, cls="da-cap"), cls="da-tile")


def _strips():
    """Sample strips, labelled so: a far trip's typical days (real NOAA normals) and a place with nothing. No forecast is shown, since none is invented."""
    first = date.today() + timedelta(days=60)
    tahoe = weather.station_named("lake tahoe")
    typical = weather.TripWeather(tuple(weather.normal_day(tahoe, first + timedelta(days=i)) for i in range(7)), place=tahoe.name)
    return (skystrip.sky_strip("Lake Tahoe", typical, asked=(first + timedelta(days=2), first + timedelta(days=5))),
            skystrip.sky_strip("Boise", weather.TripWeather((None,) * 5), first=first))


def register(app):
    @app.get("/dev/placeart")
    def dev_placeart():
        rows = [Section(H2(f"{placeart.name(s)} · {placeart.kind(s)}"),
                        Div(_tile(placeart.art(s), "Day (follows the mode)"), _tile(placeart.art(s, night=True), "Night"), cls="da-row"), cls="da-place")
                for s in placeart.SLUGS]
        wx = Section(H2("Weather layer"), Div(*(_tile(placeart.art("laketahoe", wx=w), w) for w in placeart.WX), cls="da-row"), cls="da-place")
        return page("Place art", H1("Place art"), P("F-223 preview, showcase only. Switch Light and Dark to see each day drawing turn to night."),
                    wx, *rows, Section(H2("Sky strips"), *_strips(), cls="da-strips"), head=HEAD, noindex=True)
