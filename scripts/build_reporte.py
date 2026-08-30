# -*- coding: utf-8 -*-
"""Assemble the printed market report and render it to PDF via headless Chrome.

Print is unforgiving in ways a screen is not: nothing reflows, nothing scrolls,
and a table that breaks across a page loses its header. So the layout is built
in explicit A4 pages, images are embedded as data URIs (Chrome will not read
local files from a page it prints), and every table declares its own repeat
header.
"""
import base64
import os
import re
import subprocess
import unicodedata
from datetime import date

import pandas as pd

OUT_HTML = "out/reporte_agrojuntos.html"
OUT_PDF = "out/Reporte de mercado - AgroJuntos.pdf"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"

mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
cos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
som = pd.read_csv("out/som_escenarios.csv", encoding="utf-8-sig")
ven = pd.read_csv("out/ventas_doc.csv", encoding="utf-8-sig")
cli = pd.read_csv("out/ventas_cliente.csv", encoding="utf-8-sig")
try:
    pros = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
except FileNotFoundError:
    pros = pd.DataFrame()

TAM, SAM = mod.tam_usd.sum(), mod.sam_usd.sum()
CLI = mod.clientes_sam.sum()
HA_COS = mod.ha_cosechada.sum()
MESES = 13.1


def nf(v, d=0):
    return f"{v:,.{d}f}"


def usd(v):
    if v >= 1e6:
        return f"US$ {nf(v/1e6)} MM"
    return f"US$ {nf(v)}"


def cap(s):
    return " ".join(w.capitalize() for w in str(s).split())


def img(name, cls=""):
    path = f"out/fig_{name}.png"
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return f'<img class="{cls}" src="data:image/png;base64,{b64}" alt="">'


def table(df, cols, aligns=None, foot=None):
    aligns = aligns or ["l"] + ["r"] * (len(cols) - 1)
    th = "".join(f'<th class="{a}">{c}</th>' for c, a in zip(cols, aligns))
    body = []
    for row in df:
        tds = "".join(f'<td class="{a}">{v}</td>' for v, a in zip(row, aligns))
        body.append(f"<tr>{tds}</tr>")
    tf = ""
    if foot:
        tds = "".join(f'<td class="{a}">{v}</td>' for v, a in zip(foot, aligns))
        tf = f"<tfoot><tr>{tds}</tr></tfoot>"
    return (f'<table><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody>{tf}</table>')


# ---------------------------------------------------------------- tables --
rank_rows = [[
    int(r["rank"]), cap(r["dep"]), nf(r["ha_cosechada"]), nf(r["gasto_ha"]),
    nf(r["clientes_sam"]), nf(r["ticket_anual"]), usd(r["sam_usd"]),
    f'{r["pct_acum"]:.0f}%',
] for _, r in mod.iterrows()]
rank_foot = ["", "Perú", nf(HA_COS), nf(TAM / HA_COS), nf(CLI),
             nf(SAM / CLI), usd(SAM), "100%"]

cos_top = cos[cos.insumos_usd > 0].nlargest(10, "insumos_usd")
cos_rows = [[cap(r["cultivo"]), nf(r["total_usd"]), nf(r["fertilizantes"] / 3.75),
             nf(r["plaguicidas"] / 3.75), f'<b>{nf(r["insumos_usd"])}</b>',
             f'{r["pct_insumos"]:.0f}%'] for _, r in cos_top.iterrows()]

emb_top = emb.nlargest(7, "compradores_insumos")
emb_rows = [[cap(r["dep"]), nf(r["ua_objetivo_5_mas"]),
             f'{100*r["tasa_fert"]:.0f}%', f'{100*r["tasa_pest"]:.0f}%',
             f'<b>{nf(r["compradores_insumos"])}</b>',
             nf(r["compran_a_credito"])] for _, r in emb_top.iterrows()]

som_rows = [[r["escenario"], f'{100*r["penetracion"]:.1f}%', nf(r["clientes"]),
             f'US$ {r["ventas_usd"]/1e6:.1f} MM',
             f'US$ {r["margen_usd"]/1e6:.1f} MM']
            for _, r in som.iterrows()]

cli_top = cli.nlargest(6, "usd")
cli_rows = [[cap(r["cliente"])[:34], int(r["compras"]), usd(r["usd"]),
             usd(r["ticket"]),
             ("—" if pd.isna(r["frec_dias"]) else
              "mismo día" if r["frec_dias"] < 1 else f'{r["frec_dias"]:.0f} días')]
            for _, r in cli_top.iterrows()]

pros_rows = []
if len(pros):
    p = pros[pros.nombre.str.contains(r"fundo|hacienda|agr[ií]cola|agroindustri",
                                      case=False, na=False)]
    p = (p[p.ha > 0].sort_values("ha", ascending=False)
         .groupby("dep").head(2).nlargest(9, "ha"))
    pros_rows = [[r["nombre"][:38], cap(r["dep"]), r["tipo"], nf(r["ha"], 1),
                  f'{r["lat"]:.3f} / {r["lon"]:.3f}'] for _, r in p.iterrows()]

FOCO = mod.head(8)

CSS = """
@page { size: A4; margin: 16mm 15mm 14mm; }
*{box-sizing:border-box; margin:0; padding:0}
:root{
  --ink:#121715; --ink2:#3A443E; --muted:#68726B;
  --line:#D6DCD1; --line2:#E9EDE5; --surf:#F7F9F5;
  --accent:#0B6E8F; --accent-soft:#E4F0F5;
  --costa:#C4862A; --warn:#B4541F; --good:#2E7D5B;
}
html{-webkit-print-color-adjust:exact; print-color-adjust:exact}
body{
  font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;
  font-size:9.3pt; line-height:1.52; color:var(--ink); background:#fff;
}
h1,h2,h3,h4{font-family:Archivo,"Segoe UI",sans-serif; text-wrap:balance}
.mono,.num{font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums}

.page{page-break-after:always; display:flex; flex-direction:column;
  min-height:250mm}
.page:last-child{page-break-after:auto}

.eyebrow{font-family:"IBM Plex Mono",monospace; font-size:7pt; font-weight:500;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted)}

h2.sec{font-size:17pt; font-weight:700; letter-spacing:-.02em; line-height:1.12;
  margin:5px 0 4px}
h3{font-size:10.5pt; font-weight:600; margin:16px 0 5px; letter-spacing:-.01em}
h4{font-size:8.6pt; font-weight:600; margin:11px 0 3px}
p{margin:0 0 7px; max-width:66ch}
p.lead{font-size:10.4pt; line-height:1.5; color:var(--ink2); max-width:60ch}
.sechead{border-bottom:1.6px solid var(--ink); padding-bottom:7px; margin-bottom:13px}

/* ---- cover ---- */
.cover{display:flex; flex-direction:column; height:250mm}
.cover .top{flex:1; display:flex; flex-direction:column; justify-content:center}
.cover h1{font-size:34pt; font-weight:700; letter-spacing:-.03em; line-height:1.02;
  margin:14px 0 16px; max-width:15ch}
.cover .sub{font-size:11.5pt; color:var(--ink2); max-width:52ch; line-height:1.5}
.rule{height:3px; background:var(--ink); width:52px; margin:20px 0}
.cover .meta{display:flex; gap:30px; padding-top:14px; border-top:1px solid var(--line);
  font-size:8pt; color:var(--muted)}
.cover .meta b{display:block; color:var(--ink); font-size:9pt; font-weight:600;
  margin-bottom:1px}
.coverstats{display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
  background:var(--line2); border:1px solid var(--line2); margin:24px 0 0}
.coverstats div{background:#fff; padding:11px 12px}
.coverstats .v{font-family:"IBM Plex Mono",monospace; font-size:16pt; font-weight:600;
  letter-spacing:-.03em; display:block; line-height:1.1}
.coverstats .l{font-size:7.2pt; color:var(--muted); display:block; margin-top:3px;
  line-height:1.35}

/* ---- kpi strip ---- */
.kpis{display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
  background:var(--line2); border:1px solid var(--line2); margin:12px 0 14px}
.kpis div{background:#fff; padding:9px 11px}
.kpis .v{font-family:"IBM Plex Mono",monospace; font-size:13.5pt; font-weight:600;
  letter-spacing:-.02em; display:block; line-height:1.15}
.kpis .l{font-size:7pt; color:var(--muted); display:block; margin-top:2px; line-height:1.35}

/* ---- layout ---- */
.two{display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start}
.map-l{display:grid; grid-template-columns:1.06fr 1fr; gap:18px; align-items:start}
.fig{width:100%; display:block}
figure{margin:0}
figcaption{font-size:7.4pt; color:var(--muted); margin-top:5px; line-height:1.45;
  border-top:1px solid var(--line2); padding-top:4px}

/* ---- tables ---- */
table{border-collapse:collapse; width:100%; font-size:8pt; margin:8px 0}
th,td{padding:3.6px 6px; border-bottom:1px solid var(--line2)}
th{background:var(--surf); font-size:6.9pt; font-weight:600; letter-spacing:.06em;
  text-transform:uppercase; color:var(--muted); border-bottom:1px solid var(--line)}
thead{display:table-header-group}
td.r,th.r{text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums}
td.l,th.l{text-align:left}
tfoot td{font-weight:600; background:var(--surf); border-top:1.2px solid var(--ink);
  border-bottom:0}
tbody tr:nth-child(-n+8) td:first-child{font-weight:500}

/* ---- callouts ---- */
.note{border-left:2.5px solid var(--accent); background:var(--accent-soft);
  padding:9px 12px; margin:11px 0; font-size:8.6pt; line-height:1.5}
.note.warn{border-color:var(--warn); background:#FBF1EC}
.note.good{border-color:var(--good); background:#EDF6F1}
.note b{font-weight:600}
.note p{margin:0 0 4px; max-width:none}
.note p:last-child{margin:0}

.cards{display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin:12px 0}
.card{border:1px solid var(--line); padding:11px 12px}
.card h4{margin-top:0}
.card p{font-size:8.2pt; margin-bottom:5px; color:var(--ink2)}
.card .big{font-family:"IBM Plex Mono",monospace; font-size:15pt; font-weight:600;
  display:block; letter-spacing:-.02em; margin-bottom:2px}

ul{margin:0 0 8px 15px}
li{margin-bottom:3.5px; font-size:8.8pt; color:var(--ink2)}
b.hl{background:linear-gradient(transparent 62%, #FBE6B8 62%); font-weight:600}

.foot{margin-top:auto; padding-top:8px; display:flex;
  justify-content:space-between; border-top:1px solid var(--line2);
  font-size:6.8pt; color:var(--muted)}

.srcs{font-size:7.4pt; color:var(--muted); line-height:1.6}
.srcs b{color:var(--ink2); font-weight:600}
.srcs li{font-size:7.4pt; color:var(--muted); margin-bottom:5px}
"""

HOY = date.today().strftime("%d de %B de %Y")
MESES_ES = {"January": "enero", "February": "febrero", "March": "marzo",
            "April": "abril", "May": "mayo", "June": "junio", "July": "julio",
            "August": "agosto", "September": "setiembre", "October": "octubre",
            "November": "noviembre", "December": "diciembre"}
for en, es in MESES_ES.items():
    HOY = HOY.replace(en, es)


def foot(n, txt):
    return (f'<div class="foot"><span>AgroJuntos · Reporte de mercado · Perú</span>'
            f'<span>{txt}</span><span>{n}</span></div>')


PAGES = []

# ------------------------------------------------------------------ cover --
PAGES.append(f"""
<section class="page cover">
  <div class="top">
    <span class="eyebrow">AgroJuntos · Inteligencia de mercado</span>
    <h1>Dónde está el cliente agrícola del Perú</h1>
    <div class="rule"></div>
    <p class="sub">Dimensionamiento del mercado de insumos agrícolas y priorización
       de territorio comercial, construido sobre 7,036 sectores estadísticos
       georreferenciados del MIDAGRI, el censo agropecuario del INEI y la campaña
       agrícola 2023.</p>
    <div class="coverstats">
      <div><span class="v">{usd(TAM)}</span><span class="l">TAM · mercado nacional de
        fertilizante y fitosanitario</span></div>
      <div><span class="v">{usd(SAM)}</span><span class="l">SAM · productores
        comerciales que ya compran</span></div>
      <div><span class="v">{nf(CLI)}</span><span class="l">clientes identificables
        en el mercado atendible</span></div>
      <div><span class="v">{nf(HA_COS/1e6,2)} M</span><span class="l">hectáreas
        cosechadas en la campaña 2023</span></div>
    </div>
  </div>
  <div class="meta">
    <div><b>Preparado para</b>Comité de inversión</div>
    <div><b>Fecha</b>{HOY}</div>
    <div><b>Fuentes</b>MIDAGRI · INEI · SUNAT/ICEX</div>
    <div><b>Moneda</b>US$ · tipo de cambio S/3.75</div>
  </div>
</section>
""")

# -------------------------------------------------------------- resumen ----
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">01 · Resumen ejecutivo</span>
    <h2 class="sec">Un mercado de {usd(TAM)} donde solo 7 de cada 100 productores
        son cliente</h2>
  </div>

  <p class="lead">El Perú tiene 2.26 millones de productores agropecuarios, pero la
     enorme mayoría opera por debajo de la escala que hace posible una venta
     recurrente de insumos. El mercado real es más pequeño, mucho más concentrado
     y —por eso mismo— alcanzable.</p>

  <div class="kpis">
    <div><span class="v">{usd(TAM)}</span><span class="l">TAM<br>mercado nacional</span></div>
    <div><span class="v">{usd(SAM)}</span><span class="l">SAM<br>{100*SAM/TAM:.0f}% del TAM</span></div>
    <div><span class="v">{nf(CLI)}</span><span class="l">clientes<br>que ya compran insumos</span></div>
    <div><span class="v">US$ {nf(SAM/CLI)}</span><span class="l">gasto anual<br>por cliente</span></div>
  </div>

  <h3>Cinco conclusiones</h3>
  <ul>
    <li><b>La tierra no es el mercado.</b> De 11.6 millones de hectáreas agrícolas,
        solo <b class="hl">{nf(HA_COS/1e6,2)} millones</b> pasaron por una campaña en 2023.
        La tierra en descanso no compra insumos.</li>
    <li><b>Tener tierra no hace cliente.</b> {nf(cen.ua_objetivo_5_mas.sum())} productores
        superan las 5 hectáreas, pero solo <b class="hl">{nf(CLI)}</b> declaran aplicar
        fertilizante o pesticida. Ese es el mercado que existe hoy.</li>
    <li><b>Hay un segmento que ya compra como AgroJuntos vende.</b>
        <b class="hl">{nf(emb.compran_a_credito.sum())} productores</b> usan crédito para
        adquirir insumos. Es el punto de entrada natural.</li>
    <li><b>El mercado está concentrado.</b> Ocho regiones reúnen el
        <b class="hl">{FOCO.pct_acum.iat[-1]:.0f}%</b> del mercado atendible. No hace falta
        cobertura nacional para capturar la mayor parte.</li>
    <li><b>La tracción actual es real pero mínima.</b> {len(cli)} clientes facturados y
        recompra cada <b class="hl">45 días</b> en el cliente establecido: el
        comportamiento funciona, falta escala.</li>
  </ul>

  <h3>Las ocho regiones prioritarias</h3>
  {table([[int(r["rank"]), cap(r["dep"]), nf(r["ha_cosechada"]), "US$ "+nf(r["gasto_ha"]),
           nf(r["clientes_sam"]), usd(r["sam_usd"]), f'{r["pct_acum"]:.0f}%']
          for _, r in FOCO.iterrows()],
         ["#", "Región", "Ha cosechadas", "US$/ha", "Clientes", "SAM anual", "% acum."],
         ["r","l","r","r","r","r","r"])}

  <div class="note">
    <p><b>Cómo leer estas cifras.</b> Son una estimación construida sobre fuentes
    oficiales con supuestos declarados, no una cifra publicada por el Estado. La
    metodología completa está en la sección 06 y cada componente puede recalcularse
    desde los datos de origen.</p>
  </div>
  {foot(2, "Resumen ejecutivo")}
</section>
""")

# ---------------------------------------------------------- donde la tierra -
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">02 · La base territorial</span>
    <h2 class="sec">Dónde está la tierra que produce</h2>
  </div>
  <div class="map-l">
    <figure>
      {img("superficie", "fig")}
      <figcaption>Superficie agrícola por sector estadístico. Cada círculo es una de
      las 7,036 unidades con que el MIDAGRI organiza el trabajo de campo; el tamaño
      es proporcional a sus hectáreas agrícolas y el color, a la región natural.
      Fuente: MIDAGRI, Padrón Nacional de Sectores Estadísticos 2024.</figcaption>
    </figure>
    <div>
      <p>El mapa muestra la primera decisión del modelo: trabajar a nivel de
      <b>sector estadístico</b> y no de distrito. Un distrito andino puede mezclar
      un valle irrigado con una puna sin agricultura; el sector separa uno de otro.</p>

      <p>La distribución tiene tres lógicas comerciales distintas. La
      <b>costa</b> concentra pocas hectáreas de altísimo valor por hectárea, en
      unidades grandes y formales. La <b>sierra</b> reúne la mayor superficie y la
      mayor cantidad de productores, pero muy fragmentada. La <b>selva</b> tiene
      unidades grandes con cultivos de bajo gasto por hectárea: café, cacao, palma.</p>

      <h4>Superficie por región natural</h4>
      {table([["Costa", nf(1298), nf(1654377), "14%"],
              ["Sierra", nf(4507), nf(5172835), "44%"],
              ["Selva alta", nf(641), nf(1741598), "15%"],
              ["Selva baja", nf(597), nf(3080907), "26%"]],
             ["Región natural", "Sectores", "Ha agrícolas", "% del país"],
             ["l","r","r","r"])}

      <div class="note">
        <p><b>11.6 millones de hectáreas agrícolas, {nf(HA_COS/1e6,2)} millones
        cosechadas.</b> La diferencia es tierra en descanso, en instalación o
        perdida por campaña. Solo la superficie efectivamente cosechada genera
        demanda de insumos en el año, y es sobre ella que se construye el TAM.</p>
      </div>
    </div>
  </div>
  {foot(3, "La base territorial")}
</section>
""")

# ----------------------------------------------------------- quien compra ---
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">03 · El cliente</span>
    <h2 class="sec">De 2.26 millones de productores a {nf(CLI)} clientes</h2>
  </div>

  <p class="lead">El error más común al dimensionar el agro peruano es contar
     productores. La pregunta correcta no es cuántos hay, sino cuántos compran.</p>

  <figure style="margin:10px 0 2px">
    {img("embudo", "fig")}
    <figcaption>Embudo de mercado atendible. Cada escalón aplica un filtro
    verificable del IV Censo Nacional Agropecuario, no un supuesto.</figcaption>
  </figure>

  <div class="two" style="margin-top:10px">
    <div>
      <h4>Escala mínima: 5 hectáreas</h4>
      <p>Por debajo de 5 ha la agricultura peruana es mayormente de autoconsumo. El
      productor no compra con factura, no sostiene una frecuencia de recompra y no
      es sujeto de crédito. El corte deja <b>{nf(cen.ua_objetivo_5_mas.sum())}</b>
      unidades, el {100*cen.ua_objetivo_5_mas.sum()/cen.productores.sum():.0f}% del total.</p>

      <h4>Comportamiento de compra</h4>
      <p>De esos, solo los que <b>ya aplican fertilizante o pesticida</b> son mercado
      hoy: <b>{nf(CLI)}</b> productores. Los demás requieren convertir a un no
      usuario, que es un costo de adquisición distinto y mucho mayor.</p>
    </div>
    <div>
      <h4>El segmento de entrada</h4>
      <p><b>{nf(emb.compran_a_credito.sum())} productores</b> ya usan crédito para
      comprar insumos. Compran exactamente como AgroJuntos vende —a plazo, con
      entrega— y no hay que enseñarles el modelo, solo ofrecerles mejor precio y
      servicio.</p>

      <div class="note good">
        <p><b>El promedio nacional esconde el dato útil.</b> La tasa de productores
        que fertilizan va de <b>78% en Lambayeque</b> a <b>4% en Loreto</b>. Dos
        regiones con superficie parecida pueden tener mercados incomparables.</p>
      </div>
    </div>
  </div>

  <h3>Tasas de compra por región</h3>
  {table(emb_rows,
         ["Región", "Prod. &gt;5 ha", "Fertiliza", "Aplica pesticida",
          "Clientes", "Compra a crédito"],
         ["l","r","r","r","r","r"])}
  <p style="font-size:7.4pt;color:var(--muted);margin-top:2px">Siete regiones con mayor
  número de clientes. Tasas del IV CENAGRO 2012 aplicadas al segmento de más de 5 ha.</p>
  {foot(4, "El cliente")}
</section>
""")

# --------------------------------------------------------------- gasto/ha ---
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">04 · Valor por hectárea</span>
    <h2 class="sec">Lo que se gasta depende de lo que se siembra</h2>
  </div>

  <div class="map-l">
    <div>
      <p>El gasto en insumos no es un promedio nacional: varía por un factor de tres
      entre regiones, y la causa es la mezcla de cultivos. Una hectárea de uva en Ica
      demanda <b>US$591</b> al año; una de maíz y pastos en Madre de Dios,
      <b>US$207</b>.</p>

      <p>El modelo calcula, para cada región, el promedio ponderado del gasto de sus
      145 cultivos según la superficie que efectivamente cosechó en 2023. Los precios
      por cultivo vienen del estudio de costos del INEI, medido en campo.</p>

      <h4>Qué entra y qué no</h4>
      <p>Se cuentan <b>fertilizante y fitosanitario</b>, que el productor compra. Se
      excluye el <b>abono orgánico</b>: en la mayoría de los casos lo produce la
      propia unidad y no pasa por el canal.</p>

      <div class="note">
        <p><b>Contraste con aduanas.</b> El modelo estima <b>US$1,038 MM</b> de
        fertilizante a precio de finca. El Perú importó <b>US$693 MM</b> CIF en 2024 y
        las importaciones cubren el 89.5% de la oferta nacional. La diferencia es el
        margen del canal de distribución. La cifra resiste el contraste.</p>
      </div>

      <h4>Composición del mercado</h4>
      {table([["Fertilizantes", "US$ 228", usd(1038e6), "60%"],
              ["Fitosanitarios", "US$ 153", usd(695e6), "40%"],
              ["<b>Mercado comprable</b>", "<b>US$ 381</b>", f"<b>{usd(TAM)}</b>", "<b>100%</b>"],
              ["Abono (autoproducido)", "US$ 62", usd(281e6), "excluido"]],
             ["Componente", "US$/ha", "Mercado anual", "Peso"],
             ["l","r","r","r"])}
    </div>
    <figure>
      {img("gastoha", "fig")}
      <figcaption>Gasto anual en insumos por hectárea, ponderado por la mezcla real
      de cultivos de cada región. Fuentes: MIDAGRI, Anuario de Producción Agrícola
      2023; INEI, Costos de producción (ENA 2018).</figcaption>
    </figure>
  </div>

  <h3>Gasto en insumos por cultivo</h3>
  {table(cos_rows,
         ["Cultivo", "Costo total US$/ha", "Fertiliz. US$", "Fitosan. US$",
          "Insumos US$/ha", "% del costo"],
         ["l","r","r","r","r","r"])}
  <p style="font-size:7.4pt;color:var(--muted);margin-top:2px">Diez cultivos de
  mayor gasto en insumos por hectárea, de los 73 medidos por el INEI. El porcentaje
  indica cuánto del costo total de producción representan los insumos.</p>
  {foot(5, "Valor por hectárea")}
</section>
""")

# ------------------------------------------------------------ priorizacion --
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">05 · Priorización comercial</span>
    <h2 class="sec">Ocho regiones concentran el {FOCO.pct_acum.iat[-1]:.0f}% del mercado</h2>
  </div>

  <div class="map-l">
    <figure>
      {img("sam", "fig")}
      <figcaption>Mercado atendible anual por región. En azul, las ocho regiones
      prioritarias según el score de atractivo comercial.</figcaption>
    </figure>
    <div>
      <p>El score combina cuatro factores, todos medidos: tamaño del mercado (40%),
      número de clientes que ya compran insumos (25%), gasto por hectárea —qué tan
      valiosa es cada visita comercial— (20%) y penetración del crédito, que es la
      palanca diferencial de AgroJuntos (15%).</p>

      <h4>Tres perfiles distintos</h4>
      <p><b>Volumen con densidad.</b> La Libertad y Lambayeque combinan alto gasto por
      hectárea con superficie compacta e irrigada. Cada visita comercial rinde más y
      la logística es corta.</p>
      <p><b>Volumen con dispersión.</b> Junín, Cajamarca y Cusco tienen muchos
      clientes pero repartidos y con ticket menor. Requieren canal, no venta directa.</p>
      <p><b>Alto valor por cliente.</b> Ica reúne pocos productores que gastan
      <b>US$7,356</b> al año cada uno. Es el perfil de venta consultiva.</p>

      <div class="note">
        <p><b>El orden cambia según qué se optimice.</b> Por hectáreas, San Martín
        lidera. Por mercado atendible, La Libertad. Por clientes, Junín. El score
        pondera los tres y agrega la variable de crédito.</p>
      </div>
    </div>
  </div>

  {foot(6, "Priorización comercial")}
</section>
""")

# The 24-row ranking needs a full page of its own; splitting it here keeps the
# map and its reading on one spread and the table unbroken on the next.
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">05 · Priorización comercial</span>
    <h2 class="sec">Las 24 regiones, ordenadas por atractivo</h2>
  </div>
  {table(rank_rows,
         ["#", "Región", "Ha cosechadas", "US$/ha", "Clientes",
          "US$/cliente/año", "SAM anual", "% acum."],
         ["r","l","r","r","r","r","r","r"], foot=rank_foot)}
  <p style="font-size:7.4pt;color:var(--muted);margin-top:3px">
  Ha cosechadas: superficie efectivamente llevada a cosecha en la campaña 2023.
  US$/ha: gasto anual en fertilizante y fitosanitario, ponderado por la mezcla de
  cultivos de la región. Clientes: productores de más de 5 ha que ya aplican
  insumos. SAM: mercado atendible anual.</p>

  <h3>Qué mueve el score</h3>
  <div class="cards">
    <div class="card">
      <h4>Tamaño de mercado · 40%</h4>
      <p>El SAM regional. Pesa más que todo lo demás porque define el techo de
      cualquier operación comercial en el territorio.</p>
    </div>
    <div class="card">
      <h4>Clientes y densidad · 45%</h4>
      <p>Número de compradores reales (25%) y gasto por hectárea (20%). Juntos miden
      cuánto rinde cada visita comercial.</p>
    </div>
    <div class="card">
      <h4>Crédito · 15%</h4>
      <p>Penetración del crédito para insumos. Es la palanca diferencial de
      AgroJuntos frente al distribuidor tradicional.</p>
    </div>
  </div>
  {foot(7, "Priorización comercial")}
</section>
""")

# ------------------------------------------------------------------- SOM ----
ESC = som.iloc[1]
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">06 · Captura y economía unitaria</span>
    <h2 class="sec">Qué parte del mercado es alcanzable</h2>
  </div>

  <p class="lead">El SAM dice cuánto dinero hay. El SOM tiene que decir cuánto puede
     tomar este equipo con la operación que ya demostró que funciona. Por eso los
     parámetros salen del libro de ventas, no de una meta.</p>

  <h3>Lo que muestran las ventas reales</h3>
  <div class="cards">
    <div class="card">
      <h4>Ticket</h4>
      <span class="big">US$ {nf(ven.usd.mean())}</span>
      <p>promedio por documento; mediana US$ {nf(ven.usd.median())}. El rango va de
      US$ 119 a US$ {nf(ven.usd.max())}.</p>
    </div>
    <div class="card">
      <h4>Recompra</h4>
      <span class="big">45 días</span>
      <p>en el cliente establecido, equivalente a 8.1 compras al año. Es la métrica
      más valiosa del negocio.</p>
    </div>
    <div class="card">
      <h4>Valor anual</h4>
      <span class="big">US$ {nf(ven.usd.mean()*8.1)}</span>
      <p>por cliente activo, con US$ {nf(ven.usd.mean()*8.1*0.21)} de margen bruto
      al 21%.</p>
    </div>
  </div>

  <div class="note good">
    <p><b>El modelo y la realidad coinciden.</b> El modelo de mercado estima un gasto
    anual de <b>US$ {nf(SAM/CLI)}</b> por cliente. Las ventas reales dan
    <b>US$ 3,264</b> —ticket mediano de US$ 408 por 8 compras al año—. Dos caminos
    independientes llegan al mismo número, lo que valida el dimensionamiento.</p>
  </div>

  <h3>Escenarios de captura sobre las ocho regiones foco</h3>
  <p>SAM en regiones foco: <b>{usd(FOCO.sam_usd.sum())}</b> ·
     clientes alcanzables: <b>{nf(FOCO.clientes_sam.sum())}</b></p>
  {table(som_rows,
         ["Escenario", "Penetración", "Clientes", "Ventas anuales", "Margen bruto"],
         ["l","r","r","r","r"])}

  <div class="note">
    <p><b>Qué significa el escenario base.</b> Alcanzar {nf(ESC.clientes)} clientes
    activos implica sumar <b>{ESC.clientes/36:.0f} clientes al mes durante tres
    años</b>, partiendo de los {len(cli)} actuales. Es exigente pero acotado: son
    {100*ESC.penetracion:.1f} de cada 100 clientes potenciales del territorio foco.</p>
  </div>

  <h3>Cartera actual</h3>
  {table(cli_rows,
         ["Cliente", "Compras", "Facturado", "Ticket medio", "Frecuencia"],
         ["l","r","r","r","r"])}
  <p style="font-size:7.4pt;color:var(--muted);margin-top:2px">Seis principales
  clientes por facturación, {MESES:.0f} meses de operación. Total del período:
  {usd(ven.usd.sum())} en {len(ven)} documentos a {len(cli)} clientes.</p>
  {foot(8, "Captura y economía unitaria")}
</section>
""")


# ------------------------------------------------------------ prospeccion ---
FUNDO_PAT = r"fundo|hacienda|agr[ií]cola|agroindustri"
n_fundos = 0
if len(pros):
    n_fundos = int(pros.nombre.str.contains(FUNDO_PAT, case=False, na=False).sum())
tabla_pros = (table(pros_rows, ["Nombre", "Región", "Tipo", "Hectáreas", "Coordenada"],
                    ["l", "l", "l", "r", "r"])
              if pros_rows else "<p>Sin registros con superficie mapeada.</p>")

PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">07 · Prospección</span>
    <h2 class="sec">Del territorio al nombre propio</h2>
  </div>

  <div class="map-l">
    <figure>
      {img("prospectos", "fig")}
      <figcaption>Entidades agrícolas con nombre propio y coordenada, extraídas de
      OpenStreetMap: {nf(n_fundos)} fundos y haciendas más
      {nf(len(pros) - n_fundos)} puntos de canal y agroindustria.</figcaption>
    </figure>
    <div>
      <p>Las capas anteriores dicen dónde hay mercado. Esta dice a quién llamar. Se
      extrajeron <b>{nf(len(pros))}</b> entidades agrícolas con nombre propio y
      coordenada: fundos, haciendas, agroindustrias, agroveterinarias y tiendas
      rurales.</p>

      <div class="note good">
        <p><b>La capa se validó sola.</b> Entre los registros aparece
        <b>Fundo Los Paltos SAC</b>, en Áncash, con <b>178 hectáreas</b>
        georreferenciadas. Es un cliente actual de AgroJuntos —cinco cotizaciones en
        octubre de 2025 por US$ 12,154— que el método habría identificado sin
        conocerlo de antemano.</p>
      </div>

      <p>La cobertura es desigual porque depende del trabajo de voluntarios: densa en
      Lima, Ica y Áncash, escasa en la selva. Por eso complementa la capa oficial del
      MIDAGRI y no la reemplaza. Sirve para construir rutas de visita, no para
      dimensionar mercado.</p>

      <h4>Cómo usarla</h4>
      <ul>
        <li>Cruzar los fundos con superficie contra el sector estadístico donde caen,
            para estimar su gasto potencial en insumos.</li>
        <li>Usar los puntos de canal —agroveterinarias, tiendas rurales— como red de
            distribución candidata en zonas sin venta directa.</li>
        <li>Priorizar por cercanía a los fundos ya facturados: Áncash concentra
            US$ 11,252 de las ventas actuales.</li>
      </ul>
    </div>
  </div>

  <h3>Fundos con superficie identificada</h3>
  {tabla_pros}
  <p style="font-size:7.4pt;color:var(--muted);margin-top:2px">Muestra de mayor
  superficie mapeada. El listado completo se entrega en formato CSV.</p>
  {foot(9, "Prospección")}
</section>
""")

# ------------------------------------------------------------ metodologia ---
PAGES.append(f"""
<section class="page">
  <div class="sechead">
    <span class="eyebrow">08 · Metodología y fuentes</span>
    <h2 class="sec">Cómo se construyó cada cifra</h2>
  </div>

  <div class="two">
    <div>
      <h3>Cadena de cálculo</h3>
      <h4>1 · Superficie que produce</h4>
      <p>Superficie cosechada de 145 cultivos por región, campaña 2023. No se usa
      superficie agrícola total porque la tierra en descanso no demanda insumos.</p>

      <h4>2 · Gasto por hectárea</h4>
      <p>Para cada región, el promedio del gasto en abono, fertilizante y plaguicida
      de sus cultivos, ponderado por la superficie de cada uno. Precios del estudio
      de costos del INEI. Se retiene solo fertilizante y fitosanitario.</p>

      <h4>3 · TAM</h4>
      <p>Superficie cosechada × gasto por hectárea, sumado por región:
      <b>{usd(TAM)}</b>.</p>

      <h4>4 · SAM</h4>
      <p>La porción del TAM en manos de productores de más de 5 ha que ya aplican
      insumos. La participación de superficie comercial se estima con los puntos
      medios de los estratos de tamaño del CENAGRO, reescalados a la superficie
      agrícola censada: <b>{usd(SAM)}</b>.</p>

      <h4>5 · SOM</h4>
      <p>Penetración sobre las ocho regiones foco, valorizada con el ingreso anual
      por cliente observado en las ventas propias.</p>
    </div>
    <div>
      <h3>Limitaciones declaradas</h3>
      <div class="note warn">
        <p><b>El censo agropecuario es de 2012.</b> No existe uno más reciente: el
        país lleva catorce años sin censo agropecuario. Las tasas de uso de insumos y
        de crédito provienen de esa base. La superficie y los cultivos son de
        2023–2024.</p>
      </div>
      <div class="note warn">
        <p><b>Los valores por sector son un reparto.</b> Las cifras departamentales se
        distribuyen a los 7,036 sectores en proporción a sus hectáreas agrícolas. Es
        una asignación, no una medición: sirve para priorizar territorio, no para
        cotizar a un productor concreto.</p>
      </div>
      <div class="note warn">
        <p><b>Pendiente de conciliación.</b> El dossier de inversionistas declara
        ventas acumuladas por más de US$ 200,000; el libro de ventas analizado suma
        <b>{usd(ven.usd.sum())}</b> en {MESES:.0f} meses. La diferencia debe aclararse
        antes de presentar el material: es la primera cifra que un inversionista
        verificará.</p>
      </div>

      <h3>Fuentes</h3>
      <ul class="srcs">
        <li><b>MIDAGRI · Padrón Nacional de Sectores Estadísticos 2024.</b> 7,043
        sectores con UBIGEO, hectáreas agrícolas, centroide, región natural y agencia
        agraria. Anexo del Mapa Nacional de Superficie Agrícola, RM N.º
        0026-2025-MIDAGRI.</li>
        <li><b>MIDAGRI · Anuario de Producción Agrícola 2023.</b> Superficie sembrada
        y cosechada de 145 cultivos por región.</li>
        <li><b>INEI · Costos de producción para la actividad agricultura, ganadería,
        caza y silvicultura, en base a la ENA 2018</b> (marzo 2021). Costo por
        hectárea desagregado por ítem para 73 cultivos.</li>
        <li><b>INEI · IV Censo Nacional Agropecuario 2012.</b> Productores por región,
        unidades por tamaño, uso de fertilizantes y pesticidas, y destino del crédito
        agrario.</li>
        <li><b>MIDAGRI / ICEX.</b> Importaciones de fertilizantes 2024 y participación
        de la oferta importada, usados como contraste externo del modelo.</li>
        <li><b>OpenStreetMap.</b> Entidades agrícolas nombradas y georreferenciadas,
        bajo licencia ODbL.</li>
        <li><b>AgroJuntos.</b> Libro de compras y ventas y reporte de cotizaciones,
        setiembre 2024 a octubre 2025.</li>
      </ul>
    </div>
  </div>
  {foot(10, "Metodología y fuentes")}
</section>
""")

# ------------------------------------------------------------------ build ---
html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Reporte de mercado · AgroJuntos</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style></head><body>
{"".join(PAGES)}
</body></html>"""

with open(OUT_HTML, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"HTML  {os.path.getsize(OUT_HTML)/1e6:.2f} MB  ({len(PAGES)} paginas)")

src = os.path.abspath(OUT_HTML).replace("\\", "/")
dst = os.path.abspath(OUT_PDF).replace("\\", "/")
cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
       "--run-all-compositor-stages-before-draw", "--virtual-time-budget=30000",
       f"--print-to-pdf={dst}", f"file:///{src}"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=420)
if os.path.exists(OUT_PDF):
    print(f"PDF   {os.path.getsize(OUT_PDF)/1e6:.2f} MB  ->  {OUT_PDF}")
else:
    print("FALLO:", (r.stderr or "")[-900:])
