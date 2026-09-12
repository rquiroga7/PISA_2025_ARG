# PISA Argentina: desempeño por escuela vs. nivel socioeconómico (2000–2025)

Visualizador interactivo: cada punto es una escuela argentina, con su puntaje promedio (Y) y su
índice socioeconómico y cultural promedio, ESCS (X), en Matemática, Lectura y Ciencias. Incluye un
selector de año (6 ciclos PISA: 2006, 2009, 2012, 2018, 2022 y 2025; 1.925 escuelas-año) y un
gráfico de evolución por año.

🌐 **Página hosteada:** https://rquiroga7.github.io/PISA_2025_ARG/

![Ejemplo del gráfico](pisa2025_OG.png)

## Uso

- **Año**: elige el ciclo PISA (2006, 2009, 2012, 2018, 2022, 2025).
- **Región**: muestra/oculta cada grupo geográfico (CABA, Buenos Aires, Córdoba, Santa Fe, Mendoza, NOA, NEA, Cuyo, Patagonia).
- **Gestión**: muestra/oculta escuelas públicas (●) y privadas (▲) por separado.
- **Ajuste**:
  - *Tendencias* MCO ponderadas por cantidad de estudiantes: ARG, OCDE, y una de la selección actual (se recalcula con los filtros).
  - *Dispersión intraescuela (1 DE)*: dibuja detrás de cada escuela un círculo del mismo color (α≈0,25) cuyo diámetro representa 1 desvío estándar de los puntajes de sus estudiantes.
- El gráfico inferior (3 paneles) muestra la evolución por año con **una línea por región seleccionada y por materia**, usando los mismos colores que el scatter. Las escuelas del estrato «Centro» aportan a las tres líneas (Buenos Aires, Córdoba y Santa Fe). Los tramos que cruzan años sin datos se unen con **línea punteada** (p. ej. Mendoza 2006→2022); los tramos con años consecutivos van con línea sólida. La **línea y banda grises** son el promedio general de Argentina ±1 desvío estándar (nivel estudiante, valores oficiales OCDE).
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
  build_page.py        # data/ -> index.html
  verify_national.py   # verifica los promedios de Argentina contra los oficiales de la OCDE
data/
  pisa_arg_schools.csv # 1 fila por escuela-ciclo (base compacta)
  pisa_arg_trends.csv  # parámetros de tendencia (ARG y OCDE) por ciclo/materia
  pisa_arg_national.csv# promedio y DE generales de Argentina (nivel estudiante) por ciclo/materia
  pisa_arg_meta.json   # metadatos y notas
```

### Cómo regenerar

```bash
python scripts/download_pisa.py            # baja ~4 GB a raw/ (reanudable)
python scripts/build_database.py           # construye data/ (y borra raw/ salvo --keep-raw)
python scripts/build_page.py               # genera index.html
```

## Metodología (breve)

- **Fuente**: microdatos *public use files* de la OCDE (PISA 2000–2025). Argentina participó en 2000, 2006, 2009, 2012, 2015, 2018, 2022 y 2025 (no en 2003).
- **Cada escuela**: promedio ponderado por estudiante (`W_FSTUWT`); el puntaje promedia los valores plausibles (10 en 2015+, 5 hasta 2012). Tamaño del punto = cantidad de estudiantes evaluados. El círculo de dispersión usa el desvío estándar muestral de los estudiantes de la escuela (no el error estándar del promedio).
- **Regiones**: se reconstruyen del estrato muestral (mejor esfuerzo; `region_mapping.json`). En 2009, 2012 y 2015 el estrato «Centro» se asigna simultáneamente a Buenos Aires, Córdoba y Santa Fe para permitir la comparación entre ciclos.
- **Tendencias**: MCO por escuela ponderadas por cantidad de estudiantes evaluados (ODCO: escuelas de países miembros de la OCDE en cada ciclo).
- **Datos faltantes**: ESCS usa códigos centinela (9999, 997, etc.) según el ciclo; se tratan como faltantes.
- **Promedios nacionales**: se calculan a nivel estudiante (ponderados por `W_FSTUWT`) y coinciden con los valores oficiales de la OCDE dentro del redondeo (ver `scripts/verify_national.py`).

### Advertencias

- Los datos de PISA están diseñados para estimaciones a nivel **sistema**, no para *ranquear* escuelas individuales (muestras de ~30 alumnos por escuela, con error de muestreo y medición).
- Comparabilidad entre ciclos: pruebas en papel (≤2018) vs. computadora (2022+); el índice ESCS se re-escala para análisis de tendencia en los ciclos más antiguos.
- El ciclo 2015 de Argentina se **excluyó** por problemas técnicos de muestra: sus resultados no son comparables con el resto de los ciclos.
- Se excluyó **Cuyo 2009** (resultado atípico: ≈413 pts frente a ≈354–383 en el resto de los años de Cuyo).
- **2000**: pendiente. Viene en archivos separados por área (lectura/matemática/ciencias) más un ESCS aparte, y su archivo de escuela no trae estratos regionales (`SUBNATIO` constante), por lo que no admite el desglose por región que usa este gráfico.
