# -*- coding: utf-8 -*-
"""Importación agrícola del Perú, repartida en categorías comerciales.

build_aduanas.py mira solo fertilizante y fitosanitario, que es lo que
AgroJuntos vende hoy. Alrededor de eso hay un mercado de equipo, semilla,
riego, poscosecha y alimento balanceado que sale del mismo manifiesto y que
nadie había contado.

La partida de cuatro dígitos no alcanza para separarlo. Dos ejemplos que
cambian el resultado por orden de magnitud:

  8701  junta el tractor agrícola (8701.9x, US$ 21 MM) con el tractocamión de
        carretera (8701.2x, US$ 137 MM), que no es agro por ningún lado.
  3002  junta la vacuna humana con la veterinaria; solo 3002.42 es veterinaria.

Por eso las reglas se escriben a la longitud que cada caso necesita —cuatro,
seis u ocho dígitos— y gana el prefijo más largo que calce.

Lo que queda fuera, y por qué
-----------------------------
Hay gasto agrícola real que el arancel no permite aislar, y se prefiere no
contarlo antes que inflar la cifra con supuestos:

  8413  bombas: la de riego y la de una refinería comparten subpartida
  8481  válvulas, 8482 rodamientos, 7318 tornillería: genéricos de industria
  3917  manguera y tubería plástica: la cinta de goteo no se distingue del
        resto de la manguera
  8207  útiles intercambiables: dominados por barras de perforación de minería

Tampoco están «servicios agrícolas» ni «venta de campos»: no son mercancía,
no cruzan una aduana y no existen en este registro. Se declaran en cero para
que la ausencia se vea, en vez de desaparecer de la tabla.

Uso:
    python scripts/build_import_categorias.py
"""
import glob
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_aduanas import abrir, leer_dbf, semana_de

# El archivo historico, que crece cada vez que corre acumular_aduanas.py.
CRUDOS = "data/aduanas_hist"

CATS = [
    ("semillas", "Semillas y plantines"),
    ("maquinaria", "Maquinaria y equipos"),
    ("riego", "Riego y tecnología"),
    ("poscosecha", "Molienda y poscosecha"),
    ("ganaderia", "Ganadería y alimentos balanceados"),
    ("repuestos", "Repuestos y ferretería"),
    ("servicios", "Servicios agrícolas"),
    ("campos", "Venta de campos"),
]

# prefijo NANDINA -> (categoria, glosa). Gana el prefijo más largo.
REGLAS = {
    # --------------------------------------------------- semillas y plantines
    "1209": ("semillas", "Semilla para siembra"),
    "0601": ("semillas", "Bulbos y tubérculos para plantar"),
    "0602": ("semillas", "Plantines y plantas vivas"),
    "100510": ("semillas", "Semilla de maíz"),
    "070110": ("semillas", "Papa para siembra"),
    # ------------------------------------------------------ maquinaria agrícola
    "8432": ("maquinaria", "Preparación de suelo y siembra"),
    "8433": ("maquinaria", "Cosecha y corte"),
    "870191": ("maquinaria", "Tractor agrícola"),
    "870192": ("maquinaria", "Tractor agrícola"),
    "870193": ("maquinaria", "Tractor agrícola"),
    "870194": ("maquinaria", "Tractor agrícola"),
    "870195": ("maquinaria", "Tractor agrícola"),
    "843680": ("maquinaria", "Otra maquinaria hortícola"),
    # ------------------------------------------------------- riego y aspersión
    "842441": ("riego", "Pulverizador agrícola portátil"),
    "842449": ("riego", "Pulverizador agrícola autopropulsado"),
    "842482": ("riego", "Sistema de riego y aparatos agrícolas"),
    # -------------------------------------------------- molienda y poscosecha
    "8437": ("poscosecha", "Molienda y selección de grano"),
    "8438": ("poscosecha", "Maquinaria para industria alimentaria"),
    "843360": ("poscosecha", "Pesado y envasado de producto"),
    # ------------------------------- ganadería, sanidad y alimento balanceado
    "2301": ("ganaderia", "Harina de carne, hueso y pescado"),
    "2302": ("ganaderia", "Salvados y residuos de molienda"),
    "2303": ("ganaderia", "Residuos de almidón y remolacha"),
    "2304": ("ganaderia", "Torta de soya"),
    "2305": ("ganaderia", "Torta de maní"),
    "2306": ("ganaderia", "Otras tortas oleaginosas"),
    "2308": ("ganaderia", "Otros residuos vegetales forrajeros"),
    "230990": ("ganaderia", "Preparaciones para alimentación animal"),
    "100590": ("ganaderia", "Maíz amarillo duro en grano"),
    "1214": ("ganaderia", "Forraje: alfalfa y similares"),
    "8434": ("ganaderia", "Ordeño y lechería"),
    "8436": ("ganaderia", "Avicultura, apicultura y ganadería"),
    "300242": ("ganaderia", "Vacuna veterinaria"),
    "0102": ("ganaderia", "Bovinos vivos"),
    "0103": ("ganaderia", "Porcinos vivos"),
    "0104": ("ganaderia", "Ovinos y caprinos vivos"),
    "0105": ("ganaderia", "Aves vivas: pollito BB y pavo"),
    "0106": ("ganaderia", "Otros animales vivos"),
    # --------------------------------------------- repuestos y ferretería agro
    "8201": ("repuestos", "Herramienta de mano agrícola"),
    "843290": ("repuestos", "Partes de maquinaria de suelo"),
    "843390": ("repuestos", "Partes de maquinaria de cosecha"),
    "843490": ("repuestos", "Partes de equipo de ordeño"),
    "843691": ("repuestos", "Partes de equipo avícola"),
    "843699": ("repuestos", "Partes de equipo ganadero"),
    "843790": ("repuestos", "Partes de molinería"),
    "843890": ("repuestos", "Partes de maquinaria alimentaria"),
}
# Los insumos que la plataforma ya media, para poder poner las cifras
# nuevas al lado de las conocidas y no leerlas en el vacío.
REFERENCIA = {
    "3101": "Fertilizante orgánico", "3102": "Fertilizante nitrogenado",
    "3103": "Fertilizante fosfatado", "3104": "Fertilizante potásico",
    "3105": "Fertilizante compuesto", "3808": "Protección de cultivos",
}

# Lo que no se puede aislar. Va como dato y no como comentario: el lector
# tiene que poder ver de que tamano es el borde de la medicion.
EXCLUIDAS = [
    ("8413", "Bombas", "La de riego y la de una refineria comparten subpartida"),
    ("8481", "Valvulas y grifos", "Genericos de industria, uso agricola indistinguible"),
    ("3917", "Manguera y tuberia plastica", "La cinta de goteo no se separa del resto"),
    ("8482", "Rodamientos", "Generico de industria"),
    ("7318", "Tornilleria", "Generico de industria"),
    ("8207", "Utiles intercambiables", "Dominados por barras de perforacion de mineria"),
    ("8431", "Partes de maquinaria pesada", "Dominadas por chancado y fajas de mineria"),
    ("230910", "Alimento para perros y gatos", "Mascota, no ganaderia"),
    ("2936", "Vitaminas", "Mezcla uso humano y animal sin separacion"),
]

LARGOS = sorted({len(k) for k in REGLAS} | {4}, reverse=True)
CAMPOS = {"LIBR_TRIBU", "DNOMBRE", "PART_NANDI", "FOB_DOLPOL", "PESO_NETO",
          "PAIS_ORIGE", "DESC_COMER"}


def clasificar(p10):
    for n in LARGOS:
        hit = REGLAS.get(p10[:n])
        if hit:
            return hit
    if p10[:4] in REFERENCIA:
        return ("referencia", REFERENCIA[p10[:4]])
    return (None, None)


PESO_FUERA = {}
filas = []
total_lineas = total_fob = 0
archivos = sorted(glob.glob(os.path.join(CRUDOS, "ma*.zip")))
if not archivos:
    sys.exit(f"no hay archivos de importacion en {CRUDOS}")
# Las semanas salen de lo que hay archivado y no de un numero escrito a
# mano: el historico crece y una constante vieja anualizaria mal.
SEMANAS = len({semana_de(os.path.basename(z)) for z in archivos})
for z in archivos:
    sem = semana_de(os.path.basename(z))
    fh, _ = abrir(z)
    with fh:
        for r in leer_dbf(fh, CAMPOS):
            p = re.sub(r"\D", "", str(r.get("PART_NANDI", "")))
            if not p:
                continue
            p = p.zfill(10)
            try:
                fob = float(r.get("FOB_DOLPOL") or 0)
                peso = float(r.get("PESO_NETO") or 0)
            except ValueError:
                continue
            total_lineas += 1
            total_fob += fob
            for pref, _, _ in EXCLUIDAS:
                if p.startswith(pref):
                    PESO_FUERA[pref] = PESO_FUERA.get(pref, 0.0) + fob
                    break
            cat, glosa = clasificar(p)
            if not cat:
                continue
            filas.append({
                "categoria": cat, "glosa": glosa, "partida": p,
                "partida6": p[:6], "partida4": p[:4],
                "ruc": (r.get("LIBR_TRIBU") or "").strip(),
                "razon_social": (r.get("DNOMBRE") or "").strip(),
                "fob_usd": fob, "peso_kg": peso, "semana": sem,
                "pais_origen": (r.get("PAIS_ORIGE") or "").strip(),
                "descripcion": (r.get("DESC_COMER") or "").strip()[:70],
            })
    print(f"  {os.path.basename(z)} leido")

d = pd.DataFrame(filas)
d.to_csv("out/import_agro_lineas.csv", index=False, encoding="utf-8-sig")

NOM = dict(CATS)


def resumir(g):
    return pd.Series({
        "fob_usd": g.fob_usd.sum(),
        "fob_anual": g.fob_usd.sum() / SEMANAS * 52,
        "toneladas": g.peso_kg.sum() / 1000,
        "empresas": g.ruc.nunique(),
        "partidas": g.partida6.nunique(),
        "lineas": len(g),
    })


agro = d[d.categoria != "referencia"]
res = agro.groupby("categoria").apply(resumir).reset_index()
# Las dos categorias sin mercancia entran en cero: la ausencia es el dato.
faltan = [c for c, _ in CATS if c not in set(res.categoria)]
if faltan:
    res = pd.concat([res, pd.DataFrame([{"categoria": c, "fob_usd": 0.0,
                                         "fob_anual": 0.0, "toneladas": 0.0,
                                         "empresas": 0, "partidas": 0,
                                         "lineas": 0} for c in faltan])])
res["nombre"] = res.categoria.map(NOM)
res["orden"] = res.categoria.map({c: i for i, (c, _) in enumerate(CATS)})
res = res.sort_values("orden").drop(columns="orden")
res.to_csv("out/import_agro_categoria.csv", index=False, encoding="utf-8-sig")

sub = (agro.groupby(["categoria", "glosa"]).apply(resumir).reset_index()
       .sort_values(["categoria", "fob_usd"], ascending=[True, False]))
sub.to_csv("out/import_agro_glosa.csv", index=False, encoding="utf-8-sig")

# El peso de lo excluido se mide contra el mismo universo, para que la
# renuncia sea verificable y no una declaracion de buena fe.
exc = pd.DataFrame([{"partida": p4, "nombre": n, "motivo": m,
                     "fob_usd": float(PESO_FUERA.get(p4, 0.0))}
                    for p4, n, m in EXCLUIDAS]).sort_values(
                        "fob_usd", ascending=False)
exc["fob_anual"] = exc.fob_usd / SEMANAS * 52
exc.to_csv("out/import_agro_excluidas.csv", index=False, encoding="utf-8-sig")

ref = d[d.categoria == "referencia"].groupby("glosa").apply(resumir).reset_index()
ref = ref.sort_values("fob_usd", ascending=False)
ref.to_csv("out/import_agro_referencia.csv", index=False, encoding="utf-8-sig")

TC = 52 / SEMANAS
_sems = sorted({semana_de(os.path.basename(z)) for z in archivos})
print(f"\nIMPORTACION AGRICOLA · {SEMANAS} semanas, "
      f"{_sems[0]} a {_sems[-1]}")
print(f"universo leido: {total_lineas:,} lineas · US$ {total_fob/1e6:,.0f} MM"
      f" (toda la importacion del pais)\n")
print(f"{'CATEGORIA':<36} {'FOB 10 SEM':>12} {'ANUALIZADO':>12} "
      f"{'TONELADAS':>11} {'EMPRESAS':>9}")
for _, r in res.iterrows():
    if r.lineas == 0:
        print(f"{r.nombre:<36} {'—':>12} {'—':>12} {'—':>11} {'—':>9}"
              "   no es mercancia")
        continue
    print(f"{r.nombre:<36} {r.fob_usd/1e6:>10,.1f} MM {r.fob_anual/1e6:>10,.0f} MM"
          f" {r.toneladas:>11,.0f} {int(r.empresas):>9,}")
t = res[res.lineas > 0]
print(f"{'TOTAL de las seis con mercancia':<36} {t.fob_usd.sum()/1e6:>10,.1f} MM"
      f" {t.fob_anual.sum()/1e6:>10,.0f} MM {t.toneladas.sum():>11,.0f}"
      f" {agro.ruc.nunique():>9,}")
print(f"\nreferencia · lo que la plataforma ya media:")
for _, r in ref.iterrows():
    print(f"  {r.glosa:<34} {r.fob_usd/1e6:>10,.1f} MM {r.fob_anual/1e6:>10,.0f} MM")
print(f"  {'suma de insumos':<34} {ref.fob_usd.sum()/1e6:>10,.1f} MM"
      f" {ref.fob_anual.sum()/1e6:>10,.0f} MM")
print("\nfuera de la medicion · el arancel no permite aislar el uso agricola:")
for _, e in exc.iterrows():
    print(f"  {e.partida:<7} {e.nombre:<30} {e.fob_usd/1e6:>8,.1f} MM"
          f"   {e.motivo}")
print(f"  {'suma fuera de la medicion':<38} {exc.fob_usd.sum()/1e6:>8,.1f} MM")
