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
import json
import os
import re
import struct
import sys
import zipfile
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universo import es_agro                                  # noqa: E402

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
    """Import format A: importer RUC and name, tariff heading, FOB, weight.

    Devuelve tambien el tamano del universo del que se recorta: cuantas
    lineas trae el archivo y cuanto FOB suman todas, agricolas o no. El sitio
    publica esas dos cifras como «toda la importacion del pais», y las traia
    escritas a mano de cuando la ventana era de diez semanas: con el historico
    acumulado quedaban veinte veces cortas y seguian anunciandose como el
    total nacional.
    """
    campos = {"LIBR_TRIBU", "DNOMBRE", "PART_NANDI", "FOB_DOLPOL",
              "PESO_NETO", "PAIS_ORIGE", "DESC_COMER"}
    fh, nombre = abrir(zip_path)
    filas = []
    total = 0
    fob_pais = 0.0
    with fh:
        for r in leer_dbf(fh, campos):
            total += 1
            try:
                fob_pais += float(r.get("FOB_DOLPOL") or 0)
            except ValueError:
                pass
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
    return pd.DataFrame(filas), total, fob_pais


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
    """ma06120726 -> la fecha en que empieza la semana, desde el codigo del
    nombre: dia inicial, dia final, mes y ano DEL DIA FINAL.

    Que el mes sea el del ultimo dia importa en las semanas que cruzan de mes,
    que son una de cada cuatro. `ma29050726` es del 29 de junio al 5 de julio,
    no del 29 de julio: se verifico contra las fechas de los propios registros,
    donde ese archivo trae 13,070 despachos de junio. Tomar el mes como el del
    primer dia adelantaba esas semanas un mes entero y las mandaba al casillero
    equivocado en cualquier agrupacion mensual.
    """
    m = re.search(r"(\d{2})(\d{2})(\d{2})(\d{2})", nombre)
    if not m:
        return nombre
    d1, d2, mes, anio = (int(x) for x in m.groups())
    y, mm = 2000 + anio, mes
    if d1 > d2:                      # la semana abre en el mes anterior
        mm -= 1
        if mm == 0:
            mm, y = 12, y - 1
    return f"{y}-{mm:02d}-{d1:02d}"


CACHE = "data/aduanas_hist/_leido"


def ventana(imp, semanas, lineas_pais, fob_pais):
    """El tamano de la ventana, medido y no escrito a mano.

    Lo lee `build_dashboard_data.py` para rotular la vista de importacion:
    cuantas semanas son, entre que fechas, y de que universo nacional se
    recorta. Estuvo escrito a mano —2,953,512 lineas y US$ 13,748 MM— de
    cuando la ventana era de diez semanas, y siguio publicandose como «toda la
    importacion del pais» despues de que el historico acumulado la
    multiplicara por veinte.

    Las semanas de exportacion salen del nombre de los archivos y no de
    leerlos: la fecha esta en el nombre y abrirlos para contarlas costaria
    veinte minutos por un numero que ya se sabe.
    """
    import glob
    sem_exp = {semana_de(os.path.basename(z))
               for z in glob.glob("data/aduanas_hist/x*.zip")}
    with io.open("out/aduanas_ventana.json", "w", encoding="utf-8") as fh:
        json.dump({
            "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "fuente": "manifiestos semanales de SUNAT acumulados por "
                      "acumular_aduanas.py; no es la ventana movil vigente "
                      "sino todo lo que se alcanzo a guardar",
            "semanas": int(semanas),
            "desde": str(imp["semana"].min()),
            "hasta": str(imp["semana"].max()),
            "lineas_pais": int(lineas_pais),
            "fob_pais": round(float(fob_pais), 2),
            "semanas_exportacion": len(sem_exp),
        }, fh, ensure_ascii=False, indent=1)


def import_cacheado(z):
    """Lo leido de un ZIP de importacion, guardado apenas se lee.

    Recorrer los 246 archivos son sesenta y ocho millones de registros y unos
    veinte minutos, y en una maquina de 3 GB el sistema apaga el proceso a
    mitad de camino por falta de memoria: la corrida siguiente volvia a
    empezar de cero y no terminaba nunca. Con el cache cada archivo se lee una
    sola vez en su vida, la corrida es reanudable y la segunda tarda segundos.

    Es la misma disciplina de `_semanas_procesadas.json` en el historico de
    exportacion, y el mismo motivo: un manifiesto ya leido no cambia.

    Se guarda tambien lo que no queda en el CSV —cuantas lineas trae el
    archivo y cuanto FOB suman todas, agricolas o no—, porque esas dos cifras
    son el universo del que se recorta y el sitio las publica.
    """
    p = os.path.join(CACHE, os.path.basename(z) + ".json")
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        return pd.DataFrame(d["filas"]), d["lineas"], d["fob"], True
    df, n, fob = procesar_import(z)
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"lineas": n, "fob": fob, "filas": df.to_dict("records")},
                  fh, ensure_ascii=False)
    os.replace(tmp, p)      # nunca un cache a medio escribir
    return df, n, fob, False


def main():
    import glob
    solo_ventana = "--solo-ventana" in sys.argv
    imps = []
    # El archivo historico y no la ventana movil: acumular_aduanas.py guarda
    # cada semana antes de que SUNAT la retire, y de ahi sale el historico.
    lineas_pais, fob_pais = 0, 0.0
    for z in sorted(glob.glob("data/aduanas_hist/ma*.zip")):
        d, n, fp, cache = import_cacheado(z)
        d["semana"] = semana_de(os.path.basename(z))
        imps.append(d)
        lineas_pais += n
        fob_pais += fp
        if not cache:
            print(f"  {os.path.basename(z):20s} {n:>9,} lineas -> "
                  f"{len(d):>6,} agro", flush=True)
    imp = pd.concat(imps, ignore_index=True)
    del imps
    imp.to_csv("out/aduanas_importaciones.csv", index=False,
               encoding="utf-8-sig")
    semanas = imp["semana"].nunique()
    ventana(imp, semanas, lineas_pais, fob_pais)
    if solo_ventana:
        # Para reanudar la parte cara sin rehacer la exportacion, que ya esta
        # escrita: `python scripts/build_aduanas.py --solo-ventana`.
        print("solo la ventana: out/aduanas_ventana.json")
        return

    # La exportacion no se acumula en memoria. Son 8.7 millones de lineas y
    # 712 MB de CSV: juntarlas en un DataFrame para escribirlas y volver a
    # recorrerlas mataba el proceso —el sistema lo apagaba por falta de
    # memoria— en cuanto el historico paso de las diez semanas a cuatro anos.
    # Cada archivo se escribe en cuanto se lee, y del agro se guarda solo el
    # acumulado por RUC, que es lo unico que sale de aqui.
    COLS_EXP = ["ruc", "razon_social", "partida", "partida4", "fob_usd",
                "peso_kg", "pais_destino", "semana"]
    RUTA_EXP = "out/aduanas_exportaciones.csv"
    agr, sem_exp, n_exp = {}, set(), 0
    primero = True
    for z in sorted(glob.glob("data/aduanas_hist/x*.zip")):
        d, _ = procesar_export(z)
        sem = semana_de(os.path.basename(z))
        d["semana"] = sem
        sem_exp.add(sem)
        d = d[COLS_EXP]
        d.to_csv(RUTA_EXP, index=False, encoding="utf-8-sig",
                 mode="w" if primero else "a", header=primero)
        primero = False
        n_exp += len(d)
        e = d[d["partida4"].map(es_agro)]
        for ruc, g in e.groupby("ruc"):
            a = agr.get(ruc)
            if a is None:
                a = agr[ruc] = {"nom": defaultdict(int), "fob": 0.0,
                                "kg": 0.0, "sem": set(), "dest": set()}
            # El nombre se decide por frecuencia sobre todo el periodo, igual
            # que el `mode()` que esto reemplaza: una empresa cambia de razon
            # social y el manifiesto trae las dos.
            for nom, c in g.razon_social.value_counts().items():
                a["nom"][nom] += int(c)
            a["fob"] += float(g.fob_usd.sum())
            a["kg"] += float(g.peso_kg.sum())
            a["sem"].add(sem)
            a["dest"].update(x for x in g.pais_destino.unique() if x)
        del d, e

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
    #
    # Por RUC y no por (RUC, razon social). Agrupar por los dos partia en dos
    # a la empresa que cambia de nombre —«CURTIDURIA EL PORVENIR S A» y
    # «CURTIDURIA EL PORVENIR SOCIEDAD ANONIMA» son el mismo 20100042763—, le
    # repartia el FOB entre las dos filas y dejaba el RUC repetido en el CSV,
    # que es lo que rompia el indice de `build_perfiles.py`. Con diez semanas
    # no pasaba nunca; con cuatro anos y medio, treinta y una veces. El nombre
    # se decide por frecuencia, igual que del lado exportador.
    top = (imp.groupby("ruc")
           .agg(razon_social=("razon_social", lambda s: s.mode().iat[0]),
                fob=("fob_usd", "sum"), tn=("peso_kg", lambda s: s.sum() / 1000),
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

    # Agro exports, for the client side. El CSV ya quedo escrito arriba, tanda
    # por tanda; aqui solo se cierra el acumulado por RUC.
    tope = pd.DataFrame([{
        "ruc": ruc,
        "razon_social": max(a["nom"].items(), key=lambda kv: kv[1])[0],
        "fob": a["fob"], "tn": a["kg"] / 1000,
        "semanas": len(a["sem"]), "destinos": len(a["dest"]),
    } for ruc, a in agr.items()]).sort_values("fob", ascending=False)
    fob_agro = float(tope.fob.sum())
    tope = tope[tope["ruc"].str.len() == 11].reset_index(drop=True)
    tope = tope[["ruc", "razon_social", "fob", "tn", "semanas", "destinos"]]
    tope.to_csv("out/aduanas_agroexportadores.csv", index=False,
                encoding="utf-8-sig")
    print()
    print(f"exportacion escrita : {n_exp:,} lineas en {len(sem_exp)} semanas")
    print("--- AGROEXPORTADORES (universo arancelario de universo.py) ---")
    print(f"empresas: {len(tope):,}  ·  FOB periodo: "
          f"US$ {fob_agro/1e6:,.0f} MM  ·  "
          f"anualizado US$ {fob_agro/semanas*52/1e6:,.0f} MM")
    w = tope.head(14)[["razon_social", "fob", "tn", "semanas", "destinos"]]
    w.columns = ["razon social", "FOB US$", "toneladas", "sem", "paises"]
    print(w.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    main()
