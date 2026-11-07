"""A MET Norway Locationforecast 2.0 compact answer for the founder's Tahoe trip (F-203), built from a small weather story, and a fake transport.

The shape follows MET's documentation (docs.api.met.no/doc/ForecastJSON and doc/locationforecast/datamodel): a GeoJSON Feature whose
properties.timeseries is sorted by time, in UTC; hourly steps (instant + next_1_hours + next_6_hours + next_12_hours) for the first 64 hours,
then six-hour steps at 00, 06, 12 and 18 UTC (instant + next_6_hours + next_12_hours), and the last step has an instant only.

The story, in South Lake Tahoe's own time (PST, UTC-8), with the forecast made Thu Dec 17 2026 at 6:10 AM: each day's low is at 6 AM and its high
at 3 PM, with straight lines between, so a day's low and high are exactly the numbers in TEMPS.
"""

import gzip
import json
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from zoneinfo import ZoneInfo

PST = ZoneInfo("America/Los_Angeles")
UPDATED = datetime(2026, 12, 17, 14, 10, tzinfo=timezone.utc)   # 6:10 AM in Tahoe
FIRST = datetime(2026, 12, 17, 14, tzinfo=timezone.utc)         # the first step: 6 AM Dec 17 in Tahoe
HOURLY_LAST = datetime(2026, 12, 20, 5, tzinfo=timezone.utc)    # the last hourly step: 9 PM Dec 19 in Tahoe
LAST = datetime(2026, 12, 26, 18, tzinfo=timezone.utc)          # the last step (no period): 10 AM Dec 26 in Tahoe
NOW = datetime(2026, 12, 17, 14, 30, tzinfo=timezone.utc)       # when the tests look: 6:30 AM Dec 17 in Tahoe

# local day of December -> (high C, low C)
TEMPS = {16: (3, -10), 17: (4, -9), 18: (2, -6), 19: (-1, -7), 20: (0, -12), 21: (3, -13), 22: (5, -8), 23: (6, 2), 24: (4, -1), 25: (0, -6),
         26: (2, -9), 27: (3, -8)}
# what the tests expect each covered local day to read, deg F (rounded) and words
EXPECT = {
    17: (39, 16, "sun", "Sunny"),
    18: (36, 21, "cloud", "Partly cloudy, snow late"),
    19: (30, 19, "snow", "Heavy snow"),
    20: (32, 10, "sun", "Mostly sunny, snow early"),
    21: (37, 9, "sun", "Sunny"),
    22: (41, 18, "wind", "Windy"),
    23: (43, 36, "rain", "Rain"),
    24: (39, 30, "cloud", "Cloudy, snow late"),     # the 10 PM-4 AM period's snow falls after midnight in the story, but a six-hour step cannot say when
    25: (32, 21, "snow", "Snow"),
}
_RANK = ("clearsky", "fair", "partlycloudy", "cloudy", "rain", "lightsnowshowers", "lightsnow", "snow", "heavysnow")
_VARIANTS = {"clearsky", "fair", "partlycloudy", "lightsnowshowers"}     # the symbols MET gives _day and _night versions of


def _temp(local: datetime) -> float:
    """The story's temperature at a local time: straight lines through each day's low at 6 AM and high at 3 PM."""
    day, h = local.day, local.hour + local.minute / 60
    hi, lo = TEMPS[day]
    if 6 <= h <= 15:
        return lo + (hi - lo) * (h - 6) / 9
    if h > 15:
        nxt = TEMPS[day + 1][1]
        return hi + (nxt - hi) * (h - 15) / 15
    prev_hi = TEMPS[day - 1][0]
    return prev_hi + (lo - prev_hi) * (h + 9) / 15


def _sky(local: datetime):
    """(symbol, mm of precipitation in that hour, cloud %, wind m/s) for the hour starting at `local`."""
    d, h = local.day, local.hour
    if d == 17:
        return "clearsky", 0.0, 5, 2.0
    if d == 18:
        return (("fair", 0.0, 20, 4.0) if h < 11 else ("partlycloudy", 0.0, 50, 4.0) if h < 19 else ("cloudy", 0.0, 90, 4.0) if h == 19
                else ("lightsnow", 0.3, 100, 4.0))
    if d == 19:
        return ("lightsnow", 0.5, 100, 7.0) if h < 3 else ("heavysnow", 2.0, 100, 7.0) if h < 17 else ("snow", 0.8, 100, 7.0)
    if d == 20:
        return ("lightsnowshowers", 0.1, 70, 3.0) if h < 6 else ("fair", 0.0, 15, 3.0)
    if d == 21:
        return "clearsky", 0.0, 0, 2.0
    if d == 22:
        return "partlycloudy", 0.0, 40, 11.0 if 7 <= h < 19 else 6.0
    if d == 23:
        return "rain", 0.3, 100, 5.0
    if d == 24:
        return "cloudy", 0.0, 95, 3.0
    if d == 25:
        return "snow", 0.4, 100, 4.0
    return "fair", 0.0, 20, 3.0


def _code(symbol: str, local_hour: int) -> str:
    return f"{symbol}_{'day' if 7 <= local_hour < 17 else 'night'}" if symbol in _VARIANTS else symbol


def _period(start_utc: datetime, hours: int) -> dict:
    local = [(start_utc + timedelta(hours=k)).astimezone(PST) for k in range(hours)]
    skies = [_sky(t) for t in local]
    worst = max((s[0] for s in skies), key=_RANK.index)
    out = {"summary": {"symbol_code": _code(worst, local[hours // 2].hour)}, "details": {"precipitation_amount": round(sum(s[1] for s in skies), 1)}}
    if hours == 6:
        temps = [_temp(t) for t in local]
        out["details"].update(air_temperature_max=round(max(temps), 1), air_temperature_min=round(min(temps), 1))
    return out


def _step(at: datetime, hourly: bool, last: bool) -> dict:
    local = at.astimezone(PST)
    sym, _mm, cloud, wind = _sky(local)
    data = {"instant": {"details": {"air_pressure_at_sea_level": 1018.2, "air_temperature": round(_temp(local), 1), "cloud_area_fraction": float(cloud),
                                    "relative_humidity": 74.0, "wind_from_direction": 225.0, "wind_speed": wind}}}
    if not last:
        if hourly:
            data["next_1_hours"] = _period(at, 1)
        data["next_6_hours"] = _period(at, 6)
        data["next_12_hours"] = {"summary": {"symbol_code": _period(at, 12)["summary"]["symbol_code"]}, "details": {}}
    return {"time": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data}


def compact(lat=38.9399, lon=-119.9772, altitude=1925) -> dict:
    steps, at = [], FIRST
    while at <= HOURLY_LAST:
        steps.append(_step(at, True, False))
        at += timedelta(hours=1)
    at = HOURLY_LAST + timedelta(hours=1)
    while at.hour % 6:
        at += timedelta(hours=1)
    while at <= LAST:
        steps.append(_step(at, False, at == LAST))
        at += timedelta(hours=6)
    units = {"air_pressure_at_sea_level": "hPa", "air_temperature": "celsius", "air_temperature_max": "celsius", "air_temperature_min": "celsius",
             "cloud_area_fraction": "%", "precipitation_amount": "mm", "relative_humidity": "%", "wind_from_direction": "degrees", "wind_speed": "m/s"}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat, altitude]},
            "properties": {"meta": {"updated_at": UPDATED.strftime("%Y-%m-%dT%H:%M:%SZ"), "units": units}, "timeseries": steps}}


def http_date(at: datetime) -> str:
    return format_datetime(at.astimezone(timezone.utc), usegmt=True)


def headers(expires=UPDATED + timedelta(minutes=33), modified=UPDATED, gz=False) -> dict:
    h = {"content-type": "application/json", "expires": http_date(expires), "last-modified": http_date(modified)}
    if gz:
        h["content-encoding"] = "gzip"
    return h


def body(doc=None, gz=False) -> bytes:
    raw = json.dumps(doc or compact()).encode()
    return gzip.compress(raw) if gz else raw


class Met:
    """A fake `weather.TRANSPORT`: answers from a queue of (status, headers, body) and records every call (url, headers)."""

    def __init__(self, *answers):
        self.answers = list(answers) or [(200, headers(), body())]
        self.calls = []

    def __call__(self, url, hdrs, timeout):
        self.calls.append((url, dict(hdrs)))
        status, h, b = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(status, Exception):
            raise status
        return status, h, b


def tahoe_dates():
    return [date(2026, 12, d) for d in range(19, 27)]


# ---- a local stand-in for api.met.no's socket (F-203 review): the transport is pointed at it through weather.CONNECTION ----------

import http.server       # noqa: E402
import socket            # noqa: E402
import threading         # noqa: E402
import time as _time     # noqa: E402


class Server:
    """A plain-HTTP server on 127.0.0.1 that answers every request one way (`mode`): "redirect" (302 to the cloud's metadata address), "slow" (headers,
    then a byte every 0.3 s for 6 s), "not-modified" (304, no body: what MET answers an If-Modified-Since when nothing changed) or "ok". `hits` counts
    the requests it got, `asked` keeps each request's headers."""

    def __init__(self, mode="ok"):
        outer = self
        self.mode, self.hits, self.asked = mode, 0, []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                outer.hits += 1
                outer.asked.append({k.lower(): v for k, v in self.headers.items()})
                if outer.mode == "not-modified":
                    self.send_response(304)
                    self.send_header("Expires", http_date(NOW + timedelta(hours=9)))
                    self.send_header("Last-Modified", http_date(UPDATED))
                    self.end_headers()
                    return
                if outer.mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://169.254.169.254/latest/meta-data/iam/credentials")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                raw = body()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Expires", http_date(UPDATED + timedelta(minutes=33)))
                self.send_header("Last-Modified", http_date(UPDATED))
                self.end_headers()
                if outer.mode == "slow":
                    try:
                        for b in raw[:20]:
                            self.wfile.write(bytes([b]))
                            self.wfile.flush()
                            _time.sleep(0.3)
                    except OSError:
                        pass
                    return
                self.wfile.write(raw)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def connection(self, ips, deadline):
        """Stands in for weather.CONNECTION: a plain connection to this server, whatever addresses were looked up."""
        import http.client
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=max(0.1, deadline - _time.monotonic()))

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def local_only(monkeypatch):
    """No socket may leave this machine during the test: anything but 127.0.0.1 is refused before any lookup."""
    real = socket.create_connection

    def guarded(address, *a, **kw):
        if address[0] != "127.0.0.1":
            raise OSError(f"the network is off in tests ({address[0]})")
        return real(address, *a, **kw)
    monkeypatch.setattr(socket, "create_connection", guarded)
