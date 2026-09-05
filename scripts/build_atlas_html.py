# -*- coding: utf-8 -*-
"""Compone el atlas: plantilla + payload -> HTML.

El mapa se sirve en dos sitios y ambos deben salir del mismo par
plantilla+datos. Cuando esto se armaba a mano, editar la plantilla dejaba una
de las dos copias atrás.

El JSON va dentro de un <script type="application/json"> y no como literal de
JavaScript: así el navegador no lo analiza como código y `</script>` dentro de
un nombre no puede cerrar el bloque antes de tiempo.

Salen dos variantes de la misma plantilla. La del sitio deja fuera los puntos
y las provincias —el 28% del peso— y las pide solo si el usuario elige esa
representación. La de docs/ las lleva dentro, porque se abre desde el disco y
allí un fetch no tiene a quién preguntar.

Uso:
    python scripts/build_atlas_html.py
"""
import base64
import io
import json
import os
import shutil

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLA = os.path.join(RAIZ, "scripts", "mapa_geo_template.html")
DATOS = os.path.join(RAIZ, "out", "mapa_geo.json")
CAPAS = os.path.join(RAIZ, "out", "mapa_capas.json")
SALIDA = os.path.join(RAIZ, "out", "atlas_geo.html")
DASHBOARD = os.path.abspath(
    os.path.join(RAIZ, "..", "..", "dashboard", "mapa.html"))
DATA_WEB = os.path.join(os.path.dirname(DASHBOARD), "data")

# El mismo icono que index.html: una pestaña con otro emoji leería como otro
# sitio.
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,"
           "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>\U0001F33E</text></svg>\">")

plantilla = io.open(PLANTILLA, encoding="utf-8").read()
base = json.loads(io.open(DATOS, encoding="utf-8").read())
capas = json.loads(io.open(CAPAS, encoding="utf-8").read())

if "__DATA__" not in plantilla:
    raise SystemExit("la plantilla no tiene el marcador __DATA__")


def escribir(destino, payload):
    crudo = json.dumps(payload, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False)
    # Escapar "</" es lo único que hace falta para que el bloque no pueda
    # cerrar su propia etiqueta antes de tiempo.
    html = plantilla.replace("__DATA__", crudo.replace("</", "<\\/"))
    html = html.replace("<title>", FAVICON + "\n<title>", 1)
    with io.open(destino, "w", encoding="utf-8") as fh:
        fh.write(html)
    return os.path.getsize(destino) / 1024


# El relieve: el sitio lo pide por URL y el atlas suelto lo lleva incrustado,
# porque se abre desde el disco y ahi no hay a quien pedirle nada.
RELIEVE = os.path.join(DATA_WEB, "relieve.jpg")
RELIEVE_META = os.path.join(DATA_WEB, "relieve.json")
relieve = None
if os.path.exists(RELIEVE) and os.path.exists(RELIEVE_META):
    relieve = json.loads(io.open(RELIEVE_META, encoding="utf-8").read())

# El sitio pide las capas pesadas solo si el usuario elige esa representación.
web = dict(base)
web["capas_url"] = "/data/mapa_capas.json"
if relieve:
    web["relieve"] = dict(relieve, url="/data/relieve.jpg")
kb_web = escribir(DASHBOARD, web)
shutil.copyfile(CAPAS, os.path.join(DATA_WEB, "mapa_capas.json"))

# El atlas suelto de docs/ se abre desde el disco, donde no hay a quién pedirle
# nada: ahí las capas van dentro o esas tres representaciones no existirían.
solo = dict(base)
solo.update(capas)
if relieve:
    b64 = base64.b64encode(io.open(RELIEVE, "rb").read()).decode()
    solo["relieve"] = dict(relieve, url="data:image/jpeg;base64," + b64)
kb_solo = escribir(SALIDA, solo)

print(f"dashboard/mapa.html : {kb_web:,.0f} KB + "
      f"{os.path.getsize(CAPAS)/1024:,.0f} KB diferidos")
print(f"docs/atlas_geo.html : {kb_solo:,.0f} KB (autocontenido)")
