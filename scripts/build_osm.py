# -*- coding: utf-8 -*-
"""Consolidate the OpenStreetMap harvest into named, located agri entities.

This is the prospecting layer: not "how many hectares are in this district"
but "here is a fundo with a name and a coordinate". Coverage is uneven because
it depends on what volunteers have mapped, so it complements the MIDAGRI layer
and never replaces it.
"""
import glob
import json
import os
import re

import pandas as pd
from pyproj import Geod

GEOD = Geod(ellps="WGS84")
ISO2DEP = {
    "PE-AMA": "AMAZONAS", "PE-ANC": "ANCASH", "PE-APU": "APURIMAC",
    "PE-ARE": "AREQUIPA", "PE-AYA": "AYACUCHO", "PE-CAJ": "CAJAMARCA",
    "PE-CAL": "CALLAO", "PE-CUS": "CUSCO", "PE-HUV": "HUANCAVELICA",
    "PE-HUC": "HUANUCO", "PE-ICA": "ICA", "PE-JUN": "JUNIN",
    "PE-LAL": "LA LIBERTAD", "PE-LAM": "LAMBAYEQUE", "PE-LIM": "LIMA",
    "PE-LOR": "LORETO", "PE-MDD": "MADRE DE DIOS", "PE-MOQ": "MOQUEGUA",
    "PE-PAS": "PASCO", "PE-PIU": "PIURA", "PE-PUN": "PUNO",
    "PE-SAM": "SAN MARTIN", "PE-TAC": "TACNA", "PE-TUM": "TUMBES",
    "PE-UCA": "UCAYALI",
}

# What each match is worth commercially.
FUNDO_RE = re.compile(r"\b(fundo|hacienda|agr[ií]cola|agroindustri|agroexport|"
                      r"packing|vivero|semiller|planta|molino|chacra|parcela)\b", re.I)


def ring_ha(coords):
    if len(coords) < 4:
        return 0.0
    lons = [c["lon"] for c in coords]
    lats = [c["lat"] for c in coords]
    a, _ = GEOD.polygon_area_perimeter(lons, lats)
    return abs(a) / 10000.0


def centroid(el):
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    if "lat" in el:
        return el["lat"], el["lon"]
    g = el.get("geometry") or []
    pts = [p for p in g if p.get("lat") is not None]
    if not pts:
        return None, None
    return sum(p["lat"] for p in pts) / len(pts), sum(p["lon"] for p in pts) / len(pts)


rows = []
for path in sorted(glob.glob("data/osm/*.json")):
    iso, probe = os.path.basename(path)[:-5].rsplit("_", 1)
    dep = ISO2DEP.get(iso, iso)
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    for el in data.get("elements", []):
        t = el.get("tags") or {}
        name = (t.get("name") or "").strip()
        lat, lon = centroid(el)
        if lat is None:
            continue
        ha = 0.0
        if probe == "landuse" and el.get("geometry"):
            ha = ring_ha(el["geometry"])
        rows.append({
            "dep": dep, "capa": probe, "osm_id": f"{el['type'][0]}{el['id']}",
            "nombre": name, "lat": round(lat, 6), "lon": round(lon, 6),
            "ha": round(ha, 2),
            "tipo": t.get("landuse") or t.get("shop") or t.get("man_made")
                    or t.get("craft") or t.get("building") or t.get("amenity")
                    or t.get("industrial") or t.get("place") or "",
            "cultivo": t.get("crop") or t.get("produce") or t.get("trees") or "",
            "operador": t.get("operator") or "",
            "web": t.get("website") or t.get("contact:website") or "",
            "tel": t.get("phone") or t.get("contact:phone") or "",
        })

df = pd.DataFrame(rows).drop_duplicates(subset=["osm_id"])
df.to_csv("out/osm_todo.csv", index=False, encoding="utf-8-sig")

# --- the prospect list: anything with a real name we can call on -----------
pros = df[(df.nombre != "") &
          (df.nombre.str.contains(FUNDO_RE) | df.capa.isin(["retail", "agroind"]))]
pros = pros.sort_values(["dep", "ha"], ascending=[True, False])
pros.to_csv("out/osm_prospectos.csv", index=False, encoding="utf-8-sig")

print(f"elementos OSM        : {len(df):,}   ({df.dep.nunique()} departamentos)")
print(f"con nombre propio    : {(df.nombre != '').sum():,}")
print(f"prospectos           : {len(pros):,}")
print()
print("--- por capa ---")
print(df.groupby("capa").agg(n=("osm_id", "size"),
                             con_nombre=("nombre", lambda s: (s != "").sum()),
                             ha=("ha", "sum")).to_string(float_format=lambda v: f"{v:,.0f}"))
print()
print("--- prospectos por departamento ---")
print(pros.groupby("dep").size().sort_values(ascending=False).to_string())
print()
print("--- muestra ---")
sample = pros[pros.nombre.str.contains(r"fundo|hacienda|agr", case=False)].head(18)
print(sample[["dep", "nombre", "tipo", "ha"]].to_string(index=False))
