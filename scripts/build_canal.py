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
pro["clase"] = np.where(pro["tipo"].isin(TIPOS_PUNTO), "comercio", "")
osm = pro[pro["clase"] != ""][["dep", "nombre", "tipo", "clase", "lat", "lon"]]

# Los pueblos ya no salen de adivinar en OSM —de sus 873 «hamlets», 851 eran
# fundos con nombre— sino del padrón del INEI cruzado con OSM por
# `build_ccpp.py`: 94,922 centros poblados censados, de los que 24,591 tienen
# coordenada. Los que no la tienen no se inventan; quedan contados aparte.
#
# El piso de población es un filtro declarado y no una verdad: por debajo de
# 200 habitantes un punto de venta no tiene a quién venderle, y dejarlos entrar
# llenaba la lista de aperturas de caseríos de tres casas. Se puede mover.
POB_MIN = 200
ccpp = leer("out/ccpp.csv", dtype={"ubigeo": str})
con_xy = ccpp[ccpp.lat.notna() & (ccpp.poblacion >= POB_MIN)]
pueblos = pd.DataFrame({
    "dep": con_xy["distrito"], "nombre": con_xy["nombre"],
    "tipo": "ccpp:inei", "clase": "pueblo",
    "lat": con_xy["lat"], "lon": con_xy["lon"]})
print("centros poblados del INEI: %s censados, %s con coordenada, %s sobre "
      "%d habitantes" % (f"{len(ccpp):,}", f"{int(ccpp.lat.notna().sum()):,}",
                         f"{len(pueblos):,}", POB_MIN))

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

cand = pd.concat([padron, osm, pueblos], ignore_index=True)
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
#   lo que alcanza un comercio       lo que ya existe, sin hacer nada
#   lo que alcanza algún candidato   dónde se PUEDE llegar: incluye pueblos
#                                    del padrón donde no hay comercio todavía
#   lo que no alcanza ninguno        el hueco estructural: ni tienda ni pueblo
#                                    a 45 minutos, y ahí no hay qué abrir
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
print("  con algún sitio donde abrir      %s clientes (%.1f%%)"
      % (f"{CLI[en_todos].sum():,.0f}",
         100 * CLI[en_todos].sum() / CLI.sum()))
print("  sin nada: ni tienda ni pueblo    %s clientes (%.1f%%)"
      % (f"{CLI[sin_nadie].sum():,.0f}",
         100 * CLI[sin_nadie].sum() / CLI.sum()))
print("  —el segundo incluye pueblos donde todavía no hay comercio: es dónde")
print("   se PUEDE abrir, no dónde ya se vende—")

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

# ------------------------------------------------- quién resurte a quién ---
# La cadena tiene dos tramos y hasta aquí solo se medía el de abajo. El de
# arriba —del almacén a la tienda— sale de la asignación de centros, y en el
# sentido correcto: `horas_al_hub` se calculó del centro hacia la celda, que
# es el viaje del camión de reparto y no el del cliente.
#
# Importa porque una tienda a nueve horas de su almacén no está servida
# aunque tenga clientes al lado: la cadena vale lo que valga su tramo más
# débil, y contarla entera como cobertura es el error que este cruce evita.
R_HUB = 5
asg = leer("out/hubs_asignacion.csv", dtype={"h3": str}).set_index("h3")
cand["h3_hub"] = [h3.latlng_to_cell(a, b, R_HUB)
                  for a, b in zip(cand["lat"], cand["lon"])]
_j = asg.reindex(cand["h3_hub"])
cand["hub"] = _j["hub"].values
cand["horas_reparto"] = pd.to_numeric(_j["horas_al_hub"].values,
                                      errors="coerce")
cand.loc[~np.isfinite(cand["horas_reparto"]), "horas_reparto"] = np.nan
# La promesa dejó de ser un número único: son cuatro horas en costa y seis en
# sierra y selva, y cada celda trae la suya. Leerla de la celda y no de una
# constante es lo que hace que este archivo no tenga que saber la regla.
cand["promesa_h"] = pd.to_numeric(_j["promesa_h"].values, errors="coerce")
_red = json.load(io.open("out/red_elegida.json", encoding="utf-8"))
PROMESA = _red["promesa_def_h"]
cand["reparto_en_promesa"] = cand["horas_reparto"] <= cand["promesa_h"]

vende = cand.clase.isin(("canal", "comercio"))
print()
print("el tramo de arriba: del centro a la tienda")
print("  %d de %d puntos que ya venden tienen centro asignado"
      % (int(vende.sum() - cand.loc[vende, "hub"].isna().sum()),
         int(vende.sum())))
print("  dentro de su promesa —4 h en costa, 6 en sierra y selva—: %d (%.0f%%)"
      % (int(cand.loc[vende, "reparto_en_promesa"].sum()),
         100 * cand.loc[vende, "reparto_en_promesa"].mean()))

# La cobertura de verdad: clientes cuya tienda está, además, dentro de la
# promesa de su propio centro. Es la cadena completa y no una de sus mitades.
en_cadena = np.zeros(len(sec), dtype=bool)
for (idx, t), cl, ok_rep in zip(alcance, cand.clase, cand.reparto_en_promesa):
    if cl in ("canal", "comercio") and ok_rep:
        en_cadena[idx[t <= RADIO_BASE]] = True
print("  clientes con la cadena completa —tienda a %d min y su centro dentro "
      "de la promesa—: %s (%.1f%%)"
      % (int(RADIO_BASE * 60), f"{CLI[en_cadena].sum():,.0f}",
         100 * CLI[en_cadena].sum() / CLI.sum()))

# Los clientes de un centro son la UNION de los que alcanzan sus puntos, no la
# suma: dos tiendas de la misma calle llegan a la misma gente, y sumando sus
# alcances Pisco salia con 376,695 clientes en un pais que tiene 153,984.
_por_hub = {}
for j, (idx, t) in enumerate(alcance):
    if cand.clase.iat[j] not in ("canal", "comercio"):
        continue
    h = cand.hub.iat[j]
    if not isinstance(h, str):
        continue
    _por_hub.setdefault(h, np.zeros(len(sec), dtype=bool))
    _por_hub[h][idx[t <= RADIO_BASE]] = True

hub_res = (cand[vende].groupby("hub")
           .apply(lambda x: pd.Series({
               "puntos": len(x),
               "del_padron": int((x.clase == "canal").sum()),
               "en_promesa": int(x.reparto_en_promesa.sum()),
               "horas_mediana": float(x.horas_reparto.median())}),
                  include_groups=False)
           .reset_index().sort_values("puntos", ascending=False))
hub_res["clientes"] = [float(CLI[_por_hub[h]].sum()) if h in _por_hub else 0.0
                       for h in hub_res.hub]
hub_res["pct_en_promesa"] = 100 * hub_res.en_promesa / hub_res.puntos
hub_res.to_csv("out/canal_hub.csv", index=False, encoding="utf-8-sig")
print()
print("  %-12s %7s %8s %11s %9s %11s"
      % ("centro", "puntos", "padrón", "en promesa", "h mediana", "clientes"))
for _, r in hub_res.iterrows():
    print("  %-12s %7d %8d %9.0f%%  %9.1f %11s"
          % (r.hub, r.puntos, r.del_padron, r.pct_en_promesa,
             r.horas_mediana, f"{r.clientes:,.0f}"))

# --------------------------------------------- si el punto es un negocio ---
# Hasta aquí el canal estaba medido en clientes y no en plata, y con eso no se
# puede proponer nada: nadie toma una línea nueva porque tenga gente cerca,
# sino porque le deja algo.
#
# El reparto es la parte que hay que hacer bien. El alcance de dos tiendas de
# la misma calle es casi el mismo mercado, así que sumar los alcances cuenta a
# la misma gente varias veces —el mismo error que ya se corrigió al totalizar
# por centro—. Aquí cada sector va al punto que le queda más cerca en tiempo,
# y lo que se le atribuye a cada uno es su mercado **exclusivo**: la suma de
# todos vuelve a dar el total del país.
print()
print("lo que movería cada punto")
mejor_t = np.full(len(sec), np.inf)
mejor_j = np.full(len(sec), -1, dtype=int)
for j, (idx, t) in enumerate(alcance):
    if cand.clase.iat[j] not in ("canal", "comercio"):
        continue
    m = t <= RADIO_BASE
    ii, tt = idx[m], t[m]
    gana = tt < mejor_t[ii]
    mejor_t[ii[gana]] = tt[gana]
    mejor_j[ii[gana]] = j

cand["sam_exclusivo"] = 0.0
cand["clientes_exclusivos"] = 0.0
for j in np.unique(mejor_j[mejor_j >= 0]):
    m = mejor_j == j
    cand.iat[int(j), cand.columns.get_loc("sam_exclusivo")] = float(SAM[m].sum())
    cand.iat[int(j), cand.columns.get_loc("clientes_exclusivos")] = float(CLI[m].sum())

# La economía unitaria no se inventa aquí: sale de `build_som.py`, que la midió
# sobre el libro de ventas de la propia empresa —margen bruto del 21%— y de sus
# tres escenarios de penetración. Usar otros números haría que dos pantallas
# del mismo sitio dijeran cosas distintas del mismo negocio.
som = leer("out/som_escenarios.csv")
base = som[som.escenario == "Base"].iloc[0]
PEN = float(base.penetracion)
MARGEN = float(base.margen_usd) / float(base.ventas_usd)
cand["venta_base"] = cand["sam_exclusivo"] * PEN
cand["margen_base"] = cand["venta_base"] * MARGEN
print("  penetración base %.1f%% · margen bruto %.0f%% (de build_som.py)"
      % (100 * PEN, 100 * MARGEN))
print("  OJO: eso es lo que capturaría AGROJUNTOS a través del punto, no lo")
print("  que vende la tienda. La tienda ya le vende a esos agricultores; la")
print("  penetración del 1.5% es la del proyecto sobre el mercado, no la")
print("  participación del comerciante.")

vende_i = cand.index[vende]
con_mercado = cand.loc[vende_i, "sam_exclusivo"] > 0
print("  %d de %d puntos tienen mercado exclusivo; los demás quedan dentro "
      "del radio de otro más cercano" % (int(con_mercado.sum()), len(vende_i)))
print("  el mercado exclusivo suma US$ %.1f MM de los %.1f MM del país"
      % (cand.loc[vende_i, "sam_exclusivo"].sum() / 1e6, SAM.sum() / 1e6))

# El piso de viabilidad es una decisión comercial y no un dato: no se fija
# aquí. Se publica la curva para que quien decida vea el precio de cada vara.
PISOS = [2500, 5000, 10000, 25000, 50000]
curva_piso = []
print()
print("  %-14s %8s %12s" % ("margen/año", "puntos", "clientes"))
for u in PISOS:
    m = cand.loc[vende_i, "margen_base"] >= u
    curva_piso.append({"margen_min": u, "puntos": int(m.sum()),
                       "clientes": int(round(
                           cand.loc[vende_i, "clientes_exclusivos"][m].sum()))})
    print("  US$ %-10s %8d %12s"
          % ("{:,}".format(u), m.sum(),
             "{:,.0f}".format(cand.loc[vende_i, "clientes_exclusivos"][m].sum())))

top_v = (cand.loc[vende_i].sort_values("margen_base", ascending=False).head(12))
print()
print("  los doce de mayor margen")
print("  %-34s %-9s %10s %10s" % ("punto", "clase", "clientes", "margen/año"))
for _, r in top_v.iterrows():
    print("  %-34s %-9s %10s %10s"
          % (str(r["nombre"])[:34], r["clase"],
             "{:,.0f}".format(r["clientes_exclusivos"]),
             "US$ {:,.0f}".format(r["margen_base"])))

# --------------------------------------------------------------- salida ----
cand["elegido"] = [j in sel for j in range(len(cand))]
cols = ["dep", "nombre", "tipo", "clase", "lat", "lon", "sectores_1h",
        "hub", "horas_reparto", "reparto_en_promesa", "sam_exclusivo",
        "clientes_exclusivos", "venta_base", "margen_base", "elegido"] + [c for c in cand.columns
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
    "promesa_centros_def_h": red["promesa_def_h"],
    "clientes": int(round(CLI.sum())),
    "candidatos": {c: int((cand.clase == c).sum())
                   for c in ("canal", "comercio", "pueblo")},
    "cobertura_actual": actual,
    "apertura": curva,
    "con_sitio": {
        "motivo": ("clientes con algun candidato a 45 min, incluidos los "
                   "pueblos del padron del INEI donde todavia no hay comercio"),
        "clientes": int(round(CLI[en_todos].sum())),
        "pct": round(100 * CLI[en_todos].sum() / CLI.sum(), 1)},
    "con_canal": {
        "motivo": "clientes con un comercio ya existente a 45 min",
        "clientes": int(round(sum(actual[i]["clientes"] for i in [1]))),
        "pct": actual[1]["pct"]},
    "sin_candidato": {
        "motivo": "ni comercio ni pueblo del padron a 45 min: ahi no hay que abrir sino llegar de otra forma",
        "clientes": int(round(CLI[sin_nadie].sum())),
        "pct": round(100 * CLI[sin_nadie].sum() / CLI.sum(), 1)},
    "cadena_completa": {
        "motivo": ("clientes con tienda a %d min cuya tienda esta ademas "
                   "dentro de la promesa de su centro, que son 4 h en costa "
                   "y 6 en sierra y selva" % int(RADIO_BASE * 60)),
        "clientes": int(round(CLI[en_cadena].sum())),
        "pct": round(100 * CLI[en_cadena].sum() / CLI.sum(), 1)},
    "viabilidad": {
        "motivo": ("mercado exclusivo de cada punto —cada sector va al punto "
                   "mas cercano, no se cuenta dos veces— llevado a venta y "
                   "margen con la economia unitaria de build_som.py"),
        "salvedad": ("el margen es lo que capturaria AgroJuntos a traves del "
                     "punto en el escenario base, no lo que vende la tienda: "
                     "la penetracion del 1.5% es la del proyecto sobre el "
                     "mercado y no la participacion del comerciante"),
        "puntos_con_mercado": int(con_mercado.sum()),
        "puntos_que_venden": int(len(vende_i)),
        "sam_exclusivo_mm": round(float(
            cand.loc[vende_i, "sam_exclusivo"].sum()) / 1e6, 1),
        "escenarios": [{"e": str(r.escenario),
                        "pen": round(float(r.penetracion), 4),
                        "margen_mayor": round(float(
                            cand.loc[vende_i, "sam_exclusivo"].max()
                            * float(r.penetracion) * MARGEN), 0)}
                       for _, r in som.iterrows()],
        "penetracion": round(PEN, 4),
        "margen_bruto": round(MARGEN, 4),
        "curva": curva_piso,
        "top": [{"nombre": str(r["nombre"])[:60], "dep": str(r["dep"]),
                 "clase": r["clase"], "hub": (r["hub"] if isinstance(r["hub"], str)
                                              else ""),
                 "clientes": int(round(r["clientes_exclusivos"])),
                 "sam": round(float(r["sam_exclusivo"]), 2),
                 "margen": round(float(r["margen_base"]), 2)}
                for _, r in top_v.iterrows()],
    },
    "reparto": [{"hub": r.hub, "puntos": int(r.puntos),
                 "del_padron": int(r.del_padron),
                 "en_promesa": int(r.en_promesa),
                 "pct_en_promesa": round(float(r.pct_en_promesa), 1),
                 "horas_mediana": round(float(r.horas_mediana), 2),
                 "clientes": int(round(r.clientes))}
                for _, r in hub_res.iterrows()],
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
