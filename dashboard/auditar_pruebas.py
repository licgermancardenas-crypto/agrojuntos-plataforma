# -*- coding: utf-8 -*-
"""Comprueba que las pruebas de `verificar.py` sirvan para algo.

Una prueba que nunca vio fallar su defecto no es una prueba: es una línea que
pasa. Esto reintroduce, de a uno, defectos concretos en la página —los que
cada comprobación dice cubrir— y corre la suite entera contra cada uno.

  - Si aparece el mensaje que esa comprobación emite, la prueba **caza** el
    defecto y vale.
  - Si la suite pasa igual, o falla por cualquier otro motivo, la prueba es
    **vacua**: hay que rehacerla apuntando a lo que de verdad protege.

La distinción importa: que la suite se ponga roja no basta, porque puede
enrojecer por un daño colateral de la mutación mientras el agujero que
importaba sigue abierto.

Uso:
    python servir.py
    python auditar_pruebas.py           todas las mutaciones
    python auditar_pruebas.py sin_fob   una sola
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

# Cada mutación, con el mensaje que debe hacer saltar. El mensaje es el
# contrato: si cambia el texto de la comprobación, aquí hay que actualizarlo,
# y esa fricción es deliberada —son las frases que el informe promete—.
CASOS = [
    ("sin_fob", "FOB",
     "el panel deja de decir que la cifra es FOB importado y no venta"),
    ("sin_dias", "COBERTURA",
     "la nota vuelve a tapar los años a los que les faltan días"),
    ("sin_ytd", "YTD",
     "el año en curso se presenta como un año cerrado más"),
    ("serie_corta", "ANOS",
     "la serie dibuja un año menos de los pedidos"),
    ("anio_sin_dato_elegible", "SE PUEDE ELEGIR",
     "un año sin semanas descargadas se puede elegir como si tuviera dato"),
    ("sin_nota_escala", "ESCALA",
     "el gráfico de precio recorta la escala sin declararlo"),
    ("sin_29733", "29733",
     "deja de declararse lo reservado por la Ley 29733"),
    ("sin_kg", "KILO",
     "el precio deja de expresarse por kilo"),
    ("migas_cortas", "MIGAS",
     "las migas dejan de mostrar el camino recorrido"),
]


def corre(mut):
    env = dict(os.environ, MUTAR=mut, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "verificar.py"], env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    pedidos = sys.argv[1:]
    casos = [c for c in CASOS if not pedidos or c[0] in pedidos]
    if not casos:
        sys.exit("mutación desconocida · hay: "
                 + ", ".join(c[0] for c in CASOS))
    print("auditoría de las pruebas · %d defecto(s) reintroducido(s)\n"
          % len(casos))
    vacuas, buenas = [], []
    for mut, senal, que in casos:
        # Un «vacua» se confirma corriendo otra vez. Con la máquina
        # apretada el navegador tarda, la página no llega a pintar y la
        # comprobación mira un DOM vacío: eso da un falso vacuo, que es la
        # peor salida posible aquí, porque acusa a una prueba sana y lleva
        # a «arreglar» lo que no estaba roto.
        for intento in (1, 2):
            cod, salida = corre(mut)
            lineas = [l.strip() for l in salida.splitlines()
                      if l.strip().isupper() and len(l.strip()) > 8]
            cazado = any(senal in l for l in lineas)
            if cazado or intento == 2:
                break
            print("  %-24s no cazó; se reintenta por si fue la maquina"
                  % mut)
        print("  %-24s %s" % (mut, que))
        if cazado:
            buenas.append(mut)
            caza = next(l for l in lineas if senal in l)
            print("      CAZADO   %s" % caza[:96])
        else:
            vacuas.append(mut)
            estado = ("la suite pasó igual" if cod == 0
                      else "la suite falló, pero por otra cosa: "
                           + (lineas[0][:70] if lineas else "?"))
            print("      VACUA    %s" % estado)
        print()

    print("cazan su defecto : %d de %d" % (len(buenas), len(casos)))
    if vacuas:
        print("vacuas           : " + ", ".join(vacuas))
    return 1 if vacuas else 0


if __name__ == "__main__":
    sys.exit(main())
