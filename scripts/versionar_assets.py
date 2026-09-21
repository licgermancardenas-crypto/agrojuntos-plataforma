# -*- coding: utf-8 -*-
"""Pone la huella del contenido en la dirección de cada asset.

El navegador no tiene forma de saber que `app.js` cambió: el nombre es el
mismo. Por eso hasta ahora se cacheaba diez minutos —lo justo para no volver a
pedirlo en la misma sesión y lo bastante poco para que un despliegue se notara
pronto—, que es un compromiso entre dos cosas que se quieren enteras.

Con la huella en la dirección el compromiso desaparece. `app.js?v=3f2a91` es una
dirección distinta de `app.js?v=7c10de`, así que el archivo puede cachearse un
año: cuando cambia, cambia la huella, cambia la dirección y el navegador lo pide
solo. Y el HTML, que es lo único que sigue revalidándose, es quien dice cuál es
la huella vigente.

Se corre antes de publicar, después de tocar cualquier asset:

    python scripts/versionar_assets.py

`verificar_datos.py` comprueba en cada push que las huellas escritas en el HTML
correspondan a los archivos. Olvidarse de correr esto no despliega un año de
caché equivocada: rompe la verificación.
"""
import hashlib
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent / "dashboard"

# Los assets que el HTML referencia por su nombre. Los datos no entran aquí:
# cambian por su cuenta, con otro ritmo, y ya tienen su propia política.
ASSETS = ["app.js", "styles.css", "buscador.js", "buscador.css"]
PAGINAS = ["index.html", "mapa.html"]


def huella(ruta: Path) -> str:
    """Seis caracteres bastan: distinguen versiones, no resisten ataques."""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:8]


def referencias(texto: str, asset: str):
    """Cada sitio donde el HTML nombra ese asset, con o sin huella puesta."""
    patron = re.compile(r'(["\'])(/' + re.escape(asset) + r')(\?v=[0-9a-f]+)?\1')
    return patron


def poner(escribir: bool = True) -> int:
    huellas = {}
    for a in ASSETS:
        ruta = RAIZ / a
        if not ruta.exists():
            print("  falta %s" % a)
            continue
        huellas[a] = huella(ruta)

    desfasados = 0
    for pagina in PAGINAS:
        ruta = RAIZ / pagina
        if not ruta.exists():
            continue
        txt = original = ruta.read_text(encoding="utf-8")
        for a, h in huellas.items():
            nuevo = r'\1\2?v=' + h + r'\1'
            txt, n = referencias(txt, a).subn(nuevo, txt)
            if n:
                print("  %-12s %-14s %s  (%d referencia%s)"
                      % (pagina, a, h, n, "" if n == 1 else "s"))
        if txt != original:
            desfasados += 1
            if escribir:
                ruta.write_text(txt, encoding="utf-8")
    return desfasados


def main() -> int:
    print("huella de contenido en los assets")
    cambiadas = poner(escribir=True)
    print("\n%s" % ("%d página(s) actualizada(s)" % cambiadas if cambiadas
                    else "ya estaban al día"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
