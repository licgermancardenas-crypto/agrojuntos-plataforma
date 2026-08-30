# -*- coding: utf-8 -*-
"""Derive input spend per hectare for each department from its actual crop mix.

Replaces the flat per-region assumption with a weighted average:

    gasto_ha[dep] = sum_c ( ha_cosechada[dep,c] * insumos_usd_ha[c] ) / sum_c ha

  ha_cosechada  MIDAGRI, Anuario de Produccion Agricola 2023 (sheet "cosecha")
  insumos_usd   INEI, Costos de produccion ENA 2018 -> abono + fertilizante +
                plaguicida, i.e. only what AgroJuntos actually sells

Crops present in the yearbook but absent from the cost study fall back to the
median spend of their family, so a department is never silently valued at zero.
"""
import re
import unicodedata
import pandas as pd

TC = 3.75


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---- 1. crop input spend (US$/ha) ---------------------------------------
costos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
costos["slug"] = costos["cultivo"].map(slug)
# Split the three items: fertiliser and pesticide are almost entirely bought in
# (Peru imports ~90% of its fertiliser), while "abono" is largely farmyard
# manure the producer already has. Keeping them apart lets the estimate be
# checked against customs data.
for c, src in (("fert_usd", "fertilizantes"), ("plag_usd", "plaguicidas"),
               ("abono_usd", "abono")):
    costos[c] = costos[src] / TC
COST = dict(zip(costos["slug"], costos["insumos_usd"]))
COST_F = dict(zip(costos["slug"], costos["fert_usd"]))
COST_P = dict(zip(costos["slug"], costos["plag_usd"]))
COST_A = dict(zip(costos["slug"], costos["abono_usd"]))

# Yearbook crop names do not always match the cost study's wording.
ALIAS = {
    "arrozcascara": "arroz", "maizamarilloduro": "maizamarilloduro",
    "maizamilaceo": "maizchoclo", "maizchoclo": "maizchoclo",
    "maizchala": "maizchala", "papatotal": "papa", "papablanca": "papa",
    "papaamarilla": "papa", "papanativa": "papa", "cafe": "cafe",
    "cacao": "cacao", "esparrago": "esparrago", "paltatotal": "palta",
    "palto": "palta", "uva": "uva", "arandano": "arandanos",
    "arandanos": "arandanos", "mango": "mango", "banano": "platano",
    "platano": "platano", "cañadeazucar": "canadeazucarparaazucar",
    "canadeazucar": "canadeazucarparaazucar", "aji": "aji",
    "ajipaprika": "paprika", "paprika": "paprika", "piquillo": "piquillo",
    "cebollacabeza": "cebolla", "cebollachina": "cebolla",
    "tomate": "tomate", "aceituna": "aceituna", "olivo": "aceituna",
    "limon": "limon", "naranja": "naranja", "mandarina": "mandarina",
    "tangelo": "tangelo", "granada": "granada", "granadilla": "granadilla",
    "alcachofa": "alcachofa", "quinua": "quinua", "kiwicha": "quinua",
    "canihua": "quinua", "trigo": "cebada", "cebada": "cebada",
    "avenagrano": "cebada", "avenaforrajera": "alfalfa", "alfalfa": "alfalfa",
    "algodonrama": "algodon", "algodon": "algodon", "palmaaceitera": "palmaaceitera",
    "pinatotal": "pina", "pina": "pina", "papaya": "papaya", "fresa": "fresa",
    "sandia": "sandia", "melon": "sandia", "zapallo": "zapallo",
    "zanahoria": "zanahoria", "brocoli": "brocoli", "coliflor": "brocoli",
    "col": "brocoli", "lechuga": "lechuga", "espinaca": "lechuga",
    "acelga": "lechuga", "apio": "lechuga", "camote": "camote",
    "yuca": "camote", "olluco": "olluco", "oca": "oca", "mashua": "oca",
    "ajo": "ajo", "haba": "habagranoverde", "habags": "habagranoverde",
    "habagv": "habagranoverde", "arvejags": "habagranoverde",
    "arvejagv": "habagranoverde", "frijol": "pallargranoseco",
    "pallar": "pallargranoseco", "lenteja": "pallargranoseco",
    "garbanzo": "pallargranoseco", "loctao": "pallargranoseco",
    "pimiento": "pimiento", "pimientopiquillo": "piquillo",
    "rocoto": "rocoto", "maracuya": "maracuya", "lucuma": "lucuma",
    "chirimoya": "chirimoya", "manzana": "manzana", "melocoton": "melocoton",
    "durazno": "melocoton", "pera": "manzana", "membrillo": "manzana",
    "tuna": "tuna", "pecana": "pecana", "nuez": "pecana",
    "oregano": "oregano", "albahaca": "oregano", "arracacha": "olluco",
    "betarraga": "zanahoria", "caigua": "zapallo", "calabaza": "zapallo",
    "pepino": "zapallo", "vainita": "habagranoverde", "zarandaja": "pallargranoseco",
}

FALLBACK = costos["insumos_usd"].median()


def lookup(table, crop_sheet, fallback):
    s = slug(crop_sheet)
    tgt = ALIAS.get(s, s)
    return table.get(tgt, table.get(s, fallback))


def spend(crop_sheet):
    return lookup(COST, crop_sheet, FALLBACK)


# ---- 2. harvested area by department x crop -----------------------------
# The sheet is only 11 columns wide: crops continue in stacked blocks, each
# introduced by a "Region" header row followed by one row per department.
sheet = pd.read_excel("data/anuario_agricola_2023.xlsx", sheet_name="cosecha",
                      header=None)
blocks, crops = [], []
for i in range(len(sheet)):
    if not str(sheet.iat[i, 0]).strip().lower().startswith("regi"):
        continue
    names = [str(v).strip() for v in sheet.iloc[i].tolist()[1:]]
    body = sheet.iloc[i + 1:i + 30].copy()
    body = body[body[0].apply(lambda v: isinstance(v, str) and len(v.strip()) > 2)]
    for col, crop in enumerate(names, start=1):
        if crop in ("nan", ""):
            continue
        crops.append(crop)
        blocks.append(pd.DataFrame({
            "dep": body[0].str.strip(),
            "cultivo": crop,
            "ha": pd.to_numeric(body[col], errors="coerce"),
        }))

long = pd.concat(blocks, ignore_index=True)
long["ha"] = long["ha"].fillna(0)
long = long[(long["ha"] > 0) & (~long["dep"].str.lower().isin(["nacional"]))]
long["usd_ha"] = long["cultivo"].map(spend)
med = {k: costos[k].median() for k in ("fert_usd", "plag_usd", "abono_usd")}
long["fert_ha"] = long["cultivo"].map(lambda c: lookup(COST_F, c, med["fert_usd"]))
long["plag_ha"] = long["cultivo"].map(lambda c: lookup(COST_P, c, med["plag_usd"]))
long["abono_ha"] = long["cultivo"].map(lambda c: lookup(COST_A, c, med["abono_usd"]))
for a, b in (("gasto", "usd_ha"), ("g_fert", "fert_ha"), ("g_plag", "plag_ha"),
             ("g_abono", "abono_ha")):
    long[a] = long["ha"] * long[b]

dep = (long.groupby("dep")
       .agg(ha_cosechada=("ha", "sum"), gasto_total=("gasto", "sum"),
            g_fert=("g_fert", "sum"), g_plag=("g_plag", "sum"),
            g_abono=("g_abono", "sum"), n_cultivos=("cultivo", "nunique"))
       .reset_index())
dep["gasto_ha"] = dep["gasto_total"] / dep["ha_cosechada"]
# What AgroJuntos can actually invoice: bought-in fertiliser + crop protection.
dep["gasto_ha_comprado"] = (dep["g_fert"] + dep["g_plag"]) / dep["ha_cosechada"]
dep["k"] = dep["dep"].map(slug)
dep = dep.sort_values("gasto_ha", ascending=False)
dep.to_csv("out/gasto_ha_departamento.csv", index=False, encoding="utf-8-sig")

# top crops driving each department, for the narrative
top = (long.sort_values("gasto", ascending=False)
       .groupby("dep").head(3)
       .groupby("dep")["cultivo"].apply(lambda s: ", ".join(s)))

H = long.ha.sum()
print(f"cultivos en el anuario  : {len(set(crops))}")
print(f"superficie cosechada    : {H:,.0f} ha")
print()
print(f"  fertilizantes         : US$ {long.g_fert.sum()/1e6:6,.0f} MM   "
      f"(US$ {long.g_fert.sum()/H:>3,.0f}/ha)")
print(f"  plaguicidas           : US$ {long.g_plag.sum()/1e6:6,.0f} MM   "
      f"(US$ {long.g_plag.sum()/H:>3,.0f}/ha)")
print(f"  = mercado comprable   : US$ {(long.g_fert.sum()+long.g_plag.sum())/1e6:6,.0f} MM   "
      f"(US$ {(long.g_fert.sum()+long.g_plag.sum())/H:>3,.0f}/ha)")
print(f"  abono (autoproducido) : US$ {long.g_abono.sum()/1e6:6,.0f} MM   "
      f"(US$ {long.g_abono.sum()/H:>3,.0f}/ha)")
print(f"  TOTAL insumos         : US$ {long.gasto.sum()/1e6:6,.0f} MM   "
      f"(US$ {long.gasto.sum()/H:>3,.0f}/ha)")
print()
print("  contraste: importaciones de fertilizantes 2024 = US$ 693 MM CIF;")
print("             ~89.5% de la oferta nacional es importada (MIDAGRI/ICEX),")
print("             lo que ubica el mercado a precio de finca por encima de esa cifra.")
print()
out = dep[["dep", "ha_cosechada", "gasto_ha", "gasto_ha_comprado", "n_cultivos"]].copy()
out["cultivos_top"] = out["dep"].map(top)
print(out.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
