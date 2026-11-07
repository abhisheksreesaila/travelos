"""One real MET Norway forecast (F-203): `pixi run probe-weather`.

Asks Locationforecast once for South Lake Tahoe (the founder's Tahoe trip), the way the app does (its User-Agent, four decimals, the station's
altitude), and prints the days GitAway would show, then the typical late-December weather it shows before the forecast opens.
Needs MET_NORWAY_TERMS_ACCEPTED=1: set it only after you have read and accepted https://api.met.no/doc/TermsOfService.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitaway import catalog, weather          # noqa: E402

TAHOE = "USW00093230"


def main() -> int:
    st = weather.station(TAHOE)
    print(f"Typical weather for {st.name} ({weather.NORMALS_CREDIT}):")
    for d in (date(2026, 12, 19), date(2026, 12, 24)):
        n = weather.normal_day(st, d)
        print(f"  {d:%a %b} {d.day}: high {n.high_f}°, low {n.low_f}°, {n.word} ({n.label})")
    if not weather.live():
        print("MET_NORWAY_TERMS_ACCEPTED is not 1, so nothing was asked. Read and accept MET Norway's terms first.")
        return 1
    print("User-Agent:", weather.user_agent())
    fc = weather.forecast(st.lat, st.lon, st.elev, timeout=10)
    if fc is None:
        print("No forecast came back (see the WARNING above, if any).")
        return 2
    print(f"{weather.CREDIT} · updated {weather.updated_text(fc, st.tz)} ({len(fc.points)} steps)")
    for d, day in weather.forecast_days(fc, st.tz, catalog.now_utc()).items():
        extra = f", {len(day.hours)} hourly steps" if day.hours else ""
        print(f"  {d:%a %b} {d.day}: high {day.high_f}°, low {day.low_f}°, {day.word} [{day.condition}], {day.precip_in} in, wind {day.wind_mph} mph{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
