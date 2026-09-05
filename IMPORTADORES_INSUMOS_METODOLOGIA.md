# Importadores de insumos · metodología

Cómo se reconstruye la importación de insumos agrícolas del Perú, empresa por
empresa, desde los microdatos de aduanas. Todo lo que se muestra en el módulo
sale de este pipeline y se puede rastrear hasta la línea original del
manifiesto.

Estado al cierre de este documento: **116 semanas archivadas**, 45,446
operaciones, 1,095 empresas con operación verificada, US$ 2,655.1 MM FOB y US$
3,002.8 MM CIF. **2022 y 2023 están completos: 52 semanas cada uno.** La
descarga histórica sigue corriendo sobre 2024 y 2025.

---

## El hallazgo que hizo posible esto

El proyecto venía afirmando —en el README, en el informe impreso y en cada
nota al pie— que **SUNAT mantiene una ventana móvil de diez semanas y no un
histórico**. Es cierto de la página índice y falso de los archivos.

Los ZIP siguen servidos mucho después de dejar de estar listados. Se probaron
diecinueve semanas, una por trimestre de 2022 a 2026, pidiendo el nombre
deducido: **las diecinueve respondieron con el archivo completo**. El de la
semana del 14 de febrero de 2022 trae 189,580 registros con el mismo esquema de
58 campos que el de la semana pasada.

Nunca se había probado. Se había dado por bueno porque estaba escrito.

Consecuencia: los cinco años que el módulo necesita **se bajan de la fuente
primaria**, no de fuentes secundarias ni de estimaciones.

---

## Fuentes

| Fuente | Qué aporta | Cobertura | Cómo se obtiene |
|---|---|---|---|
| **SUNAT / Aduanas** · microdatos de manifiestos, régimen definitivo de importación (Ley 27806) | Toda la información de importación: RUC, razón social, partida NANDINA de 10 dígitos, tres campos de descripción, FOB, flete, seguro, peso, cantidad, país de origen y de adquisición, puerto de embarque, aduana, agente y fechas | Semanal, de 2022-01-03 en adelante | `http://www.aduanet.gob.pe/aduanas/informae/ma{DDinicio}{DDfin}{MMfin}{AA}.zip` |
| **SUNAT** · padrón reducido del RUC | Identidad, estado, condición y domicilio fiscal del importador | Vigente | Ya en el pipeline (`build_empresas.py`) |

**No se usó ninguna fuente secundaria.** Todo número del módulo proviene del
manifiesto de aduanas. Si en el futuro se agrega una, debe quedar marcada en la
columna `fuente` de `operaciones.csv`, que existe precisamente para eso.

### Cómo se obtienen los archivos

No se consulta la página índice: está detrás de un 403 y además obligaba a
guardarla a mano, lo que impide correr el proceso sin una persona delante. Los
nombres se deducen —la semana va de lunes a domingo— y se pide cada uno. Un 404
significa que esa semana no está disponible.

**El mes del nombre es el del último día.** `ma29050726` es la semana del 29 de
junio al 5 de julio, no la del 29 de julio. Se verificó contra las fechas de los
propios registros: ese archivo trae 13,070 despachos de junio. Una de cada
cuatro semanas cruza el cambio de mes, así que leerlo mal desplazaba esas
semanas un mes entero.

---

## Identificación del importador

**La llave es el RUC** (`LIBR_TRIBU`), tal como viene en el manifiesto. No se
unen empresas por parecido de nombre: la razón social se conserva como dato
descriptivo y, cuando una misma empresa aparece con variantes de escritura, se
toma la forma más frecuente de ese RUC.

Se descarta cualquier registro cuyo RUC no tenga once dígitos.

Nunca se agrupan dos RUC distintos, aunque los nombres se parezcan. El proyecto
ya se quemó con eso: cruzar por nombre de distrito puso al 13% del padrón en
coordenadas equivocadas, porque hay cuatro «San Juan» separados por 800 km.

---

## Deduplicación

Cada línea de manifiesto ampara una serie de una declaración. La llave natural
es **aduana + año de presentación + número correlativo + número de serie**
(`CODI_ADUAN`, `ANO_PRESE`, `NUME_CORRE`, `NUME_SERIE`), y se guarda en la
columna `declaracion`.

Resultado del control: **0 declaraciones repetidas en 45,446 operaciones.** Los
archivos semanales no se solapan.

---

## Universo: qué cuenta como insumo agrícola

Se define **por partida arancelaria**, que es la única clasificación con
autoridad:

| Partida | Qué es |
|---|---|
| 3101–3105 | Fertilizantes: orgánicos, nitrogenados, fosfatados, potásicos y compuestos |
| 3808 | Protección de cultivos |
| 1209 | Semilla para siembra |
| 0601, 0602 | Bulbos, tubérculos, plantines y plantas vivas |

### Lo que se sacó, y por qué

**3402 — agentes de superficie.** Se incluyó pensando en adyuvantes agrícolas.
La evidencia lo descartó: de sus US$ 134 MM, lo que más pesa es *BASE
DETERGENTE*, *DETERGENTE EN POLVO PARA LAVAR ROPA* y *ARIEL*. El adyuvante
agrícola comparte partida con el jabón doméstico y no hay forma de separarlos
por arancel: entra entero o no entra. **No entra.**

Es el mismo caso que el nitrato de amonio de uso minero que el proyecto ya
documenta en la partida 3102.

---

## Clasificación por producto

**Manda el arancel; la descripción solo desempata.** La subpartida es una
clasificación con autoridad, la descripción la escribe el declarante.

**Nivel 1 — la subpartida decide.** Gana el prefijo más largo que calce:

| Subpartida | Categoría |
|---|---|
| 3808.91 | Insecticidas |
| 3808.92 | Fungicidas |
| 3808.93 | Herbicidas |
| 3808.94 | Desinfectantes agrícolas |
| 3808.99 | Otros fitosanitarios |
| 3808.5x, 3808.6x | Fitosanitarios restringidos |
| 3101 / 3102 / 3103 / 3104 / 3105 | Fertilizantes por tipo |
| 1209 | Semillas |
| 0601, 0602 | Plantines y bulbos |

**Nivel 2 — la descripción parte lo que la subpartida junta.** Cada regla
declara en qué partidas puede actuar; fuera de ellas no se aplica.

La subpartida 3808.93 se llama, textualmente, «herbicidas, inhibidores de
germinación y **reguladores del crecimiento** de las plantas»: son tres cosas en
un mismo casillero y el arancel no las separa. Ahí sí corresponde mirar el
texto. Se comprobó que funciona: de los US$ 14.3 MM que mencionan «regulador»,
**13.6 caen en 3808.93**. La palabra confirma lo que la partida ya insinuaba,
que es la única situación en que una palabra decide algo.

| Categoría | Actúa dentro de | Se reconoce por |
|---|---|---|
| Reguladores de crecimiento | 3808.93 | giberélico, paclobutrazol, ethephon, citoquinina, auxina |
| Biológicos | 3808 | *Bacillus*, *Trichoderma*, *Beauveria*, *Metarhizium*, micorriza |
| Nematicidas | 3808.91, 3808.99 | nematicida, nematodo |
| Bioestimulantes | 3101, 3105 | bioestimulante, extracto de alga, aminoácido, húmico, fúlvico |
| Fertilizantes foliares | 3105 | foliar |
| Nutrición vegetal | 3105 | quelato, micronutriente, manganeso, molibdeno |

**El 94.8% se clasifica solo por arancel** (43,075 de 45,446); el 5.2% restante
se desempata con la descripción. Ninguna operación queda sin categoría.

Una categoría más que se pensó y no sobrevivió: **micronutrientes** mueve US$
0.5 MM en cuarenta semanas, muy poco para casillero propio. Va dentro de
nutrición vegetal.

---

## Fechas: por qué no se usa la semana del archivo

Cada registro trae sus propias fechas —recepción, llegada, embarque— y esas son
las que mandan. Una declaración recibida el 30 de junio aparece en el archivo
de la semana que cierra en julio; contarla como de julio corre el mes entero.

Se usa `FECH_RECEP` y, si falta, `FECH_LLEGA`. Solo cuando ninguna es válida se
cae a la semana del archivo, y queda registrado en la columna `semana_archivo`
para poder auditarlo.

---

## Valor

- **FOB**: `FOB_DOLPOL`, tal cual.
- **CIF**: `FOB_DOLPOL + FLE_DOLAR + SEG_DOLAR`. No es una estimación: es la
  definición de CIF y los tres componentes vienen en el registro.

**El FOB importado no es facturación.** No son ventas, ni ingresos, ni tamaño
de la empresa. Los textos del módulo dicen «importaciones FOB», «valor
importado» y «FOB registrado», nunca «ventas».

---

## Lo que la fuente no tiene

**Proveedor internacional.** El manifiesto trae país de origen, país de
adquisición y el agente de aduana local, pero **no publica al exportador del
otro lado**. La columna existe y queda vacía; no se rellena con el agente, que
es otra cosa.

---

## Validación automática

Se corre antes de publicar cualquier cifra. Resultado actual:

| Control | Resultado |
|---|---|
| Suma por año = total | OK |
| Suma por categoría = total | OK |
| Suma por empresa = total | OK |
| Suma mensual = total | OK |
| Declaraciones repetidas | 0 |
| Mes fuera de 01–12 | 0 |
| FOB negativo | 0 |

El reporte queda en `data/importaciones/processed/anomalias.json`.

Un control ya encontró un error real: los meses viajaban fuera de rango porque
pandas leía `01` como entero y devolvía `1`, de modo que la clave `2026-01`
dejaba de calzar. Es la misma clase de deriva silenciosa que el cero a la
izquierda del código de sector.

---

## Cobertura: «sin datos» no es «cero»

Es la regla que gobierna todo el módulo. Un mes sin operaciones puede
significar dos cosas opuestas —que nadie importó, o que ese archivo todavía no
se bajó— y son exactamente las dos que no hay que confundir.

Por eso cada año y cada mes viaja con **las semanas de origen que lo
respaldan**. Sin semanas detrás, la interfaz muestra un hueco declarado y la
palabra «sin datos»; nunca US$ 0.

Cobertura al cierre de este documento:

| Año | Semanas archivadas | De 52 |
|---|---|---|
| 2022 | 52 | **completo** |
| 2023 | 52 | **completo** |
| 2024 | 1 | descarga en curso |
| 2025 | 0 | pendiente de descarga |
| 2026 | 11 | año en curso, hasta el 2026-08-30 |

Un año se considera **completo** con 45 de sus 52 semanas archivadas. Por
debajo de ese umbral la cifra anual es un recorte presentado como año: la
interfaz dibuja su barra rayada, la marca con asterisco y muestra su cobertura,
para que nadie lea una caída donde solo falta archivo.

**2026 es año en curso** y se marca como tal en toda la interfaz. La variación
interanual se calcula sobre el mismo tramo de meses en ambos años, nunca un año
parcial contra uno entero.

---

## Empresas sin información

Una empresa identificada como importadora para la que no se encontraron
operaciones **se mantiene en el directorio** y muestra «Sin información
histórica suficiente». No se fabrica un gráfico, no se interpolan valores, no
se estima nada.

---

## Archivos

```
data/aduanas_hist/                 ZIP originales, uno por semana, intactos
  manifiesto.json                  qué semanas hay, con SHA-256 y fecha
data/importaciones/processed/
  operaciones.csv                  una fila por línea de manifiesto, 29 columnas
  operaciones_clasificadas.csv     lo mismo + categoría y cómo se clasificó
  importadores.json                agregados por RUC
  mercado.json                     totales, cobertura y categorías
  anomalias.json                   reporte de validación
  _semanas_procesadas.json         libro de semanas ya extraídas
```

Los ZIP originales no se destruyen ni se modifican, pero **no se versionan en
git**: crecen unos 13 MB por semana y git no olvida nada, así que cinco años
serían unos 3.4 GB de historia permanente. Lo mismo vale para
`operaciones.csv`, que a cinco años pasa de los 50 MB.

Lo que sí se versiona es lo que no se puede regenerar solo y lo que el sitio
necesita: **el manifiesto** —con el SHA-256 de cada ZIP, que permite comprobar
que el archivo de hoy es el mismo de ayer—, los **agregados JSON** y el
**reporte de validación**. Con el manifiesto en la mano, cualquiera vuelve a
bajar los mismos archivos y debe llegar a las mismas cifras.

Los tres estados que pide el encargo —crudo, procesado, histórico— existen,
aunque no con esos nombres: el **crudo** es `data/aduanas_hist/`, que guarda los
ZIP tal como los sirve SUNAT; el **procesado** es
`data/importaciones/processed/`; y el **histórico** no es un tercer directorio
sino una propiedad del crudo, porque cada ZIP es una semana fechada y el
manifiesto dice cuáles hay. Un directorio aparte con los mismos archivos
duplicaría 1.7 GB para no decir nada nuevo. El crudo se llama `aduanas_hist` y
no `importaciones/raw` porque los mismos ZIP alimentan también la exportación.

### Trazabilidad de cada cifra

Cada fila de `operaciones.csv` lleva: `ruc`, `razon_social`, `fecha`, `anio`,
`mes`, `semana_archivo`, `partida`, `partida4`, `familia`, `descripcion`,
`desc_materia`, `desc_uso`, `fob_usd`, `flete_usd`, `seguro_usd`, `cif_usd`,
`peso_neto_kg`, `peso_bruto_kg`, `cantidad`, `unidad`, `pais_origen`,
`pais_adquisicion`, `puerto_embarque`, `aduana`, `agente_aduana`,
`declaracion`, `fuente`, `archivo` y `bajado`.

De cualquier número del módulo se llega al archivo ZIP del que salió y a la
fecha en que se descargó.

---

## Cómo se reproduce

```
python scripts/acumular_aduanas.py --desde 2022-01-03 --solo importacion
python scripts/build_import_historico.py
python scripts/build_import_clasificar.py
python scripts/build_import_agregados.py
```

Los cuatro son idempotentes y retomables: cada uno lleva registro de lo ya
hecho y solo procesa lo nuevo.

---

## Limitaciones declaradas

1. **La descarga histórica está incompleta.** 2022 y 2023 están enteros; 2024
   va por una semana y 2025 no empieza. Los años sin semanas no aparecen en
   cero: aparecen sin dato, y el módulo lo dice con esas palabras.
2. **No hay proveedor internacional** en la fuente.
3. **Los adyuvantes agrícolas no son medibles** por separado del jabón
   doméstico, así que quedan fuera del universo.
4. **La semana que cruza de mes** se imputa por la fecha del registro, pero los
   registros sin fecha válida caen en la semana del archivo.
5. **El FOB no es facturación**, y el módulo no permite deducir el tamaño
   comercial de una empresa a partir de lo que importa.
6. **La clasificación fina depende de lo que escriba el declarante.** El 5.2%
   desempatado por descripción hereda esa imprecisión; el 94.8% restante no.
