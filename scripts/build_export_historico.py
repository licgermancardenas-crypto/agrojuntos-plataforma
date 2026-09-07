# -*- coding: utf-8 -*-
"""Extrae, operacion por operacion, la agroexportacion peruana.

El gemelo de build_import_historico.py, del otro lado del muelle. Misma
disciplina: una fila por linea de manifiesto, con todo lo que hace falta para
auditarla, y semana por semana para poder cortar y retomar.

El archivo de exportacion no es el de importacion. Trae 44 campos en vez de 58
y los nombres cambian: el RUC es NDOC y no LIBR_TRIBU, el FOB es VFOBSERDOL y
no FOB_DOLPOL, el pais es de destino y no de origen. No hay flete ni seguro, y
esta bien que no los haya: la exportacion se declara FOB, que es exactamente lo
que el exportador cobra puesto a bordo.

Dos campos que el archivo de importacion no tiene y este si:

  DNOMPRO   el productor. En la agroexportacion peruana el que embarca no
            siempre es el que siembra, y este campo nombra a quien produjo la
            mercancia. Se guarda tal cual, sin cruzarlo con nada: es texto
            libre del declarante y no un identificador.
  UBIGEO    el ubigeo declarado, y el campo mas valioso del archivo. Una
            medicion previa sobre diez semanas de 2026 concluyo que solo el 3%
            del FOB lo trae y que no servia para ubicar nada. Es cierto de
            2026 y falso de los anos anteriores: viene lleno en el 100% del
            FOB hasta 2024 y en el 60% en 2025. SUNAT lo esta dejando de
            llenar, no siempre estuvo vacio.
            Y no es el domicilio fiscal: cruzado contra el padron sobre 2024
            coincide en el distrito el 26.6% de las veces y en el
            departamento el 48.8%, y donde el manifiesto dice Ica o La
            Libertad el padron dice Lima. Apunta al fundo. Ver
            `build_export_agregados.py`, que arma el corte territorial con el
            y se limita a los anos que lo traen.

El universo son los capitulos del arancel que el proyecto ya definio como agro
en build_aduanas.py y build_agroexport.py. Se reutilizan para que los totales
de las tres vistas cuadren entre si en vez de contar cada una lo suyo.

Uso:
    python scripts/build_export_historico.py
    python scripts/build_export_historico.py --rehacer
"""
import argparse
import csv
import datetime as dt
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_aduanas import abrir, leer_dbf, semana_de
from build_agroexport import AGRO, PARTIDAS

RAW = "data/aduanas_hist"
PROC = "data/exportaciones/processed"
OPERS = os.path.join(PROC, "operaciones.csv")
LIBRO = os.path.join(PROC, "_semanas_procesadas.json")
MANIFIESTO = os.path.join(RAW, "manifiesto.json")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

CAMPOS = {
    "CADU", "FANO", "NDCL", "NSER",                  # llave de la declaracion
    "NDOC", "TDOC", "DNOMBRE",                       # exportador
    "DNOMPRO",                                       # productor declarado
    "PART_NANDI", "DCOM", "DMER2",                   # que sale
    "VFOBSERDOL", "VPESNET", "VPESBRU",              # valor y peso
    "QUNICOM", "TUNICOM", "QUNIFIS", "TUNIFIS",      # cantidad
    "CPAIDES", "CPUEDES", "CVIATRA",                 # a donde y por donde
    "CADU", "CAGE", "UBIGEO",
    "FECH_RECEP", "FEMB", "FREG",                    # cuando
}

COLS = ["ruc", "razon_social", "productor", "fecha", "anio", "mes",
        "fecha_regularizacion", "dias_regularizacion",
        "semana_archivo", "partida", "partida4", "familia", "descripcion",
        "fob_usd", "peso_neto_kg", "peso_bruto_kg", "cantidad", "unidad",
        "cantidad_fisica", "unidad_fisica", "pais_destino", "puerto_destino",
        "via", "aduana", "agente_aduana", "ubigeo", "declaracion", "fuente",
        "archivo", "bajado"]

VIA = {"1": "Marítima", "2": "Aérea", "3": "Terrestre", "4": "Fluvial",
       "5": "Postal", "6": "Ferroviaria", "7": "Multimodal", "8": "Tubería"}


def num(v):
    try:
        return float(str(v).strip() or 0)
    except ValueError:
        return 0.0


def fecha(v):
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return None
    try:
        d = dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None
    if not (2000 <= d.year <= dt.date.today().year + 1):
        return None
    return d.isoformat()


def partida10(v):
    p = re.sub(r"\D", "", str(v or ""))
    return p.zfill(10) if p else ""


def cargar_libro():
    if os.path.exists(LIBRO):
        with io.open(LIBRO, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def bajado_de(man, nombre):
    for _, e in (man.get("semanas") or {}).items():
        for tipo in ("importacion", "exportacion"):
            if (e.get(tipo) or {}).get("archivo") == nombre:
                return e[tipo].get("bajado", "")
    return ""


def procesar(zip_path, man):
    nombre = os.path.basename(zip_path)
    sem = semana_de(nombre)
    baj = bajado_de(man, nombre)
    fh, _ = abrir(zip_path)
    filas, leidas = [], 0
    with fh:
        for r in leer_dbf(fh, CAMPOS):
            leidas += 1
            p10 = partida10(r.get("PART_NANDI"))
            if p10[:2] not in AGRO:
                continue
            p4 = p10[:4]
            # La serie se ancla en el **embarque**, que es cuando la
            # mercancia sale del pais y el unico momento con sentido economico.
            # No en la regularizacion, que llega despues y depende de tramites,
            # ni en el nombre del archivo, que es la semana en que SUNAT
            # publico. Todas las lineas traen fecha de embarque; se guardan
            # ademas la de regularizacion y los dias entre una y otra, que es
            # lo que permite saber cuanto de un mes reciente falta todavia.
            emb = fecha(r.get("FEMB"))
            reg = fecha(r.get("FREG"))
            f = emb or fecha(r.get("FECH_RECEP")) or reg or sem
            dias = ""
            if emb and reg:
                dias = (dt.date.fromisoformat(reg)
                        - dt.date.fromisoformat(emb)).days
            decl = "-".join([
                (r.get("CADU") or "").strip(),
                (r.get("FANO") or "").strip(),
                (r.get("NDCL") or "").strip(),
                (r.get("NSER") or "").strip()])
            via = (r.get("CVIATRA") or "").strip()
            filas.append({
                "ruc": (r.get("NDOC") or "").strip(),
                "razon_social": (r.get("DNOMBRE") or "").strip(),
                "productor": (r.get("DNOMPRO") or "").strip(),
                "fecha": f, "anio": f[:4], "mes": f[5:7],
                "fecha_regularizacion": reg or "",
                "dias_regularizacion": dias,
                "semana_archivo": sem,
                "partida": p10, "partida4": p4,
                "familia": PARTIDAS.get(p4, "Partida " + p4),
                "descripcion": (r.get("DCOM") or r.get("DMER2") or "").strip(),
                "fob_usd": round(num(r.get("VFOBSERDOL")), 2),
                "peso_neto_kg": round(num(r.get("VPESNET")), 2),
                "peso_bruto_kg": round(num(r.get("VPESBRU")), 2),
                "cantidad": round(num(r.get("QUNICOM")), 2),
                "unidad": (r.get("TUNICOM") or "").strip(),
                "cantidad_fisica": round(num(r.get("QUNIFIS")), 2),
                "unidad_fisica": (r.get("TUNIFIS") or "").strip(),
                "pais_destino": (r.get("CPAIDES") or "").strip(),
                "puerto_destino": (r.get("CPUEDES") or "").strip(),
                "via": VIA.get(via, via),
                "aduana": (r.get("CADU") or "").strip(),
                "agente_aduana": (r.get("CAGE") or "").strip(),
                "ubigeo": (r.get("UBIGEO") or "").strip(),
                "declaracion": decl,
                "fuente": "SUNAT/Aduanas microdatos (Ley 27806)",
                "archivo": nombre, "bajado": baj,
            })
    return sem, filas, leidas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rehacer", action="store_true")
    a = ap.parse_args()

    os.makedirs(PROC, exist_ok=True)
    man = {}
    if os.path.exists(MANIFIESTO):
        with io.open(MANIFIESTO, encoding="utf-8") as fh:
            man = json.load(fh)

    libro = {} if a.rehacer else cargar_libro()
    if a.rehacer and os.path.exists(OPERS):
        os.remove(OPERS)

    zips = sorted(glob.glob(os.path.join(RAW, "x*.zip")))
    print("archivos en el crudo: %d · ya procesados: %d" % (len(zips),
                                                            len(libro)))
    nuevo = 0
    for z in zips:
        nombre = os.path.basename(z)
        marca = "%s:%d" % (nombre, os.path.getsize(z))
        if libro.get(nombre) == marca:
            continue
        sem, filas, leidas = procesar(z, man)
        escribir_cab = not os.path.exists(OPERS)
        with io.open(OPERS, "a", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            if escribir_cab:
                w.writeheader()
            w.writerows(filas)
        libro[nombre] = marca
        with io.open(LIBRO, "w", encoding="utf-8") as fh:
            json.dump(libro, fh, indent=1, sort_keys=True)
        nuevo += 1
        print("  %s  %-18s %8s lineas -> %6s de agro"
              % (sem, nombre, format(leidas, ","), format(len(filas), ",")))

    print("\nsemanas nuevas procesadas: %d" % nuevo)
    if os.path.exists(OPERS):
        import pandas as pd
        d = pd.read_csv(OPERS, encoding="utf-8-sig",
                        dtype={"ruc": str, "anio": str}, low_memory=False)
        print("operaciones acumuladas : %s" % format(len(d), ","))
        print("  empresas con RUC     : %s" % format(d.ruc.nunique(), ","))
        print("  FOB total            : US$ %.1f MM" % (d.fob_usd.sum() / 1e6))
        print("  rango de fechas      : %s .. %s" % (d.fecha.min(),
                                                     d.fecha.max()))
        print("  por ano              : %s"
              % d.groupby("anio").fob_usd.sum().div(1e6).round(1).to_dict())


if __name__ == "__main__":
    main()
