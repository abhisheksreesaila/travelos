"""Travelpayouts partner links, shaped like the real "partner links" API (support.travelpayouts.com, "API for Travelpayouts partner links").

Real call: POST https://api.travelpayouts.com/links/v1/create with header `X-Access-Token: <TRAVELPAYOUTS_TOKEN>` and a body
`{"trs": <project id>, "marker": <partner id>, "shorten": true, "links": [{"url": <partner page>, "sub_id": <our SubID>}]}`; the answer is
`{"code": 200, "result": {"trs", "marker", "shorten", "links": [{"url", "code": "success", "partner_url": <tracked link>}]}}`.

Nothing here calls a network. `client()` hands back the synthetic client unless a token and a marker exist, and even then the real one only
builds the same tracked link locally until the first live key is wired (D-21). A tracked link is
`https://tp.media/r?marker=&trs=&p=&u=&campaign_id=&sub_id=`.
"""

import os
from urllib.parse import urlencode


def marker() -> str:
    return os.getenv("TRAVELPAYOUTS_MARKER", "").strip()


def token() -> str:
    return os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()


def links_request(urls_and_subs, *, shorten=True) -> dict:
    """The body of the partner-links call for `[(partner page url, sub_id), ...]`."""
    return {"trs": os.getenv("TRAVELPAYOUTS_TRS", "").strip(), "marker": marker(), "shorten": shorten,
            "links": [{"url": url, "sub_id": sub} for url, sub in urls_and_subs]}


def tracked_url(body, partner, url, sub_id) -> str:
    q = {"marker": body["marker"], "trs": body["trs"], "p": partner.program_id, "u": url, "campaign_id": partner.program_id, "sub_id": sub_id}
    return "https://tp.media/r?" + urlencode({k: v for k, v in q.items() if v != ""})


class SyntheticLinks:
    """Answers like the partner-links API, from the request alone."""

    def create(self, body, partner) -> dict:
        links = [{"url": link["url"], "code": "success", "partner_url": tracked_url(body, partner, link["url"], link["sub_id"])} for link in body["links"]]
        return {"code": 200, "result": {"trs": body["trs"], "marker": body["marker"], "shorten": body["shorten"], "links": links}}


class RealLinks(SyntheticLinks):
    """Stands where the real HTTPS call goes once a live key is wired. Today it builds the same links locally, so a key never turns a click into a crash."""


def client():
    return RealLinks() if token() and marker() else SyntheticLinks()


def tracked_link(partner, offer, trip, sub_id) -> str:
    """The https link a traveler is sent to for `offer`: Travelpayouts' redirect carrying our marker and this click's SubID."""
    body = links_request([(partner.target_url(offer, trip), sub_id)])
    return client().create(body, partner)["result"]["links"][0]["partner_url"]
