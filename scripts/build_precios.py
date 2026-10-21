# -*- coding: utf-8 -*-
"""Cuánto vale lo que vende el cliente, y cómo le va contra lo normal.

La plataforma sabía qué insumo compra un productor, para qué cultivo y en qué
mes, y no sabía nada del otro lado de su cuenta: cuánto le pagan por lo que
cosecha. Esa mitad la trae `SISAP_PERU`, que bajó doce años de precio diario
del Gran Mercado Mayorista de Lima desde EMMSA, que es quien lo opera.

Este script no calcula precios: los lee ya agregados y deflactados de
`SISAP_PERU/02_DATA_PROCESADA` y arma lo que la vista necesita.

    emmsa_precios_mensuales_reales.parquet   precio mensual por variedad,
                                             nominal y en soles de 2025
    cruce_insumos_precio.csv                 por cultivo de la canasta: mes de
                                             compra, mes caro, mes barato
    cruce_insumos_precio_detalle.csv         el gasto en insumo de cada cultivo,
                                             mes a mes, con su producto EMMSA

## Tres cifras por producto

**La serie anual**, en soles de 2025 para que doce años se puedan comparar,
de una sola variedad —la que más cotizó en los últimos cinco años—. 2013 y el
año en curso van marcados como parciales.

**El índice estacional**, con la misma fórmula del cruce —promedio del mes
sobre el promedio general, todas las variedades y todos los años— para que la
plataforma y el informe de SISAP digan lo mismo. Es nominal como el del cruce;
con la inflación peruana de estos años el sesgo entre enero y diciembre ronda
dos puntos, menos que la amplitud de cualquier cultivo con temporada.

**Contra lo normal**: los últimos doce meses con precio real, contra los mismos
meses calendario de los cinco años anteriores, variedad contra variedad. Es la
pregunta del comercial —¿a este cliente le está yendo mejor o peor que de
costumbre?— y se contesta en soles constantes, porque en nominales todo
«sube».

## Lo que esto no es

**No es el precio en chacra.** Es mayorista en Lima: entre uno y otro hay
flete, merma e intermediación. Sirve para saber cuándo un cultivo vale más y
si este año vale más que otros, no cuánto cobra el productor.

**No dice cuándo cobra el productor.** El mes de compra es el de siembra; el
de cosecha no está en ninguna de las dos bases, y deducirlo del precio se
probó y no se sostiene —el motivo está en la cabecera de
`SISAP_PERU/scripts/cruzar_agrojuntos.py`—.

**El índice estacional promedia variedades sin ponderar**, como el cruce. La
forma del año aguanta eso; un nivel o una variación, no —si EMMSA deja de
cotizar una variedad cara, el producto «baja» sin que nada haya bajado—, y por
eso la serie y la comparación no usan el promedio de producto.

Uso:
    python scripts/build_precios.py
"""
import io
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitio                                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

SISAP = os.path.join(sitio.RAIZ, "SISAP_PERU", "02_DATA_PROCESADA")
MENSUAL = os.path.join(SISAP, "emmsa_precios_mensuales_reales.parquet")
CRUCE = os.path.join(SISAP, "cruce_insumos_precio.csv")
DETALLE = os.path.join(SISAP, "cruce_insumos_precio_detalle.csv")

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set",
         "Oct", "Nov", "Dic"]
ANIOS_REF = 5        # años contra los que se mide «lo normal»

# Cajones de sastre de EMMSA: no son un cultivo y no se presentan como tal.
# Es la misma lista que deja fuera el cruce.
SIN_CULTIVO = {"HORTALIZAS CHINAS", "OTRAS FRUTAS", "OTROS PROD.AGRIC."}

# Emparejamientos del cruce que la plataforma no usa. El puente de SISAP los
# escribió a mano y se publicaron; al mirar las variedades no se sostienen.
# Van fuera con su motivo, y el motivo viaja al sitio.
NO_EMPAREJA = {
    "Amilac": ("En EMMSA «maíz» es maíz morado y su coronta: ninguna "
               "variedad de amiláceo se cotiza en Lima desde 2020. Darle el "
               "precio del morado le atribuía una subida que es de otro grano."),
}

# EMMSA escribe en mayúsculas sin tildes. Lo que se lee en pantalla va con su
# ortografía; la clave sigue siendo el nombre de EMMSA, que es el que cruza.
ORTOGRAFIA = {
    "AJI": "Ají", "ALCACHOFA": "Alcachofa", "APIO": "Apio",
    "BETERRAGA": "Beterraga", "BROCOLI": "Brócoli", "CAIGUA": "Caigua",
    "CAMOTE": "Camote", "CEBOLLA": "Cebolla", "CHOCLO": "Choclo",
    "COLIFLOR": "Coliflor", "ESPARRAGO": "Espárrago", "FREJOL": "Frejol",
    "LIMON": "Limón", "MAIZ": "Maíz morado", "MANDARINA": "Mandarina",
    "MARACUYA": "Maracuyá", "MELON": "Melón", "PAPAYA": "Papaya",
    "PALTA": "Palta", "PAPA": "Papa", "PEPINILLO": "Pepinillo",
    "PIMIENTO": "Pimiento", "PLATANO": "Plátano", "RABANITO": "Rabanito",
    "SANDIA": "Sandía", "TOMATE": "Tomate", "ZANAHORIA": "Zanahoria",
    "ZAPALLO": "Zapallo", "OLLUCO": "Olluco", "OCA": "Oca",
    "ARVEJA": "Arveja", "HABA": "Haba", "PALLAR": "Pallar",
    "VAINITA": "Vainita", "LECHUGA": "Lechuga", "AJO": "Ajo",
    "PIÑA": "Piña", "PINA": "Piña", "UVA": "Uva", "MANGO": "Mango",
    "NARANJA": "Naranja", "MANZANA": "Manzana", "FRESA": "Fresa",
    "YUCA": "Yuca", "PORO": "Poro", "NABO": "Nabo", "COL": "Col",
    "ESPINACA": "Espinaca", "ACELGA": "Acelga", "CULANTRO": "Culantro",
    "PEREJIL": "Perejil", "HUACATAY": "Huacatay", "ORÉGANO": "Orégano",
    "OREGANO": "Orégano", "MELOCOTON": "Melocotón", "GRANADILLA": "Granadilla",
    "TUNA": "Tuna", "PERA": "Pera", "LUCUMA": "Lúcuma", "CHIRIMOYA": "Chirimoya",
    "CARAMBOLA": "Carambola", "COCO": "Coco", "AGUAYMANTO": "Aguaymanto",
    "MASHUA": "Mashua", "ALBAHACA": "Albahaca", "HIERBA BUENA": "Hierba buena",
    "TORONJA": "Toronja", "KION": "Kion", "ARANDANO": "Arándano",
}


def _nombres_de_cultivo():
    """La tabla de nombres de `build_cultivos.py`, leída sin ejecutarlo.

    El cultivo llega comprimido —«arvejags», «limond»— y esa tabla es la que
    ya usa el resto del sitio. Importar el módulo correría el script entero,
    así que se lee el literal; copiarla aquí la dejaría divergir."""
    import ast
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "build_cultivos.py"), encoding="utf-8").read()
    for nodo in ast.parse(src).body:
        if (isinstance(nodo, ast.Assign)
                and getattr(nodo.targets[0], "id", "") == "NOMBRES"):
            return ast.literal_eval(nodo.value)
    return {}


NOMBRES = _nombres_de_cultivo()


def cultivo(c):
    if c in NOMBRES:
        return NOMBRES[c]
    c = c.replace("_", " ").strip()
    return c[:1].upper() + c[1:]


def bonito(p):
    p = " ".join(str(p).split())
    return ORTOGRAFIA.get(p, p.capitalize())


def r1(v):
    return None if pd.isna(v) else round(float(v), 1)


def r2(v):
    return None if pd.isna(v) else round(float(v), 2)


def main():
    if not sitio.existe():
        sys.exit("No encuentro el sitio en %s" % sitio.DASHBOARD)
    for p in (MENSUAL, CRUCE, DETALLE):
        if not os.path.exists(p):
            sys.exit("Falta %s\nSe genera en SISAP_PERU: ver su README." % p)

    m = pd.read_parquet(MENSUAL)
    m["producto"] = m.producto.map(lambda s: " ".join(str(s).split()))
    m = m[~m.producto.isin(SIN_CULTIVO)]
    con = m.dropna(subset=["precio_promedio"]).copy()
    con["per"] = con.anio * 12 + con.mes_num - 1       # mes como entero

    # El mes en curso entra en la serie pero no en la comparación: con diez
    # días cotizados, un mes no es un mes. EMMSA publica también los domingos
    # repitiendo el sábado, así que la cobertura no sirve para detectarlo; el
    # calendario sí.
    hoy = datetime.now(timezone.utc)
    per_hoy = hoy.year * 12 + hoy.month - 1
    ult_per = int(con.per.max())
    en_curso = ult_per >= per_hoy
    ult_cerrado = ult_per - 1 if en_curso else ult_per
    anio_curso = ult_per // 12

    # Ventana de «contra lo normal»: termina en el último mes cerrado que tenga
    # precio real. El IPC del INEI llega con un mes de atraso y sin él no hay
    # soles de 2025.
    real = con.dropna(subset=["precio_promedio_real"])
    fin_real = int(real[real.per <= ult_cerrado].per.max())
    ventana = list(range(fin_real - 11, fin_real + 1))

    # Precio de producto por mes: promedio simple de sus variedades. Es la
    # definición del cruce, y la salvedad está en la cabecera.
    pm = (con.groupby(["producto", "per", "anio", "mes_num"], as_index=False)
             .agg(nom=("precio_promedio", "mean"),
                  real=("precio_promedio_real", "mean"),
                  var=("variedad", "nunique")))

    cruce = pd.read_csv(CRUCE)
    det = pd.read_csv(DETALLE)
    det["producto_emmsa"] = det.producto_emmsa.map(lambda s: " ".join(str(s).split()))
    cruce["producto_emmsa"] = cruce.producto_emmsa.map(lambda s: " ".join(str(s).split()))
    fuera = cruce[cruce.cultivo.isin(NO_EMPAREJA)]
    cruce = cruce[~cruce.cultivo.isin(NO_EMPAREJA)]
    det = det[~det.cultivo.isin(NO_EMPAREJA)]
    compra = det.groupby(["producto_emmsa", "mes"]).usd.sum()

    productos = []
    for prod, g in pm.groupby("producto"):
        g = g.sort_values("per")
        base = con[con.producto == prod]

        # Índice estacional: la fórmula del cruce, sobre las filas de variedad.
        gen = base.precio_promedio.mean()
        idx_mes = base.groupby("mes_num").precio_promedio.mean() / gen * 100
        idx = [r1(idx_mes.get(i)) for i in range(1, 13)]

        # La serie anual es la de UNA variedad, no el promedio del producto.
        # El promedio cambia de composición de un año a otro —EMMSA deja de
        # cotizar una variedad, empieza otra— y con eso se mueve sin que el
        # precio se haya movido. La de referencia es la que más meses cotizó
        # en los últimos cinco años, y la vista dice cuál es.
        rv = base.dropna(subset=["precio_promedio_real"])
        recientes = rv[rv.per > fin_real - 12 * ANIOS_REF]
        ref_var = (recientes if len(recientes) else rv).groupby("variedad").per.nunique()
        ref_var = ref_var.idxmax() if len(ref_var) else None
        # Parcial no es «menos de doce meses»: el mango Kent no se vende todo
        # el año, y con esa regla salían rayados once de sus trece años. Es
        # parcial el primer año, el año en curso, y el que cotizó claramente
        # menos meses de lo habitual en esa variedad.
        anual = []
        if ref_var is not None:
            gv = rv[rv.variedad == ref_var]
            meses = gv.groupby("anio").mes_num.nunique()
            habitual = meses.median()
            for a, ga in gv.groupby("anio"):
                n = int(meses[a])
                anual.append({"a": int(a), "v": r2(ga.precio_promedio_real.mean()),
                              "meses": n,
                              "parcial": bool(a == anio_curso or a == meses.index.min()
                                              or n < habitual - 2)})

        # Contra lo normal, variedad contra variedad: cada variedad en cada mes
        # de la ventana contra la misma variedad en el mismo mes de los cinco
        # años anteriores. Comparar el promedio del producto daba el tomate a
        # +16% y emparejado da −4%: el signo lo ponía la mezcla, no el precio.
        # Hace falta al menos 3 de los 5 años de referencia por par, y pares en
        # al menos 9 de los 12 meses; con menos, son meses sueltos.
        sv = rv.set_index(["variedad", "per"]).precio_promedio_real
        hoy_v = ref_v = 0.0
        n_pares, meses_ok = 0, set()
        for (var, p), x in sv.items():
            if p < ventana[0] or p > ventana[-1]:
                continue
            ref = [sv.get((var, p - 12 * k)) for k in range(1, ANIOS_REF + 1)]
            ref = [y for y in ref if y is not None and not pd.isna(y)]
            if len(ref) >= 3:
                hoy_v += x
                ref_v += sum(ref) / len(ref)
                n_pares += 1
                meses_ok.add(p)
        normal = None
        if len(meses_ok) >= 9:
            normal = {"dif": r1(100 * (hoy_v / ref_v - 1)),
                      "pares": n_pares, "meses": len(meses_ok)}

        ult = g.iloc[-1]
        cmp = None
        if prod in compra.index.get_level_values(0):
            c = compra.loc[prod]
            tot = c.sum()
            if tot > 0:
                cmp = [r1(100 * c.get(mm, 0) / tot) for mm in MESES]
        cul = cruce[cruce.producto_emmsa == prod]

        productos.append({
            "k": prod, "n": bonito(prod),
            "var": int(base.variedad.nunique()),
            "ref_var": " ".join(str(ref_var).split()).capitalize() if ref_var else None,
            "desde": "%d-%02d" % (g.per.min() // 12, g.per.min() % 12 + 1),
            "anual": anual, "idx": idx,
            "amp": r1(max(v for v in idx if v is not None)
                      - min(v for v in idx if v is not None)),
            "caro": MESES[int(idx_mes.idxmax()) - 1],
            "barato": MESES[int(idx_mes.idxmin()) - 1],
            "normal": normal,
            "ultimo": {"per": "%d-%02d" % (ult.per // 12, ult.per % 12 + 1),
                       "nom": r2(ult.nom), "real": r2(ult.real)},
            "compra": cmp,
            "cultivos": sorted(cultivo(c) for c in cul.cultivo),
            "usd_insumos": round(float(cul.usd_insumos.sum()), 0) if len(cul) else 0,
        })

    productos.sort(key=lambda p: (-p["usd_insumos"], p["n"]))

    # La tabla de cultivos de la canasta: el cruce tal cual, con la cifra de
    # «contra lo normal» de su producto al lado.
    por_k = {p["k"]: p for p in productos}
    cultivos = []
    for _, r in cruce.iterrows():
        p = por_k.get(r.producto_emmsa)
        cultivos.append({
            "c": cultivo(r.cultivo), "k": r.producto_emmsa,
            "p": p["n"] if p else bonito(r.producto_emmsa),
            "usd": round(float(r.usd_insumos), 0),
            "compra": r.mes_de_compra if isinstance(r.mes_de_compra, str) else "",
            "idx_compra": r1(r.indice_precio_ese_mes),
            "caro": r.mes_mas_caro, "barato": r.mes_mas_barato,
            "amp": r1(r.amplitud_estacional),
            "dif": p["normal"]["dif"] if p and p["normal"] else None,
        })

    # Qué parte del gasto en insumos de la canasta tiene precio de su cultivo.
    can = json.load(io.open(os.path.join(sitio.DATA, "canasta.json"),
                            encoding="utf-8"))
    usd_cruce = float(cruce.usd_insumos.sum())
    salida = {
        "generado": hoy.strftime("%Y-%m-%d"),
        "fuente": "EMMSA · Gran Mercado Mayorista de Lima",
        "unidad": "S/ por kg",
        "base_real": int(m.anio_base.dropna().iloc[0]),
        "desde": min(p["desde"] for p in productos),
        "hasta": "%d-%02d" % (ult_per // 12, ult_per % 12 + 1),
        "en_curso": bool(en_curso),
        "ventana": ["%d-%02d" % (ventana[0] // 12, ventana[0] % 12 + 1),
                    "%d-%02d" % (ventana[-1] // 12, ventana[-1] % 12 + 1)],
        "anios_ref": ANIOS_REF,
        "meses": MESES,
        "n_productos": len(productos),
        "n_variedades": int(con.variedad.nunique()),
        "cultivos_cruzados": len(cultivos),
        "usd_cruzado": round(usd_cruce, 0),
        "usd_canasta": round(float(can["usd_total"]), 0),
        "cobertura_pct": r1(100 * usd_cruce / float(can["usd_total"])),
        "productos": productos,
        "cultivos": cultivos,
        "fuera": [{"c": cultivo(r.cultivo), "k": r.producto_emmsa,
                   "usd": round(float(r.usd_insumos), 0),
                   "motivo": NO_EMPAREJA[r.cultivo]}
                  for _, r in fuera.iterrows()],
        "salvedad": ("Precio mayorista en Lima, no en chacra: entre uno y otro "
                     "hay flete, merma e intermediación. Sirve para saber "
                     "cuándo un cultivo vale más y si este año vale más que "
                     "otros, no cuánto cobra el productor."),
        "no_dice": ("El mes de compra es el de siembra. El de cosecha no está "
                    "en ninguna de las dos bases, y deducirlo del precio se "
                    "probó contra ocho calendarios conocidos y acertó en "
                    "cuatro: Lima recibe de muchas regiones a la vez, y el "
                    "mes barato no es la cosecha de nadie en particular."),
    }

    crudo = json.dumps(salida, ensure_ascii=False, indent=1)
    os.makedirs("out", exist_ok=True)
    io.open("out/precios.json", "w", encoding="utf-8").write(crudo)
    io.open(os.path.join(sitio.DATA, "precios.json"), "w",
            encoding="utf-8").write(crudo)

    print("=" * 78)
    print("PRECIOS MAYORISTAS  ·  %d productos, %s a %s%s"
          % (len(productos), salida["desde"], salida["hasta"],
             " (en curso)" if en_curso else ""))
    print("=" * 78)
    print("contra lo normal: %s a %s, contra los mismos meses de %d años"
          % (salida["ventana"][0], salida["ventana"][1], ANIOS_REF))
    print("la canasta con precio de su cultivo: %d cultivos, %.1f%% del gasto"
          % (len(cultivos), salida["cobertura_pct"]))
    print()
    print("los cultivos que más insumo compran, y cómo vale hoy lo que venden")
    for p in [x for x in productos if x["usd_insumos"] > 0][:12]:
        n = p["normal"]
        print("  %-12s US$ %6.1f MM  ·  %s  ·  caro %s, barato %s"
              % (p["n"], p["usd_insumos"] / 1e6,
                 ("%+5.1f%% vs lo normal" % n["dif"]) if n else "sin comparación",
                 p["caro"], p["barato"]))
    sin = [p["n"] for p in productos if not p["normal"]]
    if sin:
        print()
        print("sin comparación (pocos meses o pocos años): " + ", ".join(sin))


if __name__ == "__main__":
    main()
