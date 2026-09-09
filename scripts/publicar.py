# -*- coding: utf-8 -*-
"""Lleva al repositorio lo que el pipeline acaba de calcular.

El pipeline es riguroso hasta `out/`: declara qué lee y qué escribe cada etapa,
corre lo que haga falta y se niega a decir «al día» cuando una entrada es más
nueva que su salida. Y ahí se acababa. De `out/` al repositorio se copiaba a
mano, y lo que se copia a mano se olvida.

No es hipotético. Al abrir esta sesión, `_repo/datos/` tenía **35 archivos
atrasados**, algunos por semanas: la vista de Importación del sitio anunciaba
«diez semanas, junio a agosto de 2026» sobre un archivo que ya llevaba 246
semanas, y el ranking de protección de cultivos publicaba US$ 8,823 MM anuales
donde el dato daba 359. Las cifras estaban bien calculadas en `out/`. Lo que
falló fue el reparto, que no tenía dueño.

Esto le pone dueño. **Solo actualiza archivos que ya existen en el
repositorio**: no inventa carpetas ni publica intermedios nuevos por accidente,
y lo que hoy no se versiona sigue sin versionarse hasta que alguien lo decida a
propósito. Al revés sí avisa: si un archivo publicado dejó de tener fuente en
`out/`, lo dice, porque eso significa que el sitio sirve algo que ya nadie
genera.

Los JSON del navegador no pasan por aquí: desde `sitio.py` los generadores
escriben directamente en `_repo/dashboard/data`, que es donde el sitio los lee.

Uso:
    python scripts/publicar.py            publica
    python scripts/publicar.py --secar    dice qué haría y no toca nada
"""
import filecmp
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitio                                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(RAIZ, "out")
# Los agregados de comercio exterior no viven en `out/` sino junto a sus
# operaciones, y en el repositorio van a su propia carpeta. El nombre cambia en
# un caso —el libro de semanas lleva guion bajo delante en el disco de trabajo
# y no en el publicado—, así que el par se escribe entero.
PROCESADOS = {
    "exportaciones": os.path.join(RAIZ, "data", "exportaciones", "processed"),
    "importaciones": os.path.join(RAIZ, "data", "importaciones", "processed"),
}
RENOMBRES = {"semanas_procesadas.json": "_semanas_procesadas.json"}
# Lo que se publica sin pasar por `out/`: las fronteras, que son insumo y no
# resultado, y el manifiesto de aduanas, que vive con los ZIP que describe. Van
# nombrados uno a uno para que la lista de «publicados sin fuente» siga
# significando lo que dice —nadie los regenera— y no se llene de falsos.
DESDE_DATA = {
    "geo/peru_departamental_simple.geojson": "peru_departamental_simple.geojson",
    "geo/peru_distrital_simple.geojson": "peru_distrital_simple.geojson",
    "geo/peru_provincial_simple.geojson": "peru_provincial_simple.geojson",
    "comercio/aduanas_manifiesto.json": "aduanas_hist/manifiesto.json",
    "importaciones/manifiesto_aduanas.json": "aduanas_hist/manifiesto.json",
}


def fuente(rel):
    """De dónde sale el archivo publicado `rel`, o None si de ningún sitio."""
    rel = rel.replace("\\", "/")
    if rel in DESDE_DATA:
        p = os.path.join(RAIZ, "data", DESDE_DATA[rel])
        return p if os.path.exists(p) else None
    carpeta, nombre = os.path.split(rel)
    origen = RENOMBRES.get(nombre, nombre)
    if carpeta in PROCESADOS:
        p = os.path.join(PROCESADOS[carpeta], origen)
        if os.path.exists(p):
            return p
    p = os.path.join(OUT, origen)
    return p if os.path.exists(p) else None


def main():
    secar = "--secar" in sys.argv
    if not sitio.existe():
        sys.exit("no encuentro el repositorio en %s: ¿se movió MAPEO?"
                 % sitio.REPO)
    if not os.path.isdir(sitio.DATOS):
        sys.exit("no encuentro %s" % sitio.DATOS)

    nuevos, iguales, huerfanos = [], 0, []
    for raiz, _, files in os.walk(sitio.DATOS):
        for f in files:
            dst = os.path.join(raiz, f)
            rel = os.path.relpath(dst, sitio.DATOS)
            src = fuente(rel)
            if src is None:
                huerfanos.append(rel)
                continue
            if filecmp.cmp(src, dst, shallow=False):
                iguales += 1
                continue
            if not secar:
                shutil.copy2(src, dst)
            nuevos.append((rel, os.path.getsize(src)))

    print("publicación de datos%s" % ("  ·  SIN TOCAR NADA" if secar else ""))
    print("  al día ya            : %d archivos" % iguales)
    print("  %s: %d archivos"
          % ("se actualizarían    " if secar else "actualizados        ",
             len(nuevos)))
    for rel, tam in sorted(nuevos, key=lambda x: -x[1])[:20]:
        print("      %-52s %8.1f MB" % (rel.replace("\\", "/"), tam / 1e6))
    if len(nuevos) > 20:
        print("      ... y %d más" % (len(nuevos) - 20))
    if huerfanos:
        # No se borran: puede ser un dato que se publicó una vez a propósito.
        # Pero que el sitio sirva algo que ya nadie genera hay que saberlo.
        print("  publicados sin fuente en out/ (%d): nadie los regenera"
              % len(huerfanos))
        for rel in sorted(huerfanos)[:12]:
            print("      " + rel.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
