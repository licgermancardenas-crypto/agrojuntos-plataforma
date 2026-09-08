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

Con los centros elegidos **antes** de corregir el reloj, la carga quedaba así:

| centro | cota | carga p50 | carga p90 | desnivel |
|---|---|---|---|---|
| Pisco | 20 | 390 | 604 | +584 |
| Chiclayo | 33 | 116 | 1,952 | +1,919 |
| **Otuzco** | **2,675** | **110** | **634** | **−2,041** |
| Satipo | 627 | 1,063 | 1,457 | +831 |
| Picota | 222 | 909 | 1,876 | +1,654 |
| Jauja | 3,386 | 2,281 | 4,140 | +755 |

**El 20.2% del FOB exportador —US$ 5,304 MM— estaba asignado a un centro que se
situaba más de 1,500 m por encima de la carga.** Casi todo era Otuzco, a
2,675 m, cubriendo Virú (61 m) y Chao (532 m), los dos distritos de mayor
embarque del país. El modelo de centros los eligió por cobertura de clientes
agrícolas y con el reloj en llano: Otuzco alcanzaba la costa en dos horas.

Con la pendiente contada, **Otuzco se cae de los doce candidatos**. Los centros
quedan así:

| centro | cota | carga p50 | carga p90 | desnivel | FOB MM |
|---|---|---|---|---|---|
| Chiclayo | 33 | 116 | 1,950 | +1,917 | 13,130 |
| Pisco | 20 | 382 | 498 | +478 | 11,012 |
| Juliaca | 3,845 | 1,343 | 2,700 | −1,145 | 795 |
| Satipo | 627 | 1,090 | 1,454 | +827 | 581 |
| Tarma | 3,061 | 1,862 | 4,115 | +1,054 | 380 |
| Bellavista | 318 | 544 | 1,207 | +889 | 344 |

La carga cuyo centro está más de 1,500 m por encima **cae del 20.2% al 3.1%**
—lo que queda es Juliaca sirviendo valles más bajos, que es geografía del
altiplano y no un error de elección—.

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

### Qué pasó al rehacer la elección de centros

`build_hubs.py` se corrió sobre el grafo con pendiente. **La mitad de los seis
centros cambia.**

| # | con el reloj en llano | con pendiente |
|---|---|---|
| 1 | Chiclayo, Lambayeque | Chiclayo, Lambayeque |
| 2 | Pisco, Ica | Pisco, Ica |
| 3 | **Otuzco, La Libertad** | **Bellavista, San Martín** |
| 4 | **Picota, San Martín** | **Juliaca, Puno** |
| 5 | Satipo, Junín | Satipo, Junín |
| 6 | **Jauja, Junín** | **Tarma, Junín** |

Los tres que salen son los tres que vivían de una cuesta gratis: Otuzco a
2,675 m «alcanzaba» la costa de La Libertad, Jauja a 3,386 m el valle del
Mantaro, Picota el Huallaga. Los que entran están más abajo o mejor conectados.

Lo que se mueve detrás:

- **314 distritos cambian de centro**, US$ 9,009 MM, el 32% del FOB situado.
  Virú pasa de estar a 1.9 h de Otuzco a 4.0 h de Chiclayo; Chao, de 2.1 a 4.2.
- El FOB de exportación **a menos de dos horas de un centro cae de 42.3% a
  31.6%**. No es que la red haya empeorado: nunca cubrió el 42.3%.
- La cobertura del mercado de insumos con seis centros baja de 26.2% a 23.1%.
- Virú aparece por su cuenta en el puesto 8: deja de ser territorio servido
  desde arriba y pasa a ser sitio donde poner un centro.

El séptimo centro sigue marcando el rendimiento decreciente, ahora con
+2.7 puntos.

### La red que se decidió

Los seis que elige la cobertura máxima con vara de dos horas **más Huamachuco y
Sicuani**, con una **promesa de servicio de cuatro horas**. Los dos últimos no
salieron del algoritmo: salieron de mirar dos casos concretos —Sánchez Carrión y
Pataz el primero, el agujero de reparto del altiplano el segundo—.

Ese territorio es el mayor del país —US$ 33.6 MM, el 6.7% del mercado nacional,
9,114 clientes, 434,680 ha— y está alto: cota mediana de 3,214 m, con el 69% de
su mercado sobre los 3,000 m y 231 km de punta a punta, así que no se recorre en
una salida. **No lo sirve nadie a dos horas.** El mejor centro posible es su
propia capital y alcanza el 22% de su mercado a esa vara; a cuatro horas alcanza
el 63%. Chiclayo, que era su centro asignado, llega al 0% a dos horas y al 2% a
cuatro —9.5 h pesando cada celda por su mercado, contra las 6.5 h que mide la
ficha al centroide: las dos cifras son ciertas y contestan preguntas distintas—.

Y ahí está lo que decide: **con qué vara se mide cambia el ranking entero**.

| séptimo centro | a 2 h | a 4 h |
|---|---|---|
| Morropón | +2.66 pp | — |
| Virú | +2.66 pp | — |
| **Huamachuco** | +1.90 pp *(puesto 14 de 123)* | **+5.62 pp *(puesto 1 de 123)*** |

Con promesa de dos horas, Huamachuco es el decimocuarto sitio para el séptimo
almacén y desaparece de cualquier lista corta. Con promesa de cuatro es el mejor
del país. La promesa de servicio es una decisión comercial y no un parámetro
técnico, así que **se declara** —en `build_hubs.py`, con su motivo, y en
`out/red_elegida.json` con su fecha— en vez de quedar implícita en dos números
sueltos dentro del código de asignación, que es donde estuvo hasta ahora
(«escenario de 2 h y k=6»).

Lo que la red vigente cubre:

| | cobertura del mercado |
|---|---|
| ocho centros, promesa de 4 h | **49.4%** |
| los mismos ocho, vara de 2 h | 26.1% |
| siete centros, promesa de 4 h | 46.5% |
| los seis originales, vara de 2 h | 23.1% |

### El octavo: Sicuani, y por qué no Urubamba

El cruce del canal con los centros dejó un agujero con nombre. De los 3,097
puntos de venta ubicables, **435 de los que le tocaban a Juliaca quedaban fuera
de su propia promesa**: el altiplano tenía los clientes —19,130 detrás de sus
puntos, el mayor de la red— y no tenía cómo abastecerlos, con mediana de 5.7
horas.

`diag_satelite.py` midió los 101 candidatos posibles. Una docena rescata entre
166 y 203 de esos puntos y **todos están en el mismo hueco**, así que el ranking
por clientes no decide nada por sí solo:

| candidato | puntos | clientes | SAM | h a la red |
|---|---|---|---|---|
| Urubamba, Cusco | +172 | +4,089 | +14.1 MM | 5.7 |
| Anta, Cusco | +170 | +4,041 | +15.6 MM | 5.8 |
| **Canchis (Sicuani), Cusco** | **+167** | **+3,688** | **+14.6 MM** | **3.3** |
| Islay, Arequipa | +203 | +3,282 | +20.5 MM | sin dato |

Lo que decide es la última columna, y por eso el diagnóstico la calcula: **un
satélite se reabastece de una casa madre**. A 5.7 horas de todo, Urubamba no es
un satélite sino otro almacén con su propia línea de abastecimiento, y cuesta
otra cosa. Sicuani está a 3.3 h —dentro de la promesa— y se abastece de Juliaca.

El efecto medido, ya con la red de ocho: Juliaca baja de 466 puntos a 287 y sube
del 7% al 10% dentro de promesa, con la mediana de 5.7 a 4.4 horas; Sicuani toma
199 puntos con el 84% en promesa. La cadena completa —cliente con tienda a 45
minutos y tienda abastecida dentro de la promesa— pasa de 44,451 a **48,139
clientes**.

Lo que no arregla, dicho: de los 435 huérfanos rescata 199 y quedan 236 fuera.
Con 35 candidatos que califican como satélite y ninguno que pase de +167 puntos,
la aritmética dice que el sur no se cierra con un centro más: o son varios, o se
sirve con otra cadencia —entrega programada, consolidación semanal— en vez de
con radio de cuatro horas.

Sánchez Carrión pasa a responder a Huamachuco, y su cartera alcanzada sube de 93
a **120 de sus 133 empresas**. Lo que no cambia es la naturaleza del territorio:
93 productores y 15 agroindustrias, 3.95 empresas por millón de mercado. El
dinero está en muchos minifundios y no en empresas, así que el almacén es
condición necesaria y no suficiente —sin red de canal, un centro en Huamachuco
atiende a 133 clientes formales de un mercado de 9,114—.

La alternativa que no se tomó, dicha: con vara de cuatro horas el algoritmo, si
se le deja elegir de cero, propone otra red entera —Chiclayo, Tarma, Tarapoto,
Chincha Alta, Sicuani, Huamachuco…— que cubre más pero mueve los seis centros ya
decididos. Se conservaron los seis y se sumó el séptimo.

### Y el sur no se cierra abriendo

Puesto Sicuani, quedaban 257 puntos de venta del altiplano fuera de la promesa
de su centro. La pregunta siguiente era cuántos centros más harían falta, y la
respuesta tiene dos partes y las dos importan.

**El greedy nacional nunca baja al sur.** Encadenando satélites —cada uno
obligado a estar dentro de la promesa de la red que existe cuando se abre, que
es lo que distingue un satélite de un almacén— los ocho mejores son Virú, Santa,
Sullana, Ambo, Cajamarca, Cutervo, Rioja y Huánuco. Suman 56,647 clientes a la
cadena completa **y dejan los 257 huérfanos del sur exactamente donde estaban**.
No es un defecto del algoritmo: es la respuesta. El sur no compite por plata.

**Y obligándolo a resolver el sur, no puede.** Restringiendo los candidatos al
altiplano y cambiando el objetivo a rescatar esos 257 puntos, el diagnóstico se
detiene en el primer paso: *no queda ningún candidato del sur que pueda
abastecerse dentro de la promesa*. Lo que falta ahí no es un satélite —no hay
casa madre a menos de cuatro horas— sino un almacén con su propia línea, que es
otra decisión y otro costo.

### La salida barata: prometer distinto

Con **los mismos ocho centros**, sin abrir nada:

| promesa | puntos en promesa | | clientes con cadena completa |
|---|---|---|---|
| 4 h | 2,147 | 69% | 48,252 |
| 5 h | 2,417 | 78% | 51,438 |
| **6 h** | **2,601** | **84%** | **56,938** |
| 8 h | 2,937 | 95% | 63,680 |
| 12 h | 3,092 | 100% | 68,075 |

Pasar de cuatro a seis horas compra **8,686 clientes con cero inversión**, que es
prácticamente lo mismo que compran los ocho satélites de la cadena nacional
(56,938 contra 56,647). Ocho alquileres, ocho administraciones y ocho
inventarios, o una frase distinta en la promesa comercial.

Eso no significa que seis horas sea la respuesta: significa que **la vara es la
palanca más barata que tiene esta red**, y que la comparación hay que tenerla
delante antes de firmar cualquier alquiler. Lo que la plataforma no puede
decidir es si el cliente costeño acepta lo mismo que el andino —una promesa
diferenciada por piso, cuatro horas en costa y seis en sierra, es lo que hace la
distribución real y lo que el dato sugiere—.

### La promesa dejó de ser un número

La comparación de arriba se tomó: la promesa vigente es de **cuatro horas en
costa y seis en sierra y selva**, declarada en `build_hubs.py` junto a la red.

No es un ablandamiento, es lo que el terreno obliga. La sierra paga una cuarta
parte más de su tiempo de viaje por el desnivel —está medido más arriba— así que
prometer lo mismo en los dos sitios significa incumplir en uno. La distribución
real hace exactamente esto: al valle costero se llega en la mañana, a la
provincia andina se va con ruta programada.

| región | promesa | mercado | dentro |
|---|---|---|---|
| costa | 4 h | US$ 145.7 MM | 64% |
| sierra | 6 h | US$ 214.2 MM | 67% |
| selva alta | 6 h | US$ 73.7 MM | 77% |
| selva baja | 6 h | US$ 69.0 MM | 45% |

La cobertura del mercado pasa de **49.4% a 64.4%** sin abrir un solo almacén, y
la cadena completa —cliente con tienda cerca y tienda abastecida dentro de la
promesa— de 48,139 a **53,247 clientes**. Es más de lo que compró Sicuani, que
costaba un alquiler.

El agujero del sur se cierra por donde no se veía: **Juliaca pasa del 10% al
62%** de sus puntos dentro de promesa. No porque llegue más rápido —sigue a 4.4
horas de mediana— sino porque lo que se le exige ahora es lo que su geografía
permite.

Lo que la vara no arregla, dicho: la **selva baja se queda en 45%**, la más
baja de las cuatro. Ahí el problema no es la promesa sino que no hay carretera,
y eso no lo cambia ninguna decisión comercial.

### Y los territorios detrás

Los 57 territorios de venta se trazan sobre la densidad del mercado, no sobre
las horas, así que **siguen siendo los mismos 57 y en el mismo orden**: lo que
cambia es cuánto cuesta recorrerlos. La hora media al centro provincial, pesada
por mercado, pasa de 1.33 a 1.54 h, y el reparto vuelve a ser lo interesante
—Tayacaja +1.25 h, Huancayo +0.89, Cutervo y Chota +0.58—. Los 48 que se
recorren en una salida siguen siendo 48: ese criterio es de extensión en
kilómetros y no de horas.

Lo que sí se reordena es a qué centro responde cada territorio: **26 de los 45
con centro asignado cambian**, el 52% del mercado atendido.

| territorio | antes | hoy | h antes | h hoy |
|---|---|---|---|---|
| La Libertad · Sánchez Carrión, Pataz | Otuzco | Chiclayo | 2.1 | **6.5** |
| San Martín · Picota, Lamas | Picota | Bellavista | 1.0 | 1.6 |
| Junín · Jauja, Huancayo | Jauja | Tarma | 0.9 | 1.8 |
| Cusco · Anta, Paucartambo | Pisco | Juliaca | **13.9** | 5.8 |
| Puno · Azángaro, Puno | Pisco | Juliaca | **16.2** | 0.4 |
| Puno · Chucuito, El Collao | Pisco | Juliaca | **17.7** | 2.0 |
| Arequipa · Arequipa | Pisco | Juliaca | 11.6 | 4.4 |

El cambio corta en dos direcciones y conviene no contar solo la mitad buena. El
**sur** gana un centro propio: Puno y Arequipa dejan de estar nominalmente
servidos desde Pisco a dieciséis horas y pasan a Juliaca a menos de cinco. La
**sierra de La Libertad** pierde el suyo: Sánchez Carrión pasa de 2.1 h a 6.5,
porque Otuzco existía como centro solo mientras subir esa cuesta era gratis.

Efecto de borde: dos celdas H3 cambian de territorio al rehacer la grilla —los
144 sectores sin vía cercana son uno más que antes—, y con ellas un distrito
más queda fuera de todo territorio: los huérfanos pasan de 386 a 387.

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
