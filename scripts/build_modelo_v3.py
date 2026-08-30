# -*- coding: utf-8 -*-
"""AgroJuntos market model v3 — adds logistics and seasonality to the score.

v2 answered how much and where. It could not distinguish a valley forty
minutes from Trujillo from one nine hours up the Amazon, and it treated a
region whose demand arrives in one month the same as one that buys all year.
Both distinctions decide whether a territory is worth an operation.

What enters the score now, and why each is there:

  mercado (35%)      the SAM. Still the ceiling on any operation.
  clientes (20%)     producers who already buy inputs, not merely hold land.
  accesibilidad(15%) share of the region's sectors within two hours of a
                     provincial capital — a delivery business lives on this.
  gasto/ha (10%)     how much each visit is worth.
  credito (10%)      producers already buying on terms: AgroJuntos' wedge.
  continuidad (10%)  how evenly demand falls across the year. A region that
                     buys in one month needs a campaign, not a branch.
"""
import re
import unicodedata

import numpy as np
import pandas as pd


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima"}


def key(s):
    return FIX.get(slug(s), slug(s))


mod = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
log = pd.read_csv("out/logistica_departamento.csv", encoding="utf-8-sig")
est = pd.read_csv("out/estacionalidad_region.csv", encoding="utf-8-sig")
for d in (mod, log):
    d["k"] = d["dep"].map(key)
est = est.rename(columns={"k": "k"})

m = (mod.merge(log[["k", "horas_capital", "horas_puerto", "km_puerto",
                    "pct_bajo_2h", "pct_sobre_4h", "costo_viaje", "puerto"]],
               on="k", how="left")
        .merge(est[["k", "mes_pico", "pct_pico", "pct_top4", "total"]]
               .rename(columns={"total": "demanda_anual"}), on="k", how="left"))

# Continuity: a perfectly flat year puts 33% of demand in its busiest four
# months. The further above that, the more the region is a campaign.
m["continuidad"] = 100 - m["pct_top4"]

# Delivery cost against what an average client spends in a year.
m["costo_pct_ticket"] = 100 * m["costo_viaje"] / m["ticket_anual"]


def z01(s):
    s = s.astype(float)
    return (s - s.min()) / (s.max() - s.min())


PESOS = {"sam_usd": 0.35, "clientes_sam": 0.20, "pct_bajo_2h": 0.15,
         "gasto_ha": 0.10, "tasa_credito": 0.10, "continuidad": 0.10}
m["score_v3"] = sum(p * z01(m[c]) for c, p in PESOS.items()) * 100

m["rank_v2"] = m["rank"]
m = m.sort_values("score_v3", ascending=False).reset_index(drop=True)
m["rank_v3"] = m.index + 1
m["mov"] = m["rank_v2"] - m["rank_v3"]
m["pct_sam_v3"] = 100 * m["sam_usd"] / m["sam_usd"].sum()
m["pct_acum_v3"] = m["pct_sam_v3"].cumsum()

# Territory archetype: what kind of operation the region actually needs.
def arquetipo(r):
    if r["horas_capital"] > 4:
        return "Inviable por ahora"
    if r["ticket_anual"] >= 5000 and r["pct_bajo_2h"] >= 75:
        return "Venta directa consultiva"
    if r["clientes_sam"] >= 10000 and r["ticket_anual"] < 3500:
        return "Red de canal"
    if r["pct_top4"] >= 65:
        return "Campana estacional"
    return "Operacion mixta"


m["arquetipo"] = m.apply(arquetipo, axis=1)
m.to_csv("out/modelo_v3_departamento.csv", index=False, encoding="utf-8-sig")

print("=" * 92)
print("MODELO v3 — mercado + logistica + estacionalidad")
print("=" * 92)
cols = ["rank_v3", "dep", "mov", "sam_usd", "clientes_sam", "pct_bajo_2h",
        "horas_puerto", "mes_pico", "pct_top4", "arquetipo", "score_v3"]
show = m[cols].copy()
show["sam_usd"] = (show["sam_usd"] / 1e6).round(0)
show["mov"] = show["mov"].map(lambda v: f"+{v}" if v > 0 else (str(v) if v else "="))
show.columns = ["#", "region", "mov", "SAM_MM", "clientes", "%<2h", "h_puerto",
                "pico", "%top4", "arquetipo", "score"]
print(show.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))

print()
print("--- MAYORES MOVIMIENTOS FRENTE A v2 ---")
mv = m.reindex(m["mov"].abs().sort_values(ascending=False).index).head(6)
for _, r in mv.iterrows():
    d = int(r["mov"])
    if d == 0:
        continue
    causa = ("accesibilidad" if r["pct_bajo_2h"] >= 85 or r["pct_bajo_2h"] <= 40
             else "estacionalidad")
    signo = "sube" if d > 0 else "baja"
    print(f"  {r['dep']:<14} {signo} {abs(d)} puesto(s) "
          f"(v2 #{int(r['rank_v2'])} -> v3 #{int(r['rank_v3'])})  "
          f"{r['pct_bajo_2h']:.0f}% a <2h, {r['pct_top4']:.0f}% en 4 meses  "
          f"[{causa}]")

print()
print("--- ARQUETIPOS DE TERRITORIO ---")
for a, g in m.groupby("arquetipo"):
    print(f"  {a:<26} {len(g):2d} regiones  "
          f"US$ {g.sam_usd.sum()/1e6:5,.0f} MM  ({', '.join(g.dep.head(4))})")
