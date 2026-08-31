# -*- coding: utf-8 -*-
"""Agrega todas las capas a una grilla hexagonal H3.

Los sectores estadísticos tienen tamaños muy dispares —de 200 a 30,000 ha— así
que comparar dos zonas del país mirando sectores mezcla densidad con tamaño de
la unidad de medida. La grilla H3 resuelve eso: celdas de área constante,
comparables entre sí, y con vecindad definida, que es lo que necesitan tanto el
dashboard como los algoritmos de agrupamiento.

Dos resoluciones, porque responden preguntas distintas:

    r5   ~253 km² por celda   vista nacional, decisiones de territorio
    r6   ~ 36 km² por celda   vista regional, planificación de rutas

Cada celda acumula el mercado de los sectores que caen en ella, más los
prospectos, empresas y agroexportadores que le corresponden.
"""
import re
import unicodedata

import h3
import numpy as np
import pandas as pd

RES = [5, 6]


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def celda(lat, lon, r):
    return h3.latlng_to_cell(float(lat), float(lon), r)


# ---------------------------------------------------------------- datos ----
sec = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")
sec = sec[np.isfinite(sec["horas_capital_real"])].copy()

try:
    pros = pd.read_csv("out/osm_prospectos.csv", encoding="utf-8-sig")
except FileNotFoundError:
    pros = pd.DataFrame(columns=["lat", "lon", "nombre"])

emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                  dtype={"ruc": str, "ubigeo": str})
expo = pd.read_csv("out/comercio_exportadores.csv", encoding="utf-8-sig",
                   dtype={"ruc": str})

# Las empresas traen distrito, no coordenada: se les asigna el centroide del
# sector agrícola más cercano dentro de su propio distrito, y si el distrito no
# tiene sector agrícola, el centroide del distrito.
dist_xy = (sec.groupby(sec["dist"].map(slug))
           .agg(lat=("lat", "mean"), lon=("lon", "mean")))


def ubicar(df, col_dist="distrito"):
    k = df[col_dist].map(slug)
    j = dist_xy.reindex(k)
    out = df.copy()
    out["lat"] = j["lat"].values
    out["lon"] = j["lon"].values
    return out.dropna(subset=["lat", "lon"])


emp_xy = ubicar(emp[emp["distrito"].notna()])
expo_xy = ubicar(expo[expo["distrito"].notna()])

print(f"sectores          : {len(sec):,}")
print(f"prospectos OSM    : {len(pros):,}")
print(f"empresas ubicadas : {len(emp_xy):,} de {len(emp):,}")
print(f"exportadores ubic.: {len(expo_xy):,} de {len(expo):,}")

# ------------------------------------------------------------ agregacion ---
salidas = {}
for r in RES:
    sec[f"h3_{r}"] = [celda(a, b, r) for a, b in zip(sec.lat, sec.lon)]

    g = (sec.groupby(f"h3_{r}")
         .agg(sectores=("cod_se", "size"),
              ha_agricola=("ha_agricola", "sum"),
              ha_cosechada=("s_ha_cosechada", "sum"),
              clientes=("s_clientes_sam", "sum"),
              sam_usd=("s_sam_usd", "sum"),
              horas_capital=("horas_capital_real", "mean"),
              horas_puerto=("horas_puerto_real",
                            lambda s: np.nanmean(s[np.isfinite(s)])
                            if np.isfinite(s).any() else np.nan),
              costo_viaje=("costo_viaje_real", "mean"),
              region_nat=("region_nat", lambda s: s.mode().iat[0]),
              dep=("dep", lambda s: s.mode().iat[0]),
              prov=("prov", lambda s: s.mode().iat[0]))
         .reset_index().rename(columns={f"h3_{r}": "h3"}))

    for nombre, df in (("prospectos", pros), ("empresas", emp_xy),
                       ("exportadores", expo_xy)):
        if not len(df):
            g[nombre] = 0
            continue
        c = pd.Series([celda(a, b, r) for a, b in zip(df.lat, df.lon)])
        g[nombre] = g["h3"].map(c.value_counts()).fillna(0).astype(int)

    # FOB exportado por celda: el peso comercial real de cada zona
    if len(expo_xy):
        expo_xy[f"h3_{r}"] = [celda(a, b, r)
                              for a, b in zip(expo_xy.lat, expo_xy.lon)]
        fob = expo_xy.groupby(f"h3_{r}")["fob_anual"].sum()
        g["fob_export"] = g["h3"].map(fob).fillna(0)
    else:
        g["fob_export"] = 0.0

    # geometría y centro de cada celda
    g["centro_lat"] = [h3.cell_to_latlng(c)[0] for c in g["h3"]]
    g["centro_lon"] = [h3.cell_to_latlng(c)[1] for c in g["h3"]]
    g["km2"] = [h3.cell_area(c, unit="km^2") for c in g["h3"]]
    g["sam_por_km2"] = g["sam_usd"] / g["km2"]
    g["res"] = r

    g = g.sort_values("sam_usd", ascending=False)
    g.to_csv(f"out/h3_r{r}.csv", index=False, encoding="utf-8-sig")
    salidas[r] = g

    cubierto = 100 * g["sam_usd"].sum() / sec["s_sam_usd"].sum()
    print(f"\nr{r}: {len(g):,} celdas de ~{g.km2.mean():,.0f} km2  "
          f"({cubierto:.0f}% del SAM)")
    top = g.head(6)[["h3", "dep", "prov", "sam_usd", "clientes", "sam_por_km2"]]
    print(top.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))

# ---- concentración: cuántas celdas explican la mitad del mercado ----------
print()
for r, g in salidas.items():
    ac = g["sam_usd"].cumsum() / g["sam_usd"].sum()
    n50 = int((ac <= 0.5).sum()) + 1
    n80 = int((ac <= 0.8).sum()) + 1
    print(f"r{r}: {n50} celdas concentran el 50% del SAM; {n80} el 80% "
          f"(de {len(g):,})")
