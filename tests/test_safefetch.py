"""F-183: fetching an address a creator typed must never reach our own network. Every case here is an address an attacker would try; the fake transport records whether a request was
ever made (it must not be for any refused address, and for a redirect it must not be made for the hop that points inside)."""

import socket
import ssl
import time

import pytest

from gitaway import safefetch
from tests import tls_support, weather_support as ws

PUBLIC = "93.184.216.34"


class Net:
    """A fake network: `pages` maps a URL to (status, headers, body); `calls` lists the (url, ip) pairs the code actually connected to."""

    def __init__(self, pages=None, names=None):
        self.pages, self.calls, self.names = pages or {}, [], names or {}

    def resolve(self, host):
        return self.names.get(host, [PUBLIC])

    def send(self, url, ip, timeout, kind):
        self.calls.append((url, ip))
        return self.pages[url]


@pytest.fixture
def net(monkeypatch):
    n = Net()
    monkeypatch.setattr(safefetch, "RESOLVER", n.resolve)
    monkeypatch.setattr(safefetch, "TRANSPORT", n.send)
    return n


def html(body=b"<html>ok</html>", ctype="text/html; charset=utf-8"):
    return 200, {"content-type": ctype}, body


@pytest.mark.parametrize("ip", ["127.0.0.1", "127.1.2.3", "10.0.0.5", "172.16.4.4", "192.168.1.20", "169.254.169.254", "0.0.0.0", "100.64.0.1", "224.0.0.1", "::1", "::", "fe80::1", "fd00::1", "::ffff:127.0.0.1",
                                "::ffff:10.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::", "2002:a9fe:a9fe::",
                                "::127.0.0.1", "::169.254.169.254", "::ffff:0:127.0.0.1", "fec0::1"])        # IPv4-compatible, IPv4-translated, site-local: outside 2000::/3
def test_no_address_inside_a_network_is_public(ip):
    assert safefetch.public(ip) is False


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"])
def test_public_addresses_are_public(ip):
    assert safefetch.public(ip) is True


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://127.0.0.1:80/admin", "https://10.1.2.3/secret", "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                                 "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://192.168.0.1/router", "http://0.0.0.0/"])
def test_an_address_that_is_an_internal_ip_is_refused_before_any_request(net, url):
    net.names = {h: [h] for h in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "::ffff:127.0.0.1", "192.168.0.1", "0.0.0.0")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch(url)
    assert e.value.code == "private" and str(e.value) == "GitAway can only read public websites."
    assert net.calls == []


@pytest.mark.parametrize("url", ["http://2130706433/", "http://0x7f.0.0.1/", "http://localhost/", "http://127.1/"])
def test_names_the_system_resolver_turns_into_loopback_are_refused(monkeypatch, url):
    """The real resolver (no network is needed for these): decimal, hex and short forms and "localhost" all come back as 127.0.0.1."""
    monkeypatch.setattr(safefetch, "RESOLVER", None)
    called = []
    monkeypatch.setattr(safefetch, "TRANSPORT", lambda *a: called.append(a))
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch(url)
    assert e.value.code == "private" and called == []


def test_a_name_that_resolves_to_a_private_address_is_refused(net):
    net.names = {"internal.example.com": ["10.0.0.7"]}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://internal.example.com/post")
    assert e.value.code == "private" and net.calls == []


def test_a_name_with_one_public_and_one_private_address_is_refused(net):
    net.names = {"mixed.example.com": [PUBLIC, "127.0.0.1"]}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://mixed.example.com/post")
    assert e.value.code == "private" and net.calls == []


def test_the_connection_goes_to_the_address_that_was_checked(net):
    net.names = {"blog.example.com": ["93.184.216.35"]}
    net.pages = {"https://blog.example.com/post": html()}
    got = safefetch.fetch("https://blog.example.com/post")
    assert got.body == b"<html>ok</html>" and net.calls == [("https://blog.example.com/post", "93.184.216.35")]


def test_a_redirect_to_a_private_address_is_refused_and_never_followed(net):
    net.names = {"blog.example.com": [PUBLIC], "169.254.169.254": ["169.254.169.254"]}
    net.pages = {"http://blog.example.com/go": (302, {"location": "http://169.254.169.254/latest/meta-data/"}, b"")}     # http to http: the address is what refuses it
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("http://blog.example.com/go")
    assert e.value.code == "private"
    assert net.calls == [("http://blog.example.com/go", PUBLIC)]     # the first hop only: nothing was ever sent to the metadata address


def test_a_redirect_to_a_name_that_resolves_inside_is_refused(net):
    net.names = {"evil.example.com": ["10.0.0.9"]}
    net.pages = {"https://blog.example.com/go": (301, {"location": "https://evil.example.com/x"}, b"")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/go")
    assert e.value.code == "private" and len(net.calls) == 1


def test_a_relative_redirect_is_followed_and_checked(net):
    net.pages = {"https://blog.example.com/old": (301, {"location": "/new"}, b""), "https://blog.example.com/new": html(b"<p>new</p>")}
    got = safefetch.fetch("https://blog.example.com/old")
    assert got.url == "https://blog.example.com/new" and got.body == b"<p>new</p>"


def test_at_most_five_redirects(net):
    for i in range(10):
        net.pages[f"https://blog.example.com/{i}"] = (302, {"location": f"/{i + 1}"}, b"")
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/0")
    assert e.value.code == "redirects" and len(net.calls) == 6      # the first request and five redirects


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/a", "gopher://example.com/", "javascript:alert(1)", "https://example.com:8443/a", "http://example.com:22/",
                                 "https://user:pw@example.com/", "https://example.com/a b", "https:///nothing"])
def test_only_plain_http_and_https_addresses_are_fetched(net, url):
    with pytest.raises(safefetch.FetchError):
        safefetch.fetch(url)
    assert net.calls == []


def test_a_page_over_two_megabytes_is_refused(net):
    net.pages = {"https://blog.example.com/big": html(b"x" * (safefetch.MAX_BYTES + 1))}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/big")
    assert e.value.code == "too_big"


def test_a_page_of_exactly_the_limit_is_read(net):
    net.pages = {"https://blog.example.com/ok": html(b"x" * safefetch.MAX_BYTES)}
    assert len(safefetch.fetch("https://blog.example.com/ok").body) == safefetch.MAX_BYTES


@pytest.mark.parametrize("ctype", ["application/pdf", "application/octet-stream", "image/png", "application/javascript", ""])
def test_only_html_is_read_as_a_page(net, ctype):
    net.pages = {"https://blog.example.com/f": html(b"data", ctype)}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/f")
    assert e.value.code == "content_type"


def test_an_image_is_read_only_when_asked_for_as_one(net):
    net.pages = {"https://blog.example.com/p.jpg": (200, {"content-type": "image/jpeg"}, b"\xff\xd8x")}
    assert safefetch.fetch("https://blog.example.com/p.jpg", "image").content_type == "image/jpeg"
    with pytest.raises(safefetch.FetchError):
        safefetch.fetch("https://blog.example.com/p.jpg", "html")


def test_a_slow_server_is_a_friendly_timeout(net, monkeypatch):
    def slow(url, ip, timeout, kind):
        raise TimeoutError("slow")
    monkeypatch.setattr(safefetch, "TRANSPORT", slow)
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/x")
    assert e.value.code == "timeout" and str(e.value) == "That website took too long to answer."


def test_the_total_time_is_eight_seconds_across_redirects(net, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(safefetch.time, "monotonic", lambda: clock[0])
    seen = []

    def send(url, ip, timeout, kind):
        seen.append(round(timeout, 1))
        clock[0] += 3.0
        return 302, {"location": "/next"}, b""
    monkeypatch.setattr(safefetch, "TRANSPORT", send)
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/x")
    assert e.value.code == "timeout" and seen == [8.0, 5.0, 2.0]


def test_an_error_page_is_not_read(net):
    net.pages = {"https://blog.example.com/gone": (404, {"content-type": "text/html"}, b"<html>nope</html>")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/gone")
    assert e.value.code == "http_404"


def test_the_real_transport_asks_for_no_compression_and_the_checked_address(monkeypatch):
    """The real `_http` with a fake socket: the request names the host, asks for identity encoding, and connects to the pinned address, not to the name."""
    import socket

    sent, dialled = [], []

    class Sock:
        def __init__(self):
            self.buf = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5\r\n\r\nhello"

        def sendall(self, data):
            sent.append(data)

        def makefile(self, mode="rb", buffering=None):
            import io
            return io.BytesIO(self.buf)

        def close(self):
            pass

        def settimeout(self, t):
            pass

    monkeypatch.setattr(socket, "create_connection", lambda addr, timeout=None, **kw: dialled.append(addr) or Sock())
    status, headers, body = safefetch._http("http://blog.example.com/p?a=1", "93.184.216.34", 5, "html")
    assert (status, body) == (200, b"hello") and dialled == [("93.184.216.34", 80)]
    request = b"".join(sent).decode()
    assert request.startswith("GET /p?a=1 HTTP/1.1") and "Host: blog.example.com" in request and "Accept-Encoding: identity" in request


def _drip_server(stage):
    """A local server that never finishes: stage "body" sends headers then one byte a 0.3 s forever; "headers" sends the status line then one header byte at a time; "silent" accepts and says nothing;
    "close" says "Connection: close" (so http.client lets go of conn.sock), then drips the body for six seconds and hangs up (F-208)."""
    import socket
    import threading
    import time

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    stop = threading.Event()

    def serve():
        srv.settimeout(0.2)
        conns = []
        while not stop.is_set():
            try:
                c, _ = srv.accept()
            except OSError:
                continue
            conns.append(c)
            threading.Thread(target=drip, args=(c,), daemon=True).start()
        for c in conns:
            c.close()
        srv.close()

    def drip(c):
        try:
            c.recv(4096)
            if stage == "silent":
                stop.wait(30)
                return
            head = {"body": b"Content-Length: 99999\r\n\r\n", "close": b"Connection: close\r\nContent-Length: 99999\r\n\r\n"}.get(stage, b"")
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n" + head)
            ends = time.monotonic() + 6
            while not stop.is_set() and (stage != "close" or time.monotonic() < ends):
                c.sendall(b"x" if stage in ("body", "close") else b"X-A: ")
                time.sleep(0.3)
            if stage == "close":
                c.close()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1], stop


@pytest.mark.parametrize("stage", ["body", "headers", "silent"])
def test_a_server_that_drips_bytes_cannot_hold_the_fetch_past_the_deadline(stage):
    """The deadline is enforced from outside the socket: a slow-drip body, slow-drip headers and silence all end within the limit, not when the server gets bored."""
    import time

    port, stop = _drip_server(stage)
    try:
        started = time.monotonic()
        with pytest.raises((TimeoutError, OSError, safefetch.http.client.HTTPException)):
            safefetch._http(f"http://127.0.0.1:{port}/", "127.0.0.1", 2, "html")
        assert time.monotonic() - started < 3.0
    finally:
        stop.set()



def test_a_server_that_says_it_will_close_and_then_drips_is_still_cut_at_the_deadline():
    """F-208: once an answer says "Connection: close", http.client lets go of conn.sock, so a watchdog that looks there reaches nothing and a creator's
    dripping blog held the fetch for as long as it dripped. gitaway/deadline.py holds the socket itself."""
    import time

    port, stop = _drip_server("close")
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            safefetch._http(f"http://127.0.0.1:{port}/", "127.0.0.1", 1.0, "html")
        assert time.monotonic() - started < 1.5
    finally:
        stop.set()



# ---- F-208 final fixes: redirects that cannot be followed, a lookup within the deadline --------------------------------------------------

def test_a_redirect_from_https_to_http_is_refused(net):
    net.pages = {"https://blog.example.com/go": (301, {"location": "http://blog.example.com/plain"}, b"")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/go")
    assert e.value.code == "redirect" and net.calls == [("https://blog.example.com/go", PUBLIC)]


def test_a_creator_may_still_paste_an_http_link_and_be_sent_on_to_https(net):
    net.pages = {"http://blog.example.com/a": (301, {"location": "https://blog.example.com/a"}, b""), "https://blog.example.com/a": html(b"<p>a</p>")}
    assert safefetch.fetch("http://blog.example.com/a").body == b"<p>a</p>"


def test_a_redirect_to_a_name_that_cannot_be_encoded_is_a_failed_lookup(net):
    def resolve(host):
        host.encode("idna")         # what the system resolver does first: "a..b" has an empty label
        return [PUBLIC]
    net.resolve = resolve
    safefetch.RESOLVER = resolve
    net.pages = {"https://blog.example.com/go": (302, {"location": "https://a..b/x"}, b"")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/go")
    assert e.value.code == "dns"


def test_a_redirect_the_transport_cannot_send_is_a_network_failure(net, monkeypatch):
    calls = []

    def send(url, ip, timeout, kind):
        calls.append(url)
        if len(calls) == 1:
            return 302, {"location": "/café"}, b""
        raise UnicodeEncodeError("ascii", url, 30, 31, "ordinal not in range(128)")     # http.client cannot put /café on the request line
    monkeypatch.setattr(safefetch, "TRANSPORT", send)
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/go")
    assert e.value.code == "network" and len(calls) == 2


def test_a_resolver_that_hangs_is_cut_at_the_fetchs_deadline(monkeypatch):
    monkeypatch.setattr(safefetch, "RESOLVER", None)

    def hangs(*a, **k):
        time.sleep(2)
        raise OSError("no answer")
    monkeypatch.setattr(socket, "getaddrinfo", hangs)
    started = time.monotonic()
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/p", timeout=1.0)
    assert e.value.code == "timeout" and time.monotonic() - started < 1.3


def test_the_time_a_lookup_took_counts_before_anything_is_sent(net):
    def slow(host):
        time.sleep(0.9)
        return [PUBLIC]
    safefetch.RESOLVER = slow
    net.pages = {"https://blog.example.com/p": html()}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/p", timeout=1.0)
    assert e.value.code == "timeout" and net.calls == []


# ---- F-208 final fixes: the real transport over TLS, through the pinned address -----------------------------------------------------------

@pytest.fixture
def blog(tmp_path, monkeypatch):
    """A local TLS server with a certificate for blog.invalid (a name no resolver knows), from a test CA; the transport is pinned to 127.0.0.1.
    Nothing may leave this machine, and every address dialled is kept."""
    ws.local_only(monkeypatch)
    dialled, real = [], socket.create_connection

    def dial(address, *a, **kw):
        dialled.append(address[0])
        return real(address, *a, **kw)
    monkeypatch.setattr(socket, "create_connection", dial)
    ca, cert, key = tls_support.make_certs(tmp_path, "blog.invalid")
    server = tls_support.TLSServer(cert, key, b"<html>ok</html>")
    monkeypatch.setattr(safefetch, "_TLS", ssl.create_default_context(cafile=str(ca)), raising=False)
    state = {"port": server.port, "dialled": dialled, "tmp": tmp_path}
    yield state
    server.close()


def test_the_real_transport_reads_https_through_the_pinned_address_with_a_verified_certificate(blog):
    status, _headers, body = safefetch._http(f"https://blog.invalid:{blog['port']}/p", "127.0.0.1", 3, "html")
    assert (status, body) == (200, b"<html>ok</html>") and blog["dialled"] == ["127.0.0.1"]


def test_the_real_transport_refuses_a_certificate_for_another_name(blog, monkeypatch):
    folder = blog["tmp"] / "evil"
    folder.mkdir()
    ca, cert, key = tls_support.make_certs(folder, "evil.example")
    other = tls_support.TLSServer(cert, key, b"<html>evil</html>")
    monkeypatch.setattr(safefetch, "_TLS", ssl.create_default_context(cafile=str(ca)))      # a trusted CA, the wrong name
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            safefetch._http(f"https://blog.invalid:{other.port}/p", "127.0.0.1", 3, "html")
    finally:
        other.close()


def test_a_tls_handshake_that_drags_is_cut_at_the_deadline(blog):
    proxy = tls_support.DripProxy(blog["port"], chunk=16, gap=0.1)
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            safefetch._http(f"https://blog.invalid:{proxy.port}/p", "127.0.0.1", 1.0, "html")
        assert time.monotonic() - started < 1.2
    finally:
        proxy.close()


def test_a_connection_that_comes_up_just_as_the_deadline_passes_never_starts_a_slow_handshake(blog, monkeypatch):
    """Security L1: the handshake gets only what is left of the deadline; the watchdog had fired while the socket was still connecting."""
    proxy = tls_support.DripProxy(blog["port"], chunk=16, gap=0.1)
    real, started = socket.create_connection, time.monotonic()

    def late(address, *a, **kw):
        time.sleep(max(0.0, started + 1.02 - time.monotonic()))        # the TCP connection is ready just after the deadline
        return real(address, *a, **kw)
    monkeypatch.setattr(socket, "create_connection", late)
    try:
        with pytest.raises(TimeoutError):
            safefetch._http(f"https://blog.invalid:{proxy.port}/p", "127.0.0.1", 1.0, "html")
        assert time.monotonic() - started < 1.25
    finally:
        proxy.close()


def test_the_tls_context_is_built_once_not_between_connecting_and_shaking_hands(blog, monkeypatch):
    made = []
    monkeypatch.setattr(ssl, "create_default_context", lambda *a, **k: made.append(1) or ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    assert safefetch._http(f"https://blog.invalid:{blog['port']}/p", "127.0.0.1", 3, "html")[0] == 200
    assert made == []


def test_the_tls_context_checks_every_certificate_and_its_name():
    assert safefetch._TLS.verify_mode == ssl.CERT_REQUIRED and safefetch._TLS.check_hostname
