# -*- coding: utf-8 -*-
"""Abre el dashboard en un navegador real y comprueba que no esté roto.

Un `200` del servidor no dice nada sobre si la página se ve: un error de
JavaScript la deja en blanco y el servidor ni se entera. Esto recorre las diez
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
    ("#productos", "#tProductos tbody tr", "Productos"),
    ("#comercio", "#tExportadores tbody tr", "Comercio"),
    ("#importacion", "#tImpCat tbody tr", "Importación"),
    ("#estacionalidad", ".cal tbody tr", "Estacionalidad"),
    ("#logistica", "#tLogistica tbody tr", "Logística"),
    ("#expansion", "#tHubs tbody tr", "Expansión"),
    ("#metodo", "#tFuentes tbody tr", "Método"),
]

def usd_a_num(t):
    """«US$ 3.19 mil MM» -> 3.19e9. La pagina abrevia y el chequeo tiene que
    leer lo mismo que el lector, no una cifra cruda que nadie ve."""
    t = t.replace("US$", "").replace(",", "").strip()
    mult = 1.0
    for suf, m in (("mil MM", 1e9), ("MM", 1e6), ("mil", 1e3)):
        if t.endswith(suf):
            mult = m
            t = t[: -len(suf)].strip()
            break
    try:
        return float(t) * mult
    except ValueError:
        return 0.0


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

    # La navegacion del sitio se guarda para contrastarla despues contra la
    # del mapa. Antes esto era el numero 11 escrito a mano, que quedaba viejo
    # cada vez que se agregaba una vista y hacia fallar una prueba correcta.
    NAV_SITIO = pg.eval_on_selector_all(
        "nav a", "e => e.map(a => a.textContent.trim())")

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

    # El filtro por territorio es el puente entre el mapa y la cartera: si no
    # reduce, la vista muestra un desplegable que no hace nada.
    print("\ncartera por territorio")
    total = pg.text_content("#cCount").strip()
    opciones = pg.eval_on_selector_all(
        "#fTer option", "o => o.map(x => x.value).filter(Boolean)")
    print(f"  {len(opciones)} territorios en el desplegable")
    if len(opciones) < 40:
        print("  EL DESPLEGABLE DE TERRITORIOS LLEGA VACIO O CORTO")
        ok = False
    else:
        elegido = opciones[0]
        pg.select_option("#fTer", elegido)
        pg.wait_for_timeout(500)
        filtrado = pg.text_content("#cCount").strip()
        cel = pg.eval_on_selector_all(
            "#tEmpresas tbody tr td",
            "t => t.map(x => x.textContent.trim())")
        print(f"  {elegido[:34]:<34} -> {filtrado}")
        if filtrado == total:
            print("  EL FILTRO DE TERRITORIO NO REDUCE")
            ok = False
        if elegido not in cel:
            print(f"  NINGUNA FILA DECLARA EL TERRITORIO {elegido}")
            ok = False
        pg.select_option("#fTer", "")
        pg.wait_for_timeout(400)
        if pg.text_content("#cCount").strip() != total:
            print("  LIMPIAR EL TERRITORIO NO RESTAURA EL CONTEO")
            ok = False
        else:
            print("  limpiar y restaurar: ok")

    # El eje de la serie tiene que seguir al filtro: antes se reusaba el mismo
    # arreglo de semanas para los tres modos, de modo que «Mensual» cambiaba
    # los montos pero seguia rotulando 15/06 y 22/06.
    print("\neje temporal de la serie")
    pg.evaluate("() => location.hash = '#empresa=20524269440'")
    pg.wait_for_selector("#empSerie .sb", timeout=30000)
    # Las semanas medidas salen del propio indice y no de un numero escrito
    # aqui: el archivo historico crece cada vez que corre acumular_aduanas.py,
    # y una constante en la prueba haria fallar una pagina correcta.
    n_sem = pg.evaluate(
        "async () => (await (await fetch('/data/perfil_idx.json')).json()).semanas")
    ESPERA = {
        "medido":  (n_sem, "semana", None),
        "mensual": (12, "mes",    "Ene"),
        "anual":   (6,  "año", "2021"),
    }
    for modo, (n, palabra, primera) in ESPERA.items():
        pg.click(f'#fPeriodo button[data-p="{modo}"]')
        pg.wait_for_timeout(1000)
        etq = pg.eval_on_selector_all("#empSerie .sb b", "e => e.map(x => x.textContent)")
        tit = (pg.text_content("#empSerieTit") or "").lower()
        con = pg.eval_on_selector_all(
            "#empSerie .sb", "e => e.filter(x => !x.classList.contains('vacio')).length")
        print(f"  {modo:<8} {len(etq):>2} barras ({con} con dato) · «{tit}» · eje {etq[0]}..{etq[-1]}")
        if len(etq) != n:
            print(f"  EL EJE {modo} TIENE {len(etq)} BARRAS Y DEBERIA TENER {n}")
            ok = False
        if primera and etq[0] != primera:
            print(f"  EL EJE {modo} EMPIEZA EN {etq[0]} Y DEBERIA EN {primera}")
            ok = False
        if palabra not in tit:
            print(f"  EL ROTULO {modo} NO DICE «{palabra}»: {tit}")
            ok = False
        # ninguna etiqueta de semana puede sobrevivir fuera de «medido»
        if modo != "medido" and any("/" in e for e in etq):
            print(f"  QUEDAN FECHAS SEMANALES EN EL EJE {modo}: {etq}")
            ok = False
        if con < 1:
            print(f"  EL EJE {modo} NO TIENE NINGUNA BARRA CON DATO")
            ok = False

    # La suma agrupada no puede inventar ni perder dinero.
    pg.click('#fPeriodo button[data-p="medido"]')
    pg.wait_for_timeout(800)
    tot_sem = pg.eval_on_selector_all(
        "#empSerie .sb", "e => e.map(x => x.getAttribute('title'))")
    pg.click('#fPeriodo button[data-p="mensual"]')
    pg.wait_for_timeout(800)
    con_mes = pg.eval_on_selector_all(
        "#empSerie .sb:not(.vacio)", "e => e.length")
    print(f"  {len(tot_sem)} semanas se agrupan en {con_mes} meses con dato")
    if con_mes >= len(tot_sem):
        print("  LA AGRUPACION MENSUAL NO AGRUPA NADA")
        ok = False
    pg.click('#fPeriodo button[data-p="anual"]')
    pg.wait_for_timeout(600)

    # Las cifras de comercio exterior viajan medidas y el sitio las lleva al
    # periodo elegido. Se comprueba la aritmetica, no solo que el boton pinte:
    # anual tiene que ser doce veces el mensual, y medido la base de ambos.
    print("\nperiodo de las cifras")
    pg.evaluate("() => location.hash = '#importacion'")
    pg.wait_for_selector("#tImpCat tbody tr")
    val = {}
    for modo in ("medido", "mensual", "anual"):
        pg.click(f'#fPeriodo button[data-p="{modo}"]')
        pg.wait_for_timeout(450)
        txt = pg.eval_on_selector_all("#impKpis .v", "e => e[0].textContent")
        cab = pg.eval_on_selector_all("#tImpCat thead th",
                                      "e => e[1].textContent")
        # Se lee la cifra que el usuario ve y no una funcion interna: lo que
        # hay que garantizar es que la pantalla diga la verdad.
        val[modo] = usd_a_num(txt)
        print(f"  {modo:<8} {txt:<18} columna «{cab}»")
        if modo != "medido" and modo not in cab.lower().replace("al mes", "mensual"):
            print(f"  LA COLUMNA NO DECLARA EL PERIODO {modo}")
            ok = False
    # El factor esperado sale de las semanas archivadas, no de un numero fijo:
    # el historico crece y 52/10 dejo de ser cierto en cuanto entro la semana
    # once. Una prueba con la constante vieja hace fallar una pagina correcta.
    sem_imp = pg.evaluate(
        "async () => (await (await fetch('/data/importacion.json')).json())"
        ".meta.semanas")
    esperado = 52.0 / sem_imp
    r_anual = val["anual"] / val["medido"] if val["medido"] else 0
    r_mes = val["anual"] / val["mensual"] if val["mensual"] else 0
    print(f"  anual/medido {r_anual:.2f} (esperado {esperado:.2f} = 52/{sem_imp}) · "
          f"anual/mensual {r_mes:.2f} (esperado 12.00)")
    if abs(r_anual - esperado) > .03 or abs(r_mes - 12) > .05:
        print("  LA ARITMETICA DEL PERIODO NO CUADRA")
        ok = False
    # El periodo es global: elegirlo en una vista tiene que valer en todas.
    pg.evaluate("() => location.hash = '#comercio'")
    pg.wait_for_selector("#tImportadores tbody tr")
    pg.wait_for_timeout(600)
    cab = pg.eval_on_selector_all("#tImportadores thead th",
                                  "e => e[2].textContent")
    if "anual" not in cab.lower():
        print(f"  EL PERIODO NO CRUZA DE UNA VISTA A OTRA: «{cab}»")
        ok = False
    else:
        print("  el periodo vale en todas las vistas: ok")

    # El atlas vive incrustado en los once modulos. Se comprueba que el hueco
    # exista en todos, que montar uno traiga el mapa de verdad —no un cuadro
    # vacio— y que el modulo mande sobre el: cambiar de region en la ficha
    # tiene que mover el mapa sin recargarlo.
    print("\nmapa incrustado")
    pg.evaluate("() => location.hash = '#resumen'")
    pg.wait_for_timeout(600)
    huecos = pg.eval_on_selector_all(".mapaslot", "e => e.map(x => x.id)")
    print(f"  {len(huecos)} modulos con hueco de mapa")
    if len(huecos) < 10:
        print("  FALTAN MODULOS SIN MAPA")
        ok = False

    pg.evaluate("() => location.hash = '#departamentos'")
    pg.wait_for_selector("#mapDep .mapabtn")
    pg.click("#mapDep .mapabtn")
    pg.wait_for_selector("#mapDep iframe")
    marco = pg.frame_locator("#mapDep iframe")
    marco.locator("#cuenta").wait_for(timeout=40000)
    for _ in range(40):
        uno = marco.locator("#cuenta").inner_text().strip()
        if "sector" in uno or "celda" in uno:
            break
        pg.wait_for_timeout(500)
    print(f"  montado: {uno}")

    chrome = pg.evaluate("""() => {
        const d = document.querySelector('#mapDep iframe').contentDocument;
        return ['nav', 'header.top', '.titulo'].map(
            s => { const el = d.querySelector(s);
                   return el ? getComputedStyle(el).display : 'ausente'; });
    }""")
    if any(c not in ("none", "ausente") for c in chrome):
        print(f"  EL MAPA INCRUSTADO MUESTRA EL CROMO DEL SITIO: {chrome}")
        ok = False
    else:
        print("  sin encabezado ni navegacion duplicados: ok")

    opciones = pg.eval_on_selector_all("#fDepto option", "o => o.map(x => x.value)")
    pg.select_option("#fDepto", opciones[3])
    pg.wait_for_timeout(2500)
    dos = marco.locator("#cuenta").inner_text().strip()
    print(f"  al cambiar de region: {dos}")
    if dos == uno:
        print("  EL MAPA NO SIGUE AL MODULO")
        ok = False

    # El mapa a pantalla completa no debe quedar en modo incrustado.
    entero = pg.eval_on_selector("#v-departamentos .mapacard .eyebrow a",
                                 "a => a.getAttribute('href')")
    if "e=1" in (entero or ""):
        print("  EL ENLACE A PANTALLA COMPLETA ABRE EN MODO INCRUSTADO")
        ok = False

    # El perfil es el unico modulo con una direccion por registro: 23,300
    # empresas comparten una sola vista y el RUC viaja en el hash. Se comprueba
    # el camino entero —directorio, clic, perfil— y no solo que la pagina abra.
    print("\nperfil de empresa")
    pg.evaluate("() => location.hash = '#empresas'")
    pg.wait_for_selector("#tEmpresas tbody tr td.name a")
    ruc = pg.eval_on_selector(
        "#tEmpresas tbody tr td.name a",
        "a => a.getAttribute('href').split('=')[1]")
    pg.click("#tEmpresas tbody tr td.name a")
    pg.wait_for_selector("#empPerfil h3", timeout=25000)
    pg.wait_for_timeout(900)
    titulo = (pg.text_content("#empPerfil h3") or "").strip()
    print(f"  el directorio lleva al perfil de {titulo[:34]}")
    if not titulo or "No hay perfil" in (pg.text_content("#empPerfil") or ""):
        print("  EL PERFIL NO CARGA DESDE EL DIRECTORIO")
        ok = False
    if pg.evaluate("location.hash") != "#empresa=" + ruc:
        print("  EL PERFIL NO DEJA SU PROPIA DIRECCION")
        ok = False
    kpis = len(pg.query_selector_all("#empPerfil .kpis > div"))
    mapa = pg.eval_on_selector("#empMapa", "c => c.width > 0 && c.height > 0")
    pares = len(pg.query_selector_all("#empPerfil .pares dt"))
    print(f"  {kpis} indicadores · {pares} campos de ficha · lienzo {mapa}")
    if kpis < 2 or not mapa:
        print("  EL PERFIL LLEGA INCOMPLETO")
        ok = False

    # Un RUC inexistente tiene que decirlo, no dejar la pagina cargando.
    pg.evaluate("() => location.hash = '#empresa=00000000000'")
    # Se espera al texto y no un rato fijo: los archivos de perfil crecen con
    # el historico y un temporizador que hoy alcanza manana no.
    try:
        pg.wait_for_function(
            "() => (document.getElementById('empPerfil').textContent || '')"
            ".indexOf('No hay perfil') >= 0", timeout=20000)
    except Exception:
        pass
    if "No hay perfil" not in (pg.text_content("#empPerfil") or ""):
        print("  UN RUC INEXISTENTE NO AVISA")
        ok = False
    else:
        print("  un RUC inexistente lo dice: ok")

    # La subcategoria «importador de insumos» tiene una capa propia: el panel
    # del directorio y el historico dentro de la ficha. Lo que se comprueba no
    # es que dibuje, sino la regla que la gobierna: **un ano sin semanas
    # descargadas no puede aparecer como US$ 0**. Un cero ahi seria una cifra
    # inventada, que es exactamente lo que este modulo no puede hacer.
    print("\nimportador de insumos")
    pg.evaluate("() => location.hash = '#empresas'")
    pg.wait_for_selector("#fClase .chip[data-c='6']")
    pg.click("#fClase .chip[data-c='6']")
    try:
        pg.wait_for_selector("#impResumen .v", timeout=20000)
    except Exception:
        print("  EL PANEL DE LA SUBCATEGORIA NO CARGA")
        ok = False
    kpis = pg.eval_on_selector_all(
        "#impResumen > div", "f => f.map(x => x.textContent)")
    barras_cat = len(pg.query_selector_all("#impMercadoCat .bar, "
                                           "#impMercadoCat > div"))
    cob = (pg.text_content("#impCobertura") or "")
    print(f"  panel: {len(kpis)} indicadores · {barras_cat} categorias")
    if len(kpis) < 4 or barras_cat < 3:
        print("  EL PANEL DE LA SUBCATEGORIA LLEGA INCOMPLETO")
        ok = False
    if "sin dato" not in cob:
        print("  LA COBERTURA NO DECLARA LOS ANOS SIN DESCARGAR")
        ok = False
    else:
        print("  declara los anos sin descargar como «sin dato»: ok")
    if "FOB importado" not in cob:
        print("  EL PANEL NO ACLARA QUE EL VALOR ES FOB IMPORTADO")
        ok = False

    # El panel pertenece a esta subcategoria y a ninguna otra: con cualquier
    # otro chip tiene que desaparecer, no quedarse mostrando cifras ajenas.
    otro = pg.eval_on_selector_all(
        "#fClase .chip",
        "f => { const o = f.find(x => x.dataset.c && x.dataset.c !== '6');"
        " return o ? o.dataset.c : ''; }")
    if otro:
        pg.click("#fClase .chip[data-c='" + otro + "']")
        pg.wait_for_timeout(200)
        if not pg.eval_on_selector("#impPanel", "e => e.hidden"):
            print("  EL PANEL SE QUEDA EN OTRAS SUBCATEGORIAS")
            ok = False
        else:
            print("  no se muestra en las demas subcategorias: ok")

    # El historico dentro de la ficha. Se entra por un RUC que tenga
    # operaciones medidas, tomado del propio archivo agregado.
    ruc_i = pg.evaluate(
        "async () => { const r = await (await fetch("
        "'/data/importaciones/importadores.json')).json();"
        " return Object.keys(r)[0]; }")
    anios = pg.evaluate(
        "async () => { const m = await (await fetch("
        "'/data/importaciones/mercado.json')).json();"
        " return [m.anios_pedidos, m.anios_con_dato]; }")
    faltan = [a for a in anios[0] if a not in anios[1]]
    pg.evaluate("() => location.hash = '#empresa=" + ruc_i + "'")
    try:
        pg.wait_for_selector("#impAnual .sb", timeout=25000)
    except Exception:
        print("  EL HISTORICO DE IMPORTACIONES NO CARGA EN LA FICHA")
        ok = False
    meses = len(pg.query_selector_all("#impMes .sb"))
    anuales = len(pg.query_selector_all("#impAnual .sb"))
    huecos = len(pg.query_selector_all("#impAnual .sb.vacio"))
    print(f"  ficha {ruc_i}: {meses} meses · {anuales} anos · "
          f"{huecos} sin semanas")
    if meses != 12:
        print("  EL GRAFICO MENSUAL NO TRAE LOS DOCE MESES")
        ok = False
    if anuales != len(anios[0]):
        print("  EL GRAFICO ANUAL NO TRAE LOS CINCO ANOS PEDIDOS")
        ok = False
    if huecos != len(faltan):
        print(f"  {len(faltan)} anos sin semanas y {huecos} huecos: "
              "ALGUN ANO SIN DATO SE ESTA PINTANDO COMO CERO")
        ok = False
    else:
        print(f"  los {len(faltan)} anos sin semanas quedan en hueco: ok")

    # Los anos que no se pueden mirar no se pueden elegir, y tienen que decir
    # por que.
    for a in faltan:
        chip = pg.query_selector("#impAnioSel .chip[data-a='" + a + "']")
        if not chip or chip.get_attribute("disabled") is None:
            print(f"  EL ANO {a} SIN SEMANAS SE PUEDE ELEGIR")
            ok = False
        elif "sin semanas" not in (chip.get_attribute("title") or ""):
            print(f"  EL ANO {a} NO EXPLICA POR QUE ESTA APAGADO")
            ok = False

    # Y lo mas importante de todo: el FOB importado no es facturacion. Si en
    # algun momento un texto lo llama «ventas», el modulo esta afirmando algo
    # que sus datos no dicen.
    txt = (pg.text_content("#empImportHist") or "")
    for prohibido in ("Ventas de la empresa", "Facturación", "Facturacion",
                      "Ingresos de la empresa"):
        if prohibido in txt:
            print(f"  EL HISTORICO LLAMA «{prohibido}» AL VALOR IMPORTADO")
            ok = False
    if "FOB" not in txt:
        print("  EL HISTORICO NO DICE QUE LA CIFRA ES FOB")
        ok = False
    else:
        print("  llama FOB importado a lo importado: ok")

    # El corte por ano manda sobre toda la ficha, no solo sobre el mensual: si
    # los productos y los paises no cambian al cambiar de ano, el filtro es
    # decorativo.
    def primer_barra():
        el = pg.query_selector("#impCat .n, #impCat > div")
        return (el.text_content() if el else "") or ""

    anios_emp = pg.evaluate(
        "async (r) => { const j = await (await fetch("
        "'/data/importaciones/importadores.json')).json();"
        " return Object.keys(j[r].cubo).sort(); }", ruc_i)
    if len(anios_emp) >= 2:
        pg.click("#impAnioSel .chip[data-a='" + anios_emp[0] + "']")
        pg.wait_for_timeout(250)
        a1 = pg.text_content("#impCorteNota") or ""
        pg.click("#impAnioSel .chip[data-a='" + anios_emp[-1] + "']")
        pg.wait_for_timeout(250)
        a2 = pg.text_content("#impCorteNota") or ""
        if anios_emp[0] not in a1 or anios_emp[-1] not in a2:
            print("  EL CORTE POR ANO NO SE DECLARA EN LA FICHA")
            ok = False
        else:
            print(f"  el corte por ano cambia el detalle: "
                  f"{anios_emp[0]} -> {anios_emp[-1]} ok")

    pg.click("#impAnioSel .chip[data-a='']")
    pg.wait_for_timeout(250)
    if not pg.eval_on_selector("#impMesBloque", "e => e.hidden"):
        print("  «TODOS» DEJA UN MENSUAL QUE NO CORRESPONDE A NINGUN ANO")
        ok = False
    elif "Todo lo medido" not in (pg.text_content("#impCorteNota") or ""):
        print("  «TODOS» NO DICE SOBRE QUE PERIODO AGREGA")
        ok = False
    else:
        print("  «todos» agrega y esconde el mensual: ok")

    # Un ano medido a medias no puede dibujarse como un ano entero.
    cob = pg.evaluate(
        "async () => { const m = await (await fetch("
        "'/data/importaciones/mercado.json')).json();"
        " return [m.anios_pedidos, m.cobertura_semanas]; }")
    incompletos = [a for a in cob[0]
                   if 0 < (cob[1].get(a) or 0) < 45]
    marcadas = len(pg.query_selector_all("#impAnual .sb.parcial"))
    if marcadas != len(incompletos):
        print(f"  {len(incompletos)} anos incompletos y {marcadas} barras "
              "marcadas: UN ANO A MEDIAS SE DIBUJA COMO UNO ENTERO")
        ok = False
    else:
        print(f"  los {len(incompletos)} anos incompletos van marcados: ok")

    # La vista de importacion vive de la fila desplegable: si el detalle no
    # cambia al pulsar otra categoria, la tabla es un adorno. Y las dos
    # categorias sin mercancia tienen que seguir visibles: son parte de la
    # respuesta, no filas vacias que convenga esconder.
    print("\nimportacion por categoria")
    pg.evaluate("() => location.hash = '#importacion'")
    pg.wait_for_selector("#tImpCat tbody tr td.l b")
    cats = pg.eval_on_selector_all("#tImpCat tbody tr td.l b",
                                   "f => f.map(x => x.textContent)")
    print(f"  {len(cats)} categorias en la tabla")
    for cero in ("Servicios agrícolas", "Venta de campos"):
        if cero not in cats:
            print(f"  FALTA LA CATEGORIA SIN MERCANCIA {cero}")
            ok = False
    def glosas():
        return pg.eval_on_selector_all("#impDet .bar .bn",
                                       "e => e.map(x => x.textContent)")
    uno = glosas()
    pg.click("#tImpCat tbody tr:nth-child(2)")
    pg.wait_for_timeout(400)
    dos = glosas()
    print(f"  detalle: {len(uno)} barras -> {len(dos)} al pulsar otra fila")
    if not uno or uno == dos:
        print("  LA FILA DESPLEGABLE NO CAMBIA EL DETALLE")
        ok = False
    fuera = len(pg.query_selector_all("#tImpFuera tbody tr"))
    print(f"  {fuera} partidas declaradas fuera de la medicion")
    if fuera < 5:
        print("  LA TABLA DE EXCLUSIONES LLEGA VACIA")
        ok = False

    # Territorio y centro son dos capas distintas y la tabla las une: si la
    # columna de centro llega vacia, la union se perdio en el JSON.
    pg.evaluate("() => location.hash = '#territorios'")
    pg.wait_for_selector("#tTerritorios tbody tr")
    centros = pg.eval_on_selector_all(
        "#tTerritorios tbody tr", "f => f.map(r => r.children[9].textContent.trim())")
    con = [c for c in centros if c and c != "\u2014"]
    print(f"  {len(con)} de {len(centros)} territorios declaran su centro")
    if len(con) < len(centros) * 0.7:
        print("  LA COLUMNA DE CENTRO LLEGA MAYORMENTE VACIA")
        ok = False

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
    pedidos = []
    pg.on("request", lambda r: pedidos.append(r.url))
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

    # La vista por defecto pasó a ser el sector real, cuya geometría vive en la
    # capa diferida: ahora sí se pide al abrir, y eso es deliberado. Lo que hay
    # que garantizar es lo que el usuario nota —que el mapa quede utilizable— y
    # que la capa se pida UNA vez y no en cada repintado.
    n_capas = sum(1 for u in pedidos if "mapa_capas.json" in u)
    if n_capas != 1:
        print(f"  LA CAPA DE SECTORES SE PIDIO {n_capas} VECES, DEBERIA SER UNA")
        ok = False
    else:
        print("  capa de sectores: una sola petición al abrir")
    if "sector" not in (pg.text_content("#cuenta") or ""):
        print("  EL MAPA NO ABRE EN LA VISTA DE SECTORES")
        ok = False

    # Cada representación dibuja geometría distinta y cuenta una unidad
    # distinta. Se comprueba que el contador cambie de unidad: si siguiera
    # diciendo "celdas" con los sectores en pantalla, la cifra no
    # correspondería a nada visible.
    for vista, unidad in (("area", "sectores"), ("pts", "sectores"),
                          ("prov", "provincias"),
                          ("calor", "sectores"), ("hex", "celdas")):
        pg.click(f'#vistaCtl button[data-vista="{vista}"]')
        pg.wait_for_timeout(1100)
        txt = pg.text_content("#cuenta").strip()
        kpi = pg.text_content(".kpis").strip()
        print(f"  {vista:5s} {txt}")
        if unidad not in txt or unidad not in kpi:
            print(f"  LA VISTA {vista} NO DECLARA SU UNIDAD ({unidad})")
            ok = False
    if not any("mapa_capas.json" in u for u in pedidos):
        print("  LAS CAPAS NUNCA SE DESCARGARON")
        ok = False
    else:
        print("  capas diferidas: descargadas al elegir una representación")
    print("  representaciones del mapa: ok")

    pg.click('.tema button[data-tema="dark"]')
    pg.wait_for_timeout(400)
    if pg.evaluate("() => document.documentElement.dataset.theme") != "dark":
        print("  el tema no se aplica en el mapa")
        ok = False
    else:
        print("  tema oscuro aplicado")

    # El relieve es una imagen bajo el dato: si no llega, el mapa sigue
    # dibujandose y nadie se entera. Se comprueba que cambie el lienzo.
    from PIL import Image
    import io as _io
    import numpy as _np

    def _lienzo():
        return _np.asarray(Image.open(_io.BytesIO(
            pg.locator("#map").screenshot())).convert("L"), dtype=float)

    con = _lienzo()
    pg.click("#tRelieve")
    pg.wait_for_timeout(900)
    sin = _lienzo()
    dif = _np.abs(con - sin)
    print(f"\nrelieve")
    print(f"  aporta sombra en el {100*(dif>2).mean():.0f}% del lienzo")
    if dif.max() < 5:
        print("  EL RELIEVE NO LLEGA AL LIENZO")
        ok = False
    pg.click("#tRelieve")
    pg.wait_for_timeout(600)

    # Cada unidad tiene su propio mapa y su propia direccion. Se comprueba que
    # el enlace recorte de verdad —no que abra el mapa nacional— y que elegir
    # una unidad descarte la anterior: componerlas da recortes vacios que el
    # usuario lee como un mapa roto.
    print("\nun mapa por unidad")
    nacional = pg.text_content("#cuenta").strip()
    for hash_, sel, nombre in (("#dep=ica", "#fDep", "departamento"),
                               ("#ter=9", "#fTer", "territorio"),
                               ("#prov=ica-pisco", "#fProv", "provincia")):
        # reload() y no solo goto(): navegar a la misma URL cambiando el
        # fragmento es una navegacion dentro del mismo documento, y el mapa
        # conservaria el estado del chequeo anterior en vez de abrirse en
        # frio, que es lo que el enlace compartido tiene que hacer.
        pg.goto(BASE + "/mapa" + hash_, wait_until="networkidle")
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(2600 if "prov" in hash_ else 1500)
        c = pg.text_content("#cuenta").strip()
        elegido = pg.eval_on_selector(
            sel, "e => e.selectedOptions.length ? e.selectedOptions[0].text : ''")
        print(f"  {nombre:<13} {hash_:<16} {c}")
        if c == nacional:
            print(f"  EL ENLACE {hash_} NO RECORTA EL MAPA")
            ok = False
        if not elegido or elegido.startswith("Tod"):
            print(f"  EL ENLACE {hash_} NO DEJA SELECCIONADA LA UNIDAD")
            ok = False
    otros = pg.eval_on_selector_all(
        "#fDep, #fTer", "e => e.map(x => x.value)")
    if any(v != "-1" for v in otros):
        print("  ELEGIR UNA UNIDAD NO DESCARTA LAS OTRAS")
        ok = False
    else:
        print("  las unidades se excluyen entre si: ok")
    pg.goto(BASE + "/mapa", wait_until="networkidle")
    pg.wait_for_timeout(900)

    # El mapa es un documento aparte, asi que su pertenencia al sitio depende
    # de que la navegacion funcione en ambos sentidos: aqui se comprueba, no
    # se supone.
    nav = pg.eval_on_selector_all("nav a", "e => e.map(a => a.textContent.trim())")
    activo = pg.eval_on_selector_all("nav a.on", "e => e.map(a => a.textContent.trim())")
    print(f"  nav: {len(nav)} enlaces, activo {activo}")
    if nav != NAV_SITIO or activo != ["Mapa"]:
        print(f"  LA NAVEGACION DEL MAPA NO COINCIDE CON LA DEL SITIO")
        print(f"    sitio: {NAV_SITIO}")
        print(f"    mapa : {nav}")
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
