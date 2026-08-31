# -*- coding: utf-8 -*-
"""Download SUNAT's weekly customs archives, verifying each one.

aduanet drops connections partway through the larger import files, which
leaves a truncated file that still looks plausible on disk. Every download is
checked against the declared Content-Length and then opened as a ZIP before
being accepted; anything that fails is retried.
"""
import os
import sys
import time
import zipfile

import requests

BASE = "http://www.aduanet.gob.pe/aduanas/informae/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEST = "data/aduanas"


def valido(path, esperado=None):
    if not os.path.exists(path):
        return False
    if esperado and os.path.getsize(path) != esperado:
        return False
    try:
        zipfile.ZipFile(path).namelist()
        return True
    except Exception:
        return False


def bajar(archivo, intentos=6):
    dest = os.path.join(DEST, archivo)
    url = BASE + archivo
    try:
        esperado = int(requests.head(url, headers=HEADERS, timeout=60)
                       .headers.get("content-length", 0))
    except Exception:
        esperado = 0

    if valido(dest, esperado or None):
        print(f"  ok   {archivo:18s} {os.path.getsize(dest):>11,}", flush=True)
        return True

    for n in range(1, intentos + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True,
                              timeout=(60, 300)) as r:
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
        except Exception as ex:
            print(f"  ...  {archivo} intento {n}: {type(ex).__name__}", flush=True)
            time.sleep(5 * n)
            continue
        if valido(dest, esperado or None):
            print(f"  bajo {archivo:18s} {os.path.getsize(dest):>11,}", flush=True)
            return True
        print(f"  ...  {archivo} intento {n}: incompleto "
              f"({os.path.getsize(dest):,}/{esperado:,})", flush=True)
        time.sleep(5 * n)

    print(f"  FALLO {archivo}", flush=True)
    return False


if __name__ == "__main__":
    os.makedirs(DEST, exist_ok=True)
    archivos = open(os.path.join(DEST, "archivos.txt")).read().split()
    malos = [a for a in archivos if not bajar(a)]
    print(f"\ncompletos: {len(archivos) - len(malos)}/{len(archivos)}")
    if malos:
        print("faltan:", malos)
    sys.exit(1 if malos else 0)
