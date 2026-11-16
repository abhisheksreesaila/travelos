"""The folder of the voice notes people recorded on plans before F-254 (F-091), and the one thing still done with it: `purge_trip` deletes a trip's audio files when the trip is deleted, so "delete" still
means delete. Nothing records, saves or serves a voice note any more (the plan chat is text; the Together drawer has no microphone), so the rest of the module went. Files live under
`<data folder>/voicenotes/<family>/<trip>/`.
"""

import re
import shutil
from pathlib import Path

from gitaway import auth

_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def root() -> Path:
    return auth.data_dir() / "voicenotes"


def _folder(tenant_id, trip_id) -> str:
    return f"{_SAFE.sub('_', tenant_id or '')[:80]}/{_SAFE.sub('_', trip_id or '')[:80]}"


def purge_trip(tenant_id, trip_id) -> None:
    """Delete the voice folder of a trip that is gone (its rows go in the same transaction as the trip: gitaway.importer.delete)."""
    shutil.rmtree(root() / _folder(tenant_id, trip_id), ignore_errors=True)
