"""Build gitaway/normals.json from NOAA's U.S. Climate Normals, 1991-2020 (F-203): `pixi run build-normals [cache folder]`.

NOAA's normals are public domain (a work of the U.S. Government; NCEI asks only that the source be cited). For each station below this downloads
its daily normals once into the cache folder (https://www.ncei.noaa.gov/data/normals-daily/1991-2020/access/<station>.csv) and keeps, for each
third of a month (days 1-10, 11-20, 21 to the end: "early", "mid" and "late"), the mean of:

  - the normal daily high and low (deg F),
  - the chance that a day has at least 0.01 in of precipitation (%, DLY-PRCP-PCTALL-GE001HI),
  - where the station measures snow, the chance of at least 0.1 in of snowfall (%, DLY-SNOW-PCTALL-GE001TI), else null.

The app reads only the JSON (gitaway/weather.py); nothing is fetched while it runs. Add a destination by adding a row: the station id is in
https://www.ncei.noaa.gov/data/normals-daily/1991-2020/doc/inventory_30yr.txt. A name counts only at the start of a trip's destination, as whole
words, and only when every part after it is a state the station stands for, the United States, or another of its names (so "Lake Placid, New York"
is not New York City, "Hollywood Florida" is not Los Angeles and "Disneyland Paris, France" is not Anaheim); still never add a name that is also a
different place on its own (a bare "portland", "charleston", "mammoth" or "disneyland"). The states are the postal codes a station stands for. Park City and Mammoth Lakes are left out on purpose: their own stations have no temperature or precipitation
normals and the nearest ones that do sit hundreds of metres lower.

The downloads are kept in a folder only you can read (~/.cache/gitaway-normals, mode 0700, or one you name that no one else can write to), each
read and written without following a link, and at most 5 MB each. A file whose coordinates are impossible is refused.
"""

import csv
import io
import json
import math
import os
import stat
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gitaway.weather import third     # noqa: E402 - the one rule for the thirds of a month, shared with the app that reads the table
OUT = ROOT / "gitaway" / "normals.json"
URL = "https://www.ncei.noaa.gov/data/normals-daily/1991-2020/access/{id}.csv"
USER_AGENT = "GitAway normals builder (+https://gitaway.me)"
MAX_BYTES = 5 * 1024 * 1024      # a station's daily normals file is under 1 MB

PT, MT, AZ, CT, ET, HT, AK = ("America/Los_Angeles", "America/Denver", "America/Phoenix", "America/Chicago", "America/New_York", "Pacific/Honolulu",
                              "America/Anchorage")

# (station id, the name GitAway shows, time zone, the states it stands for, names a destination may use)
STATIONS = (
    ("USW00093134", "Los Angeles", PT, ("CA",), ("los angeles", "downtown los angeles", "hollywood")),
    ("USW00023174", "Los Angeles coast (LAX)", PT, ("CA",), ("santa monica", "venice beach", "marina del rey", "manhattan beach", "redondo beach")),
    ("USC00040192", "Anaheim", PT, ("CA",), ("anaheim", "disneyland resort", "disneyland park", "disneyland california", "disneyland ca", "disneyland anaheim", "disney california adventure", "orange county")),
    ("USW00023188", "San Diego", PT, ("CA",), ("san diego", "la jolla", "coronado", "mission beach")),
    ("USW00022521", "Honolulu", HT, ("HI",), ("honolulu", "waikiki", "waikiki beach", "oahu", "ko olina")),
    ("USW00094728", "New York City", ET, ("NY",), ("new york", "new york city", "nyc", "manhattan", "brooklyn")),
    ("USW00093230", "South Lake Tahoe", PT, ("CA", "NV"), ("south lake tahoe", "lake tahoe", "tahoe", "stateline", "heavenly", "zephyr cove", "emerald bay")),
    ("USC00048758", "Tahoe City", PT, ("CA", "NV"), ("tahoe city", "north lake tahoe", "palisades tahoe", "squaw valley", "olympic valley", "kings beach",
                                      "incline village")),
    ("USC00049043", "Truckee", PT, ("CA",), ("truckee", "northstar", "donner lake")),
    ("USW00023185", "Reno", PT, ("NV",), ("reno",)),
    ("USW00012815", "Orlando", ET, ("FL",), ("orlando", "walt disney world", "walt disney world resort", "disney world", "kissimmee", "lake buena vista", "universal orlando", "universal orlando resort")),
    ("USW00023169", "Las Vegas", PT, ("NV",), ("las vegas", "vegas")),
    ("USW00023272", "San Francisco", PT, ("CA",), ("san francisco",)),
    ("USW00013743", "Washington, D.C.", ET, ("DC", "VA", "MD"), ("washington dc", "washington d c", "district of columbia")),
    ("USW00094846", "Chicago", CT, ("IL",), ("chicago",)),
    ("USW00012839", "Miami", ET, ("FL",), ("miami", "miami beach")),
    ("USW00024233", "Seattle", PT, ("WA",), ("seattle",)),
    ("USW00014739", "Boston", ET, ("MA",), ("boston",)),
    ("USW00003017", "Denver", MT, ("CO",), ("denver",)),
    ("USC00023596", "Grand Canyon", AZ, ("AZ",), ("grand canyon", "grand canyon village", "grand canyon national park", "south rim")),
    ("USC00049855", "Yosemite Valley", PT, ("CA",), ("yosemite", "yosemite valley", "yosemite national park")),
    ("USC00486845", "Old Faithful, Yellowstone", MT, ("WY", "MT", "ID"), ("yellowstone", "yellowstone national park", "old faithful")),
    ("USW00022516", "Maui (Kahului)", HT, ("HI",), ("maui", "kahului", "kihei", "wailea", "lahaina", "kaanapali")),
    ("USW00022536", "Kauai (Lihue)", HT, ("HI",), ("kauai", "lihue", "poipu", "princeville")),
    ("USW00021510", "Kona", HT, ("HI",), ("kona", "kailua kona", "waikoloa")),
    ("USW00021504", "Hilo", HT, ("HI",), ("hilo",)),
    ("USW00023183", "Phoenix", AZ, ("AZ",), ("phoenix", "scottsdale", "tempe")),
    ("USW00024127", "Salt Lake City", MT, ("UT",), ("salt lake city",)),
    ("USC00058575", "Vail", MT, ("CO",), ("vail", "beaver creek")),
    ("USC00052281", "Dillon, near Breckenridge", MT, ("CO",), ("breckenridge", "keystone resort")),
    ("USC00050372", "Aspen", MT, ("CO",), ("aspen", "snowmass")),
    ("USC00040741", "Big Bear Lake", PT, ("CA",), ("big bear", "big bear lake")),
    ("USW00093138", "Palm Springs", PT, ("CA",), ("palm springs",)),
    ("USW00023190", "Santa Barbara", PT, ("CA",), ("santa barbara",)),
    ("USW00023259", "Monterey", PT, ("CA",), ("monterey", "carmel by the sea", "pebble beach", "pacific grove")),
    ("USC00046074", "Napa", PT, ("CA",), ("napa", "napa valley")),
    ("USC00027708", "Sedona", AZ, ("AZ",), ("sedona",)),
    ("USC00429717", "Zion", MT, ("UT",), ("zion", "zion national park")),
    ("USC00425733", "Moab", MT, ("UT",), ("moab", "arches national park")),
    ("USC00484910", "Jackson Hole", MT, ("WY",), ("jackson hole", "jackson wyoming", "jackson wy", "grand teton", "grand teton national park")),
    ("USC00248809", "West Glacier", MT, ("MT",), ("glacier national park", "west glacier")),
    ("USC00170100", "Acadia", ET, ("ME",), ("acadia", "acadia national park", "bar harbor")),
    ("USC00403420", "Gatlinburg", ET, ("TN", "NC"), ("gatlinburg", "pigeon forge", "great smoky mountains", "great smoky mountains national park", "smoky mountains")),
    ("USW00093718", "North Myrtle Beach", ET, ("SC",), ("myrtle beach",)),
    ("USW00012836", "Key West", ET, ("FL",), ("key west",)),
    ("USW00012842", "Tampa", ET, ("FL",), ("tampa", "clearwater", "st petersburg", "st pete beach")),
    ("USW00013897", "Nashville", CT, ("TN",), ("nashville",)),
    ("USW00012916", "New Orleans", CT, ("LA",), ("new orleans",)),
    ("USW00012921", "San Antonio", CT, ("TX",), ("san antonio",)),
    ("USW00013904", "Austin", CT, ("TX",), ("austin",)),
    ("USW00013874", "Atlanta", ET, ("GA",), ("atlanta",)),
    ("USW00013739", "Philadelphia", ET, ("PA",), ("philadelphia",)),
    ("USW00013880", "Charleston, SC", ET, ("SC",), ("charleston sc", "charleston south carolina")),
    ("USW00003822", "Savannah", ET, ("GA",), ("savannah",)),
    ("USW00026451", "Anchorage", AK, ("AK",), ("anchorage",)),
    ("USW00024229", "Portland, Oregon", PT, ("OR",), ("portland oregon", "portland or")),
    ("USW00004724", "Niagara Falls", ET, ("NY",), ("niagara falls",)),
    ("USW00093729", "Cape Hatteras", ET, ("NC",), ("outer banks", "cape hatteras", "hatteras")),
    ("USW00003927", "Dallas", CT, ("TX",), ("dallas", "fort worth")),
    ("USW00012960", "Houston", CT, ("TX",), ("houston",)),
)

MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)   # the files have a row for Feb 29
COLUMNS = (("DLY-TMAX-NORMAL", -80, 140), ("DLY-TMIN-NORMAL", -80, 140), ("DLY-PRCP-PCTALL-GE001HI", 0, 100), ("DLY-SNOW-PCTALL-GE001TI", 0, 100))   # (column, lowest, highest)


def number(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if -500 < v < 500 else None   # NOAA marks a missing or suppressed value with -7777 / -9999 and similar


def cache_dir(named=None) -> Path:
    """Where the downloads are kept: a folder you name, if no one else can write to it, else ~/.cache/gitaway-normals, made and kept at mode 0700."""
    if named:
        folder = Path(named)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = folder.stat()
        if info.st_uid != os.getuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise SystemExit(f"{folder} is not yours alone: name a folder only you can write to, or leave it out")
        return folder
    folder = Path.home() / ".cache" / "gitaway-normals"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    return folder


def download(station: str, cache: Path) -> str:
    """The station's daily normals: the copy in `cache`, else NCEI's, kept there. Never read or written through a link; at most MAX_BYTES."""
    path = cache / f"{station}.csv"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        fd = None
    if fd is not None:
        with os.fdopen(fd, "rb") as f:
            raw = f.read(MAX_BYTES + 1)
    else:
        with urlopen(Request(URL.format(id=station), headers={"User-Agent": USER_AGENT}), timeout=60) as r:  # noqa: S310 - fixed NOAA host
            raw = r.read(MAX_BYTES + 1)
        if len(raw) <= MAX_BYTES:
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as f:
                f.write(raw)
        time.sleep(0.5)   # be gentle with NCEI
    if len(raw) > MAX_BYTES:
        raise ValueError(f"more than {MAX_BYTES // (1024 * 1024)} MB")
    return raw.decode("utf-8")


def summarise(text: str):
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("an empty file")
    sums = [[[], [], [], []] for _ in range(36)]
    for r in rows:
        month, day = int(r["month"]), int(r["day"])
        if not 1 <= month <= 12 or not 1 <= day <= MONTH_DAYS[month - 1]:
            raise ValueError(f"a row for a day that does not exist: {month}-{day}")
        p = (month - 1) * 3 + third(day)
        for k, (col, lo, hi) in enumerate(COLUMNS):
            v = number(r.get(col))
            if v is not None:
                if not lo <= v <= hi:
                    raise ValueError(f"{col} {v} on {month}-{day} is outside {lo}..{hi}")
                sums[p][k].append(v)
    out = []
    for p, (hi, lo, wet, snow) in enumerate(sums):
        if not hi or not lo or not wet:
            raise ValueError(f"no high, low or precipitation normals for period {p}")
        out.append([round(sum(hi) / len(hi)), round(sum(lo) / len(lo)), round(sum(wet) / len(wet)), round(sum(snow) / len(snow)) if snow else None])
    first = rows[0]
    lat, lon, elev = float(first["LATITUDE"]), float(first["LONGITUDE"]), float(first["ELEVATION"])
    if not all(map(math.isfinite, (lat, lon, elev))) or not (-90 <= lat <= 90 and -180 <= lon <= 180 and -500 <= elev <= 9000):
        raise ValueError(f"impossible coordinates {lat}, {lon}, {elev} m")
    return lat, lon, round(elev), out


def main() -> int:
    cache = cache_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    stations, bad = {}, []
    for sid, name, tz, states, aliases in STATIONS:
        try:
            lat, lon, elev, normals = summarise(download(sid, cache))
        except (ValueError, KeyError, OSError) as e:
            bad.append(f"{sid} {name}: {e}")
            continue
        stations[sid] = {"name": name, "lat": lat, "lon": lon, "elev": elev, "tz": tz, "states": list(states), "aliases": list(aliases), "n": normals}
        print(f"{sid} {name}: late December high {normals[35][0]}, low {normals[35][1]}, wet {normals[35][2]}%, snow {normals[35][3]}")
    if bad:
        print("Nothing written. Pick another station for:\n  " + "\n  ".join(bad))
        return 1
    doc = {"source": "NOAA NCEI U.S. Climate Normals 1991-2020, daily normals (public domain)",
           "periods": "36 per station: early (days 1-10), mid (11-20) and late (21 to the end) of each month, January first",
           "values": "[normal high F, normal low F, chance of 0.01 in or more of precipitation %, chance of 0.1 in or more of snow % or null]",
           "stations": stations}
    OUT.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(stations)} stations, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
