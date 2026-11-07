"""Build gitaway/normals.json from NOAA's U.S. Climate Normals, 1991-2020 (F-203): `pixi run build-normals [cache folder]`.

NOAA's normals are public domain (a work of the U.S. Government; NCEI asks only that the source be cited). For each station below this downloads
its daily normals once into the cache folder (https://www.ncei.noaa.gov/data/normals-daily/1991-2020/access/<station>.csv) and keeps, for each
third of a month (days 1-10, 11-20, 21 to the end: "early", "mid" and "late"), the mean of:

  - the normal daily high and low (deg F),
  - the chance that a day has at least 0.01 in of precipitation (%, DLY-PRCP-PCTALL-GE001HI),
  - where the station measures snow, the chance of at least 0.1 in of snowfall (%, DLY-SNOW-PCTALL-GE001TI), else null.

The app reads only the JSON (gitaway/weather.py); nothing is fetched while it runs. Add a destination by adding a row: the station id is in
https://www.ncei.noaa.gov/data/normals-daily/1991-2020/doc/inventory_30yr.txt. Names are matched as whole words against a trip's destination,
so never add a name that is also a different place (a bare "portland", "charleston" or "mammoth"). Park City and Mammoth Lakes are left out on
purpose: their own stations have no temperature or precipitation normals and the nearest ones that do sit hundreds of metres lower.
"""

import csv
import io
import json
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gitaway" / "normals.json"
URL = "https://www.ncei.noaa.gov/data/normals-daily/1991-2020/access/{id}.csv"
USER_AGENT = "GitAway normals builder (+https://gitaway.me)"

PT, MT, AZ, CT, ET, HT, AK = ("America/Los_Angeles", "America/Denver", "America/Phoenix", "America/Chicago", "America/New_York", "Pacific/Honolulu",
                              "America/Anchorage")

# (station id, the name GitAway shows, time zone, names a destination may use)
STATIONS = (
    ("USW00093134", "Los Angeles", PT, ("los angeles", "downtown los angeles", "hollywood")),
    ("USW00023174", "Los Angeles coast (LAX)", PT, ("santa monica", "venice beach", "marina del rey", "manhattan beach", "redondo beach")),
    ("USC00040192", "Anaheim", PT, ("anaheim", "disneyland", "disneyland resort", "disney california adventure")),
    ("USW00023188", "San Diego", PT, ("san diego", "la jolla", "coronado", "mission beach")),
    ("USW00022521", "Honolulu", HT, ("honolulu", "waikiki", "oahu", "ko olina")),
    ("USW00094728", "New York City", ET, ("new york", "new york city", "nyc", "manhattan", "brooklyn")),
    ("USW00093230", "South Lake Tahoe", PT, ("south lake tahoe", "lake tahoe", "tahoe", "stateline", "heavenly", "zephyr cove", "emerald bay")),
    ("USC00048758", "Tahoe City", PT, ("tahoe city", "north lake tahoe", "palisades tahoe", "squaw valley", "olympic valley", "kings beach",
                                      "incline village")),
    ("USC00049043", "Truckee", PT, ("truckee", "northstar", "donner lake")),
    ("USW00023185", "Reno", PT, ("reno",)),
    ("USW00012815", "Orlando", ET, ("orlando", "walt disney world", "disney world", "kissimmee", "lake buena vista", "universal orlando")),
    ("USW00023169", "Las Vegas", PT, ("las vegas", "vegas")),
    ("USW00023272", "San Francisco", PT, ("san francisco",)),
    ("USW00013743", "Washington, D.C.", ET, ("washington dc", "washington d c", "district of columbia")),
    ("USW00094846", "Chicago", CT, ("chicago",)),
    ("USW00012839", "Miami", ET, ("miami", "miami beach")),
    ("USW00024233", "Seattle", PT, ("seattle",)),
    ("USW00014739", "Boston", ET, ("boston",)),
    ("USW00003017", "Denver", MT, ("denver",)),
    ("USC00023596", "Grand Canyon", AZ, ("grand canyon", "grand canyon village", "south rim")),
    ("USC00049855", "Yosemite Valley", PT, ("yosemite", "yosemite valley", "yosemite national park")),
    ("USC00486845", "Old Faithful, Yellowstone", MT, ("yellowstone", "yellowstone national park", "old faithful")),
    ("USW00022516", "Maui (Kahului)", HT, ("maui", "kahului", "kihei", "wailea", "lahaina", "kaanapali")),
    ("USW00022536", "Kauai (Lihue)", HT, ("kauai", "lihue", "poipu", "princeville")),
    ("USW00021510", "Kona", HT, ("kona", "kailua kona", "waikoloa")),
    ("USW00021504", "Hilo", HT, ("hilo",)),
    ("USW00023183", "Phoenix", AZ, ("phoenix", "scottsdale", "tempe")),
    ("USW00024127", "Salt Lake City", MT, ("salt lake city",)),
    ("USC00058575", "Vail", MT, ("vail", "beaver creek")),
    ("USC00052281", "Dillon, near Breckenridge", MT, ("breckenridge", "keystone resort")),
    ("USC00050372", "Aspen", MT, ("aspen", "snowmass")),
    ("USC00040741", "Big Bear Lake", PT, ("big bear", "big bear lake")),
    ("USW00093138", "Palm Springs", PT, ("palm springs",)),
    ("USW00023190", "Santa Barbara", PT, ("santa barbara",)),
    ("USW00023259", "Monterey", PT, ("monterey", "carmel by the sea", "pebble beach", "pacific grove")),
    ("USC00046074", "Napa", PT, ("napa", "napa valley")),
    ("USC00027708", "Sedona", AZ, ("sedona",)),
    ("USC00429717", "Zion", MT, ("zion", "zion national park")),
    ("USC00425733", "Moab", MT, ("moab", "arches national park")),
    ("USC00484910", "Jackson Hole", MT, ("jackson hole", "jackson wyoming", "jackson wy", "grand teton")),
    ("USC00248809", "West Glacier", MT, ("glacier national park", "west glacier")),
    ("USC00170100", "Acadia", ET, ("acadia", "acadia national park", "bar harbor")),
    ("USC00403420", "Gatlinburg", ET, ("gatlinburg", "pigeon forge", "great smoky mountains", "smoky mountains")),
    ("USW00093718", "North Myrtle Beach", ET, ("myrtle beach",)),
    ("USW00012836", "Key West", ET, ("key west",)),
    ("USW00012842", "Tampa", ET, ("tampa", "clearwater", "st petersburg", "st pete beach")),
    ("USW00013897", "Nashville", CT, ("nashville",)),
    ("USW00012916", "New Orleans", CT, ("new orleans",)),
    ("USW00012921", "San Antonio", CT, ("san antonio",)),
    ("USW00013904", "Austin", CT, ("austin",)),
    ("USW00013874", "Atlanta", ET, ("atlanta",)),
    ("USW00013739", "Philadelphia", ET, ("philadelphia",)),
    ("USW00013880", "Charleston, SC", ET, ("charleston sc", "charleston south carolina")),
    ("USW00003822", "Savannah", ET, ("savannah",)),
    ("USW00026451", "Anchorage", AK, ("anchorage",)),
    ("USW00024229", "Portland, Oregon", PT, ("portland oregon", "portland or")),
    ("USW00004724", "Niagara Falls", ET, ("niagara falls",)),
    ("USW00093729", "Cape Hatteras", ET, ("outer banks", "cape hatteras", "hatteras")),
    ("USW00003927", "Dallas", CT, ("dallas", "fort worth")),
    ("USW00012960", "Houston", CT, ("houston",)),
)

MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)   # the files have a row for Feb 29


def third(day: int) -> int:
    return 0 if day <= 10 else 1 if day <= 20 else 2


def number(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if -500 < v < 500 else None   # NOAA marks a missing or suppressed value with -7777 / -9999 and similar


def download(station: str, cache: Path) -> str:
    path = cache / f"{station}.csv"
    if not path.exists():
        with urlopen(Request(URL.format(id=station), headers={"User-Agent": USER_AGENT}), timeout=60) as r:  # noqa: S310 - fixed NOAA host
            path.write_bytes(r.read())
        time.sleep(0.5)   # be gentle with NCEI
    return path.read_text(encoding="utf-8")


def summarise(text: str):
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("an empty file")
    sums = [[[], [], [], []] for _ in range(36)]
    for r in rows:
        month, day = int(r["month"]), int(r["day"])
        p = (month - 1) * 3 + third(day)
        for k, col in enumerate(("DLY-TMAX-NORMAL", "DLY-TMIN-NORMAL", "DLY-PRCP-PCTALL-GE001HI", "DLY-SNOW-PCTALL-GE001TI")):
            v = number(r.get(col))
            if v is not None:
                sums[p][k].append(v)
    out = []
    for p, (hi, lo, wet, snow) in enumerate(sums):
        if not hi or not lo or not wet:
            raise ValueError(f"no high, low or precipitation normals for period {p}")
        out.append([round(sum(hi) / len(hi)), round(sum(lo) / len(lo)), round(sum(wet) / len(wet)), round(sum(snow) / len(snow)) if snow else None])
    first = rows[0]
    return float(first["LATITUDE"]), float(first["LONGITUDE"]), round(float(first["ELEVATION"])), out


def main() -> int:
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "gitaway-normals"
    cache.mkdir(parents=True, exist_ok=True)
    stations, bad = {}, []
    for sid, name, tz, aliases in STATIONS:
        try:
            lat, lon, elev, normals = summarise(download(sid, cache))
        except (ValueError, KeyError) as e:
            bad.append(f"{sid} {name}: {e}")
            continue
        stations[sid] = {"name": name, "lat": lat, "lon": lon, "elev": elev, "tz": tz, "aliases": list(aliases), "n": normals}
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
