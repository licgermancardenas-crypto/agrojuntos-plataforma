# -*- coding: utf-8 -*-
"""Qué capítulos arancelarios deja fuera el universo agro, y cuánto valen.

Nuestro total de 2025 queda 12% por debajo del oficial de MIDAGRI. Las otras
dos explicaciones ya se midieron y se descartaron: anclar en la fecha de
regularización en vez del embarque mueve 83 MM, y las republicaciones ya se
depuran. Queda el universo: este proyecto cuenta como agro siete capítulos
—07, 08, 09, 12, 18, 20 y 21— y la estadística oficial cuenta más.

Esto lo mide recorriendo **todos** los archivos de exportación, no solo los de
un año. Ese recorte fue el error de un primer intento: los embarques de 2025
aparecen también en archivos de 2026 y de finales de 2024 —SUNAT republica—,
así que leer solo las semanas de 2025 perdía cuatro quintas partes del valor y
el resultado no reproducía ni el universo conocido.

Se deduplica como el pipeline, por serie y quedándose con la última versión,
y solo se guardan en memoria las series de los capítulos que interesan.

Uso:
    python scripts/diag_universo.py
"""
import datetime as dt
import glob
import io
import json
import os
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, "scripts")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
from build_aduanas import leer_dbf                            # noqa: E402

NUESTROS = {"07", "08", "09", "12", "18", "20", "21"}
AGRARIOS = {
    "01": "animales vivos", "02": "carne", "04": "lácteos y miel",
    "05": "productos de origen animal", "06": "plantas vivas y flores",
    "10": "cereales (quinua, kiwicha)", "11": "molinería",
    "13": "gomas y resinas (tara)", "14": "materias trenzables",
    "15": "grasas y aceites", "16": "preparaciones de carne",
    "17": "azúcares", "19": "preparaciones de cereales",
    "22": "bebidas (pisco, vino)", "23": "alimento para animales",
    "24": "tabaco", "33": "aceites esenciales", "52": "algodón",
    "53": "otras fibras vegetales",
}
INTERESAN = NUESTROS | set(AGRARIOS)
ANIOS = {"2022", "2023", "2024", "2025", "2026"}
SALIDA = "out/diag_universo.json"
# Lo que da el pipeline para los mismos años y capítulos. Si esto no cuadra,
# el resto del diagnóstico tampoco vale: es el control.
CONTROL = {"2022": "8,392", "2023": "8,880", "2024": "10,918",
           "2025": "13,169", "2026": "6,452"}


def fin_de(nombre):
    """La fecha del último día de la semana, que es la que lleva el nombre."""
    n = os.path.basename(nombre).lstrip("x").split(".")[0]
    try:
        return dt.date(2000 + int(n[6:8]), int(n[4:6]), int(n[2:4]))
    except Exception:
        return None


def main():
    archivos = sorted((f for f in glob.glob("data/aduanas_hist/x*.zip")
                       if fin_de(f)), key=fin_de)
    print("archivos de exportación: %d  (%s .. %s)"
          % (len(archivos), fin_de(archivos[0]), fin_de(archivos[-1])))

    # clave de serie -> (capítulo, año, fob). Se sobrescribe: gana la última
    # versión publicada, que es la vigente.
    serie = {}
    leidas = 0
    for i, z in enumerate(archivos, 1):
        try:
            zf = zipfile.ZipFile(z)
            with zf.open(zf.namelist()[0]) as fh:
                for r in leer_dbf(fh, None):
                    # El campo llega sin el cero inicial en los capítulos
                    # 01-09: la uva viene como 806100000 y no 0806100000. Sin
                    # rellenar, `[:2]` da «80» y se pierden frutas, hortalizas
                    # y café, que son el grueso del agro. El pipeline hace
                    # este zfill desde el principio; este diagnóstico no, y
                    # por eso sus dos primeras corridas no reproducían ni el
                    # universo conocido.
                    p = (r.get("PART_NANDI") or "").strip().zfill(10)
                    cap = p[:2]
                    if cap not in INTERESAN:
                        continue
                    f = (r.get("FEMB") or "").strip()
                    if f[:4] not in ANIOS:
                        continue
                    try:
                        v = float(r.get("VFOBSERDOL") or 0)
                    except ValueError:
                        continue
                    k = "%s-%s-%s-%s" % (r.get("CADU", ""), r.get("FANO", ""),
                                         r.get("NDCL", ""), r.get("NSER", ""))
                    serie[k] = (cap, f[:4], v)
                    leidas += 1
        except Exception as e:
            print("  %s: %s" % (os.path.basename(z), e))
        if i % 25 == 0:
            print("  %d/%d · %s series" % (i, len(archivos), format(len(serie), ",")))

    por = defaultdict(float)
    for cap, anio, v in serie.values():
        por[(cap, anio)] += v
    print("\nseries únicas: %s  (de %s líneas leídas)"
          % (format(len(serie), ","), format(leidas, ",")))

    filas = []
    for anio in sorted(ANIOS):
        nuestro = sum(v for (c, a), v in por.items() if a == anio and c in NUESTROS)
        fuera = {c: v for (c, a), v in por.items()
                 if a == anio and c in AGRARIOS and v > 5e5}
        filas.append({"anio": anio, "nuestro": nuestro,
                      "fuera": dict(sorted(fuera.items(), key=lambda x: -x[1]))})

    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(filas, fh, ensure_ascii=False, indent=1)

    for f in filas:
        if not f["nuestro"]:
            continue
        print("\n%s · nuestros siete capítulos: US$ %s MM"
              % (f["anio"], format(round(f["nuestro"] / 1e6), ",")))
        tot = 0
        for c, v in list(f["fuera"].items())[:8]:
            print("   fuera · cap %s  %7.0f MM   %s" % (c, v / 1e6, AGRARIOS[c]))
            tot += v
        tot += sum(list(f["fuera"].values())[8:])
        print("   fuera, en total: US$ %s MM   ·   con ellos sumaría US$ %s MM"
              % (format(round(tot / 1e6), ","),
                 format(round((f["nuestro"] + tot) / 1e6), ",")))


if __name__ == "__main__":
    main()
