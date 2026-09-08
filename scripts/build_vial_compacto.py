# -*- coding: utf-8 -*-
"""Convierte la red vial de Overpass a arreglos, una vez y para siempre.

`build_ruteo.py` leía los 239 MB de JSON con `json.load` en cada corrida. Eso
son unos cinco millones y medio de diccionarios `{"lat": .., "lon": ..}` vivos
a la vez, y en una máquina de 3.6 GB la corrida moría antes de llegar a rutear.
El JSON tampoco cambia: se baja de Overpass cada tanto y entre bajada y bajada
se releía entero decenas de veces.

Aquí se lee sin construir un solo diccionario —la salida de Overpass es
regular y se recorre con una expresión regular— y se guarda un `.npz` por
departamento con la coordenada ya cuantizada a entero. La red entera queda en
unos 45 MB de disco y se carga en segundos.

La cuantización a seis decimales no pierde nada: es la precisión con la que
Overpass entrega la coordenada, y es la misma que `build_ruteo.py` usaba para
decidir si dos puntos eran el mismo nodo.

Uso:
    python scripts/build_vial_compacto.py            solo lo que falte
    python scripts/build_vial_compacto.py --forzar   todo de nuevo
"""
import glob
import io
import os
import re
import sys

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

ORIGEN = "data/vial"
DESTINO = "data/vial/compacto"
DEC = 6

VEL_CLASE = {
    "motorway": 90, "motorway_link": 60, "trunk": 75, "trunk_link": 50,
    "primary": 60, "primary_link": 40, "secondary": 50, "secondary_link": 35,
    "tertiary": 40, "tertiary_link": 30,
}
FACTOR_SUP = {
    "asphalt": 1.00, "paved": 1.00, "concrete": 0.95, "paving_stones": 0.85,
    "compacted": 0.70, "gravel": 0.60, "fine_gravel": 0.65, "unpaved": 0.55,
    "ground": 0.45, "dirt": 0.45, "earth": 0.45, "sand": 0.35, "mud": 0.30,
}
FACTOR_SUP_DEF = 0.80

# Un elemento de Overpass: la geometría y, si las trae, las etiquetas. El
# `.*?` es perezoso a propósito —un `.*` se comería hasta el último corchete
# del archivo— y `re.S` porque el JSON viene en una sola línea o en varias
# según quién lo haya bajado.
VIA = re.compile(r'"geometry":\s*\[(.*?)\]'
                 r'(?:,\s*"tags":\s*\{(.*?)\})?\s*\}', re.S)
NUM = re.compile(r'-?\d+(?:\.\d+)?')
ETIQ = re.compile(r'"(highway|surface|maxspeed)":\s*"([^"]*)"')


def velocidad(tags):
    v = VEL_CLASE.get(tags.get("highway", "tertiary"), 35)
    v *= FACTOR_SUP.get(tags.get("surface", ""), FACTOR_SUP_DEF)
    m = re.match(r"(\d+)", tags.get("maxspeed", ""))
    if m:
        v = min(v, int(m.group(1)))
    return max(v, 8.0)


def convertir(ruta, destino):
    txt = io.open(ruta, encoding="utf-8").read()
    lons, lats, vels, cortes = [], [], [], [0]
    for m in VIA.finditer(txt):
        n = NUM.findall(m.group(1))
        if len(n) < 4:
            continue
        a = np.array(n, dtype=np.float64).reshape(-1, 2)   # lat, lon
        lats.append(np.round(a[:, 0] * 10 ** DEC).astype(np.int32))
        lons.append(np.round(a[:, 1] * 10 ** DEC).astype(np.int32))
        vels.append(velocidad(dict(ETIQ.findall(m.group(2) or ""))))
        cortes.append(cortes[-1] + len(a))
    del txt
    if not vels:
        return 0, 0
    np.savez_compressed(
        destino,
        lon=np.concatenate(lons), lat=np.concatenate(lats),
        vel=np.asarray(vels, dtype=np.float32),
        cut=np.asarray(cortes, dtype=np.int64))
    return len(vels), cortes[-1]


def main():
    forzar = "--forzar" in sys.argv
    os.makedirs(DESTINO, exist_ok=True)
    vias = puntos = 0
    for f in sorted(glob.glob(os.path.join(ORIGEN, "PE-*.json"))):
        dst = os.path.join(DESTINO,
                           os.path.basename(f).replace(".json", ".npz"))
        if not forzar and os.path.exists(dst) and \
                os.path.getmtime(dst) >= os.path.getmtime(f):
            d = np.load(dst)
            v, p = len(d["vel"]), int(d["cut"][-1])
            print("  %-22s ya estaba  %6d vias" % (os.path.basename(f), v))
        else:
            v, p = convertir(f, dst)
            print("  %-22s %6d vias  %9d puntos  %5.1f MB"
                  % (os.path.basename(f), v, p,
                     os.path.getsize(dst) / 1e6))
        vias += v
        puntos += p
    print("\n%d vias, %d puntos de geometria" % (vias, puntos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
