# -*- coding: utf-8 -*-
"""Cuánto mercado queda fuera de todo territorio, por qué, y qué costaría meterlo.

Los 57 territorios de venta cubren la mitad de los clientes del país. La otra
mitad no tiene dueño, y antes de proponer nada hay que separar lo que es una
decisión de diseño de lo que es un residuo del método.

`build_clusters.py` no agrupa todo el mercado: ordena las celdas por SAM, toma
**el 80% superior** y sobre eso corre DBSCAN. Lo que queda debajo del corte no
es que el algoritmo lo haya rechazado; es que nunca lo miró. Y dentro del corte
hay dos salidas más: la celda que DBSCAN marca como ruido —no tiene cinco
vecinas a menos de 15 km— y el núcleo que sí se forma pero no llega al medio
millón de dólares que se pide para llamarlo territorio.

Este archivo mide las tres, y después mide la única propuesta que hay sobre la
mesa: **que cada celda huérfana entre al territorio más cercano que la alcance
por carretera**, con la vara de horas como parámetro. Lo que importa de esa
propuesta no es cuánto mercado recupera —recupera casi todo si la vara es
generosa— sino qué le hace al territorio que lo recibe: un territorio de venta
existe para que alguien lo recorra, y `build_clusters.py` llama «visitable en
el día» al que mide menos de 120 km de punta a punta. Estirar los bordes para
ganar clientes dispersos puede dejar sin visitar a los que ya estaban.

Por eso la salida es una tabla de compromiso y no una recomendación: cuántos
clientes entran a cada vara, y cuántos territorios dejan de recorrerse en una
salida por haberlos aceptado.

No escribe nada en `out/`: es una medición para decidir, no una etapa.

Uso:
    python scripts/diag_territorios.py
    python scripts/diag_territorios.py --varas 1,2,3,4,6
"""
import io
import os
import sys

import numpy as np
import pandas as pd
from pyproj import Geod
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

COBERTURA = 0.80          # el mismo corte que usa build_clusters.py
MIN_SAM = 500_000
VISITABLE_KM = 120.0
GEOD = Geod(ellps="WGS84")


def diagonal_km(lat, lon):
    """La extensión del territorio como la mide `build_clusters.py`: la
    diagonal del rectángulo que lo envuelve."""
    if len(lat) < 2:
        return 0.0
    _, _, d = GEOD.inv([lon.min()], [lat.min()], [lon.max()], [lat.max()])
    return float(d[0]) / 1000


def main():
    varas = [1.0, 2.0, 3.0, 4.0, 6.0]
    for a in sys.argv[1:]:
        if a.startswith("--varas"):
            varas = [float(x) for x in a.split("=", 1)[-1].split(",")]

    h = pd.read_csv("out/h3_r6.csv", encoding="utf-8-sig")
    h = h[h["sam_usd"] > 0].sort_values("sam_usd", ascending=False)
    h = h.reset_index(drop=True)
    h["acum"] = h["sam_usd"].cumsum() / h["sam_usd"].sum()
    cel = pd.read_csv("out/clusters_celda.csv", encoding="utf-8-sig",
                      usecols=["h3", "cluster"]).drop_duplicates("h3")
    ter = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
    vivos = set(ter["cluster"])

    h["cluster"] = h["h3"].map(dict(zip(cel.h3, cel.cluster)))
    dentro = h["cluster"].isin(vivos)
    bajo_corte = h["acum"] > COBERTURA
    ruido = (~bajo_corte) & (h["cluster"] == -1)
    chico = (~bajo_corte) & (h["cluster"] >= 0) & (~dentro)

    TOT_C, TOT_S = h["clientes"].sum(), h["sam_usd"].sum()

    def fila(nombre, m):
        return (nombre, int(m.sum()), h.loc[m, "clientes"].sum(),
                h.loc[m, "sam_usd"].sum())

    print("=" * 78)
    print("EL MERCADO QUE NO TIENE TERRITORIO  ·  de dónde sale cada pedazo")
    print("=" * 78)
    print("%-42s %7s %11s %10s" % ("", "celdas", "clientes", "SAM MM"))
    for nombre, n, c, s in [
            fila("en un territorio de los 57", dentro),
            fila("bajo el corte del 80%: nunca se miró", bajo_corte),
            fila("ruido de DBSCAN dentro del corte", ruido),
            fila("núcleo por debajo de US$ 500 mil", chico)]:
        print("  %-40s %7s %11s %10.1f"
              % (nombre, f"{n:,}", f"{c:,.0f}", s / 1e6))
    fuera = ~dentro
    print("  %-40s %7s %11s %10.1f"
          % ("— fuera, en total", int(fuera.sum()),
             f"{h.loc[fuera, 'clientes'].sum():,.0f}",
             h.loc[fuera, "sam_usd"].sum() / 1e6))
    print("  %-40s %7s %11s %10.1f"
          % ("— el país", len(h), f"{TOT_C:,.0f}", TOT_S / 1e6))
    print()
    print("El 80% es una decisión de `build_clusters.py`, no un residuo: el "
          "resto\nnunca entró al agrupamiento. Es el pedazo más grande de lo "
          "que falta.")

    # ------------------------------------------------- lo que costaría --
    print()
    print("ruteando desde cada territorio...", flush=True)
    g = grafo_vial.construir()
    G = g.csr()
    idx_ter = g.arbol.query(np.column_stack([ter.lon.values,
                                             ter.lat.values]))[1]
    fu = h[fuera].reset_index(drop=True)
    idx_fu = g.arbol.query(np.column_stack([fu.centro_lon.values,
                                            fu.centro_lat.values]))[1]
    T = np.full((len(ter), len(fu)), np.inf)
    for i, src in enumerate(idx_ter):
        T[i] = dijkstra(G, indices=int(src), directed=True)[idx_fu]
        if (i + 1) % 15 == 0:
            print("  %d/%d" % (i + 1, len(ter)), flush=True)
    cual = np.argmin(T, axis=0)
    horas = T[cual, np.arange(len(fu))]

    # La extensión de cada territorio hoy, con sus propias celdas.
    cel_h = h[dentro]
    ext_hoy = {c: diagonal_km(gg.centro_lat.values, gg.centro_lon.values)
               for c, gg in cel_h.groupby("cluster")}

    print()
    print("=" * 78)
    print("SI CADA CELDA HUÉRFANA ENTRA AL TERRITORIO QUE LA ALCANCE")
    print("=" * 78)
    print("%-6s %11s %9s %10s %9s %12s" %
          ("vara", "clientes", "% del", "SAM MM", "% del", "visitables"))
    print("%-6s %11s %9s %10s %9s %12s" %
          ("", "que entran", "país", "que entra", "país", "en el día"))
    vis_hoy = int(ter.visitable_en_dia.sum())
    for v in varas:
        m = horas <= v
        ext = dict(ext_hoy)
        for c, gg in fu[m].assign(_c=cual[m]).groupby("_c"):
            cl = ter["cluster"].iat[int(c)]
            p = cel_h[cel_h["cluster"] == cl]
            lat = np.concatenate([p.centro_lat.values, gg.centro_lat.values])
            lon = np.concatenate([p.centro_lon.values, gg.centro_lon.values])
            ext[cl] = diagonal_km(lat, lon)
        vis = sum(1 for c in ter["cluster"] if ext.get(c, 0) <= VISITABLE_KM)
        print("%-6s %11s %8.0f%% %10.1f %8.0f%% %6d de %d"
              % ("%.0f h" % v, f"{fu.loc[m, 'clientes'].sum():,.0f}",
                 100 * fu.loc[m, "clientes"].sum() / TOT_C,
                 fu.loc[m, "sam_usd"].sum() / 1e6,
                 100 * fu.loc[m, "sam_usd"].sum() / TOT_S,
                 vis, len(ter)))
    print()
    print("hoy, sin tocar nada: %d de %d territorios se recorren en el día"
          % (vis_hoy, len(ter)))
    print("clientes sin territorio: %s (%.0f%%)"
          % (f"{h.loc[fuera, 'clientes'].sum():,.0f}",
             100 * h.loc[fuera, "clientes"].sum() / TOT_C))
    lejos = int((~np.isfinite(horas)).sum())
    if lejos:
        print("celdas que ningún territorio alcanza por carretera: %d" % lejos)

    # ------------------------------------ la vara que no es una vara fija --
    # Poner la misma hora para todos es lo cómodo y no lo correcto: un
    # territorio compacto aguanta celdas a dos horas sin dejar de recorrerse
    # en el día, y uno que ya mide 118 km no aguanta ninguna. La regla que
    # respeta el criterio del propio diseño es aceptar mientras el territorio
    # siga siendo visitable, empezando por lo más cercano.
    print()
    print("=" * 78)
    print("O SIN VARA FIJA: ACEPTAR MIENTRAS EL TERRITORIO SIGA VISITABLE")
    print("=" * 78)
    for tope in (2.0, 4.0, 6.0):
        orden = np.argsort(horas)
        latx = {c: list(gg.centro_lat.values)
                for c, gg in cel_h.groupby("cluster")}
        lonx = {c: list(gg.centro_lon.values)
                for c, gg in cel_h.groupby("cluster")}
        tomadas = np.zeros(len(fu), dtype=bool)
        for i in orden:
            if not np.isfinite(horas[i]) or horas[i] > tope:
                break
            cl = ter["cluster"].iat[int(cual[i])]
            la = latx.get(cl, []) + [fu.centro_lat.iat[i]]
            lo = lonx.get(cl, []) + [fu.centro_lon.iat[i]]
            if diagonal_km(np.array(la), np.array(lo)) <= VISITABLE_KM:
                latx[cl], lonx[cl] = la, lo
                tomadas[i] = True
        vis = sum(1 for c in ter["cluster"]
                  if diagonal_km(np.array(latx.get(c, [0, 0])),
                                 np.array(lonx.get(c, [0, 0])))
                  <= VISITABLE_KM)
        print("  tope %.0f h  ·  entran %s clientes (%.0f%%) y US$ %.1f MM "
              "(%.0f%%)  ·  %d de %d visitables"
              % (tope, f"{fu.loc[tomadas, 'clientes'].sum():,.0f}",
                 100 * fu.loc[tomadas, "clientes"].sum() / TOT_C,
                 fu.loc[tomadas, "sam_usd"].sum() / 1e6,
                 100 * fu.loc[tomadas, "sam_usd"].sum() / TOT_S,
                 vis, len(ter)))
    print()
    print("Los territorios que hoy no se recorren en el día no mejoran con "
          "esto: ya miden más de 120 km por sí solos y la regla no les añade "
          "nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
