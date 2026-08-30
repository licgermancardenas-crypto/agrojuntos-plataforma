# -*- coding: utf-8 -*-
"""Turn the MIDAGRI statistical-sector shapefile into a web-sized GeoJSON.

Artifacts cannot load external map tiles, so the map draws Peru from embedded
geometry. That makes payload size the binding constraint: geometry is
simplified and coordinates are rounded to ~11 m precision (4 decimals).
"""
import json
import geopandas as gpd
import pandas as pd

SHP = "data/shp/SectoresEstadisticos_2024_04/SectoresEstadisticos_2024_04_04.shp"
TOL = 0.004          # degrees (~440 m) — sectors average several thousand ha
DECIMALS = 4

g = gpd.read_file(SHP)
g = g.to_crs(4326)

cols = {
    "ID_SE": "cod_se", "NOMBDEP": "dep", "NOMBPROV": "prov", "NOMBDIST": "dist",
    "IDDIST": "ubigeo", "NOM_SE": "sector", "AREA_SE": "ha_se",
    "SAN_2018": "ha_agricola", "REG_NAT_LA": "region_nat",
    "REGION_AGR": "region_agraria", "AGENCIA_AG": "agencia_agraria",
    "LATITUD": "lat", "LONGITUD": "lon",
}
g = g[list(cols) + ["geometry"]].rename(columns=cols)

for c in ("dep", "prov", "dist", "sector", "region_nat", "region_agraria",
          "agencia_agraria"):
    g[c] = g[c].astype(str).str.strip().str.upper().replace({"NAN": ""})
for c in ("ha_se", "ha_agricola", "lat", "lon"):
    g[c] = pd.to_numeric(g[c], errors="coerce")
g["ha_agricola"] = g["ha_agricola"].fillna(0)
g["intensidad"] = (g["ha_agricola"] / g["ha_se"]).clip(0, 1).fillna(0)

g["geometry"] = (g.geometry.buffer(0)
                 .simplify(TOL, preserve_topology=True)
                 .set_precision(10 ** -DECIMALS))
g = g[~g.geometry.is_empty & g.geometry.notna()]

g.to_file("out/sectores.gpkg", layer="sectores", driver="GPKG")

gj = json.loads(g.to_json(drop_id=True))
for f in gj["features"]:
    p = f["properties"]
    for k in ("ha_se", "ha_agricola", "lat", "lon"):
        if p.get(k) is not None:
            p[k] = round(p[k], 4)
    p["intensidad"] = round(p["intensidad"], 3)
with open("out/sectores.geojson", "w", encoding="utf-8") as fh:
    json.dump(gj, fh, separators=(",", ":"), ensure_ascii=False)

import os
print(f"sectores      : {len(g):,}")
print(f"geojson       : {os.path.getsize('out/sectores.geojson')/1e6:.1f} MB")
print(f"ha agricolas  : {g.ha_agricola.sum():,.0f}")
print(f"regiones agr. : {g.region_agraria.nunique()}")
print(f"agencias agr. : {g.agencia_agraria.nunique()}")
print()
print(g.groupby("region_nat")
      .agg(sectores=("cod_se", "count"), ha_agricola=("ha_agricola", "sum"))
      .to_string(float_format=lambda v: f"{v:,.0f}"))
