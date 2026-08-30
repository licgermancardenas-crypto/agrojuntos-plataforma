# -*- coding: utf-8 -*-
"""Render the figures for the report's new sections: when, and how to get there.

Same palette and type as the rest of the document so the three new sections
read as part of one system rather than an appendix.
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
    "text.color": "#0F1A16",
    "savefig.facecolor": "white",
})

INK, MUTED, LINE = "#0F1A16", "#6E7872", "#D5DBD2"
FOREST, BRASS = "#0F4C3F", "#B07D2E"
LAND, LAND_LINE = "#EDF0EA", "#C3CCBB"
RAMP = LinearSegmentedColormap.from_list(
    "agro", ["#F1F4EE", "#CBD9C4", "#8FB585", "#4C8A6B", "#125A57", "#0B3B4A"])
# Accessibility reads better hot-to-cold: near is good, far is a warning.
RAMP_ACC = LinearSegmentedColormap.from_list(
    "acc", ["#1F6B4C", "#5D9330", "#C9A227", "#C1873F", "#A34A25"])

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct",
         "Nov", "Dic"]


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def cap(s):
    return " ".join(w.capitalize() for w in str(s).split())


mod = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
log = pd.read_csv("out/logistica_sector.csv", encoding="utf-8-sig")
est_n = pd.read_csv("out/estacionalidad_nacional.csv", encoding="utf-8-sig")
est_r = pd.read_csv("out/estacionalidad_region.csv", encoding="utf-8-sig")
puertos = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
log["k"] = log["dep"].map(key)

dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["k"] = dep_g["NOMBDEP"].map(key)

XLIM, YLIM = (-81.6, -68.5), (-18.6, -0.0)
ASPECT = 1 / np.cos(np.radians(9.2))


def base_ax(figsize=(5.4, 7.0)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_aspect(ASPECT)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    path = f"out/fig_{name}.png"
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    plt.close(fig)
    print(f"  {path}")


# ---- 1. national demand curve --------------------------------------------
def curva_estacional():
    n = est_n.set_index("mes").reindex(MESES)
    fig, ax = plt.subplots(figsize=(5.6, 2.5))
    x = np.arange(12)
    v = n["demanda"].values / 1e6
    pico = int(np.argmax(v))
    colores = [FOREST if i in np.argsort(v)[-4:] else "#B8C6BC" for i in range(12)]
    ax.bar(x, v, color=colores, width=.72)
    ax.plot(x, v, color=BRASS, lw=1.3, marker="o", ms=3.2, zorder=5)
    ax.annotate(f"pico {MESES[pico]}\nUS$ {v[pico]:,.0f} MM",
                (pico, v[pico]), xytext=(0, 12), textcoords="offset points",
                ha="center", fontsize=7.5, color=FOREST, fontweight="bold",
                linespacing=1.4)
    ax.set_xticks(x)
    ax.set_xticklabels(MESES, fontsize=7.5)
    ax.set_ylabel("US$ millones", fontsize=7.5, color=MUTED)
    ax.tick_params(labelsize=7, colors=MUTED)
    ax.set_ylim(0, v.max() * 1.22)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis="y", color=LINE, lw=.5, alpha=.6)
    ax.set_axisbelow(True)
    save(fig, "curva_estacional")


# ---- 2. region x month heatmap -------------------------------------------
def calendario_regional():
    r = est_r.copy()
    r["dep"] = r["k"].map(lambda k: mod.set_index(mod["dep"].map(key))
                          ["dep"].get(k, k))
    r = r.sort_values("total", ascending=False).head(16)
    M = r[MESES].values
    # Share of each region's own year, so small regions stay readable
    M = 100 * M / M.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(5.7, 4.3))
    im = ax.imshow(M, cmap=RAMP, aspect="auto", vmin=0, vmax=M.max())
    ax.set_xticks(range(12))
    ax.set_xticklabels(MESES, fontsize=7.2)
    ax.set_yticks(range(len(r)))
    ax.set_yticklabels([cap(d) for d in r["dep"]], fontsize=7.2)
    ax.tick_params(length=0, colors=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    # mark each region's peak month
    for i in range(len(r)):
        j = int(np.argmax(M[i]))
        ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False,
                                   edgecolor=BRASS, lw=1.5))
    cb = fig.colorbar(im, ax=ax, fraction=.026, pad=.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6.5, colors=MUTED, length=0)
    cb.set_label("% de la demanda anual de la región", fontsize=6.8,
                 color=MUTED)
    save(fig, "calendario_regional")


# ---- 3. accessibility map -------------------------------------------------
def mapa_accesibilidad():
    fig, ax = base_ax()
    dep_g.plot(ax=ax, facecolor=LAND, edgecolor=LAND_LINE, linewidth=.45,
               zorder=1)
    s = log.sort_values("ha_agricola", ascending=False)
    h = s["horas_capital"].clip(0, 8)
    ax.scatter(s.lon, s.lat,
               s=0.7 + 62 * np.sqrt(s.ha_agricola / s.ha_agricola.max()),
               c=h, cmap=RAMP_ACC, vmin=0, vmax=8, alpha=.62, linewidths=0,
               zorder=3)
    sm = plt.cm.ScalarMappable(cmap=RAMP_ACC, norm=plt.Normalize(0, 8))
    cax = fig.add_axes([0.15, 0.20, 0.025, 0.19])
    cb = fig.colorbar(sm, cax=cax)
    cb.outline.set_visible(False)
    cb.set_ticks([0, 2, 4, 6, 8])
    cb.set_ticklabels(["0 h", "2 h", "4 h", "6 h", "8 h +"])
    cb.ax.tick_params(labelsize=6.5, colors=MUTED, length=0, pad=3)
    cb.ax.set_title("A la capital\nprovincial", fontsize=6.5, color=MUTED,
                    loc="left", pad=7, linespacing=1.4)
    ax.text(-81.3, -0.9, "Tiempo estimado de viaje\ndesde cada sector agrícola",
            fontsize=7, color=MUTED, va="top", linespacing=1.5)
    save(fig, "accesibilidad")


# ---- 4. ports and their hinterland ---------------------------------------
def mapa_puertos():
    fig, ax = base_ax()
    dep_g.plot(ax=ax, facecolor=LAND, edgecolor=LAND_LINE, linewidth=.45,
               zorder=1)
    s = log.sample(min(2600, len(log)), random_state=7)
    # colour each sector by the port it would ship through
    orden = list(puertos[puertos.tipo == "maritimo"].puerto)
    cmap = plt.get_cmap("tab20")
    col = {p: cmap(i % 20) for i, p in enumerate(orden)}
    ax.scatter(s.lon, s.lat, s=2.6,
               c=[col.get(p, (.7, .7, .7, 1)) for p in s.puerto_maritimo],
               alpha=.5, linewidths=0, zorder=3)

    mar = puertos[puertos.tipo == "maritimo"]
    alta = mar[mar.relevancia_agro == "alta"]
    ax.scatter(mar.lon, mar.lat, s=26, facecolor="white", edgecolor=INK,
               linewidths=.9, zorder=6)
    ax.scatter(alta.lon, alta.lat, s=54, facecolor=BRASS, edgecolor=INK,
               linewidths=.9, zorder=7)
    for _, p in alta.iterrows():
        ax.annotate(p.puerto.split(" (")[0], (p.lon, p.lat),
                    xytext=(-7, 0), textcoords="offset points", ha="right",
                    fontsize=6.9, color=INK, fontweight="bold", zorder=8)
    flu = puertos[puertos.tipo == "fluvial"]
    ax.scatter(flu.lon, flu.lat, s=22, facecolor="white", edgecolor="#2E6E8E",
               linewidths=.9, zorder=6)
    for _, p in flu.iterrows():
        ax.annotate(p.puerto, (p.lon, p.lat), xytext=(7, 0),
                    textcoords="offset points", fontsize=6.4, color="#2E6E8E",
                    zorder=8)

    h = [Line2D([], [], marker="o", ls="", ms=7, markerfacecolor=BRASS,
                markeredgecolor=INK, label="Puerto agroexportador"),
         Line2D([], [], marker="o", ls="", ms=5.5, markerfacecolor="white",
                markeredgecolor=INK, label="Otro terminal marítimo"),
         Line2D([], [], marker="o", ls="", ms=5, markerfacecolor="white",
                markeredgecolor="#2E6E8E", label="Puerto fluvial")]
    ax.legend(handles=h, loc="lower left", frameon=False, fontsize=6.8,
              handletextpad=.5, bbox_to_anchor=(-0.02, 0.02))
    ax.text(-81.3, -0.9,
            "Color del sector = puerto\nmarítimo más cercano",
            fontsize=7, color=MUTED, va="top", linespacing=1.5)
    save(fig, "puertos")


# ---- 5. cost to serve vs market ------------------------------------------
def dispersion_costo():
    m = mod.copy()
    fig, ax = plt.subplots(figsize=(5.6, 3.5))
    x = m["horas_capital"]
    y = m["sam_usd"] / 1e6
    tam = 12 + 190 * (m["clientes_sam"] / m["clientes_sam"].max())
    col = [FOREST if r <= 8 else ("#8FB585" if r <= 16 else "#C1873F")
           for r in m["rank_v3"]]
    ax.scatter(x, y, s=tam, c=col, alpha=.72, linewidths=0)
    for _, r in m.iterrows():
        if r["rank_v3"] <= 8 or r["horas_capital"] > 4:
            ax.annotate(cap(r["dep"]), (r["horas_capital"], r["sam_usd"] / 1e6),
                        xytext=(5, 3), textcoords="offset points",
                        fontsize=6.6, color=INK)
    ax.axvline(2, color=BRASS, lw=1, ls="--", alpha=.8)
    ax.text(2.08, y.max() * .97, "2 h", fontsize=6.8, color=BRASS)
    ax.set_xlabel("Horas medias al centro provincial", fontsize=7.6,
                  color=MUTED)
    ax.set_ylabel("Mercado atendible · US$ MM", fontsize=7.6, color=MUTED)
    ax.tick_params(labelsize=7, colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(LINE)
    ax.grid(color=LINE, lw=.5, alpha=.55)
    ax.set_axisbelow(True)
    save(fig, "costo_mercado")


if __name__ == "__main__":
    print("figuras nuevas...")
    curva_estacional()
    calendario_regional()
    mapa_accesibilidad()
    mapa_puertos()
    dispersion_costo()
    print("listo")
