# -*- coding: utf-8 -*-
"""Estimate cost-to-serve and export orientation for every statistical sector.

For a business that delivers on credit, distance is margin. Two sectors with
the same hectares are not the same customer if one sits forty minutes from
Trujillo and the other six hours up a valley.

Measured routing over the OSM graph is the right instrument and is being
harvested separately; it is slow. This builds the interim layer from geometry
we already hold, and is explicit about being a proxy:

  · geodesic distance from each sector to its provincial capital, and to the
    nearest commercial port
  · an effective road speed by natural region, because a kilometre on the
    coastal Panamericana and a kilometre in the sierra are not the same trip

Speeds are conservative averages for loaded delivery vehicles, and the detour
factor converts straight-line distance into road distance.
"""
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod
from shapely.geometry import Point

GEOD = Geod(ellps="WGS84")

# Effective km/h for a loaded vehicle, and how much longer the road is than
# the straight line. Both vary sharply with terrain in Peru.
VELOCIDAD = {"COSTA": 55.0, "SIERRA": 28.0, "SELVA ALTA": 32.0,
             "SELVA BAJA": 22.0}
RODEO = {"COSTA": 1.25, "SIERRA": 1.75, "SELVA ALTA": 1.60, "SELVA BAJA": 1.85}


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def dist_km(lon1, lat1, lon2, lat2):
    """Geodesic distance in km; scalars are broadcast against the array side."""
    a = np.asarray(lon1, float)
    lon2 = np.full_like(a, float(lon2)) if np.isscalar(lon2) else np.asarray(lon2, float)
    lat2 = np.full_like(a, float(lat2)) if np.isscalar(lat2) else np.asarray(lat2, float)
    _, _, d = GEOD.inv(a, np.asarray(lat1, float), lon2, lat2)
    return d / 1000.0


sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
sec["k"] = sec["dep"].map(key)
puertos = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")

# ---- provincial capitals: representative point of each province ----------
prov = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
prov["k"] = prov["FIRST_NOMB"].map(key)
prov["kp"] = prov["NOMBPROV"].map(slug)
pts = prov.geometry.representative_point()
prov["lon_cap"] = pts.x
prov["lat_cap"] = pts.y

sec["kp"] = sec["prov"].map(slug)
sec = sec.merge(prov[["k", "kp", "lon_cap", "lat_cap", "NOMBPROV"]],
                on=["k", "kp"], how="left")
sin_cap = sec["lon_cap"].isna().sum()

# Sectors whose province did not match fall back to their department's centroid
if sin_cap:
    dep_c = (prov.dissolve(by="k").geometry.representative_point()
             .to_frame("g"))
    dep_c["lon_d"] = dep_c["g"].x
    dep_c["lat_d"] = dep_c["g"].y
    sec = sec.merge(dep_c[["lon_d", "lat_d"]], left_on="k", right_index=True,
                    how="left")
    sec["lon_cap"] = sec["lon_cap"].fillna(sec["lon_d"])
    sec["lat_cap"] = sec["lat_cap"].fillna(sec["lat_d"])

# ---- distance to provincial capital --------------------------------------
sec["km_capital"] = dist_km(sec.lon, sec.lat, sec.lon_cap, sec.lat_cap)

# ---- distance to the nearest commercial port -----------------------------
mar = puertos[puertos.tipo == "maritimo"]
best_km = np.full(len(sec), np.inf)
best_name = np.array([""] * len(sec), dtype=object)
for _, p in puertos.iterrows():
    d = dist_km(sec.lon, sec.lat, p.lon, p.lat)
    mejor = d < best_km
    best_km = np.where(mejor, d, best_km)
    best_name = np.where(mejor, p.puerto, best_name)
sec["km_puerto"] = best_km
sec["puerto_cercano"] = best_name

# maritime-only, since river ports do not serve container agro-export
best_km_m = np.full(len(sec), np.inf)
best_name_m = np.array([""] * len(sec), dtype=object)
for _, p in mar.iterrows():
    d = dist_km(sec.lon, sec.lat, p.lon, p.lat)
    mejor = d < best_km_m
    best_km_m = np.where(mejor, d, best_km_m)
    best_name_m = np.where(mejor, p.puerto, best_name_m)
sec["km_puerto_maritimo"] = best_km_m
sec["puerto_maritimo"] = best_name_m

# ---- turn distance into time ---------------------------------------------
sec["vel"] = sec["region_nat"].map(VELOCIDAD).fillna(30.0)
sec["rodeo"] = sec["region_nat"].map(RODEO).fillna(1.7)
sec["km_via_capital"] = sec["km_capital"] * sec["rodeo"]
sec["horas_capital"] = sec["km_via_capital"] / sec["vel"]
sec["horas_puerto"] = sec["km_puerto_maritimo"] * sec["rodeo"] / sec["vel"]

# ---- cost to serve --------------------------------------------------------
# A delivery run is round trip; this is the vehicle cost of reaching the sector,
# before the value of the order itself.
COSTO_HORA = 18.0        # US$/h all-in for a loaded light truck with driver
sec["costo_viaje_usd"] = 2 * sec["horas_capital"] * COSTO_HORA
sec["costo_pct_venta"] = 100 * sec["costo_viaje_usd"] / (
    sec["s_sam_usd"] / sec["s_clientes_sam"].replace(0, np.nan)).replace(0, np.nan)

sec["accesible"] = pd.cut(
    sec["horas_capital"], [-0.01, 1, 2, 4, 8, 999],
    labels=["<1 h", "1-2 h", "2-4 h", "4-8 h", ">8 h"])

cols = ["cod_se", "dep", "prov", "dist", "sector", "region_nat", "lat", "lon",
        "ha_agricola", "s_ha_cosechada", "s_clientes_sam", "s_sam_usd",
        "km_capital", "km_via_capital", "horas_capital", "accesible",
        "km_puerto_maritimo", "puerto_maritimo", "horas_puerto",
        "costo_viaje_usd", "costo_pct_venta"]
sec[cols].to_csv("out/logistica_sector.csv", index=False, encoding="utf-8-sig")

# ---- department roll-up ---------------------------------------------------
def wavg(g, col):
    w = g["ha_agricola"]
    return np.average(g[col], weights=w) if w.sum() else np.nan


dep = (sec.groupby("dep")
       .apply(lambda g: pd.Series({
           "sectores": len(g),
           "horas_capital": wavg(g, "horas_capital"),
           "horas_puerto": wavg(g, "horas_puerto"),
           "km_puerto": wavg(g, "km_puerto_maritimo"),
           "pct_bajo_2h": 100 * (g.horas_capital <= 2).mean(),
           "pct_sobre_4h": 100 * (g.horas_capital > 4).mean(),
           "costo_viaje": wavg(g, "costo_viaje_usd"),
           "puerto": g["puerto_maritimo"].mode().iat[0],
           "sam": g["s_sam_usd"].sum(),
       }), include_groups=False)
       .reset_index()
       .sort_values("horas_capital"))
dep.to_csv("out/logistica_departamento.csv", index=False, encoding="utf-8-sig")

print(f"sectores procesados      : {len(sec):,}")
print(f"sin capital provincial   : {sin_cap}")
print(f"horas medias a capital   : {np.average(sec.horas_capital, weights=sec.ha_agricola):.2f} h")
print(f"horas medias a puerto    : {np.average(sec.horas_puerto, weights=sec.ha_agricola):.2f} h")
print()
print("--- ACCESIBILIDAD NACIONAL (ponderada por hectareas) ---")
acc = (sec.groupby("accesible", observed=True)
       .agg(sectores=("cod_se", "size"), ha=("ha_agricola", "sum"),
            sam=("s_sam_usd", "sum")))
acc["pct_sam"] = 100 * acc["sam"] / acc["sam"].sum()
for i, r in acc.iterrows():
    print(f"  {str(i):>6}  {int(r.sectores):5d} sectores  "
          f"{r.ha/1e3:8,.0f} mil ha  US$ {r.sam/1e6:6,.0f} MM  "
          f"{r.pct_sam:5.1f}% del SAM")
print()
print("--- POR REGION ---")
show = dep[["dep", "horas_capital", "pct_bajo_2h", "pct_sobre_4h",
            "horas_puerto", "puerto", "costo_viaje"]].copy()
show.columns = ["region", "h_capital", "%<2h", "%>4h", "h_puerto", "puerto",
                "US$_viaje"]
print(show.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
