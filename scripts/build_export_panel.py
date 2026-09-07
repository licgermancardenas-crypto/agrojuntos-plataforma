# -*- coding: utf-8 -*-
"""Arma el cubo del bloque «Qué exporta este agro».

El gemelo del panel de importacion, con la jerarquia dada vuelta porque la
pregunta comercial es otra. En importacion interesa **que** se trae y con que
partida; en exportacion interesa **a donde** va: producto -> destino ->
exportador. La palta no se entiende sin saber si sale a Estados Unidos o a
Paises Bajos.

Dos advertencias propias de la exportacion, y las dos viajan en el archivo:

  El rezago de regularizacion. La serie se ancla en el embarque, pero el
  archivo semanal se arma cuando la declaracion se regulariza, y entre una
  cosa y otra pasan 11 dias en la mediana. Eso significa que **el ultimo mes
  de la serie siempre esta incompleto**, aunque su semana este descargada:
  faltan los embarques que todavia no regularizan. Es la misma disciplina que
  el «sin descargar no es cero» del lado de importacion, aplicada a un rezago
  en vez de a un hueco.

  Donde esta frontera se calcula: en `build_export_agregados.py`, que mide la
  curva de maduracion sobre meses ya cerrados. Aqui solo se lee de su
  `mercado.json`. Antes este archivo restaba un percentil fijo de 28 dias por
  su cuenta y declaraba una frontera distinta a la del agregado sobre los
  mismos embarques: dos numeros que se contradecian en la misma pagina.

  Fechas de embarque imposibles. Una fraccion minima de las lineas declara
  embarques de hace diez anos. No se corrigen ni se borran: se cuentan y se
  declaran, y quedan fuera de los anos que la interfaz muestra.

Uso:
    python scripts/build_export_panel.py
"""
import datetime as dt
import io
import json
import os
import sys

import pandas as pd

PROC = "data/exportaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones.csv")
SALIDA = os.path.join(PROC, "panel.json")
MERCADO = os.path.join(PROC, "mercado.json")   # de donde sale la frontera
REZAGO_RESPALDO = 31   # solo si el agregado todavia no corrio

# Las once columnas que el cubo necesita, con el tipo con el que entran.
COLS = {
    "ruc": "category", "razon_social": "category", "fecha": "category",
    "anio": "category", "mes": "category", "semana_archivo": "category",
    "familia": "category", "pais_destino": "category", "via": "category",
    "fob_usd": "float64", "peso_neto_kg": "float64",
}

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def bloque(sub):
    return {"fob": round(float(sub.fob_usd.sum()), 2),
            "kg": round(float(sub.peso_neto_kg.sum()), 1),
            "ops": int(len(sub)),
            "emp": int(sub.ruc[sub.pub].nunique())}


def por_fob(pares):
    return sorted(pares, key=lambda kv: -kv[1].fob_usd.sum())


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_export_historico.py")
    # El archivo tiene 30 columnas y el panel usa once. Leer las diecinueve
    # restantes —descripcion, productor, agente de aduana, declaracion— cuesta
    # gigabytes que la maquina no tiene, y ninguna entra en el cubo. Las que
    # se repiten mucho van como categoria: el RUC de una agroexportadora sale
    # miles de veces y no hace falta guardar la cadena miles de veces.
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig", usecols=list(COLS),
                    dtype=COLS, low_memory=False)
    d = d[d.fob_usd >= 0].copy()
    # fecha ordenada para que .max() siga dando el ultimo embarque; una
    # categoria sin orden no se puede comparar.
    d["fecha"] = d.fecha.cat.as_ordered()
    # Igual que en importacion: «No Disponib» no es un RUC, es la reserva del
    # exportador persona natural bajo la Ley 29733.
    d["pub"] = d.ruc.str.fullmatch(r"\d{11}", na=False)

    ultimo = str(d.fecha.max())
    anio_actual = ultimo[:4]
    anios_pedidos = [str(int(anio_actual) - i) for i in range(4, -1, -1)]

    # Fechas de embarque fuera de los anos que se muestran: se cuentan y se
    # dejan fuera, nunca se reparan a mano.
    fuera = d[~d.anio.isin(anios_pedidos)].copy()
    fuera["anio"] = fuera.anio.astype(str)
    previo = str(int(anios_pedidos[0]) - 1)
    d = d[d.anio.isin(anios_pedidos)]
    # Lo reservado se cuenta despues del recorte, no antes: contarlo sobre el
    # universo entero lo dejaba sin cuadrar contra los totales de este mismo
    # archivo, que son los de la ventana.
    reservado = d[~d.pub]

    # La frontera de completitud. Un embarque posterior a esta fecha puede no
    # haber regularizado todavia, asi que su mes esta incompleto por definicion
    # y no por falta de descarga. La calcula el agregado midiendo la curva de
    # maduracion; aqui se lee para que los dos archivos digan lo mismo.
    completitud, criterio = {}, None
    if os.path.exists(MERCADO):
        r = json.load(io.open(MERCADO, encoding="utf-8"))["rezago"]
        frontera = r["frontera_completitud"]
        completitud = r.get("completitud_mes", {})
        umbral = r.get("umbral_completo_pct")
        rezago = (dt.date.fromisoformat(ultimo)
                  - dt.date.fromisoformat(frontera)).days
        criterio = ("curva de maduracion medida sobre meses cerrados; el "
                    "ultimo dia de embarque cuya completitud esperada llega "
                    "al %s%%" % umbral)
    else:
        rezago, umbral = REZAGO_RESPALDO, None
        frontera = (dt.date.fromisoformat(ultimo)
                    - dt.timedelta(days=rezago)).isoformat()
        criterio = ("respaldo: %d dias fijos, porque falta %s; corre "
                    "build_export_agregados.py para medirla"
                    % (rezago, os.path.basename(MERCADO)))

    cob = {a: int(v) for a, v in
           d.groupby("anio", observed=True).semana_archivo.nunique().items()}
    anios = sorted(cob)
    # Algun RUC llega sin razon social en ninguna de sus lineas; en ese caso el
    # nombre es el propio RUC, que es un dato y no un invento.
    def nombre_de(g, ruc):
        m = g.razon_social.dropna().mode()
        return m.iat[0] if len(m) else ruc

    nombres = {r: nombre_de(g, r) for r, g in d[d.pub].groupby("ruc", observed=True)}
    total = {a: bloque(g) for a, g in d.groupby("anio", observed=True)}
    meses = {"%s-%s" % (a, m): bloque(g)
             for (a, m), g in d.groupby(["anio", "mes"], observed=True)}

    cats = {}
    for cat, gc in d.groupby("familia", observed=True):
        c = {"anios": {}, "paises": {}, "empresas": {}, "emp_pais": {},
             "vias": {}}
        for a, ga in gc.groupby("anio", observed=True):
            c["anios"][a] = bloque(ga)
            c["paises"][a] = [dict(n=p, **bloque(gp))
                              for p, gp in por_fob(ga.groupby("pais_destino", observed=True))]
            c["empresas"][a] = [
                {"r": r, "fob": round(float(gr.fob_usd.sum()), 2),
                 "kg": round(float(gr.peso_neto_kg.sum()), 1),
                 "ops": int(len(gr))}
                for r, gr in por_fob(ga[ga.pub].groupby("ruc", observed=True))]
            c["emp_pais"][a] = {
                p: [{"r": r, "fob": round(float(gr.fob_usd.sum()), 2),
                     "kg": round(float(gr.peso_neto_kg.sum()), 1),
                     "ops": int(len(gr))}
                    for r, gr in por_fob(gp[gp.pub].groupby("ruc", observed=True))]
                for p, gp in ga.groupby("pais_destino", observed=True)}
            c["vias"][a] = [{"n": v, "fob": round(float(x.fob_usd.sum()), 2)}
                            for v, x in por_fob(ga.groupby("via", observed=True))]
        cats[cat] = c

    out = {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "fuente": "SUNAT/Aduanas · microdatos de manifiestos (Ley 27806)",
        "ultimo_registro": ultimo,
        "anio_en_curso": anio_actual,
        "anios_pedidos": anios_pedidos,
        "anios_con_dato": anios,
        "cobertura_semanas": cob,
        "semanas_completo": 45,
        "frontera_completitud": frontera,
        "rezago_dias": rezago,
        "criterio_completitud": criterio,
        "umbral_completo_pct": umbral,
        "completitud_mes": completitud,
        "total": total,
        "meses": meses,
        "reservado": {
            "motivo": "exportadores persona natural; SUNAT no publica al "
                      "titular (Ley 29733)",
            "fob": round(float(reservado.fob_usd.sum()), 2),
            "ops": int(len(reservado)),
        },
        # Dos cosas distintas quedan fuera de la ventana y conviene no
        # confundirlas. El ano anterior al primero mostrado trae embarques de
        # diciembre que regularizan en enero: son legitimos y solo caen fuera
        # del recorte. Lo anterior a eso son fechas de embarque que no se
        # sostienen —envios declarados con diez anos de antiguedad— y esas se
        # cuentan aparte, sin corregirlas.
        "fuera_de_rango": {
            "ventana_anterior": {
                "anio": previo,
                "motivo": "embarques de diciembre que regularizan en enero; "
                          "quedan fuera del recorte de cinco años",
                "fob": round(float(fuera[fuera.anio == previo].fob_usd.sum()), 2),
                "ops": int((fuera.anio == previo).sum()),
            },
            "fechas_no_creibles": {
                "motivo": "fecha de embarque anterior a la ventana; no se "
                          "corrigen ni se borran, se declaran",
                "fob": round(float(fuera[fuera.anio < previo].fob_usd.sum()), 2),
                "ops": int((fuera.anio < previo).sum()),
                "anios": sorted(fuera[fuera.anio < previo].anio.unique().tolist()),
            },
        },
        "cats": cats,
        "nombres": nombres,
    }
    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    print("productos         : %d" % len(cats))
    print("exportadores      : %s" % format(len(nombres), ","))
    print("operaciones       : %s" % format(len(d), ","))
    print("FOB total         : US$ %.1f MM" % (d.fob_usd.sum() / 1e6))
    print("anios con dato    : %s" % anios)
    print("cobertura         : %s" % cob)
    print("ultimo embarque   : %s" % ultimo)
    print("frontera completa : %s (%d dias de rezago)" % (frontera, rezago))
    print("criterio          : %s" % criterio)
    parciales = {k: v for k, v in completitud.items()
                 if umbral is not None and v < umbral}
    print("meses parciales   : %s"
          % (", ".join("%s %.1f%%" % kv for kv in sorted(parciales.items()))
             or "ninguno"))
    print("archivo           : %.2f MB" % (os.path.getsize(SALIDA) / 1e6))

    tot = d.fob_usd.sum()
    tot_emp = d[d.pub].fob_usd.sum()
    s_cat = sum(v["fob"] for c in cats.values() for v in c["anios"].values())
    s_pais = sum(x["fob"] for c in cats.values() for l in c["paises"].values()
                 for x in l)
    s_emp = sum(x["fob"] for c in cats.values() for l in c["empresas"].values()
                for x in l)
    s_ep = sum(x["fob"] for c in cats.values() for a in c["emp_pais"].values()
               for l in a.values() for x in l)
    for k, v, ref in (("producto x anio", s_cat, tot), ("+ destino", s_pais, tot),
                      ("+ empresa", s_emp, tot_emp),
                      ("+ destino x empresa", s_ep, tot_emp)):
        print("  cuadra %-22s %s" % (k, "OK" if abs(v - ref) < 1
                                     else "NO CUADRA"))
    print("  reservado Ley 29733         US$ %.1f MM en %s operaciones"
          % (reservado.fob_usd.sum() / 1e6, format(len(reservado), ",")))
    prev = fuera[fuera.anio == previo]
    malas = fuera[fuera.anio < previo]
    print("  fuera de la ventana (%s)   US$ %.1f MM en %s operaciones"
          % (previo, prev.fob_usd.sum() / 1e6, format(len(prev), ",")))
    print("  fechas no creibles          US$ %.1f MM en %s operaciones (%s)"
          % (malas.fob_usd.sum() / 1e6, format(len(malas), ","),
             ", ".join(sorted(malas.anio.unique()))))


if __name__ == "__main__":
    main()
