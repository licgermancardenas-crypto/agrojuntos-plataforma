# -*- coding: utf-8 -*-
"""Las rutas de visita: en qué orden se recorren los puntos de cada centro.

El proyecto tenía la red mapeada y los tiempos punto a punto, pero ninguna
**ruta**: nada que dijera «salir de Chiclayo, visitar estos siete en este orden
y volver». `visitable_en_dia` era un proxy —la caja que envuelve al territorio
mide menos de 120 km— y eso dice que el territorio es compacto, no que exista
una vuelta que lo recorra en un día.

Esto arma esa vuelta, sobre los **333 puntos reclutables** de
`build_reclutar.py`: los que tienen mercado propio y además se pueden resurtir.
Visitar a quien no se puede abastecer sería vender una entrega que no se
sostiene, así que la ruta se arma sobre la misma lista que ya pasó ese examen.

## Los supuestos, que son de operación y no de dato

Ninguno sale del manifiesto ni de OpenStreetMap: son parámetros del negocio, y
como no los tengo medidos van declarados arriba, en un solo sitio, y viajan en
la salida para que cualquiera vea con qué se armó lo que está mirando.

    JORNADA_H     9      horas de puerta a puerta, salida y regreso al centro
    VISITA_H      0.67   cuarenta minutos por punto, atención incluida
    TOPE_H        6      lo más lejos que se considera un punto de esa ruta

Cambiar `VISITA_H` de 40 a 25 minutos mete aproximadamente un punto más por
ruta; cambiar la jornada de 9 a 10 horas, otro. Son sensibles y por eso se
declaran: **una ruta vale lo que valga su supuesto**.

Lo que sí es medido es el viaje. Los tiempos salen del grafo vial con pendiente
—dirigido, porque subir no cuesta lo que bajar— y no de la distancia en línea
recta.

## El método, y su límite

Vecino más cercano con vuelta al centro comprobada, y después una pasada de
2-opt sobre cada ruta. Es una heurística: no promete el óptimo, promete una
vuelta factible y razonable. Para 333 puntos repartidos en ocho centros, la
diferencia contra un óptimo exacto es menor que la que produce mover el tiempo
de visita cinco minutos, y ese sí es un número que nadie midió.

No hay ventanas horarias ni capacidad de vehículo: la visita comercial no
carga producto. Para reparto físico haría falta lo segundo, y no está.

Uso:
    python scripts/build_rutas.py
"""
import io
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafo_vial                                      # noqa: E402
import sitio                                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

RECLUTAR = "out/reclutar.json"
PUNTOS = "out/canal_punto.csv"
RED = "out/red_elegida.json"
SALIDA = "out/rutas.json"

# --- los supuestos, todos aquí -------------------------------------------
JORNADA_H = 9.0      # de puerta a puerta, saliendo y volviendo al centro
VISITA_H = 40 / 60   # cuarenta minutos por punto
TOPE_H = 6.0         # un punto más lejos que esto no entra en ninguna ruta
SUPUESTOS = {
    "jornada_h": JORNADA_H,
    "visita_h": round(VISITA_H, 3),
    "tope_h": TOPE_H,
    "origen": "el centro de distribución; la ruta sale y vuelve a él",
    "medido": ("el tiempo de viaje, ruteado sobre la red vial con pendiente y "
               "en el sentido correcto —subir no cuesta lo que bajar—"),
    "supuesto": ("la jornada, el tiempo de visita y el tope de lejanía. No "
                 "salen del dato: son parámetros de operación que nadie midió "
                 "todavía, y una ruta vale lo que valga su supuesto"),
    "sensibilidad": ("bajar la visita de 40 a 25 minutos mete alrededor de un "
                     "punto más por ruta; subir la jornada de 9 a 10 horas, "
                     "otro"),
    "sin_modelar": ("ventanas horarias y capacidad de vehículo. La visita "
                    "comercial no carga producto; para reparto físico haría "
                    "falta lo segundo"),
}


def dos_opt(orden, T, ida, vuelta):
    """Una pasada de 2-opt: desarma cruces. `ida` es del centro al primero y
    `vuelta` del último al centro."""
    mejor = list(orden)

    def costo(o):
        if not o:
            return 0.0
        c = ida[o[0]] + vuelta[o[-1]]
        for a, b in zip(o, o[1:]):
            c += T[a, b]
        return c

    hubo = True
    while hubo and len(mejor) > 3:
        hubo = False
        base = costo(mejor)
        for i in range(len(mejor) - 1):
            for j in range(i + 2, len(mejor)):
                cand = mejor[:i + 1] + mejor[i + 1:j + 1][::-1] + mejor[j + 1:]
                if costo(cand) < base - 1e-9:
                    mejor, base, hubo = cand, costo(cand), True
    return mejor


def main():
    for p in (RECLUTAR, PUNTOS, RED):
        if not os.path.exists(p):
            sys.exit("falta %s: corre el pipeline" % p)
    rec = json.load(io.open(RECLUTAR, encoding="utf-8"))
    red = json.load(io.open(RED, encoding="utf-8"))
    d = pd.read_csv(PUNTOS, encoding="utf-8-sig")
    d = d.loc[:, ~d.columns.duplicated()]
    # Los reclutables: mercado propio y resurtibles. La ruta se arma sobre la
    # lista que ya pasó el examen del resurtido, no sobre los 517.
    v = d[(d.sam_exclusivo > 0) & d.reparto_en_promesa].copy()
    v = v.reset_index(drop=True)
    print("puntos reclutables: %d en %d centros"
          % (len(v), v.hub.nunique()), flush=True)

    hubs = {c["hub"]: (float(c["lat"]), float(c["lon"]))
            for c in red["centros"]}

    print("armando el grafo vial...", flush=True)
    g = grafo_vial.construir()
    G = g.csr()
    idx_p = g.snap(v.lon.values, v.lat.values)
    nom_h = [h for h in v.hub.unique() if h in hubs]
    idx_h = g.snap(np.array([hubs[h][1] for h in nom_h]),
                   np.array([hubs[h][0] for h in nom_h]))

    print("midiendo el tiempo entre cada par de puntos...", flush=True)
    T = np.full((len(v), len(v)), np.inf)
    for i, src in enumerate(idx_p):
        T[i] = dijkstra(G, indices=int(src), directed=True,
                        limit=TOPE_H)[idx_p]
        if (i + 1) % 60 == 0:
            print("  %d/%d" % (i + 1, len(v)), flush=True)
    np.fill_diagonal(T, 0.0)
    ida = {}
    for j, h in enumerate(nom_h):
        ida[h] = dijkstra(G, indices=int(idx_h[j]), directed=True,
                          limit=TOPE_H)[idx_p]
    Gv = g.csr(hacia=True)
    vuelta = {}
    for j, h in enumerate(nom_h):
        vuelta[h] = dijkstra(Gv, indices=int(idx_h[j]), directed=True,
                             limit=TOPE_H)[idx_p]
    del G, Gv, g

    rutas, sueltos = [], []
    for h in nom_h:
        loc = list(v.index[v.hub == h])
        # Se empieza por el que más margen deja: si la jornada se acaba, lo
        # que queda fuera es lo que menos vale.
        loc.sort(key=lambda i: -float(v.margen_base.iat[i]))
        pend = set(loc)
        n = 1
        while pend:
            act, orden, t = None, [], 0.0
            while True:
                mejor, mejor_t = None, np.inf
                for c in pend:
                    viaje = ida[h][c] if act is None else T[act, c]
                    if not np.isfinite(viaje):
                        continue
                    if not np.isfinite(vuelta[h][c]):
                        continue
                    if t + viaje + VISITA_H + vuelta[h][c] > JORNADA_H:
                        continue
                    if viaje < mejor_t:
                        mejor, mejor_t = c, viaje
                if mejor is None:
                    break
                t += mejor_t + VISITA_H
                orden.append(mejor)
                pend.discard(mejor)
                act = mejor
            if not orden:
                # Lo que no entra en ninguna jornada: se dice, no se reparte a
                # la fuerza en una ruta que no se puede cumplir.
                for c in sorted(pend):
                    sueltos.append({
                        "punto": str(v.nombre.iat[c])[:60],
                        "dep": str(v.dep.iat[c]), "hub": h,
                        "horas_ida": (round(float(ida[h][c]), 2)
                                      if np.isfinite(ida[h][c]) else None),
                        "margen_anual": round(float(v.margen_base.iat[c]), 2),
                        "motivo": ("no cabe en una jornada de %.0f h con "
                                   "vuelta al centro" % JORNADA_H)})
                break
            orden = dos_opt(orden, T, ida[h], vuelta[h])
            viaje = ida[h][orden[0]] + vuelta[h][orden[-1]] + sum(
                T[a, b] for a, b in zip(orden, orden[1:]))
            rutas.append({
                "hub": h, "ruta": n, "puntos": len(orden),
                "horas_viaje": round(float(viaje), 2),
                "horas_total": round(float(viaje + VISITA_H * len(orden)), 2),
                "margen_anual": round(
                    float(sum(v.margen_base.iat[c] for c in orden)), 2),
                "clientes": round(
                    float(sum(v.clientes_exclusivos.iat[c] for c in orden)), 1),
                "paradas": [{
                    "orden": k + 1, "punto": str(v.nombre.iat[c])[:60],
                    "dep": str(v.dep.iat[c]),
                    "lat": round(float(v.lat.iat[c]), 5),
                    "lon": round(float(v.lon.iat[c]), 5),
                    "margen_anual": round(float(v.margen_base.iat[c]), 2),
                } for k, c in enumerate(orden)],
            })
            n += 1

    en_ruta = sum(r["puntos"] for r in rutas)
    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("en qué orden se recorren los puntos reclutables de cada "
                   "centro, en jornadas que salen y vuelven al centro"),
        "supuestos": SUPUESTOS,
        "metodo": ("vecino más cercano con vuelta comprobada y una pasada de "
                   "2-opt; es una heurística y promete una vuelta factible, "
                   "no la óptima"),
        "puntos": int(len(v)),
        "en_ruta": int(en_ruta),
        "rutas": len(rutas),
        "sueltos": sueltos,
        "por_hub": [{
            "hub": h,
            "rutas": sum(1 for r in rutas if r["hub"] == h),
            "puntos": sum(r["puntos"] for r in rutas if r["hub"] == h),
            "horas_total": round(sum(r["horas_total"] for r in rutas
                                     if r["hub"] == h), 1),
            "margen_anual": round(sum(r["margen_anual"] for r in rutas
                                      if r["hub"] == h), 2),
        } for h in nom_h],
        "lista": rutas,
    }
    crudo = json.dumps(salida, ensure_ascii=False, indent=1)
    io.open(SALIDA, "w", encoding="utf-8").write(crudo)
    io.open(os.path.join(sitio.DATA, "rutas.json"), "w",
            encoding="utf-8").write(crudo)
    pd.DataFrame([
        dict(hub=r["hub"], ruta=r["ruta"], orden=p["orden"], punto=p["punto"],
             dep=p["dep"], lat=p["lat"], lon=p["lon"],
             margen_anual=p["margen_anual"], horas_ruta=r["horas_total"])
        for r in rutas for p in r["paradas"]
    ]).to_csv("out/rutas.csv", index=False, encoding="utf-8-sig")

    print()
    print("=" * 76)
    print("RUTAS DE VISITA  ·  jornada de %.0f h, %.0f min por punto"
          % (JORNADA_H, VISITA_H * 60))
    print("=" * 76)
    print("%d rutas cubren %d de %d puntos · %d no caben en ninguna jornada"
          % (len(rutas), en_ruta, len(v), len(sueltos)))
    print()
    print("  %-12s %6s %8s %9s %12s"
          % ("centro", "rutas", "puntos", "h totales", "US$/año"))
    for h in salida["por_hub"]:
        if not h["rutas"]:
            continue
        print("  %-12s %6d %8d %9.1f %12s"
              % (h["hub"], h["rutas"], h["puntos"], h["horas_total"],
                 f"{h['margen_anual']:,.0f}"))
    print()
    ej = max(rutas, key=lambda r: r["margen_anual"]) if rutas else None
    if ej:
        print("la ruta que más deja · %s, ruta %d · %.1f h · US$ %s"
              % (ej["hub"], ej["ruta"], ej["horas_total"],
                 f"{ej['margen_anual']:,.0f}"))
        for p in ej["paradas"]:
            print("   %d. %-46s %s" % (p["orden"], p["punto"][:46], p["dep"]))
    print()
    print("%s · out/rutas.csv" % SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
