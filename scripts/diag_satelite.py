# -*- coding: utf-8 -*-
"""Qué compraría un octavo centro en el sur, y si hace falta.

El cruce del canal con los centros dejó un agujero con nombre: **Juliaca
resurte 466 puntos de venta, detrás de los cuales hay 19,130 clientes, y solo
el 7% de esos puntos está dentro de la promesa de cuatro horas** —mediana de
5.7 h—. Es el centro con más gente detrás de su canal y el que peor puede
abastecerlo. El altiplano tiene los clientes y no tiene cómo llegarles.

Esto mide qué pasaría al abrir un centro más, candidato por candidato, sin
mover ninguno de los siete que ya se decidieron. Tres cosas por candidato:

  puntos que entran     cuántos puntos de venta pasan a estar dentro de la
                        promesa de alguien
  clientes de cadena    cuántos clientes ganan la cadena completa: tienda a 45
                        minutos Y esa tienda abastecida dentro de la promesa
  su propio abasto      a cuántas horas está el candidato del centro más
                        cercano. Un satélite se reabastece de una casa madre;
                        si está a nueve horas de todo, no es un satélite sino
                        otro almacén, y cuesta otra cosa

La tercera es la que evita el error caro: proponer un satélite donde en
realidad hace falta un almacén completo.

No es una etapa del pipeline: es un diagnóstico que contesta una pregunta. Si
la respuesta se toma, el centro se agrega a `RED_EXTRA` en `build_hubs.py`,
que es donde viven las decisiones.

Uso:
    python scripts/diag_satelite.py
"""
import io
import json
import os
import re
import sys
import unicodedata

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                            # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

RADIO = 0.75          # el radio del cliente a la tienda, igual que en el canal
LIMITE = 0.8
R_HUB = 5
TIPOS_PUNTO = {"hardware", "veterinary", "trade", "doityourself", "agrarian",
               "garden_centre", "plant_nursery", "pet", "agricultural_engines",
               "yes"}


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def leer(p, **kw):
    return pd.read_csv(p, encoding="utf-8-sig", **kw)


red = json.load(io.open("out/red_elegida.json", encoding="utf-8"))
PROMESA = float(red["promesa_h"])
print("la red vigente: %s · promesa de %.0f h"
      % (" · ".join(c["hub"] for c in red["centros"]), PROMESA))

# --------------------------------------------------------------- demanda ---
sec = leer("out/ruteo_sector.csv")
sec = sec[np.isfinite(sec["horas_capital_real"])].copy()
CLI = sec["s_clientes_sam"].values

# ------------------------------------------------- los puntos que venden ---
# Los mismos de `build_canal.py`: padrón de clase «canal» y comercios de OSM.
emp = leer("out/empresas_agro_activas.csv", dtype={"ruc": str, "ubigeo": str})
emp = emp[(emp["clase"] == "canal") & emp["distrito"].notna()].copy()


def clave(d, *cols):
    j = d[list(cols)].astype(str).agg("|".join, axis=1)
    return j.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode(
        "ascii").str.upper()


xy = (sec.groupby(clave(sec, "dep", "prov", "dist"))
      .agg(lat=("lat", "mean"), lon=("lon", "mean")))
j = xy.reindex(clave(emp, "dep", "provincia", "distrito"))
emp["lat"], emp["lon"] = j["lat"].values, j["lon"].values
emp = emp[emp["lat"].notna()]

pro = leer("out/osm_prospectos.csv")
pro = pro[pro["lat"].notna() & pro["tipo"].isin(TIPOS_PUNTO)]
pts = pd.concat([
    pd.DataFrame({"nombre": emp["razon_social"], "dep": emp["dep"],
                  "clase": "canal", "lat": emp["lat"], "lon": emp["lon"]}),
    pd.DataFrame({"nombre": pro["nombre"], "dep": pro["dep"],
                  "clase": "comercio", "lat": pro["lat"], "lon": pro["lon"]}),
], ignore_index=True)
print("puntos que ya venden: %d" % len(pts))

print("armando el grafo vial...", flush=True)
g = grafo_vial.construir()
sec_idx = g.snap(sec.lon.values, sec.lat.values)
pts_idx = g.snap(pts.lon.values, pts.lat.values)

print("midiendo a cuántos clientes llega cada punto...", flush=True)
G = g.csr(hacia=True)
alcance = []
for src in pts_idx:
    d = dijkstra(G, indices=int(src), directed=True, limit=LIMITE)
    t = d[sec_idx]
    alcance.append(np.flatnonzero(np.isfinite(t) & (t <= RADIO)))

# -------------------------------------- el tramo de arriba, hoy y con uno --
# La matriz candidato x celda ya está calculada por `build_hubs.py`, y está en
# el sentido del reparto —del centro a la celda—. Aquí solo se consulta: no
# hace falta rutear nada de nuevo.
dem = leer("out/h3_r5.csv", dtype={"h3": str})
dem = dem[dem["sam_usd"] > 0].reset_index(drop=True)
W = dem["sam_usd"].values
T = np.load("out/hubs_matriz_tiempos.npy")

cap = gpd.read_file("data/peru_capital_provincia.geojson").to_crs(4326)
cap["kp"] = cap["PROVINCIA"].map(slug)
# Ojo: `build_hubs.py` calcula el mercado provincial sobre el archivo entero,
# sin descartar los sectores sin ruta. Filtrarlos aquí movía el umbral del
# 0.2% y cambiaba cuántas ciudades entran como candidatas, con lo que la
# matriz guardada dejaba de corresponder a esta lista.
_sec_todo = leer("out/ruteo_sector.csv")
cap["sam"] = cap["kp"].map(
    _sec_todo.groupby(_sec_todo["prov"].map(slug))["s_sam_usd"].sum()).fillna(0)
cap["lat"], cap["lon"] = cap.geometry.y, cap.geometry.x
cand = (cap[cap["sam"] > W.sum() * 0.002]
        .sort_values("sam", ascending=False).reset_index(drop=True))
if len(cand) != T.shape[0]:
    sys.exit("la matriz no corresponde a estos candidatos: corre build_hubs")

idx_celda = {c: i for i, c in enumerate(dem.h3)}
pts["h3"] = [h3.latlng_to_cell(a, b, R_HUB)
             for a, b in zip(pts["lat"], pts["lon"])]
pos = np.array([idx_celda.get(c, -1) for c in pts["h3"]])
vivo = pos >= 0
print("puntos ubicables en la grilla de reparto: %d de %d"
      % (int(vivo.sum()), len(pts)))

# horas de cada punto al centro vigente más cercano
sel_actual = [int(cand.index[cand["PROVINCIA"].map(slug) == slug(c["provincia"])][0])
              for c in red["centros"]]
t_actual = T[sel_actual][:, pos.clip(min=0)].min(axis=0)
t_actual[~vivo] = np.inf
hoy = t_actual <= PROMESA
print()
print("hoy: %d de %d puntos dentro de la promesa (%.0f%%)"
      % (hoy.sum(), vivo.sum(), 100 * hoy.sum() / vivo.sum()))


def clientes_cadena(mask_ok):
    """Clientes con la cadena completa: tienda a 45 min y esa tienda dentro de
    la promesa de algún centro."""
    en = np.zeros(len(sec), dtype=bool)
    for a, ok in zip(alcance, mask_ok):
        if ok:
            en[a] = True
    return CLI[en].sum()


# Los puntos que hoy le tocan a Juliaca y quedan fuera de su promesa: son el
# agujero que abrió el cruce del canal con los centros, y la pregunta no es
# cuánto suma un octavo centro en general sino cuánto de ESTO arregla.
_dueno = np.array(sel_actual)[T[sel_actual][:, pos.clip(min=0)].argmin(axis=0)]
_i_jul = int(cand.index[cand["PROVINCIA"].map(slug) == slug("San Roman")][0])
huerf_jul = (_dueno == _i_jul) & ~hoy & vivo
print("     de ellos, %d puntos son de Juliaca y quedan fuera de su promesa"
      % int(huerf_jul.sum()))

base_cli = clientes_cadena(hoy)
base_sam = W[(T[sel_actual] <= PROMESA).any(axis=0)].sum()
print("     %s clientes con la cadena completa · US$ %.0f MM de mercado "
      "dentro de la promesa" % (f"{base_cli:,.0f}", base_sam / 1e6))

# ------------------------------------------------- qué compra el octavo ----
print()
print("qué compraría un octavo centro", flush=True)
filas = []
for i in range(len(cand)):
    if i in sel_actual:
        continue
    t_nuevo = np.minimum(t_actual, T[i][pos.clip(min=0)])
    t_nuevo[~vivo] = np.inf
    nuevo = t_nuevo <= PROMESA
    if nuevo.sum() == hoy.sum():
        continue
    cli = clientes_cadena(nuevo)
    sam = W[((T[sel_actual + [i]]) <= PROMESA).any(axis=0)].sum()
    filas.append({
        "candidato": str(cand.loc[i, "PROVINCIA"]).title(),
        "region": str(cand.loc[i, "DEPARTAM"]).title(),
        "puntos_nuevos": int(nuevo.sum() - hoy.sum()),
        "clientes_cadena": int(round(cli)),
        "clientes_nuevos": int(round(cli - base_cli)),
        "sam_mm": round(sam / 1e6, 1),
        "sam_nuevo_mm": round((sam - base_sam) / 1e6, 1),
        "rescata_juliaca": int((huerf_jul & nuevo).sum()),
    })

res = pd.DataFrame(filas).sort_values("clientes_nuevos", ascending=False)

# El propio abasto del candidato: horas desde cada centro vigente hasta la
# celda del candidato. Si no cae en la grilla, no se inventa.
cap_h3 = [h3.latlng_to_cell(la, lo, R_HUB)
          for la, lo in zip(cand["lat"], cand["lon"])]
h_madre = {}
for i, c in enumerate(cap_h3):
    p = idx_celda.get(c, -1)
    h_madre[str(cand.loc[i, "PROVINCIA"]).title()] = (
        float(T[sel_actual, p].min()) if p >= 0 else float("nan"))
res["h_a_la_red"] = res["candidato"].map(h_madre)

res.to_csv("out/diag_satelite.csv", index=False, encoding="utf-8-sig")
print("  %-18s %-10s %7s %10s %8s %10s %10s"
      % ("candidato", "región", "puntos", "clientes", "SAM +MM",
         "de Juliaca", "h a la red"))
for _, r in res.head(12).iterrows():
    print("  %-18s %-10s %+7d %+10s %+8.1f %10d %10s"
          % (r.candidato[:18], r.region[:10], r.puntos_nuevos,
             f"{r.clientes_nuevos:,}", r.sam_nuevo_mm, r.rescata_juliaca,
             "—" if not np.isfinite(r.h_a_la_red) else "%.1f" % r.h_a_la_red))

# Un satélite se abastece de la casa madre; si el candidato está fuera de la
# promesa de todos los centros, lo que hace falta ahí es otro almacén y no un
# satélite, y cuesta otra cosa. La distinción no la puede hacer el ranking.
sat = res[res.h_a_la_red <= PROMESA]
print()
print("los que pueden funcionar como satélite —a menos de %.0f h de la red—"
      % PROMESA)
if not len(sat):
    print("  ninguno: todo lo que arregla el sur está fuera de la promesa")
for _, r in sat.head(5).iterrows():
    print("  %-18s %-10s %+7d puntos  %+9s clientes  a %.1f h de la red"
          % (r.candidato[:18], r.region[:10], r.puntos_nuevos,
             f"{r.clientes_nuevos:,}", r.h_a_la_red))

print()
print("out/diag_satelite.csv")
