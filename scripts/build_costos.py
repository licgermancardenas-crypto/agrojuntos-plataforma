# -*- coding: utf-8 -*-
"""Lo que cuesta cada opción, para que las decisiones se puedan cerrar.

Todo el proyecto mide beneficios. Las cuatro decisiones abiertas dicen qué
compra cada alternativa —cuántos puntos, cuántos clientes, cuánto margen— y
ninguna dice qué cuesta. Así se puede comparar A contra B en lo que traen,
nunca decidir cuál conviene.

Esto pone el otro lado. **Ningún número de aquí sale del dato del proyecto**:
son parámetros de operación, y por eso van todos juntos arriba, cada uno con lo
que lo ancla o con la confesión de que no lo ancla nada. Cambiar uno cambia la
respuesta, que es exactamente por lo que tienen que estar a la vista.

## Lo único que no es supuesto

El ingreso por cliente. Sale del libro de ventas real —ticket, frecuencia y
margen bruto observados— vía `build_som.py`: **US$ 1,694 de margen al año por
cliente capturado**. Es el ancla de todo lo que sigue, y viene de quince
clientes, así que es tan firme como esos quince.

## La trampa que hay que evitar al leerlo

`satelite.json` dice que un centro nuevo pone a **+3,132 clientes** dentro de la
cadena completa. Esos no son clientes de AgroJuntos: son clientes del mercado
que pasan a tener tienda cerca y tienda abastecida. Multiplicarlos por el margen
por cliente daría US$ 5.3 millones y sería un disparate. Lo que se captura es la
penetración —0.5%, 1.5% o 3% según el escenario del propio proyecto— y sobre eso
se calcula.

## Lo que sale

El punto de equilibrio: cuánta penetración necesita un centro nuevo para pagarse
solo. Con los supuestos de abajo, un centro cuesta del orden de US$ 72 mil al
año y el mejor candidato que puede abastecerse compra —al 1.5%— unos US$ 80 mil.
Es decir: **la decisión no se juega en el mapa sino en la penetración**, que es
el número más flojo de la cadena porque sale de quince clientes.

Uso:
    python scripts/build_costos.py
"""
import io
import json
import os
import sys

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

SALIDA = "out/costos.json"
TC = 3.75

# --- los supuestos, todos aquí y todos declarados ------------------------
# El único con fuente pública es el sueldo mínimo; el resto son parámetros de
# operación que nadie midió y que hay que reemplazar con los reales.
RMV_SOLES = 1025.0          # remuneración mínima vital, S/ al mes
CARGA = 1.55                # gratificaciones, CTS y EsSalud sobre el bruto
PLANILLA = [                # quién trabaja en un centro, y a cuántas RMV
    ("jefe de almacén", 1, 3.0),
    ("almacenero", 2, 1.3),
    ("vendedor", 1, 1.5),
    ("chofer", 1, 1.4),
]
ALQUILER_SOLES_MES = 6000.0  # un local de unos 500 m² en capital de provincia
VEHICULO_USD_ANO = 12000.0   # camioneta: depreciación, combustible y taller
OTROS_USD_ANO = 6000.0       # servicios, seguros, licencias
JORNADA_H = 9.0              # el mismo de build_rutas.py

FUENTE = {
    "RMV_SOLES": "remuneración mínima vital vigente, dato público",
    "CARGA": ("14 sueldos al año más 9% de EsSalud y CTS; es la carga laboral "
              "peruana estándar, redondeada"),
    "PLANILLA": "supuesto: cinco personas por centro, sin medir",
    "ALQUILER_SOLES_MES": "supuesto: nadie coticé un local",
    "VEHICULO_USD_ANO": "supuesto",
    "OTROS_USD_ANO": "supuesto",
    "margen_por_cliente": ("medido: del libro de ventas real, vía "
                           "build_som.py"),
}


def main():
    for p in ("out/som_escenarios.csv", "out/satelite.json",
              "out/reclutar.json", "out/rutas.json"):
        if not os.path.exists(p):
            sys.exit("falta %s: corre el pipeline" % p)
    som = pd.read_csv("out/som_escenarios.csv", encoding="utf-8-sig")
    sat = json.load(io.open("out/satelite.json", encoding="utf-8"))
    rec = json.load(io.open("out/reclutar.json", encoding="utf-8"))
    rut = json.load(io.open("out/rutas.json", encoding="utf-8"))

    som["margen_cliente"] = som.margen_usd / som.clientes
    margen_cliente = float(som.margen_cliente.iloc[0])
    escen = [{"escenario": str(r.escenario), "penetracion": float(r.penetracion)}
             for r in som.itertuples()]

    # --- lo que cuesta un centro ---------------------------------------
    planilla = []
    for cargo, n, mult in PLANILLA:
        anual = RMV_SOLES * mult * 12 * CARGA * n / TC
        planilla.append({"cargo": cargo, "personas": n, "rmv": mult,
                         "usd_ano": round(anual, 2)})
    costo_planilla = sum(p["usd_ano"] for p in planilla)
    costo_alquiler = ALQUILER_SOLES_MES * 12 / TC
    centro_ano = costo_planilla + costo_alquiler + VEHICULO_USD_ANO + OTROS_USD_ANO

    # --- lo que compra un centro nuevo ----------------------------------
    # Los clientes del satélite son de mercado, no capturados: se aplica la
    # penetración del escenario y no el total.
    surt = [c for c in sat["candidatos"] if c.get("h_a_la_red") is not None]
    cand = surt[0] if surt else None
    equilibrio = None
    filas = []
    if cand:
        for e in escen:
            cap = cand["clientes_nuevos"] * e["penetracion"]
            filas.append({
                "escenario": e["escenario"], "penetracion": e["penetracion"],
                "clientes_capturados": round(cap, 1),
                "margen_ano": round(cap * margen_cliente, 2),
                "resultado": round(cap * margen_cliente - centro_ano, 2),
            })
        equilibrio = centro_ano / (cand["clientes_nuevos"] * margen_cliente)

    # --- lo que cuesta recorrer lo que ya se puede -----------------------
    # Una jornada cuesta lo que cuesta tener a un vendedor y una camioneta ese
    # día. Es el costo de la campaña de reclutamiento, no del centro.
    dias_ano = 240.0
    vend = next(p for p in planilla if p["cargo"] == "vendedor")
    chof = next(p for p in planilla if p["cargo"] == "chofer")
    jornada_usd = ((vend["usd_ano"] + chof["usd_ano"] + VEHICULO_USD_ANO)
                   / dias_ano)
    campana = []
    for h in rut["por_hub"]:
        if not h["rutas"]:
            continue
        campana.append({
            "hub": h["hub"], "jornadas": h["rutas"],
            "costo_una_vuelta": round(h["rutas"] * jornada_usd, 2),
            "margen_ano": h["margen_anual"],
            "vueltas_que_paga": round(
                h["margen_anual"] / (h["rutas"] * jornada_usd), 1)
            if h["rutas"] else None,
        })
    campana.sort(key=lambda x: -x["margen_ano"])

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("lo que cuesta cada opción, para poder cerrar decisiones "
                   "que hasta ahora solo comparaban beneficios"),
        "advertencia": ("ningún costo de aquí sale del dato del proyecto: son "
                        "parámetros de operación. El único medido es el margen "
                        "por cliente, que viene del libro de ventas real y de "
                        "quince clientes"),
        "supuestos": {
            "rmv_soles_mes": RMV_SOLES, "carga_laboral": CARGA,
            "alquiler_soles_mes": ALQUILER_SOLES_MES,
            "vehiculo_usd_ano": VEHICULO_USD_ANO,
            "otros_usd_ano": OTROS_USD_ANO, "tipo_de_cambio": TC,
            "dias_habiles_ano": dias_ano, "jornada_h": JORNADA_H,
            "fuente": FUENTE,
        },
        "margen_por_cliente_usd_ano": round(margen_cliente, 2),
        "centro": {
            "planilla": planilla,
            "usd_planilla": round(costo_planilla, 2),
            "usd_alquiler": round(costo_alquiler, 2),
            "usd_vehiculo": VEHICULO_USD_ANO,
            "usd_otros": OTROS_USD_ANO,
            "usd_ano": round(centro_ano, 2),
        },
        "noveno_centro": {
            "candidato": cand["candidato"] if cand else None,
            "clientes_de_mercado": cand["clientes_nuevos"] if cand else None,
            "advertencia": ("son clientes del mercado que ganan cadena "
                            "completa, no clientes capturados: se les aplica "
                            "la penetración"),
            "escenarios": filas,
            "penetracion_de_equilibrio": (round(equilibrio, 4)
                                          if equilibrio else None),
        },
        "jornada_usd": round(jornada_usd, 2),
        "campana_de_reclutamiento": campana,
        "falta": ("el costo de servir peor —lo que se pierde al alargar la "
                  "promesa— sigue sin modelarse, así que esa comparación "
                  "sigue coja"),
    }
    io.open(SALIDA, "w", encoding="utf-8").write(
        json.dumps(salida, ensure_ascii=False, indent=1))

    print("=" * 76)
    print("LO QUE CUESTA  ·  todos los costos son supuestos declarados")
    print("=" * 76)
    print("medido, del libro real: US$ %s de margen al año por cliente "
          "capturado" % f"{margen_cliente:,.0f}")
    print()
    print("un centro de distribución, al año")
    for p in planilla:
        print("  %-18s %d × %.1f RMV %14s" % (p["cargo"], p["personas"],
                                              p["rmv"],
                                              "US$ %s" % f"{p['usd_ano']:,.0f}"))
    print("  %-18s %26s" % ("alquiler", "US$ %s" % f"{costo_alquiler:,.0f}"))
    print("  %-18s %26s" % ("vehículo", "US$ %s" % f"{VEHICULO_USD_ANO:,.0f}"))
    print("  %-18s %26s" % ("otros", "US$ %s" % f"{OTROS_USD_ANO:,.0f}"))
    print("  %-18s %26s" % ("TOTAL", "US$ %s" % f"{centro_ano:,.0f}"))
    print()
    if cand:
        print("¿se paga el noveno centro? — candidato %s, +%s clientes de "
              "mercado" % (cand["candidato"],
                           f"{cand['clientes_nuevos']:,}"))
        print("  %-13s %11s %13s %14s"
              % ("escenario", "penetración", "margen/año", "resultado"))
        for f in filas:
            print("  %-13s %10.1f%% %13s %14s"
                  % (f["escenario"], 100 * f["penetracion"],
                     "US$ %s" % f"{f['margen_ano']:,.0f}",
                     "US$ %s" % f"{f['resultado']:,.0f}"))
        print("  se paga solo a partir del %.2f%% de penetración"
              % (100 * equilibrio))
    print()
    print("la campaña de reclutamiento · una jornada cuesta US$ %.0f"
          % jornada_usd)
    print("  %-12s %9s %16s %13s"
          % ("centro", "jornadas", "una vuelta", "margen/año"))
    for c in campana[:6]:
        print("  %-12s %9d %16s %13s"
              % (c["hub"], c["jornadas"],
                 "US$ %s" % f"{c['costo_una_vuelta']:,.0f}",
                 "US$ %s" % f"{c['margen_ano']:,.0f}"))
    print()
    print(SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
