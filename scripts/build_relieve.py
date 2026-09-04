# -*- coding: utf-8 -*-
"""Fetch terrain tiles and bake one hillshade raster per department.

Peru is the reason this layer exists. Half the report argues about the cost of
serving a region -- hours to the capital, sectors beyond four hours, the price
of a sales visit -- and on a flat plate those numbers are assertions. Against
shaded relief they are obvious: the coast is a ribbon of irrigated valleys, the
sierra is a wall, and the reader sees why one valley is worth a route and the
next is not.

Source is the public Terrarium tile set on AWS (elevation-tiles-prod), which
encodes height in the RGB channels of a PNG: h = R*256 + G + B/256 - 32768.
Tiles are cached on disk, so a rerun costs nothing.

Zoom 9 gives about 300 m per pixel at this latitude; on a plate 190 mm wide
covering some 300 km that is roughly 130 dpi of relief, which is soft enough to
sit under the data without competing with it and sharp enough to read a valley.
"""
import math
import os
import re
import time
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from PIL import Image

Z = 9
CACHE = "data/dem"
OUT = "out/relieve"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
UA = {"User-Agent": "AgroJuntos-atlas/1.0 (reporte de mercado)"}
MARGEN = 0.35          # degrees of context beyond the department bounds


# Same department key the rest of the pipeline uses; copied rather than
# imported because build_laminas_dep.py renders all 24 plates at import time.
FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima",
       "provconstdelcallao": "callao"}


def key(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    return FIX.get(s, s)


def xyz(lon, lat, z=Z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    la = math.radians(max(min(lat, 85.05), -85.05))
    y = int((1.0 - math.log(math.tan(la) + 1 / math.cos(la)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def tile_bounds(x, y, z=Z):
    n = 2 ** z
    lon1 = x / n * 360.0 - 180.0
    lon2 = (x + 1) / n * 360.0 - 180.0
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat2 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lon1, lat2, lon2, lat1


def bajar(x, y):
    p = os.path.join(CACHE, f"{Z}_{x}_{y}.png")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    for intento in range(4):
        try:
            r = requests.get(URL.format(z=Z, x=x, y=y), headers=UA, timeout=45)
            if r.status_code == 200:
                open(p, "wb").write(r.content)
                return p
            if r.status_code == 404:      # ocean tiles are simply absent
                open(p, "wb").write(b"")
                return p
        except requests.RequestException:
            pass
        time.sleep(1.5 * (intento + 1))
    return None


def elevacion(path):
    if not path or os.path.getsize(path) == 0:
        return None
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    return a[:, :, 0] * 256.0 + a[:, :, 1] + a[:, :, 2] / 256.0 - 32768.0


def hillshade(dem, res_m, az=315.0, alt=42.0, z_factor=1.4):
    """Standard Horn hillshade, 0-255.

    The vertical exaggeration is deliberate: at 300 m per pixel the Andes are
    steep enough to clip to black, so the shade is computed on a mild z factor
    and then flattened again when the plate draws it at low opacity.
    """
    dy, dx = np.gradient(dem.astype(np.float32), res_m)
    slope = np.arctan(z_factor * np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az_r, alt_r = math.radians(360.0 - az + 90.0), math.radians(alt)
    sh = (np.sin(alt_r) * np.cos(slope) +
          np.cos(alt_r) * np.sin(slope) * np.cos(az_r - aspect))
    return np.clip(sh, 0, 1) * 255.0


def mosaico(lon0, lat0, lon1, lat1):
    x0, y0 = xyz(lon0, lat1)
    x1, y1 = xyz(lon1, lat0)
    xs, ys = range(x0, x1 + 1), range(y0, y1 + 1)
    alto, ancho = len(list(ys)) * 256, len(list(xs)) * 256
    m = np.full((alto, ancho), np.nan, dtype=np.float32)
    faltan = 0
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            e = elevacion(bajar(x, y))
            if e is None:
                faltan += 1
                continue
            m[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = e
    b0 = tile_bounds(x0, y0)
    b1 = tile_bounds(x1, y1)
    extent = (b0[0], b1[2], b1[1], b0[3])       # lon_min, lon_max, lat_min, lat_max
    return m, extent, faltan


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    dep = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
    perfil = pd.read_pickle("out/perfil_dep.pkl")

    dep["k"] = dep["NOMBDEP"].map(key)

    for _, r in perfil.iterrows():
        k = r["k"]
        dst = os.path.join(OUT, f"{k}.npz")
        if os.path.exists(dst):
            print(f"  {k:<14} ya estaba")
            continue
        g = dep[dep.k == k]
        if not len(g):
            print(f"  {k:<14} sin geometria")
            continue
        lon0, lat0, lon1, lat1 = g.total_bounds
        dem, extent, faltan = mosaico(lon0 - MARGEN, lat0 - MARGEN,
                                      lon1 + MARGEN, lat1 + MARGEN)
        lat_med = (extent[2] + extent[3]) / 2
        res_m = 156543.03392 * math.cos(math.radians(lat_med)) / (2 ** Z)
        dem = np.where(np.isnan(dem), 0.0, dem)
        hs = hillshade(dem, res_m).astype(np.uint8)
        np.savez_compressed(dst, hs=hs, extent=np.array(extent),
                            dem_max=np.float32(dem.max()))
        print(f"  {k:<14} {hs.shape[1]}x{hs.shape[0]} px  "
              f"{res_m:.0f} m/px  {faltan} teselas sin dato  "
              f"{os.path.getsize(dst)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
