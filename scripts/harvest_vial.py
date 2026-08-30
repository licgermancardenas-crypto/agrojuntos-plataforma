# -*- coding: utf-8 -*-
"""Download Peru's road network and its ports from OpenStreetMap.

For a business that delivers on credit, travel time is margin: a sector forty
minutes from Trujillo and one six hours up a valley are not the same customer
even when they buy the same tonnage. The national model cannot see that
difference, so we pull the road graph and measure it.

Roads come in one request per department to keep each response small enough
that a timeout costs one region, not the whole run.
"""
import json
import os
import sys
import time

import requests

HEADERS = {"User-Agent": "agrojuntos-logistics/1.0 (contacto@agrojuntos.com)"}
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

DEPTS = {
    1973462: "PE-AMA", 1953170: "PE-ANC", 1929522: "PE-APU", 1879287: "PE-ARE",
    1930901: "PE-AYA", 1896111: "PE-CAJ", 1944657: "PE-CAL", 1923695: "PE-CUS",
    1933551: "PE-HUV", 1954493: "PE-HUC", 1899013: "PE-ICA", 1948258: "PE-JUN",
    1967959: "PE-LAL", 1969722: "PE-LAM", 1944659: "PE-LIM", 1994077: "PE-LOR",
    1891287: "PE-MDD", 1875889: "PE-MOQ", 1948452: "PE-PAS", 1986151: "PE-PIU",
    1907899: "PE-PUN", 1971661: "PE-SAM", 1874307: "PE-TAC", 1986974: "PE-TUM",
    1921996: "PE-UCA",
}

# Trunk through tertiary is the network a delivery truck actually uses;
# residential and track would multiply the graph without changing route choice.
VIAS = "^(motorway|trunk|primary|secondary|tertiary)(_link)?$"

Q_VIAL = """
[out:json][timeout:600];
area({area})->.a;
way(area.a)["highway"~"{vias}"];
out geom tags;
"""

# Ports, terminals and their access: where agro-export volume leaves the country.
Q_PUERTOS = """
[out:json][timeout:600];
area(3600288247)->.pe;
(
  nwr(area.pe)["harbour"];
  nwr(area.pe)["landuse"="harbour"];
  nwr(area.pe)["industrial"="port"];
  nwr(area.pe)["amenity"="ferry_terminal"];
  nwr(area.pe)["man_made"="pier"]["name"];
  nwr(area.pe)["aeroway"="aerodrome"]["name"];
);
out center tags;
"""


def run(query, tries=6):
    last = None
    for i in range(tries):
        url = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS,
                              timeout=900)
            if r.status_code == 200:
                return json.loads(r.text)
            last = f"HTTP {r.status_code}"
        except Exception as ex:
            last = repr(ex)[:120]
        print(f"    retry {i+1}/{tries} {url.split('/')[2]}: {last}", flush=True)
        time.sleep(90 * (i + 1))
    raise RuntimeError(last)


def main():
    os.makedirs("data/vial", exist_ok=True)

    path = "data/vial/puertos.json"
    if not os.path.exists(path) or os.path.getsize(path) < 200:
        t0 = time.time()
        try:
            d = run(Q_PUERTOS)
            json.dump(d, open(path, "w", encoding="utf-8"))
            print(f"puertos y terminales  {len(d['elements']):6d} el  "
                  f"{time.time()-t0:5.1f}s", flush=True)
        except Exception as ex:
            print(f"FALLO puertos: {ex}", flush=True)

    fallos = []
    for rel, iso in DEPTS.items():
        path = f"data/vial/{iso}.json"
        if os.path.exists(path) and os.path.getsize(path) > 200:
            continue
        t0 = time.time()
        try:
            d = run(Q_VIAL.format(area=3600000000 + rel, vias=VIAS))
        except Exception as ex:
            print(f"FALLO {iso}: {ex}", flush=True)
            fallos.append(iso)
            continue
        json.dump(d, open(path, "w", encoding="utf-8"))
        print(f"{iso}  {len(d['elements']):6d} vias  {time.time()-t0:6.1f}s  "
              f"{os.path.getsize(path)/1e6:5.1f}MB", flush=True)
        time.sleep(2)
    print(f"\nDONE. fallos={fallos}")


if __name__ == "__main__":
    main()
