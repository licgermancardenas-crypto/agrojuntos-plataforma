# -*- coding: utf-8 -*-
"""Pack the v2 territory model into one compact JSON for the map artifact.

Published artifacts cannot fetch external map tiles, so Peru is drawn from
embedded geometry. Everything is sized for that: department outlines are
simplified and each sector ships as a fixed-length tuple, not an object.

Department-level figures (harvested area, spend per hectare, buying customers)
are pushed down to sectors in proportion to agricultural hectares. That is an
allocation, not a measurement, and the page says so.
"""
import json
import os
import re
import unicodedata

import geopandas as gpd
import pandas as pd

DEC = 3          # ~110 m, plenty for a national overview


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
sec = pd.read_csv("out/sectores_2024.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
geo = gpd.read_file("out/sectores.gpkg", layer="sectores")

mod["k"] = mod["dep"].map(key)
cen["k"] = cen["dep"].map(key)
sec["k"] = sec["dep"].map(key)
for d in (sec, geo):
    d["cod_se"] = d["cod_se"].astype(str).str.strip().str.zfill(8)
sec = sec.merge(geo[["cod_se", "region_nat", "agencia_agraria"]], on="cod_se",
                how="left")

# Callao has 71 ha and no commercial agriculture; the yearbook omits it.
sec = sec[sec["k"].isin(set(mod["k"]))]

# --- push department totals down to sectors -------------------------------
sec["share"] = sec["ha_agricola"] / sec.groupby("k")["ha_agricola"].transform("sum")
cols = ["k", "ha_cosechada", "gasto_ha", "sam_usd", "clientes_sam",
        "tam_usd", "share_comercial", "tasa_compra"]
sec = sec.merge(mod[cols], on="k", how="left")
for c in ("ha_cosechada", "sam_usd", "clientes_sam", "tam_usd"):
    sec[f"s_{c}"] = sec["share"] * sec[c]

sec.to_csv("out/modelo_v2_sector.csv", index=False, encoding="utf-8-sig")

# --- department attributes -------------------------------------------------
mod = mod.sort_values("rank").reset_index(drop=True)
dep_idx = {k: i for i, k in enumerate(mod["k"])}
cenm = cen.set_index("k")

deps = []
for _, r in mod.iterrows():
    c = cenm.loc[r["k"]]
    deps.append({
        "n": r["dep"], "rank": int(r["rank"]), "score": round(r["score"], 1),
        "haCos": int(r["ha_cosechada"]), "gastoHa": int(round(r["gasto_ha"])),
        "tam": int(r["tam_usd"]), "sam": int(r["sam_usd"]),
        "cli": int(r["clientes_sam"]), "ticket": int(round(r["ticket_anual"])),
        "prod": int(c["productores"]), "obj": int(c["ua_objetivo_5_mas"]),
        "micro": int(c["ua_micro_0_5"]), "peq": int(c["ua_pequeno_5_20"]),
        "med": int(c["ua_mediano_20_100"]), "gra": int(c["ua_grande_100_mas"]),
        "tasaCompra": round(100 * r["tasa_compra"], 1),
        "tasaCred": round(100 * r["tasa_credito"], 1),
        "cultivos": int(r["n_cultivos"]), "pctAcum": round(r["pct_acum"], 1),
        "sect": int((sec["k"] == r["k"]).sum()),
    })

# --- department outlines ---------------------------------------------------
g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
g["k"] = g["NOMBDEP"].map(key)
g["geometry"] = g.geometry.buffer(0).simplify(0.012, preserve_topology=True)
g = g[g["k"].isin(dep_idx)]


def rings(geom):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    out = []
    for p in polys:
        ring = [[round(x, DEC), round(y, DEC)] for x, y in p.exterior.coords]
        if len(ring) > 3:
            out.append(ring)
    return out


shapes = [{"d": dep_idx[r["k"]], "r": rings(r.geometry)} for _, r in g.iterrows()]

# --- sectors ---------------------------------------------------------------
REG = ["COSTA", "SIERRA", "SELVA ALTA", "SELVA BAJA"]
reg_idx = {r: i for i, r in enumerate(REG)}

sec = sec.sort_values("ha_agricola", ascending=False)
pts = []
for _, r in sec.iterrows():
    pts.append([
        round(float(r["lon"]), DEC), round(float(r["lat"]), DEC),
        int(round(r["ha_agricola"])),
        dep_idx[r["k"]],
        reg_idx.get(r["region_nat"], 1),
        int(round(r["s_clientes_sam"])),
        int(round(r["s_sam_usd"] / 1000)),          # US$ thousands
        int(round(r["s_ha_cosechada"])),
        str(r["prov"]), str(r["sector"]),
    ])

payload = {
    "meta": {
        "sectores": len(pts),
        "haAgricola": int(sec["ha_agricola"].sum()),
        "haCosechada": int(mod["ha_cosechada"].sum()),
        "gastoHa": int(round(mod["tam_usd"].sum() / mod["ha_cosechada"].sum())),
        "tam": int(mod["tam_usd"].sum()),
        "sam": int(mod["sam_usd"].sum()),
        "cli": int(mod["clientes_sam"].sum()),
        "prod": int(cen["productores"].sum()),
        "obj": int(cen["ua_objetivo_5_mas"].sum()),
    },
    "regiones": REG,
    "deps": deps,
    "shapes": shapes,
    "pts": pts,
}

with open("out/mapdata.json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)

print(f"mapdata.json : {os.path.getsize('out/mapdata.json')/1e6:.2f} MB")
print(f"sectores     : {len(pts):,}   departamentos: {len(deps)}")
print(f"TAM {payload['meta']['tam']/1e6:,.0f} MM   SAM {payload['meta']['sam']/1e6:,.0f} MM"
      f"   clientes {payload['meta']['cli']:,}")
