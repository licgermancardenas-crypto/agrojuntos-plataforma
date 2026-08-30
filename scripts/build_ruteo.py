# -*- coding: utf-8 -*-
"""Measure real road travel times over the OpenStreetMap network.

This replaces the geodesic proxy with routing on the actual road graph: 88,962
ways across the 25 departments, each edge weighted by the time a loaded
delivery vehicle would take on it.

Speed model. Peru's road reality is not captured by road class alone — a
"secondary" road can be asphalt on the coast and a rutted track in the sierra —
so the speed of every segment is the road class adjusted by its surface, and
capped by the posted limit where OSM records one. Two thirds of the network
carries a surface tag and a third a maxspeed tag.

Algorithm. The question "how far is each sector from a hub" is answered for the
whole country in one pass: a virtual source is joined to every hub at zero cost
and a single Dijkstra then labels every node in the graph with the time to its
nearest hub. Two passes — provincial capitals, and maritime ports — instead of
seven thousand separate routings.
"""
import glob
import json
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

GEOD = Geod(ellps="WGS84")

# Free-flow km/h for a loaded light truck, before surface and terrain.
VEL_CLASE = {
    "motorway": 90, "motorway_link": 60, "trunk": 75, "trunk_link": 50,
    "primary": 60, "primary_link": 40, "secondary": 50, "secondary_link": 35,
    "tertiary": 40, "tertiary_link": 30,
}
# Multiplier by surface. Unpaved roads in the Andes are the binding constraint
# on rural delivery far more than road classification is.
FACTOR_SUP = {
    "asphalt": 1.00, "paved": 1.00, "concrete": 0.95, "paving_stones": 0.85,
    "compacted": 0.70, "gravel": 0.60, "fine_gravel": 0.65, "unpaved": 0.55,
    "ground": 0.45, "dirt": 0.45, "earth": 0.45, "sand": 0.35, "mud": 0.30,
}
FACTOR_SUP_DEF = 0.80          # untagged: most are partly improved
DEC = 6                        # coordinate rounding for node identity


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def parse_maxspeed(v):
    m = re.match(r"(\d+)", str(v))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- graph ----
print("leyendo red vial...", flush=True)
nodos = {}          # (lon, lat) -> index
orig, dest, peso = [], [], []
n_vias = 0

for f in sorted(glob.glob("data/vial/PE-*.json")):
    for e in json.load(open(f, encoding="utf-8"))["elements"]:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        clase = t.get("highway", "tertiary")
        v = VEL_CLASE.get(clase, 35)
        v *= FACTOR_SUP.get(t.get("surface", ""), FACTOR_SUP_DEF)
        ms = parse_maxspeed(t.get("maxspeed", ""))
        if ms:
            v = min(v, ms)
        v = max(v, 8.0)                      # nothing crawls below this
        n_vias += 1

        pts = [(round(p["lon"], DEC), round(p["lat"], DEC)) for p in g]
        idx = []
        for p in pts:
            i = nodos.get(p)
            if i is None:
                i = len(nodos)
                nodos[p] = i
            idx.append(i)
        lons = np.array([p[0] for p in pts])
        lats = np.array([p[1] for p in pts])
        _, _, d = GEOD.inv(lons[:-1], lats[:-1], lons[1:], lats[1:])
        horas = (d / 1000.0) / v
        for a, b, h in zip(idx[:-1], idx[1:], horas):
            if a == b:
                continue
            orig.append(a); dest.append(b); peso.append(h)
            orig.append(b); dest.append(a); peso.append(h)

N = len(nodos)
print(f"  vias {n_vias:,} | nodos {N:,} | aristas {len(orig)//2:,}", flush=True)

coords = np.zeros((N, 2))
for (lon, lat), i in nodos.items():
    coords[i] = (lon, lat)
arbol = cKDTree(coords)


def construir(fuentes_idx):
    """Graph plus a virtual source joined to every hub at zero cost."""
    o = np.array(orig + [N] * len(fuentes_idx), dtype=np.int32)
    d = np.array(dest + list(fuentes_idx), dtype=np.int32)
    w = np.array(peso + [0.0] * len(fuentes_idx), dtype=np.float64)
    return csr_matrix((w, (o, d)), shape=(N + 1, N + 1))


def snap(lons, lats):
    _, idx = arbol.query(np.column_stack([lons, lats]))
    return idx


# --------------------------------------------------------------- hubs -----
sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
sec["k"] = sec["dep"].map(key)
puertos = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")

prov = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
cap = prov.geometry.representative_point()
cap_idx = snap(cap.x.values, cap.y.values)

mar = puertos[puertos.tipo == "maritimo"]
puerto_idx = snap(mar.lon.values, mar.lat.values)

sec_idx = snap(sec.lon.values, sec.lat.values)
# how far the sector centroid sits from the road it was snapped to
_, _, d_snap = GEOD.inv(sec.lon.values, sec.lat.values,
                        coords[sec_idx, 0], coords[sec_idx, 1])
sec["km_a_via"] = d_snap / 1000.0

# --------------------------------------------------------------- routing --
print("ruteando a capitales provinciales...", flush=True)
t_cap = dijkstra(construir(cap_idx), indices=N, directed=False)[:N]
print("ruteando a puertos maritimos...", flush=True)
t_pue = dijkstra(construir(puerto_idx), indices=N, directed=False)[:N]

sec["horas_capital_real"] = t_cap[sec_idx]
sec["horas_puerto_real"] = t_pue[sec_idx]

# A sector whose nearest road is far off is not truly served by that road;
# add the off-road leg at a slow speed rather than pretending it is zero.
sec["horas_capital_real"] += sec["km_a_via"] / 15.0
sec["horas_puerto_real"] += sec["km_a_via"] / 15.0

alcanzables = np.isfinite(sec["horas_capital_real"])
sin_puerto = ~np.isfinite(sec["horas_puerto_real"])
print(f"  sectores alcanzables: {alcanzables.sum():,} de {len(sec):,}", flush=True)
print(f"  sin conexion vial a puerto maritimo: {sin_puerto.sum():,}", flush=True)

# ------------------------------------------------------- compare vs proxy --
prev = pd.read_csv("out/logistica_sector.csv", encoding="utf-8-sig")
sec = sec.merge(prev[["cod_se", "horas_capital", "horas_puerto",
                      "puerto_maritimo"]],
                on="cod_se", how="left", suffixes=("", "_proxy"))
sec = sec.rename(columns={"horas_capital": "horas_capital_proxy",
                          "horas_puerto": "horas_puerto_proxy"})

COSTO_HORA = 18.0
sec["costo_viaje_real"] = 2 * sec["horas_capital_real"] * COSTO_HORA
sec["accesible_real"] = pd.cut(
    sec["horas_capital_real"], [-0.01, 1, 2, 4, 8, 1e9],
    labels=["<1 h", "1-2 h", "2-4 h", "4-8 h", ">8 h"])

cols = ["cod_se", "dep", "prov", "dist", "sector", "region_nat", "lat", "lon",
        "ha_agricola", "s_ha_cosechada", "s_clientes_sam", "s_sam_usd",
        "km_a_via", "horas_capital_real", "horas_capital_proxy",
        "horas_puerto_real", "horas_puerto_proxy", "puerto_maritimo",
        "costo_viaje_real", "accesible_real"]
sec[cols].to_csv("out/ruteo_sector.csv", index=False, encoding="utf-8-sig")

ok = sec[alcanzables]
print()
print("=" * 74)
print("RUTEO REAL SOBRE LA RED VIAL")
print("=" * 74)
print(f"snap medio del sector a la via : {sec.km_a_via.median():.1f} km")
print(f"horas a capital  · ruteo real  : "
      f"{np.average(ok.horas_capital_real, weights=ok.ha_agricola):.2f} h")
print(f"horas a capital  · proxy       : "
      f"{np.average(ok.horas_capital_proxy, weights=ok.ha_agricola):.2f} h")
_okp = ok[np.isfinite(ok.horas_puerto_real)]
print(f"horas a puerto   · ruteo real  : "
      f"{np.average(_okp.horas_puerto_real, weights=_okp.ha_agricola):.2f} h"
      f"   (sobre {len(_okp):,} sectores con conexion)")
print(f"horas a puerto   · proxy       : "
      f"{np.average(ok.horas_puerto_proxy, weights=ok.ha_agricola):.2f} h")
print()
acc = (ok.groupby("accesible_real", observed=True)
       .agg(sectores=("cod_se", "size"), sam=("s_sam_usd", "sum")))
acc["pct"] = 100 * acc["sam"] / acc["sam"].sum()
print("--- ACCESIBILIDAD MEDIDA ---")
for i, r in acc.iterrows():
    print(f"  {str(i):>6}  {int(r.sectores):5d} sectores  "
          f"US$ {r.sam/1e6:6,.0f} MM  {r.pct:5.1f}% del SAM")

dep = (ok.groupby("dep")
       .apply(lambda g: pd.Series({
           "horas_real": np.average(g.horas_capital_real, weights=g.ha_agricola),
           "horas_proxy": np.average(g.horas_capital_proxy, weights=g.ha_agricola),
           "puerto_real": (np.average(gp.horas_puerto_real, weights=gp.ha_agricola)
                           if len(gp := g[np.isfinite(g.horas_puerto_real)]) else np.nan),
           "pct_sin_puerto": 100 * (~np.isfinite(g.horas_puerto_real)).mean(),
           "pct_bajo_2h": 100 * (g.horas_capital_real <= 2).mean(),
           "pct_sobre_4h": 100 * (g.horas_capital_real > 4).mean(),
           "costo_viaje": np.average(g.costo_viaje_real, weights=g.ha_agricola),
           "sam": g.s_sam_usd.sum(),
       }), include_groups=False).reset_index())
dep["k"] = dep["dep"].map(key)
dep["dif"] = dep["horas_real"] - dep["horas_proxy"]
dep = dep.sort_values("horas_real")
dep.to_csv("out/ruteo_departamento.csv", index=False, encoding="utf-8-sig")

print()
print("--- POR REGION: MEDIDO vs ESTIMADO ---")
show = dep[["dep", "horas_real", "horas_proxy", "dif", "pct_bajo_2h",
            "puerto_real", "pct_sin_puerto", "costo_viaje"]].copy()
show["puerto_real"] = show.apply(
    lambda r: "sin via" if r["pct_sin_puerto"] > 50 else f"{r['puerto_real']:.1f}",
    axis=1)
show = show.drop(columns="pct_sin_puerto")
show.columns = ["region", "real_h", "proxy_h", "dif", "%<2h", "puerto_h",
                "US$_viaje"]
print(show.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))

print()
print("--- SIN CONEXION VIAL A PUERTO MARITIMO ---")
sp = dep[dep.pct_sin_puerto > 50][["dep", "pct_sin_puerto", "sam"]]
for _, r in sp.iterrows():
    print(f"  {r['dep']:<14} {r['pct_sin_puerto']:5.1f}% de sus sectores  "
          f"US$ {r['sam']/1e6:,.0f} MM de mercado")
print("  Su produccion no sale por puerto maritimo: es de mercado interno,")
print("  o sale por via fluvial. Cambia la canasta de insumos que demanda.")
