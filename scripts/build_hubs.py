# -*- coding: utf-8 -*-
"""Dónde ubicar los centros de distribución, midiendo sobre la red vial.

Es la decisión de capital más cara de un negocio que entrega: un almacén mal
puesto se paga todos los días en horas de camión. El problema es de cobertura
máxima —elegir k ubicaciones que dejen la mayor cantidad de mercado dentro de
un radio de tiempo— y se resuelve con el algoritmo voraz, que en funciones
submodulares garantiza quedar dentro del 63% del óptimo y en la práctica llega
mucho más cerca.

Método:
  candidatos   capitales de provincia con mercado agrícola relevante
  demanda      celdas H3 r5, ponderadas por su SAM
  costo        tiempo de viaje ruteado sobre la red vial, no distancia recta
  criterio     SAM que queda a menos de 2, 4 y 6 horas de algún centro

Se corre un Dijkstra por candidato y solo se conservan los tiempos hacia los
nodos de demanda: guardar la matriz completa contra 5.2 millones de nodos
ocuparía gigabytes sin aportar nada.
"""
import re
import unicodedata

import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial

UMBRALES = [2.0, 4.0, 6.0]      # horas
K_MAX = 12                      # centros a evaluar

def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ------------------------------------------------------------------ grafo --
G, coords, arbol = grafo_vial.construir()


def snap(lons, lats):
    return arbol.query(np.column_stack([lons, lats]))[1]


# --------------------------------------------------------------- demanda --
dem = pd.read_csv("out/h3_r5.csv", encoding="utf-8-sig")
dem = dem[dem["sam_usd"] > 0].reset_index(drop=True)
dem_idx = snap(dem.centro_lon.values, dem.centro_lat.values)
W = dem["sam_usd"].values
SAM_TOTAL = W.sum()

# ------------------------------------------------------------- candidatos -
# La ciudad capital, no el centroide de la provincia: un almacén se instala en
# un pueblo con carretera, energía y mano de obra, no en el centro geométrico
# de un polígono. Usar el centroide hacía ganar a provincias como Chepén o
# Picota por accidente de forma.
cap = gpd.read_file("data/peru_capital_provincia.geojson").to_crs(4326)
cap["lon"] = cap.geometry.x
cap["lat"] = cap.geometry.y
cap["kp"] = cap["PROVINCIA"].map(slug)

sec = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")
sam_prov = sec.groupby(sec["prov"].map(slug))["s_sam_usd"].sum()
cap["sam"] = cap["kp"].map(sam_prov).fillna(0)

cand = cap[cap["sam"] > SAM_TOTAL * 0.002].copy()
cand = cand.sort_values("sam", ascending=False).reset_index(drop=True)
cand_idx = snap(cand.lon.values, cand.lat.values)
print(f"candidatos: {len(cand)} ciudades capitales con mercado relevante",
      flush=True)

# --------------------------------------------- matriz candidato x demanda --
print("ruteando desde cada candidato...", flush=True)
T = np.full((len(cand), len(dem)), np.inf)
for i, src in enumerate(cand_idx):
    d = dijkstra(G, indices=int(src), directed=False)
    T[i] = d[dem_idx]
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(cand)}", flush=True)

np.save("out/hubs_matriz_tiempos.npy", T)


# ------------------------------------------------------------------ greedy -
def cobertura(seleccion, umbral):
    if not seleccion:
        return 0.0
    return W[(T[seleccion] <= umbral).any(axis=0)].sum()


resultados = []
for umbral in UMBRALES:
    sel, filas = [], []
    for k in range(1, K_MAX + 1):
        mejor, mejor_val = None, -1
        for j in range(len(cand)):
            if j in sel:
                continue
            v = cobertura(sel + [j], umbral)
            if v > mejor_val:
                mejor, mejor_val = j, v
        sel.append(mejor)
        filas.append({
            "umbral_h": umbral, "k": k,
            "hub": cand.loc[mejor, "CAPITAL"].title(),
            "provincia": cand.loc[mejor, "PROVINCIA"].title(),
            "region": cand.loc[mejor, "DEPARTAM"].title(),
            "lat": round(cand.loc[mejor, "lat"], 5),
            "lon": round(cand.loc[mejor, "lon"], 5),
            "sam_cubierto": mejor_val,
            "pct_sam": 100 * mejor_val / SAM_TOTAL,
        })
    resultados += filas

res = pd.DataFrame(resultados)
res["marginal"] = res.groupby("umbral_h")["pct_sam"].diff().fillna(
    res["pct_sam"])
res.to_csv("out/hubs_cobertura.csv", index=False, encoding="utf-8-sig")

# asignación de cada celda al hub más cercano, para el escenario de 2 h y k=6
u = 2.0
sel = [int(cand[cand.CAPITAL.str.title() == r.hub].index[0])
       for _, r in res[(res.umbral_h == u) & (res.k <= 6)].iterrows()]
sub = T[sel]
mejor_hub = np.argmin(sub, axis=0)
dem_out = dem.copy()
dem_out["hub"] = [res[(res.umbral_h == u)].iloc[i]["hub"] for i in mejor_hub]
dem_out["horas_al_hub"] = sub[mejor_hub, np.arange(len(dem))]
dem_out["cubierto_2h"] = dem_out["horas_al_hub"] <= u
dem_out.to_csv("out/hubs_asignacion.csv", index=False, encoding="utf-8-sig")

print()
print("=" * 74)
print("UBICACION DE CENTROS DE DISTRIBUCION")
print("=" * 74)
print(f"SAM total considerado: US$ {SAM_TOTAL/1e6:,.0f} MM en {len(dem):,} celdas")
for umbral in UMBRALES:
    r = res[res.umbral_h == umbral]
    print(f"\n--- cobertura a {umbral:.0f} horas ---")
    for _, x in r.iterrows():
        barra = "#" * int(x.pct_sam / 2.5)
        print(f"  {int(x.k):2d}. {x.hub:<16s} {x.region:<14s} "
              f"{x.pct_sam:5.1f}%  (+{x.marginal:4.1f})  {barra}")

r2 = res[res.umbral_h == 2.0]
print()
print(f"Con 6 centros a 2 horas se cubre el {r2[r2.k==6].pct_sam.iat[0]:.0f}% "
      f"del mercado atendible.")
print(f"El septimo centro agrega {r2[r2.k==7].marginal.iat[0]:.1f} puntos: "
      "ahi empieza el rendimiento decreciente.")
