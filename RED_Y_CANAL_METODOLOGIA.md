# La red y el canal · metodología

Dónde poner inventario y quién le vende al agricultor. Es la última capa de la
plataforma y la que más decisiones toca, así que vive aparte del README: quien
discuta un centro o un punto de venta tiene que poder llegar hasta el archivo
que lo produce sin leer el proyecto entero.

Hermano de [`TOPOGRAFIA_METODOLOGIA.md`](TOPOGRAFIA_METODOLOGIA.md) —de donde
salen la pendiente y los pisos que aquí se dan por sabidos—, de
[`AGROEXPORTACION_METODOLOGIA.md`](AGROEXPORTACION_METODOLOGIA.md) y de
[`IMPORTADORES_INSUMOS_METODOLOGIA.md`](IMPORTADORES_INSUMOS_METODOLOGIA.md).

---

## La red de canal

La red de centros contesta dónde poner inventario. No contesta quién le vende al
agricultor: en Sánchez Carrión y Pataz hay 9,114 clientes y 133 empresas
formales, así que un almacén propio —aunque esté en Huamachuco— atiende al 1.5%
de ese mercado y el resto no se toca sin un punto de venta local.

`build_canal.py` arma esa capa, y no inventa la red: **el canal ya existe**. Los
candidatos son de tres clases, porque cuestan cosas distintas: **612
empresas del padrón con clase «canal»** —distribuidores y minoristas de insumos
con RUC, captarlos es un acuerdo comercial—, **2,658 comercios mapeados en
OpenStreetMap** —ferreterías, agroveterinarias, tiendas agrícolas— y los centros
poblados sin comercio conocido, donde llegar significa abrir algo.

El radio no es el del almacén: al almacén va un camión, a la tienda va el
agricultor. Se miden 30, 45 y 60 minutos sobre la red vial con pendiente y en el
sentido correcto —del sector a la tienda, que es el viaje que hace el cliente—.

Cuatro cifras que es fácil confundir, y confundirlas cambia la conclusión:

| a 45 minutos | clientes | |
|---|---|---|
| los 40 puntos de mayor captación | 50,621 | 32.9% |
| **con un comercio ya existente** | **68,840** | **44.7%** |
| **con algún sitio donde abrir** —sumando pueblos del padrón— | **143,466** | **93.2%** |
| **sin nada: ni tienda ni pueblo** | **10,518** | **6.8%** |

Los cuarenta mejores puntos capturan dos tercios de lo que alcanzan los 3,270
que existen: el canal está concentrado y una lista corta de acuerdos comerciales
rinde casi tanto como la red completa.

Por territorio el reparto es desigual y sigue la misma línea que todo lo demás:
Chiclayo tiene el 82% de sus clientes con canal cerca y **Sánchez Carrión el
20%** —1,813 de sus 9,115—. El territorio más grande del país es también el
peor servido en las dos capas.

### Quién resurte a quién

La cadena tiene dos tramos y hasta aquí solo se medía el de abajo. El de arriba
—del almacén a la tienda— sale de la asignación de centros y en el sentido del
camión de reparto, no del cliente.

| centro | puntos que resurte | del padrón | dentro de la promesa | horas, mediana | clientes detrás |
|---|---|---|---|---|---|
| Pisco | 1476 | 127 | 85% | 3.0 h | 7,470 |
| Huamachuco | 477 | 70 | 61% | 3.0 h | 7,122 |
| Tarma | 307 | 52 | 78% | 2.0 h | 9,527 |
| Juliaca | 287 | 76 | 62% | 4.4 h | 13,998 |
| Chiclayo | 230 | 133 | 83% | 3.0 h | 16,452 |
| Sicuani | 199 | 21 | 86% | 2.8 h | 5,342 |
| Bellavista | 100 | 79 | 93% | 3.2 h | 6,866 |
| Satipo | 21 | 21 | 100% | 1.4 h | 3,451 |

El cruce dio vuelta al mapa y de ahí salió el octavo centro. Pisco resurte 1,476
puntos que llegan a 7,470 clientes —costa densa, muchas tiendas sobre la misma
gente— mientras que Juliaca resurtía 466 que llegan a 19,130 con **solo el 7%
dentro de la promesa** y mediana de 5.7 horas: el centro con más clientes detrás
de su canal era el que no podía abastecerlo.

**Sicuani se puso por eso.** `diag_satelite.py` midió los 101 candidatos
posibles: una docena rescata entre 166 y 203 de los 435 puntos huérfanos de
Juliaca y todos están en el mismo hueco, así que el ranking por clientes no
decide. Lo que decide es a cuántas horas queda el candidato de la red que ya
existe —un satélite se reabastece de una casa madre; a seis horas de todo no es
un satélite sino otro almacén—. Urubamba compra 400 clientes más y está a 5.7 h
de todo; **Sicuani está a 3.3 h, dentro de la promesa, y se abastece de
Juliaca**. Con él, Juliaca baja de 466 puntos a 287 y la mediana de 5.7 a 4.4 horas; con
la promesa diferenciada encima, del 7% al 62% dentro de promesa.

Lo que no arregla, dicho: rescata 199 puntos y quedan 236 fuera. El sur no se
cierra con un centro más.

Huamachuco y Sicuani, los dos puestos por decisión, resurten 477 y 199 puntos:
el segundo y el sexto de la red.

De ahí sale la cifra que cuenta, porque **la cadena vale lo que valga su tramo
más débil**: clientes con tienda a 45 minutos *y* cuya tienda está además dentro
de la promesa de su centro son **53,247 (34.6%)**, contra el 45.2% que tiene
tienda cerca sin mirar cómo se abastece. Con la vara única de cuatro horas eran
48,139: la promesa diferenciada sumó 5,108 clientes sin abrir nada, que es más
de lo que compró Sicuani.

### Si un punto es negocio

El canal medido en clientes no alcanza para proponer nada: nadie toma una línea
nueva porque tenga gente cerca. Puesto en plata, con el reparto hecho —cada
sector va al punto que le queda más cerca, o se contaría a la misma gente dos
veces— y con la economía unitaria que la propia empresa midió sobre su libro de
ventas: penetración base 1.5% y margen bruto 21%.

**517 de los 3,270 puntos tienen mercado propio**; el resto cae dentro del
radio de otro más cercano. Entre esos 517 se reparten **US$ 240.3 MM**, la
mitad del mercado nacional.

| margen al año, mínimo | puntos que lo superan | clientes detrás |
|---|---|---|
| US$ 2,500 | 95 | 41,372 |
| US$ 5,000 | 32 | 20,705 |
| US$ 10,000 | 5 | 4,972 |
| US$ 25,000 | 0 | 0 |
| US$ 50,000 | 0 | 0 |

**El mayor punto del país deja US$ 15,260 al año** en el escenario base, y solo
cinco pasan de US$ 10,000. Esa es la cifra que hay que mirar antes de diseñar
una red de canal propia: a esta penetración, ningún punto sostiene por sí solo
una operación dedicada.

Con una salvedad que cambia la lectura y por eso viaja en la pantalla: **ese
margen es lo que capturaría AgroJuntos a través del punto, no lo que vende la
tienda**. La tienda ya le vende a esos agricultores; el 1.5% es la penetración
del proyecto sobre el mercado, no la participación del comerciante. Y el piso
de viabilidad no lo fija la plataforma —es una decisión comercial—: por eso se
publica la curva y no un veredicto.

### Dónde abrir donde no hay nadie

La pregunta quedó abierta hasta que entró el padrón. `build_ccpp.py` cruza dos
fuentes que solas no alcanzan: el **Directorio Nacional de Centros Poblados del
INEI** (censo 2017, 26 archivos por departamento) sabe qué pueblos existen,
cuánta gente vive en cada uno y a qué altura, pero **no publica coordenadas**;
**OpenStreetMap** tiene la coordenada de cada pueblo que alguien mapeó, pero no
sabe cuáles faltan. Se cruzan por nombre dentro del mismo distrito.

El resultado más útil no es la lista sino **la medida de lo que falta**:

| | centros poblados | |
|---|---|---|
| en el padrón del INEI | 94,922 | |
| **con coordenada tras el cruce** | **24,591** | **25.9%** |
| población que vive en esos | | **41.5% de la censada en centros poblados** |

Y sube con el tamaño: 17% de los caseríos de menos de 50 habitantes, 73% de los
pueblos de mil a cinco mil. Los que no pegaron **no se inventan** —ponerles el
centroide de su distrito sería inventar un pueblo donde no lo hay—: quedan en
`datos/poblacion/ccpp.csv` con su población y sin coordenada, que sirve para
contar lo que falta.

Con esos pueblos como candidatos, la lista de aperturas deja de ser solo
comercios existentes y el hueco se reduce a su tamaño real: de los 84,424
clientes «sin punto cerca» que daba la medición anterior, **10,518 no tienen ni
tienda ni pueblo a 45 minutos**. Ahí no hay dónde abrir; hay que llegar de otra
forma o no llegar.

### Y el hueco no es lo que parecía

Los 10,518 clientes sin tienda ni pueblo cerca invitaban a una explicación
cómoda: donde no hay carretera no hay nada. **El dato la desmiente**, y vale
decirlo porque la hipótesis era nuestra.

De esos 10,518, **31 están en sectores sin ruta vial a un puerto marítimo**. Los
otros 10,487 tienen camino y no tienen a quién comprarle: dos tercios están en
sierra —quechua 2,568 clientes, puna 2,366, suni 1,668— y los departamentos que
más aportan son Junín, Cusco y Lambayeque, no la selva. **El hueco es de
comercio, no de acceso.**

El caso más grande tiene nombre y ya había aparecido antes por otro lado:
**Olmos**, 1,270 clientes en tres sectores, a 1.8 horas de su capital
provincial, con el 76% de ellos sin nada cerca. Es tierra nueva de irrigación
—el mismo distrito que embarca US$ 1,541 MM sin caer en ningún territorio de
venta—: hay campo y no hay pueblo todavía.

Y la selva baja, la otra mitad de la sospecha, resulta bien servida por abajo:
**el 40% de sus clientes tiene un comercio a 45 minutos y solo el 2% no tiene ni
tienda ni pueblo**. Su problema es la distancia al almacén —45% dentro de la
promesa— y no la ausencia de canal.

Una salvedad sobre el descarte, porque sin ella no vale: quedarse sin ruta vial
a un puerto es raro en todo el país —105 sectores de 6,892, el 0.5% de los
clientes—, así que nunca iba a explicar diez mil personas. Lo que el cruce
descarta con seguridad es que el hueco esté hecho de sitios incomunicados; lo
que no puede es medir grados de mal camino.

**Dos límites del dato, dichos.** La ubicación del padrón de SUNAT es el
distrito y no la esquina: alcanza para un radio de 45 minutos y no para decidir
un local. Y que OpenStreetMap no mapee una tienda no significa que no exista: su
cobertura en la sierra rural es pobre, así que el 55.3% sin comercio conocido
es un **techo** —cuánto no se puede demostrar que esté cubierto— y no una
medición de abandono. Los pueblos, en cambio, ya no dependen de OSM para
existir: dependen de él solo para tener coordenada, y cuánto pesa eso está
medido arriba.

