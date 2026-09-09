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

Cada caso levanta un Chrome y corre la suite entera, así que las trece
seguidas piden más memoria de la que suele haber libre: conviene ir por lotes
de dos o tres. Si el sistema queda apretado, la página no llega a pintar y una
prueba sana aparece como vacua —por eso cada «vacua» se reintenta antes de
reportarse, y aun así un lote más chico da resultados más fiables—.

Uso:
    python servir.py
    python auditar_pruebas.py sin_fob sin_dias   un lote
    python auditar_pruebas.py sin_fob            una sola
    python auditar_pruebas.py                    todas, si la máquina da
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
    # Segunda tanda: el defecto ya no está en el texto sino en las cifras.
    # Sirven para ver qué comprobaciones contrastan contra el dato y cuáles
    # solo cuentan casillas.
    ("cifras_infladas", "CIFRAS DEL PANEL",
     "las cifras del panel dejan de corresponder al agregado"),
    ("meses_en_blanco", "MENSUAL",
     "el gráfico mensual conserva sus doce casillas y pierde el contenido"),
    ("reparto_falso", "REPARTO",
     "el reparto por categoría deja de sumar cien"),
    ("ranking_desordenado", "NO ESTA ORDENADO",
     "el ranking deja de estar ordenado por valor"),
    # Tercera tanda: el control sigue ahí y se deja pulsar, pero no hace nada.
    ("filtro_territorio_muerto", "FILTRO DE TERRITORIO",
     "el filtro de territorio deja de filtrar"),
    ("busqueda_muerta", "BUSQUEDA",
     "la búsqueda del directorio deja de filtrar"),
    ("periodo_muerto", "PERIODO",
     "el selector de periodo deja de actuar sobre las cifras"),
    # Cuarta tanda: las vistas de acopio, recién añadidas.
    ("radio_invertido", "ALCANCE NO CRECE",
     "el alcance de cada centro deja de crecer con el radio"),
    ("sin_carga_huerfana", "NINGUN CENTRO ALCANZA",
     "se calla la carga que ningún centro alcanza"),
    ("sin_salvedad_partida", "SALVEDAD",
     "uva y espárrago dejan de declarar que su partida agrupa otras cosas"),
    # Quinta tanda: la mitad exportadora de Comercio, que dejo de extrapolarse,
    # y el bloque de cinco anos de la ficha de empresa.
    ("comercio_export_anualiza", "NO CUADRA CON EL AGREGADO",
     "la mitad exportadora de Comercio vuelve a anualizarse"),
    ("ficha_origen_sin_salvedad", "DOMICILIO FISCAL",
     "la ficha presenta el ubigeo del manifiesto como domicilio fiscal"),
    # Sexta tanda: el relieve, que hasta ahora era fondo de mapa y ahora entra
    # en el tiempo de viaje y en donde vive cada negocio.
    ("terreno_plano", "EL TERRENO NO APORTA NADA",
     "el desnivel deja de contar en el tiempo de viaje"),
    ("banda_al_nivel_del_mar", "EL CAFE SALE A",
     "cada producto sale a la altura del puerto y no del fundo"),
    ("red_sin_decision", "NO DISTINGUE LOS CENTROS PUESTOS POR DECISION",
     "el centro puesto por decisión se presenta como elegido por el algoritmo"),
    ("canal_sin_salvedad", "COBERTURA DE OSM ES UN TECHO",
     "el techo de lo que OSM mapea se presenta como abandono medido"),
    ("productos_anualiza", "NO SALE DEL AGREGADO MEDIDO",
     "la vista de productos vuelve a comer de la ventana de diez semanas"),
    # Septima tanda: el universo arancelario, que dejo de ser una eleccion
    # tacita y ahora sostiene un 13% del total medido.
    ("universo_sin_marca", "NO DECLARA LA AMPLIACION DEL UNIVERSO",
     "las familias que entraron al ampliar el universo dejan de marcarse"),
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
            # Un fallo no siempre viene en una linea toda en mayusculas:
            # varios mensajes mezclan el grito con el dato que lo motiva
            # —«las categorias suman 47.5% EL REPARTO NO...»—. Filtrar por
            # isupper() los descartaba y hacia pasar por vacuas a pruebas
            # que si cazaban. Se toma cualquier linea que no sea un «ok».
            lineas = [l.strip() for l in salida.splitlines()
                      if l.strip() and not l.rstrip().endswith("ok")]
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
