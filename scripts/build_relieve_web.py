# -*- coding: utf-8 -*-
"""Un sombreado de relieve del país entero, para el fondo del atlas web.

Las láminas impresas llevan relieve desde el principio y por una razón que vale
igual en pantalla: media plataforma discute el costo de servir una región
—horas al centro, sectores más allá de cuatro horas, el precio de una visita— y
sobre un mapa plano esos números son afirmaciones. Contra el relieve son
evidentes: la costa es una cinta de valles irrigados, la sierra es un muro, y
se ve por qué un valle merece una ruta y el de al lado no.

Reusa el mismo pipeline de las láminas —teselas Terrarium de AWS, que codifican
la altura en el RGB de un PNG— y el mismo sombreado de Horn, de modo que el
mapa de pantalla y el de papel se parecen porque son el mismo cálculo.

Diferencias con la lámina, todas por el medio:

  una sola imagen nacional y no una por departamento, porque el atlas hace
  zoom sobre un lienzo continuo y no imprime hojas sueltas.

  se guarda en JPEG. El relieve es una superficie suave sin bordes duros, que
  es justo lo que un compresor con pérdida hace bien: la versión sin pérdida
  pesa cinco veces más y en pantalla no se distingue.

  el mar no se borra en la imagen sino que el mapa recorta contra el contorno
  del país al dibujarla. Guardar la transparencia obligaría a PNG y a pagar
  esas cinco veces por un recorte que el lienzo hace gratis.

Uso:
    python scripts/build_relieve_web.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_relieve as R

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(os.path.join(RAIZ, "..", "..", "dashboard", "data"))

# El Perú continental con un margen que evita el borde duro en la costa.
PERU = (-81.6, -18.6, -68.4, 0.2)
ANCHO_MAX = 2048       # pixeles del lado mayor tras reducir
CALIDAD = 82


def main():
    os.makedirs(R.CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    print(f"mosaico z{R.Z} del pais...")
    dem, extent, faltan = R.mosaico(*PERU)
    print(f"  DEM {dem.shape[1]} x {dem.shape[0]} px · teselas ausentes: {faltan}")
    print(f"  extent lon {extent[0]:.3f}..{extent[1]:.3f} "
          f"lat {extent[2]:.3f}..{extent[3]:.3f}")

    # El mar llega como NaN y como cero. Se rellena con cero para que el
    # gradiente no propague NaN tierra adentro; el recorte lo tapa despues.
    mar = ~np.isfinite(dem)
    dem = np.nan_to_num(dem, nan=0.0)

    # Resolucion real de un pixel a la latitud media, que es lo que el
    # sombreado necesita para que la pendiente tenga sentido fisico.
    lat_media = (extent[2] + extent[3]) / 2
    res_m = (extent[1] - extent[0]) / dem.shape[1] * 111320 * \
        np.cos(np.radians(lat_media))
    print(f"  resolucion ~{res_m:.0f} m por pixel")

    # El sombreado de Horn solo, que en una lamina impresa a 130 dpi se lee
    # perfecto, en pantalla a escala nacional desaparece: la imagen se reduce
    # de 1463 px a unos 400 y el promediado se come las lineas finas de
    # pendiente, que es donde vive todo el contraste. Queda un mapa liso.
    #
    # Se le suma entonces una componente de altura. La pendiente dibuja el
    # valle y la altura dibuja la masa: la cordillera se oscurece como bloque y
    # sobrevive a cualquier reduccion, que es como se hace un relieve de
    # escala pequena desde que existen los mapas en relieve.
    sh = R.hillshade(dem, res_m) / 255.0
    alt = np.clip(dem / 4800.0, 0, 1) ** 0.75
    sombra = sh * (1.0 - 0.55 * alt)
    sombra[mar] = 1.0                   # el mar, plano y claro
    img = Image.fromarray((np.clip(sombra, 0, 1) * 255).astype(np.uint8),
                          mode="L")

    k = ANCHO_MAX / max(img.size)
    if k < 1:
        img = img.resize((max(1, round(img.width * k)),
                          max(1, round(img.height * k))), Image.LANCZOS)
    dst = os.path.join(OUT, "relieve.jpg")
    img.save(dst, "JPEG", quality=CALIDAD, optimize=True, progressive=True)

    meta = {"extent": [round(v, 6) for v in extent],
            "w": img.width, "h": img.height, "z": R.Z}
    with open(os.path.join(OUT, "relieve.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, separators=(",", ":"))

    print(f"relieve.jpg : {img.width} x {img.height} px · "
          f"{os.path.getsize(dst)/1024:,.0f} KB")


if __name__ == "__main__":
    main()
