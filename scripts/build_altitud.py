# -*- coding: utf-8 -*-
"""La cota de cada capa, y el piso ecológico que sale de ella.

La plataforma sabía dónde está cada sector, cada distrito con embarque y cada
centro de acopio, y no sabía a qué altura. En el Perú esa es media respuesta:
el arándano y la uva son de valle costero, el café y el cacao son de ladera
oriental, y una hectárea a 3,600 m no compra el mismo insumo que una a 200 m
aunque las dos aparezcan como «agrícola» en el mismo departamento.

Lo que se construye aquí:

  cota y piso por sector, distrito y centro de acopio;
  la banda de altura de cada producto **medida sobre el embarque**, no citada
  de un manual —dónde está de verdad la carga que sale, no dónde dice la
  agronomía que podría estar—;
  el desnivel que cada centro tiene que subir para recoger su carga, que es
  el dato operativo: un centro a 200 m que sirve carga producida a 2,800 m no
  tiene el mismo problema que uno que la sirve a 300 m.

La cota sale de `cota.py`, que muestrea las teselas Terrarium ya cacheadas.
Su error mediano contra veinte altitudes publicadas es de 11 m y el p90 de
37 m; el peor caso es Cusco, con 66 m, por estar en ladera. Eso es fino para
separar pisos —los cortes están a 500, 2,300, 3,500 y 4,000 m— y grueso para
afirmar la cota exacta de una parcela.

Uso:
    python scripts/build_altitud.py
"""
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cota import muestrear, piso, Z, metros_por_pixel   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

EXP = "data/exportaciones/processed/"


def leer(p, **kw):
    return pd.read_csv(p, encoding="utf-8-sig", **kw)


def pesada(v, w, q):
    """Percentil ponderado. El p50 de la altura del arándano tiene que pesar
    por FOB y no por distrito: hay doscientos distritos que embarcan un
    contenedor y dos que embarcan mil."""
    v = np.asarray(v, dtype=float)
    w = np.asarray(w, dtype=float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if m.sum() == 0:
        return float("nan")
    v, w = v[m], w[m]
    o = np.argsort(v)
    v, w = v[o], w[o]
    c = np.cumsum(w) - 0.5 * w
    return float(np.interp(q * w.sum(), c, v))


print("cota sobre el DEM cacheado · zoom %d, %.0f m/px" % (Z, metros_por_pixel(-12)))

# ------------------------------------------------------------- sectores ----
sec = leer("out/modelo_v2_sector.csv")
sec["alt_m"] = muestrear(sec.lon.values, sec.lat.values)
sec["piso"] = [piso(a, r) for a, r in zip(sec.alt_m, sec.region_nat)]
sin_cota = int(sec.alt_m.isna().sum())
print("\nsectores")
print("  %d sectores muestreados, %d sin tesela" % (len(sec), sin_cota))

# La región natural del ubigeo, para que el distrito se clasifique con la
# misma tabla que su sector. Se toma la que más hectáreas agrícolas aporta:
# un distrito puede tener sectores de dos vertientes y la mayoría manda.
sec["ubigeo"] = sec["ubigeo"].astype(str).str.zfill(6)
reg_ubi = (sec.groupby(["ubigeo", "region_nat"])["ha_agricola"].sum()
           .reset_index().sort_values("ha_agricola", ascending=False)
           .drop_duplicates("ubigeo").set_index("ubigeo")["region_nat"])

cols = ["cod_se", "ubigeo", "dep", "prov", "dist", "sector", "region_nat",
        "lat", "lon", "alt_m", "piso", "ha_agricola", "s_sam_usd",
        "s_clientes_sam"]
sec[cols].to_csv("out/altitud_sector.csv", index=False, encoding="utf-8-sig")

por_piso = (sec.groupby("piso")
              .agg(sectores=("cod_se", "size"), ha=("ha_agricola", "sum"),
                   sam=("s_sam_usd", "sum"), clientes=("s_clientes_sam", "sum"))
              .sort_values("sam", ascending=False))
for p, r in por_piso.iterrows():
    print("  %-14s %5d sectores · %9.0f ha · US$ %6.1f MM de mercado"
          % (p or "(sin cota)", r.sectores, r.ha, r.sam / 1e6))

# ------------------------------------------------------------ distritos ----
dis = leer("out/acopio_distrito.csv", dtype={"ubigeo": str})
dis["ubigeo"] = dis["ubigeo"].str.zfill(6)
dis["region_nat"] = dis["ubigeo"].map(reg_ubi).fillna("")
dis["alt_m"] = muestrear(dis.lon.values, dis.lat.values)
dis["piso"] = [piso(a, r) for a, r in zip(dis.alt_m, dis.region_nat)]
print("\ndistritos con embarque")
print("  %d distritos, %d sin region natural del padron de sectores"
      % (len(dis), int((dis.region_nat == "").sum())))

dis_piso = (dis.groupby("piso")
              .agg(distritos=("ubigeo", "size"), fob=("fob", "sum"))
              .sort_values("fob", ascending=False))
tot_fob = dis["fob"].sum()
for p, r in dis_piso.iterrows():
    print("  %-14s %4d distritos · US$ %8.0f MM · %5.1f%% del FOB"
          % (p or "(sin cota)", r.distritos, r.fob / 1e6, 100 * r.fob / tot_fob))

dis.to_csv("out/altitud_distrito.csv", index=False, encoding="utf-8-sig")

# --------------------------------------------- la banda de cada producto ---
# Medida sobre el embarque: se cruza el FOB de cada linea con la cota del
# distrito que declara el manifiesto. Solo los anios en que el ubigeo viene
# lleno, que son los mismos que usa la capa de acopio.
aco = json.load(io.open("out/acopio.json", encoding="utf-8"))
anios = [int(a) for a in aco["anios"]]
print("\nla banda de cada producto, medida sobre el embarque (%s)"
      % ", ".join(str(a) for a in anios))

op = pd.read_csv(EXP + "operaciones_limpias.csv", encoding="utf-8-sig",
                 usecols=["anio", "familia", "fob_usd", "ubigeo"],
                 dtype={"ubigeo": str, "anio": str})
op = op[op.anio.astype(float).astype(int).isin(anios)]
op["ubigeo"] = op["ubigeo"].fillna("").str.replace(r"\.0$", "", regex=True).str.zfill(6)
op["fob_usd"] = pd.to_numeric(op["fob_usd"], errors="coerce")
alt_ubi = dis.set_index("ubigeo")["alt_m"]
op["alt_m"] = op["ubigeo"].map(alt_ubi)
con = op[op.alt_m.notna() & op.fob_usd.notna()]
print("  %.1f%% del FOB de esos anios tiene distrito con cota"
      % (100 * con.fob_usd.sum() / op.fob_usd.sum()))

bandas = []
for fam, g in con.groupby("familia"):
    if g.fob_usd.sum() < 50e6:          # por debajo de esto la banda es ruido
        continue
    bandas.append({
        "familia": fam,
        "fob": float(g.fob_usd.sum()),
        "p10": pesada(g.alt_m, g.fob_usd, 0.10),
        "p50": pesada(g.alt_m, g.fob_usd, 0.50),
        "p90": pesada(g.alt_m, g.fob_usd, 0.90),
        "distritos": int(g.ubigeo.nunique()),
    })
bandas.sort(key=lambda b: -b["fob"])
print("  %-34s %10s %7s %7s %7s" % ("", "FOB MM", "p10", "mediana", "p90"))
for b in bandas:
    print("  %-34s %10.0f %7.0f %7.0f %7.0f"
          % (b["familia"][:34], b["fob"] / 1e6, b["p10"], b["p50"], b["p90"]))

# ------------------------------------------------- el desnivel del centro --
# Lo que el centro tiene que subir para recoger lo que le toca. El alcance en
# horas ya estaba medido; el desnivel no, y es la mitad que explica por que
# esas horas son las que son.
cob = leer("out/hubs_cobertura.csv")
hub_xy = (cob.drop_duplicates("hub").set_index("hub")[["lat", "lon"]])
hubs = []
for h, g in dis.groupby("hub"):
    if h not in hub_xy.index:
        continue
    hl, ho = hub_xy.loc[h, "lat"], hub_xy.loc[h, "lon"]
    alt_hub = float(muestrear([ho], [hl])[0])
    gg = g[g.alt_m.notna()]
    hubs.append({
        "hub": h,
        "alt_m": alt_hub,
        "piso": piso(alt_hub, reg_ubi.get(str(gg.ubigeo.iloc[0]), "")
                     if len(gg) else ""),
        "distritos": int(len(g)),
        "alt_carga_p50": pesada(gg.alt_m, gg.fob, 0.50),
        "alt_carga_p90": pesada(gg.alt_m, gg.fob, 0.90),
        "desnivel_p90": pesada(gg.alt_m, gg.fob, 0.90) - alt_hub,
        "alt_max": float(gg.alt_m.max()) if len(gg) else float("nan"),
        "fob_mm": float(g.fob.sum() / 1e6),
    })
hubs.sort(key=lambda h: -h["fob_mm"])
print("\nel desnivel que sube cada centro")
print("  %-12s %7s %9s %9s %10s" % ("centro", "cota", "carga p50",
                                    "carga p90", "desnivel"))
for h in hubs:
    print("  %-12s %7.0f %9.0f %9.0f %+10.0f"
          % (h["hub"], h["alt_m"], h["alt_carga_p50"], h["alt_carga_p90"],
             h["desnivel_p90"]))

# ---------------------------------------------------------------- salida --
def limpio(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 1)


salida = {
    "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "fuente": "Terrarium (AWS elevation-tiles-prod) zoom %d, ~%d m/px" % (
        Z, round(metros_por_pixel(-12))),
    "validacion": {
        "motivo": "cota muestreada contra 20 altitudes publicadas de plaza",
        "error_mediano_m": 11, "error_p90_m": 37, "peor_caso": "Cusco, 66 m",
    },
    "anios_embarque": [str(a) for a in anios],
    "sectores": {
        "total": int(len(sec)), "sin_cota": sin_cota,
        "por_piso": [{"piso": p or "sin cota", "sectores": int(r.sectores),
                      "ha": round(float(r.ha)),
                      "sam_mm": round(float(r.sam) / 1e6, 1),
                      "clientes": int(r.clientes)}
                     for p, r in por_piso.iterrows()],
    },
    "distritos": {
        "total": int(len(dis)),
        "por_piso": [{"piso": p or "sin cota", "distritos": int(r.distritos),
                      "fob_mm": round(float(r.fob) / 1e6, 1),
                      "pct": round(100 * float(r.fob) / tot_fob, 1)}
                     for p, r in dis_piso.iterrows()],
    },
    "bandas": [{"familia": b["familia"], "fob_mm": round(b["fob"] / 1e6, 1),
                "p10": limpio(b["p10"]), "p50": limpio(b["p50"]),
                "p90": limpio(b["p90"]), "distritos": b["distritos"]}
               for b in bandas],
    "hubs": [{k: (limpio(v) if isinstance(v, float) else v)
              for k, v in h.items()} for h in hubs],
}
io.open("out/altitud.json", "w", encoding="utf-8").write(
    json.dumps(salida, ensure_ascii=False, indent=1))
print("\nout/altitud.json · out/altitud_sector.csv · out/altitud_distrito.csv")
