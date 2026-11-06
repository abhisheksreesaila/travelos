"""Fetch a web address a person typed, without letting it reach anything inside our own network (F-183, the SSRF guard).

    fetch(url, kind="html")   the page's bytes as a `Fetched`, or FetchError with a sentence fit to show

The address is untrusted: it can name this machine, the cloud's metadata service, a private network, or redirect there. So, in this order and on every hop:

  1. http or https only, the default port only (80, 443), no user name or password in the address;
  2. the name is resolved here and EVERY address it gives must be a public one (not loopback, private, link-local, carrier-grade NAT, multicast, reserved or unspecified;
     an IPv4 address wrapped in an IPv6 one, "::ffff:127.0.0.1", "64:ff9b::7f00:1" or a 6to4 "2002:7f00:1::", is judged by the IPv4 address inside);
  3. the connection goes to the address we checked (never the name again), so a name that answers differently a second time (DNS rebinding) cannot slip through;
  4. a redirect is followed by hand, at most MAX_REDIRECTS times, and goes through 1 to 3 again;
  5. at most MAX_BYTES (2 MB for a page, MAX_IMAGE for a picture) are read, within TIMEOUT seconds in all, only the content type asked for (`kind`), no compression.

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

MAX_REDIRECTS = 5
MAX_BYTES = 2 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
TIMEOUT = 8.0
USER_AGENT = "GitAwayBot/1.0 (+https://gitaway.me; reads a post its author asked us to read)"
ACCEPT = {"html": ("text/html", "application/xhtml+xml"), "json": ("application/json",), "xml": ("application/xml", "text/xml", "application/rss+xml", "application/atom+xml"), "image": ("image/jpeg", "image/png", "image/webp")}
LIMIT = {"html": MAX_BYTES, "json": MAX_BYTES, "xml": MAX_BYTES, "image": MAX_IMAGE}
RESOLVER = None    # tests: a function name -> list of address strings, instead of DNS
TRANSPORT = None   # tests: a function (url, ip, timeout, kind) -> (status, headers dict with lower-case keys, body bytes), instead of the network
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


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
        return addr.is_global and not addr.is_multicast
    return addr.is_global and not addr.is_multicast and addr not in _CGNAT


def _resolve(host):
    try:
        found = RESOLVER(host) if RESOLVER else [i[4][0] for i in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]
    except (socket.gaierror, OSError, KeyError):
        raise FetchError("GitAway could not find that website.", "dns") from None
    found = list(dict.fromkeys(found))
    if not found:
        raise FetchError("GitAway could not find that website.", "dns")
    return found


def check(url):
    """(host, port, ip) for an address that is safe to fetch, or FetchError. Resolves the name and judges every address it answers with."""
    try:
        parts = urlsplit(url)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        raise FetchError("That link doesn't look right.", "bad_url") from None
    if parts.scheme not in ("http", "https") or not host or any(ord(c) < 33 for c in url) or "@" in parts.netloc:
        raise FetchError("Paste a web link that starts with https://.", "bad_url")
    if port not in (None, 80, 443):
        raise FetchError("Paste the plain link, without a port number.", "bad_port")
    ips = _resolve(host)
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

    def connect(self):
        raw = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = raw      # so the watchdog can cut a handshake that drips too
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)   # the certificate is checked against the NAME


def _http(url, ip, timeout, kind):
    """One request, no redirect followed: (status, headers, body). Reads at most the limit for `kind` plus one byte, and stops at the deadline."""
    parts = urlsplit(url)
    cls = _PinnedTLS if parts.scheme == "https" else _Pinned
    conn = cls(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), timeout=timeout)
    conn.ip = ip
    deadline = time.monotonic() + timeout
    timed_out = threading.Event()

    def cut():      # the hard deadline, from outside the socket: a socket timeout only bounds ONE wait, so a server dripping a byte at a time would hold us for ever
        timed_out.set()
        for act in ("shutdown", "close"):
            try:
                getattr(conn.sock, act)(*((socket.SHUT_RDWR,) if act == "shutdown" else ()))
            except (OSError, AttributeError):
                pass

    watchdog = threading.Timer(timeout, cut)
    watchdog.daemon = True
    watchdog.start()
    try:
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        conn.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": ", ".join(ACCEPT[kind]), "Accept-Encoding": "identity"})
        resp = conn.getresponse()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        if resp.status in (301, 302, 303, 307, 308):
            return resp.status, headers, b""
        limit, body = LIMIT[kind] + 1, bytearray()
        while len(body) < limit:
            if time.monotonic() > deadline:
                raise TimeoutError("the fetch took too long")
            chunk = resp.read(min(65536, limit - len(body)))
            if not chunk:
                break
            body += chunk
        return resp.status, headers, bytes(body)
    except (OSError, http.client.HTTPException, ValueError):
        if timed_out.is_set():
            raise TimeoutError("the fetch took too long") from None
        raise
    finally:
        watchdog.cancel()
        conn.close()


def fetch(url, kind="html") -> Fetched:
    """The bytes at `url` (html, json, xml (a sitemap or a feed, F-190) or image, per `kind`). Raises FetchError with a sentence fit to show; see the module's list for what is refused."""
    started = time.monotonic()
    send = TRANSPORT or _http
    for _hop in range(MAX_REDIRECTS + 1):
        left = TIMEOUT - (time.monotonic() - started)
        if left <= 0.25:
            raise FetchError("That website took too long to answer.", "timeout")
        _host, _port, ip = check(url)
        try:
            status, headers, body = send(url, ip, left, kind)
        except (TimeoutError, socket.timeout):
            raise FetchError("That website took too long to answer.", "timeout") from None
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise FetchError("GitAway could not open that website.", "network") from None
        if status in (301, 302, 303, 307, 308):
            where = headers.get("location", "")
            if not where:
                raise FetchError("That website sent GitAway somewhere it could not follow.", "redirect")
            url = urljoin(url, where)
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
