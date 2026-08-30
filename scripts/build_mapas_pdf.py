# -*- coding: utf-8 -*-
"""Render the print maps for the PDF report.

Print is a different medium from the interactive map: no hover, no zoom, one
fixed scale. So each map here answers exactly one question and carries its own
labels, and the palette is the same as the web map so the two read as one
system.
"""
import re
import unicodedata

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": "#D6DCD1",
    "text.color": "#121715",
    "figure.dpi": 220,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

INK, MUTED, LINE = "#121715", "#68726B", "#D6DCD1"
LAND, LAND_LINE = "#EDF0EA", "#C3CCBB"
ACCENT = "#0B6E8F"
REGCOL = {"COSTA": "#C4862A", "SIERRA": "#3E7F93",
          "SELVA ALTA": "#5D9330", "SELVA BAJA": "#1F6B4C"}
RAMP = LinearSegmentedColormap.from_list(
    "agro", ["#F1F4EE", "#CBD9C4", "#8FB585", "#4C8A6B", "#125A57", "#0B3B4A"])


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
mod["k"] = mod["dep"].map(key)
sec["k"] = sec["dep"].map(key)

dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["k"] = dep_g["NOMBDEP"].map(key)
dep_g = dep_g.merge(mod, on="k", how="left")

XLIM, YLIM = (-81.6, -68.5), (-18.6, -0.0)


def base_ax(figsize=(5.4, 7.0)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_aspect(1 / np.cos(np.radians(9.2)))
    ax.axis("off")
    return fig, ax


def outline(ax, lw=0.45, fc=LAND):
    dep_g.plot(ax=ax, facecolor=fc, edgecolor=LAND_LINE, linewidth=lw, zorder=1)


def save(fig, name):
    path = f"out/fig_{name}.png"
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white",
                pad_inches=0.04)
    plt.close(fig)
    print(f"  {path}")


# ---- 1. where the agricultural land is -----------------------------------
def mapa_superficie():
    fig, ax = base_ax()
    outline(ax)
    s = sec.sort_values("ha_agricola", ascending=False)
    sizes = 0.7 + 62 * np.sqrt(s.ha_agricola / s.ha_agricola.max())
    colors = s.region_nat.map(REGCOL).fillna(REGCOL["SIERRA"])
    ax.scatter(s.lon, s.lat, s=sizes, c=colors, alpha=.42, linewidths=0, zorder=3)
    handles = [Line2D([], [], marker="o", ls="", markersize=6,
                      markerfacecolor=c, markeredgecolor="none",
                      label=r.title()) for r, c in REGCOL.items()]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=7,
              handletextpad=.4, labelspacing=.45, bbox_to_anchor=(-0.02, 0.02))
    ax.text(-81.3, -0.9, "7,036 sectores estadísticos\ntamaño = hectáreas agrícolas",
            fontsize=7, color=MUTED, va="top", linespacing=1.5)
    save(fig, "superficie")


# ---- 2. choropleths -------------------------------------------------------
def choropleth(col, name, label, fmt, top_n=8, subtitle=""):
    fig, ax = base_ax()
    dep_g.plot(ax=ax, column=col, cmap=RAMP, edgecolor="white", linewidth=.5,
               zorder=1, missing_kwds={"color": "#F2F4F0"})
    top = mod.nsmallest(top_n, "rank")
    g_top = dep_g[dep_g.k.isin(top.k)]
    g_top.boundary.plot(ax=ax, edgecolor=ACCENT, linewidth=1.15, zorder=4)

    for _, r in g_top.iterrows():
        c = r.geometry.representative_point()
        ax.annotate(f"{int(r['rank'])}", (c.x, c.y), ha="center", va="center",
                    fontsize=7.5, fontweight="bold", color="white", zorder=6,
                    bbox=dict(boxstyle="circle,pad=0.24", fc=ACCENT, ec="none"))

    vals = dep_g[col].dropna()
    sm = plt.cm.ScalarMappable(cmap=RAMP,
                               norm=plt.Normalize(vals.min(), vals.max()))
    cax = fig.add_axes([0.15, 0.20, 0.025, 0.19])
    cb = fig.colorbar(sm, cax=cax)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6.5, colors=MUTED, length=0, pad=3)
    cb.set_ticks([vals.min(), vals.max()])
    cb.set_ticklabels([fmt(vals.min()), fmt(vals.max())])
    cb.ax.set_title(label, fontsize=6.5, color=MUTED, loc="left", pad=6)
    if subtitle:
        ax.text(-81.3, -0.9, subtitle, fontsize=7, color=MUTED, va="top",
                linespacing=1.5)
    ax.text(-81.3, -16.4, f"1 a {top_n}\nregiones prioritarias", fontsize=6.8,
            color=ACCENT, va="top", linespacing=1.5)
    save(fig, name)


# ---- 3. prospects from OSM ------------------------------------------------
def mapa_prospectos():
    try:
        p = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
    except FileNotFoundError:
        return
    fig, ax = base_ax()
    outline(ax)
    fundos = p[p.nombre.str.contains(r"fundo|hacienda|agr[ií]cola|agroindustri",
                                     case=False, na=False)]
    tiendas = p[~p.index.isin(fundos.index)]
    ax.scatter(tiendas.lon, tiendas.lat, s=5, c=MUTED, alpha=.35,
               linewidths=0, zorder=3, label=f"Canal y agroindustria ({len(tiendas):,})")
    ax.scatter(fundos.lon, fundos.lat, s=13, c="#C4862A", alpha=.85,
               linewidths=0, zorder=4, label=f"Fundos y haciendas ({len(fundos):,})")
    ax.legend(loc="lower left", frameon=False, fontsize=7, handletextpad=.4,
              bbox_to_anchor=(-0.02, 0.02))
    ax.text(-81.3, -0.9,
            "Entidades con nombre propio\nlocalizadas en OpenStreetMap",
            fontsize=7, color=MUTED, va="top", linespacing=1.5)
    save(fig, "prospectos")


# ---- 4. spend per hectare, by crop ---------------------------------------
def barras_cultivos():
    c = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
    c = c[c.insumos_usd > 0].nlargest(20, "insumos_usd").sort_values("insumos_usd")
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    y = np.arange(len(c))
    ax.barh(y, c.fertilizantes / 3.75, color="#4C8A6B", height=.68,
            label="Fertilizante")
    ax.barh(y, c.plaguicidas / 3.75, left=c.fertilizantes / 3.75,
            color="#C4862A", height=.68, label="Fitosanitario")
    ax.barh(y, c.abono / 3.75, left=(c.fertilizantes + c.plaguicidas) / 3.75,
            color="#CBD9C4", height=.68, label="Abono (autoproducido)")
    ax.set_yticks(y)
    ax.set_yticklabels([s.title() for s in c.cultivo], fontsize=7.5)
    ax.set_xlabel("US$ por hectárea y campaña", fontsize=7.5, color=MUTED)
    ax.tick_params(axis="x", labelsize=7, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis="x", color=LINE, lw=.5, alpha=.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    save(fig, "cultivos")


# ---- 5. the funnel --------------------------------------------------------
def embudo():
    emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
    cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
    steps = [
        ("Productores agropecuarios", cen.productores.sum(), "#CBD9C4"),
        ("Unidades con más de 5 ha", cen.ua_objetivo_5_mas.sum(), "#8FB585"),
        ("Ya compran insumos", emb.compradores_insumos.sum(), "#4C8A6B"),
        ("Ya compran a crédito", emb.compran_a_credito.sum(), "#0B3B4A"),
    ]
    top = steps[0][1]
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    for i, (lab, v, col) in enumerate(steps):
        w = v / top
        ax.barh(-i, w, height=.62, color=col, zorder=2)
        ax.text(w + .012, -i, f"{v:,.0f}", va="center", fontsize=8.5,
                fontweight="bold", color=INK)
        ax.text(w + .012, -i - .30, f"{100*v/top:.1f}% del total", va="center",
                fontsize=6.8, color=MUTED)
        ax.text(-.012, -i, lab, va="center", ha="right", fontsize=8, color=INK)
    ax.set_xlim(-.42, 1.24)
    ax.set_ylim(-len(steps) + .35, .55)
    ax.axis("off")
    save(fig, "embudo")


def mapa_hero():
    """Cover version: the shape of Peruvian agriculture, nothing else.

    The cover already carries the title, the figures and the sources, so the
    map there only has to be recognisable and beautiful; captions and legend
    would compete with the headline."""
    fig, ax = base_ax(figsize=(5.6, 7.3))
    outline(ax, lw=.4, fc="#F2F4F0")
    s = sec.sort_values("ha_agricola", ascending=False)
    sizes = 0.8 + 78 * np.sqrt(s.ha_agricola / s.ha_agricola.max())
    ax.scatter(s.lon, s.lat, s=sizes,
               c=s.region_nat.map(REGCOL).fillna(REGCOL["SIERRA"]),
               alpha=.5, linewidths=0, zorder=3)
    save(fig, "hero")


if __name__ == "__main__":
    print("renderizando mapas...")
    mapa_hero()
    mapa_superficie()
    choropleth("sam_usd", "sam", "SAM anual", lambda v: f"US$ {v/1e6:,.0f} MM",
               subtitle="Mercado atendible por región\nfertilizante + fitosanitario")
    choropleth("clientes_sam", "clientes", "Clientes", lambda v: f"{v/1000:,.0f} mil",
               subtitle="Productores de más de 5 ha\nque ya aplican insumos")
    choropleth("gasto_ha", "gastoha", "US$/ha", lambda v: f"US$ {v:,.0f}",
               subtitle="Gasto en insumos por hectárea\nsegún la mezcla real de cultivos")
    mapa_prospectos()
    barras_cultivos()
    embudo()
    print("listo")
