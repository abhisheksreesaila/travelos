"""What the trip pages share about a day's plans (kept from the old trip calendar, retired in F-147): side-by-side lanes for overlapping plans, the first free
hour of a day, who wrote a note, the first line of the trip's note feed, and where a ride block goes."""

from gitaway import session as ses, tripcal as cal
from gitaway.pages import plan as plan_ui, rides as rides_ui


def lanes(acts):
    """{activity id: (lane, lanes in its cluster)} so overlapping activities sit side by side."""
    out, cluster, ends, cluster_end = {}, [], [], -1

    def flush():
        for a, lane in cluster:
            out[a.id] = (lane, len(ends))

    for a in sorted(acts, key=lambda a: (a.start, a.end, a.id)):
        if a.start >= cluster_end:
            flush()
            cluster, ends = [], []
        lane = next((i for i, e in enumerate(ends) if e <= a.start), len(ends))
        if lane == len(ends):
            ends.append(a.end)
        else:
            ends[lane] = a.end
        cluster.append((a, lane))
        cluster_end = max(cluster_end, a.end)
    flush()
    return out


def _clashes(blocks, day, s, e):
    return any(b.day == day and s < b.end and b.start < e for b in blocks)


def free_start(blocks, day, gs):
    """The first half hour from 9 AM (or the grid start, or when you land) with an hour free of booked items, inside the day's window."""
    lo, hi = cal.day_window(blocks, day)
    t = -(-max(9 * 60, gs, lo) // 30) * 30
    while t + 60 <= hi:
        if not _clashes(blocks, day, t, t + 60):
            return t
        t += 30
    return gs


def default_end(blocks, day, start):
    end = min(start + 60, cal.GRID_END)
    for b in blocks:
        if b.day == day and b.start >= start:
            end = min(end, b.start)
    return end if end - start >= cal.MIN_LEN else min(start + 60, cal.GRID_END)



def ride_href(ctx, block):
    """Where a ride block goes: the ride itself, or (an offer, id "ro-<leg>") the flow that schedules it for the booked picks."""
    if block.kind == "ride":
        return f"/rides/{block.id}"
    if cal.is_imported(ctx["booking"]):  # an imported trip has no picks: the ride flow names the trip instead (F-042)
        b = ctx["booking"]
        return rides_ui.new_url(cal.flight_of(b), cal.stay_of(b), cal.trip_of(b), block.id[3:])
    return plan_ui.ride_path(block.id[3:], cal.flight_of(ctx["booking"]).id, (cal.stay_of(ctx["booking"]) or None) and cal.stay_of(ctx["booking"]).id, cal.trip_of(ctx["booking"]))

FORMER = ses.Friend("Former member", "?", "sky")


def note_writer(n, who, people, family):
    """(name shown, avatar person) for a note: a pretend friend by name, another member by their user id, and "You" only for the viewer's own."""
    if n.by:
        return n.by, people.get(n.by.casefold(), who)
    if not n.by_id or n.by_id == who.id:
        return "You", who
    member = family.get(n.by_id, FORMER)
    return member.name, member

def booked_note(b):
    """The first note on the feed: what was booked, as a list that fits any mix of flight, stay and car. Flights and a stay are
    blocks on the calendar; a car has none, so it is only ever said to be booked."""
    if cal.is_imported(b):
        where = cal.plan_of(b).booked_on
        lanes = [w for w, got in (("flights", cal.flight_of(b)), ("hotel", cal.stay_of(b)), ("car", cal.car_of(b))) if got]  # only what this trip really has
        if not lanes:
            return f"Imported from {where}. Add anything you want to do."
        return f"Imported from {where}. Your {cal.oxford(lanes)} {'is' if len(lanes) == 1 and lanes != ['flights'] else 'are'} on the calendar, locked. Tap one for its details. Add anything you want to do."
    stay, pick, car = cal.stay_of(b), cal.stay_pick_of(b), cal.car_of(b)
    flights = cal.flight_of(b) is not None
    on_cal = (["flights"] if flights else []) + ([f"{stay.name} ({pick.summary})" if flights else f"stay at {stay.name} ({pick.summary})"] if stay else [])
    rental = f"{car.name} rental" if car else ""
    if not on_cal:
        return f"Booked! Your {rental} is booked. It has no block here, but you can still plan the days."
    are = "are" if len(on_cal) > 1 or on_cal == ["flights"] else "is"
    if not car:
        return f"Booked! Your {cal.oxford(on_cal)} {are} on the calendar. Add anything you want to do."
    placed = cal.oxford((["flights"] if flights else []) + (["stay"] if stay else []))
    return f"Booked! Your {cal.oxford(on_cal + [rental])} are all set. The {placed} {are} on the calendar; the car has no block there. Add anything you want to do."
