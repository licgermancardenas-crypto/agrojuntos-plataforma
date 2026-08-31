# -*- coding: utf-8 -*-
"""Paso 2 · Descarga los datasets de contexto alojados en GitHub.

Trae dos cosas que el análisis de insumos necesita como marco:

  cropdatape           series de producción, rendimiento y precio en chacra del
                       MIDAGRI, ya ordenadas en formato tidy
  peru-geojson         polígonos y UBIGEO de departamentos, provincias y
                       distritos, para ubicar cada RUC en el territorio

Se usa la API de GitHub en vez de `git clone` porque solo hacen falta unos
archivos de cada repositorio y clonar traería el historial completo.
"""
import json
import os
import sys
import time

import requests

RAW = "raw_data/github"
API = "https://api.github.com"
HEADERS = {"User-Agent": "agro-insumos-pe/1.0",
           "Accept": "application/vnd.github+json"}

REPOS = [
    # repo, subcarpetas de interés, extensiones que queremos
    #
    # juaneladio publica el UBIGEO nacional completo en GeoJSON; joseluisq,
    # pese a su nombre, solo cubre Lima y Callao, y geoperu/cropdatape
    # entregan .rda, que es serialización binaria de R y requiere R para
    # leerse. Se descargan igual para dejar constancia de la fuente.
    ("juaneladio/peru-geojson", [""], (".geojson",)),
    ("omarbenites/cropdatape", ["data", "data-raw", "inst/extdata"],
     (".csv", ".rda", ".rds", ".xlsx")),
    ("joseluisq/peru-geojson-datasets", [""], (".geojson", ".json")),
    ("PaulESantos/geoperu", ["data", "data-raw"], (".csv", ".rda", ".geojson")),
]


def log(msg):
    print(msg, flush=True)


def listar(repo, ruta=""):
    url = f"{API}/repos/{repo}/contents/{ruta}".rstrip("/")
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            return []
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:
        return []


def bajar(item, destino):
    url = item.get("download_url")
    if not url:
        return False
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino) and os.path.getsize(destino) == item.get("size", -1):
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=300)
        if r.status_code != 200:
            return False
        with open(destino, "wb") as fh:
            fh.write(r.content)
        return True
    except Exception:
        return False


def recorrer(repo, ruta, exts, base, prof=0):
    """Baja recursivamente los archivos con las extensiones pedidas."""
    n = 0
    for item in listar(repo, ruta):
        if item["type"] == "dir" and prof < 2:
            n += recorrer(repo, item["path"], exts, base, prof + 1)
        elif item["type"] == "file" and item["name"].lower().endswith(exts):
            destino = os.path.join(base, item["path"])
            if bajar(item, destino):
                n += 1
                log(f"    {item['path'][:58]:60s} {item['size']:>9,} B")
        time.sleep(0.1)                      # cortesía con la API pública
    return n


def main():
    os.makedirs(RAW, exist_ok=True)
    resumen = {}
    for repo, rutas, exts in REPOS:
        carpeta = os.path.join(RAW, repo.split("/")[1])
        log(f"\n[{repo}]")
        meta = requests.get(f"{API}/repos/{repo}", headers=HEADERS, timeout=60)
        if meta.status_code != 200:
            log(f"    no accesible (HTTP {meta.status_code})")
            resumen[repo] = 0
            continue
        total = sum(recorrer(repo, r, exts, carpeta) for r in rutas)
        if total == 0:                       # sin subcarpetas conocidas: raíz
            total = recorrer(repo, "", exts, carpeta)
        log(f"    -> {total} archivos")
        resumen[repo] = total

    with open(os.path.join(RAW, "_resumen.json"), "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, indent=2, ensure_ascii=False)
    log(f"\ntotal descargado: {sum(resumen.values())} archivos en {RAW}/")
    return 0 if sum(resumen.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
