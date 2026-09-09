# Agroexportación · metodología

Cómo se construye la capa exportadora del proyecto, qué decide cada criterio y
qué no aguanta el dato. El gemelo de
[`IMPORTADORES_INSUMOS_METODOLOGIA.md`](IMPORTADORES_INSUMOS_METODOLOGIA.md)
para el otro lado de la aduana.

Cifras al día de la última corrida: **1,894,908 series de embarque, 4,812
exportadores con RUC, US$ 55,106 MM FOB entre 2022 y 2026**, en 177 familias de
producto y 162 destinos, sobre 245 semanas de manifiesto. El salto contra la
corrida anterior —1,468,627 series y 47,811 MM— es la ampliación del universo
arancelario, no un cambio de fuente.

---

## La fuente

SUNAT publica los manifiestos semanales en `aduanet.gob.pe/aduanas/informae`
bajo la Ley 27806, en ZIP con un DBF dentro. El índice lista unas diez
semanas, pero **los archivos siguen servidos mucho después de dejar de estar
listados**: el histórico se baja de la fuente primaria y no se estima.

El archivo de exportación trae dos campos que el de importación no tiene:

- `DNOMPRO`, el productor. En la agroexportación peruana el que embarca no
  siempre es el que siembra. Se guarda tal cual, sin cruzarlo con nada: es
  texto libre del declarante y no un identificador.
- `UBIGEO`, que resulta ser el campo más valioso del archivo. Ver más abajo.

### La semana que cruza el año viene partida

Cuando la semana cruza el 31 de diciembre, SUNAT a veces la publica en dos
archivos —los días de diciembre en uno, los de enero en otro— y a veces no: la
del 26 de diciembre de 2022 salió entera y la del 30 de diciembre de 2024
partida. No hay regla; hay que pedir y ver.

Esto costó ocho días de calendario. El pipeline generaba solo el nombre de la
semana completa, recibía un 404 y la anotaba como no publicada, de donde salió
la conclusión —equivocada— de que SUNAT no publicaba esa semana. `tramos()` en
`acumular_aduanas.py` pide ahora el entero y, si cruza el año y no está, los
dos pedazos.

---

## El universo

El universo está escrito en `scripts/universo.py`, que es el único sitio donde
se decide qué partida cuenta como agro: de ahí lo toman el histórico, los
agregados, la ventana de diez semanas y el dashboard. La partida se lee de
`PART_NANDI`, que **llega sin el cero inicial en los capítulos 01–09** —la uva
viene como `806100000`— y hay que rellenar a diez dígitos antes de mirar nada.

La regla es **veinticinco capítulos del arancel, menos una lista corta de
partidas que no pertenecen**. Los siete con que arrancó el proyecto —07
hortalizas, 08 frutas, 09 café, 12 semillas, 18 cacao, 20 y 21 preparaciones—
daban US$ 13,230 MM en 2025 contra los 15,013 que publica MIDAGRI: un 12%
menos, y la diferencia no era de método sino de universo.

`diag_universo.py` midió qué quedaba fuera, capítulo por capítulo, y después
hubo que bajar a cuatro dígitos, porque a nivel de capítulo la pregunta no
tiene respuesta: el capítulo 23 son 2,126 MM de los que 1,871 son harina de
pescado, y el 15 son 802 de los que 518 son aceite de pescado. Contarlos
enteros habría inflado el agro con la pesca; dejarlos fuera habría perdido el
aceite de palma, el alimento balanceado y el salvado.

Entraron 18 capítulos —preparaciones de cereales, alimento para
animales, grasas y aceites, bebidas y alcohol, cereales, azúcares, esencias,
lácteos, materias trenzables, flores, molinería, gomas y resinas, y seis más
pequeños— y quedaron fuera a propósito:

| Fuera | Por qué |
|---|---|
| capítulos 03 y 16 enteros | pescado y conservas; el 1602, que sí sería agro, no llega a un millón |
| partidas 1504 y 2301 | aceite y harina de pescado, US$ 2,388 MM de pesca dentro de capítulos agrarios |
| 3303–3307 | perfumería y cosmética; el 3301, aceite esencial, sí entra |
| 5204–5212 y 5306–5311 | hilados y tejidos; el algodón en rama sí entra |

Con esa regla 2025 da **US$ 14,790 MM** depurado contra los 15,013 oficiales:
un 1.5% por debajo, y del lado prudente. Lo que queda es diferencia de
criterio —MIDAGRI ancla en la regularización y no en el embarque, y arrastra
rectificaciones posteriores al corte—, no capítulos olvidados.

La ampliación vale US$ 7,295 MM del período de cinco años, el 13% del total, y
trae **758 exportadores** que antes no aparecían en ninguno de los siete
capítulos originales: es cartera nueva, no solo FOB nuevo. `mercado.json`
guarda el desglose en su bloque `universo`, de modo que la plataforma puede
marcar qué familias son de la ampliación en vez de anunciar un salto del 12%
sin explicación.

---

## Depuración

`build_export_depurar.py` aparta dos cosas antes de agregar nada, y deja
constancia de ambas en `depuracion.json`.

### Republicaciones · US$ 19,459 MM

SUNAT vuelve a publicar cada declaración en semanas posteriores con el valor
rectificado: misma aduana, año, declaración y serie, mismo peso, un FOB que
cambia unos miles de dólares. En 2025 alcanzaba al **51% del valor**. De
216,381 líneas repetidas, 216,303 estaban en archivos distintos y solo 78
dentro del mismo: una serie es una fila, así que toda repetición es una
versión nueva del mismo embarque. Se conserva la última, que es la vigente.

Sumarlas contaba varias veces el mismo embarque e inflaba el total un tercio.
También fabricaba una caída: las republicaciones se acumulan más en los años
viejos que en el corriente, así que el año en curso parecía hundirse. La
variación de 2026 pasó de −5.4% a **+2.8%** al depurar.

### Precios que el producto no aguanta · US$ 140 MM

Una declaración de café verde declara US$ 37.4 millones por 56,925 kg —US$ 657
el kilo— cuando la serie anterior del mismo documento va a 8.7. No se filtran
con un umbral fijo: la semilla híbrida de hortaliza cuesta legítimamente
cientos de dólares el kilo y borrarla sería otro error. Cada línea se compara
contra **la mediana de su propia familia**, que es lo que sabe cuánto vale un
kilo de esa cosa.

---

## Las dos reglas que gobiernan lo que se puede afirmar

### 1. El último mes nunca está completo

El embarque se declara al salir, pero el archivo se arma cuando la declaración
se regulariza, y entre una cosa y otra pasan 11 días en la mediana.

**El percentil de días no sirve para decidir cuándo un mes cerró**, y conviene
decir por qué: se calcula sobre las líneas que ya llegaron, y las que faltan
son justamente las lentas. Que el p99 dé 30 días no significa que un mes de 30
días de antigüedad esté completo; significa que el 99% de lo que ya llegó
llegó en menos de 30. Es censura por la derecha, y leída al revés inventa
caídas del último trimestre.

Lo que sí decide es la **curva de maduración**, medida sobre meses de embarque
con más de 120 días de antigüedad: 25% del FOB visible a los 7 días, 63% a los
14, 97% a los 28, 99.5% a los 30, 100% a los 120. Aplicada día por día dice
cuánto de cada mes reciente debería estar a la vista. Un mes entra en la
variación interanual solo si llega al 99.5% en los dos años, y el tramo se
declara.

`build_export_panel.py` no calcula esa frontera por su cuenta: la lee del
agregado. Antes restaba 28 días fijos y declaraba una fecha distinta sobre los
mismos embarques.

### 2. El UBIGEO apunta al fundo, y se está apagando

El UBIGEO del manifiesto **no es el domicilio fiscal**. Cruzado contra el
padrón de SUNAT sobre 2024 —529 exportadores, 120,815 líneas— coincide en el
distrito el 26.6% de las veces y en el departamento el 48.8%. Las diferencias
no son ruido: donde el manifiesto dice Ica, La Libertad, Lambayeque o Piura,
el padrón dice Lima. El manifiesto apunta al fundo y el padrón a la oficina.

Es el único puente directo entre la aduana y el territorio, y por eso el corte
territorial se construye con él. Pero SUNAT lo está dejando de llenar: viene
en el **100% del FOB hasta 2024, el 60% en 2025 y el 2.3% en 2026**. El corte
se limita a los años que lo traen y se niega a extenderse a los demás:
extenderlo sería dibujar el mapa de la caída del campo, no el de la
producción.

Una versión anterior de este proyecto concluyó que el campo era inservible
—«solo el 3% del FOB lo trae»—. Era cierto de 2026 y falso de los años
anteriores: la medición se hizo sobre diez semanas y se generalizó a cinco
años.

---

## Lo que queda fuera, dicho

- **Ley 29733.** US$ 53 MM en 9,096 operaciones son de exportadores persona
  natural, cuyo titular SUNAT no publica. Están en los totales del mercado y
  en ningún corte por empresa.
- **Fuera de la ventana.** Los embarques de diciembre que regularizan en enero
  caen fuera del recorte de cinco años y se cuentan aparte.
- **Fechas no creíbles.** Unas 2,500 líneas declaran embarques de hace diez
  años. No se corrigen ni se borran: se cuentan y se declaran.
- **Una declaración trae 1.36 líneas** —una por partida y serie—, así que la
  declaración repetida no es una anomalía como en importación: es la forma del
  documento.

---

## Lo que baja el navegador

`exportadores.json` pesa 7.8 MB porque lleva por empresa el cubo completo de
producto × destino × partida. Eso está bien para el informe, que lo lee del
disco, y mal para una web. `build_export_web.py` deja el ranking, la serie por
año, el origen declarado y los tres primeros productos y destinos: **1.25 MB,
el 16%**. Lo que no se recorta son las advertencias —la cobertura del ubigeo
año por año y la frontera de completitud viajan en el recorte—, porque una
cifra sin su salvedad viaja más rápido que la salvedad.

---

## Orden de ejecución

No es opcional. `pipeline.py` lo declara y lo hace cumplir:

```
export-historico → export-depurar → export-agregados → export-panel
                                                     → export-web
                                                     → export-figuras
senasa → acopio → reporte
```

`export-panel` lee del agregado la frontera de completitud; `acopio` necesita
el agregado, SENASA, los hubs y los clusters. Correrlas en otro orden no
revienta nada: mezcla cifras viejas con nuevas.
