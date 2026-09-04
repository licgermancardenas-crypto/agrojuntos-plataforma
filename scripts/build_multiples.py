# -*- coding: utf-8 -*-
"""Series de mapas pequeños: un mapa por territorio y uno por provincia.

El sitio le da a cada unidad su propio mapa a pantalla completa. En papel eso
no se puede copiar: la lámina departamental ocupa una A4 y pesa 260 KB, de modo
que 57 territorios y 197 provincias serían 254 páginas y 51 MB. Un informe que
nadie abre no informa nada.

La respuesta cartográfica a esto tiene nombre desde hace décadas: series de
mapas pequeños. Todas las unidades comparten escala, encuadre relativo y
símbolo, así que la comparación se hace de un vistazo y sin dar vuelta la
página, que es justo lo que la lámina grande no permite. Cada mapita renuncia
al detalle —no lleva red vial ni relieve— y a cambio la serie entera se lee
como una sola figura.

Dos decisiones de método:

  cada mapita se encuadra en su propia unidad y no en un marco común. Un marco
  común pondría Loreto y Tumbes a la misma escala, y Tumbes quedaría en cuatro
  píxeles. La escala se declara con la barra de cada cuadro.

  el punto es proporcional al mercado y no al área. La pregunta que la serie
  responde es dónde hay demanda, no qué unidad es más grande.

Uso:
    python scripts/build_multiples.py
"""
import io
import math
import os
import re
import unicodedata

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm

mpl.use("Agg")

for _f in sorted(os.listdir("data/fonts")):
    if _f.endswith(".ttf"):
        fm.fontManager.addfont(os.path.join("data/fonts", _f))

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
    "svg.fonttype": "none",
    "savefig.facecolor": "white",
})

MONO = "IBM Plex Mono"
INK, INK2, MUTED, FAINT = "#0F1A16", "#37443E", "#6E7872", "#9AA39D"
LINE, CTX, CTX_LINE = "#D5DBD2", "#F2F4EF", "#E0E5DA"
FOREST, BRASS = "#0F4C3F", "#B07D2E"
SELF_FILL = "#FDFEFC"
REGCOL = {"COSTA": "#C1873F", "SIERRA": "#3E7F93",
          "SELVA ALTA": "#5D9330", "SELVA BAJA": "#1F6B4C"}

A4 = (8.268, 11.693)
COLS_TER, FILAS_TER = 4, 5          # 20 territorios por plana
COLS_PRV, FILAS_PRV = 5, 6          # 30 provincias por plana


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima",
       "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def cap(s):
    s = " ".join(w.capitalize() for w in str(s).split())
    for a, b in (("De ", "de "), ("Del ", "del "), ("La ", "la "), ("Y ", "y ")):
        s = s.replace(" " + a, " " + b)
    return s


def usd(v):
    return f"US$ {v/1e6:,.1f} MM" if v >= 1e6 else f"US$ {v/1e3:,.0f} mil"


# ------------------------------------------------------------------ datos ---
sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
sec["k"] = sec["dep"].map(key)
sec["kp"] = sec["prov"].map(key)
celda = pd.read_csv("out/clusters_celda.csv", encoding="utf-8-sig")
terr = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
v3 = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
DEP_OK = {key(d): d for d in v3["dep"]}

dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["k"] = dep_g["NOMBDEP"].map(key)
prov_g = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
prov_g["k"] = prov_g["FIRST_NOMB"].map(key)
prov_g["kp"] = prov_g["NOMBPROV"].map(key)
prov_g["geometry"] = prov_g.geometry.simplify(0.006, preserve_topology=True)

os.makedirs("out/multiples", exist_ok=True)


def marco(ax, xs, ys, pad_rel=.16):
    """Encuadre cuadrado alrededor del contenido: sin esto, una provincia
    alargada se dibuja aplastada contra el borde de su celda de la grilla."""
    x0, x1 = float(np.min(xs)), float(np.max(xs))
    y0, y1 = float(np.min(ys)), float(np.max(ys))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lat = math.cos(math.radians(cy)) or 1
    r = max((x1 - x0) * lat, y1 - y0, .05) / 2 * (1 + pad_rel)
    ax.set_xlim(cx - r / lat, cx + r / lat)
    ax.set_ylim(cy - r, cy + r)
    ax.set_aspect(1 / lat)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    return (cx - r / lat, cx + r / lat, cy - r, cy + r)


def barra_escala(ax, lim):
    """Cada cuadro tiene su escala porque cada cuadro tiene la suya: sin la
    barra, la serie invita a comparar tamaños que no son comparables."""
    x0, x1, y0, y1 = lim
    ancho_km = (x1 - x0) * 111 * math.cos(math.radians((y0 + y1) / 2))
    paso = 10 ** math.floor(math.log10(max(ancho_km / 3, 1)))
    for m in (5, 2, 1):
        if paso * m <= ancho_km / 2.2:
            paso *= m
            break
    dx = paso / (111 * math.cos(math.radians((y0 + y1) / 2)) or 1)
    bx, by = x0 + (x1 - x0) * .06, y0 + (y1 - y0) * .07
    ax.plot([bx, bx + dx], [by, by], color=MUTED, lw=1.1,
            solid_capstyle="butt", zorder=6)
    ax.text(bx, by + (y1 - y0) * .028, f"{paso:.0f} km", fontsize=3.6,
            color=MUTED, family=MONO, zorder=6)


def rotulo(ax, titulo, sub, pie, color=INK):
    ax.text(.5, 1.045, titulo, transform=ax.transAxes, ha="center",
            fontsize=6.2, color=color, weight=600)
    if sub:
        ax.text(.5, .985, sub, transform=ax.transAxes, ha="center",
                fontsize=4.6, color=MUTED)
    if pie:
        ax.text(.5, -.055, pie, transform=ax.transAxes, ha="center",
                fontsize=4.6, color=INK2, family=MONO)


def plana(n_filas, n_cols, titulo, kicker):
    fig = plt.figure(figsize=A4)
    # El espaciado del kicker se hace a mano: matplotlib no expone letter
    # spacing y el resto del informe lo usa en todos los antetitulos. Se
    # separan las letras dentro de cada palabra y las palabras entre si con
    # mas aire, o «SERIE DE MAPAS» se lee «SERIEDEMAPAS».
    # El espacio entre palabras es un espacio em y no varios normales: el XML
    # del SVG colapsa los espacios consecutivos y «SERIE DE MAPAS» volvia a
    # leerse «SERIEDEMAPAS».
    espaciado = " ".join(" ".join(w) for w in kicker.split(" "))
    fig.text(.055, .962, espaciado, fontsize=6.0, color=BRASS, family=MONO)
    fig.text(.055, .935, titulo, fontsize=13, color=INK, weight=500)
    gs = fig.add_gridspec(n_filas, n_cols, left=.055, right=.945,
                          top=.905, bottom=.075, wspace=.28, hspace=.52)
    return fig, gs


_NUM = re.compile(r"-?\d+\.\d+")
_D = re.compile(r'd="([^"]*)"')


def adelgazar(svg):
    """Redondea los vertices a la decima de punto. Matplotlib los escribe con
    precision completa, lo que triplica el archivo por una exactitud que
    ninguna impresora resuelve: la plana mide 595 puntos de ancho, de modo que
    una decima de punto es la cuarentava parte de un milimetro. Solo se tocan
    los atributos `d`; redondear una matriz de transformacion desarma las
    escalas de los glifos."""
    def uno(m):
        return f"{round(float(m.group()), 1):g}"
    return _D.sub(lambda m: 'd="' + _NUM.sub(uno, m.group(1)) + '"', svg)


def guardar(fig, nombre):
    p = f"out/multiples/{nombre}.svg"
    fig.savefig(p, format="svg", bbox_inches=None)
    plt.close(fig)
    with io.open(p, encoding="utf-8") as fh:
        crudo = fh.read()
    with io.open(p, "w", encoding="utf-8") as fh:
        fh.write(adelgazar(crudo))
    return p, os.path.getsize(p)


# -------------------------------------------------- serie de territorios ---
celda_cl = celda[celda["cluster"] >= 0]
rank_de = dict(zip(terr["cluster"], terr["rank"]))
por_rank = {}
for cl, g in celda_cl.groupby("cluster"):
    if cl in rank_de:
        por_rank[int(rank_de[cl])] = g

terr = terr.sort_values("rank")
TER_MAX = celda_cl["sam_usd"].max() or 1
paginas_ter = []
filas = list(terr.iterrows())
POR_PAGINA = COLS_TER * FILAS_TER
for pag in range(math.ceil(len(filas) / POR_PAGINA)):
    trozo = filas[pag * POR_PAGINA:(pag + 1) * POR_PAGINA]
    fig, gs = plana(FILAS_TER, COLS_TER,
                    "Los 57 territorios de venta, uno por uno",
                    f"SERIE DE MAPAS · TERRITORIOS · {pag+1} DE "
                    f"{math.ceil(len(filas)/POR_PAGINA)}")
    for i, (_, r) in enumerate(trozo):
        ax = fig.add_subplot(gs[i // COLS_TER, i % COLS_TER])
        g = por_rank.get(int(r["rank"]))
        if g is None or not len(g):
            ax.set_axis_off()
            continue
        lim = marco(ax, g["centro_lon"].values, g["centro_lat"].values, .30)
        # el departamento va de contexto, recortado al encuadre del cuadro
        ctx = dep_g[dep_g["k"] == key(r["dep"])]
        if len(ctx):
            ctx.plot(ax=ax, facecolor=CTX, edgecolor=CTX_LINE, lw=.35,
                     zorder=1)
        tam = 1.2 + 16 * (g["sam_usd"] / TER_MAX) ** .5
        ax.scatter(g["centro_lon"], g["centro_lat"], s=tam, c=FOREST,
                   alpha=.72, linewidths=0, zorder=3)
        ax.set_xlim(lim[0], lim[1])
        ax.set_ylim(lim[2], lim[3])
        barra_escala(ax, lim)
        dep = DEP_OK.get(key(r["dep"]), cap(r["dep"]))
        rotulo(ax, f"{int(r['rank']):02d} · {dep}", cap(r["provincias"])[:34],
               f"{usd(r['sam_usd'])} · {r['extension_km']:.0f} km")
    paginas_ter.append(guardar(fig, f"ter_{pag+1}"))

# --------------------------------------------------- serie de provincias ---
sec_pv = sec[sec["s_sam_usd"] > 0]
agg = sec_pv.groupby(["k", "kp"]).agg(sam=("s_sam_usd", "sum")).reset_index()
AGG = {(r["k"], r["kp"]): r["sam"] for _, r in agg.iterrows()}
PRV_MAX = sec_pv["s_sam_usd"].max() or 1

prov_orden = prov_g.copy()
prov_orden["sam"] = [AGG.get((r["k"], r["kp"]), 0.0)
                     for _, r in prov_orden.iterrows()]
prov_orden["dep_ok"] = prov_orden["k"].map(lambda k: DEP_OK.get(k, cap(k)))
prov_orden = prov_orden.sort_values(["dep_ok", "NOMBPROV"])

paginas_prv = []
POR_PAGINA_P = COLS_PRV * FILAS_PRV
lista = list(prov_orden.iterrows())
n_pag = math.ceil(len(lista) / POR_PAGINA_P)
for pag in range(n_pag):
    trozo = lista[pag * POR_PAGINA_P:(pag + 1) * POR_PAGINA_P]
    desde = trozo[0][1]["dep_ok"]
    hasta = trozo[-1][1]["dep_ok"]
    rango = desde if desde == hasta else f"{desde} a {hasta}"
    fig, gs = plana(FILAS_PRV, COLS_PRV,
                    f"Las 197 provincias · {rango}",
                    f"SERIE DE MAPAS · PROVINCIAS · {pag+1} DE {n_pag}")
    for i, (_, r) in enumerate(trozo):
        ax = fig.add_subplot(gs[i // COLS_PRV, i % COLS_PRV])
        geo = gpd.GeoSeries([r.geometry], crs=4326)
        xs, ys = geo.total_bounds[[0, 2]], geo.total_bounds[[1, 3]]
        lim = marco(ax, xs, ys, .18)
        geo.plot(ax=ax, facecolor=SELF_FILL, edgecolor=LINE, lw=.5, zorder=2)
        s = sec_pv[(sec_pv["k"] == r["k"]) & (sec_pv["kp"] == r["kp"])]
        if len(s):
            tam = .6 + 11 * (s["s_sam_usd"] / PRV_MAX) ** .5
            col = [REGCOL.get(str(x).upper(), FOREST) for x in s["region_nat"]]
            ax.scatter(s["lon"], s["lat"], s=tam, c=col, alpha=.78,
                       linewidths=0, zorder=3)
        ax.set_xlim(lim[0], lim[1])
        ax.set_ylim(lim[2], lim[3])
        barra_escala(ax, lim)
        rotulo(ax, cap(r["NOMBPROV"])[:22], r["dep_ok"],
               usd(r["sam"]) if r["sam"] else "sin mercado registrado",
               color=INK if r["sam"] else FAINT)
    paginas_prv.append(guardar(fig, f"prov_{pag+1}"))

print(f"territorios : {len(terr)} en {len(paginas_ter)} planas")
for p, b in paginas_ter:
    print(f"  {p}  {b/1024:,.0f} KB")
print(f"provincias  : {len(prov_orden)} en {len(paginas_prv)} planas")
for p, b in paginas_prv:
    print(f"  {p}  {b/1024:,.0f} KB")
print(f"peso total  : "
      f"{sum(b for _, b in paginas_ter + paginas_prv)/1e6:.2f} MB")
