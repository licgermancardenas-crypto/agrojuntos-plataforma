# -*- coding: utf-8 -*-
"""Qué se cultiva en cada departamento, y qué departamento manda en cada cultivo.

El sitio decía cuánto vale cada región pero no qué se siembra en ella. Para
vender insumos eso es la mitad de la conversación: no se le ofrece lo mismo a
un valle de arroz que a uno de palta, y el calendario de compra sale del
cultivo, no del departamento.

La fuente es el anuario de producción agrícola del MIDAGRI, ya parseado por
build_estacionalidad.py en superficie por cultivo, departamento y mes. Aquí se
suman los meses y se cruza con el costo de insumos por hectárea, que es lo que
convierte hectáreas en mercado.

Uso:
    python scripts/build_cultivos.py
"""
import re
import unicodedata

import pandas as pd


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


# El anuario nombra las hojas con abreviaturas propias. Las que siguen su
# convencion —gs grano seco, gv grano verde, f forrajera, g grano— se traducen;
# las que no la siguen se quedan como vienen, con mayuscula inicial. Inventarle
# un nombre a un cultivo es peor que dejar el codigo a la vista.
NOMBRES = {
    "MAD": "Maíz amarillo duro", "Amilac": "Maíz amiláceo",
    "Mmorado": "Maíz morado", "choclo": "Maíz choclo", "chala": "Maíz chala",
    "avenaf": "Avena forrajera", "avenag": "Avena grano",
    "cebadaf": "Cebada forrajera", "cebada": "Cebada grano",
    "habags": "Haba grano seco", "habagv": "Haba grano verde",
    "arvejags": "Arveja grano seco", "arvejagv": "Arveja grano verde",
    "pallargs": "Pallar grano seco", "pallarverd": "Pallar verde",
    "frijolverd": "Frijol grano verde", "fpalo": "Frijol de palo",
    "loctao": "Frijol loctao", "zarandaja": "Frijol zarandaja",
    "braquearia": "Brachiaria (pasto)", "pelefante": "Pasto elefante",
    "gramalote": "Pasto gramalote", "grama_chilena": "Grama chilena",
    "gramaazul": "Grama azul", "ryegrass": "Ryegrass (pasto)",
    "alfalfa": "Alfalfa", "trebol": "Trébol",
    "cañaalcohol": "Caña de azúcar para alcohol",
    "cañaetanol": "Caña de azúcar para etanol",
    "tarhui": "Tarwi", "achiot": "Achiote", "limond": "Limón dulce",
    "piquillo": "Pimiento piquillo", "sachainchi": "Sacha inchi",
    "camucamu": "Camu camu", "cebollacabeza": "Cebolla de cabeza",
    "cebollachina": "Cebolla china", "pijuayo": "Pijuayo",
    "taperiba": "Taperibá", "cirolero": "Ciruelo",
    # Restitucion de tildes: el anuario escribe sin acentos.
    "cafe": "Café", "platano": "Plátano", "limon": "Limón",
    "esparrago": "Espárrago", "maracuya": "Maracuyá",
    "melocoton": "Melocotón", "algodon": "Algodón", "mani": "Maní",
    "paprika": "Páprika", "marañon": "Marañón", "piña": "Piña",
    "piña": "Piña", "oregano": "Orégano", "lucuma": "Lúcuma",
    "kiwicha": "Kiwicha", "cañihua": "Cañihua", "aji": "Ají",
    "brocoli": "Brócoli", "te": "Té", "té": "Té", "sandia": "Sandía",
    "guanabana": "Guanábana", "nispero": "Níspero", "pecana": "Pecana",
    "granadilla": "Granadilla", "arandano": "Arándano", "mashua": "Mashua",
    "poro": "Poro", "betarraga": "Betarraga", "caigua": "Caigua",
    "quinua": "Quinua", "olluco": "Olluco", "camote": "Camote",
    "yuca": "Yuca", "tuna": "Tuna", "oca": "Oca", "coco": "Coco",
    "higo": "Higo", "pera": "Pera", "col": "Col", "apio": "Apio",
    "nabo": "Nabo", "lima": "Lima", "soya": "Soya", "sorgo": "Sorgo",
}


def bonito(c):
    if c in NOMBRES:
        return NOMBRES[c]
    c = c.replace("_", " ").strip()
    return c[:1].upper() + c[1:]


det = pd.read_csv("out/estacionalidad_detalle.csv", encoding="utf-8-sig")
cos = pd.read_csv("out/costos_cultivo.csv", encoding="utf-8-sig")

# --------------------------------------------------------------- cultivos -
# Un cultivo por departamento, sumando los doce meses. `demanda_usd` ya trae
# el gasto en insumos que esa superficie implica.
cd = det.groupby(["k", "dep", "cultivo", "tipo"], as_index=False).agg(
    ha=("ha", "sum"), usd=("demanda_usd", "sum"))
cd = cd[cd["ha"] > 0]

# Mes de mayor siembra: es cuándo hay que tener el producto en el almacén.
pico = (det.sort_values("ha", ascending=False)
           .drop_duplicates(["k", "cultivo"])[["k", "cultivo", "mes"]]
           .rename(columns={"mes": "mes_pico"}))
cd = cd.merge(pico, on=["k", "cultivo"], how="left")

cd["cultivo"] = cd["cultivo"].map(bonito)

nac = cd.groupby("cultivo", as_index=False).agg(
    ha_nac=("ha", "sum"), usd_nac=("usd", "sum"), deps=("dep", "nunique"))
nac = nac.sort_values("ha_nac", ascending=False)
nac["rank_nac"] = range(1, len(nac) + 1)
# Concentración: qué parte del cultivo está en su departamento principal. Un
# cultivo concentrado se atiende desde un almacén; uno disperso, no.
lider = (cd.sort_values("ha", ascending=False)
           .drop_duplicates("cultivo")[["cultivo", "dep", "ha"]]
           .rename(columns={"dep": "dep_lider", "ha": "ha_lider"}))
nac = nac.merge(lider, on="cultivo", how="left")
nac["pct_lider"] = (100 * nac["ha_lider"] / nac["ha_nac"]).round(1)
nac["usd_ha"] = (nac["usd_nac"] / nac["ha_nac"]).round(0)

cd = cd.merge(nac[["cultivo", "rank_nac"]], on="cultivo", how="left")
tot_dep = cd.groupby("k")["ha"].sum().rename("ha_dep")
cd = cd.join(tot_dep, on="k")
cd["pct_dep"] = (100 * cd["ha"] / cd["ha_dep"]).round(2)
cd = cd.sort_values(["k", "ha"], ascending=[True, False])
cd["rank_dep"] = cd.groupby("k").cumcount() + 1

cd[["k", "dep", "cultivo", "tipo", "ha", "usd", "pct_dep", "rank_dep",
    "rank_nac", "mes_pico"]].to_csv(
    "out/cultivos_departamento.csv", index=False, encoding="utf-8-sig")

nac[["cultivo", "ha_nac", "usd_nac", "usd_ha", "deps", "dep_lider",
     "pct_lider", "rank_nac"]].to_csv(
    "out/cultivos_nacional.csv", index=False, encoding="utf-8-sig")

print(f"cultivos_nacional.csv     {len(nac):>5,} cultivos")
print(f"cultivos_departamento.csv {len(cd):>5,} pares cultivo-departamento")
print(f"  superficie total        {nac['ha_nac'].sum():>12,.0f} ha")
print(f"  mercado implicado       US$ {nac['usd_nac'].sum()/1e6:>9,.1f} MM")
print()
crudos = sorted({c for c in det["cultivo"].unique()
                 if c not in NOMBRES and not c[:1].isupper()})
print(f"  nombres sin traducir    {len(crudos)} "
      f"(se muestran con mayuscula inicial)")
print()
print("Los diez cultivos de mayor superficie:")
for _, r in nac.head(10).iterrows():
    print(f"  {r['rank_nac']:>2}. {r['cultivo'][:26]:26s} "
          f"{r['ha_nac']:>10,.0f} ha · US$ {r['usd_nac']/1e6:>6,.1f} MM · "
          f"{r['dep_lider'][:14]:14s} {r['pct_lider']:>5.1f}%")
