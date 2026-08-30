# -*- coding: utf-8 -*-
"""Resumable downloader for large public files.

SUNAT's servers drop the connection partway through the 391 MB padrón, and a
naive retry either restarts from zero or — worse — appends to the previous
partial and produces a corrupt archive. This resumes by byte range against the
declared Content-Length and refuses to report success unless the final size
matches exactly.
"""
import os
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}


def size_remoto(url):
    r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=90)
    return int(r.headers.get("content-length", 0))


def descargar(url, dest, intentos=40):
    total = size_remoto(url)
    if not total:
        raise RuntimeError("el servidor no declara Content-Length")
    print(f"objetivo: {total:,} bytes -> {dest}", flush=True)

    for n in range(1, intentos + 1):
        hecho = os.path.getsize(dest) if os.path.exists(dest) else 0
        if hecho >= total:
            break
        h = dict(HEADERS)
        if hecho:
            h["Range"] = f"bytes={hecho}-"
        try:
            with requests.get(url, headers=h, stream=True, timeout=(60, 300)) as r:
                # A server that ignores Range restarts the body: start over
                # rather than append, which is what corrupts the archive.
                modo = "ab" if (hecho and r.status_code == 206) else "wb"
                if modo == "wb":
                    hecho = 0
                with open(dest, modo) as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                        hecho += len(chunk)
        except Exception as ex:
            print(f"  intento {n}: corte en {hecho:,} ({type(ex).__name__})",
                  flush=True)
            time.sleep(min(5 * n, 45))
            continue
        pct = 100 * hecho / total
        print(f"  intento {n}: {hecho:,} bytes ({pct:.1f}%)", flush=True)
        if hecho >= total:
            break
        time.sleep(3)

    final = os.path.getsize(dest) if os.path.exists(dest) else 0
    ok = final == total
    print(f"{'COMPLETO' if ok else 'INCOMPLETO'}: {final:,} / {total:,}",
          flush=True)
    return ok


if __name__ == "__main__":
    sys.exit(0 if descargar(sys.argv[1], sys.argv[2]) else 1)
