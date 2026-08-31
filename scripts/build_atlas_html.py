# -*- coding: utf-8 -*-
"""Compone el atlas: plantilla + payload -> un solo HTML autónomo.

El mapa se sirve en dos sitios (el archivo suelto de `out/` y la ruta /mapa del
dashboard) y ambos deben salir del mismo par plantilla+datos. Cuando esto se
armaba a mano, editar la plantilla dejaba una de las dos copias atrás.

El JSON va dentro de un <script type="application/json"> y no como literal de
JavaScript: así el navegador no lo analiza como código y `</script>` dentro de
un nombre no puede cerrar el bloque antes de tiempo.

Uso:
    python scripts/build_atlas_html.py
"""
import io
import json
import os
import shutil

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLA = os.path.join(RAIZ, "scripts", "mapa_geo_template.html")
DATOS = os.path.join(RAIZ, "out", "mapa_geo.json")
SALIDA = os.path.join(RAIZ, "out", "atlas_geo.html")
DASHBOARD = os.path.abspath(
    os.path.join(RAIZ, "..", "..", "dashboard", "mapa.html"))

# El mismo icono que index.html: una pestaña con otro emoji leería como
# otro sitio.
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,"
           "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>🌾</text></svg>\">")

plantilla = io.open(PLANTILLA, encoding="utf-8").read()
crudo = io.open(DATOS, encoding="utf-8").read()
json.loads(crudo)                      # falla aquí, no en el navegador

if "__DATA__" not in plantilla:
    raise SystemExit("la plantilla no tiene el marcador __DATA__")

# El escape de "</" es lo único que un bloque application/json necesita para
# no poder cerrar su propia etiqueta.
html = plantilla.replace("__DATA__", crudo.replace("</", r"<\/"))
html = html.replace("<title>", FAVICON + "\n<title>", 1)

with io.open(SALIDA, "w", encoding="utf-8") as fh:
    fh.write(html)
shutil.copyfile(SALIDA, DASHBOARD)

kb = os.path.getsize(SALIDA) / 1024
print(f"atlas_geo.html   : {kb:,.0f} KB")
print(f"dashboard/mapa.html : copiado")
