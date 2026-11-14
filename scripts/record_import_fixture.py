"""Record one real blog post for the creator-import tests (F-235): `pixi run python scripts/record_import_fixture.py <url> <name>`.

Reads the post the way the app does (robots.txt first, then the page, through the app's safe fetcher) and keeps what the network answered in tests/fixtures/creator_import/<name>/:
robots.txt, page.html, lead.jpg (the post's first picture, when it has one) and meta.json (the address, the status codes, the date it was read). Tests replay these through
`safefetch.TRANSPORT`, so no test reaches the network. The model's answer is NOT recorded here: it needs ANTHROPIC_API_KEY (`pixi run probe-import <url>` prints it).
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitaway import importsource, safefetch  # noqa: E402

seen = {}


def recording(url, ip, timeout, kind):
    got = safefetch._http(url, ip, timeout, kind)
    seen[url] = got
    return got


def main(url, name):
    safefetch.TRANSPORT = recording
    material = importsource.gather(url)
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "creator_import" / name
    out.mkdir(parents=True, exist_ok=True)
    meta = {"url": url, "read": date.today().isoformat(), "title": material.title, "by": material.by, "lead": material.images[0] if material.images else "", "responses": {}}
    for u, (status, headers, body) in seen.items():
        file = "robots.txt" if u.endswith("/robots.txt") else "page.html"
        (out / file).write_bytes(body)
        meta["responses"][u] = {"status": status, "file": file, "content-type": headers.get("content-type", "")}
    if material.images:
        try:
            got = safefetch.fetch(material.images[0], "image")
            (out / "lead.jpg").write_bytes(got.body)
        except Exception as e:  # noqa: BLE001
            print("no lead picture kept:", e)
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(material.title, "|", material.by, "|", len(material.text), "chars |", len(material.images), "pictures |", meta["lead"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
