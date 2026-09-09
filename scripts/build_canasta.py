# -*- coding: utf-8 -*-
"""Qué insumo se compra, para qué cultivo, en qué región y en qué mes.

El proyecto tenía las tres piezas por separado y ninguna contestaba la
pregunta de un comercial, que es siempre la misma: *en Piura, en marzo, ¿qué se
está comprando y para qué?*

    `estacionalidad_detalle.csv`  cuánta demanda de insumo hay en cada cultivo,
                                  departamento y mes — pero como un solo monto,
                                  sin decir de qué insumo
    `costos_cultivo.csv`          la hoja de costos de MIDAGRI: cuánto de una
                                  hectárea de palta es fertilizante, cuánto
                                  plaguicida, cuánto semilla — pero nacional y
                                  sin calendario

Cruzarlas da la canasta: el monto de cada mes repartido en las seis líneas de
insumo con la estructura de **ese** cultivo. Papa y palta no compran lo mismo
—la papa se lleva el 30% en semilla y la palta cero, porque no se resiembra— y
esa diferencia es justamente lo que un promedio nacional borra.

## Dónde está el mes

En la **siembra**, no en la cosecha. El fertilizante entra con el cultivo y no
cuando sale el camión, así que `build_estacionalidad.py` ancla la demanda en el
mes sembrado; los permanentes, que no se siembran cada año, reparten su
mantenimiento en los doce meses y viajan marcados como supuesto. Anclarlo en la
cosecha correría el calendario medio año y mandaría al vendedor tarde.

## Lo que esto es y lo que no

**No es una medición de compras.** Nadie publica lo que compró un agricultor.
Es la hoja de costos de MIDAGRI aplicada a la superficie sembrada, que es un
coeficiente técnico —lo que cuesta producir una hectárea bien hecha— y no un
ticket. Sirve para saber a qué le entra la plata y cuándo; no para afirmar que
alguien compró.

Las tres capas del supuesto, en orden de menos a más frágil:

  la superficie sembrada por mes y departamento     medida, MIDAGRI 2023
  el reparto entre líneas de insumo por cultivo     coeficiente, MIDAGRI
  que el productor gaste lo que la hoja dice        supuesto, y es el flojo

El tercero es el que hay que tener presente: la hoja describe un manejo
tecnificado y el minifundio de sierra no lo alcanza. Por eso la canasta dice
**a qué se destina el gasto**, y el cuánto sale del modelo de mercado, que sí
corrige por tamaño de unidad con las tasas de uso del CENAGRO.

Uso:
    python scripts/build_canasta.py
"""
import io
import json
import os
import re
import sys
import unicodedata

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

DETALLE = "out/estacionalidad_detalle.csv"
COSTOS = "out/costos_cultivo.csv"
LINEAS = ["fertilizantes", "plaguicidas", "semillas", "riego", "abono",
          "asistencia_tecnica"]
NOMBRE = {"fertilizantes": "Fertilizante", "plaguicidas": "Fitosanitario",
          "semillas": "Semilla", "riego": "Riego", "abono": "Abono orgánico",
          "asistencia_tecnica": "Asistencia técnica"}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set",
         "Oct", "Nov", "Dic"]
# El anuario abrevia y la hoja de costos no. No son cultivos distintos: son el
# mismo nombre escrito corto en una planilla y largo en la otra, y sin esta
# tabla un tercio de la demanda del país se quedaba sin estructura de insumo.
ALIAS = {
    "mad": "maiz amarillo duro", "amilac": "maiz amilaceo",
    "choclo": "maiz choclo", "chala": "maiz chala",
    "avenaf": "avena forrajera", "cebadaf": "cebada forrajera",
    "palma": "palma aceitera", "pelefante": "pasto de elefante",
    "frijol": "frijol grano seco", "habags": "haba grano seco",
    "habagv": "haba grano verde", "arvejags": "arveja grano seco",
    "arvejagv": "arveja grano verde", "olivo": "aceituna",
    "cebollacabeza": "cebolla", "canaalcohol": "cana de azucar para alcohol",
    "canaazucar": "cana de azucar para azucar", "arandano": "arandanos",
    "achiot": "achiote", "algodonrama": "algodon", "cafe": "cafe",
    "platano": "platano", "papaamarilla": "papa", "papablanca": "papa",
}


def k(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    for p in (DETALLE, COSTOS):
        if not os.path.exists(p):
            sys.exit("falta %s: corre el pipeline" % p)
    d = pd.read_csv(DETALLE, encoding="utf-8-sig")
    c = pd.read_csv(COSTOS, encoding="utf-8-sig")

    c["kc"] = c.cultivo.map(k)
    # La estructura de cada cultivo, en fracciones que suman uno.
    est = c.set_index("kc")[LINEAS]
    est = est.div(est.sum(axis=1), axis=0).fillna(0.0)

    d["kc"] = d.cultivo.map(k).map(lambda x: k(ALIAS.get(x, x)))
    d["tiene_hoja"] = d.kc.isin(est.index)

    # Los que no tienen hoja usan la estructura media de su familia, y la
    # salida lo dice fila por fila: un promedio disfrazado de dato propio es
    # peor que un promedio declarado.
    fam = {}
    for t in d.tipo.dropna().unique():
        ks = d.loc[d.tipo == t, "kc"]
        sub = est.reindex(ks.unique()).dropna()
        fam[t] = (sub.mean() if len(sub) else est.mean())
    media = est.mean()

    filas = []
    for _, r in d.iterrows():
        s = est.loc[r.kc] if r.tiene_hoja else fam.get(r.tipo, media)
        for ln in LINEAS:
            v = float(r.demanda_usd) * float(s[ln])
            if v <= 0:
                continue
            filas.append({"insumo": NOMBRE[ln], "dep": r.dep,
                          "cultivo": r.cultivo, "tipo": r.tipo, "mes": r.mes,
                          "ha": float(r.ha), "usd": round(v, 2),
                          "estructura": "propia" if r.tiene_hoja
                                        else "media de su familia"})
    x = pd.DataFrame(filas)
    x.to_csv("out/canasta_detalle.csv", index=False, encoding="utf-8-sig")

    tot = float(x.usd.sum())
    prop = float(x.loc[x.estructura == "propia", "usd"].sum())

    def corte(col, n=None):
        g = x.groupby(col).usd.sum().sort_values(ascending=False)
        if n:
            g = g.head(n)
        return [{"n": str(i), "usd": round(float(v), 2),
                 "pct": round(100 * float(v) / tot, 1)} for i, v in g.items()]

    def cruce(a, b, n=4):
        """Para cada `a`, sus `n` mayores `b`. Es la respuesta que se usa: en
        Piura, qué insumo; en marzo, qué cultivo."""
        out = {}
        for i, g in x.groupby(a):
            s = g.groupby(b).usd.sum().sort_values(ascending=False).head(n)
            out[str(i)] = [{"n": str(j), "usd": round(float(v), 2),
                            "pct": round(100 * float(v) / float(g.usd.sum()), 1)}
                           for j, v in s.items()]
        return out

    mes_ins = {}
    for m in MESES:
        g = x[x.mes == m]
        if not len(g):
            continue
        mes_ins[m] = {"usd": round(float(g.usd.sum()), 2),
                      "pct": round(100 * float(g.usd.sum()) / tot, 1),
                      "insumos": [{"n": str(i), "usd": round(float(v), 2)}
                                  for i, v in g.groupby("insumo").usd.sum()
                                  .sort_values(ascending=False).items()]}

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("qué insumo se compra, para qué cultivo, en qué región y en "
                   "qué mes; la hoja de costos de MIDAGRI aplicada a la "
                   "superficie sembrada por mes y departamento"),
        "salvedad": ("no es una medición de compras: nadie publica lo que "
                     "compró un agricultor. Es un coeficiente técnico —lo que "
                     "cuesta producir bien una hectárea— aplicado a la "
                     "superficie real. Dice a qué se destina el gasto y "
                     "cuándo, no que alguien lo haya comprado"),
        "el_mes_es": ("el de la siembra y no el de la cosecha: el fertilizante "
                      "entra con el cultivo. Los permanentes reparten su "
                      "mantenimiento en los doce meses, que es un supuesto"),
        "usd_total": round(tot, 2),
        "cultivos": int(x.cultivo.nunique()),
        "con_estructura_propia_pct": round(100 * prop / tot, 1),
        "por_insumo": corte("insumo"),
        "por_region": corte("dep"),
        "por_cultivo": corte("cultivo", 15),
        "por_mes": mes_ins,
        "insumo_por_region": cruce("dep", "insumo", 6),
        "cultivo_por_region": cruce("dep", "cultivo", 5),
        "mes_por_region": cruce("dep", "mes", 3),
        "insumo_por_cultivo": cruce("cultivo", "insumo", 6),
    }
    io.open("out/canasta.json", "w", encoding="utf-8").write(
        json.dumps(salida, ensure_ascii=False, indent=1))

    print("=" * 78)
    print("LA CANASTA DE INSUMOS  ·  US$ %.0f MM al año en %d cultivos"
          % (tot / 1e6, x.cultivo.nunique()))
    print("=" * 78)
    print("con estructura de costos propia: %.0f%% del gasto; el resto usa el "
          "promedio de su familia" % (100 * prop / tot))
    print()
    print("por insumo")
    for r in salida["por_insumo"]:
        print("  %-22s %8.1f MM  %5.1f%%" % (r["n"], r["usd"] / 1e6, r["pct"]))
    print()
    print("las ocho regiones que más compran, y en qué se les va")
    for r in salida["por_region"][:8]:
        top = salida["insumo_por_region"][r["n"]][:3]
        print("  %-14s %7.1f MM  ·  %s"
              % (r["n"], r["usd"] / 1e6,
                 ", ".join("%s %.0f%%" % (t["n"], t["pct"]) for t in top)))
    print()
    print("el calendario nacional")
    for m in MESES:
        if m in mes_ins:
            b = "#" * int(mes_ins[m]["pct"] * 2)
            print("  %-4s %7.1f MM %5.1f%%  %s"
                  % (m, mes_ins[m]["usd"] / 1e6, mes_ins[m]["pct"], b))
    print()
    print("out/canasta.json · out/canasta_detalle.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
