"""Every file the Dockerfile copies reaches the build: .dockerignore must not drop it (a release once failed to build because
docs/research/creators.csv was copied but docs/* was ignored)."""

import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ignored(path: str) -> bool:
    """.dockerignore's verdict for `path`: the last matching line wins, a `!` line lets it back in, a match on a parent folder counts."""
    verdict = False
    for line in (ROOT / ".dockerignore").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keep, pattern = line.startswith("!"), line.lstrip("!").rstrip("/")
        parts = path.split("/")
        if any(fnmatch.fnmatch("/".join(parts[:i]), pattern) for i in range(1, len(parts) + 1)):
            verdict = not keep
    return verdict


def test_every_file_the_dockerfile_copies_is_in_the_build_context():
    sources = [line.split()[1] for line in (ROOT / "Dockerfile").read_text().splitlines()
               if line.startswith("COPY ") and "--from" not in line]
    for src in sources:
        assert (ROOT / src).exists(), f"the Dockerfile copies {src}, which is not in the repo"
        assert not _ignored(src), f"the Dockerfile copies {src}, but .dockerignore leaves it out of the build"
