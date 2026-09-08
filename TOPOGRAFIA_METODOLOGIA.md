# Topografía · metodología

Qué hace el proyecto con el relieve, qué decide cada criterio y qué no aguanta
el dato. Hermano de
[`AGROEXPORTACION_METODOLOGIA.md`](AGROEXPORTACION_METODOLOGIA.md) y de
[`IMPORTADORES_INSUMOS_METODOLOGIA.md`](IMPORTADORES_INSUMOS_METODOLOGIA.md).

---

## De dónde sale la altura

El proyecto ya bajaba teselas **Terrarium** del bucket público
`elevation-tiles-prod` de AWS para sombrear los mapas: la altura viene
codificada en el RGB de un PNG, `h = R·256 + G + B/256 − 32768`. Estaban en
disco desde el principio y se usaban solo como dibujo.

`cota.py` las lee como dato. Zoom 9, unos **299 m por píxel** a esta latitud,
con interpolación bilineal entre los cuatro píxeles vecinos —sin interpolar,
dos fincas del mismo valle a 200 m una de otra caían en el mismo píxel y salían
con la misma cota exacta, que es una precisión que el dato no tiene—.

### Cuánto se equivoca

No se supone: se mide. `python scripts/cota.py` muestrea veinte altitudes de
plaza publicadas, elegidas para incluir los casos duros —Cerro de Pasco a
4,330 m, La Oroya en el fondo de un valle encajonado, Iquitos en llano
amazónico—.

| | error |
|---|---|
| mediano | **11 m** |
| p90 | 37 m |
| peor caso | Cusco, 66 m (ladera) |
| sesgo | −5 m |
| mediano en sierra (11 casos sobre 2,300 m) | 12 m |
| mediano en costa y selva | 6 m |

Eso es fino para separar pisos —los cortes están a 500, 2,300, 3,500 y
4,000 m— y grueso para afirmar la cota exacta de una parcela. **No se bajaron
teselas más finas porque la medición dijo que no hacía falta**, y esa decisión
se puede rehacer si algún día se quiere pendiente de parcela: eso sí pediría
30 m por píxel.

---

## Los pisos

Las ocho regiones de Pulgar Vidal, que es la clasificación con la que habla el
agro peruano, agrupando las que el dato no distingue —janca y puna se separan
a 4,800 m, donde ya no hay agricultura comercial—.

La región natural del sector desempata: **a 800 m, la vertiente occidental es
yunga seca y la oriental es selva alta**, y no producen lo mismo ni compran lo
mismo. Un distrito hereda la vertiente de los sectores que más hectáreas
agrícolas le aportan.

| vertiente occidental | | vertiente oriental | |
|---|---|---|---|
| chala | 0–500 m | selva baja | 0–400 m |
| yunga | 500–2,300 | selva alta | 400–1,000 |
| quechua | 2,300–3,500 | ceja de selva | 1,000–3,500 |
| suni | 3,500–4,000 | puna | > 3,500 |
| puna | > 4,000 | | |

---

## Lo que aparece al cruzarlo

### El dinero exportador y los clientes no están en el mismo piso

El FOB de exportación sale **75.4% de chala** y 11.4% de yunga: agroexportación
de valle costero irrigado. El mercado de insumos vive en otra parte.

| piso | sectores | mercado | clientes |
|---|---|---|---|
| chala | 897 | US$ 103.6 MM | 22,644 |
| quechua | 1,634 | 86.3 | 28,447 |
| suni | 1,562 | 77.0 | 31,256 |
| yunga | 577 | 54.7 | 13,374 |
| ceja de selva | 498 | 54.0 | 18,665 |
| selva alta | 308 | 51.8 | 14,978 |
| selva baja | 425 | 42.9 | 11,881 |
| puna | 1,135 | 42.0 | 15,633 |

Quechua, suni y puna suman **US$ 205 MM de mercado y 75,336 clientes —el 48%
del padrón—** contra 22,644 en chala. Inventario colocado siguiendo el FOB
exportador queda lejos de la mitad de los compradores. Son dos negocios
distintos y conviene no confundirlos: el exportador es concentrado, costero y
de ticket grande; el de sierra es disperso, de ticket chico y de muchos.

### La banda de cada producto, medida sobre el embarque

No citada de un manual de agronomía: **medida** cruzando el FOB de cada línea
del manifiesto con la cota del distrito que declara, sobre los años en que el
ubigeo viene lleno (2022–2024) y ponderando por FOB, no por distrito.

| producto | FOB MM | p10 | mediana | p90 |
|---|---|---|---|---|
| Arándano, fresa y otras bayas | 5,473 | 61 | 290 | 532 |
| Uva | 4,892 | 100 | 354 | 432 |
| Palta, mango, dátil y piña | 4,061 | 61 | 106 | 499 |
| Café | 3,167 | 33 | **1,331** | 1,953 |
| Hortalizas frescas (espárrago) | 1,178 | 34 | 116 | 516 |
| Cacao en grano | 1,154 | 122 | 483 | 1,213 |
| Jengibre, cúrcuma y especias | 307 | 640 | 1,041 | 1,467 |

Que el café salga con mediana de 1,331 m y p90 de 1,953 —la banda cafetalera
conocida— **es una validación independiente de que el ubigeo del manifiesto
apunta al fundo y no al domicilio fiscal**. Si apuntara a la oficina, el café
tendría la cota de Lima o de Chiclayo.

### El desnivel que sube cada centro

| centro | cota | carga p50 | carga p90 | desnivel |
|---|---|---|---|---|
| Pisco | 20 | 390 | 604 | +584 |
| Chiclayo | 33 | 116 | 1,952 | +1,919 |
| **Otuzco** | **2,675** | **110** | **634** | **−2,041** |
| Satipo | 627 | 1,063 | 1,457 | +831 |
| Picota | 222 | 909 | 1,876 | +1,654 |
| Jauja | 3,386 | 2,281 | 4,140 | +755 |

**El 20.2% del FOB exportador —US$ 5,304 MM— está asignado a un centro que se
sitúa más de 1,500 m por encima de la carga.** Casi todo es Otuzco, a 2,675 m,
cubriendo Virú (61 m) y Chao (532 m), los dos distritos de mayor embarque del
país. El modelo de centros los eligió por cobertura de clientes agrícolas y con
el reloj en llano: Otuzco alcanzaba la costa en dos horas.

Eso es exactamente lo que la corrección de pendiente pone a prueba.

---

## La pendiente en el ruteo

`build_ruteo.py` declaraba su velocidad como «free-flow km/h for a loaded light
truck, **before surface and terrain**». La superficie sí entraba; el terreno
nunca. Un camión cargado subiendo tres mil metros contaba igual que uno en
llano, y de esa cuenta colgaban las horas al centro, el costo de la visita y el
orden de apertura de centros.

### El modelo

    subida : factor = 1 / (1 + 0.12 · pendiente_%)      8% -> 0.51
    bajada : sin castigo hasta −8%; más allá manda el freno

Una hiperbólica de un solo parámetro. No hay curva peruana publicada para
camión ligero cargado; esta es la forma que tienen las tablas de camión pesado
y no finge una precisión que no existe.

### La pendiente no se mide entre nodos

Es la decisión que más cambia el resultado. Los nodos de OSM están a decenas de
metros y el DEM tiene 300 m por píxel: **un tramo de 50 m que cruza una ladera
hereda el gradiente del cerro** —treinta, cuarenta por ciento— aunque la
carretera esté subiendo al ocho por ciento en zigzag. Medida así, la pendiente
alargaba el grafo un 47% y la mitad de eso era la ladera y no la vía.

Se mide sobre una **ventana de 1 km a lo largo de la vía**: a esa distancia los
dos extremos caen en píxeles distintos y lo que se lee es el desnivel neto que
el camión efectivamente sube. Las lomas de menos de un kilómetro se promedian,
que es lo que hace un camión que sube y baja. Se recorta a ±12%, que es el
máximo de diseño vial peruano.

### El grafo deja de ser simétrico

Subir de Virú a Otuzco no cuesta lo mismo que bajar. Eso obliga a dos cambios:

- El ruteo se corre **en los dos sentidos** —ida del sector al centro sobre el
  grafo traspuesto, vuelta sobre el directo— y el costo del viaje es la suma de
  las dos mitades, **no el doble de una**.
- `directed=False` deja de ser válido: haría a scipy recorrer cada arista por
  el peso que encuentre primero, que es justamente la cuenta que se quiso dejar
  atrás.

### Cuánto pesa

Sobre 6,892 sectores alcanzables, ponderando por hectárea agrícola:

| | horas a la capital provincial |
|---|---|
| con terreno | **2.05 h** |
| en llano (lo que decía la plataforma) | 1.81 h |
| línea recta (el proxy anterior) | 2.31 h |
| vuelta desde la capital | 2.07 h |

El promedio nacional sube 13%, y ahí no está la noticia: **el terreno no se
reparte parejo**.

| región | cota media | más horas | más % |
|---|---|---|---|
| Huancavelica | 3,600 | +0.42 | **+27.4%** |
| Ayacucho | 3,283 | +0.52 | +26.8% |
| Junín | 2,239 | +0.52 | +25.5% |
| Áncash | 3,016 | +0.36 | +23.4% |
| Apurímac | 3,578 | +0.35 | +21.0% |
| … | | | |
| Lambayeque | 412 | +0.06 | +4.2% |
| Loreto | 171 | +0.15 | +3.0% |
| Ica | 519 | +0.04 | +2.9% |

El porcentaje es el cociente de las dos medias publicadas —con terreno sobre
llano, ponderadas por hectárea agrícola— y no el promedio de los porcentajes
de cada sector. Las dos cuentas son defendibles y dan distinto; se eligió la
que el lector puede rehacer con la tabla a la vista, y es la única que
calculan tanto el script como el sitio.

La sierra pagaba una cuarta parte de su tiempo de viaje sin que ninguna cifra
lo dijera, y la costa casi nada. Toda comparación entre una región andina y una
costeña —costo de servir, sectores bajo dos horas, orden de apertura— estaba
sesgada a favor de la sierra.

### Dos cosas que costaron

**La memoria.** Cinco millones y medio de puntos de geometría como
diccionarios de Python son cerca de un giga, y la máquina tiene 3.6 GB: la
corrida moría antes de rutear. `build_vial_compacto.py` convierte los 239 MB de
JSON de Overpass a 32 MB de arreglos, una vez y para siempre —lee sin construir
un solo diccionario y reproduce exactamente las 88,962 vías del lector
anterior—. Y el grafo se **contrae**: un punto que aparece en una sola vía es
punto de forma, no ofrece a dónde doblar y su tiempo se suma al tramo. Se
conserva además un hito cada kilómetro para que un sector no tenga que
engancharse a un nodo lejano. La pendiente se calcula sobre la geometría
completa **antes** de contraer, así que la cuenta no pierde nada.

**Las aristas repetidas.** `csr_matrix` suma las casillas repetidas, y dos vías
que comparten el mismo par de nodos —un puente mapeado dos veces, una vía de
servicio paralela— son repetidas: ese tramo salía al doble de caro. Se conserva
el más rápido, que es el que un camión tomaría. El defecto era anterior a este
trabajo y se arregló al pasar por ahí.

---

### Un solo grafo para las dos mitades de la decisión

La pendiente vive en `grafo_vial.py`, que es el módulo que ya usaba la elección
de centros. Ponerla solo en `build_ruteo.py` habría dejado el ruteo midiendo de
una forma y la elección de almacenes de otra: las dos mitades de la misma
decisión, hablando idiomas distintos. Durante una tarde hubo dos
implementaciones de la contracción del grafo —una en cada archivo— y ya habían
empezado a separarse.

Consecuencia pendiente: **la elección de centros sigue siendo la que se hizo
con el reloj en llano**. Rehacerla es correr `build_hubs.py`, y eso cambia los
seis centros, los 57 territorios, la capa de acopio y toda cifra publicada que
cuelgue de ellos. Es una decisión de negocio, no de código, y por eso no se
hizo de oficio.

---

## Orden de ejecución

```
build_vial_compacto.py  (una vez por bajada de Overpass)
        ↓
grafo_vial.py           (grafo contraído con pendiente; módulo, no etapa)
        ↓
build_ruteo.py          (horas y costo con pendiente)
build_hubs.py           (dónde poner los centros)

acopio → altitud        (cota y piso de cada capa)
```

`altitud` necesita el agregado exportador, la capa de acopio y los centros;
`pipeline.py` lo declara y lo hace cumplir.
