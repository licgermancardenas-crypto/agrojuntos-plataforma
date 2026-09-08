# -*- coding: utf-8 -*-
"""Construye el grafo vial contraído, con pendiente, en memoria acotada.

La máquina tiene 3.6 GB de RAM. Un grafo con los 5.2 millones de puntos de
forma de OpenStreetMap no entra: un diccionario de Python con esa cantidad de
claves de tupla ocupa más de un gigabyte solo en sobrecosto de objeto, y
`json.load` sobre los 239 MB de Overpass otro tanto.

Tres decisiones lo resuelven sin degradar el resultado:

1. La geometría se lee del caché de arreglos que deja `build_vial_compacto.py`,
   no del JSON. La coordenada ya viene entera y la identidad del nodo es
   exacta: no depende de cómo redondee un float.

2. El grafo se contrae a nodos de unión. La inmensa mayoría de los puntos de
   OSM son vértices de forma que describen la curvatura de la vía, no
   intersecciones: no cambian el camino más corto, solo el dibujo. Se conservan
   los extremos de cada vía, los puntos compartidos por dos o más vías y un
   hito cada kilómetro —para que quien se enganche al grafo no tenga que
   caminar diez— y el tiempo de los tramos intermedios se acumula en la arista.

3. Todo se arma con numpy, incluida la contracción. La versión anterior
   recorría los cinco millones y medio de vértices en un bucle de Python.

## La pendiente

Cada nodo lleva su cota, muestreada por `cota.py` del DEM que el proyecto ya
tenía cacheado para sombrear mapas. Antes el terreno no entraba en ninguna
cuenta —la velocidad era clase de vía por superficie— y un camión cargado
subiendo tres mil metros contaba igual que uno en llano.

    subida : factor = 1 / (1 + 0.12 · pendiente_%)      8% -> 0.51
    bajada : sin castigo hasta −8%; más allá manda el freno

**La pendiente no se mide entre nodo y nodo.** Los vértices de OSM están a
decenas de metros y el DEM tiene 300 m por píxel: un tramo de 50 m que cruza
una ladera hereda el gradiente del cerro —treinta, cuarenta por ciento— aunque
la carretera suba al ocho en zigzag. Medida así alargaba el grafo un 47%, y la
mitad de eso era la ladera y no la vía. Se mide sobre una ventana de 1 km a lo
largo de la vía y se recorta a ±12%, que es el máximo de diseño vial peruano.

Con pendiente **el grafo deja de ser simétrico**: subir de Virú a Otuzco no
cuesta lo mismo que bajar. Por eso `Grafo` guarda los dos sentidos y quien lo
use tiene que decir cuál quiere. `directed=False` en scipy deja de ser válido.

El parámetro `clases`, que permitía quedarse solo con la red principal, se
retiró al pasar al caché: no lo usaba ninguna etapa, solo la demostración de
este mismo archivo.
"""
import glob
import os
import sys

import numpy as np
from pyproj import Geod
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cota import muestrear                                    # noqa: E402

GEOD = Geod(ellps="WGS84")
DEC = 6                        # decimales con que viene la coordenada

VENTANA_M = 1000.0             # ventana sobre la que se mide la pendiente
K_SUBE = 0.12
K_BAJA = 0.05
BAJADA_LIBRE = 8.0             # % hasta donde bajar no cuesta
PEND_MAX = 12.0                # % máximo de diseño vial peruano
FACTOR_MIN = 0.25              # nada se arrastra por debajo de esto

CACHE = os.path.join("data", "vial", "compacto", "PE-*.npz")


def factor(p):
    """Multiplicador de velocidad para una pendiente en %, en el sentido en
    que se recorre: positiva es subida."""
    f = np.ones_like(p)
    sube = p > 0
    f[sube] = 1.0 / (1.0 + K_SUBE * p[sube])
    baja = p < -BAJADA_LIBRE
    f[baja] = 1.0 / (1.0 + K_BAJA * (-p[baja] - BAJADA_LIBRE))
    return np.clip(f, FACTOR_MIN, 1.0)


class Grafo(object):
    """El grafo contraído y sus tres pesos: ida, vuelta y llano.

    `ida` es el tiempo de recorrer la arista de O a D; `vuelta`, de D a O. El
    llano —sin terreno— se conserva para poder medir cuánto pesa la pendiente,
    que es la única forma de defender el cambio ante quien vio las cifras
    anteriores.
    """

    def __init__(self, O, D, ida, vuelta, llano, coords, pend):
        self.O, self.D = O, D
        self.ida, self.vuelta, self.llano = ida, vuelta, llano
        self.coords = coords
        self.pend = pend
        self.N = len(coords)
        self.arbol = cKDTree(coords)

    def snap(self, lons, lats):
        return self.arbol.query(np.column_stack([lons, lats]))[1]

    def csr(self, llano=False, hacia=False, fuentes=None):
        """Matriz dirigida: la casilla (a, b) es el tiempo de ir de a a b.

        `llano=True` arma la versión sin terreno, que solo sirve para medir
        cuánto pesa la pendiente. `hacia=True` traspone, de modo que un
        Dijkstra desde la fuente contesta «cuánto tarda cada nodo en LLEGAR»
        en vez de «cuánto tarda en salir» —con pendiente no son lo mismo—.
        `fuentes` agrega un nodo virtual unido a esas posiciones a costo cero:
        una sola corrida contesta por todos los destinos a la vez.
        """
        o = np.concatenate([self.O, self.D])
        d = np.concatenate([self.D, self.O])
        w = (np.concatenate([self.llano, self.llano]) if llano
             else np.concatenate([self.ida, self.vuelta]))
        if hacia:
            o, d = d, o
        n = self.N
        if fuentes is not None:
            f = np.asarray(fuentes, dtype=np.int32)
            o = np.concatenate([o, np.full(len(f), n, dtype=np.int32)])
            d = np.concatenate([d, f])
            w = np.concatenate([w, np.zeros(len(f))])
            n = self.N + 1
        return csr_matrix((w, (o, d)), shape=(n, n))


def construir(cache=CACHE, ventana=VENTANA_M, verbose=True):
    """Lee el caché vial, mide la pendiente y contrae. Devuelve un `Grafo`."""
    arch = sorted(glob.glob(cache))
    if not arch:
        raise SystemExit("falta el cache vial: corre "
                         "scripts/build_vial_compacto.py")
    q_lon, q_lat, vel, cut = [], [], [], [np.zeros(1, dtype=np.int64)]
    for a in arch:
        d = np.load(a)
        q_lon.append(d["lon"])
        q_lat.append(d["lat"])
        vel.append(d["vel"])
        cut.append(d["cut"][1:] + cut[-1][-1])
    q_lon = np.concatenate(q_lon)
    q_lat = np.concatenate(q_lat)
    vel = np.concatenate(vel).astype(np.float64)
    cut = np.concatenate(cut)
    n_vias = len(vel)

    clave = ((q_lon.astype(np.int64) + 200_000_000) * 1_000_000_000
             + (q_lat.astype(np.int64) + 200_000_000))
    _, primero, P = np.unique(clave, return_index=True, return_inverse=True)
    P = P.astype(np.int32)
    coords = np.column_stack([q_lon[primero] / 10.0 ** DEC,
                              q_lat[primero] / 10.0 ** DEC])
    del clave, primero, q_lon, q_lat
    if verbose:
        print("  vias %s · puntos %s · nodos %s"
              % (f"{n_vias:,}", f"{len(P):,}", f"{len(coords):,}"), flush=True)

    alt = muestrear(coords[:, 0], coords[:, 1]).astype(np.float32)
    alt = np.where(np.isnan(alt), 0.0, alt)

    veces = np.bincount(P, minlength=len(coords))
    c_a, c_b, c_ab, c_ba, c_ll, c_p = [], [], [], [], [], []
    for w in range(n_vias):
        ini, fin = cut[w], cut[w + 1]
        idx = P[ini:fin]
        if len(idx) < 2:
            continue
        xlon, xlat = coords[idx, 0], coords[idx, 1]
        _, _, dm = GEOD.inv(xlon[:-1], xlat[:-1], xlon[1:], xlat[1:])
        h = alt[idx].astype(np.float64)
        c = np.concatenate([[0.0], np.cumsum(dm)])
        med = (c[:-1] + c[1:]) / 2.0
        lo = np.clip(med - ventana / 2, 0.0, c[-1])
        hi = np.clip(med + ventana / 2, 0.0, c[-1])
        p = np.clip(100.0 * (np.interp(hi, c, h) - np.interp(lo, c, h))
                    / np.maximum(hi - lo, 1.0), -PEND_MAX, PEND_MAX)

        base = (dm / 1000.0) / vel[w]
        t_ab = base / factor(p)
        t_ba = base / factor(-p)

        guarda = veces[idx] > 1                  # cruces con otras vías
        guarda[0] = guarda[-1] = True            # extremos de la vía
        guarda |= np.concatenate([[False],       # un hito cada kilómetro
                                  np.diff((c // ventana).astype(np.int64)) > 0])
        r = np.flatnonzero(guarda)
        if len(r) < 2:
            continue
        for acum, destino in ((t_ab, c_ab), (t_ba, c_ba), (base, c_ll)):
            s = np.concatenate([[0.0], np.cumsum(acum)])
            destino.append(s[r[1:]] - s[r[:-1]])
        c_a.append(idx[r[:-1]])
        c_b.append(idx[r[1:]])
        c_p.append(p[r[:-1]])

    O = np.concatenate(c_a)
    D = np.concatenate(c_b)
    ida = np.concatenate(c_ab)
    vuelta = np.concatenate(c_ba)
    llano = np.concatenate(c_ll)
    pend = np.concatenate(c_p)
    del c_a, c_b, c_ab, c_ba, c_ll, c_p, P, cut, vel, alt, veces

    # Los nodos que sobrevivieron se renumeran: el árbol de búsqueda tiene que
    # ver los mismos que el grafo, o algo se engancharía a un nodo inexistente.
    vivos, remap = np.unique(np.concatenate([O, D]), return_inverse=True)
    mitad = len(O)
    O = remap[:mitad].astype(np.int32)
    D = remap[mitad:].astype(np.int32)
    coords = coords[vivos]
    del vivos, remap

    # `csr_matrix` suma las casillas repetidas, y dos vías que comparten el
    # mismo par de nodos —un puente mapeado dos veces, una vía de servicio
    # paralela— son repetidas: ese tramo salía al doble de caro. Se conserva la
    # más rápida, que es la que un camión tomaría.
    #
    # El par se canoniza antes de comparar. Dos vías pueden describir el mismo
    # tramo en sentidos opuestos —una como a→b y la otra como b→a— y entonces
    # no se parecen como pares aunque sean el mismo camino; al armar la matriz
    # caían en la misma casilla y se sumaban igual. Al voltear el par hay que
    # voltear también los tiempos, o la subida quedaría cobrada como bajada.
    voltear = O > D
    O, D = np.where(voltear, D, O), np.where(voltear, O, D)
    ida, vuelta = (np.where(voltear, vuelta, ida),
                   np.where(voltear, ida, vuelta))
    orden = np.lexsort((ida + vuelta, D, O))
    O, D = O[orden], D[orden]
    ida, vuelta, llano, pend = (ida[orden], vuelta[orden], llano[orden],
                                pend[orden])
    primera = np.ones(len(O), dtype=bool)
    primera[1:] = (O[1:] != O[:-1]) | (D[1:] != D[:-1])
    if verbose:
        print("  aristas %s · %s duplicadas descartadas"
              % (f"{int(primera.sum()):,}",
                 f"{len(O) - int(primera.sum()):,}"), flush=True)
        print("  pendiente mediana %.1f%% · el terreno alarga el grafo %.1f%%"
              % (np.median(np.abs(pend[primera])),
                 100 * (ida[primera].sum() + vuelta[primera].sum())
                 / (2 * llano[primera].sum()) - 100), flush=True)
    return Grafo(O[primera], D[primera], ida[primera], vuelta[primera],
                 llano[primera], coords, pend[primera])


if __name__ == "__main__":
    print("grafo vial con pendiente:")
    g = construir()
    sube = g.pend > 2
    print("  %s nodos vivos · %.1f%% de las aristas suben mas de 2%%"
          % (f"{g.N:,}", 100 * sube.mean()))
    print("  una arista tipo: %.2f h de ida, %.2f de vuelta, %.2f en llano"
          % (g.ida[sube].mean(), g.vuelta[sube].mean(), g.llano[sube].mean()))
