# -*- coding: utf-8 -*-
"""Read SUNAT's bulk customs microdata and extract the agro-input trade.

Correction of record: an earlier version of this analysis stated that
company-level customs data is not publicly downloadable in Peru. It is. Under
the Transparency Law (Ley 27806) SUNAT publishes the full definitive-regime
databases at aduanet.gob.pe/aduanas/informae/ as weekly DBF archives:

    ma<fecha>.zip   importación definitiva, formato A — importer RUC and name
    mb<fecha>.zip   importación definitiva, formato B — supplier abroad
    x<fecha>.zip    exportación definitiva
    idv<fecha>.zip  informes de verificación

That gives, per customs line: RUC, razón social, tariff heading, FOB value,
net weight and country. For AgroJuntos this is the competitive map — who
imports fertiliser and crop protection into Peru, and at what scale.

The files are dBase III with no Python reader installed here, so this parses
the format directly and streams records rather than loading 263 MB into memory.

Tariff chapters that matter:
    31  abonos (fertilisers)
    38  productos diversos de la industria química, incl. 3808 pesticides
    12  semillas y frutos oleaginosos, incl. 1209 seeds for sowing
"""
import glob
import io
import os
import re
import struct
import sys
import zipfile
from collections import defaultdict

import pandas as pd

# Classification at four digits, not two. Chapter 38 as a whole is "chemical
# products" and sweeps in explosives and mining reagents — Maxam and Orica are
# not competitors. Only 3808 is crop protection.
PARTIDAS = {
    "3101": "Fertilizante organico",
    "3102": "Fertilizante nitrogenado",
    "3103": "Fertilizante fosfatado",
    "3104": "Fertilizante potasico",
    "3105": "Fertilizante compuesto",
    "3808": "Proteccion de cultivos",
    "1209": "Semillas para siembra",
    "2510": "Fosfatos naturales",
}
RUBRO = {
    "3101": "Fertilizantes", "3102": "Fertilizantes", "3103": "Fertilizantes",
    "3104": "Fertilizantes", "3105": "Fertilizantes", "2510": "Fertilizantes",
    "3808": "Proteccion de cultivos",
    "1209": "Semillas",
}


def leer_dbf(fh, campos_query=None):
    """Stream a dBase III file, yielding dicts. Only `campos_query` is decoded.

    The whole header is read in one block: probing for the 0x0D terminator a
    field at a time overshoots it by 31 bytes and silently misaligns every
    record that follows.
    """
    cab = fh.read(32)
    if len(cab) < 32:
        return
    n_reg = struct.unpack("<I", cab[4:8])[0]
    len_cab = struct.unpack("<H", cab[8:10])[0]
    len_reg = struct.unpack("<H", cab[10:12])[0]

    resto = fh.read(len_cab - 32)            # descriptors + terminator + padding
    campos = []
    pos = 1                                  # byte 0 of a record is the delete flag
    for off in range(0, len(resto) - 31, 32):
        d = resto[off:off + 32]
        if d[0] == 0x0D:
            break
        nombre = d[:11].split(bytes([0]))[0].decode("latin-1").strip()
        largo = d[16]
        campos.append((nombre, pos, largo))
        pos += largo

    quer = [c for c in campos if campos_query is None or c[0] in campos_query]
    for _ in range(n_reg):
        raw = fh.read(len_reg)
        if len(raw) < len_reg or raw[:1] == b"*":     # deleted record
            continue
        yield {n: raw[p:p + l].decode("latin-1").strip() for n, p, l in quer}


def abrir(zip_path):
    zf = zipfile.ZipFile(zip_path)
    nombre = zf.namelist()[0]
    return zf.open(nombre), nombre


def partida4(part):
    """NANDINA headings arrive as a 10-digit number, sometimes unpadded."""
    p = re.sub(r"\D", "", str(part))
    if not p:
        return ""
    return p.zfill(10)[:4]


def procesar_import(zip_path):
    """Import format A: importer RUC and name, tariff heading, FOB, weight."""
    campos = {"LIBR_TRIBU", "DNOMBRE", "PART_NANDI", "FOB_DOLPOL",
              "PESO_NETO", "PAIS_ORIGE", "DESC_COMER"}
    fh, nombre = abrir(zip_path)
    filas = []
    total = 0
    with fh:
        for r in leer_dbf(fh, campos):
            total += 1
            p4 = partida4(r.get("PART_NANDI", ""))
            if p4 not in PARTIDAS:
                continue
            try:
                fob = float(r.get("FOB_DOLPOL") or 0)
                peso = float(r.get("PESO_NETO") or 0)
            except ValueError:
                continue
            filas.append({
                "ruc": r.get("LIBR_TRIBU", "").strip(),
                "razon_social": r.get("DNOMBRE", "").strip(),
                "partida": str(r.get("PART_NANDI", "")).strip().zfill(10),
                "partida4": p4,
                "familia": PARTIDAS[p4],
                "rubro": RUBRO[p4],
                "uso_dual": p4 == "3102",
                "fob_usd": fob,
                "peso_kg": peso,
                "pais_origen": r.get("PAIS_ORIGE", "").strip(),
                "descripcion": r.get("DESC_COMER", "").strip()[:70],
            })
    return pd.DataFrame(filas), total


def procesar_export(zip_path):
    campos = {"DNOMBRE", "CPAIDES", "PART_NANDI", "VFOBSERDOL", "VPESNET",
              "NDOC", "DCOM"}
    fh, nombre = abrir(zip_path)
    filas = []
    total = 0
    with fh:
        for r in leer_dbf(fh, campos):
            total += 1
            try:
                fob = float(r.get("VFOBSERDOL") or 0)
                peso = float(r.get("VPESNET") or 0)
            except ValueError:
                continue
            filas.append({
                "ruc": r.get("NDOC", "").strip(),
                "razon_social": r.get("DNOMBRE", "").strip(),
                "partida": str(r.get("PART_NANDI", "")).strip().zfill(10),
                "partida4": partida4(r.get("PART_NANDI", "")),
                "fob_usd": fob,
                "peso_kg": peso,
                "pais_destino": r.get("CPAIDES", "").strip(),
            })
    return pd.DataFrame(filas), total


def semana_de(nombre):
    """ma06120726 -> the week's start date, from the ddDDmmyy filename code."""
    m = re.search(r"(\d{2})(\d{2})(\d{2})(\d{2})", nombre)
    if not m:
        return nombre
    d1, d2, mes, anio = m.groups()
    return f"20{anio}-{mes}-{d1}"


def main():
    import glob
    imps, exps = [], []
    for z in sorted(glob.glob("data/aduanas/ma*.zip")):
        d, n = procesar_import(z)
        d["semana"] = semana_de(os.path.basename(z))
        imps.append(d)
        print(f"  {os.path.basename(z):20s} {n:>9,} lineas -> {len(d):>6,} agro",
              flush=True)
    for z in sorted(glob.glob("data/aduanas/x*.zip")):
        d, n = procesar_export(z)
        d["semana"] = semana_de(os.path.basename(z))
        exps.append(d)

    imp = pd.concat(imps, ignore_index=True)
    exp = pd.concat(exps, ignore_index=True)
    imp.to_csv("out/aduanas_importaciones.csv", index=False,
               encoding="utf-8-sig")

    semanas = imp["semana"].nunique()
    print()
    print("=" * 80)
    print(f"IMPORTACION DE INSUMOS AGRICOLAS  ·  {semanas} semanas")
    print("=" * 80)
    res = (imp.groupby("rubro")
           .agg(lineas=("ruc", "size"), empresas=("ruc", "nunique"),
                fob=("fob_usd", "sum"),
                tn=("peso_kg", lambda s: s.sum() / 1000)))
    res["fob_semanal"] = res["fob"] / semanas
    res["anualizado"] = res["fob_semanal"] * 52
    print(res.to_string(float_format=lambda v: f"{v:,.0f}"))
    print()
    print(f"total periodo   : US$ {imp.fob_usd.sum()/1e6:,.1f} MM en {semanas} semanas")
    print(f"anualizado      : US$ {imp.fob_usd.sum()/semanas*52/1e6:,.0f} MM CIF")
    print(f"empresas unicas : {imp.ruc.nunique():,}")

    # The competitive map: who brings crop inputs into the country.
    top = (imp.groupby(["ruc", "razon_social"])
           .agg(fob=("fob_usd", "sum"), tn=("peso_kg", lambda s: s.sum() / 1000),
                semanas=("semana", "nunique"), lineas=("partida", "size"),
                rubro=("rubro", lambda s: s.mode().iat[0]))
           .sort_values("fob", ascending=False).reset_index())
    top["pct"] = 100 * top["fob"] / top["fob"].sum()
    top["pct_acum"] = top["pct"].cumsum()
    top.to_csv("out/aduanas_importadores.csv", index=False,
               encoding="utf-8-sig")

    dual = imp[imp.uso_dual]
    print()
    print(f"de los cuales, partida 3102 (nitrogenados): "
          f"US$ {dual.fob_usd.sum()/1e6:,.0f} MM. El nitrato de amonio de esta")
    print("partida sirve como fertilizante y como base de explosivos de mineria;")
    print("empresas como Orica, Famesa o Exsa aparecen por ese uso, no por el agro.")
    print()
    print("--- LOS 20 MAYORES IMPORTADORES ---")
    v = top.head(20)[["razon_social", "rubro", "fob", "tn", "semanas", "pct_acum"]]
    v.columns = ["razon social", "rubro", "FOB US$", "toneladas", "sem", "% acum"]
    print(v.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
    print()
    n10 = (top["pct_acum"] <= 50).sum() + 1
    print(f"concentracion: {n10} empresas explican el 50% de la importacion")
    print(f"              las 20 mayores, el {top.pct_acum.iloc[19]:.0f}%")

    # Where it comes from
    print()
    print("--- ORIGEN ---")
    o = (imp.groupby("pais_origen")
         .agg(fob=("fob_usd", "sum"), tn=("peso_kg", lambda s: s.sum() / 1000))
         .sort_values("fob", ascending=False).head(8))
    o["pct"] = 100 * o["fob"] / imp.fob_usd.sum()
    print(o.to_string(float_format=lambda v: f"{v:,.0f}"))

    # Agro exports, for the client side
    exp.to_csv("out/aduanas_exportaciones.csv", index=False,
               encoding="utf-8-sig")
    AGRO_EXP = {"07", "08", "09", "12", "18", "20", "21"}
    ea = exp[exp["partida4"].str[:2].isin(AGRO_EXP)]
    tope = (ea.groupby("ruc")
            .agg(razon_social=("razon_social", lambda s: s.mode().iat[0]),
                 fob=("fob_usd", "sum"),
                 tn=("peso_kg", lambda s: s.sum() / 1000),
                 semanas=("semana", "nunique"),
                 destinos=("pais_destino", "nunique"))
            .sort_values("fob", ascending=False).reset_index())
    tope = tope[tope["ruc"].str.len() == 11]
    tope.to_csv("out/aduanas_agroexportadores.csv", index=False,
                encoding="utf-8-sig")
    print()
    print("--- AGROEXPORTADORES (capitulos 07,08,09,12,18,20,21) ---")
    print(f"empresas: {len(tope):,}  ·  FOB periodo: "
          f"US$ {ea.fob_usd.sum()/1e6:,.0f} MM  ·  "
          f"anualizado US$ {ea.fob_usd.sum()/semanas*52/1e6:,.0f} MM")
    w = tope.head(14)[["razon_social", "fob", "tn", "semanas", "destinos"]]
    w.columns = ["razon social", "FOB US$", "toneladas", "sem", "paises"]
    print(w.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    main()
