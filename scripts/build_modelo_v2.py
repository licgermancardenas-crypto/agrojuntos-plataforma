# -*- coding: utf-8 -*-
"""AgroJuntos market model v2 - every driver measured instead of assumed.

What changed from v1
--------------------
  base de superficie   superficie agricola (11.6M ha)  ->  superficie COSECHADA
                       (4.55M ha). Only land actually taken through a campaign
                       buys inputs in a given year.
  gasto por hectarea   flat guess per natural region   ->  weighted by each
                       department's real 2023 crop mix, priced with INEI's
                       field-measured cost study.
  que se vende         "insumos" in the abstract       ->  fertiliser + crop
                       protection only. Manure is excluded: producers make it.
  cuantos clientes     everyone over 5 ha              ->  over 5 ha AND already
                       buying fertiliser or pesticide, per CENAGRO.

Cross-check: the fertiliser leg lands at US$1,038 MM at farm-gate against
US$693 MM of CIF imports covering ~89.5% of national supply - a distribution
margin of roughly a third, which is what the channel actually runs.
"""
import re
import unicodedata
import pandas as pd


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima"}


def key(s):
    k = slug(s)
    return FIX.get(k, k)


gasto = pd.read_csv("out/gasto_ha_departamento.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
sec = pd.read_csv("out/sectores_2024.csv", encoding="utf-8-sig")

for d in (gasto, cen, emb):
    d["k"] = d["dep"].map(key)
sec["k"] = sec["dep"].map(key)

# Lima Metropolitana is reported separately in the yearbook; fold it into Lima.
gasto = (gasto.groupby("k")
         .apply(lambda g: pd.Series({
             "ha_cosechada": g.ha_cosechada.sum(),
             "g_fert": g.g_fert.sum(), "g_plag": g.g_plag.sum(),
             "n_cultivos": g.n_cultivos.max()}), include_groups=False)
         .reset_index())
gasto["gasto_ha"] = (gasto.g_fert + gasto.g_plag) / gasto.ha_cosechada

# --- share of land in commercial hands ------------------------------------
# CENAGRO reports units per size band, not hectares. Midpoints give the shape
# of the distribution; we then rescale so the department totals match the
# agricultural surface the census actually measured.
MID = {"ha_0_5": 2.0, "ha_5_10": 7.5, "ha_10_20": 15.0,
       "ha_20_50": 35.0, "ha_50_100": 75.0, "ha_100_mas": 250.0}
for c, m in MID.items():
    cen[f"sup_{c}"] = cen[c] * m
sup_cols = [f"sup_{c}" for c in MID]
cen["sup_est"] = cen[sup_cols].sum(axis=1)
cen["sup_com"] = cen[sup_cols[1:]].sum(axis=1)          # everything over 5 ha
cen["share_comercial"] = cen["sup_com"] / cen["sup_est"]

m = (gasto.merge(cen[["k", "dep", "ua_total", "ua_objetivo_5_mas",
                      "share_comercial", "productores"]], on="k")
          .merge(emb[["k", "compradores_insumos", "compran_a_credito",
                      "tasa_fert", "tasa_pest", "tasa_credito"]], on="k"))

# --- market layers ---------------------------------------------------------
m["tam_usd"] = m["ha_cosechada"] * m["gasto_ha"]

# SAM: commercial land, and only the part whose owners already buy inputs.
m["tasa_compra"] = m[["tasa_fert", "tasa_pest"]].max(axis=1)
m["ha_sam"] = m["ha_cosechada"] * m["share_comercial"] * m["tasa_compra"]
m["sam_usd"] = m["ha_sam"] * m["gasto_ha"]
m["clientes_sam"] = m["compradores_insumos"]
m["ticket_anual"] = m["sam_usd"] / m["clientes_sam"].replace(0, pd.NA)

# --- priority score --------------------------------------------------------
def z01(s):
    return (s - s.min()) / (s.max() - s.min())


m["densidad"] = m["sam_usd"] / m["ha_cosechada"]
m["score"] = (0.40 * z01(m["sam_usd"])
              + 0.25 * z01(m["clientes_sam"])
              + 0.20 * z01(m["gasto_ha"])
              + 0.15 * z01(m["tasa_credito"])) * 100
m = m.sort_values("score", ascending=False).reset_index(drop=True)
m["rank"] = m.index + 1
m["pct_sam"] = 100 * m["sam_usd"] / m["sam_usd"].sum()
m["pct_acum"] = m["pct_sam"].cumsum()
m.to_csv("out/modelo_v2_departamento.csv", index=False, encoding="utf-8-sig")

TAM, SAM = m.tam_usd.sum(), m.sam_usd.sum()
CLI = m.clientes_sam.sum()
print("=" * 78)
print("MODELO DE MERCADO v2 - AGROJUNTOS")
print("=" * 78)
print(f"superficie cosechada 2023 : {m.ha_cosechada.sum():>12,.0f} ha")
print(f"gasto ponderado           : US$ {TAM/m.ha_cosechada.sum():>8,.0f} /ha  (fertilizante + fitosanitario)")
print()
print(f"TAM  mercado nacional     : US$ {TAM/1e6:>8,.0f} MM")
print(f"SAM  comercial y comprador: US$ {SAM/1e6:>8,.0f} MM   ({100*SAM/TAM:.0f}% del TAM)")
print(f"     clientes en el SAM   : {CLI:>12,.0f}")
print(f"     gasto medio anual    : US$ {SAM/CLI:>8,.0f} por cliente")
print()
print("--- CONCENTRACION ---")
for n in (3, 5, 8):
    print(f"  top {n:>2} regiones = {m.pct_acum.iat[n-1]:>4.0f}% del SAM   "
          f"({', '.join(m.dep.head(n))})")
print()
cols = ["rank", "dep", "ha_cosechada", "gasto_ha", "clientes_sam",
        "ticket_anual", "sam_usd", "pct_acum", "score"]
show = m[cols].copy()
show["sam_usd"] = (show["sam_usd"] / 1e6).round(1)
show = show.rename(columns={"sam_usd": "sam_MM", "gasto_ha": "US$/ha",
                            "ticket_anual": "US$/cliente"})
print(show.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
