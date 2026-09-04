# -*- coding: utf-8 -*-
"""Pone a cada empresa dentro de un territorio de venta y de un centro.

El mapeo llega hasta el territorio: 57 núcleos de venta y el orden en que
conviene abrir centros. El padrón llega hasta el nombre propio: 21,063 empresas
agrícolas con RUC. Entre los dos no había puente, de modo que el territorio era
una mancha sin cartera y la empresa un nombre sin ruta.

Aquí se cruzan. La empresa se ubica igual que en build_h3.py —en el punto medio
de los sectores agrícolas de su distrito, con la clave departamento + provincia
+ distrito— y de ahí sale la celda H3, que es la unidad con la que ya están
escritos los territorios y la asignación a centros. Compartir el método importa:
si cada capa ubicara a su manera, el sitio mostraría dos conteos distintos de
empresas para el mismo territorio.

  distrito -> punto agrícola del distrito -> celda H3 -> territorio + centro

La advertencia de siempre, y aquí pesa más que en ninguna otra capa: **el
domicilio fiscal no es donde se cultiva**. Un agroexportador con fundo en La
Libertad suele estar inscrito en San Isidro. Esta capa sirve para saber a quién
visitar cuando el vendedor está en el territorio, no para ubicar la producción.

Uso:
    python scripts/build_cartera.py
"""
import re
import unicodedata

import h3
import numpy as np
import pandas as pd

R_HUB = 5      # resolución con la que se escribió la asignación a centros
R_CLU = 6      # resolución con la que se detectaron los territorios

FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "limametropolitana": "lima",
       "provconstdelcallao": "callao"}


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def dep_key(s):
    return FIX.get(slug(s), slug(s))


def clave(df, dep, prov, dist):
    return df[dep].map(dep_key) + "|" + df[prov].map(slug) + "|" + df[dist].map(slug)


def cap(s):
    s = " ".join(w.capitalize() for w in str(s).split())
    for a, b in (("De ", "de "), ("Del ", "del "), ("La ", "la "), ("Y ", "y ")):
        s = s.replace(" " + a, " " + b)
    return s


def sinac(s):
    return unicodedata.normalize("NFKD", str(s)).encode(
        "ascii", "ignore").decode().upper()


# ------------------------------------------------------- punto por distrito -
sec = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")
sec = sec[np.isfinite(sec["horas_capital_real"])]
dist_xy = (sec.groupby(clave(sec, "dep", "prov", "dist"))
           .agg(lat=("lat", "mean"), lon=("lon", "mean")))
print(f"distritos con sector agrícola: {len(dist_xy):,}")

emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                  dtype={"ruc": str, "ubigeo": str})
emp = emp[emp["distrito"].notna()].copy()
j = dist_xy.reindex(clave(emp, "dep", "provincia", "distrito"))
emp["lat"], emp["lon"] = j["lat"].values, j["lon"].values
sin_geo = emp["lat"].isna().sum()
print(f"empresas del padrón: {len(emp):,}  ·  sin distrito ubicable: {sin_geo:,}"
      f" ({100*sin_geo/len(emp):.1f}%)")
emp = emp[emp["lat"].notna()].copy()

emp["h3_hub"] = [h3.latlng_to_cell(a, b, R_HUB)
                 for a, b in zip(emp["lat"], emp["lon"])]
emp["h3_clu"] = [h3.latlng_to_cell(a, b, R_CLU)
                 for a, b in zip(emp["lat"], emp["lon"])]

# ------------------------------------------------------------ centro y zona -
hub = pd.read_csv("out/hubs_asignacion.csv", encoding="utf-8-sig",
                  usecols=["h3", "hub", "horas_al_hub", "cubierto_2h"])
# Las celdas sin vía mapeada cerca quedan a distancia infinita del grafo. Es
# «no se sabe», no «muy lejos»: promediado con el resto, un solo infinito se
# come la media de todo un centro.
hub["horas_al_hub"] = hub["horas_al_hub"].replace([np.inf, -np.inf], np.nan)
emp = emp.merge(hub.rename(columns={"h3": "h3_hub"}), on="h3_hub", how="left")

clu = pd.read_csv("out/clusters_celda.csv", encoding="utf-8-sig",
                  usecols=["h3", "cluster"])
emp = emp.merge(clu.rename(columns={"h3": "h3_clu"}), on="h3_clu", how="left")
# -1 es ruido del DBSCAN y NaN es una celda sin mercado: las dos cosas
# significan «fuera de territorio», y conviene que se lean igual.
emp["cluster"] = emp["cluster"].fillna(-1).astype(int)

ter = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
# Las capas geoespaciales guardan el departamento en mayúsculas y sin tildes;
# el modelo regional lo tiene escrito como corresponde.
v3 = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
DEP_OK = {sinac(d): d for d in v3["dep"]}
ter["dep_ok"] = ter["dep"].map(lambda d: DEP_OK.get(sinac(d), cap(d)))
ter["territorio"] = [f"{r.dep_ok} · {cap(r.provincias)}"
                     for r in ter.itertuples()]
emp = emp.merge(ter[["cluster", "territorio", "rank"]], on="cluster", how="left")
emp["territorio"] = emp["territorio"].fillna("Fuera de territorio")

dentro = (emp["cluster"] >= 0).sum()
print(f"dentro de alguno de los {len(ter)} territorios: {dentro:,}"
      f" ({100*dentro/len(emp):.1f}%)")
print(f"a menos de dos horas de un centro: {emp['cubierto_2h'].sum():,.0f}"
      f" ({100*emp['cubierto_2h'].mean():.1f}%)")

COLS = ["ruc", "razon_social", "clase", "dep", "provincia", "distrito",
        "ubigeo", "lat", "lon", "exporta", "importa", "cluster", "rank",
        "territorio", "hub", "horas_al_hub", "cubierto_2h"]
emp[COLS].to_csv("out/cartera_empresa.csv", index=False, encoding="utf-8-sig")


def resumen(g):
    return pd.Series({
        "empresas": len(g),
        "agroindustria": int((g["clase"] == "agroindustria").sum()),
        "productor": int((g["clase"] == "productor").sum()),
        "exportadores": int(g["exporta"].sum()),
        "importadores": int(g["importa"].sum()),
        "dentro_2h": int(g["cubierto_2h"].fillna(False).sum()),
        "horas_al_hub": g["horas_al_hub"].median(),
    })


# ------------------------------------------------------- cartera por zona ---
car = (emp[emp["cluster"] >= 0].groupby("cluster").apply(resumen)
       .reset_index())
# El centro que sirve al territorio es el que sirve a la mayoría de su
# cartera: un territorio puede quedar repartido entre dos, y decir «Chiclayo»
# cuando el 60% va a Chiclayo describe la ruta mejor que no decir nada.
modal = (emp[emp["cluster"] >= 0].dropna(subset=["hub"])
         .groupby("cluster")["hub"].agg(lambda x: x.mode().iat[0])
         .rename("hub").reset_index())
car = car.merge(modal, on="cluster", how="left")
car = car.merge(ter[["cluster", "rank", "territorio", "dep_ok", "sam_usd",
                     "clientes", "extension_km", "visitable_en_dia"]]
                .rename(columns={"dep_ok": "dep"}), on="cluster")
car["empresas_por_mm"] = car["empresas"] / (car["sam_usd"] / 1e6)
car = car.sort_values("rank")
car.to_csv("out/cartera_territorio.csv", index=False, encoding="utf-8-sig")

# La asignación a centro es al más cercano de los seis, sin tope de distancia:
# toda Lima cae bajo Pisco aunque esté a media jornada. Por eso va también
# `dentro_2h`, que es la parte de la cartera que ese centro sirve de verdad.
carh = emp[emp["hub"].notna()].groupby("hub").apply(resumen).reset_index()
carh = carh.sort_values("empresas", ascending=False)
carh.to_csv("out/cartera_hub.csv", index=False, encoding="utf-8-sig")

print(f"\ncartera_empresa.csv     {len(emp):,} empresas ubicadas")
print(f"cartera_territorio.csv  {len(car):,} territorios con cartera")
print(f"cartera_hub.csv         {len(carh):,} centros")
print("\nlos ocho territorios con más empresas:")
top = car.nlargest(8, "empresas")
for r in top.itertuples():
    print(f"  {r.rank:>2}. {r.territorio[:38]:<38} {r.empresas:>5,} empresas"
          f"  ·  US$ {r.sam_usd/1e6:>5,.1f} MM SAM")
