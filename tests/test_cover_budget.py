"""F-206: the cover's budget and its build. The landing's JavaScript stays within 250 KB gzipped with three.js inside it; three.js is self-hosted,
version-pinned and keeps its licence; the world shipped was built from the sources in cover3d/src; the terrain data stays small."""
import gzip
import hashlib
import json
import re
from pathlib import Path

from scripts.cover_size import BUDGET_JS, measure, module_graph

ROOT = Path(__file__).resolve().parent.parent
THREE = ROOT / "assets/vendor/three-0.187.0"
WORLD = ROOT / "assets/js/cover/world.js"


def test_the_landing_javascript_fits_in_250_kb_gzipped(client, capsys):
    rows, _ = measure(client.get("/").text)
    names = [w for w, _ in rows]
    assert "/assets/vendor/three-0.187.0/three.cover.min.js" in names and "/assets/js/cover/world.js" in names and "/assets/js/cover.js" in names
    total = sum(n for _, n in rows)
    with capsys.disabled():
        print(f"\nlanding JavaScript {total / 1024:.1f} KB gzip of {BUDGET_JS / 1024:.0f} KB: " + ", ".join(f"{Path(w).name} {n / 1024:.1f}" for w, n in rows))
    assert total <= BUDGET_JS, f"{total / 1024:.1f} KB"


def test_three_is_vendored_pinned_and_licensed():
    pin = json.loads((ROOT / "cover3d/package.json").read_text())
    assert pin["dependencies"]["three"] == "0.187.0" and pin["devDependencies"]["esbuild"] == "0.28.2"
    assert "MIT License" in (THREE / "LICENSE").read_text() and "three.js authors" in (THREE / "LICENSE").read_text()
    head = (THREE / "three.cover.min.js").read_text(encoding="utf-8")[:200]
    assert "@license" in head and "Three.js Authors" in head and "MIT" in head
    assert module_graph("/assets/js/cover/world.js") == ["/assets/js/cover/world.js", "/assets/vendor/three-0.187.0/three.cover.min.js"]   # no CDN, nothing else


def test_the_vendored_three_exports_everything_the_world_imports():
    world = WORLD.read_text(encoding="utf-8")
    wanted = set()
    for names in re.findall(r'import\{([^}]*)\}from"/assets/vendor/three-0\.187\.0/three\.cover\.min\.js"', world):
        wanted |= {n.strip().split(" as ")[0] for n in names.split(",") if n.strip()}
    exported = {n.strip().split(" as ")[-1] for n in re.findall(r"export\{([^}]*)\}\s*;?\s*$", (THREE / "three.cover.min.js").read_text(encoding="utf-8"))[0].split(",")}
    assert wanted and wanted <= exported, sorted(wanted - exported)


def test_the_world_shipped_is_built_from_the_sources_and_minified():
    src = hashlib.sha256()
    for f in sorted((ROOT / "cover3d/src").glob("*.js")):
        src.update((f.name + "\n" + f.read_text(encoding="utf-8").replace("\r\n", "\n")).encode())
    banner = WORLD.read_text(encoding="utf-8")[:300]
    assert f"src:{src.hexdigest()[:16]})" in banner, "cover3d/src changed since the last build: run `node cover3d/build.mjs`"
    assert "DEV" not in banner                                           # never the unminified debug build


def test_the_terrain_data_is_small_and_well_formed():
    sizes = {p.name: p.stat().st_size for p in (ROOT / "assets/cover").glob("tahoe-*.gz")}
    assert set(sizes) == {"tahoe-hi.bin.gz", "tahoe-lo.bin.gz", "tahoe-geo.json.gz"}
    assert sizes["tahoe-hi.bin.gz"] + sizes["tahoe-geo.json.gz"] <= 2 * 1024 * 1024        # a laptop's live world
    assert sizes["tahoe-lo.bin.gz"] + sizes["tahoe-geo.json.gz"] <= 600 * 1024            # a phone's
    for tier in ("hi", "lo"):
        raw = gzip.decompress((ROOT / f"assets/cover/tahoe-{tier}.bin.gz").read_bytes())
        assert raw[:4] == b"GAT1"
        n = int.from_bytes(raw[4:8], "little")
        head = json.loads(raw[8:8 + n])
        h, s = head["height"], head["sdf"]
        assert len(raw) == 8 + n + h["bytes"] + h["esc"] * 2 + s["bytes"] and h["bytes"] == h["w"] * h["h"] and s["bytes"] == s["w"] * s["h"]
    geo = json.loads(gzip.decompress((ROOT / "assets/cover/tahoe-geo.json.gz").read_bytes()))
    assert {"cabin", "emerald", "tahoeCity", "sand", "heavenly", "taylor"} <= set(geo["places"]) and len(geo["trails"]["fork"]) > 10
    assert "OpenStreetMap" in geo["credit"]
