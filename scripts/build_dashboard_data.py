# -*- coding: utf-8 -*-
"""Empaqueta los datos del dashboard web.

Cada vista carga su propio archivo, no un único paquete: el directorio de
empresas pesa varias veces más que el resto junto, y quien entra a ver el
resumen no debería esperar por él.

El directorio es la vista que un equipo comercial usa a diario, así que se
optimiza para búsqueda: campos cortos, nombres de clave de una letra y un
índice de texto ya normalizado —sin tildes ni mayúsculas— para que filtrar
sobre veinte mil filas no requiera recorrerlas transformándolas.
"""
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

OUT = "out/dashboard"
os.makedirs(OUT, exist_ok=True)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def cap(s):
    return " ".join(w.capitalize() for w in str(s).split())


def guardar(nombre, obj):
    p = os.path.join(OUT, nombre)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"), ensure_ascii=False)
    print(f"  {nombre:26s} {os.path.getsize(p)/1024:>8,.0f} KB")


# ------------------------------------------------------------- resumen ----
mod = pd.read_csv("out/modelo_v3_departamento.csv", encoding="utf-8-sig")
cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")
emb = pd.read_csv("out/embudo_departamento.csv", encoding="utf-8-sig")
som = pd.read_csv("out/som_escenarios.csv", encoding="utf-8-sig")
est_n = pd.read_csv("out/estacionalidad_nacional.csv", encoding="utf-8-sig")
est_r = pd.read_csv("out/estacionalidad_region.csv", encoding="utf-8-sig")
rut = pd.read_csv("out/ruteo_departamento.csv", encoding="utf-8-sig")
ter = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
hub = pd.read_csv("out/hubs_cobertura.csv", encoding="utf-8-sig")

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct",
         "Nov", "Dic"]

resumen = {
    "kpi": {
        "tam": int(mod.tam_usd.sum()),
        "sam": int(mod.sam_usd.sum()),
        "clientes": int(mod.clientes_sam.sum()),
        "productores": int(cen.productores.sum()),
        "sobre5ha": int(cen.ua_objetivo_5_mas.sum()),
        "credito": int(emb.compran_a_credito.sum()),
        "ha_cosechada": int(mod.ha_cosechada.sum()),
        "gasto_ha": int(round(mod.tam_usd.sum() / mod.ha_cosechada.sum())),
        "ticket": int(round(mod.sam_usd.sum() / mod.clientes_sam.sum())),
        "territorios": int(len(ter)),
        "territorios_dia": int(ter.visitable_en_dia.sum()),
    },
    "embudo": [
        {"n": "Productores agropecuarios", "v": int(cen.productores.sum())},
        {"n": "Unidades de más de 5 ha", "v": int(cen.ua_objetivo_5_mas.sum())},
        {"n": "Ya compran insumos", "v": int(emb.compradores_insumos.sum())},
        {"n": "Ya compran a crédito", "v": int(emb.compran_a_credito.sum())},
    ],
    "regiones": [{
        "n": cap(r["dep"]), "rank": int(r["rank_v3"]),
        "sam": int(r["sam_usd"]), "cli": int(r["clientes_sam"]),
        "gasto": int(round(r["gasto_ha"])),
        "ticket": int(round(r["ticket_anual"])),
        "ha": int(r["ha_cosechada"]),
        "acc": round(float(r["pct_bajo_2h"]), 1),
        "horas": round(float(r["horas_capital"]), 1),
        "pico": r["mes_pico"], "top4": round(float(r["pct_top4"])),
        "arq": r["arquetipo"], "score": round(float(r["score_v3"]), 1),
        "credito": round(float(r["tasa_credito"]) * 100, 1),
        "fert": round(float(r["tasa_fert"]) * 100, 1),
    } for _, r in mod.sort_values("rank_v3").iterrows()],
    "som": [{"e": r["escenario"], "pen": float(r["penetracion"]),
             "cli": int(r["clientes"]), "ventas": float(r["ventas_usd"]),
             "margen": float(r["margen_usd"])} for _, r in som.iterrows()],
    "curva": [{"m": r["mes"], "v": float(r["demanda"]),
               "pct": round(float(r["pct"]), 1)}
              for _, r in est_n.set_index("mes").reindex(MESES).reset_index().iterrows()],
    "hubs": [{"k": int(r["k"]), "u": int(r["umbral_h"]), "hub": r["hub"],
              "region": r["region"], "pct": round(float(r["pct_sam"]), 1),
              "marg": round(float(r["marginal"]), 1)}
             for _, r in hub.iterrows()],
}
guardar("resumen.json", resumen)

# --------------------------------------------------------- estacionalidad -
est_r = est_r.merge(mod[["dep"]].assign(k=mod["dep"].map(norm)),
                    left_on="k", right_on="k", how="left")
cal = []
for _, r in est_r.sort_values("total", ascending=False).iterrows():
    tot = float(r["total"]) or 1
    cal.append({
        "n": cap(r["dep"]) if pd.notna(r.get("dep")) else cap(r["k"]),
        "tot": float(r["total"]),
        "pico": r["mes_pico"], "top4": round(float(r["pct_top4"])),
        "m": [round(100 * float(r[m]) / tot, 1) for m in MESES],
    })
guardar("estacionalidad.json", {"meses": MESES, "regiones": cal})

# ------------------------------------------------------------ territorios -
guardar("territorios.json", [{
    "rank": int(r["rank"]), "dep": cap(r["dep"]), "prov": r["provincias"],
    "sam": int(r["sam_usd"]), "cli": int(r["clientes"]),
    "ha": int(r["ha_agricola"]), "celdas": int(r["celdas"]),
    "ext": int(round(r["extension_km"])), "dia": bool(r["visitable_en_dia"]),
    "emp": int(r["empresas"]), "exp": int(r["exportadores"]),
    "lat": round(float(r["lat"]), 4), "lon": round(float(r["lon"]), 4),
    "horas": round(float(r["horas_capital"]), 1),
} for _, r in ter.iterrows()])

# --------------------------------------------------------------- empresas -
emp = pd.read_csv("out/empresas_agro_activas.csv", encoding="utf-8-sig",
                  dtype={"ruc": str, "ubigeo": str})
expo = pd.read_csv("out/comercio_exportadores.csv", encoding="utf-8-sig",
                   dtype={"ruc": str})
impo = pd.read_csv("out/comercio_importadores.csv", encoding="utf-8-sig",
                   dtype={"ruc": str})

# El FOB de comercio exterior es el dato que distingue a un cliente grande de
# uno cualquiera, así que se une al directorio en lugar de vivir aparte.
fob_exp = dict(zip(expo["ruc"], expo["fob_anual"]))
fob_imp = dict(zip(impo["ruc"], impo["fob_anual"]))
rubro_imp = dict(zip(impo["ruc"], impo["rubro"]))

CLASE = {"productor": "P", "agroindustria": "A", "canal": "C",
         "proveedor": "V", "agro_otro": "O"}

filas = []
vistos = set()
for _, r in emp.iterrows():
    ruc = r["ruc"]
    vistos.add(ruc)
    filas.append({
        "r": ruc, "n": r["razon_social"][:70],
        "c": CLASE.get(r["clase"], "O"),
        "d": cap(r["dep"]) if pd.notna(r.get("dep")) else "",
        "p": cap(r["provincia"]) if pd.notna(r.get("provincia")) else "",
        "t": cap(r["distrito"]) if pd.notna(r.get("distrito")) else "",
        "x": int(fob_exp.get(ruc, 0)),
        "i": int(fob_imp.get(ruc, 0)),
    })

# Exportadores e importadores que no figuran en el directorio agro: no llevan
# "agro" en la razón social —Camposol o Danper, por ejemplo— pero son los
# clientes y competidores más relevantes del mercado.
for df, campo, clase in ((expo, "x", "E"), (impo, "i", "I")):
    for _, r in df.iterrows():
        if r["ruc"] in vistos:
            continue
        vistos.add(r["ruc"])
        filas.append({
            "r": r["ruc"], "n": str(r["razon_social"])[:70], "c": clase,
            "d": cap(r["dep"]) if pd.notna(r.get("dep")) else "",
            "p": cap(r["provincia"]) if pd.notna(r.get("provincia")) else "",
            "t": cap(r["distrito"]) if pd.notna(r.get("distrito")) else "",
            "x": int(r["fob_anual"]) if campo == "x" else 0,
            "i": int(r["fob_anual"]) if campo == "i" else 0,
        })

d = pd.DataFrame(filas)
d = d.sort_values(["x", "i", "n"], ascending=[False, False, True])

# Formato de tuplas y catálogos: veintidós mil objetos con claves repetidas
# pesan más del doble que las mismas filas como listas, y region, provincia y
# distrito se repiten miles de veces cada uno. El índice de búsqueda se arma
# en el navegador, que es donde se usa.
def catalogo(col):
    vals = sorted(x for x in d[col].unique() if x)
    return vals, {v: i for i, v in enumerate(vals)}


deps, i_dep = catalogo("d")
provs, i_prov = catalogo("p")
dists, i_dist = catalogo("t")
CL = ["P", "A", "C", "V", "O", "E", "I"]
i_cl = {c: i for i, c in enumerate(CL)}

filas_t = [[
    r["r"], r["n"], i_cl.get(r["c"], 4),
    i_dep.get(r["d"], -1), i_prov.get(r["p"], -1), i_dist.get(r["t"], -1),
    int(round(r["x"] / 1000)), int(round(r["i"] / 1000)),   # FOB en miles
] for _, r in d.iterrows()]

guardar("empresas.json", {
    "campos": ["ruc", "nombre", "clase", "dep", "prov", "dist",
               "fob_exp_mil", "fob_imp_mil"],
    "clases": ["Productor", "Agroindustria", "Canal", "Proveedor",
               "Otro agro", "Agroexportador", "Importador de insumos"],
    "deps": deps, "provs": provs, "dists": dists,
    "filas": filas_t,
})

print()
print(f"empresas en el directorio : {len(d):,}")
print(f"  con FOB de exportacion  : {(d.x > 0).sum():,}")
print(f"  con FOB de importacion  : {(d.i > 0).sum():,}")
print(f"  ubicadas                : {(d.d != '').sum():,}")
