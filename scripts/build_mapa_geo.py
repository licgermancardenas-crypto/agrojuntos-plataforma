# -*- coding: utf-8 -*-
"""Empaqueta las capas geoespaciales para el mapa web interactivo.

El artefacto publicado no puede pedir teselas a un servidor externo, así que el
Perú se dibuja desde geometría incluida en la propia página. Eso vuelve el peso
del archivo la restricción que manda: la geometría va simplificada, las
coordenadas redondeadas a cuatro decimales —unos 11 metros— y cada celda o
punto viaja como una tupla de posición fija en vez de un objeto con claves
repetidas.
"""
import json
import os
import re
import unicodedata

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

DEC = 4


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


FIX = {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
       "junn": "junin", "sanmartn": "sanmartin", "provconstdelcallao": "callao"}


def key(s):
    return FIX.get(slug(s), slug(s))


def cap(s):
    return " ".join(w.capitalize() for w in str(s).split())


h5 = pd.read_csv("out/h3_r5.csv", encoding="utf-8-sig")
h5 = h5[h5["sam_usd"] > 0].copy()
terr = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
celda = pd.read_csv("out/clusters_celda.csv", encoding="utf-8-sig")
hubs = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")
asig = pd.read_csv("out/hubs_asignacion.csv", encoding="utf-8-sig")
puertos = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
mod = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
sec_ruteo = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")

# ------------------------------------------------------- contorno del pais -
dep_g = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_g["geometry"] = dep_g.geometry.buffer(0).simplify(0.02,
                                                      preserve_topology=True)


def anillos(geom):
    partes = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    out = []
    for p in partes:
        r = [[round(x, DEC), round(y, DEC)] for x, y in p.exterior.coords]
        if len(r) > 3:
            out.append(r)
    return out


# El contorno va por departamento y no aplanado: filtrar, resaltar y encuadrar
# la vista exigen saber a quién pertenece cada anillo.
deps_geo = []
for _, r in dep_g.sort_values("NOMBDEP").iterrows():
    a = anillos(r.geometry)
    if not a:
        continue
    xs = [p[0] for anillo in a for p in anillo]
    ys = [p[1] for anillo in a for p in anillo]
    deps_geo.append({
        "n": cap(r["NOMBDEP"]), "k": key(r["NOMBDEP"]), "r": a,
        "bb": [round(min(xs), DEC), round(min(ys), DEC),
               round(max(xs), DEC), round(max(ys), DEC)],
    })
contorno = [a for d in deps_geo for a in d["r"]]

# ------------------------------------------------------------ hexagonos ---
# El hexágono se dibuja desde su índice H3; enviar los seis vértices de cada
# celda pesaría cuatro veces más que enviar el centro y el radio.
h5 = h5.sort_values("sam_usd", ascending=False)
i_dep = {d["k"]: i for i, d in enumerate(deps_geo)}
REG = ["COSTA", "SIERRA", "SELVA ALTA", "SELVA BAJA"]
i_reg = {r: i for i, r in enumerate(REG)}
hex_cells = []
for _, r in h5.iterrows():
    vs = h3.cell_to_boundary(r["h3"])
    hex_cells.append([
        [[round(lon, DEC), round(lat, DEC)] for lat, lon in vs],
        int(round(r["sam_usd"] / 1000)),        # SAM en miles de US$
        int(round(r["clientes"])),
        int(round(r["ha_cosechada"])),
        round(float(r["horas_capital"]), 1),
        int(r["empresas"]), int(r["exportadores"]), int(r["prospectos"]),
        cap(r["dep"]), cap(r["prov"]),
        i_dep.get(key(r["dep"]), -1),
        i_reg.get(str(r.get("region_nat", "")).upper(), 1),
    ])

# ------------------------------------------------------------ territorios -
celda_cl = celda[celda["cluster"] >= 0]
mapa_rank = dict(zip(terr["cluster"], terr["rank"]))
terr_pts = {}
for _, r in celda_cl.iterrows():
    rk = mapa_rank.get(r["cluster"])
    if rk is None:
        continue
    terr_pts.setdefault(int(rk), []).append(
        [round(r["centro_lon"], DEC), round(r["centro_lat"], DEC)])

territorios = []
for _, r in terr.iterrows():
    territorios.append({
        "rank": int(r["rank"]),
        "dep": cap(r["dep"]), "prov": r["provincias"],
        "sam": int(r["sam_usd"]), "cli": int(r["clientes"]),
        "celdas": int(r["celdas"]), "ext": round(float(r["extension_km"])),
        "dia": bool(r["visitable_en_dia"]),
        "lat": round(float(r["lat"]), DEC), "lon": round(float(r["lon"]), DEC),
        "pts": terr_pts.get(int(r["rank"]), []),
    })

# ------------------------------------------------------------------ hubs ---
hubs_out = {}
for u in sorted(hubs["umbral_h"].unique()):
    sub = hubs[hubs["umbral_h"] == u].sort_values("k")
    hubs_out[str(int(u))] = [{
        "k": int(x["k"]), "hub": x["hub"], "region": x["region"],
        "lat": round(float(x["lat"]), DEC), "lon": round(float(x["lon"]), DEC),
        "pct": round(float(x["pct_sam"]), 1),
        "marg": round(float(x["marginal"]), 1),
    } for _, x in sub.iterrows()]

# Celdas cubiertas / no cubiertas en el escenario de 6 centros a 2 h.
# Una celda sin camino a ningún centro sale con distancia infinita, e
# `Infinity` no es JSON válido: JSON.parse lo rechaza y la página queda en
# blanco. Se traduce a null, que el mapa dibuja como "sin conexión".
def horas(v):
    v = float(v)
    return round(v, 1) if np.isfinite(v) else None


cob = [[round(r["centro_lon"], DEC), round(r["centro_lat"], DEC),
        1 if r["cubierto_2h"] else 0, horas(r["horas_al_hub"])]
       for _, r in asig.iterrows()]

# --------------------------------------------------------------- puertos ---
pu = [{"n": r["puerto"], "lat": round(float(r["lat"]), DEC),
       "lon": round(float(r["lon"]), DEC), "tipo": r["tipo"],
       "rel": r["relevancia_agro"]} for _, r in puertos.iterrows()]

# -------------------------------------------------------------- ciudades ---
cap_g = gpd.read_file("data/peru_capital_provincia.geojson").to_crs(4326)
sam_prov = sec_ruteo.groupby(sec_ruteo["prov"].map(slug))["s_sam_usd"].sum()
cap_g["sam"] = cap_g["PROVINCIA"].map(slug).map(sam_prov).fillna(0)
cap_g = cap_g.sort_values("sam", ascending=False)
ciudades = [{
    "n": cap(r["CAPITAL"]), "d": cap(r["DEPARTAM"]),
    "lat": round(float(r.geometry.y), DEC),
    "lon": round(float(r.geometry.x), DEC),
    "sam": int(r["sam"]),
    "k": i_dep.get(key(r["DEPARTAM"]), -1),
} for _, r in cap_g.iterrows()]

# ------------------------------------------------------------ carreteras ---
try:
    vial = json.load(open("out/vial_mapa.json", encoding="utf-8"))
except FileNotFoundError:
    vial = {"niveles": {}, "refs": []}

# ------------------------------------------------------------------ salida -

# ===================================================================== #
#  Representaciones alternativas del mapa.                               #
#                                                                        #
#  La grilla hexagonal compara áreas iguales, que es su virtud, pero un   #
#  hexágono no es un lugar: nadie lo reconoce ni puede señalarlo. Estas    #
#  dos capas dan las dos cosas que la grilla no da —la ubicación real de   #
#  la producción y una forma que el usuario reconoce— y habilitan además   #
#  el mapa de calor, que se calcula en el navegador a partir de los        #
#  puntos y no cuesta un solo byte de payload.                            #
# ===================================================================== #

# ------------------------------------------------------- puntos por sector -
# El sector estadístico del MIDAGRI es la unidad real: tiene centroide,
# hectáreas y mercado propios. Coordenadas a tres decimales (~110 m) porque
# un punto de tres píxeles no distingue más, y eso baja el peso a la mitad.
sec_pt = sec_ruteo.copy()
sec_pt = sec_pt[sec_pt["s_sam_usd"] > 0]

i_dep_sec = {d["k"]: i for i, d in enumerate(deps_geo)}
i_reg_sec = {r: i for i, r in enumerate(REG)}


def finito(v, dec=1):
    """El ruteo deja `inf` en los sectores sin camino; JSON no lo admite."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, dec) if np.isfinite(v) else None


# La provincia viaja como indice a un catalogo: el buscador tiene que filtrar
# igual en puntos que en hexagonos, y repetir la cadena 6,873 veces pesa mas
# que el catalogo entero.
cat_prov = sorted({cap(v) for v in sec_pt["prov"].dropna().unique()})
i_prov_sec = {v: i for i, v in enumerate(cat_prov)}

sectores_pt = []
for _, r in sec_pt.sort_values("s_sam_usd", ascending=False).iterrows():
    sectores_pt.append([
        round(float(r["lon"]), 3), round(float(r["lat"]), 3),
        int(round(float(r["s_sam_usd"]) / 1000)),      # SAM en miles de US$
        int(round(float(r["s_clientes_sam"]))),
        finito(r["horas_capital_real"]),
        i_dep_sec.get(key(r["dep"]), -1),
        i_reg_sec.get(str(r["region_nat"]).upper(), -1),
        i_prov_sec.get(cap(r["prov"]), -1),
    ])

# --------------------------------------------------------- coropleta real -
# Provincias y no distritos: 196 formas se reconocen a escala nacional y
# 1,874 se leen como ruido, además de pesar tres veces más.
prov_g = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
prov_g["geometry"] = prov_g.geometry.buffer(0).simplify(
    0.01, preserve_topology=True)

sec_pv = sec_ruteo.assign(
    kd=sec_ruteo["dep"].map(key), kp=sec_ruteo["prov"].map(key))
agg_pv = sec_pv.groupby(["kd", "kp"]).agg(
    sam=("s_sam_usd", "sum"), cli=("s_clientes_sam", "sum"),
    ha=("s_ha_cosechada", "sum"), n=("cod_se", "size")).reset_index()
agg_pv = agg_pv.set_index(["kd", "kp"])

provs_geo = []
for _, r in prov_g.iterrows():
    kd, kp = key(r["FIRST_NOMB"]), key(r["NOMBPROV"])
    a = agg_pv.loc[(kd, kp)] if (kd, kp) in agg_pv.index else None
    anl = anillos(r.geometry)
    if not anl:
        continue
    xs = [p[0] for ring in anl for p in ring]
    ys = [p[1] for ring in anl for p in ring]
    provs_geo.append({
        "n": cap(r["NOMBPROV"]), "d": cap(r["FIRST_NOMB"]),
        "i": i_dep_sec.get(kd, -1),
        "sam": int(a["sam"]) if a is not None else 0,
        "cli": int(round(a["cli"])) if a is not None else 0,
        "ha": int(a["ha"]) if a is not None else 0,
        "r": anl,
        "bb": [min(xs), min(ys), max(xs), max(ys)],
    })

sin_dato = sum(1 for p in provs_geo if p["sam"] == 0)


payload = {
    "meta": {
        "celdas": len(hex_cells),
        "km2_celda": int(round(h5["km2"].mean())),
        "sam": int(h5["sam_usd"].sum()),
        "clientes": int(h5["clientes"].sum()),
        "territorios": len(territorios),
        "territorios_dia": int(terr["visitable_en_dia"].sum()),
        "pct_sam_territorios": round(float(terr["pct_sam"].sum())),
    },
    "deps": deps_geo,
    "regiones": REG,
    "ciudades": ciudades,
    "vial": vial,
    "hex": hex_cells,
    "sect": sectores_pt,
    "sect_prov": cat_prov,
    "provs": provs_geo,
    "territorios": territorios,
    "hubs": hubs_out,
    "cobertura": cob,
    "puertos": pu,
}

# allow_nan=False obliga a que cualquier infinito o NaN que se escape falle
# aquí y no en el navegador del usuario.
with open("out/mapa_geo.json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False,
              allow_nan=False)

print(f"mapa_geo.json : {os.path.getsize('out/mapa_geo.json')/1e6:.2f} MB")
print(f"  hexagonos   : {len(hex_cells):,} de ~{payload['meta']['km2_celda']} km2")
print(f"  territorios : {len(territorios)}")
print(f"  hubs        : {sum(len(v) for v in hubs_out.values())} escenarios")
print(f"  puertos     : {len(pu)}")
print(f"  celdas cob. : {len(cob):,}")
print(f"  departamentos: {len(deps_geo)}")
print(f"  ciudades    : {len(ciudades)}")
print(f"  trazos viales: "
      f"{sum(len(v) for v in vial['niveles'].values()):,}")
print(f"  sectores punto: {len(sectores_pt):,}")
print(f"  provincias    : {len(provs_geo)} "
      f"({sin_dato} sin mercado registrado)")
