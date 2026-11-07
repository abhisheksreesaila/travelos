"""gitaway/deadline.py, the GET that ends at its deadline (F-203, F-208), tested on its own: it reads no more than it is told, and once the deadline has
passed whatever goes wrong is a TimeoutError, the watchdog done with the sockets before they are closed. Everything is local (127.0.0.1 or fakes)."""

import http.client
import http.server
import threading
import time

import pytest

from gitaway import deadline


class Endless:
    """A local server whose every answer is a 200 with a body far bigger than anyone should read."""

    def __init__(self, size=2_000_000):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(size))
                self.end_headers()
                try:
                    for _ in range(size // 65536 + 1):
                        self.wfile.write(b"x" * 65536)
                except OSError:
                    pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def connection(self):
        return http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_it_reads_exactly_the_limit_from_a_server_that_streams_far_more():
    server = Endless()
    try:
        status, _headers, body = deadline.get(server.connection(), "/", {}, time.monotonic() + 5, 1000)
        assert (status, len(body)) == (200, 1000)
        assert len(deadline.get(server.connection(), "/", {}, time.monotonic() + 5, 70_001)[2]) == 70_001      # across reads, too
    finally:
        server.close()


class _Sock:
    """A socket whose shutdown is slow (the watchdog's cut takes a while) and that logs what is done to it."""

    def __init__(self, log):
        self.log = log

    def shutdown(self, how):
        self.log.append("cut begins")
        time.sleep(0.3)
        self.log.append("cut ends")

    def close(self):
        self.log.append("closed")


class _Stuck:
    """A connection whose answer arrives only after the deadline, and then breaks in a way no list of exceptions would name."""

    def __init__(self, log, error):
        self.log, self.error, self.sock = log, error, None

    def connect(self):
        self.sock = _Sock(self.log)

    def request(self, *a, **k):
        pass

    def getresponse(self):
        time.sleep(0.45)            # the watchdog fires at 0.2 s and starts its slow cut
        raise self.error

    def close(self):
        self.log.append("conn closed")


@pytest.mark.parametrize("error", [AttributeError("'NoneType' object has no attribute 'recv_into'"), RuntimeError("anything at all")], ids=["attribute", "runtime"])
def test_once_the_deadline_has_passed_whatever_goes_wrong_is_a_timeout(error):
    with pytest.raises(TimeoutError):
        deadline.get(_Stuck([], error), "/", {}, time.monotonic() + 0.2, 100)


def test_the_watchdog_is_done_with_the_socket_before_it_is_closed():
    log = []
    with pytest.raises(TimeoutError):
        deadline.get(_Stuck(log, OSError("cut")), "/", {}, time.monotonic() + 0.2, 100)
    assert log.index("cut ends") < log.index("closed") and log.count("cut begins") == 1      # one cut, finished before anything is closed
