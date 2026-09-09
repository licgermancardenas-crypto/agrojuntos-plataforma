# -*- coding: utf-8 -*-
"""Qué compran las empresas que trajo el universo ampliado, y cuáles son cliente.

Ampliar el universo arancelario sumó **769 exportadores** que no aparecían en
ninguno de los siete capítulos originales, y la conclusión fácil era llamarlos
cartera nueva: US$ 3,650 MM de embarque que antes no se veían. Este archivo
cruza esos RUC contra lo que **importan**, que es lo único que dice si compran
lo que la plataforma vende, y la respuesta es que la mayoría no es cliente.

## Las tres cosas que resultaron ser

**La industria del insumo.** Importa fertilizante y fitosanitario para
revenderlo: BASF, Interoc, Montana, Neoagrum —cuatro de ellas ya están en el
ranking de protección de cultivos de este mismo proyecto—. No son clientes: son
el proveedor de quien vende, o la competencia de quien quiere vender. Se
reconocen porque están en el padrón de importadores de insumo *y* despachan
cincuenta veces o más al año: un fundo compra por campaña, no cada semana.

**El grano y el alimento balanceado.** ADM, Seaboard, Cargill, San Fernando,
Vitapro, Rinti: seis empresas son el 88% de los US$ 5,450 MM de insumo ganadero
que compra el grupo. Es su mayor compra con diferencia y **no está en el
catálogo**: torta de soya y maíz no son fertilizante ni fitosanitario.

**El resto.** Lo que queda después de sacar las dos anteriores, y hay que
mirarlo empresa por empresa antes de llamarlo cartera: lo encabeza una química
que compra insumo a granel en veintidós despachos al año, que tampoco es un
fundo aunque no revenda.

## Por qué el clasificador del proyecto no ayuda aquí

`build_empresas.py` clasifica por razón social —AGRICOLA, FUNDO,
AGROINDUSTRIAL— y eso funciona en el padrón agrario. Con estas no: **el 93% no
está clasificado**, porque se llaman Quimpac, Seaboard o Cargill. La ampliación
metió en el universo agro a empresas que el propio proyecto no reconoce como
agro por su nombre, y eso no es un error del clasificador sino la señal de que
son otra cosa.

## Lo que no hace

No decide. Publica el reparto con la regla con que se hizo, para que la
pregunta «¿qué hacemos con los 769?» del módulo de decisiones tenga cifra en
vez de entusiasmo.

Uso:
    python scripts/build_ampliacion.py
"""
import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tandas import leer_en_tandas                       # noqa: E402
from universo import ampliada                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

OPER = "data/exportaciones/processed/operaciones_limpias.csv"
SALIDA = "out/ampliacion.json"
# Cuántos despachos al año separan a quien compra para revender de quien compra
# para producir. Un fundo compra por campaña; un distribuidor, todas las
# semanas. El umbral es grueso a propósito y se declara.
DESPACHOS_REVENTA = 50


def main():
    d = leer_en_tandas(OPER, {"ruc": "category", "partida": "category",
                              "familia": "category", "fob_usd": "float64"})
    d = d[d.ruc.astype(str).str.fullmatch(r"\d{11}", na=False)]
    d["amp"] = d.partida.astype(str).map(ampliada)
    g = d.groupby("ruc", observed=True).agg(solo=("amp", "all"),
                                            fob=("fob_usd", "sum"))
    nuevos = set(g.index[g.solo].astype(str))
    fob_nuevos = float(g.fob[g.solo].sum())
    fam = (d[d.ruc.astype(str).isin(nuevos)]
           .groupby("familia", observed=True).fob_usd.sum()
           .nlargest(6) / 1e6).round(1)
    del d

    emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                      dtype={"ruc": str})
    clase = dict(zip(emp.ruc, emp.clase))
    ins = pd.read_csv("out/aduanas_importaciones.csv", encoding="utf-8-sig",
                      dtype={"ruc": str})
    imp = pd.read_csv("out/comercio_importadores.csv", encoding="utf-8-sig",
                      dtype={"ruc": str})
    otros = pd.read_csv("out/import_agro_lineas.csv", encoding="utf-8-sig",
                        dtype={"ruc": str})
    otros = otros[otros["categoria"] != "referencia"]

    a = (ins[ins.ruc.isin(nuevos)]
         .groupby(["ruc", "razon_social"])
         .agg(fob=("fob_usd", "sum"), despachos=("partida", "size"))
         .reset_index())
    a["clase"] = a.ruc.map(clase).fillna("sin clasificar")
    a["reventa"] = a.ruc.isin(set(imp.ruc)) & (a.despachos >= DESPACHOS_REVENTA)
    gan = (otros[(otros.categoria == "ganaderia") & otros.ruc.isin(nuevos)]
           .groupby(["ruc", "razon_social"]).fob_usd.sum()
           .sort_values(ascending=False))

    reventa, resto = a[a.reventa], a[~a.reventa]
    prod = [r for r in nuevos if clase.get(r) in ("productor", "agroindustria")]

    def top(df, col, n=6):
        return [{"n": str(r.razon_social)[:46], "fob": round(float(r[col]), 2),
                 "clase": str(r.clase), "despachos": int(r.despachos)}
                for _, r in df.sort_values(col, ascending=False).head(n).iterrows()]

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("qué importan las empresas que trajo el universo ampliado; "
                   "el embarque dice qué venden y solo la importación dice si "
                   "compran lo que la plataforma vende"),
        "regla_reventa": ("está en el padrón de importadores de insumo y "
                          "despacha %d veces o más: compra para revender, no "
                          "para producir" % DESPACHOS_REVENTA),
        "empresas": len(nuevos),
        "fob_export": round(fob_nuevos, 2),
        "exportan": [{"n": str(k), "mm": float(v)} for k, v in fam.items()],
        "importan_algo": int(len(set(a.ruc) | set(gan.index.get_level_values(0)))),
        "sin_clasificar_pct": round(
            100 * sum(1 for r in nuevos if r not in clase) / len(nuevos), 1),
        "productor_o_agroindustria": len(prod),
        "industria_del_insumo": {
            "empresas": int(len(reventa)),
            "fob": round(float(reventa.fob.sum()), 2),
            "pct_de_lo_que_compra": round(
                100 * float(reventa.fob.sum()) / float(a.fob.sum()), 1)
            if len(a) else 0.0,
            "top": top(reventa, "fob"),
        },
        "grano_y_balanceado": {
            "empresas": int(len(gan)),
            "fob": round(float(gan.sum()), 2),
            "pct_en_seis": round(100 * float(gan.head(6).sum())
                                 / float(gan.sum()), 1) if len(gan) else 0.0,
            "top": [{"n": str(n)[:46], "fob": round(float(v), 2)}
                    for (_, n), v in gan.head(6).items()],
        },
        "el_resto": {
            "empresas": int(len(resto)),
            "fob": round(float(resto.fob.sum()), 2),
            "top": top(resto, "fob", 8),
        },
    }
    io.open(SALIDA, "w", encoding="utf-8").write(
        json.dumps(salida, ensure_ascii=False, indent=1))

    print("=" * 78)
    print("LAS %d EMPRESAS DEL UNIVERSO AMPLIADO  ·  qué compran" % len(nuevos))
    print("=" * 78)
    print("exportan US$ %.0f MM · importa algo el %.0f%% · sin clasificar en "
          "el padrón agrario el %.0f%%"
          % (fob_nuevos / 1e6,
             100 * salida["importan_algo"] / len(nuevos),
             salida["sin_clasificar_pct"]))
    print()
    print("1. la industria del insumo: %d empresas · US$ %.1f MM (%.0f%% de "
          "lo que compra el grupo)"
          % (len(reventa), reventa.fob.sum() / 1e6,
             salida["industria_del_insumo"]["pct_de_lo_que_compra"]))
    print("   " + ", ".join(x["n"][:24] for x in
                            salida["industria_del_insumo"]["top"][:5]))
    print()
    print("2. el grano y el balanceado: %d empresas · US$ %.0f MM · las seis "
          "primeras son el %.0f%%"
          % (len(gan), gan.sum() / 1e6,
             salida["grano_y_balanceado"]["pct_en_seis"]))
    print("   " + ", ".join(x["n"][:24] for x in
                            salida["grano_y_balanceado"]["top"][:4]))
    print()
    print("3. el resto: %d empresas · US$ %.1f MM en fertilizante y "
          "fitosanitario" % (len(resto), resto.fob.sum() / 1e6))
    for x in salida["el_resto"]["top"][:5]:
        print("     %-44s %7.1f MM  %-14s %4d despachos"
              % (x["n"][:44], x["fob"] / 1e6, x["clase"], x["despachos"]))
    print()
    print("clasificadas productor o agroindustria: %d de %d"
          % (len(prod), len(nuevos)))
    print(SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
