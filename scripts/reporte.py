# -*- coding: utf-8 -*-
"""Assemble the AgroJuntos market report and render it to PDF.

Structure: cover, contents, three numbered parts each opened by a divider, and
a regional atlas with one fiche per department. Pages are explicit A4 blocks;
images embed as data URIs because Chrome will not read local files from a page
it prints.
"""
import base64
import os
import re
import subprocess
import unicodedata
from datetime import date

import pandas as pd

from estilo import CSS, FONTS

OUT_HTML = "out/reporte_agrojuntos.html"
OUT_PDF = "out/Reporte de mercado - AgroJuntos.pdf"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
TC = 3.75

mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
cos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
som = pd.read_csv("out/som_escenarios.csv", encoding="utf-8-sig")
ven = pd.read_csv("out/ventas_doc.csv", encoding="utf-8-sig")
cli = pd.read_csv("out/ventas_cliente.csv", encoding="utf-8-sig")
perfil = pd.read_pickle("out/perfil_dep.pkl").sort_values("rank")
est_n = pd.read_csv("out/estacionalidad_nacional.csv", encoding="utf-8-sig")
est_r = pd.read_csv("out/estacionalidad_region.csv", encoding="utf-8-sig")
v3 = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
try:
    pros = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
except FileNotFoundError:
    pros = pd.DataFrame(columns=["nombre", "dep", "tipo", "ha", "lat", "lon"])

TAM, SAM = mod.tam_usd.sum(), mod.sam_usd.sum()
CLI = mod.clientes_sam.sum()
HA_COS = mod.ha_cosechada.sum()
FOCO = mod.head(8)
MESES = 13.1


def nf(v, d=0):
    return f"{v:,.{d}f}"


def usd(v):
    return f"US$ {nf(v/1e6)} MM" if v >= 1e6 else f"US$ {nf(v)}"


def cap(s):
    s = " ".join(w.capitalize() for w in str(s).split())
    for a, b in (("De ", "de "), ("Del ", "del "), ("La ", "la "), ("Y ", "y ")):
        s = s.replace(" " + a, " " + b)
    return s


def img(path, cls="fig"):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return f'<img class="{cls}" src="data:image/png;base64,{b64}" alt="">'


def fig(name, cls="fig"):
    return img(f"out/fig_{name}.png", cls)


def table(rows, cols, aligns=None, foot=None, cls=""):
    aligns = aligns or ["l"] + ["r"] * (len(cols) - 1)
    th = "".join(f'<th class="{a}">{c}</th>' for c, a in zip(cols, aligns))
    body = "".join("<tr>" + "".join(
        f'<td class="{a}">{v}</td>' for v, a in zip(r, aligns)) + "</tr>"
        for r in rows)
    tf = ""
    if foot:
        tf = "<tfoot><tr>" + "".join(
            f'<td class="{a}">{v}</td>' for v, a in zip(foot, aligns)) + "</tr></tfoot>"
    return (f'<table class="{cls}"><thead><tr>{th}</tr></thead>'
            f"<tbody>{body}</tbody>{tf}</table>")


MES_ES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo",
          6: "junio", 7: "julio", 8: "agosto", 9: "setiembre", 10: "octubre",
          11: "noviembre", 12: "diciembre"}
_h = date.today()
HOY = f"{_h.day} de {MES_ES[_h.month]} de {_h.year}"

PAGES = []
_pg = {"n": 1}


def page(body, seccion="", n=True):
    """One A4 page with running head and folio."""
    _pg["n"] += 1
    p = _pg["n"]
    rh = (f'<div class="rh"><span>AgroJuntos · Mercado de insumos agrícolas · Perú</span>'
          f'<span class="sec">{seccion}</span></div>') if seccion else ""
    ft = (f'<div class="foot"><span>Documento de trabajo · uso interno</span>'
          f'<span class="pg">{p:02d}</span></div>') if n else ""
    PAGES.append(f'<section class="page">{rh}{body}{ft}</section>')
    return p


INDICE = {}


def divider(num, titulo, texto, indice):
    _pg["n"] += 1
    INDICE[num] = _pg["n"]
    items = "".join(f"<span>{i}</span>" for i in indice)
    PAGES.append(f"""
<section class="divider">
  <div class="n">{num}</div>
  <h2>{titulo}</h2>
  <p>{texto}</p>
  <div class="idx">{items}</div>
</section>""")


# ============================================================== 01 PORTADA ==
PAGES.append(f"""
<section class="cover">
  <div class="bar"></div>
  <div class="brandline"><span>AgroJuntos</span><span>Inteligencia de mercado</span></div>
  <h1>Dónde está el <em>cliente agrícola</em> del Perú</h1>
  <p class="lede">Dimensionamiento del mercado de insumos agrícolas y priorización
     del territorio comercial, sobre 7,036 sectores estadísticos georreferenciados,
     145 cultivos y el censo agropecuario nacional.</p>
  <div class="hero">{fig("hero", "")}</div>
  <div class="cstats">
    <div><span class="v">{usd(TAM)}</span><span class="l">Mercado nacional de
      fertilizante y fitosanitario</span></div>
    <div><span class="v">{usd(SAM)}</span><span class="l">Mercado atendible por un
      canal digital con crédito</span></div>
    <div><span class="v">{nf(CLI)}</span><span class="l">Productores que hoy
      compran insumos</span></div>
    <div><span class="v">{nf(HA_COS/1e6,2)} M ha</span><span class="l">Superficie
      cosechada en la campaña 2023</span></div>
  </div>
  <div class="foot2">
    <div><b>Preparado para</b>Comité de inversión</div>
    <div><b>Fecha</b>{HOY}</div>
    <div><b>Fuentes primarias</b>MIDAGRI · INEI · SUNAT</div>
    <div><b>Moneda</b>US$ · S/{TC} por dólar</div>
  </div>
</section>""")
_pg["n"] = 1

# ============================================================== 02 CONTENIDO =
page(f"""
  <span class="kicker">Contenido</span>
  <h2 class="title">Qué contiene <em>este documento</em></h2>
  <p class="deck">El informe responde tres preguntas en orden: cuánto vale el mercado,
     quién es cliente y dónde empezar. La última parte es un atlas con una ficha por
     cada una de las 24 regiones agrícolas del país.</p>

  <ul class="toc">
    <li><span class="n">I</span><span class="t">El tamaño del mercado</span>
        <span class="d"></span><span class="p">@@PGI@@</span>
        <span class="desc">La base territorial, el gasto real por hectárea y por qué
        la superficie agrícola no es el mercado.</span></li>
    <li><span class="n">II</span><span class="t">Quién es cliente</span>
        <span class="d"></span><span class="p">@@PGII@@</span>
        <span class="desc">El embudo de 2.26 millones de productores a
        {nf(CLI)} compradores reales, y la economía unitaria observada.</span></li>
    <li><span class="n">III</span><span class="t">Cuándo y cómo llegar</span>
        <span class="d"></span><span class="p">@@PGIII@@</span>
        <span class="desc">El calendario de compra de cada región, el costo de
        servirla y el puerto por el que sale su producción.</span></li>
    <li><span class="n">IV</span><span class="t">Dónde empezar</span>
        <span class="d"></span><span class="p">@@PGIV@@</span>
        <span class="desc">Priorización de las 24 regiones, escenarios de captura y
        la capa de prospección con nombre propio.</span></li>
    <li><span class="n">V</span><span class="t">Atlas regional</span>
        <span class="d"></span><span class="p">@@PGV@@</span>
        <span class="desc">Ficha por región: mapa de sectores, métricas de mercado,
        mezcla de cultivos y lectura comercial.</span></li>
    <li><span class="n">VI</span><span class="t">Metodología y fuentes</span>
        <span class="d"></span><span class="p">@@PGVI@@</span>
        <span class="desc">Cadena de cálculo, contraste con aduanas y limitaciones
        declaradas.</span></li>
  </ul>

  <div class="note brass">
    <span class="h">Nota sobre el estatus de las cifras</span>
    <p>Ninguna de las cifras de mercado de este informe es una estadística oficial.
    Son estimaciones construidas sobre fuentes oficiales, con supuestos declarados en
    la sección V y contrastadas contra datos de importación de aduanas. Los datos
    territoriales —superficie, sectores, cultivos, productores— sí son oficiales y se
    citan uno a uno.</p>
  </div>
""", "Contenido")

# ============================================================ 03 RESUMEN ====
page(f"""
  <span class="kicker">Resumen ejecutivo</span>
  <h2 class="title">Un mercado de {usd(TAM)} donde <em>siete de cada cien</em>
     productores son cliente</h2>
  <p class="deck">El Perú tiene 2.26 millones de productores agropecuarios. La
     inmensa mayoría opera por debajo de la escala que hace posible una venta
     recurrente de insumos. El mercado real es más pequeño, mucho más concentrado
     y —por eso mismo— alcanzable.</p>

  <div class="kpis">
    <div><span class="v">{usd(TAM)}</span><span class="l">TAM<br>mercado nacional</span></div>
    <div><span class="v">{usd(SAM)}</span><span class="l">SAM<br>{100*SAM/TAM:.0f}% del TAM</span></div>
    <div><span class="v">{nf(CLI)}</span><span class="l">clientes<br>que ya compran insumos</span></div>
    <div><span class="v">US$ {nf(SAM/CLI)}</span><span class="l">gasto anual<br>por cliente</span></div>
  </div>

  <h3 class="rule">Cinco conclusiones</h3>
  <ul class="num">
    <li><b>La tierra no es el mercado.</b> De 11.6 millones de hectáreas agrícolas,
        solo <b class="hl">{nf(HA_COS/1e6,2)} millones</b> pasaron por una campaña en
        2023. La tierra en descanso no demanda insumos, y usarla para dimensionar
        infla el mercado casi tres veces.</li>
    <li><b>Tener tierra no hace cliente.</b> {nf(cen.ua_objetivo_5_mas.sum())}
        productores superan las cinco hectáreas, pero solo <b class="hl">{nf(CLI)}</b>
        declaran aplicar fertilizante o pesticida. Los demás exigen convertir a un no
        usuario, que es un costo de adquisición distinto.</li>
    <li><b>Existe un segmento que ya compra como AgroJuntos vende.</b>
        <b class="hl">{nf(emb.compran_a_credito.sum())} productores</b> usan crédito
        para adquirir insumos. No hay que enseñarles el modelo, solo ofrecer mejor
        precio y servicio.</li>
    <li><b>El mercado está concentrado.</b> Ocho regiones reúnen el
        <b class="hl">{FOCO.pct_acum.iat[-1]:.0f}%</b> del mercado atendible. No hace
        falta cobertura nacional para capturar la mayor parte del valor.</li>
    <li><b>La tracción existe pero es mínima.</b> {len(cli)} clientes facturados y
        recompra cada <b class="hl">45 días</b> en el cliente establecido. El
        comportamiento de compra funciona; lo que falta es escala.</li>
  </ul>

  <h3 class="rule">Las ocho regiones prioritarias</h3>
  {table([[int(r["rank"]), cap(r["dep"]), nf(r["ha_cosechada"]),
           "US$ "+nf(r["gasto_ha"]), nf(r["clientes_sam"]), usd(r["sam_usd"]),
           f'{r["pct_acum"]:.0f}%'] for _, r in FOCO.iterrows()],
         ["#", "Región", "Ha cosechadas", "Gasto/ha", "Clientes", "SAM anual",
          "% acumulado"], ["r","l","r","r","r","r","r"])}
""", "Resumen ejecutivo")


# ======================================================== PARTE I ===========
divider("I", "El tamaño <em>del mercado</em>",
        "Cuánto vale realmente el mercado peruano de insumos agrícolas, medido "
        "sobre la tierra que efectivamente produce y a los precios que el "
        "productor paga en campo.",
        ["La base territorial", "El gasto por hectárea", "Contraste con aduanas"])

page(f"""
  <span class="kicker">Parte I · La base territorial</span>
  <h2 class="title">Dónde está la tierra <em>que produce</em></h2>

  <div class="mapl" style="margin-top:14px">
    <figure>
      {fig("superficie")}
      <figcaption><b>Superficie agrícola por sector estadístico.</b> Cada círculo es
      una de las 7,036 unidades con que el MIDAGRI organiza el trabajo de campo; el
      área es proporcional a sus hectáreas agrícolas y el color indica la región
      natural. Fuente: MIDAGRI, Padrón Nacional de Sectores Estadísticos 2024.</figcaption>
    </figure>
    <div>
      <p>El modelo trabaja a nivel de <b>sector estadístico</b> y no de distrito. Un
      distrito andino puede mezclar un valle irrigado con una puna sin agricultura;
      el sector separa uno de otro, y por eso permite ubicar demanda donde realmente
      está.</p>

      <p>La distribución encierra tres lógicas comerciales distintas. La
      <b>costa</b> concentra pocas hectáreas de altísimo valor unitario, en unidades
      grandes y formales. La <b>sierra</b> reúne la mayor superficie y el mayor número
      de productores, pero muy fragmentada. La <b>selva</b> tiene unidades grandes con
      cultivos de bajo gasto por hectárea: café, cacao y palma.</p>

      <h4 class="lab">Superficie por región natural</h4>
      {table([["Costa", nf(1298), nf(1654377), "14%"],
              ["Sierra", nf(4507), nf(5172835), "44%"],
              ["Selva alta", nf(641), nf(1741598), "15%"],
              ["Selva baja", nf(597), nf(3080907), "26%"]],
             ["Región natural", "Sectores", "Ha agrícolas", "% del país"],
             ["l","r","r","r"], cls="tight")}

      <div class="note">
        <span class="h">La distinción que cambia el número</span>
        <p>El país tiene <b>11.6 millones</b> de hectáreas agrícolas, pero solo
        <b>{nf(HA_COS/1e6,2)} millones</b> se cosecharon en 2023. La diferencia es
        tierra en descanso, en instalación o perdida por campaña. Solo la superficie
        efectivamente cosechada genera demanda de insumos en el año, y es sobre ella
        que se construye el TAM.</p>
      </div>
    </div>
  </div>
""", "Parte I · La base territorial")

page(f"""
  <span class="kicker">Parte I · El gasto por hectárea</span>
  <h2 class="title">Lo que se gasta depende <em>de lo que se siembra</em></h2>

  <div class="mapr" style="margin-top:14px">
    <div>
      <p>El gasto en insumos no es un promedio nacional: varía por un factor de tres
      entre regiones y la causa es la mezcla de cultivos. Una hectárea de uva en Ica
      demanda <b>US$ 591</b> al año; una de maíz y pastos en Madre de Dios,
      <b>US$ 207</b>.</p>

      <p>Para cada región, el modelo calcula el promedio del gasto de sus 145 cultivos
      ponderado por la superficie que cada uno cosechó en 2023. Los precios provienen
      del estudio de costos del INEI, levantado en campo con productores.</p>

      <h4>Qué entra y qué se excluye</h4>
      <p>Se cuentan <b>fertilizante y fitosanitario</b>, que el productor compra por
      el canal. Se excluye el <b>abono orgánico</b>: lo produce la propia unidad
      agropecuaria y nunca pasa por una factura.</p>

      <h4 class="lab">Composición del mercado nacional</h4>
      {table([["Fertilizantes", "US$ 228", usd(1038e6), "60%"],
              ["Fitosanitarios", "US$ 153", usd(695e6), "40%"],
              ["<b>Mercado comprable</b>", "<b>US$ 381</b>", f"<b>{usd(TAM)}</b>", "<b>100%</b>"],
              ["Abono autoproducido", "US$ 62", usd(281e6), "excluido"]],
             ["Componente", "Gasto/ha", "Mercado anual", "Peso"],
             ["l","r","r","r"], cls="tight")}

      <div class="note brass">
        <span class="h">Contraste con datos de aduanas</span>
        <p>El modelo estima <b>US$ 1,038 MM</b> de fertilizante a precio de finca. El
        Perú importó <b>US$ 693 MM</b> CIF en 2024 y las importaciones cubren el
        <b>89.5%</b> de la oferta nacional. La diferencia entre ambas cifras es el
        margen del canal de distribución, del orden de un tercio. La estimación
        resiste el contraste con una fuente independiente.</p>
      </div>
    </div>
    <figure>
      {fig("gastoha")}
      <figcaption><b>Gasto anual en insumos por hectárea</b>, ponderado por la mezcla
      real de cultivos de cada región. Fuentes: MIDAGRI, Anuario de Producción
      Agrícola 2023; INEI, Costos de producción (ENA 2018).</figcaption>
    </figure>
  </div>

  <h3 class="rule">El rango entre regiones</h3>
  <div class="cards c3">
    <div class="card"><span class="big">US$ 591</span>
      <p><b>Ica.</b> Uva y espárrago de exportación. El gasto por hectárea más alto
      del país y el ticket por cliente más elevado.</p></div>
    <div class="card"><span class="big">US$ 381</span>
      <p><b>Promedio nacional.</b> Ponderado por la superficie cosechada de las 24
      regiones y los 145 cultivos del anuario.</p></div>
    <div class="card"><span class="big">US$ 207</span>
      <p><b>Madre de Dios.</b> Maíz amarillo duro y pastos. Cultivos extensivos de
      bajo requerimiento de insumos comprados.</p></div>
  </div>
""", "Parte I · El gasto por hectárea")


# ======================================================== PARTE II ==========
divider("II", "Quién es <em>cliente</em>",
        "Contar productores sobreestima el mercado. La pregunta correcta no es "
        "cuántos hay, sino cuántos compran, con qué frecuencia y a qué plazo.",
        ["El embudo", "Tasas de compra", "Economía unitaria"])

page(f"""
  <span class="kicker">Parte II · El embudo</span>
  <h2 class="title">De 2.26 millones de productores a <em>{nf(CLI)} clientes</em></h2>

  <figure style="margin:12px 0 0">
    {fig("embudo")}
    <figcaption><b>Embudo de mercado atendible.</b> Cada escalón aplica un filtro
    verificable del IV Censo Nacional Agropecuario, no un supuesto de penetración.</figcaption>
  </figure>

  <div class="two" style="margin-top:14px">
    <div>
      <h4>Escala mínima: cinco hectáreas</h4>
      <p>Por debajo de cinco hectáreas la agricultura peruana es mayormente de
      autoconsumo. El productor no compra con factura, no sostiene una frecuencia de
      recompra y no califica para crédito. El corte deja
      <b>{nf(cen.ua_objetivo_5_mas.sum())}</b> unidades, el
      {100*cen.ua_objetivo_5_mas.sum()/cen.productores.sum():.0f}% del total.</p>

      <h4>Comportamiento de compra</h4>
      <p>De ese universo, solo quienes <b>ya aplican fertilizante o pesticida</b>
      constituyen mercado hoy: <b>{nf(CLI)}</b> productores. Los demás requieren
      convertir a un no usuario, lo que implica un costo de adquisición
      sustancialmente mayor y un ciclo de venta más largo.</p>
    </div>
    <div>
      <h4>El segmento de entrada</h4>
      <p><b>{nf(emb.compran_a_credito.sum())} productores</b> ya emplean crédito para
      comprar insumos. Compran exactamente como AgroJuntos vende —a plazo, con
      entrega— de modo que la propuesta no exige un cambio de hábito, solo mejor
      precio y servicio.</p>

      <div class="note brass">
        <span class="h">El promedio nacional esconde el dato útil</span>
        <p>La proporción de productores que fertiliza va de <b>78% en Lambayeque</b> a
        <b>4% en Loreto</b>. Dos regiones de superficie comparable pueden ser mercados
        incomparables, y por eso la priorización se hace región por región.</p>
      </div>
    </div>
  </div>

  <h3 class="rule">Tasas de compra por región</h3>
  {table([[cap(r["dep"]), nf(r["ua_objetivo_5_mas"]), f'{100*r["tasa_fert"]:.0f}%',
           f'{100*r["tasa_pest"]:.0f}%', f'<b>{nf(r["compradores_insumos"])}</b>',
           nf(r["compran_a_credito"])]
          for _, r in emb.nlargest(5, "compradores_insumos").iterrows()],
         ["Región", "Prod. &gt;5 ha", "Fertiliza", "Aplica pesticida", "Clientes",
          "Compra a crédito"], ["l","r","r","r","r","r"])}
  <p class="sub">Cinco regiones con mayor número de clientes. Tasas del IV CENAGRO
  2012 aplicadas al segmento de más de cinco hectáreas.</p>
""", "Parte II · El embudo")

page(f"""
  <span class="kicker">Parte II · Economía unitaria</span>
  <h2 class="title">Lo que muestran <em>las ventas reales</em></h2>
  <p class="deck">Los parámetros de captura no salen de una meta sino del libro de
     ventas de la compañía: {MESES:.0f} meses de operación, {len(ven)} documentos
     emitidos y {len(cli)} clientes facturados.</p>

  <div class="cards c3">
    <div class="card"><span class="big">US$ {nf(ven.usd.mean())}</span>
      <p><b>Ticket promedio</b> por documento; mediana US$ {nf(ven.usd.median())}.
      El rango va de US$ 119 a US$ {nf(ven.usd.max())}.</p></div>
    <div class="card"><span class="big">45 días</span>
      <p><b>Recompra</b> en el cliente establecido, equivalente a 8.1 compras al año.
      Es la métrica más valiosa del negocio.</p></div>
    <div class="card"><span class="big">US$ {nf(ven.usd.mean()*8.1)}</span>
      <p><b>Valor anual</b> por cliente activo, con US$ {nf(ven.usd.mean()*8.1*0.21)}
      de margen bruto al 21%.</p></div>
  </div>

  <div class="note">
    <span class="h">Validación cruzada</span>
    <p><b>El modelo y la operación coinciden.</b> El modelo de mercado estima un gasto
    anual de <b>US$ {nf(SAM/CLI)}</b> por cliente, partiendo de superficie y precios
    oficiales. Las ventas reales arrojan <b>US$ 3,264</b> —ticket mediano de US$ 408
    por 8 compras al año—. Dos caminos independientes llegan al mismo número, lo que
    respalda el dimensionamiento.</p>
  </div>

  <h3 class="rule">Cartera actual</h3>
  {table([[cap(r["cliente"])[:36], int(r["compras"]), usd(r["usd"]), usd(r["ticket"]),
           ("—" if pd.isna(r["frec_dias"]) else "mismo día" if r["frec_dias"] < 1
            else f'{r["frec_dias"]:.0f} días')]
          for _, r in cli.nlargest(6, "usd").iterrows()],
         ["Cliente", "Compras", "Facturado", "Ticket medio", "Frecuencia"],
         ["l","r","r","r","r"])}
  <p class="sub">Seis principales clientes por facturación. Total del período:
  {usd(ven.usd.sum())} en {len(ven)} documentos a {len(cli)} clientes,
  {100*(ven.pago=='CRÉDITO').mean():.0f}% de ellos a crédito.</p>

  <h3 class="rule">Concentración de la cartera</h3>
  <p>Los dos primeros clientes explican el
  <b>{100*cli.nlargest(2,'usd').usd.sum()/cli.usd.sum():.0f}%</b> de la facturación
  del período. Es la concentración esperable en una etapa temprana, pero constituye el
  riesgo operativo más relevante de la compañía y debe reducirse antes de escalar la
  estructura comercial.</p>
""", "Parte II · Economía unitaria")


# ======================================================== PARTE III =========
divider("III", "Cuándo y <em>cómo llegar</em>",
        "Un mercado no se sirve en abstracto. Esta parte responde en qué mes "
        "compra cada región, cuánto cuesta llegar a ella y por qué puerto sale "
        "lo que produce.",
        ["El calendario de compra", "Costo de servir", "Puertos y salida"])

_pico = est_n.loc[est_n["pct"].idxmax()]
_top4 = est_n.nlargest(4, "pct")
page(f"""
  <span class="kicker">Parte III · El calendario de compra</span>
  <h2 class="title">La demanda no llega pareja: <em>llega en campaña</em></h2>
  <p class="deck">El insumo se compra contra el calendario de siembra, no a lo
     largo del año. Cada una de las 145 hojas de cultivo del anuario del MIDAGRI
     trae el mes en que se sembró cada hectárea; valorizadas al costo del cultivo,
     dan la curva de demanda del país.</p>

  <figure style="margin:12px 0 0">
    {fig("curva_estacional")}
    <figcaption><b>Demanda mensual de fertilizante y fitosanitario.</b> En verde
    oscuro, los cuatro meses de mayor demanda. Cultivos transitorios ubicados en
    su mes de siembra; permanentes distribuidos en el año. Fuente: MIDAGRI,
    Anuario de Producción Agrícola 2023, valorizado con costos INEI.</figcaption>
  </figure>

  <div class="two" style="margin-top:14px">
    <div>
      <h4>La concentración</h4>
      <p>El mes pico es <b>{_pico['mes']}</b>, con <b>{_pico['pct']:.1f}%</b> de la
      demanda anual. Cuatro meses —{', '.join(_top4['mes'])}— concentran el
      <b>{_top4['pct'].sum():.0f}%</b>. Entre abril y julio la demanda cae a poco
      más de la mitad del pico.</p>

      <h4>Qué decide esto</h4>
      <ul class="pts">
        <li><b>Capital de trabajo.</b> El inventario y el crédito a clientes deben
        estar dispuestos antes de setiembre, no repartidos en doce cuotas iguales.</li>
        <li><b>Estructura comercial.</b> Una planilla dimensionada para el pico
        queda ociosa medio año; una dimensionada al promedio pierde la campaña.</li>
      </ul>
    </div>
    <div>
      <div class="note brass">
        <span class="h">El dato que elige la primera sede</span>
        <p>La curva nacional esconde dos negocios distintos. <b>San Martín</b>
        reparte su demanda casi parejo —su mes más fuerte es apenas el 10.6% del
        año— porque combina arroz con café permanente. <b>Lambayeque</b> concentra
        el <b>32%</b> en enero. La primera región sostiene una operación
        permanente; la segunda exige una campaña.</p>
      </div>
      <p>Esa diferencia no aparece en el tamaño de mercado ni en el número de
      clientes, y sin embargo determina si un territorio se atiende con oficina
      propia o con una brigada estacional.</p>
    </div>
  </div>
""", "Parte III · El calendario de compra")

page(f"""
  <span class="kicker">Parte III · El calendario de compra</span>
  <h2 class="title">Cada región compra <em>en su propio mes</em></h2>

  <figure style="margin:12px 0 0">
    {fig("calendario_regional")}
    <figcaption><b>Distribución mensual de la demanda de insumos</b>, como
    porcentaje del año de cada región. El recuadro marca el mes pico. Dieciséis
    regiones de mayor demanda.</figcaption>
  </figure>

  <h3 class="rule">Continuidad de la demanda</h3>
  {table([[cap(r["k"]), f'{r["total"]/1e6:,.0f}', r["mes_pico"],
           f'{r["pct_pico"]:.0f}%', f'{r["pct_top4"]:.0f}%',
           "Permanente" if r["pct_top4"] < 45 else
           ("Mixta" if r["pct_top4"] < 65 else "Campaña")]
          for _, r in est_r.nlargest(8, "total").iterrows()],
         ["Región", "Demanda US$ MM", "Mes pico", "% en el pico",
          "% en 4 meses", "Operación sugerida"],
         ["l","r","r","r","r","l"])}
  <p class="sub">Un año perfectamente parejo pondría 33% de la demanda en sus
  cuatro meses más fuertes. Cuanto más se aleja de esa cifra, más estacional es
  el territorio y menos sostiene una estructura fija.</p>
""", "Parte III · El calendario de compra")

_acc = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")
_acc = _acc.rename(columns={"horas_capital_real": "horas_capital",
                            "horas_puerto_real": "horas_puerto",
                            "costo_viaje_real": "costo_viaje_usd"})
_acc = _acc[_acc["horas_capital"].notna() & (_acc["horas_capital"] < 1e6)]
_rut = pd.read_csv("out/ruteo_departamento.csv", encoding="utf-8-sig")
_bajo2 = 100 * _acc[_acc.horas_capital <= 2].s_sam_usd.sum() / _acc.s_sam_usd.sum()
_sobre4 = 100 * _acc[_acc.horas_capital > 4].s_sam_usd.sum() / _acc.s_sam_usd.sum()
_caros = int((100 * _acc.costo_viaje_usd /
              (_acc.s_sam_usd / _acc.s_clientes_sam.replace(0, pd.NA)) > 10).sum())
page(f"""
  <span class="kicker">Parte III · Costo de servir</span>
  <h2 class="title">La distancia <em>es margen</em></h2>

  <div class="mapl" style="margin-top:12px">
    <figure style="max-width:56mm;margin:0 auto">
      {fig("accesibilidad")}
      <figcaption><b>Tiempo de viaje medido</b> desde cada sector agrícola hasta
      el centro provincial más próximo, ruteado sobre la red vial nacional:
      88,962 vías, 5.2 millones de nodos.</figcaption>
    </figure>
    <div>
      <p>Dos sectores con las mismas hectáreas no son el mismo cliente si uno está
      a cuarenta minutos de Trujillo y el otro a nueve horas de Iquitos. Para un
      negocio que entrega y financia, esa diferencia se come el margen antes de
      que la venta ocurra.</p>
      <div class="note good" style="border-left-color:var(--forest)">
        <span class="h">El hallazgo que sostiene el modelo</span>
        <p>El <b>{_bajo2:.0f}%</b> del mercado atendible está a menos de dos horas
        de un centro provincial, y solo el <b>{_sobre4:.0f}%</b> pasa de cuatro
        horas. El costo de entrega supera el 10% del gasto anual del cliente en
        apenas <b>{_caros}</b> de {len(_acc):,} sectores. La logística no es el
        obstáculo del negocio: es un argumento a favor.</p>
      </div>

      <div class="note brass">
        <span class="h">La medición corrigió a la estimación</span>
        <p>Estimar por línea recta daba <b>2.31 horas</b> de promedio nacional; el
        ruteo real da <b>1.84</b>. La estimación castigaba de más a la selva
        —Madre de Dios pasó de 9.0 a <b>3.5 horas</b> por la Interoceánica— y era
        optimista en la costa, donde la vía rodea el terreno.</p>
      </div>

    </div>
  </div>

  <figure style="margin-top:12px">
    {fig("costo_mercado")}
    <figcaption><b>Mercado frente a costo de acceso.</b> Cada círculo es una
    región; el área es proporcional al número de clientes y en verde oscuro van
    las ocho prioritarias. La línea marca el umbral de dos horas.</figcaption>
  </figure>

""", "Parte III · Costo de servir")

_pu = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
_mar = _pu[_pu.tipo == "maritimo"]
page(f"""
  <span class="kicker">Parte III · Puertos y salida</span>
  <h2 class="title">Por dónde sale <em>lo que se produce</em></h2>

  <div class="mapr" style="margin-top:14px">
    <div>
      <p>La orientación exportadora cambia qué insumo se compra. Un fundo que
      embarca a Europa necesita producto certificado, con carencia controlada y
      trazabilidad; uno que vende al mercado interno compra por precio. La
      distancia al puerto es el mejor indicador disponible de en cuál de los dos
      mundos está cada valle.</p>

      <p>Se ubicaron <b>{len(_pu)}</b> terminales del inventario de la Autoridad
      Portuaria Nacional: <b>{len(_mar)}</b> marítimos y
      <b>{len(_pu)-len(_mar)}</b> fluviales. Cada sector agrícola quedó asignado a
      su puerto de embarque más cercano.</p>

      <h4 class="lab">Puertos agroexportadores y su zona de influencia</h4>
      {table([[r["puerto"].split(" (")[0], cap(r["region"]),
               f'{_acc[_acc.puerto_maritimo == r["puerto"]].s_ha_cosechada.sum()/1000:,.0f}k',
               f'{_acc[_acc.puerto_maritimo == r["puerto"]].s_sam_usd.sum()/1e6:,.0f}']
              for _, r in _mar[_mar.relevancia_agro == "alta"].iterrows()],
             ["Terminal", "Región", "Ha cosechadas", "SAM US$ MM"],
             ["l","l","r","r"], cls="tight")}

      <div class="note">
        <span class="h">Lo que revela el mapa</span>
        <p><b>San Martín es la tercera región del país por mercado y está a 22
        horas de Salaverry.</b> Su agricultura —arroz y café— es de mercado
        interno, no de exportación. Eso cambia la canasta de insumos que demanda y
        explica por qué su ticket es alto pero su perfil no es el de la costa.</p>
      </div>
    </div>
    <figure>
      {fig("puertos")}
      <figcaption><b>Terminales portuarios y su zona de influencia.</b> Cada sector
      agrícola aparece coloreado según el puerto marítimo más cercano. Fuente:
      inventario de la Autoridad Portuaria Nacional, geocodificado.</figcaption>
    </figure>
  </div>

  <h3 class="rule">Distancia media al puerto, por región</h3>
  {table([[cap(r["dep"]), f'{r["horas_puerto"]:.0f} h',
           f'{r["km_puerto"]:,.0f}', r["puerto"].split(" (")[0],
           "Exportadora" if r["horas_puerto"] <= 6 else
           ("Intermedia" if r["horas_puerto"] <= 15 else "Mercado interno")]
          for _, r in pd.read_csv("out/logistica_departamento.csv",
                                  encoding="utf-8-sig")
          .nsmallest(8, "horas_puerto").iterrows()],
         ["Región", "Horas al puerto", "Km", "Terminal", "Orientación"],
         ["l","r","r","l","l"])}
  <p class="sub">Ocho regiones más cercanas a un terminal marítimo. La orientación
  es una lectura de la distancia, no una medición de flujos de exportación.</p>
""", "Parte III · Puertos y salida")


# ======================================================== PARTE IV ==========
divider("IV", "Dónde <em>empezar</em>",
        "Ocho regiones concentran el 58% del mercado atendible. Esta parte las "
        "ordena, dimensiona la captura posible y baja del territorio al nombre "
        "propio del prospecto.",
        ["Priorización", "Escenarios de captura", "Prospección"])

page(f"""
  <span class="kicker">Parte IV · Priorización</span>
  <h2 class="title">Ocho regiones concentran el <em>{FOCO.pct_acum.iat[-1]:.0f}%</em>
     del mercado</h2>

  <div class="mapl" style="margin-top:14px">
    <figure>
      {fig("sam")}
      <figcaption><b>Mercado atendible anual por región.</b> Contorneadas en verde,
      las ocho regiones prioritarias según el score de atractivo comercial.</figcaption>
    </figure>
    <div>
      <p>El score pondera seis factores, todos medidos: tamaño del mercado (35%),
      clientes que ya compran insumos (20%), accesibilidad —qué proporción de la
      región está a menos de dos horas de un centro provincial— (15%), gasto por
      hectárea (10%), penetración del crédito (10%) y continuidad de la demanda a
      lo largo del año (10%).</p>

      <h4>Qué cambió al incorporar logística y calendario</h4>
      <p>El primer grupo no se movió, lo que habla de la solidez del orden. Los
      desplazamientos son explicables uno a uno:</p>
      <ul class="pts">
        <li><b>Huánuco sube cuatro puestos</b> (11.º a 7.º): su demanda es de las
        más parejas del país y el 78% de sus sectores está a menos de dos horas.</li>
        <li><b>Puno baja tres</b> (9.º a 12.º): concentra el 79% de su demanda en
        cuatro meses y solo el 46% de sus sectores es accesible en dos horas.</li>
        <li><b>Tumbes baja tres</b> pese a ser la región más accesible del país:
        el 78% de su demanda cae en una sola campaña.</li>
      </ul>

      <div class="note">
        <span class="h">El orden depende de qué se optimice</span>
        <p>Por hectáreas lidera San Martín; por mercado atendible, La Libertad; por
        número de clientes, Junín. El score pondera las tres dimensiones y agrega
        crédito, accesibilidad y estacionalidad, que ninguna captura por separado.</p>
      </div>
    </div>
  </div>

  <h3 class="rule">Qué tipo de operación necesita cada territorio</h3>
  {table([[a, str(len(g)), f"US$ {g.sam_usd.sum()/1e6:,.0f} MM",
           ", ".join(cap(x) for x in g.dep.head(5))]
          for a, g in v3.groupby("arquetipo")],
         ["Arquetipo", "Regiones", "SAM", "Ejemplos"],
         ["l","r","r","l"])}
  <p class="sub">La clasificación combina ticket por cliente, número de clientes,
  accesibilidad y concentración estacional. No es una etiqueta descriptiva: define
  si el territorio se atiende con ejecutivos de cuenta, con red de distribuidores o
  con una brigada de campaña.</p>
""", "Parte IV · Priorización")

RANK_ROWS = [[int(r["rank_v3"]), cap(r["dep"]), nf(r["ha_cosechada"]),
              nf(r["gasto_ha"]), nf(r["clientes_sam"]),
              f'{r["pct_bajo_2h"]:.0f}%', r["mes_pico"],
              f'{r["pct_top4"]:.0f}%', usd(r["sam_usd"]),
              f'{r["pct_acum_v3"]:.0f}%'] for _, r in v3.iterrows()]
page(f"""
  <span class="kicker">Parte IV · Priorización</span>
  <h2 class="title">Las 24 regiones, <em>ordenadas por atractivo</em></h2>
  {table(RANK_ROWS,
         ["#", "Región", "Ha cosechadas", "Gasto/ha", "Clientes", "% a &lt;2 h",
          "Mes pico", "% en 4 meses", "SAM anual", "% acum."],
         ["r","l","r","r","r","r","r","r","r","r"],
         foot=["", "Perú", nf(HA_COS), nf(TAM/HA_COS), nf(CLI), "71%", "Oct",
               "45%", usd(SAM), "100%"])}
  <p class="sub"><b>Ha cosechadas:</b> superficie llevada a cosecha en la campaña
  2023. <b>Gasto/ha:</b> desembolso anual en fertilizante y fitosanitario,
  ponderado por la mezcla de cultivos. <b>Clientes:</b> productores de más de cinco
  hectáreas que ya aplican insumos. <b>% a &lt;2 h:</b> sectores a menos de dos
  horas de un centro provincial. <b>% en 4 meses:</b> concentración estacional de
  la demanda; 33% sería un año perfectamente parejo.</p>

""", "Parte IV · Priorización")

ESC = som.iloc[1]
page(f"""
  <span class="kicker">Parte IV · Escenarios de captura</span>
  <h2 class="title">Qué parte del mercado <em>es alcanzable</em></h2>
  <p class="deck">El SAM indica cuánto dinero existe. El SOM debe indicar cuánto puede
     tomar este equipo con la operación que ya demostró que funciona.</p>

  <h3 class="rule">Escenarios sobre las ocho regiones foco</h3>
  <p>SAM en regiones foco: <b>{usd(FOCO.sam_usd.sum())}</b> · clientes alcanzables:
  <b>{nf(FOCO.clientes_sam.sum())}</b> · valor anual por cliente activo:
  <b>US$ {nf(ven.usd.mean()*8.1)}</b></p>
  {table([[r["escenario"], f'{100*r["penetracion"]:.1f}%', nf(r["clientes"]),
           f'US$ {r["ventas_usd"]/1e6:.1f} MM', f'US$ {r["margen_usd"]/1e6:.1f} MM']
          for _, r in som.iterrows()],
         ["Escenario", "Penetración", "Clientes activos", "Ventas anuales",
          "Margen bruto"], ["l", "r", "r", "r", "r"])}

  <div class="note">
    <span class="h">Qué implica el escenario base</span>
    <p>Alcanzar <b>{nf(ESC.clientes)} clientes activos</b> supone incorporar
    <b>{ESC.clientes/36:.0f} clientes al mes durante tres años</b>, partiendo de los
    {len(cli)} actuales. Es exigente pero acotado: representa
    {100*ESC.penetracion:.1f} de cada 100 clientes potenciales del territorio foco, y
    no requiere presencia fuera de las ocho regiones prioritarias.</p>
  </div>

  <h3 class="rule">Implicancias operativas</h3>
  <ul class="pts">
    <li><b>La estructura comercial se dimensiona por cliente, no por región.</b> Con
    recompra cada 45 días, {nf(ESC.clientes)} clientes activos generan del orden de
    {nf(ESC.clientes*8.1/12)} pedidos al mes. Ese es el volumen que la operación
    logística debe sostener.</li>
    <li><b>El crédito es el cuello de botella, no la demanda.</b> Al ticket y
    frecuencia observados, financiar {nf(ESC.clientes)} clientes a 30 días exige
    capital de trabajo del orden de <b>US$ {nf(ESC.ventas_usd/12)}</b> permanente.</li>
    <li><b>Las regiones de canal y las de venta directa requieren equipos
    distintos.</b> Junín y Cajamarca se atienden con distribuidores; Ica y La Libertad,
    con ejecutivos de cuenta.</li>
  </ul>
""", "Parte IV · Escenarios de captura")

emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                  dtype={"ruc": str, "ubigeo": str})
_c = emp.clase.value_counts()
EMP_CLASES = [
    ("productor", _c.get("productor", 0), "El cliente: fundos y empresas agrícolas"),
    ("agroindustria", _c.get("agroindustria", 0), "El cliente grande: packing, molinos, agroexport"),
    ("agro_otro", _c.get("agro_otro", 0), "Otras empresas del sector, por clasificar"),
    ("canal", _c.get("canal", 0), "Competidor y socio: agroveterinarias y distribuidoras"),
    ("proveedor", _c.get("proveedor", 0), "Aguas arriba: fertilizantes y agroquímicos"),
]
EMP_REG = (emp.groupby("dep")
           .agg(empresas=("ruc", "size"),
                productor=("clase", lambda x: (x == "productor").sum()),
                agroind=("clase", lambda x: (x == "agroindustria").sum()),
                canal=("clase", lambda x: (x == "canal").sum()))
           .sort_values("empresas", ascending=False).reset_index())
EMP_EXP, EMP_IMP, EMP_COM = (nf(emp.exporta.sum()), nf(emp.importa.sum()),
                             nf(emp.comex.sum()))

FUNDO = r"fundo|hacienda|agr[ií]cola|agroindustri"
n_fundos = int(pros.nombre.str.contains(FUNDO, case=False, na=False).sum()) if len(pros) else 0
pf = pros[pros.nombre.str.contains(FUNDO, case=False, na=False)] if len(pros) else pros
if len(pf):
    pf = (pf[pf.ha > 0].sort_values("ha", ascending=False)
          .groupby("dep").head(2).nlargest(9, "ha"))
tabla_pf = (table([[r["nombre"][:36], cap(r["dep"]), r["tipo"], nf(r["ha"], 1),
                    f'{r["lat"]:.3f} / {r["lon"]:.3f}'] for _, r in pf.iterrows()],
                  ["Nombre", "Región", "Uso de suelo", "Hectáreas",
                   "Latitud / longitud"], ["l", "l", "l", "r", "r"])
            if len(pf) else "<p>Sin registros con superficie.</p>")

page(f"""
  <span class="kicker">Parte IV · Prospección</span>
  <h2 class="title">Del territorio <em>al nombre propio</em></h2>

  <div class="mapl" style="margin-top:14px">
    <figure>
      {fig("prospectos")}
      <figcaption><b>Entidades agrícolas con nombre propio y coordenada</b>, extraídas
      de OpenStreetMap: {nf(n_fundos)} fundos y haciendas más
      {nf(len(pros)-n_fundos)} puntos de canal y agroindustria.</figcaption>
    </figure>
    <div>
      <p>Las capas anteriores indican dónde hay mercado. Esta indica a quién llamar. Se
      extrajeron <b>{nf(len(pros))}</b> entidades agrícolas georreferenciadas con
      nombre propio: fundos, haciendas, agroindustrias, agroveterinarias y tiendas
      rurales.</p>

      <div class="note brass">
        <span class="h">La capa se validó sola</span>
        <p>Entre los registros aparece <b>Fundo Los Paltos SAC</b>, en Áncash, con
        <b>178 hectáreas</b> georreferenciadas. Es un cliente actual de AgroJuntos
        —cinco cotizaciones en octubre de 2025 por US$ 12,154— que el método habría
        identificado sin conocerlo de antemano.</p>
      </div>

      <p>La cobertura es desigual porque depende del trabajo de voluntarios: densa en
      Lima, Ica y Áncash, escasa en la selva. Complementa la capa oficial del MIDAGRI
      sin reemplazarla, y sirve para construir rutas de visita, no para dimensionar
      mercado.</p>

      <h4>Cómo se utiliza</h4>
      <ul class="pts">
        <li>Cruzar cada fundo con el sector estadístico donde cae, para estimar su
        gasto potencial en insumos.</li>
        <li>Usar los puntos de canal como red de distribución candidata en zonas sin
        venta directa.</li>
        <li>Priorizar por cercanía a los fundos ya facturados: Áncash concentra
        US$ 11,252 de las ventas actuales.</li>
      </ul>
    </div>
  </div>

  <h3 class="rule">Fundos con superficie identificada</h3>
  {tabla_pf}
  <p class="sub">Muestra de mayor superficie mapeada, limitada a dos por región para
  reflejar la dispersión geográfica. El listado íntegro se entrega en formato CSV.</p>
""", "Parte IV · Prospección")

page(f"""
  <span class="kicker">Parte IV · Prospección</span>
  <h2 class="title">El universo formal: <em>21,063 empresas</em> con RUC</h2>
  <p class="deck">La capa de OpenStreetMap dice dónde hay un fundo. El padrón de
     contribuyentes dice quién lo factura. Cruzados, dan una lista de prospectos
     con nombre, RUC y distrito.</p>

  <p>Al padrón de contribuyentes de SUNAT —18.4 millones de registros, actualizado
  a diario— se le aplicó una clasificación por razón social restringida a personas
  jurídicas. El resultado es un directorio de empresas agrícolas activas, con RUC
  verificable, domicilio fiscal y distrito.</p>

  {table([[c.replace("_", " ").capitalize(), nf(n), d]
          for c, n, d in EMP_CLASES],
         ["Clase", "Empresas activas", "Qué representa para AgroJuntos"],
         ["l","r","l"])}

  <div class="two" style="margin-top:6px">
    <div>
      <h4 class="lab">Concentración regional</h4>
      {table([[cap(r["dep"]), nf(r["empresas"]), nf(r["productor"]),
               nf(r["agroind"]), nf(r["canal"])]
              for _, r in EMP_REG.head(8).iterrows()],
             ["Región", "Total", "Productor", "Agroindustria", "Canal"],
             ["l","r","r","r","r"], cls="tight")}
    </div>
    <div>
      <div class="note brass">
        <span class="h">Sobre comercio exterior</span>
        <p>{EMP_EXP} empresas declaran exportación en su razón social,
        {EMP_IMP} importación y {EMP_COM} operan como trading. Es un subconjunto
        real y verificable, no el universo completo: <b>los registros aduaneros a
        nivel de empresa no son de descarga pública en el Perú</b>. Las estadísticas
        de SUNAT se publican agregadas por sector y partida, sin RUC.</p>
      </div>
      <p>El padrón reducido tampoco incluye el código CIIU de actividad, que SUNAT
      solo expone consultando RUC por RUC. La clasificación por nombre subestima:
      no ve a la empresa que opera bajo una razón social neutra.</p>
    </div>
  </div>


""", "Parte IV · Prospección")



# ======================================================== PARTE IV =========
divider("V", "Atlas <em>regional</em>",
        "Una ficha por cada una de las 24 regiones agrícolas del país: mapa de "
        "sectores, métricas de mercado, mezcla de cultivos que sostiene el gasto y "
        "una lectura comercial de una línea.",
        ["24 regiones", "Mapa de sectores", "Lectura comercial"])


def lectura(r):
    """One line telling a salesperson what they are walking into."""
    dep = cap(r["dep"])
    tk, gh, cl = r["ticket_anual"], r["gasto_ha"], r["clientes_sam"]
    cred, fert = 100 * r["tasa_credito"], 100 * r["tasa_fert"]
    partes = []

    if tk >= 5000:
        partes.append(f"Ticket alto: <b>US$ {nf(tk)}</b> por cliente al año. "
                      "Perfil de venta consultiva y contrato anual")
    elif cl >= 10000:
        partes.append(f"<b>{nf(cl)}</b> clientes dispersos con ticket de "
                      f"US$ {nf(tk)}. Se atiende con red de canal, no con "
                      "fuerza de venta propia")
    else:
        partes.append(f"<b>{nf(cl)}</b> clientes a US$ {nf(tk)} al año. "
                      "Mercado de tamaño medio")

    if cred >= 12:
        partes.append(f"el <b>{cred:.0f}%</b> ya compra a crédito, la tasa más "
                      "alta del país: entrada natural para la propuesta")
    elif cred <= 3:
        partes.append(f"solo el <b>{cred:.0f}%</b> usa crédito, lo que exige "
                      "vender al contado primero")

    if fert <= 25:
        partes.append(f"apenas <b>{fert:.0f}%</b> fertiliza, de modo que buena "
                      "parte del potencial exige conversión")
    elif fert >= 65:
        partes.append(f"<b>{fert:.0f}%</b> fertiliza: demanda ya instalada")

    if r["prospectos"] >= 150:
        partes.append(f"<b>{nf(r['prospectos'])}</b> prospectos ya localizados "
                      "con nombre y coordenada")
    return f"<b>{dep}.</b> " + "; ".join(partes) + "."


def barras(items, total_ref):
    out = []
    for nombre, val, _ in items[:4]:
        w = 100 * val / total_ref if total_ref else 0
        out.append(f'<div class="fbar"><span class="nm">{cap(nombre)}</span>'
                   f'<span class="tr"><i style="width:{min(w,100):.0f}%"></i></span>'
                   f'<span class="vl">{nf(val/1e6,1)} MM</span></div>')
    return '<div class="fbars">' + "".join(out) + "</div>"


def ficha(r):
    mapa = f"out/dep/{r['k']}.png"
    tot = r["top_gasto"][0][1] if len(r["top_gasto"]) else 1
    return f"""
<div class="fiche">
  <div class="mp">{img(mapa, "")}</div>
  <div>
    <div class="hd">
      <span class="rk">{int(r['rank']):02d}</span>
      <h3>{cap(r['dep'])}</h3>
      <span class="tag">{cap(r['region_nat'])} · {int(r['n_cultivos'])} cultivos</span>
    </div>
    <div class="fgrid">
      <div><span class="v">{usd(r['sam_usd'])}</span><span class="l">Mercado anual</span></div>
      <div><span class="v">{nf(r['clientes_sam'])}</span><span class="l">Clientes</span></div>
      <div><span class="v">US$ {nf(r['gasto_ha'])}</span><span class="l">Gasto por ha</span></div>
      <div><span class="v">US$ {nf(r['ticket_anual'])}</span><span class="l">Por cliente/año</span></div>
    </div>
    <div class="fgrid" style="border-top:0">
      <div><span class="v">{nf(r['ha_cosechada']/1000)}k</span><span class="l">Ha cosechadas</span></div>
      <div><span class="v">{100*r['tasa_fert']:.0f}%</span><span class="l">Fertiliza</span></div>
      <div><span class="v">{100*r['tasa_credito']:.0f}%</span><span class="l">Usa crédito</span></div>
      <div><span class="v">{nf(r['prospectos'])}</span><span class="l">Prospectos OSM</span></div>
    </div>
    <h4 class="lab">Cultivos que concentran el gasto en insumos</h4>
    {barras(r['top_gasto'], tot)}
    <p class="fread">{lectura(r)}</p>
  </div>
</div>"""


filas = list(perfil.iterrows())
POR_HOJA = 3
for i in range(0, len(filas), POR_HOJA):
    grupo = filas[i:i + POR_HOJA]
    par = [ficha(r) for _, r in grupo]
    desde = int(grupo[0][1]["rank"])
    hasta = int(grupo[-1][1]["rank"])
    page(f"""
  <span class="kicker">Atlas regional · posiciones {desde:02d} a {hasta:02d}</span>
  {''.join(par)}
""", "Parte V · Atlas regional")



# ========================================================= PARTE V =========
divider("VI", "Metodología <em>y fuentes</em>",
        "La cadena completa de cálculo, el contraste con datos de aduanas y las "
        "tres limitaciones que el lector debe tener presentes al usar estas cifras.",
        ["Cadena de cálculo", "Limitaciones", "Fuentes"])

page(f"""
  <span class="kicker">Parte VI · Metodología</span>
  <h2 class="title">Cómo se construyó <em>cada cifra</em></h2>

  <div class="two" style="margin-top:14px">
    <div>
      <h3 class="rule">Cadena de cálculo</h3>
      <ul class="num">
        <li><b>Superficie que produce.</b> Superficie cosechada de 145 cultivos por
        región, campaña 2023. No se emplea superficie agrícola total porque la tierra
        en descanso no demanda insumos.</li>
        <li><b>Gasto por hectárea.</b> Para cada región, el promedio del gasto en
        abono, fertilizante y plaguicida de sus cultivos, ponderado por la superficie
        de cada uno. Precios del estudio de costos del INEI. Se retiene solo
        fertilizante y fitosanitario.</li>
        <li><b>TAM.</b> Superficie cosechada por gasto por hectárea, sumado sobre las
        24 regiones: <b>{usd(TAM)}</b>.</li>
        <li><b>SAM.</b> La porción del TAM en manos de productores de más de cinco
        hectáreas que ya aplican insumos. La participación de superficie comercial se
        estima con los puntos medios de los estratos de tamaño del CENAGRO,
        reescalados a la superficie agrícola censada: <b>{usd(SAM)}</b>.</li>
        <li><b>SOM.</b> Penetración sobre las ocho regiones foco, valorizada con el
        ingreso anual por cliente observado en las ventas propias de la compañía.</li>
      </ul>

      <h3 class="rule">Contraste independiente</h3>
      <p>El componente de fertilizantes del modelo asciende a <b>US$ 1,038 MM</b> a
      precio de finca. Las importaciones peruanas de fertilizantes sumaron
      <b>US$ 693 MM</b> CIF en 2024 y representan el <b>89.5%</b> de la oferta
      nacional. La brecha corresponde al margen del canal de distribución, del orden
      de un tercio, lo que sitúa la estimación dentro de un rango verificable contra
      registros aduaneros.</p>
    </div>
    <div>
      <h3 class="rule">Limitaciones declaradas</h3>
      <div class="note warn">
        <span class="h">Antigüedad del censo</span>
        <p>El censo agropecuario vigente es de <b>2012</b>. No existe uno más
        reciente: el país acumula catorce años sin levantamiento censal del agro. Las
        tasas de uso de insumos y de crédito provienen de esa base, mientras que la
        superficie y los cultivos corresponden a 2023–2024. La composición del agro
        peruano ha cambiado en ese período, particularmente en la costa exportadora.</p>
      </div>
      <div class="note warn">
        <span class="h">Naturaleza de los valores por sector</span>
        <p>Las cifras departamentales se distribuyen entre los 7,036 sectores en
        proporción a sus hectáreas agrícolas. Se trata de una asignación, no de una
        medición: es válida para priorizar territorio y construir rutas, pero no para
        cotizar a un productor determinado.</p>
      </div>
      <div class="note warn">
        <span class="h">Alcance del ruteo</span>
        <p>Los tiempos se rutean sobre la red vial de OpenStreetMap con velocidad
        por clase de vía ajustada por superficie y limitada por la velocidad
        máxima señalizada. Dos tercios de la red declara superficie y un tercio
        velocidad; el resto usa el valor por defecto de su clase. No modela
        congestión, estacionalidad de caminos ni cierres. <b>143 de 7,036
        sectores</b> quedan fuera del grafo por no tener vía mapeada cerca.</p>
      </div>
      <div class="note warn">
        <span class="h">Cifra pendiente de conciliación</span>
        <p>El dossier de inversionistas declara ventas acumuladas superiores a
        <b>US$ 200,000</b>; el libro de ventas analizado suma
        <b>{usd(ven.usd.sum())}</b> en {MESES:.0f} meses. La diferencia debe aclararse
        antes de presentar el material a terceros: es la primera cifra que un
        inversionista verificará y la más sencilla de contrastar.</p>
      </div>

      <h3 class="rule">Cobertura de la capa de prospección</h3>
      <p>Las {nf(len(pros))} entidades georreferenciadas provienen de OpenStreetMap,
      cuya cobertura depende del trabajo de voluntarios y es marcadamente desigual
      entre regiones. Debe entenderse como un punto de partida para prospección, no
      como un catastro.</p>
    </div>
  </div>
""", "Parte VI · Metodología")

page(f"""
  <span class="kicker">Parte VI · Fuentes</span>
  <h2 class="title">Origen de <em>los datos</em></h2>

  <div class="two" style="margin-top:14px">
    <div>
      <h4 class="lab">Fuentes oficiales primarias</h4>
      <ul class="srcs">
        <li><b>MIDAGRI · Padrón Nacional de Sectores Estadísticos 2024.</b> 7,043
        sectores con UBIGEO, hectáreas agrícolas, centroide georreferenciado, región
        natural y agencia agraria. Anexo del Mapa Nacional de Superficie Agrícola,
        aprobado por Resolución Ministerial N.º 0026-2025-MIDAGRI.</li>
        <li><b>MIDAGRI · Anuario de Producción Agrícola 2023.</b> Superficie sembrada
        y cosechada, producción, rendimiento y precio en chacra para 145 cultivos,
        desagregado por región.</li>
        <li><b>INEI · Costos de producción para la actividad agricultura, ganadería,
        caza y silvicultura, en base a la Encuesta Nacional Agropecuaria 2018</b>
        (marzo 2021). Costo por hectárea desagregado por ítem —abono, fertilizante,
        plaguicida, semilla, jornal, riego— para 73 cultivos.</li>
        <li><b>INEI · IV Censo Nacional Agropecuario 2012.</b> Anexos departamentales:
        número de productores, unidades agropecuarias por tamaño, aplicación de
        fertilizantes químicos y pesticidas, condición jurídica y destino del crédito
        agrario.</li>
      </ul>
    </div>
    <div>
      <h4 class="lab">Fuentes de contraste y complemento</h4>
      <ul class="srcs">
        <li><b>MIDAGRI e ICEX.</b> Importaciones peruanas de fertilizantes 2024 y
        participación de la oferta importada en el consumo nacional, empleadas como
        validación externa del modelo.</li>
        <li><b>SUNAT · Padrón Reducido del RUC.</b> 18.4 millones de registros,
        actualizado a diario. Aporta razón social, estado, condición de domicilio,
        ubigeo y domicilio fiscal. <b>No incluye el código CIIU de actividad</b>,
        que SUNAT solo expone consultando RUC por RUC; la clasificación sectorial
        de este informe es por razón social, restringida a personas jurídicas.</li>
        <li><b>Autoridad Portuaria Nacional.</b> Inventario de terminales
        portuarios de uso público, geocodificado contra Nominatim de
        OpenStreetMap para obtener coordenada verificable.</li>
        <li><b>OpenStreetMap.</b> Entidades agrícolas nombradas y georreferenciadas
        —fundos, haciendas, agroindustrias, agroveterinarias y tiendas rurales— y
        la red vial nacional, extraídas mediante la API Overpass. Licencia ODbL.</li>
        <li><b>AgroJuntos.</b> Libro de compras y ventas y reporte de cotizaciones del
        período setiembre 2024 – octubre 2025, empleados para calibrar ticket,
        frecuencia de recompra y valor anual por cliente.</li>
      </ul>

      <h4 class="lab">Convenciones</h4>
      <ul class="srcs">
        <li>Todos los importes se expresan en dólares estadounidenses, convertidos a
        un tipo de cambio de <b>S/ {TC}</b> por dólar.</li>
        <li>El separador de miles es la coma; el decimal, el punto.</li>
        <li>«Región» se emplea como sinónimo de departamento, siguiendo la
        nomenclatura del MIDAGRI.</li>
        <li>Los porcentajes de tasas de compra provienen del censo 2012 y se aplican
        al segmento de más de cinco hectáreas sin ajuste al alza, lo que mantiene la
        estimación por el lado conservador.</li>
        <li>El score de priorización pondera mercado (35%), clientes (20%),
        accesibilidad (15%), gasto por hectárea (10%), crédito (10%) y continuidad
        de la demanda (10%).</li>
      </ul>
    </div>
  </div>

  <div class="note" style="margin-top:18px">
    <span class="h">Reproducibilidad</span>
    <p>Cada cifra de este informe se genera por script a partir de los archivos de
    origen, sin transcripción manual. El conjunto de datos derivado —modelo por
    región, embudo, costos por cultivo, perfil de las 24 regiones y listado de
    prospectos— se entrega en formato CSV junto con este documento, de modo que
    cualquier supuesto pueda modificarse y el modelo recalcularse íntegramente.</p>
  </div>
""", "Parte VI · Fuentes")


# ============================================================== BUILD ======
html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Reporte de mercado · AgroJuntos</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style></head><body>
{"".join(PAGES)}
</body></html>"""

for rom, pg in INDICE.items():
    html = html.replace(f"@@PG{rom}@@", f"{pg:02d}")
assert "@@PG" not in html, "quedaron referencias de indice sin resolver"

with open(OUT_HTML, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"HTML  {os.path.getsize(OUT_HTML)/1e6:.2f} MB  ({len(PAGES)} paginas)")

src = os.path.abspath(OUT_HTML).replace("\\", "/")
dst = os.path.abspath(OUT_PDF).replace("\\", "/")
cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
       "--run-all-compositor-stages-before-draw", "--virtual-time-budget=40000",
       f"--print-to-pdf={dst}", f"file:///{src}"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
if os.path.exists(OUT_PDF):
    print(f"PDF   {os.path.getsize(OUT_PDF)/1e6:.2f} MB  ->  {OUT_PDF}")
else:
    print("FALLO:", (r.stderr or "")[-900:])
