# -*- coding: utf-8 -*-
"""Extract the agricultural business universe from SUNAT's reduced RUC padrón.

The padrón reducido carries RUC, trade name, taxpayer status, domicile
condition, ubigeo and fiscal address — but *not* the CIIU activity code, which
SUNAT only exposes through per-RUC lookup. So companies are classified by
trade name, which in Peru is unusually reliable for this sector: agricultural
firms almost invariably carry AGRICOLA, AGRO, FUNDO or AGROINDUSTRIAL in their
registered name.

The classification is deliberately not a single "agro" bucket, because the four
groups mean different things commercially:

  productor     the customer — farms and estates
  agroindustria the large customer — packing, processing, export
  canal         the competitor and the partner — agro-input retail
  proveedor     upstream — fertiliser and agrochemical makers and importers

Only juridical persons are considered — RUC beginning with 20. Peru issues 10
to natural persons, and several of the keywords here are also common surnames
("Abono", "Molino", "Agrota"), so without that filter the list fills with
individuals whose family name merely resembles the trade.

Name matching cannot see a company that trades under a neutral name, so this
undercounts. It never invents: every row is a real registered taxpayer.
"""
import io
import os
import re
import zipfile

import pandas as pd

ZIP = "data/sunat/ruc.zip"
UBIGEO_GEO = "data/peru_distrital_simple.geojson"

# Ordered: the first pattern that matches wins, so the most specific
# classifications are tested before the generic "agro" catch-all.
REGLAS = [
    # Patterns are prefixes, not whole words: Peruvian trade names inflect
    # freely (AGROINDUSTRIAL / AGROINDUSTRIAS / AGROINDUSTRIA), and a trailing
    # word boundary would drop most of the plurals into the generic bucket.
    ("proveedor", re.compile(
        r"(FERTILIZANT|AGROQUIMIC|AGROQUÍMIC|PLAGUICID|FITOSANITARI|"
        r"NUTRICION VEGETAL|NUTRICIÓN VEGETAL|BIOINSUMO|ABONOS|"
        r"AGROINSUMO|AGRO INSUMO)")),
    ("canal", re.compile(
        r"(AGROVETERINARIA|AGRO VETERINARIA|VETERINARIA AGRO|AGROCOMERCIAL|"
        r"AGRO COMERCIAL|INSUMOS AGRICOLA|INSUMOS AGRÍCOLA|AGROSERVICIO|"
        r"AGRO SERVICIO|SEMILLER|AGROTIENDA|DISTRIBUIDORA AGRO|AGRO DISTRIBU|"
        r"COMERCIALIZADORA AGRO|AGRO COMERCIALIZ)")),
    ("agroindustria", re.compile(
        r"(AGROINDUSTRI|AGRO INDUSTRI|AGROEXPORT|AGRO EXPORT|PACKING|"
        r"EMPACADORA|AGROFRESH|MOLINER|MOLINO|AZUCARER|CONSERVER|"
        r"AGROPROCES|PROCESADORA AGRO)")),
    ("productor", re.compile(
        r"(AGRICOLA|AGRÍCOLA|FUNDO|AGROPECUARI|AGRO PECUARI|HACIENDA|"
        r"AGRARI|PLANTACION|PLANTACIÓN|VIVERO|AGROCULTIV|AGRO CULTIV|"
        r"AGROGANADER|AGRONEGOCIO|AGRO NEGOCIO)")),
    ("agro_otro", re.compile(r"AGRO")),
]


# Foreign-trade orientation, orthogonal to the four groups above.
RE_COMEX = re.compile(r"\b(EXPORT|IMPORT|TRADING|COMEX|COMERCIO EXTERIOR)\b")
RE_EXPORT = re.compile(r"\bEXPORT")
RE_IMPORT = re.compile(r"\bIMPORT")

# Anything matching these is not an agricultural operation despite the word.
RE_EXCLUIR = re.compile(
    r"\b(TRANSPORTE|TRANSPORTES|CONSTRUCTORA|INMOBILIARIA|GRIFO|"
    r"RESTAURANT|HOTEL|BOTICA|FARMACIA|LIBRERIA|TAXI)\b")


def clasificar(nombre):
    if RE_EXCLUIR.search(nombre):
        return None
    for etiqueta, patron in REGLAS:
        if patron.search(nombre):
            return etiqueta
    return None


def leer(zip_path):
    zf = zipfile.ZipFile(zip_path)
    nombre = zf.namelist()[0]
    with zf.open(nombre) as f:
        for linea in io.TextIOWrapper(f, encoding="latin-1", errors="replace"):
            yield linea


def main():
    filas = []
    total = 0
    cab = None
    for linea in leer(ZIP):
        total += 1
        if cab is None:
            cab = [c.strip() for c in linea.rstrip("\n").split("|")]
            continue
        p = linea.rstrip("\n").split("|")
        if len(p) < 6:
            continue
        ruc, nom = p[0].strip(), p[1].strip().upper()
        if not ruc.isdigit() or len(nom) < 4:
            continue
        if not ruc.startswith("20"):        # 20 = persona juridica
            continue
        cls = clasificar(nom)
        if cls is None:
            continue
        # The fiscal address arrives split across ten columns (via type, via
        # name, number, interior, lot, block, kilometre...) with "-" for the
        # ones that do not apply; rebuild it into one readable line.
        partes = [x.strip() for x in p[5:15] if x.strip() not in ("-", "")]
        filas.append({
            "ruc": ruc, "razon_social": p[1].strip(), "clase": cls,
            "estado": p[2].strip(), "condicion": p[3].strip(),
            "ubigeo": p[4].strip().zfill(6),
            "direccion": " ".join(partes)[:90],
            "exporta": bool(RE_EXPORT.search(nom)),
            "importa": bool(RE_IMPORT.search(nom)),
            "comex": bool(RE_COMEX.search(nom)),
        })

    print(f"lineas leidas   : {total:,}")
    print(f"empresas agro   : {len(filas):,}")
    d = pd.DataFrame(filas)

    # Only active, locatable taxpayers are commercially useful.
    d["activo"] = d["estado"].str.upper().str.startswith("ACTIVO")
    d["habido"] = d["condicion"].str.upper().str.startswith("HABIDO")

    # Attach district / province / department from the ubigeo.
    import geopandas as gpd
    g = gpd.read_file(UBIGEO_GEO)[["IDDIST", "NOMBDIST", "NOMBPROV", "NOMBDEP"]]
    g = g.rename(columns={"IDDIST": "ubigeo", "NOMBDIST": "distrito",
                          "NOMBPROV": "provincia", "NOMBDEP": "dep"})
    g["ubigeo"] = g["ubigeo"].astype(str).str.zfill(6)
    d = d.merge(g, on="ubigeo", how="left")

    d.to_csv("out/empresas_agro.csv", index=False, encoding="utf-8-sig")
    act = d[d.activo & d.habido]
    act.to_csv("out/empresas_agro_activas.csv", index=False,
               encoding="utf-8-sig")

    print(f"activas y habidas: {len(act):,}")
    print(f"ubigeo resuelto  : {act.dep.notna().sum():,}")
    print()
    print("--- POR CLASE (activas) ---")
    print(act.clase.value_counts().to_string())
    print()
    print("--- COMERCIO EXTERIOR (nombre declara export/import) ---")
    print(f"  exportadoras : {act.exporta.sum():,}")
    print(f"  importadoras : {act.importa.sum():,}")
    print(f"  trading/comex: {act.comex.sum():,}")
    print()
    print("--- TOP REGIONES ---")
    t = (act.groupby("dep")
         .agg(empresas=("ruc", "size"),
              productor=("clase", lambda s: (s == "productor").sum()),
              agroind=("clase", lambda s: (s == "agroindustria").sum()),
              canal=("clase", lambda s: (s == "canal").sum()),
              comex=("comex", "sum"))
         .sort_values("empresas", ascending=False))
    print(t.head(14).to_string())


if __name__ == "__main__":
    if not os.path.exists(ZIP):
        raise SystemExit(f"falta {ZIP}")
    main()
