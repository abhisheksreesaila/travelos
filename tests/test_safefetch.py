"""F-183: fetching an address a creator typed must never reach our own network. Every case here is an address an attacker would try; the fake transport records whether a request was
ever made (it must not be for any refused address, and for a redirect it must not be made for the hop that points inside)."""

import pytest

from gitaway import safefetch

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
                                "::ffff:10.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::", "2002:a9fe:a9fe::"])
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
    net.pages = {"https://blog.example.com/go": (302, {"location": "http://169.254.169.254/latest/meta-data/"}, b"")}
    with pytest.raises(safefetch.FetchError) as e:
        safefetch.fetch("https://blog.example.com/go")
    assert e.value.code == "private"
    assert net.calls == [("https://blog.example.com/go", PUBLIC)]     # the first hop only: nothing was ever sent to the metadata address


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
