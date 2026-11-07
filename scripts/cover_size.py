"""How much JavaScript and data the signed-out landing (the cover, F-206) downloads, gzip -9 (what Cloudflare sends in front of gitaway.me).

    pixi run python scripts/cover_size.py

Counts every <script src> on the page wherever it comes from, every inline script, and the world cover.js loads when the live world is wanted
(world.js and everything it imports: the vendored three.js). A script from another site is counted from EXTERNAL, measured once; one that is
not there stops the count (ValueError), so the budget never skips a script silently. The Travelpayouts Drive script is off in the tests'
settings; switched on (TRAVELPAYOUTS_DRIVE_ID) it is one more external script to measure and add. tests/test_cover_budget.py holds the budget;
this prints the table.
"""
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BUDGET_JS = 250 * 1024
# Scripts from other sites, gzip -9 as gz() counts them, downloaded and measured 2026-11-07. FastHTML adds these four from jsDelivr to every page
# until F-207 switches them off (FastHTML(htmx=False, surreal=False)); surreal and css-scope-inline follow a branch (@main), so re-measure if they move.
EXTERNAL = {
    "https://cdn.jsdelivr.net/npm/htmx.org@2.0.7/dist/htmx.js": 37498,
    "https://cdn.jsdelivr.net/gh/answerdotai/fasthtml-js@1.0.12/fasthtml.js": 865,
    "https://cdn.jsdelivr.net/gh/answerdotai/surreal@main/surreal.js": 4128,
    "https://cdn.jsdelivr.net/gh/gnat/css-scope-inline@main/script.js": 867,
}
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
                todo.append(dep.split("?")[0])
            elif dep.startswith("."):
                todo.append(str(Path(url).parent / dep).replace("\\", "/"))
    return seen


def measure(html: str):
    """[(what, bytes gzip)] for the landing's JavaScript, and the world's data files [(file, bytes as sent)]."""
    rows = []
    for src in re.findall(r'<script[^>]*\ssrc="([^"]+)"', html):
        url = src.split("?")[0]
        if url.startswith("/") and not url.startswith("//"):
            rows.append((url, gz(asset(src).read_bytes())))
        elif url in EXTERNAL:
            rows.append((url, EXTERNAL[url]))
        else:
            raise ValueError(f"{src}: a script from another site that nobody has measured: download it, gzip -9 it and add it to EXTERNAL in scripts/cover_size.py")
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
