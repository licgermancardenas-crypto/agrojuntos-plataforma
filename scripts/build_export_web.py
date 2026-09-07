# -*- coding: utf-8 -*-
"""Recorta el directorio de exportadores a lo que el navegador necesita.

`exportadores.json` pesa 7.7 MB porque lleva, por cada una de las 4,062
empresas, el cubo completo de producto × destino × partida año por año. Eso
está bien para el informe, que lo lee una vez desde el disco, y está mal para
una página web, que se lo haría descargar entero a cada visitante antes de
pintar la primera fila de una tabla.

Este recorte deja lo que la vista muestra —el ranking, la serie por año, el
origen declarado y los tres primeros productos y destinos de cada empresa— y
tira el resto. Un décimo del tamaño para lo mismo que se ve.

Lo que **no** se recorta es la advertencia: el archivo se lleva la cobertura
del ubigeo año por año y la frontera de completitud, porque una cifra sin su
salvedad viaja más rápido que la salvedad, y en una pantalla más todavía.

Uso:
    python scripts/build_export_web.py
"""
import io
import json
import os
import sys

PROC = "data/exportaciones/processed"
ENTRADA = os.path.join(PROC, "exportadores.json")
MERCADO = os.path.join(PROC, "mercado.json")
SALIDA = os.path.join(PROC, "exportadores_min.json")
TOPE = 3          # productos y destinos que se guardan de cada empresa

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def main():
    for p in (ENTRADA, MERCADO):
        if not os.path.exists(p):
            sys.exit("falta " + p + ": corre build_export_agregados.py")
    emp = json.load(io.open(ENTRADA, encoding="utf-8"))
    m = json.load(io.open(MERCADO, encoding="utf-8"))
    anios = m["anios_pedidos"]

    # Claves de una letra: con 4,062 filas, «razon_social» repetido 4,062 veces
    # pesa más que varios de los datos que nombra.
    fuera = []
    for r, e in emp.items():
        fila = {
            "r": r,
            "n": e["n"],
            "d": e["dep"],
            "t": round(e["total"]["fob"], 2),
            "o": e["total"]["ops"],
            "a": {a: round(e["por_anio"][a]["fob"], 2)
                  for a in anios if a in e["por_anio"]},
            "f": [{"n": x["n"], "v": round(x["fob"], 2)}
                  for x in e["familias"][:TOPE]],
            "p": [{"n": x["n"], "v": round(x["fob"], 2)}
                  for x in e["paises"][:TOPE]],
            # El conteo real, no el largo de la lista recortada a diez.
            "np": e["n_paises"], "nf": e["n_familias"],
            "de": e["primera"][:7], "ha": e["ultima"][:7],
        }
        fuera.append(fila)
    fuera.sort(key=lambda x: -x["t"])

    out = {
        "meta": {
            "generado": m["generado"],
            "fuente": m["fuente"],
            "ultimo_registro": m["ultimo_registro"],
            "anio_en_curso": m["anio_en_curso"],
            "anios": anios,
            "anios_con_dato": m["anios_con_dato"],
            "cobertura_semanas": m["cobertura_semanas"],
            "empresas": len(fuera),
            "reservado": m["reservado"],
            # Las dos salvedades que no pueden quedarse en el informe impreso.
            "frontera_completitud": m["rezago"]["frontera_completitud"],
            "completitud_mes": m["rezago"]["completitud_mes"],
            "umbral_completo_pct": m["rezago"]["umbral_completo_pct"],
            "ubigeo": {
                "motivo": m["departamentos"]["motivo"],
                "cobertura_fob_por_anio":
                    m["departamentos"]["cobertura_fob_por_anio"],
                "anios_usados": m["departamentos"]["anios_usados"],
                "advertencia": m["departamentos"]["advertencia"],
            },
        },
        "emp": fuera,
    }
    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    o, n = os.path.getsize(ENTRADA), os.path.getsize(SALIDA)
    print("empresas          : %s" % format(len(fuera), ","))
    print("origen            : %.2f MB  exportadores.json" % (o / 1e6))
    print("recorte           : %.2f MB  %s  (%.0f%% del original)"
          % (n / 1e6, os.path.basename(SALIDA), 100 * n / o))
    print("anios en la serie : %s" % anios)
    print("mayor             : %s · %s · US$ %.0f MM"
          % (fuera[0]["n"], fuera[0]["d"] or "sin origen",
             fuera[0]["t"] / 1e6))
    sin_dep = sum(1 for x in fuera if not x["d"])
    print("sin origen        : %s empresas (%.1f%%)"
          % (format(sin_dep, ","), 100 * sin_dep / len(fuera)))
    # La suma tiene que seguir cuadrando despues del recorte.
    t1 = sum(e["total"]["fob"] for e in emp.values())
    t2 = sum(x["t"] for x in fuera)
    print("cuadra el total   : %s" % ("OK" if abs(t1 - t2) < 1 else "NO CUADRA"))


if __name__ == "__main__":
    main()
