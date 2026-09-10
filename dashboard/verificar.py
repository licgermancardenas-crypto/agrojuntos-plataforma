# -*- coding: utf-8 -*-
"""Abre el dashboard en un navegador real y comprueba que no esté roto.

Un `200` del servidor no dice nada sobre si la página se ve: un error de
JavaScript la deja en blanco y el servidor ni se entera. Esto recorre las
vistas una por una, recorre las 24 fichas departamentales, ejerce los filtros
del mapa, prueba los tres estados del tema y falla ante cualquier error de
consola.

Lo que comprueba de los dos modulos de aduanas no es que dibujen, sino las
reglas que los gobiernan: que un ano sin descargar no aparezca como US$ 0 del
lado importador, y del lado exportador que el tramo que todavia regulariza
vaya marcado, que el corte territorial no se extienda a los anos en que SUNAT
dejo de llenar el ubigeo, y que nada de lo ya medido se anualice.

Así se detectó que `Infinity` en el JSON del mapa —que Python escribe sin
protestar y `JSON.parse` rechaza— dejaba el atlas sin dibujar.

Uso:
    python servir.py
    python verificar.py
"""
import io
import json
import os
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
    ("#exportacion", "#tExpEmpresas tbody tr", "Exportación"),
    ("#logistica", "#tLogistica tbody tr", "Logística"),
    ("#expansion", "#tHubs tbody tr", "Expansión"),
    ("#canasta", "#canInsumos .bar", "Canasta"),
    # El calendario de todas las regiones era su propia vista y ahora es un
    # bloque de la canasta. Se sigue exigiendo que pinte: fusionar dos vistas
    # es la manera más fácil de perder la mitad de una sin que nadie lo note.
    ("#canasta", ".cal tbody tr", "Canasta · calendario"),
    ("#decisiones", "#decLista .card .b p", "Decisiones"),
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


# --------------------------------------------------------- mutaciones ----
# Una prueba que nunca vio fallar su defecto no es una prueba: es una línea
# que pasa. Con MUTAR=<nombre> se reintroduce a propósito un defecto concreto
# en la página —no en los datos— y se corre la suite entera: si la
# comprobación que debería cazarlo no aparece en la salida, esa comprobación
# es vacua. `auditar_pruebas.py` las recorre todas.
#
# Dos cosas que costaron y conviene dejar dichas. La mutación tiene que ir
# envuelta y llamada: `add_init_script` con una flecha suelta la evalúa y la
# descarta sin ejecutarla, y entonces todo «pasa» y la auditoría miente. Y
# tiene que tocar **nodos de texto**: reescribir innerHTML cada tantos
# milisegundos destruye los manejadores de los chips y deja la página
# inservible, con lo que la suite falla por no poder navegar y no por el
# defecto que se quería probar.
_MUT_BASE = """
  const textos = (sel, de, a) => {
    document.querySelectorAll(sel).forEach(raiz => {
      const it = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
      const ns = []; while (it.nextNode()) ns.push(it.currentNode);
      ns.forEach(n => { if (n.nodeValue.includes(de))
        n.nodeValue = n.nodeValue.split(de).join(a); });
    });
  };
"""

_SEL_IMP = "#impCobertura, #impCorteNota, #impDetalle, #impResumen"

MUTACIONES = {
    # El panel deja de aclarar que la cifra es FOB importado y no venta.
    "sin_fob": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('""" + _SEL_IMP + """', 'FOB', 'valor'), 120);
    })();""",

    # La nota vuelve a tapar los años a los que les faltan días.
    "sin_dias": "(() => {" + _MUT_BASE + """
      setInterval(() => {
        textos('#impCobertura', 'día por día', 'en general');
        textos('#impCobertura', 'faltan los días', 'sobran los días');
      }, 120);
    })();""",

    # El año en curso se presenta como un año cerrado más.
    "sin_ytd": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('#impPanel, #expKpis', ' YTD', ''), 120);
    })();""",

    # La serie dibuja un año menos de los pedidos.
    "serie_corta": """(() => {
      setInterval(() => document.querySelectorAll('.serie').forEach(s => {
        if (s.children.length > 1) s.removeChild(s.lastElementChild);
      }), 120);
    })();""",

    # Un año sin semanas descargadas se puede elegir como si tuviera dato.
    "anio_sin_dato_elegible": """(() => {
      setInterval(() => document.querySelectorAll(
        '#impAnio option, #expAnio option').forEach(o => {
        if (o.disabled) { o.disabled = false; o.title = ''; }
      }), 120);
    })();""",

    # El gráfico de precio recorta la escala sin declararlo.
    "sin_nota_escala": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('#v-empresas', 'no en cero', 'en cero'), 120);
    })();""",

    # Deja de declararse lo reservado por la Ley 29733.
    "sin_29733": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('#impPanel, #v-exportacion', 'Ley 29733',
        'la norma'), 60);
    })();""",

    # El precio deja de expresarse por kilo.
    "sin_kg": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('#v-empresas', '/kg', ''), 120);
    })();""",

    # Las migas dejan de mostrar el camino recorrido.
    "migas_cortas": """(() => {
      setInterval(() => {
        const n = document.getElementById('impMiga');
        if (n && n.textContent.indexOf('\\u203a') >= 0)
          n.textContent = n.textContent.split('\\u203a')[0];
      }, 120);
    })();""",

    # --- segunda tanda: mutaciones de valor -------------------
    # Las de arriba tocan texto y solo pueden auditar las
    # comprobaciones que leen texto. Estas cambian las cifras sin
    # tocar la forma —mismas casillas, mismos rotulos, otros
    # numeros— y sirven para ver si algo contrasta contra el dato.
    "cifras_infladas": r"""(() => {
      const infla = () => document.querySelectorAll(
        '#impResumen .v, #impKpis .v').forEach(n => {
        if (n.dataset.mut) return;
        n.dataset.mut = '1';
        n.textContent = n.textContent.replace(/[\d.,]+/, m => {
          const x = parseFloat(m.replace(/,/g, ''));
          return isNaN(x) ? m : (x * 3).toLocaleString('es-PE',
            {maximumFractionDigits: 1});
        });
      });
      setInterval(infla, 120);
    })();""",
    "meses_en_blanco": """(() => {
      setInterval(() => document.querySelectorAll(
        '#impMensual .sb i, #impMes .sb i').forEach(i => {
        i.style.height = '0%';
      }), 120);
    })();""",
    "reparto_falso": """(() => {
      setInterval(() => document.querySelectorAll(
        '#impMercadoCat .bar .bp').forEach(n => {
        if (n.dataset.mut) return;
        n.dataset.mut = '1';
        n.textContent = (parseFloat(n.textContent) / 2).toFixed(1) + '%';
      }), 120);
    })();""",
    "ranking_desordenado": """(() => {
      setInterval(() => document.querySelectorAll(
        '#tImportadores tbody, #tExportadores tbody, #tExpEmpresas tbody')
        .forEach(t => {
          if (t.dataset.mut || t.children.length < 3) return;
          t.dataset.mut = '1';
          t.appendChild(t.firstElementChild);
        }), 300);
    })();""",

    # --- tercera tanda: mutaciones de interaccion ---------------------
    # Las anteriores cambian lo que la pagina dice. Estas cambian lo que la
    # pagina hace: se traga el evento antes de que llegue a su manejador, de
    # modo que el control sigue ahi, se deja pulsar y no surte efecto. Es el
    # defecto mas facil de tener sin enterarse, porque no se ve.
    "filtro_territorio_muerto": """(() => {
      document.addEventListener('change', e => {
        if (e.target && e.target.id === 'fTer') e.stopImmediatePropagation();
      }, true);
    })();""",

    "busqueda_muerta": """(() => {
      ['input', 'keyup', 'change'].forEach(ev =>
        document.addEventListener(ev, e => {
          if (e.target && e.target.id === 'q') e.stopImmediatePropagation();
        }, true));
    })();""",

    "periodo_muerto": """(() => {
      document.addEventListener('click', e => {
        if (e.target && e.target.closest && e.target.closest('.periodo button'))
          e.stopImmediatePropagation();
      }, true);
    })();""",


    # --- cuarta tanda: las vistas de acopio ---------------------------
    "radio_invertido": """(() => {
      setInterval(() => document.querySelectorAll('#tAcopioHub tbody tr')
        .forEach(t => {
          if (t.dataset.mut) return;
          t.dataset.mut = '1';
          var c = t.querySelectorAll('td');
          if (c.length > 3) { var x = c[1].textContent;
            c[1].textContent = c[3].textContent; c[3].textContent = x; }
        }), 200);
    })();""",

    "sin_carga_huerfana": """(() => {
      setInterval(() => {
        var n = document.getElementById('expAcopioNota');
        if (n && n.textContent.indexOf('fuera de alcance') >= 0)
          n.textContent = n.textContent.split('Y ')[0];
      }, 120);
    })();""",

    "sin_salvedad_partida": """(() => {
      setInterval(() => {
        var n = document.getElementById('expSinLista');
        if (!n) return;
        n.querySelectorAll('.sub').forEach(function (s) { s.textContent = ''; });
      }, 120);
    })();""",

    # La mitad exportadora de Comercio vuelve a anualizarse: la cifra medida
    # se multiplica por el factor de la ventana de importacion.
    "comercio_export_anualiza": """(() => {
      setInterval(() => {
        var v = document.querySelector('#comKpis > div:nth-child(3) .v');
        if (!v || v.dataset.mut) return;
        var m = v.textContent.match(/([0-9][0-9.,]*)/);
        if (!m) return;
        var n = parseFloat(m[1].replace(/,/g, '')) * 4.7;
        v.textContent = v.textContent.replace(m[1], n.toFixed(2));
        v.dataset.mut = '1';
      }, 120);
    })();""",

    # La ficha muestra el origen del manifiesto como si fuera el domicilio
    # fiscal de la empresa, que es la lectura equivocada de ese campo.
    "ficha_origen_sin_salvedad": "(() => {" + _MUT_BASE + """
      setInterval(() => textos('#empExpHist',
        'ubigeo del manifiesto, no domicilio fiscal', 'domicilio de la empresa'),
        120);
    })();""",

    # El terreno vuelve a no contar: la columna dice que el desnivel no agrega
    # nada, que es la cuenta que la plataforma hizo durante meses.
    # Ojo con la forma: una version anterior de esta mutacion pedia el JSON
    # con `fetch` desde dentro del propio reemplazo de `fetch`, se llamaba a
    # si misma sin fin y dejaba la pagina colgada. La suite fallaba —por no
    # poder pintar la tabla— y la auditoria la daba por vacua, que es la
    # confusion que estas mutaciones existen para evitar.
    "terreno_plano": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('logistica.json') < 0) return r;
        const d = await r.clone().json();
        d.deps.forEach(x => { x.terr = 0; x.pct_terr = 0; x.llano = x.real; });
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # El cruce entre el embarque y la cota se rompe: cada producto sale a la
    # altura del puerto, que es lo que pasaria si el ubigeo apuntara a la
    # oficina del exportador y no al fundo.
    # La pantalla deja de decir que el septimo centro entro por decision y no
    # por cobertura: los dos se leen como si el algoritmo los hubiera elegido.
    "red_sin_decision": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('red.json') < 0) return r;
        const d = await r.clone().json();
        d.centros.forEach(c => { c.por = 'algoritmo'; });
        d.motivo = 'Los centros que elige la cobertura maxima.';
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # La pantalla deja de advertir que la cobertura de OSM es un techo y no
    # una medicion: el 54.8% «sin punto cerca» se lee como abandono medido.
    # La vista de productos vuelve a comer de la ventana de diez semanas: el
    # FOB del año cerrado se reemplaza por la ventana anualizada.
    "productos_anualiza": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('exportaciones/mercado.json') < 0) return r;
        const d = await r.clone().json();
        Object.keys(d.por_anio).forEach(a => { d.por_anio[a].fob *= 0.21; });
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # La pantalla deja de decir que el universo arancelario se amplio: las
    # familias nuevas pierden su marca y la nota, su explicacion. El total
    # sigue siendo el mismo y un 12% mas alto que la version anterior, sin
    # nada en pantalla que lo justifique.
    "universo_sin_marca": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('exportaciones/mercado.json') < 0) return r;
        const d = await r.clone().json();
        if (d.universo) {
          d.universo.familias_ampliacion = [];
          d.universo.por_capitulo = [];
        }
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # La cobertura pierde la banda: todos los meses dan el promedio, y la red
    # vuelve a juzgarse con una cifra plana que ocho meses del año no cumplen.
    "cobertura_sin_banda": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('cobertura_mes.json') < 0) return r;
        const d = await r.clone().json();
        d.meses.forEach(m => { m.cubierto_pct = d.plano_pct; });
        d.peor = d.meses[0]; d.mejor = d.meses[0];
        d.brecha_puntos = 0; d.meses_bajo_el_plano = 0;
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # La canasta pierde el calendario: todos los meses pesan lo mismo, de modo
    # que la temporada de compra desaparece y el vendedor sale cuando quiere.
    "canasta_sin_temporada": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('canasta.json') < 0) return r;
        const d = await r.clone().json();
        Object.keys(d.serie_por_region).forEach(k => {
          const s = d.serie_por_region[k];
          const m = s.reduce((a, b) => a + b, 0) / s.length;
          d.serie_por_region[k] = s.map(() => m);
        });
        Object.keys(d.insumo_por_region_mes).forEach(k => {
          const meses = d.insumo_por_region_mes[k];
          const uno = meses[Object.keys(meses)[0]];
          Object.keys(meses).forEach(m => { meses[m] = uno; });
          const cul = d.cultivo_por_region_mes[k] || {};
          const c1 = cul[Object.keys(cul)[0]];
          Object.keys(cul).forEach(m => { cul[m] = c1; });
        });
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    # La pantalla de decisiones pierde la alternativa contra la que se decidio:
    # queda el resultado sin el costo de oportunidad, que es exactamente la
    # lamina de conclusiones que este modulo existe para no ser.
    "decision_sin_alternativa": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('decisiones.json') < 0) return r;
        const d = await r.clone().json();
        d.decisiones.forEach(x => { x.alternativa = 'No aplica.'; });
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

    "canal_sin_salvedad": "(() => {" + _MUT_BASE + """
      setInterval(() => {
        textos('#redCanal', 'es un techo', 'es una medicion');
        textos('#redCanal', 'OpenStreetMap', 'el catastro');
      }, 120);
    })();""",

    "banda_al_nivel_del_mar": """(() => {
      const orig = window.fetch;
      window.fetch = async function (u, o) {
        const r = await orig.call(this, u, o);
        if (String(u).indexOf('altitud.json') < 0) return r;
        const d = await r.clone().json();
        d.bandas.forEach(b => { b.p10 = 5; b.p50 = 30; b.p90 = 120; });
        return new Response(JSON.stringify(d),
                            {headers: {'Content-Type': 'application/json'}});
      };
    })();""",

}


errores = []
ok = True

with sync_playwright() as pw:
    # En esta máquina se usa el Chrome instalado; en un runner de CI no hay
    # ninguno y sí está el chromium que trae playwright. La diferencia se
    # elige por entorno para que el mismo archivo sirva en los dos sitios.
    _nav = os.environ.get("NAVEGADOR", "chrome")
    # La máquina de desarrollo tiene 3.6 GB y el pipeline deja poco libre: sin
    # estos tres interruptores la suite muere a mitad de camino por falta de
    # memoria, y una corrida muerta se confunde con una prueba que falla.
    # Ninguno cambia lo que la página hace, solo lo que el navegador reserva.
    _ARGS = ["--disable-dev-shm-usage", "--disable-extensions", "--disable-gpu"]
    b = (pw.chromium.launch(args=_ARGS) if _nav == "chromium"
         else pw.chromium.launch(channel=_nav, args=_ARGS))
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    _mut = os.environ.get("MUTAR", "")
    if _mut:
        if _mut not in MUTACIONES:
            sys.exit("mutacion desconocida: " + _mut + " · disponibles: "
                     + ", ".join(sorted(MUTACIONES)))
        print("[MUTADO: " + _mut + "] defecto reintroducido a proposito; la suite DEBE fallar")
        pg.add_init_script(MUTACIONES[_mut])
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

    chrome = pg.evaluate("""(() => {
        const d = document.querySelector('#mapDep iframe').contentDocument;
        return ['nav', 'header.top', '.titulo'].map(
            s => { const el = d.querySelector(s);
                   return el ? getComputedStyle(el).display : 'ausente'; });
    })();
    """)
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

    # Contar cuatro indicadores no dice nada de lo que hay escrito en ellos:
    # con los cuatro rotulos en su sitio y las cifras multiplicadas por tres,
    # esta comprobacion pasaba. Ahora el importe se lee de la pantalla y se
    # contrasta contra el agregado del que la pagina dice sacarlo.
    PN = pg.evaluate("""async () => {
        const r = await fetch('/data/importaciones/panel.json');
        return await r.json(); }""")
    _tot = PN.get("total") or {}
    _por = {a: (_tot.get(a) or {}).get("fob") or 0 for a in PN["anios_pedidos"]}
    _acum = sum(_por.values())
    # El textContent de cada indicador pega valor, rotulo y pie: hay que leer
    # el valor solo, o el importe no se parsea y la comprobacion se cae sobre
    # un cero que no existe en ninguna parte.
    _vistos = [usd_a_num(v) for v in pg.eval_on_selector_all(
        "#impResumen .v", "f => f.map(x => x.textContent)") if "US$" in v]
    _esperados = [v for v in list(_por.values()) + [_acum] if v > 0]
    _cuadra = [v for v in _vistos
               if any(abs(v - e) / e < 0.02 for e in _esperados)]
    if _vistos and not _cuadra:
        print("  LAS CIFRAS DEL PANEL NO CUADRAN CON EL AGREGADO: "
              f"{[round(v) for v in _vistos]} no está en el JSON")
        ok = False
    elif _vistos:
        print(f"  {len(_cuadra)} de {len(_vistos)} importes del panel salen "
              "del agregado: ok")
    # La nota de cobertura tiene que decir la verdad en los tres escenarios:
    # con anos pendientes, nombrarlos y llamarlos «sin dato»; con los cinco
    # descargados pero alguno al que le faltan dias, decir cuales estan
    # enteros y cuales no; y solo si no falta nada, declararlos completos. Lo
    # que no puede es callarse ninguno de los tres.
    XP = pg.evaluate("""async () => {
        const r = await fetch('/data/importaciones/panel.json');
        const p = await r.json();
        return p.dias_sin_cubrir_por_anio || {}; }""")
    # El año en curso siempre tiene días por delante: que le falten no es un
    # hueco que declarar, y ya arrastra su YTD por todas partes. La regla vale
    # para los años cerrados, que son los que se leen como definitivos.
    parciales = [a for a, v in XP.items() if v and a != XP.get("_curso")]
    curso = pg.evaluate("""async () => {
        const p = await (await fetch('/data/importaciones/panel.json')).json();
        return p.anio_en_curso; }""")
    parciales = [a for a in parciales if a != curso]
    if "sin dato" in cob:
        print("  la cobertura nombra los anos sin descargar: ok")
    elif parciales:
        # 52 semanas archivadas no son 365 dias: la semana de ano nuevo no se
        # publica y se lleva dias de dos anos. Si la nota los tapa, un ano al
        # que le faltan ocho dias se lee como cerrado.
        faltan_nombrados = [a for a in parciales if a not in cob]
        if "día por día" not in cob or faltan_nombrados:
            print(f"  LA COBERTURA NO DECLARA LOS ANOS INCOMPLETOS "
                  f"{faltan_nombrados or parciales}")
            ok = False
        else:
            print(f"  declara que {', '.join(parciales)} no estan enteros: ok")
    elif "cinco años están completos" in cob:
        print("  la cobertura declara los cinco anos completos: ok")
        # Que hoy no falte ningun dia no puede dejar la regla sin probar:
        # manana falta uno y nadie se entera. Se sirve un panel con un ano
        # cerrado al que le faltan dias y se exige que la nota lo diga.
        _falso = json.loads(json.dumps(PN))
        _victima = [a for a in PN["anios_pedidos"]
                    if a != PN["anio_en_curso"]][-1]
        _falso.setdefault("dias_sin_cubrir_por_anio", {})[_victima] = 9
        pg.route("**/data/importaciones/panel.json", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(_falso, ensure_ascii=False)))
        pg.reload(wait_until="networkidle")
        pg.wait_for_selector("#fClase .chip[data-c='6']")
        pg.click("#fClase .chip[data-c='6']")
        pg.wait_for_selector("#impResumen .v", timeout=20000)
        _cob2 = pg.text_content("#impCobertura") or ""
        if _victima not in _cob2 or "día por día" not in _cob2:
            print(f"  CON {_victima} INCOMPLETO, LA COBERTURA NO LO DECLARA")
            ok = False
        else:
            print(f"  con {_victima} al que le faltan dias, la nota lo "
                  "nombra: ok")
        pg.unroute("**/data/importaciones/panel.json")
        pg.reload(wait_until="networkidle")
        pg.wait_for_selector("#fClase .chip[data-c='6']")
        pg.click("#fClase .chip[data-c='6']")
        pg.wait_for_selector("#impResumen .v", timeout=20000)
    else:
        print("  LA COBERTURA NO DECLARA QUE ANOS FALTAN")
        ok = False
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
    # Doce casillas vacías siguen siendo doce: contar barras daba por bueno un
    # gráfico con todas las alturas en cero. Lo que importa es que dibujen
    # algo y que el mes más alto sea el que manda en el dato.
    _alt = pg.eval_on_selector_all(
        "#impMes .sb i",
        "f => f.map(x => parseFloat(x.style.height) || 0)")
    if _alt and max(_alt) <= 0:
        print("  EL GRAFICO MENSUAL DIBUJA LOS DOCE MESES EN CERO")
        ok = False
    else:
        _pico = _alt.index(max(_alt)) + 1 if _alt else 0
        _emp = pg.evaluate("""async (ruc) => {
            const r = await fetch('/data/importaciones/importadores.json');
            const d = await r.json();
            return (d[ruc] || {}).por_mes || {}; }""", ruc_i)
        _anio = pg.eval_on_selector("#impAnio", "s => s.value") if             pg.query_selector("#impAnio") else ""
        _mes = {k[5:]: v for k, v in _emp.items() if k[:4] == _anio}
        if _mes:
            _pico_dato = int(max(_mes, key=lambda k: _mes[k]))
            if _pico != _pico_dato:
                print(f"  EL MES PICO DIBUJADO ({_pico}) NO ES EL DEL DATO "
                      f"({_pico_dato})")
                ok = False
            else:
                print(f"  el mes más alto del gráfico es el del dato "
                      f"({_pico_dato:02d}): ok")
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

    # El recorrido completo del bloque: mercado -> ano -> categoria -> partida
    # -> empresa. Lo que se comprueba no es que dibuje, sino que cada escalon
    # diga la verdad del escalon anterior: que los porcentajes se recalculen
    # sobre el ano elegido, que el ranking de una partida sea un subconjunto
    # del de su categoria, y que un ano sin descargar no se pueda elegir.
    print("\nque importa este mercado · recorrido")
    pg.evaluate("() => location.hash = '#empresas'")
    pg.wait_for_selector("#fClase .chip[data-c='6']")
    pg.click("#fClase .chip[data-c='6']")
    pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=20000)

    P = pg.evaluate(
        "async () => (await (await fetch("
        "'/data/importaciones/panel.json')).json())")
    medidos = [a for a in P["anios_pedidos"]
               if (P["cobertura_semanas"].get(a) or 0) > 0]
    sin = [a for a in P["anios_pedidos"] if a not in medidos]

    # Los anos sin manifiestos existen en el selector pero no se pueden elegir,
    # y dicen por que.
    ops = pg.eval_on_selector_all(
        "#impAnio option",
        "f => f.map(o => [o.value, o.disabled, o.textContent])")
    apagados = [o[0] for o in ops if o[1]]
    if sorted(apagados) != sorted(sin):
        print(f"  {sin} sin descargar y {apagados} apagados: "
              "UN ANO SIN MANIFIESTOS SE PUEDE ELEGIR")
        ok = False
    elif any("pendiente" not in o[2] for o in ops if o[1]):
        print("  UN ANO APAGADO NO DICE QUE ESTA PENDIENTE DE CARGA")
        ok = False
    elif sin:
        print(f"  {len(sin)} anos pendientes de carga, apagados y explicados: ok")

    # Con los cinco anos descargados no hay ninguno que apagar, y una prueba
    # sin caso pasa en silencio: comparaba una lista vacia contra otra y
    # firmaba «ok» sin haber mirado nada. El caso se construye —se sirve el
    # panel con un ano sin semanas— y se mira si la interfaz lo apaga.
    falso = json.loads(json.dumps(P))
    hueco = P["anios_pedidos"][0]
    falso["cobertura_semanas"][hueco] = 0
    falso["anios_con_dato"] = [a for a in P["anios_con_dato"] if a != hueco]
    pg.route("**/data/importaciones/panel.json", lambda ruta: ruta.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(falso, ensure_ascii=False)))
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector("#fClase .chip[data-c='6']")
    pg.click("#fClase .chip[data-c='6']")
    pg.wait_for_selector("#impResumen .v", timeout=20000)
    fila = [o for o in pg.eval_on_selector_all(
        "#impAnio option",
        "f => f.map(o => [o.value, o.disabled, o.textContent])")
        if o[0] == hueco]
    if not fila or not fila[0][1]:
        print(f"  UN ANO SIN SEMANAS SE PUEDE ELEGIR: {hueco}")
        ok = False
    elif "pendiente" not in fila[0][2]:
        print(f"  EL ANO {hueco} NO DICE QUE ESTA PENDIENTE DE CARGA")
        ok = False
    else:
        print(f"  con {hueco} sin semanas, la interfaz lo apaga y lo "
              "explica: ok")
    pg.unroute("**/data/importaciones/panel.json")
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector("#fClase .chip[data-c='6']")
    pg.click("#fClase .chip[data-c='6']")
    pg.wait_for_selector("#impResumen .v", timeout=20000)

    def pcts():
        return [float(t.replace("%", "").replace(",", "."))
                for t in pg.eval_on_selector_all(
                    "#impMercadoCat .bar .bp", "f => f.map(x => x.textContent)")]

    # El reparto se recalcula sobre el ano elegido: si sumara 100 en un ano y
    # no en otro, estaria reutilizando porcentajes ajenos.
    for a in medidos[:2]:
        pg.select_option("#impAnio", a)
        pg.wait_for_timeout(250)
        s = sum(pcts())
        fob = pg.text_content("#impResumen .v") or ""
        if abs(s - 100) > 1.5:
            print(f"  {a}: las categorias suman {s:.1f}% "
                  "EL REPARTO NO SE RECALCULA SOBRE EL ANO")
            ok = False
        else:
            print(f"  {a}: {len(pcts())} categorias suman {s:.1f}% ok")

    # Categoria.
    anio = medidos[0]
    pg.select_option("#impAnio", anio)
    pg.wait_for_timeout(250)
    cat = pg.eval_on_selector("#impMercadoCat .bar.clic",
                              "e => e.dataset.k")
    pg.click("#impMercadoCat .bar.clic")
    pg.wait_for_selector("#impEmpresas tbody tr", timeout=15000)
    miga = (pg.text_content("#impMiga") or "")
    if cat not in miga:
        print("  LA CATEGORIA NO APARECE EN LAS MIGAS")
        ok = False
    n_cat = len(pg.query_selector_all("#impEmpresas tbody tr"))
    n_part = len(pg.query_selector_all("#impCatPart .bar.clic"))
    print(f"  {cat}: {n_part} partidas · {n_cat} importadores en el top 10")

    # El Top N y el buscador mueven el ranking, no lo decoran.
    pg.click("#impTope .chip[data-t='0']")
    pg.wait_for_timeout(200)
    n_todos = len(pg.query_selector_all("#impEmpresas tbody tr"))
    if n_todos <= n_cat:
        print("  «TODOS» NO MUESTRA MAS EMPRESAS QUE EL TOP 10")
        ok = False
    else:
        print(f"  Top 10 -> Todos: {n_cat} -> {n_todos} importadores ok")
    ruc = pg.eval_on_selector(
        "#impEmpresas tbody tr td.name a",
        "a => a.getAttribute('href').split('=')[1]")
    pg.fill("#impBuscar", ruc)
    pg.wait_for_timeout(250)
    n_busca = len(pg.query_selector_all("#impEmpresas tbody tr"))
    if n_busca != 1:
        print(f"  buscar un RUC exacto devuelve {n_busca} filas: "
              "EL BUSCADOR NO FILTRA")
        ok = False
    else:
        print("  el buscador encuentra un RUC exacto: ok")
    pg.fill("#impBuscar", "")
    pg.wait_for_timeout(200)

    # Partida: su ranking tiene que ser un subconjunto del de la categoria.
    if n_part:
        pg.click("#impCatPart .bar.clic")
        pg.wait_for_selector("#impEmpresas tbody tr", timeout=15000)
        pg.click("#impTope .chip[data-t='0']")
        pg.wait_for_timeout(200)
        n_p = len(pg.query_selector_all("#impEmpresas tbody tr"))
        if n_p > n_todos:
            print("  UNA PARTIDA TIENE MAS IMPORTADORES QUE SU CATEGORIA")
            ok = False
        else:
            print(f"  la partida acota el ranking: {n_todos} -> {n_p} ok")
        if (pg.text_content("#impMiga") or "").count("›") < 3:
            print("  LAS MIGAS NO LLEGAN AL NIVEL DE PARTIDA")
            ok = False

    # Volver por las migas devuelve al nivel anterior sin recargar.
    pg.click("#impMiga a[data-n='raiz']")
    pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=10000)
    print("  volver por las migas: ok")

    # Evolucion.
    pg.click("#impVista .chip[data-v='evol']")
    pg.wait_for_selector("#impEvolSerie .sb", timeout=10000)
    barras_ev = len(pg.query_selector_all("#impEvolSerie .sb"))
    huecos_ev = len(pg.query_selector_all("#impEvolSerie .sb.vacio"))
    if barras_ev != len(P["anios_pedidos"]) or huecos_ev != len(sin):
        print(f"  evolucion: {barras_ev} barras y {huecos_ev} huecos, "
              f"esperados {len(P['anios_pedidos'])} y {len(sin)}: MAL")
        ok = False
    else:
        print(f"  evolucion: {barras_ev} anos, {huecos_ev} sin descargar ok")
    alguna = sorted(P["cats"])[0]
    pg.select_option("#impSerie", alguna)
    pg.wait_for_timeout(300)
    if alguna not in (pg.text_content("#impEvol") or ""):
        print("  LA SERIE POR CATEGORIA NO SE APLICA")
        ok = False
    else:
        print(f"  serie por categoria «{alguna[:22]}»: ok")

    # El ano en curso nunca se presenta como ano cerrado.
    txt_panel = pg.text_content("#impPanel") or ""
    if P["anio_en_curso"] in txt_panel and "YTD" not in txt_panel:
        print("  EL ANO EN CURSO SE PRESENTA SIN MARCA DE YTD")
        ok = False
    else:
        print("  el ano en curso arrastra su YTD: ok")

    # Y de la tabla se llega a la ficha de la empresa, que ya existia.
    pg.click("#impVista .chip[data-v='anio']")
    pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=10000)
    pg.click("#impMercadoCat .bar.clic")
    pg.wait_for_selector("#impEmpresas tbody tr td.name a", timeout=15000)
    pg.click("#impEmpresas tbody tr td.name a")
    pg.wait_for_selector("#empPerfil h3", timeout=25000)
    if not (pg.text_content("#empPerfil h3") or "").strip():
        print("  DESDE EL RANKING NO SE LLEGA A LA FICHA DE LA EMPRESA")
        ok = False
    else:
        print("  del ranking a la ficha de la empresa: ok")

    # El precio por kilo. Lo que se comprueba no es que dibuje: es que solo
    # aparezca donde significa algo. Una subpartida que agrupa productos que no
    # se parecen —o que no se comercia por peso— no puede mostrar precio, y
    # tiene que decir por que en vez de callarse.
    # Un ranking desordenado sigue teniendo sus cien filas y sus columnas:
    # ninguna comprobacion de forma lo nota. Y el orden es justamente lo que
    # la tabla promete en su encabezado —«los cien mayores»—, asi que si la
    # primera fila no es la mayor, la pagina miente donde mas se la lee.
    pg.evaluate("() => location.hash = '#comercio'")
    pg.wait_for_selector("#tImportadores tbody tr td", timeout=25000)
    # La tabla se lee un momento despues de pintarse y no en el instante. La
    # auditoria lo destapo: el defecto que desordena el ranking lo reintroduce
    # un temporizador cada 300 ms, asi que leer la tabla recien pintada la
    # encontraba todavia en orden y esta comprobacion cantaba «ok» sobre una
    # pagina rota —la cazaba otra, por casualidad—. Una prueba que depende de
    # llegar tarde o temprano no es una prueba.
    pg.wait_for_timeout(900)
    for tid, col in (("tImportadores", 3), ("tExportadores", 2)):
        vals = [usd_a_num(t) for t in pg.eval_on_selector_all(
            "#" + tid + " tbody tr td:nth-child(" + str(col) + ")",
            "f => f.map(x => x.textContent)")]
        vals = [v for v in vals if v > 0]
        if len(vals) < 3:
            continue
        if vals != sorted(vals, reverse=True):
            bajos = [i for i in range(len(vals) - 1) if vals[i] < vals[i + 1]]
            print("  " + tid + ": EL RANKING NO ESTA ORDENADO POR VALOR "
                  "(filas " + str(bajos[:2]) + ")")
            ok = False
        else:
            print("  " + tid + ": " + str(len(vals)) +
                  " filas en orden descendente: ok")


    print("\nprecio de importacion")
    # El bloque anterior termino dentro de una ficha de empresa; hay que
    # volver al directorio y encender la subcategoria para que el panel
    # exista antes de recorrerlo.
    pg.evaluate("() => location.hash = '#empresas'")
    pg.wait_for_selector("#fClase .chip[data-c='6']", timeout=20000)
    pg.click("#fClase .chip[data-c='6']")
    pg.wait_for_selector("#impMiga", timeout=20000)
    # El panel conserva el recorrido: puede haber quedado dentro de una
    # categoria, y entonces la lista de categorias no esta a la vista.
    raiz = pg.query_selector("#impMiga a[data-n='raiz']")
    if raiz:
        raiz.click()
    pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=20000)
    PR = pg.evaluate(
        "async () => (await (await fetch("
        "'/data/importaciones/precios.json')).json())")
    con_precio = sorted(PR["partidas"],
                        key=lambda p: -PR["partidas"][p]["total"]["fob"])
    sin_precio = list(PR["rechazadas"])
    print(f"  {len(con_precio)} subpartidas publican precio, "
          f"{len(sin_precio)} no")

    def ir_a(part):
        cat = (PR["partidas"].get(part) or {}).get("categoria")
        if not cat:
            cat = pg.evaluate(
                "async (p) => { const j = await (await fetch("
                "'/data/importaciones/panel.json')).json();"
                " for (const c in j.cats) { const y = j.cats[c].partidas;"
                "  for (const a in y) if (y[a].some(x => x.p === p)) return c; }"
                " return null; }", part)
        # En la raiz, «Importaciones» es texto y no enlace: solo hay que
        # pulsarlo cuando el recorrido esta mas adentro.
        r = pg.query_selector("#impMiga a[data-n='raiz']")
        if r:
            r.click()
        pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=10000)
        pg.click("#impMercadoCat .bar.clic[data-k=" + repr(cat) + "]")
        pg.wait_for_selector("#impCatPart .bar.clic", timeout=15000)
        b = pg.query_selector("#impCatPart .bar.clic[data-k='" + part + "']")
        if not b:
            return False
        b.click()
        pg.wait_for_timeout(600)
        return True

    # Una partida con precio: cuatro indicadores, la serie anual completa y el
    # mes a mes del ano elegido.
    p_si = con_precio[0]
    if ir_a(p_si):
        k = len(pg.query_selector_all("#impPrecioKpi > div"))
        an = len(pg.query_selector_all("#impPrecioAnual .sb"))
        me = len(pg.query_selector_all("#impPrecioMes .sb"))
        v = (pg.text_content("#impPrecioKpi .v") or "")
        print(f"  {p_si}: {k} indicadores · {an} anos · {me} meses · {v}")
        if k != 4 or an != 5 or me != 12:
            print("  EL BLOQUE DE PRECIO LLEGA INCOMPLETO")
            ok = False
        if "US$" not in v or "/kg" not in v:
            print("  EL PRECIO NO SE EXPRESA EN US$ POR KILO")
            ok = False
        # La escala recortada tiene que declararse: si no, la altura de la
        # barra se lee como proporcion y no lo es.
        nota = (pg.text_content("#impPrecioNota") or "")
        if "no en cero" not in nota:
            print("  LA ESCALA RECORTADA NO SE DECLARA")
            ok = False
        else:
            print("  declara que la escala no arranca en cero: ok")
        # Y el ranking gana las dos columnas del precio por empresa.
        cols = pg.eval_on_selector_all(
            "#impEmpresas thead th", "f => f.map(x => x.textContent)")
        if "US$/kg" not in cols or "vs mercado" not in cols:
            print(f"  EL RANKING NO TRAE PRECIO POR EMPRESA: {cols}")
            ok = False
        else:
            print("  el ranking compara el precio de cada empresa: ok")

    # Una partida sin precio: tiene que explicarse, no quedarse muda.
    p_no = None
    for p in ("380891", "380892", "310590"):
        if p in PR["rechazadas"]:
            p_no = p
            break
    if p_no and ir_a(p_no):
        t = (pg.text_content("#impDetalle") or "")
        if pg.query_selector("#impPrecioKpi"):
            print(f"  {p_no} NO DEBERIA PUBLICAR PRECIO Y LO PUBLICA")
            ok = False
        elif "no publica precio" not in t:
            print("  UNA PARTIDA SIN PRECIO NO EXPLICA POR QUE")
            ok = False
        else:
            print(f"  {p_no} explica por que no publica precio: ok")

    # Los importadores sin titular publicable no pueden aparecer como empresa.
    pg.click("#impMiga a[data-n='raiz']")
    pg.wait_for_selector("#impMercadoCat .bar.clic", timeout=10000)
    pg.click("#impMercadoCat .bar.clic")
    pg.wait_for_selector("#impEmpresas tbody tr", timeout=15000)
    pg.click("#impTope .chip[data-t='0']")
    pg.wait_for_timeout(300)
    rucs = pg.eval_on_selector_all(
        "#impEmpresas tbody tr td:nth-child(3)",
        "f => f.map(x => x.textContent.trim())")
    malos = [r for r in rucs if not r.isdigit()]
    if malos:
        print(f"  UN IMPORTADOR SIN RUC APARECE EN EL RANKING: {malos[:2]}")
        ok = False
    else:
        print(f"  los {len(rucs)} del ranking tienen RUC de verdad: ok")
    cob = (pg.text_content("#impCobertura") or "")
    if "29733" not in cob:
        print("  NO SE DECLARA LO RESERVADO POR LA LEY 29733")
        ok = False
    else:
        print("  declara el monto reservado por la Ley 29733: ok")


    # ------------------------------------------------------- exportacion --
    # La vista exportadora no se comprueba porque dibuje, sino por las cuatro
    # reglas que la gobiernan, que son las mismas que gobiernan el dato:
    #
    #   1. Abre en el ultimo ano completo. El ano en curso, de titular, invita
    #      a compararlo con anos enteros.
    #   2. El tramo que todavia regulariza va marcado y declarado. Una serie
    #      que termina en una caida invita a leer una caida.
    #   3. El corte territorial no se extiende a los anos en que SUNAT dejo de
    #      llenar el ubigeo.
    #   4. Nada se anualiza: el selector de periodo del encabezado manda sobre
    #      las vistas de diez semanas y no sobre esta, que trae anos medidos.
    print("\nexportacion · cinco anos medidos")
    pg.evaluate("() => location.hash = '#exportacion'")
    pg.wait_for_selector("#tExpEmpresas tbody tr", timeout=25000)

    # El JSON es la referencia: lo que la pantalla dice tiene que salir de ahi
    # y no de una constante escrita en el JavaScript.
    XM = pg.evaluate("""async () => {
        const r = await fetch('/data/exportaciones/mercado.json');
        return await r.json(); }""")
    anio_curso = XM["anio_en_curso"]
    completos = [a for a in XM["anios_con_dato"]
                 if a != anio_curso and XM["cobertura_semanas"].get(a, 0) >= 45]
    esperado = completos[-1]

    sel_anio = pg.eval_on_selector("#expAnio", "s => s.value")
    print(f"  abre en {sel_anio} · ultimo completo {esperado} · "
          f"en curso {anio_curso}")
    if sel_anio != esperado:
        print("  LA VISTA NO ABRE EN EL ULTIMO ANO COMPLETO")
        ok = False
    opciones = pg.eval_on_selector_all("#expAnio option",
                                       "o => o.map(x => x.textContent)")
    if not any(o.strip() == anio_curso + " YTD" for o in opciones):
        print("  EL ANO EN CURSO NO ARRASTRA SU YTD EN EL SELECTOR")
        ok = False
    else:
        print("  el ano en curso arrastra su YTD: ok")

    # El KPI sale del JSON, no de otro lado.
    kpi_fob = usd_a_num(pg.eval_on_selector("#expKpis > div .v", "e => e.textContent"))
    fob_json = XM["por_anio"][esperado]["fob"]
    if abs(kpi_fob - fob_json) / fob_json > 0.01:
        print(f"  EL KPI NO COINCIDE CON EL JSON: {kpi_fob:,.0f} vs {fob_json:,.0f}")
        ok = False
    else:
        print("  el KPI de FOB sale del agregado: ok")

    # --- regla 2: el tramo incompleto, marcado y dicho ---------------------
    barras = pg.eval_on_selector_all("#expSerie .sb", """f => f.map(x => ({
        a: x.querySelector('b').textContent.trim(),
        parcial: x.classList.contains('parcial'),
        px: Math.round(x.querySelector('i').getBoundingClientRect().height)}))""")
    parciales = [x["a"] for x in barras if x["parcial"]]
    print(f"  serie: {len(barras)} anos · parcial {parciales}")
    if not any(anio_curso in a for a in parciales):
        print("  EL ANO EN CURSO NO SE MARCA COMO PARCIAL EN LA SERIE")
        ok = False
    for bar in barras:
        if bar["a"].endswith("*") and bar["a"].rstrip("*") in completos:
            print(f"  UN ANO COMPLETO APARECE MARCADO: {bar['a']}")
            ok = False

    # La altura tiene que seguir al valor. Con la etiqueta del ano dentro de
    # la caja, el porcentaje se calculaba sobre un alto que ya estaba ocupado
    # y todo lo que pasara del 77% topaba igual: dos anos distintos se
    # dibujaban iguales. Se comprueba el orden, no el pixel.
    porc = [(x["a"].rstrip("*"), x["px"]) for x in barras]
    valores = {a: XM["por_anio"][a]["fob"] for a in XM["por_anio"]}
    # La comparacion va en los dos sentidos. Mirar solo uno dejaba pasar el
    # caso que importa: dos anos altos topando contra el mismo maximo, que es
    # como se veia el defecto —2024 y 2025 dibujados iguales—.
    desorden = []
    for i, x in enumerate(porc):
        for y in porc[i + 1:]:
            if x[0] not in valores or y[0] not in valores:
                continue
            vx, vy = valores[x[0]], valores[y[0]]
            # Diferencias de menos del 3% pueden empatar por redondeo a pixel.
            if abs(vx - vy) / max(vx, vy) < 0.03:
                continue
            # El empate es la forma que tenia el defecto: dos anos que se
            # diferencian en un 19% dibujados con el mismo alto, porque los
            # dos topaban contra el maximo. Comparar solo «mayor que» no lo
            # veia —ningun estricto dispara cuando los dos lados son iguales—.
            if abs(x[1] - y[1]) <= 1 or (vx > vy) != (x[1] > y[1]):
                desorden.append((x, y))
    if desorden:
        print(f"  LAS BARRAS NO SIGUEN AL VALOR: {desorden[:2]}")
        ok = False
    else:
        print("  la altura de cada barra sigue a su FOB: ok")

    nota = pg.text_content("#expSerieNota") or ""
    frontera = XM["rezago"]["frontera_completitud"]
    if frontera not in nota:
        print("  LA SERIE NO DECLARA LA FRONTERA DE COMPLETITUD")
        ok = False
    elif "rezago" not in nota:
        print("  LA SERIE NO EXPLICA QUE LO ULTIMO ES REZAGO Y NO CAIDA")
        ok = False
    else:
        print(f"  declara la frontera {frontera} y el rezago: ok")

    # --- regla 3: el territorio, solo donde hay ubigeo ---------------------
    usados = XM["departamentos"]["anios_usados"]
    et_dep = pg.text_content("#expDepEt") or ""
    nota_dep = pg.text_content("#expDepNota") or ""
    print(f"  territorio sobre {usados[0]}-{usados[-1]}")
    if usados[0] not in et_dep or usados[-1] not in et_dep:
        print("  EL CORTE TERRITORIAL NO DECLARA SOBRE QUE ANOS SE CALCULA")
        ok = False
    if anio_curso in et_dep:
        print("  EL CORTE TERRITORIAL SE EXTIENDE AL ANO SIN UBIGEO")
        ok = False
    apaga = any(t in nota_dep for t in ("dejando de llenar", "apagando",
                                        "se está apagando"))
    if "domicilio fiscal" not in nota_dep or not apaga:
        print("  LA NOTA NO ADVIERTE QUE EL UBIGEO NO ES DOMICILIO FISCAL "
              "NI QUE SE ESTA APAGANDO")
        ok = False
    else:
        print("  advierte que el ubigeo apunta al fundo y que se apaga: ok")

    # --- el conteo de destinos es un conteo ---------------------------------
    # `paises` viaja recortado a los diez mayores, asi que su largo no es el
    # numero de destinos. Cuando lo era, toda la tabla decia «10 destinos».
    destinos = pg.eval_on_selector_all(
        "#tExpEmpresas tbody tr td:nth-child(4) .sub2",
        "f => f.map(x => parseInt(x.textContent))")
    if destinos and max(destinos) <= 10:
        print(f"  EL CONTEO DE DESTINOS TOPA EN {max(destinos)}: "
              "esta contando una lista recortada")
        ok = False
    else:
        print(f"  destinos por empresa: hasta {max(destinos)}: ok")

    # --- regla 4: aqui no se anualiza --------------------------------------
    # El selector del encabezado multiplica las cifras de las vistas que miden
    # diez semanas. Esta trae anos medidos y tiene que ignorarlo: si al pasar
    # a «Anual» el FOB se mueve, alguien esta extrapolando lo ya medido.
    antes = pg.eval_on_selector("#expKpis > div .v", "e => e.textContent")
    botones = pg.eval_on_selector_all(".periodo button",
                                      "b => b.map(x => x.textContent.trim())")
    if "Anual" in botones:
        pg.click(".periodo button:has-text('Anual')")
        pg.wait_for_timeout(600)
        pg.evaluate("() => location.hash = '#exportacion'")
        pg.wait_for_timeout(600)
        despues = pg.eval_on_selector("#expKpis > div .v", "e => e.textContent")
        if antes != despues:
            print(f"  EL PERIODO ANUALIZA UNA CIFRA YA MEDIDA: "
                  f"{antes} -> {despues}")
            ok = False
        else:
            print("  el selector de periodo no toca los anos medidos: ok")
        if "Medido" in botones:
            pg.click(".periodo button:has-text('Medido')")
            pg.wait_for_timeout(400)

    # --- cambiar de ano cambia la tabla ------------------------------------
    fob_antes = pg.eval_on_selector("#tExpEmpresas tbody tr td:nth-child(2)",
                                    "e => e.textContent")
    pg.select_option("#expAnio", anio_curso)
    pg.wait_for_timeout(700)
    fob_curso = pg.eval_on_selector("#tExpEmpresas tbody tr td:nth-child(2)",
                                    "e => e.textContent")
    pie = pg.text_content("#expAnioPie") or ""
    if fob_antes == fob_curso:
        print("  CAMBIAR DE ANO NO CAMBIA LA TABLA")
        ok = False
    elif "regularizando" not in pie:
        print("  EL ANO EN CURSO NO AVISA QUE SIGUE REGULARIZANDO")
        ok = False
    else:
        print("  al ano en curso: la tabla cambia y el pie avisa: ok")

    # --- lo reservado por la Ley 29733, dicho ------------------------------
    pie_nota = pg.text_content("#expNota") or ""
    if "29733" not in pie_nota:
        print("  NO SE DECLARA LO RESERVADO POR LA LEY 29733")
        ok = False
    else:
        print("  declara lo que queda fuera por proteccion de datos: ok")

    # ------------------------------- comercio · dos relojes en una pantalla --
    # La pantalla junta la importacion de insumos —diez semanas anualizadas,
    # que es todo lo que hay— con la agroexportacion, que desde el historico
    # tiene cinco anos medidos. Mezclarlas sin decirlo era el defecto: las dos
    # cifras se leian como si salieran del mismo periodo. Se comprueba que la
    # mitad exportadora salga del agregado, que el selector no la toque y que
    # el pie diga cual es cual.
    print("")
    print("comercio · dos relojes en una pantalla")
    pg.evaluate("() => location.hash = '#comercio'")
    pg.wait_for_selector("#tExportadores tbody tr td", timeout=25000)
    pg.wait_for_timeout(700)
    EX = pg.evaluate("""async () => {
        const r = await fetch('/data/exportaciones/mercado.json');
        return await r.json(); }""")
    WEB = pg.evaluate("""async () => {
        const r = await fetch('/data/exportaciones/exportadores_min.json');
        return await r.json(); }""")
    cerrado = [a for a in EX["anios_con_dato"] if a < EX["anio_en_curso"]][-1]
    esperado = EX["por_anio"][cerrado]["fob"]
    kpis = pg.eval_on_selector_all("#comKpis > div",
                                   "d => d.map(x => x.textContent)")
    k_exp = [k for k in kpis if "agroexportación" in k]
    visto = usd_a_num(pg.eval_on_selector(
        "#comKpis > div:nth-child(3) .v", "e => e.textContent"))
    print("  agroexportacion %s: pantalla %s · agregado %s"
          % (cerrado, f"{visto:,.0f}", f"{esperado:,.0f}"))
    if not k_exp or cerrado not in k_exp[0]:
        print("  EL KPI EXPORTADOR NO DECLARA EL ANO QUE MIDE")
        ok = False
    elif abs(visto - esperado) / esperado > 0.01:
        print("  EL FOB EXPORTADO DE COMERCIO NO CUADRA CON EL AGREGADO")
        ok = False
    else:
        print("  el KPI exportador es el ano cerrado del agregado: ok")

    # El selector de periodo mueve una mitad y no la otra. Que las dos se
    # muevan —o que ninguna lo haga— significa que se perdio la distincion.
    imp_a = pg.eval_on_selector("#comKpis > div:nth-child(1) .v",
                                "e => e.textContent")
    exp_a = pg.eval_on_selector("#comKpis > div:nth-child(3) .v",
                                "e => e.textContent")
    pg.click(".periodo button:has-text('Medido')")
    pg.wait_for_timeout(700)
    imp_d = pg.eval_on_selector("#comKpis > div:nth-child(1) .v",
                                "e => e.textContent")
    exp_d = pg.eval_on_selector("#comKpis > div:nth-child(3) .v",
                                "e => e.textContent")
    if imp_a == imp_d:
        print("  EL PERIODO NO ACTUA SOBRE LA MITAD IMPORTADORA")
        ok = False
    elif exp_a != exp_d:
        print("  EL PERIODO ANUALIZA LA MITAD EXPORTADORA: %s -> %s"
              % (exp_a, exp_d))
        ok = False
    else:
        print("  el periodo mueve la importacion (%s -> %s) y deja quieta la "
              "exportacion: ok" % (imp_a, imp_d))
    pg.click(".periodo button:has-text('Anual')")
    pg.wait_for_timeout(500)

    # El ranking tiene que salir del recorte de cinco anos y no de la ventana:
    # con diez semanas la primera fila era otra empresa y otro orden de
    # magnitud.
    mayor = max(WEB["emp"], key=lambda e: e["t"])
    fila = pg.eval_on_selector_all(
        "#tExportadores tbody tr:first-child td",
        "c => c.map(x => x.textContent)")
    if mayor["n"][:20] not in fila[0] or \
            abs(usd_a_num(fila[1]) - mayor["t"]) / mayor["t"] > 0.01:
        print("  EL RANKING EXPORTADOR NO SALE DEL RECORTE DE CINCO ANOS: "
              "%s / %s" % (fila[0][:40], fila[1]))
        ok = False
    else:
        print("  el ranking sale de los cinco anos medidos (%s, %s): ok"
              % (mayor["n"][:24], fila[1]))

    nota_com = pg.text_content("#comNota") or ""
    if "anualiza" not in nota_com or "no se extrapola" not in nota_com:
        print("  LA NOTA NO DISTINGUE LOS DOS PERIODOS DE LA PANTALLA")
        ok = False
    else:
        print("  el pie declara los dos relojes: ok")

    # ---------------------------- la ficha, del lado exportador -------------
    # La ficha de empresa mostraba la exportacion de la ventana de diez
    # semanas. Ahora trae los cinco anos y, con ellos, el origen declarado en
    # el manifiesto —que apunta al fundo y no al domicilio fiscal—. Esa
    # salvedad es la que hace util el campo: sin ella, la ficha estaria
    # afirmando que la empresa tiene su sede donde en realidad tiene el campo.
    print("")
    print("la ficha, del lado exportador")
    pg.evaluate("() => location.hash = '#empresa=" + mayor["r"] + "'")
    pg.wait_for_selector("#empExpHist .card", timeout=25000)
    pg.wait_for_timeout(600)
    ficha = " ".join((pg.text_content("#empExpHist") or "").split())
    fob_ficha = usd_a_num(pg.eval_on_selector(
        "#empExpHist .kpis > div:first-child .v", "e => e.textContent"))
    barras_anio = len(pg.query_selector_all("#empExpHist .serie .sb"))
    print("  %s: %s en %d anos" % (mayor["n"][:24],
                                   f"{fob_ficha:,.0f}", barras_anio))
    if abs(fob_ficha - mayor["t"]) / mayor["t"] > 0.01:
        print("  EL FOB DE LA FICHA NO CUADRA CON EL RECORTE")
        ok = False
    elif barras_anio != len(WEB["meta"]["anios"]):
        print("  LA SERIE DE LA FICHA NO TRAE LOS %d ANOS"
              % len(WEB["meta"]["anios"]))
        ok = False
    else:
        print("  el bloque de cinco anos cuadra con el recorte: ok")
    if "no domicilio fiscal" not in ficha:
        print("  LA FICHA PRESENTA EL ORIGEN COMO DOMICILIO FISCAL")
        ok = False
    else:
        print("  declara que el origen es el ubigeo del manifiesto: ok")

    # Y una empresa que solo importa no puede estrenar un bloque exportador
    # vacio: la ausencia de dato tiene que ser ausencia de bloque.
    rucs_exp = set(e["r"] for e in WEB["emp"])
    solo_imp = pg.evaluate("""async () => {
        const r = await fetch('/data/comercio.json'); const d = await r.json();
        return d.importadores.map(x => x.r); }""")
    candidato = next((r for r in solo_imp if r not in rucs_exp), None)
    if candidato:
        pg.evaluate("() => location.hash = '#empresa=" + candidato + "'")
        pg.wait_for_timeout(1500)
        resto = (pg.text_content("#empExpHist") or "").strip()
        if resto:
            print("  UNA EMPRESA SIN EXPORTACION ESTRENA BLOQUE EXPORTADOR")
            ok = False
        else:
            print("  quien no exporta no estrena bloque de embarques: ok")

    # ------------------------------- logistica · el terreno entra en la cuenta -
    # La hora de viaje salia de la clase de via y su superficie, y el terreno
    # nunca entraba. Lo que se comprueba no es que la columna exista, sino tres
    # reglas que el dato tiene que cumplir y que un cruce mal hecho romperia
    # sin que nada se vea raro:
    #
    #   El terreno solo puede sumar. Si en alguna region restara, se estaria
    #   cobrando la subida como bajada.
    #   Pesa mucho mas en la sierra que en la costa. Si diera parejo, la
    #   pendiente se estaria promediando donde no debe.
    #   La pantalla dice ambas cosas, porque la comparacion entre una region
    #   andina y una costeña que se hizo antes esta sesgada y callarlo deja al
    #   lector con la conclusion vieja.
    print("")
    print("logistica · la pendiente en la cuenta")
    pg.evaluate("() => location.hash = '#logistica'")
    pg.wait_for_selector("#tLogistica tbody tr td", timeout=25000)
    pg.wait_for_timeout(600)
    LG = pg.evaluate("""async () => {
        const r = await fetch('/data/logistica.json'); return await r.json(); }""")
    cabs = [h.strip() for h in pg.eval_on_selector_all(
        "#tLogistica thead th", "e => e.map(x => x.textContent)")]
    if "Del terreno" not in cabs or "Cota" not in cabs:
        print("  LA TABLA NO DECLARA NI LA COTA NI LO QUE APORTA EL TERRENO")
        ok = False
    else:
        print("  la tabla declara cota y aporte del terreno: ok")

    resta = [d["n"] for d in LG["deps"]
             if d.get("terr") is not None and d["terr"] < 0]
    if resta:
        print("  EL TERRENO RESTA HORAS EN %s: la subida se cobra como bajada"
              % resta[:3])
        ok = False
    else:
        print("  el terreno solo suma, en las %d regiones: ok" % len(LG["deps"]))

    alto = [d for d in LG["deps"] if d.get("alt", 0) >= 2000
            and d.get("pct_terr") is not None]
    bajo = [d for d in LG["deps"] if d.get("alt", 0) < 700
            and d.get("pct_terr") is not None]
    if alto and bajo:
        ma = sum(d["pct_terr"] for d in alto) / len(alto)
        mb = sum(d["pct_terr"] for d in bajo) / len(bajo)
        print("  sierra +%.1f%% · costa y llano +%.1f%%" % (ma, mb))
        # Dos condiciones y no una. Comparar solo sierra contra costa deja
        # pasar el caso en que el terreno no aporte en ninguna parte: cero
        # tampoco es mayor que cero, y la comprobacion daba «ok» sobre una
        # tabla que habia vuelto al reloj en llano.
        if ma < 5.0:
            print("  EL TERRENO NO APORTA NADA EN LA SIERRA (+%.1f%%): "
                  "la hora volvio a ser la del llano" % ma)
            ok = False
        elif ma < mb * 2:
            print("  EL TERRENO PESA IGUAL ARRIBA QUE ABAJO: "
                  "la pendiente se esta promediando donde no debe")
            ok = False
        else:
            print("  la pendiente pesa donde hay pendiente: ok")

    nota_log = " ".join((pg.text_content("#logNota") or "").split())
    if "pendiente" not in nota_log or "sierra" not in nota_log:
        print("  LA NOTA NO AVISA QUE LAS COMPARACIONES ANTERIORES ESTABAN "
              "SESGADAS")
        ok = False
    else:
        print("  la nota declara el sesgo de las cifras anteriores: ok")



    # -------------------------------------- productos · dos fuentes, un ojo --
    # Esta pantalla pone una al lado de la otra la hectárea de MIDAGRI y el
    # dólar embarcado de SUNAT. La mitad exportadora salía de la ventana de
    # diez semanas anualizada y ahora son cinco años medidos, lo que obliga a
    # comprobar tres cosas que un cruce mal hecho rompería sin que se note:
    #
    #   Que las cifras salgan del agregado y no de la ventana.
    #   Que el selector de periodo no las mueva, porque ya están medidas.
    #   Que el corte por departamento declare hasta dónde llega: el ubigeo del
    #   manifiesto se apaga en 2025 y extender el mapa a los años sin él sería
    #   dibujar la caída del registro y no la de la producción.
    print("")
    print("productos · la hectárea y el embarque")
    EX2 = json.load(io.open(os.path.join("data", "exportaciones",
                                         "mercado.json"), encoding="utf-8"))
    pg.evaluate("() => location.hash = '#productos'")
    pg.wait_for_selector("#tAduanas tbody tr td", timeout=25000)
    pg.wait_for_timeout(500)
    _cerr = [a for a in EX2["anios_con_dato"]
             if a < EX2["anio_en_curso"]][-1]
    _kpi = usd_a_num(pg.eval_on_selector("#proKpis > div:nth-child(3) .v",
                                         "e => e.textContent"))
    _esp = EX2["por_anio"][_cerr]["fob"]
    print("  agroexportación %s: pantalla %s · agregado %s"
          % (_cerr, f"{_kpi:,.0f}", f"{_esp:,.0f}"))
    if abs(_kpi - _esp) / _esp > 0.01:
        print("  EL FOB DE PRODUCTOS NO SALE DEL AGREGADO MEDIDO")
        ok = False
    else:
        print("  el KPI exportador es el año cerrado del agregado: ok")

    # La familia mayor de la tabla tiene que ser la del agregado: si la tabla
    # siguiera comiendo de la ventana de diez semanas, el orden sería otro.
    _prim = pg.eval_on_selector("#tProductos tbody tr:first-child td",
                                "e => e.textContent")
    if EX2["familias"][0]["n"][:12] not in _prim:
        print("  LA TABLA DE PRODUCTOS NO ESTA ORDENADA POR EL AGREGADO: «%s»"
              % _prim[:40])
        ok = False
    else:
        print("  la primera familia coincide con el agregado (%s): ok"
              % EX2["familias"][0]["n"][:24])

    _antes = pg.eval_on_selector("#proKpis > div:nth-child(3) .v",
                                 "e => e.textContent")
    pg.click('.periodo button:has-text("Medido")')
    pg.wait_for_timeout(600)
    _desp = pg.eval_on_selector("#proKpis > div:nth-child(3) .v",
                                "e => e.textContent")
    if _antes != _desp:
        print("  EL PERIODO ANUALIZA UNA CIFRA MEDIDA EN PRODUCTOS: %s -> %s"
              % (_antes, _desp))
        ok = False
    else:
        print("  el selector de periodo no toca lo ya medido: ok")

    # El universo arancelario se amplió, y la pantalla tiene que decirlo. Sin
    # ese aviso el total de agroexportación sube un 12% de una versión a la
    # otra y parece un error del sitio en vez de lo que es: dieciocho
    # capítulos que antes no se contaban. Lo esperado se lee del archivo en
    # disco y no de la página, para que una mutación que vacíe el bloque no
    # pueda engañar a la prueba con su propia versión de los datos.
    _uni = EX2.get("universo") or {}
    _nn = " ".join((pg.text_content("#proExpNota") or "").split())
    _bn = pg.eval_on_selector_all("#proExpDep .bar",
                                  "b => b.map(x => x.textContent)")
    if _uni.get("por_capitulo"):
        if "universo arancelario" not in _nn or "nuevo" not in _nn:
            print("  LA PANTALLA NO DECLARA LA AMPLIACION DEL UNIVERSO")
            ok = False
        else:
            print("  la nota declara los %d capítulos de la ampliación "
                  "y sus %d exportadores: ok"
                  % (len(_uni["por_capitulo"]),
                     _uni["exportadores_solo_ampliacion"]))
        _amp = set(_uni.get("familias_ampliacion") or [])
        _mal = [b for b in _bn
                if b.split("·")[0].strip() in _amp and "nuevo" not in b]
        if _mal:
            print("  UNA FAMILIA DE LA AMPLIACION SALE SIN MARCAR: «%s»"
                  % _mal[0][:40])
            ok = False
        else:
            print("  %d familias de la ampliación, ninguna sin marcar: ok"
                  % len(_amp))

    # El corte por departamento, con su año de corte declarado.
    pg.select_option("#fProDep", "Ica")
    pg.wait_for_timeout(800)
    _nd = " ".join((pg.text_content("#proExpNota") or "").split())
    _anter = EX2["departamentos"]["anios_usados"]
    if _anter[-1] not in _nd or "ubigeo" not in _nd:
        print("  EL CORTE POR DEPARTAMENTO NO DICE HASTA CUANDO LLEGA")
        ok = False
    else:
        print("  el corte por departamento declara su límite (%s) y su fuente: ok"
              % ", ".join(_anter))
    _bar = pg.eval_on_selector_all("#proExpDep .bar",
                                   "b => b.map(x => x.textContent)")
    if not _bar or "Uva" not in _bar[0]:
        print("  ICA NO SALE COMO UVA: el corte por departamento no es el medido")
        ok = False
    else:
        print("  Ica sale como uva, que es lo que embarca: ok")

    # ------------------------------------------- la cobertura, mes a mes ----
    # El sitio publica una cifra plana de cobertura y al lado la banda mensual.
    # Lo que hay que impedir es que la banda se pierda y quede solo el
    # promedio: es la cifra con la que se juzga la red, y ocho de los doce
    # meses están por debajo. Se comprueba contra el archivo en disco.
    print("")
    print("cobertura · la banda mensual junto a la cifra plana")
    CM = json.load(io.open(os.path.join("data", "cobertura_mes.json"),
                           encoding="utf-8"))
    pg.evaluate("() => location.hash = '#logistica'")
    pg.wait_for_selector("#cmCal button", timeout=25000)
    pg.wait_for_timeout(400)
    _cm = pg.eval_on_selector_all("#cmCal button .mono",
                                  "b => b.map(x => x.textContent)")
    print("  %d meses en pantalla · banda %.1f puntos · %d bajo el promedio"
          % (len(_cm), CM["brecha_puntos"], CM["meses_bajo_el_plano"]))
    if len(_cm) != 12 or len(set(_cm)) < 6:
        print("  LA BANDA MENSUAL NO SE MUESTRA O SALE PLANA")
        ok = False
    else:
        print("  los doce meses con su cobertura, y no son iguales: ok")
    _ci = " ".join((pg.text_content("#cmIntro") or "").split())
    if "%.1f%%" % CM["peor"]["cubierto_pct"] not in _ci.replace(",", "."):
        print("  LA PANTALLA NO DICE EL PEOR MES DE LA BANDA")
        ok = False
    else:
        print("  declara el peor mes (%s %.1f%%): ok"
              % (CM["peor"]["mes"], CM["peor"]["cubierto_pct"]))

    # ---------------------------------------------------------- canasta -----
    # La vista existe para contestar «en Piura, en marzo, qué llevo», y eso
    # depende de dos cosas que se comprueban aquí: que elegir región cambie de
    # verdad la mezcla de insumo —Huánuco es fitosanitario y San Martín
    # fertilizante, y si el filtro está muerto se ven iguales— y que la
    # pantalla diga que el mes es el de la siembra. Sin esa frase, un comercial
    # sale medio año tarde.
    print("")
    print("canasta · el insumo por región y mes")
    CAN = json.load(io.open(os.path.join("data", "canasta.json"),
                            encoding="utf-8"))
    pg.evaluate("() => location.hash = '#canasta'")
    pg.wait_for_selector("#canInsumos .bar", timeout=25000)
    pg.wait_for_timeout(400)
    _txt = " ".join((pg.text_content("#canIntro") or "").split())
    if "siembra" not in _txt.lower():
        print("  LA PANTALLA NO DICE QUE EL MES ES EL DE LA SIEMBRA")
        ok = False
    else:
        print("  declara que el mes es el de la siembra: ok")

    def _mezcla():
        return pg.eval_on_selector_all(
            "#canInsumos .bar .bn", "b => b.map(x => x.textContent)")

    _pais = _mezcla()
    pg.select_option("#fCanDep", "Huánuco")
    pg.wait_for_timeout(500)
    _hua = _mezcla()
    pg.select_option("#fCanDep", "San Martín")
    pg.wait_for_timeout(500)
    _sm = _mezcla()
    print("  país %s · Huánuco %s · San Martín %s"
          % (_pais[0] if _pais else "—", _hua[0] if _hua else "—",
             _sm[0] if _sm else "—"))
    if not _hua or not _sm or _hua == _sm:
        print("  EL FILTRO DE REGION NO CAMBIA LA MEZCLA DE INSUMO")
        ok = False
    else:
        print("  la mezcla cambia con la región: ok")

    # Y que el mes filtre de verdad. Se comparan dos meses entre sí y no el mes
    # contra el año: el año trae una fila más y la comparación pasaría por la
    # longitud aunque el contenido fuera el mismo, que es exactamente lo que
    # deja pasar una prueba vacua.
    def _mes(m):
        pg.click('#canCal button[data-m="%s"]' % m)
        pg.wait_for_timeout(450)
        return pg.eval_on_selector_all(
            "#canCultivos .bar", "b => b.map(x => x.textContent)")

    _oct, _abr = _mes("Oct"), _mes("Abr")
    if not _oct or _oct == _abr:
        print("  DOS MESES DISTINTOS MUESTRAN EL MISMO CORTE POR CULTIVO")
        ok = False
    else:
        print("  octubre y abril siembran cosas distintas: ok")

    # El calendario tampoco puede salir plano: si los doce meses pesan igual,
    # la temporada de compra desaparece de la pantalla.
    _pcts = pg.eval_on_selector_all(
        "#canCal button .mono", "b => b.map(x => x.textContent)")
    if len(set(_pcts)) <= 2:
        print("  EL CALENDARIO SALE PLANO: no hay temporada que mostrar")
        ok = False
    else:
        print("  el calendario tiene temporada (%d valores distintos): ok"
              % len(set(_pcts)))

    # ------------------------------------------------------- decisiones -----
    # El módulo existe para que la alternativa descartada no se pierda. Si una
    # decisión se muestra sin la cifra contra la que se decidió, vuelve a ser
    # una lámina de conclusiones: se comprueba que cada tarjeta traiga las tres
    # partes, y que las cifras sean las del archivo y no un texto escrito.
    print("")
    print("decisiones · la alternativa que se descartó")
    DEC = json.load(io.open(os.path.join("data", "decisiones.json"),
                            encoding="utf-8"))
    pg.evaluate("() => location.hash = '#decisiones'")
    pg.wait_for_selector("#decLista .card .b p", timeout=25000)
    pg.wait_for_timeout(400)
    _txt = " ".join((pg.text_content("#decLista") or "").split())
    _faltan = [d["id"] for d in DEC["decisiones"]
               if d["pregunta"][:34] not in _txt]
    if _faltan:
        print("  FALTAN DECISIONES EN LA PANTALLA: %s" % ", ".join(_faltan))
        ok = False
    else:
        print("  las %d decisiones están en la pantalla: ok"
              % len(DEC["decisiones"]))
    _sin_alt = [d["id"] for d in DEC["decisiones"]
                if d["alternativa"][:30] not in _txt]
    if _sin_alt:
        print("  UNA DECISION SE MUESTRA SIN SU ALTERNATIVA: %s"
              % ", ".join(_sin_alt))
        ok = False
    else:
        print("  cada decisión trae la alternativa que se descartó: ok")
    if "Qué la daría vuelta" not in _txt:
        print("  LA PANTALLA NO DICE QUE DARIA VUELTA CADA DECISION")
        ok = False
    else:
        print("  cada decisión trae su bisagra: ok")

    # ---------------------------------------------- la red de canal ---------
    # El almacen no le vende al agricultor: en el mayor territorio hay 9,114
    # clientes y 133 empresas formales. Esta capa dice quien si, y descansa en
    # tres cifras que es facil confundir —lo que cubren los elegidos, lo que
    # cubre el canal entero, y lo que no cubre nadie—. Confundirlas cambia la
    # conclusion, asi que se comprueba que la pantalla muestre las tres y que
    # sumen lo que tienen que sumar.
    print("")
    print("la red de canal")
    CAN = json.load(io.open(os.path.join("data", "canal.json"),
                            encoding="utf-8"))
    pg.evaluate("() => location.hash = '#expansion'")
    pg.wait_for_selector("#tCanal tbody tr td", timeout=25000)
    pg.wait_for_timeout(400)
    print("  %s clientes · %.1f%% con canal a %d min · %.1f%% sin ninguno"
          % (f"{CAN['clientes']:,}", CAN["con_canal"]["pct"],
             CAN["radio_base_min"], CAN["sin_candidato"]["pct"]))
    # Tres cifras encajadas: quien tiene comercio cerca es un subconjunto de
    # quien tiene algun sitio donde abrir, y lo que sobra de eso es el hueco.
    # Si el orden se rompiera, se estarian contando pueblos como si ya fueran
    # tiendas —que es la confusion que el padron del INEI vino a deshacer—.
    if not (CAN["con_canal"]["pct"] <= CAN["con_sitio"]["pct"]):
        print("  MAS CLIENTES CON TIENDA QUE CON SITIO DONDE ABRIR: "
              "un pueblo se esta contando como comercio")
        ok = False
    elif abs(CAN["con_sitio"]["pct"] + CAN["sin_candidato"]["pct"] - 100) > 0.3:
        print("  CON SITIO Y SIN NADA NO SUMAN CIEN (%.1f)"
              % (CAN["con_sitio"]["pct"] + CAN["sin_candidato"]["pct"]))
        ok = False
    else:
        print("  comercio (%.1f%%) cabe en sitio donde abrir (%.1f%%) y el "
              "resto es el hueco (%.1f%%): ok"
              % (CAN["con_canal"]["pct"], CAN["con_sitio"]["pct"],
                 CAN["sin_candidato"]["pct"]))

    caja = " ".join((pg.text_content("#redCanal") or "").split())
    if str(CAN["radio_base_min"]) not in caja:
        print("  LA PANTALLA NO DECLARA EL RADIO DEL CANAL")
        ok = False
    elif "techo" not in caja or "OpenStreetMap" not in caja:
        print("  NO SE DECLARA QUE LA COBERTURA DE OSM ES UN TECHO")
        ok = False
    else:
        print("  declara el radio y la salvedad de la fuente: ok")

    # La cadena completa no puede superar a una de sus mitades: si el numero
    # de clientes con tienda cerca Y centro dentro de la promesa fuera mayor
    # que el de clientes con tienda cerca, el cruce estaria sumando en vez de
    # intersecando.
    if CAN["cadena_completa"]["pct"] > CAN["con_canal"]["pct"]:
        print("  LA CADENA COMPLETA SUPERA A LA COBERTURA DE TIENDAS: "
              "el cruce con los centros suma en vez de intersecar")
        ok = False
    else:
        print("  la cadena completa (%.1f%%) cabe dentro de la cobertura de "
              "tiendas (%.1f%%): ok"
              % (CAN["cadena_completa"]["pct"], CAN["con_canal"]["pct"]))

    # Y los clientes detras de un centro son la union de los que alcanzan sus
    # puntos: sumando alcances que se solapan, un solo centro salia con mas
    # clientes que el pais entero.
    peor = max(CAN["reparto"], key=lambda r: r["clientes"])
    if peor["clientes"] > CAN["clientes"]:
        print("  UN CENTRO TIENE MAS CLIENTES QUE EL PAIS (%s): se estan "
              "sumando alcances solapados" % peor["hub"])
        ok = False
    else:
        print("  el centro de mayor alcance (%s, %s clientes) cabe en el "
              "padron: ok" % (peor["hub"], f"{peor['clientes']:,}"))

    # El canal medido en plata. Dos invariantes y una salvedad:
    #
    #   El mercado exclusivo no puede pasar del mercado del pais. Si lo
    #   pasara, se estarian sumando alcances que se pisan —dos tiendas de la
    #   misma calle llegan a la misma gente— que es el error que el reparto
    #   por cercania existe para evitar.
    #   La curva de pisos tiene que caer: cuanto mas alta la vara, menos
    #   puntos la superan.
    #   Y la pantalla tiene que decir que ese margen es lo que capturaria el
    #   proyecto y no lo que vende la tienda, porque leido al reves convierte
    #   una lista de socios en una lista de negocios ajenos.
    V = CAN["viabilidad"]
    print("  %s de %s puntos con mercado propio · US$ %.1f MM repartidos"
          % (f"{V['puntos_con_mercado']:,}", f"{V['puntos_que_venden']:,}",
             V["sam_exclusivo_mm"]))
    if V["sam_exclusivo_mm"] * 1e6 > 1.01 * 502.7e6:
        print("  EL MERCADO EXCLUSIVO SUPERA AL DEL PAIS: los alcances se "
              "estan sumando en vez de repartirse")
        ok = False
    else:
        print("  el mercado repartido cabe en el del pais: ok")
    _p = [c["puntos"] for c in V["curva"]]
    if _p != sorted(_p, reverse=True):
        print("  LA CURVA DE VIABILIDAD NO CAE AL SUBIR LA VARA: %s" % _p)
        ok = False
    else:
        print("  cuanto mas alta la vara, menos puntos la pasan (%s): ok"
              % " > ".join(str(x) for x in _p))
    if "no lo que vende la tienda" not in caja:
        print("  LA PANTALLA NO ACLARA DE QUIEN ES ESE MARGEN")
        ok = False
    else:
        print("  aclara que el margen es del proyecto y no del comerciante: ok")

    # Un punto de captacion no vale lo mismo si ya existe que si hay que
    # abrirlo. La tabla tiene que decir cual es cual.
    clases = set(pg.eval_on_selector_all(
        "#tCanal tbody tr td:nth-child(3)",
        "f => f.map(x => x.textContent.trim())"))
    if not clases or clases == {""}:
        print("  LA TABLA DE CAPTACION NO DICE QUE ES CADA PUNTO")
        ok = False
    else:
        print("  distingue de que clase es cada punto (%s): ok"
              % ", ".join(sorted(clases)))

    # El orden de apertura es por clientes nuevos y tiene que ser decreciente:
    # si no lo fuera, no seria un orden de prioridad sino una lista.
    nuevos = [usd_a_num(t.replace(",", "")) for t in pg.eval_on_selector_all(
        "#tCanal tbody tr td:nth-child(4)", "f => f.map(x => x.textContent)")]
    if nuevos != sorted(nuevos, reverse=True):
        print("  EL ORDEN DE CAPTACION NO ESTA POR CLIENTES NUEVOS")
        ok = False
    else:
        print("  el orden de captacion cae con cada punto: ok")

    # --------------------------------- los pisos, y la banda de cada producto -
    # El bloque existe para una decision concreta —donde poner inventario— y
    # descansa en que los dos negocios no viven a la misma altura. Se comprueba
    # contra el dato, no contra si mismo.
    #
    # Y una prueba que vale por todo el cruce: el cafe. Su banda medida tiene
    # que caer en ladera. Si el join entre el embarque y la cota se rompiera,
    # o si el ubigeo del manifiesto apuntara a la oficina y no al fundo, el
    # cafe apareceria al nivel del mar —donde estan las oficinas de Lima— y
    # ninguna comprobacion de forma lo notaria.
    print("")
    print("los pisos ecologicos")
    AL = pg.evaluate("""async () => {
        const r = await fetch('/data/altitud.json'); return await r.json(); }""")
    barras_sam = len(pg.query_selector_all("#altSam .bar"))
    filas_b = len(pg.query_selector_all("#tAltBanda tbody tr"))
    print("  %d pisos con mercado · %d productos con banda medida"
          % (barras_sam, filas_b))
    if barras_sam < 5 or filas_b < 10:
        print("  EL BLOQUE DE PISOS NO CARGA")
        ok = False

    cafe = [b for b in AL["bandas"] if b["familia"].lower().startswith("caf")]
    if not cafe:
        print("  NO HAY BANDA MEDIDA PARA EL CAFE")
        ok = False
    elif not (900 <= cafe[0]["p50"] <= 2200):
        print("  EL CAFE SALE A %d m: el cruce entre el embarque y la cota "
              "esta roto" % cafe[0]["p50"])
        ok = False
    else:
        print("  el cafe cae en su banda conocida (%d m de mediana): ok"
              % cafe[0]["p50"])

    # El dinero exportador y los clientes no estan en el mismo piso: es el
    # hallazgo del bloque y tiene que seguir siendo cierto en el dato.
    sam = {r["piso"]: r for r in AL["sectores"]["por_piso"]}
    fob = {r["piso"]: r for r in AL["distritos"]["por_piso"]}
    sierra = sum(sam[p]["clientes"] for p in ("quechua", "suni", "puna")
                 if p in sam)
    todos = sum(r["clientes"] for r in AL["sectores"]["por_piso"])
    print("  chala: %.1f%% del FOB · la sierra: %.0f%% de los clientes"
          % (fob.get("chala", {}).get("pct", 0), 100 * sierra / todos))
    nota_alt = " ".join((pg.text_content("#altNota") or "").split())
    if str(int(round(100 * sierra / todos))) not in nota_alt:
        print("  LA NOTA NO DICE DONDE ESTA EL PADRON DE CLIENTES")
        ok = False
    else:
        print("  la nota separa los dos negocios: ok")
    if "error mediano" not in nota_alt and "no para afirmar la cota" not in nota_alt:
        print("  EL BLOQUE NO DECLARA EL ERROR DE LA COTA")
        ok = False
    else:
        print("  declara con cuanto error se muestreo la cota: ok")

    # ------------------------------------------- la red elegida y su promesa -
    # La red no es el resultado del algoritmo: son los seis de cobertura máxima
    # más Huamachuco, con promesa de cuatro horas. Es una decisión comercial y
    # la pantalla tiene que decirlo, porque con otra vara el ranking de
    # ciudades cambia entero —Huamachuco es el candidato 14 a dos horas y el
    # primero del país a cuatro— y quien lea la tabla sin la vara a la vista
    # sacará la conclusión contraria.
    print("")
    print("la red elegida")
    pg.evaluate("() => location.hash = '#expansion'")
    pg.wait_for_selector("#tRed tbody tr td", timeout=25000)
    pg.wait_for_timeout(500)
    # Se lee del disco y no con un `fetch` desde la pagina. La diferencia no
    # es de estilo: una comprobacion que pide el dato por el mismo camino que
    # la pagina compara la pantalla contra si misma, y cualquier defecto que
    # toque ese camino la deja pasar. Aqui el contraste es contra el archivo
    # publicado, que es lo que un tercero descargaria.
    RED = json.load(io.open(os.path.join("data", "red.json"), encoding="utf-8"))
    filas = pg.eval_on_selector_all(
        "#tRed tbody tr", "f => f.map(r => r.textContent)")
    # La promesa es un criterio y no un numero: cuatro horas en costa y seis
    # en sierra y selva. Se comprueba que la pantalla muestre las dos, porque
    # ensenar solo una haria parecer que media red incumple.
    horas = sorted(set(RED["promesa_h"].values()))
    print("  %d centros · promesa de %s · cubre %.1f%%"
          % (len(RED["centros"]),
             " y ".join("%.0f h" % h for h in horas),
             RED["sam_cubierto_promesa_pct"]))
    if len(filas) != len(RED["centros"]):
        print("  LA TABLA DE LA RED NO LISTA LOS %d CENTROS"
              % len(RED["centros"]))
        ok = False
    else:
        print("  la tabla lista los %d centros: ok" % len(filas))

    # Cuál entró por decisión y cuál por cobertura tiene que estar dicho: son
    # dos clases de centro que no se defienden igual ante un tercero.
    por_dec = [c for c in RED["centros"] if c["por"] == "decision"]
    marcados = [f for f in filas if "decisión" in f]
    if len(por_dec) != len(marcados):
        print("  LA TABLA NO DISTINGUE LOS CENTROS PUESTOS POR DECISION")
        ok = False
    else:
        print("  distingue los %d puestos por decisión (%s): ok"
              % (len(por_dec), ", ".join(c["hub"] for c in por_dec)))

    nota_red = " ".join((pg.text_content("#redElegida") or "").split())
    falta = [h for h in horas if ("%.0f h" % h) not in nota_red]
    if falta or "decisión" not in nota_red:
        print("  LA PANTALLA NO DECLARA LA PROMESA DE SERVICIO ENTERA "
              "(falta %s)" % falta)
        ok = False
    else:
        print("  declara las dos varas de la promesa y que es una decisión: ok")

    # La cobertura tiene que crecer con la vara. Si la de dos horas fuera mayor
    # que la de la promesa, el cruce estaría invertido.
    if RED["sam_cubierto_2h_pct"] > RED["sam_cubierto_promesa_pct"]:
        print("  LA COBERTURA A DOS HORAS SUPERA A LA DE CUATRO: vara invertida")
        ok = False
    else:
        print("  la cobertura crece con la vara (%.1f%% -> %.1f%%): ok"
              % (RED["sam_cubierto_2h_pct"], RED["sam_cubierto_promesa_pct"]))

    # Y el territorio que motivó el séptimo centro: Sánchez Carrión y Pataz es
    # el mayor del país y estaba a 6.5 h de Chiclayo. Si vuelve a quedar lejos,
    # el centro no está haciendo lo que se decidió que hiciera.
    TE = pg.evaluate("""async () => {
        const r = await fetch('/data/territorios.json'); return await r.json(); }""")
    mayor = sorted(TE, key=lambda t: -t.get("sam", 0))[0]
    print("  territorio mayor: %s · %s · centro %s · %d de %d empresas "
          "dentro de la promesa"
          % (mayor.get("dep", ""), str(mayor.get("prov", ""))[:24],
             mayor.get("hub", "—"), mayor.get("dpr", 0), mayor.get("emp", 0)))
    if mayor.get("hub") != "Huamachuco":
        print("  EL MAYOR TERRITORIO NO RESPONDE AL CENTRO QUE SE PUSO PARA EL")
        ok = False
    elif not mayor.get("dpr", 0) > mayor.get("d2h", 0):
        print("  EL CENTRO NUEVO NO ALCANZA MAS CARTERA EN LA PROMESA QUE A 2 H")
        ok = False
    else:
        print("  el mayor territorio responde a Huamachuco y su cartera "
              "alcanzada crece de %d a %d: ok" % (mayor["d2h"], mayor["dpr"]))


    # ------------------------------------------------------- acopio ------
    # El bloque que sitúa la carga donde se produce. Lo que se comprueba no es
    # que dibuje, sino tres reglas que el dato tiene que cumplir y que un
    # error de cruce rompería sin que se note:
    #
    #   El alcance crece con el radio. Si a dos horas se alcanzara más que a
    #   seis, el cruce con las horas al centro estaría invertido.
    #   La carga sin centro se declara. Es el hueco del análisis y callarlo lo
    #   convierte en un cero.
    #   Los productos sin lista de SENASA dicen que su partida agrupa otras
    #   cosas. Decir «espárrago» a secas afina más de lo que el dato aguanta.
    print("")
    print("acopio · la carga puesta donde se produce")
    AC = pg.evaluate("""async () => {
        const r = await fetch('/data/acopio.json'); return await r.json(); }""")
    filas_hub = pg.eval_on_selector_all(
        "#tAcopioHub tbody tr",
        "f => f.map(t => [...t.querySelectorAll('td')].map(x => x.textContent))")
    print("  %d centros, %d distritos, %d territorios"
          % (len(filas_hub), len(pg.query_selector_all("#tAcopioDist tbody tr")),
             len(pg.query_selector_all("#tAcopioTer tbody tr"))))
    if not filas_hub:
        print("  EL BLOQUE DE ACOPIO NO CARGA")
        ok = False
    else:
        malos = []
        for f in filas_hub:
            v2, v4, v6 = (usd_a_num(f[1]), usd_a_num(f[2]), usd_a_num(f[3]))
            if not (v2 <= v4 <= v6):
                malos.append((f[0].splitlines()[0],
                              round(v2), round(v4), round(v6)))
        if malos:
            print("  EL ALCANCE NO CRECE CON EL RADIO: %s" % malos[:2])
            ok = False
        else:
            print("  el alcance de cada centro crece con el radio: ok")
        # y contra el dato, no contra sí mismo
        mayor = max(AC["hubs"], key=lambda h: h["fob_2h_mm"])
        visto = usd_a_num(filas_hub[0][1])
        if abs(visto - mayor["fob_2h_mm"] * 1e6) / (mayor["fob_2h_mm"] * 1e6) > 0.02:
            print("  LA TABLA DE CENTROS NO CUADRA CON EL AGREGADO")
            ok = False
        else:
            print("  el alcance del primer centro sale del agregado: ok")

    nota = pg.text_content("#expAcopioNota") or ""
    if "fuera de alcance" not in nota or str(AC["sin_centro"]["distritos"]) not in nota:
        print("  NO SE DECLARA LA CARGA QUE NINGUN CENTRO ALCANZA")
        ok = False
    else:
        print("  declara los %d distritos sin centro: ok"
              % AC["sin_centro"]["distritos"])

    sl = AC.get("sin_lista_senasa") or {}
    txt_sl = pg.text_content("#expSinLista") or ""
    if sl:
        faltan = [k for k in sl if k not in txt_sl]
        sin_salvedad = [k for k, v in sl.items()
                        if v["salvedad"][:25] not in txt_sl]
        if faltan or sin_salvedad:
            print("  LOS PRODUCTOS SIN LISTA NO DECLARAN SU SALVEDAD: %s"
                  % (faltan or sin_salvedad))
            ok = False
        else:
            print("  %s: situados y con su salvedad a la vista: ok"
                  % ", ".join(sl))

    cob = (AC.get("senasa_cobertura") or {}).get("productos", [])
    txt_s = pg.text_content("#expSenasa") or ""
    if cob and any(c not in txt_s for c in cob):
        print("  LA NOTA DE SENASA NO NOMBRA TODOS LOS PRODUCTOS QUE CUBRE")
        ok = False
    elif cob:
        print("  la nota nombra los %d productos certificados: ok" % len(cob))

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
