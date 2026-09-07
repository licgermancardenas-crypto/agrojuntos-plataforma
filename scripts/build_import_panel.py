# -*- coding: utf-8 -*-
"""Arma el cubo que necesita el bloque «Qué importa este mercado».

El panel deja recorrer mercado -> ano -> categoria -> partida -> empresa, y
cada escalon tiene que traer su propio FOB, sus operaciones y sus importadores.
Eso es un cubo de cuatro dimensiones, que suena caro y no lo es: las
combinaciones que existen de verdad son 4,591, porque el universo son 19
categorias, 46 subpartidas y 1,095 empresas. Cabe entero en un archivo, asi que
el «Todos» del ranking muestra todos y no un recorte disfrazado.

Lo que este archivo NO hace, y es deliberado:

  - no rellena anos sin semanas descargadas. Un ano que no esta, no esta: la
    cobertura viaja al lado para que la interfaz diga «pendiente de carga» en
    vez de dibujar un cero.
  - no calcula variaciones interanuales. Eso lo decide la interfaz, que tiene
    la cobertura a la vista y sabe cuando el ano anterior no da para comparar.

Los nombres de subpartida salen de la nomenclatura NANDINA, que es el nombre
oficial del codigo y no una interpretacion de lo que escribio el declarante.
Una subpartida que no este en la tabla se muestra con su codigo, que es
preferible a ponerle un nombre inventado.

Uso:
    python scripts/build_import_panel.py
"""
import datetime as dt
import io
import json
import os
import sys

import pandas as pd

PROC = "data/importaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones_clasificadas.csv")
SALIDA = os.path.join(PROC, "panel.json")
MERCADO = os.path.join(PROC, "mercado.json")   # de donde sale la cobertura

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

# Nomenclatura NANDINA, seis digitos. Es el nombre oficial de la subpartida.
NOMBRE_PARTIDA = {
    "310100": "Abonos de origen animal o vegetal",
    "310210": "Urea, incluso en disolución acuosa",
    "310221": "Sulfato de amonio",
    "310229": "Sales dobles y mezclas de sulfato y nitrato de amonio",
    "310230": "Nitrato de amonio, incluso en disolución acuosa",
    "310250": "Nitrato de sodio",
    "310260": "Sales dobles y mezclas de nitrato de calcio y de amonio",
    "310280": "Mezclas de urea con nitrato de amonio en disolución",
    "310290": "Los demás abonos nitrogenados y sus mezclas",
    "310311": "Superfosfatos con 35% o más de pentóxido de difósforo",
    "310319": "Los demás superfosfatos",
    "310390": "Los demás abonos fosfatados",
    "310420": "Cloruro de potasio",
    "310430": "Sulfato de potasio",
    "310490": "Los demás abonos potásicos",
    "310510": "Abonos en tabletas o en envases de hasta 10 kg",
    "310520": "Abonos con nitrógeno, fósforo y potasio (NPK)",
    "310530": "Fosfato diamónico (DAP)",
    "310540": "Fosfato monoamónico (MAP) y sus mezclas con DAP",
    "310551": "Los demás abonos con nitratos y fosfatos",
    "310559": "Los demás abonos con nitrógeno y fósforo",
    "310560": "Abonos con fósforo y potasio",
    "310590": "Los demás abonos",
    "380852": "DDT, en envases de hasta 300 g",
    "380859": "Los demás bienes del Anexo III del Convenio de Rótterdam",
    "380861": "Insecticidas del Anexo, en envases de hasta 300 g",
    "380862": "Insecticidas del Anexo, en envases de hasta 7.5 kg",
    "380869": "Los demás insecticidas del Anexo",
    "380891": "Insecticidas",
    "380892": "Fungicidas",
    "380893": "Herbicidas, inhibidores de germinación y reguladores",
    "380894": "Desinfectantes",
    "380899": "Los demás productos fitosanitarios",
    "120921": "Semilla de alfalfa",
    "120922": "Semilla de trébol",
    "120923": "Semilla de festuca",
    "120924": "Semilla de pasto azul de Kentucky",
    "120925": "Semilla de ballico",
    "120929": "Las demás semillas forrajeras",
    "120930": "Semillas de plantas herbáceas cultivadas por sus flores",
    "120991": "Semillas de hortalizas",
    "120999": "Las demás semillas para siembra",
    "060110": "Bulbos y tubérculos en reposo vegetativo",
    "060210": "Esquejes sin enraizar e injertos",
    "060220": "Árboles y arbustos de frutas o frutos comestibles",
    "060290": "Las demás plantas vivas",
}


def bloque(sub):
    # «emp» cuenta importadores identificables. La etiqueta reservada de la Ley
    # 29733 agrupa a muchas personas naturales bajo un mismo texto: contarla
    # como una empresa seria contar mal en las dos direcciones.
    return {"fob": round(float(sub.fob_usd.sum()), 2),
            "ops": int(len(sub)),
            "emp": int(sub.ruc[sub.ruc.str.fullmatch(r"\d{11}", na=False)]
                       .nunique())}


def por_fob(pares):
    return sorted(pares, key=lambda kv: -kv[1].fob_usd.sum())


def _cobertura(clave, porDefecto):
    """Lee del agregado lo que el agregado ya midió."""
    if not os.path.exists(MERCADO):
        return porDefecto
    return json.load(io.open(MERCADO, encoding="utf-8")).get(clave, porDefecto)


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_import_clasificar.py")
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig",
                    dtype={"ruc": str, "partida": str, "anio": str,
                           "mes": str}, low_memory=False)
    d = d[d.fob_usd >= 0].copy()
    d["p6"] = d.partida.str[:6]
    # «No Disponib» no es un RUC: es la etiqueta con la que SUNAT reserva al
    # importador persona natural (Ley 29733). Suma en el mercado y no puede
    # sumar en un ranking de empresas.
    d["pub"] = d.ruc.str.fullmatch(r"\d{11}", na=False)
    reservado = d[~d.pub]

    ultimo = str(d.fecha.max())
    anio_actual = ultimo[:4]
    cob = {a: int(v) for a, v in
           d.groupby("anio").semana_archivo.nunique().items()}
    anios = sorted(cob)

    # El nombre de cada empresa una sola vez: repetirlo en cada fila del cubo
    # multiplicaria el archivo sin agregar nada.
    nombres = {r: g.razon_social.mode().iat[0]
               for r, g in d[d.pub].groupby("ruc")}

    total = {a: bloque(g) for a, g in d.groupby("anio")}

    cats = {}
    for cat, gc in d.groupby("categoria"):
        c = {"anios": {}, "partidas": {}, "empresas": {}, "paises": {},
             "emp_part": {}}
        for a, ga in gc.groupby("anio"):
            c["anios"][a] = bloque(ga)
            c["partidas"][a] = [dict(p=p, **bloque(gp))
                                for p, gp in por_fob(ga.groupby("p6"))]
            c["empresas"][a] = [
                {"r": r, "fob": round(float(gr.fob_usd.sum()), 2),
                 "ops": int(len(gr))}
                for r, gr in por_fob(ga[ga.pub].groupby("ruc"))]
            c["paises"][a] = [
                {"n": p, "fob": round(float(v), 2)} for p, v in
                ga.groupby("pais_origen").fob_usd.sum().nlargest(10).items()]
            c["emp_part"][a] = {
                p: [{"r": r, "fob": round(float(gr.fob_usd.sum()), 2),
                     "ops": int(len(gr))}
                    for r, gr in por_fob(gp[gp.pub].groupby("ruc"))]
                for p, gp in ga.groupby("p6")}
        cats[cat] = c

    out = {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "fuente": "SUNAT/Aduanas · microdatos de manifiestos (Ley 27806)",
        "ultimo_registro": ultimo,
        "anio_en_curso": anio_actual,
        "anios_pedidos": [str(int(anio_actual) - i) for i in range(4, -1, -1)],
        "anios_con_dato": anios,
        "cobertura_semanas": cob,
        "semanas_completo": 45,
        # Los dias que ningun archivo descargado respalda. Los calcula
        # `build_import_agregados.py` y aqui se leen: contar semanas no basta
        # para decir que un ano esta entero —52 semanas no cubren 365 dias— y
        # dos archivos que lo midieran por separado acabarian discrepando.
        "dias_sin_cubrir_por_anio": _cobertura("dias_sin_cubrir_por_anio", {}),
        "dias_sin_cubrir": _cobertura("dias_sin_cubrir", {}),
        "completitud_mes": _cobertura("completitud_mes", {}),
        "total": total,
        "reservado": {
            "motivo": "importadores persona natural; SUNAT no publica al "
                      "titular (Ley 29733)",
            "fob": round(float(reservado.fob_usd.sum()), 2),
            "ops": int(len(reservado)),
            "por_anio": {a: round(float(v), 2) for a, v in
                         reservado.groupby("anio").fob_usd.sum().items()},
        },
        "cats": cats,
        "nombres": nombres,
        "nombres_partida": {p: NOMBRE_PARTIDA.get(p, "")
                            for p in sorted(d.p6.unique())},
    }
    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    sin_nombre = [p for p, n in out["nombres_partida"].items() if not n]
    print("categorias        : " + str(len(cats)))
    print("subpartidas       : " + str(len(out["nombres_partida"])))
    print("empresas          : " + format(len(nombres), ","))
    print("anios con dato    : " + str(anios))
    print("cobertura         : " + str(cob))
    print("archivo           : %.2f MB" % (os.path.getsize(SALIDA) / 1e6))
    if sin_nombre:
        print("subpartidas sin nombre en la tabla: " + str(sin_nombre))

    # Cuadraturas. El cubo tiene que sumar lo mismo que el total en los cuatro
    # cortes; si no, alguna fila se perdio o se conto dos veces.
    tot = d.fob_usd.sum()
    s_cat = sum(v["fob"] for c in cats.values() for v in c["anios"].values())
    s_par = sum(x["fob"] for c in cats.values() for l in c["partidas"].values()
                for x in l)
    s_emp = sum(x["fob"] for c in cats.values() for l in c["empresas"].values()
                for x in l)
    s_ep = sum(x["fob"] for c in cats.values() for a in c["emp_part"].values()
               for l in a.values() for x in l)
    tot_emp = tot - reservado.fob_usd.sum()
    for k, v, ref in (("categoria x anio", s_cat, tot), ("+ partida", s_par, tot),
                      ("+ empresa", s_emp, tot_emp),
                      ("+ partida x empresa", s_ep, tot_emp)):
        print("  cuadra %-22s %s" % (k, "OK" if abs(v - ref) < 1
                                     else "NO CUADRA"))
    print("  reservado por Ley 29733     US$ %.1f MM en %s operaciones"
          % (reservado.fob_usd.sum() / 1e6, format(len(reservado), ",")))


if __name__ == "__main__":
    main()
