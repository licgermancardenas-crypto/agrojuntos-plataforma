# -*- coding: utf-8 -*-
"""Revisa los datos publicados sin abrir un navegador.

`verificar.py` comprueba que la página no esté rota, pero tarda minutos y
necesita Chrome. Esto mira lo que se puede mirar leyendo los archivos, que es
barato y cubre otra clase de fallo: un JSON que el navegador no sabe parsear,
una cuadratura que dejó de dar, una cifra del README que ya no corresponde a
los datos.

Ese último caso no es teórico. La documentación de este proyecto se desfasó
tres veces en un día —cifras de exportación anteriores a la depuración, «241
semanas» donde había 244, operaciones de importación tomadas del histórico
completo en vez de la ventana de cinco años— y las tres se encontraron a mano.
Es exactamente el trabajo que conviene que haga una máquina en cada push.

Uso:
    python scripts/verificar_datos.py
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "dashboard", "data")
fallos = []


def falla(msg):
    fallos.append(msg)
    print("  FALLA  " + msg)


def carga(rel):
    """Un JSON del sitio, con las trampas que el navegador no perdona."""
    p = os.path.join(WEB, rel)
    if not os.path.exists(p):
        falla("no existe " + rel)
        return None
    crudo = io.open(p, encoding="utf-8").read()
    # Python escribe Infinity y NaN sin protestar y `JSON.parse` los rechaza:
    # así se quedó el atlas sin dibujar una vez, sin más síntoma que una
    # página en blanco.
    for veneno in ("Infinity", "NaN"):
        if re.search(r"(?<![\"\w])%s(?![\"\w])" % veneno, crudo):
            falla("%s contiene %s, que JSON.parse rechaza" % (rel, veneno))
    try:
        return json.loads(crudo)
    except Exception as e:
        falla("%s no parsea: %s" % (rel, e))
        return None


def cuadraturas():
    print("\ncuadraturas de los agregados")
    for lado in ("importaciones", "exportaciones"):
        an = carga("%s/anomalias.json" % lado)
        if not an:
            continue
        malas = [k for k, v in an.items()
                 if k.startswith("cuadra_") and v is not True]
        if malas:
            falla("%s: no cuadran %s" % (lado, malas))
        else:
            n = sum(1 for k in an if k.startswith("cuadra_"))
            print("  %-14s %d cuadraturas, todas OK" % (lado, n))


def coherencia():
    """Lo que un archivo dice de otro tiene que coincidir."""
    print("\ncoherencia entre archivos")
    exp = carga("exportaciones/mercado.json")
    pan = carga("exportaciones/exportadores_min.json")
    aco = carga("acopio.json")
    if not (exp and pan and aco):
        return
    if pan["meta"]["ultimo_registro"] != exp["ultimo_registro"]:
        falla("el recorte web y el agregado difieren en el último registro")
    else:
        print("  el recorte web y el agregado hablan del mismo corte: ok")
    # El acopio se calcula sobre los años en que el ubigeo viene lleno.
    usados = exp["departamentos"]["anios_usados"]
    if aco["anios"] != usados:
        falla("acopio usa %s y el agregado declara %s" % (aco["anios"], usados))
    else:
        print("  acopio se limita a los años con ubigeo (%s): ok"
              % ", ".join(usados))
    # El alcance de un centro no puede encoger al ampliar el radio.
    malos = [h["hub"] for h in aco["hubs"]
             if not (h["fob_2h_mm"] <= h["fob_4h_mm"] <= h["fob_6h_mm"])]
    if malos:
        falla("el alcance no crece con el radio en %s" % malos[:3])
    else:
        print("  el alcance de los %d centros crece con el radio: ok"
              % len(aco["hubs"]))


def documentacion():
    """Las cifras del README, contra los datos de los que salen."""
    print("\nlas cifras de la documentación, contra los datos")
    # Todos los documentos de la raíz y no una lista escrita a mano: al partir
    # el README en cuatro metodologías, las cifras se mudaron de archivo y esta
    # comprobación empezó a fallar por buscarlas donde ya no estaban. Con el
    # glob, una cifra vale esté donde esté escrita, que es lo que importa.
    txt = ""
    for p in sorted(glob.glob(os.path.join(RAIZ, "*.md"))):
        txt += io.open(p, encoding="utf-8").read()
    exp = carga("exportaciones/mercado.json")
    imp = carga("importaciones/mercado.json")
    aco = carga("acopio.json")
    log = carga("logistica.json")
    red = carga("red.json")
    can = carga("canal.json")
    if not (exp and imp and aco and log and red and can and txt):
        return
    mil = lambda v: "{:,}".format(int(round(v)))          # noqa: E731
    esperadas = [
        ("exportadores con RUC", mil(exp["empresas_con_dato"])),
        ("agroexportación 2025", mil(exp["por_anio"]["2025"]["fob"] / 1e6)),
        ("agroexportación 5 años", mil(exp["total"]["fob"] / 1e6)),
        ("series de embarque", mil(exp["operaciones"])),
        ("importación · operaciones", mil(imp["operaciones"])),
        ("importación · empresas", mil(imp["empresas_con_dato"])),
        ("distritos con embarque", str(aco["distritos"])),
        ("plantas certificadas", str(aco["senasa"]["empacadoras"])),
        ("plantas sin embarque propio", str(aco["senasa"]["sin_embarque_propio"])),
        ("distritos huérfanos", str(aco["huerfanos"]["distritos"])),
        # La accesibilidad se movió nueve puntos al entrar la pendiente en el
        # ruteo, y el README tenía la cifra vieja. Las dos van juntas: la de
        # hoy y la de antes, porque el documento explica el cambio.
        ("mercado bajo 2 h", "%.1f%%" % log["meta"]["sam_bajo_2h"]),
        ("mercado bajo 2 h, sin pendiente",
         "%.1f%%" % log["meta"]["sam_bajo_2h_llano"]),
        ("sectores fuera del grafo vial",
         str(log["meta"]["sectores_sin_grafo"])),
        # La promesa de servicio es una decisión y la documentación la
        # explica; si alguien la cambia en `build_hubs.py` sin tocar el texto,
        # el README quedaría defendiendo una red que ya no existe.
        ("centros de la red", str(len(red["centros"]))),
        ("cobertura en promesa", "%.1f%%" % red["sam_cubierto_promesa_pct"]),
        ("cobertura a 2 h", "%.1f%%" % red["sam_cubierto_2h_pct"]),
        ("clientes con canal cerca", "{:,}".format(can["con_canal"]["clientes"])),
        ("clientes sin ningún punto", "{:,}".format(
            can["sin_candidato"]["clientes"])),
        ("clientes con algún sitio donde abrir",
         "{:,}".format(can["con_sitio"]["clientes"])),
        ("puntos del padrón", "{:,}".format(can["candidatos"]["canal"])),
        ("clientes con la cadena completa",
         "{:,}".format(can["cadena_completa"]["clientes"])),
        ("puntos con mercado propio",
         "{:,}".format(can["viabilidad"]["puntos_con_mercado"])),
        ("margen del mayor punto",
         "{:,.0f}".format(can["viabilidad"]["escenarios"][1]["margen_mayor"])),
    ]
    for que, valor in esperadas:
        if valor in txt:
            print("  %-30s %s: ok" % (que, valor))
        else:
            falla("la documentación no dice %s (%s), que es lo que hay en los "
                  "datos" % (valor, que))


def main():
    print("verificación de los datos publicados")
    for rel in ("exportaciones/mercado.json", "exportaciones/exportadores_min.json",
                "exportaciones/anomalias.json", "importaciones/mercado.json",
                "importaciones/panel.json", "importaciones/anomalias.json",
                "acopio.json", "resumen.json"):
        if carga(rel) is not None:
            print("  %-42s parsea" % rel)
    cuadraturas()
    coherencia()
    documentacion()
    print("\n" + ("TODO OK" if not fallos else "%d FALLAS" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
