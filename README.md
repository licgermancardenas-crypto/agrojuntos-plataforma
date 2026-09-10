# AgroJuntos · Plataforma de datos

Mapeo del mercado peruano de insumos agrícolas: dónde está la tierra que
produce, quién compra, cuándo compra y cuánto cuesta llegar.

**Dashboard en vivo → [agrojuntos.vercel.app](https://agrojuntos.vercel.app)**

Todo lo publicado aquí se genera por script a partir de fuentes oficiales, sin
transcripción manual. Cada cifra es reproducible corriendo el script que la
construye.

---

## Cifras principales

| Indicador | Valor |
|---|---|
| Superficie cosechada, campaña 2023 | 4,551,363 ha |
| Gasto en insumos por hectárea (ponderado) | US$ 381 |
| **TAM** — mercado nacional de fertilizante y fitosanitario | **US$ 1,734 MM** |
| **SAM** — productores comerciales que ya compran | **US$ 512 MM** |
| Clientes en el mercado atendible | 156,880 |
| Empresas agrícolas formales con RUC | 21,063 |
| Importadores de insumos agrícolas | 1,344 |
| Agroexportadores con RUC, 2022–2026 | 4,812 |
| Agroexportación medida en 2025 | US$ 14,790 MM FOB |
| Distritos con embarque propio, situados por el manifiesto | 629 |
| Plantas de empaque certificadas por SENASA | 296 |
| Importación de insumos, anualizada | US$ 1,168 MM CIF |
| Sectores estadísticos georreferenciados | 7,036 |

El SAM está a distancia razonable: **67.3% a menos de dos horas** de un centro
provincial, ruteado sobre la red vial y con la pendiente contada. Sin contar el
desnivel daba 76.2%, que es la cifra que este documento publicó hasta ahora: la
diferencia son nueve puntos de mercado que estaban más lejos de lo que decíamos,
casi todos en la sierra. La demanda se concentra: **45% entre setiembre y
diciembre**.

---

## Estructura

El repositorio contiene dos cuerpos de trabajo. `datos/` es el mapeo
territorial del mercado —dónde está la tierra, quién compra, cuándo y cuánto
cuesta llegar—. `agro_insumos_pe_data/` es un proyecto autocontenido que
extrae de los microdatos de aduanas quién importa insumos y quién exporta
producción, con su propio pipeline y datos crudos.

```
datos/
  mercado/          TAM, SAM, embudo de clientes, costos por cultivo
  territorio/       7,036 sectores estadísticos con superficie y mercado
  logistica/        tiempos de viaje, costo de servir, puertos
  estacionalidad/   calendario mensual de demanda por región y cultivo
  empresas/         21,063 empresas agrícolas con RUC; prospectos OSM
  comercio/         importadores de insumos y agroexportadores, desde aduanas
  importacion/      la importación agrícola repartida en categorías
  exportaciones/    cinco años de agroexportación por empresa y territorio
  acopio/           dónde se produce lo que se embarca, y quién tiene planta
  geo/              geometrías: sectores y límites administrativos
  geoespacial/      grilla H3, territorios de venta y centros de distribución
scripts/            el pipeline completo, en orden de dependencia
docs/figuras/       mapas y gráficos generados
dashboard/          sitio estático desplegado en Vercel

agro_insumos_pe_data/          proyecto autocontenido de comercio exterior
  scripts/                     descarga y procesamiento, 4 pasos
  raw_data/sunat/              20 archivos DBF de aduanas · 10 semanas
  raw_data/midagri/            anuario agrícola 2022-2023, costos INEI
  raw_data/github/             UBIGEO nacional y datasets de contexto
  processed_data/              importadores, agroexportadores · CSV y JSON
```

### Archivos clave

| Archivo | Qué contiene |
|---|---|
| `datos/mercado/modelo_v3_departamento.csv` | Modelo final: mercado, clientes, logística, estacionalidad y score por región |
| `datos/territorio/sectores_2024.csv` | Los 7,036 sectores con UBIGEO, hectáreas y centroide |
| `datos/territorio/clusters_territorio.csv` | Los 57 territorios de venta, con extensión, cartera y horas al centro |
| `datos/territorio/clusters_absorcion.json` | La regla con que un territorio absorbe lo que quedó fuera, y cuánto entra |
| `datos/decisiones/decisiones.json` | Cada decisión con su cifra, la alternativa que se descartó y su bisagra |
| `datos/territorio/satelite.json` | Qué compra un centro más, cuántos cerrarían el sur y qué pasaría con otra promesa |
| `datos/decisiones/ampliacion.json` | Qué importan los 769 exportadores que trajo el universo ampliado |
| `datos/insumos/canasta.json` | Qué insumo se compra, para qué cultivo, en qué región y en qué mes |
| `datos/logistica/cobertura_mes.json` | La cobertura de la promesa mes a mes, pesada por la demanda |
| `datos/insumos/canasta_detalle.csv` | El mismo cruce, fila por fila: insumo × cultivo × departamento × mes |
| `datos/territorio/cartera_territorio.csv` | Qué cartera cae en cada territorio y a qué centro responde |
| `datos/territorio/hubs_cobertura.csv` | Los centros elegidos por cobertura máxima, en tres umbrales de horas |
| `datos/logistica/ruteo_sector.csv` | Horas al centro provincial y al puerto, ruteadas sobre la red vial con pendiente, ida y vuelta por separado |
| `datos/topografia/altitud_sector.csv` | Cota y piso ecológico de los 7,036 sectores |
| `datos/topografia/altitud_distrito.csv` | Cota, piso y desnivel al centro de los 629 distritos con embarque |
| `datos/topografia/altitud.json` | Mercado y FOB por piso, y la banda de altura medida de cada producto |
| `datos/estacionalidad/estacionalidad_region.csv` | Demanda mes a mes, mes pico y concentración |
| `datos/empresas/empresas_agro_activas.csv` | Empresas con RUC, razón social, clase y distrito |
| `datos/comercio/comercio_importadores.csv` | Quién importa fertilizante y agroquímico, con valor FOB y distrito |
| `datos/importacion/import_agro_categoria.csv` | La importación agrícola en ocho categorías comerciales, con FOB, tonelaje y empresas |
| `datos/importacion/import_agro_lineas.csv` | Línea a línea con RUC, partida y país de origen, para prospectar cada rubro |
| `datos/comercio/comercio_exportadores.csv` | Los agroexportadores del país, con RUC, FOB y destinos · diez semanas |
| `datos/exportaciones/mercado.json` | Cinco años de agroexportación: por año, por mes, por familia, por destino y por departamento, con su cobertura |
| `datos/exportaciones/exportadores.json` | 4,062 exportadores con su cubo de producto × destino × partida, año por año |
| `datos/exportaciones/exportadores_min.json` | El recorte de 1.25 MB que consume el dashboard, del archivo de 7.8 MB |
| `datos/acopio/acopio_distrito.csv` | Los 629 distritos que embarcan, con producto líder, mes pico, centro que los sirve y horas |
| `datos/acopio/acopio_hub.csv` | Cuánta carga alcanza cada centro candidato a 2, 4 y 6 horas |
| `datos/acopio/acopio_huerfanos.csv` | Los 416 distritos con embarque que no caen en ningún territorio de venta |
| `datos/acopio/senasa_exportadores.csv` | Establecimientos certificados por SENASA, cruzados con quien embarca |
| `datos/geoespacial/h3_r5.csv` | 1,992 celdas hexagonales de ~292 km² con mercado, clientes y accesibilidad |
| `datos/geoespacial/clusters_territorio.csv` | 57 territorios de venta detectados por densidad |
| `datos/geoespacial/hubs_cobertura.csv` | Orden óptimo de apertura de centros, a 2, 4 y 6 horas |
| `datos/geoespacial/hubs_distrito.csv` | Los 1,826 distritos del país con su centro, sus horas y la distancia al nodo vial usado |
| `datos/empresas/cartera_empresa.csv` | Cada empresa con su territorio de venta y el centro que la sirve |
| `datos/empresas/cartera_territorio.csv` | Cartera de los 57 territorios: empresas, agroindustria, agroexportadores y cobertura a dos horas |
| `agro_insumos_pe_data/processed_data/importadores_insumos_agro.csv` | 446 importadores de insumos, sin el nitrato de amonio de uso minero |
| `agro_insumos_pe_data/processed_data/agroexportadores.csv` | 1,529 agroexportadores de la ventana de diez semanas; el histórico está en `datos/exportaciones/` |

---

## Cómo se construye

Los scripts corren en este orden. Los que descargan lo hacen desde la fuente
oficial; los datos crudos no se versionan aquí porque suman 1.6 GB y son
públicos y reproducibles.

```
descargar.py              descarga reanudable para archivos grandes
build_padron.py           MIDAGRI · sectores estadísticos 2024
build_superficie.py       MIDAGRI · superficie agrícola por sector
build_cenagro.py          INEI  · productores y tamaño de unidad (CENAGRO 2012)
build_costos.py           INEI  · costo de insumos por hectárea, 73 cultivos
build_gasto_ha.py         gasto por hectárea ponderado por mezcla de cultivos
build_embudo.py           embudo: de productores a compradores reales
build_modelo_v2.py        TAM y SAM por región
build_estacionalidad.py   calendario mensual de demanda
harvest_osm.py            OSM  · entidades agrícolas nombradas
harvest_vial.py           OSM  · red vial y terminales
build_puertos.py          APN  · terminales portuarios, geocodificados
build_logistica.py        tiempos de viaje y costo de servir
build_empresas.py         SUNAT · padrón RUC -> empresas agrícolas
acumular_aduanas.py       archiva cada semana antes de que SUNAT la retire
listar_aduanas.py         lista los archivos de aduanas publicados
bajar_aduanas.py          los descarga con verificación de integridad
build_aduanas.py          lee los DBF y filtra partidas de insumos agrícolas
build_import_categorias.py  reparte toda la importación en categorías del agro
build_perfiles.py         un perfil por empresa, con su comercio exterior línea a línea
build_comercio.py         cruza aduanas con el padrón para ubicar cada empresa
build_modelo_v3.py        modelo final con logística y estacionalidad
grafo_vial.py             grafo vial contraído: de 5.2 M de nodos a 95 mil
build_h3.py               agrega todas las capas a grilla hexagonal H3
build_clusters.py         territorios de venta por densidad (DBSCAN)
build_hubs.py             ubicación de centros por cobertura máxima
build_cartera.py          cruza el padrón con territorios y centros
build_vial_mapa.py        simplifica la red vial principal para dibujarla
build_mapa_geo.py         empaqueta las capas para el atlas web
build_atlas_html.py       compone plantilla + datos en un HTML autónomo
build_cultivos.py         qué se siembra en cada región, y qué mercado implica
build_agroexport.py       qué se exporta y por qué aduana sale, desde el manifiesto
build_figs_export.py      la serie mensual de exportación y el perfil por región
build_acopio.py           sitúa la carga donde se produce y la cruza con los centros
build_senasa.py           plantas certificadas por producto y mercado de destino
diag_universo.py          qué capítulos deja fuera el universo agro, y cuánto valen
build_dashboard_data.py   arma los JSON que consume el sitio
build_mapas_pdf.py        figuras del reporte
build_relieve.py          sombreado de relieve por departamento, para las láminas
build_relieve_web.py      un solo sombreado nacional, para el fondo del atlas web
build_cultivo.py          huella cultivada desde el landuse de OSM
build_territorios.py      da forma a los territorios de venta para dibujarlos
build_laminas_dep.py      una lámina a página completa por departamento
build_multiples.py        series de mapas pequeños: 57 territorios, 197 provincias
reporte.py                reporte PDF
medir_paginas.py          mide cada página del reporte contra el marco A4
```

**Qué se comprueba solo.** En cada push, `verificar_datos.py` revisa los
archivos publicados —que los JSON parseen sin `Infinity` ni `NaN`, que las
cuadraturas den, que los agregados sean coherentes entre sí y que las cifras
de esta documentación correspondan a los datos— y `verificar.py` recorre el
sitio en un Chrome de verdad. Una vez por semana, `auditar_pruebas.py`
reintroduce cada defecto que las pruebas dicen cubrir y exige que salten.

## La canasta: qué insumo, para qué cultivo, dónde y cuándo

El proyecto tenía las piezas separadas y ninguna contestaba la pregunta que
hace un comercial: *en Piura, en marzo, ¿qué se está comprando y para qué?*
`build_canasta.py` cruza el calendario de siembra —`estacionalidad_detalle`,
superficie sembrada por cultivo, departamento y mes— con la hoja de costos de
MIDAGRI, que dice cuánto de una hectárea de cada cultivo es fertilizante,
plaguicida o semilla.

| | US$ MM al año | |
|---|---|---|
| Fertilizante | 642 | 38% |
| Fitosanitario | 510 | 30% |
| Semilla | 248 | 15% |
| Abono orgánico | 161 | 9% |
| Riego | 120 | 7% |
| Asistencia técnica | 20 | 1% |

La estructura cambia con el cultivo, y ese es el punto: la **papa** se lleva el
31% en semilla y la **palta** el 39% en riego y cero en semilla, porque no se
resiembra. Un promedio nacional borra justamente eso.

**El mes es el de la siembra, no el de la cosecha.** El fertilizante entra con
el cultivo, no cuando sale el camión; anclarlo en la cosecha correría el
calendario medio año y mandaría al vendedor tarde. Octubre pesa 12.9% y abril
5.6%: el año tiene una temporada de compra de 2.3 veces el valle.

La vista **Canasta** del sitio la deja consultable: se elige región y mes y
responde qué insumo y para qué cultivo. Pulsar octubre en Puno y pulsar abril
en Piura devuelven cosas distintas, que es el punto — y la prueba del navegador
compara justamente dos meses entre sí, porque comparar un mes contra el año
pasaría por la diferencia de longitud aunque el filtro estuviera muerto.

**No es una medición de compras.** Nadie publica lo que compró un agricultor.
Es un coeficiente técnico —lo que cuesta producir bien una hectárea— aplicado a
la superficie real, y la hoja describe un manejo tecnificado que el minifundio
de sierra no alcanza. Dice **a qué se destina el gasto y cuándo**; el cuánto
sale del modelo de mercado, que sí corrige por tamaño con las tasas del
CENAGRO. El 95% del gasto usa la estructura de su propio cultivo; el resto, el
promedio de su familia, y la salida lo marca fila por fila.

### La cobertura no es un número, es una banda

El sitio publica **64.4% del mercado dentro de la promesa**, y esa cifra pesa
cada celda por su SAM anual: como si el país comprara parejo los doce meses. La
canasta acaba de mostrar que no. Pesada por la demanda de cada mes, la cobertura
va de **60.8% en mayo a 70.9% en enero**, y **ocho de los doce meses quedan por
debajo del promedio** con que se juzga la red.

**La hipótesis con que se empezó era la contraria y era falsa.** Se esperaba que
la red se viera peor en los meses grandes, porque las regiones mal cubiertas
—sierra y selva— son las que más concentran su compra en la siembra. Un primer
cálculo pareció confirmarlo: octubre al 60.8%. Ese cálculo pesaba la cobertura
departamental por los montos de la canasta, mezclando dos construcciones
distintas del mismo mercado y contando el supuesto dos veces. Hecho por celda y
tomando del calendario solo la forma, **octubre da 65.1%**: enero, diciembre y
octubre están entre los mejores meses, y los peores son los flojos de mayo a
agosto.

Queda en pie lo que importa: el promedio anual esconde diez puntos de banda, y
la decisión del noveno centro pasa de leerse «35.6% fuera de la promesa» a
«entre 29% y 39% según el mes».

## Decisiones

La plataforma contesta muy bien *qué es verdad*. Lo que no contestaba es *qué
hacemos y cuánto vale*, y se notaba: el universo arancelario, el séptimo y
octavo centro, la promesa diferenciada, la regla de absorción y el ruteo por
distrito se decidieron todos midiendo alternativas —y las mediciones
terminaban **en mensajes de commit**. Quien abriera el proyecto seis meses
después vería la red de ocho centros sin saber que la de seis se midió, ni
cuánto peor era.

`build_decisiones.py` lo pone en un archivo. Cada decisión lleva **la cifra que
la sostiene**, **la alternativa que se midió y se descartó —con la suya—** y
**la bisagra**: lo que tendría que cambiar para darla vuelta. Los números salen
de los archivos que el pipeline ya publica, así que cuando el dato cambia, la
decisión que se muestra cambia con él.

Dos reglas de contenido, y las dos son lo que separa esto de una lámina de
conclusiones. Una decisión abierta se publica con su cifra y su bisagra, nunca
con un adjetivo: «conviene expandir al sur» no es un dato aunque lleve
tipografía de dato. Y no se inventan preguntas: están las que el proyecto
enfrentó o enfrenta, no un catálogo de las plausibles.

La única cifra que no se recalcula está marcada: la del método anterior de
acopio —41 distritos sin centro y US$ 2,257 MM— viaja con la fecha en que se
midió, porque ese método ya no existe en el código.

Las preguntas abiertas dejaron de depender de que alguien corra un diagnóstico
a mano. `diag_satelite.py` era un script de una vez que imprimía en la terminal
lo que compra un centro más; ahora es `build_satelite.py`, una etapa que emite
`satelite.json`, y de ahí sale el marginal del noveno centro. **De paso apareció
que llevaba roto desde que la promesa dejó de ser un número único**: leía
`float(red["promesa_h"])` sobre un diccionario de cuatro regiones y no
arrancaba.

### Los 769 exportadores nuevos no son 769 clientes

Ampliar el universo sumó 769 exportadores y US$ 3,650 MM de embarque, y la
conclusión fácil era llamarlos cartera nueva. `build_ampliacion.py` cruza esos
RUC contra lo que **importan**, que es lo único que dice si compran lo que la
plataforma vende, y resultaron ser tres cosas:

| | empresas | compran |
|---|---|---|
| la industria del insumo | 25 | US$ 250 MM · el 57% de lo que compra el grupo |
| grano y alimento balanceado | 78 | US$ 5,450 MM · el 88% en seis empresas |
| el resto | 59 | US$ 188 MM, y 168 de ellos son una sola química |

Las del primer grupo —BASF, Interoc, Montana, Neoagrum— **ya están en el
ranking de protección de cultivos de este mismo proyecto**: son proveedor o
competencia, no cliente. Las del segundo —ADM, Seaboard, Cargill, San
Fernando— compran torta de soya y maíz, que no está en el catálogo.

**Clasificadas como productor o agroindustria quedan 47 de 769**, y el 93% ni
siquiera está en el padrón agrario porque se llaman Quimpac o Cargill. El
clasificador no falló: que no las reconozca por su nombre es la señal de que
son otra cosa. El embarque dice qué venden; solo la importación dice si compran.

Y el número del noveno centro, ahora que existe, dice algo que no se veía: el mejor candidato
—Barranca, +265 puntos de venta y +3,563 clientes— **no tiene ningún centro
dentro de su promesa**, así que no sería un satélite sino otro almacén. El
primero que sí puede abastecerse es Santa, a 4.6 h de la red, con +196 puntos.
Y prometer seis horas parejas, sin abrir nada, compra +164 puntos y +3,578
clientes: casi lo mismo que el mejor centro nuevo, sin alquiler.

**El orden no es opcional y ya no es tradición oral.** `pipeline.py` declara
las veinticinco etapas con lo que lee y lo que escribe cada una, corre lo que haga
falta y falla —diciendo qué etapa produce lo que falta— cuando una entrada no
está. Al terminar publica: `publicar.py` lleva a `datos/` lo que se recalculó y
avisa de lo que se sirve sin que nadie lo genere. Iba a mano y a mano se
olvidaba —`datos/` llegó a tener 35 archivos atrasados mientras `out/` estaba al
día—, así que el rigor llegaba hasta la puerta y ahí soltaba. Los JSON del
navegador ya no se copian: los generadores escriben directamente donde el sitio
los lee, que es lo que explica `scripts/sitio.py`. Depurar antes de agregar, agregar antes del panel —que lee del agregado
la frontera de completitud—, SENASA antes que acopio. Correrlas en otro orden
no revienta nada: mezcla cifras viejas con nuevas, que es peor.

```
python scripts/pipeline.py            corre lo que haga falta
python scripts/pipeline.py --secar    dice qué haría, sin hacerlo
python scripts/pipeline.py --desde export
python scripts/medir_paginas.py       después del informe, siempre
```

---

## Fuentes

| Fuente | Aporte |
|---|---|
| **MIDAGRI** · Padrón Nacional de Sectores Estadísticos 2024 | 7,043 sectores con UBIGEO, hectáreas agrícolas y centroide. Anexo del Mapa Nacional de Superficie Agrícola, RM N.º 0026-2025-MIDAGRI |
| **MIDAGRI** · Anuario de Producción Agrícola 2023 | Superficie sembrada y cosechada de 145 cultivos por región, con calendario mensual |
| **INEI** · Costos de producción (ENA 2018) | Costo por hectárea desagregado por ítem, 73 cultivos |
| **INEI** · IV Censo Nacional Agropecuario 2012 | Productores, tamaño de unidad, uso de insumos y crédito |
| **SUNAT** · Padrón Reducido del RUC | 18.4 M registros. Razón social, estado, ubigeo y domicilio fiscal |
| **SUNAT** · Microdatos de aduanas, regímenes definitivos | Archivos DBF semanales bajo Ley 27806 de Transparencia: RUC, partida NANDINA, FOB, peso y país por línea de despacho |
| **Autoridad Portuaria Nacional** | Terminales portuarios de uso público |
| **OpenStreetMap** | Entidades agrícolas nombradas y red vial · © colaboradores de OSM, [ODbL](https://opendatacommons.org/licenses/odbl/) |

---

## Advertencias

**El censo agropecuario es de 2012.** No existe uno más reciente. Las tasas de
uso de insumos y crédito vienen de esa base; la superficie y los cultivos son
de 2023–2024.

**Los valores por sector son un reparto.** Las cifras departamentales se
distribuyen entre los 7,036 sectores en proporción a sus hectáreas. Sirve para
priorizar territorio, no para cotizar a un productor concreto.

**Los tiempos de viaje se rutean sobre la red vial** de OpenStreetMap: 88,962
vías, 5.2 millones de puntos de geometría que se contraen a 345,807 nodos de
decisión. La velocidad de cada tramo es su clase de vía ajustada por superficie,
limitada por la velocidad máxima señalizada y **corregida por la pendiente**,
medida sobre el relieve en una ventana de un kilómetro de carretera. Con
pendiente el grafo deja de ser simétrico —subir no cuesta lo que bajar—, así que
el viaje redondo es la suma de las dos mitades y no el doble de la ida. El
detalle está en [`TOPOGRAFIA_METODOLOGIA.md`](TOPOGRAFIA_METODOLOGIA.md).

No modela congestión ni cierres estacionales, y 144 de los 7,036 sectores quedan
fuera del grafo por no tener vía mapeada cerca. `logistica_sector.csv` conserva
la estimación geodésica previa para contraste.

**Los datos de aduanas del eje general cubren diez semanas**, de junio a agosto
de 2026. Las dos subcategorías que corren sobre el histórico acumulado son la
de importadores de insumos —ver `IMPORTADORES_INSUMOS_METODOLOGIA.md`— y la de
agroexportación, con cinco años medidos; ninguna de las dos anualiza nada. Las cifras anualizadas
extrapolan ese período sin corregir estacionalidad y deben leerse como orden de
magnitud. La partida 3102 incluye nitrato de amonio, que es fertilizante y a la
vez base de explosivos de minería: empresas como Orica o Famesa aparecen por ese
uso y no por el agro; el campo `uso_dual` las marca.

**La partida arancelaria no siempre distingue el uso.** El reparto de la
importación en categorías comerciales se escribe a cuatro, seis u ocho dígitos
según el caso, porque a cuatro varias partidas mezclan usos incompatibles: 8701
junta el tractor agrícola con el tractocamión de carretera y 3002 la vacuna
humana con la veterinaria. Donde no hay corte posible —bombas, válvulas,
manguera plástica, rodamientos, tornillería— la partida queda fuera y se declara
en `import_agro_excluidas.csv`: son US$ 366 MM en diez semanas de zona ambigua,
no de gasto agrícola sin contar.

**Servicios agrícolas y venta de campos no aparecen en aduanas.** No son
mercancía y no cruzan una frontera. Se conservan en la tabla con valor cero
para que la ausencia se vea; dimensionarlos exige el padrón de SUNAT por CIIU y
registros públicos.

**El domicilio de una empresa no es donde cultiva.** La ubicación viene del
domicilio fiscal del padrón, y los agroexportadores suelen estar registrados en
Lima aunque su fundo esté en La Libertad o Ica. Para exportación hay un dato
mejor y está medido: el UBIGEO del propio manifiesto apunta al lugar de
producción —ver «Agroexportadores»—, aunque solo hasta 2024.

**La empresa se sitúa por su distrito**, en el punto medio de los sectores
agrícolas que ese distrito tiene, cruzando por departamento + provincia +
distrito. Cruzar solo por el nombre del distrito no sirve: 95 nombres se repiten
entre departamentos —hay cuatro «San Juan», separados por 800 km— y promediarlos
ponía al 13% del padrón en un punto que no está en ninguno de ellos.

**Las empresas se clasifican por razón social**, no por código CIIU: el padrón
reducido de SUNAT no lo incluye. La clasificación subestima —no ve a la empresa
con nombre neutro— y se restringe a personas jurídicas.

**El dimensionamiento de mercado es una estimación**, no una estadística
oficial. Los datos territoriales sí lo son y se citan uno a uno. Como contraste
externo: el modelo estima US$ 1,038 MM de fertilizante a precio de finca, contra
US$ 693 MM CIF importados en 2024, que cubren el 89.5% de la oferta nacional.

---

## Análisis geoespacial

Sobre las capas anteriores se construyeron tres análisis, en
`datos/geoespacial/`:

**Grilla H3.** Los sectores estadísticos miden entre 200 y 30,000 hectáreas, de
modo que comparar dos zonas mirando sectores mezcla densidad con tamaño de la
unidad de medida. La grilla hexagonal tiene área constante: 1,992 celdas de
~292 km² en r5, y 5,198 de ~42 km² en r6. **280 celdas concentran la mitad del
mercado atendible.**

**Territorios de venta.** DBSCAN con radio de 15 km sobre el 80% superior del
mercado da **57 territorios**, de los cuales **48 miden menos de 120 km** de
punta a punta y se recorren en una salida. Agrupar sobre el total encadenaba el
país entero en un solo núcleo de 2,000 km: la agricultura peruana es continua a
lo largo de los valles.

Ese corte del 80%, más el ruido de DBSCAN, dejaba **73,298 clientes —el 48%—
sin territorio**, y no es lo mismo que decir que no se pueden atender: una
celda rala pegada a un territorio denso la visita el mismo vendedor en el mismo
viaje. Después de agrupar hay entonces un segundo paso con una regla sola:
**una celda huérfana entra al territorio que la alcance por carretera, mientras
el territorio siga midiendo menos de 120 km**. Se aceptan de la más cercana a
la más lejana y se para donde la caja se rompe.

Entran **24,971 clientes y US$ 75.6 MM**. La cobertura pasa de la mitad a
**69% de los clientes** y al **71% del SAM**, y **ningún territorio deja de
recorrerse en el día**: siguen siendo **48 de 57**. La alternativa obvia —una vara
fija de horas para todos— está medida en `diag_territorios.py` y sale peor:
recupera los mismos clientes y deja 34 de 57 visitables.

Los ~48,000 que siguen fuera lo están porque meterlos rompería el territorio
que los recibe. Ese es el argumento de la capa de canal —alguien más les
vende— y no el de un territorio más grande.

**Centros de distribución.** Cobertura máxima con algoritmo voraz sobre 129
ciudades capitales, evaluadas contra tiempos ruteados. El resultado corrige una
intuición: **a dos horas, seis centros cubren apenas el 26%** del mercado —la
agricultura está demasiado dispersa—, mientras que **a seis horas cubren el
75%**. El radio de operación, no el número de almacenes, es lo que decide la
cobertura.

**Cada unidad tiene su propio mapa y su propia dirección.** Los 24
departamentos, los 57 territorios de venta y las 197 provincias se enfocan
desde tres selectores que se excluyen entre sí, y el recorte queda en el enlace:
`/mapa#dep=junin`, `/mapa#ter=9`, `/mapa#prov=ica-pisco`. La ficha de cada
departamento y cada fila de la tabla de territorios llevan a su mapa. Se dibujan
en vivo sobre el mismo lienzo, sin generar una imagen por unidad: 254 láminas
estáticas serían 51 MB y no se podrían recorrer con el zoom.

La pertenencia a territorio se resuelve una sola vez, sobre la celda H3 de
resolución 6 que es donde se detectaron los núcleos, y la heredan las tres capas
—sectores, hexágonos y provincias—. Si cada una la dedujera por su cuenta darían
tres respuestas distintas a la misma pregunta.

En el informe, el departamento conserva su lámina a página completa y los
otros dos niveles van como **series de mapas pequeños**: tres planas con los 57
territorios y siete con las 197 provincias, todas con la misma simbología y el
mismo encuadre relativo. Copiar el sitio habría costado 254 páginas y 51 MB; la
serie ocupa diez y pesa 4 MB, y además se compara de un vistazo, que es lo que
la lámina grande no permite.

El atlas interactivo está en `docs/atlas_geo.html` y publicado en
[agrojuntos.vercel.app/mapa](https://agrojuntos.vercel.app/mapa). Filtra por
departamento, región natural y búsqueda de provincia o ciudad —los totales
del encabezado se recalculan sobre lo filtrado—, y superpone la red vial en
tres niveles sobre 194 capitales de provincia y los puertos agroexportadores.
Es la capa que explica el mapa: se ve por qué un valle con mercado alto queda
lejos en tiempo, que es lo que el color por sí solo no dice.

**El atlas completo vive dentro de cada módulo.** Los once —resumen,
departamentos, territorios, empresas, perfil, productos, comercio, importación,
estacionalidad, logística y expansión— llevan la misma página de `/mapa` en un
iframe, no una versión recortada: hay un solo motor de mapa y lo que se arregla
ahí vale en los once lugares. Se monta al pulsar y no al abrir la vista, porque
entre página, capas y relieve son unos 4 MB y quien entra a leer una tabla no
tiene por qué pagarlos; después quedan en caché y los demás módulos los reusan.

El módulo manda sobre su mapa: cambiar de región en la ficha departamental
mueve el mapa, y pulsar un territorio lo enfoca. Se reenfoca cambiando el hash
del iframe, que es una navegación dentro del mismo documento y no una recarga
—por eso `#peru` existe como enlace explícito: vaciar el hash no dispara el
evento—. Con `?e=1` el mapa se dibuja sin encabezado ni navegación, que dentro
de una tarjeta serían una barra de navegación dentro de otra.

**El atlas tiene relieve de fondo**, el mismo cálculo de sombreado que las
láminas impresas: teselas Terrarium de AWS, sombreado de Horn, 302 m por píxel.
El sombreado solo, que en papel a 130 dpi se lee perfecto, en pantalla a escala
nacional desaparecía —la imagen se reduce de 1463 px a unos 400 y el promediado
se come las líneas finas de pendiente—, así que se le suma una componente de
altura: la pendiente dibuja el valle y la altura dibuja la masa. Va en JPEG
(877 KB a 705 m por píxel) porque el relieve es una superficie suave sin bordes
duros, que es lo que un compresor con pérdida hace bien; el mar no se borra en la imagen sino
que el lienzo recorta contra el contorno del país al dibujarla, lo que evita
pagar PNG por una transparencia. Se apaga con su propio interruptor.

**El mapa dibuja el sector, no un círculo sobre el sector.** La unidad de todo
el análisis son los 7,036 sectores estadísticos del MIDAGRI, y el atlas los
mostraba como puntos proporcionales sobre su centroide. Un círculo dice «hay
algo por acá»; el polígono dice dónde empieza y dónde termina. La
representación **Sectores** es ahora la que abre.

El peso no estaba en cuántos vértices hay —simplificar apenas los reduce,
porque las formas ya vienen mínimas— sino en cómo se escriben. Cuantizados a
1e-4 grados (11 m, la mitad del ancho de una chacra) y guardados como
diferencias respecto del vértice anterior, los números pasan de `-80.1234` a
`-3`: 2.6 MB quedan en 1.2, que son **0.46 MB comprimidos**, lo mismo que
pesaban los círculos. La capa se decodifica una vez al recibirla, no en cada
cuadro.

**Los límites vienen del IGN y no del geojson publicado.** El archivo que se
usaba antes ya venía generalizado por su editor —de ahí el «simple» de su
nombre— con 3,374 vértices para los 25 departamentos. El servicio WFS del
propio Instituto Geográfico Nacional tiene **307,384**: noventa y una veces
más. Simplificados a 222 m quedan 22,868, que son 130 KB comprimidos.

Las provincias salen de geoBoundaries, cuya fuente declarada es el IGN:
**689,927 vértices contra 19,010**. No traen el departamento, así que el par
(departamento, provincia) se recupera por **cruce espacial** —el punto
representativo de cada forma nueva dentro de la forma vieja— y no por nombre:
cruzar por nombre es lo que ya rompió la ubicación de las empresas una vez. El
cruce ubica las 196 formas y cubre 195 de las 197 anteriores; las dos que
sobran son erratas del archivo viejo, «PUIRA» y «VICTOR FAFARDO», que es una
razón más para cambiarlo.

La red dibujada sale de `build_vial_mapa.py`, que une los tramos de OSM antes
de simplificarlos —OSM corta cada vía en los cruces, así que la Panamericana
llega como miles de segmentos de dos puntos— y baja de 47,729 vías a 10,656
trazos. Es geometría para leer, no para rutear: el ruteo usa el grafo completo
de `grafo_vial.py`.

---

## Dashboard

`dashboard/` es un sitio estático sin framework ni servidor: HTML, CSS y
JavaScript plano sobre los JSON precalculados. Se despliega con
`vercel deploy --prod` y no cuesta nada de operar.

| Vista | Qué responde |
|---|---|
| Resumen | Tamaño del mercado, embudo de clientes, curva de demanda y las 24 regiones ordenadas |
| Departamentos | Ficha por región: mercado, clientes, cultivos, logística y estacionalidad |
| Territorios | Los 57 núcleos de venta, con extensión, cartera, centro que los sirve y si se recorren en un día |
| Empresas | Directorio buscable de 22,437 empresas con RUC, clase, ubicación, territorio de venta, centro y FOB |
| Productos | Qué se cultiva, qué se exporta y por qué aduana sale, filtrable por región |
| Comercio | Importadores de insumos —diez semanas anualizadas— junto a la agroexportación medida de cinco años, cada mitad con su periodo declarado |
| Importación | Qué importa el agro en ocho categorías, con detalle por partida y mayores importadores |
| Exportación | Cinco años medidos: serie por año, qué sale y a dónde, de qué departamento y quién lo embarca |
| Estacionalidad | Calendario de demanda mes a mes por región |
| Logística | Horas al centro provincial y al puerto, y el costo de servir cada región |
| Expansión | Orden óptimo de apertura de centros según el radio que se acepte |
| Perfil de empresa | Una página por RUC: qué importa, de qué origen, con qué continuidad, sus cinco años de embarques y el origen declarado en el manifiesto |
| Método | Cadena de cálculo, fuentes y limitaciones declaradas |
| Mapa | Atlas geoespacial con seis representaciones, y un mapa propio por departamento, territorio y provincia |

**Las cifras de la ventana de diez semanas tienen tres periodos**: *Medido*,
*Mensual* y *Anual*, en un selector del encabezado que manda sobre todas las
vistas. Esa ventana viaja MEDIDA en los JSON —las diez semanas tal cual— y es
el navegador el que multiplica; así ninguna vista puede anualizar por su cuenta
y mostrar una cifra distinta de la de al lado. «Medido» es el único dato duro:
mensual y anual extrapolan la ventana sin corregir estacionalidad, y las
cabeceras lo declaran («CIF anual», «FOB al mes», «FOB 10 sem»).

**El selector no toca lo que ya está medido.** Las vistas que corren sobre el
histórico —Importación, Exportación, la mitad exportadora de Comercio y el
bloque de embarques de la ficha— lo ignoran a propósito: anualizar cinco años
medidos sería inventar. En Comercio esto deja dos relojes en una pantalla, y
por eso cada KPI declara el suyo y el pie explica la diferencia; el ranking de
exportadores salió de la ventana de diez semanas hasta que hubo histórico, y
ahí la primera fila era otra empresa y otro orden de magnitud.

**El eje de las series sigue a ese filtro.** Una sola función, `ejeTemporal`,
decide el reparto del tiempo para todos los gráficos de serie: semanas en
Medido, los doce meses en Mensual, los años en Anual, con el subtítulo cambiando
entre *FOB por semana*, *por mes* y *por año*. Antes los tres modos reusaban el
mismo arreglo de semanas, de modo que elegir «Mensual» cambiaba los montos pero
el eje seguía rotulando 15/06 y 22/06.

Aquí la agregación sí es real y no una extrapolación: la barra de junio es la
suma de lo que entró en junio. El KPI de la tarjeta extrapola porque responde
otra pregunta —cuánto sería en un mes tipo—, de modo que los dos números no
coinciden ni deben. Y los periodos fuera de la ventana se dibujan como **hueco
declarado, nunca como cero**: hoy hay registro en tres de los doce meses y en
uno de los seis años del eje, y un cero diría que no hubo importación cuando lo
cierto es que no hay dato.

Cada vista carga su propio JSON la primera vez que se abre: el directorio de
empresas pesa 1.8 MB —460 KB comprimido— y no debe frenar la portada.

**Cada empresa tiene su perfil y su dirección**: `#empresa=20461642706`. Es el
único módulo con una página por registro —23,300— y por eso los perfiles no
viajan como un archivo cada uno ni como uno solo. Van repartidos en cien
archivos por los dos últimos dígitos del RUC: uno por empresa serían 23 mil
archivos en el repositorio para servir 2 KB cada vez, y uno solo obligaría a
bajar 9.9 MB para ver una. La partición deja cada consulta en unos 88 KB.

El perfil responde qué compra afuera esa empresa, de qué origen, en qué
cantidad y **con qué continuidad**: la ventana de diez semanas distingue al
importador de flujo —presente en casi todas— del que hizo un despacho aislado,
y eso a un canal de ventas le cambia la conversación. Incluye la descripción
comercial que escribió el propio declarante en el manifiesto, que es el detalle
más fino que existe de qué compró, con marca y modelo cuando los declara. El
mapa localizador lo dibuja un lienzo y no una imagen, porque tiene que
repintarse al cambiar de tema.

El perfil no tiene equivalente impreso: 23,300 fichas no son un anexo, son un
padrón. El informe conserva las tablas de mayores importadores y
agroexportadores, que es lo que un documento de lectura lineal puede sostener.

**La barra está ordenada por quién pregunta, no por cuándo se construyó.**
Cada vista se agregaba al final el día que se hacía, y con quince entradas la
barra —que tiene `overflow-x:auto`— dejaba fuera de pantalla justo las dos que
un comercial usa a diario. El orden es ahora Resumen, Decisiones y Canasta
primero —dónde estamos, qué está abierto, qué llevo—, después lo operativo
—Territorios, Empresas, Logística, Expansión— y al final la consulta de
mercado y comercio exterior.

**Estacionalidad se fusionó en Canasta.** Mostraba el calendario de demanda por
región; Canasta muestra ese mismo calendario con dos dimensiones más —el insumo
y el cultivo—, así que mantener las dos era pedirle al lector que eligiera entre
dos respuestas a la misma pregunta, y la peor de las dos. Lo único propio que
tenía —ver las veinticinco regiones a la vez— vive dentro de Canasta como un
bloque, y la prueba del navegador lo sigue exigiendo: fusionar dos vistas es la
manera más fácil de perder la mitad de una sin que nadie lo note. `#estacionalidad`
redirige a `#canasta`, para que un marcador viejo aterrice donde está la
respuesta y no rebote al resumen.

Las trece vistas viven en `index.html` y se conmutan por hash. El
mapa es un documento propio en `/mapa`: su lienzo ocupa el ancho completo y su
payload pesa 1.1 MB, que no tiene por qué cargarse para ver el resumen. Comparte
encabezado, navegación, tema y pie con el resto, así que se recorre como una
página más y no como un anexo.

**Tema claro y oscuro**, con tres estados: *Auto* sigue al sistema operativo,
y *Claro* u *Oscuro* lo fijan. La elección se guarda en el navegador y se
aplica antes de pintar, de modo que la página no aparece un instante en claro
antes de volverse oscura. El mapa se dibuja en canvas leyendo variables CSS,
así que cambiar el tema lo obliga a repintarse: el CSS solo alcanza al DOM.

`verificar.py` abre el sitio en un navegador real, recorre las trece vistas,
prueba la búsqueda, ejerce los filtros del mapa —comprueba que reduzcan el
conteo y que *Limpiar* restaure—, navega entre el mapa y el resto en ambos
sentidos, recorre los tres estados del tema, mide el contraste real de una
etiqueta en modo oscuro y falla si aparece un error de consola. Un `200` del
servidor no garantiza que la página no esté en blanco por un error de
JavaScript: así fue como se detectó que `Infinity` en el JSON del mapa —válido
en Python, inválido en JSON— dejaba el atlas sin dibujar.

Se sirve con `servir.py`, no con `http.server` a secas, porque hace falta
resolver `/mapa` -> `mapa.html` como la regla `cleanUrls` de `vercel.json`. Sin
eso la comprobación local pasaría por rutas que el sitio publicado no usa,
justo donde viven los enlaces de la navegación.

```
python servir.py      # en una terminal
python verificar.py   # en otra
```

---

## El reporte

**El informe está publicado aquí →
[`docs/Reporte de mercado - AgroJuntos.pdf`](docs/Reporte%20de%20mercado%20-%20AgroJuntos.pdf)**

`reporte.py` compone el informe impreso —**94 páginas A4**— y lo imprime con
Chrome headless, y deja la copia publicada en `docs/`. La estructura es de ocho
partes más el atlas regional:

| Parte | Qué responde |
|---|---|
| I · El tamaño del mercado | La base territorial, el gasto real por hectárea y por qué la superficie agrícola no es el mercado |
| II · Quién es cliente | El embudo de 2.26 M de productores a 156,880 compradores, y la economía unitaria observada |
| III · Cuándo y cómo llegar | Calendario de compra, costo de servir y puerto de salida de cada región |
| IV · Dónde empezar | Priorización de las 24 regiones, escenarios de captura, prospección con nombre propio y el mercado vecino de importación |
| V · Qué se cultiva y por dónde sale | Los 144 cultivos y el mercado que implican, las 66 partidas agroexportadas y las 15 aduanas de salida, más los cinco años de exportación medida: qué sale, cuándo sale y de dónde |
| VI · La geometría del mercado | La grilla hexagonal, los 57 territorios, el orden de apertura de centros y la cartera con nombre propio de cada territorio |
| VII · Atlas regional | Ficha y lámina por cada una de las 24 regiones, más las series de mapas pequeños con los 57 territorios y las 197 provincias |
| VIII · Metodología y fuentes | Cadena de cálculo, contraste con aduanas y limitaciones declaradas |

El impreso no perdona lo que la pantalla sí: nada refluye y nada se desplaza,
de modo que las páginas son bloques A4 explícitos y las imágenes van
incrustadas como data URI —Chrome no lee archivos locales desde una página que
imprime—.

`medir_paginas.py` carga el mismo HTML en el mismo motor y reporta, página por
página, cuánto se pasa del marco imprimible. **El ancho importa tanto como el
alto**: la hoja deja 178 mm útiles y medir sobre 180 mm reacomoda cada párrafo,
lo que esconde justamente la página que se desborda por una línea.

```
python scripts/reporte.py         # HTML + PDF
python scripts/medir_paginas.py   # falla si alguna página desborda
```

La parte II se apoya en el libro de ventas de AgroJuntos (`ventas_*.csv`), que
no se versiona aquí por confidencial: el PDF publicado sí muestra sus
resultados —facturación del período, ticket, recompra, margen y los principales
clientes por nombre—, pero los datos de origen no están, de modo que esa parte
no se reconstruye desde un clon. El resto del informe sí.

`docs/` guarda dos entregables generados: el PDF del informe y el atlas
interactivo autocontenido. Los dos se regeneran por script y se sobreescriben,
así que el historial de git acumula una versión por cada corrida que se
commitee. Si con el tiempo pesan, van a *Releases*.

---

## El histórico de aduanas

SUNAT publica los manifiestos bajo la Ley 27806 y su página índice lista unas
diez semanas. Este proyecto dio por sentado, durante meses, que fuera de esa
ventana los archivos desaparecían. **Es falso, y nunca se había probado.**

La ventana es del índice, no de los archivos: los ZIP siguen servidos mucho
después de dejar de estar listados. Se probaron diecinueve semanas, una por
trimestre entre 2022 y 2026, pidiendo el nombre deducido, y **las diecinueve
respondieron con el archivo completo**; el de la semana del 14 de febrero de
2022 trae 189,580 registros con el mismo esquema de 58 campos que el de la
semana pasada.

Así que el histórico se baja de la fuente primaria y no hay que estimarlo.
`acumular_aduanas.py` mira qué hay archivado, calcula qué semanas faltan y baja
solo esas; se puede correr todas las semanas sin pensar, y con `--desde` va
hacia atrás tantos años como haga falta.

No consulta la página índice —está detrás de un 403 y además obligaba a
guardarla a mano, que es lo que impide correr esto sin nadie delante—. Los
nombres se deducen: la semana va de lunes a domingo y el archivo se llama
`ma{día inicial}{día final}{mes final}{año}.zip`, `ma` para importación y `x`
para exportación. El 404 es la respuesta de que esa semana ya no está.

**El mes del nombre es el del último día.** `ma29050726` es la semana del 29 de
junio al 5 de julio y no la del 29 de julio; se verificó contra las fechas de
los propios registros, donde ese archivo trae 13,070 despachos de junio. Una de
cada cuatro semanas cruza el cambio de mes, así que leerlo mal las desplazaba
un mes entero y las mandaba al casillero equivocado en cualquier agrupación
mensual. Estuvo mal hasta que el histórico obligó a mirarlo de cerca.

Lo que se versiona es `datos/comercio/aduanas_manifiesto.json` —qué semanas
hay, con su SHA-256, su tamaño y cuándo se bajaron— y no los ZIP: crecen unos
40 MB por semana y git conserva cada versión para siempre. Los crudos viven en
`data/aduanas_hist/`, fuera del repositorio. El manifiesto también anota si
SUNAT **republica** una semana con contenido distinto, que es la clase de cosa
que después nadie puede explicar.

Ninguna parte del pipeline tiene ya el número de semanas escrito a mano: sale
de lo archivado. Una constante vieja anualizaría con el divisor equivocado en
cuanto entre la semana siguiente.

## Importadores de insumos

La subcategoría «importador de insumos» del directorio de empresas corre sobre
una capa propia, reconstruida operación por operación desde los manifiestos
acumulados: los cinco años. 244 semanas, 101,722 operaciones, 1,426 empresas
con operación verificada, US$ 5,505 MM FOB. Cada empresa tiene su historia
de importación dentro de su ficha —mensual, anual, por producto, por país y
por partida—.

**Los años se miden en días, no en semanas, y ocho días estuvieron perdidos
por un nombre.** Este README afirmaba «2022 a 2025 completos» con un umbral de
45 de 52 semanas. Dos cosas fallan ahí: las semanas se cuentan sobre las que
traen operación, y **52 semanas no cubren 365 días**. Contados en días, a 2025
le faltaban 8, a 2024 y 2022 les faltaban 2 y solo 2023 estaba entero.

Los huecos caían siempre en la misma semana, la que cruza el año, y se dio por
hecho que SUNAT no la publicaba. **Sí la publica: cuando cruza el año la parte
en dos archivos** —los días de diciembre en uno, los de enero en otro— y el
pipeline solo pedía el nombre de la semana entera, recibía un 404 y la anotaba
como no publicada. No siempre la parte: la del 26 de diciembre de 2022 salió
entera, y por eso 2023 era el único año sin huecos. Con los doce archivos
recuperados, **los cuatro años cerrados están enteros día por día**.

```
scripts/build_import_historico.py    extrae las lineas de insumo de cada ZIP
scripts/build_import_clasificar.py   clasifica: manda el arancel
scripts/build_import_agregados.py    agrega por empresa y por mercado
scripts/build_import_panel.py        cubo categoria x anio x partida x empresa
scripts/build_import_precios.py      US$/kg donde el kilo significa algo
```

El bloque «Qué importa este mercado» se recorre entero: mercado → año →
categoría → partida → empresa → ficha. Y donde el kilo es la unidad en que se
comercia, trae el precio de importación: la urea a US$ 0.663/kg en 2022 y US$
0.314 en 2024, con la diferencia de precio entre importadores a la vista.

Cuatro reglas la gobiernan y las cuatro están comprobadas en `verificar.py`, que
a su vez se comprueba con `auditar_pruebas.py`: reintroduce a propósito cada
defecto que las pruebas dicen cubrir y exige que salte la que corresponde. Una
prueba que nunca vio fallar su defecto no es una prueba, es una línea que
pasa —así se descubrió que la de los años sin descargar comparaba dos listas
vacías y firmaba «ok» sin mirar nada—.

1. **Un año sin semanas descargadas no es US$ 0.** Se dibuja como hueco y se
   dice con esas palabras. Un año que sí se midió y en el que la empresa no
   importó es otra cosa —un cero de verdad— y se dibuja distinto. Y un año con
   sus 52 semanas archivadas al que le faltan días del calendario no es un año
   cerrado: la ficha y el informe declaran cuántos días le faltan.
2. **La variación interanual solo compara meses enteros en los dos años.**
   Antes el tramo llegaba hasta el mes del último despacho visto, que por
   definición está a medias: comparar 30 días de agosto contra 31 resta un día
   de comercio y lo presenta como caída. Hoy el tramo se recorta a los meses
   con todos sus días descargados en ambos años y se declara cuáles quedaron
   fuera. El cambio movió la cifra publicada de +9.5% a **+9.8%**, tres
   décimas: el criterio estaba mal aunque el número casi no se moviera.
3. **Manda la partida arancelaria**, no la descripción. El 95.0% se clasifica
   solo por arancel; la descripción únicamente parte lo que la subpartida junta,
   como el 3808.93 que mete herbicidas y reguladores de crecimiento en el mismo
   casillero.
4. **El FOB importado no es facturación.** Los textos dicen «importaciones
   FOB», «valor importado» o «FOB registrado», nunca «ventas».

El detalle —fuentes, cobertura año por año, deduplicación, qué partidas entran
y cuál se sacó y por qué— está en
[`IMPORTADORES_INSUMOS_METODOLOGIA.md`](IMPORTADORES_INSUMOS_METODOLOGIA.md).

## Agroexportadores

El otro lado de la aduana, y con la misma regla que el lado importador: años
medidos, nunca anualizados. 245 semanas de manifiesto, 1,894,908 series de
embarque, 4,812 exportadores con RUC y US$ 55,106 MM FOB entre 2022 y 2026,
en 177 familias de producto y 162 destinos.

```
scripts/build_export_historico.py   extrae las lineas de agro de cada ZIP
scripts/build_export_agregados.py   agrega por empresa, mercado y territorio
scripts/build_export_panel.py       cubo producto x destino x exportador
scripts/build_export_web.py         el recorte que baja el navegador
scripts/build_figs_export.py        la serie mensual y el perfil por region
```

En importación interesa **qué** se trae y con qué partida; en exportación
interesa **a dónde** va, así que la jerarquía del cubo está dada vuelta: el
producto no se entiende sin saber si sale a Estados Unidos o a Países Bajos.

Dos cosas gobiernan lo que aquí se puede afirmar, y las dos viajan dentro de
los archivos.

### El último mes nunca está completo

El embarque se declara al salir, pero el archivo semanal se arma cuando la
declaración se **regulariza**, y entre una cosa y otra pasan 11 días en la
mediana. El último mes de la serie está incompleto aunque su semana esté
descargada.

El percentil de días no sirve para decidir cuándo un mes cerró, y conviene
decir por qué: se calcula sobre las líneas que ya llegaron, y las que faltan
son justamente las lentas. Que el p99 dé 30 días no significa que un mes de 30
días de antigüedad esté completo; significa que el 99% de lo que ya llegó llegó
en menos de 30. Es censura por la derecha, y leída al revés **inventa caídas del
último trimestre**.

Lo que sí decide es la curva de maduración, medida sobre meses de embarque con
más de 120 días —cuando el mes ya no crece—: a los 7 días se ve el 25.0% del
FOB de un mes, a los 14 el 63.0%, a los 28 el 97.0%, a los 30 el 99.5% y a los
120 el 100%. Aplicada día por día da la completitud esperada de cada mes
reciente. Un mes entra en la variación interanual solo si llega al 99.5% en los
dos años comparados, y el tramo se declara: la caída de **−5.4% de enero a
julio de 2026** se calcula así, con agosto —al 48%— fuera.

`build_export_panel.py` ya no calcula esa frontera por su cuenta: la lee de
`mercado.json`. Antes restaba 28 días fijos y declaraba una fecha distinta de
la del agregado sobre los mismos embarques, que es la clase de contradicción
que aparece cuando dos archivos calculan lo mismo por separado.

### El UBIGEO del manifiesto apunta al fundo, y se está apagando

Este proyecto dio por inservible el campo UBIGEO: se midió sobre diez semanas
de 2026, se vio vacío en el 97% del FOB y se generalizó a todo el archivo. **Es
cierto de 2026 y falso de los años anteriores**: viene lleno en el 100% del FOB
hasta 2024 y en el 60% en 2025.

Y no es el domicilio fiscal. Cruzado contra el padrón de SUNAT sobre 2024 —529
exportadores, 120,815 líneas— coincide en el distrito el 26.6% de las veces y
en el departamento el 48.8%. Las diferencias no son ruido: donde el manifiesto
dice Ica, La Libertad, Lambayeque o Piura, el padrón dice Lima. El manifiesto
apunta al fundo y el padrón a la oficina. Es el único puente directo entre la
aduana y el territorio, y da un mapa de producción exportadora que encabezan
Ica con el 22.9% del valor y La Libertad con el 21.6%.

Por eso el corte territorial se calcula solo sobre 2022–2024 y se niega a
extenderse: un mapa que incluyera 2026 sería el mapa de la caída del campo, no
el de la producción. Descargar el archivo viejo mientras SUNAT lo siga sirviendo
es lo que preserva ese dato.

### Lo que queda fuera, dicho

US$ 59 MM en 13,006 operaciones son de exportadores persona natural, cuyo
titular SUNAT no publica por la Ley 29733 de protección de datos personales:
están en los totales del mercado y en ningún corte por empresa. Quedan fuera
del recorte de cinco años US$ 1,703.3 MM de 2021 —embarques de diciembre que
regularizan en enero— y 2,702 líneas con fecha de embarque anterior, que no se
corrigen ni se borran: se cuentan y se declaran.

La unidad no es la declaración sino **la serie**: una DUA trae una línea por
partida y serie, y la clave con que este proyecto identifica cada embarque
—aduana, año, declaración y serie— ya las distingue. Por eso la repetición de
una declaración no es una anomalía como en importación: es la forma del
documento.

### Lo que baja el navegador

El dashboard no recibe `exportadores.json`: son 7.8 MB y llevan por empresa un
cubo que la pantalla no muestra. `build_export_web.py` deja el ranking, la serie
por año, el origen declarado y los tres primeros productos y destinos de cada
empresa —**1.25 MB, el 16%**— y con eso se pinta la vista entera. Lo que no se
recorta son las advertencias: la cobertura del ubigeo año por año y la frontera
de completitud viajan en el recorte, porque una cifra sin su salvedad viaja más
rápido que la salvedad.

### Lo que el archivo repite, y hay que quitar

El total salía 25% **por encima** del que publica MIDAGRI, y contrastarlo
contra esa cifra —que es lo que nadie había hecho— destapó dos cosas del
archivo de SUNAT. Ninguna es un error de este proyecto y las dos son
invisibles si no se buscan.

**Republicaciones.** SUNAT vuelve a publicar cada declaración en semanas
posteriores con el valor rectificado: misma aduana, año, declaración y serie,
mismo peso, un FOB que cambia unos miles de dólares. En 2025 eso alcanzaba al
**51% del valor**, y de 216,381 líneas repetidas, 216,303 estaban en archivos
distintos y solo 78 dentro del mismo. Una serie es una fila, así que toda
repetición es una versión nueva del mismo embarque. Se conserva la última, que
es la vigente: son US$ 19,459 MM en cinco años.

**Precios que el producto no aguanta.** Una declaración de café verde declara
US$ 37.4 millones por 56,925 kg —US$ 657 el kilo— cuando la serie anterior del
mismo documento va a 8.7. No se filtran con un umbral fijo, porque la semilla
híbrida de hortaliza cuesta legítimamente cientos de dólares el kilo: se
compara cada línea contra la mediana de su propia familia. Son 140 MM.

Depurado, 2025 pasa de US$ 20,426 MM a **14,790**. Y con eso se cae una
afirmación que este informe publicaba: la caída de 5.4% de la agroexportación
en 2026 era el arrastre de las republicaciones, que se acumulan más en los
años viejos que en el corriente. El tramo comparable da **+2.8%**.

### El universo arancelario, que era una elección tácita

Depurado, el total quedaba **12% por debajo** de los US$ 15,013 MM que publica
MIDAGRI para 2025. La explicación está medida en `diag_universo.py`, no
supuesta: el proyecto contaba como agro siete capítulos —07, 08, 09, 12, 18,
20 y 21— y la estadística oficial cuenta más. Esa elección no estaba escrita
en ninguna parte; era un `set` de siete cadenas repetido en cuatro archivos.

Ahora está en `scripts/universo.py`, es una sola, y la regla es **capítulos
del arancel menos una lista corta de partidas que no pertenecen**. La lista
corta hace falta porque a nivel de capítulo la pregunta no tiene respuesta: el
capítulo 23 son 2,126 MM de los que **1,871 son harina de pescado**, y el 15
son 802 de los que **518 son aceite de pescado**. Contarlos enteros habría
inflado el agro con la pesca; dejarlos fuera habría perdido el aceite de
palma, el alimento balanceado y el salvado, que sí son agro.

Entraron 18 capítulos y quedaron fuera, a propósito, el 03 y el 16
enteros —pescado y conservas—, las partidas 1504 y 2301, la cosmética del
capítulo 33 y los tejidos de los capítulos 52 y 53.

| | 2025 |
|---|---|
| siete capítulos, como estaba | US$ 13,230 MM · −12% |
| universo escrito, depurado | **US$ 14,790 MM · −1.5%** |
| MIDAGRI | US$ 15,013 MM |

Lo que queda de diferencia es de criterio —MIDAGRI ancla en la regularización
y no en el embarque, y arrastra rectificaciones posteriores al corte—, no
capítulos olvidados. La ampliación vale US$ 7,295 MM del período de cinco
años, el 13% del total, y trae **758 exportadores** que antes no estaban en la
cartera: es cartera nueva y no solo FOB nuevo. `mercado.json` guarda el
desglose por capítulo en su bloque `universo`, para que la plataforma marque
las familias añadidas en vez de anunciar un salto sin explicación.

El diagnóstico costó tres intentos, y los dos primeros fallaron igual: no
reproducían el universo conocido y aun así devolvían un desglose de aspecto
razonable. El primero leía solo los archivos del año, cuando los embarques de
2025 aparecen también en archivos de 2026. El segundo tomaba el capítulo de
`PART_NANDI` sin rellenar, y **ese campo llega sin el cero inicial** —la uva
viene como `806100000`—, así que perdía frutas, hortalizas y café enteros. El
script imprime ahora al lado lo que dice el pipeline: si el control no cuadra,
se ve en la misma línea.

## Dónde se produce lo que se embarca

El proyecto repartía el valor exportado por el domicilio fiscal del padrón,
que lo acumula en Lima: una agroexportadora con oficina en San Isidro aportaba
su tonelaje a la capital. Para decidir dónde abrir un almacén ese es
justamente el error que importa.

`build_acopio.py` sitúa la carga con el UBIGEO del manifiesto, que apunta al
lugar de producción. Son **629 distritos con coordenada, 3,883 empresas y
US$ 32,835 MM** entre 2022 y 2024 —los años en que SUNAT llenó el campo—, cada
uno con su producto líder, su mes pico y el centro que lo sirve.

```
datos/acopio/acopio_distrito.csv    los 629 distritos, con centro y horas
datos/acopio/acopio_hub.csv         cuánto alcanza cada centro a 2, 4 y 6 h
datos/acopio/acopio_territorio.csv  la carga de cada territorio de venta
datos/acopio/acopio_huerfanos.csv   la que no cae en ningún territorio
```

**La pregunta de inventario no es cuánto mercado hay sino cuánto se alcanza.**
Pisco llega a US$ 6,254 MM a dos horas y Chiclayo a 2,142; Chiclayo pasa de
2,142 a 8,999 al abrir el radio de dos a seis, así que lo que vale depende del
compromiso de entrega. Fuera de alcance quedan **22 distritos con 130 MM**, y
lo que los deja fuera ya no es la distancia: ocho de ellos —Santa Anita entre
ellos, que son 87 de esos 130— no traen geometría en la capa distrital, y el
resto son ribereños de Loreto y Madre de Dios sin ninguna ruta por carretera.

Esa cifra era **41 distritos y US$ 2,257 MM**, y la diferencia no fue abrir
ningún almacén. El centro que sirve a cada distrito se heredaba de la celda H3
que le tocaba encima, y `hubs_asignacion.csv` solo tiene las celdas **con
clientes**: donde produce la agroindustria grande y no el pequeño agricultor no
hay celda, y el distrito salía sin centro. Olmos —1,599 MM de arándano, 118
empresas, 56,369 ha— encabezaba así la lista de carga que nadie alcanza, y está
a **2.5 horas de Chiclayo**, dentro de la promesa de cuatro. `build_hubs.py`
rutea ahora los 1,826 distritos del país desde la red elegida, al punto medio
de sus sectores agrícolas —donde está la tierra, no el centro del polígono— y
al primero de los quince nodos viales más cercanos al que de verdad se llegue:
el grafo de OSM tiene tramos sueltos, y engancharse al más cercano a secas
dejaba a Chao, con 1,602 MM y a cinco kilómetros de la Panamericana, sin salida
al resto del país.

**La mitad de la carga cae fuera de los territorios de venta.** US$ 17,670 MM
en 416 distritos, el 54%. No es que estén mal trazados —dentro se exportan
8,308 dólares por hectárea agrícola y fuera 4,856, así que capturan lo denso—
sino que se detectaron sobre la densidad del mercado de insumos, y la demanda
exportadora no se concentra en el mismo sitio. Se intentó agrupar los
huérfanos para proponer territorios nuevos y el método no sirve: los distritos
se alinean a lo largo de la costa y un DBSCAN por cercanía los encadena en un
bloque de 322, que no es un territorio sino el país. Van listados por valor,
que es lo que permite decidirlos uno a uno.

### Quién tiene planta certificada

El manifiesto dice quién embarca y desde dónde; no dice quién tiene
infraestructura de acopio. Eso lo publica SENASA por par producto–mercado, y
`build_senasa.py` lo recoge: **296 plantas de empaque y 21,046 lugares de
producción** de arándano, palta, cítricos, limón y mango.

Los dos universos responden preguntas distintas y mezclarlos da un porcentaje
que no dice nada. Las plantas son infraestructura —pocas, grandes, 101
embarcan a su nombre— y **las 195 que no embarcan son el perfil de un socio
logístico**: tienen acopio y venden por medio de terceros. Los lugares de
producción son fundos certificados, casi todos de personas naturales que
embarcan a través de un tercero: no son socios, son demanda de insumo con
certificación encima.

Tres cosas del catálogo que conviene saber. La mitad de las listas son de
establecimientos **extranjeros** autorizados a exportar al Perú —manzanas de
Chile, naranjas de Egipto— y se filtran por el nombre de la publicación. Cada
lista nombra la columna del titular a su manera —`ENTERPRISE NAME`, `COMPANY
NAME`, `PACKINGHOUSE NAME`— y la variante que falta se lleva la hoja entera en
silencio: así se perdieron primero la lista de limón y después las plantas de
mango. Y el mercado de destino no está en la hoja, va en el nombre del
archivo.

**Estas listas no ubican.** Traen la región y nada más fino, y cruzarlas
contra el padrón para sacar la dirección devuelve la oficina: Agrícola Pampa
Baja figura en Arequipa según SENASA y en Ate según el padrón. Se usan como
atributo sobre empresas que el manifiesto ya sitúa.

El detalle —fuentes, universo, depuración, las dos reglas que gobiernan lo que
se puede afirmar y el orden de ejecución— está en
[`AGROEXPORTACION_METODOLOGIA.md`](AGROEXPORTACION_METODOLOGIA.md).

De **uva y espárrago** no hay lista: SENASA publica solo los protocolos de
trabajo por mercado, en PDF —se revisaron las 672 publicaciones del catálogo—.
De esos dos no se sabe quién tiene planta, pero el manifiesto sí los sitúa:
uva son US$ 4,892 MM en 105 distritos y las hortalizas frescas del espárrago
1,178 MM en 138. Cada uno con su salvedad, porque la partida agrupa más de lo
que el nombre sugiere: la de uva junta fresca y pasas, y la del espárrago lo
mete con otras hortalizas frescas sin manera de separarlos.

## La red, el canal y el relieve

Tres capas que se explican en sus propios documentos, porque cada una toca
decisiones distintas y el README no es sitio para desarrollarlas:

- **[`TOPOGRAFIA_METODOLOGIA.md`](TOPOGRAFIA_METODOLOGIA.md)** — el relieve como
  dato y no como fondo de mapa: la cota de cada capa, los pisos ecológicos y la
  pendiente en el tiempo de viaje. La sierra pagaba una cuarta parte de su
  viaje sin que ninguna cifra lo dijera, y el mercado a menos de dos horas cayó
  de 76.2% a 67.3% al contarlo.
- **[`RED_Y_CANAL_METODOLOGIA.md`](RED_Y_CANAL_METODOLOGIA.md)** — los ocho
  centros con promesa diferenciada —cuatro horas en costa, seis en sierra y
  selva—, quién resurte a quién, y la red de canal: 3,270 puntos que ya
  existen, 94,922 centros poblados del padrón del INEI, y la cadena completa
  que llega al 34.6% de los clientes.

## Sobre los datos crudos de aduanas

`agro_insumos_pe_data/raw_data/sunat/` versiona los 20 archivos DBF originales
(197 MB) para que el análisis sea reproducible tal cual. El histórico completo
—hoy 244 semanas y 4.2 GB— vive en `data/aduanas_hist/`, fuera del repositorio, y se
reconstruye con `acumular_aduanas.py` desde el propio servidor de SUNAT.

Si con el tiempo se acumulan muchas corridas, lo sano es mover los archivos
crudos a *Releases* de GitHub en vez de al historial de git, que conserva cada
versión para siempre y encarece cada clon.

---

## Licencia

Los datos derivados de OpenStreetMap se distribuyen bajo ODbL. Los datos
oficiales de MIDAGRI, INEI y SUNAT son de acceso público. El código de este
repositorio es de AgroJuntos.
