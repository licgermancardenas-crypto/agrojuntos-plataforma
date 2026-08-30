# AgroJuntos · Plataforma de datos

Mapeo del mercado peruano de insumos agrícolas: dónde está la tierra que
produce, quién compra, cuándo compra y cuánto cuesta llegar.

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
| Sectores estadísticos georreferenciados | 7,036 |

El SAM está a distancia razonable: **71% a menos de dos horas** de un centro
provincial. La demanda se concentra: **45% entre setiembre y diciembre**.

---

## Estructura

```
datos/
  mercado/          TAM, SAM, embudo de clientes, costos por cultivo
  territorio/       7,036 sectores estadísticos con superficie y mercado
  logistica/        tiempos de viaje, costo de servir, puertos
  estacionalidad/   calendario mensual de demanda por región y cultivo
  empresas/         21,063 empresas agrícolas con RUC; prospectos OSM
  geo/              geometrías: sectores y límites administrativos
scripts/            el pipeline completo, en orden de dependencia
docs/figuras/       mapas y gráficos generados
```

### Archivos clave

| Archivo | Qué contiene |
|---|---|
| `datos/mercado/modelo_v3_departamento.csv` | Modelo final: mercado, clientes, logística, estacionalidad y score por región |
| `datos/territorio/sectores_2024.csv` | Los 7,036 sectores con UBIGEO, hectáreas y centroide |
| `datos/logistica/logistica_sector.csv` | Horas al centro provincial y al puerto, costo de viaje |
| `datos/estacionalidad/estacionalidad_region.csv` | Demanda mes a mes, mes pico y concentración |
| `datos/empresas/empresas_agro_activas.csv` | Empresas con RUC, razón social, clase y distrito |

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
build_modelo_v3.py        modelo final con logística y estacionalidad
build_mapas_pdf.py        figuras del reporte
reporte.py                reporte PDF
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

**Los tiempos de viaje son estimados, no ruteados.** Distancia geodésica
corregida por velocidad efectiva y factor de rodeo según región natural. La red
vial de OSM ya permite reemplazarlos por tiempos medidos.

**Las empresas se clasifican por razón social**, no por código CIIU: el padrón
reducido de SUNAT no lo incluye. La clasificación subestima —no ve a la empresa
con nombre neutro— y se restringe a personas jurídicas.

**El dimensionamiento de mercado es una estimación**, no una estadística
oficial. Los datos territoriales sí lo son y se citan uno a uno. Como contraste
externo: el modelo estima US$ 1,038 MM de fertilizante a precio de finca, contra
US$ 693 MM CIF importados en 2024, que cubren el 89.5% de la oferta nacional.

---

## Licencia

Los datos derivados de OpenStreetMap se distribuyen bajo ODbL. Los datos
oficiales de MIDAGRI, INEI y SUNAT son de acceso público. El código de este
repositorio es de AgroJuntos.
