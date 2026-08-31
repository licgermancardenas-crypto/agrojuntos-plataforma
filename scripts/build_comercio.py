# -*- coding: utf-8 -*-
"""Cross customs records with the taxpayer registry to locate the trade.

Customs gives who imports inputs and who exports produce, with RUC and value.
The SUNAT padrón gives each RUC a district. Joining them turns a list of names
into a map: where the largest input buyers actually are, and which of them sit
inside the eight priority regions.

Two commercial readings come out of it:

  importadores  the competitive set — who already brings fertiliser and crop
                protection into Peru, and how concentrated that is
  exportadores  the demand side at its most creditworthy — firms invoicing in
                dollars, on a certification calendar, buying the most inputs
                per hectare of anyone in the country
"""
import io
import re
import sys
import unicodedata

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
SEMANAS = 10


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


imp = pd.read_csv("out/aduanas_importadores.csv", encoding="utf-8-sig",
                  dtype={"ruc": str})
exp = pd.read_csv("out/aduanas_agroexportadores.csv", encoding="utf-8-sig",
                  dtype={"ruc": str})
pad = pd.read_csv("out/empresas_agro.csv", encoding="utf-8-sig",
                  dtype={"ruc": str, "ubigeo": str})

# The agro-named subset only locates a quarter of these firms — Camposol and
# Danper do not carry "agro" in their names — so the full padrón is swept once
# for exactly the RUCs that appear in customs.
def ubicar(rucs):
    import zipfile
    import geopandas as gpd
    faltan = set(rucs)
    filas = []
    zf = zipfile.ZipFile("data/sunat/ruc.zip")
    with zf.open(zf.namelist()[0]) as f:
        for linea in io.TextIOWrapper(f, encoding="latin-1", errors="replace"):
            r = linea.split("|", 6)
            if len(r) < 6 or r[0] not in faltan:
                continue
            filas.append({"ruc": r[0], "razon_padron": r[1].strip(),
                          "ubigeo": r[4].strip().zfill(6)})
            faltan.discard(r[0])
            if not faltan:
                break
    u = pd.DataFrame(filas)
    g = gpd.read_file("data/peru_distrital_simple.geojson")[
        ["IDDIST", "NOMBDIST", "NOMBPROV", "NOMBDEP"]]
    g.columns = ["ubigeo", "distrito", "provincia", "dep"]
    g["ubigeo"] = g["ubigeo"].astype(str).str.zfill(6)
    return u.merge(g, on="ubigeo", how="left")


ubic = ubicar(set(imp["ruc"]) | set(exp["ruc"]))
print(f"RUC ubicados en el padron: {len(ubic):,}", flush=True)
ubic = ubic[["ruc", "distrito", "provincia", "dep"]].drop_duplicates("ruc")

imp = imp.merge(ubic, on="ruc", how="left")
exp = exp.merge(ubic, on="ruc", how="left")

imp["fob_anual"] = imp["fob"] / SEMANAS * 52
exp["fob_anual"] = exp["fob"] / SEMANAS * 52

imp.to_csv("out/comercio_importadores.csv", index=False, encoding="utf-8-sig")
exp.to_csv("out/comercio_exportadores.csv", index=False, encoding="utf-8-sig")

print("=" * 78)
print("EL MERCADO DE INSUMOS VISTO DESDE ADUANAS")
print("=" * 78)
print(f"importadores de insumos : {len(imp):,} empresas")
print(f"  ubicados por padron   : {imp.dep.notna().sum():,}")
print(f"  FOB anualizado        : US$ {imp.fob_anual.sum()/1e6:,.0f} MM CIF")
print()
print(f"agroexportadores        : {len(exp):,} empresas")
print(f"  ubicados por padron   : {exp.dep.notna().sum():,}")
print(f"  FOB anualizado        : US$ {exp.fob_anual.sum()/1e6:,.0f} MM")

# ---- what this says about the addressable market -------------------------
mod = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
FOCO = set(mod.nsmallest(8, "rank_v3")["dep"].map(slug))

exp_ub = exp[exp.dep.notna()].copy()
exp_ub["en_foco"] = exp_ub["dep"].map(slug).isin(FOCO)
print()
print("--- AGROEXPORTADORES UBICADOS, POR REGION ---")
r = (exp_ub.groupby("dep")
     .agg(empresas=("ruc", "size"), fob=("fob_anual", "sum"))
     .sort_values("fob", ascending=False).head(10))
r["fob"] = (r["fob"] / 1e6).round(0)
r.columns = ["empresas", "FOB anual US$ MM"]
print(r.to_string(float_format=lambda v: f"{v:,.0f}"))
print()
print(f"en las 8 regiones foco: {exp_ub.en_foco.sum():,} de {len(exp_ub):,} "
      f"empresas ubicadas  ({100*exp_ub.en_foco.mean():.0f}%)")

# ---- concentration -------------------------------------------------------
print()
print("--- CONCENTRACION DEL LADO IMPORTADOR ---")
imp_s = imp.sort_values("fob", ascending=False)
tot = imp_s["fob"].sum()
for n in (5, 10, 20, 50):
    print(f"  top {n:>2}: {100*imp_s.head(n)['fob'].sum()/tot:5.1f}% del valor importado")

prot = imp[imp.rubro == "Proteccion de cultivos"].sort_values("fob", ascending=False)
print()
print("--- PROTECCION DE CULTIVOS: EL SET COMPETITIVO DIRECTO ---")
v = prot.head(14)[["razon_social", "fob_anual", "tn", "semanas", "dep"]].copy()
v["fob_anual"] = (v["fob_anual"] / 1e6).round(1)
v.columns = ["razon social", "FOB anual MM", "tn (10 sem)", "sem", "region"]
print(v.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
print()
print(f"El rubro mueve US$ {prot.fob_anual.sum()/1e6:,.0f} MM anuales CIF entre "
      f"{len(prot)} importadores.")
print("Son los proveedores de los que AgroJuntos compra y, a la vez, la")
print("competencia de su canal.")
