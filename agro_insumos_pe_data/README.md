# agro_insumos_pe_data

Extracción masiva y procesamiento de las empresas que **importan insumos
agrícolas** y **exportan producción agraria** en el Perú, a partir de los
microdatos de aduanas de SUNAT.

Todo el contenido de `processed_data/` se genera corriendo los scripts en
orden. No hay transcripción manual.

---

## Resultado

| | |
|---|---|
| Líneas de despacho leídas | 2,953,512 importación · 387,669 exportación |
| Líneas de insumos aisladas | 4,429 |
| **Importadores de insumos agrícolas** | **491** empresas con RUC |
| — excluyendo nitrato de amonio de uso minero | 446 |
| **Agroexportadores** | **1,529** empresas con RUC |
| FOB de insumos importados | US$ 252.5 MM en 10 semanas |
| Anualizado | US$ 1,313 MM CIF |
| Período observado | 15 jun – 27 ago 2026 |

---

## Cómo correrlo

```bash
python -m venv --system-site-packages .venv
.venv/Scripts/python.exe scripts/01_github_datasets.py   # contexto GitHub
.venv/Scripts/python.exe scripts/02_sunat_aduanas.py     # microdatos SUNAT
.venv/Scripts/python.exe scripts/03_midagri.py           # contexto productivo
.venv/Scripts/python.exe scripts/process_data.py         # filtrado y salidas
```

El venv se crea con `--system-site-packages` porque en este entorno `pip` no
tiene salida a la red aunque PyPI responda a `curl`. Las dependencias de
`requirements.txt` ya están presentes en el Python del sistema. En una máquina
con pip funcional, `pip install -r requirements.txt` sobre un venv limpio.

---

## Estructura

```
agro_insumos_pe_data/
├── scripts/
│   ├── 01_github_datasets.py    repositorios de contexto vía API de GitHub
│   ├── 02_sunat_aduanas.py      microdatos de aduanas, con verificación
│   ├── 03_midagri.py            anuario agrícola y costos de producción
│   └── process_data.py          parser DBF, filtrado y consolidación
├── raw_data/
│   ├── github/                  8 archivos (GeoJSON nacional, .rda)
│   ├── sunat/                   20 ZIP · 197 MB · 10 semanas
│   └── midagri/                 anuario 2022 y 2023, costos INEI
├── processed_data/
│   ├── importadores_insumos.csv / .json          491 empresas
│   ├── importadores_insumos_agro.csv / .json     446, sin uso dual minero
│   ├── agroexportadores.csv / .json            1,529 empresas
│   ├── importaciones_detalle.csv               4,429 líneas de despacho
│   └── _metadata.json                          parámetros de la corrida
└── logs/
```

### Columnas de las tablas de empresas

`ruc` · `razon_social` · `nombre_limpio` (sin sufijo societario) · `rubro` ·
`fob_usd` · `peso_kg` · `toneladas` · `operaciones` · `partidas` ·
`semanas_activo` · `paises` · `fob_anualizado` · `uso_dual`

`semanas_activo` indica en cuántas de las diez semanas la empresa registró
despacho: diez significa flujo continuo, y distingue al importador habitual del
ocasional.

---

## Qué se descargó, y qué no

**SUNAT · microdatos de aduanas — completo.** No hizo falta el plan de
contingencia por CAPTCHA: SUNAT publica las bases completas de regímenes
definitivos en `aduanet.gob.pe/aduanas/informae` bajo la Ley 27806 de
Transparencia, como DBF comprimidos de descarga directa. Se bajaron las 20
disponibles (10 de importación, 10 de exportación) con verificación de
integridad; el servidor corta las conexiones largas y los archivos de
importación pesan 263 MB descomprimidos.

SUNAT mantiene una **ventana móvil de unas diez semanas**, no un histórico.
Para construir una serie anual hay que correr `02_sunat_aduanas.py` de forma
periódica y acumular.

**MIDAGRI e INEI — completo.** Anuario de Producción Agrícola 2022 y 2023 y el
estudio de costos de producción del INEI. `siea.midagri.gob.pe` no resolvía DNS
y `datosabiertos.gob.pe` devolvía 418; ambos se sortearon por el CDN de gob.pe.

**GitHub — parcial, por límites de los repositorios.**

| Repositorio | Resultado |
|---|---|
| `juaneladio/peru-geojson` | 4 GeoJSON: UBIGEO nacional de departamentos, provincias y distritos |
| `omarbenites/cropdatape` | solo `cropdatape.rda`, serialización binaria de R. **Requiere R para leerse**; el anuario del MIDAGRI cubre lo mismo con 145 cultivos en vez de 6 |
| `joseluisq/peru-geojson-datasets` | solo Lima y Callao, pese al nombre. Sin cobertura nacional |
| `PaulESantos/geoperu` | solo `peru.rda`, misma limitación de formato |

Por eso se agregó `juaneladio/peru-geojson`, que sí publica el UBIGEO nacional
en formato legible.

---

## Filtros aplicados

**Por partida arancelaria** — las seis solicitadas más dos añadidas:

| Partida | Familia |
|---|---|
| 3102 3103 3104 3105 | fertilizantes nitrogenados, fosfatados, potásicos y compuestos |
| 3808 | agroquímicos: insecticidas, fungicidas, herbicidas |
| 1209 | semillas para siembra |
| 3101 · 2510 | añadidas: abono orgánico y fosfato natural, que son fertilizante y quedaban fuera de la lista original |

**Por texto** sobre la descripción comercial declarada, para recuperar
despachos mal clasificados: *fertilizante, abono, urea, nitrato de amonio,
sulfato de amonio, fosfato diamónico, cloruro de potasio, insecticida,
fungicida, herbicida, acaricida, nematicida, plaguicida, pesticida, semilla
para siembra, bioestimulante, coadyuvante*.

De las 4,429 líneas aisladas, **3,964 entraron por partida y 465 se recuperaron
por texto** — un 10% que el filtro arancelario solo habría perdido.

**Limpieza:** RUC validado a 11 dígitos, razón social normalizada quitando
sufijos societarios de forma iterativa (hay nombres con doble sufijo), y
consolidación por RUC sumando FOB y peso.

---

## Advertencia sobre el nitrato de amonio

La partida **3102 incluye nitrato de amonio**, que es fertilizante y a la vez
base de los explosivos de minería. Sin separarlo, el ranking de "importadores
de insumos agrícolas" lo encabezan Orica, Exsa y Famesa, que no compiten en el
agro.

El campo `uso_dual` marca esas líneas y `importadores_insumos_agro.csv` las
excluye. Es la tabla que sirve para leer competencia agrícola: 446 empresas,
encabezadas por Tecnología Química y Comercio, Bayer, Farmex y Hortus.

---

## Otras advertencias

- **Diez semanas no son un año.** Los valores anualizados extrapolan el período
  sin corregir estacionalidad. La importación de fertilizante se concentra
  antes de la campaña grande, de modo que el anualizado es orden de magnitud,
  no proyección.
- **El FOB de importación es valor en aduana**, anterior al margen del canal.
  No es precio al productor.
- **La razón social no dice dónde opera la empresa.** Para ubicarla hace falta
  cruzar el RUC contra el padrón de SUNAT.

---

## Fuentes

- **SUNAT** · Bases de datos de regímenes definitivos —
  `aduanet.gob.pe/aduanas/informae` · Ley 27806 de Transparencia
- **MIDAGRI** · Anuario de Producción Agrícola 2022 y 2023
- **INEI** · Costos de producción para la actividad agropecuaria, ENA 2018
- **OpenStreetMap / colaboradores** vía los repositorios de GeoJSON, bajo ODbL
