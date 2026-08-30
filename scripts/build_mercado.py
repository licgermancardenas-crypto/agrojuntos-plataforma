# -*- coding: utf-8 -*-
"""Build the AgroJuntos territory model: TAM / SAM / SOM and a priority score.

Layers combined
---------------
1. MIDAGRI Padron de Sectores Estadisticos 2024 (7,043 sectors, georeferenced)
   -> where the hectares actually are, at sector resolution.
2. INEI IV CENAGRO 2012, departmental annexes
   -> how many producers, and how they split by farm size.

The two do not share a common key below department level, so producers are
allocated down to sector proportionally to agricultural hectares within their
department. This is an estimate and is labelled as such everywhere it surfaces.

Segment logic: AgroJuntos sells crop inputs with delivery and credit. A 2 ha
subsistence plot is not an addressable buyer; the commercial segment starts
around 5 ha. So SAM is built on producers holding >5 ha.
"""
import pandas as pd

# Average annual input spend per hectare, in USD. Ranges reflect what
# agro-input distributors quote for Peru; the mid value is what we model.
GASTO_HA = {"COSTA": 1400, "SELVA ALTA": 520, "SELVA BAJA": 380, "SIERRA": 450}
GASTO_HA_DEFAULT = 600

sec = pd.read_csv("out/sectores_2024.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")

# region natural per sector comes from the shapefile build
import geopandas as gpd
geo = gpd.read_file("out/sectores.gpkg", layer="sectores")
# cod_se is a zero-padded code; pandas may read it as int from CSV.
for df in (sec, geo):
    df["cod_se"] = df["cod_se"].astype(str).str.strip().str.zfill(8)
sec = sec.merge(
    geo[["cod_se", "region_nat", "region_agraria", "agencia_agraria"]],
    on="cod_se", how="left")

# --- align department spellings between INEI (accented) and MIDAGRI (upper) ---
def key(s):
    return (str(s).upper().strip()
            .replace("Á", "A").replace("É", "E").replace("Í", "I")
            .replace("Ó", "O").replace("Ú", "U").replace("Ñ", "N")
            .replace("�", ""))

cen["k"] = cen["dep"].map(key)
sec["k"] = sec["dep"].map(key)
# INEI text came out of a PDF with a broken encoding for accents: repair by
# matching on the un-accented skeleton.
fix = {"NCASH": "ANCASH", "APURMAC": "APURIMAC", "HUNUCO": "HUANUCO",
       "JUNN": "JUNIN", "SAN MARTN": "SAN MARTIN"}
cen["k"] = cen["k"].replace(fix)

missing = set(sec.k) - set(cen.k)
assert not missing, f"departamentos sin CENAGRO: {missing}"

# --- allocate producers to sectors, proportional to agricultural hectares ---
dep_ha = sec.groupby("k")["ha_agricola"].sum().rename("ha_dep")
sec = sec.join(dep_ha, on="k")
sec["share"] = sec["ha_agricola"] / sec["ha_dep"]

cen_small = cen[["k", "productores", "ua_total", "ua_micro_0_5",
                 "ua_pequeno_5_20", "ua_mediano_20_100", "ua_grande_100_mas",
                 "ua_objetivo_5_mas"]]
sec = sec.merge(cen_small, on="k", how="left")

for c in ["productores", "ua_micro_0_5", "ua_pequeno_5_20",
          "ua_mediano_20_100", "ua_grande_100_mas", "ua_objetivo_5_mas"]:
    sec[f"est_{c}"] = sec["share"] * sec[c]

# --- market value ---
sec["gasto_ha"] = sec["region_nat"].map(GASTO_HA).fillna(GASTO_HA_DEFAULT)
sec["tam_usd"] = sec["ha_agricola"] * sec["gasto_ha"]

# SAM: the share of hectares held by commercial producers (>5 ha).
sec["ha_comercial"] = sec["ha_agricola"] * (
    sec["ua_objetivo_5_mas"] / sec["ua_total"]).clip(0, 1)
# Commercial farms are larger than average, so hectares concentrate more than
# headcount does. Applied as an explicit, single uplift factor.
CONCENTRACION = 2.2
sec["ha_comercial"] = (sec["ha_comercial"] * CONCENTRACION).clip(
    upper=sec["ha_agricola"])
sec["sam_usd"] = sec["ha_comercial"] * sec["gasto_ha"]

sec.to_csv("out/mercado_sector.csv", index=False, encoding="utf-8-sig")

# --- department roll-up ---
dep = (sec.groupby("dep")
       .agg(sectores=("cod_se", "count"),
            distritos=("ubigeo", "nunique"),
            ha_agricola=("ha_agricola", "sum"),
            ha_comercial=("ha_comercial", "sum"),
            tam_usd=("tam_usd", "sum"),
            sam_usd=("sam_usd", "sum"),
            agencias=("agencia_agraria", "nunique"))
       .reset_index())
dep["k"] = dep["dep"].map(key)
dep = dep.merge(cen_small, on="k", how="left")
dep["ha_prom_ua"] = dep["ha_agricola"] / dep["ua_total"]
dep["densidad_ha_sector"] = dep["ha_agricola"] / dep["sectores"]

# --- priority score: size x concentration x commercial mix ---
def z01(s):
    return (s - s.min()) / (s.max() - s.min())

dep["score"] = (0.45 * z01(dep["sam_usd"])
                + 0.25 * z01(dep["densidad_ha_sector"])
                + 0.20 * z01(dep["ua_objetivo_5_mas"])
                + 0.10 * z01(dep["ha_prom_ua"])) * 100
dep = dep.sort_values("score", ascending=False).reset_index(drop=True)
dep["rank"] = dep.index + 1
dep.to_csv("out/mercado_departamento.csv", index=False, encoding="utf-8-sig")

tam, sam = dep.tam_usd.sum(), dep.sam_usd.sum()
print(f"TAM Peru insumos agricolas : US$ {tam/1e6:>10,.0f} MM")
print(f"SAM (productores >5 ha)    : US$ {sam/1e6:>10,.0f} MM   ({100*sam/tam:.0f}% del TAM)")
print(f"Productores totales        : {dep.productores.sum():>12,.0f}")
print(f"Productores objetivo >5 ha : {dep.ua_objetivo_5_mas.sum():>12,.0f}")
print(f"Hectareas agricolas        : {dep.ha_agricola.sum():>12,.0f}")
print()
cols = ["rank", "dep", "ha_agricola", "ua_objetivo_5_mas", "sam_usd",
        "ha_prom_ua", "agencias", "score"]
show = dep[cols].copy()
show["sam_usd"] = (show["sam_usd"] / 1e6).round(0)
show = show.rename(columns={"sam_usd": "sam_MMusd"})
print(show.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
