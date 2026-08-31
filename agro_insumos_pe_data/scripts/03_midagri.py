# -*- coding: utf-8 -*-
"""Paso 3b · Contexto productivo del MIDAGRI.

Plan de contingencia previsto en el encargo. No llegó a hacer falta —aduanet
entrega los microdatos sin CAPTCHA ni bloqueo— pero el contexto de producción
sí es necesario para interpretar el consumo de insumos, así que se descarga
igual: sin saber cuántas hectáreas se siembran y cuándo, el valor importado no
se puede traducir a demanda.

Fuentes que respondieron en 2026:

  gob.pe/institucion/midagri   Anuario de Producción Agrícola, en Excel. Trae
                               superficie sembrada y cosechada de 145 cultivos
                               por región, con desagregación mensual
  inei.gob.pe                  Costos de producción por hectárea (ENA 2018),
                               desagregados por ítem para 73 cultivos

Notas de terreno: siea.midagri.gob.pe no resolvía DNS y datosabiertos.gob.pe
respondía 418 al cliente por defecto; ambos se sortean yendo al CDN de gob.pe,
que sí sirve los mismos archivos.
"""
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

DEST = "raw_data/midagri"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

PAGINAS = [
    ("anuario_produccion_agricola",
     "https://www.gob.pe/institucion/midagri/informes-publicaciones/"
     "2730325-compendio-anual-de-produccion-agricola"),
]
DIRECTOS = [
    ("inei_costos_produccion_ena2018.pdf",
     "https://www.inei.gob.pe/media/MenuRecursivo/investigaciones/"
     "costos-de-produccion-v7.pdf"),
]


def log(m):
    print(m, flush=True)


def bajar(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        log(f"  ya estaba  {os.path.basename(dest)[:52]:54s} "
            f"{os.path.getsize(dest):>11,} B")
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=600)
        if r.status_code != 200 or len(r.content) < 10000:
            log(f"  fallo      {os.path.basename(dest)[:52]} (HTTP {r.status_code})")
            return False
        with open(dest, "wb") as fh:
            fh.write(r.content)
        log(f"  descargado {os.path.basename(dest)[:52]:54s} {len(r.content):>11,} B")
        return True
    except Exception as ex:
        log(f"  fallo      {os.path.basename(dest)[:52]} ({type(ex).__name__})")
        return False


def enlaces_excel(url):
    """Extrae del portal los enlaces a los cuadros en Excel más recientes."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=300)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    sopa = BeautifulSoup(r.text, "html.parser")
    salida = []
    for a in sopa.find_all("a", href=True):
        h = a["href"]
        if re.search(r"\.xlsx?(\?|$)", h, re.I) and "cuadros" in h.lower():
            salida.append(h if h.startswith("http") else "https://www.gob.pe" + h)
    # el nombre incluye el año; nos quedamos con los dos más recientes
    return sorted(set(salida))[-2:]


def main():
    os.makedirs(DEST, exist_ok=True)
    n = 0
    for nombre, url in PAGINAS:
        log(f"[{nombre}]")
        for i, enlace in enumerate(enlaces_excel(url)):
            ext = ".xlsx" if ".xlsx" in enlace.lower() else ".xls"
            anio = re.search(r"(20\d\d)", enlace)
            etiqueta = anio.group(1) if anio else str(i)
            if bajar(enlace, os.path.join(DEST, f"{nombre}_{etiqueta}{ext}")):
                n += 1
    log("[fuentes directas]")
    for nombre, url in DIRECTOS:
        if bajar(url, os.path.join(DEST, nombre)):
            n += 1
    log(f"\ntotal: {n} archivos en {DEST}/")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
