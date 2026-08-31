# -*- coding: utf-8 -*-
"""Extrae la red vial principal para dibujarla en el mapa.

El mapa mostraba dónde hay mercado pero no por qué unos valles son accesibles y
otros no. La carretera es la explicación, y verla convierte el mapa de un
gráfico de datos en algo que se puede leer geográficamente.

Aquí la geometría es decorativa, no se rutea sobre ella, así que se simplifica
con fuerza: el trazo se reduce con Douglas-Peucker a una tolerancia de unos
500 metros y las coordenadas se redondean a tres decimales —unos 110 metros—,
que es más precisión de la que un trazo de un píxel puede mostrar.

Tres niveles, porque no todas pesan igual en la lectura:
    1  autopistas y troncales — la Panamericana, la Central, la Interoceánica
    2  primarias — la red que une capitales de provincia
    3  secundarias — solo se dibujan con zoom
"""
import glob
import json
import os

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

NIVEL = {
    "motorway": 1, "motorway_link": 1, "trunk": 1, "trunk_link": 1,
    "primary": 2, "primary_link": 2,
    "secondary": 3, "secondary_link": 3,
}
TOLERANCIA = {1: 0.004, 2: 0.006, 3: 0.010}     # grados; ~450 a 1100 m
DEC = 3

# Las vías nacionales llevan referencia (PE-1N, PE-3S...). Se conserva para
# poder etiquetar las troncales en el mapa.
tramos = {1: [], 2: [], 3: []}
refs = {}

for f in sorted(glob.glob("data/vial/PE-*.json")):
    for e in json.load(open(f, encoding="utf-8"))["elements"]:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        n = NIVEL.get(t.get("highway", ""))
        if not n:
            continue
        tramos[n].append(LineString([(p["lon"], p["lat"]) for p in g]))

        ref = (t.get("ref") or "").strip()
        if ref and n == 1:
            m = g[len(g) // 2]
            refs.setdefault(ref.split(";")[0],
                            [round(m["lon"], DEC), round(m["lat"], DEC)])

# OSM parte cada vía en los cruces, de modo que la Panamericana llega como
# miles de segmentos de dos puntos. Unirlos antes de simplificar evita
# repetir el extremo compartido de cada par y permite que Douglas-Peucker
# trabaje sobre el trazo completo y no sobre fragmentos.
niveles = {}
for n in (1, 2, 3):
    unido = linemerge(tramos[n]) if tramos[n] else MultiLineString([])
    partes = list(unido.geoms) if unido.geom_type == "MultiLineString" else [unido]
    salida_n = []
    for linea in partes:
        linea = linea.simplify(TOLERANCIA[n], preserve_topology=False)
        if linea.is_empty or len(linea.coords) < 2:
            continue
        pts = [[round(x, DEC), round(y, DEC)] for x, y in linea.coords]
        limpio = [pts[0]]
        for q in pts[1:]:
            if q != limpio[-1]:
                limpio.append(q)
        if len(limpio) >= 2:
            salida_n.append(limpio)
    niveles[n] = salida_n

salida = {
    "niveles": {str(k): v for k, v in niveles.items()},
    "refs": [{"ref": r, "lon": c[0], "lat": c[1]} for r, c in
             sorted(refs.items())[:40]],
}
with open("out/vial_mapa.json", "w", encoding="utf-8") as fh:
    json.dump(salida, fh, separators=(",", ":"), ensure_ascii=False)

kb = os.path.getsize("out/vial_mapa.json") / 1024
print(f"vial_mapa.json : {kb:,.0f} KB")
for n, nombre in ((1, "troncales"), (2, "primarias"), (3, "secundarias")):
    pts = sum(len(t) for t in niveles[n])
    print(f"  nivel {n} {nombre:12s} {len(tramos[n]):>6,} vias OSM -> "
          f"{len(niveles[n]):>5,} trazos  {pts:>7,} puntos")
print(f"  referencias etiquetables: {len(salida['refs'])}")
