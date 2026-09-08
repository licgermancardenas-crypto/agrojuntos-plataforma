# -*- coding: utf-8 -*-
"""Cota sobre el DEM que ya está en disco, y los pisos que salen de ella.

El proyecto bajó teselas Terrarium para sombrear los mapas —la altura viene
codificada en el RGB de un PNG— y las dejó ahí como dibujo. Este módulo las
lee como dato: dado un punto, cuántos metros sobre el mar.

Dos cosas lo justifican. El tiempo de viaje se calculaba con la clase de vía y
su superficie, y el propio comentario de `build_ruteo.py` decía «before surface
and terrain»: el terreno nunca entró, de modo que un camión cargado subiendo
tres mil metros contaba igual que uno en llano. Y la capa de acopio sabe dónde
sale la carga pero no a qué altura, que es lo que decide qué se puede sembrar
ahí y, por lo tanto, qué insumo se vende.

Resolución. Las teselas están al zoom 9: unos 300 m por píxel a esta latitud.
Es suficiente para el perfil de una carretera que sube 3,000 m en 100 km y es
grueso para el fondo de un cañón. La única forma honesta de saber cuánto pesa
eso es medirlo, y por eso el módulo trae su propia validación contra veinte
altitudes conocidas: `python scripts/cota.py`. El error que imprime es el que
hay que tener en la cabeza al leer cualquier cifra que salga de aquí.

Uso como módulo:
    from cota import muestrear, piso
    alt = muestrear(lons, lats)          # metros, NaN donde no hay tesela
"""
import math
import os
import time

import numpy as np
from PIL import Image

Z = 9
CACHE = os.path.join("data", "dem")
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
UA = {"User-Agent": "AgroJuntos-atlas/1.0 (analisis de mercado)"}

_TESELAS = {}          # (z, x, y) -> ndarray 256x256 float32, o None si océano


def _ruta(z, x, y):
    return os.path.join(CACHE, "%d_%d_%d.png" % (z, x, y))


def _bajar(z, x, y):
    """Una tesela que falte. Las de océano no existen y se anotan vacías para
    no volver a pedirlas nunca."""
    p = _ruta(z, x, y)
    if os.path.exists(p):
        return p
    import requests
    os.makedirs(CACHE, exist_ok=True)
    for intento in range(4):
        try:
            r = requests.get(URL.format(z=z, x=x, y=y), headers=UA, timeout=45)
            if r.status_code == 200:
                open(p, "wb").write(r.content)
                return p
            if r.status_code == 404:
                open(p, "wb").write(b"")
                return p
        except Exception:
            pass
        time.sleep(1.5 * (intento + 1))
    return None


def _tesela(z, x, y, bajar=True):
    k = (z, x, y)
    if k in _TESELAS:
        return _TESELAS[k]
    p = _ruta(z, x, y)
    if not os.path.exists(p) and bajar:
        p = _bajar(z, x, y)
    if not p or not os.path.exists(p) or os.path.getsize(p) == 0:
        _TESELAS[k] = None
        return None
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
    # Terrarium: h = R*256 + G + B/256 - 32768
    _TESELAS[k] = a[:, :, 0] * 256.0 + a[:, :, 1] + a[:, :, 2] / 256.0 - 32768.0
    return _TESELAS[k]


def _pixeles(gx, gy, z, bajar):
    """Elevación de píxeles globales enteros, agrupando por tesela para abrir
    cada PNG una sola vez —son cientos de miles de puntos contra 564 teselas—."""
    out = np.full(len(gx), np.nan, dtype=np.float64)
    n = 2 ** z
    gx = np.clip(gx, 0, 256 * n - 1)
    gy = np.clip(gy, 0, 256 * n - 1)
    tx, ty = gx // 256, gy // 256
    ox, oy = gx % 256, gy % 256
    clave = tx.astype(np.int64) * 100000 + ty
    for c in np.unique(clave):
        m = clave == c
        t = _tesela(z, int(tx[m][0]), int(ty[m][0]), bajar)
        if t is None:
            continue
        out[m] = t[oy[m], ox[m]]
    return out


def _global(lons, lats, z):
    """Coordenada de píxel global, en float: Web Mercator del esquema XYZ."""
    n = 2 ** z
    lons = np.asarray(lons, dtype=np.float64)
    lats = np.clip(np.asarray(lats, dtype=np.float64), -85.05, 85.05)
    px = (lons + 180.0) / 360.0 * 256.0 * n
    la = np.radians(lats)
    py = ((1.0 - np.log(np.tan(la) + 1.0 / np.cos(la)) / np.pi) / 2.0
          * 256.0 * n)
    return px, py


def muestrear(lons, lats, z=Z, bajar=True):
    """Metros sobre el mar, con interpolación bilineal entre los cuatro
    píxeles vecinos. Sin interpolar, dos fincas del mismo valle a 200 m una de
    otra caían en el mismo píxel y salían con la misma cota exacta, que es una
    precisión que el dato no tiene."""
    px, py = _global(lons, lats, z)
    # El centro del píxel i está en i+0.5: se corre medio píxel antes de
    # repartir el peso, o la interpolación queda sesgada media celda.
    px -= 0.5
    py -= 0.5
    x0, y0 = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
    fx, fy = px - x0, py - y0
    e00 = _pixeles(x0, y0, z, bajar)
    e10 = _pixeles(x0 + 1, y0, z, bajar)
    e01 = _pixeles(x0, y0 + 1, z, bajar)
    e11 = _pixeles(x0 + 1, y0 + 1, z, bajar)
    return ((e00 * (1 - fx) + e10 * fx) * (1 - fy) +
            (e01 * (1 - fx) + e11 * fx) * fy)


def metros_por_pixel(lat, z=Z):
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


# ------------------------------------------------------------ los pisos ----
# Las ocho regiones de Pulgar Vidal, que es la clasificación con la que habla
# el agro peruano. Se agrupan las que el dato no distingue —janca y puna se
# separan a 4,800 m, donde ya no hay agricultura comercial— y se usa la región
# natural para desempatar: a 800 m, la vertiente occidental es yunga seca y la
# oriental es selva alta, y no producen lo mismo ni compran lo mismo.
PISOS = [
    ("chala", 0, 500),
    ("yunga", 500, 2300),
    ("quechua", 2300, 3500),
    ("suni", 3500, 4000),
    ("puna", 4000, 10000),
]
PISOS_SELVA = [
    ("selva baja", 0, 400),
    ("selva alta", 400, 1000),
    ("ceja de selva", 1000, 3500),
    ("puna", 3500, 10000),
]


def piso(alt, region_natural=""):
    """El piso ecológico de una cota. Devuelve '' si no hay cota: la ausencia
    de dato no es el nivel del mar."""
    if alt is None or not np.isfinite(alt):
        return ""
    tabla = PISOS_SELVA if str(region_natural).lower().startswith("selva") \
        else PISOS
    for nombre, lo, hi in tabla:
        if lo <= alt < hi:
            return nombre
    return tabla[-1][0]


def pisos(alts, regiones):
    return [piso(a, r) for a, r in zip(alts, regiones)]


# ------------------------------------------------------------ validación ---
# Altitudes de plaza de armas publicadas por las municipalidades y el IGN. Se
# eligen a propósito los casos duros: Cerro de Pasco a 4,330 m, La Oroya en el
# fondo de un valle encajonado, Iquitos en llano amazónico. Si el muestreo
# funciona en el llano y falla en el cañón, hay que saberlo antes y no después.
CONOCIDAS = [
    ("Lima",            -12.0464, -77.0428,  154),
    ("Trujillo",         -8.1120, -79.0288,   34),
    ("Chiclayo",         -6.7714, -79.8409,   27),
    ("Piura",            -5.1945, -80.6328,   29),
    ("Ica",             -14.0678, -75.7286,  406),
    ("Tacna",           -18.0146, -70.2536,  562),
    ("Moquegua",        -17.1939, -70.9350, 1410),
    ("Arequipa",        -16.3989, -71.5350, 2335),
    ("Abancay",         -13.6339, -72.8814, 2377),
    ("Cajamarca",        -7.1617, -78.5128, 2750),
    ("Ayacucho",        -13.1588, -74.2239, 2761),
    ("Huancayo",        -12.0653, -75.2049, 3259),
    ("Huaraz",           -9.5278, -77.5278, 3052),
    ("Cusco",           -13.5320, -71.9675, 3399),
    ("La Oroya",        -11.5250, -75.9000, 3745),
    ("Juliaca",         -15.4997, -70.1333, 3825),
    ("Puno",            -15.8402, -70.0219, 3827),
    ("Cerro de Pasco",  -10.6839, -76.2564, 4330),
    ("Tarapoto",         -6.4869, -76.3719,  356),
    ("Iquitos",          -3.7491, -73.2538,  106),
]


def validar():
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    lat = np.array([c[1] for c in CONOCIDAS])
    lon = np.array([c[2] for c in CONOCIDAS])
    ref = np.array([c[3] for c in CONOCIDAS], dtype=float)
    alt = muestrear(lon, lat)
    err = alt - ref
    print("cota muestreada contra altitud publicada · zoom %d, %.0f m/px"
          % (Z, metros_por_pixel(-12)))
    print()
    print("  %-16s %8s %8s %8s" % ("", "medido", "publicado", "error"))
    for (n, _, _, r), a, e in zip(CONOCIDAS, alt, err):
        print("  %-16s %8.0f %8.0f %+8.0f" % (n, a, r, e))
    print()
    print("  error absoluto mediano : %6.0f m" % np.median(np.abs(err)))
    print("  error absoluto p90     : %6.0f m"
          % np.percentile(np.abs(err), 90))
    print("  sesgo (media)          : %+6.0f m" % err.mean())
    sierra = ref >= 2300
    print("  mediano en sierra      : %6.0f m  (%d casos sobre 2,300 m)"
          % (np.median(np.abs(err[sierra])), sierra.sum()))
    print("  mediano en costa/selva : %6.0f m  (%d casos)"
          % (np.median(np.abs(err[~sierra])), (~sierra).sum()))
    return 0


if __name__ == "__main__":
    raise SystemExit(validar())
