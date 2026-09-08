# -*- coding: utf-8 -*-
"""Los centros poblados del país, con su población y sus coordenadas.

La red de canal dejó una pregunta sin contestar: **dónde abrir donde no hay
nadie**. Son 84,424 clientes sin ningún punto de venta a 45 minutos, y para
proponer algo hace falta saber en qué pueblos vive esa gente. La capa de
prospectos no servía: de sus 873 «hamlets» de OpenStreetMap, 851 eran fundos y
haciendas con nombre, que son clientes y no sitios donde abrir.

Ninguna fuente sola alcanza, y por eso se cruzan dos:

  **INEI, Directorio Nacional de Centros Poblados (censo 2017).** El padrón
  completo —quién es un centro poblado, cuánta gente vive ahí, a qué altura y
  en qué región natural—, publicado en 26 archivos por departamento. Lo que no
  trae es coordenada: ubica por código de distrito y nada más.

  **OpenStreetMap.** Trae la coordenada de cada pueblo que alguien mapeó. Lo
  que no trae es el padrón: no sabe cuáles faltan.

El cruce se hace por nombre dentro del mismo distrito, y su resultado más útil
no es la lista sino **la medida de lo que falta**: cuántos centros poblados del
padrón no están en OSM, y cuánta población viven en ellos. Esa cifra es la que
convierte «OSM no lo mapea» de excusa en dato.

## Por qué el nombre y no otra cosa

No hay identificador común. El INEI numera el centro poblado dentro de su
distrito y OSM tiene su propio `osm_id`; lo único compartido es cómo se llama
y en qué distrito está. El nombre se normaliza —sin tildes, sin mayúsculas,
sin los prefijos que uno pone y el otro no: «anexo», «caserío», «centro
poblado»— y aun así el cruce no es perfecto. Se declara cuánto pega.

## Lo que este archivo NO hace

No inventa coordenadas para los que no pegaron. Un centro poblado sin
coordenada queda en la salida con su población y sin `lat`/`lon`, marcado como
tal: sirve para contar lo que falta y no para dibujarlo en un mapa. Ponerle el
centroide de su distrito sería inventar un pueblo donde no lo hay.

Uso:
    python scripts/build_ccpp.py
    python scripts/build_ccpp.py --overpass   fuerza bajar OSM de nuevo
"""
import glob
import io
import json
import os
import re
import sys
import time
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

INEI = "data/inei"
CACHE_OSM = "data/inei/osm_places.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
CONSULTA = """
[out:json][timeout:600];
area["ISO3166-1"="PE"][admin_level=2]->.pe;
node["place"~"^(city|town|village|hamlet)$"]["name"](area.pe);
out body;
"""

# Lo que uno escribe y el otro no. «Anexo Huaracalla» y «Huaracalla» son el
# mismo sitio, y sin quitar el prefijo el cruce los da por distintos.
PREFIJOS = ("centro poblado ", "cp ", "anexo ", "caserio ", "pueblo ",
            "comunidad campesina ", "comunidad ", "asentamiento humano ",
            "ah ", "urbanizacion ", "barrio ", "sector ", "unidad agropecuaria ")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    for p in PREFIJOS:
        if s.startswith(p):
            s = s[len(p):].strip()
    return s


# ----------------------------------------------------- el padron del INEI --
def leer_inei():
    """Los 26 archivos por departamento, que vienen jerárquicos: una fila fija
    el distrito y las que siguen son sus centros poblados.

    La trampa está en el código. Un centro poblado se numera con cuatro
    dígitos dentro de su distrito —0001, 0003…— y **la fila de PROVINCIA
    también trae cuatro dígitos**: 1304 es la provincia de Chepén. Contarlas
    como centros poblados sumaba el total de cada provincia encima de sus
    propios pueblos, y la población nacional daba 40.7 millones contra los 31
    del censo. Lo que las distingue no es el código sino la región natural:
    un centro poblado dice «Chala» o «Quechua» y un título no dice nada.
    """
    filas = []
    for f in sorted(glob.glob(os.path.join(INEI, "dpto*.xlsx"))):
        d = pd.read_excel(f, header=None)
        ubigeo = dist = None
        for _, r in d.iterrows():
            cod = "" if pd.isna(r[0]) else str(r[0]).strip()
            nom = "" if pd.isna(r[1]) else str(r[1]).strip()
            if not cod or not nom:
                continue
            if len(cod) == 6 and cod.isdigit() and nom.upper().startswith(
                    "DISTRITO"):
                ubigeo, dist = cod, nom[8:].strip()
                continue
            if nom.upper().startswith(("PROVINCIA", "DEPARTAMENTO")):
                continue
            if pd.isna(r[2]) or not str(r[2]).strip():
                continue          # sin región natural no es un centro poblado
            if ubigeo and len(cod) == 4 and cod.isdigit():
                filas.append({
                    "ubigeo": ubigeo, "distrito": dist, "cod": cod,
                    "nombre": nom,
                    "region_nat": "" if pd.isna(r[2]) else str(r[2]).strip(),
                    "altitud": pd.to_numeric(
                        str(r[3]).replace(" ", ""), errors="coerce"),
                    "poblacion": pd.to_numeric(
                        str(r[4]).replace(" ", ""), errors="coerce"),
                })
    return pd.DataFrame(filas)


# ------------------------------------------------------ los puntos de OSM --
def leer_osm(forzar=False):
    if os.path.exists(CACHE_OSM) and not forzar:
        return json.load(io.open(CACHE_OSM, encoding="utf-8"))["elements"]
    print("pidiendo los pueblos a Overpass (una sola consulta, puede "
          "tardar)...", flush=True)
    for intento in range(3):
        # Sin User-Agent, Overpass contesta 406 y no dice por qué.
        r = requests.post(OVERPASS, data={"data": CONSULTA}, timeout=900,
                          headers={"User-Agent": "AgroJuntos/1.0 "
                                                 "(mapeo de mercado agricola)"})
        if r.status_code == 200:
            io.open(CACHE_OSM, "w", encoding="utf-8").write(r.text)
            return r.json()["elements"]
        # Overpass tumba las consultas seguidas con 429 y 504; hay que esperar.
        print("  http %d, reintento en 60 s" % r.status_code, flush=True)
        time.sleep(60)
    sys.exit("Overpass no respondió")


def main():
    ine = leer_inei()
    print("padrón del INEI: %s centros poblados en %s distritos"
          % (f"{len(ine):,}", f"{ine.ubigeo.nunique():,}"))
    print("  población censada en ellos: %s" % f"{ine.poblacion.sum():,.0f}")
    # El censo de 2017 contó 31.2 millones de personas y en centros poblados
    # vive algo menos. Si esta suma se pasa, se está contando algo dos veces
    # —fue exactamente lo que pasó con las filas de provincia— y conviene que
    # el propio archivo lo diga en vez de que se note tres pantallas después.
    if ine.poblacion.sum() > 32e6:
        sys.exit("la población suma %s: más que el censo entero, hay filas "
                 "contadas dos veces" % f"{ine.poblacion.sum():,.0f}")

    els = leer_osm("--overpass" in sys.argv)
    osm = pd.DataFrame([{"osm_id": e["id"], "nombre": e["tags"].get("name", ""),
                         "tipo": e["tags"].get("place", ""),
                         "lat": e["lat"], "lon": e["lon"]} for e in els])
    print("OpenStreetMap: %s lugares con nombre" % f"{len(osm):,}")

    # A qué distrito pertenece cada punto de OSM. Sin esto el cruce por nombre
    # juntaría los cuatro «San Juan» del país en uno solo.
    print("ubicando cada punto en su distrito...", flush=True)
    dis = gpd.read_file("data/peru_distrital_simple.geojson").to_crs(4326)
    col_u = next((c for c in dis.columns
                  if c.upper() in ("IDDIST", "UBIGEO", "CCDD_CCPP", "IDDPTO")),
                 None)
    if col_u is None:
        sys.exit("la capa distrital no trae ubigeo: columnas %s"
                 % list(dis.columns))
    pts = gpd.GeoDataFrame(osm, geometry=gpd.points_from_xy(osm.lon, osm.lat),
                           crs=4326)
    osm = gpd.sjoin(pts, dis[[col_u, "geometry"]], how="left",
                    predicate="within").drop(columns="geometry")
    osm = osm.rename(columns={col_u: "ubigeo"})
    osm["ubigeo"] = osm["ubigeo"].astype(str).str.zfill(6)
    fuera = osm.ubigeo.isna().sum() + (osm.ubigeo == "0000NAN").sum()
    print("  %s puntos ubicados, %s fuera de toda frontera"
          % (f"{len(osm) - fuera:,}", f"{fuera:,}"))

    # --------------------------------------------------------- el cruce ---
    ine["k"] = ine["ubigeo"] + "|" + ine["nombre"].map(norm)
    osm["k"] = osm["ubigeo"] + "|" + osm["nombre"].map(norm)
    xy = (osm.dropna(subset=["k"]).drop_duplicates("k")
             .set_index("k")[["lat", "lon", "tipo", "osm_id"]])
    j = xy.reindex(ine["k"])
    for c in ("lat", "lon", "tipo", "osm_id"):
        ine[c] = j[c].values
    con = ine.lat.notna()
    print()
    print("el cruce, dicho como es")
    print("  %s de %s centros poblados del padrón tienen coordenada (%.1f%%)"
          % (f"{con.sum():,}", f"{len(ine):,}", 100 * con.mean()))
    print("  esos concentran el %.1f%% de la población censada en centros "
          "poblados" % (100 * ine.loc[con, "poblacion"].sum()
                        / ine["poblacion"].sum()))
    gr = ine.assign(con=con).groupby(pd.cut(
        ine.poblacion, [0, 50, 200, 1000, 5000, 1e9],
        labels=["<50", "50-200", "200-1k", "1k-5k", ">5k"]),
        observed=True)["con"].agg(["size", "sum"])
    print()
    print("  %-10s %10s %10s %8s" % ("población", "del padrón", "con coord",
                                     "%"))
    for i, r in gr.iterrows():
        print("  %-10s %10s %10s %7.0f%%"
              % (i, f"{int(r['size']):,}", f"{int(r['sum']):,}",
                 100 * r["sum"] / r["size"]))

    ine.drop(columns="k").to_csv("out/ccpp.csv", index=False,
                                 encoding="utf-8-sig")
    resumen = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "fuente": ("INEI, Directorio Nacional de Centros Poblados (censo "
                   "2017), 26 archivos por departamento; coordenadas de "
                   "OpenStreetMap cruzadas por nombre dentro del distrito"),
        "centros": int(len(ine)),
        "distritos": int(ine.ubigeo.nunique()),
        "poblacion": int(ine.poblacion.sum()),
        "con_coordenada": int(con.sum()),
        "pct_con_coordenada": round(100 * float(con.mean()), 1),
        "pct_poblacion_con_coordenada": round(
            100 * float(ine.loc[con, "poblacion"].sum()
                        / ine["poblacion"].sum()), 1),
        "advertencia": ("los que no pegaron quedan sin lat/lon a proposito: "
                        "ponerles el centroide de su distrito seria inventar "
                        "un pueblo donde no lo hay"),
    }
    io.open("out/ccpp.json", "w", encoding="utf-8").write(
        json.dumps(resumen, ensure_ascii=False, indent=1))
    print()
    print("out/ccpp.csv · out/ccpp.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
