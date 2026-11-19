"""F-300: My trip as a journey. What the page sends the road (gitaway/journey.py) and the sun's own times (gitaway/sun.py)."""

import json
import re
from datetime import date

import pytest

from gitaway import sun, weather
from tests.test_calendar import add, book
from tests.test_signin import person


def hm(m):
    return f"{m // 60}:{m % 60:02d}"


# ---- the sun ----------------------------------------------------------------------------------------------------------------

def test_south_lake_tahoe_in_december_rises_about_7_12_and_sets_about_4_40():
    """Almanac values for Tahoe on Dec 18 (Reno, 0.2 degrees east, is 7:09 and 4:39 on a flat horizon; the mountains are not counted)."""
    st = weather.station("USW00093230")
    rise, set_ = sun.times(st.lat, st.lon, date(2026, 12, 18), st.tz)
    assert abs(rise - (7 * 60 + 12)) <= 4 and abs(set_ - (16 * 60 + 40)) <= 4, (hm(rise), hm(set_))


def test_the_sun_is_local_time_and_summer_days_are_longer_than_winter_ones():
    st = weather.station("USW00093230")
    winter = sun.times(st.lat, st.lon, date(2026, 12, 18), st.tz)
    summer = sun.times(st.lat, st.lon, date(2026, 6, 21), st.tz)
    assert summer[1] - summer[0] > winter[1] - winter[0] + 5 * 60
    assert abs(summer[0] - (5 * 60 + 40)) <= 6 and abs(summer[1] - (20 * 60 + 25)) <= 6, (hm(summer[0]), hm(summer[1]))      # PDT in June


def test_polar_night_has_no_sunrise():
    assert sun.times(78.2, 15.6, date(2026, 12, 18), "Arctic/Longyearbyen") is None
