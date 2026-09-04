# -*- coding: utf-8 -*-
"""Render one full-page plate per department for the regional atlas.

The fiche map was a 56 mm thumbnail: it showed the outline and little else. A
salesperson cannot route on that. Each department now gets its own sheet, and
at roughly 190 x 235 mm the plate carries what the thumbnail could not —
districts, the road network that explains why one valley is reachable and the
next is not, every statistical sector sized by its agricultural hectares, the
prospects already located by name, the provincial capitals, the port that
serves the region and the hub the routing model picks.

Output is SVG and gets inlined into the report rather than embedded as an
image: a full-sheet PNG weighs some 700 KB and pixelates, and inlining lets the
plate use the same webfont as the running text instead of baking outlines.
"""
import io
import json
import os
import re
import unicodedata

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

mpl.use("Agg")

# The report loads IBM Plex from Google Fonts; matplotlib needs the same faces
# locally or it lays the labels out on DejaVu metrics and they drift.
for _f in sorted(os.listdir("data/fonts")):
    if _f.endswith(".ttf"):
        fm.fontManager.addfont(os.path.join("data/fonts", _f))

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
    "svg.fonttype": "none",          # keep text as text: small files, real font
    "savefig.facecolor": "white",
})

MONO = "IBM Plex Mono"
SERIF = "Newsreader"

INK, INK2, MUTED, FAINT = "#0F1A16", "#37443E", "#6E7872", "#9AA39D"
LINE = "#D5DBD2"
FOREST, BRASS = "#0F4C3F", "#B07D2E"
CTX, CTX_LINE = "#F2F4EF", "#E0E5DA"
SELF_FILL = "#FDFEFC"
REGCOL = {"COSTA": "#C1873F", "SIERRA": "#3E7F93",
          "SELVA ALTA": "#5D9330", "SELVA BAJA": "#1F6B4C"}
VIACOL = {1: "#8C6B3A", 2: "#A98D63", 3: "#C9B893"}
VIAW = {1: 1.15, 2: .70, 3: .38}

A4 = (8.268, 11.693)
FRAME = (.042, .050, .916, .800)     # left, bottom, width, height


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
    for a, b in ((" De ", " de "), (" Del ", " del "), (" La ", " la "),
                 (" Y ", " y "), (" El ", " el ")):
        s = s.replace(a, b)
    return s


def nf(v, d=0):
    return f"{v:,.{d}f}"


# ------------------------------------------------------------------ data ---
sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
sec["k"] = sec["dep"].map(key)

perfil = pd.read_pickle("out/perfil_dep.pkl")
v3 = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
V3 = v3.set_index("k")

try:
    pros = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
    pros["k"] = pros["dep"].map(key)
except FileNotFoundError:
    pros = pd.DataFrame(columns=["k", "nombre", "lat", "lon", "ha", "tipo"])

pue = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
hub = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")
hub = hub[hub.umbral_h == hub.umbral_h.min()]

dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["k"] = dep_g["NOMBDEP"].map(key)
prov_g = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
prov_g["k"] = prov_g["FIRST_NOMB"].map(key)
dist_g = gpd.read_file("data/peru_distrital_simple.geojson").to_crs(4326)
dist_g["k"] = dist_g["NOMBDEP"].map(key)
dist_g["geometry"] = dist_g.geometry.simplify(0.003)
cap_g = gpd.read_file("data/peru_capital_provincia.geojson").to_crs(4326)
cap_g["k"] = cap_g["DEPARTAM"].map(key)

VIAL = json.load(open("out/vial_mapa.json", encoding="utf-8"))
TREES = {}
for _n in ("1", "2", "3"):
    _ls = [LineString(t) for t in VIAL["niveles"][_n] if len(t) >= 2]
    TREES[int(_n)] = (_ls, STRtree(_ls) if _ls else None)

os.makedirs("out/lamina", exist_ok=True)

_NUM = re.compile(r"-?\d+\.\d+")
_D = re.compile(r'd="([^"]*)"')


def _adelgazar(svg):
    """Round path coordinates to a tenth of a point.

    Matplotlib writes every vertex at full float precision, which triples the
    file for accuracy no printer can resolve: the canvas is 827 points wide, so
    a tenth of a point is a fortieth of a millimetre. Only the `d` attributes
    are touched — rounding a transform matrix would collapse the glyph scales.
    """
    def uno(m):
        v = round(float(m.group()), 1)
        return f"{v:g}"
    return _D.sub(lambda m: 'd="' + _NUM.sub(uno, m.group(1)) + '"', svg)


# ----------------------------------------------------------------- utils ---
def marco(me, aspect):
    """Frame the department to the plate's own aspect, with a 10% margin."""
    x0, y0, x1, y1 = me.total_bounds
    w, h = x1 - x0, (y1 - y0) * aspect
    r = (FRAME[2] * A4[0]) / (FRAME[3] * A4[1])
    if w / h < r:
        w = h * r
    else:
        h = w / r
    w *= 1.10
    h *= 1.10
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return ((cx - w / 2, cx + w / 2),
            (cy - h / (2 * aspect), cy + h / (2 * aspect)))


def esquinas(me, xlim, ylim):
    """Rank the four corners by how little department falls in them, so the
    legend and the insets never land on top of the subject."""
    poly = me.union_all()
    dx, dy = (xlim[1] - xlim[0]) * .30, (ylim[1] - ylim[0]) * .27
    out = {}
    for nm, (x, y) in (("ne", (xlim[1] - dx, ylim[1] - dy)),
                       ("nw", (xlim[0], ylim[1] - dy)),
                       ("se", (xlim[1] - dx, ylim[0])),
                       ("sw", (xlim[0], ylim[0]))):
        out[nm] = box(x, y, x + dx, y + dy).intersection(poly).area
    return [n for n, _ in sorted(out.items(), key=lambda kv: kv[1])]


def rotulo(ax, x, y, txt, size, color=INK, weight=400, dy=0, ha="center",
           va="bottom", family=None, alpha=1.0):
    t = ax.annotate(txt, (x, y), xytext=(0, dy), textcoords="offset points",
                    fontsize=size, color=color, ha=ha, va=va, zorder=30,
                    fontweight=weight, alpha=alpha)
    if family:
        t.set_fontfamily(family)
    return t


class Etiquetas:
    """Keeps labels off each other.

    Everything on the plate wants to be named — sectors, provincial capitals,
    provinces, the port, the hub — and at 5.5 pt two names a few kilometres
    apart become one illegible smear. Names are placed in order of commercial
    value and anything that would land on top of one already placed is
    dropped, not nudged: a nudged label points at the wrong dot.
    """

    def __init__(self, xlim, ylim, aspect, ancho=.048):
        self.pts = []
        self.dx = (xlim[1] - xlim[0]) * ancho
        self.dy = self.dx / aspect * .48

    def libre(self, x, y, f=1.0):
        return not any(abs(x - a) < self.dx * f and abs(y - b) < self.dy * f
                       for a, b in self.pts)

    def ocupar(self, x, y):
        self.pts.append((x, y))


def escala(ax, xlim, ylim, corner):
    """Bar in kilometres. A degree of longitude shrinks with latitude, so the
    length is measured on the parallel actually drawn."""
    lat = (ylim[0] + ylim[1]) / 2
    km_grado = 111.32 * np.cos(np.radians(lat))
    span = (xlim[1] - xlim[0]) * km_grado
    paso = next((p for p in (10, 20, 25, 50, 100, 200, 250, 500)
                 if p >= span * .12), 500)
    ancho = paso / km_grado
    x0 = xlim[0] + (xlim[1] - xlim[0]) * (.04 if corner[1] == "w" else .96)
    if corner[1] == "e":
        x0 -= ancho
    y0 = ylim[0] + (ylim[1] - ylim[0]) * (.05 if corner[0] == "s" else .925)
    h = (ylim[1] - ylim[0]) * .0055
    for i in range(2):
        ax.add_patch(Rectangle((x0 + i * ancho / 2, y0), ancho / 2, h,
                               fc=INK if i == 0 else "white", ec=INK, lw=.5,
                               zorder=31))
    rotulo(ax, x0, y0 + h * 1.6, "0", 5.6, MUTED, family=MONO)
    rotulo(ax, x0 + ancho, y0 + h * 1.6, f"{paso} km", 5.6, MUTED, family=MONO)
    nx = x0 + ancho * (1.24 if corner[1] == "w" else -.24)
    ax.annotate("", (nx, y0 + (ylim[1] - ylim[0]) * .024), (nx, y0),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=.8,
                                mutation_scale=7), zorder=31)
    rotulo(ax, nx, y0 + (ylim[1] - ylim[0]) * .028, "N", 5.8, INK,
           family=MONO, weight=600)


def locator(fig, me, corner):
    """Thumbnail of Peru with the department picked out."""
    w, h = .108, .143
    px = FRAME[0] + .013 if corner[1] == "w" else FRAME[0] + FRAME[2] - w - .013
    py = (FRAME[1] + FRAME[3] - h - .013 if corner[0] == "n"
          else FRAME[1] + .013)
    ax = fig.add_axes([px, py, w, h], zorder=40)
    ax.set_facecolor("white")
    dep_g.plot(ax=ax, facecolor="#EDF0EA", edgecolor="white", linewidth=.3)
    me.plot(ax=ax, facecolor=FOREST, edgecolor=FOREST, linewidth=.4)
    ax.set_aspect(1 / np.cos(np.radians(9.2)))
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(.5)
        s.set_color(LINE)


def leyenda(ax, corner, s):
    """Key for colour, size and symbol, boxed in the emptiest corner left."""
    filas = [("dot", c, cap(n)) for n, c in REGCOL.items()
             if len(s) and (s.region_nat == n).any()]
    filas += [("via", VIACOL[1], "Vía troncal"),
              ("via", VIACOL[2], "Vía primaria"),
              ("sq", INK, "Capital de provincia"),
              ("x", "#2A3B33", "Prospecto localizado")]
    h = []
    for tipo, cl, lab in filas:
        if tipo == "dot":
            h.append(Line2D([], [], marker="o", ls="", ms=5.4, mfc=cl,
                            mec="white", mew=.4, alpha=.75, label=lab))
        elif tipo == "via":
            h.append(Line2D([], [], color=cl, lw=1.3, label=lab))
        elif tipo == "sq":
            h.append(Line2D([], [], marker="s", ls="", ms=4.2, mfc="white",
                            mec=cl, mew=.7, label=lab))
        else:
            h.append(Line2D([], [], marker="x", ls="", ms=4.4, mec=cl,
                            mew=.7, label=lab))
    for rel, lab in ((1.0, "Sector: mayor ha"), (.30, "ha media"),
                     (.06, "menor ha")):
        h.append(Line2D([], [], marker="o", ls="", alpha=.42, mfc="#9AA39D",
                        mec="white", mew=.3, label=lab,
                        ms=np.sqrt(4 + 460 * np.sqrt(rel)) * .62))
    lg = ax.legend(handles=h, frameon=True, fontsize=6.0, labelspacing=.62,
                   handletextpad=.8, borderpad=.85, borderaxespad=.9,
                   title="REFERENCIAS",
                   loc=f"{'upper' if corner[0] == 'n' else 'lower'} "
                       f"{'left' if corner[1] == 'w' else 'right'}")
    lg.set_zorder(35)
    fr = lg.get_frame()
    fr.set_facecolor("white")
    fr.set_alpha(.93)
    fr.set_edgecolor(LINE)
    fr.set_linewidth(.5)
    lg.get_title().set(fontsize=5.8, color=MUTED)
    for t in lg.get_texts():
        t.set_color(INK2)


# ------------------------------------------------------------------ plate --
def lamina(r):
    k, nombre = r["k"], cap(r["dep"])
    me = dep_g[dep_g.k == k]
    if me.empty:
        return None
    aspect = 1 / np.cos(np.radians(me.geometry.union_all().centroid.y))
    xlim, ylim = marco(me, aspect)
    libres = esquinas(me, xlim, ylim)

    fig = plt.figure(figsize=A4, dpi=100)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes(FRAME)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect(aspect)
    ax.axis("off")
    ax.add_patch(Rectangle((xlim[0], ylim[0]), xlim[1] - xlim[0],
                           ylim[1] - ylim[0], fc="#FAFBF8", ec=LINE, lw=.7,
                           zorder=0))
    frame_box = box(xlim[0], ylim[0], xlim[1], ylim[1])

    # --- context, districts, provinces ------------------------------------
    tol = (xlim[1] - xlim[0]) / 420          # ~0.45 mm on the printed frame
    ctx = dep_g[dep_g.k != k].clip(frame_box)
    ctx["geometry"] = ctx.geometry.simplify(tol)
    if len(ctx):
        ctx.plot(ax=ax, facecolor=CTX, edgecolor=CTX_LINE, linewidth=.45,
                 zorder=1)
    me.plot(ax=ax, facecolor=SELF_FILL, edgecolor="none", zorder=2)
    di = dist_g[dist_g.k == k].copy()
    di["geometry"] = di.geometry.simplify(tol)
    if len(di):
        di.boundary.plot(ax=ax, edgecolor="#E4E9DF", linewidth=.35, zorder=3)
    pv = prov_g[prov_g.k == k].copy()
    pv["geometry"] = pv.geometry.simplify(tol)
    if len(pv):
        pv.boundary.plot(ax=ax, edgecolor="#C3CCBD", linewidth=.75, zorder=4)

    # --- roads ------------------------------------------------------------
    for n in (3, 2, 1):
        ls, tree = TREES[n]
        if tree is None:
            continue
        segs = []
        for i in tree.query(frame_box):
            g = ls[i].intersection(frame_box)
            if g.is_empty:
                continue
            for part in (g.geoms if g.geom_type == "MultiLineString" else [g]):
                part = part.simplify(tol)
                if part.geom_type == "LineString" and len(part.coords) > 1:
                    segs.append(np.asarray(part.coords))
        if segs:
            # One compound path per level. A LineCollection writes each
            # segment as its own SVG element and the repeated style attribute
            # costs more than the geometry does.
            verts = np.vstack(segs)
            codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(a) - 1)
                                    for a in segs]).astype(np.uint8)
            ax.add_patch(PathPatch(MPath(verts, codes), fill=False,
                                   edgecolor=VIACOL[n], linewidth=VIAW[n],
                                   alpha=.75 if n == 1 else .55, zorder=5,
                                   capstyle="round", joinstyle="round"))

    me.boundary.plot(ax=ax, edgecolor=FOREST, linewidth=1.5, zorder=12)

    # --- sectors ----------------------------------------------------------
    s = sec[sec.k == k].sort_values("ha_agricola", ascending=False)
    if len(s):
        rel = (s.ha_agricola / max(s.ha_agricola.max(), 1)).to_numpy()
        col = s.region_nat.map(REGCOL).fillna(REGCOL["SIERRA"]).to_numpy()
        # Binning the radii is what lets the SVG carry one symbol definition
        # per bin instead of one path per sector; at 14 steps the difference
        # is below the width of the marker outline.
        paso = np.clip(np.round(np.sqrt(rel) * 14), 0, 14) / 14
        for b in np.unique(paso):
            m = paso == b
            ax.scatter(s.lon[m], s.lat[m], s=4 + 460 * b, c=col[m], alpha=.42,
                       linewidths=.35, edgecolors="white", zorder=8)

    pr = pros[pros.k == k]
    if len(pr):
        ax.scatter(pr.lon, pr.lat, s=5.5, marker="x", c="#2A3B33",
                   linewidths=.5, alpha=.70, zorder=9)

    # --- named features, in order of who gets the space -------------------
    et = Etiquetas(xlim, ylim, aspect)

    for _, t in pue[(pue.lon.between(*xlim)) & (pue.lat.between(*ylim))].iterrows():
        ax.scatter([t.lon], [t.lat], s=44, marker="^", c=BRASS,
                   edgecolors="white", linewidths=.6, zorder=15)
        rotulo(ax, t.lon, t.lat, f"Puerto {cap(t['puerto'])}", 6.2, BRASS,
               weight=600, dy=5.5)
        et.ocupar(t.lon, t.lat)

    for _, t in hub[hub.region.map(key) == k].iterrows():
        if not (xlim[0] < t.lon < xlim[1] and ylim[0] < t.lat < ylim[1]):
            continue
        ax.scatter([t.lon], [t.lat], s=150, marker="o", facecolors="none",
                   edgecolors=FOREST, linewidths=1.3, zorder=16)
        rotulo(ax, t.lon, t.lat, f"Hub · {t['hub']}", 6.3, FOREST,
               weight=600, dy=-12, va="top")
        et.ocupar(t.lon, t.lat)

    cp = cap_g[cap_g.k == k]
    if len(cp):
        ax.scatter(cp.geometry.x, cp.geometry.y, s=18, marker="s", c="white",
                   edgecolors=INK, linewidths=.65, zorder=14)
        for _, t in cp.iterrows():
            x, y = t.geometry.x, t.geometry.y
            rotulo(ax, x, y, cap(t["CAPITAL"])[:16], 6.1, INK, weight=600,
                   dy=4.4)
            et.ocupar(x, y)

    # The biggest markets get named next; the rest of the sectors stay dots.
    if len(s):
        n = 0
        for _, t in s.sort_values("s_sam_usd", ascending=False).head(40).iterrows():
            if not (xlim[0] < t.lon < xlim[1] and ylim[0] < t.lat < ylim[1]):
                continue
            if not et.libre(t.lon, t.lat):
                continue
            et.ocupar(t.lon, t.lat)
            rotulo(ax, t.lon, t.lat, str(t["sector"]).title()[:20], 5.7, INK2,
                   dy=-5.0, va="top")
            n += 1
            if n >= 16:
                break

    # Province names last: they are orientation, not information, so they only
    # take space nothing else wanted.
    if len(pv):
        for _, t in pv.iterrows():
            c = t.geometry.representative_point()
            if not et.libre(c.x, c.y, 1.15):
                continue
            et.ocupar(c.x, c.y)
            rotulo(ax, c.x, c.y, str(t["NOMBPROV"]).upper()[:18], 5.5,
                   "#B6BFB1", weight=600, va="center")

    escala(ax, xlim, ylim, libres[0])
    locator(fig, me, libres[1])
    leyenda(ax, libres[2], s)

    # --- title block ------------------------------------------------------
    v = V3.loc[k] if k in V3.index else None
    fig.text(.042, .960, f"ATLAS REGIONAL  ·  LÁMINA {int(r['rank']):02d} DE 24",
             fontsize=6.6, color=BRASS, fontfamily=MONO, fontweight=500)
    fig.text(.042, .914, nombre, fontsize=25, color=INK, fontfamily=SERIF,
             va="baseline")
    tag = (f"{cap(r['region_nat'])}   ·   {int(r['sectores'])} SECTORES   ·   "
           f"{int(r['n_cultivos'])} CULTIVOS")
    if v is not None:
        tag += f"   ·   {str(v['arquetipo']).upper()}"
    fig.text(.042, .893, tag, fontsize=6.2, color=MUTED, fontfamily=MONO,
             fontweight=500)

    x = .958
    for val, lab in reversed([(f"US$ {nf(r['sam_usd']/1e6, 1)} MM", "Mercado anual"),
                              (nf(r["clientes_sam"]), "Clientes"),
                              (f"US$ {nf(r['ticket_anual'])}", "Por cliente/año"),
                              (f"{nf(r['ha_cosechada']/1000)}k", "Ha cosechadas")]):
        fig.text(x, .914, val, fontsize=11.5, color=FOREST, fontfamily=MONO,
                 fontweight=600, ha="right", va="baseline")
        fig.text(x, .895, lab, fontsize=6.1, color=MUTED, ha="right")
        x -= .128
    fig.add_artist(Line2D([.042, .958], [.878, .878], color=INK, linewidth=1.1,
                          transform=fig.transFigure))

    fig.text(.042, .020,
             "Sectores estadísticos MIDAGRI 2024  ·  red vial OpenStreetMap  ·  "
             "límites INEI  ·  mercado estimado por el modelo AgroJuntos",
             fontsize=5.7, color=FAINT, fontfamily=MONO)
    fig.text(.958, .020, f"LÁMINA {int(r['rank']):02d}", fontsize=5.7,
             color=FAINT, fontfamily=MONO, ha="right")

    path = f"out/lamina/{k}.svg"
    buf = io.StringIO()
    fig.savefig(buf, format="svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_adelgazar(buf.getvalue()))
    return path


if __name__ == "__main__":
    tot = 0
    for _, row in perfil.sort_values("rank").iterrows():
        p = lamina(row)
        if p:
            kb = os.path.getsize(p) / 1024
            tot += kb
            print(f"  {int(row['rank']):>2}  {row['dep']:<16} {kb:>7,.0f} KB")
    print(f"24 láminas · {tot / 1024:.2f} MB")
