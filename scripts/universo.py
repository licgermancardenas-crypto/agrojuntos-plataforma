# -*- coding: utf-8 -*-
"""Qué partida arancelaria cuenta como agroexportación, y por qué.

El proyecto arrancó con siete capítulos —07 hortalizas, 08 frutas, 09 café,
12 semillas, 18 cacao, 20 preparaciones y 21 preparaciones alimenticias—
porque son los que concentran el valor y los que un catálogo de insumos
reconoce sin discutir. El recorte se sostuvo hasta que hubo con qué medirlo:
MIDAGRI publicó **US$ 15,013 MM** de agroexportación en 2025 y esos siete
capítulos daban 13,230, un 12% menos. La diferencia no era de método sino de
universo, y este archivo la cierra.

`diag_universo.py` recorrió todos los manifiestos y midió, capítulo por
capítulo, qué quedaba fuera. Después se bajó a cuatro dígitos, porque a nivel
de capítulo la pregunta no tiene respuesta: el capítulo 23 son 2,126 MM de los
cuales 1,871 son harina de pescado, y el 15 son 802 de los cuales 518 son
aceite de pescado. Contarlos enteros habría inflado el agro con la pesca; no
contarlos habría perdido el aceite de palma, el alimento balanceado y el
salvado, que sí son agro.

De ahí la forma que tiene esta regla: **capítulos, menos una lista corta de
partidas que no pertenecen**.

## Lo que entra y no entraba

    23  alimento para animales      256 MM   sin la harina de pescado
    19  preparaciones de cereales   308 MM   galletas, fideos, panetón
    15  grasas y aceites            285 MM   sin el aceite de pescado
    10  cereales                    182 MM   quinua y kiwicha, sobre todo
    22  bebidas y alcohol           167 MM   alcohol etílico y pisco
    17  azúcares                     92 MM
    04  lácteos, huevos y miel       76 MM
    33  aceites esenciales           70 MM   sin perfumería ni cosmética
    14  materias trenzables          68 MM
    06  plantas vivas y flores       45 MM
    11  molinería                    35 MM
    13  gomas y resinas              16 MM   tara
    01 02 05 24 52 53                22 MM

## Lo que se deja fuera a propósito

**El capítulo 03 y el 16 enteros.** Pescado fresco y conservas: 433 MM que son
1604 y 1605, atún y conchas. El 1602 —preparaciones de carne, que sí sería
agro— no llega a un millón en el Perú, y meter el capítulo entero por él
costaría 433 MM de pesca.

**Las partidas 1504 y 2301.** Aceite y harina de pescado, 2,388 MM juntas. Son
las dos que hacían de sus capítulos algo distinto de lo que su nombre promete.
Una salvedad: 2301 incluye también harinas de carne, que serían agro; a seis
dígitos es 2301.20 lo que es pesca y 2301.10 lo que no, pero el resto del
proyecto agrupa a cuatro y no se va a cambiar por una fracción de punto.

**Perfumería y cosmética del capítulo 33.** El 3301 es aceite esencial de
limón y de eucalipto y es agro; el 3304 es maquillaje.

**Hilados y tejidos de los capítulos 52 y 53.** El algodón en rama es agro y
la tela es industria textil. En el Perú de 2025 esto es casi todo tela, así
que el capítulo aporta poco: se deja la regla correcta igual, porque la
composición puede cambiar y la definición no debería.

## Con qué cuadra

Con esta regla, 2025 da **US$ 14,852 MM** contra los 15,013 de MIDAGRI: 1.1%
por debajo, y del lado prudente. Esa cifra es el universo deduplicado pero sin
el filtro de precios imposibles; con él —que es lo que publica el sitio— queda
en 14,790, un 1.5%. Las dos son la misma medición vista antes y después de
`build_export_depurar.py`, y conviene no confundirlas. Lo que falta son diferencias de criterio que
no se pueden resolver desde el manifiesto —MIDAGRI ancla en regularización y
no en embarque, y arrastra rectificaciones posteriores al corte—, no capítulos
olvidados.

Lo importante es que **la cifra dejó de ser una elección tácita**. Antes el
12% de diferencia era una nota al pie; ahora el universo está escrito, medido
contra el oficial, y cada familia que entró se puede marcar como añadida.

Uso:
    from universo import es_agro, ampliada, CAPITULO
"""

# Los siete con que arrancó el proyecto. Se conservan nombrados porque la
# plataforma marca qué familias son de la ampliación y cuáles estaban desde el
# principio: un total que crece 12% de una semana a otra tiene que poder
# explicarse en la propia pantalla.
CAP_ORIGEN = {"07", "08", "09", "12", "18", "20", "21"}

CAPITULO = {
    "01": "Animales vivos", "02": "Carne", "04": "Lácteos, huevos y miel",
    "05": "Productos de origen animal", "06": "Plantas vivas y flores",
    "07": "Hortalizas", "08": "Frutas", "09": "Café, té y especias",
    "10": "Cereales", "11": "Molinería", "12": "Semillas y oleaginosas",
    "13": "Gomas y resinas", "14": "Materias trenzables",
    "15": "Grasas y aceites", "17": "Azúcares", "18": "Cacao",
    "19": "Preparaciones de cereales", "20": "Preparaciones de frutas y hortalizas",
    "21": "Preparaciones alimenticias", "22": "Bebidas y alcohol",
    "23": "Alimento para animales", "24": "Tabaco",
    "33": "Aceites esenciales", "52": "Algodón",
    "53": "Otras fibras vegetales",
}

CAP = set(CAPITULO)

# Partidas que caen en un capítulo agro y no son agro. La lista es corta a
# propósito: cada una está medida y justificada en el encabezado, y una
# excepción que no se pueda defender con una cifra no debería estar aquí.
FUERA = ({"1504", "2301"}
         | {"3303", "3304", "3305", "3306", "3307"}
         | {"52%02d" % n for n in range(4, 13)}
         | {"53%02d" % n for n in range(6, 12)})


def es_agro(partida):
    """¿Esta partida cuenta como agroexportación?

    Acepta la partida a cuatro o a diez dígitos. **Ojo con el cero inicial**:
    el DBF de SUNAT entrega los capítulos 01-09 sin él —la uva llega como
    806100000— y sin rellenar a la izquierda `[:2]` da «80» y se pierde el
    grueso del agro. Aquí se rellena, para que ningún llamador tenga que
    acordarse.
    """
    p = str(partida or "").strip()
    p = p.zfill(10) if len(p) > 4 else p.zfill(4)
    return p[:2] in CAP and p[:4] not in FUERA


def ampliada(partida):
    """¿Entró con la ampliación del universo, o estaba desde el principio?"""
    p = str(partida or "").strip()
    p = p.zfill(10) if len(p) > 4 else p.zfill(4)
    return es_agro(p) and p[:2] not in CAP_ORIGEN
