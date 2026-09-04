# -*- coding: utf-8 -*-
"""Turn the OSM landuse harvest into a cultivated-footprint layer.

The plates dimensioned every statistical sector with a proportional circle. On
a region with 364 sectors those circles fuse into one blob: the symbol stops
carrying size and starts reading as density. The polygons harvested from
OpenStreetMap are the alternative -- the actual shape of the farmland, the
orchard, the vineyard -- so the map shows where the crop is instead of where
the centroid of an administrative unit falls.

Coverage is uneven: OSM is volunteer-mapped, dense on the coast and thin in the
sierra. This layer is therefore drawn as context under the modelled market, and
the plate says so in its source line. It never replaces the MIDAGRI surface.

Output is one GeoPackage per department, simplified to a tolerance no printer
can resolve, so the plate builder opens only the region it is drawing.
"""
import glob
import json
import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

# Copied rather than imported: build_osm.py runs its consolidation at module
# level, so importing it would rebuild the prospect tables as a side effect.
ISO2DEP = {
    "PE-AMA": "AMAZONAS", "PE-ANC": "ANCASH", "PE-APU": "APURIMAC",
    "PE-ARE": "AREQUIPA", "PE-AYA": "AYACUCHO", "PE-CAJ": "CAJAMARCA",
    "PE-CAL": "CALLAO", "PE-CUS": "CUSCO", "PE-HUV": "HUANCAVELICA",
    "PE-HUC": "HUANUCO", "PE-ICA": "ICA", "PE-JUN": "JUNIN",
    "PE-LAL": "LA LIBERTAD", "PE-LAM": "LAMBAYEQUE", "PE-LIM": "LIMA",
    "PE-LOR": "LORETO", "PE-MDD": "MADRE DE DIOS", "PE-MOQ": "MOQUEGUA",
    "PE-PAS": "PASCO", "PE-PIU": "PIURA", "PE-PUN": "PUNO",
    "PE-SAM": "SAN MARTIN", "PE-TAC": "TACNA", "PE-TUM": "TUMBES",
    "PE-UCA": "UCAYALI",
}

# Which landuse values are a crop and how the plate should colour them. Anything
# else in the harvest (residential, quarry, forest) is dropped here.
CLASES = {
    "farmland": "cultivo",
    "orchard": "frutal",
    "vineyard": "frutal",
    "greenhouse_horticulture": "intensivo",
    "plant_nursery": "intensivo",
    "aquaculture": "acuicola",
}

# A tenth of a millimetre on a plate that spans some 300 km is about 30 m; at
# 1e-4 degrees (~11 m) the outline is still finer than the press can print.
TOL = 1e-4
MIN_HA = 0.5

# South America Albers: hectares stay honest from Tumbes to Tacna.
AEA = ("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +x_0=0 +y_0=0 "
       "+ellps=aust_SA +units=m +no_defs")


def anillo(el):
    g = el.get("geometry") or []
    if len(g) < 4:
        return None
    p = Polygon([(c["lon"], c["lat"]) for c in g])
    return p if p.is_valid and not p.is_empty else p.buffer(0) or None


def leer(path):
    els = json.load(open(path, encoding="utf-8")).get("elements", [])
    filas = []
    for el in els:
        tags = el.get("tags") or {}
        val = tags.get("landuse") or tags.get("crop") or ""
        clase = CLASES.get(val)
        if clase is None:
            continue
        poly = anillo(el)
        if poly is None or poly.is_empty:
            continue
        filas.append({"clase": clase, "uso": val, "geometry": poly})
    return filas


def main():
    os.makedirs("out/cultivo", exist_ok=True)
    resumen = []
    for path in sorted(glob.glob("data/osm/PE-*_landuse.json")):
        iso = os.path.basename(path).split("_")[0]
        dep = ISO2DEP.get(iso)
        if dep is None:
            continue
        filas = leer(path)
        if not filas:
            print(f"  {iso}  sin poligonos de cultivo")
            continue
        g = gpd.GeoDataFrame(filas, crs=4326)
        # Area needs an equal-area projection; South America Albers keeps the
        # hectare honest across the whole country.
        g["ha"] = g.to_crs(AEA).area / 1e4
        g = g[g.ha >= MIN_HA].copy()
        g["geometry"] = g.geometry.simplify(TOL, preserve_topology=True)
        g = g[~g.geometry.is_empty & g.geometry.notna()]
        dst = f"out/cultivo/{iso}.gpkg"
        g.to_file(dst, driver="GPKG", layer="cultivo")
        resumen.append({"iso": iso, "dep": dep, "poligonos": len(g),
                        "ha": round(g.ha.sum()),
                        "mb": round(os.path.getsize(dst) / 1e6, 2)})
        print(f"  {iso}  {len(g):>6,} poligonos  {g.ha.sum():>10,.0f} ha")

    r = pd.DataFrame(resumen)
    r.to_csv("out/cultivo_resumen.csv", index=False, encoding="utf-8-sig")
    print(f"\n{r.poligonos.sum():,} poligonos  {r.ha.sum():,.0f} ha  "
          f"{r.mb.sum():.1f} MB en out/cultivo/")


if __name__ == "__main__":
    main()
