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

    # --- la cadena geografica ------------------------------------------------
    # Estaba fuera del orquestador y no debia estarlo: cuando la pendiente
    # entro en el ruteo hubo que reconstruir a mano —grep mediante— que las
    # horas alimentan la grilla H3, la grilla alimenta la eleccion de centros y
    # los territorios, y los territorios alimentan la carga de acopio. Cada uno
    # de esos pasos es una etapa con entradas y salidas declaradas; declararlas
    # aqui es lo unico que impide volver a reconstruirlo de memoria.
    ("vial", "build_vial_compacto.py", [],
     ["data/vial/compacto/PE-LIM.npz"],
     "convierte la red vial de Overpass a arreglos, una vez por bajada"),
    ("ruteo", "build_ruteo.py",
     ["data/vial/compacto/PE-LIM.npz", "out/modelo_v2_sector.csv"],
     ["out/ruteo_sector.csv", "out/ruteo_departamento.csv"],
     "horas y costo al centro y al puerto, con pendiente"),
    ("h3", "build_h3.py", ["out/ruteo_sector.csv"],
     ["out/h3_r5.csv", "out/h3_r6.csv"],
     "agrega la demanda en la grilla hexagonal"),
    ("hubs", "build_hubs.py",
     ["out/h3_r5.csv", "out/ruteo_sector.csv", "data/vial/compacto/PE-LIM.npz",
      "data/peru_distrital_simple.geojson"],
     ["out/hubs_cobertura.csv", "out/hubs_asignacion.csv",
      "out/hubs_distrito.csv", "out/hubs_matriz_tiempos.npy"],
     "elige donde poner los centros, por cobertura maxima"),
    # Lee tambien la red vial: despues de agrupar reparte lo que quedo fuera
    # entre los territorios que lo alcanzan, y para eso rutea.
    ("clusters", "build_clusters.py",
     ["out/h3_r6.csv", "data/vial/compacto/PE-LIM.npz"],
     ["out/clusters_territorio.csv", "out/clusters_celda.csv"],
     "traza los territorios de venta sobre la densidad del mercado"),
    ("cartera", "build_cartera.py",
     ["out/clusters_celda.csv", "out/hubs_asignacion.csv",
      "out/ruteo_sector.csv"],
     ["out/cartera_territorio.csv", "out/cartera_empresa.csv"],
     "que cartera cae en cada territorio y a que centro responde"),

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

    # `universo.py` va declarado como entrada de todo lo que decide con él qué
    # es agro. El orquestador vigila el script de la etapa, no lo que el script
    # importa: sin esta línea, ampliar el universo arancelario dejaba las tres
    # etapas «al día» sirviendo el recorte viejo. Van tres veces el mismo
    # defecto —`mapa-geo`, `reporte` y ahora esto—, y siempre por lo mismo.
    ("export-historico", "build_export_historico.py",
     ["data/aduanas_hist/manifiesto.json", "scripts/universo.py"],
     [EXP + "operaciones.csv"],
     "extrae las líneas de agro de cada ZIP"),
    ("export-depurar", "build_export_depurar.py",
     [EXP + "operaciones.csv"],
     [EXP + "operaciones_limpias.csv", EXP + "depuracion.json"],
     "quita republicaciones y precios imposibles"),
    ("export-agregados", "build_export_agregados.py",
     [EXP + "operaciones_limpias.csv", "scripts/universo.py"],
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
      "out/senasa_exportadores.csv", "out/hubs_distrito.csv",
      "out/clusters_celda.csv", "out/sectores_2024.csv"],
     ["out/acopio.json", "out/acopio_distrito.csv", "out/acopio_hub.csv"],
     "sitúa la carga donde se produce y la cruza con los centros"),

    ("altitud", "build_altitud.py",
     [EXP + "operaciones_limpias.csv", "out/acopio.json",
      "out/acopio_distrito.csv", "out/modelo_v2_sector.csv",
      "out/hubs_cobertura.csv"],
     ["out/altitud.json", "out/altitud_sector.csv", "out/altitud_distrito.csv"],
     "la cota y el piso ecológico de cada capa"),

    ("ccpp", "build_ccpp.py", ["data/inei/dpto01.xlsx"],
     ["out/ccpp.csv", "out/ccpp.json"],
     "el padrón de centros poblados del INEI, con coordenadas de OSM"),
    ("canal", "build_canal.py",
     ["out/ruteo_sector.csv", "out/osm_prospectos.csv", "out/ccpp.csv",
      "out/empresas_agro_activas.csv", "out/clusters_celda.csv",
      "out/red_elegida.json"],
     ["out/canal.json", "out/canal_punto.csv", "out/canal_territorio.csv"],
     "quién le vende al cliente que el almacén no alcanza"),

    ("mapa-geo", "build_mapa_geo.py",
     # Lee tambien los centros y su asignacion: con la lista corta quedaba
     # «al dia» dibujando la red anterior mientras el resto del sitio ya
     # mostraba la nueva. Una etapa que declara de menos miente mejor que una
     # que no se declara.
     ["out/clusters_territorio.csv", "out/clusters_celda.csv",
      "out/ruteo_sector.csv", "out/hubs_cobertura.csv",
      "out/hubs_asignacion.csv", "out/h3_r5.csv"],
     ["out/mapa_geo.json", "out/mapa_capas.json"],
     "el atlas geoespacial que baja el navegador"),
    ("dashboard", "build_dashboard_data.py",
     ["out/ruteo_departamento.csv", "out/clusters_territorio.csv",
      "out/cartera_territorio.csv", "out/hubs_asignacion.csv",
      "out/aduanas_exportaciones.csv", "out/aduanas_importaciones.csv",
      "scripts/universo.py"],
     # En el repositorio, que es donde el sitio los lee. Antes apuntaban al
     # dashboard viejo que esta al lado de MAPEO, y de ahi habia que copiarlos
     # a mano: ver `scripts/sitio.py`, que es donde se explica por que habia
     # dos arboles y cual sobrevive.
     ["../../../_repo/dashboard/data/resumen.json",
      "../../../_repo/dashboard/data/logistica.json"],
     "los JSON que sirve el sitio"),

    # Con qué puntos de canal trabajar primero. El margen ordena la lista; el
    # resurtido la acorta, y es el mismo examen que a un centro nuevo.
    ("reclutar", "build_reclutar.py",
     ["out/canal_punto.csv", "out/canal.json"],
     ["out/reclutar.json", "out/reclutar.csv",
      "../../../_repo/dashboard/data/reclutar.json"],
     "con qué puntos de venta trabajar primero"),

    # En qué orden se recorren los puntos reclutables. Los tiempos son
    # medidos; la jornada y el tiempo de visita son supuestos declarados.
    ("rutas", "build_rutas.py",
     ["out/reclutar.json", "out/canal_punto.csv", "out/red_elegida.json",
      "data/vial/compacto/PE-LIM.npz"],
     ["out/rutas.json", "out/rutas.csv",
      "../../../_repo/dashboard/data/rutas.json"],
     "las rutas de visita, en jornadas que vuelven al centro"),

    # La cobertura de la red pesada por la demanda de cada mes. La cifra plana
    # pesa el año entero, y las regiones mal cubiertas son justo las que
    # concentran su compra: el promedio anual esconde una banda de diez puntos.
    ("cobertura-mes", "build_cobertura_mes.py",
     ["out/hubs_asignacion.csv", "out/estacionalidad_region.csv"],
     ["out/cobertura_mes.json",
      "../../../_repo/dashboard/data/cobertura_mes.json"],
     "la cobertura mes a mes, pesada por la demanda"),

    # Qué compra un centro más sobre la red vigente. Era un diagnóstico de una
    # vez; es etapa desde que el módulo de decisiones publica esa pregunta como
    # abierta, porque una decisión abierta cuyo número solo existe en la
    # terminal de quien corrió el script es una decisión sin dato.
    ("satelite", "build_satelite.py",
     ["out/red_elegida.json", "out/hubs_matriz_tiempos.npy",
      "out/hubs_asignacion.csv", "out/h3_r5.csv", "out/ruteo_sector.csv",
      "out/empresas_agro_activas.csv", "out/osm_prospectos.csv"],
     ["out/satelite.json", "out/diag_satelite.csv"],
     "qué compra un centro más, y si podría abastecerse"),

    # Qué insumo, para qué cultivo, en qué región y en qué mes. Cruza el
    # calendario de siembra con la hoja de costos de MIDAGRI; ninguno de los
    # dos, solo, contesta la pregunta que hace un comercial.
    ("canasta", "build_canasta.py",
     ["out/estacionalidad_detalle.csv", "out/costos_cultivo.csv"],
     ["out/canasta.json", "out/canasta_detalle.csv",
      "../../../_repo/dashboard/data/canasta.json"],
     "el insumo por cultivo, región y mes"),

    # Qué compran las empresas que trajo el universo ampliado. El embarque dice
    # qué venden; solo la importación dice si compran lo que la plataforma
    # vende, y la diferencia entre las dos cosas es la decisión.
    ("ampliacion", "build_ampliacion.py",
     [EXP + "operaciones_limpias.csv", "out/aduanas_importaciones.csv",
      "out/comercio_importadores.csv", "out/import_agro_lineas.csv",
      "out/empresas_agro_activas.csv", "scripts/universo.py"],
     ["out/ampliacion.json"],
     "qué compran los exportadores que trajo el universo ampliado"),

    # Las decisiones se arman al final: leen lo que todas las demás dejaron.
    ("decisiones", "build_decisiones.py",
     ["out/red_elegida.json", "out/canal.json", "out/clusters_absorcion.json",
      "out/acopio.json", "out/hubs_cobertura.csv", "out/satelite.json",
      "out/ampliacion.json", "out/cobertura_mes.json", "out/reclutar.json",
      EXP + "mercado.json"],
     ["out/decisiones.json",
      "../../../_repo/dashboard/data/decisiones.json"],
     "cada decisión con su alternativa medida y su bisagra"),

    ("reporte", "reporte.py",
     # Todas las que lee, sacadas del propio archivo y no de memoria. Declarar
     # solo unas cuantas es lo que dejaba el informe «al día» con un PDF
     # armado media hora antes que los datos que muestra: pasó con `mapa-geo`,
     # pasó aquí con las páginas nuevas, y volvió a pasar cuando el corte de
     # aduanas cambió de once semanas a 246 y el informe no se enteró.
     [EXP + "exportadores.json", EXP + "mercado.json", EXP + "panel.json",
      IMP + "importadores.json", IMP + "mercado.json", IMP + "panel.json",
      IMP + "precios.json", "out/acopio.json", "out/aduanas_ventana.json",
      "out/agroexport_aduana.csv", "out/agroexport_departamento.csv",
      "out/agroexport_producto.csv", "out/altitud.json", "out/canal.json",
      "out/cartera_empresa.csv", "out/cartera_hub.csv",
      "out/cartera_territorio.csv", "out/cenagro_departamento.csv",
      "out/clusters_territorio.csv", "out/comercio_exportadores.csv",
      "out/comercio_importadores.csv", "out/costos_cultivo.csv",
      "out/cultivos_nacional.csv", "out/embudo_departamento.csv",
      "out/empresas_agro_activas.csv", "out/estacionalidad_nacional.csv",
      "out/estacionalidad_region.csv", "out/h3_r5.csv",
      "out/hubs_cobertura.csv", "out/import_agro_categoria.csv",
      "out/import_agro_excluidas.csv", "out/import_agro_glosa.csv",
      "out/import_agro_lineas.csv", "out/import_agro_referencia.csv",
      "out/logistica_departamento.csv", "out/modelo_v2_departamento.csv",
      "out/modelo_v2_sector.csv", "out/modelo_v3_departamento.csv",
      "out/osm_prospectos.csv", "out/puertos.csv", "out/red_elegida.json",
      "out/ruteo_departamento.csv", "out/ruteo_sector.csv",
      "out/som_escenarios.csv", "out/ventas_cliente.csv",
      "out/ventas_doc.csv"],
     ["out/reporte_agrojuntos.html"], "arma el informe y lo imprime"),
]


def mtime(p):
    return os.path.getmtime(p) if os.path.exists(p) else None


def al_dia(entradas, salidas, script=None):
    """Una etapa está al día si todas sus salidas son más nuevas que la más
    reciente de sus entradas. Sin salidas, nunca lo está.

    El propio script cuenta como entrada. Sin eso, cambiar un criterio en el
    código dejaba la etapa «al día» sirviendo la cifra vieja: se agregó
    Sicuani a la red en `build_hubs.py`, se corrió el pipeline entero y
    contestó «0 etapas corridas, 21 al día» con los siete centros anteriores.
    El dato no había cambiado; la regla que lo produce, sí."""
    if not salidas or any(mtime(s) is None for s in salidas):
        return False
    ent = [mtime(e) for e in entradas if mtime(e) is not None]
    if script and mtime(script) is not None:
        ent.append(mtime(script))
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
        if not a.forzar and not si_toca and al_dia(
                ent, sal, os.path.join("scripts", script)):
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

    # Publicar no es una etapa con entradas y salidas: es lo que hay que hacer
    # siempre al final, y por eso corre aunque no se haya recalculado nada.
    # Compara contenido, así que repetirlo no cuesta ni ensucia el repositorio.
    #
    # Iba a mano hasta hoy, y a mano se olvidaba: `_repo/datos/` llegó a tener
    # 35 archivos atrasados mientras `out/` estaba al día. El pipeline era
    # riguroso hasta la puerta y ahí soltaba.
    print()
    r = subprocess.run(
        [sys.executable, os.path.join("scripts", "publicar.py")]
        + (["--secar"] if a.secar else []),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linea in (r.stdout or "").splitlines():
        print("  " + linea)
    if r.returncode:
        print((r.stderr or "")[-600:])
        return 1

    if not a.secar and any(e[0] == "reporte" for e in etapas):
        print("recuerda medir las páginas: python scripts/medir_paginas.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
