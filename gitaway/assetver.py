"""Content-hashed asset URLs (F-044).

Every /assets/css/*.css and /assets/js/*.js link in a page gets `?v=<hash of the file>`, so a changed file is a new URL:
the phone's service worker and the browser can keep assets for ever and still never pair old CSS or JS with fresh HTML.
AssetVersionMiddleware adds the hash to the HTML on the way out, so no page module has to remember it.
"""

import hashlib
import re
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LINK = re.compile(r'(\b(?:href|src)=")(/assets/(?:css|js)/[^"?#]+\.(?:css|js))(")')
_seen: dict = {}


def file_hash(url_path: str):
    """First 8 hex digits of the file's SHA-1, or None when there is no such file. Cached until the file changes."""
    path = ASSETS_DIR / url_path.removeprefix("/assets/")
    try:
        st = path.stat()
    except OSError:
        return None
    sig = (str(path), st.st_mtime_ns, st.st_size)
    hit = _seen.get(path)
    if hit and hit[0] == sig:
        return hit[1]
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
    _seen[path] = (sig, digest)
    return digest


def versioned(url_path: str) -> str:
    h = file_hash(url_path)
    return f"{url_path}?v={h}" if h else url_path


def rewrite(html: str) -> str:
    return LINK.sub(lambda m: f"{m.group(1)}{versioned(m.group(2))}{m.group(3)}", html)


class AssetVersionMiddleware:
    """Pure ASGI (no thread hop, so request context survives): buffers HTML responses and versions their asset links."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start, body = None, []

        async def wrapped(message):
            nonlocal start
            if message["type"] == "http.response.start":
                ctype = dict(message["headers"]).get(b"content-type", b"")
                if ctype.startswith(b"text/html"):
                    start = message
                    return
                return await send(message)
            if start is None:
                return await send(message)
            body.append(message.get("body", b""))
            if message.get("more_body"):
                return
            data = rewrite(b"".join(body).decode("utf-8")).encode("utf-8")
            headers = [(k, v) for k, v in start["headers"] if k.lower() != b"content-length"]
            headers.append((b"content-length", str(len(data)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": data})

        await self.app(scope, receive, wrapped)
