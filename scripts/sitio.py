# -*- coding: utf-8 -*-
"""Dónde vive el sitio publicado, que no es donde el pipeline venía escribiendo.

Hay dos árboles de dashboard en el disco y llevan meses divergiendo:

    AGRO EXPORTACIONES/dashboard/     el viejo. Su `app.js` se quedó en una
                                      versión de hace semanas —sin la vista de
                                      canal, sin la de pisos, sin la de red— y
                                      su `verificar.py` tiene la mitad de las
                                      comprobaciones. Pero **el pipeline seguía
                                      escribiendo aquí los JSON**.

    AGRO EXPORTACIONES/_repo/dashboard/   el que se versiona y el que Vercel
                                      publica. Aquí se editan `app.js`,
                                      `index.html` y `verificar.py`, y aquí
                                      llegaban los datos a mano.

Así que el sitio real se servía con datos copiados a mano desde el árbol
abandonado, y cuando la copia no se hacía, se publicaba lo de la corrida
anterior. Pasó: la vista de Importación anunció durante semanas «diez semanas,
junio a agosto de 2026» y `2,953,512 líneas por US$ 13,748 MM` sobre un archivo
que ya tenía 246 semanas y 58.6 millones de líneas. No fue un error de cálculo
—el cálculo estaba bien en `out/`— sino de reparto.

Este módulo deja **un solo destino**. Todo lo que el pipeline genera para el
sitio se escribe directamente donde el sitio lo lee, y el árbol viejo queda
inerte: se puede borrar cuando alguien confirme que no le cuelga nada.

La ruta se resuelve desde este archivo y no desde el directorio de trabajo,
porque los scripts se corren tanto desde `MAPEO/` como desde el repositorio.

Uso:
    from sitio import DATA, DATOS, DASHBOARD
"""
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> MAPEO -> AGRO JUNTOS -> AGRO EXPORTACIONES
RAIZ = os.path.abspath(os.path.join(_AQUI, "..", "..", ".."))
REPO = os.path.join(RAIZ, "_repo")

DASHBOARD = os.path.join(REPO, "dashboard")     # el sitio que Vercel publica
DATA = os.path.join(DASHBOARD, "data")          # los JSON que baja el navegador
DATOS = os.path.join(REPO, "datos")             # los CSV que se publican como dato
DOCS = os.path.join(REPO, "docs")               # el informe impreso


def existe():
    """¿Está el repositorio donde se espera?

    Si alguien mueve `MAPEO` de sitio, es preferible que el script lo diga a
    que escriba los JSON en un directorio recién creado que nadie sirve.
    """
    return os.path.isdir(DASHBOARD)
