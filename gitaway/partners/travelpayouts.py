"""Travelpayouts links (D-70). Two ways a traveler is sent to a partner with our marker and this click's SubID:

- Aviasales (flights) takes the marker on the search link itself: `https://www.aviasales.com/search/<route>?marker=<marker>.<sub_id>`. No call, no program id.
- Klook (stays, cars) needs the partner-links API: POST https://api.travelpayouts.com/links/v1/create, header `X-Access-Token: <TRAVELPAYOUTS_TOKEN>`,
  body `{"trs": <project id>, "marker": <partner id>, "shorten": false, "links": [{"url": <Klook page>, "sub_id": <SubID>}]}`; the answer is
  `{"code": 200, "result": {"links": [{"url", "code": "success", "partner_url": <tracked link>}]}}`.
  It runs at /go time (never while a page renders), with a 2 second timeout, and a good answer is cached per (url, sub_id). With no token, or on any
  failure, the traveler goes to `KLOOK_FALLBACK_URL` (the plain Klook partner link of our account). A failure with a token set (a timeout, a refusal, a project id
  that is missing or wrong) is a WARNING with its reason and a count on /admin (F-195, gitaway/partners/failures.py); having no token is only an INFO line.

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


class NotConfigured(LookupError):
    """No token or no marker: the partner-links API is simply not in use (a local copy), which is not a failure."""


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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an error, never followed (F-198 review): urllib would carry our X-Access-Token header to wherever it points."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(NoRedirect)


def redacted(error: Exception, limit: int = 160) -> str:
    """"<Type>: <message>" with the token taken out before the line is cut, so no part of it can be left at the cut."""
    reason = f"{type(error).__name__}: {error}"
    if token():
        reason = reason.replace(token(), "***")
    return reason[:limit]


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    """The one network call (the partner-links API). Raises on any failure, a redirect included."""
    req = urllib.request.Request(url, json.dumps(body).encode(), {**headers, "Content-Type": "application/json"}, method="POST")
    with _opener.open(req, timeout=timeout) as r:   # noqa: S310 (a fixed https URL)
        return json.load(r)


def create_link(url: str, sub_id: str) -> str:
    """A tracked link for one partner page, from the API. Raises when there is no token or the API does not answer with a success."""
    if not (token() and marker()):
        raise NotConfigured("no token or marker")
    body = links_request([(url, sub_id)])
    if body is None:
        raise LookupError("no numeric project id (TRAVELPAYOUTS_TRS) or marker")
    answer = _post(API, {"X-Access-Token": token()}, body, TIMEOUT)
    link = answer["result"]["links"][0]
    if link.get("code") != "success" or not str(link.get("partner_url", "")).startswith("https://"):
        raise LookupError(f"the API refused the link: {link.get('code')}")
    return link["partner_url"]


def connected() -> bool:
    """Can the partner-links API make tracked links here? A token, a marker and a numeric project id (TRAVELPAYOUTS_TRS)."""
    trs = os.getenv("TRAVELPAYOUTS_TRS", "").strip()
    return bool(token() and marker() and trs.isascii() and trs.isdigit())


def _failed(error: Exception, fallback_name: str) -> None:
    """Say why the partner-links API did not give a link: one WARNING line and one count for /admin. The token is never in either."""
    reason = redacted(error)
    log.warning("partner-links API failed, the click goes to the %s (%s)", fallback_name, reason)
    try:
        from gitaway.partners import failures
        failures.record(reason)
    except Exception:   # the click must not fail because the count could not be written
        log.exception("could not count the partner-links failure")


def tracked_link(url: str, sub_id: str, fallback: str = "", fallback_name: str = "plain link") -> str:
    """Where a click on a partner page goes: the tracked link of `url` with our SubID, else `fallback` (the plain page itself when not given: the click lands, untracked). Never raises.
    Any brand our Travelpayouts project is connected to works the same way (F-198: a program approved later is `PARTNER_TRACKED`, not code)."""
    fallback = fallback or url
    key = (url, sub_id)
    if key in _CACHE:
        return _CACHE[key]
    try:
        link = create_link(url, sub_id)
    except NotConfigured as e:
        log.info("partner-links API not used (%s)", e)
        return fallback
    except Exception as e:   # a timeout, a bad answer, a wrong project id: a click must always land somewhere, and the failure must be noticed (F-195)
        _failed(e, fallback_name)
        return fallback
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = link
    return link


def klook_link(url: str, sub_id: str) -> str:
    """Where a Klook click goes: the tracked link of `url` with our SubID, else the plain Klook partner link of our account. Never raises."""
    return tracked_link(url, sub_id, klook_fallback(), "plain Klook link")


def aviasales_link(url: str, sub_id: str, own: str = "") -> str:
    """The Aviasales search link with `marker=<marker>.<sub_id>` (the way a Travelpayouts-made Aviasales link carries it). `own` is a creator's marker (F-184) in place of ours."""
    return f"{url}{'&' if '?' in url else '?'}marker={quote((own or marker()) + '.' + sub_id, safe='.-')}&sub_id={quote(sub_id, safe='-')}"


def link_for(partner, offer, trip, sub_id, own: str = "") -> str:
    """The https link a traveler is sent to for `offer`. `own` is the creator's marker (F-184): flights carry it; Klook always goes through our token and marker (D-101)."""
    url = partner.target_url(offer, trip)
    return aviasales_link(url, sub_id, own) if partner.key == "aviasales" else klook_link(url, sub_id)
