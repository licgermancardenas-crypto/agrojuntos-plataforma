# -*- coding: utf-8 -*-
"""Quita del archivo de exportación lo que no debería sumarse dos veces.

El total salía 25% por encima de lo que publica MIDAGRI, y contrastarlo contra
esa cifra —que es lo que nadie había hecho— destapó dos cosas distintas en el
archivo de SUNAT. Ninguna es un error de este proyecto; las dos vienen en el
DBF y hay que decidir qué hacer con ellas.

**Declaraciones republicadas.** Esto es lo gordo, y no se ve mirando el
archivo de una semana. SUNAT vuelve a publicar una declaración en semanas
posteriores con el valor rectificado: la misma aduana, el mismo año, la misma
declaración y la misma serie aparecen hasta media docena de veces, con el
mismo peso y un FOB que cambia unos miles de dólares. En 2025 eso alcanzaba al
**51% del valor**: 216,303 de 216,381 líneas repetidas estaban en archivos
distintos, y solo 78 dentro del mismo, así que una serie es una fila y toda
repetición es una versión nueva de la misma exportación.

Sumarlas todas contaba varias veces el mismo embarque e inflaba el total un
tercio. Se conserva **la última versión de cada serie**, que es la vigente.

**Precios que el producto no aguanta.** Una declaración de café verde declara
US$ 37.4 millones por 56,925 kg —US$ 657 el kilo— cuando la serie anterior del
mismo documento va a US$ 8.7. No se descarta por ser cara: la semilla híbrida
de hortaliza cuesta legítimamente cientos de dólares el kilo y sería un error
borrarla. Se compara cada línea contra **la mediana de su propia familia**, que
es lo que sabe cuánto vale un kilo de esa cosa, y se aparta lo que la supera
por más de `VECES`.

Lo apartado no se pierde: va contado y con su motivo a `depuracion.json`, para
que la diferencia con la cifra oficial se pueda seguir línea por línea.

## Por qué esto no carga el archivo

Al ampliar el universo arancelario `operaciones.csv` pasó de 750 a 927 MB, y
la versión anterior —que leía las treinta columnas en un DataFrame— murió con
`ArrowMemoryError` en una máquina con 480 MB libres. Aquí se leen **seis
columnas en tandas y en tipos compactos**: la declaración va como hash de 64
bits, la semana y la familia como códigos enteros, y de todo eso salen dos
máscaras de booleanos. Después el archivo se copia línea por línea con el
módulo `csv`, sin volver a cargarlo.

La declaración se compara por su hash y no por su texto, que es lo que ahorra
los cientos de megas. Con 1.9 millones de declaraciones distintas sobre 2^64
valores, la probabilidad de que dos choquen es del orden de 1 en 10 millones;
si chocaran, se perdería una línea. Es el precio de que esto corra, y queda
dicho.

Uso:
    python scripts/build_export_depurar.py
"""
import csv
import io
import json
import os
import sys

import numpy as np
import pandas as pd

PROC = "data/exportaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones.csv")
SALIDA = os.path.join(PROC, "operaciones_limpias.csv")
INFORME = os.path.join(PROC, "depuracion.json")
VECES = 50          # cuántas medianas de su familia puede valer un kilo
# La serie de una declaración: aduana-año-declaración-serie. Es la unidad de
# la exportación, y lo que se repite entre semanas son versiones de ella.
CLAVE = ["declaracion"]
# Las seis que deciden. El archivo tiene treinta.
LEE = ["declaracion", "semana_archivo", "anio", "familia", "fob_usd",
       "peso_neto_kg"]
TANDA = 250_000

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def leer():
    """Las seis columnas, en tandas y en tipos que caben.

    Devuelve los vectores en el orden físico del archivo, que es el orden en
    que después hay que copiarlo. `semana` y `familia` viajan como código
    entero de su valor; el código de la semana respeta el orden alfabético de
    la fecha, que es el que decide cuál es la última republicación.
    """
    dec, sem, anio, fam, fob, kg = [], [], [], [], [], []
    semanas, familias = {}, {}
    for ch in pd.read_csv(ENTRADA, encoding="utf-8-sig", usecols=LEE,
                          dtype=str, chunksize=TANDA):
        dec.append(pd.util.hash_array(
            ch["declaracion"].fillna("").to_numpy(dtype=object)))
        for v in ch["semana_archivo"].fillna(""):
            if v not in semanas:
                semanas[v] = len(semanas)
        for v in ch["familia"].fillna(""):
            if v not in familias:
                familias[v] = len(familias)
        sem.append(ch["semana_archivo"].fillna("").map(semanas)
                   .to_numpy(dtype="int32"))
        fam.append(ch["familia"].fillna("").map(familias)
                   .to_numpy(dtype="int32"))
        anio.append(pd.to_numeric(ch["anio"], errors="coerce")
                    .fillna(0).to_numpy(dtype="int16"))
        fob.append(pd.to_numeric(ch["fob_usd"], errors="coerce")
                   .fillna(0.0).to_numpy(dtype="float64"))
        kg.append(pd.to_numeric(ch["peso_neto_kg"], errors="coerce")
                  .fillna(0.0).to_numpy(dtype="float64"))
    # El código de la semana se reordena para que comparar códigos sea
    # comparar fechas: los archivos no llegan en orden y el código nace del
    # orden de aparición.
    orden_sem = {k: i for i, k in enumerate(sorted(semanas))}
    remap = np.empty(len(semanas), dtype="int32")
    for k, viejo in semanas.items():
        remap[viejo] = orden_sem[k]
    s = remap[np.concatenate(sem)]
    nombres = [None] * len(familias)
    for k, i in familias.items():
        nombres[i] = k
    return (np.concatenate(dec), s, np.concatenate(anio),
            np.concatenate(fam), np.concatenate(fob), np.concatenate(kg),
            nombres)


def copiar(entrada, salida, quedan):
    """Reescribe el CSV con las filas que `quedan` marca, sin cargarlo.

    El orden de `quedan` es el orden físico del archivo, que es el mismo que
    le da `read_csv` sin ordenar. Se copia la cabecera tal cual: la salida
    tiene las mismas columnas que la entrada, y el resto del pipeline las
    espera así.
    """
    n = 0
    fe = io.open(entrada, encoding="utf-8-sig", newline="")
    fs = io.open(salida, "w", encoding="utf-8-sig", newline="")
    with fe, fs:
        r = csv.reader(fe)
        w = csv.writer(fs, lineterminator="\n")
        w.writerow(next(r))
        for i, fila in enumerate(r):
            if quedan[i]:
                w.writerow(fila)
                n += 1
    return n


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_export_historico.py")
    dec, sem, anio, fam, fob, kg, familias = leer()
    n0, fob0 = len(dec), float(fob.sum())

    # ------------------------------------------------------- repetidas --
    # «La última» es la republicación más reciente, y para eso hay que
    # ordenar por la semana que trae la fila: el nombre del ZIP lleva el día
    # al principio y el año al final, así que el orden alfabético del archivo
    # no sirve. El desempate por posición reproduce el orden estable del
    # `sort_values` que esto reemplaza.
    pos = np.arange(n0)
    orden = np.lexsort((pos, sem, dec))
    d_ord = dec[orden]
    fin = np.empty(n0, dtype=bool)
    fin[-1] = True
    fin[:-1] = d_ord[1:] != d_ord[:-1]
    quedan = np.zeros(n0, dtype=bool)
    quedan[orden[fin]] = True
    del orden, d_ord, fin, pos, dec
    rep = ~quedan
    n_rep, fob_rep = int(rep.sum()), float(fob[rep].sum())
    por_anio_rep = (pd.Series(fob[rep]).groupby(anio[rep]).sum() / 1e6).round(1)

    # -------------------------------------------- precios imposibles --
    # La mediana se calcula sobre lo que ya quedó limpio de repetidas y con
    # peso declarado: sin peso no hay precio que comparar.
    con = quedan & (kg > 0)
    usd = np.full(n0, np.nan)
    usd[con] = fob[con] / kg[con]
    med_fam = (pd.Series(usd[con]).groupby(fam[con]).median()
               .reindex(range(len(familias))))
    med = med_fam.to_numpy()[fam]
    atipica = con & np.isfinite(med) & (med > 0) & (usd > VECES * med)
    n_at, fob_at = int(atipica.sum()), float(fob[atipica].sum())
    det_at = (pd.DataFrame({"fam": fam[atipica], "fob": fob[atipica]})
              .groupby("fam").agg(lineas=("fob", "size"), fob=("fob", "sum"))
              .sort_values("fob", ascending=False))
    quedan &= ~atipica
    fob1 = float(fob[quedan].sum())
    por_anio = (pd.Series(fob[quedan]).groupby(anio[quedan]).sum() / 1e6)
    del con, usd, med, atipica, rep, fam, kg, fob, anio

    n1 = copiar(ENTRADA, SALIDA, quedan)
    if n1 != int(quedan.sum()):
        sys.exit("la copia escribió %d filas y el filtro marcó %d: el archivo "
                 "cambió debajo" % (n1, int(quedan.sum())))
    inf = {
        "entrada": {"lineas": n0, "fob": round(fob0, 2)},
        "salida": {"lineas": int(n1), "fob": round(fob1, 2)},
        "repetidas": {
            "motivo": "SUNAT republica la declaración en semanas posteriores "
                      "con el valor rectificado; se conserva la última "
                      "versión de cada serie, que es la vigente",
            "clave": CLAVE,
            "lineas": n_rep, "fob": round(fob_rep, 2),
            "fob_por_anio_mm": {str(k): float(v)
                                for k, v in por_anio_rep.items()},
        },
        "precio_imposible": {
            "motivo": "US$/kg mayor a %d veces la mediana de su propia "
                      "familia; el umbral es por familia porque la semilla "
                      "híbrida cuesta cientos de dólares el kilo con toda "
                      "legitimidad y el café no" % VECES,
            "veces": VECES,
            "lineas": n_at, "fob": round(fob_at, 2),
            "por_familia": [{"n": familias[k], "lineas": int(r.lineas),
                             "fob": round(float(r.fob), 2)}
                            for k, r in det_at.head(10).iterrows()],
        },
    }
    with io.open(INFORME, "w", encoding="utf-8") as fh:
        json.dump(inf, fh, ensure_ascii=False, separators=(",", ":"))

    print("entrada           : {:,} lineas · US$ {:,.0f} MM".format(n0, fob0/1e6))
    print("repetidas         : {:,} lineas · US$ {:,.0f} MM ({:.1f}%)".format(
        n_rep, fob_rep/1e6, 100*fob_rep/fob0))
    print("precio imposible  : {:,} lineas · US$ {:,.0f} MM ({:.1f}%)".format(
        n_at, fob_at/1e6, 100*fob_at/fob0))
    for k, r in det_at.head(4).iterrows():
        print("    {:<38} {:>4,} lineas · {:>6,.0f} MM".format(
            str(familias[k])[:38], int(r.lineas), r.fob/1e6))
    print("salida            : {:,} lineas · US$ {:,.0f} MM".format(n1, fob1/1e6))
    print("archivo           : {:.0f} MB".format(os.path.getsize(SALIDA)/1e6))
    for a in (2024, 2025):
        print("  {} depurado     : US$ {:,.0f} MM".format(
            a, por_anio.get(a, 0.0)))


if __name__ == "__main__":
    main()
