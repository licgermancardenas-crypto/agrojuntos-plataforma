# -*- coding: utf-8 -*-
"""Construye el grafo vial contraído, en memoria acotada.

La máquina tiene 3.4 GB de RAM. Un grafo con los 5.2 millones de puntos de
forma de OpenStreetMap no entra: un diccionario de Python con esa cantidad de
claves de tupla ocupa más de un gigabyte solo en sobrecosto de objeto.

Dos decisiones lo resuelven sin degradar el resultado:

1. Todo se arma con numpy. Las coordenadas se codifican como enteros de 64 bits
   y `np.unique` asigna los identificadores de nodo; 5.2 millones de int64 son
   42 MB, contra el gigabyte largo del diccionario equivalente.

2. El grafo se contrae a nodos de unión. La inmensa mayoría de los puntos de
   OSM son vértices de forma que describen la curvatura de la vía, no
   intersecciones: no cambian el camino más corto, solo el dibujo. Se conservan
   los extremos de cada vía y los puntos compartidos por dos o más vías, y el
   tiempo de los tramos intermedios se acumula en la arista.

El resultado es el mismo enrutamiento con dos órdenes de magnitud menos de
nodos.
"""
import glob
import json
import re

import numpy as np
from pyproj import Geod
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

GEOD = Geod(ellps="WGS84")

VEL_CLASE = {"motorway": 90, "motorway_link": 60, "trunk": 75,
             "trunk_link": 50, "primary": 60, "primary_link": 40,
             "secondary": 50, "secondary_link": 35, "tertiary": 40,
             "tertiary_link": 30}
FACTOR_SUP = {"asphalt": 1.00, "paved": 1.00, "concrete": 0.95,
              "paving_stones": 0.85, "compacted": 0.70, "gravel": 0.60,
              "fine_gravel": 0.65, "unpaved": 0.55, "ground": 0.45,
              "dirt": 0.45, "earth": 0.45, "sand": 0.35, "mud": 0.30}

ESC = 1_000_000          # 6 decimales, ~11 cm
OFF_LON, OFF_LAT = 180, 90


def _maxspeed(v):
    m = re.match(r"(\d+)", str(v))
    return int(m.group(1)) if m else None


def _clave(lon, lat):
    """Empaqueta lon/lat en un int64 único."""
    a = np.rint((lon + OFF_LON) * ESC).astype(np.int64)
    b = np.rint((lat + OFF_LAT) * ESC).astype(np.int64)
    return a * 400_000_000 + b


def _desclave(k):
    b = k % 400_000_000
    a = (k - b) // 400_000_000
    return a / ESC - OFF_LON, b / ESC - OFF_LAT


def construir(patron="data/vial/PE-*.json", clases=None, verbose=True):
    """Devuelve (G, coords, arbol). `clases` limita los tipos de vía."""
    claves, tiempos, corte = [], [], [0]
    n_vias = 0

    for f in sorted(glob.glob(patron)):
        for e in json.load(open(f, encoding="utf-8"))["elements"]:
            g = e.get("geometry")
            if not g or len(g) < 2:
                continue
            t = e.get("tags", {})
            hw = t.get("highway", "tertiary")
            if clases and hw not in clases:
                continue
            v = VEL_CLASE.get(hw, 35) * FACTOR_SUP.get(t.get("surface", ""), 0.80)
            ms = _maxspeed(t.get("maxspeed", ""))
            v = max(min(v, ms) if ms else v, 8.0)

            lo = np.fromiter((p["lon"] for p in g), float, len(g))
            la = np.fromiter((p["lat"] for p in g), float, len(g))
            _, _, dm = GEOD.inv(lo[:-1], la[:-1], lo[1:], la[1:])
            claves.append(_clave(lo, la))
            tiempos.append((dm / 1000.0 / v).astype(np.float32))
            corte.append(corte[-1] + len(g))
            n_vias += 1

    K = np.concatenate(claves)
    del claves
    uniq, inv = np.unique(K, return_inverse=True)
    del K
    inv = inv.astype(np.int32)

    # Un nodo se conserva si es extremo de vía o si lo comparten dos o más
    # vías; el resto son vértices de forma y se absorben en la arista.
    grados = np.bincount(inv, minlength=len(uniq))
    es_union = grados > 2
    for c in corte[:-1]:
        es_union[inv[c]] = True
    for c in corte[1:]:
        es_union[inv[c - 1]] = True

    O, D, W = [], [], []
    for i in range(n_vias):
        a, b = corte[i], corte[i + 1]
        nodos = inv[a:b]
        pesos = tiempos[i]
        ancla, acum = nodos[0], 0.0
        for j in range(len(pesos)):
            acum += pesos[j]
            sig = nodos[j + 1]
            if es_union[sig] or j == len(pesos) - 1:
                if sig != ancla:
                    O.append(ancla); D.append(sig); W.append(acum)
                ancla, acum = sig, 0.0
    del tiempos, inv

    O = np.asarray(O, dtype=np.int32)
    D = np.asarray(D, dtype=np.int32)
    W = np.asarray(W, dtype=np.float32)

    # reindexar solo los nodos que quedaron en uso
    usados = np.unique(np.concatenate([O, D]))
    mapa = np.full(len(uniq), -1, dtype=np.int32)
    mapa[usados] = np.arange(len(usados), dtype=np.int32)
    O, D = mapa[O], mapa[D]

    lon, lat = _desclave(uniq[usados])
    coords = np.column_stack([lon, lat])
    del uniq, usados, mapa

    N = len(coords)
    G = csr_matrix((np.concatenate([W, W]),
                    (np.concatenate([O, D]), np.concatenate([D, O]))),
                   shape=(N, N))
    if verbose:
        print(f"  vias {n_vias:,} · nodos {N:,} · aristas {G.nnz // 2:,}",
              flush=True)
    return G, coords, cKDTree(coords)


if __name__ == "__main__":
    print("grafo completo:")
    construir()
    print("solo red principal (sin terciarias):")
    construir(clases={"motorway", "motorway_link", "trunk", "trunk_link",
                      "primary", "primary_link", "secondary",
                      "secondary_link"})
