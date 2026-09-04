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
import shutil
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
_cul = pd.read_csv("out/cultivos_nacional.csv", encoding="utf-8-sig")
_apr = pd.read_csv("out/agroexport_producto.csv", encoding="utf-8-sig",
                   dtype={"partida4": str})
_adu = pd.read_csv("out/agroexport_aduana.csv", encoding="utf-8-sig",
                   dtype={"codigo": str})
_adep = pd.read_csv("out/agroexport_departamento.csv", encoding="utf-8-sig")
_h3 = pd.read_csv("out/h3_r5.csv", encoding="utf-8-sig")
_clu2 = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
_hub2 = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")
_car = pd.read_csv("out/cartera_territorio.csv", encoding="utf-8-sig")
_carh = pd.read_csv("out/cartera_hub.csv", encoding="utf-8-sig")
CAR_UBI = int(pd.read_csv("out/cartera_empresa.csv", encoding="utf-8-sig",
                          usecols=["ruc"]).shape[0])
CAR_EMP = int(_car.empresas.sum())
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
  <p class="deck">El informe responde cuatro preguntas en orden: cuánto vale el
     mercado, quién es cliente, dónde empezar y qué se le vende. Después vienen la
     geometría del territorio comercial y un atlas con una ficha por cada una de
     las 24 regiones agrícolas del país.</p>

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
        <span class="desc">Priorización de las 24 regiones, escenarios de captura,
        la capa de prospección con nombre propio y el mercado vecino de
        importación.</span></li>
    <li><span class="n">V</span><span class="t">Qué se cultiva y por dónde sale</span>
        <span class="d"></span><span class="p">@@PGV@@</span>
        <span class="desc">Los {len(_cul)} cultivos y el mercado de insumos que
        implican, las {len(_apr)} partidas agroexportadas y las {len(_adu)} aduanas de
        salida.</span></li>
    <li><span class="n">VI</span><span class="t">La geometría del mercado</span>
        <span class="d"></span><span class="p">@@PGVI@@</span>
        <span class="desc">La grilla hexagonal, los territorios de venta que emergen
        de la densidad, el orden de apertura de centros y la cartera con nombre
        propio de cada territorio.</span></li>
    <li><span class="n">VII</span><span class="t">Atlas regional</span>
        <span class="d"></span><span class="p">@@PGVII@@</span>
        <span class="desc">Ficha por región: mapa de sectores, métricas de mercado,
        mezcla de cultivos y lectura comercial.</span></li>
    <li><span class="n">VIII</span><span class="t">Metodología y fuentes</span>
        <span class="d"></span><span class="p">@@PGVIII@@</span>
        <span class="desc">Cadena de cálculo, contraste con aduanas y limitaciones
        declaradas.</span></li>
  </ul>

  <div class="note brass">
    <span class="h">Nota sobre el estatus de las cifras</span>
    <p>Ninguna de las cifras de mercado de este informe es una estadística oficial.
    Son estimaciones construidas sobre fuentes oficiales, con supuestos declarados en
    la parte VIII y contrastadas contra datos de importación de aduanas. Los datos
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
        "ordena, dimensiona la captura posible, baja del territorio al nombre "
        "propio del prospecto y mide el mercado vecino que el mismo cliente "
        "ya compra afuera.",
        ["Priorización", "Escenarios de captura", "Prospección",
         "El mercado vecino"])

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
        {EMP_IMP} importación y {EMP_COM} operan como trading. Esa lectura por
        nombre es solo indicativa: el dato firme viene de los registros aduaneros,
        que SUNAT sí publica a nivel de empresa y se analizan en la página
        siguiente.</p>
      </div>
      <p>El padrón reducido tampoco incluye el código CIIU de actividad, que SUNAT
      solo expone consultando RUC por RUC. La clasificación por nombre subestima:
      no ve a la empresa que opera bajo una razón social neutra.</p>
    </div>
  </div>


""", "Parte IV · Prospección")



# --------------------------------------------------- comercio exterior ----
_impo = pd.read_csv("out/comercio_importadores.csv", encoding="utf-8-sig",
                    dtype={"ruc": str})
_expo = pd.read_csv("out/comercio_exportadores.csv", encoding="utf-8-sig",
                    dtype={"ruc": str})
_prot = _impo[_impo.rubro == "Proteccion de cultivos"].sort_values(
    "fob", ascending=False)
_fert = _impo[_impo.rubro == "Fertilizantes"]
_impo_s = _impo.sort_values("fob", ascending=False)
_tot_i = _impo_s["fob"].sum()
_top10 = 100 * _impo_s.head(10)["fob"].sum() / _tot_i

page(f"""
  <span class="kicker">Parte IV · El mercado desde aduanas</span>
  <h2 class="title">Quién trae el insumo <em>y quién exporta la cosecha</em></h2>
  <p class="deck">SUNAT publica los microdatos de aduanas bajo la Ley de
     Transparencia: cada línea de despacho con RUC, partida, valor FOB, peso y
     país. Diez semanas dan el mapa competitivo y los mayores compradores.</p>

  <div class="kpis">
    <div><span class="v">{nf(len(_impo))}</span><span class="l">importadores<br>de insumos agrícolas</span></div>
    <div><span class="v">US$ {nf(_impo.fob_anual.sum()/1e6)} MM</span><span class="l">importación anualizada<br>valor CIF</span></div>
    <div><span class="v">{nf(len(_expo))}</span><span class="l">agroexportadores<br>con RUC verificado</span></div>
    <div><span class="v">{_top10:.0f}%</span><span class="l">lo concentran<br>10 importadores</span></div>
  </div>

  <div class="two" style="margin-top:6px">
    <div>
      <h3 class="rule">El set competitivo</h3>
      <p>La protección de cultivos mueve <b>US$ {nf(_prot.fob_anual.sum()/1e6)} MM</b>
      anuales CIF entre <b>{len(_prot)}</b> importadores. Son, a la vez, los
      proveedores a los que AgroJuntos compra y la competencia de su canal.</p>
      {table([[r["razon_social"][:30], f'{r["fob_anual"]/1e6:,.1f}',
               nf(r["tn"]), int(r["semanas"])]
              for _, r in _prot.head(6).iterrows()],
             ["Importador", "FOB anual MM", "Toneladas", "Sem."],
             ["l","r","r","r"], cls="tight")}
      <p class="sub">«Sem.» indica en cuántas de las diez semanas observadas la
      empresa registró importación: diez significa flujo continuo.</p>
    </div>
    <div>
      <h3 class="rule">Los mayores compradores</h3>
      <p>Los agroexportadores son el cliente más solvente del mercado: facturan en
      dólares, operan bajo certificación y gastan más insumo por hectárea que
      cualquier otro productor.</p>
      {table([[r["razon_social"][:30], f'{r["fob_anual"]/1e6:,.0f}',
               int(r["destinos"])]
              for _, r in _expo.head(6).iterrows()],
             ["Agroexportador", "FOB anual MM", "Países"],
             ["l","r","r"], cls="tight")}

      <div class="note brass">
        <span class="h">Corrección respecto de una versión anterior</span>
        <p>Una versión previa de este informe afirmaba que los registros aduaneros
        a nivel de empresa no eran de descarga pública en el Perú. <b>Es
        incorrecto.</b> SUNAT los publica en aduanet.gob.pe/aduanas/informae como
        archivos DBF semanales, en cumplimiento de la Ley 27806. Las cifras de
        esta página provienen de esa fuente.</p>
      </div>
    </div>
  </div>

  <h3 class="rule">De dónde viene el fertilizante</h3>
  <p>El fertilizante peruano es casi enteramente importado y depende de
  <b>Rusia en un 30%</b> de su valor, seguida de China (16%), Colombia (7%) y
  Arabia Saudita (6%). Ese es el origen de la volatilidad de precio que enfrenta
  el productor —y que un canal con crédito puede amortiguar.</p>
  <p class="sub">Diez semanas de registros, junio a agosto de 2026. El anualizado
  extrapola ese período sin corregir estacionalidad, de modo que debe leerse como
  orden de magnitud.</p>
""", "Parte IV · El mercado desde aduanas")
# --------------------------------------------- lo que el agro importa ------
# El mercado vecino al que AgroJuntos ya vende: equipo, semilla, riego,
# poscosecha y alimento balanceado, del mismo manifiesto de aduanas.
_imc = pd.read_csv("out/import_agro_categoria.csv", encoding="utf-8-sig")
_img = pd.read_csv("out/import_agro_glosa.csv", encoding="utf-8-sig")
_imx = pd.read_csv("out/import_agro_excluidas.csv", encoding="utf-8-sig",
                   dtype={"partida": str})
_imr = pd.read_csv("out/import_agro_referencia.csv", encoding="utf-8-sig")
_iml = pd.read_csv("out/import_agro_lineas.csv", encoding="utf-8-sig",
                   dtype={"ruc": str})
_iml = _iml[_iml.categoria != "referencia"]

_imcon = _imc[_imc.lineas > 0]
IMP_A = _imcon.fob_anual.sum()
INS_A = _imr.fob_anual.sum()
# Las dos materias primas a granel son otro negocio: no las compra un
# agricultor sino cuatro comercializadoras internacionales, y dejarlas dentro
# tapa el mercado que si se parece al de AgroJuntos.
_gran = _img[_img.glosa.isin(["Maíz amarillo duro en grano", "Torta de soya"])]
GRAN_A = _gran.fob_anual.sum()
SIN_GRAN = IMP_A - GRAN_A
# La razon social no se recorta a un numero de caracteres: cortar
# «CARGILL AMERICAS PERU S.R.L.» en «Cargill Americas P» deja basura en la
# pagina. Se quitan la forma societaria y el pais, que no informan nada.
_SUF = ("S.R.L.", "S.A.C.", "S.A.A.", "S.A.", "E.I.R.L.", "SRL", "SAC", "SA",
        "SOCIEDAD ANONIMA CERRADA", "SOCIEDAD ANONIMA", "DEL PERU", "PERU")


def marca(nombre):
    n = " ".join(str(nombre).upper().split())
    cambio = True
    while cambio:
        cambio = False
        for suf in _SUF:
            if n.endswith(" " + suf):
                n, cambio = n[: -len(suf) - 1].rstrip(" ,."), True
    # Las siglas cortas se quedan en mayuscula: «Adm Andina» no es nadie.
    return " ".join(t if len(t) <= 3 else cap(t) for t in n.split())


_gtop = (_iml[_iml.categoria == "ganaderia"].groupby("razon_social")
         .fob_usd.sum().nlargest(4))
_gpais = (_iml[_iml.categoria == "ganaderia"].groupby("pais_origen")
          .fob_usd.sum().nlargest(3))
_PAIS = {"AR": "Argentina", "BO": "Bolivia", "PY": "Paraguay",
         "US": "Estados Unidos", "BR": "Brasil"}

IMP_ROWS = []
for _, r in _imcon.sort_values("fob_usd", ascending=False).iterrows():
    _g = _img[_img.categoria == r["categoria"]].nlargest(1, "fob_usd")
    IMP_ROWS.append([r["nombre"], f'{r["fob_anual"]/1e6:,.0f}',
                     f'{r["fob_usd"]/1e6:,.1f}', nf(r["toneladas"]),
                     int(r["empresas"]), int(r["partidas"]),
                     _g.glosa.iat[0] if len(_g) else "—",
                     f'{100*r["fob_usd"]/_imcon.fob_usd.sum():.1f}%'])
for _, r in _imc[_imc.lineas == 0].iterrows():
    IMP_ROWS.append([r["nombre"], "—", "—", "—", "—", "—",
                     "no cruza una aduana", "—"])
IMP_FOOT = ["Seis categorías con mercancía", f"{IMP_A/1e6:,.0f}",
            f'{_imcon.fob_usd.sum()/1e6:,.1f}', nf(_imcon.toneladas.sum()),
            nf(_iml.ruc.nunique()), nf(_imcon.partidas.sum()), "", "100%"]
page(f"""
  <span class="kicker">Parte IV · El mercado vecino</span>
  <h2 class="title">Lo que el agro importa <em>además del insumo</em></h2>
  <p class="deck">El mismo manifiesto que identifica al importador de
     fertilizante dice qué más compra el agro afuera. Es la respuesta a hasta
     dónde estira un catálogo sin cambiar de cliente.</p>

  <div class="kpis">
    <div><span class="v">{usd(IMP_A)}</span><span class="l">importación agrícola<br>anualizada · seis categorías</span></div>
    <div><span class="v">{usd(SIN_GRAN)}</span><span class="l">sin el granel de<br>alimento balanceado</span></div>
    <div><span class="v">{usd(INS_A)}</span><span class="l">fertilizante y fitosanitario<br>lo que ya se mide</span></div>
    <div><span class="v">{nf(_iml.ruc.nunique())}</span><span class="l">empresas importadoras<br>con RUC</span></div>
  </div>

  {table(IMP_ROWS,
         ["Categoría", "FOB anual MM", "FOB 10 sem", "Toneladas", "Empresas",
          "Partidas", "Mayor componente", "% del total"],
         ["l","r","r","r","r","r","l","r"], foot=IMP_FOOT)}
  <p class="sub">Diez semanas de manifiestos, junio a agosto de 2026. Se
  clasifica a la longitud de partida que cada caso pide: a cuatro dígitos
  <b>8701</b> junta el tractor agrícola con el tractocamión —21 contra 137 MM—
  y <b>3002</b> la vacuna humana con la veterinaria.</p>

  <div class="two" style="margin-top:4px">
    <div>
      <div class="note brass">
        <span class="h">El mercado vecino pesa lo mismo que el propio</span>
        <p>Descontado el granel, las seis categorías suman
        <b>{usd(SIN_GRAN)}</b> al año contra los <b>{usd(INS_A)}</b> de
        fertilizante y fitosanitario. Es un mercado del mismo tamaño, comprado
        por el mismo cliente y por el mismo corredor logístico. La pregunta
        que abre no es si hay demanda, sino cuánto catálogo aguanta la
        operación.</p>
      </div>
    </div>
    <div>
      <div class="note warn">
        <span class="h">Ganadería es granel, y el granel es de cuatro</span>
        <p>De los US$ {_imc[_imc.categoria=="ganaderia"].fob_usd.iat[0]/1e6:,.0f} MM
        de la categoría mayor, <b>{100*_gran.fob_usd.sum()/_imc[_imc.categoria=="ganaderia"].fob_usd.iat[0]:.0f}%</b>
        son maíz amarillo y torta de soya, que traen
        {", ".join(marca(x) for x in _gtop.index[:4])} —el
        {100*_gtop.sum()/_imc[_imc.categoria=="ganaderia"].fob_usd.iat[0]:.0f}% de
        la categoría— desde {", ".join(_PAIS.get(p, p) for p in _gpais.index)}.
        Es comercio de commodities, no venta de canal: lo que sí lo es
        —sanidad animal, avicultura, ordeño— son US$
        {(_imc[_imc.categoria=="ganaderia"].fob_usd.iat[0]-_gran.fob_usd.sum())/1e6:,.0f} MM.</p>
      </div>
    </div>
  </div>

  <p class="sub" style="margin-top:2px"><b>Servicios agrícolas y venta de
  campos van en cero a propósito:</b> no son mercancía y no dejan rastro en un
  registro aduanero. Se quedan en la tabla para que la ausencia se vea.
  Dimensionarlos exige otra fuente —padrón de SUNAT por CIIU y registros
  públicos— y no se estiman aquí.</p>
""", "Parte IV · El mercado vecino")


# ========================================================= PARTE V =========
# Que se cultiva y por donde sale. El modelo regional dice cuanto vale cada
# region; no dice que se siembra en ella. Para vender insumos eso es la mitad
# de la conversacion: no se le ofrece lo mismo a un valle de arroz que a uno
# de palta, y el mes de compra sale del cultivo, no del departamento.
_cul = _cul.sort_values("usd_nac", ascending=False).reset_index(drop=True)
_cul["ac"] = 100 * _cul.usd_nac.cumsum() / _cul.usd_nac.sum()
CUL_USD, CUL_HA = _cul.usd_nac.sum(), _cul.ha_nac.sum()
# La mediana del panel del INEI es el valor que reciben los cultivos sin costeo
# propio. Se identifica por la moda porque es, por construccion, el unico valor
# que se repite entre cultivos distintos.
_MED = _cul.usd_ha.mode().iat[0]
_sinc = _cul[_cul.usd_ha == _MED]
_arroz, _cafe = _cul.iloc[0], _cul[_cul.cultivo.str.startswith("Caf")].iloc[0]
_palta = _cul[_cul.cultivo == "Palta"].iloc[0]

_apr = _apr.sort_values("fob_usd", ascending=False).reset_index(drop=True)
_apr["ac"] = 100 * _apr.fob_usd.cumsum() / _apr.fob_usd.sum()
_apr["fob_kg"] = _apr.fob_usd / _apr.kg
EXP_FOB = _apr.fob_usd.sum()
_ber = _apr[_apr.partida4 == "0810"].iloc[0]
_cit = _apr[_apr.partida4 == "0805"].iloc[0]

_adu = _adu.sort_values("fob_usd", ascending=False).reset_index(drop=True)
_adu["ac"] = 100 * _adu.fob_usd.cumsum() / _adu.fob_usd.sum()
_chancay = _adu[_adu.codigo == "370"].iloc[0]
_aereo = _adu[_adu.codigo == "235"].iloc[0]

divider("V", "Qué se cultiva <em>y por dónde sale</em>",
        "El modelo dice cuánto vale cada región. Esta parte dice qué se siembra "
        "en ella, qué se exporta y por qué puerto sale: el cultivo decide el "
        "producto que se ofrece y el mes en que hay que tenerlo en almacén.",
        ["Los cultivos", "La agroexportación", "Los puntos de salida"])

CUL_ROWS = [[r["cultivo"], nf(r["ha_nac"]), f'US$ {nf(r["usd_ha"])}',
             f'{r["usd_nac"]/1e6:,.0f}', int(r["deps"]), cap(r["dep_lider"]),
             f'{r["pct_lider"]:.0f}%', f'{r["ac"]:.0f}%']
            for _, r in _cul.head(10).iterrows()]
CUL_FOOT = [f"Perú · {nf(len(_cul))} cultivos", nf(CUL_HA),
            f"US$ {nf(CUL_USD/CUL_HA)}", f"{CUL_USD/1e6:,.0f}", "24", "", "",
            "100%"]
page(f"""
  <span class="kicker">Parte V · Los cultivos</span>
  <h2 class="title">El mercado no compra hectáreas, <em>compra cultivos</em></h2>
  <p class="deck">Una hectárea de pimiento piquillo demanda US$ {nf(_cul.usd_ha.max())}
     de insumo al año; una de pijuayo, US$ {nf(_cul.usd_ha.min())}. Son
     {_cul.usd_ha.max()/_cul.usd_ha.min():.0f} veces de diferencia sobre la misma
     unidad de superficie. Un mapa de hectáreas, sin la mezcla de cultivos, no
     dice qué se le puede vender a cada una.</p>

  <div class="kpis">
    <div><span class="v">{nf(len(_cul))}</span><span class="l">cultivos con superficie<br>declarada en el anuario</span></div>
    <div><span class="v">{nf(CUL_HA/1e6,2)} M ha</span><span class="l">superficie que sostiene<br>la demanda modelada</span></div>
    <div><span class="v">{usd(CUL_USD)}</span><span class="l">mercado de insumos<br>que esa mezcla implica</span></div>
    <div><span class="v">{_cul.ac.iat[9]:.0f}%</span><span class="l">lo explican<br>diez cultivos</span></div>
  </div>

  <h3 class="rule">Los diez cultivos que explican el
     {_cul.ac.iat[9]:.0f}% del mercado</h3>
  {table(CUL_ROWS,
         ["Cultivo", "Hectáreas", "Gasto/ha", "Mercado MM", "Regiones",
          "Región líder", "% del cultivo", "% acum."],
         ["l","r","r","r","r","l","r","r"], foot=CUL_FOOT)}
  <p class="sub"><b>Gasto/ha:</b> desembolso anual en fertilizante y fitosanitario
  por hectárea del cultivo, del costeo del INEI. <b>Regiones:</b> en cuántas de las
  24 aparece con superficie. <b>% del cultivo:</b> qué parte de su superficie
  nacional está en la región líder — un cultivo concentrado se atiende desde un
  almacén; uno disperso, no.</p>

  <div class="two" style="margin-top:4px">
    <div>
      <div class="note">
        <span class="h">Dos lecturas opuestas del mismo cuadro</span>
        <p>El arroz encabeza por mercado —US$ {nf(_arroz.usd_nac/1e6)} MM— con
        {_arroz.ha_nac/1e3:.0f} mil hectáreas. El café tiene prácticamente la misma
        superficie y vale la cuarta parte, porque gasta US$ {nf(_cafe.usd_ha)} por
        hectárea contra {nf(_arroz.usd_ha)}. La palta, con {_palta.ha_nac/1e3:.0f}
        mil hectáreas —seis veces menos que el arroz— ya vale
        US$ {nf(_palta.usd_nac/1e6)} MM y crece. Ordenar por superficie y ordenar
        por mercado dan dos listas distintas.</p>
      </div>
    </div>
    <div>
      <div class="note warn">
        <span class="h">Qué tan firme es el gasto por cultivo</span>
        <p>El costeo del INEI cubre 73 cultivos. Los otros <b>{len(_sinc)} de
        {len(_cul)}</b> reciben la mediana del panel, US$ {nf(_MED)} por hectárea:
        son el {100*_sinc.ha_nac.sum()/CUL_HA:.0f}% de la superficie y el
        {100*_sinc.usd_nac.sum()/CUL_USD:.0f}% del valor. Los del cuadro que
        muestran exactamente US$ {nf(_MED)} son de ese grupo: sirve para el
        agregado, no para cotizar ese cultivo.</p>
      </div>
    </div>
  </div>
""", "Parte V · Los cultivos")

APR_ROWS = [[r["partida4"], r["producto"], f'{r["fob_usd"]/1e6:,.1f}',
             nf(r["kg"]/1e6, 1), int(r["empresas"]), int(r["destinos"]),
             f'{r["fob_kg"]:,.2f}', f'{r["ac"]:.0f}%']
            for _, r in _apr.head(12).iterrows()]
APR_FOOT = ["", f"{nf(len(_apr))} partidas", f"{EXP_FOB/1e6:,.1f}",
            nf(_apr.kg.sum()/1e6, 1), "", "",
            f"{EXP_FOB/_apr.kg.sum():,.2f}", "100%"]
page(f"""
  <span class="kicker">Parte V · La agroexportación</span>
  <h2 class="title">Seis partidas explican <em>tres cuartas partes</em>
     de lo que sale</h2>
  <p class="deck">Los mismos manifiestos que identifican al importador de insumo
     identifican, del otro lado, qué producto agrícola sale del país, en qué
     volumen y hacia cuántos destinos. Es la demanda final que arrastra al
     insumo.</p>

  <div class="kpis">
    <div><span class="v">{usd(EXP_FOB)}</span><span class="l">agroexportado en diez<br>semanas · FOB medido</span></div>
    <div><span class="v">{nf(len(_apr))}</span><span class="l">partidas arancelarias<br>a cuatro dígitos</span></div>
    <div><span class="v">{nf(len(_expo))}</span><span class="l">empresas exportadoras<br>con RUC verificado</span></div>
    <div><span class="v">{_apr.ac.iat[5]:.0f}%</span><span class="l">lo explican<br>seis partidas</span></div>
  </div>

  <h3 class="rule">Las doce partidas mayores</h3>
  {table(APR_ROWS,
         ["Partida", "Producto", "FOB MM", "Miles t", "Empresas", "Destinos",
          "US$/kg", "% acum."],
         ["l","l","r","r","r","r","r","r"], foot=APR_FOOT)}
  <p class="sub">Diez semanas de manifiestos, junio a agosto de 2026. «Empresas» y
  «destinos» no se suman entre partidas: una misma empresa exporta varias, y un
  mismo país recibe varias.</p>

  <div class="two" style="margin-top:4px">
    <div>
      <div class="note">
        <span class="h">El valor está en el kilo, no en el tonelaje</span>
        <p>El arándano sale a US$ {_ber.fob_kg:,.2f} por kilo y los cítricos a
        US$ {_cit.fob_kg:,.2f}. Con {100*_ber.kg/_cit.kg:.0f}% del tonelaje
        cítrico, el arándano factura {_ber.fob_usd/_cit.fob_usd:.1f} veces más.
        Ese margen es el que paga programas de nutrición y sanidad caros: es donde
        el insumo premium tiene demanda real, y no donde hay más hectáreas.</p>
      </div>
    </div>
    <div>
      <div class="note">
        <span class="h">Por qué la partida y no el nombre comercial</span>
        <p>El manifiesto trae una descripción libre escrita por el declarante
        —«PALTAS FRESCAS EN CAJAS VARIEDAD: HASS»—, útil para leer pero inservible
        para agregar. La partida NANDINA a cuatro dígitos sí agrupa, al costo de
        juntar lo que el arancel junta: la 0804 es palta, mango, dátil y piña en
        una sola línea.</p>
      </div>
    </div>
  </div>
""", "Parte V · La agroexportación")

ADU_ROWS = [[r["codigo"], r["aduana"], f'{r["fob_usd"]/1e6:,.1f}',
             nf(r["kg"]/1e6, 1), int(r["empresas"]), r["producto_lider"],
             f'{r["pct_lider"]:.0f}%', r["via_principal"], f'{r["ac"]:.1f}%']
            for _, r in _adu.head(12).iterrows()]
ADU_FOOT = ["", f"{len(_adu)} aduanas", f"{_adu.fob_usd.sum()/1e6:,.1f}",
            nf(_adu.kg.sum()/1e6, 1), "", "", "", "", "100%"]
page(f"""
  <span class="kicker">Parte V · Los puntos de salida</span>
  <h2 class="title">Cuatro puertos mueven <em>el {_adu.ac.iat[3]:.0f}%</em>
     de la agroexportación</h2>
  <p class="deck">La aduana de embarque dice qué corredor logístico usa cada
     región productora. Es el mismo por el que sube el insumo.</p>

  {table(ADU_ROWS,
         ["Cód.", "Aduana de embarque", "FOB MM", "Miles t", "Empresas",
          "Producto líder", "% de la aduana", "Vía", "% acum."],
         ["l","l","r","r","r","l","r","l","r"], foot=ADU_FOOT)}
  <p class="sub">Las doce aduanas listadas son el {_adu.ac.iat[11]:.2f}% del FOB;
  las tres restantes no llegan a US$ 1 MM entre las tres. Los nombres salen de la
  Tabla 4 del Anexo 01 de SUNAT (RS 040-2022), no de deducirlos: un código mal
  atribuido convierte un puerto en otro.</p>

  <div class="two" style="margin-top:6px">
    <div>
      <h3 class="rule">Chancay ya es el sexto punto de salida</h3>
      <p>El código 370 no figura en el anexo de 2022 porque entonces no existía. Es
      Chancay, habilitada el <b>21 de octubre de 2024</b> por la RS 000192-2024, y
      en las diez semanas observadas movió
      <b>US$ {_chancay.fob_usd/1e6:,.1f} MM</b> con
      <b>{int(_chancay.empresas)} empresas</b>: más exportadores distintos que
      Salaverry, Chiclayo y Chimbote juntos. Para un canal de insumos un puerto
      nuevo es un corredor nuevo, y cambia dónde conviene tener inventario.</p>

      <p>Lo aéreo tampoco es marginal: la Aérea del Callao mueve
      US$ {_aereo.fob_usd/1e6:,.0f} MM con {int(_aereo.empresas)} empresas y apenas
      {_aereo.kg/1e6:,.1f} mil toneladas, que es el canal del perecible de altísimo
      valor. Tumbes, Tacna y Desaguadero salen por carretera hacia Ecuador, Chile y
      Bolivia.</p>
    </div>
    <div>
      <div class="note warn">
        <span class="h">Lima aparece grande porque ahí está la oficina</span>
        <p>Lima concentra el {100*_adep.fob_usd.iat[0]/_adep.fob_usd.sum():.0f}%
        del FOB y {int(_adep.empresas.iat[0])} empresas, pero no cultiva esa
        proporción: el UBIGEO del manifiesto resultó inservible —solo el 3% del FOB
        lo trae— y la región sale del domicilio fiscal del padrón. <b>Domicilio
        fiscal no es lugar de cultivo.</b> Para ubicar producción sirve la aduana
        de embarque; para ubicar al comprador, el padrón.</p>
      </div>
    </div>
  </div>
""", "Parte V · Los puntos de salida")


# ======================================================== PARTE VI =========
# La geometria del mercado. El sector estadistico mide entre 200 y 30,000 ha,
# de modo que comparar dos zonas mirando sectores mezcla densidad con tamano
# de la unidad de medida. La grilla hexagonal tiene area constante y separa
# una cosa de la otra.
AREA_PE = 1_285_216  # km2, superficie continental del Peru

_h3 = _h3.sort_values("sam_usd", ascending=False).reset_index(drop=True)
_h3["ac"] = _h3.sam_usd.cumsum() / _h3.sam_usd.sum()
_h3con = _h3[_h3.sam_usd > 0]
KM2 = _h3.km2.mean()


def celdas_para(p):
    """Cuantas celdas, de mayor a menor, acumulan la fraccion p del SAM."""
    return int((_h3.ac < p).sum()) + 1


C25, C50, C80 = celdas_para(.25), celdas_para(.5), celdas_para(.8)

# Las capas geoespaciales guardan el departamento en mayusculas y sin tildes.
# El resto del informe lo escribe acentuado, asi que se recupera del modelo.
def _sinac(x):
    return unicodedata.normalize("NFKD", str(x)).encode(
        "ascii", "ignore").decode().upper()


DEP_OK = {_sinac(d): d for d in v3.dep}
_clu2["dep_ok"] = _clu2.dep.map(lambda d: DEP_OK.get(_sinac(d), cap(d)))
UMB = sorted(_hub2.umbral_h.unique())


def hubk(u, k):
    g = _hub2[(_hub2.umbral_h == u) & (_hub2.k == k)]
    return g.iloc[0] if len(g) else None


divider("VI", "La geometría <em>del mercado</em>",
        "Sobre las capas anteriores se construyen tres análisis geométricos: una "
        "grilla de área constante que permite comparar zonas, los territorios de "
        "venta que emergen de la densidad, el orden de apertura de centros de "
        "distribución que maximiza la cobertura, y la cartera con nombre propio "
        "que cae dentro de cada territorio.",
        ["La grilla hexagonal", "Centros de distribución", "La cartera del territorio"])

CLU_ROWS = [[int(r["rank"]), r["dep_ok"], cap(r["provincias"]),
             f'{r["sam_usd"]/1e6:,.1f}', nf(r["clientes"]),
             f'US$ {nf(r["sam_por_cliente"])}', f'{r["extension_km"]:.0f} km',
             f'{r["horas_capital"]:.1f} h', f'{r["pct_acum"]:.0f}%']
            for _, r in _clu2.head(10).iterrows()]
CLU_FOOT = ["", f"{len(_clu2)} territorios", "",
            f'{_clu2.sam_usd.sum()/1e6:,.1f}', nf(_clu2.clientes.sum()), "",
            "", "", f'{_clu2.pct_sam.sum():.0f}%']
page(f"""
  <span class="kicker">Parte VI · La grilla hexagonal</span>
  <h2 class="title"><em>{nf(C50)} celdas</em> concentran la mitad del mercado
     atendible</h2>
  <p class="deck">Los sectores estadísticos miden entre 200 y 30,000 hectáreas, de
     modo que comparar dos zonas mirando sectores mezcla la densidad del mercado
     con el tamaño de la unidad de medida. La grilla hexagonal H3 corrige eso:
     todas las celdas miden lo mismo, {nf(KM2)} km², y lo único que varía entre
     ellas es el mercado.</p>

  <div class="kpis">
    <div><span class="v">{nf(len(_h3con))}</span><span class="l">celdas con mercado atendible<br>de {nf(KM2)} km² cada una</span></div>
    <div><span class="v">{nf(C25)}</span><span class="l">celdas reúnen el primer<br>cuarto del SAM</span></div>
    <div><span class="v">{nf(C50)}</span><span class="l">celdas reúnen<br>la mitad</span></div>
    <div><span class="v">{100*C50/len(_h3con):.0f}%</span><span class="l">del territorio con mercado<br>vale esa mitad</span></div>
  </div>

  <p>El primer cuarto del mercado cabe en <b>{nf(C25)} celdas</b> —unos
  {nf(C25*KM2/1e3,1)} mil km², el {100*C25*KM2/AREA_PE:.1f}% del país—. La mitad
  cabe en <b>{nf(C50)}</b> y el 80% en <b>{nf(C80)}</b>. La curva se aplana rápido:
  pasar de la mitad del mercado a los cuatro quintos exige multiplicar por
  <b>{C80/C50:.1f}</b> el territorio a cubrir, y cada celda añadida vale menos que
  la anterior.</p>

  <h3 class="rule">Los diez mayores territorios de venta</h3>
  {table(CLU_ROWS,
         ["#", "Región", "Provincias núcleo", "SAM MM", "Clientes",
          "SAM/cliente", "Extensión", "A capital", "% acum."],
         ["r","l","l","r","r","r","r","r","r"], foot=CLU_FOOT)}
  <p class="sub">DBSCAN con radio de 15 km sobre el 80% superior del mercado.
  <b>Extensión:</b> distancia de punta a punta del territorio. <b>A capital:</b>
  horas medias de sus celdas al centro provincial, ruteadas sobre la red vial.</p>

  <div class="note" style="margin-top:6px">
    <span class="h">Por qué agrupar sobre el 80% superior y no sobre el total</span>
    <p>Agrupando sobre todas las celdas, el algoritmo encadenaba el país entero en
    un solo núcleo de 2,000 km: la agricultura peruana es continua a lo largo de
    los valles y no deja huecos que corten la cadena. Restringido al 80% superior
    del mercado, el mismo radio da <b>{len(_clu2)} territorios</b>, de los cuales
    <b>{int(_clu2.visitable_en_dia.sum())} miden menos de 120 km</b> de punta a
    punta y se recorren en una sola salida. Los {len(_clu2)} juntos son el
    {_clu2.pct_sam.sum():.0f}% del mercado atendible del país.</p>
  </div>
""", "Parte VI · La grilla hexagonal")

HUB_ROWS = []
for _k in range(1, 7):
    _fila = [str(_k)]
    for _u in UMB:
        _h = hubk(_u, _k)
        _fila += [cap(_h["hub"]) if _h is not None else "—",
                  f'{_h["pct_sam"]:.1f}%' if _h is not None else "—"]
    HUB_ROWS.append(_fila)
H2, H4, H6 = [hubk(u, 6) for u in UMB]
KMAX2 = _hub2[_hub2.umbral_h == 2.0]
page(f"""
  <span class="kicker">Parte VI · Centros de distribución</span>
  <h2 class="title">El radio de operación decide la cobertura,
     <em>no el número de almacenes</em></h2>
  <p class="deck">Cobertura máxima por algoritmo voraz sobre las 129 ciudades
     capitales de provincia, evaluada contra tiempos ruteados sobre la red vial.
     La pregunta que responde no es cuántos centros abrir, sino qué tan lejos se
     acepta ir a entregar.</p>

  <div class="kpis">
    <div><span class="v">{H2["pct_sam"]:.0f}%</span><span class="l">del SAM cubren seis<br>centros, a dos horas</span></div>
    <div><span class="v">{H4["pct_sam"]:.0f}%</span><span class="l">los mismos seis,<br>a cuatro horas</span></div>
    <div><span class="v">{H6["pct_sam"]:.0f}%</span><span class="l">los mismos seis,<br>a seis horas</span></div>
    <div><span class="v">{H6["pct_sam"]/H2["pct_sam"]:.1f}×</span><span class="l">gana triplicar el radio,<br>sin abrir un almacén más</span></div>
  </div>

  <h3 class="rule">Orden óptimo de apertura y cobertura acumulada</h3>
  {table(HUB_ROWS,
         ["Centro #", "A 2 horas", "% SAM", "A 4 horas", "% SAM",
          "A 6 horas", "% SAM"],
         ["r","l","r","l","r","l","r"])}
  <p class="sub">Cada fila añade un centro al conjunto de la fila anterior y el
  porcentaje es acumulado. El orden se recalcula para cada umbral, así que no es
  la misma lista desplazada: con radio de dos horas conviene abrir primero en
  Chiclayo; con radio de cuatro, en San Pedro de Lloc.</p>

  <div class="two" style="margin-top:4px">
    <div>
      <div class="note">
        <span class="h">La intuición que el dato corrige</span>
        <p>Parece razonable suponer que abrir más almacenes cubre más mercado. Con
        radio de dos horas no ocurre: seis centros cubren
        <b>{H2["pct_sam"]:.0f}%</b> y hacen falta {int(KMAX2.k.max())} para llegar
        apenas al {KMAX2.pct_sam.max():.0f}%. La agricultura peruana está demasiado
        estirada a lo largo de los valles como para que un radio corto la
        alcance.</p>
      </div>
    </div>
    <div>
      <div class="note brass">
        <span class="h">Qué decisión se sigue de esto</span>
        <p>Con seis centros y radio de seis horas se llega al
        <b>{H6["pct_sam"]:.0f}%</b> del mercado atendible. La palanca no es el
        capital inmovilizado en almacenes, sino la capacidad de entrega a
        distancia: flota, ruta programada y tiempo de promesa. Un séptimo almacén
        aporta menos que extender el radio de los seis que ya existen.</p>
      </div>
    </div>
  </div>
""", "Parte VI · Centros de distribución")

CAR_ROWS = [[int(r["rank"]), r["territorio"], nf(r["empresas"]),
             nf(r["agroindustria"]), int(r["exportadores"]),
             f'{r["sam_usd"]/1e6:,.1f}', f'{r["empresas_por_mm"]:.0f}',
             r["hub"] if isinstance(r["hub"], str) else "—",
             f'{100*r["dentro_2h"]/r["empresas"]:.0f}%']
            for _, r in _car.head(10).iterrows()]
CAR_FOOT = ["", f"{len(_car)} territorios con cartera", nf(CAR_EMP),
            nf(_car.agroindustria.sum()), int(_car.exportadores.sum()),
            f'{_car.sam_usd.sum()/1e6:,.1f}',
            f'{CAR_EMP/(_car.sam_usd.sum()/1e6):.0f}', "",
            f'{100*_car.dentro_2h.sum()/CAR_EMP:.0f}%']
# El contraste se busca dentro de los diez que la tabla muestra: comparar el
# primero contra un territorio marginal de una fila que el lector no tiene
# delante convierte un hallazgo en un truco.
_diez = _car.head(10)
_ralo = _diez.nsmallest(1, "empresas_por_mm").iloc[0]
_denso = _diez.nlargest(1, "empresas_por_mm").iloc[0]
page(f"""
  <span class="kicker">Parte VI · La cartera del territorio</span>
  <h2 class="title">El territorio ya tiene <em>nombres propios</em></h2>
  <p class="deck">Hasta aquí el territorio era una mancha con un número. Cruzado
     el padrón contra la grilla, cada núcleo de venta trae su lista de empresas
     con RUC y el centro desde el que se lo sirve: del dónde vender al a quién
     visitar, sin una hoja de cálculo intermedia.</p>

  <div class="kpis">
    <div><span class="v">{nf(CAR_UBI)}</span><span class="l">empresas del padrón<br>ubicadas sobre la grilla</span></div>
    <div><span class="v">{nf(CAR_EMP)}</span><span class="l">caen dentro de alguno<br>de los territorios</span></div>
    <div><span class="v">{len(_car)} de {len(_clu2)}</span><span class="l">territorios tienen<br>al menos una empresa</span></div>
    <div><span class="v">{100*_car.dentro_2h.sum()/CAR_EMP:.0f}%</span><span class="l">de esa cartera está a menos<br>de dos horas de su centro</span></div>
  </div>

  <h3 class="rule">Los diez territorios de mayor mercado, con su cartera</h3>
  {table(CAR_ROWS,
         ["#", "Territorio", "Empresas", "Agroind.", "Agroexp.", "SAM MM",
          "Emp./MM", "Centro", "A &lt;2 h"],
         ["r","l","r","r","r","r","r","l","r"], foot=CAR_FOOT)}
  <p class="sub"><b>Emp./MM:</b> empresas formales por millón de dólares de
  mercado atendible. <b>Centro:</b> el almacén que sirve a la mayor parte de esa
  cartera. <b>A &lt;2 h:</b> qué parte de ella queda a menos de dos horas de él.</p>

  <div class="two" style="margin-top:4px">
    <div>
      <div class="note warn">
        <span class="h">El registro formal y el mercado no se superponen</span>
        <p>Los dos extremos están en la misma región. {_ralo.territorio} es el
        territorio <b>número {int(_ralo["rank"])}</b> del país por mercado
        —US$ {_ralo.sam_usd/1e6:,.1f} MM— y tiene {int(_ralo.empresas)} empresas
        inscritas: {_ralo.empresas_por_mm:.0f} por millón. {_denso.territorio}
        vale {_ralo.sam_usd/_denso.sam_usd:.0f} veces menos, tiene
        {int(_denso.empresas)} y es <b>{_denso.empresas_por_mm/_ralo.empresas_por_mm:.0f}
        veces más denso</b>. Donde el mercado es grande y el padrón está vacío el
        comprador es informal: ahí no sirve un directorio, sirve campo.</p>
      </div>
    </div>
    <div>
      <div class="note">
        <span class="h">Tener la cartera no es alcanzarla</span>
        <p>{_car.iloc[1].territorio} tiene {int(_car.iloc[1].empresas)} empresas y
        el {100*_car.iloc[1].dentro_2h/_car.iloc[1].empresas:.0f}% a menos de dos
        horas de su centro: es una ruta que se hace en el día.
        {_car.iloc[2].territorio} tiene {int(_car.iloc[2].empresas)} y
        <b>ninguna</b> dentro de ese radio —su centro más cercano es
        {_car.iloc[2].hub}, al otro lado de la sierra—. Son dos operaciones
        distintas con el mismo número de clientes en la tabla.</p>
      </div>
    </div>
  </div>

  <p class="sub" style="margin-top:2px">La empresa se ubica por el distrito de su
  domicilio fiscal: sirve para saber a quién visitar estando en el territorio, no
  para ubicar el fundo.</p>
""", "Parte VI · La cartera del territorio")


# ======================================================= PARTE VII ========
divider("VII", "Atlas <em>regional</em>",
        "Un pliego de dos hojas por cada una de las 24 regiones agrícolas: la "
        "ficha con estructura productiva, comportamiento de compra, costo de "
        "servir y mayores sectores, y frente a ella la lámina cartográfica de la "
        "región a página completa.",
        ["24 regiones", "Ficha y lámina", "Lectura comercial"])


def barras(items, total_ref):
    out = []
    for nombre, val, _ in items[:5]:
        w = 100 * val / total_ref if total_ref else 0
        out.append(f'<div class="fbar"><span class="nm">{cap(nombre)}</span>'
                   f'<span class="tr"><i style="width:{min(w,100):.0f}%"></i></span>'
                   f'<span class="vl">{nf(val/1e6,1)} MM</span></div>')
    return '<div class="fbars">' + "".join(out) + "</div>"


# ---------------------------------------------------- datos del atlas -----
def _slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


_FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
        "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima",
        "provconstdelcallao": "callao"}


def _key(s):
    return _FIX.get(_slug(s), _slug(s))


sec_d = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig",
                    usecols=["cod_se", "dep", "prov", "sector", "region_nat",
                             "ha_agricola", "s_ha_cosechada", "s_sam_usd",
                             "s_clientes_sam"])
_rut = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig",
                   usecols=["cod_se", "horas_capital_real", "horas_puerto_real",
                            "puerto_maritimo"])
sec_d = sec_d.merge(_rut, on="cod_se", how="left")
sec_d["k"] = sec_d["dep"].map(_key)

_clu = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
_clu["k"] = _clu["dep"].map(_key)
_hub = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")
_hub = _hub[_hub.umbral_h == _hub.umbral_h.min()]
_hub["k"] = _hub["region"].map(_key)
_emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                   usecols=["dep", "exporta", "importa"])
_emp["k"] = _emp["dep"].map(_key)
EMPD = _emp.groupby("k").agg(empresas=("dep", "size"),
                             exporta=("exporta", "sum"),
                             importa=("importa", "sum")).to_dict("index")
V3 = v3.set_index("k")
ESTR = est_r.set_index("k")
M12 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct",
       "Nov", "Dic"]
if len(pros):
    pros["k"] = pros["dep"].map(_key)


def calendario(k):
    """Twelve bars: when the region actually buys."""
    if k not in ESTR.index:
        return ""
    fila = ESTR.loc[k]
    vals = [float(fila[m]) for m in M12]
    mx = max(vals) or 1
    top4 = sorted(range(12), key=lambda i: -vals[i])[:4]
    barras = "".join(
        f'<span class="cb{" pico" if i in top4 else ""}">'
        f'<i style="height:{100 * v / mx:.0f}%"></i><b>{m[0]}</b></span>'
        for i, (m, v) in enumerate(zip(M12, vals)))
    return f'<div class="cal">{barras}</div>'


def estructura(r):
    """How the land is split between farm sizes, and therefore who to sell to."""
    tramos = [("0–5 ha", r.get("ua_micro_0_5"), "#CBD4C6"),
              ("5–20 ha", r.get("ua_pequeno_5_20"), "#8FAE9B"),
              ("20–100 ha", r.get("ua_mediano_20_100"), "#3B7A63"),
              ("100+ ha", r.get("ua_grande_100_mas"), "#0F4C3F")]
    tramos = [(n, float(v), c) for n, v, c in tramos
              if v is not None and pd.notna(v) and float(v) > 0]
    tot = sum(v for _, v, _ in tramos) or 1
    seg = "".join(f'<i style="width:{100 * v / tot:.2f}%;background:{c}"></i>'
                  for _, v, c in tramos)
    leg = "".join(f'<span><b style="background:{c}"></b>{n} · '
                  f'{100 * v / tot:.0f}%</span>' for n, v, c in tramos)
    return f'<div class="stack">{seg}</div><div class="stackleg">{leg}</div>'


def dl(filas):
    return '<div class="dl">' + "".join(
        f'<div><span class="n">{n}</span><span class="v">{v}</span></div>'
        for n, v in filas) + "</div>"


def sectores_tabla(k, n=9):
    """Where inside the region the money is, and how far it is from the capital."""
    s = sec_d[sec_d.k == k]
    top = s.nlargest(n, "s_sam_usd")
    filas = []
    for _, t in top.iterrows():
        h = t["horas_capital_real"]
        filas.append([cap(t["sector"])[:24], cap(t["prov"])[:15],
                      nf(t["ha_agricola"]), f"{t['s_sam_usd'] / 1e6:,.2f}",
                      nf(t["s_clientes_sam"]),
                      "s/d" if pd.isna(h) else f"{h:,.1f}"])
    pie = [f"Toda la región · {len(s)} sectores", f"{s.prov.nunique()} prov.",
           nf(s.ha_agricola.sum()), f"{s.s_sam_usd.sum() / 1e6:,.1f}",
           nf(s.s_clientes_sam.sum()), ""]
    return table(filas, ["Sector estadístico", "Provincia", "Ha agrícolas",
                         "Mercado US$ MM", "Clientes", "h a capital"],
                 ["l", "l", "r", "r", "r", "r"], pie, cls="tight")


ARQ = {
    "Venta directa consultiva":
        "pocos compradores grandes y accesibles: se atiende con vendedor propio "
        "y contrato de campaña, no con red de terceros",
    "Red de canal":
        "demasiados compradores y demasiado dispersos para una fuerza de venta "
        "propia: el margen se defiende apoyándose en distribuidores locales",
    "Campaña estacional":
        "la demanda se juega en pocas semanas: el stock y el crédito tienen que "
        "estar colocados antes del pico, no durante",
    "Operación mixta":
        "cabeceras de valle con volumen y una periferia dispersa: vendedor propio "
        "en las primeras, canal en la segunda",
    "Inviable por ahora":
        "el costo de servir se come el margen a los precios actuales; entra "
        "cuando haya un cliente ancla que pague el viaje",
}


def lectura_larga(r, v):
    """Four sentences a salesperson can act on, built from this region's numbers."""
    dep = cap(r["dep"])
    tk, cl = r["ticket_anual"], r["clientes_sam"]
    cred, fert = 100 * r["tasa_credito"], 100 * r["tasa_fert"]
    p = []
    p.append(f"<b>{dep}</b> vale <b>{usd(r['sam_usd'])}</b> al año en "
             f"fertilizante y fitosanitario sobre <b>{nf(cl)}</b> compradores "
             f"de más de cinco hectáreas, un ticket de <b>US$ {nf(tk)}</b> por "
             f"cliente y año.")

    if fert >= 60:
        p.append(f"El <b>{fert:.0f}%</b> de las unidades ya fertiliza: la "
                 "demanda está instalada y lo que se disputa es el proveedor.")
    elif fert <= 28:
        p.append(f"Solo el <b>{fert:.0f}%</b> fertiliza, de modo que una parte "
                 "grande del potencial no es venta sino conversión, y llega con "
                 "el ciclo de adopción que eso implica.")
    else:
        p.append(f"Fertiliza el <b>{fert:.0f}%</b> y aplica fitosanitario el "
                 f"<b>{100 * r['tasa_pest']:.0f}%</b>: mercado a medio formar, "
                 "con espacio tanto para captura como para conversión.")

    if cred >= 10:
        p.append(f"El <b>{cred:.0f}%</b> ya compra a crédito —"
                 f"<b>{nf(r['compran_a_credito'])}</b> unidades—, la puerta de "
                 "entrada natural para el financiamiento embebido.")
    elif cred <= 3:
        p.append(f"Apenas el <b>{cred:.0f}%</b> compra a crédito, así que la "
                 "primera venta es al contado y el crédito se ofrece después, "
                 "sobre historial propio.")
    else:
        p.append(f"El <b>{cred:.0f}%</b> compra a crédito, por debajo del "
                 "promedio útil: el financiamiento abre conversación pero no "
                 "cierra la venta por sí solo.")

    if v is not None:
        p.append(f"Logísticamente, el <b>{v['pct_bajo_2h']:.0f}%</b> de sus "
                 f"sectores está a menos de dos horas de la capital regional y "
                 f"el <b>{v['pct_sobre_4h']:.0f}%</b> a más de cuatro, con un "
                 f"costo de viaje de <b>US$ {nf(v['costo_viaje'])}</b> por "
                 f"visita; el pico de compra cae en <b>{v['mes_pico']}</b> y "
                 f"cuatro meses concentran el <b>{v['pct_top4']:.0f}%</b> del "
                 "año.")
        p.append(f"Arquetipo: <b>{v['arquetipo'].lower()}</b> — "
                 f"{ARQ.get(v['arquetipo'], 'sin lectura asignada')}.")
    return " ".join(p)


def hoja_datos(r):
    """The data sheet; the plate that follows it carries the map."""
    k = r["k"]
    v = V3.loc[k] if k in V3.index else None
    e = EMPD.get(k, {"empresas": 0, "exporta": 0, "importa": 0})
    cl = _clu[_clu.k == k].sort_values("rank")
    hb = _hub[_hub.k == k]
    pr = pros[pros.k == k] if len(pros) else pros
    tot_gasto = r["top_gasto"][0][1] if len(r["top_gasto"]) else 1

    tag = cap(r["region_nat"])
    if v is not None:
        tag += f" · {v['arquetipo']}"
    tag += f" · Puesto {int(r['rank']):02d} de 24"

    log = [("Horas medias a la capital regional",
            "s/d" if v is None else f"{v['horas_capital']:.1f} h"),
           ("Sectores a menos de 2 h",
            "s/d" if v is None else f"{v['pct_bajo_2h']:.0f}%"),
           ("Sectores a más de 4 h",
            "s/d" if v is None else f"{v['pct_sobre_4h']:.0f}%"),
           ("Costo de una visita comercial",
            "s/d" if v is None else f"US$ {nf(v['costo_viaje'])}"),
           ("Horas al puerto marítimo",
            "s/d" if v is None else f"{v['horas_puerto']:.1f} h")]
    if len(hb):
        log.append(("Hub de distribución sugerido",
                    f"{hb.iloc[0]['hub']} ({hb.iloc[0]['pct_sam']:.1f}% país)"))

    prod = [("Superficie agrícola declarada", f"{nf(r['ha_agricola'])} ha"),
            ("Superficie cosechada 2023", f"{nf(r['ha_cosechada'])} ha"),
            ("Intensidad de uso del suelo", f"{100 * r['uso_ha']:.0f}%"),
            ("Sectores estadísticos", nf(r["sectores"])),
            ("Cultivos con superficie registrada", nf(r["n_cultivos"])),
            ("Productores censados 2012", nf(r["productores_x"])),
            ("Gasto en insumos por hectárea", f"US$ {nf(r['gasto_ha'])}")]

    pros_txt = (f"{nf(r['prospectos'])} entidades con nombre y coordenada, de "
                f"ellas {nf(r['fundos'])} identificables como fundo o "
                f"agroindustria")
    if len(pr):
        nombres = [str(x).strip() for x in
                   pr.sort_values("ha", ascending=False)["nombre"].head(6)
                   if str(x).strip() and str(x) != "nan"]
        if nombres:
            pros_txt += ". Entre las mayores: " + ", ".join(
                f"<b>{n[:38]}</b>" for n in nombres)

    if len(cl):
        c = cl.iloc[0]
        clu_txt = (f"El modelo de territorios agrupa la región en "
                   f"<b>{len(cl)}</b> {'zona' if len(cl) == 1 else 'zonas'} "
                   f"operables. La principal concentra "
                   f"<b>{usd(c['sam_usd'])}</b> sobre "
                   f"<b>{nf(c['clientes'])}</b> clientes en "
                   f"{cap(str(c['provincias']))[:60]}, con "
                   f"<b>{c['extension_km']:.0f} km</b> de extensión y "
                   f"{'visitable' if c['visitable_en_dia'] else 'no visitable'} "
                   f"en un día de ruta.")
    else:
        clu_txt = ("Ningún territorio de la región alcanza el umbral de tamaño "
                   "del modelo de zonas operables: se atiende como cola, no "
                   "como ruta propia.")

    return f"""
  <span class="kicker">Atlas regional · Ficha {int(r['rank']):02d} de 24</span>
  <div class="dephd">
    <span class="rk">{int(r['rank']):02d}</span>
    <h2>{cap(r['dep'])}</h2>
    <span class="tag">{tag}</span>
  </div>

  <div class="kpis dep">
    <div><span class="v">{usd(r['sam_usd'])}</span>
      <span class="l">Mercado anual alcanzable<br>{r['pct_sam']:.1f}% del país</span></div>
    <div><span class="v">{nf(r['clientes_sam'])}</span>
      <span class="l">Compradores de<br>más de 5 hectáreas</span></div>
    <div><span class="v">US$ {nf(r['ticket_anual'])}</span>
      <span class="l">Facturación esperada<br>por cliente y año</span></div>
    <div><span class="v">US$ {nf(r['gasto_ha'])}</span>
      <span class="l">Gasto en insumos<br>por hectárea cosechada</span></div>
  </div>

  <div class="two" style="margin-top:9px">
    <div>
      <h3 class="rule">Qué produce</h3>
      {dl(prod)}
      <h4 class="lab" style="margin-top:8px">Cultivos que concentran el gasto</h4>
      {barras(r['top_gasto'], tot_gasto)}
      <h4 class="lab" style="margin-top:7px">Tamaño de las unidades agropecuarias</h4>
      {estructura(r)}
      <p class="sub">Censo 2012. El modelo sólo considera vendible la superficie
      en manos de unidades de más de cinco hectáreas que ya aplican insumos.</p>
    </div>
    <div>
      <h3 class="rule">Cómo compra</h3>
      <div class="mini">
        <div><span class="v">{100 * r['tasa_fert']:.0f}%</span>
          <span class="l">aplica fertilizante</span></div>
        <div><span class="v">{100 * r['tasa_pest']:.0f}%</span>
          <span class="l">aplica fitosanitario</span></div>
        <div><span class="v">{100 * r['tasa_credito']:.0f}%</span>
          <span class="l">compra a crédito</span></div>
      </div>
      <h4 class="lab">Cuándo compra · demanda mensual estimada</h4>
      {calendario(k)}
      <p class="sub">En verde oscuro, los cuatro meses que concentran
      {"s/d" if v is None else f"{v['pct_top4']:.0f}%"} de la demanda del año.</p>

      <h3 class="rule" style="margin-top:10px">Cuánto cuesta llegar</h3>
      {dl(log)}
    </div>
  </div>

  <h3 class="rule" style="margin-top:8px">Dónde está el mercado dentro de la región</h3>
  {sectores_tabla(k)}

  <div class="two" style="margin-top:7px">
    <div>
      <h4 class="lab">Territorio operable</h4>
      <p class="sub" style="font-size:7.6pt">{clu_txt}</p>
    </div>
    <div>
      <h4 class="lab">Tejido empresarial y prospección</h4>
      <p class="sub" style="font-size:7.6pt"><b>{nf(e['empresas'])}</b> empresas
      agropecuarias activas en el padrón SUNAT, de ellas <b>{nf(e['exporta'])}</b>
      con actividad de exportación. {pros_txt}.</p>
    </div>
  </div>

  <p class="fread" style="margin-top:6px">{lectura_larga(r, v)}</p>
"""


def _lamina(k):
    """Inline the plate: as an <img> it would lose the report's webfont."""
    raw = open(f"out/lamina/{k}.svg", encoding="utf-8").read()
    raw = raw[raw.index("<svg "):]
    raw = re.sub(r'(<svg[^>]*?)\s+width="[^"]*"\s+height="[^"]*"', r"\1",
                 raw, count=1)
    return raw.replace("<svg ", '<svg class="lamina" ', 1)


def lamina_pagina(k):
    _pg["n"] += 1
    PAGES.append(f'<section class="plate">{_lamina(k)}</section>')


# ---- the ranking that opens the atlas ------------------------------------
page(f"""
  <div class="rank">
  <span class="kicker">Parte VII · Atlas regional</span>
  <h2 class="title">Las 24 regiones, <em>de mayor a menor</em></h2>
  <p class="deck">Cada región recibe a continuación un pliego de dos hojas: una
     ficha con su estructura productiva, su comportamiento de compra, su costo de
     servir y sus mayores sectores, y una lámina cartográfica a página completa
     donde esa misma región aparece con sus distritos, su red vial, sus
     {nf(len(sec_d))} sectores dimensionados por superficie y los prospectos ya
     localizados. El orden es el del modelo de priorización.</p>

  {table([[f"{int(r['rank']):02d}", cap(r['dep']), cap(r['region_nat']),
           f"{r['sam_usd'] / 1e6:,.1f}", f"{r['pct_sam']:.1f}%",
           nf(r['clientes_sam']), nf(r['ticket_anual']),
           f"{100 * r['tasa_credito']:.0f}%",
           "s/d" if r['k'] not in V3.index else f"{V3.loc[r['k'], 'horas_capital']:.1f}",
           "s/d" if r['k'] not in V3.index else V3.loc[r['k'], 'arquetipo']]
          for _, r in perfil.iterrows()],
         ["#", "Región", "Región natural", "Mercado US$ MM", "% país",
          "Clientes", "Ticket US$", "Crédito", "h capital", "Arquetipo"],
         ["r", "l", "l", "r", "r", "r", "r", "r", "r", "l"],
         ["", "Total país", "", f"{perfil.sam_usd.sum() / 1e6:,.1f}", "100.0%",
          nf(perfil.clientes_sam.sum()), "", "", "", ""],
         cls="tight")}

  <p class="sub">El arquetipo resume cómo se atiende la región: venta directa
  consultiva donde hay pocos compradores grandes y accesibles, red de canal donde
  son muchos y dispersos, campaña estacional donde la demanda se concentra en
  pocas semanas, operación mixta donde conviven ambas cosas.</p>
  </div>
""", "Parte VII · Atlas regional")

for _, _r in perfil.iterrows():
    page(hoja_datos(_r), "Parte VII · Atlas regional")
    lamina_pagina(_r["k"])



# ====================================================== PARTE VIII ========
divider("VIII", "Metodología <em>y fuentes</em>",
        "La cadena completa de cálculo, el contraste con datos de aduanas y las "
        "tres limitaciones que el lector debe tener presentes al usar estas cifras.",
        ["Cadena de cálculo", "Limitaciones", "Fuentes"])

page(f"""
  <span class="kicker">Parte VIII · Metodología</span>
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
    </div>
  </div>
""", "Parte VIII · Metodología")

page(f"""
  <span class="kicker">Parte VIII · Limitaciones</span>
  <h2 class="title">Los supuestos que <em>pueden mover el resultado</em></h2>
  <p class="deck">Ninguno de estos puntos invalida el dimensionamiento, y todos
     acotan hasta dónde puede estirarse. Se declaran aquí para que el lector
     ajuste el supuesto que le parezca discutible y vuelva a correr el modelo.</p>

  <div class="two" style="margin-top:10px">
    <div>
      <div class="note warn">
        <span class="h">Ubicación de la empresa</span>
        <p>El padrón entrega distrito, no coordenada. La empresa se sitúa en el
        punto medio de los sectores agrícolas de su distrito, con la clave
        departamento + provincia + distrito. <b>Una versión anterior cruzaba solo
        por el nombre del distrito</b>, y 95 nombres se repiten entre departamentos
        —hay cuatro «San Juan», separados por 800 km—: el 13% del padrón quedaba
        promediado en un punto que no está en ninguno de ellos. Corregido, quedan
        60 empresas sin ubicar que antes se ubicaban mal. Aun así, el domicilio
        fiscal no es el lugar de cultivo.</p>
      </div>
      <div class="note warn">
        <span class="h">Frontera de la clasificación arancelaria</span>
        <p>El reparto de la importación en categorías comerciales se corta donde
        el arancel deja de distinguir el uso. Quedan fuera
        <b>US$ {_imx.fob_usd.sum()/1e6:,.0f} MM</b> en diez semanas de partidas
        que mezclan agro con industria: bombas, válvulas, manguera plástica,
        rodamientos, tornillería y útiles de perforación. No es gasto agrícola
        sin contar, es el tamaño de la zona ambigua. Riego sale bajo por esta
        razón: la cinta de goteo no se separa del resto de la manguera.</p>
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
    </div>
    <div>
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
""", "Parte VIII · Limitaciones")


page(f"""
  <span class="kicker">Parte VIII · Fuentes</span>
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
        <li><b>SUNAT · Microdatos de aduanas, regímenes definitivos.</b>
        Archivos DBF semanales publicados en cumplimiento de la Ley 27806 de
        Transparencia: cada línea de despacho con RUC, razón social, partida
        NANDINA, valor FOB, peso y país. Diez semanas analizadas, junio a agosto
        de 2026.</li>
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
""", "Parte VIII · Fuentes")


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
       "--run-all-compositor-stages-before-draw", "--virtual-time-budget=90000",
       f"--print-to-pdf={dst}", f"file:///{src}"]
# 74 sheets, 24 of them full-page vector plates: Chrome needs the room.
r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
if os.path.exists(OUT_PDF):
    print(f"PDF   {os.path.getsize(OUT_PDF)/1e6:.2f} MB  ->  {OUT_PDF}")
    # El PDF publicado se copia aqui y no a mano: un informe que se actualiza
    # en out/ y se olvida en el repositorio es la misma averia que dejaba al
    # sitio con JSON de dos fechas distintas.
    pub = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
        "_repo", "docs", os.path.basename(OUT_PDF)))
    if os.path.isdir(os.path.dirname(pub)):
        shutil.copyfile(OUT_PDF, pub)
        print(f"      publicado en {pub}")
else:
    print("FALLO:", (r.stderr or "")[-900:])
