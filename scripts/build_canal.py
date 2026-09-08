# -*- coding: utf-8 -*-
"""La red de canal: quién le vende al cliente que el almacén no alcanza.

La red de centros contesta dónde poner inventario. No contesta quién le vende
al agricultor: en Sánchez Carrión y Pataz —el mayor territorio del país— hay
9,114 clientes y 133 empresas formales, así que un almacén propio, aunque esté
en Huamachuco, atiende al 1.5% de ese mercado y el resto no se toca sin un
punto de venta local.

Esto arma esa capa. No inventa la red: **el canal ya existe** y lo que hace
falta es saber a cuántos clientes alcanza, cuáles quedan fuera y dónde haría
falta abrir. Por eso los candidatos son de tres clases y se declaran distintas,
porque cuestan cosas distintas y el informe no puede presentarlas como si
fueran la misma decisión:

  canal      empresa del padrón con RUC y clase «canal»: distribuidor o
             minorista de insumos ya constituido. Captarlo es un acuerdo
             comercial con alguien que ya vende esto.
  comercio   ferretería, agroveterinaria o tienda agrícola mapeada en
             OpenStreetMap. Existe, vende cosas afines, y habría que
             convencerla de tomar la línea.
  pueblo     centro poblado sin comercio conocido. Llegar ahí es abrir algo.

## Dos límites del dato, dichos antes de leer ninguna cifra

**La ubicación del padrón es el distrito, no la esquina.** SUNAT publica el
domicilio fiscal y este proyecto lo lleva al centroide agrícola del distrito,
así que un candidato de clase «canal» está bien puesto a escala de distrito y
mal puesto a escala de cuadra. Para un radio de 45 minutos alcanza; para
decidir un local, no.

**Que OSM no mapee una tienda no significa que no exista.** La cobertura de
OpenStreetMap en la sierra rural es pobre, y por eso la cifra de clientes «sin
comercio cerca» es un techo y no una medición: dice cuánto no se puede
demostrar que esté cubierto, que no es lo mismo que estar descubierto. La capa
del padrón, que no depende de OSM, existe justamente para acotar eso.

## El radio

No es el del almacén. Al almacén va un camión; a la tienda va el agricultor,
en moto o a pie, y una hora de camino es mucho. Se miden tres radios —30, 45 y
60 minutos— sobre la red vial **con pendiente**, y en el sentido correcto: del
sector a la tienda, que es el viaje que hace el cliente, y no al revés.

## Por qué un Dijkstra acotado

Son unos tres mil candidatos contra siete mil sectores. La matriz completa no
hace falta: a nadie le sirve saber que una tienda está a nueve horas. Con
`limit` el recorrido se corta en el radio máximo y cada candidato cuesta
milisegundos en vez de segundos.

Uso:
    python scripts/build_canal.py
"""
import io
import json
import os
import sys
import time

import h3
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                            # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

# Lo que puede vender un insumo agrícola. La ferretería de pueblo vende
# alambre, herramienta y agroquímico en el mismo mostrador; la agroveterinaria
# vende sanidad animal y fertilizante. Quedan fuera las capas que no son
# comercio —industria, obras, chacras— porque no atienden a nadie.
TIPOS_PUNTO = {"hardware", "veterinary", "trade", "doityourself", "agrarian",
               "garden_centre", "plant_nursery", "pet", "agricultural_engines",
               "yes"}
TIPOS_PUEBLO = {"hamlet", "village", "neighbourhood", "locality", "quarter"}

# OSM etiqueta como «hamlet» muchas cosas que no son pueblos: un fundo, una
# hacienda, una parcela con nombre. Un fundo no es un sitio donde abrir una
# tienda —es un cliente, no un canal— y colarlo entre los candidatos hacía que
# la lista de aperturas propusiera vender en la chacra de al lado.
NO_ES_PUEBLO = ("fundo", "hacienda", "chacra", "granja", "predio", "parcela",
                "establo", "criadero", "planta", "molino")

RADIOS = [0.5, 0.75, 1.0]        # horas de camino del cliente a la tienda
RADIO_BASE = 0.75                # con cuál se ordena la apertura
K_MAX = 40                       # puntos a evaluar en la curva
R_TER = 6                        # la resolucion H3 con que se trazo el territorio
LIMITE = 1.05                    # hasta dónde explora el Dijkstra acotado


def leer(p, **kw):
    return pd.read_csv(p, encoding="utf-8-sig", **kw)


print("armando el grafo vial...", flush=True)
g = grafo_vial.construir()

# ------------------------------------------------------------- la demanda --
sec = leer("out/ruteo_sector.csv")
sec = sec[np.isfinite(sec["horas_capital_real"])].copy()
sec_idx = g.snap(sec.lon.values, sec.lat.values)
CLI = sec["s_clientes_sam"].values
SAM = sec["s_sam_usd"].values
print("demanda: %s clientes en %s sectores · US$ %.0f MM"
      % (f"{CLI.sum():,.0f}", f"{len(sec):,}", SAM.sum() / 1e6))

# ------------------------------------------------------------ candidatos ---
pro = leer("out/osm_prospectos.csv")
pro = pro[pro["lat"].notna() & pro["lon"].notna()].copy()
_nom = pro["nombre"].fillna("").str.lower()
_es_fundo = _nom.str.startswith(NO_ES_PUEBLO)
pro["clase"] = np.where(pro["tipo"].isin(TIPOS_PUNTO), "comercio",
                        np.where(pro["tipo"].isin(TIPOS_PUEBLO) & ~_es_fundo,
                                 "pueblo", ""))
osm = pro[pro["clase"] != ""][["dep", "nombre", "tipo", "clase", "lat", "lon"]]

# El canal formal: empresas del padrón cuya clase es «canal». Se ubican en el
# centroide agrícola de su distrito, que es lo que hay —ver la salvedad de la
# cabecera—.
emp = leer("out/empresas_agro_activas.csv", dtype={"ruc": str, "ubigeo": str})
emp = emp[(emp["clase"] == "canal") & emp["distrito"].notna()].copy()
_sec = leer("out/ruteo_sector.csv")


def _clave(d, *cols):
    j = d[list(cols)].astype(str).agg("|".join, axis=1)
    return j.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode(
        "ascii").str.upper()


_xy = (_sec.groupby(_clave(_sec, "dep", "prov", "dist"))
       .agg(lat=("lat", "mean"), lon=("lon", "mean")))
_j = _xy.reindex(_clave(emp, "dep", "provincia", "distrito"))
emp["lat"], emp["lon"] = _j["lat"].values, _j["lon"].values
emp = emp[emp["lat"].notna()]
padron = pd.DataFrame({"dep": emp["dep"], "nombre": emp["razon_social"],
                       "tipo": "padron:canal", "clase": "canal",
                       "lat": emp["lat"], "lon": emp["lon"]})

cand = pd.concat([padron, osm], ignore_index=True)
cand_idx = g.snap(cand.lon.values, cand.lat.values)
print("candidatos: %d del padrón, %d comercios de OSM y %d centros poblados"
      % (int((cand.clase == "canal").sum()),
         int((cand.clase == "comercio").sum()),
         int((cand.clase == "pueblo").sum())))

# ------------------------------------------- alcance de cada candidato -----
# El sentido importa: se rutea sobre el grafo traspuesto, de modo que lo que
# se mide es cuánto tarda el CLIENTE en llegar a la tienda. Con pendiente, ir
# y volver no cuestan lo mismo, y el que sube la cuesta es él.
print("midiendo el alcance de cada candidato...", flush=True)
G = g.csr(hacia=True)
t0 = time.time()
alcance = []                       # por candidato: (idx de sectores, horas)
for i, src in enumerate(cand_idx):
    d = dijkstra(G, indices=int(src), directed=True, limit=LIMITE)
    t = d[sec_idx]
    m = np.isfinite(t) & (t <= max(RADIOS))
    alcance.append((np.flatnonzero(m), t[m]))
    if (i + 1) % 500 == 0:
        print("  %d/%d · %.0f s" % (i + 1, len(cand), time.time() - t0),
              flush=True)

cand["sectores_1h"] = [len(a[0]) for a in alcance]
for r in RADIOS:
    cand["clientes_%d" % int(r * 60)] = [
        float(CLI[a[0][a[1] <= r]].sum()) for a in alcance]
    cand["sam_%d" % int(r * 60)] = [
        float(SAM[a[0][a[1] <= r]].sum()) for a in alcance]

col_cli = "clientes_%d" % int(RADIO_BASE * 60)
print("  %.0f s · el candidato de mayor alcance llega a %s clientes"
      % (time.time() - t0, f"{cand[col_cli].max():,.0f}"))

# ----------------------------------------------------- cuánto cubre el todo -
print()
print("lo que alcanza el canal que YA existe (padrón + comercios)")
actual = []
for r in RADIOS:
    en = np.zeros(len(sec), dtype=bool)
    for (idx, t), cl in zip(alcance, cand.clase):
        if cl in ("canal", "comercio"):
            en[idx[t <= r]] = True
    actual.append({"min": int(r * 60), "clientes": int(round(CLI[en].sum())),
                   "pct": round(100 * CLI[en].sum() / CLI.sum(), 1),
                   "sam_mm": round(SAM[en].sum() / 1e6, 1)})
    print("  a %2d min de un comercio: %s clientes (%.1f%%) · US$ %.0f MM"
          % (int(r * 60), f"{CLI[en].sum():,.0f}",
             100 * CLI[en].sum() / CLI.sum(), SAM[en].sum() / 1e6))

# --------------------------------------------------- orden de apertura -----
# Cobertura máxima otra vez, pero sobre clientes y no sobre mercado: el canal
# se justifica por cuánta gente alcanza, no por cuántos dólares hay cerca. Un
# punto que cubre mucho dinero y pocos clientes ya lo sirve el almacén.
print()
print("orden de apertura, con radio de %d minutos" % int(RADIO_BASE * 60))
dentro = [a[0][a[1] <= RADIO_BASE] for a in alcance]
cubierto = np.zeros(len(sec), dtype=bool)
sel, curva = [], []
for k in range(K_MAX):
    mejor, mejor_v = None, 0.0
    for j in range(len(cand)):
        if j in sel:
            continue
        v = CLI[dentro[j][~cubierto[dentro[j]]]].sum()
        if v > mejor_v:
            mejor, mejor_v = j, v
    if mejor is None:
        break
    sel.append(mejor)
    cubierto[dentro[mejor]] = True
    r = cand.loc[mejor]
    curva.append({
        "k": k + 1, "nombre": str(r["nombre"])[:60], "clase": r["clase"],
        "tipo": str(r["tipo"]), "dep": str(r["dep"]),
        "lat": round(float(r["lat"]), 5), "lon": round(float(r["lon"]), 5),
        "clientes_nuevos": int(round(mejor_v)),
        "clientes_acum": int(round(CLI[cubierto].sum())),
        "pct_acum": round(100 * CLI[cubierto].sum() / CLI.sum(), 2),
    })
    if k < 12:
        print("  %2d. %-34s %-7s %-12s +%6s clientes  %5.1f%%"
              % (k + 1, str(r["nombre"])[:34], r["clase"], str(r["dep"])[:12],
                 f"{mejor_v:,.0f}", curva[-1]["pct_acum"]))

# ------------------------------------------------- el hueco que queda ------
# Tres cifras distintas que es fácil confundir, y confundirlas cambia la
# conclusión:
#
#   lo que cubren los 40 elegidos    la lista de prioridad
#   lo que cubre el canal entero     lo que ya existe, sin hacer nada
#   lo que no cubre NINGÚN candidato el hueco estructural: ahí no hay a quién
#                                    captar y hay que abrir o no llegar
en_todos = np.zeros(len(sec), dtype=bool)
for idx in dentro:
    en_todos[idx] = True
sin_nadie = ~en_todos
fuera = ~cubierto
print()
print("las tres cifras que no son la misma")
print("  los %d puntos elegidos cubren      %s clientes (%.1f%%)"
      % (len(sel), f"{CLI[cubierto].sum():,.0f}",
         100 * CLI[cubierto].sum() / CLI.sum()))
print("  el canal entero (%d candidatos)   %s clientes (%.1f%%)"
      % (len(cand), f"{CLI[en_todos].sum():,.0f}",
         100 * CLI[en_todos].sum() / CLI.sum()))
print("  sin ningún candidato a %d min     %s clientes (%.1f%%)  <- hay que abrir"
      % (int(RADIO_BASE * 60), f"{CLI[sin_nadie].sum():,.0f}",
         100 * CLI[sin_nadie].sum() / CLI.sum()))

# ------------------------------------------------ por territorio de venta --
# El territorio se asigna por celda H3 y no por el `cluster` que trae
# `clusters_sector.csv`: ese campo es de otra corrida y tiene ocho valores,
# con 6,455 de los 6,892 sectores en el mismo. Cruzado por ahí, este corte
# daba 150,831 clientes al mayor territorio —el país entero— y cero a los
# demás. La verdad vive en `clusters_celda.csv`, que es lo que usa el resto
# del pipeline.
ter = leer("out/clusters_territorio.csv")
cel = leer("out/clusters_celda.csv", dtype={"h3": str})
sec["h3"] = [h3.latlng_to_cell(a, b, R_TER)
             for a, b in zip(sec["lat"], sec["lon"])]
sec = sec.merge(cel[["h3", "cluster"]], on="h3", how="left")
sec["cluster"] = sec["cluster"].fillna(-1).astype(int)
sec["cubierto"] = cubierto
sec["con_canal"] = en_todos
sec["cli"] = CLI
sec["sam"] = SAM
por_ter = (sec[sec.cluster >= 0].groupby("cluster")
           .apply(lambda x: pd.Series({
               "clientes": x.cli.sum(),
               "con_canal": x.loc[x.con_canal, "cli"].sum(),
               "clientes_cubiertos": x.loc[x.cubierto, "cli"].sum(),
               "sam": x.sam.sum()}), include_groups=False)
           .reset_index())
# Solo los que son territorio de venta: la grilla tiene celdas con cluster que
# no llegaron a ser uno de los 57 —el trazado descarta los que no juntan
# mercado suficiente— y arrastrarlos aqui inventaba territorios sin nombre.
por_ter = por_ter.merge(ter[["cluster", "dep", "provincias", "rank"]],
                        on="cluster", how="inner").sort_values("rank")
por_ter["pct"] = 100 * por_ter.con_canal / por_ter.clientes
por_ter["pct_elegidos"] = (100 * por_ter.clientes_cubiertos
                           / por_ter.clientes)
por_ter.to_csv("out/canal_territorio.csv", index=False, encoding="utf-8-sig")

print()
print("los cinco territorios de mayor mercado")
print("  %-32s %9s %9s %7s" % ("territorio", "clientes", "con canal", "%"))
for _, r in por_ter.head(6).iterrows():
    print("  %-32s %9s %9s %6.1f%%"
          % (("%s · %s" % (r.dep, r.provincias))[:32],
             f"{r.clientes:,.0f}", f"{r.con_canal:,.0f}", r.pct))

# --------------------------------------------------------------- salida ----
cand["elegido"] = [j in sel for j in range(len(cand))]
cols = ["dep", "nombre", "tipo", "clase", "lat", "lon", "sectores_1h",
        "elegido"] + [c for c in cand.columns
                      if c.startswith(("clientes_", "sam_"))]
cand[cols].to_csv("out/canal_punto.csv", index=False, encoding="utf-8-sig")

red = json.load(io.open("out/red_elegida.json", encoding="utf-8"))
salida = {
    "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "motivo": ("la red de centros dice dónde poner inventario; esta dice "
               "quién le vende al agricultor que no es empresa formal"),
    "radios_min": [int(r * 60) for r in RADIOS],
    "radio_base_min": int(RADIO_BASE * 60),
    "promesa_centros_h": red["promesa_h"],
    "clientes": int(round(CLI.sum())),
    "candidatos": {c: int((cand.clase == c).sum())
                   for c in ("canal", "comercio", "pueblo")},
    "cobertura_actual": actual,
    "apertura": curva,
    "con_canal": {"clientes": int(round(CLI[en_todos].sum())),
                  "pct": round(100 * CLI[en_todos].sum() / CLI.sum(), 1)},
    "sin_candidato": {"clientes": int(round(CLI[sin_nadie].sum())),
                      "pct": round(100 * CLI[sin_nadie].sum() / CLI.sum(), 1)},
    "territorios": [{"cluster": int(r.cluster), "dep": r.dep,
                     "provincias": r.provincias, "rank": int(r["rank"]),
                     "clientes": int(round(r.clientes)),
                     "con_canal": int(round(r.con_canal)),
                     "cubiertos": int(round(r.clientes_cubiertos)),
                     "pct": round(float(r.pct), 1)}
                    for _, r in por_ter.iterrows()],
}
io.open("out/canal.json", "w", encoding="utf-8").write(
    json.dumps(salida, ensure_ascii=False, indent=1))
print()
print("out/canal.json · out/canal_punto.csv · out/canal_territorio.csv")
