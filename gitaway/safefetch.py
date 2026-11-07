"""Fetch a web address a person typed, without letting it reach anything inside our own network (F-183, the SSRF guard).

    fetch(url, kind="html")   the page's bytes as a `Fetched`, or FetchError with a sentence fit to show

The address is untrusted: it can name this machine, the cloud's metadata service, a private network, or redirect there. So, in this order and on every hop:

  1. http or https only, the default port only (80, 443), no user name or password in the address;
  2. the name is resolved here, within the fetch's deadline, and EVERY address it gives must be a public one (not loopback, private, link-local, carrier-grade NAT, multicast, reserved or
     unspecified; an IPv6 address must also be global unicast, in 2000::/3; an IPv4 address wrapped in an IPv6 one, "::ffff:127.0.0.1", "64:ff9b::7f00:1" or a 6to4 "2002:7f00:1::",
     is judged by the IPv4 address inside);
  3. the connection goes to the address we checked (never the name again), so a name that answers differently a second time (DNS rebinding) cannot slip through;
  4. a redirect is followed by hand, at most MAX_REDIRECTS times, never from https down to http, and goes through 1 to 3 again;
  5. at most MAX_BYTES (2 MB for a page, MAX_IMAGE for a picture) are read, within TIMEOUT seconds in all (gitaway/deadline.py keeps it), only the content type asked for (`kind`), no compression.

Tests never reach the network: `RESOLVER` (name -> list of addresses) and `TRANSPORT` (url, ip, timeout, kind -> (status, headers, body)) are the seams, like `ai.TRANSPORT`.
"""

import http.client
import ipaddress
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from gitaway import deadline

MAX_REDIRECTS = 5
MAX_BYTES = 2 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
TIMEOUT = 8.0
USER_AGENT = "GitAwayBot/1.0 (+https://gitaway.me; reads a post its author asked us to read)"
USER_AGENT_UNASKED = "GitAwayBot/1.0 (+https://gitaway.me; drafts a public post for its author to look at; the author has not asked us to)"     # the captain's pre-draft (F-194): the author did not ask
ACCEPT = {"html": ("text/html", "application/xhtml+xml"), "json": ("application/json",), "xml": ("application/xml", "text/xml", "application/rss+xml", "application/atom+xml"), "image": ("image/jpeg", "image/png", "image/webp"),
          "robots": ("text/plain", "text/html")}
LIMIT = {"html": MAX_BYTES, "json": MAX_BYTES, "xml": MAX_BYTES, "image": MAX_IMAGE, "robots": MAX_BYTES}
RESOLVER = None    # tests: a function name -> list of address strings, instead of DNS
TRANSPORT = None   # tests: a function (url, ip, timeout, kind) -> (status, headers dict with lower-case keys, body bytes), instead of the network
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_GLOBAL_UNICAST = ipaddress.ip_network("2000::/3")
_TLS = ssl.create_default_context()     # built once: loading the trust store between connecting and shaking hands would eat the deadline (F-208)


class FetchError(Exception):
    """A fetch that did not happen; the text is fit to show a person and never repeats the address or the server's own words. `code` is for the log."""

    def __init__(self, message, code="error"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Fetched:
    url: str            # the address the bytes came from, after redirects
    content_type: str
    body: bytes

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def public(ip) -> bool:
    """Is this address one the open internet owns? False for everything inside a network or special-purpose, and for an unreadable address."""
    try:
        addr = ipaddress.ip_address(str(ip).split("%")[0])
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address):
        inner = addr.ipv4_mapped
        if inner is None and addr in ipaddress.ip_network("64:ff9b::/96"):
            inner = ipaddress.IPv4Address(addr.packed[-4:])
        if inner is None and addr in ipaddress.ip_network("2002::/16"):
            inner = ipaddress.IPv4Address(addr.packed[2:6])
        if inner is not None:
            return public(inner)
        return addr in _GLOBAL_UNICAST and addr.is_global and not addr.is_multicast      # "::127.0.0.1", "::ffff:0:7f00:1" and "fec0::1" are not
    return addr.is_global and not addr.is_multicast and addr not in _CGNAT


def _system_resolve(host, until):
    """The system resolver's addresses for `host`, asked in a thread of its own so that a resolver that hangs cannot hold the fetch past `until` (a time.monotonic() time)."""
    found = {}

    def look():
        try:
            found["ips"] = [i[4][0] for i in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]
        except (OSError, UnicodeError) as e:
            found["error"] = e

    t = threading.Thread(target=look, daemon=True, name="safefetch-lookup")
    t.start()
    t.join(max(0.0, until - time.monotonic()))
    if t.is_alive():
        raise FetchError("That website took too long to answer.", "timeout")
    if "error" in found:
        raise found["error"]
    return found["ips"]


def _resolve(host, until=None):
    until = time.monotonic() + TIMEOUT if until is None else until
    try:
        found = RESOLVER(host) if RESOLVER else _system_resolve(host, until)
    except (socket.gaierror, OSError, KeyError, UnicodeError):       # UnicodeError: a name the IDNA codec cannot write ("a..b") is no name at all
        raise FetchError("GitAway could not find that website.", "dns") from None
    found = list(dict.fromkeys(found))
    if not found:
        raise FetchError("GitAway could not find that website.", "dns")
    return found


def check(url, until=None):
    """(host, port, ip) for an address that is safe to fetch, or FetchError. Resolves the name (by `until`, a time.monotonic() time) and judges every address it answers with."""
    try:
        parts = urlsplit(url)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        raise FetchError("That link doesn't look right.", "bad_url") from None
    if parts.scheme not in ("http", "https") or not host or any(ord(c) < 33 for c in url) or "@" in parts.netloc:
        raise FetchError("Paste a web link that starts with https://.", "bad_url")
    if port not in (None, 80, 443):
        raise FetchError("Paste the plain link, without a port number.", "bad_port")
    ips = _resolve(host, until)
    if not all(public(ip) for ip in ips):
        raise FetchError("GitAway can only read public websites.", "private")
    return host, port or (443 if parts.scheme == "https" else 80), ips[0]


class _Pinned(http.client.HTTPConnection):
    """A connection that goes to the address we already checked, whatever the name would answer now."""
    ip = ""

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class _PinnedTLS(http.client.HTTPSConnection):
    ip = ""

    def connect(self):      # the certificate is checked against the NAME; the handshake runs where the watchdog can cut it, with what is left of the deadline (gitaway/deadline.py)
        deadline.handshake(self, socket.create_connection((self.ip, self.port), self.timeout), _TLS, self.deadline)


def _http(url, ip, timeout, kind, ua=USER_AGENT):
    """One request, no redirect followed: (status, headers, body). Reads at most the limit for `kind` plus one byte, and stops at the deadline: a socket timeout only bounds ONE
    wait, so gitaway/deadline.py's watchdog cuts the socket from outside, also after an answer that says it will close the connection (F-208). `ua` is the User-Agent sent."""
    parts = urlsplit(url)
    cls = _PinnedTLS if parts.scheme == "https" else _Pinned
    conn = cls(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), timeout=timeout)
    conn.ip = ip
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return deadline.get(conn, path, {"User-Agent": ua, "Accept": ", ".join(ACCEPT[kind]), "Accept-Encoding": "identity"}, time.monotonic() + timeout, LIMIT[kind] + 1)


def fetch(url, kind="html", timeout=None, asked=True) -> Fetched:
    """The bytes at `url` (html, json, xml (a sitemap or a feed, F-190), image, or a robots.txt, per `kind`), within TIMEOUT seconds in all, or `timeout` when that is less (a scan passes what is
    left of its budget, F-182). `asked`: the post's author asked for this read (their own paste); False for the captain's pre-draft, which says so in its User-Agent (F-194).
    Raises FetchError with a sentence fit to show; see the module's list for what is refused."""
    started = time.monotonic()
    total = TIMEOUT if timeout is None else min(TIMEOUT, timeout)
    send = TRANSPORT or (lambda u, ip, t, k: _http(u, ip, t, k, USER_AGENT if asked else USER_AGENT_UNASKED))
    for _hop in range(MAX_REDIRECTS + 1):
        left = total - (time.monotonic() - started)
        if left <= 0.25:
            raise FetchError("That website took too long to answer.", "timeout")
        _host, _port, ip = check(url, started + total)
        left = total - (time.monotonic() - started)      # the lookup took some of it
        if left <= 0.25:
            raise FetchError("That website took too long to answer.", "timeout")
        try:
            status, headers, body = send(url, ip, left, kind)
        except (TimeoutError, socket.timeout):
            raise FetchError("That website took too long to answer.", "timeout") from None
        except (OSError, http.client.HTTPException, ssl.SSLError, ValueError):      # ValueError: an address http.client cannot send ("/café" in a redirect)
            raise FetchError("GitAway could not open that website.", "network") from None
        if status in deadline.REDIRECTS:
            where = headers.get("location", "")
            if not where:
                raise FetchError("That website sent GitAway somewhere it could not follow.", "redirect")
            nxt = urljoin(url, where)
            if urlsplit(url).scheme == "https" and urlsplit(nxt).scheme != "https":
                raise FetchError("That website sent GitAway from a secure page to one that is not.", "redirect")
            url = nxt
            continue
        if not 200 <= status < 300:
            raise FetchError("That website would not let GitAway read the page.", f"http_{status}")
        ctype = headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype not in ACCEPT[kind]:
            raise FetchError("That link is not a web page GitAway can read." if kind != "image" else "That is not a picture GitAway can use.", "content_type")
        if len(body) > LIMIT[kind]:
            raise FetchError("That page is too big for GitAway to read.", "too_big")
        return Fetched(url, ctype, body)
    raise FetchError("That link sends GitAway round in circles.", "redirects")
