# -*- coding: utf-8 -*-
"""Qué se exporta del agro, desde qué región y por qué puerto.

El análisis de comercio exterior llegaba hasta la empresa: cuánto factura cada
agroexportador. Faltaba lo que de verdad se mueve —la palta, el arándano, el
café— y por dónde sale, que es lo que decide dónde conviene tener producto.

Tres campos del DBF de exportación que hasta ahora no se leían:

    CADU     aduana de salida. Es la operativa, no la más cercana en línea
             recta: dice por dónde embarca de verdad la carga.
    UBIGEO   ubigeo declarado. Resulta casi inservible: solo el 3% del FOB lo
             trae, así que el departamento se toma del padrón de SUNAT por
             RUC. Eso es domicilio fiscal, no lugar de cultivo —las grandes
             declaran en Lima y siembran en otra región—, y así se dice.
    DCOM     descripción comercial de la mercancía, que nombra el producto
             cuando la partida arancelaria sola no basta.

La partida se agrupa a cuatro dígitos: a diez hay cientos de variantes de la
misma fruta —fresca, seca, en trozos— y el nombre comercial se pierde en el
detalle.

Uso:
    python scripts/build_agroexport.py
"""
import collections
import csv
import glob
import os
import re
import unicodedata

from build_aduanas import abrir, leer_dbf, partida4

# Capítulos del arancel que son agro. Los mismos que usa build_aduanas.py, de
# modo que los totales de las dos vistas cuadran entre sí.
AGRO = {"07", "08", "09", "12", "18", "20", "21"}

CAMPOS = {"CADU", "UBIGEO", "PART_NANDI", "DCOM", "VFOBSERDOL", "VPESNET",
          "CPAIDES", "CVIATRA", "NDOC"}

# Nombre de partida a cuatro dígitos. Solo las que aparecen en la
# agroexportación peruana; el resto se queda con su código, que es preferible
# a inventarle un nombre.
PARTIDAS = {
    "0709": "Hortalizas frescas (espárrago y otras)", "0703": "Cebolla y ajo",
    "0710": "Hortalizas congeladas", "0712": "Hortalizas secas",
    "0713": "Legumbres secas", "0714": "Raíces y tubérculos",
    "0704": "Coles y brócoli", "0706": "Zanahoria y remolacha",
    "0708": "Legumbres frescas", "0702": "Tomate", "0707": "Pepino",
    "0705": "Lechuga", "0701": "Papa",
    "0804": "Palta, mango, dátil y piña", "0806": "Uva",
    "0810": "Arándano, fresa y otras bayas", "0805": "Cítricos",
    "0803": "Banano y plátano", "0808": "Manzana y pera",
    "0809": "Melocotón, cereza y ciruela", "0813": "Frutas secas",
    "0811": "Frutas congeladas", "0802": "Nueces", "0801": "Coco y castaña",
    "0807": "Melón y sandía", "0814": "Cortezas de cítricos",
    "0901": "Café", "0902": "Té", "0904": "Pimienta y ají",
    "0910": "Jengibre, cúrcuma y especias", "0908": "Nuez moscada",
    "0909": "Semillas de anís e hinojo", "0905": "Vainilla",
    "1202": "Maní", "1207": "Semillas oleaginosas",
    "1209": "Semillas para siembra", "1211": "Plantas para perfumería",
    "1212": "Algarroba y otros frutos", "1214": "Forrajes",
    "1201": "Soya", "1204": "Linaza", "1206": "Girasol", "1208": "Harinas",
    "1213": "Paja y cascabillo",
    "1801": "Cacao en grano", "1804": "Manteca de cacao",
    "1805": "Cacao en polvo", "1806": "Chocolate", "1803": "Pasta de cacao",
    "2005": "Hortalizas preparadas", "2008": "Frutas preparadas",
    "2009": "Jugos de fruta", "2007": "Mermeladas y purés",
    "2002": "Tomate preparado", "2001": "Conservas en vinagre",
    "2004": "Hortalizas congeladas preparadas", "2006": "Frutas confitadas",
    "2003": "Setas preparadas",
    "2101": "Extractos de café y té", "2106": "Preparaciones alimenticias",
    "2103": "Salsas y condimentos", "2102": "Levaduras",
    "2104": "Sopas y caldos", "2105": "Helados",
    "0711": "Hortalizas conservadas provisionalmente", "0903": "Mate",
    "0906": "Canela", "0907": "Clavo de olor", "1802": "Cáscara de cacao",
}

# Tabla 4 del Anexo 01 de SUNAT (RS 040-2022), mas la aduana de Chancay,
# codigo 370, habilitada el 21 de octubre de 2024 por la RS 000192-2024 y que
# el anexo de 2022 todavia no recoge. No se deducen del dato: un codigo mal
# atribuido convierte un puerto en otro.
ADUANAS = {
    "000": "Sede Central - Chucuito", "019": "Tumbes", "028": "Talara",
    "037": "Sullana", "046": "Paita", "055": "Chiclayo", "064": "Eten",
    "073": "Pacasmayo", "082": "Salaverry", "091": "Chimbote",
    "109": "Huacho", "118": "Marítima del Callao", "127": "Pisco",
    "136": "San Juan", "145": "Mollendo Matarani", "154": "Arequipa",
    "163": "Ilo", "172": "Tacna", "181": "Puno", "190": "Cusco",
    "217": "Pucallpa", "226": "Iquitos", "235": "Aérea del Callao",
    "244": "Postal de Lima", "253": "Puesto de control de Tarapoto",
    "262": "Desaguadero", "271": "Tarapoto", "280": "Puerto Maldonado",
    "299": "La Tina", "370": "Chancay",
    "884": "Dependencia ferroviaria Tacna", "893": "Dependencia postal Tacna",
    "901": "Oficina postal de Lince", "910": "Aduana postal Arequipa",
    "929": "Complejo fronterizo Santa Rosa Tacna",
    "938": "Terminal terrestre Tacna", "947": "Aeropuerto Tacna",
    "956": "Ceticos Tacna", "965": "Dependencia postal de Salaverry",
    "974": "Almacén Santa Anita",
}

# Departamento por los dos primeros dígitos del ubigeo del INEI.
DEP_UBIGEO = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa",
    "05": "Ayacucho", "06": "Cajamarca", "07": "Callao", "08": "Cusco",
    "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes",
    "25": "Ucayali",
}

VIA = {"1": "Marítima", "2": "Fluvial", "3": "Lacustre", "4": "Aérea",
       "5": "Postal", "6": "Ferroviaria", "7": "Carretera", "8": "Tubería",
       "9": "Cable", "0": "Otra"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()


def guardar(nombre, campos, filas):
    ruta = os.path.join("out", nombre)
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(f"  {nombre:26s} {len(filas):>6,} filas")


def dep_por_ruc():
    """Departamento del exportador segun el padron de SUNAT.

    El UBIGEO del propio DBF de exportacion viene vacio en el 97% del FOB, de
    modo que no sirve para repartir por region. El padron cubre a casi todos
    los exportadores, a costa de que la ubicacion sea la fiscal.
    """
    ruta = os.path.join("out", "comercio_exportadores.csv")
    if not os.path.exists(ruta):
        print("  aviso: sin comercio_exportadores.csv, no habra corte por "
              "departamento")
        return {}
    m = {}
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("dep") or "").strip()
            if d:
                m[r["ruc"].strip()] = d.title()
    return m


def main():
    DEP_RUC = dep_por_ruc()
    por_part = collections.defaultdict(
        lambda: {"fob": 0.0, "kg": 0.0, "rucs": set(), "dest": set(),
                 "desc": collections.Counter()})
    por_aduana = collections.defaultdict(
        lambda: {"fob": 0.0, "kg": 0.0, "rucs": set(), "part": collections.Counter(),
                 "via": collections.Counter()})
    por_dep = collections.defaultdict(
        lambda: {"fob": 0.0, "kg": 0.0, "rucs": set(), "part": collections.Counter()})
    dep_part = collections.defaultdict(lambda: {"fob": 0.0, "kg": 0.0})
    adu_part = collections.defaultdict(lambda: {"fob": 0.0, "kg": 0.0})

    archivos = sorted(glob.glob("data/aduanas/x*.zip"))
    if not archivos:
        raise SystemExit("no hay archivos de exportación en data/aduanas/")

    n_agro = 0
    for z in archivos:
        fh, nombre = abrir(z)
        for r in leer_dbf(fh, CAMPOS):
            p4 = partida4(r.get("PART_NANDI", ""))
            if p4[:2] not in AGRO:
                continue
            try:
                fob = float(r.get("VFOBSERDOL") or 0)
                kg = float(r.get("VPESNET") or 0)
            except ValueError:
                continue
            if fob <= 0:
                continue
            n_agro += 1

            ruc = (r.get("NDOC") or "").strip()
            adu = (r.get("CADU") or "").strip().zfill(3)
            ub = re.sub(r"\D", "", r.get("UBIGEO") or "").zfill(6)[:2]
            dep = DEP_RUC.get(ruc) or DEP_UBIGEO.get(ub, "")
            via = VIA.get((r.get("CVIATRA") or "").strip()[-1:], "")
            dest = (r.get("CPAIDES") or "").strip()

            a = por_part[p4]
            a["fob"] += fob; a["kg"] += kg
            if ruc: a["rucs"].add(ruc)
            if dest: a["dest"].add(dest)
            d = norm(r.get("DCOM", ""))[:60]
            if d:
                a["desc"][d] += 1

            b = por_aduana[adu]
            b["fob"] += fob; b["kg"] += kg
            if ruc: b["rucs"].add(ruc)
            b["part"][p4] += fob
            if via: b["via"][via] += fob

            if dep:
                c = por_dep[dep]
                c["fob"] += fob; c["kg"] += kg
                if ruc: c["rucs"].add(ruc)
                c["part"][p4] += fob
                k = dep_part[(dep, p4)]
                k["fob"] += fob; k["kg"] += kg
            k = adu_part[(adu, p4)]
            k["fob"] += fob; k["kg"] += kg
        fh.close()
        print(f"  leido {os.path.basename(z)}")

    def nom(p4):
        return PARTIDAS.get(p4, "Partida " + p4)

    def adu(c):
        return ADUANAS.get(c, "Aduana " + c)

    guardar("agroexport_producto.csv",
            ["partida4", "producto", "fob_usd", "kg", "empresas", "destinos",
             "descripcion"],
            [{"partida4": p, "producto": nom(p), "fob_usd": round(v["fob"], 2),
              "kg": round(v["kg"], 1), "empresas": len(v["rucs"]),
              "destinos": len(v["dest"]),
              "descripcion": v["desc"].most_common(1)[0][0] if v["desc"] else ""}
             for p, v in sorted(por_part.items(),
                                key=lambda x: -x[1]["fob"])])

    guardar("agroexport_aduana.csv",
            ["codigo", "aduana", "fob_usd", "kg", "empresas", "producto_lider",
             "pct_lider", "via_principal"],
            [{"codigo": a, "aduana": adu(a), "fob_usd": round(v["fob"], 2), "kg": round(v["kg"], 1),
              "empresas": len(v["rucs"]),
              "producto_lider": nom(v["part"].most_common(1)[0][0])
              if v["part"] else "",
              "pct_lider": round(100 * v["part"].most_common(1)[0][1] / v["fob"], 1)
              if v["part"] and v["fob"] else 0,
              "via_principal": v["via"].most_common(1)[0][0] if v["via"] else ""}
             for a, v in sorted(por_aduana.items(), key=lambda x: -x[1]["fob"])])

    guardar("agroexport_departamento.csv",
            ["dep", "fob_usd", "kg", "empresas", "producto_lider", "pct_lider"],
            [{"dep": d, "fob_usd": round(v["fob"], 2), "kg": round(v["kg"], 1),
              "empresas": len(v["rucs"]),
              "producto_lider": nom(v["part"].most_common(1)[0][0])
              if v["part"] else "",
              "pct_lider": round(100 * v["part"].most_common(1)[0][1] / v["fob"], 1)
              if v["part"] and v["fob"] else 0}
             for d, v in sorted(por_dep.items(), key=lambda x: -x[1]["fob"])])

    guardar("agroexport_dep_producto.csv",
            ["dep", "partida4", "producto", "fob_usd", "kg"],
            [{"dep": d, "partida4": p, "producto": nom(p),
              "fob_usd": round(v["fob"], 2), "kg": round(v["kg"], 1)}
             for (d, p), v in sorted(dep_part.items(), key=lambda x: -x[1]["fob"])])

    guardar("agroexport_aduana_producto.csv",
            ["codigo", "aduana", "partida4", "producto", "fob_usd", "kg"],
            [{"codigo": a, "aduana": adu(a), "partida4": p, "producto": nom(p),
              "fob_usd": round(v["fob"], 2), "kg": round(v["kg"], 1)}
             for (a, p), v in sorted(adu_part.items(), key=lambda x: -x[1]["fob"])])

    total = sum(v["fob"] for v in por_part.values())
    print()
    print(f"lineas agro          : {n_agro:,}")
    print(f"FOB agro             : US$ {total/1e6:,.1f} MM en 10 semanas")
    print(f"partidas             : {len(por_part)}")
    print(f"aduanas              : {len(por_aduana)}")
    print(f"departamentos        : {len(por_dep)}")
    cub = sum(v["fob"] for v in por_dep.values())
    print(f"FOB con departamento : {100*cub/total:.1f}% "
          f"(padron por RUC; el UBIGEO del DBF solo cubre el 3%)")
    sin_nombre = [p for p in por_part if p not in PARTIDAS]
    if sin_nombre:
        print(f"partidas sin nombre  : {len(sin_nombre)} -> "
              f"{', '.join(sorted(sin_nombre)[:12])}")
    sin_adu = [c for c in por_aduana if c not in ADUANAS]
    if sin_adu:
        print(f"aduanas sin nombre   : {', '.join(sorted(sin_adu))}")


if __name__ == "__main__":
    main()
