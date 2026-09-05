# -*- coding: utf-8 -*-
"""Clasifica cada operación de importación en la categoría que usa el agro.

La regla es una sola y ordena todo lo demás: **manda el arancel, la descripción
solo desempata**. La subpartida NANDINA es una clasificación con autoridad, la
descripción la escribe el declarante y dice lo que quiere. Así que primero se
decide por subpartida, y el texto solo se usa para partir *dentro* de lo que la
subpartida ya permite.

El caso que muestra por qué. La subpartida 3808.93 se llama, textualmente,
«herbicidas, inhibidores de germinación y reguladores del crecimiento de las
plantas»: son tres cosas en un mismo casillero y el arancel no las separa. Ahí
sí corresponde mirar la descripción, y cuando dice GIBERELICO o PACLOBUTRAZOL
es un regulador y no un herbicida. Se comprobó que funciona: de los US$ 14.3 MM
que mencionan «regulador», 13.6 caen en 3808.93. La palabra confirma lo que la
partida ya insinuaba, que es la única situación en que una palabra decide algo.

Al revés no: nada que la partida clasifique con precisión se reasigna por
texto. Un 3808.92 es fungicida aunque el declarante escriba «producto agrícola».

Dos categorías que se pensaron y no sobrevivieron a los datos:

  adyuvantes      viven en la partida 3402, que resultó ser jabón de lavar
                  ropa. Quedó fuera del universo en build_import_historico.py.
  micronutrientes US$ 0.5 MM en cuarenta semanas. Demasiado poco para una
                  categoría propia; van dentro de nutrición vegetal.

Uso:
    python scripts/build_import_clasificar.py
"""
import io
import os
import re
import sys

import pandas as pd

PROC = "data/importaciones/processed"
OPERS = os.path.join(PROC, "operaciones.csv")
SALIDA = os.path.join(PROC, "operaciones_clasificadas.csv")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

# ---- nivel 1: la subpartida decide -----------------------------------------
# El prefijo mas largo que calce es el que manda, de modo que 380893 gana sobre
# 3808 y 3808 sobre 38.
POR_PARTIDA = {
    "380891": "Insecticidas",
    "380892": "Fungicidas",
    "380893": "Herbicidas",
    "380894": "Desinfectantes agricolas",
    "380899": "Otros fitosanitarios",
    "380852": "Fitosanitarios restringidos",
    "380859": "Fitosanitarios restringidos",
    "380861": "Fitosanitarios restringidos",
    "380862": "Fitosanitarios restringidos",
    "380869": "Fitosanitarios restringidos",
    "3808":   "Otros fitosanitarios",
    "3101":   "Fertilizantes organicos",
    "3102":   "Fertilizantes nitrogenados",
    "3103":   "Fertilizantes fosfatados",
    "3104":   "Fertilizantes potasicos",
    "3105":   "Fertilizantes compuestos",
    "1209":   "Semillas",
    "0601":   "Plantines y bulbos",
    "0602":   "Plantines y bulbos",
}

# ---- nivel 2: la descripcion parte lo que la subpartida junta ---------------
# Cada regla declara en que partidas puede actuar. Fuera de ellas no se aplica,
# que es lo que impide que una palabra pise una clasificacion arancelaria buena.
REGLAS = [
    ("Reguladores de crecimiento", ("380893",),
     r"REGULADOR DE CRECIMIENTO|REGULADOR DEL CRECIMIENTO|GIBERELIC|"
     r"PACLOBUTRAZOL|ETHEPHON|ETEFON|CITOQUININ|AUXINA|BRASINO|"
     r"ACIDO GIBERELICO"),
    ("Biologicos", ("3808",),
     r"BACILLUS|TRICHODERMA|BEAUVERIA|METARHIZIUM|BACULOVIRUS|PAECILOMYCES|"
     r"MICORRIZ|RHIZOBIUM|BIOFUNGICIDA|BIOINSECTICIDA|BIOLOGICO"),
    ("Nematicidas", ("380891", "380899"),
     r"NEMATICIDA|NEMATODO|\bNEMATA"),
    ("Bioestimulantes", ("3101", "3105"),
     r"BIOESTIMULANT|ESTIMULANTE|EXTRACTO DE ALGA|ALGA MARINA|AMINOACID|"
     r"ACIDO HUMICO|ACIDOS HUMICOS|HUMICO|FULVICO"),
    ("Fertilizantes foliares", ("3105",), r"FOLIAR"),
    ("Nutricion vegetal", ("3105",),
     r"QUELAT|MICRONUTRIENTE|SULFATO DE ZINC|MANGANESO|MOLIBDEN"),
]


def categoria_base(p10):
    for n in (6, 4):
        c = POR_PARTIDA.get(str(p10)[:n])
        if c:
            return c
    return "Otros insumos"


def main():
    if not os.path.exists(OPERS):
        sys.exit(f"falta {OPERS}: corre build_import_historico.py primero")
    # anio y mes se leen como texto o pandas los convierte a entero y «01»
    # vuelve como «1»: el mes pierde el cero a la izquierda al pasar por aqui y
    # cualquier clave «2026-01» deja de calzar mas adelante.
    d = pd.read_csv(OPERS, encoding="utf-8-sig",
                    dtype={"ruc": str, "partida": str, "partida4": str,
                           "anio": str, "mes": str, "aduana": str,
                           "declaracion": str},
                    low_memory=False)
    print(f"operaciones a clasificar: {len(d):,}")

    d["categoria"] = d.partida.map(categoria_base)
    d["clasificada_por"] = "partida"

    txt = (d.descripcion.fillna("") + " " + d.desc_materia.fillna("") + " "
           + d.desc_uso.fillna("")).str.upper()
    for nombre, prefijos, patron in REGLAS:
        alcance = d.partida.str.startswith(tuple(prefijos))
        pega = alcance & txt.str.contains(patron, regex=True, na=False)
        d.loc[pega, "categoria"] = nombre
        d.loc[pega, "clasificada_por"] = "partida + descripcion"

    d.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    print(f"\n{'categoria':<30}{'ops':>8}{'FOB MM':>10}{'%':>7}  como")
    tot = d.fob_usd.sum()
    g = d.groupby("categoria").agg(n=("fob_usd", "size"), fob=("fob_usd", "sum"))
    for c, r in g.sort_values("fob", ascending=False).iterrows():
        como = d[d.categoria == c].clasificada_por.mode().iat[0]
        print(f"{c:<30}{int(r.n):>8,}{r.fob/1e6:>9.1f}{100*r.fob/tot:>6.1f}%  {como}")
    print(f"{'TOTAL':<30}{len(d):>8,}{tot/1e6:>9.1f}{100:>6.1f}%")

    por_desc = (d.clasificada_por == "partida + descripcion").sum()
    print(f"\nclasificadas solo por arancel : {len(d)-por_desc:,} "
          f"({100*(len(d)-por_desc)/len(d):.1f}%)")
    print(f"desempatadas por descripcion  : {por_desc:,} "
          f"({100*por_desc/len(d):.1f}%)")
    sin = (d.categoria == "Otros insumos").sum()
    if sin:
        print(f"sin categoria reconocida      : {sin:,}")


if __name__ == "__main__":
    main()
