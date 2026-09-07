# -*- coding: utf-8 -*-
"""Quién tiene planta de empaque certificada, y para qué mercado.

El manifiesto dice quién embarca y desde qué distrito. Lo que no dice es
quién tiene infraestructura de acopio y empaque **certificada**, que es lo que
distingue a un socio posible de una razón social. Eso lo publica SENASA, lista
por lista, por par producto–mercado de destino.

Dos advertencias sobre lo que estas listas son y no son.

**No sirven para ubicar.** Traen la región y nada más fino, y cruzarlas contra
el padrón de SUNAT para sacar la dirección devuelve el domicilio fiscal, no la
planta: Agrícola Pampa Baja figura en Arequipa según SENASA y en Ate según el
padrón. Aquí se usan como **atributo** —esta empresa tiene planta certificada
para tal mercado— y la ubicación la sigue poniendo el ubigeo del manifiesto.

**La mitad del catálogo mira al revés.** SENASA publica en el mismo sitio las
listas de establecimientos extranjeros autorizados a exportar *al* Perú
—manzanas de Chile, naranjas de Egipto—. Se filtran por el propio nombre de la
publicación: lo que diga «al Peru» o «desde <país>» no es oferta peruana.

Uso:
    python scripts/build_senasa.py
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

import pandas as pd

BASE = "https://www.gob.pe"
CRUDO = "data/senasa"
SALIDA = "out/senasa_establecimientos.csv"
CRUCE = "out/senasa_exportadores.csv"
EXPORTADORES = "data/exportaciones/processed/exportadores.json"

# Las publicaciones de oferta peruana. El resto del catálogo son
# establecimientos extranjeros autorizados a exportar al Perú.
PUBS = {
    "4372428": "arandano",
    "2829797": "palta",
    "5662555": "citricos",
    "1928779": "cebolla",
    "1705615": "cebolla",
    "2169220": "limon",
    "1715878": "citricos",
    "1732515": "granada",
    # El mango no aparece bajo «lista de lugares de produccion» sino como
    # «listas aprobadas para la exportacion»: buscar por el patrón de las
    # otras lo dejaba fuera. Trae códigos de LP y de planta de tratamiento
    # por temporada y mercado.
    "3651257": "mango",
}

# Uva y espárrago no tienen lista de establecimientos en este catálogo: de
# ellos SENASA publica solo los protocolos de trabajo por mercado, en PDF. Se
# comprobó publicación por publicación sobre las 672 del catálogo. No es que
# falten aquí: es que no existen como lista.
SIN_LISTA = ("uva", "esparrago")
AJENAS = re.compile(r"al-peru|desde-(uruguay|egipto|chile|china|espana|portugal)")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def pide(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def limpia(n):
    """Razón social comparable: sin forma societaria ni puntuación."""
    n = re.sub(r"[^A-Z0-9 ]", " ", str(n).upper())
    for suf in ("SAC", "S A C", "SA", "S A", "SRL", "S R L", "EIRL",
                "E I R L", "SAA", "S A A", "DEL PERU", "PERU"):
        n = re.sub(r"\b%s\b" % suf, " ", n)
    return " ".join(n.split())


def descargar():
    """Los XLSX de cada publicación, con su producto y su mercado."""
    os.makedirs(CRUDO, exist_ok=True)
    bajados = []
    for ident, producto in PUBS.items():
        try:
            html = pide("%s/institucion/senasa/informes-publicaciones/%s"
                        % (BASE, ident)).decode("utf-8", "replace")
        except Exception as e:
            print("  %s: no responde (%s)" % (ident, e))
            continue
        for url in sorted(set(re.findall(
                r'https://cdn\.www\.gob\.pe/uploads/document/file/[^"?]+\.xlsx',
                html))):
            nom = url.rsplit("/", 1)[-1]
            dest = os.path.join(CRUDO, nom)
            if not os.path.exists(dest):
                try:
                    with io.open(dest, "wb") as fh:
                        fh.write(pide(url))
                    time.sleep(1)
                except Exception as e:
                    print("  %s: %s" % (nom, e))
                    continue
            # El mercado de destino va en el nombre del archivo, que es lo
            # único que lo dice: la hoja no lo trae.
            mercado = re.sub(r"^\d+-", "", nom.rsplit(".", 1)[0])
            mercado = re.sub(r"lista-de-.*?(de-)?", "", mercado)
            bajados.append({"archivo": dest, "producto": producto,
                            "mercado": mercado[:60]})
    return bajados


def lee(fila):
    """Las filas de un XLSX de SENASA, venga como venga la cabecera."""
    out = []
    try:
        xl = pd.ExcelFile(fila["archivo"])
    except Exception:
        return out
    for hoja in xl.sheet_names:
        # El encabezado no está en la primera fila: hay un título arriba y la
        # cabecera real aparece dos o tres filas más abajo, distinto en cada
        # lista. Se busca la fila que menciona la región.
        crudo = xl.parse(hoja, header=None)
        cab = None
        for i in range(min(8, len(crudo))):
            vals = [str(v).upper() for v in crudo.iloc[i].tolist()]
            if any("REGION" in v or "REGIÓN" in v for v in vals):
                cab = i
                break
        if cab is None:
            continue
        d = xl.parse(hoja, header=cab)
        d.columns = [re.sub(r"\s+", " ", str(c).split("\n")[0]).strip().upper()
                     for c in d.columns]
        col_reg = next((c for c in d.columns if "REGION" in c or "REGIÓN" in c), None)
        # Cada lista nombra la columna a su manera —ENTERPRISE NAME,
        # COMPANY NAME, EMPRESA— y una sola variante sin contemplar deja la
        # lista entera fuera sin avisar: la de limón se perdía por eso.
        # Van tres variantes distintas del mismo campo —ENTERPRISE NAME,
        # COMPANY NAME, PACKINGHOUSE NAME— y cada una que falta se lleva una
        # lista entera en silencio: así se perdió la de limón primero y las
        # plantas de mango después. Se acepta cualquier columna de nombre que
        # no sea la del fundo, que es un dato distinto.
        col_nom = next((c for c in d.columns
                        if (any(t in c for t in ("ENTERPRISE", "COMPANY",
                                                 "EMPRESA", "RAZON",
                                                 "PACKINGHOUSE"))
                            or c.endswith("NAME") or "NOMBRE" in c)
                        and "ORCHARD" not in c and "FUNDO" not in c), None)
        col_cod = next((c for c in d.columns if "CODE" in c or "CODIGO" in c
                        or "CÓDIGO" in c), None)
        if not col_nom:
            continue
        h = hoja.upper()
        tipo = ("empacadora" if "PACK" in h or "EMPAC" in h
                else "lugar de produccion")
        for _, r in d.iterrows():
            nom = str(r.get(col_nom, "")).strip()
            if not nom or nom.lower() in ("nan", "none"):
                continue
            out.append({
                "producto": fila["producto"], "mercado": fila["mercado"],
                "tipo": tipo, "region": str(r.get(col_reg, "")).strip(),
                "codigo": str(r.get(col_cod, "")).strip(), "empresa": nom,
            })
    return out


def main():
    print("descargando listas de SENASA")
    archivos = descargar()
    print("  %d archivos" % len(archivos))
    filas = []
    for a in archivos:
        filas += lee(a)
    if not filas:
        sys.exit("no se pudo leer ninguna lista")
    d = pd.DataFrame(filas)
    d["k"] = d.empresa.map(limpia)
    d = d[d.k.str.len() > 3]
    d.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    # Qué productos cubre la capa, para que los textos no lo lleven escrito a
    # mano: al entrar el mango, el informe y la web decían «arándano, palta,
    # cítricos y limón» y ya no era verdad.
    with io.open("out/senasa_cobertura.json", "w", encoding="utf-8") as fh:
        json.dump({"productos": sorted(d.producto.unique().tolist()),
                   "sin_lista": list(SIN_LISTA)}, fh, ensure_ascii=False)

    emp = d.groupby("k").agg(
        empresa=("empresa", "first"),
        productos=("producto", lambda s: ", ".join(sorted(set(s)))),
        mercados=("mercado", lambda s: str(len(set(s)))),
        empacadoras=("tipo", lambda s: int((s == "empacadora").sum())),
        lugares=("tipo", lambda s: int((s == "lugar de produccion").sum())),
        regiones=("region", lambda s: ", ".join(sorted({x for x in s if x
                                                        and x != "nan"}))[:60]))

    # El cruce contra quien de verdad embarca: la lista sola no dice cuánto
    # pesa cada nombre, y el manifiesto no dice quién tiene planta.
    cruz = pd.DataFrame()
    if os.path.exists(EXPORTADORES):
        ex = json.load(io.open(EXPORTADORES, encoding="utf-8"))
        e = pd.DataFrame([{"ruc": k, "empresa_ruc": v["n"], "dep": v["dep"],
                           "fob": v["total"]["fob"],
                           "familia": v["familias"][0]["n"] if v["familias"] else ""}
                          for k, v in ex.items()])
        e["k"] = e.empresa_ruc.map(limpia)
        cruz = emp.reset_index().merge(e, on="k", how="left")
        cruz = cruz.sort_values("fob", ascending=False)
        cruz.to_csv(CRUCE, index=False, encoding="utf-8-sig")

    print("\nestablecimientos          : %s" % format(len(d), ","))
    print("empresas distintas        : %s" % format(len(emp), ","))
    print("  con planta de empaque   : %s" % format(int((emp.empacadoras > 0).sum()), ","))
    print("productos cubiertos       : %s" % ", ".join(sorted(d.producto.unique())))
    print("sin lista publicada       : %s  (solo protocolos, en PDF)"
          % ", ".join(SIN_LISTA))
    if len(cruz):
        con = cruz.ruc.notna()
        # Los dos universos responden preguntas distintas y mezclarlos da
        # un porcentaje que no significa nada: las empacadoras son
        # infraestructura de acopio —pocas, grandes, casi todas exportan—
        # y los lugares de producción son fundos certificados, casi todos
        # de personas naturales que embarcan a través de un tercero. Ese
        # fundo no es un socio logístico, pero sí es un comprador de
        # insumo con certificación encima.
        pack = cruz[cruz.empacadoras > 0]
        fundo = cruz[cruz.empacadoras == 0]
        print("")
        print("empacadoras (acopio)      : %d, de las que %d embarcan a su nombre"
              % (len(pack), int(pack.ruc.notna().sum())))
        print("lugares de producción     : %d, de los que %d embarcan a su nombre"
              % (len(fundo), int(fundo.ruc.notna().sum())))
        print("  el resto vende por medio de un tercero: son demanda de insumo, no socios logísticos")
        print("  FOB que representan   : US$ %s MM"
              % format(round(cruz[con].fob.sum() / 1e6), ","))
        print("\nlos mayores con planta certificada:")
        for _, r in cruz[con & (cruz.empacadoras > 0)].head(8).iterrows():
            print("  %-30s %6.0f MM  %-12s %s"
                  % (str(r.empresa)[:30], r.fob / 1e6, str(r.dep)[:12],
                     str(r.productos)[:26]))


if __name__ == "__main__":
    main()
