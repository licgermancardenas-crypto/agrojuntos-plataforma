# -*- coding: utf-8 -*-
"""La razón social completa y bien escrita, para todo lo que va al sitio.

Los nombres llegaban al sitio con tres defectos, y ninguno era de cálculo:

    cortados en 40      el manifiesto de aduanas trae la razón social en un
                        campo de 40 caracteres. «LECHE GLORIA SOCIEDAD ANONIMA
                        - GLORIA S» no es un nombre: es el borde del campo.
                        710 exportadores y 206 importadores llegaban así.
    cortados en 70      ese corte era nuestro: `build_dashboard_data.py` hacía
                        `[:70]` sobre el padrón, que trae hasta 100. Además
                        cortaba en 60 la lista de importadores y en 44 la de
                        mayores importadores por categoría.
    la ñ en minúscula   «COMPAñIA», «DOñA». El padrón y el manifiesto escriben
                        la eñe en minúscula dentro de nombres en mayúsculas.

El primero se corrige con el padrón de SUNAT, que es la misma fuente con el
campo entero: `build_nombres_ruc.py` saca de él el nombre de cada RUC que el
sitio puede mostrar. Los otros dos se corrigen aquí. Cuando un nombre no cabe
en pantalla lo resuelve el CSS, que sabe cuánto espacio hay; recortar el dato
lo esconde también del CSV y del buscador.

Uso:
    from nombres import razon_social
    razon_social(ruc, nombre_de_la_fuente)
"""
import csv
import io
import os
import re

TABLA = "out/nombres_ruc.csv"
_PADRON = None

# Una minúscula que no sea la eñe delata un nombre escrito en caja mixta, y en
# ese caso la ñ minúscula es correcta y no se toca.
_MINUSCULA = re.compile(r"[a-záéíóúü]")


def _padron():
    global _PADRON
    if _PADRON is None:
        _PADRON = {}
        if os.path.exists(TABLA):
            with io.open(TABLA, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    _PADRON[r["ruc"]] = r["razon_social"]
    return _PADRON


def limpiar(nombre):
    n = " ".join(str(nombre).split())
    if "ñ" in n and not _MINUSCULA.search(n.replace("ñ", "")):
        n = n.replace("ñ", "Ñ")
    return n


def razon_social(ruc, nombre):
    """El nombre del padrón si lo hay; si no, el de la fuente. Limpio en los
    dos casos, y nunca recortado."""
    p = _padron().get(str(ruc))
    return limpiar(p if p else nombre)
