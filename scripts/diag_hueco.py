# -*- coding: utf-8 -*-
"""Quiénes son los que no tienen dónde comprar, y por qué.

Del padrón de clientes, 10,518 no tienen ni una tienda ni un centro poblado a
45 minutos: es el hueco que quedó después de meter los 94,922 centros poblados
del INEI como candidatos. Y por otro lado la **selva baja** es la región peor
servida por la red de centros —45% dentro de su promesa contra 67% de la
sierra—, y ninguna vara la arregla.

La sospecha era que son la misma historia y que el problema es el camino:
donde no hay carretera, ni el almacén llega ni la tienda existe. **El dato la
desmiente**, y por eso este archivo se conserva: la respuesta útil salió de
descartar la hipótesis, no de confirmarla.

De los 10,518 clientes del hueco, **31 están en sectores sin ruta vial a un
puerto**. Los otros 10,487 tienen carretera y no tienen a quién comprarle: dos
tercios están en sierra —quechua, puna y suni— y los departamentos que más
aportan son Junín, Cusco y Lambayeque, no la selva. El hueco no es de acceso
sino de comercio.

Y la selva baja, que era la otra mitad de la sospecha, resulta bien servida por
abajo: el 40% de sus clientes tiene un comercio a 45 minutos y solo el 2% no
tiene ni tienda ni pueblo. Lo suyo es distancia al almacén —45% dentro de la
promesa— y no ausencia de canal.

El cruce, para que se pueda rehacer:

  `canal_sector.csv`   qué sector tiene comercio, cuál tiene solo pueblo y
                       cuál no tiene nada, a 45 minutos
  `ruteo_sector.csv`   qué sector no tiene ninguna ruta por carretera hasta un
                       puerto marítimo —el proxy más honesto de «sin salida
                       vial», porque un sector que no alcanza el mar tampoco
                       alcanza mucho más—
  `altitud_sector.csv` el piso ecológico, para separar el hueco de altura del
                       hueco de selva

Una salvedad sobre el proxy, porque sin ella el descarte no vale: **sin ruta
vial a un puerto es raro en todo el país** —105 sectores de 6,892, el 0.5% de
los clientes—, así que nunca iba a explicar diez mil personas. Lo que el cruce
descarta con seguridad es que el hueco esté hecho de sitios incomunicados; lo
que no puede es medir grados de mal camino, que el ruteo sí conoce y esta
pregunta no usó.

Uso:
    python scripts/diag_hueco.py
"""
import io
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def leer(p, **kw):
    return pd.read_csv(p, encoding="utf-8-sig", **kw)


s = leer("out/canal_sector.csv")
alt = leer("out/altitud_sector.csv")[["cod_se", "piso", "alt_m"]]
s = s.merge(alt, on="cod_se", how="left")
s["sin_via_puerto"] = ~np.isfinite(s["horas_puerto_real"])

TOT = s["clientes"].sum()
hueco = s[s["sin_nada"]]
print("el hueco: %s clientes de %s (%.1f%%) sin tienda ni pueblo a 45 min"
      % (f"{hueco.clientes.sum():,.0f}", f"{TOT:,.0f}",
         100 * hueco.clientes.sum() / TOT))
print("  en %d sectores · US$ %.1f MM de mercado"
      % (len(hueco), hueco.sam_usd.sum() / 1e6))

# --- la pregunta central --------------------------------------------------
sv = hueco.loc[hueco.sin_via_puerto, "clientes"].sum()
print()
print("¿se explica por falta de carretera?")
print("  %s de esos clientes están en sectores sin ninguna ruta vial a un "
      "puerto marítimo (%.0f%%)" % (f"{sv:,.0f}", 100 * sv / hueco.clientes.sum()))
base = s.loc[~s.sin_nada, "clientes"]
base_sv = s.loc[~s.sin_nada & s.sin_via_puerto, "clientes"].sum()
print("  en el resto del país esa proporción es %.0f%%"
      % (100 * base_sv / base.sum()))
if hueco.clientes.sum() > 0 and base.sum() > 0:
    r = (sv / hueco.clientes.sum()) / max(base_sv / base.sum(), 1e-9)
    print("  o sea: %.0f veces más probable estar sin vía si estás en el hueco"
          % r)

print()
print("dónde está el hueco")
por = (hueco.groupby("region_nat")
       .agg(sectores=("cod_se", "size"), clientes=("clientes", "sum"),
            sam=("sam_usd", "sum"), sin_via=("sin_via_puerto", "mean"))
       .sort_values("clientes", ascending=False))
print("  %-14s %9s %10s %10s %10s" % ("región", "sectores", "clientes",
                                      "US$ MM", "sin vía"))
for i, r in por.iterrows():
    print("  %-14s %9d %10s %10.1f %9.0f%%"
          % (i, r.sectores, f"{r.clientes:,.0f}", r.sam / 1e6,
             100 * r.sin_via))

dep = (hueco.groupby("dep").agg(clientes=("clientes", "sum"),
                                sin_via=("sin_via_puerto", "mean"))
       .sort_values("clientes", ascending=False).head(8))
print()
print("  los ocho departamentos con más clientes en el hueco")
for i, r in dep.iterrows():
    print("  %-16s %10s clientes · %.0f%% sin vía a puerto"
          % (i, f"{r.clientes:,.0f}", 100 * r.sin_via))

# --- la selva baja, que es la otra mitad de la sospecha -------------------
print()
print("la selva baja, la región peor servida por la red de centros")
sb = s[s.region_nat.str.upper().str.startswith("SELVA BAJA")]
if len(sb):
    print("  %s clientes en %d sectores · US$ %.1f MM"
          % (f"{sb.clientes.sum():,.0f}", len(sb), sb.sam_usd.sum() / 1e6))
    print("  sin vía a puerto     : %.0f%% de sus clientes"
          % (100 * sb.loc[sb.sin_via_puerto, "clientes"].sum()
             / sb.clientes.sum()))
    print("  sin tienda ni pueblo : %.0f%%"
          % (100 * sb.loc[sb.sin_nada, "clientes"].sum() / sb.clientes.sum()))
    print("  con comercio a 45 min: %.0f%%"
          % (100 * sb.loc[sb.con_comercio, "clientes"].sum()
             / sb.clientes.sum()))
    otras = s[~s.region_nat.str.upper().str.startswith("SELVA BAJA")]
    print("  —en el resto del país, sin vía a puerto es el %.0f%%—"
          % (100 * otras.loc[otras.sin_via_puerto, "clientes"].sum()
             / otras.clientes.sum()))

# --- y lo que no se explica por la vía ------------------------------------
resto = hueco[~hueco.sin_via_puerto]
print()
print("lo que NO se explica por falta de carretera")
print("  %s clientes en %d sectores: tienen vía pero no tienen a quién "
      "comprarle cerca" % (f"{resto.clientes.sum():,.0f}", len(resto)))
if len(resto):
    top = resto.nlargest(6, "clientes")[["dep", "prov", "dist", "clientes",
                                         "horas_capital_real", "piso"]]
    print("  %-14s %-16s %9s %8s %-12s" % ("departamento", "distrito",
                                           "clientes", "h capital", "piso"))
    for _, r in top.iterrows():
        print("  %-14s %-16s %9s %8.1f %-12s"
              % (str(r.dep)[:14], str(r.dist)[:16], f"{r.clientes:,.0f}",
                 r.horas_capital_real, str(r.piso)[:12]))

print()
print("out/canal_sector.csv tiene el detalle por sector")
