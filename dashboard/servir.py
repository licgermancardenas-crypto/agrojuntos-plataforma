# -*- coding: utf-8 -*-
"""Sirve el dashboard como lo hace Vercel, para poder verificarlo de verdad.

`http.server` a secas no resuelve `/mapa` -> `mapa.html`, que es la regla
`cleanUrls` de vercel.json. Sin ella la comprobación local pasa por rutas que
no son las que usa el sitio publicado, justo donde viven los enlaces de la
navegación.

Uso:
    python servir.py [puerto]
"""
import functools
import http.server
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))


class Limpio(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        real = super().translate_path(path)
        if not os.path.exists(real) and not real.endswith((os.sep, "/")):
            html = real + ".html"
            if os.path.isfile(html):
                return html
        return real

    def log_message(self, *a):
        pass


puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
h = functools.partial(Limpio, directory=RAIZ)
print(f"http://127.0.0.1:{puerto}")
http.server.ThreadingHTTPServer(("127.0.0.1", puerto), h).serve_forever()
