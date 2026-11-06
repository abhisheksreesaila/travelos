"""Travelpayouts links (D-70). Two ways a traveler is sent to a partner with our marker and this click's SubID:

- Aviasales (flights) takes the marker on the search link itself: `https://www.aviasales.com/search/<route>?marker=<marker>.<sub_id>`. No call, no program id.
- Klook (stays, cars) needs the partner-links API: POST https://api.travelpayouts.com/links/v1/create, header `X-Access-Token: <TRAVELPAYOUTS_TOKEN>`,
  body `{"trs": <project id>, "marker": <partner id>, "shorten": false, "links": [{"url": <Klook page>, "sub_id": <SubID>}]}`; the answer is
  `{"code": 200, "result": {"links": [{"url", "code": "success", "partner_url": <tracked link>}]}}`.
  It runs at /go time (never while a page renders), with a 2 second timeout, and a good answer is cached per (url, sub_id). With no token, or on any
  failure, the traveler goes to `KLOOK_FALLBACK_URL` (the plain Klook partner link of our account).

`_post` is the only function that touches a network; tests replace it. Settings come from the environment by name: TRAVELPAYOUTS_MARKER (801445),
TRAVELPAYOUTS_TOKEN, TRAVELPAYOUTS_TRS (the project id; the Drive script id 596534 is probably it), KLOOK_FALLBACK_URL.
"""

import json
import logging
import os
import urllib.request
from urllib.parse import quote

API = "https://api.travelpayouts.com/links/v1/create"
TIMEOUT = 2
DEFAULT_KLOOK_FALLBACK = "https://klook.tpx.lv/s1rIcwCA"
_CACHE: dict = {}
_CACHE_MAX = 512
log = logging.getLogger(__name__)


def marker() -> str:
    return os.getenv("TRAVELPAYOUTS_MARKER", "").strip()


def token() -> str:
    return os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()


def klook_fallback() -> str:
    return os.getenv("KLOOK_FALLBACK_URL", "").strip() or DEFAULT_KLOOK_FALLBACK


def links_request(urls_and_subs, *, shorten=False) -> dict | None:
    """The body of the partner-links call for `[(partner page url, sub_id), ...]`, or None without a numeric project id (trs) and marker.

    trs and marker go as numbers: the live API answers 400 "invalid body" when they are strings (probed 2026-11-05)."""
    trs, mk = os.getenv("TRAVELPAYOUTS_TRS", "").strip(), marker()
    if not (trs.isascii() and trs.isdigit() and mk.isascii() and mk.isdigit()):
        return None
    return {"trs": int(trs), "marker": int(mk), "shorten": shorten,
            "links": [{"url": url, "sub_id": sub} for url, sub in urls_and_subs]}


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    """The one network call (the partner-links API). Raises on any failure."""
    req = urllib.request.Request(url, json.dumps(body).encode(), {**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (a fixed https URL)
        return json.load(r)


def create_link(url: str, sub_id: str) -> str:
    """A tracked link for one partner page, from the API. Raises when there is no token or the API does not answer with a success."""
    if not (token() and marker()):
        raise LookupError("no token or marker")
    body = links_request([(url, sub_id)])
    if body is None:
        raise LookupError("no numeric project id (TRAVELPAYOUTS_TRS) or marker")
    answer = _post(API, {"X-Access-Token": token()}, body, TIMEOUT)
    link = answer["result"]["links"][0]
    if link.get("code") != "success" or not str(link.get("partner_url", "")).startswith("https://"):
        raise LookupError(f"the API refused the link: {link.get('code')}")
    return link["partner_url"]


def klook_link(url: str, sub_id: str) -> str:
    """Where a Klook click goes: the tracked link of `url` with our SubID, else the plain Klook partner link. Never raises."""
    key = (url, sub_id)
    if key in _CACHE:
        return _CACHE[key]
    try:
        link = create_link(url, sub_id)
    except Exception as e:   # no token, a timeout, a bad answer: a click must always land somewhere
        log.info("partner-links API not used (%s: %s)", type(e).__name__, e)
        return klook_fallback()
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = link
    return link


def aviasales_link(url: str, sub_id: str) -> str:
    """The Aviasales search link with `marker=<marker>.<sub_id>` (the way a Travelpayouts-made Aviasales link carries it)."""
    return f"{url}{'&' if '?' in url else '?'}marker={quote(marker() + '.' + sub_id, safe='.-')}&sub_id={quote(sub_id, safe='-')}"


def link_for(partner, offer, trip, sub_id) -> str:
    """The https link a traveler is sent to for `offer`."""
    url = partner.target_url(offer, trip)
    return aviasales_link(url, sub_id) if partner.key == "aviasales" else klook_link(url, sub_id)
