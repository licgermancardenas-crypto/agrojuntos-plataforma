# -*- coding: utf-8 -*-
"""Cuántos centros haría falta para cerrar el sur, y si conviene.

El cruce del canal con los centros dejó un agujero con nombre: **Juliaca
resurte 466 puntos de venta, detrás de los cuales hay 19,130 clientes, y solo
el 7% de esos puntos está dentro de la promesa de cuatro horas** —mediana de
5.7 h—. Es el centro con más gente detrás de su canal y el que peor puede
abastecerlo. El altiplano tiene los clientes y no tiene cómo llegarles.

La primera corrida de esto contestó una pregunta más chica —qué compraría UN
centro más— y su respuesta fue Sicuani, que ya está en la red. Lo que quedó
abierto es lo otro: de los 435 puntos huérfanos, Sicuani rescató 199 y quedan
236. Así que ahora mide dos cosas.

**Cuántos centros harían falta.** Una cadena de satélites, uno tras otro, cada
uno elegido por lo que suma y sujeto a poder abastecerse: se exige que esté
dentro de la promesa de la red que ya existe en ese momento —incluidos los
satélites anteriores, que a su vez pueden ser casa madre del siguiente—. La
curva dice dónde deja de pagar.

**Qué pasaría con otra cadencia.** Abrir no es la única salida: la otra es
prometer distinto. Con los mismos centros, cuántos puntos entran si la promesa
fuera de cinco, seis u ocho horas. Es la comparación que hay que tener delante
antes de firmar un alquiler, y no se puede hacer sin ponerlas juntas.

Por candidato se miden tres cosas:

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

Era un diagnóstico de una vez y ahora es una etapa, porque la pregunta no se
cerró: «¿conviene un noveno centro?» está abierta en el módulo de decisiones, y
una decisión abierta cuyo número solo existe en la terminal de quien corrió el
script es una decisión sin dato. Emite `satelite.json`, que es de donde
`build_decisiones.py` saca el marginal.

Si la respuesta se toma, el centro se agrega a `RED_EXTRA` en `build_hubs.py`,
que es donde viven las decisiones.

Uso:
    python scripts/build_satelite.py
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
# La promesa dejó de ser un número: son cuatro horas en la costa y seis en el
# resto, porque el terreno no se reparte parejo. Este archivo la leía como
# `float(red["promesa_h"])` y desde entonces reventaba al arrancar; se lee por
# celda, que es como la publica `hubs_asignacion.csv`.
PROMESA_TXT = " · ".join("%s %.0f h" % (k.lower(), v)
                         for k, v in red["promesa_h"].items())
print("la red vigente: %s · promesa %s"
      % (" · ".join(c["hub"] for c in red["centros"]), PROMESA_TXT))

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

# La promesa de cada celda, que es la vara con la que se juzga si algo está
# dentro. `PROM_C` va por celda —para el SAM— y `PROM_P` por punto de venta,
# que hereda la de la celda donde cae.
_asg = leer("out/hubs_asignacion.csv", dtype={"h3": str})
_pmap = dict(zip(_asg["h3"], _asg["promesa_h"]))
PROM_DEF = float(red.get("promesa_def_h", 6.0))
PROM_C = np.array([float(_pmap.get(c, PROM_DEF)) for c in dem.h3])

idx_celda = {c: i for i, c in enumerate(dem.h3)}
pts["h3"] = [h3.latlng_to_cell(a, b, R_HUB)
             for a, b in zip(pts["lat"], pts["lon"])]
pos = np.array([idx_celda.get(c, -1) for c in pts["h3"]])
vivo = pos >= 0
PROM_P = np.where(vivo, PROM_C[pos.clip(min=0)], PROM_DEF)
print("puntos ubicables en la grilla de reparto: %d de %d"
      % (int(vivo.sum()), len(pts)))

# horas de cada punto al centro vigente más cercano
sel_actual = [int(cand.index[cand["PROVINCIA"].map(slug) == slug(c["provincia"])][0])
              for c in red["centros"]]
t_actual = T[sel_actual][:, pos.clip(min=0)].min(axis=0)
t_actual[~vivo] = np.inf
hoy = t_actual <= PROM_P
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
base_sam = W[(T[sel_actual] <= PROM_C).any(axis=0)].sum()
print("     %s clientes con la cadena completa · US$ %.0f MM de mercado "
      "dentro de la promesa" % (f"{base_cli:,.0f}", base_sam / 1e6))

# ------------------------------------------------- qué compra el octavo ----
def gana(t_ref, extra=None):
    """Puntos dentro de la promesa y clientes con la cadena completa, para la
    red vigente más `extra`."""
    t = t_ref if extra is None else np.minimum(t_ref, T[extra][pos.clip(min=0)])
    t = np.where(vivo, t, np.inf)
    ok = t <= PROM_P
    return ok, clientes_cadena(ok), t


print()
print("qué compraría un centro más, uno por uno", flush=True)
filas = []
for i in range(len(cand)):
    if i in sel_actual:
        continue
    nuevo_ok, cli, _ = gana(t_actual, i)
    if nuevo_ok.sum() == hoy.sum():
        continue
    sam = W[((T[sel_actual + [i]]) <= PROM_C).any(axis=0)].sum()
    filas.append({
        "candidato": str(cand.loc[i, "PROVINCIA"]).title(),
        "region": str(cand.loc[i, "DEPARTAM"]).title(),
        "puntos_nuevos": int(nuevo_ok.sum() - hoy.sum()),
        "clientes_cadena": int(round(cli)),
        "clientes_nuevos": int(round(cli - base_cli)),
        "sam_mm": round(sam / 1e6, 1),
        "sam_nuevo_mm": round((sam - base_sam) / 1e6, 1),
        "rescata_juliaca": int((huerf_jul & nuevo_ok).sum()),
    })

res = pd.DataFrame(filas).sort_values("clientes_nuevos", ascending=False)
cap_h3 = [h3.latlng_to_cell(la, lo, R_HUB)
          for la, lo in zip(cand["lat"], cand["lon"])]
h_madre = {}
for i, c in enumerate(cap_h3):
    q = idx_celda.get(c, -1)
    h_madre[str(cand.loc[i, "PROVINCIA"]).title()] = (
        float(T[sel_actual, q].min()) if q >= 0 else float("nan"))
res["h_a_la_red"] = res["candidato"].map(h_madre)
res.to_csv("out/diag_satelite.csv", index=False, encoding="utf-8-sig")
print("  %-18s %-10s %7s %10s %10s %10s"
      % ("candidato", "región", "puntos", "clientes", "de Juliaca", "h a la red"))
for _, r in res.head(6).iterrows():
    print("  %-18s %-10s %+7d %+10s %10d %10s"
          % (r.candidato[:18], r.region[:10], r.puntos_nuevos,
             f"{r.clientes_nuevos:,}", r.rescata_juliaca,
             "—" if not np.isfinite(r.h_a_la_red) else "%.1f" % r.h_a_la_red))

# ------------------------------------ cuántos harían falta para cerrarlo ---
# Cada satélite tiene que poder abastecerse de la red que existe cuando se
# abre —incluidos los satélites anteriores—, o no es un satélite.
print()
print("la cadena de satélites: cuántos harían falta", flush=True)
t_red = t_actual.copy()
en_red = list(sel_actual)
celda_cand = np.array([idx_celda.get(c, -1) for c in cap_h3])
curva = []
for paso in range(1, 9):
    mejor, mejor_v, mejor_ok = None, 0, None
    for i in range(len(cand)):
        if i in en_red or celda_cand[i] < 0:
            continue
        # ¿puede abastecerse? el candidato tiene que estar dentro de la
        # promesa de alguno de los centros ya abiertos
        if T[en_red, celda_cand[i]].min() > PROM_C[celda_cand[i]]:
            continue
        ok, cli, _ = gana(t_red, i)
        if cli > mejor_v:
            mejor, mejor_v, mejor_ok = i, cli, ok
    if mejor is None:
        print("  no queda ningún candidato que pueda abastecerse: la cadena "
              "se corta aquí")
        break
    _, _, t_red = gana(t_red, mejor)
    en_red.append(mejor)
    nom = str(cand.loc[mejor, "PROVINCIA"]).title()
    dentro = t_red <= PROM_P
    curva.append({"paso": paso, "centro": nom,
                  "region": str(cand.loc[mejor, "DEPARTAM"]).title(),
                  "puntos": int(dentro.sum()),
                  "clientes_cadena": int(round(mejor_v)),
                  "huerf_jul": int((huerf_jul & ~dentro).sum())})
    print("  %d. %-18s %-10s  %5d puntos en promesa · %s clientes · "
          "quedan %d huérfanos del sur"
          % (paso, nom[:18], str(cand.loc[mejor, "DEPARTAM"])[:10],
             dentro.sum(), f"{mejor_v:,.0f}", curva[-1]["huerf_jul"]))
    if curva[-1]["huerf_jul"] == 0:
        break

# ------------------------------------- el sur, obligando a que se resuelva -
# El greedy anterior es nacional y por eso nunca baja al sur: ocho satélites
# después, los huérfanos del altiplano siguen siendo los mismos. No es un
# defecto del algoritmo, es la respuesta —el sur no compite por plata— y hay
# que verla antes de decidir si se lo atiende igual.
#
# Esta segunda pasada cambia el objetivo: en vez de clientes nacionales,
# maximiza puntos rescatados del sur, y solo mira candidatos del sur. Dice el
# precio de cerrarlo, que es lo que se estaba preguntando.
SUR = {"PUNO", "CUSCO", "AREQUIPA", "MOQUEGUA", "TACNA", "APURIMAC"}
print()
print("obligando a cerrar el sur: solo candidatos del altiplano", flush=True)
t_sur = t_actual.copy()
en_sur = list(sel_actual)
for paso in range(1, 9):
    mejor, mejor_v, mejor_t = None, 0, None
    for i in range(len(cand)):
        if i in en_sur or celda_cand[i] < 0:
            continue
        if str(cand.loc[i, "DEPARTAM"]).upper() not in SUR:
            continue
        if T[en_sur, celda_cand[i]].min() > PROM_C[celda_cand[i]]:
            continue
        t = np.where(vivo, np.minimum(t_sur, T[i][pos.clip(min=0)]), np.inf)
        v = int((huerf_jul & (t <= PROM_P)).sum())
        if v > mejor_v:
            mejor, mejor_v, mejor_t = i, v, t
    if mejor is None:
        print("  no queda candidato del sur que pueda abastecerse: para "
              "cerrar lo que falta habría que abrir fuera de promesa, que ya "
              "no es un satélite")
        break
    t_sur = mejor_t
    en_sur.append(mejor)
    quedan = int((huerf_jul & (t_sur > PROM_P)).sum())
    print("  %d. %-18s %-10s rescata %3d · quedan %3d · cadena %s clientes"
          % (paso, str(cand.loc[mejor, "PROVINCIA"]).title()[:18],
             str(cand.loc[mejor, "DEPARTAM"])[:10], mejor_v, quedan,
             f"{clientes_cadena(t_sur <= PROM_P):,.0f}"))
    if quedan == 0:
        break

# --------------------------------------------- la otra salida: la cadencia -
print()
print("la alternativa: los mismos centros con otra promesa")
print("  %8s %9s %12s %14s" % ("promesa", "puntos", "% de puntos", "clientes cadena"))
cadencia = []
for h in (4.0, 5.0, 6.0, 8.0, 12.0):
    ok = np.where(vivo, t_actual, np.inf) <= h
    cadencia.append({"promesa_h": h, "puntos": int(ok.sum()),
                     "pct_puntos": round(100 * ok.sum() / vivo.sum(), 1),
                     "clientes_cadena": int(round(clientes_cadena(ok)))})
    print("  %6.0f h %9d %11.0f%% %14s"
          % (h, ok.sum(), 100 * ok.sum() / vivo.sum(),
             f"{clientes_cadena(ok):,.0f}"))

# ------------------------------------------------------- lo que se publica -
# La pregunta «¿conviene un noveno centro?» está abierta en el módulo de
# decisiones, y `build_decisiones.py` saca de aquí su marginal. Sin este
# archivo la decisión se publicaría con el hueco que queda —«35.6% sin
# cubrir»— y sin lo único que permite decidirla: cuánto compra el que sigue.
mejor = res.iloc[0] if len(res) else None
salida = {
    "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "motivo": ("qué compra un centro más sobre la red vigente, cuántos harían "
               "falta para cerrar el sur y qué pasaría con otra promesa; el "
               "candidato tiene que poder abastecerse de la red que ya existe "
               "o no es un satélite sino otro almacén"),
    "promesa": red["promesa_h"],
    "hoy": {
        "puntos_en_promesa": int(hoy.sum()),
        "puntos": int(vivo.sum()),
        "pct": round(100 * hoy.sum() / vivo.sum(), 1),
        "clientes_cadena": int(round(base_cli)),
        "sam_en_promesa_mm": round(float(base_sam) / 1e6, 1),
        "huerfanos_del_sur": int(huerf_jul.sum()),
    },
    "mejor_candidato": (None if mejor is None else {
        "centro": mejor.candidato, "region": mejor.region,
        "puntos_nuevos": int(mejor.puntos_nuevos),
        "clientes_nuevos": int(mejor.clientes_nuevos),
        "sam_nuevo_mm": float(mejor.sam_nuevo_mm),
        "rescata_del_sur": int(mejor.rescata_juliaca),
        "h_a_la_red": (None if not np.isfinite(mejor.h_a_la_red)
                       else round(float(mejor.h_a_la_red), 2)),
    }),
    "candidatos": [
        {k: (None if isinstance(v, float) and not np.isfinite(v)
             else (float(v) if isinstance(v, (float, np.floating))
                   else (int(v) if isinstance(v, (int, np.integer)) else v)))
         for k, v in r._asdict().items() if k != "Index"}
        for r in res.head(8).itertuples()],
    "cadena": curva,
    "cadencia": cadencia,
}
io.open("out/satelite.json", "w", encoding="utf-8").write(
    json.dumps(salida, ensure_ascii=False, indent=1))

print()
print("out/diag_satelite.csv · out/satelite.json")
