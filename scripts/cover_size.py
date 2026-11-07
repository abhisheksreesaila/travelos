"""How much JavaScript and data the signed-out landing (the cover, F-206) downloads, gzip -9 (what Cloudflare sends in front of gitaway.me).

    pixi run python scripts/cover_size.py

Counts every same-origin <script src> and inline script on the page, plus the world cover.js loads when the live world is wanted (world.js and
everything it imports: the vendored three.js). The Travelpayouts Drive script, when it is switched on, is another site's and not counted.
tests/test_cover_budget.py holds the budget; this prints the table.
"""
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BUDGET_JS = 250 * 1024
IMPORT = re.compile(r"""(?:import|export)\s*(?:[\w*{}\s,$]*?\s*from\s*)?["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)""")


def gz(data: bytes) -> int:
    return len(gzip.compress(data, 9))


def asset(url: str) -> Path:
    path = url.split("?")[0]
    assert path.startswith("/assets/"), url
    return ASSETS / path[len("/assets/"):]


def module_graph(entry: str):
    """The entry module and every module it imports, statically, by absolute or relative URL."""
    seen, todo = [], [entry.split("?")[0]]
    while todo:
        url = todo.pop()
        if url in seen:
            continue
        seen.append(url)
        text = asset(url).read_text(encoding="utf-8")
        for a, b in IMPORT.findall(text):
            dep = a or b
            if dep.startswith("/"):
                todo.append(dep)
            elif dep.startswith("."):
                todo.append(str(Path(url).parent / dep).replace("\\", "/"))
    return seen


def measure(html: str):
    """[(what, bytes gzip)] for the landing's JavaScript, and the world's data files [(file, bytes as sent)]."""
    rows = []
    for src in re.findall(r'<script[^>]*\ssrc="([^"]+)"', html):
        if src.startswith("/"):
            rows.append((src.split("?")[0], gz(asset(src).read_bytes())))
    for i, body in enumerate(re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S)):
        if body.strip():
            rows.append((f"inline script {i + 1}", gz(body.encode())))
    world = re.search(r'data-world="([^"]+)"', html).group(1)
    for url in module_graph(world):
        rows.append((url, gz(asset(url).read_bytes())))
    data = [(p.name, p.stat().st_size) for p in sorted((ASSETS / "cover").glob("tahoe-*.gz"))]
    return rows, data


def main():
    sys.path.insert(0, str(ROOT))
    import tests.conftest  # noqa: F401  (the test settings: a throwaway data folder, the local sign-in)
    from starlette.testclient import TestClient
    from main import app
    rows, data = measure(TestClient(app).get("/").text)
    total = sum(n for _, n in rows)
    for what, n in rows:
        print(f"{n / 1024:8.1f} KB  {what}")
    print(f"{total / 1024:8.1f} KB  landing JavaScript, gzip (budget {BUDGET_JS / 1024:.0f} KB)")
    for name, n in data:
        print(f"{n / 1024:8.1f} KB  {name} (already gzip)")


if __name__ == "__main__":
    main()
