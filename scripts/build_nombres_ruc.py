# -*- coding: utf-8 -*-
"""El nombre completo, según el padrón de SUNAT, de cada RUC que el sitio muestra.

El manifiesto de aduanas corta la razón social en 40 caracteres; el padrón la
trae entera. Este script reúne los RUC de comercio exterior —exportadores,
importadores y las líneas de importación de donde salen los perfiles— y saca
del padrón su nombre. El resultado es una tabla chica que `nombres.py` lee.

El padrón son 390 MB comprimidos. Se lee línea por línea y sin pandas, y solo
se guarda lo que se busca: en esta máquina, cargarlo entero es la diferencia
entre terminar y que Windows mate el proceso.

Uso:
    python scripts/build_nombres_ruc.py
"""
import csv
import io
import os
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

ZIP = "data/sunat/ruc.zip"
FUENTES = ["out/comercio_exportadores.csv", "out/comercio_importadores.csv",
           "out/aduanas_importaciones.csv", "out/import_agro_lineas.csv"]
SALIDA = "out/nombres_ruc.csv"


def rucs_buscados():
    buscados = set()
    for f in FUENTES:
        with io.open(f, encoding="utf-8-sig", newline="") as fh:
            lector = csv.reader(fh)
            i = next(lector).index("ruc")
            for fila in lector:
                if len(fila) > i and fila[i].isdigit():
                    buscados.add(fila[i])
    return buscados


def main():
    buscados = rucs_buscados()
    print("RUC buscados        : %s" % format(len(buscados), ","))
    hallados = {}
    with zipfile.ZipFile(ZIP) as zf, zf.open(zf.namelist()[0]) as f:
        for linea in io.TextIOWrapper(f, encoding="latin-1", errors="replace"):
            ruc, _, resto = linea.partition("|")
            ruc = ruc.strip()
            if ruc in buscados:
                hallados[ruc] = resto.partition("|")[0].strip()
    tmp = SALIDA + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ruc", "razon_social"])
        for ruc in sorted(hallados):
            w.writerow([ruc, hallados[ruc]])
    os.replace(tmp, SALIDA)
    largos = sum(1 for n in hallados.values() if len(n) > 40)
    print("hallados en el padrón: %s" % format(len(hallados), ","))
    print("sin padrón           : %s (quedan con el nombre de aduanas)"
          % format(len(buscados - set(hallados)), ","))
    print("de más de 40 letras  : %s, los que aduanas cortaba"
          % format(largos, ","))


if __name__ == "__main__":
    main()
