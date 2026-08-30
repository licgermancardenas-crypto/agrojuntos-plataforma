# -*- coding: utf-8 -*-
"""Extract per-hectare input spend by crop from INEI's cost study (ENA 2018).

This replaces the flat regional assumption in the market model with a figure
measured in the field. AgroJuntos sells nutrition and crop protection, so the
addressable spend is exactly three of INEI's cost items:

    Abono + Fertilizantes + Plaguicidas

Labour, land rent, fuel and irrigation are real costs but nothing we can sell,
so they stay out. Each crop table gives cost, max, min and percent share; we
keep the mean cost.
"""
import re
import fitz
import pandas as pd

PDF = "data/inei_costos.pdf"
ITEMS = ["Abono", "Fertilizantes", "Plaguicidas", "Semillas", "Jornales",
         "Riego", "Asistencia técnica"]
# INEI's PDF text layer mangles accents; match on a skeleton instead.
ASCII = {"Asistencia técnica": "Asistencia t"}


def num(t):
    t = t.strip().replace("\xa0", "").replace(" ", "")
    if t in ("-", "–", "—", ""):
        return 0.0
    t = t.replace(",", ".")
    # thousands were space-separated, already stripped above
    return float(t)


rows = []
doc = fitz.open(PDF)
for pg in doc:
    t = pg.get_text()
    m = re.search(r"Costos promedio de producci\S*n de (.{2,40}?) por hect", t, re.S)
    if not m:
        continue
    crop = re.sub(r"\s+", " ", m.group(1)).strip().lower()
    crop = re.sub(r"[^a-záéíóúñ \-]", "", crop).strip()
    lines = [l.strip() for l in t.split("\n") if l.strip()]

    rec = {"cultivo": crop}
    for i, l in enumerate(lines):
        label = None
        if l == "Total":
            label = "total"
        else:
            for it in ITEMS:
                probe = ASCII.get(it, it)
                if l.startswith(probe):
                    label = it.lower().replace(" ", "_").replace("é", "e")
                    break
        if not label or label in rec:
            continue
        # value is the next numeric-looking line
        for j in range(i + 1, min(i + 3, len(lines))):
            try:
                rec[label] = num(lines[j])
                break
            except ValueError:
                continue
    if "total" in rec:
        rows.append(rec)

df = pd.DataFrame(rows).fillna(0.0)
df = df.drop_duplicates(subset="cultivo", keep="first")

# The three items AgroJuntos actually sells into.
df["insumos_soles"] = df["abono"] + df["fertilizantes"] + df["plaguicidas"]
df["pct_insumos"] = 100 * df["insumos_soles"] / df["total"].replace(0, pd.NA)

TC = 3.75
df["insumos_usd"] = df["insumos_soles"] / TC
df["total_usd"] = df["total"] / TC

df = df.sort_values("insumos_usd", ascending=False)
df.to_csv("out/costos_cultivo.csv", index=False, encoding="utf-8-sig")

print(f"cultivos extraidos: {len(df)}   (tipo de cambio S/{TC}/US$)\n")
show = df[["cultivo", "total_usd", "abono", "fertilizantes", "plaguicidas",
           "insumos_usd", "pct_insumos"]].copy()
show.columns = ["cultivo", "costo_total_US$", "abono_S/", "fertiliz_S/",
                "plaguic_S/", "INSUMOS_US$/ha", "%_del_costo"]
print(show.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
print()
w = df[df.insumos_usd > 0]
print(f"mediana insumos: US$ {w.insumos_usd.median():,.0f}/ha   "
      f"promedio: US$ {w.insumos_usd.mean():,.0f}/ha")
print(f"los insumos son el {w.pct_insumos.median():.1f}% del costo de produccion (mediana)")
