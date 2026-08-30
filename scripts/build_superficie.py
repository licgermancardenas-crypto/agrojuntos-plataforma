# -*- coding: utf-8 -*-
"""Normalise the MIDAGRI Mapa Nacional de Superficie Agricola tabular annex.

The source sheet `tabular_RM` carries one row per statistical sector plus
interleaved "Total <DISTRITO>" subtotal rows. We keep the sector rows and
rebuild the department/province/district aggregates ourselves so the numbers
are internally consistent.
"""
import pandas as pd

SRC = "data/midagri_superficie_agricola.xlsx"

raw = pd.read_excel(SRC, sheet_name="tabular_RM", header=1)
raw.columns = ["dep", "prov", "dist", "sector", "ha_agricola", "ha_territorial"]
raw = raw.dropna(subset=["ha_agricola"])

# forward-fill the sparse hierarchy, then drop the subtotal rows
for c in ("dep", "prov", "dist"):
    raw[c] = raw[c].ffill()
sectors = raw[raw["sector"].notna() & ~raw["dist"].astype(str).str.startswith("Total")].copy()
for c in ("dep", "prov", "dist", "sector"):
    sectors[c] = sectors[c].astype(str).str.strip().str.upper()
sectors["ha_agricola"] = pd.to_numeric(sectors["ha_agricola"], errors="coerce")
sectors["ha_territorial"] = pd.to_numeric(sectors["ha_territorial"], errors="coerce")
sectors = sectors.dropna(subset=["ha_agricola"])
sectors["intensidad_agricola"] = sectors["ha_agricola"] / sectors["ha_territorial"]

sectors.to_csv("out/superficie_sector.csv", index=False, encoding="utf-8-sig")

dist = (sectors.groupby(["dep", "prov", "dist"], as_index=False)
        .agg(ha_agricola=("ha_agricola", "sum"),
             ha_territorial=("ha_territorial", "sum"),
             n_sectores=("sector", "nunique")))
dist["intensidad_agricola"] = dist["ha_agricola"] / dist["ha_territorial"]
dist.to_csv("out/superficie_distrito.csv", index=False, encoding="utf-8-sig")

dep = (sectors.groupby("dep", as_index=False)
       .agg(ha_agricola=("ha_agricola", "sum"),
            ha_territorial=("ha_territorial", "sum"),
            n_sectores=("sector", "nunique"),
            n_distritos=("dist", "nunique"))
       .sort_values("ha_agricola", ascending=False))
dep["pct_nacional"] = 100 * dep["ha_agricola"] / dep["ha_agricola"].sum()
dep["pct_acum"] = dep["pct_nacional"].cumsum()
dep.to_csv("out/superficie_departamento.csv", index=False, encoding="utf-8-sig")

print(f"sectores={len(sectors)}  distritos={len(dist)}  deptos={len(dep)}")
print(f"TOTAL nacional = {sectors['ha_agricola'].sum():,.0f} ha agricolas\n")
print(dep.to_string(index=False,
      formatters={"ha_agricola": "{:,.0f}".format, "ha_territorial": "{:,.0f}".format,
                  "pct_nacional": "{:.1f}".format, "pct_acum": "{:.1f}".format}))
