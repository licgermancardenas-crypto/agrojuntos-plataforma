# -*- coding: utf-8 -*-
"""Corre el pipeline en orden y falla si algo no está donde debe.

El orden importa y hasta ahora vivía en la cabeza de quien lo había corrido:
depurar antes que agregar, agregar antes que el panel —que lee del agregado la
frontera de completitud—, SENASA antes que acopio. Correrlos en otro orden no
revienta nada: produce cifras viejas mezcladas con nuevas, que es el fallo que
más caro sale porque nadie lo ve.

Cada etapa declara qué lee y qué escribe. De ahí salen dos cosas: el orden, y
la decisión de saltarse una etapa cuyas salidas ya son más nuevas que sus
entradas. Con `--forzar` se corre todo igual.

La descarga no entra por defecto: baja gigabytes de SUNAT y tarda horas. Va
aparte, con `--con-descarga`.

Uso:
    python scripts/pipeline.py                 lo que haga falta
    python scripts/pipeline.py --secar         qué haría, sin hacerlo
    python scripts/pipeline.py --desde export  desde esa etapa en adelante
    python scripts/pipeline.py --solo acopio   una sola
    python scripts/pipeline.py --forzar        todo, esté al día o no
"""
import argparse
import io
import os
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

IMP = "data/importaciones/processed/"
EXP = "data/exportaciones/processed/"

# nombre, script, entradas, salidas. Las entradas son lo que la etapa lee de
# otra etapa; los archivos crudos que ya están en disco no se listan.
ETAPAS = [
    ("descarga", "acumular_aduanas.py", [], ["data/aduanas_hist/manifiesto.json"],
     "baja de SUNAT las semanas que falten"),

    ("import-historico", "build_import_historico.py",
     ["data/aduanas_hist/manifiesto.json"], [IMP + "operaciones.csv"],
     "extrae las líneas de insumo de cada ZIP"),
    ("import-clasificar", "build_import_clasificar.py",
     [IMP + "operaciones.csv"], [IMP + "operaciones_clasificadas.csv"],
     "clasifica por partida arancelaria"),
    ("import-agregados", "build_import_agregados.py",
     [IMP + "operaciones_clasificadas.csv", IMP + "_semanas_procesadas.json"],
     [IMP + "mercado.json", IMP + "importadores.json", IMP + "anomalias.json"],
     "agrega por empresa y mercado, y mide la cobertura en días"),
    ("import-panel", "build_import_panel.py",
     [IMP + "operaciones_clasificadas.csv", IMP + "mercado.json"],
     [IMP + "panel.json"], "cubo categoría × año × partida × empresa"),
    ("import-precios", "build_import_precios.py",
     [IMP + "operaciones_clasificadas.csv"], [IMP + "precios.json"],
     "US$/kg donde el kilo significa algo"),

    ("export-historico", "build_export_historico.py",
     ["data/aduanas_hist/manifiesto.json"], [EXP + "operaciones.csv"],
     "extrae las líneas de agro de cada ZIP"),
    ("export-depurar", "build_export_depurar.py",
     [EXP + "operaciones.csv"],
     [EXP + "operaciones_limpias.csv", EXP + "depuracion.json"],
     "quita republicaciones y precios imposibles"),
    ("export-agregados", "build_export_agregados.py",
     [EXP + "operaciones_limpias.csv"],
     [EXP + "mercado.json", EXP + "exportadores.json", EXP + "anomalias.json"],
     "agrega por empresa, mercado y territorio"),
    ("export-panel", "build_export_panel.py",
     [EXP + "operaciones_limpias.csv", EXP + "mercado.json"],
     [EXP + "panel.json"], "cubo producto × destino × exportador"),
    ("export-web", "build_export_web.py",
     [EXP + "exportadores.json", EXP + "mercado.json"],
     [EXP + "exportadores_min.json"], "el recorte que baja el navegador"),
    ("export-figuras", "build_figs_export.py",
     [EXP + "mercado.json"],
     ["out/fig_export_serie.png", "out/fig_export_perfil_dep.png"],
     "la serie mensual y el perfil por región"),

    ("senasa", "build_senasa.py", [EXP + "exportadores.json"],
     ["out/senasa_exportadores.csv", "out/senasa_cobertura.json"],
     "plantas certificadas por producto y mercado"),
    ("acopio", "build_acopio.py",
     [EXP + "operaciones_limpias.csv", EXP + "mercado.json",
      "out/senasa_exportadores.csv", "out/hubs_asignacion.csv",
      "out/clusters_celda.csv", "out/sectores_2024.csv"],
     ["out/acopio.json", "out/acopio_distrito.csv", "out/acopio_hub.csv"],
     "sitúa la carga donde se produce y la cruza con los centros"),

    ("reporte", "reporte.py",
     [IMP + "mercado.json", EXP + "mercado.json", "out/acopio.json"],
     ["out/reporte_agrojuntos.html"], "arma el informe y lo imprime"),
]


def mtime(p):
    return os.path.getmtime(p) if os.path.exists(p) else None


def al_dia(entradas, salidas):
    """Una etapa está al día si todas sus salidas son más nuevas que la más
    reciente de sus entradas. Sin salidas, nunca lo está."""
    if not salidas or any(mtime(s) is None for s in salidas):
        return False
    ent = [mtime(e) for e in entradas if mtime(e) is not None]
    if not ent:
        return True
    return min(mtime(s) for s in salidas) >= max(ent)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--secar", action="store_true",
                    help="dice qué haría y no hace nada")
    ap.add_argument("--desde", help="etapa desde la que arrancar")
    ap.add_argument("--solo", help="una sola etapa")
    ap.add_argument("--con-descarga", action="store_true",
                    help="incluye la descarga de SUNAT, que tarda horas")
    a = ap.parse_args()

    etapas = [e for e in ETAPAS
              if e[0] != "descarga" or a.con_descarga or a.solo == "descarga"]
    nombres = [e[0] for e in etapas]
    if a.solo:
        if a.solo not in nombres:
            sys.exit("etapa desconocida: %s\nhay: %s" % (a.solo, ", ".join(nombres)))
        etapas = [e for e in etapas if e[0] == a.solo]
    elif a.desde:
        # Se acepta el prefijo: «--desde export» arranca en la primera de
        # exportación, que es como se piensa el pipeline cuando se corre a mano.
        idx = next((i for i, e in enumerate(etapas)
                    if e[0] == a.desde or e[0].startswith(a.desde)), None)
        if idx is None:
            sys.exit("etapa desconocida: %s\nhay: %s" % (a.desde, ", ".join(nombres)))
        etapas = etapas[idx:]

    print("pipeline · %d etapas" % len(etapas))
    corridas = saltadas = 0
    # En seco no basta con mirar las fechas: una etapa puede estar al día
    # ahora y dejar de estarlo en cuanto la anterior reescriba su entrada.
    # Sin esto, `--secar` decía «al día» de export-web mientras anunciaba que
    # iba a regenerar el mercado.json del que come, que es mentir en la
    # dirección más cómoda.
    tocados = set()
    for nom, script, ent, sal, que in etapas:
        faltan = [e for e in ent if not os.path.exists(e)]
        if faltan:
            print("\n  %-18s FALTA SU ENTRADA: %s" % (nom, faltan[0]))
            print("  la produce: %s" % (
                next((o for o, s, _, ss, _ in ETAPAS if faltan[0] in ss),
                     "ninguna etapa de este pipeline")))
            return 1
        si_toca = any(e in tocados for e in ent)
        if not a.forzar and not si_toca and al_dia(ent, sal):
            print("  %-18s al día" % nom)
            saltadas += 1
            continue
        tocados.update(sal)
        print("\n  %-18s %s" % (nom, que))
        if a.secar:
            corridas += 1
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, "scripts/" + script],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            print("    FALLÓ (%s)" % script)
            for l in (r.stdout or "").splitlines()[-6:]:
                print("      " + l)
            for l in (r.stderr or "").splitlines()[-6:]:
                print("      " + l)
            return 1
        ultimo = [l for l in (r.stdout or "").splitlines() if l.strip()][-1:]
        print("    %.0f s%s" % (time.time() - t0,
                                " · " + ultimo[0].strip()[:70] if ultimo else ""))
        corridas += 1

    print("\n%d etapas corridas, %d al día" % (corridas, saltadas))
    if not a.secar and any(e[0] == "reporte" for e in etapas):
        print("recuerda medir las páginas: python scripts/medir_paginas.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
