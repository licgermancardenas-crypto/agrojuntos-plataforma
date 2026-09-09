# -*- coding: utf-8 -*-
"""Identifica los núcleos agrícolas densos y los convierte en territorios.

Un vendedor no cubre una región: cubre una zona donde los clientes están lo
bastante juntos como para visitar varios en un día. El departamento es una
división política y no dice nada de eso.

Dos decisiones de método, ambas aprendidas de intentos que fallaron:

  se agrupa sobre celdas H3, no sobre sectores. Los sectores miden entre 200 y
  30,000 hectáreas, de modo que su densidad espacial refleja el tamaño de la
  unidad de medida antes que el mercado. La celda H3 tiene área constante.

  se agrupa solo el 80% superior del mercado. La agricultura peruana es
  continua a lo largo de los valles y de la franja costera, así que DBSCAN
  sobre el total encadena el país entero en un único núcleo de 2,000 km. Al
  quedarse con las celdas de mayor valor, las zonas ralas quedan fuera por
  construcción, que es además la respuesta honesta: no sostienen un territorio.

DBSCAN y no k-means porque el número de núcleos no se conoce de antemano y
porque hace falta poder marcar celdas como dispersas; en k-means toda celda
pertenece a algún grupo, lo que inventaría territorios donde no los hay.

## Lo que el agrupamiento deja fuera, y lo que se recupera después

El corte del 80% y el ruido de DBSCAN dejaban **73,298 clientes —el 48% del
país— sin territorio**, y eso no es lo mismo que decir que no se pueden
atender: una celda rala pegada a un territorio denso la visita el mismo
vendedor en el mismo viaje. Lo que no se puede es estirar el territorio sin
mirar, porque un territorio existe para recorrerse en el día.

Así que después de agrupar hay un segundo paso con una regla sola: **una celda
huérfana entra al territorio que la alcance por carretera, mientras el
territorio siga midiendo menos de 120 km de punta a punta.** Se aceptan de la
más cercana a la más lejana y se para donde la caja se rompe; el tope de horas
solo evita pegar celdas absurdamente lejanas a territorios de caja chica.

La alternativa —una vara fija de horas para todos— se midió y es peor:
`diag_territorios.py` muestra que una vara de dos horas recupera los mismos
clientes y deja 34 de 57 territorios sin poder recorrerse en el día, contra
los 48 de hoy. Aceptar mientras quepa recupera **24,971 clientes y US$ 75.6 MM
sin que ningún territorio deje de ser visitable**, que es el criterio que el
propio diseño usa.

Los ~48,000 clientes que siguen fuera lo están porque meterlos rompería el
territorio que los recibe. Ese es el argumento de la capa de canal —alguien más
les vende— y no el de un territorio más grande.
"""
import io
import json
import os
import sys

import numpy as np
import pandas as pd
from pyproj import Geod
from scipy.sparse.csgraph import dijkstra
from sklearn.cluster import DBSCAN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                      # noqa: E402

GEOD = Geod(ellps="WGS84")
TIERRA_KM = 6371.0
COBERTURA = 0.80         # porción del SAM que entra al agrupamiento
EPS_KM = 15.0            # radio de vecindad
MIN_CELDAS = 5           # celdas mínimas para constituir núcleo
MIN_SAM = 500_000        # US$ anuales para llamarlo territorio
VISITABLE_KM = 120.0     # de punta a punta, lo que se recorre en una salida
ABSORBE_H = 4.0          # tope de viaje para siquiera considerar una celda

h = pd.read_csv("out/h3_r6.csv", encoding="utf-8-sig")
h = h[h["sam_usd"] > 0].sort_values("sam_usd", ascending=False)
h = h.reset_index(drop=True)
SAM_TOTAL = h["sam_usd"].sum()
h["acum"] = h["sam_usd"].cumsum() / SAM_TOTAL

nucleo = h[h["acum"] <= COBERTURA].copy()
disperso = h[h["acum"] > COBERTURA].copy()

X = np.radians(nucleo[["centro_lat", "centro_lon"]].values)
nucleo["cluster"] = DBSCAN(eps=EPS_KM / TIERRA_KM, min_samples=MIN_CELDAS,
                           metric="haversine",
                           algorithm="ball_tree").fit_predict(X)

val = nucleo[nucleo["cluster"] >= 0]


def agregar(cel):
    """La ficha de cada territorio a partir de sus celdas."""
    return (cel.groupby("cluster")
            .agg(celdas=("h3", "size"),
                 sam_usd=("sam_usd", "sum"),
                 clientes=("clientes", "sum"),
                 ha_agricola=("ha_agricola", "sum"),
                 empresas=("empresas", "sum"),
                 exportadores=("exportadores", "sum"),
                 prospectos=("prospectos", "sum"),
                 lat=("centro_lat", "mean"), lon=("centro_lon", "mean"),
                 horas_capital=("horas_capital", "mean"),
                 dep=("dep", lambda s: s.mode().iat[0]),
                 provincias=("prov", lambda s: ", ".join(
                     s.value_counts().head(2).index.str.title())))
            .reset_index())


g = agregar(val)


def diagonal_km(lat, lon):
    """La extensión del territorio: la diagonal del rectángulo que lo envuelve."""
    if len(lat) < 2:
        return 0.0
    _, _, d = GEOD.inv([np.min(lon)], [np.min(lat)],
                       [np.max(lon)], [np.max(lat)])
    return float(d[0]) / 1000


# Extensión: la diagonal del rectángulo que envuelve al núcleo.
g["extension_km"] = [
    diagonal_km(val.loc[val["cluster"] == c, "centro_lat"].values,
                val.loc[val["cluster"] == c, "centro_lon"].values)
    for c in g["cluster"]]
g["sam_por_cliente"] = g["sam_usd"] / g["clientes"].replace(0, np.nan)

g = g[g["sam_usd"] >= MIN_SAM].sort_values("sam_usd", ascending=False)
g = g.reset_index(drop=True)

# --------------------------------- lo que cabe sin romper el territorio ---
# Ya están los territorios; falta repartir lo que quedó fuera. Se acepta de la
# celda más cercana a la más lejana y se para donde la caja de 120 km se
# rompe, que es el criterio con el que este mismo archivo decide si un
# territorio se recorre en el día. La alternativa —una vara fija de horas—
# está medida en `diag_territorios.py` y sale peor: recupera los mismos
# clientes y deja 34 de 57 territorios sin poder recorrerse.
# Los núcleos que no llegaron al medio millón dejan de ser territorio, así que
# sus celdas vuelven al montón de huérfanas y compiten por entrar a uno que sí.
val = val[val["cluster"].isin(set(g["cluster"]))]
huerf = h[~h["h3"].isin(set(val["h3"]))].reset_index(drop=True)
print("ruteando %s celdas huérfanas desde %d territorios..."
      % (f"{len(huerf):,}", len(g)), flush=True)
gr = grafo_vial.construir()
G = gr.csr()
i_ter = gr.arbol.query(np.column_stack([g.lon.values, g.lat.values]))[1]
i_hue = gr.arbol.query(np.column_stack([huerf.centro_lon.values,
                                        huerf.centro_lat.values]))[1]
T = np.full((len(g), len(huerf)), np.inf)
for i, src in enumerate(i_ter):
    T[i] = dijkstra(G, indices=int(src), directed=True)[i_hue]
cual = np.argmin(T, axis=0)
horas = T[cual, np.arange(len(huerf))]
del T, G, gr

caja = {c: [list(val.loc[val["cluster"] == c, "centro_lat"].values),
            list(val.loc[val["cluster"] == c, "centro_lon"].values)]
        for c in g["cluster"]}
asignada = np.full(len(huerf), -1)
for i in np.argsort(horas):
    if not np.isfinite(horas[i]) or horas[i] > ABSORBE_H:
        break
    c = int(g["cluster"].iat[int(cual[i])])
    la = caja[c][0] + [huerf.centro_lat.iat[i]]
    lo = caja[c][1] + [huerf.centro_lon.iat[i]]
    if diagonal_km(la, lo) <= VISITABLE_KM:
        caja[c] = [la, lo]
        asignada[i] = c

n_abs = int((asignada >= 0).sum())
sumadas = huerf[asignada >= 0].copy()
c_abs = float(sumadas["clientes"].sum())
s_abs = float(sumadas["sam_usd"].sum())
sumadas["cluster"] = asignada[asignada >= 0]
sumadas["horas_al_territorio"] = horas[asignada >= 0]
val = pd.concat([val.assign(horas_al_territorio=0.0), sumadas],
                ignore_index=True)
g = agregar(val)
g["extension_km"] = [diagonal_km(caja[c][0], caja[c][1]) for c in g["cluster"]]
g["sam_por_cliente"] = g["sam_usd"] / g["clientes"].replace(0, np.nan)
g = g.sort_values("sam_usd", ascending=False).reset_index(drop=True)
g["rank"] = g.index + 1
g["pct_sam"] = 100 * g["sam_usd"] / SAM_TOTAL
g["pct_acum"] = g["pct_sam"].cumsum()

# Un territorio se recorre en el día si mide menos de ~120 km de punta a punta.
g["visitable_en_dia"] = g["extension_km"] <= 120

g.to_csv("out/clusters_territorio.csv", index=False, encoding="utf-8-sig")
# `val` y no `nucleo`: lleva las celdas absorbidas, que son las que el resto
# del proyecto tiene que ver como parte de su territorio. Se conservan también
# las que quedaron fuera, con cluster -1, para que quien las busque las
# encuentre marcadas y no ausentes.
salida = pd.concat([
    val[["h3", "dep", "prov", "centro_lat", "centro_lon", "sam_usd",
         "clientes", "cluster", "horas_al_territorio"]],
    huerf.loc[asignada < 0, ["h3", "dep", "prov", "centro_lat", "centro_lon",
                             "sam_usd", "clientes"]]
         .assign(cluster=-1, horas_al_territorio=np.nan),
], ignore_index=True).drop_duplicates("h3")
salida.to_csv("out/clusters_celda.csv", index=False, encoding="utf-8-sig")

# La absorción es una decisión con regla, y la documentación repite sus cifras.
# Van a un archivo para que `verificar_datos.py` las contraste contra el texto
# en vez de contra una constante escrita a mano, que es una prueba que no
# prueba nada.
_vis = int((g["extension_km"] <= VISITABLE_KM).sum())
io.open("out/clusters_absorcion.json", "w", encoding="utf-8").write(
    json.dumps({
        "regla": ("una celda huerfana entra al territorio que la alcance por "
                  "carretera mientras el territorio siga midiendo menos de "
                  "%.0f km de punta a punta" % VISITABLE_KM),
        "tope_horas": ABSORBE_H,
        "visitable_km": VISITABLE_KM,
        "celdas": n_abs,
        "clientes": round(c_abs, 2),
        "sam_usd": round(s_abs, 2),
        "territorios": int(len(g)),
        "visitables": _vis,
        "pct_clientes_en_territorio": round(
            100 * float(g.clientes.sum() / h.clientes.sum()), 1),
        "pct_sam_en_territorio": round(float(g.pct_sam.sum()), 1),
        "clientes_sin_territorio": round(
            float(h.clientes.sum() - g.clientes.sum()), 2),
    }, ensure_ascii=False, indent=1))

ruido = int((nucleo["cluster"] < 0).sum())
print("=" * 84)
print(f"NUCLEOS AGRICOLAS  ·  DBSCAN sobre celdas H3, radio {EPS_KM:.0f} km")
print("=" * 84)
print(f"celdas con mercado    : {len(h):,}")
print(f"celdas agrupadas      : {len(nucleo):,} (el {COBERTURA:.0%} superior del SAM)")
print(f"nucleos detectados    : {nucleo['cluster'].max() + 1}  "
      f"({len(g)} superan US$ {MIN_SAM/1000:.0f} mil)")
print(f"celdas dispersas      : {ruido:,} dentro del corte, mas "
      f"{len(disperso):,} debajo")
print(f"absorbidas despues    : {n_abs:,} celdas, {c_abs:,.0f} clientes y "
      f"US$ {s_abs/1e6:,.1f} MM (tope {ABSORBE_H:.0f} h, sin pasar de "
      f"{VISITABLE_KM:.0f} km)")
print(f"mercado en territorios: {g.pct_sam.sum():.0f}% del SAM · "
      f"{g.clientes.sum()/h.clientes.sum():.0%} de los clientes")
print()
print("--- LOS 15 TERRITORIOS MAS VALIOSOS ---")
v = g.head(15)[["rank", "dep", "provincias", "celdas", "clientes", "sam_usd",
                "extension_km", "pct_acum"]].copy()
v["sam_usd"] = (v["sam_usd"] / 1e6).round(1)
v.columns = ["#", "region", "provincias", "celdas", "clientes", "SAM MM",
             "ext km", "% acum"]
print(v.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
print()
n50 = int((g["pct_acum"] <= 50).sum()) + 1
print(f"{n50} territorios concentran la mitad del mercado agrupado.")
print(f"{g.visitable_en_dia.sum()} de {len(g)} miden menos de 120 km de punta "
      "a punta: se recorren en una salida.")
