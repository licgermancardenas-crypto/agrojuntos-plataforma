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


def clave(s):
    """Union entre tablas que escriben el departamento de distinta forma.

    build_estacionalidad emite `lalibertad`; norm() produce `la libertad`.
    Quitar los espacios es lo unico que hace falta para que casen, y es lo que
    faltaba: en la vista de estacionalidad se leia `Lalibertad`.
    """
    return norm(s).replace(" ", "")


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
est_r = est_r.merge(mod[["dep"]].assign(k=mod["dep"].map(clave)),
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


# ===================================================================== #
#  Las tres capas que hasta ahora solo existían en el PDF.               #
#  Un informe se lee una vez; el sitio se consulta. Todo lo que sirve     #
#  para decidir tiene que estar en línea, no en un archivo adjunto.       #
# ===================================================================== #

per = pd.read_csv("out/perfil_departamento.csv", encoding="utf-8-sig")
log = pd.read_csv("out/logistica_departamento.csv", encoding="utf-8-sig")
pue = pd.read_csv("out/puertos.csv", encoding="utf-8-sig")
imp_l = pd.read_csv("out/aduanas_importaciones.csv", encoding="utf-8-sig",
                    dtype={"ruc": str})
exp_l = pd.read_csv("out/aduanas_exportaciones.csv", encoding="utf-8-sig",
                    dtype={"ruc": str, "partida4": str})

# El archivo de aduanas trae la exportacion completa del pais: el mineral de
# cobre (2603) y el oro (7108) son por si solos el 60% del FOB. Sin este filtro
# la pagina anunciaria US$ 33,813 MM de agroexportacion en diez semanas, mas
# que todo lo que el Peru exporta en un ano. Capitulos 07, 08, 09, 12, 18, 20
# y 21, los mismos que usa build_aduanas.py.
AGRO_EXP = {"07", "08", "09", "12", "18", "20", "21"}
exp_l = exp_l[exp_l["partida4"].str.zfill(4).str[:2].isin(AGRO_EXP)]


def num(v, dec=1):
    """None en vez de NaN: JSON no admite NaN y el navegador sí admite null."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, dec) if np.isfinite(v) else None


# ---------------------------------------------------------- departamentos -
# Una ficha por departamento con lo que hace falta antes de entrar a una
# región: cuánto vale, quién compra, cuándo compra y cuánto cuesta llegar.
per_k = per.set_index(per["dep"].map(norm))
log_k = log.set_index(log["dep"].map(norm))
rut_k = rut.set_index(rut["dep"].map(norm))
est_k = est_r.set_index("k")
CLAVE_EST = clave
ter_dep = ter.assign(kk=ter["dep"].map(norm)).groupby("kk")

expo_k = expo.assign(kk=expo["dep"].map(lambda v: norm(v) if pd.notna(v) else ""))
impo_k = impo.assign(kk=impo["dep"].map(lambda v: norm(v) if pd.notna(v) else ""))
expo_g = expo_k.groupby("kk").agg(n=("ruc", "size"), fob=("fob_anual", "sum"))
impo_g = impo_k.groupby("kk").agg(n=("ruc", "size"), fob=("fob_anual", "sum"))

deps_ficha = []
for _, r in mod.sort_values("rank_v3").iterrows():
    k = norm(r["dep"])
    p = per_k.loc[k] if k in per_k.index else None
    lg = log_k.loc[k] if k in log_k.index else None
    ru = rut_k.loc[k] if k in rut_k.index else None
    ke = CLAVE_EST(r["dep"])
    e = est_k.loc[ke] if ke in est_k.index else None
    tot = float(e["total"]) if e is not None and float(e["total"]) else 1.0
    tt = ter_dep.get_group(k) if k in ter_dep.groups else None

    deps_ficha.append({
        "n": cap(r["dep"]), "k": k,
        "rank": int(r["rank_v3"]), "score": num(r["score_v3"]),
        "arq": r["arquetipo"],
        "reg": (str(p["region_nat"]) if p is not None else ""),
        # mercado
        "tam": int(r["tam_usd"]), "sam": int(r["sam_usd"]),
        "cli": int(r["clientes_sam"]), "ticket": int(round(r["ticket_anual"])),
        "pct_sam": num(r["pct_sam_v3"], 2),
        # tierra
        "ha": int(r["ha_cosechada"]),
        "ha_agri": int(p["ha_agricola"]) if p is not None else None,
        "sectores": int(p["sectores"]) if p is not None else None,
        "gasto": int(round(r["gasto_ha"])),
        "cultivos": int(r["n_cultivos"]),
        # productores
        "prod": int(r["productores"]),
        "sobre5": int(r["ua_objetivo_5_mas"]),
        "compran": int(r["compradores_insumos"]),
        "credito": int(r["compran_a_credito"]),
        "estratos": ([int(p["ua_micro_0_5"]), int(p["ua_pequeno_5_20"]),
                      int(p["ua_mediano_20_100"]), int(p["ua_grande_100_mas"])]
                     if p is not None else None),
        "t_fert": num(float(r["tasa_fert"]) * 100),
        "t_cred": num(float(r["tasa_credito"]) * 100),
        # logistica
        "horas": num(ru["horas_real"]) if ru is not None else None,
        "horas_proxy": num(ru["horas_proxy"]) if ru is not None else None,
        "bajo2": num(r["pct_bajo_2h"]),
        "sobre4": num(r["pct_sobre_4h"]),
        "puerto": (str(lg["puerto"]) if lg is not None
                   and pd.notna(lg["puerto"]) else None),
        "h_puerto": num(ru["puerto_real"]) if ru is not None else None,
        "sin_puerto": num(ru["pct_sin_puerto"]) if ru is not None else None,
        "costo": num(r["costo_viaje"]),
        # demanda
        "mes": r["mes_pico"], "top4": num(r["pct_top4"], 0),
        "meses": ([num(100 * float(e[m]) / tot) for m in MESES]
                  if e is not None else None),
        # tejido empresarial
        "emp": int(p["prospectos"]) if p is not None else None,
        "exp_n": int(expo_g["n"].get(k, 0)),
        "exp_fob": int(expo_g["fob"].get(k, 0)),
        "imp_n": int(impo_g["n"].get(k, 0)),
        "imp_fob": int(impo_g["fob"].get(k, 0)),
        # territorios
        "terr": int(len(tt)) if tt is not None else 0,
        "terr_dia": int(tt["visitable_en_dia"].sum()) if tt is not None else 0,
    })
guardar("departamentos.json", {"meses": MESES, "deps": deps_ficha})

# -------------------------------------------------------------- logistica -
# El ruteo real corrige al proxy en un sentido que cambia decisiones: hay
# departamentos que la línea recta daba por perdidos y la carretera rescata.
guardar("logistica.json", {
    "deps": [{
        "n": cap(r["dep"]),
        "real": num(r["horas_real"]), "proxy": num(r["horas_proxy"]),
        "dif": num(r["dif"]),
        "puerto": num(r["puerto_real"]),
        "sin_puerto": num(r["pct_sin_puerto"]),
        "bajo2": num(r["pct_bajo_2h"]), "sobre4": num(r["pct_sobre_4h"]),
        "costo": num(r["costo_viaje"]),
        "sam": int(r["sam"]),
    } for _, r in rut.sort_values("sam", ascending=False).iterrows()],
    "puertos": [{
        "n": str(r["puerto"]), "reg": cap(r["region"]), "tipo": str(r["tipo"]),
        "rel": str(r["relevancia_agro"]),
        "lat": num(r["lat"], 4), "lon": num(r["lon"], 4),
    } for _, r in pue.iterrows()],
})

# --------------------------------------------------------------- comercio -
# Las importaciones son la validación externa del modelo: si el mercado
# estimado no guarda proporción con lo que entra por aduanas, el modelo está
# mal. Las exportaciones dicen quién tiene con qué pagar.
def agrupar(df, campo, n=None):
    g = (df.groupby(campo).agg({"fob_usd": "sum", "peso_kg": "sum"})
           .sort_values("fob_usd", ascending=False).reset_index())
    if n:
        g = g.head(n)
    return [{"n": str(r[campo]), "fob": int(r["fob_usd"]),
             "tn": int(round(r["peso_kg"] / 1000))} for _, r in g.iterrows()]


guardar("comercio.json", {
    "meta": {
        "semanas_imp": int(imp_l["semana"].nunique()),
        "semanas_exp": int(exp_l["semana"].nunique()),
        "fob_imp": int(imp_l["fob_usd"].sum()),
        "fob_exp": int(exp_l["fob_usd"].sum()),
        "n_imp": int(imp_l["ruc"].nunique()),
        "n_exp": int(exp_l["ruc"].nunique()),
    },
    "rubros": agrupar(imp_l, "rubro"),
    "familias": agrupar(imp_l, "familia"),
    "origenes": agrupar(imp_l, "pais_origen", 20),
    "destinos": agrupar(exp_l, "pais_destino", 20),
    "importadores": [{
        "r": str(r["ruc"]), "n": str(r["razon_social"])[:60],
        "rubro": str(r["rubro"]), "fob": int(r["fob_anual"]),
        "tn": int(round(r["tn"])), "pct": num(r["pct"], 2),
        "dep": cap(r["dep"]) if pd.notna(r.get("dep")) else "",
    } for _, r in impo.sort_values("fob_anual", ascending=False)
        .head(100).iterrows()],
    "exportadores": [{
        "r": str(r["ruc"]), "n": str(r["razon_social"])[:60],
        "fob": int(r["fob_anual"]), "tn": int(round(r["tn"])),
        "dest": int(r["destinos"]),
        "dep": cap(r["dep"]) if pd.notna(r.get("dep")) else "",
    } for _, r in expo.sort_values("fob_anual", ascending=False)
        .head(100).iterrows()],
})
