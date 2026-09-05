# -*- coding: utf-8 -*-
"""Extrae, operación por operación, la importación de insumos agrícolas.

De cada manifiesto semanal saca solo las líneas de insumo —unas 200 de las
190,000 que trae el archivo— y las guarda con todo lo que hace falta para
auditarlas: de qué archivo salieron, cuándo se bajó, qué declaración las
ampara y qué decía el declarante.

Trabaja semana por semana y lleva un registro de lo ya hecho, de modo que se
puede cortar y retomar. Importa porque son cinco años de archivos y la máquina
que corre esto tiene 3.4 GB de memoria: cargar todo junto no es una opción, y
tampoco hace falta.

Sobre las fechas. El nombre del archivo dice la semana, pero cada registro trae
sus propias fechas —recepción, llegada, embarque— y esas son las que mandan:
una declaración recibida el 30 de junio aparece en el archivo de la semana que
cierra en julio, y contarla como de julio corre el mes entero. Se usa
FECH_RECEP, que es la fecha en que la aduana recibe la declaración, y se deja
constancia de la semana del archivo para poder rastrear el origen.

Sobre el CIF. No viene como campo, pero sí sus tres componentes: el valor FOB,
el flete y el seguro. CIF = FOB + flete + seguro, que es la definición, no una
estimación.

Sobre el proveedor internacional. **No está en este archivo.** Hay país de
origen, país de adquisición y agente de aduana local, pero el exportador del
otro lado no se publica. Se deja la columna vacía en vez de rellenarla con el
agente, que es otra cosa.

Uso:
    python scripts/build_import_historico.py
    python scripts/build_import_historico.py --rehacer
"""
import argparse
import datetime as dt
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_aduanas import abrir, leer_dbf, semana_de

RAW = "data/aduanas_hist"
PROC = "data/importaciones/processed"
OPERS = os.path.join(PROC, "operaciones.csv")
LIBRO = os.path.join(PROC, "_semanas_procesadas.json")
MANIFIESTO = os.path.join(RAW, "manifiesto.json")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

# El universo de la subcategoria: que partidas cuentan como insumo agricola.
# Se define por arancel y no por palabras, porque la partida es la unica
# clasificacion con autoridad. La categoria comercial fina se decide despues,
# en build_import_clasificar.py, bajando a subpartida.
PARTIDAS = {
    "3101": "Fertilizante organico",
    "3102": "Fertilizante nitrogenado",
    "3103": "Fertilizante fosfatado",
    "3104": "Fertilizante potasico",
    "3105": "Fertilizante compuesto y foliar",
    "3808": "Proteccion de cultivos",
    "1209": "Semilla para siembra",
    "0601": "Bulbos y tuberculos para plantar",
    "0602": "Plantines y plantas vivas",
}

# Fuera del universo, con la razon a la vista:
#
#   3402  agentes de superficie. Se incluyo pensando en adyuvantes agricolas y
#         resulto ser jabon: de sus US$ 134 MM en treinta y seis semanas, lo
#         que mas pesa es «BASE DETERGENTE», «DETERGENTE EN POLVO PARA LAVAR
#         ROPA» y «ARIEL». El adyuvante agricola comparte partida con el
#         detergente domestico y no hay forma de separarlos por arancel, asi
#         que entra entero o no entra. No entra.
FUERA = {
    "3402": ("Agentes de superficie",
             "Dominada por detergente domestico e industrial; el adyuvante "
             "agricola no se separa por arancel"),
}

CAMPOS = {
    "CODI_ADUAN", "ANO_PRESE", "NUME_CORRE", "NUME_SERIE",   # llave declaracion
    "LIBR_TRIBU", "DNOMBRE",                                  # importador
    "PART_NANDI", "DESC_COMER", "DESC_MATCO", "DESC_USOAP",   # que es
    "FOB_DOLPOL", "FLE_DOLAR", "SEG_DOLAR",                   # valor
    "PESO_NETO", "PESO_BRUTO", "QUNICOM", "TUNICOM",          # cantidad
    "PAIS_ORIGE", "PAIS_ADQUI", "PUER_EMBAR",                 # de donde
    "FECH_RECEP", "FECH_LLEGA", "FECH_EMBAR",                 # cuando
    "CODI_AGENT",                                             # agente local
}

COLS = ["ruc", "razon_social", "fecha", "anio", "mes", "semana_archivo",
        "partida", "partida4", "familia", "descripcion", "desc_materia",
        "desc_uso", "fob_usd", "flete_usd", "seguro_usd", "cif_usd",
        "peso_neto_kg", "peso_bruto_kg", "cantidad", "unidad",
        "pais_origen", "pais_adquisicion", "puerto_embarque", "aduana",
        "agente_aduana", "declaracion", "fuente", "archivo", "bajado"]


def num(v):
    try:
        return float(str(v).strip() or 0)
    except ValueError:
        return 0.0


def fecha(v):
    """AAAAMMDD numerico -> ISO. Devuelve None si no es una fecha creible."""
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
            fam = PARTIDAS.get(p10[:4])
            if not fam:
                continue
            f = fecha(r.get("FECH_RECEP")) or fecha(r.get("FECH_LLEGA")) or sem
            fob = num(r.get("FOB_DOLPOL"))
            fle = num(r.get("FLE_DOLAR"))
            seg = num(r.get("SEG_DOLAR"))
            decl = "-".join([
                (r.get("CODI_ADUAN") or "").strip(),
                (r.get("ANO_PRESE") or "").strip(),
                (r.get("NUME_CORRE") or "").strip(),
                (r.get("NUME_SERIE") or "").strip()])
            filas.append({
                "ruc": (r.get("LIBR_TRIBU") or "").strip(),
                "razon_social": (r.get("DNOMBRE") or "").strip(),
                "fecha": f, "anio": f[:4], "mes": f[5:7],
                "semana_archivo": sem,
                "partida": p10, "partida4": p10[:4], "familia": fam,
                "descripcion": (r.get("DESC_COMER") or "").strip(),
                "desc_materia": (r.get("DESC_MATCO") or "").strip(),
                "desc_uso": (r.get("DESC_USOAP") or "").strip(),
                "fob_usd": round(fob, 2), "flete_usd": round(fle, 2),
                "seguro_usd": round(seg, 2),
                "cif_usd": round(fob + fle + seg, 2),
                "peso_neto_kg": round(num(r.get("PESO_NETO")), 2),
                "peso_bruto_kg": round(num(r.get("PESO_BRUTO")), 2),
                "cantidad": round(num(r.get("QUNICOM")), 2),
                "unidad": (r.get("TUNICOM") or "").strip(),
                "pais_origen": (r.get("PAIS_ORIGE") or "").strip(),
                "pais_adquisicion": (r.get("PAIS_ADQUI") or "").strip(),
                "puerto_embarque": (r.get("PUER_EMBAR") or "").strip(),
                "aduana": (r.get("CODI_ADUAN") or "").strip(),
                "agente_aduana": (r.get("CODI_AGENT") or "").strip(),
                "declaracion": decl,
                "fuente": "SUNAT/Aduanas microdatos (Ley 27806)",
                "archivo": nombre, "bajado": baj,
            })
    return sem, filas, leidas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rehacer", action="store_true",
                    help="reprocesa todo desde cero")
    a = ap.parse_args()

    os.makedirs(PROC, exist_ok=True)
    man = {}
    if os.path.exists(MANIFIESTO):
        with io.open(MANIFIESTO, encoding="utf-8") as fh:
            man = json.load(fh)

    libro = {} if a.rehacer else cargar_libro()
    if a.rehacer and os.path.exists(OPERS):
        os.remove(OPERS)

    zips = sorted(glob.glob(os.path.join(RAW, "ma*.zip")))
    print(f"archivos en el crudo: {len(zips)} · ya procesados: {len(libro)}")
    nuevo = 0
    import csv
    for z in zips:
        nombre = os.path.basename(z)
        marca = f"{nombre}:{os.path.getsize(z)}"
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
        print(f"  {sem}  {nombre:<18} {leidas:>8,} lineas -> "
              f"{len(filas):>5,} de insumo")

    print(f"\nsemanas nuevas procesadas: {nuevo}")
    if os.path.exists(OPERS):
        import pandas as pd
        d = pd.read_csv(OPERS, encoding="utf-8-sig", dtype={"ruc": str},
                        low_memory=False)
        print(f"operaciones acumuladas : {len(d):,}")
        print(f"  empresas con RUC     : {d.ruc.nunique():,}")
        print(f"  FOB total            : US$ {d.fob_usd.sum()/1e6:,.1f} MM")
        print(f"  rango de fechas      : {d.fecha.min()} .. {d.fecha.max()}")
        print(f"  por ano              : "
              f"{d.groupby('anio').fob_usd.sum().div(1e6).round(1).to_dict()}")


if __name__ == "__main__":
    main()
