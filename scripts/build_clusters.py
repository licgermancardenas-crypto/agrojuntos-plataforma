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
"""
import numpy as np
import pandas as pd
from pyproj import Geod
from sklearn.cluster import DBSCAN

GEOD = Geod(ellps="WGS84")
TIERRA_KM = 6371.0
COBERTURA = 0.80         # porción del SAM que entra al agrupamiento
EPS_KM = 15.0            # radio de vecindad
MIN_CELDAS = 5           # celdas mínimas para constituir núcleo
MIN_SAM = 500_000        # US$ anuales para llamarlo territorio

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
g = (val.groupby("cluster")
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

# Extensión: la diagonal del rectángulo que envuelve al núcleo.
diag = []
for c in g["cluster"]:
    p = val[val["cluster"] == c]
    _, _, d = GEOD.inv([p.centro_lon.min()], [p.centro_lat.min()],
                       [p.centro_lon.max()], [p.centro_lat.max()])
    diag.append(d[0] / 1000)
g["extension_km"] = diag
g["sam_por_cliente"] = g["sam_usd"] / g["clientes"].replace(0, np.nan)

g = g[g["sam_usd"] >= MIN_SAM].sort_values("sam_usd", ascending=False)
g = g.reset_index(drop=True)
g["rank"] = g.index + 1
g["pct_sam"] = 100 * g["sam_usd"] / SAM_TOTAL
g["pct_acum"] = g["pct_sam"].cumsum()

# Un territorio se recorre en el día si mide menos de ~120 km de punta a punta.
g["visitable_en_dia"] = g["extension_km"] <= 120

g.to_csv("out/clusters_territorio.csv", index=False, encoding="utf-8-sig")
nucleo[["h3", "dep", "prov", "centro_lat", "centro_lon", "sam_usd",
        "clientes", "cluster"]].to_csv("out/clusters_celda.csv", index=False,
                                       encoding="utf-8-sig")

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
print(f"mercado en territorios: {g.pct_sam.sum():.0f}% del SAM")
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
