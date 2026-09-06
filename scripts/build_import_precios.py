# -*- coding: utf-8 -*-
"""Valor unitario de importacion: US$ por kilo, partida por partida.

Cada operacion trae su FOB y su peso neto, asi que el precio ya estaba en los
datos sin calcular. Lo que hace este archivo es decidir **donde ese precio
significa algo**, que es la mitad dificil.

No en todas las partidas. Una subpartida de commodity —urea, DAP, cloruro de
potasio— agrupa un solo producto y su US$/kg es un precio de mercado. Una
subpartida como «los demas abonos» o «insecticidas» agrupa cosas que no se
parecen: un insecticida de US$ 3/kg y otro de US$ 200/kg comparten casillero
arancelario y promediarlos no da un precio, da un numero.

Asi que la elegibilidad la decide la dispersion medida, no una lista escrita a
mano. Y se mide **dentro de cada mes**: entre 2022 y 2026 el precio del
fertilizante se movio tanto que medir la dispersion sobre los cinco anos juntos
confundiria «producto heterogeneo» con «precio que cambio». La urea pasa de
0.88 a 0.36 solo con hacer bien esa distincion.

Sobre los atipicos. El cloruro de potasio se mueve entre 0.24 y 0.38 US$/kg en
camiones de diez mil toneladas, y en la misma subpartida aparecen viales de 0.1
kg de solucion calibradora de laboratorio a US$ 900/kg. Son declaraciones
legitimas y no son comercio de fertilizante. Se recortan por reglas de
cuartiles sobre el logaritmo del precio, dentro de cada partida y ano, y se
deja constancia de cuantas se recortaron.

El valor unitario que se publica es la suma de FOB dividida por la suma de
kilos —el «valor unitario» de la estadistica de comercio—, que ademas es
robusto por construccion: esos viales aportan US$ 15 y cero kilos.

Uso:
    python scripts/build_import_precios.py
"""
import datetime as dt
import io
import json
import os
import sys

import numpy as np
import pandas as pd

PROC = "data/importaciones/processed"
ENTRADA = os.path.join(PROC, "operaciones_clasificadas.csv")
SALIDA = os.path.join(PROC, "precios.json")
PANEL = os.path.join(PROC, "panel.json")

# Una partida admite precio si, despues de recortar atipicos, la mitad central
# de sus operaciones cabe dentro del 40% de la mediana en un mes cualquiera.
# El umbral no es magico: es donde los datos separan solos los commodities de
# los casilleros «los demas» y de los fitosanitarios formulados.
DISPERSION_MAX = 0.40
MIN_OPS = 150          # operaciones con peso, en los cinco anos
MIN_MESES = 18         # meses con al menos MIN_OPS_MES operaciones
MIN_OPS_MES = 5

# El kilo tiene que ser la unidad en que se comercia, no solo una columna que
# viene llena. El declarante anota la unidad comercial, y ahi se ve: la urea se
# declara en toneladas, la semilla de alfalfa en kilos, pero los arboles
# frutales se declaran en unidades y los bulbos en millares. Un US$/kg de arbol
# es aritmetica valida sobre una pregunta que nadie hace. Se exige que las
# unidades de peso manden en las declaraciones de la partida.
UNIDADES_PESO = {"KG", "TM", "LB"}
MIN_PESO_DECLARADO = 0.60

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def nombres_partida():
    """Los nombres NANDINA ya viven en panel.json. Se leen de ahi y no se
    importa el modulo que los define: importarlo envuelve sys.stdout una
    segunda vez y el primer envoltorio, al recogerse, cierra el buffer que
    este proceso todavia esta usando."""
    if not os.path.exists(PANEL):
        return {}
    with io.open(PANEL, encoding="utf-8") as fh:
        return json.load(fh).get("nombres_partida", {})


def recortar(g):
    """Marca como atipica la operacion cuyo log-precio cae fuera de las vallas
    de Tukey del grupo. En logaritmo porque el precio es asimetrico: en escala
    lineal la valla de abajo cae en negativo y no recorta nada."""
    if len(g) < 8:
        return pd.Series(True, index=g.index)
    l = np.log(g)
    q1, q3 = l.quantile(.25), l.quantile(.75)
    iqr = q3 - q1
    return (l >= q1 - 1.5 * iqr) & (l <= q3 + 1.5 * iqr)


def cuantil_kg(precio, kg, q):
    """Cuantil ponderado por kilos."""
    o = np.argsort(precio)
    v, w = np.asarray(precio)[o], np.asarray(kg)[o]
    c = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, c, v))


def dispersion(g):
    """Dispersion del precio dentro del mes, **ponderada por kilos**.

    Ponderar importa y no es un detalle. Lo que se publica es un valor unitario
    kilo-ponderado, de modo que la pregunta correcta no es si las operaciones
    se parecen entre si, sino si se parecen los kilos. El cloruro de potasio lo
    muestra: por operacion su dispersion es 0.47 —lo arrastra una cola de
    viales de laboratorio de 0.1 kg—, y por kilo es 0.08, porque el 99.99% de
    la tonelada es el mismo camion de fertilizante a granel. Rechazarlo por lo
    primero seria rechazar un commodity por culpa de un frasco.
    """
    if len(g) < MIN_OPS_MES or g.peso_neto_kg.sum() <= 0:
        return np.nan
    v, w = g.upk.values, g.peso_neto_kg.values
    m = cuantil_kg(v, w, .5)
    if m <= 0:
        return np.nan
    return (cuantil_kg(v, w, .75) - cuantil_kg(v, w, .25)) / m


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_import_clasificar.py")
    d = pd.read_csv(ENTRADA, encoding="utf-8-sig",
                    dtype={"ruc": str, "partida": str, "anio": str,
                           "mes": str}, low_memory=False)
    # El precio del mercado incluye toda la tonelada; el ranking por empresa,
    # solo a quien tiene titular publicable (ver Ley 29733 mas arriba).
    d = d[(d.fob_usd > 0) & (d.peso_neto_kg > 0)]
    d = d.copy()
    d["p6"] = d.partida.str[:6]
    d["upk"] = d.fob_usd / d.peso_neto_kg
    d["ym"] = d.anio + "-" + d.mes
    total_con_peso = len(d)

    d["ok"] = (d.groupby(["p6", "anio"]).upk
                .transform(lambda g: recortar(g)).astype(bool))
    recortadas = int((~d.ok).sum())
    v = d[d.ok]

    # ------------------------------------------------------- elegibilidad --
    disp = (v.groupby(["p6", "ym"])[["upk", "peso_neto_kg"]]
             .apply(dispersion).dropna())
    meses = disp.groupby("p6").size()
    dmed = disp.groupby("p6").median()
    ops = v.groupby("p6").size()
    # Que proporcion de la partida se declara en unidades de peso.
    unid = v.unidad.fillna("").str.strip().str.upper()
    peso_decl = (unid.isin(UNIDADES_PESO).groupby(v.p6).mean())

    elegibles, rechazadas = {}, {}
    for p in ops.index:
        motivo = None
        if peso_decl.get(p, 0) < MIN_PESO_DECLARADO:
            top = unid[v.p6 == p].value_counts().head(2).index.tolist()
            motivo = ("solo %.0f%% se declara en peso; se comercia en %s"
                      % (100 * peso_decl.get(p, 0), "/".join(t or "(vacío)"
                                                            for t in top)))
        elif ops[p] < MIN_OPS:
            motivo = f"solo {int(ops[p])} operaciones con peso"
        elif meses.get(p, 0) < MIN_MESES:
            motivo = f"solo {int(meses.get(p, 0))} meses con suficiente detalle"
        elif dmed.get(p, np.nan) > DISPERSION_MAX:
            motivo = (f"dispersion {dmed[p]:.2f} de la tonelada dentro del "
                      "mes: la subpartida agrupa productos que no se parecen")
        if motivo:
            rechazadas[p] = motivo
        else:
            elegibles[p] = round(float(dmed[p]), 3)

    e = v[v.p6.isin(elegibles)]
    NOMBRES = nombres_partida()

    def uv(g):
        return {"uv": round(float(g.fob_usd.sum() / g.peso_neto_kg.sum()), 4),
                "kg": round(float(g.peso_neto_kg.sum()), 1),
                "fob": round(float(g.fob_usd.sum()), 2),
                "ops": int(len(g)),
                "p25": round(float(g.upk.quantile(.25)), 4),
                "p50": round(float(g.upk.median()), 4),
                "p75": round(float(g.upk.quantile(.75)), 4)}

    partidas = {}
    for p, gp in e.groupby("p6"):
        # Una subpartida «los demas» que pasa el filtro lo hace porque un
        # producto domina su tonelada. El precio es real, pero es el precio de
        # ese producto y no el de un casillero entero: queda marcado para que
        # la interfaz lo diga y nadie lea mas de lo que hay.
        nom = NOMBRES.get(p, "")
        partidas[p] = {
            "dispersion": elegibles[p],
            "generica": nom.lower().startswith(("los demás", "las demás")),
            "categoria": gp.categoria.mode().iat[0],
            "total": uv(gp),
            "anios": {a: uv(g) for a, g in gp.groupby("anio")},
            "meses": {m: uv(g) for m, g in gp.groupby("ym")
                      if len(g) >= MIN_OPS_MES},
            # Quien compra caro y quien barato, contra el valor unitario del
            # mercado en ese mismo ano. Sin el ano al lado la comparacion no
            # significaria nada: el precio se movio mas entre anos que entre
            # empresas.
            "empresas": {a: [
                {"r": r, "uv": round(float(g.fob_usd.sum() /
                                           g.peso_neto_kg.sum()), 4),
                 "kg": round(float(g.peso_neto_kg.sum()), 1),
                 "ops": int(len(g))}
                for r, g in sorted(ga[ga.ruc.str.fullmatch(r"\d{11}",
                                                            na=False)]
                                   .groupby("ruc"),
                                   key=lambda kv: -kv[1].peso_neto_kg.sum())
                if g.peso_neto_kg.sum() > 0]
                for a, ga in gp.groupby("anio")},
        }

    ultimo = str(v.fecha.max())
    out = {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "fuente": "SUNAT/Aduanas · microdatos de manifiestos (Ley 27806)",
        "ultimo_registro": ultimo,
        "anio_en_curso": ultimo[:4],
        "regla": {
            "dispersion_max": DISPERSION_MAX,
            "min_operaciones": MIN_OPS,
            "min_meses": MIN_MESES,
            "medida": "IQR sobre la mediana, ponderado por kilos, dentro de cada mes",
            "valor_unitario": "suma de FOB dividida por suma de kilos",
        },
        "operaciones_con_peso": total_con_peso,
        "operaciones_recortadas": recortadas,
        "partidas": partidas,
        "rechazadas": rechazadas,
    }
    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    print("operaciones con peso  : %s" % format(total_con_peso, ","))
    print("recortadas por atipico: %s (%.2f%%)"
          % (format(recortadas, ","), 100 * recortadas / total_con_peso))
    print("partidas con precio   : %d de %d" % (len(elegibles), len(ops)))
    print("archivo               : %.2f MB" % (os.path.getsize(SALIDA) / 1e6))
    print()
    NOMBRE_PARTIDA = NOMBRES
    print("%-8s %-46s %6s %10s %9s" % ("part", "producto", "disp", "US$/kg",
                                       "FOB MM"))
    for p in sorted(partidas, key=lambda x: -partidas[x]["total"]["fob"]):
        t = partidas[p]["total"]
        print("%-8s %-46s %6.2f %10.3f %9.1f"
              % (p, NOMBRE_PARTIDA.get(p, "")[:46], partidas[p]["dispersion"],
                 t["uv"], t["fob"] / 1e6))
    print("\nsin precio publicable, con el motivo:")
    for p in sorted(rechazadas,
                    key=lambda x: -float(v[v.p6 == x].fob_usd.sum())):
        print("  %-8s %-40s %s" % (p, NOMBRE_PARTIDA.get(p, "")[:40],
                                   rechazadas[p]))


if __name__ == "__main__":
    main()
