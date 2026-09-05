# -*- coding: utf-8 -*-
"""Agrega la importación de insumos por empresa y por mercado, con cobertura.

Lo que distingue este agregado de una suma cualquiera es que lleva la cuenta de
**qué se llegó a mirar**. Un mes sin operaciones puede significar dos cosas
opuestas —que nadie importó, o que ese archivo todavía no se bajó— y son
exactamente las dos cosas que no hay que confundir. Por eso cada año y cada mes
viaja con las semanas de origen que lo respaldan: sin semanas, la respuesta no
es cero, es «no hay dato».

El 2026 es un año en curso y se marca como tal. Comparar sus meses contra un
año entero no dice nada, así que la variación interanual se calcula sobre el
mismo tramo de meses en los dos años y se declara cuál es ese tramo.

Uso:
    python scripts/build_import_agregados.py
"""
import datetime as dt
import io
import json
import os
import sys

import pandas as pd

PROC = "data/importaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones_clasificadas.csv")
SALIDA = os.path.join(PROC, "importadores.json")
MERCADO = os.path.join(PROC, "mercado.json")
ANOMALIAS = os.path.join(PROC, "anomalias.json")
ANIOS = 5

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def semanas_por(d, cols):
    return d.groupby(cols).semana_archivo.nunique()


def main():
    if not os.path.exists(ENTRADA):
        sys.exit(f"falta {ENTRADA}: corre build_import_clasificar.py")
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig",
                    dtype={"ruc": str, "partida": str, "partida4": str,
                           "anio": str, "mes": str}, low_memory=False)
    d = d[d.ruc.str.len() == 11]                       # RUC valido
    d = d[d.fob_usd >= 0]

    # ---------------------------------------------------------- validacion --
    an = {"generado": dt.datetime.now().isoformat(timespec="seconds")}
    an["operaciones"] = int(len(d))
    an["ruc_invalidos_descartados"] = 0
    an["mes_fuera_de_rango"] = int((~d.mes.isin(
        [f"{m:02d}" for m in range(1, 13)])).sum())
    an["fob_negativo"] = int((d.fob_usd < 0).sum())
    an["declaraciones_repetidas"] = int(d.declaracion.duplicated().sum())
    an["fecha_min"], an["fecha_max"] = str(d.fecha.min()), str(d.fecha.max())

    # ------------------------------------------------------------ cobertura --
    # Las semanas de archivo que respaldan cada ano y cada mes. Es la diferencia
    # entre «no importo» y «no lo bajamos».
    cob_anio = semanas_por(d, ["anio"]).to_dict()
    cob_mes = {f"{a}-{m}": int(v) for (a, m), v in
               semanas_por(d, ["anio", "mes"]).items()}
    ultimo = str(d.fecha.max())
    anio_actual = ultimo[:4]
    mes_ultimo = ultimo[5:7]
    anios = sorted(cob_anio)
    an["cobertura_semanas_por_anio"] = {k: int(v) for k, v in cob_anio.items()}

    # -------------------------------------------------------------- mercado --
    def bloque(sub):
        return {
            "fob": round(float(sub.fob_usd.sum()), 2),
            "cif": round(float(sub.cif_usd.sum()), 2),
            "kg": round(float(sub.peso_neto_kg.sum()), 1),
            "ops": int(len(sub)),
            "empresas": int(sub.ruc.nunique()),
            "semanas": int(sub.semana_archivo.nunique()),
        }

    por_anio = {a: bloque(g) for a, g in d.groupby("anio")}
    # Variacion interanual sobre el mismo tramo de meses, no ano contra ano.
    meses_ytd = [f"{m:02d}" for m in range(1, int(mes_ultimo) + 1)]
    yoy = None
    prev = str(int(anio_actual) - 1)
    if prev in por_anio:
        a1 = d[(d.anio == anio_actual) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        a0 = d[(d.anio == prev) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        if a0 > 0:
            yoy = {"tramo": f"ene-{mes_ultimo}", "anios": [prev, anio_actual],
                   "fob_previo": round(float(a0), 2),
                   "fob_actual": round(float(a1), 2),
                   "variacion_pct": round(100 * (a1 - a0) / a0, 1)}

    cat = (d.groupby("categoria")
             .agg(fob=("fob_usd", "sum"), ops=("fob_usd", "size"),
                  empresas=("ruc", "nunique"))
             .sort_values("fob", ascending=False))
    pais = d.groupby("pais_origen").fob_usd.sum().sort_values(ascending=False)

    mercado = {
        "generado": an["generado"],
        "fuente": "SUNAT/Aduanas · microdatos de manifiestos (Ley 27806)",
        "ultimo_registro": ultimo,
        "anio_en_curso": anio_actual,
        "meses_del_anio_en_curso": meses_ytd,
        "anios_con_dato": anios,
        "anios_pedidos": [str(int(anio_actual) - i) for i in range(ANIOS - 1, -1, -1)],
        "cobertura_semanas": {k: int(v) for k, v in cob_anio.items()},
        "cobertura_mes": cob_mes,
        "empresas_con_dato": int(d.ruc.nunique()),
        "operaciones": int(len(d)),
        "total": bloque(d),
        "por_anio": por_anio,
        "yoy": yoy,
        "categorias": [{"n": c, "fob": round(float(r.fob), 2),
                        "ops": int(r.ops), "empresas": int(r.empresas),
                        "pct": round(100 * r.fob / d.fob_usd.sum(), 2)}
                       for c, r in cat.iterrows()],
        "paises": [{"n": p, "fob": round(float(v), 2)}
                   for p, v in pais.head(20).items()],
    }

    # ------------------------------------------------------------- empresas --
    emp = {}
    for ruc, g in d.groupby("ruc"):
        meses = {f"{a}-{m}": round(float(v), 2) for (a, m), v in
                 g.groupby(["anio", "mes"]).fob_usd.sum().items()}
        emp[ruc] = {
            "ruc": ruc,
            "n": g.razon_social.mode().iat[0],
            "total": bloque(g),
            "por_anio": {a: bloque(x) for a, x in g.groupby("anio")},
            "por_mes": meses,
            "categorias": [{"n": c, "fob": round(float(v), 2)} for c, v in
                           g.groupby("categoria").fob_usd.sum()
                            .sort_values(ascending=False).items()],
            "partidas": [{"n": p, "fob": round(float(v), 2)} for p, v in
                         g.groupby("partida").fob_usd.sum()
                          .nlargest(10).items()],
            "paises": [{"n": p, "fob": round(float(v), 2)} for p, v in
                       g.groupby("pais_origen").fob_usd.sum()
                        .nlargest(10).items()],
            "aduanas": [{"n": p, "fob": round(float(v), 2)} for p, v in
                        g.groupby("aduana").fob_usd.sum().nlargest(5).items()],
            "primera": str(g.fecha.min()), "ultima": str(g.fecha.max()),
        }

    # ------------------------------------------- cuadraturas que deben dar --
    tot = d.fob_usd.sum()
    an["cuadra_suma_anios"] = bool(abs(
        sum(v["fob"] for v in por_anio.values()) - tot) < 1)
    an["cuadra_suma_categorias"] = bool(abs(cat.fob.sum() - tot) < 1)
    an["cuadra_suma_empresas"] = bool(abs(
        sum(e["total"]["fob"] for e in emp.values()) - tot) < 1)
    an["cuadra_suma_meses"] = bool(abs(
        sum(sum(e["por_mes"].values()) for e in emp.values()) - tot) < 1)

    for p, o in ((SALIDA, emp), (MERCADO, mercado), (ANOMALIAS, an)):
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh, ensure_ascii=False, separators=(",", ":"))

    print(f"empresas con dato : {len(emp):,}")
    print(f"operaciones       : {len(d):,}")
    print(f"FOB total         : US$ {tot/1e6:,.1f} MM")
    print(f"ultimo registro   : {ultimo}")
    print(f"anios con dato    : {anios}")
    print(f"anios sin dato    : "
          f"{[a for a in mercado['anios_pedidos'] if a not in anios]}")
    print(f"semanas por anio  : {an['cobertura_semanas_por_anio']}")
    print("\ncuadraturas:")
    for k in ("cuadra_suma_anios", "cuadra_suma_categorias",
              "cuadra_suma_empresas", "cuadra_suma_meses"):
        print(f"  {k:<26} {'OK' if an[k] else 'NO CUADRA'}")
    print(f"  declaraciones repetidas    {an['declaraciones_repetidas']}")
    print(f"  mes fuera de rango         {an['mes_fuera_de_rango']}")
    print(f"  FOB negativo               {an['fob_negativo']}")
    if yoy:
        print(f"\nvariacion {yoy['tramo']} {yoy['anios'][0]}->{yoy['anios'][1]}: "
              f"{yoy['variacion_pct']:+.1f}%")


if __name__ == "__main__":
    main()
