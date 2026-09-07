# -*- coding: utf-8 -*-
"""Dónde está la carga exportadora de verdad, y a qué distancia de cada centro.

El proyecto ya repartía FOB exportado por celda hexagonal, pero lo situaba con
el domicilio fiscal del padrón: una agroexportadora con oficina en San Isidro
aportaba su tonelaje a Lima. Eso pone la demanda donde están las oficinas y no
donde está el campo, que para decidir dónde abrir un almacén es exactamente el
error que importa.

Aquí la carga se sitúa con el **UBIGEO del manifiesto**, que apunta al lugar de
producción —se comprobó contra el padrón: coincide en el distrito solo el 26.6%
de las veces, y donde el manifiesto dice Virú el padrón dice Lima—. Sale de los
años en que SUNAT llenó ese campo, 2022 a 2024, y no se extiende a los demás.

Tres salidas, una por pregunta:

  `acopio_distrito.csv`  los 581 distritos que embarcan, con cuánto, cuántas
                         empresas, qué producto manda, en qué mes pica y a qué
                         distancia del centro más cercano.
  `acopio_hub.csv`       cuánta de esa carga queda dentro de 2, 4 y 6 horas de
                         cada centro candidato. Es la respuesta de inventario:
                         no «cuánto mercado hay» sino «cuánto alcanzo».
  `acopio_territorio.csv` lo mismo por territorio de venta, para cruzarlo con
                         la cartera que ya existe.

Uso:
    python scripts/build_acopio.py
"""
import io
import json
import os
import sys

import h3
import pandas as pd

PROC = "data/exportaciones/processed"
OPERACIONES = os.path.join(PROC, "operaciones_limpias.csv")
MERCADO = os.path.join(PROC, "mercado.json")
SECTORES = "out/sectores_2024.csv"
ASIGNACION = "out/hubs_asignacion.csv"
CARTERA = "out/cartera_territorio.csv"
CELDAS = "out/clusters_celda.csv"
SENASA = "out/senasa_exportadores.csv"
RES_HUB = 5      # la grilla con la que se asignaron los centros
RES_TER = 6      # la grilla con la que se detectaron los territorios
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def main():
    for p in (OPERACIONES, MERCADO, SECTORES, ASIGNACION):
        if not os.path.exists(p):
            sys.exit("falta " + p)
    m = json.load(io.open(MERCADO, encoding="utf-8"))
    anios = m["departamentos"]["anios_usados"]

    d = pd.read_csv(OPERACIONES, encoding="utf-8-sig", low_memory=False,
                    usecols=["ruc", "ubigeo", "fob_usd", "anio", "mes",
                             "familia", "peso_neto_kg"], dtype=str)
    for c in ("fob_usd", "peso_neto_kg"):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    d = d[d.anio.isin(anios) & d.ubigeo.fillna("").str.fullmatch(r"\d{6}")]

    # ---------------------------------------------------- por distrito --
    por = d.groupby("ubigeo").agg(
        fob=("fob_usd", "sum"), kg=("peso_neto_kg", "sum"),
        ops=("fob_usd", "size"), empresas=("ruc", "nunique"))
    lider = (d.groupby(["ubigeo", "familia"]).fob_usd.sum()
             .reset_index().sort_values("fob_usd", ascending=False)
             .drop_duplicates("ubigeo").set_index("ubigeo"))
    por["familia_lider"] = lider.familia
    por["pct_lider"] = (100 * lider.fob_usd / por.fob).round(1)
    # El mes que manda en cada distrito: es el que decide cuándo hay que tener
    # el almacén lleno, y no es el mismo en Ica que en Piura.
    pm = d.groupby(["ubigeo", "mes"]).fob_usd.sum().reset_index()
    pico = pm.sort_values("fob_usd", ascending=False).drop_duplicates("ubigeo")
    por["mes_pico"] = pico.set_index("ubigeo").mes.map(
        lambda x: MESES[int(x) - 1])

    # El distrito se sitúa en el centro de sus sectores agrícolas, que es
    # donde está la tierra y no donde está la plaza de armas.
    sec = pd.read_csv(SECTORES, encoding="utf-8-sig", dtype={"ubigeo": str})
    geo = sec.groupby("ubigeo").agg(dep=("dep", "first"), prov=("prov", "first"),
                                    dist=("dist", "first"), lat=("lat", "mean"),
                                    lon=("lon", "mean"),
                                    ha_agricola=("ha_agricola", "sum"))
    j = por.join(geo, how="left")
    sin_geo = int(j.lat.isna().sum())
    j = j.dropna(subset=["lat", "lon"]).copy()
    # Cada capa se hizo con su propia resolución: los centros sobre r5 y los
    # territorios sobre r6. Cruzar una con la otra no devuelve nada, así que
    # el distrito lleva las dos celdas.
    j["h3"] = [h3.latlng_to_cell(float(a), float(b), RES_HUB)
               for a, b in zip(j.lat, j.lon)]
    j["h3_ter"] = [h3.latlng_to_cell(float(a), float(b), RES_TER)
                   for a, b in zip(j.lat, j.lon)]

    # ------------------------------------------------- hub y territorio --
    asg = pd.read_csv(ASIGNACION, encoding="utf-8-sig")
    asg = asg.drop_duplicates("h3").set_index("h3")
    j = j.join(asg[["hub", "horas_al_hub", "cubierto_2h"]], on="h3")
    j["fob_mm"] = (j.fob / 1e6).round(1)
    j = j.sort_values("fob", ascending=False).reset_index()

    # ------------------------------------------------------ por centro --
    # La pregunta de inventario no es cuánto mercado hay sino cuánto se
    # alcanza: la misma carga cambia de dueño según el radio que se acepte.
    filas = []
    for hub, g in j.dropna(subset=["hub"]).groupby("hub"):
        fila = {"hub": hub, "distritos": len(g),
                "fob_mm": round(g.fob.sum() / 1e6, 1),
                "empresas": int(g.empresas.sum())}
        for h in (2, 4, 6):
            sub = g[g.horas_al_hub <= h]
            fila["fob_%dh_mm" % h] = round(sub.fob.sum() / 1e6, 1)
            fila["distritos_%dh" % h] = len(sub)
        filas.append(fila)
    hub = pd.DataFrame(filas).sort_values("fob_2h_mm", ascending=False)
    hub.to_csv("out/acopio_hub.csv", index=False, encoding="utf-8-sig")

    # --------------------------------------------------- por territorio --
    # El territorio se asigna por celda, no por centro. Cruzarlo por `hub`
    # repartía el total del centro a cada territorio que cuelga de él y los
    # cinco primeros salían con la misma cifra, que es como se ve un merge
    # que multiplica filas: todos iguales y todos enormes.
    ter = None
    if os.path.exists(CARTERA) and os.path.exists(CELDAS):
        cel = pd.read_csv(CELDAS, encoding="utf-8-sig",
                          usecols=["h3", "cluster"]).drop_duplicates("h3")
        cel = cel.rename(columns={"h3": "h3_ter"})
        j = j.merge(cel, on="h3_ter", how="left")
        car = pd.read_csv(CARTERA, encoding="utf-8-sig")
        # Sumar la columna «empresas» por territorio contaba tres veces a la
        # que embarca desde tres distritos. Se vuelve al detalle y se cuentan
        # RUC distintos.
        ub2cl = j.set_index("ubigeo").cluster
        det = d.copy()
        det["cluster"] = det.ubigeo.map(ub2cl)
        emp_ter = det.dropna(subset=["cluster"]).groupby("cluster").ruc.nunique()
        t = (j.dropna(subset=["cluster"]).groupby("cluster")
             .agg(fob=("fob", "sum"), distritos=("fob", "size")))
        t["empresas_export"] = emp_ter
        ter = car.merge(t.reset_index(), on="cluster", how="left")
        ter["fob_export_mm"] = (ter.fob / 1e6).round(1)
        ter.drop(columns=["fob"]).to_csv("out/acopio_territorio.csv",
                                         index=False, encoding="utf-8-sig")
        j.to_csv("out/acopio_distrito.csv", index=False, encoding="utf-8-sig")
        fuera = j.cluster.isna().sum()
        print("")
        print("distritos fuera de todo territorio de venta: %d · US$ %s MM"
              % (fuera, format(round(j[j.cluster.isna()].fob.sum() / 1e6), ",")))

    # ------------------------------------------------- lo que lee la web --
    sin_hub = j[j.hub.isna()]
    # Un JSON chico con lo que las dos salidas muestran: el detalle por
    # distrito son 580 filas que nadie mira de una vez.
    import json as _js
    pack = None
    if os.path.exists(SENASA):
        sn = pd.read_csv(SENASA, encoding="utf-8-sig")
        pk = sn[sn.empacadoras > 0]
        pack = {
            "empacadoras": int(len(pk)),
            "embarcan": int(pk.ruc.notna().sum()),
            "sin_embarque_propio": int(pk.ruc.isna().sum()),
            "lugares_produccion": int((sn.empacadoras == 0).sum()),
            "por_region": (pk.regiones.fillna("").str.split(",").explode()
                           .str.strip().replace("", pd.NA).dropna()
                           .value_counts().head(10).to_dict()),
            "mayores": [{"n": r.empresa, "fob": float(r.fob or 0),
                         "dep": str(r.dep or ""), "prod": str(r.productos or "")}
                        for _, r in pk[pk.ruc.notna()].head(10).iterrows()],
        }
    web = {
        "generado": pd.Timestamp.now().isoformat(timespec="seconds"),
        "anios": anios,
        "fuente": "ubigeo del manifiesto de SUNAT (lugar de producción) y "
                  "listas de establecimientos certificados de SENASA",
        "distritos": int(len(j)), "empresas": int(d.ruc.nunique()),
        "fob": float(j.fob.sum()),
        "sin_centro": {"distritos": int(len(sin_hub)),
                       "fob": float(sin_hub.fob.sum()),
                       "mayores": [{"n": str(r.dist).title(), "fob": float(r.fob)}
                                   for _, r in sin_hub.head(5).iterrows()]},
        "hubs": hub.to_dict("records"),
        "top_distritos": [
            {"n": str(r.dist).title(), "dep": str(r.dep), "fob": float(r.fob),
             "empresas": int(r.empresas), "familia": str(r.familia_lider),
             "mes": str(r.mes_pico), "hub": str(r.hub) if pd.notna(r.hub) else "",
             "horas": float(r.horas_al_hub) if pd.notna(r.horas_al_hub) else None}
            for _, r in j.head(25).iterrows()],
        "territorios": ([{"n": str(r.territorio), "fob": float(r.fob_export_mm or 0) * 1e6,
                          "empresas_export": int(r.empresas_export or 0),
                          "cartera": int(r.empresas or 0),
                          "importadores": int(r.importadores or 0),
                          "hub": str(r.hub), "horas": float(r.horas_al_hub or 0)}
                         for _, r in ter.dropna(subset=["fob_export_mm"])
                         .sort_values("fob_export_mm", ascending=False).head(15).iterrows()]
                        if ter is not None else []),
        "senasa": pack,
        "senasa_cobertura": (_js.load(io.open("out/senasa_cobertura.json",
                                              encoding="utf-8"))
                             if os.path.exists("out/senasa_cobertura.json")
                             else {"productos": [], "sin_lista": []}),
    }
    with io.open("out/acopio.json", "w", encoding="utf-8") as fh:
        _js.dump(web, fh, ensure_ascii=False, separators=(",", ":"))

    print("años con ubigeo    : %s" % ", ".join(anios))
    print("distritos con carga: %s  (sin sector agrícola mapeado: %d)"
          % (format(len(j), ","), sin_geo))
    print("FOB situado        : US$ %s MM" % format(round(j.fob.sum() / 1e6), ","))
    print("empresas           : %s" % format(int(d.ruc.nunique()), ","))
    print("\nlos diez distritos que más embarcan:")
    for _, r in j.head(10).iterrows():
        print("  %-26s %7.0f MM  %4d emp  pico %s  %s a %.1f h"
              % ("%s, %s" % (str(r.dist)[:16], str(r.dep)[:9]), r.fob / 1e6,
                 int(r.empresas), r.mes_pico, str(r.hub)[:12],
                 r.horas_al_hub if pd.notna(r.horas_al_hub) else -1))
    print("\ncuánta carga alcanza cada centro, por radio:")
    # Un distrito cuya celda no está en la asignación no tiene centro que
    # lo sirva: no es carga cero, es carga fuera de alcance, y se dice.
    print("")
    print("sin centro asignado : %d distritos · US$ %s MM"
          % (len(sin_hub), format(round(sin_hub.fob.sum() / 1e6), ",")))
    if len(sin_hub):
        print("  los mayores: %s" % ", ".join(
            "%s (%.0f MM)" % (str(r.dist).title(), r.fob / 1e6)
            for _, r in sin_hub.head(3).iterrows()))
    for _, r in hub.head(8).iterrows():
        print("  %-14s 2h %6.0f MM · 4h %6.0f MM · 6h %6.0f MM  (%d distritos)"
              % (r.hub[:14], r.fob_2h_mm, r.fob_4h_mm, r.fob_6h_mm,
                 r.distritos))
    if ter is not None:
        print("\nterritorios con más carga exportadora:")
        for _, r in ter.sort_values("fob_export_mm", ascending=False).head(5).iterrows():
            print("  %-34s %7.0f MM  %s empresas en cartera"
                  % (str(r.territorio)[:34], r.fob_export_mm or 0,
                     int(r.empresas) if pd.notna(r.empresas) else 0))


if __name__ == "__main__":
    main()
