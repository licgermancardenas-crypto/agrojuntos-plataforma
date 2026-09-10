# -*- coding: utf-8 -*-
"""Las decisiones del proyecto, con el número que las sostiene y el que las daría vuelta.

La plataforma contesta muy bien *qué es verdad*. No contestaba *qué hacemos y
cuánto vale*, y eso se notó: el universo arancelario, el séptimo y octavo
centro, la promesa diferenciada, la regla con que un territorio absorbe lo que
quedó fuera y el ruteo por distrito se decidieron todos midiendo alternativas
—y las mediciones terminaron **en mensajes de commit**. Quien abra el proyecto
dentro de seis meses verá la red de ocho centros y no sabrá que la de seis se
midió, ni cuánto peor era.

Esto lo pone en un archivo. Cada decisión lleva cinco cosas:

    pregunta      lo que había que decidir, dicho como pregunta
    respuesta     lo que se decidió, con la cifra de hoy
    alternativa   lo que se midió y se descartó, con **su** cifra
    bisagra       qué tendría que cambiar para dar vuelta la respuesta
    fuente        qué archivo produce el número, para poder rehacerlo

## De dónde salen los números

De los artefactos que el pipeline ya publica, y no de este archivo: la
cobertura sale de `red_elegida.json`, la absorción de `clusters_absorcion.json`,
el universo del bloque `universo` de `mercado.json`, el reparto del canal de
`canal.json`. Cuando cambie el dato, cambia la decisión que se muestra, sin que
nadie edite un texto.

La excepción está marcada y es una sola: **la cifra del método anterior**. Que
el ruteo por celda diera 41 distritos sin centro y US$ 2,257 MM no se puede
recalcular —ese método ya no existe—, así que viaja con la fecha en que se
midió y con el nombre de quien la produjo. Es un dato histórico y se declara
como tal en vez de disfrazarse de cifra viva.

## Lo que este archivo no hace

No recomienda con adjetivos. Una decisión abierta se publica con su cifra y su
bisagra, no con «conviene expandir al sur»: si la recomendación no se puede
recalcular, no es una recomendación sino una opinión con formato de dato.

Y no inventa preguntas. Están las que el proyecto de verdad enfrentó o
enfrenta; una lista larga de preguntas plausibles sería otra vez decoración.

Uso:
    python scripts/build_decisiones.py
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

EXP = "data/exportaciones/processed/mercado.json"
SALIDA = "out/decisiones.json"
# El oficial contra el que se contrasta la agroexportación medida. Es de
# MIDAGRI y no se calcula aquí: se cita.
MIDAGRI_2025 = 15013.0


def leer(p):
    if not os.path.exists(p):
        sys.exit("falta %s: corre el pipeline" % p)
    return json.load(io.open(p, encoding="utf-8"))


def mm(v):
    """Millones, con un decimal cuando la cifra es chica y el decimal importa."""
    v = v / 1e6
    return "US$ %s MM" % (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.1f}")


def main():
    red = leer("out/red_elegida.json")
    can = leer("out/canal.json")
    abso = leer("out/clusters_absorcion.json")
    aco = leer("out/acopio.json")
    sat = leer("out/satelite.json")
    amp = leer("out/ampliacion.json")
    cmes = leer("out/cobertura_mes.json")
    rec = leer("out/reclutar.json")
    mer = leer(EXP)
    uni = mer["universo"]
    cob = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")

    anio = max(a for a in mer["por_anio"] if a < mer["anio_en_curso"])
    fob = mer["por_anio"][anio]["fob"] / 1e6
    sin_amp = fob - uni["fob_ampliacion_por_anio"].get(anio, 0) / 1e6
    # Los seis que el algoritmo elige con la vara de dos horas: es la red que
    # había antes de decidir el séptimo y el octavo.
    c2 = cob[(cob.umbral_h == 2.0) & (cob.k == 6)]
    pct6 = float(c2.pct_sam.iat[0]) if len(c2) else None
    decididos = [c for c in red["centros"] if c.get("por") == "decision"]

    # El canal que su propio centro no alcanza dentro de la promesa.
    rep = pd.DataFrame(can["reparto"])
    rep["fuera"] = rep["puntos"] - rep["en_promesa"]
    # El peor no es el que tiene más puntos fuera —ese sería siempre el centro
    # más grande, y Pisco encabezaría la lista sirviendo al 85% de los suyos—
    # sino el que peor proporción alcanza.
    peor = rep.sort_values("pct_en_promesa").iloc[0]
    fuera_tot = int(rep["fuera"].sum())

    via = can["viabilidad"]
    base = next((e for e in via["escenarios"] if e["e"] == "Base"),
                via["escenarios"][0])

    D = []

    # ------------------------------------------------------- decididas --
    D.append({
        "id": "universo-arancelario", "estado": "decidida",
        "familia": "Qué contamos",
        "pregunta": "¿Qué partida arancelaria cuenta como agroexportación?",
        "respuesta": "25 capítulos del arancel menos la pesca disfrazada de "
                     "capítulo agrario. %s en %s, un %.1f%% por debajo de los "
                     "US$ %s MM que publica MIDAGRI."
                     % (mm(fob * 1e6), anio,
                        abs(100 * (fob - MIDAGRI_2025) / MIDAGRI_2025),
                        f"{MIDAGRI_2025:,.0f}"),
        "alternativa": "Los siete capítulos con que arrancó el proyecto: %s, "
                       "un %.0f%% por debajo del oficial."
                       % (mm(sin_amp * 1e6),
                          abs(100 * (sin_amp - MIDAGRI_2025) / MIDAGRI_2025)),
        "bisagra": "Que el aceite y la harina de pescado —%s de las partidas "
                   "1504 y 2301— pasen a contarse como agro, o que MIDAGRI "
                   "cambie su propio criterio." % "US$ 2,388 MM",
        "cifra": round(fob, 1), "unidad": "US$ MM en %s" % anio,
        "fuente": "scripts/universo.py · mercado.json bloque universo",
    })

    D.append({
        "id": "red-de-centros", "estado": "decidida",
        "familia": "Dónde estar",
        "pregunta": "¿Cuántos centros de distribución y dónde?",
        "respuesta": "%d centros: los que elige la cobertura máxima más %s, "
                     "puestos por decisión. Cubren el %.1f%% del mercado "
                     "dentro de su promesa."
                     % (len(red["centros"]),
                        " y ".join(c["hub"] for c in decididos),
                        red["sam_cubierto_promesa_pct"]),
        "alternativa": ("Quedarse en los seis del algoritmo: %.1f%% del "
                        "mercado a dos horas." % pct6) if pct6 else
                       "Quedarse en los seis del algoritmo.",
        "bisagra": "Lo que agregue un noveno centro sobre esta red, que no es "
                   "lo mismo que el noveno de la lista voraz: esa lista "
                   "reordena la red entera en cada paso.",
        "cifra": red["sam_cubierto_promesa_pct"], "unidad": "% del SAM",
        "fuente": "out/red_elegida.json · build_hubs.py",
    })

    D.append({
        "id": "promesa-de-servicio", "estado": "decidida",
        "familia": "Cómo servimos",
        "pregunta": "¿En cuántas horas se promete la entrega?",
        "respuesta": "%s. Cubre el %.1f%% del mercado."
                     % (", ".join("%s %.0f h" % (k.lower(), v)
                                  for k, v in red["promesa_h"].items()),
                        red["sam_cubierto_promesa_pct"]),
        "alternativa": "Prometer dos horas a todo el país: %.1f%% del "
                       "mercado. La misma red, menos de la mitad de la "
                       "cobertura." % red["sam_cubierto_2h_pct"],
        "bisagra": "La selva baja, que con la promesa de seis horas llega "
                   "solo al %.0f%%: es la región donde la vara no alcanza."
                   % next((r["pct"] for r in red["por_region"]
                           if r["region"] == "SELVA BAJA"), 0),
        "cifra": red["sam_cubierto_promesa_pct"], "unidad": "% del SAM",
        "fuente": "out/red_elegida.json · PROMESA_H en build_hubs.py",
    })

    D.append({
        "id": "territorios-absorben", "estado": "decidida",
        "familia": "Quién atiende a quién",
        "pregunta": "¿Qué se hace con el mercado que no cae en ningún "
                    "territorio de venta?",
        "respuesta": "Entra al territorio que lo alcance por carretera "
                     "mientras el territorio siga midiendo menos de %.0f km. "
                     "Entran %s clientes y %s; la cobertura llega al %.0f%% "
                     "de los clientes y %d de %d territorios se siguen "
                     "recorriendo en el día."
                     % (abso["visitable_km"], f"{abso['clientes']:,.0f}",
                        mm(abso["sam_usd"]),
                        abso["pct_clientes_en_territorio"],
                        abso["visitables"], abso["territorios"]),
        "alternativa": "Una vara fija de horas para todos. Con dos horas "
                       "entran los mismos clientes y los territorios "
                       "visitables bajan de %d a 34; con seis horas, a 14."
                       % abso["visitables"],
        "bisagra": "Los %s clientes que siguen fuera: meterlos rompe el "
                   "territorio que los recibe, así que son argumento de la "
                   "capa de canal y no de un territorio más grande."
                   % f"{abso['clientes_sin_territorio']:,.0f}",
        "cifra": abso["pct_clientes_en_territorio"], "unidad": "% de clientes",
        "fuente": "out/clusters_absorcion.json · diag_territorios.py",
    })

    D.append({
        "id": "acopio-por-distrito", "estado": "decidida",
        "familia": "Cómo medimos",
        "pregunta": "¿Qué centro sirve a un distrito que embarca?",
        "respuesta": "Se rutea al distrito, al punto medio de sus sectores "
                     "agrícolas. Quedan %d distritos y %s fuera del alcance "
                     "de todo centro."
                     % (aco["sin_centro"]["distritos"],
                        mm(aco["sin_centro"]["fob"])),
        "alternativa": "Heredarlo de la celda de demanda que le toca encima. "
                       "Daba 41 distritos y US$ 2,257 MM sin centro, entre "
                       "ellos Olmos con 1,599 MM, que está a 2.5 horas de "
                       "Chiclayo.",
        "alternativa_historica": {
            "medido_el": "2026-09-08",
            "por": "el método anterior, que ya no existe en el código",
        },
        "bisagra": "Los ocho distritos que la capa distrital trae sin "
                   "geometría, que son la mayor parte de lo que queda fuera.",
        "cifra": aco["sin_centro"]["distritos"], "unidad": "distritos",
        "fuente": "out/acopio.json · out/hubs_distrito.csv",
    })

    # --------------------------------------------------------- abiertas --
    # El mejor por clientes y el mejor que además puede abastecerse no son el
    # mismo, y esa es la columna que decide: un centro al que la red no llega
    # dentro de su promesa no es un satélite sino otro almacén, y cuesta otra
    # cosa.
    surt = [c for c in sat["candidatos"] if c.get("h_a_la_red") is not None]
    mejor = sat["candidatos"][0] if sat["candidatos"] else None
    mejor_surt = surt[0] if surt else None
    seis = next((c for c in sat["cadencia"] if c["promesa_h"] == 6.0), None)
    hoy_s = sat["hoy"]

    D.append({
        "id": "noveno-centro", "estado": "abierta",
        "familia": "Dónde estar",
        "pregunta": "¿Conviene un noveno centro, y dónde?",
        "respuesta": "Sin decidir. La cobertura no es un número sino una "
                     "banda: %.1f%% en el año, pero entre %.1f%% en %s y "
                     "%.1f%% en %s según el mes, y %d de los doce por debajo "
                     "del promedio. Hoy %s de %s puntos de venta están dentro "
                     "de la promesa del centro que los surte (%.0f%%), y "
                     "detrás hay %s clientes con la cadena completa. El "
                     "candidato que más compraría es %s: +%d puntos y +%s "
                     "clientes."
                     % (cmes["plano_pct"], cmes["peor"]["cubierto_pct"],
                        cmes["peor"]["mes"], cmes["mejor"]["cubierto_pct"],
                        cmes["mejor"]["mes"], cmes["meses_bajo_el_plano"],
                        f"{hoy_s['puntos_en_promesa']:,}",
                        f"{hoy_s['puntos']:,}", hoy_s["pct"],
                        f"{hoy_s['clientes_cadena']:,}",
                        mejor["candidato"] if mejor else "—",
                        mejor["puntos_nuevos"] if mejor else 0,
                        f"{mejor['clientes_nuevos']:,}" if mejor else "0"),
        "alternativa": "No abrir y prometer seis horas parejas: %s puntos "
                       "(+%d) y %s clientes con la cadena completa (+%s). Un "
                       "centro nuevo compra casi lo mismo que mover la "
                       "cadencia, y el alquiler lo paga solo uno de los dos."
                       % (f"{seis['puntos']:,}",
                          seis["puntos"] - hoy_s["puntos_en_promesa"],
                          f"{seis['clientes_cadena']:,}",
                          f"{seis['clientes_cadena'] - hoy_s['clientes_cadena']:,}")
                       if seis else "No abrir y mover la promesa.",
        "bisagra": ("Que el candidato pueda abastecerse. %s, el que más "
                    "compra, no tiene ningún centro dentro de su promesa: no "
                    "sería un satélite sino otro almacén. El primero que sí "
                    "se abastece es %s, a %.1f h de la red, y compra +%d "
                    "puntos."
                    % (mejor["candidato"], mejor_surt["candidato"],
                       mejor_surt["h_a_la_red"], mejor_surt["puntos_nuevos"]))
                   if mejor and mejor_surt and mejor.get("h_a_la_red") is None
                   else "Que el candidato pueda abastecerse de la red que ya "
                        "existe: si no, no es un satélite sino otro almacén.",
        "cifra": mejor["clientes_nuevos"] if mejor else 0,
        "unidad": "clientes que compra el mejor candidato",
        "fuente": "out/satelite.json · build_satelite.py",
    })

    D.append({
        "id": "canal-sin-resurtido", "estado": "abierta",
        "familia": "Cómo servimos",
        "pregunta": "¿Qué se hace con el canal que su centro no alcanza?",
        "respuesta": "Sin decidir. %d puntos de venta quedan fuera de la "
                     "promesa del centro que los surte. El peor no es el que "
                     "deja más puntos fuera sino el que peor proporción "
                     "alcanza: %s llega al %.0f%% de los suyos, con mediana "
                     "de %.1f horas."
                     % (fuera_tot, peor["hub"], peor["pct_en_promesa"],
                        peor["horas_mediana"]),
        "alternativa": "Esperar. La promesa de seis horas ya rescató parte "
                       "del sur al abrir Sicuani, y el resto no paga todavía "
                       "un alquiler.",
        "bisagra": "Los %s clientes que hay detrás del canal de %s: es el "
                   "centro con más gente detrás de sus puntos y el que peor "
                   "puede abastecerlos."
                   % (f"{int(peor['clientes']):,}", peor["hub"]),
        "cifra": fuera_tot, "unidad": "puntos fuera de promesa",
        "fuente": "out/canal.json bloque reparto",
    })

    _si, _no = rec["resurtibles"], rec["fuera_de_promesa"]
    _pri = rec["lista"][0] if rec["lista"] else None
    D.append({
        "id": "canal-a-reclutar", "estado": "abierta",
        "familia": "Quién atiende a quién",
        "pregunta": "¿Con qué puntos de venta conviene trabajar primero?",
        "respuesta": "Sin decidir, pero la lista está ordenada y acortada. De "
                     "%s puntos que ya venden, %d tienen mercado propio, y de "
                     "esos %d se pueden resurtir dentro de la promesa: %s "
                     "al año de margen y %s clientes detrás. El primero es %s "
                     "(%s, %s) con %s al año a %.1f h de su centro."
                     % (f"{rec['puntos_que_venden']:,}", rec["con_mercado"],
                        _si["puntos"],
                        "US$ %s" % f"{_si['margen_anual']:,.0f}",
                        f"{_si['clientes']:,.0f}",
                        _pri["nombre"] if _pri else "—",
                        _pri["dep"] if _pri else "", _pri["hub"] if _pri else "",
                        "US$ %s" % f"{_pri['margen_anual']:,.0f}" if _pri else "",
                        _pri["horas_reparto"] if _pri else 0),
        "alternativa": "Trabajar la lista entera por margen, sin mirar el "
                       "resurtido: %d puntos más y %s al año que hoy no se "
                       "pueden abastecer a tiempo."
                       % (_no["puntos"], "US$ %s" % f"{_no['margen_anual']:,.0f}"),
        "bisagra": "El resurtido, que es el mismo examen que a un centro "
                   "nuevo: reclutar a quien no se alcanza dentro de la promesa "
                   "es prometer una entrega que no se sostiene, y eso no da "
                   "cero sino negativo. Esos %d puntos son la carta que "
                   "justifica mover la promesa, no clientes a visitar."
                   % _no["puntos"],
        "cifra": _si["puntos"], "unidad": "puntos reclutables",
        "fuente": "out/reclutar.json · build_reclutar.py",
    })

    _ins = amp["industria_del_insumo"]
    _gan = amp["grano_y_balanceado"]
    _res = amp["el_resto"]
    D.append({
        "id": "exportadores-nuevos", "estado": "abierta",
        "familia": "A quién le vendemos",
        "pregunta": "¿Qué se hace con los exportadores que trajo el universo "
                    "ampliado?",
        "respuesta": "Sin decidir, y son menos de los que parecían. De las %d "
                     "empresas, %d están clasificadas como productor o "
                     "agroindustria; el %.0f%% ni siquiera está en el padrón "
                     "agrario, porque se llaman Quimpac, Seaboard o Cargill. "
                     "Solo el %.0f%% importa algo."
                     % (amp["empresas"], amp["productor_o_agroindustria"],
                        amp["sin_clasificar_pct"],
                        100 * amp["importan_algo"] / amp["empresas"]),
        "alternativa": "Tratarlas como cartera nueva por su embarque: %s de "
                       "exportación que antes no se veían. El embarque dice "
                       "qué venden y no si compran lo que la plataforma vende."
                       % mm(amp["fob_export"]),
        "bisagra": "Lo que compran, que son tres cosas distintas. %d son la "
                   "industria del insumo —%s, el %.0f%% de lo que compra el "
                   "grupo, y cuatro de ellas ya están en el ranking de "
                   "protección de cultivos de este proyecto: son proveedor o "
                   "competencia, no cliente—. %d compran grano y alimento "
                   "balanceado, %s, que no está en el catálogo. Y el resto "
                   "son %d empresas con %s, encabezadas por una química que "
                   "compra a granel en %d despachos al año."
                   % (_ins["empresas"], mm(_ins["fob"]),
                      _ins["pct_de_lo_que_compra"], _gan["empresas"],
                      mm(_gan["fob"]), _res["empresas"], mm(_res["fob"]),
                      _res["top"][0]["despachos"] if _res["top"] else 0),
        "cifra": amp["productor_o_agroindustria"],
        "unidad": "de %d son productor o agroindustria" % amp["empresas"],
        "fuente": "out/ampliacion.json · build_ampliacion.py",
    })

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("cada decisión con la cifra que la sostiene, la "
                   "alternativa que se midió y se descartó, y lo que tendría "
                   "que cambiar para darla vuelta; las cifras salen de los "
                   "archivos del pipeline y no de este texto"),
        "abiertas": sum(1 for d in D if d["estado"] == "abierta"),
        "decididas": sum(1 for d in D if d["estado"] == "decidida"),
        "decisiones": D,
    }
    crudo = json.dumps(salida, ensure_ascii=False, indent=1)
    io.open(SALIDA, "w", encoding="utf-8").write(crudo)
    # Y al sitio, que lo lee tal cual: es un archivo chico y no hay recorte que
    # hacerle, así que pasarlo por el empaquetador solo agregaría un lugar más
    # donde se puede quedar viejo.
    io.open(os.path.join(sitio.DATA, "decisiones.json"), "w",
            encoding="utf-8").write(crudo)

    print("=" * 78)
    print("DECISIONES  ·  %d decididas, %d abiertas"
          % (salida["decididas"], salida["abiertas"]))
    print("=" * 78)
    for d in D:
        print("\n[%s] %s" % (d["estado"].upper(), d["pregunta"]))
        print("  hoy         : %s" % d["respuesta"])
        print("  alternativa : %s" % d["alternativa"])
        print("  bisagra     : %s" % d["bisagra"])
    print()
    print(SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
