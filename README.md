# PISA Argentina: desempeño por escuela vs. nivel socioeconómico (2006–2025)

Visualizador interactivo: cada burbuja es una escuela argentina, con su puntaje promedio (Y) y su
índice socioeconómico y cultural promedio, ESCS (X), en Matemática, Lectura y Ciencias. Incluye un
selector de año (6 ciclos PISA: 2006, 2009, 2012, 2018, 2022 y 2025; 1.755 escuelas-año) y un
gráfico de evolución por año.

🌐 **Página hosteada:** https://rquiroga7.github.io/PISA_2025_ARG/

![Ejemplo del gráfico](pisa2025_OG.png)

## Uso

- **Año**: elige el ciclo PISA (2006, 2009, 2012, 2018, 2022, 2025).
- **Región**: muestra/oculta cada grupo geográfico (CABA, Buenos Aires, Córdoba, Santa Fe, Mendoza, NOA, NEA, Cuyo, Patagonia).
- **Gestión**: muestra/oculta escuelas públicas (●) y privadas (▲) por separado.
- **Ajuste**:
  - *Tendencias* MCO por escuela **ponderadas por el peso de expansión** (`w_sum`, suma de `W_FSTUWT`): ARG, OCDE, y una de la selección actual (se recalcula con los filtros).
  - *Tamaño de burbuja*: proporcional a la **población** de estudiantes de 15 años que representa cada escuela (metodología de la Figura 5 de la OCDE). Es un atributo absoluto de la escuela: **no cambia** al prender/apagar regiones, gestión o año. Las burbujas más chicas se dibujan **encima** de las más grandes cuando se solapan (opacidad 0,6).
- El gráfico inferior (3 paneles) muestra la evolución por año con **una línea por región seleccionada y por materia**, con los mismos colores que el scatter. Los tramos que cruzan años sin datos se unen con **línea punteada**; los de años consecutivos, con línea sólida. Todo lleva un **contorno blanco fino**. La **línea gris** es el promedio general de Argentina —**total, pública o privada según la gestión seleccionada**— con su **IC 95 %**, y se dibuja por encima del resto. El **eje Y es fijo** (no cambia con los filtros).
- Pasá el cursor sobre un punto para ver el detalle de la escuela.

## Estructura del repositorio

```
scripts/
  download_pisa.py     # descarga los microdatos PUF de la OCDE (2000-2025) a raw/
  download_ps.ps1      # descarga alternativa vía .NET (para URLs que rechazan OpenSSL)
  pisa_io.py           # lectores .sav / TXT ancho fijo + utilidades
  region_mapping.json  # mapeo estrato -> región por ciclo (mejor esfuerzo)
  inspect_strata.py    # ayuda a curar los mapeos de estrato
  build_database.py    # raw/ -> data/ (escuelas + tendencias + nacional) y borra raw/
  build_estimates.py   # errores estándar BRR/Fay + Rubin (por año, región y gestión)
  build_page.py        # data/ -> index.html
  verify_national.py   # verifica los promedios de Argentina contra los oficiales de la OCDE
  compare_years.py     # diferencias entre años con linking error
data/
  pisa_arg_schools.csv # 1 fila por escuela-ciclo (base compacta)
  pisa_arg_trends.csv  # parámetros de tendencia (ARG y OCDE) por ciclo/materia
  pisa_arg_national.csv# promedio y DE generales de Argentina (nivel estudiante) por ciclo/materia
  pisa_arg_estimates.csv# medias + SE (BRR/Fay + Rubin) por año, región y gestión
  linking_errors.csv   # linking error oficial de PISA por par de ciclos/materia
  pisa_arg_meta.json   # metadatos y notas
```

### Cómo regenerar

```bash
python scripts/download_pisa.py                 # baja ~4 GB a raw/ (reanudable)
python scripts/build_database.py                # escuelas + tendencias + nacional (borra raw/ salvo --keep-raw)
python scripts/build_estimates.py               # medias + SE con replicación y Rubin
python scripts/build_page.py                    # genera index.html
python scripts/verify_national.py               # controla los promedios contra la OCDE
```

## Metodología

- **Fuente**: microdatos *public use files* de la OCDE. Argentina participó en 2000, 2006, 2009, 2012, 2015, 2018, 2022 y 2025 (no en 2003). Se incluyen 2006, 2009, 2012, 2018, 2022 y 2025.
- **Cada escuela**: promedio **ponderado por estudiante** (`W_FSTUWT`); el puntaje es el promedio de los valores plausibles (10 en 2015+, 5 hasta 2012).
- **Grado modal (Figura 5 OCDE)**: el scatter muestra **solo escuelas con estudiantes en el grado modal** para 15 años (los promedios se calculan sobre todos sus alumnos). Se usa `GRADE == 0`; para 2006 (sin `GRADE`) se usa el grado modal de `ST01Q01` (10.º). Esto, por ejemplo, excluye escuelas sin ningún estudiante de grado modal.
- **Tamaño de burbuja**: área proporcional a la suma de `W_FSTUWT` de la escuela, en una escala **fija** (mediana global); no se recalcula con los filtros.
- **Regiones**: se reconstruyen del estrato muestral (mejor esfuerzo; `region_mapping.json`). En 2009 y 2012 el estrato «Centro» se asigna simultáneamente a Buenos Aires, Córdoba y Santa Fe.
- **Tendencias**: MCO por escuela ponderadas por **peso de expansión** (`w_sum`) —tanto ARG como OCDE— y la de seleccionados se recalcula con las escuelas visibles.
- **Promedios nacionales**: a nivel estudiante (ponderados por `W_FSTUWT`); coinciden con los valores oficiales de la OCDE dentro del redondeo (ver `scripts/verify_national.py`).
- **Datos faltantes**: ESCS usa códigos centinela según el ciclo (9999 en 2012, 997/999 en 2006, etc.); se tratan como faltantes.
- **ESCS**: se usa el índice provisto en cada ciclo (no el re-escalado para análisis de tendencia). El eje X del scatter es específico de cada año; no se comparan valores de ESCS entre ciclos.
- **Errores estándar**: diseño muestral complejo con **replicación BRR/Fay** (80 réplicas, factor de Fay 0,5) y combinación de los 10 valores plausibles con las **reglas de Rubin** (`scripts/build_estimates.py`). Se grafican como **IC 95 %**. Hay estimaciones para el total y por gestión (pública/privada).
- **Linking error**: afecta el error de las **diferencias entre ciclos**, no el de cada año. Se aplica `SE(θ₂−θ₁) = √(SE₁² + SE₂² + linking²)` en `scripts/compare_years.py`, con los valores oficiales de `data/linking_errors.csv` (por ahora solo 2018↔2022: mat 2,24 · lec 1,47 · cie 1,61). Las bandas por año **no** incluyen linking.

### Advertencias

- Los datos de PISA están diseñados para estimaciones a nivel **sistema**, no para *ranquear* escuelas individuales (muestras de ~30 alumnos por escuela, con error de muestreo y medición).
- Comparabilidad entre ciclos: pruebas en papel (≤2018) vs. computadora (2022+); usar el *linking error* al comparar (ver arriba).
- El ciclo **2015** de Argentina se **excluyó** por problemas técnicos de muestra: sus resultados no son comparables con el resto.
- Se excluyó **Cuyo 2009** (resultado atípico: ≈413 pts frente a ≈354–383 en el resto de los años de Cuyo).
- **2000**: pendiente. Viene en archivos separados por área (lectura/matemática/ciencias) más un ESCS aparte, y su archivo de escuela no trae estratos regionales (`SUBNATIO` constante), por lo que no admite el desglose por región que usa este gráfico.
