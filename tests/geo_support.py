"""A fake Nominatim and OSRM behind geo.fetch, for tests that read a drive or a place (it was in tests/test_plan_widgets.py, which went with the booking lanes page)."""


class Router:
    """South Lake Tahoe is found, and the drive from RNO takes `seconds`."""

    def __init__(self, seconds=3900):
        self.seconds, self.urls = seconds, []

    def __call__(self, url, timeout=None):
        self.urls.append(url)
        if "nominatim" in url:
            return [{"lat": "38.9399", "lon": "-119.9772", "display_name": "South Lake Tahoe, El Dorado County, California, United States"}]
        if "osrm" in url:
            return {"code": "Ok", "routes": [{"duration": self.seconds, "distance": 95000, "geometry": {"type": "LineString", "coordinates": [[-119.77, 39.50], [-119.98, 38.94]]},
                                              "legs": []}]}
        raise AssertionError(url)
