# -*- coding: utf-8 -*-
"""Abre el dashboard en un navegador real y comprueba que no esté roto.

Un `200` del servidor no dice nada sobre si la página se ve: un error de
JavaScript la deja en blanco y el servidor ni se entera. Esto recorre las nueve
vistas, recorre las 24 fichas departamentales, ejerce los filtros del mapa,
prueba los tres estados del tema y falla ante cualquier error de consola.

Así se detectó que `Infinity` en el JSON del mapa —que Python escribe sin
protestar y `JSON.parse` rechaza— dejaba el atlas sin dibujar.

Uso:
    python servir.py
    python verificar.py
"""
import io
import sys

from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
BASE = "http://127.0.0.1:8899"

# El selector apunta a una celda con datos y no a una fila cualquiera: la fila
# de "Cargando…" también es un <tr> y daría por buena una vista vacía.
VISTAS = [
    ("#resumen", "#tRegiones tbody tr", "Resumen"),
    ("#departamentos", "#depFicha .pares dd", "Departamentos"),
    ("#territorios", "#tTerritorios tbody tr", "Territorios"),
    ("#empresas", "#tEmpresas tbody tr td.name", "Empresas"),
    ("#comercio", "#tExportadores tbody tr", "Comercio"),
    ("#estacionalidad", ".cal tbody tr", "Estacionalidad"),
    ("#logistica", "#tLogistica tbody tr", "Logística"),
    ("#expansion", "#tHubs tbody tr", "Expansión"),
    ("#metodo", "#tFuentes tbody tr", "Método"),
]

errores = []
ok = True

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.on("response", lambda r: errores.append(f"HTTP {r.status} {r.url}")
          if r.status >= 400 else None)

    pg.goto(BASE + "/", wait_until="networkidle")

    print("vistas")
    for hash_, sel, nombre in VISTAS:
        pg.evaluate("h => location.hash = h", hash_)
        try:
            pg.wait_for_selector(sel, timeout=25000)
            pg.wait_for_function("s => document.querySelectorAll(s).length > 1",
                                 arg=sel, timeout=25000)
            n = pg.eval_on_selector_all(sel, "e => e.length")
            print(f"  {nombre:16s} {n:>5} filas")
        except Exception:
            print(f"  {nombre:16s} SIN CONTENIDO")
            ok = False

    # La ficha departamental es la vista con más uniones entre tablas, y es
    # donde una clave que no casa pasa inadvertida: la página se dibuja igual,
    # solo que sin calendario. Por eso se recorren las 24, no una de muestra.
    print("\ndepartamentos")
    pg.evaluate("() => location.hash = '#departamentos'")
    pg.wait_for_selector("#depFicha .pares dd")
    vals = pg.eval_on_selector_all("#fDepto option", "e => e.map(o => o.value)")
    print(f"  {len(vals)} departamentos en el selector")
    if len(vals) != 24:
        print("  FALTAN DEPARTAMENTOS")
        ok = False
    incompletas = []
    for v in vals:
        pg.select_option("#fDepto", value=v)
        pg.wait_for_timeout(80)
        meses = pg.eval_on_selector_all("#depFicha .mc i", "e => e.length")
        sam = (pg.text_content("#depFicha .ficha .v") or "").strip()
        if meses != 12 or not sam.startswith("US$"):
            incompletas.append(f"{v}(meses={meses}, sam={sam!r})")
    if incompletas:
        print("  FICHAS INCOMPLETAS: " + ", ".join(incompletas[:6]))
        ok = False
    else:
        print("  las 24 fichas traen calendario y mercado")

    print("\nbusqueda")
    pg.evaluate("() => location.hash = '#empresas'")
    pg.wait_for_selector("#tEmpresas tbody tr td.name")
    pg.fill("#q", "camposol")
    pg.wait_for_timeout(700)
    fila = pg.text_content("#tEmpresas tbody tr:first-child") or ""
    print(f"  'camposol' -> {pg.text_content('#cCount').strip()}")
    if "camposol" not in fila.lower():
        print("  LA BUSQUEDA NO FILTRA")
        ok = False
    pg.fill("#q", "")
    pg.wait_for_timeout(400)

    # El tema se prueba contra el sistema opuesto: es donde se rompen los
    # colores que se declararon solo dentro de prefers-color-scheme.
    print("\ntema")
    for elegido, espera in (("dark", "dark"), ("light", "light"), ("auto", None)):
        pg.click(f'.tema button[data-tema="{elegido}"]')
        pg.wait_for_timeout(350)
        real = pg.evaluate("() => document.documentElement.dataset.theme || null")
        bg = pg.evaluate("() => getComputedStyle(document.body).backgroundColor")
        marcado = pg.evaluate(
            "() => [...document.querySelectorAll('.tema button')]"
            ".filter(b => b.getAttribute('aria-pressed') === 'true')"
            ".map(b => b.dataset.tema).join(',')")
        bien = real == espera and marcado == elegido
        print(f"  {elegido:5s} -> data-theme={str(real):5s} body={bg:22s} "
              f"{'ok' if bien else 'FALLA'}")
        if not bien:
            ok = False

    # Contraste real de una etiqueta en oscuro forzado: si su color solo
    # existiera bajo prefers-color-scheme, aquí saldría texto claro sobre
    # fondo claro.
    pg.click('.tema button[data-tema="dark"]')
    pg.wait_for_timeout(350)
    par = pg.evaluate(
        "() => {const t = document.querySelector('.tag'); if(!t) return null;"
        "const s = getComputedStyle(t); return [s.backgroundColor, s.color];}")
    if par:
        def lum(c):
            v = [int(x) / 255 for x in c[c.find("(") + 1:c.find(")")].split(",")[:3]]
            v = [(x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4) for x in v]
            return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]
        a, z = lum(par[0]), lum(par[1])
        ratio = (max(a, z) + .05) / (min(a, z) + .05)
        print(f"  contraste de etiqueta en oscuro: {ratio:.1f}:1 "
              f"{'ok' if ratio >= 3 else 'INSUFICIENTE'}")
        if ratio < 3:
            ok = False

    print("\nmapa")
    pg.goto(BASE + "/mapa", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    n = pg.evaluate("() => document.querySelectorAll('.item').length")
    print(f"  {n} elementos en la lista lateral")
    if n == 0:
        ok = False
    # Los filtros son la razón de ser del mapa: se prueban de verdad, no solo
    # comprobando que el control exista en el DOM.
    base = pg.text_content("#cuenta").strip()
    pg.select_option("#fDep", label="Lambayeque")
    pg.wait_for_timeout(900)
    filtrado = pg.text_content("#cuenta").strip()
    print(f"  sin filtro : {base}")
    print(f"  Lambayeque : {filtrado}")
    if not filtrado or filtrado == base:
        print("  EL FILTRO DE DEPARTAMENTO NO REDUCE")
        ok = False

    pg.click('#fReg button[data-reg="0"]')
    pg.wait_for_timeout(600)
    if pg.text_content("#cuenta").strip() == filtrado:
        print("  EL FILTRO DE REGION NATURAL NO ACTUA")
        ok = False

    pg.click("#reset")
    pg.wait_for_timeout(600)
    if pg.text_content("#cuenta").strip() != base:
        print("  LIMPIAR NO RESTAURA EL ESTADO INICIAL")
        ok = False
    else:
        print("  region natural y limpiar: ok")

    pg.fill("#q", "chiclayo")
    pg.wait_for_timeout(800)
    busq = pg.text_content("#cuenta").strip()
    if busq == base:
        print("  LA BUSQUEDA DEL MAPA NO FILTRA")
        ok = False
    else:
        print(f"  buscar     : {busq}")
    pg.click("#reset")
    pg.wait_for_timeout(500)

    for nivel in ("0", "2", "3", "1"):
        pg.click(f'#fVial button[data-vial="{nivel}"]')
        pg.wait_for_timeout(300)
    print("  niveles de red vial: ok")

    pg.click('.tema button[data-tema="dark"]')
    pg.wait_for_timeout(400)
    if pg.evaluate("() => document.documentElement.dataset.theme") != "dark":
        print("  el tema no se aplica en el mapa")
        ok = False
    else:
        print("  tema oscuro aplicado")

    # El mapa es un documento aparte, asi que su pertenencia al sitio depende
    # de que la navegacion funcione en ambos sentidos: aqui se comprueba, no
    # se supone.
    nav = pg.eval_on_selector_all("nav a", "e => e.map(a => a.textContent.trim())")
    activo = pg.eval_on_selector_all("nav a.on", "e => e.map(a => a.textContent.trim())")
    print(f"  nav: {len(nav)} enlaces, activo {activo}")
    if len(nav) != 10 or activo != ["Mapa"]:
        print("  LA NAVEGACION DEL MAPA NO COINCIDE CON LA DEL SITIO")
        ok = False
    pg.click('nav a[href="/#empresas"]')
    pg.wait_for_selector("#tEmpresas tbody tr td.name", timeout=25000)
    print("  mapa -> empresas: ok")
    pg.click('nav a[href="/mapa"]')
    pg.wait_for_timeout(2500)
    if pg.evaluate("() => document.querySelectorAll('.item').length") == 0:
        print("  EL REGRESO AL MAPA NO DIBUJA")
        ok = False
    else:
        print("  empresas -> mapa: ok")

    b.close()

# El favicon lo pide el navegador solo; su ausencia no es un fallo del sitio.
errores = [e for e in errores if "favicon" not in e.lower()]
if errores:
    print("\nERRORES:")
    for e in errores[:10]:
        print("  ", e[:170])
    ok = False

print("\n" + ("TODO OK" if ok else "HAY FALLAS"))
sys.exit(0 if ok else 1)
