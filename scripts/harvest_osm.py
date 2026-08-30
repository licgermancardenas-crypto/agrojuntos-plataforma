# -*- coding: utf-8 -*-
"""Harvest agricultural features for Peru from OpenStreetMap via Overpass.

Runs one small query per (department, probe) pair so a single slow or failing
probe never kills the whole run. Results are cached as JSON under data/osm/ and
the script is safe to re-run: existing files are skipped.

Probes:
  landuse   - farmland/orchard/vineyard/greenhouse/nursery polygons (with geometry)
  named     - places/landuse named "Fundo|Hacienda|Chacra|..."
  agroind   - agro-industrial works, mills, industrial sites
  retail    - agro shops, veterinaries, garden centres (the "tienda rural" channel)
  farmbld   - farm buildings and greenhouses
"""
import json, os, sys, time
import requests

HEADERS = {"User-Agent": "agrojuntos-market-map/1.0 (contacto@agrojuntos.com)"}
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# OSM relation id -> (ISO code, department name). area id = 3600000000 + rel id.
DEPTS = {
    1973462: ("PE-AMA", "Amazonas"),      1953170: ("PE-ANC", "Ancash"),
    1929522: ("PE-APU", "Apurimac"),      1879287: ("PE-ARE", "Arequipa"),
    1930901: ("PE-AYA", "Ayacucho"),      1896111: ("PE-CAJ", "Cajamarca"),
    1944657: ("PE-CAL", "Callao"),        1923695: ("PE-CUS", "Cusco"),
    1933551: ("PE-HUV", "Huancavelica"),  1954493: ("PE-HUC", "Huanuco"),
    1899013: ("PE-ICA", "Ica"),           1948258: ("PE-JUN", "Junin"),
    1967959: ("PE-LAL", "La Libertad"),   1969722: ("PE-LAM", "Lambayeque"),
    1944659: ("PE-LIM", "Lima"),          1994077: ("PE-LOR", "Loreto"),
    1891287: ("PE-MDD", "Madre de Dios"), 1875889: ("PE-MOQ", "Moquegua"),
    1948452: ("PE-PAS", "Pasco"),         1986151: ("PE-PIU", "Piura"),
    1907899: ("PE-PUN", "Puno"),          1971661: ("PE-SAM", "San Martin"),
    1874307: ("PE-TAC", "Tacna"),         1986974: ("PE-TUM", "Tumbes"),
    1921996: ("PE-UCA", "Ucayali"),
}

LU = '^(farmland|orchard|greenhouse_horticulture|vineyard|plant_nursery|aquaculture)$'

PROBES = {
    "landuse": ('way(area.a)["landuse"~"%s"];\n  relation(area.a)["landuse"~"%s"];' % (LU, LU),
                "geom"),
    "named":   ('nwr(area.a)["place"]["name"~"[Ff]undo|[Hh]acienda|[Cc]hacra|[Pp]arcela",i];\n'
                '  nwr(area.a)["landuse"]["name"];', "center"),
    "agroind": ('nwr(area.a)["man_made"="works"];\n'
                '  nwr(area.a)["landuse"="industrial"]["name"];\n'
                '  nwr(area.a)["craft"~"^(agricultural_engines|distillery|winery|oil_mill)$"];', "center"),
    "retail":  ('nwr(area.a)["shop"~"^(agrarian|farm|garden_centre|trade|doityourself|hardware|pet|veterinary)$"];\n'
                '  nwr(area.a)["amenity"="veterinary"];', "center"),
    "farmbld": ('nwr(area.a)["building"~"^(farm|farm_auxiliary|greenhouse|barn|silo|warehouse)$"]["name"];\n'
                '  nwr(area.a)["man_made"="silo"];', "center"),
}

TPL = "[out:json][timeout:600];\narea({area})->.a;\n(\n  {body}\n);\nout {out};\n"


def run(query, tries=4):
    last = None
    for i in range(tries):
        url = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=700)
            if r.status_code == 200:
                return json.loads(r.text)
            last = f"HTTP {r.status_code}: {r.text[:120].strip()}"
        except Exception as ex:
            last = repr(ex)[:160]
        print(f"    retry {i+1}/{tries} {url.split('/')[2]}: {last}", flush=True)
        time.sleep(30 * (i + 1))
    raise RuntimeError(last)


def main():
    os.makedirs("data/osm", exist_ok=True)
    wanted_dep = [a for a in sys.argv[1:] if a.startswith("PE-")]
    wanted_probe = [a for a in sys.argv[1:] if not a.startswith("PE-")]
    failures = []
    for rel, (iso, name) in DEPTS.items():
        if wanted_dep and iso not in wanted_dep:
            continue
        for probe, (body, out) in PROBES.items():
            if wanted_probe and probe not in wanted_probe:
                continue
            path = f"data/osm/{iso}_{probe}.json"
            if os.path.exists(path) and os.path.getsize(path) > 200:
                continue
            t0 = time.time()
            try:
                data = run(TPL.format(area=3600000000 + rel, body=body, out=out))
            except Exception as ex:
                print(f"FAIL {iso:8s} {probe:8s} {ex}", flush=True)
                failures.append((iso, probe))
                continue
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            print(f"{iso:8s} {name:14s} {probe:8s} {len(data['elements']):6d} el  "
                  f"{time.time()-t0:6.1f}s  {os.path.getsize(path)/1e6:5.1f}MB", flush=True)
            time.sleep(2)
    print(f"\nDONE. failures={failures}")


if __name__ == "__main__":
    main()
