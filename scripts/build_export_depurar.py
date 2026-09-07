# -*- coding: utf-8 -*-
"""Quita del archivo de exportación lo que no debería sumarse dos veces.

El total salía 25% por encima de lo que publica MIDAGRI, y contrastarlo contra
esa cifra —que es lo que nadie había hecho— destapó dos cosas distintas en el
archivo de SUNAT. Ninguna es un error de este proyecto; las dos vienen en el
DBF y hay que decidir qué hacer con ellas.

**Filas repetidas.** El manifiesto trae la misma línea dos veces: misma
aduana, mismo año, misma declaración, misma serie, mismo FOB y mismo peso. A
veces dentro del mismo archivo semanal y a veces republicada en el siguiente.
Sumarlas dos veces infla el total sin que se note, porque cada una parece una
operación legítima. Se descartan: una serie de una declaración es un hecho, y
un hecho ocurre una vez.

**Precios que el producto no aguanta.** Una declaración de café verde declara
US$ 37.4 millones por 56,925 kg —US$ 657 el kilo— cuando la serie anterior del
mismo documento va a US$ 8.7. No se descarta por ser cara: la semilla híbrida
de hortaliza cuesta legítimamente cientos de dólares el kilo y sería un error
borrarla. Se compara cada línea contra **la mediana de su propia familia**, que
es lo que sabe cuánto vale un kilo de esa cosa, y se aparta lo que la supera
por más de `VECES`.

Lo apartado no se pierde: va contado y con su motivo a `depuracion.json`, para
que la diferencia con la cifra oficial se pueda seguir línea por línea.

Uso:
    python scripts/build_export_depurar.py
"""
import io
import json
import os
import sys

import pandas as pd

PROC = "data/exportaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones.csv")
SALIDA = os.path.join(PROC, "operaciones_limpias.csv")
INFORME = os.path.join(PROC, "depuracion.json")
VECES = 50          # cuántas medianas de su familia puede valer un kilo
CLAVE = ["declaracion", "fob_usd", "peso_neto_kg"]

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_export_historico.py")
    # Todo como texto y solo lo que hay que comparar como número. Leerlo
    # «como venga» convertía el ubigeo 150812 en 150812.0 y el corte
    # territorial se quedaba sin un solo departamento: este archivo se
    # reescribe entero, así que cualquier reformateo silencioso viaja al
    # resto del pipeline.
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig", low_memory=False, dtype=str)
    for col in ("fob_usd", "peso_neto_kg"):
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    n0, fob0 = len(d), float(d.fob_usd.sum())

    # ------------------------------------------------------- repetidas --
    rep = d.duplicated(subset=CLAVE, keep="first")
    fob_rep = float(d.loc[rep, "fob_usd"].sum())
    por_anio_rep = (d.loc[rep].groupby("anio").fob_usd.sum() / 1e6).round(1)
    d = d[~rep].copy()

    # -------------------------------------------- precios imposibles --
    # La mediana se calcula sobre lo que ya quedó limpio de repetidas y con
    # peso declarado: sin peso no hay precio que comparar.
    con = d.peso_neto_kg > 0
    d["_usd_kg"] = (d.fob_usd / d.peso_neto_kg).where(con)
    med = d.groupby("familia")._usd_kg.transform("median")
    atipica = con & (d._usd_kg > VECES * med) & med.notna() & (med > 0)
    fob_at = float(d.loc[atipica, "fob_usd"].sum())
    det_at = (d.loc[atipica].groupby("familia")
              .agg(lineas=("fob_usd", "size"), fob=("fob_usd", "sum"))
              .sort_values("fob", ascending=False))
    d = d[~atipica].drop(columns=["_usd_kg"])

    d.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    fob1 = float(d.fob_usd.sum())
    inf = {
        "entrada": {"lineas": n0, "fob": round(fob0, 2)},
        "salida": {"lineas": int(len(d)), "fob": round(fob1, 2)},
        "repetidas": {
            "motivo": "la misma serie de la misma declaración aparece más de "
                      "una vez en el archivo de SUNAT, a veces dentro del "
                      "mismo ZIP y a veces republicada en el siguiente",
            "clave": CLAVE,
            "lineas": int(rep.sum()), "fob": round(fob_rep, 2),
            "fob_por_anio_mm": {k: float(v) for k, v in por_anio_rep.items()},
        },
        "precio_imposible": {
            "motivo": "US$/kg mayor a %d veces la mediana de su propia "
                      "familia; el umbral es por familia porque la semilla "
                      "híbrida cuesta cientos de dólares el kilo con toda "
                      "legitimidad y el café no" % VECES,
            "veces": VECES,
            "lineas": int(atipica.sum()), "fob": round(fob_at, 2),
            "por_familia": [{"n": k, "lineas": int(r.lineas),
                             "fob": round(float(r.fob), 2)}
                            for k, r in det_at.head(10).iterrows()],
        },
    }
    with io.open(INFORME, "w", encoding="utf-8") as fh:
        json.dump(inf, fh, ensure_ascii=False, separators=(",", ":"))

    print("entrada           : {:,} lineas · US$ {:,.0f} MM".format(n0, fob0/1e6))
    print("repetidas         : {:,} lineas · US$ {:,.0f} MM ({:.1f}%)".format(
        int(rep.sum()), fob_rep/1e6, 100*fob_rep/fob0))
    print("precio imposible  : {:,} lineas · US$ {:,.0f} MM ({:.1f}%)".format(
        int(atipica.sum()), fob_at/1e6, 100*fob_at/fob0))
    for k, r in det_at.head(4).iterrows():
        print("    {:<38} {:>4,} lineas · {:>6,.0f} MM".format(
            str(k)[:38], int(r.lineas), r.fob/1e6))
    print("salida            : {:,} lineas · US$ {:,.0f} MM".format(len(d), fob1/1e6))
    print("archivo           : {:.0f} MB".format(os.path.getsize(SALIDA)/1e6))
    for a in ("2024", "2025"):
        v = d[d.anio == a].fob_usd.sum()/1e6
        print("  {} depurado     : US$ {:,.0f} MM".format(a, v))


if __name__ == "__main__":
    main()
