# -*- coding: utf-8 -*-
"""Normalise the Padron Nacional de Sectores Estadisticos 2024 (MIDAGRI).

Each statistical sector is MIDAGRI's operational unit for agricultural
fieldwork: it already carries agricultural hectares and a centroid, which makes
it the natural atom for a territory / coverage map.
"""
import pandas as pd

SRC = "data/shp/Padron_Nacional_SE_2024_0403.xlsx"

df = pd.read_excel(SRC, sheet_name="Padron_Nacional_2024", header=2)
df.columns = ["n", "ubigeo", "dep", "prov", "dist", "cod_se", "n_se", "sector",
              "ha_se", "ha_agricola", "lat", "lon"]
df = df.dropna(subset=["ubigeo", "lat", "lon"])

df["ubigeo"] = df["ubigeo"].astype(str).str.zfill(6)
df["cod_se"] = df["cod_se"].astype(str).str.strip()
for c in ("dep", "prov", "dist", "sector"):
    df[c] = df[c].astype(str).str.strip().str.upper()
for c in ("ha_se", "ha_agricola", "lat", "lon"):
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["ha_agricola", "lat", "lon"])

# Sanity: Peru's mainland bounding box.
df = df[(df.lat.between(-18.5, 0.0)) & (df.lon.between(-81.5, -68.6))]
df["intensidad"] = (df["ha_agricola"] / df["ha_se"]).clip(0, 1)

keep = ["ubigeo", "dep", "prov", "dist", "cod_se", "sector", "ha_se",
        "ha_agricola", "intensidad", "lat", "lon"]
df[keep].to_csv("out/sectores_2024.csv", index=False, encoding="utf-8-sig")

print(f"sectores            : {len(df):,}")
print(f"distritos           : {df.ubigeo.nunique():,}")
print(f"ha agricolas totales: {df.ha_agricola.sum():,.0f}")
print()
dep = (df.groupby("dep")
       .agg(sectores=("cod_se", "count"), ha_agricola=("ha_agricola", "sum"),
            ha_media_sector=("ha_agricola", "mean"))
       .sort_values("ha_agricola", ascending=False))
print(dep.to_string(float_format=lambda v: f"{v:,.0f}"))
