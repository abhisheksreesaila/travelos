"""What the journey view knows (F-300, docs/briefs/journey.md): the trip as a road you scroll along. Plain functions, no framework; the page (gitaway/pages/planv2.py) sends their answer as JSON
and assets/js/v2journey.js draws it.

    data(v, t, *, tz, edit) -> dict          the whole road: the days (with the sun and the day's sky), every event (booked ones locked), the stay, the hours of weather, the place's colour
    suns(dates, where) -> [(rise, set) | None]    the sun of each date at the place's weather station, local minutes
    forecast_points(t, where) -> [dict]     MET Norway's steps over the trip, in the place's time

Time on the road is one number: minutes from midnight of the trip's first day (`day * 1440 + minutes into the day`), the place's own time, so the script never meets a time zone.
Nothing is invented: a day's sky is weather.py's (a forecast, typical weather labelled so, or nothing), the hours are MET's own steps and exist only where MET reaches (never for typical days, never
for the showcase's sample trip), and the sun is computed (gitaway/sun.py) only where there is a station to say where the place is.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from gitaway import catalog, placecolor, sun, weather

DAY = 1440
KINDS = {"snow": "snow", "sleet": "snow", "rain": "rain"}        # weather.symbol_kind families that fall: sleet is drawn as snow


def suns(dates, where) -> list:
    """The sun of each date, (rise, set) in local minutes, or None where there is no station to place the trip (or the sun does not rise or set)."""
    st = where.station if where else None
    return [sun.times(st.lat, st.lon, d, where.tz) if st else None for d in dates]


def forecast_points(t, where) -> list:
    """MET's forecast steps that fall on the trip's days, in the place's time: [{"t": minutes from the first day's midnight, "h": hours the step covers, "f": deg F, "c": cloud %, "p": mm an hour,
    "s": "snow" | "rain" | ""}]. Empty when there is no real forecast: no place, MET not asked or silent, a trip too far off (typical days have no hours), or the showcase's sample trip."""
    if where is None or weather.sample(t):
        return []
    dates = [t.depart + timedelta(days=i) for i in range((t.return_ - t.depart).days + 1)]
    today = catalog.today_in(where.tz)
    if not any(today <= d <= today + weather.REACH for d in dates):
        return []
    fc = weather.forecast(where.station)
    if fc is None:
        return []
    zone, out = ZoneInfo(where.tz), []
    for p in fc.points:
        if p.hours not in (1, 6):
            continue
        local = p.at.astimezone(zone)
        day = (local.date() - t.depart).days
        if not 0 <= day < len(dates):
            continue
        out.append({"t": day * DAY + local.hour * 60 + local.minute, "h": p.hours, "f": None if p.temp_c is None else weather.fahrenheit(p.temp_c), "c": p.cloud,
                    "p": round(p.precip_mm / p.hours, 2), "s": KINDS.get(weather.symbol_kind(p.symbol), "")})
    return out


def _wx(w):
    if not w.cond:
        return None
    return {"hi": w.hi, "lo": w.lo, "word": w.word, "cond": w.cond, "typical": w.typical, "sample": w.sample, "label": w.label}


def _event(e):
    return {"id": e.id, "day": e.day, "start": e.start, "end": e.end, "title": e.title, "kind": e.kind, "locked": e.locked, "href": e.href, "by": e.by, "tag": e.tag}


def _stay(booked):
    stays = sorted((e for e in booked if e.kind == "stay"), key=lambda e: (e.day, e.start))
    if not stays:
        return None
    a, b = stays[0], stays[-1]
    name = a.title.removeprefix("Check in · ").split(" · ")[0]
    first, last = a.day * DAY + a.start, (b.day * DAY + b.start) if b is not a else a.day * DAY + a.end
    return {"name": name, "from": first, "to": last, "nights": b.day - a.day, "href": a.href}


def _range(events, days):
    """Where the road starts and ends: an hour before the first thing (but not after 6 AM of the first day) and an hour after the last (but not before 10 PM of the last), on the hour."""
    first = min((e.day * DAY + e.start for e in events), default=6 * 60)
    last = max((e.day * DAY + e.end for e in events), default=22 * 60)
    lo = max(0, min(6 * 60, (first - 60) // 60 * 60))
    hi = min(days * DAY, max((days - 1) * DAY + 22 * 60, -(-(last + 60) // 60) * 60))
    return [lo, hi]


def _now(t, tz):
    at = catalog.now_utc().astimezone(ZoneInfo(tz))
    day = (at.date() - t.depart).days
    return day * DAY + at.hour * 60 + at.minute if 0 <= day <= (t.return_ - t.depart).days else None


def data(v, t, *, tz, edit) -> dict:
    """The road for view `v` of trip `t`; `tz` is the trip's zone where the place has no weather station (the station's own zone says what "now" is otherwise), `edit` whether this person may write."""
    where = weather.where(t)
    dates = [d for _, d in v.days]
    sun_of = suns(dates, where)
    days = [{"i": i, "label": f"{d.strftime('%a')} {d.day}", "date": d.isoformat(), "sun": list(s) if s else None, "wx": _wx(v.sky[i])} for (i, d), s in zip(v.days, sun_of)]
    return {"title": v.title, "dates": v.dates, "place": v.place, "pc": placecolor.of(v.place)[0], "days": days, "events": [_event(e) for e in v.events], "stay": _stay(v.booked),
            "range": _range(v.events, len(days)), "points": forecast_points(t, where), "now": _now(t, where.tz if where else tz), "edit": bool(edit),
            "notes": [[text, link] for text, link in v.sky_notes]}
