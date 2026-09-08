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
import io
import json
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

# --- la red elegida --------------------------------------------------------
# La cobertura maxima es un calculo; la red es una decision. Hasta ahora la
# decision vivia implicita en dos numeros sueltos dentro del codigo de
# asignacion —«escenario de 2 h y k=6»— de modo que cambiarla era editar una
# linea sin dejar rastro de por que.
#
# La red vigente son los seis que elige el algoritmo con vara de dos horas MAS
# Huamachuco, y la promesa de servicio es de cuatro horas. La razon esta
# medida y no supuesta: Sanchez Carrion y Pataz son el mayor territorio del
# pais —US$ 33.6 MM, el 6.7% del mercado nacional, 9,114 clientes, el 69% de
# su mercado sobre los 3,000 m— y no lo sirve nadie a dos horas. El mejor
# centro posible es su propia capital y alcanza el 22% de ese mercado a dos
# horas y el 63% a cuatro. Con vara de dos horas Huamachuco es el candidato
# numero 14 para el septimo almacen; con vara de cuatro es el primero del
# pais, con +5.62 puntos de cobertura nacional.
#
# Que la vara cambie el ranking entero no es un defecto del metodo: es que la
# promesa de servicio es una decision comercial y no un parametro tecnico.
# Por eso se declara aqui, con su fecha y su motivo, y no se deduce.
RED_BASE_K = 6                  # los que elige el greedy con vara de 2 h
RED_BASE_UMBRAL = 2.0
RED_EXTRA = ["Huamachuco", "Sicuani"]   # por decision, no por el algoritmo
# La promesa no es un número sino un criterio, y esa es la segunda decisión
# comercial que este archivo declara. Cuatro horas en costa y seis en sierra y
# selva, porque el terreno no se reparte parejo y prometer lo mismo en los dos
# sitios significa incumplir en uno.
#
# Sale de una medición y no de una intuición. Con vara única de cuatro horas
# quedaban 257 puntos de venta del altiplano fuera de la promesa de su centro,
# y `diag_satelite.py` mostró que ese hueco no se cierra abriendo: encadenando
# ocho satélites nacionales los 257 se quedan donde estaban —el sur no compite
# por plata— y obligando al algoritmo a resolver el sur no encuentra ni un
# candidato que pueda abastecerse dentro de la promesa. En cambio pasar de
# cuatro a seis horas compra 8,686 clientes con cero inversión, casi lo mismo
# que los ocho almacenes.
#
# La vara es la palanca más barata que tiene esta red. Diferenciarla es lo que
# hace la distribución real: al valle costero se llega en la mañana y a la
# provincia andina se va con ruta programada.
PROMESA_H = {"COSTA": 4.0, "SIERRA": 6.0, "SELVA ALTA": 6.0,
             "SELVA BAJA": 6.0}
PROMESA_DEF = 6.0               # lo que no se pueda clasificar, por el lado caro

# El segundo agregado, Sicuani, sale del cruce del canal con los centros y no
# de la cobertura de mercado. El problema que resuelve: de los 3,097 puntos de
# venta ubicables, 435 de los que le tocan a Juliaca quedan fuera de su propia
# promesa —el altiplano tiene los clientes y no tiene como abastecerlos, con
# mediana de 5.7 h—.
#
# `diag_satelite.py` midio los 101 candidatos posibles. Una docena rescata
# entre 166 y 203 de esos puntos y todos estan en el mismo hueco, asi que el
# ranking por clientes no decide: lo que decide es a cuantas horas queda el
# candidato de la red que ya existe. Un satelite se reabastece de una casa
# madre; a seis horas de todo no es un satelite sino otro almacen, y cuesta
# otra cosa. Urubamba compra 400 clientes mas y esta a 5.7 h de todo;
# **Sicuani esta a 3.3 h, dentro de la promesa, y se abastece de Juliaca**.
#
# Lo que no hace, dicho: rescata 167 de los 435 puntos y quedan 268 fuera. El
# sur no se arregla con un centro mas.

def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ------------------------------------------------------------------ grafo --
# El grafo ya lleva la pendiente, y con ella dejo de ser simetrico: el tiempo
# de bajar del centro al valle no es el de subir. Aqui se mide el sentido de
# la entrega —del centro hacia la celda de demanda—, que es el viaje que el
# almacen hace todos los dias, y por eso `directed=True` y la matriz directa.
g = grafo_vial.construir()
coords, arbol = g.coords, g.arbol
G = g.csr()


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
    d = dijkstra(G, indices=int(src), directed=True)
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

# --------------------------------------------------- asignacion a la red ---
# Cada celda va a su centro mas cercano DE LA RED ELEGIDA, que no es lo mismo
# que el mejor conjunto que el algoritmo encontraria con la vara de cuatro
# horas: ese seria otro —Chiclayo, Tarma, Tarapoto, Chincha Alta, Sicuani,
# Huamachuco...— y significaria mover los seis centros ya decididos. La red
# vigente conserva los seis y suma el septimo, que es lo que se decidio.
base = res[(res.umbral_h == RED_BASE_UMBRAL) & (res.k <= RED_BASE_K)]
nombres = list(base.hub) + list(RED_EXTRA)
sel = []
for nom in nombres:
    f = cand[cand.CAPITAL.str.title() == nom]
    if not len(f):
        sys.exit("el centro %r no esta entre los candidatos: revisa RED_EXTRA"
                 % nom)
    sel.append(int(f.index[0]))

sub = T[sel]
mejor_hub = np.argmin(sub, axis=0)
dem_out = dem.copy()
dem_out["hub"] = [nombres[i] for i in mejor_hub]
dem_out["horas_al_hub"] = sub[mejor_hub, np.arange(len(dem))]
# Las dos varas viajan juntas a proposito. La de dos horas es la que uso este
# proyecto durante meses y hay cifras publicadas con ella; la promesa vigente
# es la de cuatro. Publicar solo una obligaria a rehacer la comparacion a mano
# cada vez que alguien pregunte cuanto cambio.
dem_out["cubierto_2h"] = dem_out["horas_al_hub"] <= 2.0
dem_out["promesa_h"] = (dem_out["region_nat"].map(PROMESA_H)
                        .fillna(PROMESA_DEF))
dem_out["cubierto_promesa"] = dem_out["horas_al_hub"] <= dem_out["promesa_h"]
dem_out.to_csv("out/hubs_asignacion.csv", index=False, encoding="utf-8-sig")

cub2 = W[dem_out["cubierto_2h"].values].sum() / SAM_TOTAL
cubp = W[dem_out["cubierto_promesa"].values].sum() / SAM_TOTAL
por_region = (dem_out.assign(sam=W)
              .groupby("region_nat")
              .apply(lambda x: pd.Series({
                  "promesa_h": float(x.promesa_h.iloc[0]),
                  "sam_mm": x.sam.sum() / 1e6,
                  "pct": 100 * x.loc[x.cubierto_promesa, "sam"].sum()
                  / x.sam.sum()}), include_groups=False)
              .reset_index())
red = {
    "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "motivo": ("La red es una decisión y no el resultado del algoritmo: son "
               "los %d centros que elige la cobertura máxima con vara de "
               "%.0f horas, más %s. La promesa de servicio tampoco es un "
               "número único: %s, porque el terreno no se reparte parejo y "
               "prometer lo mismo en los dos sitios significa incumplir en "
               "uno."
               % (RED_BASE_K, RED_BASE_UMBRAL, ", ".join(RED_EXTRA),
                  ", ".join("%.0f h en %s" % (v, k.lower())
                            for k, v in sorted(PROMESA_H.items(),
                                               key=lambda x: x[1])))),
    "promesa_h": PROMESA_H,
    "promesa_def_h": PROMESA_DEF,
    "centros": [{"hub": r.hub, "provincia": r.provincia, "region": r.region,
                 "lat": r.lat, "lon": r.lon, "por": "algoritmo"}
                for _, r in base.iterrows()]
               + [{"hub": n, "provincia": str(cand.loc[i, "PROVINCIA"]).title(),
                   "region": str(cand.loc[i, "DEPARTAM"]).title(),
                   "lat": round(float(cand.loc[i, "lat"]), 5),
                   "lon": round(float(cand.loc[i, "lon"]), 5),
                   "por": "decision"}
                  for n, i in zip(RED_EXTRA, sel[RED_BASE_K:])],
    "sam_cubierto_promesa_pct": round(100 * cubp, 2),
    "sam_cubierto_2h_pct": round(100 * cub2, 2),
    "por_region": [{"region": r.region_nat, "promesa_h": r.promesa_h,
                    "sam_mm": round(float(r.sam_mm), 1),
                    "pct": round(float(r.pct), 1)}
                   for _, r in por_region.iterrows()],
}
with io.open("out/red_elegida.json", "w", encoding="utf-8") as fh:
    json.dump(red, fh, ensure_ascii=False, indent=1)
print()
print("la red elegida: %s" % " · ".join(nombres))
print("  promesa diferenciada (%s): cubre el %.1f%% del mercado"
      % (", ".join("%.0f h %s" % (v, k.lower())
                   for k, v in sorted(PROMESA_H.items(), key=lambda x: x[1])),
         100 * cubp))
for _, r in por_region.iterrows():
    print("    %-12s %.0f h · US$ %6.1f MM · %.1f%% dentro"
          % (r.region_nat, r.promesa_h, r.sam_mm, r.pct))
print("  con vara de 2 h  : cubre el %.1f%%" % (100 * cub2))

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
