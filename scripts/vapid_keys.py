"""Make the VAPID key pair for the morning plan push (F-066) and put it in ./.env.

    pixi run vapid-keys mailto:you@example.com [--force]   (or the site's https:// address)

Writes GITAWAY_VAPID_PUBLIC, GITAWAY_VAPID_PRIVATE and GITAWAY_VAPID_SUBJECT into the project's .env (gitignored; created if missing).
The private key is never printed. It refuses to replace keys that are already there unless you pass --force, because new keys
silently end every phone's morning plan until each person turns it on again. docs/setup.md shows how to send the same three
values to Railway without printing them.
"""

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01

ENV = Path(__file__).resolve().parent.parent / ".env"
NAMES = ("GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_pair() -> dict:
    """{"public": the uncompressed P-256 point the browser subscribes with, "private": the raw 32-byte scalar}, both URL-safe base64."""
    v = Vapid01()
    v.generate_keys()
    public = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    return {"public": _b64(public), "private": _b64(private)}


def write_env(path: Path, values: dict, force=False) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    have = {line.split("=", 1)[0] for line in lines if "=" in line and not line.lstrip().startswith("#")}
    if "GITAWAY_VAPID_PRIVATE" in have and not force:
        raise SystemExit("There are already push keys in .env. Replacing them ends every phone's morning plan until each person turns it on again. Run again with --force if you mean it.")
    kept = [line for line in lines if line.split("=", 1)[0] not in values]
    kept += [f"{k}={v}" for k, v in values.items()]
    path.write_text("\n".join(kept) + "\n")
    path.chmod(0o600)


def main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    subject = args[0] if args else ""
    if not ((subject.startswith("mailto:") and "@" in subject) or subject.startswith("https://")):
        print("Usage: pixi run vapid-keys mailto:you@example.com|https://your.site [--force]\nThe address is the contact push services may use if your server misbehaves.", file=sys.stderr)
        return 2
    pair = make_pair()
    write_env(ENV, {"GITAWAY_VAPID_PUBLIC": pair["public"], "GITAWAY_VAPID_PRIVATE": pair["private"], "GITAWAY_VAPID_SUBJECT": subject}, force="--force" in argv)
    print(f"Wrote {', '.join(NAMES)} to {ENV} (the private key is not shown).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
