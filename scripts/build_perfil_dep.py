# -*- coding: utf-8 -*-
"""Build the per-department profile data that the regional fiches need.

The national model answers "where should we go". A fiche has to answer "what
will we find when we get there", so each department gets its crop mix, its
buying behaviour, its prospect count and a one-line commercial read.
"""
import re
import unicodedata

import pandas as pd


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima",
       "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


TC = 3.75
mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
cos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")
sec = pd.read_csv("out/modelo_v2_sector.csv", encoding="utf-8-sig")
for d in (mod, emb, cen, sec):
    d["k"] = d["dep"].map(key)

try:
    pros = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
    pros["k"] = pros["dep"].map(key)
    FUNDO = r"fundo|hacienda|agr[ií]cola|agroindustri"
    pros["es_fundo"] = pros["nombre"].str.contains(FUNDO, case=False, na=False)
    pcount = pros.groupby("k").agg(prospectos=("nombre", "size"),
                                   fundos=("es_fundo", "sum")).reset_index()
except FileNotFoundError:
    pcount = pd.DataFrame({"k": [], "prospectos": [], "fundos": []})

# ---- crop mix, rebuilt from the yearbook the same way the model reads it ----
sheet = pd.read_excel("data/anuario_agricola_2023.xlsx", sheet_name="cosecha",
                      header=None)
blocks = []
for i in range(len(sheet)):
    if not str(sheet.iat[i, 0]).strip().lower().startswith("regi"):
        continue
    names = [str(v).strip() for v in sheet.iloc[i].tolist()[1:]]
    body = sheet.iloc[i + 1:i + 30]
    body = body[body[0].apply(lambda v: isinstance(v, str) and len(v.strip()) > 2)]
    for col, crop in enumerate(names, start=1):
        if crop in ("nan", ""):
            continue
        blocks.append(pd.DataFrame({
            "dep": body[0].str.strip(), "cultivo": crop,
            "ha": pd.to_numeric(body[col], errors="coerce")}))

long = pd.concat(blocks, ignore_index=True)
long = long[(long.ha.fillna(0) > 0) & (~long.dep.str.lower().eq("nacional"))]
long["k"] = long["dep"].map(key)

cos["slug"] = cos["cultivo"].map(slug)
COST = dict(zip(cos["slug"], (cos["fertilizantes"] + cos["plaguicidas"]) / TC))
MED = ((cos["fertilizantes"] + cos["plaguicidas"]) / TC).median()

ALIAS = {"arrozcascara": "arroz", "cafepergamino": "cafe", "maizaduro": "maizamarilloduro",
         "maizamilaceo": "maizchoclo", "cañaparaazucar": "canadeazucarparaazucar",
         "canaparaazucar": "canadeazucarparaazucar", "limonsutil": "limon",
         "ajipaprika": "paprika", "algodonrama": "algodon", "banano": "platano",
         "pastoelefante": "alfalfa", "braquearia": "alfalfa", "ryegrass": "alfalfa",
         "avenaforrajera": "alfalfa", "cebadaforrajera": "alfalfa",
         "arandanos": "arandanos", "cebollacabeza": "cebolla"}


def spend(c):
    s = slug(c)
    return COST.get(ALIAS.get(s, s), COST.get(s, MED))


long["usd_ha"] = long["cultivo"].map(spend)
long["gasto"] = long["ha"] * long["usd_ha"]

# Two different questions: what covers the ground, and what pays the bill.
top_ha = (long.sort_values("ha", ascending=False).groupby("k").head(5)
          .groupby("k").apply(
              lambda g: [(r.cultivo, r.ha, r.usd_ha) for r in g.itertuples()],
              include_groups=False).rename("top_ha"))
top_gasto = (long.sort_values("gasto", ascending=False).groupby("k").head(5)
             .groupby("k").apply(
                 lambda g: [(r.cultivo, r.gasto, r.usd_ha) for r in g.itertuples()],
                 include_groups=False).rename("top_gasto"))

perfil = (mod.merge(cen[["k", "productores", "ua_objetivo_5_mas", "ua_micro_0_5",
                         "ua_pequeno_5_20", "ua_mediano_20_100", "ua_grande_100_mas"]],
                    on="k", how="left")
          .merge(emb[["k", "tasa_fert", "tasa_pest", "tasa_credito",
                      "compran_a_credito"]], on="k", how="left", suffixes=("", "_e"))
          .merge(pcount, on="k", how="left")
          .join(top_ha, on="k").join(top_gasto, on="k"))
perfil["prospectos"] = perfil["prospectos"].fillna(0).astype(int)
perfil["fundos"] = perfil["fundos"].fillna(0).astype(int)
perfil["sectores"] = perfil["k"].map(sec.groupby("k").size())
perfil["ha_agricola"] = perfil["k"].map(sec.groupby("k")["ha_agricola"].sum())
perfil["region_nat"] = perfil["k"].map(
    sec.groupby("k")["region_nat"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else ""))
perfil["uso_ha"] = perfil["ha_cosechada"] / perfil["ha_agricola"]

perfil.to_pickle("out/perfil_dep.pkl")
perfil.drop(columns=["top_ha", "top_gasto"]).to_csv(
    "out/perfil_departamento.csv", index=False, encoding="utf-8-sig")

print(f"perfiles: {len(perfil)}")
print(perfil[["rank", "dep", "sectores", "ha_cosechada", "uso_ha", "gasto_ha",
              "clientes_sam", "prospectos", "fundos"]]
      .sort_values("rank")
      .to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
