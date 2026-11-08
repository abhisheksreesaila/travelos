"""F-206: the cover's budget and its build. The landing's JavaScript stays within 250 KB gzipped with three.js inside it, counting every script
on the page wherever it comes from; three.js is self-hosted, version-pinned and keeps its licence, and so does the code adapted from Meng To's
skills; the world shipped was built from the sources in cover3d/src, by the pinned tools only; every file the world fetches is addressed by its
content, so a new build never mixes with a cached old one; the terrain data stays small and bakes to the same bytes every time."""
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.cover_size import BUDGET_JS, measure, module_graph

ROOT = Path(__file__).resolve().parent.parent
THREE = ROOT / "assets/vendor/three-0.187.0"
WORLD = ROOT / "assets/js/cover/world.js"
NODE = shutil.which("node")
MIT = "Permission is hereby granted, free of charge"


def _h(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def test_the_landing_javascript_fits_in_250_kb_gzipped(client, capsys):
    rows, _ = measure(client.get("/").text)
    names = [w for w, _ in rows]
    assert "/assets/vendor/three-0.187.0/three.cover.min.js" in names and "/assets/js/cover/world.js" in names and "/assets/js/cover.js" in names
    total = sum(n for _, n in rows)
    with capsys.disabled():
        print(f"\nlanding JavaScript {total / 1024:.1f} KB gzip of {BUDGET_JS / 1024:.0f} KB: " + ", ".join(f"{Path(w).name} {n / 1024:.1f}" for w, n in rows))
    assert total <= BUDGET_JS, f"{total / 1024:.1f} KB"


def test_every_script_on_the_landing_counts_wherever_it_comes_from(client):
    """Every script on the page counts. Since F-207 the landing loads none from another site (FastHTML's jsDelivr scripts are off), and a script
    from another site that nobody has measured (scripts/cover_size.py EXTERNAL) fails the budget instead of slipping past it."""
    html = client.get("/").text
    rows, _ = measure(html)
    names = {w for w, _ in rows}
    srcs = re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    assert srcs and not any(s.startswith(("https:", "http:", "//")) for s in srcs), srcs
    for src in srcs:
        assert src.split("?")[0] in names, src
    with pytest.raises(ValueError, match="https://example.com/new.js"):
        measure(html.replace("</body>", '<script src="https://example.com/new.js"></script></body>'))


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
    for names in re.findall(r'import\{([^}]*)\}from"/assets/vendor/three-0\.187\.0/three\.cover\.min\.js(?:\?v=[0-9a-f]+)?"', world):
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


def test_every_file_the_world_fetches_is_addressed_by_its_content(client):
    """The service worker keeps /assets/ files with ?v= for good, so the world imports three.js and fetches the terrain by URLs that carry each file's
    own hash (written in by build.mjs), and the page preloads the very URL the world imports."""
    world = WORLD.read_text(encoding="utf-8")
    three = f"/assets/vendor/three-0.187.0/three.cover.min.js?v={_h(THREE / 'three.cover.min.js')}"
    assert set(re.findall(r'from"(/assets/vendor/[^"]+)"', world)) == {three}
    for name in ("tahoe-hi.bin.gz", "tahoe-lo.bin.gz", "tahoe-geo.json.gz"):
        assert f'"{name}":"{_h(ROOT / "assets/cover" / name)}"' in world, name
    main = re.search(r"<main\b[^>]*>", client.get("/").text).group(0)
    assert f'data-three="{three}"' in main


def test_the_code_adapted_from_meng_tos_skills_ships_with_its_mit_notice():
    notice = (ROOT / "cover3d/LICENSE-mengto").read_text(encoding="utf-8")
    assert "Copyright (c) 2026 Meng To" in notice and MIT in notice
    for shipped in (WORLD, ROOT / "assets/js/cover.js"):
        text = shipped.read_text(encoding="utf-8")
        assert "Copyright (c) 2026 Meng To" in text and MIT in text, shipped.name


def _fake_modules(mods, esbuild):
    (mods / "three").mkdir(parents=True)
    (mods / "three/package.json").write_text('{"version": "0.187.0"}')
    (mods / "esbuild").mkdir()
    (mods / "esbuild/package.json").write_text(json.dumps({"name": "esbuild", "version": esbuild, "main": "index.js"}))
    (mods / "esbuild/index.js").write_text(f"module.exports = {{ version: '{esbuild}', build() {{ throw new Error('built with a stand-in esbuild'); }} }};")


@pytest.mark.skipif(not NODE, reason="needs node")
def test_the_build_takes_only_its_own_pinned_tools(tmp_path):
    """build.mjs takes three and esbuild from cover3d/node_modules (or COVER3D_MODULES), never from another project's cache in the home folder, and
    refuses an esbuild other than the pinned one, before it writes anything. A copy runs from a scratch folder, so the repo is never touched."""
    work = tmp_path / "cover3d"
    work.mkdir()
    for f in ("build.mjs", "package.json"):
        shutil.copy(ROOT / "cover3d" / f, work)
    home = tmp_path / "home"
    _fake_modules(home / ".cache/story3d-build/node_modules", "0.28.2")
    env = {k: v for k, v in os.environ.items() if k != "COVER3D_MODULES"} | {"HOME": str(home)}
    r = subprocess.run([NODE, str(work / "build.mjs")], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "npm ci --ignore-scripts" in r.stderr, r.stderr[-400:]
    _fake_modules(tmp_path / "other/node_modules", "0.27.0")
    r = subprocess.run([NODE, str(work / "build.mjs")], env=env | {"COVER3D_MODULES": str(tmp_path / "other/node_modules")}, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "esbuild 0.27.0 found, 0.28.2 pinned" in r.stderr, r.stderr[-400:]
    assert not (tmp_path / "assets").exists()                                          # it stopped before writing anything


def test_installing_the_build_tools_runs_no_install_scripts():
    assert "ignore-scripts=true" in (ROOT / "cover3d/.npmrc").read_text(encoding="utf-8").split()
    assert "npm ci --ignore-scripts" in (ROOT / "cover3d/README.md").read_text(encoding="utf-8")


def test_the_terrain_bakes_to_the_same_bytes_every_time():
    """No timestamp in the gzip headers (the same data bakes to the same files), and no debug picture written from the bake."""
    for p in sorted((ROOT / "assets/cover").glob("tahoe-*.gz")):
        head = p.read_bytes()[:10]
        assert head[:3] == b"\x1f\x8b\x08" and head[4:8] == b"\0\0\0\0", p.name
    bake = (ROOT / "cover3d/tools/bake_tahoe.py").read_text(encoding="utf-8")
    assert ".save(" not in bake and "f206-tmp" not in bake and "mtime=0" in bake


def test_the_tools_use_playwrights_own_chromium():
    for tool in ("capture.py", "measure.py"):
        text = (ROOT / "cover3d/tools" / tool).read_text(encoding="utf-8")
        assert "chromium-1248" not in text and "ms-playwright" not in text, tool
