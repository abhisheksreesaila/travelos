"""Shared constants for the browser tests."""
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}


def seed_plan(request, base_url, id, day, start, end, title, kind="fun"):
    """A plan on the open trip, the way the app makes one (the add sheet's route runs an hour; the canvas then sets the end). `request` is a browser context's or page's `.request`."""
    request.post(f"{base_url}/trip/plans", form={"id": id, "day": str(day), "start": start, "title": title, "kind": kind}, max_redirects=0)
    h, m = map(int, end.split(":"))
    request.post(f"{base_url}/trip/canvas/plan", form={"op": "edit", "act": id, "end": str(h * 60 + m)}, max_redirects=0)
