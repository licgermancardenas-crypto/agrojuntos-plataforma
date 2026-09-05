# -*- coding: utf-8 -*-
"""Un perfil por empresa: qué compra afuera, a quién, cuándo y desde dónde.

El directorio decía el nombre, el RUC y dos cifras de FOB. Con eso no se
prepara una visita. Los manifiestos de aduanas tienen, línea por línea, la
partida, el peso, el país de origen y la descripción comercial que escribió el
propio declarante, y esa es la materia con la que se arma el perfil: qué
insumo entra, en qué cantidad, de qué origen y con qué continuidad.

La continuidad es el dato que no se ve en un total. Diez semanas de ventana
permiten distinguir al importador de flujo —presente casi todas— del que hizo
un despacho aislado, y a un canal de ventas eso le cambia la conversación.

Los perfiles se reparten en cien archivos por los dos últimos dígitos del RUC.
Uno por empresa serían 2,810 archivos en el repositorio para servir 2 KB cada
vez; uno solo pesaría 6 MB y habría que bajarlo entero para ver una empresa. La
partición deja cada consulta en unos 60 KB y el repositorio en cien archivos.

Uso:
    python scripts/build_perfiles.py
"""
import json
import os
import unicodedata
from collections import defaultdict

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(os.path.join(RAIZ, "..", "..", "dashboard", "data"))
DEST = os.path.join(OUT, "perfil")
os.makedirs(DEST, exist_ok=True)
# Las semanas salen de lo archivado y no de una constante: el historico
# crece cada vez que corre acumular_aduanas.py.
SEMANAS = None            # se fija abajo, cuando ya se leyeron las fuentes


def cap(s):
    s = " ".join(w.capitalize() for w in str(s).split())
    for a, b in (("De ", "de "), ("Del ", "del "), ("La ", "la "), ("Y ", "y ")):
        s = s.replace(" " + a, " " + b)
    return s


def sinac(s):
    return unicodedata.normalize("NFKD", str(s)).encode(
        "ascii", "ignore").decode().upper()


def leer(f, **k):
    return pd.read_csv("out/" + f, encoding="utf-8-sig", dtype={"ruc": str}, **k)


# ------------------------------------------------------------------ datos ---
ins = leer("aduanas_importaciones.csv")
ins["categoria"] = "insumos"
ins["glosa"] = ins["rubro"]
agro = leer("import_agro_lineas.csv")
agro = agro[agro["categoria"] != "referencia"]
# Las dos fuentes miden lo mismo desde reglas distintas: build_aduanas mira
# fertilizante y fitosanitario, build_import_categorias el resto del agro. No
# se solapan porque sus partidas son disjuntas, y juntas son la importacion
# agricola de la empresa.
COMUN = ["ruc", "razon_social", "categoria", "glosa", "partida", "fob_usd",
         "peso_kg", "pais_origen", "descripcion", "semana"]
imp = pd.concat([ins[COMUN], agro[COMUN]], ignore_index=True)

expr = leer("comercio_exportadores.csv")
# El manifiesto de exportacion es el del pais entero: trae mineria, textil y
# pesca. Solo interesa el detalle de los agroexportadores ya verificados por
# build_comercio, o el directorio se llenaria de empresas que no son del agro.
exp = leer("aduanas_exportaciones.csv")
exp = exp[exp["ruc"].isin(set(expr["ruc"]))]
emp = leer("empresas_agro_activas.csv")
car = leer("cartera_empresa.csv")
impr = leer("comercio_importadores.csv")

# El manifiesto nombra el pais con su codigo ISO. «NL» no le dice nada a un
# comercial; «Paises Bajos», si. Los codigos 1B y 1D son de SUNAT y no del
# estandar, asi que se dejan a la vista en vez de inventarles un nombre.
PAIS = {
    "AE": "Emiratos Árabes", "AG": "Antigua y Barbuda", "AO": "Angola",
    "AR": "Argentina", "AT": "Austria", "AU": "Australia", "AW": "Aruba",
    "BB": "Barbados", "BD": "Bangladés", "BE": "Bélgica", "BG": "Bulgaria",
    "BH": "Baréin", "BJ": "Benín", "BM": "Bermudas", "BO": "Bolivia",
    "BQ": "Caribe Neerlandés", "BR": "Brasil", "BS": "Bahamas",
    "BZ": "Belice", "CA": "Canadá", "CG": "Congo", "CH": "Suiza",
    "CI": "Costa de Marfil", "CL": "Chile", "CN": "China", "CO": "Colombia",
    "CR": "Costa Rica", "CU": "Cuba", "CV": "Cabo Verde", "CW": "Curazao",
    "CY": "Chipre", "CZ": "Chequia", "DE": "Alemania", "DK": "Dinamarca",
    "DM": "Dominica", "DO": "Rep. Dominicana", "DZ": "Argelia",
    "EC": "Ecuador", "EE": "Estonia", "EG": "Egipto", "ES": "España",
    "FI": "Finlandia", "FO": "Islas Feroe", "FR": "Francia",
    "GB": "Reino Unido", "GD": "Granada", "GE": "Georgia",
    "GF": "Guayana Francesa", "GH": "Ghana", "GM": "Gambia", "GN": "Guinea",
    "GP": "Guadalupe", "GR": "Grecia", "GT": "Guatemala", "GY": "Guyana",
    "HK": "Hong Kong", "HN": "Honduras", "HR": "Croacia", "HT": "Haití",
    "HU": "Hungría", "ID": "Indonesia", "IE": "Irlanda", "IL": "Israel",
    "IN": "India", "IR": "Irán", "IS": "Islandia", "IT": "Italia",
    "JM": "Jamaica", "JO": "Jordania", "JP": "Japón", "KE": "Kenia",
    "KG": "Kirguistán", "KH": "Camboya", "KN": "San Cristóbal y Nieves",
    "KP": "Corea del Norte", "KR": "Corea del Sur", "KW": "Kuwait",
    "KY": "Islas Caimán", "KZ": "Kazajistán", "LB": "Líbano",
    "LC": "Santa Lucía", "LK": "Sri Lanka", "LR": "Liberia",
    "LT": "Lituania", "LU": "Luxemburgo", "LV": "Letonia",
    "MA": "Marruecos", "MG": "Madagascar", "ML": "Malí",
    "MN": "Mongolia", "MQ": "Martinica", "MR": "Mauritania",
    "MU": "Mauricio", "MV": "Maldivas", "MX": "México", "MY": "Malasia",
    "MZ": "Mozambique", "NC": "Nueva Caledonia", "NG": "Nigeria",
    "NI": "Nicaragua", "NL": "Países Bajos", "NO": "Noruega",
    "NP": "Nepal", "NZ": "Nueva Zelanda", "OM": "Omán", "PA": "Panamá",
    "PE": "Perú", "PG": "Papúa Nueva Guinea", "PH": "Filipinas",
    "PK": "Pakistán", "PL": "Polonia", "PR": "Puerto Rico",
    "PT": "Portugal", "PY": "Paraguay", "QA": "Catar", "RO": "Rumanía",
    "RS": "Serbia", "RU": "Rusia", "SA": "Arabia Saudita", "SE": "Suecia",
    "SG": "Singapur", "SI": "Eslovenia", "SK": "Eslovaquia",
    "SL": "Sierra Leona", "SN": "Senegal", "SR": "Surinam",
    "SV": "El Salvador", "SX": "Sint Maarten", "SY": "Siria",
    "TG": "Togo", "TH": "Tailandia", "TN": "Túnez", "TR": "Turquía",
    "TT": "Trinidad y Tobago", "TW": "Taiwán", "TZ": "Tanzania",
    "UA": "Ucrania", "UG": "Uganda", "US": "Estados Unidos",
    "UY": "Uruguay", "UZ": "Uzbekistán", "VC": "San Vicente",
    "VE": "Venezuela", "VG": "Islas Vírgenes Br.", "VI": "Islas Vírgenes EE.UU.",
    "VN": "Vietnam", "ZA": "Sudáfrica", "ZM": "Zambia", "ZW": "Zimbabue",
}


def pais(c):
    c = str(c).strip().upper()
    return PAIS.get(c, c)


# La partida arancelaria de exportacion se muestra con el producto que nombra:
# «0804» no es legible, «Palta, mango, datil y pina» si.
PROD = {}
try:
    _pr = pd.read_csv("out/agroexport_producto.csv", encoding="utf-8-sig",
                      dtype={"partida4": str})
    PROD = dict(zip(_pr["partida4"], _pr["producto"]))
except FileNotFoundError:
    pass


def producto(part):
    p = str(part).zfill(10)
    n = PROD.get(p[:4])
    return f"{n} · {p[:4]}" if n else p


CAT = {"insumos": "Fertilizante y fitosanitario",
       "semillas": "Semillas y plantines",
       "maquinaria": "Maquinaria y equipos",
       "riego": "Riego y tecnología",
       "poscosecha": "Molienda y poscosecha",
       "ganaderia": "Ganadería y alimentos balanceados",
       "repuestos": "Repuestos y ferretería"}

CARD = car.set_index("ruc").to_dict("index")
EMPD = emp.set_index("ruc").to_dict("index")
EXPR = expr.set_index("ruc").to_dict("index")
IMPR = impr.set_index("ruc").to_dict("index")
NOMBRE = {}
for d in (imp, exp, emp):
    for r, n in zip(d["ruc"], d["razon_social"]):
        NOMBRE.setdefault(r, str(n))

SEMS = sorted(imp["semana"].dropna().unique())
SEMANAS = len(SEMS)


def top(df, campo, valor, n, extra=None):
    g = df.groupby(campo).agg(fob=(valor, "sum"), kg=("peso_kg", "sum"),
                              lineas=(valor, "size"))
    g = g.sort_values("fob", ascending=False).head(n)
    out = []
    for k, r in g.iterrows():
        d = {"n": str(k), "fob": round(float(r.fob), 2),
             "kg": round(float(r.kg), 1), "l": int(r.lineas)}
        if extra:
            d.update(extra(df[df[campo] == k]))
        out.append(d)
    return out


# Un filtro por RUC dentro del bucle recorre la tabla entera 22 mil veces. Se
# agrupa una sola vez y el bucle solo consulta el diccionario.
GI = dict(list(imp.groupby("ruc")))
GE = dict(list(exp.groupby("ruc")))

perfiles = defaultdict(dict)
rucs = sorted(set(emp["ruc"]) | set(imp["ruc"]) | set(expr["ruc"]))
VACIO = imp.iloc[0:0]
for ruc in rucs:
    if not isinstance(ruc, str) or not ruc.strip():
        continue
    gi = GI.get(ruc, VACIO)
    ge = GE.get(ruc, exp.iloc[0:0])
    car_r = CARD.get(ruc, {})
    emp_r = EMPD.get(ruc, {})
    # La ubicacion tambien esta en las tablas de comercio exterior, que traen
    # distrito, provincia y departamento del padron por RUC. Sin este respaldo,
    # una empresa que no clasifica como agro por su razon social —Perales
    # Huancaruna, el mayor exportador de cafe del pais— quedaba con la ficha
    # entera vacia aunque supieramos donde esta.
    ubi = EXPR.get(ruc) or IMPR.get(ruc) or {}
    p = {
        "ruc": ruc,
        "n": NOMBRE.get(ruc, ""),
        "clase": (car_r.get("clase") or emp_r.get("clase")
                  or ("agroexportador" if ruc in EXPR else
                      "importador" if ruc in IMPR else "")),
        "dep": cap(car_r.get("dep") or emp_r.get("dep") or ubi.get("dep") or ""),
        "prov": cap(car_r.get("provincia") or emp_r.get("provincia")
                    or ubi.get("provincia") or ""),
        "dist": cap(car_r.get("distrito") or emp_r.get("distrito")
                    or ubi.get("distrito") or ""),
        "dir": str(emp_r.get("direccion") or "")[:90],
        "estado": emp_r.get("estado") or "",
        "condicion": emp_r.get("condicion") or "",
        "padron": bool(emp_r),
    }
    if car_r.get("lat") == car_r.get("lat") and car_r.get("lat") is not None:
        p["lat"] = round(float(car_r["lat"]), 4)
        p["lon"] = round(float(car_r["lon"]), 4)
        p["ter"] = car_r.get("territorio") or ""
        p["rank"] = (int(car_r["rank"]) if car_r.get("rank") == car_r.get("rank")
                     and car_r.get("rank") is not None else -1)
        p["hub"] = car_r.get("hub") if isinstance(car_r.get("hub"), str) else ""
        h = car_r.get("horas_al_hub")
        p["h_hub"] = round(float(h), 1) if h == h and h is not None else None

    if len(gi):
        p["imp"] = {
            "fob": round(float(gi.fob_usd.sum()), 2),
            "kg": round(float(gi.peso_kg.sum()), 1),
            "lineas": int(len(gi)),
            "partidas": int(gi["partida"].nunique()),
            "semanas": int(gi["semana"].nunique()),
            "cats": [{"k": k, "n": CAT.get(k, k),
                      "fob": round(float(g.fob_usd.sum()), 2),
                      "kg": round(float(g.peso_kg.sum()), 1)}
                     for k, g in gi.groupby("categoria")],
            "glosas": top(gi, "glosa", "fob_usd", 8),
            "partidas_top": top(gi, "partida", "fob_usd", 10),
            "paises": [dict(x, n=pais(x["n"]))
                       for x in top(gi, "pais_origen", "fob_usd", 8)],
            "serie": [round(float(gi[gi.semana == s].fob_usd.sum()), 2)
                      for s in SEMS],
            # La descripcion comercial la escribe el declarante: es el detalle
            # mas fino que existe de que compro exactamente esta empresa.
            "desc": [{"d": str(r["descripcion"])[:70],
                      "fob": round(float(r["fob_usd"]), 2),
                      "kg": round(float(r["peso_kg"]), 1),
                      "p": str(r["partida"]), "o": pais(r["pais_origen"])}
                     for _, r in gi.nlargest(12, "fob_usd").iterrows()],
        }
    if len(ge):
        ex = EXPR.get(ruc, {})
        p["exp"] = {
            "fob": round(float(ge.fob_usd.sum()), 2),
            "kg": round(float(ge.peso_kg.sum()), 1),
            "lineas": int(len(ge)),
            "partidas": int(ge["partida"].nunique()),
            "destinos": int(ge["pais_destino"].nunique()),
            "semanas": int(ge["semana"].nunique()) if "semana" in ge else 0,
            "partidas_top": [dict(x, n=producto(x["n"]))
                             for x in top(ge, "partida", "fob_usd", 10)],
            "paises": [dict(x, n=pais(x["n"]))
                       for x in top(ge, "pais_destino", "fob_usd", 10)],
        }
        if ex:
            p["exp"]["fob_anual"] = round(float(ex.get("fob_anual", 0)), 2)
    elif ruc in EXPR:
        ex = EXPR[ruc]
        p["exp"] = {"fob": round(float(ex.get("fob", 0)), 2),
                    "kg": round(float(ex.get("tn", 0)) * 1000, 1),
                    "destinos": int(ex.get("destinos", 0)),
                    "semanas": int(ex.get("semanas", 0)),
                    "fob_anual": round(float(ex.get("fob_anual", 0)), 2),
                    "partidas_top": [], "paises": [], "lineas": 0,
                    "partidas": 0}
    if ruc in IMPR:
        p["rubro"] = IMPR[ruc].get("rubro", "")
    perfiles[ruc[-2:] if len(ruc) >= 2 else "00"][ruc] = p

total = 0
for grupo, cont in sorted(perfiles.items()):
    with open(os.path.join(DEST, f"{grupo}.json"), "w", encoding="utf-8") as fh:
        json.dump(cont, fh, separators=(",", ":"), ensure_ascii=False,
                  allow_nan=False)
    total += len(cont)

# El mapa localizador del perfil necesita el contorno del pais y el del
# departamento. Va simplificado a mano gruesa: es un mapa de 300 px donde un
# vertice cada dos kilometros no se distingue de uno cada doscientos metros, y
# la diferencia entre uno y otro es todo el peso del archivo.
import geopandas as gpd

dep_min = gpd.read_file("data/peru_departamental_simple.geojson").to_crs(4326)
dep_min["geometry"] = dep_min.geometry.buffer(0).simplify(
    0.02, preserve_topology=True)


def anillos_min(g):
    out = []
    for poly in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
        if poly.is_empty:
            continue
        c = [[round(x, 2), round(y, 2)] for x, y in poly.exterior.coords]
        if len(c) >= 4:
            out.append(c)
    return out


geo = [{"n": r["NOMBDEP"], "k": sinac(r["NOMBDEP"]),
        "r": anillos_min(r.geometry)}
       for _, r in dep_min.iterrows()]
geo = [g for g in geo if g["r"]]
with open(os.path.join(OUT, "geo_min.json"), "w", encoding="utf-8") as fh:
    json.dump(geo, fh, separators=(",", ":"), ensure_ascii=False)
print(f"  geo_min.json    : {os.path.getsize(os.path.join(OUT,'geo_min.json'))/1024:,.0f} KB"
      f" · {len(geo)} departamentos")

# El indice no lleva la lista de RUC: el directorio ya los tiene todos y
# repetirlos costaba 300 KB en cada carga del sitio.
idx = {"semanas": SEMANAS, "sems": SEMS, "cats": CAT,
       "perfiles": sum(len(g) for g in perfiles.values())}
with open(os.path.join(OUT, "perfil_idx.json"), "w", encoding="utf-8") as fh:
    json.dump(idx, fh, separators=(",", ":"), ensure_ascii=False)

pesos = [os.path.getsize(os.path.join(DEST, f)) for f in os.listdir(DEST)]
print(f"perfiles       : {total:,} empresas en {len(pesos)} archivos")
print(f"  con importacion : {sum(1 for g in perfiles.values() for p in g.values() if 'imp' in p):,}")
print(f"  con exportacion : {sum(1 for g in perfiles.values() for p in g.values() if 'exp' in p):,}")
print(f"  ubicadas        : {sum(1 for g in perfiles.values() for p in g.values() if 'lat' in p):,}")
print(f"  en el padron    : {sum(1 for g in perfiles.values() for p in g.values() if p['padron']):,}")
print(f"  peso            : {sum(pesos)/1e6:.2f} MB · mediana "
      f"{sorted(pesos)[len(pesos)//2]/1024:,.0f} KB por archivo")
print(f"  indice          : {os.path.getsize(os.path.join(OUT,'perfil_idx.json'))/1024:,.0f} KB")
