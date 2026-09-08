# -*- coding: utf-8 -*-
"""Measure real road travel times over the OpenStreetMap network.

This replaces the geodesic proxy with routing on the actual road graph: 88,962
ways across the 25 departments, each edge weighted by the time a loaded
delivery vehicle would take on it.

El grafo, el modelo de velocidad y la pendiente los arma `grafo_vial.py`, que
es el mismo módulo que usa la elección de centros: clase de vía por superficie,
topada por el límite señalizado, corregida por la pendiente medida sobre una
ventana de 1 km de carretera.

Terreno. Durante meses este archivo declaró la velocidad como «free-flow km/h
for a loaded light truck, before surface and terrain» y el terreno nunca entró:
un camión cargado subiendo tres mil metros contaba igual que uno en llano, y
media plataforma —horas al centro, costo de la visita, orden de apertura de
centros— colgaba de esa cuenta.

Eso obliga a un cambio de fondo: **con pendiente el grafo deja de ser
simétrico**. Subir de Virú a Otuzco no cuesta lo mismo que bajar, así que el
ruteo se corre en los dos sentidos —ida del sector al centro, vuelta del centro
al sector— y el costo del viaje es la suma de las dos, no el doble de una. La
diferencia entre las dos mitades es, además, un dato en sí: dice de qué lado
del desnivel está el problema.

Algorithm. The question "how far is each sector from a hub" is answered for the
whole country in one pass: a virtual source is joined to every hub at zero cost
and a single Dijkstra then labels every node in the graph with the time to its
nearest hub. Con el grafo asimétrico se corre además sobre el grafo traspuesto,
que es el truco estándar para contestar «cuánto tarda cada nodo en llegar al
hub» en vez de «cuánto tarda el hub en llegar al nodo». Dos destinos —capitales
provinciales y puertos marítimos— por dos sentidos, y una corrida más en llano
para poder medir cuánto pesa el terreno.
"""
import os
import re
import sys
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                            # noqa: E402
from cota import muestrear                                    # noqa: E402

GEOD = Geod(ellps="WGS84")


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


# ---------------------------------------------------------------- graph ----
# El grafo lo arma `grafo_vial.py`, que es el mismo que usa la selección de
# centros: si el ruteo midiera la pendiente de una forma y la elección de
# almacenes de otra, las dos mitades de la misma decisión dejarían de hablar
# entre sí. Este archivo tuvo su propia copia durante una tarde y esa tarde
# alcanzó para que las dos versiones ya no coincidieran.
print("armando el grafo vial...", flush=True)
g = grafo_vial.construir()
coords, N = g.coords, g.N
snap = g.snap

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
# `directed=True` no es un detalle: con pendiente el grafo dejó de ser
# simétrico, y `directed=False` haría a scipy recorrer cada arista en los dos
# sentidos por el peso que encuentre, que es justamente la cuenta que se quiso
# dejar atrás.
def rutear(fuentes, nombre):
    print("ruteando %s..." % nombre, flush=True)
    ida = dijkstra(g.csr(hacia=True, fuentes=fuentes),
                   indices=N, directed=True)[:N]
    vuelta = dijkstra(g.csr(hacia=False, fuentes=fuentes),
                      indices=N, directed=True)[:N]
    return ida, vuelta


print("ruteando en llano, para medir cuanto pesa el terreno...", flush=True)
cap_llano = dijkstra(g.csr(llano=True, hacia=True, fuentes=cap_idx),
                     indices=N, directed=True)[:N]

cap_ida, cap_vuelta = rutear(cap_idx, "a capitales provinciales")
pue_ida, pue_vuelta = rutear(puerto_idx, "a puertos maritimos")

sec["horas_capital_real"] = cap_ida[sec_idx]
sec["horas_capital_vuelta"] = cap_vuelta[sec_idx]
sec["horas_capital_llano"] = cap_llano[sec_idx]
sec["horas_puerto_real"] = pue_ida[sec_idx]
sec["horas_puerto_vuelta"] = pue_vuelta[sec_idx]
sec["alt_m"] = muestrear(sec.lon.values, sec.lat.values)

# A sector whose nearest road is far off is not truly served by that road;
# add the off-road leg at a slow speed rather than pretending it is zero.
for c in ("horas_capital_real", "horas_capital_vuelta", "horas_capital_llano",
          "horas_puerto_real", "horas_puerto_vuelta"):
    sec[c] += sec["km_a_via"] / 15.0

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
# El viaje redondo ya no es el doble de la ida: subir y bajar cuestan distinto,
# así que se suman las dos mitades medidas.
sec["horas_ida_vuelta"] = sec["horas_capital_real"] + sec["horas_capital_vuelta"]
sec["costo_viaje_real"] = sec["horas_ida_vuelta"] * COSTO_HORA
sec["horas_terreno"] = sec["horas_capital_real"] - sec["horas_capital_llano"]
sec["accesible_real"] = pd.cut(
    sec["horas_capital_real"], [-0.01, 1, 2, 4, 8, 1e9],
    labels=["<1 h", "1-2 h", "2-4 h", "4-8 h", ">8 h"])

cols = ["cod_se", "dep", "prov", "dist", "sector", "region_nat", "lat", "lon",
        "alt_m", "ha_agricola", "s_ha_cosechada", "s_clientes_sam", "s_sam_usd",
        "km_a_via", "horas_capital_real", "horas_capital_vuelta",
        "horas_capital_llano", "horas_terreno", "horas_ida_vuelta",
        "horas_capital_proxy", "horas_puerto_real", "horas_puerto_vuelta",
        "horas_puerto_proxy", "puerto_maritimo",
        "costo_viaje_real", "accesible_real"]
sec[cols].to_csv("out/ruteo_sector.csv", index=False, encoding="utf-8-sig")

ok = sec[alcanzables]
print()
print("=" * 74)
print("RUTEO REAL SOBRE LA RED VIAL")
print("=" * 74)
print(f"snap medio del sector a la via : {sec.km_a_via.median():.1f} km")
print(f"horas a capital  · con terreno : "
      f"{np.average(ok.horas_capital_real, weights=ok.ha_agricola):.2f} h")
print(f"horas a capital  · en llano    : "
      f"{np.average(ok.horas_capital_llano, weights=ok.ha_agricola):.2f} h"
      f"   (lo que decia esta plataforma hasta ahora)")
print(f"horas a capital  · proxy       : "
      f"{np.average(ok.horas_capital_proxy, weights=ok.ha_agricola):.2f} h")
print(f"vuelta desde la capital        : "
      f"{np.average(ok.horas_capital_vuelta, weights=ok.ha_agricola):.2f} h"
      f"   (la asimetria del desnivel)")

# Lo que el terreno agrega no se reparte parejo, y ahi esta el interes: la
# media nacional se mueve poco y hay regiones que se mueven mucho.
peor = (ok.assign(pen=ok.horas_terreno)
          .groupby("dep")
          .apply(lambda g: pd.Series({
              "mas_h": np.average(g.pen, weights=g.ha_agricola),
              # El porcentaje se saca de las dos medias publicadas y no del
              # promedio de los porcentajes de cada sector: es la cuenta que
              # el lector puede rehacer con la tabla a la vista, y es la misma
              # que sirve el sitio. Dos definiciones del mismo numero acaban
              # discrepando en la tercera pantalla que lo muestra.
              "pct": 100 * (np.average(g.horas_capital_real,
                                       weights=g.ha_agricola)
                            / np.average(g.horas_capital_llano,
                                         weights=g.ha_agricola) - 1),
              "alt": np.average(g.alt_m.fillna(0), weights=g.ha_agricola),
          }), include_groups=False)
          .sort_values("pct", ascending=False))
print()
print("--- LO QUE AGREGA EL TERRENO, POR REGION ---")
print("  %-16s %9s %8s %9s" % ("region", "cota med", "mas h", "mas %"))
for d, r in peor.head(8).iterrows():
    print("  %-16s %9.0f %8.2f %8.1f%%" % (d, r.alt, r.mas_h, r.pct))
print("  ...")
for d, r in peor.tail(3).iterrows():
    print("  %-16s %9.0f %8.2f %8.1f%%" % (d, r.alt, r.mas_h, r.pct))
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
           "horas_llano": np.average(g.horas_capital_llano, weights=g.ha_agricola),
           "horas_vuelta": np.average(g.horas_capital_vuelta, weights=g.ha_agricola),
           "alt_m": np.average(g.alt_m.fillna(0), weights=g.ha_agricola),
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
