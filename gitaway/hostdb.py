"""The one door to fh-saas's host database.

fh-saas keeps a single shared connection to the host database (`HostDatabase.from_env()`), and its helpers (sign-in, membership checks,
tenant lookup) use it from whichever thread FastHTML runs a route on. Two threads on one connection corrupt each other, so every
GitAway use of the host database goes through `locked()`: the dev sign-in, the Google callback and the family database's
membership check. See docs/fh-saas-proposals.md (#9) for the package fix that would make this unnecessary.
"""

import threading
from contextlib import contextmanager

_LOCK = threading.RLock()


@contextmanager
def locked():
    """`with hostdb.locked():` use the host database (directly or through fh-saas helpers) without another thread on its connection."""
    with _LOCK:
        yield
