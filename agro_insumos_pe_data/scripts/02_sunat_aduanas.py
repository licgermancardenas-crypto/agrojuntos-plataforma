# -*- coding: utf-8 -*-
"""Paso 3 · Descarga los microdatos de aduanas de SUNAT.

No hace falta sortear CAPTCHA: SUNAT publica las bases completas de regímenes
definitivos en aduanet.gob.pe/aduanas/informae en cumplimiento de la Ley 27806
de Transparencia, como archivos DBF comprimidos y de descarga directa.

    ma<ddDDmmyy>.zip   importación definitiva, formato A
                       RUC del importador, razón social, partida NANDINA,
                       FOB, peso neto y país de origen
    mb<ddDDmmyy>.zip   importación formato B, datos del proveedor extranjero
    x<ddDDmmyy>.zip    exportación definitiva
    idv<ddDDmmyy>.zip  informes de verificación

SUNAT mantiene una ventana móvil de unas diez semanas, no un histórico. Los
nombres codifican la semana y no se pueden generar: se leen del índice.

El servidor corta las conexiones largas —los archivos de importación pesan
263 MB descomprimidos— así que cada descarga se valida contra el
Content-Length declarado y se reintenta si el ZIP no abre.
"""
import os
import re
import sys
import time
import zipfile

import requests
from bs4 import BeautifulSoup

INDICE = "http://www.aduanet.gob.pe/aduanas/informae/presentacion_bases_web.htm"
BASE = "http://www.aduanet.gob.pe/aduanas/informae/"
DEST = "raw_data/sunat"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PATRON = re.compile(r"^(ma|x)\d{8}\.zip$", re.I)


def log(m):
    print(m, flush=True)


def listar_archivos():
    """Lee el índice y devuelve los nombres de archivo publicados hoy."""
    r = requests.get(INDICE, headers=HEADERS, timeout=120)
    r.encoding = "latin-1"
    sopa = BeautifulSoup(r.text, "html.parser")
    nombres = set()
    for a in sopa.find_all("a", href=True):
        base = os.path.basename(a["href"].replace("\\", "/"))
        if PATRON.match(base):
            nombres.add(base)
    return sorted(nombres)


def zip_valido(path, esperado=None):
    if not os.path.exists(path):
        return False
    if esperado and os.path.getsize(path) != esperado:
        return False
    try:
        zipfile.ZipFile(path).namelist()
        return True
    except Exception:
        return False


def descargar(nombre, intentos=6):
    dest = os.path.join(DEST, nombre)
    url = BASE + nombre
    try:
        esperado = int(requests.head(url, headers=HEADERS, timeout=60)
                       .headers.get("content-length", 0))
    except Exception:
        esperado = 0

    if zip_valido(dest, esperado or None):
        log(f"  ya estaba  {nombre:18s} {os.path.getsize(dest):>12,} B")
        return True

    for n in range(1, intentos + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True,
                              timeout=(60, 300)) as r:
                with open(dest, "wb") as fh:
                    for bloque in r.iter_content(1 << 20):
                        fh.write(bloque)
        except Exception as ex:
            log(f"  reintento {n} {nombre}: {type(ex).__name__}")
            time.sleep(5 * n)
            continue
        if zip_valido(dest, esperado or None):
            log(f"  descargado {nombre:18s} {os.path.getsize(dest):>12,} B")
            return True
        log(f"  reintento {n} {nombre}: incompleto")
        time.sleep(5 * n)
    log(f"  FALLO      {nombre}")
    return False


def main():
    os.makedirs(DEST, exist_ok=True)
    log("consultando el indice de SUNAT...")
    archivos = listar_archivos()
    if not archivos:
        log("el indice no devolvio archivos; revisar si cambio la pagina")
        return 1
    imp = [a for a in archivos if a.lower().startswith("ma")]
    exp = [a for a in archivos if a.lower().startswith("x")]
    log(f"publicados: {len(imp)} semanas de importacion, "
        f"{len(exp)} de exportacion\n")

    fallidos = [a for a in archivos if not descargar(a)]
    ok = len(archivos) - len(fallidos)
    log(f"\ncompletos {ok}/{len(archivos)}"
        + (f"  ·  faltan: {fallidos}" if fallidos else ""))
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
