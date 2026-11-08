"""One HTTP GET that ends at its deadline whatever the server does (F-203, F-208): gitaway/weather.py asks MET Norway with it, and gitaway/safefetch.py
reads a creator's blog with it.

A socket timeout bounds only one wait, so a server that drips a byte at a time, or a TLS handshake that drags on, would hold a page for as long as it
likes. A watchdog timer shuts the socket down at the deadline, from outside, and the request then fails with TimeoutError. Three things keep the
watchdog able to reach the socket:
  - the TLS handshake runs on the TLS socket itself, set on the connection first (`handshake`): wrapping takes the plain socket's file over, so a
    shutdown sent to the plain one no longer reaches anything;
  - the socket is held here once connected, because http.client lets go of `conn.sock` as soon as an answer says it will close the connection;
  - the watchdog only shuts the socket down; it is closed by the request's own `finally`, after the watchdog is done, so no thread ever touches a file
    another thread closed.
The TLS handshake also gets only what is left of the deadline, and once the deadline has passed any error the request meets is a TimeoutError.
"""

import socket
import threading
import time

REDIRECTS = (301, 302, 303, 307, 308)     # answers that send the caller elsewhere: returned at once, with no body, and never followed here


def handshake(conn, raw, context, deadline):
    """Wrap the connected socket `raw` in TLS for `conn.host` (the certificate is checked against that name) and shake hands on the TLS socket itself,
    put on `conn` first so that a watchdog can cut a handshake that drags, and given only what is left of `deadline` (a time.monotonic() time): none
    left (the connection came up just as the deadline passed, after the watchdog had fired at nothing) is a TimeoutError before a byte is sent."""
    tls = context.wrap_socket(raw, server_hostname=conn.host, do_handshake_on_connect=False)
    conn.sock = tls
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("past the deadline")
    tls.settimeout(left)
    tls.do_handshake()


def get(conn, path, headers, deadline, limit):
    """GET `path` on `conn` (an http.client connection, not yet connected) by `deadline` (a time.monotonic() time): (status, headers with lower-case
    names, body). The body is read up to `limit` bytes (ask for one more than you accept, to tell "too big"); a redirect comes back with no body. Raises
    TimeoutError at the deadline, and what the connection raises before it (refused, a bad certificate). The connection learns its deadline as
    `conn.deadline` before it connects (`handshake` needs it)."""
    timed_out, held, resp = threading.Event(), {}, None

    def cut():
        timed_out.set()
        socks = [held.get("sock")]
        if getattr(conn, "sock", None) is not socks[0]:
            socks.append(getattr(conn, "sock", None))
        for sock in socks:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, AttributeError):
                pass

    watchdog = threading.Timer(max(0.0, deadline - time.monotonic()), cut)
    watchdog.daemon = True
    watchdog.start()
    try:
        conn.deadline = deadline
        conn.connect()
        held["sock"] = conn.sock
        if timed_out.is_set():          # the deadline passed while connecting, even if the connection came up after all
            raise TimeoutError("past the deadline")
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        got = {k.lower(): v for k, v in resp.getheaders()}
        if resp.status in REDIRECTS:
            return resp.status, got, b""
        body = bytearray()
        while len(body) < limit:
            if time.monotonic() > deadline:
                raise TimeoutError("past the deadline")
            chunk = resp.read(min(65536, limit - len(body)))
            if not chunk:
                break
            body += chunk
        if timed_out.is_set():
            raise TimeoutError("past the deadline")
        return resp.status, got, bytes(body)
    except Exception:
        if timed_out.is_set():          # once cut, a socket can break in ways no list would name: it is the deadline either way
            raise TimeoutError("past the deadline") from None
        raise
    finally:
        watchdog.cancel()
        watchdog.join()                 # a cut that has begun finishes before anything is closed
        for thing in (resp, conn, held.get("sock")):
            try:
                if thing is not None:
                    thing.close()
            except OSError:
                pass
