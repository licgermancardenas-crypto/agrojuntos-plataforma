# -*- coding: utf-8 -*-
"""Paso 4 · Consolida los microdatos de aduanas y aísla las empresas de insumos.

Los archivos de SUNAT son dBase III. No hay lector de DBF instalado y pip no
tiene salida a la red en este entorno, así que el formato se parsea aquí
directamente y en streaming: un solo archivo de importación ocupa 263 MB
descomprimido y no conviene cargarlo entero en memoria.

Doble filtro, como se pidió:

  por partida    3102 3103 3104 3105 fertilizantes
                 3808                agroquímicos y plaguicidas
                 1209                semillas para siembra
                 3101 2510           añadidos: abono orgánico y fosfato
                                     natural, que son fertilizante y quedaban
                                     fuera de la lista original

  por texto      sobre la descripción comercial declarada, para recuperar
                 despachos mal clasificados en la partida

Advertencia que queda registrada en la salida: la partida 3102 incluye nitrato
de amonio, insumo tanto de fertilizante como de explosivos de minería. Orica,
Famesa o Exsa aparecen por ese segundo uso. El campo `uso_dual` los marca para
que puedan excluirse del análisis competitivo agrícola.
"""
import glob
import io
import json
import os
import re
import struct
import sys
import zipfile

import pandas as pd

RAW = "raw_data/sunat"
OUT = "processed_data"
SEMANAS_ANIO = 52

PARTIDAS = {
    "3101": ("Fertilizantes", "Abono organico"),
    "3102": ("Fertilizantes", "Fertilizante nitrogenado"),
    "3103": ("Fertilizantes", "Fertilizante fosfatado"),
    "3104": ("Fertilizantes", "Fertilizante potasico"),
    "3105": ("Fertilizantes", "Fertilizante compuesto"),
    "2510": ("Fertilizantes", "Fosfato natural"),
    "3808": ("Agroquimicos", "Proteccion de cultivos"),
    "1209": ("Semillas", "Semilla para siembra"),
}

RE_TEXTO = re.compile(
    r"fertilizan|abono|urea|nitrato de amonio|sulfato de amonio|fosfato dia|"
    r"cloruro de potasio|insecticid|fungicid|herbicid|acaricid|nematicid|"
    r"plaguicid|pesticid|semilla para siembra|semillas para siembra|"
    r"bioestimulante|coadyuvante", re.I)

# Capítulos del arancel cuya exportación es agrícola.
CAP_AGRO_EXPORT = {"06", "07", "08", "09", "10", "12", "18", "20", "21"}


def log(m):
    print(m, flush=True)


# ----------------------------------------------------------------- DBF ----
def leer_dbf(fh, campos=None):
    """Recorre un dBase III y entrega dicts. Solo decodifica `campos`."""
    cab = fh.read(32)
    if len(cab) < 32:
        return
    n_reg = struct.unpack("<I", cab[4:8])[0]
    len_cab = struct.unpack("<H", cab[8:10])[0]
    len_reg = struct.unpack("<H", cab[10:12])[0]

    # La cabecera se lee de una vez: buscar el terminador 0x0D leyendo de a 32
    # bytes lo sobrepasa en 31 y desalinea silenciosamente todos los registros.
    resto = fh.read(len_cab - 32)
    defs, pos = [], 1                    # el byte 0 del registro es la marca de borrado
    for off in range(0, len(resto) - 31, 32):
        d = resto[off:off + 32]
        if d[0] == 0x0D:
            break
        nombre = d[:11].split(bytes([0]))[0].decode("latin-1").strip()
        defs.append((nombre, pos, d[16]))
        pos += d[16]

    quer = [c for c in defs if campos is None or c[0] in campos]
    for _ in range(n_reg):
        raw = fh.read(len_reg)
        if len(raw) < len_reg or raw[:1] == b"*":
            continue
        yield {n: raw[p:p + l].decode("latin-1").strip() for n, p, l in quer}


def abrir_zip(path):
    zf = zipfile.ZipFile(path)
    return zf.open(zf.namelist()[0])


def partida4(v):
    p = re.sub(r"\D", "", str(v))
    return p.zfill(10)[:4] if p else ""


def num(v):
    try:
        return float(str(v).strip() or 0)
    except ValueError:
        return 0.0


def semana(nombre):
    m = re.search(r"(\d{2})(\d{2})(\d{2})(\d{2})", nombre)
    if not m:
        return nombre
    d1, _d2, mes, anio = m.groups()
    return f"20{anio}-{mes}-{d1}"


# ------------------------------------------------------------ extracción --
def leer_importaciones():
    campos = {"LIBR_TRIBU", "DNOMBRE", "PART_NANDI", "FOB_DOLPOL",
              "PESO_NETO", "PAIS_ORIGE", "DESC_COMER"}
    filas, leidas = [], 0
    for z in sorted(glob.glob(os.path.join(RAW, "ma*.zip"))):
        sem, n = semana(os.path.basename(z)), 0
        with abrir_zip(z) as fh:
            for r in leer_dbf(fh, campos):
                leidas += 1
                p4 = partida4(r.get("PART_NANDI"))
                desc = r.get("DESC_COMER", "")
                por_partida = p4 in PARTIDAS
                por_texto = bool(RE_TEXTO.search(desc))
                if not (por_partida or por_texto):
                    continue
                rubro, familia = PARTIDAS.get(p4, ("Otro", "Detectado por texto"))
                filas.append({
                    "ruc": r.get("LIBR_TRIBU", "").strip(),
                    "razon_social": r.get("DNOMBRE", "").strip(),
                    "partida": partida4(r.get("PART_NANDI")),
                    "rubro": rubro, "familia": familia,
                    "criterio": "partida" if por_partida else "texto",
                    "uso_dual": p4 == "3102",
                    "fob_usd": num(r.get("FOB_DOLPOL")),
                    "peso_kg": num(r.get("PESO_NETO")),
                    "pais_origen": r.get("PAIS_ORIGE", "").strip(),
                    "descripcion": desc[:80],
                    "semana": sem,
                })
                n += 1
        log(f"  {os.path.basename(z):18s} -> {n:>6,} lineas de insumos")
    return pd.DataFrame(filas), leidas


def leer_exportaciones():
    campos = {"NDOC", "DNOMBRE", "PART_NANDI", "VFOBSERDOL", "VPESNET",
              "CPAIDES", "DCOM"}
    filas, leidas = [], 0
    for z in sorted(glob.glob(os.path.join(RAW, "x*.zip"))):
        sem = semana(os.path.basename(z))
        with abrir_zip(z) as fh:
            for r in leer_dbf(fh, campos):
                leidas += 1
                p4 = partida4(r.get("PART_NANDI"))
                filas.append({
                    "ruc": r.get("NDOC", "").strip(),
                    "razon_social": r.get("DNOMBRE", "").strip(),
                    "partida": p4, "capitulo": p4[:2],
                    "fob_usd": num(r.get("VFOBSERDOL")),
                    "peso_kg": num(r.get("VPESNET")),
                    "pais_destino": r.get("CPAIDES", "").strip(),
                    "descripcion": r.get("DCOM", "")[:80],
                    "semana": sem,
                })
        log(f"  {os.path.basename(z):18s} -> {len(filas):>6,} acumuladas")
    return pd.DataFrame(filas), leidas


# ------------------------------------------------------------- limpieza ---
SUFIJOS = re.compile(
    r"\s*(S\.?A\.?C\.?|S\.?A\.?A\.?|S\.?A\.?|S\.?R\.?L\.?|E\.?I\.?R\.?L\.?|"
    r"SOCIEDAD ANONIMA CERRADA|SOCIEDAD ANONIMA|SOCIEDAD COMERCIAL DE "
    r"RESPONSABILIDAD LIMITADA|EMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA)"
    r"\s*$", re.I)


def limpiar_nombre(s):
    s = re.sub(r"\s+", " ", str(s)).strip().upper()
    previo = None
    while previo != s:                  # razones sociales con doble sufijo
        previo = s
        s = SUFIJOS.sub("", s).strip(" .,-")
    return s or str(s)


def consolidar(df, campo_pais):
    """Una fila por empresa, con FOB y peso sumados."""
    df = df[df["ruc"].str.len() == 11].copy()
    df["nombre_limpio"] = df["razon_social"].map(limpiar_nombre)
    g = (df.groupby("ruc")
         .agg(razon_social=("razon_social", lambda s: s.mode().iat[0]),
              nombre_limpio=("nombre_limpio", lambda s: s.mode().iat[0]),
              fob_usd=("fob_usd", "sum"),
              peso_kg=("peso_kg", "sum"),
              operaciones=("partida", "size"),
              partidas=("partida", "nunique"),
              semanas_activo=("semana", "nunique"),
              paises=(campo_pais, "nunique"))
         .reset_index())
    g["toneladas"] = g["peso_kg"] / 1000
    g["fob_anualizado"] = g["fob_usd"] / df["semana"].nunique() * SEMANAS_ANIO
    return g.sort_values("fob_usd", ascending=False).reset_index(drop=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    if not glob.glob(os.path.join(RAW, "ma*.zip")):
        log(f"no hay archivos en {RAW}/ — correr antes 02_sunat_aduanas.py")
        return 1

    log("leyendo importaciones...")
    imp, n_imp = leer_importaciones()
    log("\nleyendo exportaciones...")
    exp, n_exp = leer_exportaciones()

    semanas = imp["semana"].nunique()
    log(f"\nlineas leidas: {n_imp:,} importacion · {n_exp:,} exportacion")
    log(f"lineas de insumos aisladas: {len(imp):,}")
    log(f"  por partida arancelaria : {(imp.criterio=='partida').sum():,}")
    log(f"  recuperadas por texto   : {(imp.criterio=='texto').sum():,}")

    # --- empresas de insumos (importadores) -------------------------------
    importadores = consolidar(imp, "pais_origen")
    rub = (imp[imp["ruc"].str.len() == 11]
           .groupby("ruc")["rubro"].agg(lambda s: s.mode().iat[0]))
    dual = imp[imp["ruc"].str.len() == 11].groupby("ruc")["uso_dual"].max()
    importadores["rubro"] = importadores["ruc"].map(rub)
    importadores["uso_dual"] = importadores["ruc"].map(dual)

    # --- agroexportadores --------------------------------------------------
    exp_agro = exp[exp["capitulo"].isin(CAP_AGRO_EXPORT)]
    exportadores = consolidar(exp_agro, "pais_destino")

    # --- salidas -----------------------------------------------------------
    # Vista limpia: sin nitrato de amonio de uso minero, que arrastra a Orica,
    # Exsa y Famesa. Es la que sirve para leer competencia agrícola.
    agro = importadores[~importadores["uso_dual"].fillna(False)].copy()
    agro = agro.reset_index(drop=True)

    tablas = {
        "importadores_insumos": importadores,
        "importadores_insumos_agro": agro,
        "agroexportadores": exportadores,
        "importaciones_detalle": imp,
    }
    for nombre, d in tablas.items():
        d.to_csv(os.path.join(OUT, f"{nombre}.csv"), index=False,
                 encoding="utf-8-sig")
        if nombre != "importaciones_detalle":       # el detalle pesa demasiado
            d.to_json(os.path.join(OUT, f"{nombre}.json"), orient="records",
                      force_ascii=False, indent=1)
        log(f"  {nombre:24s} {len(d):>7,} filas")

    meta = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "semanas_observadas": int(semanas),
        "periodo": [str(imp.semana.min()), str(imp.semana.max())],
        "lineas_importacion_leidas": int(n_imp),
        "lineas_exportacion_leidas": int(n_exp),
        "importadores_insumos": int(len(importadores)),
        "agroexportadores": int(len(exportadores)),
        "importadores_sin_uso_dual": int(len(agro)),
        "fob_insumos_periodo_usd": float(imp.fob_usd.sum()),
        "fob_insumos_anualizado_usd": float(imp.fob_usd.sum() / semanas * 52),
        "partidas_filtro": sorted(PARTIDAS),
    }
    with open(os.path.join(OUT, "_metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)

    # --- ranking en consola ------------------------------------------------
    log("\n" + "=" * 88)
    log(f"TOP 10 IMPORTADORES DE INSUMOS AGRICOLAS  ·  {semanas} semanas "
        f"({meta['periodo'][0]} a {meta['periodo'][1]})")
    log("=" * 88)
    v = importadores.head(10)[["ruc", "razon_social", "rubro", "fob_usd",
                               "toneladas", "semanas_activo"]].copy()
    v["razon_social"] = v["razon_social"].str.slice(0, 34)
    v.columns = ["RUC", "Razon social", "Rubro", "FOB US$", "Toneladas", "Sem"]
    log(v.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

    log("\n" + "=" * 88)
    log("TOP 10 IMPORTADORES, EXCLUYENDO NITRATO DE AMONIO DE USO MINERO")
    log("=" * 88)
    a = agro.head(10)[["ruc", "razon_social", "rubro", "fob_usd",
                       "toneladas", "semanas_activo"]].copy()
    a["razon_social"] = a["razon_social"].str.slice(0, 34)
    a.columns = ["RUC", "Razon social", "Rubro", "FOB US$", "Toneladas", "Sem"]
    log(a.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
    log(f"\nExcluidas {len(importadores) - len(agro)} empresas de la partida "
        "3102 (nitrato de amonio), insumo compartido con explosivos de mineria.")

    log("\n" + "=" * 88)
    log("TOP 10 AGROEXPORTADORES")
    log("=" * 88)
    w = exportadores.head(10)[["ruc", "razon_social", "fob_usd", "toneladas",
                               "paises"]].copy()
    w["razon_social"] = w["razon_social"].str.slice(0, 34)
    w.columns = ["RUC", "Razon social", "FOB US$", "Toneladas", "Paises"]
    log(w.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

    log(f"\nFOB insumos importados: US$ {imp.fob_usd.sum()/1e6:,.1f} MM en "
        f"{semanas} semanas  ·  US$ {meta['fob_insumos_anualizado_usd']/1e6:,.0f} MM "
        "anualizado")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.exit(main())
