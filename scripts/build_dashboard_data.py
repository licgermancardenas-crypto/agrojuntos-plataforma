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
import io
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universo import es_agro                                  # noqa: E402

# Se escribe directo en el sitio y no en out/, que obligaba a copiar a mano
# antes de desplegar. build_atlas_html.py ya escribia aqui, asi que la mitad
# de los datos se renovaba y la otra mitad no: el paso manual era el que
# dejaba el sitio con JSON de dos fechas distintas.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(os.path.join(RAIZ, "..", "..", "dashboard", "data"))
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
# El territorio dice dónde vender; el centro, desde dónde entregar. Sin las dos
# cosas juntas la tabla obliga a cruzar a mano con la vista de expansión.
car_ter = pd.read_csv("out/cartera_territorio.csv", encoding="utf-8-sig")
CT = car_ter.set_index("cluster")[["hub", "dentro_2h",
                                   "dentro_promesa"]].to_dict("index")
guardar("territorios.json", [{
    "rank": int(r["rank"]), "dep": cap(r["dep"]), "prov": r["provincias"],
    "sam": int(r["sam_usd"]), "cli": int(r["clientes"]),
    "ha": int(r["ha_agricola"]), "celdas": int(r["celdas"]),
    "ext": int(round(r["extension_km"])), "dia": bool(r["visitable_en_dia"]),
    "emp": int(r["empresas"]), "exp": int(r["exportadores"]),
    "lat": round(float(r["lat"]), 4), "lon": round(float(r["lon"]), 4),
    "horas": round(float(r["horas_capital"]), 1),
    "hub": CT.get(r["cluster"], {}).get("hub", "") or "",
    "d2h": int(CT.get(r["cluster"], {}).get("dentro_2h", 0) or 0),
    # La cartera que el centro alcanza dentro de la promesa vigente. La de dos
    # horas se conserva al lado: es la vara con la que se publicaron las
    # cifras anteriores y sin ella el cambio no se puede leer.
    "dpr": int(CT.get(r["cluster"], {}).get("dentro_promesa", 0) or 0),
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
# El directorio decía dónde está inscrita cada empresa, no en qué territorio
# de venta cae ni desde qué centro se la sirve. Sin eso, pasar del mapa a la
# ruta obligaba a cruzar dos vistas a mano.
car = pd.read_csv("out/cartera_empresa.csv", encoding="utf-8-sig",
                  dtype={"ruc": str})
ter_ruc = dict(zip(car["ruc"], car["territorio"]))
# El rango del territorio viaja junto a su nombre. El sitio necesita ir del
# filtro del directorio al mapa de ese territorio, y deducirlo cruzando textos
# es la misma trampa que ya rompio la ubicacion de las empresas.
rank_ter = {t: int(r) for t, r in zip(car["territorio"], car["rank"])
            if r == r and r is not None and int(r) > 0}
hub_ruc = dict(zip(car["ruc"], car["hub"].fillna("")))

# Medido, no anualizado: el directorio comparte el selector de periodo con el
# resto del sitio y no puede traer su propia unidad.
SEM_COMEX = int(expo["semanas"].max())      # la ventana movil de SUNAT
fob_exp = dict(zip(expo["ruc"], expo["fob"]))
fob_imp = dict(zip(impo["ruc"], impo["fob"]))
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
        "z": ter_ruc.get(ruc, ""),
        "h": hub_ruc.get(ruc, ""),
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
            "x": int(r["fob"]) if campo == "x" else 0,
            "i": int(r["fob"]) if campo == "i" else 0,
            "z": ter_ruc.get(r["ruc"], ""),
            "h": hub_ruc.get(r["ruc"], ""),
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
ters, i_ter = catalogo("z")
hubs, i_hub = catalogo("h")
CL = ["P", "A", "C", "V", "O", "E", "I"]
i_cl = {c: i for i, c in enumerate(CL)}

filas_t = [[
    r["r"], r["n"], i_cl.get(r["c"], 4),
    i_dep.get(r["d"], -1), i_prov.get(r["p"], -1), i_dist.get(r["t"], -1),
    int(round(r["x"] / 1000)), int(round(r["i"] / 1000)),   # FOB en miles
    i_ter.get(r["z"], -1), i_hub.get(r["h"], -1),
] for _, r in d.iterrows()]

guardar("empresas.json", {
    "campos": ["ruc", "nombre", "clase", "dep", "prov", "dist",
               "fob_exp_mil", "fob_imp_mil", "territorio", "centro"],
    "clases": ["Productor", "Agroindustria", "Canal", "Proveedor",
               "Otro agro", "Agroexportador", "Importador de insumos"],
    "deps": deps, "provs": provs, "dists": dists,
    "ters": ters, "ters_rank": [rank_ter.get(t, -1) for t in ters],
    "hubs": hubs,
    # El FOB de las filas va medido: sin las semanas, el sitio no sabria
    # a que periodo llevarlo.
    "semanas": SEM_COMEX,
    "filas": filas_t,
})

print()
print(f"empresas en el directorio : {len(d):,}")
print(f"  con FOB de exportacion  : {(d.x > 0).sum():,}")
print(f"  con FOB de importacion  : {(d.i > 0).sum():,}")
print(f"  ubicadas                : {(d.d != '').sum():,}")
# "Fuera de territorio" es una etiqueta y no un vacio: la empresa esta ubicada,
# solo que su distrito no cae en ninguno de los nucleos de venta. Se conserva
# como categoria para poder filtrarla, y por eso no se cuenta aqui.
FUERA = "Fuera de territorio"
print(f"  dentro de un territorio : {((d.z != '') & (d.z != FUERA)).sum():,}")
print(f"  con centro asignado     : {(d.h != '').sum():,}")


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
# La exportacion cruda de aduanas ya no se lee aqui. Se leia entera —712 MB,
# 8.7 millones de lineas—, se filtraba al universo agro y no se usaba en
# ninguna salida: la mitad exportadora de esta pantalla pasó a
# `exportaciones/mercado.json` y el filtro quedó huérfano. Costaba el
# archivo entero en memoria en una máquina que no lo tiene.


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
# Todo el comercio exterior viaja MEDIDO —las semanas archivadas tal cual— y
# es el sitio el que anualiza o mensualiza segun lo que el lector elija. Antes el
# FOB salia anualizado y el tonelaje medido en la misma fila, de modo que una
# tabla mezclaba dos periodos sin decirlo.
expo_g = expo_k.groupby("kk").agg(n=("ruc", "size"), fob=("fob", "sum"))
impo_g = impo_k.groupby("kk").agg(n=("ruc", "size"), fob=("fob", "sum"))

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
guardar("departamentos.json", {"meses": MESES, "semanas": SEM_COMEX,
                                "deps": deps_ficha})

# -------------------------------------------------------------- logistica -
# El ruteo real corrige al proxy en un sentido que cambia decisiones: hay
# departamentos que la línea recta daba por perdidos y la carretera rescata.
#
# Y desde que el grafo lleva pendiente, la hora medida incluye el desnivel. Se
# manda también la versión en llano —la que esta pantalla mostró hasta ahora—
# porque el cambio no es parejo: la sierra pagaba una cuarta parte de su
# tiempo de viaje sin que ninguna cifra lo dijera y la costa casi nada, así
# que toda comparación entre una región andina y una costeña estaba sesgada.
# La cifra que el README publica en su primera tabla —cuánto del mercado está a
# menos de dos horas— sale de aquí y no de una cuenta a mano: se desfasó una
# vez, al entrar la pendiente, y `verificar_datos.py` la compara en cada push.
_rs = pd.read_csv("out/ruteo_sector.csv", encoding="utf-8-sig")
_rs = _rs[np.isfinite(_rs["horas_capital_real"])]
_sam = _rs["s_sam_usd"].sum()
_b2 = 100 * _rs.loc[_rs.horas_capital_real <= 2, "s_sam_usd"].sum() / _sam
_b2l = 100 * _rs.loc[_rs.horas_capital_llano <= 2, "s_sam_usd"].sum() / _sam

_red = json.load(io.open("out/red_elegida.json", encoding="utf-8"))
guardar("red.json", _red)

guardar("logistica.json", {
    "meta": {"sam_bajo_2h": num(_b2, 1), "sam_bajo_2h_llano": num(_b2l, 1),
             "sectores_sin_grafo": int(7036 - len(_rs))},
    "deps": [{
        "n": cap(r["dep"]),
        "real": num(r["horas_real"]), "proxy": num(r["horas_proxy"]),
        "llano": num(r["horas_llano"]), "vuelta": num(r["horas_vuelta"]),
        "alt": int(round(r["alt_m"])),
        # Calculados aquí y no en el navegador: `num` redondea a un decimal y
        # una división entre dos cifras ya redondeadas convertía un +26% en un
        # +33%. La pantalla no tiene por qué rehacer una cuenta que aquí sale
        # exacta.
        "terr": num(r["horas_real"] - r["horas_llano"], 2),
        "pct_terr": num(100 * (r["horas_real"] / r["horas_llano"] - 1), 1)
        if r["horas_llano"] else None,
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


# La mitad exportadora salia de aqui —la misma ventana de diez semanas,
# anualizada— y ya no: la vista lee `exportaciones/mercado.json` y
# `exportadores_min.json`, que son cinco anos medidos y depurados de
# republicaciones. Se quitan los campos en vez de dejarlos sin leer: un
# `fob_exp` que ya nadie usa y que no coincide con lo que muestra la pantalla
# es una cifra esperando que alguien la tome por buena.
guardar("comercio.json", {
    "meta": {
        "semanas_imp": int(imp_l["semana"].nunique()),
        "fob_imp": int(imp_l["fob_usd"].sum()),
        "n_imp": int(imp_l["ruc"].nunique()),
    },
    "rubros": agrupar(imp_l, "rubro"),
    "familias": agrupar(imp_l, "familia"),
    "origenes": agrupar(imp_l, "pais_origen", 20),
    "importadores": [{
        "r": str(r["ruc"]), "n": str(r["razon_social"])[:60],
        "rubro": str(r["rubro"]), "fob": int(r["fob"]),
        "tn": num(r["tn"], 1), "pct": num(r["pct"], 2),
        "dep": cap(r["dep"]) if pd.notna(r.get("dep")) else "",
    } for _, r in impo.sort_values("fob", ascending=False)
        .head(100).iterrows()],
})


# ===================================================================== #
#  Productos: qué se cultiva, qué se exporta y por qué puerto sale.      #
#                                                                        #
#  El sitio decía cuánto vale cada región pero no qué se siembra en ella. #
#  Para vender insumos eso es la mitad de la conversación: no se le       #
#  ofrece lo mismo a un valle de arroz que a uno de palta.                #
# ===================================================================== #

cul_n = pd.read_csv("out/cultivos_nacional.csv", encoding="utf-8-sig")
cul_d = pd.read_csv("out/cultivos_departamento.csv", encoding="utf-8-sig")
ax_p = pd.read_csv("out/agroexport_producto.csv", encoding="utf-8-sig")
ax_a = pd.read_csv("out/agroexport_aduana.csv", encoding="utf-8-sig",
                   dtype={"codigo": str})
ax_d = pd.read_csv("out/agroexport_departamento.csv", encoding="utf-8-sig")
ax_dp = pd.read_csv("out/agroexport_dep_producto.csv", encoding="utf-8-sig")
ax_ap = pd.read_csv("out/agroexport_aduana_producto.csv", encoding="utf-8-sig",
                    dtype={"codigo": str})

# Derivado de lo archivado: el historico crece y una constante vieja
# anualizaria con el divisor equivocado.
SEM = int(imp_l["semana"].nunique())
ANUAL = 52 / SEM
# El universo del que se recorta la importacion agricola: cuantas lineas trae
# el manifiesto y cuanto FOB suman todas, agricolas o no. Lo mide
# build_aduanas.py sobre los mismos archivos. Estuvo escrito a mano —2,953,512
# lineas y US$ 13,748 MM— de cuando la ventana era de diez semanas, y siguio
# publicandose como «toda la importacion del pais» despues de que el historico
# acumulado la multiplicara por veinte.
VENTANA = json.load(io.open("out/aduanas_ventana.json", encoding="utf-8"))


def top_por(df, clave, n=6, etiqueta="producto", valor="fob_usd"):
    """Los n productos mayores de cada clave, ya ordenados."""
    out = {}
    for k, g in df.sort_values(valor, ascending=False).groupby(clave):
        out[k] = [{"n": r[etiqueta], "v": int(r[valor]),
                   "tn": int(round(r["kg"] / 1000))}
                  for _, r in g.head(n).iterrows()]
    return out


cult_por_dep = {}
for k, g in cul_d.sort_values("ha", ascending=False).groupby("dep"):
    cult_por_dep[k] = [{"n": r["cultivo"], "ha": int(r["ha"]),
                        "usd": int(r["usd"]), "pct": round(float(r["pct_dep"]), 1),
                        "mes": r["mes_pico"], "tipo": r["tipo"][:4]}
                       for _, r in g.head(12).iterrows()]

exp_por_dep = top_por(ax_dp, "dep")
exp_por_adu = top_por(ax_ap, "aduana")

# La mitad exportadora de esta pantalla salía de aquí —la ventana de diez
# semanas, anualizada— y ya no: la vista lee `exportaciones/mercado.json`, que
# son cinco años medidos, con las familias de cada departamento y la mezcla de
# cada aduana. Se quitan los campos en vez de dejarlos sin leer: un `fob_exp`
# que nadie usa y que no coincide con lo que muestra la pantalla es una cifra
# esperando que alguien la tome por buena.
#
# De la aduana sobrevive solo el diccionario —código, nombre y vía—, porque el
# manifiesto trae el código y el agregado también: el nombre hay que sacarlo
# de la Tabla 4 del Anexo 01 de SUNAT, y ese cruce vive aquí.
guardar("productos.json", {
    "meta": {
        "ha": int(cul_n["ha_nac"].sum()),
        "cultivos": int(len(cul_n)),
    },
    # --- lo que se cultiva -------------------------------------------------
    "cultivos": [{
        "n": r["cultivo"], "ha": int(r["ha_nac"]), "usd": int(r["usd_nac"]),
        "usdha": int(r["usd_ha"]), "deps": int(r["deps"]),
        "lider": r["dep_lider"], "pct": round(float(r["pct_lider"]), 1),
    } for _, r in cul_n.sort_values("ha_nac", ascending=False).head(60).iterrows()],
    "cult_dep": cult_por_dep,
    # --- cómo se llama cada aduana -----------------------------------------
    "aduanas": [{
        "c": r["codigo"], "n": r["aduana"], "via": r["via_principal"],
    } for _, r in ax_a.sort_values("fob_usd", ascending=False).iterrows()],
})


# ------------------------------------------------------------ importacion -
# Que importa el agro peruano, mas alla del fertilizante y el fitosanitario
# que la plataforma ya media. Lo arma build_import_categorias.py leyendo los
# manifiestos crudos; aqui solo se empaqueta.
imp_c = pd.read_csv("out/import_agro_categoria.csv", encoding="utf-8-sig")
imp_g = pd.read_csv("out/import_agro_glosa.csv", encoding="utf-8-sig")
imp_x = pd.read_csv("out/import_agro_excluidas.csv", encoding="utf-8-sig",
                    dtype={"partida": str})
imp_r = pd.read_csv("out/import_agro_referencia.csv", encoding="utf-8-sig")
imp_l = pd.read_csv("out/import_agro_lineas.csv", encoding="utf-8-sig",
                    dtype={"ruc": str})
imp_l = imp_l[imp_l.categoria != "referencia"]

# Los mayores importadores de cada categoria: es la lista de con quien compite
# o a quien le compra un canal que quiera entrar en ese rubro.
top_cat = {}
for k, g in imp_l.groupby("categoria"):
    t = g.groupby("razon_social").fob_usd.sum().nlargest(6)
    top_cat[k] = [{"n": n[:44], "fob": int(v)} for n, v in t.items()]

glosas = {}
for k, g in imp_g.groupby("categoria"):
    glosas[k] = [{"g": r["glosa"], "fob": int(r["fob_usd"]),
                  "tn": int(round(r["toneladas"])), "emp": int(r["empresas"])}
                 for _, r in g.sort_values("fob_usd", ascending=False).iterrows()]

con_mercancia = imp_c[imp_c.lineas > 0]
guardar("importacion.json", {
    "meta": {
        "semanas": SEM,
        "desde": VENTANA["desde"],
        "hasta": VENTANA["hasta"],
        "lineas_pais": int(VENTANA["lineas_pais"]),
        "fob_pais": int(VENTANA["fob_pais"]),
        "fob": int(con_mercancia.fob_usd.sum()),
        "tn": int(round(con_mercancia.toneladas.sum())),
        "empresas": int(imp_l.ruc.nunique()),
        "fob_insumos": int(imp_r.fob_usd.sum()),
        "fob_fuera": int(imp_x.fob_usd.sum()),
    },
    "cats": [{
        "k": r["categoria"], "n": r["nombre"], "fob": int(r["fob_usd"]),
        "tn": int(round(r["toneladas"])), "emp": int(r["empresas"]),
        "part": int(r["partidas"]), "lineas": int(r["lineas"]),
        "glosas": glosas.get(r["categoria"], []),
        "top": top_cat.get(r["categoria"], []),
    } for _, r in imp_c.iterrows()],
    "ref": [{"g": r["glosa"], "fob": int(r["fob_usd"])}
            for _, r in imp_r.iterrows()],
    "fuera": [{"p": r["partida"], "n": r["nombre"], "m": r["motivo"],
               "fob": int(r["fob_usd"])} for _, r in imp_x.iterrows()],
})
print(f"\nimportacion agricola     : US$ {con_mercancia.fob_usd.sum()/1e6:,.1f} MM"
      f" en {SEM} semanas, {imp_l.ruc.nunique():,} empresas")
