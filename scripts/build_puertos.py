# -*- coding: utf-8 -*-
"""Locate Peru's commercial port terminals and tie each region to its outlet.

OpenStreetMap turned out to hold mostly river landings for Peru, not the
maritime terminals that actually move agro-export volume, so the terminal list
comes from the Autoridad Portuaria Nacional's public inventory and each one is
geocoded against OSM's Nominatim to get a verified coordinate rather than a
remembered one.

Why this matters commercially: an agro-export valley buys a different basket of
inputs than a subsistence one — certified, residue-controlled, on a tighter
calendar — and it is creditworthy because it invoices in dollars. Distance to
the loading port is a decent proxy for how export-oriented a region is.
"""
import json
import time

import pandas as pd
import requests

HEADERS = {"User-Agent": "agrojuntos-logistics/1.0 (contacto@agrojuntos.com)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Autoridad Portuaria Nacional: terminals open to public commercial traffic.
# "tipo" separates deep-water maritime terminals from river ports, which serve
# a different logistic reality in the Amazon.
PUERTOS = [
    # nombre para geocodificar, etiqueta, region, tipo, relevancia agro
    ("Puerto del Callao, Callao, Perú", "Callao", "CALLAO", "maritimo", "alta"),
    ("Puerto de Paita, Piura, Perú", "Paita", "PIURA", "maritimo", "alta"),
    ("Puerto de Salaverry, La Libertad, Perú", "Salaverry", "LA LIBERTAD", "maritimo", "alta"),
    ("Puerto de Matarani, Islay, Arequipa, Perú", "Matarani", "AREQUIPA", "maritimo", "alta"),
    ("Puerto San Martin, Paracas, Ica, Perú", "Pisco (Gral. San Martín)", "ICA", "maritimo", "alta"),
    ("Puerto de Chancay, Lima, Perú", "Chancay", "LIMA", "maritimo", "alta"),
    ("Puerto de Chimbote, Áncash, Perú", "Chimbote", "ANCASH", "maritimo", "media"),
    ("Puerto de Ilo, Moquegua, Perú", "Ilo", "MOQUEGUA", "maritimo", "media"),
    ("Puerto de Supe, Barranca, Lima, Perú", "Supe", "LIMA", "maritimo", "media"),
    ("Puerto de Huacho, Lima, Perú", "Huacho", "LIMA", "maritimo", "baja"),
    ("Puerto de Talara, Piura, Perú", "Talara", "PIURA", "maritimo", "baja"),
    ("Puerto Eten, Chiclayo, Lambayeque, Perú", "Eten", "LAMBAYEQUE", "maritimo", "baja"),
    ("Puerto de Iquitos, Loreto, Perú", "Iquitos", "LORETO", "fluvial", "media"),
    ("Puerto de Yurimaguas, Loreto, Perú", "Yurimaguas", "LORETO", "fluvial", "media"),
    ("Puerto de Pucallpa, Ucayali, Perú", "Pucallpa", "UCAYALI", "fluvial", "media"),
    ("Puerto Maldonado, Madre de Dios, Perú", "Puerto Maldonado", "MADRE DE DIOS", "fluvial", "baja"),
]


def geocodificar(consulta):
    r = requests.get(NOMINATIM, headers=HEADERS, timeout=60,
                     params={"q": consulta, "format": "json", "limit": 1,
                             "countrycodes": "pe"})
    if r.status_code != 200:
        return None
    d = r.json()
    if not d:
        return None
    return float(d[0]["lat"]), float(d[0]["lon"]), d[0].get("display_name", "")


filas = []
for consulta, nombre, region, tipo, rel in PUERTOS:
    pos = None
    for intento in range(3):
        try:
            pos = geocodificar(consulta)
            break
        except Exception:
            time.sleep(4)
    if pos is None:
        print(f"  SIN UBICAR  {nombre}")
        continue
    lat, lon, disp = pos
    filas.append({"puerto": nombre, "region": region, "tipo": tipo,
                  "relevancia_agro": rel, "lat": round(lat, 5),
                  "lon": round(lon, 5), "osm": disp[:70]})
    print(f"  {nombre:26s} {tipo:9s} {lat:9.4f} {lon:10.4f}")
    time.sleep(1.2)                      # Nominatim asks for 1 req/s

p = pd.DataFrame(filas)
p.to_csv("out/puertos.csv", index=False, encoding="utf-8-sig")

# ---- add the river landings OSM does know about, as secondary nodes -------
try:
    d = json.load(open("data/vial/puertos.json", encoding="utf-8"))
    sec = []
    for x in d["elements"]:
        t = x.get("tags", {})
        n = (t.get("name") or "").strip()
        if not n:
            continue
        lat = x.get("lat") or (x.get("center") or {}).get("lat")
        lon = x.get("lon") or (x.get("center") or {}).get("lon")
        if lat is None:
            continue
        clase = ("aeropuerto" if t.get("aeroway") else
                 "embarcadero" if t.get("amenity") == "ferry_terminal" else
                 "muelle" if t.get("man_made") == "pier" else "portuario")
        sec.append({"nombre": n, "clase": clase, "lat": round(lat, 5),
                    "lon": round(lon, 5)})
    s = pd.DataFrame(sec).drop_duplicates(subset=["nombre", "lat", "lon"])
    s.to_csv("out/puntos_logisticos.csv", index=False, encoding="utf-8-sig")
    print(f"\npuntos logisticos secundarios (OSM): {len(s)}")
    print(s.clase.value_counts().to_string())
except FileNotFoundError:
    pass

print(f"\nterminales ubicados: {len(p)} de {len(PUERTOS)}")
print(p.groupby(["tipo", "relevancia_agro"]).size().to_string())
