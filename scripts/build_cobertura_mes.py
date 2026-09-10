# -*- coding: utf-8 -*-
"""La cobertura de la red, mes a mes, pesada por la demanda de cada mes.

El proyecto publica **64.4% del mercado dentro de la promesa**, y esa cifra pesa
cada celda por su SAM anual: como si el país comprara parejo los doce meses.
No compra. La canasta mostró que octubre vale el 12.9% del año y abril el 5.6%,
y sobre todo que **cada región tiene su propio pico** —Puno concentra el 79% en
cuatro meses; San Martín reparte y su mejor mes no llega al 11%—.

Medido: la cobertura va de **60.8% en mayo a 70.9% en enero**, y **ocho de los
doce meses quedan por debajo del 64.4% publicado**. Diez puntos de banda que la
cifra plana no deja ver.

## La hipótesis con que se empezó, y por qué era falsa

Se esperaba lo contrario de lo que salió. La corazonada era que las regiones mal
cubiertas —sierra y selva— son las que más concentran su compra en la siembra,
así que la red debía verse peor justo en los meses grandes. Un primer cálculo
pareció confirmarlo: octubre al 60.8%, casi cuatro puntos bajo el promedio.

**Ese cálculo estaba mal y el error vale documentarlo**, porque es el que este
mismo archivo advierte dos párrafos más abajo: pesaba la cobertura departamental
por los montos de la canasta, mezclando dos construcciones distintas del mismo
mercado y contando el supuesto dos veces. Hecho por celda y tomando del
calendario solo la forma, **octubre da 65.1%, por encima del promedio**.

Así que la conclusión útil es otra: la red **no** está peor en los meses que más
pesan —enero, diciembre y octubre son de los mejores—, sino en los meses flojos
de mayo a agosto. Lo que sí queda en pie es que el 64.4% es un promedio anual
que esconde una banda de diez puntos, y que ocho meses del año están debajo.

## Cómo se cruza

La cobertura viene por celda H3 de `hubs_asignacion.csv` —cada una con su SAM,
sus horas al centro y la promesa de su región—. El calendario viene por
departamento de `estacionalidad_region.csv`, que es lo más fino que da la
siembra. Se aplica **el perfil del departamento a cada celda suya**, conservando
el SAM de la celda como tamaño:

    demanda(celda, mes) = sam(celda) × perfil(departamento, mes)

El tamaño sigue siendo el del modelo de mercado, que corrige por tamaño de
unidad con las tasas del CENAGRO; del calendario se toma **solo la forma**. Es
deliberado: la canasta y el SAM son dos construcciones distintas del mismo
mercado, y mezclar sus montos absolutos sumaría dos veces el supuesto.

## Lo que esto no dice

Que la red esté peor de lo que se creía en términos físicos: las horas son las
mismas. Dice que **la vara con que se la juzgaba era generosa**, porque
promediaba doce meses que no pesan igual. Y que la decisión del noveno centro
—que hoy se lee «35.6% fuera de la promesa»— tiene una lectura más útil: cuánto
queda fuera en el mes en que de verdad se compra.

Uso:
    python scripts/build_cobertura_mes.py
"""
import io
import json
import os
import re
import sys
import unicodedata

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitio                                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

ASG = "out/hubs_asignacion.csv"
PERFIL = "out/estacionalidad_region.csv"
SALIDA = "out/cobertura_mes.json"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set",
         "Oct", "Nov", "Dic"]


def k(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    for p in (ASG, PERFIL):
        if not os.path.exists(p):
            sys.exit("falta %s: corre el pipeline" % p)
    a = pd.read_csv(ASG, encoding="utf-8-sig")
    e = pd.read_csv(PERFIL, encoding="utf-8-sig")

    a["kd"] = a.dep.map(k)
    e["kd"] = e.k.map(k)
    # El perfil, normalizado: del calendario se toma la forma y no el monto.
    per = e.set_index("kd")[MESES]
    per = per.div(per.sum(axis=1), axis=0).fillna(0.0)
    # Un departamento sin calendario propio hereda el del país, y se dice
    # cuánto mercado quedó en esa situación.
    nac = per.mul(e.set_index("kd")["total"], axis=0).sum()
    nac = nac / nac.sum()
    sin_perfil = a.loc[~a.kd.isin(per.index), "sam_usd"].sum()

    plano = 100 * a.loc[a.cubierto_promesa, "sam_usd"].sum() / a.sam_usd.sum()
    plano_2h = 100 * a.loc[a.cubierto_2h, "sam_usd"].sum() / a.sam_usd.sum()

    filas = []
    for m in MESES:
        w = a.kd.map(per[m]).fillna(nac[m]).values * a.sam_usd.values
        filas.append({
            "mes": m,
            "peso_pct": round(100 * float(w.sum())
                              / float((a.sam_usd.values * 1.0).sum()), 2),
            "demanda_rel": round(float(w.sum()), 2),
            "cubierto_pct": round(
                100 * float(w[a.cubierto_promesa.values].sum())
                / float(w.sum()), 1),
            "cubierto_2h_pct": round(
                100 * float(w[a.cubierto_2h.values].sum())
                / float(w.sum()), 1),
        })
    tot_w = sum(f["demanda_rel"] for f in filas)
    for f in filas:
        f["peso_pct"] = round(100 * f["demanda_rel"] / tot_w, 1)

    peor = min(filas, key=lambda f: f["cubierto_pct"])
    mejor = max(filas, key=lambda f: f["cubierto_pct"])
    pico = max(filas, key=lambda f: f["demanda_rel"])
    bajo = [f["mes"] for f in filas if f["cubierto_pct"] < plano]

    # Y por región, que es donde se ve el mecanismo: la que peor se cubre es la
    # que más concentra.
    reg = []
    for kd, g in a.groupby("kd"):
        if not len(g) or g.sam_usd.sum() <= 0:
            continue
        p = per.loc[kd] if kd in per.index else nac
        cub = 100 * g.loc[g.cubierto_promesa, "sam_usd"].sum() / g.sam_usd.sum()
        reg.append({"region": str(g.dep.iat[0]),
                    "sam_mm": round(float(g.sam_usd.sum()) / 1e6, 1),
                    "cubierto_pct": round(float(cub), 1),
                    "mes_pico": MESES[int(p.values.argmax())],
                    "pct_pico": round(100 * float(p.max()), 1),
                    "concentracion_4m": round(
                        100 * float(sum(sorted(p.values)[-4:])), 1)})
    reg.sort(key=lambda r: r["cubierto_pct"])

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("la cobertura de la promesa pesada por la demanda de cada "
                   "mes; la cifra plana pesa el año entero y le da peso a "
                   "demanda que no está cuando no está"),
        "metodo": ("cobertura por celda H3 de hubs_asignacion.csv, calendario "
                   "por departamento de estacionalidad_region.csv; del "
                   "calendario se toma solo la forma y el tamaño sigue siendo "
                   "el SAM del modelo de mercado"),
        "plano_pct": round(float(plano), 1),
        "plano_2h_pct": round(float(plano_2h), 1),
        "sam_sin_perfil_pct": round(
            100 * float(sin_perfil) / float(a.sam_usd.sum()), 1),
        "meses": filas,
        "peor": peor, "mejor": mejor, "mes_pico": pico,
        "meses_bajo_el_plano": len(bajo),
        "brecha_puntos": round(mejor["cubierto_pct"] - peor["cubierto_pct"], 1),
        "regiones": reg,
    }
    crudo = json.dumps(salida, ensure_ascii=False, indent=1)
    io.open(SALIDA, "w", encoding="utf-8").write(crudo)
    io.open(os.path.join(sitio.DATA, "cobertura_mes.json"), "w",
            encoding="utf-8").write(crudo)

    print("=" * 74)
    print("COBERTURA DE LA PROMESA, MES A MES")
    print("=" * 74)
    print("la cifra plana, sin calendario: %.1f%%" % plano)
    print()
    print("  %-5s %9s %11s" % ("mes", "del año", "cubierto"))
    for f in filas:
        marca = "  <-- el mayor" if f is pico else ""
        print("  %-5s %8.1f%% %10.1f%%%s"
              % (f["mes"], f["peso_pct"], f["cubierto_pct"], marca))
    print()
    print("%d de 12 meses por debajo del %.1f%% publicado"
          % (len(bajo), plano))
    print("peor %s %.1f%% · mejor %s %.1f%% · brecha %.1f puntos"
          % (peor["mes"], peor["cubierto_pct"], mejor["mes"],
             mejor["cubierto_pct"], salida["brecha_puntos"]))
    print()
    print("las cinco regiones peor cubiertas, y cuánto concentran")
    print("  %-16s %8s %9s %8s" % ("región", "SAM MM", "cubierto", "pico"))
    for r in reg[:5]:
        print("  %-16s %7.1f %8.1f%% %5s %.0f%%"
              % (r["region"][:16], r["sam_mm"], r["cubierto_pct"],
                 r["mes_pico"], r["pct_pico"]))
    print()
    print(SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
