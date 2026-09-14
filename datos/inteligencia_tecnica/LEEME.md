# Inteligencia técnica de insumos

Qué se importa al Perú como insumo agrícola, qué lleva adentro cada producto y
a qué precio se vende. Es la base que contesta lo que la aduana no declara: en
cuatro de cada cinco líneas de manifiesto el producto dice «INSECTICIDA» y nada
más, y la etiqueta oficial dice «Abamectina 18 g/L».

Generado en septiembre de 2026. La canalización que lo produce vive aparte, en
`E:\INVESTIGACION AGRICOLA` (23 scripts, reanudables).

## Qué hay acá

    indices/       los índices maestros y derivados
    precios/       precio público con IGV en cuatro comercios peruanos
    exportables/   costo por hectárea en CSV

| | |
|---|---:|
| Líneas de manifiesto aduanero | 96,433 |
| FOB importado | US$ 5,499 MM |
| Productos declarados · marcas | 14,646 · 4,329 |
| Plaguicidas registrados en SENASA | 6,335 |
| Etiquetas oficiales descargadas | 28,164 |
| Documentos con texto leído | 28,316 de 28,673 (98.8%) |
| **Productos con ingrediente activo leído de su etiqueta** | **3,737** |
| Productos con precio público | 2,898 |

### Los archivos que importan

- **`indices/documentos.jsonl`** — el índice maestro: una línea por documento
  con su URL, su SHA-256, su ruta, la fecha de consulta y el estado. Es lo que
  hace verificable todo lo demás: cualquier dato se puede rastrear hasta el
  archivo del que salió. 28,673 documentos.
- **`indices/composicion.json`** — la composición por producto, leída de la
  etiqueta y contrastada contra el vocabulario de ingredientes activos
  registrados. Cada fila trae su veredicto: `coincide_producto` (el padrón
  confirma que ese activo es de ese producto), `coincide_registro` (es un
  activo registrado, pero el padrón no lo ata a este producto) o
  `sin_respaldo`. Una fila sin respaldo se publica como tal y no se promueve.
- **`indices/registro_peru.json`** — el padrón de SENASA: 6,335 productos con
  ingrediente activo, formulación, toxicología y su tabla de cultivo, plaga,
  dosis y carencia.
- **`indices/registro_espana.json`** — el registro de MAPA España, que publica
  el campo `Formulado`: la concentración que Perú no declara.
- **`indices/agregados.json`** — los cortes de aduana por categoría,
  importador, país, partida y año.
- **`indices/margenes.json`** y **`indices/costo_ha.json`** — FOB contra precio
  de tienda, y el costo de tratar una hectárea según qué producto se elija.

## Qué NO está acá, y por qué

**El corpus de documentos: 24 GB.** Son 28,164 etiquetas oficiales en PDF, Word
y JPEG bajadas de SENASA en 47 horas de corrida. No entran en git —GitHub corta
en 100 MB por archivo— y tampoco haría falta: lo que se versiona es el índice,
que dice exactamente qué se bajó y de dónde. Con `06_senasa.py` se vuelve a
bajar solo.

Tampoco están los 195 millones de caracteres de texto extraído
(`05_texto/texto.jsonl`, 207 MB), por el mismo motivo: salen de correr las
etapas de lectura sobre el corpus.

## La regla que gobierna estos datos

**No se inventa ninguno.** Todo número, composición, registro o precio trae
fuente, fecha y —si es un documento— su SHA-256 y su ruta. Si no hay fuente
citable, la celda queda vacía o dice «sin información». Una coincidencia solo
por nombre es **probable**; **verificada** exige nombre, marca, fabricante,
concentración, formulación, país y registro coincidiendo en un documento
oficial.

## Fuentes

| | |
|---|---|
| SUNAT · Aduanas | manifiestos semanales de regímenes definitivos, Ley 27806 |
| SENASA · SIGIA | padrón de plaguicidas y etiquetas oficiales |
| MAPA · España | fitosanitarios y fertilizantes, con concentración |
| Comercios peruanos | cuatro tiendas con API pública, precio con IGV |
| ICA Colombia · SENASAG Bolivia | registros parciales |

SAG Chile estaba en mantenimiento y Agrofit Brasil responde 403 desde un
cortafuegos: se anotan como inaccesibles y se sigue. No se evade ningún
bloqueo, login ni CAPTCHA.
