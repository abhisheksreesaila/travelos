"""Sunrise and sunset for a place and a date (F-300), NOAA's solar equations (the "General Solar Position Calculations" spreadsheet), good to a few minutes between 60 degrees north and south. Nothing is fetched.

    times(lat, lon, day, tz) -> (rise, set) | None    local minutes after midnight, or None where the sun does not rise or does not set that day (polar night, midnight sun)
"""

import math
from datetime import datetime, time
from zoneinfo import ZoneInfo


def times(lat, lon, day, tz):
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)       # the fractional year at noon, in radians (the day's own hour changes the answer by seconds)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    c = math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl)) - math.tan(la) * math.tan(decl)
    if not -1 <= c <= 1:
        return None
    ha = math.degrees(math.acos(c))
    offset = ZoneInfo(tz).utcoffset(datetime.combine(day, time(12))).total_seconds() / 60      # the zone's offset that day (daylight time included)
    rise, set_ = 720 - 4 * (lon + ha) - eqtime + offset, 720 - 4 * (lon - ha) - eqtime + offset
    return round(rise), round(set_)
