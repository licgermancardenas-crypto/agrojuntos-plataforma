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

# La pertenencia a territorio se resuelve una sola vez, sobre la celda r6 que
# es donde se detectaron los nucleos, y la heredan las tres capas del mapa:
# sectores, hexagonos y provincias. Si cada una la dedujera por su cuenta
# darian tres respuestas distintas para la misma pregunta.
celda_cl = celda[celda["cluster"] >= 0]
mapa_rank = dict(zip(terr["cluster"], terr["rank"]))
R6_RANK = {r["h3"]: int(mapa_rank[r["cluster"]])
           for _, r in celda_cl.iterrows() if r["cluster"] in mapa_rank}


def rank_de(lat, lon):
    return R6_RANK.get(h3.latlng_to_cell(float(lat), float(lon), 6), -1)


def rank_modal(ranks):
    """El territorio de una forma es el de la mayoria de sus celdas."""
    v = [r for r in ranks if r >= 0]
    return max(set(v), key=v.count) if v else -1

hubs = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")
asig = pd.read_csv("out/hubs_asignacion.csv", encoding="utf-8-sig")
puertos = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
mod = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
sec_ruteo = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")

# ------------------------------------------------------- contorno del pais -
# El contorno sale del servicio WFS del propio IGN y no del geojson publicado
# «simple», que ya venia generalizado por su editor: 307,384 vertices contra
# 3,374, noventa y una veces mas. Simplificado a 222 m quedan 23 mil, que son
# 130 KB comprimidos: siete veces el detalle de antes por 112 KB. Es la
# diferencia entre una costa dibujada y una costa recta.
#
# El cruce va por IDDPTO y no por nombre, que es la unica manera de que no se
# repita el problema de los distritos homonimos.
TOL_ADM = 0.002
dep_g = gpd.read_file("data/ign/departamentos.geojson").to_crs(4326)
dep_g = dep_g.rename(columns={"DEPARTAMEN": "NOMBDEP"})
dep_g["geometry"] = dep_g.geometry.buffer(0).simplify(
    TOL_ADM, preserve_topology=True)


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
        rank_modal([R6_RANK.get(c, -1)
                    for c in h3.cell_to_children(r["h3"], 6)]),
    ])

# ------------------------------------------------------------ territorios -
# Cada capa del mapa tiene que saber a que territorio pertenece, porque el
# usuario elige un territorio y espera que se filtre lo que este mirando, sea
# sectores, hexagonos o provincias. La pertenencia se resuelve una vez, sobre
# la celda r6 que es donde se detectaron los nucleos, y las tres capas la
# heredan: si cada una la dedujera por su cuenta darian tres respuestas.
terr_pts = {}
for _, r in celda_cl.iterrows():
    rk = mapa_rank.get(r["cluster"])
    if rk is None:
        continue
    terr_pts.setdefault(int(rk), []).append(
        [round(r["centro_lon"], DEC), round(r["centro_lat"], DEC)])

def bb_de(pts, lon, lat):
    """Encuadre del territorio. Con una sola celda no hay caja: se abre un
    grado alrededor del centro para que el zoom no salte al infinito."""
    if not pts:
        return [lon - .5, lat - .5, lon + .5, lat + .5]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = .12
    return [round(min(xs) - m, DEC), round(min(ys) - m, DEC),
            round(max(xs) + m, DEC), round(max(ys) + m, DEC)]


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
        "bb": bb_de(terr_pts.get(int(r["rank"]), []),
                    float(r["lon"]), float(r["lat"])),
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
        rank_de(r["lat"], r["lon"]),
    ])

# --------------------------------------------------------- coropleta real -
# Provincias y no distritos: 196 formas se reconocen a escala nacional y
# 1,874 se leen como ruido, además de pesar tres veces más.
prov_g = gpd.read_file("data/peru_provincial_simple.geojson").to_crs(4326)
# La geometria viene de geoBoundaries, cuya fuente declarada es el IGN:
# 689,927 vertices contra los 19,010 del archivo publicado. No trae el
# departamento, asi que el par (departamento, provincia) se recupera por cruce
# ESPACIAL contra el archivo viejo —el punto representativo de cada forma
# nueva dentro de la forma vieja— y no por nombre. Cruzar por nombre es lo que
# ya rompio la ubicacion de las empresas una vez.
#
# El cruce ubica las 196 formas y cubre 195 de nuestras 197 provincias. Las dos
# que sobran son erratas del archivo viejo —«PUIRA» y «VICTOR FAFARDO»—, y esa
# es una razon mas para cambiarlo.
prov_vieja = prov_g
gb = gpd.read_file("data/ign/provincias_gb.geojson").to_crs(4326)
gb["geometry"] = gb.geometry.buffer(0)
_pt = gb.copy()
_pt["geometry"] = gb.geometry.representative_point()
_j = gpd.sjoin(_pt, prov_vieja[["FIRST_NOMB", "NOMBPROV", "geometry"]],
               how="left", predicate="within")
gb["FIRST_NOMB"] = _j["FIRST_NOMB"].values
gb["NOMBPROV"] = _j["NOMBPROV"].values
_sin = gb["NOMBPROV"].isna().sum()
if _sin:
    print(f"  aviso: {_sin} provincias nuevas sin ubicar, se descartan")
prov_g = gb[gb["NOMBPROV"].notna()].copy()
prov_g["geometry"] = prov_g.geometry.simplify(TOL_ADM, preserve_topology=True)

sec_pv = sec_ruteo.assign(
    kd=sec_ruteo["dep"].map(key), kp=sec_ruteo["prov"].map(key))
agg_pv = sec_pv.groupby(["kd", "kp"]).agg(
    sam=("s_sam_usd", "sum"), cli=("s_clientes_sam", "sum"),
    ha=("s_ha_cosechada", "sum"), n=("cod_se", "size")).reset_index()
agg_pv = agg_pv.set_index(["kd", "kp"])

# El territorio de una provincia es el de la mayoria de sus sectores: una
# provincia puede quedar repartida entre dos nucleos de venta.
ter_pv = {}
for (kd, kp), g in sec_pv.groupby(["kd", "kp"]):
    ter_pv[(kd, kp)] = rank_modal([rank_de(la, lo)
                                   for la, lo in zip(g["lat"], g["lon"])])

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
        "t": ter_pv.get((kd, kp), -1),
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

# Los puntos y las provincias viajan aparte: son el 28% del peso y solo hacen
# falta si el usuario elige esa representacion. Quien entra a ver el mapa
# nacional no deberia descargarlas nunca.
# ------------------------------------------------- sectores como poligono -
# La unidad del analisis son los 7,043 sectores estadisticos del MIDAGRI, y
# hasta ahora el mapa los dibujaba como circulos sobre su centroide. Un
# circulo dice «hay algo por aca»; el poligono dice donde empieza y donde
# termina, que es lo que se le pide a un mapa.
#
# El peso no esta en cuantos vertices hay —simplificar apenas los reduce,
# porque las formas ya vienen minimas— sino en como se escriben. Cuantizados a
# 1e-4 grados (11 m) y guardados como diferencias respecto del vertice
# anterior, los numeros pasan de «-80.1234» a «-3», y el archivo de 2.6 MB
# queda en 1.2, que son 0.46 comprimidos: lo mismo que hoy pesan los circulos.
Q = 10000

sec_poly = gpd.read_file("out/sectores.geojson").to_crs(4326)
sec_poly["geometry"] = sec_poly.geometry.buffer(0).simplify(
    0.001, preserve_topology=True)
sec_poly["k"] = sec_poly["dep"].map(key)
# El geojson guarda cod_se como texto de ocho digitos con cero a la izquierda
# y el modelo lo leyo como entero, que se lo come: «05040402» contra «5040402».
# Sin rellenar, se pierden los nueve departamentos con codigo bajo la mitad de
# los sectores, y el mapa queda con un agujero que nadie sabe explicar.
sec_poly["cod_se"] = sec_poly["cod_se"].astype(str).str.strip().str.zfill(8)
sec_poly = sec_poly.merge(
    sec_pt[["cod_se", "s_sam_usd", "s_clientes_sam", "horas_capital_real"]]
    .assign(cod_se=lambda d: d["cod_se"].astype(str).str.strip().str.zfill(8)),
    on="cod_se", how="inner")


def delta(coords):
    """Anillo como enteros: el primer vertice absoluto, el resto diferencias."""
    pl = [(round(x * Q), round(y * Q)) for x, y in coords]
    out = [pl[0][0], pl[0][1]]
    px, py = pl[0]
    for x, y in pl[1:]:
        out.append(x - px)
        out.append(y - py)
        px, py = x, y
    return out


poligonos, atrib = [], []
for _, r in sec_poly.sort_values("s_sam_usd", ascending=False).iterrows():
    g = r.geometry
    if g.is_empty:
        continue
    partes = g.geoms if g.geom_type == "MultiPolygon" else [g]
    anl = [delta(p.exterior.coords) for p in partes
           if len(p.exterior.coords) > 3]
    if not anl:
        continue
    poligonos.append(anl)
    atrib.append([
        int(round(float(r["s_sam_usd"]) / 1000)),
        int(round(float(r["s_clientes_sam"]))),
        finito(r["horas_capital_real"]),
        i_dep_sec.get(key(r["dep"]), -1),
        i_reg_sec.get(str(r["region_nat"]).upper(), -1),
        i_prov_sec.get(cap(r["prov"]), -1),
        rank_de(r["lat"], r["lon"]),
    ])

capas = {"sect": sectores_pt, "sect_prov": cat_prov, "provs": provs_geo,
         "sect_poly": poligonos, "sect_poly_at": atrib, "q": Q}
with open("out/mapa_capas.json", "w", encoding="utf-8") as fh:
    json.dump(capas, fh, separators=(",", ":"), ensure_ascii=False,
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
print(f"mapa_capas.json: {os.path.getsize('out/mapa_capas.json')/1e6:.2f} MB "
      f"(carga diferida)")
