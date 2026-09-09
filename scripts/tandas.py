# -*- coding: utf-8 -*-
"""Leer un CSV grande en una máquina que no lo aguanta de una vez.

`read_csv` pide al sistema un bloque contiguo del tamaño del archivo antes de
convertir una sola columna. Al ampliar el universo arancelario,
`operaciones_limpias.csv` pasó de 562 a 719 MB y esa petición empezó a fallar
con **«Error tokenizing data. C error: out of memory»** en los dos scripts que
lo leen —el agregado y el panel—, en una máquina con unos 600 MB libres.

Leído en tandas el pico es el de una tanda. Lo que hay que cuidar es lo que
pasa al juntarlas, y es la razón de que esto sea un archivo y no dos líneas
repetidas:

  **Las categorías.** Cada tanda descubre sus propios valores, así que
  concatenarlas devolvería el texto a memoria para volver a codificarlo, que
  es justamente lo que se quería evitar. `union_categoricals` las une por
  código.

  **El orden de las categorías.** Y aquí está la trampa que costó una corrida
  entera: `union_categoricals` deja las categorías en el orden en que
  aparecieron, no ordenadas. El agregado hace `d.fecha.cat.as_ordered()` y
  después `.max()` para saber cuál es el último embarque; con las categorías
  en orden de aparición, `.max()` devolvió una fecha de 2021, el año en curso
  pasó a ser 2021 y la variación interanual se publicó como **+389%**. Sin el
  `sort_categories=True` de abajo, esto no es una optimización sino un
  generador de cifras falsas que no falla, que es peor.

Uso:
    from tandas import leer_en_tandas
    d = leer_en_tandas(ruta, {"ruc": "category", "fob_usd": "float64"})
"""
import numpy as np
import pandas as pd
from pandas.api.types import union_categoricals

TANDA = 200_000


def leer_en_tandas(path, cols, tanda=TANDA, encoding="utf-8-sig"):
    """El mismo DataFrame que daría `read_csv(path, usecols=cols, dtype=cols)`.

    `cols` es el diccionario columna -> tipo que se le pasaría a `read_csv`.
    Las columnas declaradas `category` se leen como texto en cada tanda, se
    categorizan ahí y se unen después con las categorías ordenadas.
    """
    crudo = {k: ("str" if v == "category" else v) for k, v in cols.items()}
    trozos = []
    for ch in pd.read_csv(path, encoding=encoding, usecols=list(cols),
                          dtype=crudo, chunksize=tanda, low_memory=False):
        for c, t in cols.items():
            if t == "category":
                ch[c] = ch[c].astype("category")
        trozos.append(ch)
    if not trozos:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in cols.items()})
    if len(trozos) == 1:
        return trozos[0]
    salida = {}
    for c, t in cols.items():
        if t == "category":
            salida[c] = union_categoricals([x[c] for x in trozos],
                                           sort_categories=True)
        else:
            salida[c] = np.concatenate([x[c].to_numpy() for x in trozos])
        # Se suelta la columna de cada tanda en cuanto está unida: si no, el
        # pico es el archivo entero dos veces y no se habría ganado nada.
        for x in trozos:
            del x[c]
    return pd.DataFrame(salida)
