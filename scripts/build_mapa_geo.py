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


contorno = [a for _, r in dep_g.iterrows() for a in anillos(r.geometry)]

# ------------------------------------------------------------ hexagonos ---
# El hexágono se dibuja desde su índice H3; enviar los seis vértices de cada
# celda pesaría cuatro veces más que enviar el centro y el radio.
h5 = h5.sort_values("sam_usd", ascending=False)
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

# celdas cubiertas / no cubiertas en el escenario de 6 centros a 2 h
cob = [[round(r["centro_lon"], DEC), round(r["centro_lat"], DEC),
        1 if r["cubierto_2h"] else 0, round(float(r["horas_al_hub"]), 1)]
       for _, r in asig.iterrows()]

# --------------------------------------------------------------- puertos ---
pu = [{"n": r["puerto"], "lat": round(float(r["lat"]), DEC),
       "lon": round(float(r["lon"]), DEC), "tipo": r["tipo"],
       "rel": r["relevancia_agro"]} for _, r in puertos.iterrows()]

# ------------------------------------------------------------------ salida -
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
    "contorno": contorno,
    "hex": hex_cells,
    "territorios": territorios,
    "hubs": hubs_out,
    "cobertura": cob,
    "puertos": pu,
}

with open("out/mapa_geo.json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)

print(f"mapa_geo.json : {os.path.getsize('out/mapa_geo.json')/1e6:.2f} MB")
print(f"  hexagonos   : {len(hex_cells):,} de ~{payload['meta']['km2_celda']} km2")
print(f"  territorios : {len(territorios)}")
print(f"  hubs        : {sum(len(v) for v in hubs_out.values())} escenarios")
print(f"  puertos     : {len(pu)}")
print(f"  celdas cob. : {len(cob):,}")
