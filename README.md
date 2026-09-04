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
| Importadores de insumos agrícolas | 491 |
| Agroexportadores con RUC verificado | 1,529 |
| Importación de insumos, anualizada | US$ 1,313 MM CIF |
| Sectores estadísticos georreferenciados | 7,036 |

El SAM está a distancia razonable: **74.6% a menos de dos horas** de un centro
provincial, medido por ruteo sobre la red vial. La demanda se concentra:
**45% entre setiembre y diciembre**.

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
| `datos/logistica/ruteo_sector.csv` | Horas al centro provincial y al puerto, ruteadas sobre la red vial |
| `datos/estacionalidad/estacionalidad_region.csv` | Demanda mes a mes, mes pico y concentración |
| `datos/empresas/empresas_agro_activas.csv` | Empresas con RUC, razón social, clase y distrito |
| `datos/comercio/comercio_importadores.csv` | Quién importa fertilizante y agroquímico, con valor FOB y distrito |
| `datos/comercio/comercio_exportadores.csv` | Los agroexportadores del país, con RUC, FOB y destinos |
| `datos/geoespacial/h3_r5.csv` | 1,992 celdas hexagonales de ~292 km² con mercado, clientes y accesibilidad |
| `datos/geoespacial/clusters_territorio.csv` | 57 territorios de venta detectados por densidad |
| `datos/geoespacial/hubs_cobertura.csv` | Orden óptimo de apertura de centros, a 2, 4 y 6 horas |
| `agro_insumos_pe_data/processed_data/importadores_insumos_agro.csv` | 446 importadores de insumos, sin el nitrato de amonio de uso minero |
| `agro_insumos_pe_data/processed_data/agroexportadores.csv` | 1,529 agroexportadores consolidados por RUC |

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
listar_aduanas.py         lista los archivos de aduanas publicados
bajar_aduanas.py          los descarga con verificación de integridad
build_aduanas.py          lee los DBF y filtra partidas de insumos agrícolas
build_comercio.py         cruza aduanas con el padrón para ubicar cada empresa
build_modelo_v3.py        modelo final con logística y estacionalidad
grafo_vial.py             grafo vial contraído: de 5.2 M de nodos a 95 mil
build_h3.py               agrega todas las capas a grilla hexagonal H3
build_clusters.py         territorios de venta por densidad (DBSCAN)
build_hubs.py             ubicación de centros por cobertura máxima
build_vial_mapa.py        simplifica la red vial principal para dibujarla
build_mapa_geo.py         empaqueta las capas para el atlas web
build_atlas_html.py       compone plantilla + datos en un HTML autónomo
build_cultivos.py         qué se siembra en cada región, y qué mercado implica
build_agroexport.py       qué se exporta y por qué aduana sale, desde el manifiesto
build_dashboard_data.py   arma los JSON que consume el sitio
build_mapas_pdf.py        figuras del reporte
build_relieve.py          sombreado de relieve por departamento
build_cultivo.py          huella cultivada desde el landuse de OSM
build_territorios.py      da forma a los territorios de venta para dibujarlos
build_laminas_dep.py      una lámina a página completa por departamento
reporte.py                reporte PDF
medir_paginas.py          mide cada página del reporte contra el marco A4
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
vías, 5.2 millones de nodos. La velocidad de cada tramo es su clase de vía
ajustada por superficie y limitada por la velocidad máxima señalizada. No modela
congestión ni cierres estacionales, y 143 de los 7,036 sectores quedan fuera del
grafo por no tener vía mapeada cerca. `logistica_sector.csv` conserva la
estimación geodésica previa para contraste.

**Los datos de aduanas cubren diez semanas**, de junio a agosto de 2026 —
SUNAT mantiene una ventana móvil, no un histórico—. Las cifras anualizadas
extrapolan ese período sin corregir estacionalidad y deben leerse como orden de
magnitud. La partida 3102 incluye nitrato de amonio, que es fertilizante y a la
vez base de explosivos de minería: empresas como Orica o Famesa aparecen por ese
uso y no por el agro; el campo `uso_dual` las marca.

**El domicilio de una empresa no es donde cultiva.** La ubicación viene del
domicilio fiscal del padrón, y los agroexportadores suelen estar registrados en
Lima aunque su fundo esté en La Libertad o Ica.

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

**Centros de distribución.** Cobertura máxima con algoritmo voraz sobre 129
ciudades capitales, evaluadas contra tiempos ruteados. El resultado corrige una
intuición: **a dos horas, seis centros cubren apenas el 26%** del mercado —la
agricultura está demasiado dispersa—, mientras que **a seis horas cubren el
75%**. El radio de operación, no el número de almacenes, es lo que decide la
cobertura.

El atlas interactivo está en `docs/atlas_geo.html` y publicado en
[agrojuntos.vercel.app/mapa](https://agrojuntos.vercel.app/mapa). Filtra por
departamento, región natural y búsqueda de provincia o ciudad —los totales
del encabezado se recalculan sobre lo filtrado—, y superpone la red vial en
tres niveles sobre 194 capitales de provincia y los puertos agroexportadores.
Es la capa que explica el mapa: se ve por qué un valle con mercado alto queda
lejos en tiempo, que es lo que el color por sí solo no dice.

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
| Territorios | Los 57 núcleos de venta, con extensión y si se recorren en un día |
| Empresas | Directorio buscable de 22,437 empresas con RUC, clase, ubicación y FOB de comercio exterior |
| Productos | Qué se cultiva, qué se exporta y por qué aduana sale, filtrable por región |
| Comercio | Importadores de insumos y agroexportadores, desde el manifiesto de aduanas |
| Estacionalidad | Calendario de demanda mes a mes por región |
| Logística | Horas al centro provincial y al puerto, y el costo de servir cada región |
| Expansión | Orden óptimo de apertura de centros según el radio que se acepte |
| Método | Cadena de cálculo, fuentes y limitaciones declaradas |
| Mapa | Atlas geoespacial con las cinco capas |

Cada vista carga su propio JSON la primera vez que se abre: el directorio de
empresas pesa 1.7 MB —460 KB comprimido— y no debe frenar la portada.

Las diez primeras vistas viven en `index.html` y se conmutan por hash. El
mapa es un documento propio en `/mapa`: su lienzo ocupa el ancho completo y su
payload pesa 1.1 MB, que no tiene por qué cargarse para ver el resumen. Comparte
encabezado, navegación, tema y pie con el resto, así que se recorre como una
página más y no como un anexo.

**Tema claro y oscuro**, con tres estados: *Auto* sigue al sistema operativo,
y *Claro* u *Oscuro* lo fijan. La elección se guarda en el navegador y se
aplica antes de pintar, de modo que la página no aparece un instante en claro
antes de volverse oscura. El mapa se dibuja en canvas leyendo variables CSS,
así que cambiar el tema lo obliga a repintarse: el CSS solo alcanza al DOM.

`verificar.py` abre el sitio en un navegador real, recorre las diez vistas,
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

`reporte.py` compone el informe impreso —**81 páginas A4**— y lo imprime con
Chrome headless. La estructura es de ocho partes más el atlas regional:

| Parte | Qué responde |
|---|---|
| I · El tamaño del mercado | La base territorial, el gasto real por hectárea y por qué la superficie agrícola no es el mercado |
| II · Quién es cliente | El embudo de 2.26 M de productores a 156,880 compradores, y la economía unitaria observada |
| III · Cuándo y cómo llegar | Calendario de compra, costo de servir y puerto de salida de cada región |
| IV · Dónde empezar | Priorización de las 24 regiones, escenarios de captura y prospección con nombre propio |
| V · Qué se cultiva y por dónde sale | Los 144 cultivos y el mercado que implican, las 66 partidas agroexportadas y las 15 aduanas de salida |
| VI · La geometría del mercado | La grilla hexagonal, los 57 territorios de venta y el orden de apertura de centros |
| VII · Atlas regional | Ficha y lámina a página completa por cada una de las 24 regiones |
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
no se versiona aquí por confidencial. El resto del informe se reconstruye
íntegramente con lo que está en este repositorio.

---

## Sobre los datos crudos de aduanas

`agro_insumos_pe_data/raw_data/sunat/` versiona los 20 archivos DBF originales
(197 MB) para que el análisis sea reproducible tal cual, sin depender de que
SUNAT siga publicando esas semanas. Conviene saber que **SUNAT mantiene una
ventana móvil de unas diez semanas, no un histórico**: acumular series exige
correr `02_sunat_aduanas.py` de forma periódica.

Si con el tiempo se acumulan muchas corridas, lo sano es mover los archivos
crudos a *Releases* de GitHub en vez de al historial de git, que conserva cada
versión para siempre y encarece cada clon.

---

## Licencia

Los datos derivados de OpenStreetMap se distribuyen bajo ODbL. Los datos
oficiales de MIDAGRI, INEI y SUNAT son de acceso público. El código de este
repositorio es de AgroJuntos.
