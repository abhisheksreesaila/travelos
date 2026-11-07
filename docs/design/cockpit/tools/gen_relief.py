"""Draws the relief under Direction 3's paper map from the elevation grid that fetch_geo.py cached:
a soft hillshade with snow above the snow line, in a light and a dark palette. Lakes are left out (the SVG draws them).

    pixi run python -I docs/design/cockpit/tools/gen_relief.py
"""
from pathlib import Path

import math

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
RAW = Path.home() / ".cache" / "cockpit-geo-raw"
OUT_W = 1344  # the relief is drawn from the raw z11 tiles at 1344 px across the 50 km box (about 37 m a pixel)
BBOX = (-120.20, 38.84, -119.62, 39.54)

PALETTES = {
    # low valley, forest band, snow, shade colour, light colour
    "light": {"low": (226, 224, 218), "mid": (196, 205, 196), "snow": (250, 251, 253), "shade": (92, 96, 112), "lift": (255, 255, 255)},
    "dark": {"low": (34, 34, 38), "mid": (30, 38, 34), "snow": (74, 78, 88), "shade": (0, 0, 0), "lift": (120, 126, 140)},
}


def main():
    w0, s0, e0, n0 = BBOX
    Z = 11
    def txy(lon, lat):
        return ((lon + 180) / 360 * 2 ** Z, (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** Z)
    x0, y0 = txy(w0, n0); x1, y1 = txy(e0, s0)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            a = np.asarray(Image.open(RAW / f"dem-{Z}-{tx}-{ty}.png").convert("RGB"), dtype=np.float32)
            mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    km_w = (e0 - w0) * 111.32 * math.cos(math.radians((s0 + n0) / 2)); km_h = (n0 - s0) * 110.57
    OUT_H = round(OUT_W * km_h / km_w)
    # sample the mosaic on an even lon/lat grid (bilinear), so the relief lines up with the SVG's projection
    lons = w0 + (np.arange(OUT_W) + .5) / OUT_W * (e0 - w0)
    lats = n0 - (np.arange(OUT_H) + .5) / OUT_H * (n0 - s0)
    px = ((lons + 180) / 360 * 2 ** Z - tx0) * 256
    py = ((1 - np.log(np.tan(np.radians(lats)) + 1 / np.cos(np.radians(lats))) / np.pi) / 2 * 2 ** Z - ty0) * 256
    PX, PY = np.meshgrid(px, py)
    ix, iy = np.clip(PX.astype(int), 0, mos.shape[1] - 2), np.clip(PY.astype(int), 0, mos.shape[0] - 2)
    fx, fy = PX - ix, PY - iy
    z = (mos[iy, ix] * (1 - fx) * (1 - fy) + mos[iy, ix + 1] * fx * (1 - fy) + mos[iy + 1, ix] * (1 - fx) * fy + mos[iy + 1, ix + 1] * fx * fy)
    for _ in range(2):  # a light 3x3 smoothing, twice: softer, toy-like relief
        zp = np.pad(z, 1, mode="edge")
        z = sum(zp[1 + dy:zp.shape[0] - 1 + dy, 1 + dx:zp.shape[1] - 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
    cell = km_w / OUT_W * 1000  # metres per pixel
    dzdx = np.gradient(z, axis=1) / cell
    dzdy = np.gradient(z, axis=0) / cell
    # light from the north-west, 40 degrees up
    az, alt = np.radians(315), np.radians(40)
    slope = np.arctan(np.hypot(dzdx, dzdy) * 1.25)
    aspect = np.arctan2(-dzdx, dzdy)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)
    for name, p in PALETTES.items():
        t_snow = np.clip((z - 2050) / 450, 0, 1)[..., None]
        t_mid = np.clip((z - 1600) / 300, 0, 1)[..., None]
        base = np.array(p["low"]) * (1 - t_mid) + np.array(p["mid"]) * t_mid
        base = base * (1 - t_snow) + np.array(p["snow"]) * t_snow
        s = shade[..., None]
        k = (s - 0.62)  # flat ground is ~0.64: leave it, darken the shaded side, lift the sunny side a little
        dark = np.clip(-k * 1.25, 0, 0.55)
        lift = np.clip(k * 0.9, 0, 0.25)
        rgb = base * (1 - dark) + np.array(p["shade"]) * dark
        rgb = rgb * (1 - lift) + np.array(p["lift"]) * lift
        out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
        f = HERE / "img" / f"relief-{name}.webp"
        out.save(f, "WEBP", quality=80, method=6)
        print(f.name, f.stat().st_size, "bytes", out.size)


if __name__ == "__main__":
    main()
