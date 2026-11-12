"""A copy of the test data folder for a script that edits files in place (forget a person, forget their orders).

The live test folder grows to hundreds of family databases over a run (about 800 MB with their write-ahead logs), and copying all of it
for each test filled /tmp when runs went in parallel (2026-11-12). A copy keeps every file except other families' databases: only the
families named in `keep` come along. The copy sits beside the folder as `<folder>-copy-<id>`, which conftest deletes when the run ends."""

import shutil
import uuid
from pathlib import Path


def copy_data(src: Path, keep) -> Path:
    keep = tuple(str(k) for k in keep)
    dst = Path(f"{src}-copy-{uuid.uuid4().hex[:8]}")    # its own folder per test: Windows cannot delete a database file a closed test still had open

    def others(folder, names):
        return [n for n in names if "_db.db" in n and not n.startswith(keep)] if Path(folder) == Path(src) else []

    shutil.copytree(src, dst, ignore=others)
    return dst
