# -*- coding: utf-8 -*-
"""Archiva las semanas de aduanas para construir el histórico que SUNAT no da.

SUNAT publica los manifiestos bajo la Ley 27806, pero mantiene una **ventana
móvil de unas diez semanas**: lo que hoy está, en tres meses no está. Todo el
análisis de comercio exterior de la plataforma vive de esa ventana, y por eso
el eje anual tiene un solo año y el mensual tres meses. La única manera de
tener histórico es bajarlo antes de que se caiga y guardarlo.

Este script es esa memoria. Se puede correr todas las semanas sin pensar: mira
qué hay en el archivo, calcula qué semanas faltan y baja solo esas.

No consulta la página índice. Está detrás de un 403 y ademas obligaba a
guardarla a mano, que es justo lo que impide correr esto sin un humano
delante. Los nombres son deducibles: la semana va de lunes a domingo y el
archivo se llama `ma{dia_inicial}{dia_final}{mes_final}{año}.zip` —`ma` para
importación, `x` para exportación—. Se generan y se pide cada uno; el 404 es
la respuesta de que esa semana ya no está publicada.

Y deducirlos destapó algo que cambia el alcance del proyecto: **la ventana
móvil es solo del índice**. Los archivos siguen en el servidor mucho después de
dejar de estar listados. Se probaron diecinueve semanas de 2022 a 2026, una por
trimestre, y las diecinueve responden con el ZIP completo; la de febrero de
2022 trae 189,580 registros con el mismo esquema de campos que la de la semana
pasada. El histórico que parecía imposible se baja de la fuente primaria.

Sobre el mes del nombre: es el del ÚLTIMO día. `ma29050726` es la semana del
29 de junio al 5 de julio y no la del 29 de julio, cosa que se verificó contra
las fechas de los propios registros. Una de cada cuatro semanas cruza el
cambio de mes, así que leerlo mal desplazaba esas semanas un mes entero.

Uso:
    python scripts/acumular_aduanas.py              # baja lo que falte
    python scripts/acumular_aduanas.py --desde 2026-06-01
    python scripts/acumular_aduanas.py --sembrar    # adopta lo ya bajado
"""
import argparse
import datetime as dt
import glob
import hashlib
import io
import json
import os
import shutil
import sys
import time
import zipfile

import requests

BASE = "http://www.aduanet.gob.pe/aduanas/informae/"
UA = {"User-Agent": "Mozilla/5.0"}
ARCHIVO = "data/aduanas_hist"
MANIFIESTO = os.path.join(ARCHIVO, "manifiesto.json")
SEMILLA = "data/aduanas"          # lo que ya bajaron las corridas anteriores
PRIMERA = dt.date(2026, 6, 15)    # la semana más vieja que llegamos a ver

# line_buffering: la corrida historica dura horas y sin esto el avance no se
# ve hasta el final, que es cuando ya no sirve para nada.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def lunes(d):
    return d - dt.timedelta(days=d.weekday())


def nombres(inicio):
    """Los dos archivos de la semana que abre en `inicio` (un lunes)."""
    fin = inicio + dt.timedelta(days=6)
    cod = f"{inicio.day:02d}{fin.day:02d}{fin.month:02d}{fin.year % 100:02d}"
    return {"importacion": f"ma{cod}.zip", "exportacion": f"x{cod}.zip"}


def sha(path, bloque=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(bloque), b""):
            h.update(b)
    return h.hexdigest()


def zip_sano(path):
    try:
        return bool(zipfile.ZipFile(path).namelist())
    except Exception:
        return False


def cargar():
    if os.path.exists(MANIFIESTO):
        with io.open(MANIFIESTO, encoding="utf-8") as fh:
            return json.load(fh)
    return {"semanas": {}, "actualizado": None}


def guardar(man):
    man["actualizado"] = dt.datetime.now().isoformat(timespec="seconds")
    with io.open(MANIFIESTO, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False, sort_keys=True)


def registrar(man, semana, tipo, nombre, path, origen):
    e = man["semanas"].setdefault(semana, {})
    nuevo = sha(path)
    viejo = e.get(tipo, {}).get("sha256")
    if viejo and viejo != nuevo:
        # SUNAT republicó la semana. Se anota el cambio en vez de taparlo: una
        # cifra que se movió sin aviso es la clase de cosa que después nadie
        # puede explicar.
        e.setdefault("republicados", []).append(
            {"tipo": tipo, "sha_anterior": viejo,
             "visto": dt.date.today().isoformat()})
        print(f"      OJO: {nombre} cambió respecto de lo archivado")
    e[tipo] = {"archivo": nombre, "bytes": os.path.getsize(path),
               "sha256": nuevo, "origen": origen,
               "bajado": dt.date.today().isoformat()}


def bajar(nombre, dest, intentos=5):
    url = BASE + nombre
    try:
        r = requests.head(url, headers=UA, timeout=45)
        if r.status_code == 404:
            return "ausente"
        esperado = int(r.headers.get("content-length", 0))
    except requests.RequestException:
        esperado = 0
    tmp = dest + ".parcial"
    for n in range(1, intentos + 1):
        try:
            with requests.get(url, headers=UA, stream=True,
                              timeout=(60, 300)) as r:
                if r.status_code == 404:
                    return "ausente"
                with open(tmp, "wb") as fh:
                    for c in r.iter_content(1 << 20):
                        fh.write(c)
        except requests.RequestException as ex:
            print(f"      intento {n}: {type(ex).__name__}")
            time.sleep(4 * n)
            continue
        ok = zip_sano(tmp) and (not esperado or os.path.getsize(tmp) == esperado)
        if ok:
            os.replace(tmp, dest)
            return "bajado"
        print(f"      intento {n}: incompleto "
              f"({os.path.getsize(tmp):,}/{esperado:,})")
        time.sleep(4 * n)
    if os.path.exists(tmp):
        os.remove(tmp)
    return "fallo"


def sembrar(man):
    """Adopta lo que corridas anteriores ya dejaron en data/aduanas."""
    n = 0
    for p in sorted(glob.glob(os.path.join(SEMILLA, "*.zip"))):
        nombre = os.path.basename(p)
        if not zip_sano(p):
            continue
        tipo = "importacion" if nombre.lower().startswith("ma") else (
            "exportacion" if nombre.lower().startswith("x") else None)
        if not tipo:
            continue
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from build_aduanas import semana_de
        sem = semana_de(nombre)
        dest = os.path.join(ARCHIVO, nombre)
        if not os.path.exists(dest):
            shutil.copy2(p, dest)
        registrar(man, sem, tipo, nombre, dest, "sembrado")
        n += 1
    print(f"sembrado: {n} archivos adoptados de {SEMILLA}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=PRIMERA.isoformat())
    ap.add_argument("--sembrar", action="store_true")
    ap.add_argument("--solo", choices=["importacion", "exportacion"],
                    help="baja un solo tipo; util para reconstruir historico")
    a = ap.parse_args()

    os.makedirs(ARCHIVO, exist_ok=True)
    man = cargar()
    if a.sembrar:
        sembrar(man)
        guardar(man)

    desde = lunes(dt.date.fromisoformat(a.desde))
    # La última semana completa: la actual todavía no cerró.
    hasta = lunes(dt.date.today()) - dt.timedelta(days=7)
    print(f"\nrevisando semanas del {desde} al {hasta}")

    nuevas = ausentes = ya = 0
    d = desde
    while d <= hasta:
        sem = d.isoformat()
        e = man["semanas"].get(sem, {})
        pend = []
        for tipo, nombre in nombres(d).items():
            if a.solo and tipo != a.solo:
                continue
            reg = e.get(tipo)
            dest = os.path.join(ARCHIVO, nombre)
            if reg and os.path.exists(dest) and os.path.getsize(dest) == reg["bytes"]:
                ya += 1
                continue
            pend.append((tipo, nombre, dest))
        if pend:
            print(f"  {sem}")
            for tipo, nombre, dest in pend:
                r = bajar(nombre, dest)
                if r == "bajado":
                    registrar(man, sem, tipo, nombre, dest, "aduanet")
                    print(f"      {nombre}  {os.path.getsize(dest):,} bytes")
                    nuevas += 1
                elif r == "ausente":
                    man["semanas"].setdefault(sem, {}).setdefault(
                        "ausentes", {})[tipo] = dt.date.today().isoformat()
                    print(f"      {nombre}  ya no publicado")
                    ausentes += 1
            guardar(man)
        d += dt.timedelta(days=7)

    guardar(man)
    con = {s: v for s, v in man["semanas"].items() if v.get("importacion")}
    print(f"\narchivo historico en {ARCHIVO}/")
    print(f"  semanas con importacion : {len(con)}")
    if con:
        k = sorted(con)
        print(f"  cobertura               : {k[0]} .. {k[-1]}")
        meses = sorted({s[:7] for s in con})
        print(f"  meses                   : {len(meses)}  {meses}")
        print(f"  anos                    : {sorted({s[:4] for s in con})}")
    peso = sum(os.path.getsize(p) for p in glob.glob(os.path.join(ARCHIVO, "*.zip")))
    print(f"  peso                    : {peso/1e6:,.0f} MB")
    print(f"  en esta corrida         : {nuevas} nuevas, {ya} ya estaban, "
          f"{ausentes} ya no publicadas")


if __name__ == "__main__":
    main()
