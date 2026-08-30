# -*- coding: utf-8 -*-
"""Build the monthly input-demand calendar from MIDAGRI's per-crop sheets.

The market model says how much money exists and where. It does not say *when*,
and in agriculture that is half the problem: inputs are bought against the
crop calendar, not spread evenly through the year.

Two crop families, two calendars:

  Transitory crops  Each sheet stacks five tables (sown area, harvested area,
                    production, yield, farm-gate price). Only the first —
                    "Superficie sembrada", laid out Aug→Jul — is a sowing
                    calendar; the rest must not be summed into it. Demand is
                    placed in the month of sowing, when the purchase happens.

  Permanent crops   Perennials have no sowing month; their sheet reports
                    standing area for the year. Their maintenance inputs are
                    spread evenly across the twelve months, which is an
                    assumption and is labelled as one in every output.
"""
import re
import unicodedata

import pandas as pd

TC = 3.75
SRC = "data/anuario_agricola_2023.xlsx"
MESES = ["Ago", "Set", "Oct", "Nov", "Dic", "Ene", "Feb", "Mar", "Abr", "May",
         "Jun", "Jul"]
ORDEN_CAL = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set",
             "Oct", "Nov", "Dic"]


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima"}


def key(s):
    k = slug(s)
    # A few sheets carry a corrupted "Madre de Dios" ("sandre de Dios",
    # "tomare de Dios"): a spreadsheet find-replace that hit the region label.
    if k.endswith("rededios") or k.endswith("dedios"):
        k = "madrededios"
    return FIX.get(k, k)


cos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
cos["slug"] = cos["cultivo"].map(slug)
COST = dict(zip(cos["slug"], (cos["fertilizantes"] + cos["plaguicidas"]) / TC))
MED = ((cos["fertilizantes"] + cos["plaguicidas"]) / TC).median()

ALIAS = {"arroz": "arroz", "arrozcascara": "arroz", "cafepergamino": "cafe",
         "cafe": "cafe", "maizaduro": "maizamarilloduro",
         "maizamilaceo": "maizchoclo", "canaparaazucar": "canadeazucarparaazucar",
         "canaparaalcohol": "canadeazucarparaalcohol",
         "canaparaetanol": "canadeazucarparaetanol", "limonsutil": "limon",
         "limondulce": "limon", "ajipaprika": "paprika",
         "algodonrama": "algodon", "banano": "platano", "papatotal": "papa",
         "cebollacabeza": "cebolla", "cebollachina": "cebolla",
         "pastoelefante": "alfalfa", "braquearia": "alfalfa",
         "ryegrass": "alfalfa", "avenaforrajera": "alfalfa",
         "cebadaforrajera": "alfalfa", "gramalote": "alfalfa",
         "gramaazul": "alfalfa", "gramachilena": "alfalfa", "trebol": "alfalfa",
         "trigo": "cebada", "avenagrano": "cebada", "cebadagrano": "cebada",
         "olivo": "aceituna", "palto": "palta", "vid": "uva",
         "frijolseco": "pallargranoseco", "frijolcastilla": "pallargranoseco",
         "frijolverde": "habagranoverde", "habaseca": "pallargranoseco",
         "habaverde": "habagranoverde", "arvejagranoseco": "pallargranoseco",
         "arvejagranoverde": "habagranoverde", "pallarseco": "pallargranoseco",
         "pallarverde": "habagranoverde", "vainita": "habagranoverde"}


def spend(crop):
    s = slug(crop)
    return COST.get(ALIAS.get(s, s), COST.get(s, MED))


SALTAR = {"Indice", "siembras", "cosecha", "producción", "produccion", "rdto",
          "precio", "TRANSITORIOS", "PERMANENTES"}


def bloque_sembrada(raw):
    """Return (header_row, first_row, last_row) of the 'sembrada' table."""
    titulos = []
    for i in range(len(raw)):
        v = str(raw.iat[i, 0])
        if v.strip().lower().startswith("cuadro"):
            fila = " ".join(str(x) for x in raw.iloc[i].tolist())
            titulos.append((i, fila.lower()))
    if not titulos:
        return None
    inicio = None
    for n, (i, t) in enumerate(titulos):
        if "sembrada" in t:
            fin = titulos[n + 1][0] if n + 1 < len(titulos) else len(raw)
            inicio = (i, fin)
            break
    if inicio is None:
        return None
    i0, fin = inicio
    for h in range(i0, min(i0 + 6, fin)):
        vals = [str(v).strip() for v in raw.iloc[h].tolist()]
        if sum(m in vals for m in MESES) >= 10:
            return h, h + 1, fin
    return None


xls = pd.ExcelFile(SRC)
filas, permanentes, sin_leer = [], [], []

for hoja in xls.sheet_names:
    if hoja in SALTAR:
        continue
    raw = xls.parse(hoja, header=None)
    usd_ha = spend(hoja)
    blk = bloque_sembrada(raw)

    if blk:                                   # transitory: real sowing months
        h, a, b = blk
        cols = [str(v).strip() for v in raw.iloc[h].tolist()]
        idx = {m: cols.index(m) for m in MESES if m in cols}
        body = raw.iloc[a:b]
        body = body[body[0].apply(lambda v: isinstance(v, str) and len(v.strip()) > 2)]
        for _, r in body.iterrows():
            dep = str(r[0]).strip()
            if dep.lower().startswith(("nacional", "campa", "total", "fuente")):
                continue
            for m, c in idx.items():
                ha = pd.to_numeric(r[c], errors="coerce")
                if pd.notna(ha) and ha > 0:
                    filas.append({"cultivo": hoja, "tipo": "transitorio",
                                  "dep": dep, "mes": m, "ha": float(ha),
                                  "usd_ha": usd_ha,
                                  "demanda_usd": float(ha) * usd_ha})
        continue

    # Permanent crops: one annual table with a "Superficie (ha)" column. These
    # sheets are not anchored at column 0 — several start sixteen columns in —
    # so both the name and the value column are located from the header row.
    hdr = csup = cname = None
    for i in range(min(10, len(raw))):
        vals = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if any(v.startswith("superficie") for v in vals) and any(
                v.startswith(("regi", "regi�n")) for v in vals):
            hdr = i
            csup = next(j for j, v in enumerate(vals) if v.startswith("superficie"))
            cname = next(j for j, v in enumerate(vals) if v.startswith("regi"))
            break
    if hdr is None:
        sin_leer.append(hoja)
        continue
    # stop before the next "Cuadro", which starts a different table
    fin = len(raw)
    for i in range(hdr + 1, len(raw)):
        if any(str(v).strip().lower().startswith("cuadro") for v in raw.iloc[i].tolist()):
            fin = i
            break
    body = raw.iloc[hdr + 1:fin]
    body = body[body[cname].apply(
        lambda v: isinstance(v, str) and len(v.strip()) > 2)]
    permanentes.append(hoja)
    for _, r in body.iterrows():
        dep = str(r[cname]).strip()
        if dep.lower().startswith(("nacional", "total", "fuente")):
            continue
        ha = pd.to_numeric(r[csup], errors="coerce")
        if pd.isna(ha) or ha <= 0:
            continue
        for m in ORDEN_CAL:                   # spread evenly: declared assumption
            filas.append({"cultivo": hoja, "tipo": "permanente", "dep": dep,
                          "mes": m, "ha": float(ha) / 12, "usd_ha": usd_ha,
                          "demanda_usd": float(ha) / 12 * usd_ha})

d = pd.DataFrame(filas)
d["k"] = d["dep"].map(key)
d = d[d["k"] != ""]
d.to_csv("out/estacionalidad_detalle.csv", index=False, encoding="utf-8-sig")

nac = (d.groupby("mes").agg(ha=("ha", "sum"), demanda=("demanda_usd", "sum"))
       .reindex(ORDEN_CAL).fillna(0))
nac["pct"] = 100 * nac["demanda"] / nac["demanda"].sum()
nac.to_csv("out/estacionalidad_nacional.csv", encoding="utf-8-sig")

piv = (d.pivot_table(index="k", columns="mes", values="demanda_usd",
                     aggfunc="sum", fill_value=0)
       .reindex(columns=ORDEN_CAL, fill_value=0))
piv["total"] = piv.sum(axis=1)
piv["mes_pico"] = piv[ORDEN_CAL].idxmax(axis=1)
piv["pct_pico"] = 100 * piv[ORDEN_CAL].max(axis=1) / piv["total"]
piv["pct_top4"] = 100 * piv[ORDEN_CAL].apply(
    lambda r: r.nlargest(4).sum(), axis=1) / piv["total"]
piv = piv.sort_values("total", ascending=False)
piv.to_csv("out/estacionalidad_region.csv", encoding="utf-8-sig")

tr = d[d.tipo == "transitorio"]
pe = d[d.tipo == "permanente"]
print(f"cultivos transitorios : {tr.cultivo.nunique():>3}   "
      f"{tr.ha.sum():>12,.0f} ha sembradas")
print(f"cultivos permanentes  : {pe.cultivo.nunique():>3}   "
      f"{pe.ha.sum():>12,.0f} ha en pie")
print(f"hojas no leidas       : {len(sin_leer)}  {sin_leer[:5]}")
print(f"demanda anual modelada: US$ {d.demanda_usd.sum()/1e6:,.0f} MM")
print()
print("--- CURVA NACIONAL DE DEMANDA DE INSUMOS ---")
for m, r in nac.iterrows():
    print(f"  {m}  US$ {r['demanda']/1e6:5,.0f} MM  {r['pct']:4.1f}%  "
          + "#" * int(round(r["pct"] * 3.2)))
pico = nac["pct"].idxmax()
top4 = nac["pct"].nlargest(4)
print(f"\nmes pico: {pico} ({nac.loc[pico,'pct']:.1f}%)   "
      f"4 meses = {top4.sum():.0f}%  ({', '.join(top4.index)})")
print()
print("--- POR REGION (top 12) ---")
show = piv.head(12)[["total", "mes_pico", "pct_pico", "pct_top4"]].copy()
show["total"] = (show["total"] / 1e6).round(1)
show.columns = ["demanda_MM", "mes_pico", "%_pico", "%_top4"]
print(show.to_string(float_format=lambda v: f"{v:,.1f}"))
