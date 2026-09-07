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
import calendar
import datetime as dt
import io
import json
import os
import re
import sys

import pandas as pd

PROC = "data/importaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones_clasificadas.csv")
SEMANAS = os.path.join(PROC, "_semanas_procesadas.json")
SALIDA = os.path.join(PROC, "importadores.json")
MERCADO = os.path.join(PROC, "mercado.json")
ANOMALIAS = os.path.join(PROC, "anomalias.json")
ANIOS = 5

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def semanas_por(d, cols):
    return d.groupby(cols).semana_archivo.nunique()


def dias_cubiertos():
    """Los días del calendario que respalda algún archivo descargado.

    Contar semanas no alcanza para decir que un año está completo, y este
    archivo lo daba por bueno con un umbral: 45 de 52 y listo. Pero las
    semanas se cuentan sobre las que **traen operación**, así que una semana
    que no se bajó y otra en la que nadie importó suman igual, y sobre todo:
    52 semanas no cubren 365 días. El año nuevo es el caso: la semana del 29
    de diciembre al 4 de enero no la publica SUNAT, y con ella se van tres
    días de diciembre y cuatro de enero de dos años que el informe venía
    llamando completos.

    Aquí se cuentan días, que es la unidad en la que un mes está o no está.

    De esa cuenta salió la pista que faltaba. Los días huecos caían siempre en
    la misma semana —la que cruza el año— y se dio por hecho que SUNAT no la
    publicaba. Sí la publica: cuando cruza el año **la parte en dos archivos**,
    los días de diciembre en uno y los de enero en otro, y el pipeline solo
    pedía el nombre de la semana entera. Ver `tramos()` en
    `acumular_aduanas.py`. Recuperados esos archivos, los cuatro años cerrados
    quedaron enteros.
    """
    cub = set()
    for k in json.load(io.open(SEMANAS, encoding="utf-8")):
        n = re.sub(r"^ma", "", k.split(":")[0]).split(".")[0]
        # El nombre lleva dia inicial, dia final, mes y año **del ultimo dia**.
        fin = dt.date(2000 + int(n[6:8]), int(n[4:6]), int(n[2:4]))
        for j in range(7):
            cub.add(fin - dt.timedelta(days=6 - j))
    return cub


def completitud(cub, anio, mes):
    """Fracción de los días de un mes que algún archivo descargado respalda."""
    nd = calendar.monthrange(int(anio), int(mes))[1]
    hay = sum(1 for d in range(1, nd + 1)
              if dt.date(int(anio), int(mes), d) in cub)
    return round(100 * hay / nd, 2), nd - hay


def main():
    if not os.path.exists(ENTRADA):
        sys.exit(f"falta {ENTRADA}: corre build_import_clasificar.py")
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig",
                    dtype={"ruc": str, "partida": str, "partida4": str,
                           "anio": str, "mes": str}, low_memory=False)
    d = d[d.fob_usd >= 0]
    # SUNAT no publica al titular cuando es persona natural: esas lineas
    # llegan con el RUC literal «No Disponib» y la razon social «No
    # Disponible - Ley 29733». Tiene once caracteres, asi que un filtro por
    # longitud las dejaba pasar y aparecian en el ranking como si fueran una
    # empresa. No lo son: son muchas personas bajo una misma etiqueta.
    # Se quedan en los totales del mercado —el comercio ocurrio— y salen de
    # todo corte por empresa, con el monto declarado aparte.
    pub = d.ruc.str.fullmatch(r"\d{11}", na=False)
    reservado = d[~pub]
    d_emp = d[pub]

    # ---------------------------------------------------------- validacion --
    an = {"generado": dt.datetime.now().isoformat(timespec="seconds")}
    an["operaciones"] = int(len(d))
    an["operaciones_sin_titular_publicable"] = int(len(reservado))
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
    # La cobertura de verdad se mide en dias del calendario, no en semanas con
    # operacion. Un mes al que le faltan tres dias no es un mes.
    cub = dias_cubiertos()
    comp_mes, faltan_dia = {}, {}
    for a, m in sorted({(x, y) for x, y in zip(d.anio, d.mes)}):
        pct_, falta = completitud(cub, a, m)
        comp_mes[f"{a}-{m}"] = pct_
        if falta:
            faltan_dia[f"{a}-{m}"] = falta
    ultimo = str(d.fecha.max())
    anio_actual = ultimo[:4]
    mes_ultimo = ultimo[5:7]
    # La ventana es de cinco años. Al recuperar la semana partida de fin de
    # año entraron despachos de diciembre de 2021 —el archivo trae los dos
    # lados del corte—, y un año con cinco días de dato no es un año: se
    # cuenta aparte y sale de todos los cortes.
    pedidos = [str(int(anio_actual) - i) for i in range(ANIOS - 1, -1, -1)]
    fuera_ventana = d[~d.anio.isin(pedidos)]
    d = d[d.anio.isin(pedidos)].copy()
    # Los cortes por empresa se rehacen sobre la ventana: calculados antes,
    # arrastraban 2021 y dejaban de cuadrar contra los totales de aqui.
    pub = d.ruc.str.fullmatch(r"\d{11}", na=False)
    reservado = d[~pub]
    d_emp = d[pub]
    anios = sorted(cob_anio)
    an["cobertura_semanas_por_anio"] = {k: int(v) for k, v in cob_anio.items()}

    # -------------------------------------------------------------- mercado --
    def bloque(sub):
        return {
            "fob": round(float(sub.fob_usd.sum()), 2),
            "cif": round(float(sub.cif_usd.sum()), 2),
            "kg": round(float(sub.peso_neto_kg.sum()), 1),
            "ops": int(len(sub)),
            "empresas": int(sub.ruc[sub.ruc.str.fullmatch(r"\d{11}",
                                                          na=False)].nunique()),
            "semanas": int(sub.semana_archivo.nunique()),
        }

    por_anio = {a: bloque(g) for a, g in d.groupby("anio")}
    # Variacion interanual sobre el mismo tramo de meses, y solo sobre meses
    # que esten enteros **en los dos anios**. Antes el tramo llegaba hasta el
    # mes del ultimo despacho visto, que por definicion es un mes a medias:
    # comparar treinta dias de agosto contra treinta y uno resta un dia de
    # comercio y lo presenta como caida.
    prev = str(int(anio_actual) - 1)
    meses_ytd = [f"{m:02d}" for m in range(1, int(mes_ultimo) + 1)
                 if comp_mes.get(f"{anio_actual}-{m:02d}", 0) >= 100
                 and comp_mes.get(f"{prev}-{m:02d}", 0) >= 100]
    yoy = None
    if prev in por_anio and meses_ytd:
        a1 = d[(d.anio == anio_actual) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        a0 = d[(d.anio == prev) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        if a0 > 0:
            yoy = {"tramo": f"{meses_ytd[0]}-{meses_ytd[-1]}",
                   "meses": meses_ytd,
                   "motivo": "solo meses con todos sus dias descargados en los "
                             "dos anios; los que no lo estan quedan fuera",
                   "excluidos": [m for m in
                                 (f"{x:02d}" for x in range(1, int(mes_ultimo) + 1))
                                 if m not in meses_ytd],
                   "anios": [prev, anio_actual],
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
        "anios_pedidos": pedidos,
        "fuera_de_ventana": {
            "motivo": "despachos anteriores a la ventana de cinco años, que "
                      "llegan dentro del archivo partido de fin de año",
            "fob": round(float(fuera_ventana.fob_usd.sum()), 2),
            "ops": int(len(fuera_ventana)),
            "anios": sorted(fuera_ventana.anio.unique().tolist()),
        },
        "cobertura_semanas": {k: int(v) for k, v in cob_anio.items()},
        "cobertura_mes": cob_mes,
        # Cobertura medida en dias, que es la que decide si un mes o un ano
        # estan enteros. La de semanas se conserva porque dice cuantos
        # archivos respaldan cada tramo, que es otra pregunta.
        # Solo la ventana: la cobertura se mide sobre todos los meses que el
        # archivo toca, pero 2021 no es un año de este informe.
        "completitud_mes": {k: v for k, v in comp_mes.items()
                            if k[:4] in pedidos},
        "dias_sin_cubrir": {k: v for k, v in faltan_dia.items()
                            if k[:4] in pedidos},
        "dias_sin_cubrir_por_anio": {
            a: sum(v for k, v in faltan_dia.items() if k[:4] == a)
            for a in pedidos},
        "ultimo_dia_cubierto": max(x for x in cub
                                   if x <= dt.date.fromisoformat(ultimo)).isoformat(),
        "empresas_con_dato": int(d_emp.ruc.nunique()),
        "reservado": {
            "motivo": "importadores persona natural; SUNAT no publica al "
                      "titular (Ley 29733 de protección de datos personales)",
            "fob": round(float(reservado.fob_usd.sum()), 2),
            "ops": int(len(reservado)),
            "por_anio": {a: round(float(v), 2) for a, v in
                         reservado.groupby("anio").fob_usd.sum().items()},
        },
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
    def top(sub, col, n=8):
        return [{"n": k, "fob": round(float(v), 2)} for k, v in
                sub.groupby(col).fob_usd.sum().nlargest(n).items()]

    emp = {}
    for ruc, g in d_emp.groupby("ruc"):
        meses = {f"{a}-{m}": round(float(v), 2) for (a, m), v in
                 g.groupby(["anio", "mes"]).fob_usd.sum().items()}
        # El mismo corte por producto, pais y partida repetido ano por ano, que
        # es lo que permite filtrar la ficha sin volver a pedir nada. Se guardan
        # los ocho primeros de cada eje: mas no cabe en un grafico de barras y
        # el archivo lo leen todas las fichas.
        cubo = {a: {"cat": top(x, "categoria"), "pais": top(x, "pais_origen"),
                    "part": top(x, "partida")}
                for a, x in g.groupby("anio")}
        emp[ruc] = {
            "cubo": cubo,
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
    # Los cortes por empresa cuadran contra el total menos lo reservado, que
    # es exactamente lo que no tiene empresa a la cual atribuirse.
    tot_emp = tot - reservado.fob_usd.sum()
    an["cuadra_suma_empresas"] = bool(abs(
        sum(e["total"]["fob"] for e in emp.values()) - tot_emp) < 1)
    an["cuadra_suma_meses"] = bool(abs(
        sum(sum(e["por_mes"].values()) for e in emp.values()) - tot_emp) < 1)

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
    print("dias sin cubrir   : "
          + (", ".join(f"{k} ({v})" for k, v in sorted(faltan_dia.items()))
             or "ninguno"))
    enteros = [a for a in mercado["anios_pedidos"]
               if a in anios and not any(k[:4] == a for k in faltan_dia)]
    print(f"anios enteros     : {enteros}")
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
