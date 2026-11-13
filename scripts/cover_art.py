"""The cover's place art (F-227), ported from the approved F-221 drawings (docs/design/trip-matrix/art.js): one style, flat paper-cut layers, a
day palette for light mode and a night palette for dark mode.

    pixi run python scripts/cover_art.py            # write the sprite and the palettes
    pixi run python scripts/cover_art.py --check    # exit 1 when either is out of date (tests/test_cover.py runs this)

Runs art.js under node with a stand-in document, takes each place's drawing and writes:
  assets/cover/art.svg    one <symbol id="pa-<place>"> per place the cover shows. Every fill and stroke is a CSS custom property
                          (style="fill:var(--far)"), so one drawing serves day and night and every <use> of it (gitaway/pages/cover.py art()).
  assets/css/cover.css    the palettes, between /* art:begin */ and /* art:end */: a place's fourteen colours on .pa[data-art=...], light and dark,
                          and the weather (data-wx sun, cloud, snow) as the opacity of the clouds, the sun and the snow.
The art is still on the cover: the clouds, rain, turbines and fireworks of art.js do not move here (D-428). The sky is the .pa box's own
gradient, so the drawings carry no ids and any number of them can share a page.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs/design/trip-matrix/art.js"
SPRITE = ROOT / "assets/cover/art.svg"
CSS = ROOT / "assets/css/cover.css"
PLACES = ("san-diego", "los-angeles", "lake-tahoe", "new-york", "palm-springs")      # the places the cover draws (cover.py ART)
BEGIN, END = "/* art:begin (scripts/cover_art.py writes this block) */", "/* art:end */"

NODE = r"""
const fs = require('fs');
let css = '';
globalThis.window = globalThis;
globalThis.document = { createElement: () => ({}), head: { appendChild: (s) => { css = s.textContent; } } };
const src = fs.readFileSync(process.argv[1], 'utf8').replace(/\}\)\(\);\s*$/, 'globalThis.__PAL = PAL; globalThis.__VARS = VARS; })();');
eval(src);
const ids = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify({ svg: Object.fromEntries(ids.map((id) => [id, TMArt.svg(id)])), pal: __PAL, vars: __VARS }));
"""

# art.js's classes, as the custom property each one paints with (fills, then strokes: S() names a stroke "<class>s")
FILL = {"fa": "far", "mi": "mid", "ne": "near", "wa": "water", "gr": "ground", "g2": "ground2", "ln": "line", "ac": "acc", "lf": "leaf",
        "sn": "snow", "sn2": "snow", "fo": "foam"}
STROKE = {"fos": "foam", "lns": "line", "acs": "acc", "sns": "snow", "lfs": "leaf", "mis": "mid", "nes": "near", "was": "water"}
WEATHER = {
    "sn-disc": "fill:var(--sun);opacity:var(--pa-sun,1)",
    "wx-cl": "fill:var(--pa-cloud);opacity:var(--pa-cl,0)",
    "wx-cl2": "fill:var(--pa-cloud);opacity:var(--pa-cl2,0)",
    "wx-rn": "stroke:var(--water);stroke-width:2;stroke-linecap:round;fill:none;opacity:var(--pa-rn,0)",
    "wx-sn": "fill:var(--snow);opacity:var(--pa-sn,0)",
}


def _style(cls):
    if cls in WEATHER:
        return WEATHER[cls]
    if cls in STROKE:
        return f"stroke:var(--{STROKE[cls]})"
    return f"fill:var(--{FILL[cls]})"


def symbol(place, svg):
    """art.js's drawing of a place as a <symbol>: its sky rectangle and gradient dropped (the .pa box paints the sky), every class a style."""
    body = re.sub(r"^<svg[^>]*>|</svg>$", "", svg)
    body = re.sub(r"<defs>.*?</defs>", "", body)
    body = re.sub(r'<rect width="480" height="240" fill="url\(#pa\d+\)"/>', "", body)
    body = re.sub(r'<g class="(?:wx|fw)">', "<g>", body)
    body = re.sub(r'<g class="tb" style="[^"]*">', "<g>", body)                       # the turbines stand still
    body = re.sub(r'class="([\w-]+)"', lambda m: f'style="{_style(m.group(1))}"', body)
    assert "class=" not in body and "url(#" not in body, place
    return f'<symbol id="pa-{place}" viewBox="0 0 480 240">{body}</symbol>'


def palettes(pal, names):
    """The day and night colours of each place as custom properties, and the weather as opacities."""
    def block(sel, colours):
        return f"{sel} {{ " + "; ".join(f"--{n}: {c}" for n, c in zip(names, colours)) + "; }"
    day = [block(f'.pa[data-art="{p}"]', pal[p]["day"]) for p in PLACES]
    night = [block(f'.pa[data-art="{p}"]', pal[p]["night"]) for p in PLACES]
    weather = [
        ".pa { --pa-cloud: #FFFFFF; --pa-cl: .75; }",
        '.pa[data-wx="cloud"] { --pa-cl: .92; --pa-cl2: .92; --pa-sun: .45; }',
        '.pa[data-wx="snow"] { --pa-cloud: #E6ECF3; --pa-cl: .95; --pa-cl2: .95; --pa-sn: .95; --pa-sun: 0; }',
    ]
    dark = night + [".pa { --pa-cloud: #3A4660; }"]
    return "\n".join([BEGIN, *day, *weather,
                      ":root[data-mode=\"dark\"] {", *[f"  {r}" for r in dark], "}",
                      "@media (prefers-color-scheme: dark) { :root:not([data-mode=\"light\"]) {", *[f"  {r}" for r in dark], "} }",
                      END])


def build():
    out = subprocess.run(["node", "-e", NODE, str(SOURCE), json.dumps(PLACES)], capture_output=True, text=True, check=True, timeout=60)
    data = json.loads(out.stdout)
    sprite = ('<svg xmlns="http://www.w3.org/2000/svg" class="pa-sprite" aria-hidden="true" focusable="false">'
              + "".join(symbol(p, data["svg"][p]) for p in PLACES) + "</svg>\n")
    css = CSS.read_text(encoding="utf-8")
    start, end = css.index(BEGIN), css.index(END) + len(END)
    return sprite, css[:start] + palettes(data["pal"], data["vars"]) + css[end:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sprite, css = build()
    if a.check:
        stale = [p.name for p, text in ((SPRITE, sprite), (CSS, css)) if p.read_text(encoding="utf-8") != text]
        if stale:
            print("out of date: " + ", ".join(stale) + " (run pixi run python scripts/cover_art.py)")
            sys.exit(1)
        return
    SPRITE.write_text(sprite, encoding="utf-8")
    CSS.write_text(css, encoding="utf-8")
    print(f"{SPRITE.relative_to(ROOT)} {len(sprite) / 1024:.1f} KB, {len(PLACES)} places")


if __name__ == "__main__":
    main()
