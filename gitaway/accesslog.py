"""A claim link is the key to a creator's draft: it must not sit in the server's access log (F-182). uvicorn logs every request line, path included; this filter swaps
`/claim/<token>` for `/claim/[link]` (and a `/wallet/<vendor>/<token>` the same way) in the `uvicorn.access` records. (Railway's own edge log sees the path too: that one is outside the app, see docs/decisions.md.)"""

import logging
import re

_TOKEN = re.compile(r"/claim/[A-Za-z0-9_-]{20,}")
_WALLET = re.compile(r"(/wallet/(?:apple|google)/)[A-Za-z0-9_.=-]{20,}")      # F-288: a wallet link names a booking and a family, so the log keeps neither


class Redact(logging.Filter):
    def filter(self, record) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_WALLET.sub(r"\1[link]", _TOKEN.sub("/claim/[link]", a)) if isinstance(a, str) else a for a in record.args)
        return True


def install() -> None:
    log = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, Redact) for f in log.filters):
        log.addFilter(Redact())
