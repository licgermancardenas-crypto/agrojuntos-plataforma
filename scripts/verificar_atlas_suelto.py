# -*- coding: utf-8 -*-
"""El atlas de docs/ se abre desde el disco. Ahi un fetch no tiene a quien
preguntar, asi que las capas van embebidas: esto lo comprueba."""
import io, pathlib, sys
from playwright.sync_api import sync_playwright
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
F = pathlib.Path(r"E:\LENOVO ideapad Flex5\AGRO EXPORTACIONES\AGRO JUNTOS\MAPEO\out\atlas_geo.html")
err, red = [], []
ok = True
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.on("console", lambda m: err.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: err.append(str(e)))
    pg.on("request", lambda r: red.append(r.url))
    pg.goto(F.as_uri())
    pg.wait_for_timeout(3200)
    for v, u in (("pts", "sectores"), ("prov", "provincias"),
                 ("calor", "sectores"), ("hex", "celdas")):
        pg.click(f'#vistaCtl button[data-vista="{v}"]')
        pg.wait_for_timeout(1200)
        t = pg.text_content("#cuenta").strip()
        print(f"  {v:5s} {t}")
        if u not in t:
            print(f"  {v} NO FUNCIONA DESDE EL DISCO")
            ok = False
    b.close()
if any("mapa_capas" in u for u in red):
    print("  EL ATLAS SUELTO INTENTA PEDIR LAS CAPAS POR RED")
    ok = False
else:
    print("  no pide nada por red: autocontenido")
print("errores:", err[:4] if err else "ninguno")
if err:
    ok = False
print("SUELTO OK" if ok else "SUELTO FALLA")
sys.exit(0 if ok else 1)
