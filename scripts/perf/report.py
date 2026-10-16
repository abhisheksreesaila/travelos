"""F-168: the tables in docs/perf-feel.md from measure.py's runs (medians over the repeats), and the server's own times from serve.py's logs.

    python scripts/perf/report.py /tmp/x            (reads /tmp/x/runs.jsonl and /tmp/x/server-*.jsonl)
"""
import glob
import json
import re
import statistics
import sys
from collections import defaultdict


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs)) if xs else None


def drop_at(d):
    """For a drag or a swipe, time is counted from the lift (the last pointerup), not from the press."""
    ups = [s[1] for s in d["steps"] if s[0] == "pointerup"] or [s[1] for s in d["steps"] if s[0] in ("touchend",)]
    return max(ups) if ("move" in d["name"] or "swipe" in d["name"]) and ups else 0


def starts(d, t0):
    """When the new thing starts to show, on the page's clock: a view transition is ready, or an animation starts (else the first DOM change), after t0."""
    s = d["steps"]
    moves = [e[1] for e in s if e[1] >= t0 and (e[0] in ("vt-ready", "waapi") or (e[0] == "animationstart" and not str(e[2]).startswith("-ua-")))]
    if moves:
        return min(moves)
    muts = [b[0] for b in d["mut_bursts"] if b[0] >= t0]
    return min(muts) if muts else None


def done(d, t0):
    """When it is all over, on the page's clock: the last transition, animation or DOM change (the Ask sheet's pulsing mic, which never ends, is left out)."""
    ends = [e[1] for e in d["steps"] if e[0] in ("vt-done", "waapi-end", "animationend") and e[1] >= t0 and "pulse" not in str(e[2:])]
    ends += [b[1] for b in d["mut_bursts"] if b[1] >= t0]
    return max(ends) if ends else None


def blocking(d, t0, c):
    """Network time the screen waited on: requests that ended before the content began to move."""
    return [n for n in d["net"] if c is not None and n["end"] <= c + 20 and n["end"] > t0]


def main(folder):
    runs = [json.loads(l) for l in open(f"{folder}/runs.jsonl")]
    groups = defaultdict(list)
    for d in runs:
        if "error" in d:
            continue
        groups[(d["kind"], d["cpu"], d["latency"], d["name"])].append(d)
    last = None
    for (kind, cpu, lat, name), ds in groups.items():
        if (kind, cpu, lat) != last:
            print(f"\n### {kind}, CPU {cpu}x slower, +{lat} ms per request  (median of {len(ds)} runs)\n")
            print("| interaction | starts moving | settled | last screen change | waited on network | requests | longest task | dropped frames | layout+style ms |")
            print("|---|---|---|---|---|---|---|---|---|")
            last = (kind, cpu, lat)
        rows = []
        for d in ds:
            t0 = drop_at(d)
            c, z = starts(d, t0), done(d, t0)
            wait = sum(n["end"] - max(n["start"], t0) for n in blocking(d, t0, c))
            lt = max([x[1] for x in d["longtasks"] if x[0] + x[1] >= t0] or [0])
            rows.append(dict(content=(c - t0) if c is not None else None, settled=(z - t0) if z is not None else None,
                             screen=(d["settled"] - t0) if d["settled"] is not None else None, wait=wait, nreq=len(d["net"]), lt=lt, drop=d["frames_dropped"], ls=d["layout_ms"] + d["style_ms"]))
        g = {k: med([r[k] for r in rows]) for k in rows[0]}
        print(f"| {name} | {g['content']} | {g['settled']} | {g['screen']} | {g['wait']} | {g['nreq']} | {g['lt']} | {g['drop']} | {g['ls']} |")

    print("\n### Server time per route (ms to first byte, median / p90, all measured runs; body size median)\n")
    srv = defaultdict(list)
    for f in glob.glob(f"{folder}/server-*.jsonl"):
        started = False
        for l in open(f):
            r = json.loads(l)
            if "mark" in r:
                started = True
                continue
            if not started:
                continue
            p = r["path"]
            if p.startswith("/assets/"):
                continue
            key = r["method"] + " " + re.sub(r"(act|step|block|plan|thread)=[^&]+", r"\1=…", re.sub(r"[?&]trip=[0-9a-f]+", "", re.sub(r"day=\d+", "day=N", p)))
            if "frag=1" in p:
                key = "GET level fragment: " + ("week" if "day=" not in p else "day" if "plan=" not in p and "block=" not in p else "day+plan panel" if "plan=" in p else "block")
            srv[key].append((r["ms"], r["bytes"]))
    print("| route | n | median ms | p90 ms | median bytes |")
    print("|---|---|---|---|---|")
    for k, v in sorted(srv.items(), key=lambda kv: -len(kv[1])):
        if len(v) < 3:
            continue
        ms = sorted(x[0] for x in v)
        print(f"| {k[:70]} | {len(v)} | {statistics.median(ms):.0f} | {ms[int(len(ms) * 0.9) - 1]:.0f} | {statistics.median([x[1] for x in v]):.0f} |")


if __name__ == "__main__":
    main(sys.argv[1])
