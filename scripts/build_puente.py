# -*- coding: utf-8 -*-
"""El puente entre el mapa y la venta real: dónde ya se vende y qué hay al lado.

Treinta y dos etapas miden un mercado de 156,880 clientes y US$ 512 MM. El
libro de ventas tiene **15 clientes y US$ 24,787** en trece meses. Nadie había
cruzado las dos cosas, y al cruzarlas aparece lo que ninguna de las dos dice
sola.

**Once de los quince no están en el padrón** que la plataforma usa como
cartera. Son personas naturales, una universidad, una empresa de seguridad: el
padrón se filtra a empresas con razón social agraria, así que por construcción
no puede contenerlos. El 32% del ingreso viene de personas naturales y la lista
accionable que el sitio le entrega a un vendedor no las tiene.

**Y se vende donde la red no llega.** Áncash es el 45% del ingreso y la región
que los centros cubren al 6.4% dentro de la promesa. No es un error de nadie:
es que el mapa se dibujó por tamaño de mercado y la venta ocurrió por contacto.
Ponerlo junto es la única manera de verlo.

## Las dos mitades

**Dónde.** Se ubica cada cliente por el padrón y, si no está, por el
departamento que trae su propio documento. Con eso, para cada departamento
donde ya se vende: qué dice la plataforma de él —SAM, cobertura, mes pico, en
qué se le va el gasto— y qué hay para trabajar al lado: los puntos de canal
reclutables que le corresponden.

**Qué.** El detalle de líneas dice qué se vendió, y eso se compara contra la
canasta. Ahí hay una trampa que hay que declarar: `ventas_lineas.csv` mezcla
soles y dólares en la misma columna —29 líneas en soles y 14 en dólares— y
sumarlas sin convertir da US$ 75,719 donde los documentos dicen 24,787. Se
convierte a 3.75 soles por dólar, que es el mismo tipo de cambio que usa el
resto del proyecto.

## Un dato roto que se declara en vez de taparse

Los tres primeros documentos —FE01-00001 a 3, US$ 9,585—
traen un número donde debería ir el departamento: `3076.465590484282`, el mismo
en los tres. Es una columna corrida en la planilla de origen, que es
confidencial y no está en el repositorio, así que no se puede arreglar desde
aquí. No se les inventa un departamento: se cuentan aparte. Uno de los tres sí
se ubica por el padrón, que es justamente para lo que sirve tener dos fuentes.

## Esto no se publica

La salida lleva nombres de clientes y montos facturados. Se queda en `out/` y
**no va al sitio ni al repositorio**, como el resto del libro de ventas. El
`.gitignore` la nombra por si alguien la mueve de sitio sin pensarlo.

Uso:
    python scripts/build_puente.py
"""
import io
import json
import os
import re
import sys
import unicodedata

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

TC = 3.75            # soles por dólar, el mismo del resto del proyecto
SALIDA = "out/puente.json"
# El libro trae a veces la provincia donde va el departamento. No es un dato
# distinto: es el mismo sitio escrito con otro nivel, y sin esto Lambayeque
# aparece partido en dos filas.
ALIAS_DEP = {"chiclayo": "LAMBAYEQUE", "trujillo": "LA LIBERTAD",
             "sullana": "PIURA", "huaraz": "ANCASH"}


def k(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def leer(p, **kw):
    if not os.path.exists(p):
        sys.exit("falta %s: corre el pipeline" % p)
    return pd.read_csv(p, encoding="utf-8-sig", **kw)


def main():
    cli = leer("out/ventas_cliente.csv", dtype={"ruc": str})
    doc = leer("out/ventas_doc.csv", dtype={"ruc": str})
    lin = leer("out/ventas_lineas.csv", dtype={"ruc": str})
    car = leer("out/cartera_empresa.csv", dtype={"ruc": str})
    can = json.load(io.open("out/canasta.json", encoding="utf-8"))
    rec = json.load(io.open("out/reclutar.json", encoding="utf-8"))
    cob = json.load(io.open("out/cobertura_mes.json", encoding="utf-8"))

    # --- lo que se vendió, con las dos monedas resueltas -----------------
    lin["usd"] = [t / TC if str(m).upper().startswith("SOL") else t
                  for t, m in zip(lin.total_linea, lin.moneda)]
    prod = (lin.groupby("producto").usd.sum()
            .sort_values(ascending=False))

    # --- dónde ------------------------------------------------------------
    ubic = car.drop_duplicates("ruc").set_index("ruc")
    cli["en_padron"] = cli.ruc.isin(ubic.index)
    # El departamento del documento, cuando el padrón no lo tiene. Un valor
    # numérico no es un departamento: se marca y no se usa.
    doc["dep_roto"] = doc.dep.astype(str).str.fullmatch(r"[\d.]+")
    rotos = [{"doc": str(r.doc), "cliente": str(r.cliente),
              "usd": round(float(r.usd), 2), "valor": str(r.dep)}
             for r in doc[doc.dep_roto].itertuples()]
    dep_doc = {}
    for r, g in doc[~doc.dep_roto].groupby("ruc"):
        d = str(g.dep.iloc[0]).strip()
        dep_doc[r] = ALIAS_DEP.get(k(d), d.upper())
    cli["dep"] = [
        (str(ubic.dep.get(r)).upper()
         if r in ubic.index and pd.notna(ubic.dep.get(r))
         else dep_doc.get(r, "")) for r in cli.ruc]
    # Lo que de verdad quedó sin sitio: ni el padrón lo ubica ni su documento
    # trae un departamento legible. Es distinto de «el documento venía roto»,
    # porque a uno de esos el padrón sí lo salva.
    sin_sitio = cli[cli.dep == ""]
    cli["tipo"] = cli.ruc.str[:2].map({"10": "persona natural",
                                       "20": "empresa"}).fillna("otro")

    TOT = float(cli.usd.sum())
    por_tipo = [{"tipo": t, "clientes": int(len(g)),
                 "usd": round(float(g.usd.sum()), 2),
                 "pct": round(100 * float(g.usd.sum()) / TOT, 1)}
                for t, g in cli.groupby("tipo")]

    # --- qué hay al lado, departamento por departamento -------------------
    # Los cortes de la canasta vienen con el nombre del departamento tal como
    # lo escribe MIDAGRI —«Piura»— y aquí el departamento va en mayúsculas
    # porque así lo trae el padrón. Se indexan por clave normalizada o el
    # cruce no encuentra nada y las tres líneas útiles desaparecen sin avisar.
    ins_reg = {k(a): b for a, b in can["insumo_por_region"].items()}
    mes_reg = {k(a): b for a, b in can["mes_por_region"].items()}
    cul_reg = {k(a): b for a, b in can["cultivo_por_region"].items()}
    reg_cob = {k(r["region"]): r for r in cob["regiones"]}
    # Los puntos reclutables no traen departamento en la lista corta, así que
    # se cuentan del archivo entero por hub y por región.
    rec_dep = {}
    for p in rec["lista"] + rec.get("en_espera", []):
        rec_dep.setdefault(k(p["dep"]), []).append(p)

    donde = []
    for dep, g in cli[cli.dep != ""].groupby("dep"):
        kd = k(dep)
        nom = next((r for r in can["por_region"] if k(r["n"]) == kd), None)
        cb = reg_cob.get(kd)
        cand = sorted(rec_dep.get(kd, []), key=lambda x: -x["margen_anual"])
        donde.append({
            "dep": dep,
            "clientes": int(len(g)),
            "usd": round(float(g.usd.sum()), 2),
            "pct_ingreso": round(100 * float(g.usd.sum()) / TOT, 1),
            "canasta_mm": nom["usd"] / 1e6 if nom else None,
            "cobertura_pct": cb["cubierto_pct"] if cb else None,
            "mes_pico": cb["mes_pico"] if cb else None,
            "insumos": [x["n"] for x in ins_reg.get(kd, [])[:3]],
            "meses": [x["n"] for x in mes_reg.get(kd, [])[:3]],
            "cultivos": [x["n"] for x in cul_reg.get(kd, [])[:3]],
            "reclutables": len(cand),
            "reclutables_top": [
                {"nombre": c["nombre"], "hub": c["hub"],
                 "margen_anual": c["margen_anual"],
                 "resurtible": c["resurtible"]} for c in cand[:5]],
        })
    donde.sort(key=lambda x: -x["usd"])

    salida = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "confidencial": ("lleva nombres de clientes y montos facturados: se "
                         "queda en out/ y no va al sitio ni al repositorio"),
        "motivo": ("dónde se vende hoy, qué dice la plataforma de esos sitios "
                   "y qué hay al lado para trabajar"),
        "tipo_de_cambio": TC,
        "periodo": {"desde": str(doc.fecha.min()), "hasta": str(doc.fecha.max())},
        "clientes": int(len(cli)),
        "usd": round(TOT, 2),
        "documentos": int(len(doc)),
        "en_padron": int(cli.en_padron.sum()),
        "fuera_del_padron": int((~cli.en_padron).sum()),
        "motivo_fuera": ("el padrón se filtra a empresas con razón social "
                         "agraria; una persona natural o una universidad no "
                         "puede estar ahí por construcción"),
        "por_tipo": por_tipo,
        "recompraron": int((cli.compras > 1).sum()),
        "pct_ingreso_recompra": round(
            100 * float(cli.loc[cli.compras > 1, "usd"].sum()) / TOT, 1),
        "documentos_dep_roto": rotos,
        "usd_dep_roto": round(sum(r["usd"] for r in rotos), 2),
        "clientes_sin_sitio": int(len(sin_sitio)),
        "usd_sin_sitio": round(float(sin_sitio.usd.sum()), 2),
        "donde": donde,
        "productos": [{"n": str(p), "usd": round(float(v), 2)}
                      for p, v in prod.head(15).items()],
        "productos_total": round(float(lin.usd.sum()), 2),
    }
    io.open(SALIDA, "w", encoding="utf-8").write(
        json.dumps(salida, ensure_ascii=False, indent=1))

    print("=" * 78)
    print("EL PUENTE  ·  %d clientes, US$ %s, %s a %s"
          % (len(cli), f"{TOT:,.0f}", salida["periodo"]["desde"],
             salida["periodo"]["hasta"]))
    print("=" * 78)
    print("en el padrón que la plataforma usa como cartera: %d de %d"
          % (salida["en_padron"], len(cli)))
    for t in por_tipo:
        print("  %-16s %2d clientes · US$ %8s · %4.1f%%"
              % (t["tipo"], t["clientes"], f"{t['usd']:,.0f}", t["pct"]))
    print("  recompraron %d, y son el %.0f%% del ingreso"
          % (salida["recompraron"], salida["pct_ingreso_recompra"]))
    print()
    print("dónde se vende, y qué dice la plataforma de ahí")
    for d in donde:
        cb = ("%.1f%%" % d["cobertura_pct"]) if d["cobertura_pct"] is not None \
            else "—"
        cm = ("US$ %.0f MM" % d["canasta_mm"]) if d["canasta_mm"] else "—"
        print("  %-14s US$ %8s (%4.1f%%) · canasta %-12s · cubierto %-7s · "
              "%d reclutables"
              % (d["dep"], f"{d['usd']:,.0f}", d["pct_ingreso"], cm, cb,
                 d["reclutables"]))
        if d["insumos"]:
            print("      se compra %s · pico %s · %s"
                  % (", ".join(d["insumos"]), ", ".join(d["meses"]),
                     ", ".join(d["cultivos"][:2])))
        for c in d["reclutables_top"][:3]:
            print("      al lado: %-40s %s  US$ %s/año"
                  % (c["nombre"][:40], c["hub"], f"{c['margen_anual']:,.0f}"))
    if rotos:
        print()
        print("%d documentos traen un número donde va el departamento "
              "(US$ %s): columna corrida en la planilla de origen"
              % (len(rotos), f"{salida['usd_dep_roto']:,.0f}"))
    if len(sin_sitio):
        print("clientes que quedan sin sitio —ni padrón ni documento—: "
              "%d, US$ %s (%.0f%% del ingreso)"
              % (len(sin_sitio), f"{salida['usd_sin_sitio']:,.0f}",
                 100 * salida["usd_sin_sitio"] / TOT))
        print("  no se les inventa un departamento")
    print()
    print("lo que se vende, con las dos monedas resueltas a US$ %.2f/S" % TC)
    for p in salida["productos"][:8]:
        print("  %-46s %8s" % (p["n"][:46], f"{p['usd']:,.0f}"))
    print("  —suman US$ %s contra US$ %s de los documentos—"
          % (f"{salida['productos_total']:,.0f}", f"{TOT:,.0f}"))
    print()
    print(SALIDA + "  (confidencial: no se publica)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
