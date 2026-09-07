# -*- coding: utf-8 -*-
"""Las dos figuras de la serie mensual de agroexportación.

Misma paleta y misma tipografía que el resto del documento, para que las
páginas nuevas no se lean como un anexo pegado al final.

Cada figura contesta una pregunta distinta y ninguna de las dos se contesta
con una tabla:

  La serie nacional muestra a la vez el nivel, la estacionalidad y el tramo
  que todavía está entrando. Ese último tramo es el que se dibuja distinto:
  una serie mensual que termina en una caída invita a leer una caída, y lo
  que hay ahí es un mes que aún no regulariza. Se sombrea, se marca y se
  anota.

  El perfil por departamento va en porcentaje del año de cada uno, no en
  dólares. En dólares Ica y La Libertad aplastan al resto y las cinco curvas
  se vuelven una sola; en porcentaje se ve lo que importa para un canal de
  insumos, que es **cuándo** compra cada región. Ica y Piura no siembran en el
  mismo mes, y un almacén que reparte igual todo el año les llega tarde a las
  dos.

Uso:
    python scripts/build_figs_export.py
"""
import io
import json
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
    "text.color": "#0F1A16",
    "savefig.facecolor": "white",
})

INK, MUTED, LINE = "#0F1A16", "#6E7872", "#D5DBD2"
FOREST, BRASS = "#0F4C3F", "#B07D2E"
SERIE = ["#0F4C3F", "#B07D2E", "#4C8A6B", "#8FB585", "#6E7872"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct",
         "Nov", "Dic"]
PROC = "data/exportaciones/processed"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

M = json.load(io.open(PROC + "/mercado.json", encoding="utf-8"))
R = M["rezago"]
D = M["departamentos"]
TILDE = {"ANCASH": "Áncash", "APURIMAC": "Apurímac", "HUANUCO": "Huánuco",
         "JUNIN": "Junín", "SAN MARTIN": "San Martín",
         "MADRE DE DIOS": "Madre de Dios", "LA LIBERTAD": "La Libertad"}


def nom(n):
    return TILDE.get(str(n).upper(), str(n).title())


def save(fig, name):
    path = "out/fig_%s.png" % name
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    plt.close(fig)
    print("  " + path)


def serie_nacional():
    """FOB mes a mes, con el tramo que todavia regulariza marcado aparte."""
    claves = sorted(M["por_mes"])
    v = np.array([M["por_mes"][k]["fob"] / 1e6 for k in claves])
    x = np.arange(len(claves))
    comp = R["completitud_mes"]
    umbral = R["umbral_completo_pct"]
    parcial = np.array([comp.get(k, 100.0) < umbral for k in claves])

    fig, ax = plt.subplots(figsize=(7.6, 1.68))
    # El tramo cerrado, que es el que se puede leer como serie.
    xc = x[~parcial]
    ax.plot(xc, v[~parcial], color=FOREST, lw=1.5, zorder=4)
    ax.fill_between(xc, 0, v[~parcial], color=FOREST, alpha=.07, zorder=1)
    # El tramo incompleto: mismo dato, otro trazo, y dicho con todas las letras.
    if parcial.any():
        i = int(np.argmax(parcial))
        ax.plot(x[i - 1:], v[i - 1:], color=MUTED, lw=1.2, ls=(0, (2.5, 2)),
                zorder=4)
        ax.axvspan(i - .5, x[-1] + .5, color=LINE, alpha=.35, zorder=0)
        pct = comp.get(claves[i], 0.0)
        ax.annotate("%s\nal %.0f%%: sigue\nregularizando" % (claves[i], pct),
                    (x[-1], v[-1]), xytext=(-4, 26), textcoords="offset points",
                    ha="right", va="bottom", fontsize=6.6, color=MUTED,
                    linespacing=1.35)
    # El maximo de la serie cerrada, que es la referencia de escala.
    j = int(np.argmax(np.where(parcial, -1, v)))
    ax.annotate("{} · US$ {:,.0f} MM".format(claves[j], v[j]),
                (x[j], v[j]), xytext=(0, 9), textcoords="offset points",
                ha="center", fontsize=6.8, color=FOREST, fontweight="bold")

    anios = sorted({k[:4] for k in claves})
    ini = [next(i for i, k in enumerate(claves) if k[:4] == a) for a in anios]
    for i in ini[1:]:
        ax.axvline(i - .5, color=LINE, lw=.7, zorder=1)
    ax.set_xticks([i + 5.5 for i in ini])
    ax.set_xticklabels(anios, fontsize=8, color=INK)
    ax.set_xlim(-.5, x[-1] + .5)
    ax.set_ylim(0, v.max() * 1.30)
    ax.set_ylabel("US$ millones · FOB", fontsize=7.2, color=MUTED)
    ax.tick_params(length=0, labelsize=7, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis="y", color=LINE, lw=.5, alpha=.6)
    ax.set_axisbelow(True)
    save(fig, "export_serie")


def perfil_departamento():
    """Cuando embarca cada region, en % de su propio ano."""
    tops = [d for d in D["lista"][:5] if d.get("perfil")]
    fig, ax = plt.subplots(figsize=(7.6, 1.42))
    x = np.arange(12)
    # Etiquetar en el pico de cada curva parecia lo mas directo, pero La
    # Libertad y Lambayeque pican el mismo mes y los rotulos se tapaban. Una
    # leyenda arriba no compite con los datos y se lee igual.
    for k, d in enumerate(tops):
        p = np.array(d["perfil"])
        ax.plot(x, p, color=SERIE[k], lw=1.7, marker="o", ms=3.0,
                label=nom(d["n"]), zorder=4)
        j = int(np.argmax(p))
        ax.plot([x[j]], [p[j]], marker="o", ms=6.5, mfc="none",
                mec=SERIE[k], mew=1.2, zorder=5)
    leg = ax.legend(loc="upper left", bbox_to_anchor=(0, 1.16), ncol=5,
                    frameon=False, fontsize=7.2, handlelength=1.4,
                    columnspacing=1.6, handletextpad=.5)
    for t in leg.get_texts():
        t.set_color(INK)
    ax.set_xticks(x)
    ax.set_xticklabels(MESES, fontsize=7.2)
    ax.set_ylabel("% del año propio", fontsize=7.2, color=MUTED)
    ax.set_ylim(0, max(max(d["perfil"]) for d in tops) * 1.12)
    ax.tick_params(length=0, labelsize=7, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis="y", color=LINE, lw=.5, alpha=.6)
    ax.set_axisbelow(True)
    save(fig, "export_perfil_dep")


def main():
    print("figuras de exportacion:")
    serie_nacional()
    perfil_departamento()
    u = D["anios_usados"]
    print("serie nacional    : %d meses, %s .. %s"
          % (len(M["por_mes"]), min(M["por_mes"]), max(M["por_mes"])))
    print("perfil por dep    : %s, anios %s-%s"
          % (", ".join(nom(d["n"]) for d in D["lista"][:5]), u[0], u[-1]))
    for d in D["lista"][:5]:
        p = d["perfil"]
        print("  %-14s pico %s (%.0f%% del ano), valle %s"
              % (nom(d["n"]), MESES[int(np.argmax(p))], max(p),
                 MESES[int(np.argmin(p))]))


if __name__ == "__main__":
    main()
