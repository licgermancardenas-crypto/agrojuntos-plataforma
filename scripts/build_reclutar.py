# -*- coding: utf-8 -*-
"""Con qué puntos de venta conviene trabajar primero, y a cuáles no.

`build_canal.py` mide, para cada punto que ya vende, el mercado que le queda
más cerca que a cualquier otro —su mercado exclusivo— y lo lleva a venta y
margen con la economía unitaria del proyecto. De 3,270 puntos, **517 tienen
mercado propio**. Esa lista existía y vivía en un CSV de 9,467 filas ordenado
por nada en particular.

Ordenarla por margen es lo obvio y no alcanza, porque deja fuera la pregunta
que de verdad decide: **¿se le puede resurtir?**

## El mismo examen que a un centro nuevo

Un satélite que la red no alcanza dentro de su promesa no es un satélite: es
otro almacén y cuesta otra cosa. Con un punto de canal pasa lo mismo. Reclutar
a quien no se puede abastecer a tiempo es prometer una entrega que no se va a
cumplir, y el resultado no es cero sino negativo: el comerciante queda mal con
su cliente y con AgroJuntos.

`canal_punto.csv` ya trae la respuesta en `reparto_en_promesa`, y separa la
lista en dos mitades muy distintas:

    resurtibles en promesa   333 puntos · US$ 557 mil/año · 52,213 clientes
    fuera de promesa         184 puntos · US$ 200 mil/año · 16,627 clientes

El 36% de los puntos con mercado propio —y una cuarta parte del margen— está
detrás de una entrega que hoy no se sostiene. No se borran de la lista: se
publican aparte, porque son exactamente la carta que justifica mover la promesa
o abrir un centro, y confundirlos con los reclutables es lo que haría fracasar
la campaña.

## Qué es el margen

Lo que capturaría AgroJuntos a través del punto en el escenario base —1.5% de
penetración sobre el mercado exclusivo del punto, 21% de margen bruto—, no lo
que vende la tienda. La salida lleva los tres escenarios para que nadie
confunda una cosa con la otra.

Uso:
    python scripts/build_reclutar.py
"""
import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitio                                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

PUNTOS = "out/canal_punto.csv"
CANAL = "out/canal.json"
SALIDA = "out/reclutar.json"
TOPE = 60          # cuántos van con nombre a la salida publicada
# Las varas con que se prueba alargar la promesa. No son propuestas: son el
# precio de cada una, para poder comparar contra abrir un centro.
VARAS = (5.0, 6.0, 8.0, 12.0)


def main():
    for p in (PUNTOS, CANAL):
        if not os.path.exists(p):
            sys.exit("falta %s: corre el pipeline" % p)
    d = pd.read_csv(PUNTOS, encoding="utf-8-sig")
    d = d.loc[:, ~d.columns.duplicated()]
    can = json.load(io.open(CANAL, encoding="utf-8"))
    via = can["viabilidad"]

    v = d[d.sam_exclusivo > 0].copy()
    v["margen_base"] = v["margen_base"].fillna(0.0)
    si = v[v.reparto_en_promesa]
    no = v[~v.reparto_en_promesa]

    def ficha(r):
        return {
            "nombre": str(r.nombre)[:60], "dep": str(r.dep),
            "clase": str(r.clase), "hub": str(r.hub),
            "horas_reparto": round(float(r.horas_reparto), 2)
            if pd.notna(r.horas_reparto) else None,
            "resurtible": bool(r.reparto_en_promesa),
            "clientes": round(float(r.clientes_exclusivos), 1),
            "sam_exclusivo": round(float(r.sam_exclusivo), 2),
            "margen_anual": round(float(r.margen_base), 2),
            "lat": round(float(r.lat), 5), "lon": round(float(r.lon), 5),
        }

    lista = [ficha(r) for r in si.nlargest(TOPE, "margen_base").itertuples()]
    espera = [ficha(r) for r in no.nlargest(15, "margen_base").itertuples()]

    def por_hub(df):
        g = (df.groupby("hub")
             .agg(puntos=("nombre", "size"),
                  margen=("margen_base", "sum"),
                  clientes=("clientes_exclusivos", "sum"),
                  horas=("horas_reparto", "median"))
             .sort_values("margen", ascending=False))
        return [{"hub": str(i), "puntos": int(r.puntos),
                 "margen_anual": round(float(r.margen), 2),
                 "clientes": round(float(r.clientes), 1),
                 "horas_mediana": round(float(r.horas), 2)}
                for i, r in g.iterrows()]

    # ¿Y si en vez de abrir se promete más largo? Es la alternativa barata y
    # hay que ponerle número antes de descartarla. La respuesta es que compra
    # poco: los puntos bloqueados no están apenas fuera de la línea sino
    # lejos —medianas de seis a diez horas—, así que alargar la promesa
    # desbloquea una cuarta parte del margen y a cambio empeora el servicio
    # donde sí se cumple.
    cad = []
    for h in VARAS:
        m = no.horas_reparto <= h
        cad.append({
            "promesa_h": h,
            "puntos": int(m.sum()),
            "pct": round(100 * float(m.mean()), 1) if len(no) else 0.0,
            "margen_anual": round(float(no.loc[m, "margen_base"].sum()), 2),
            "clientes": round(float(no.loc[m, "clientes_exclusivos"].sum()), 1),
        })

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("con qué puntos de venta conviene trabajar primero: los que "
                   "tienen mercado propio y además se pueden resurtir dentro "
                   "de la promesa del centro que los abastece"),
        "salvedad": via["salvedad"],
        "escenarios": via["escenarios"],
        "penetracion": via["penetracion"],
        "margen_bruto": via["margen_bruto"],
        "puntos_que_venden": via["puntos_que_venden"],
        "con_mercado": int(len(v)),
        "resurtibles": {
            "puntos": int(len(si)),
            "margen_anual": round(float(si.margen_base.sum()), 2),
            "clientes": round(float(si.clientes_exclusivos.sum()), 1),
            "sam": round(float(si.sam_exclusivo.sum()), 2),
        },
        "fuera_de_promesa": {
            "puntos": int(len(no)),
            "margen_anual": round(float(no.margen_base.sum()), 2),
            "clientes": round(float(no.clientes_exclusivos.sum()), 1),
            "sam": round(float(no.sam_exclusivo.sum()), 2),
            "motivo": ("tienen mercado propio pero su centro no los alcanza "
                       "dentro de la promesa: reclutarlos es prometer una "
                       "entrega que no se sostiene"),
        },
        "si_se_promete_mas_largo": cad,
        "limite": ("solo está medido el lado del beneficio. Lo que cuesta "
                   "servir peor —alargar la promesa en la costa, que es donde "
                   "está el mercado que hoy sí se cumple— no lo modela este "
                   "proyecto, así que la comparación está coja de un lado"),
        "por_hub": por_hub(si),
        "por_hub_bloqueado": por_hub(no),
        "lista": lista,
        "en_espera": espera,
    }
    crudo = json.dumps(salida, ensure_ascii=False, indent=1)
    io.open(SALIDA, "w", encoding="utf-8").write(crudo)
    io.open(os.path.join(sitio.DATA, "reclutar.json"), "w",
            encoding="utf-8").write(crudo)
    cols = ["nombre", "dep", "clase", "hub", "horas_reparto",
            "reparto_en_promesa", "clientes_exclusivos", "sam_exclusivo",
            "margen_base", "lat", "lon"]
    v.sort_values("margen_base", ascending=False)[cols].to_csv(
        "out/reclutar.csv", index=False, encoding="utf-8-sig")

    print("=" * 76)
    print("CON QUÉ PUNTOS TRABAJAR PRIMERO")
    print("=" * 76)
    print("%d de %s puntos que ya venden tienen mercado propio"
          % (len(v), f"{via['puntos_que_venden']:,}"))
    print("  resurtibles en promesa : %3d · US$ %s/año · %s clientes"
          % (len(si), f"{si.margen_base.sum():,.0f}",
             f"{si.clientes_exclusivos.sum():,.0f}"))
    print("  fuera de promesa       : %3d · US$ %s/año · %s clientes"
          % (len(no), f"{no.margen_base.sum():,.0f}",
             f"{no.clientes_exclusivos.sum():,.0f}"))
    print()
    print("los diez primeros")
    print("  %-38s %-11s %-11s %9s %6s"
          % ("punto", "región", "centro", "US$/año", "h"))
    for r in lista[:10]:
        print("  %-38s %-11s %-11s %9s %6.1f"
              % (r["nombre"][:38], r["dep"][:11], r["hub"][:11],
                 f"{r['margen_anual']:,.0f}", r["horas_reparto"] or 0))
    print()
    print("por centro, lo reclutable")
    for h in salida["por_hub"]:
        print("  %-12s %3d puntos · US$ %8s/año · %s clientes · %.1f h"
              % (h["hub"], h["puntos"], f"{h['margen_anual']:,.0f}",
                 f"{h['clientes']:,.0f}", h["horas_mediana"]))
    print()
    print("si en vez de abrir se promete más largo, de los %d bloqueados:"
          % len(no))
    print("  %8s %8s %14s" % ("promesa", "puntos", "US$/año"))
    for c in cad:
        print("  %6.0f h %8d %14s"
              % (c["promesa_h"], c["puntos"], f"{c['margen_anual']:,.0f}"))
    print("  —de US$ %s bloqueados en total—" % f"{no.margen_base.sum():,.0f}")
    print()
    print("los centros con más margen bloqueado detrás")
    for h in salida["por_hub_bloqueado"][:4]:
        print("  %-12s %3d puntos · US$ %8s/año · mediana %.1f h"
              % (h["hub"], h["puntos"], f"{h['margen_anual']:,.0f}",
                 h["horas_mediana"]))
    print()
    print("%s · out/reclutar.csv" % SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
