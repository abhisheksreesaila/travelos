"""F-223: the sky strip, a row of days each wearing its sky: the forecast when near, typical weather labelled when far, nothing invented."""
import re
from datetime import date, timedelta
from pathlib import Path

from fasthtml.common import to_xml

from gitaway import weather
from gitaway.pages import skystrip

CSS = (Path(__file__).resolve().parent.parent / "assets" / "css" / "skystrip.css").read_text(encoding="utf-8")
TAHOE = weather.station_named("lake tahoe")


def text(ft):
    return " ".join(re.sub(r"<[^>]+>", " ", to_xml(ft)).split())


def fc(d, condition="cloud", word="Cloudy", precip=None, hi=44, lo=28):
    return weather.Day(d, weather.FORECAST, hi, lo, condition, word, precip_in=precip, wind_mph=8)


def typical(days):
    return weather.TripWeather(tuple(weather.normal_day(TAHOE, d) for d in days), place=TAHOE.name)


DEC = [date(2027, 12, 20) + timedelta(days=i) for i in range(5)]


def test_far_days_say_typical_not_a_forecast_yet_and_show_the_normals_note():
    html = to_xml(skystrip.sky_strip("Lake Tahoe", typical(DEC)))
    words = text(skystrip.sky_strip("Lake Tahoe", typical(DEC)))
    assert "typical, not a forecast yet" in words.lower()
    assert "From NOAA climate normals for" in words                        # weather.notes, shown as it is
    assert html.count('class="ss-day ss-typ') == 5 and "ss-fc" not in html
    hi, lo = weather.normal_day(TAHOE, DEC[0]).high_f, weather.normal_day(TAHOE, DEC[0]).low_f
    assert f"{hi}°" in words and f"{lo}°" in words


def test_rain_is_said_in_words_not_only_an_icon():
    nov = date(2027, 11, 23)
    tw = weather.TripWeather((fc(nov - timedelta(days=1), "sun", "Sunny"), fc(nov, "rain", "Rain most of the day", 0.6)), place="South Lake Tahoe", updated="6:10 AM")
    html, words = to_xml(skystrip.sky_strip("Lake Tahoe", tw)), text(skystrip.sky_strip("Lake Tahoe", tw))
    rainy = re.search(r'<li [^>]*class="ss-day ss-fc ss-wet[^"]*"[^>]*>(.*?)</li>', html, re.S).group(1)
    assert "Rain" in re.sub(r"<[^>]+>", " ", rainy)
    assert "Tue Nov 23: Rain most of the day · 0.6 in" in words
    assert "based on data from MET Norway" in words and weather.CREDIT_URL in html  # the credit, wherever a forecast shows


def test_a_mix_says_where_the_forecast_ends():
    days = [date(2027, 11, 21) + timedelta(days=i) for i in range(4)]
    tw = weather.TripWeather((fc(days[0]), fc(days[1]), weather.normal_day(TAHOE, days[2]), weather.normal_day(TAHOE, days[3])), place=TAHOE.name, updated="6:10 AM")
    assert "Forecast to Nov 22 · then typical" in text(skystrip.sky_strip("Lake Tahoe", tw))


def test_a_place_without_weather_shows_its_days_and_invents_nothing():
    tw = weather.TripWeather((None, None, None))
    html, words = to_xml(skystrip.sky_strip("Boise", tw, first=DEC[0])), text(skystrip.sky_strip("Boise", tw, first=DEC[0]))
    assert "No weather for this place yet" in words
    assert "°" not in words and "<svg" not in html.split("ss-days")[1]        # no number and no sky drawn on a day
    assert html.count('class="ss-day ss-none') == 3 and "Boise · Dec 20–22" in words
    assert "ss-day" not in to_xml(skystrip.sky_strip("Boise", tw))               # no dates given: the line alone


def test_a_plain_list_of_days_works_and_still_credits_a_forecast():
    d = date(2027, 11, 21)
    words = text(skystrip.sky_strip("Lake Tahoe", [fc(d), None]))
    assert "MET Norway" in words and "Sun 21" in words.replace("Sun  21", "Sun 21")


def test_every_day_reads_whole_to_a_screen_reader():
    html = to_xml(skystrip.sky_strip("Lake Tahoe", typical(DEC[:1])))
    assert re.search(r'aria-label="Mon 20: high \d+°, low \d+°, typical, not a forecast"', html)


def test_the_place_wears_its_art_when_it_has_some():
    assert "pa-svg" in to_xml(skystrip.sky_strip("Lake Tahoe", typical(DEC)))
    assert "pa-svg" not in to_xml(skystrip.sky_strip("Boise", weather.TripWeather((None,))))


def test_weather_for_a_place_and_dates_reads_the_real_tables():
    far = skystrip.weather_for("Lake Tahoe", DEC[0], DEC[-1])
    assert len(far.days) == 5 and all(d.kind == weather.NORMAL for d in far.days)
    assert skystrip.weather_for("Nowhereville", DEC[0], DEC[-1]).days == (None,) * 5


def test_the_stylesheet_uses_only_tokens_floors_and_motion_tokens():
    code = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\d", code), "colours are tokens"
    assert not re.search(r"(?<![\w.-])\d*\.?\d+m?s\b", code), "times are --motion-* tokens"
    for m in re.finditer(r"font(?:-size)?:[^;]*?(\d*\.?\d+)rem", code):
        assert "max(var(--text-min)" in m.group(0) or "max(var(--label-min)" in m.group(0) or float(m.group(1)) * 16 >= 16, m.group(0)
    assert "prefers-reduced-motion" in code and "border-style: dashed" in code
