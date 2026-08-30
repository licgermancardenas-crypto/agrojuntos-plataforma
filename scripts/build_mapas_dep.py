# -*- coding: utf-8 -*-
"""Render one detail map per department for the regional fiches.

Each map is a small figure that has to work at roughly 70 mm wide on paper, so
it carries only what survives that size: the department filled and outlined,
its neighbours as context, its sectors sized by agricultural hectares, and the
provincial capitals that a salesperson would actually route through.
"""
import os
import re
import unicodedata

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
    "savefig.facecolor": "white",
})

INK, MUTED = "#101A17", "#6B7570"
CTX, CTX_LINE = "#F0F2EE", "#DDE2D8"     # neighbouring departments
SELF_FILL, SELF_LINE = "#FBFCFA", "#0F4C3F"
REGCOL = {"COSTA": "#C1873F", "SIERRA": "#3E7F93",
          "SELVA ALTA": "#5D9330", "SELVA BAJA": "#1F6B4C"}


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
sec["k"] = sec["dep"].map(key)
perfil = pd.read_pickle("out/perfil_dep.pkl")

dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["k"] = dep_g["NOMBDEP"].map(key)
prov_g = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
prov_g["k"] = prov_g["FIRST_NOMB"].map(key)

ASPECT = 1 / np.cos(np.radians(9.2))
os.makedirs("out/dep", exist_ok=True)


def render(k, name):
    me = dep_g[dep_g.k == k]
    if me.empty:
        return None
    x0, y0, x1, y1 = me.total_bounds
    pad = max(x1 - x0, (y1 - y0) / ASPECT) * 0.10
    xlim = (x0 - pad, x1 + pad)
    ylim = (y0 - pad * ASPECT, y1 + pad * ASPECT)

    fig, ax = plt.subplots(figsize=(3.1, 3.1 * ((y1 - y0 + 2 * pad * ASPECT) /
                                                (x1 - x0 + 2 * pad)) / ASPECT))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect(ASPECT)
    ax.axis("off")

    dep_g.plot(ax=ax, facecolor=CTX, edgecolor=CTX_LINE, linewidth=.4, zorder=1)
    me.plot(ax=ax, facecolor=SELF_FILL, edgecolor="none", zorder=2)
    pv = prov_g[prov_g.k == k]
    if len(pv):
        pv.boundary.plot(ax=ax, edgecolor="#D8DED4", linewidth=.45, zorder=3)
    me.boundary.plot(ax=ax, edgecolor=SELF_LINE, linewidth=1.15, zorder=6)

    s = sec[sec.k == k].sort_values("ha_agricola", ascending=False)
    if len(s):
        r = s.ha_agricola / s.ha_agricola.max()
        ax.scatter(s.lon, s.lat, s=1.6 + 105 * np.sqrt(r),
                   c=s.region_nat.map(REGCOL).fillna(REGCOL["SIERRA"]),
                   alpha=.48, linewidths=0, zorder=5)

        # Two labels only: at 70 mm on paper a third one always collides, and
        # they alternate above/below so the pair never overlaps either.
        for n, (_, t) in enumerate(s.head(2).iterrows()):
            dy = 9 if n == 0 else -13
            ax.annotate(str(t["sector"]).title()[:18], (t.lon, t.lat),
                        xytext=(0, dy), textcoords="offset points",
                        fontsize=6.4, color=INK, ha="center", zorder=8,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                  ec="none", alpha=.82))

    path = f"out/dep/{k}.png"
    fig.savefig(path, dpi=240, bbox_inches="tight", pad_inches=0.02,
                facecolor="white")
    plt.close(fig)
    return path


if __name__ == "__main__":
    done = 0
    for _, r in perfil.sort_values("rank").iterrows():
        p = render(r["k"], r["dep"])
        if p:
            done += 1
            print(f"  {r['rank']:>2}  {r['dep']:<16} {os.path.getsize(p)/1e3:>6.0f} KB")
    print(f"{done} mapas departamentales")
