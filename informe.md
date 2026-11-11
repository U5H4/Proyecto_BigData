# Informe — Corporativo JUC: pipeline de datos de extremo a extremo

**Documento de apoyo para la exposición y para desarrollar el Word final.**
Cubre objetivo, arquitectura, operación, las siete partes de la rúbrica, los
resultados verificados y todas las decisiones del proyecto. Escrito para que
cualquier lector (incluido el jurado) entienda qué hace el sistema, cómo está
dividido y funcione concepto a concepto.

- Fecha del corte de datos: **2026-11-09** (corrida en vivo verificada)
- Semilla: `SEED = 20260904` (reproducibilidad exacta)
- Repositorio: `Proyecto_BigData` (rama `main`)
- Solo quedan **2 archivos `.md`** en el repositorio: este informe y `README.md`
  (guía de uso). Los demás `.md` fueron consolidados aquí y, donde aplica,
  regenerables (ver sección 17).

> Cómo leer el documento: las secciones 1–5 explican el proyecto de forma
> general; 6–12 siguen la estructura del enunciado (Partes I–VII); 13–16 son
> decisiones, verificación y detalles prácticos; 17–19 cubren limitaciones y los
> anexos; 20–26 son la guía operativa completa: flujo de ejecución, comandos,
> qué hace cada archivo, justificación de cada decisión, preguntas probables
> del jurado, guion de exposición y qué hace cada dependencia.

---

## 1. Resumen ejecutivo

| Indicador | Valor |
|---|---|
| Facturación (pedidos completados) | $127,336,206.51 |
| Pedidos completados / totales | 1,483 / 2,259 |
| Ticket promedio | $85,863.93 |
| Tasa de cancelación | 34.35% |
| Unidades vendidas | 10,782 (7.27 por pedido) |
| Utilidad bruta | $37,982,053.12 |
| Margen real ponderado | 29.46% |
| Clientes con al menos un pedido | 1,314 |
| Productos vendidos | 514 de 606 |
| Producto más vendido | Monitor Ultrawide Kortex Air (252 uds) |
| Categoría más rentable | Computadoras ($19,450,980.64 de utilidad bruta) |
| Ciudad con mayores ventas | Tijuana ($17,084,442.12) |
| Mejor mes | 2024-08 ($6,099,562.33) |
| Producto más visto | Switch Kortex Core (23 visualizaciones) |
| Calificación promedio | 3.01 (2,475 reseñas) |
| Preguntas respondidas | 20 SQL + 12 pipelines + 15 `find`/`count` |
| Pruebas | 167 (en verde) |
| Visualizaciones | 13 (Plotly, HTML interactivo) |
| Indicadores | 22 |

> Cada número de esta tabla tiene una base de cálculo que conviene tener lista
> para el jurado — ver **sección 15.1** (por qué "pedidos" aparece tres veces,
> ticket por pedido vs por línea, rango de fechas del dataset 2024‑2026).

**Lo que hace el sistema, en una frase:** genera tres fuentes sucias, las
limpia con 10 transformaciones auditables, las carga en PostgreSQL (3FN) y
MongoDB, y responde 47 preguntas de negocio que atraviesan ambos motores, con
evidencia reproducible en cada paso.

## 2. Objetivo y alcance (rúbrica)

**Objetivo general (enunciado):** diseñar e implementar una solución completa
de gestión y análisis de datos que integre **PostgreSQL**, **MongoDB**, un
proceso **ETL** y servicios de **Cloud Computing** dentro de una misma
arquitectura, demostrando cuándo y por qué se usa cada tecnología, cómo se
integran y qué ventajas y limitaciones presentan.

**Situación problemática (enunciado):** una empresa (ficticia) creció y sus
datos están distribuidos en CSV, hojas de cálculo, bases SQL, JSON y registros
de aplicaciones; se pide un **prototipo funcional** capaz de integrar esa
información, almacenar datos estructurados y semiestructurados, generar
indicadores, ejecutarse parcialmente en la nube y soportar crecimiento.

**Cumplimiento de la arquitectura mínima (cuatro componentes obligatorios):**

| Componente | Implementación real |
|---|---|
| ETL | Python + Pandas (extract → transform → load) con 10 transformaciones auditables |
| PostgreSQL | Modelo relacional 3FN (9 tablas: 8 operativas + fact_ventas, más la vista v_resumen_ventas), cargado en **Supabase** (cloud real) |
| MongoDB | Colecciones documentales, cargadas en **MongoDB Atlas M0** (cloud real) |
| Cloud Computing | Supabase (Database) + Atlas (Database) como servicios administrados; almacenamiento/cómputo vía árbol portable (simulado, permitido por el enunciado) + degradación local |

El enunciado permite modificar o mejorar la arquitectura siempre que se
conserven y justifiquen los cuatro componentes; cada sustitución está
justificada en la sección 13 (y Colab se descartó de forma explícita por
decisión del equipo; ver secciones 11 y 18).

**El entorno usado para este corte (2026-11-09):** Windows 11, Python 3.12
(`venv` propio), 167 pruebas con pytest. La última corrida completa (5 etapas)
fue contra **Supabase** y **MongoDB Atlas** reales; ver sección 14 para el
detalle de verificación y el comportamiento ante fallos transitorios de Atlas.

## 3. Arquitectura

```
FUENTES (con errores intencionales)
   A  CSV          (clientes, productos, pedidos, detalle_pedido, pagos)
   B  JSON         (productos semiestructurados, resenas, actividad_usuario)
   C  Sheets->XLSX (sucursales, proveedores, promociones, objetivos_venta)
        |
        v
ETL  extract -> transform -> load     (10 transformaciones, evidencia de calidad)
        |
        v
INTEGRACIÓN
   PostgreSQL 3FN (9 tablas: 8 operativas + fact_ventas, más la vista v_resumen_ventas)
   MongoDB       (productos / resenas / actividad_usuario, 12 índices)
        |
        v
ANÁLISIS (Pandas)  -> 21 CSV de análisis + 22 indicadores
        |
        v
VISUALIZACIÓN (Plotly/HTML)  -> 13 figuras + reporte.html
        |
        v
CLOUD  Supabase (PG17, pooler) + MongoDB Atlas (M0)  -> degradación local si fallan
```

Orquestación: `src/run_all.py` en cinco etapas, **deteniéndose ante el primer
fallo** para no dejar datasets a medio escribir: `generar → etl → integracion →
análisis → graficos` (y `tests` opcional con `--con-tests`).

Layout de almacenamiento (punto 26 del enunciado, replicado en `data/`):

```
data/raw/{csv,json,sheets}          fuentes crudas
data/processed/tablas               tablas normalizadas 3FN (SQL)
data/processed/dataset_*.{csv,json} datasets para los motores
data/sql/                           01_ddl.sql, 02_consultas.sql, 03/04 explain
data/nosql/                         NDJSON, indices.json, 01/02 consultas
data/reports/                       evidencia y resultados (Q/A/B, análisis, KPIs)
data/figures/                       13 HTML + plotly.min.js
```

## 4. Operación y reproducción

### 4.1 Instalación y ejecución

```powershell
cd Proyecto_BigData
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py
```

### 4.2 Flags del orquestador

| Flag | Efecto |
|---|---|
| `--listar` | Imprime las etapas y sale |
| `--sin-generar` | Reutiliza `data/raw` existente |
| `--solo analisis graficos` | Ejecuta solo las etapas indicadas, en orden |
| `--con-tests` | Añade la suite de pytest como etapa final |

Etapas sueltas: `generate_sources.py` → `etl_load.py` → `integration.py` →
`analysis.py` → `viz.py`.

### 4.3 Modo nube vs modo local

El pipeline conecta a la nube **solo si hay credenciales válidas**; si no
(existen o fallan), degrada a SQLite (archivo local, nombre definido en
`src/config.py`) + NDJSON (pipelines equivalentes en Pandas) con un `WARNING`,
**sin dejar de producir** resultados. Nunca sube datos a cuentas ajenas: usa
únicamente el `.env` del operador.

Variables (`.env`, nunca versionado; `.env.example` como plantilla):

| Variable | Efecto |
|---|---|
| `SUPABASE_HOST`…`SUPABASE_PASSWORD`, `PG_SSLMODE=require` | PostgreSQL real (pooler IPv4) |
| `PG_HOST`…`PG_PASSWORD` | Conexión directa (IPv6 en Supabase) |
| `MONGO_URI` / `MONGO_ATLAS_URI`, `MONGO_DB` | MongoDB real (Atlas) |
| `SIN_POSTGRES=1` / `SIN_MONGO=1` / `FORZAR_SQLITE=1` | Forzar modo local |

Notas operativas:

- El host directo de Supabase (`db.<proyecto>.supabase.co`) solo resuelve por
  **IPv6**; por eso se usa el **Session pooler**
  (`aws-0-us-east-1.pooler.supabase.com`, usuario `postgres.<ref>`).
- Atlas y Supabase gratuitos implican cuotas y latencia; la red de la escuela
  puede bloquear puertos → el demo en vivo puede degradar a local (ver
  sección 16).
- `pytest` usa SQLite temporal: no requiere nube.
- `python-docx` (generación de Word) **no** está en `requirements.txt`
  (está instalado en el `.venv` actual, pero para reexportar con el entorno
  de otra máquina haría falta `pip install python-docx` — documentado por
  honestidad, aunque la herramienta de exportación ya no forma parte del
  repositorio en este corte).

### 4.4 Verificación de esta entrega (2026-11-09)

| Comprobación | Resultado |
|---|---|
| Pipeline completo | 5/5 etapas OK |
| Pruebas | 167 passed |
| Consultas SQL | 20/20 OK |
| Pipelines NoSQL | 12/12 OK |
| Consultas `find`/`count` | 15/15 OK |
| Visualizaciones | 13/13 OK |
| Motor relacional | Supabase (PostgreSQL 17) |
| Motor NoSQL | MongoDB Atlas (M0) |
| Diagrama ER | presente (`data/reports/modelo_relacional.png`, commiteado) |

Detalle de incidencias reales: sección 14 y 16.

## 5. Estructura del repositorio

```
Proyecto_BigData/
├── README.md                 guía de uso (este proyecto)
├── informe.md                este documento (fuente para el Word)
├── requirements.txt          dependencias del pipeline (Python 3.12)
├── .env.example              plantilla de credenciales (sin secretos)
├── .gitignore                excluye .env, .venv/, venv/, caches, logs/*.log,
│                             data/processed/integracion/ (fallback local) y los
│                             .md generados (ver sección 17)
├── src/
│   ├── config.py             rutas, semilla, mínimos, catálogos, conexiones
│   ├── utils.py              logging, tracker de calidad, tablas
│   ├── generate_sources.py   Parte I: 3 fuentes crudas con errores
│   ├── etl_extract.py        extracción + evidencia por tabla y columna
│   ├── etl_transform.py      las 10 transformaciones (T01..T10)
│   ├── etl_load.py           3FN + dataset analítico + documentos
│   ├── integration.py        DDL, carga, verificación, 20 SQL, 12 pipelines, 15 find
│   ├── analysis.py           21 análisis de negocio
│   ├── viz.py                13 gráficos Plotly -> HTML
│   └── run_all.py            orquestador de etapas
├── tests/                    167 pruebas (analysis, integration, run_all, transform)
├── data/
│   ├── raw/                  csv/ (A), json/ (B), sheets/ (C) — con errores
│   ├── processed/            tablas/ (3FN), dataset_postgresql.csv, dataset_mongodb.json
│   ├── sql/                  01_ddl.sql, 02_consultas.sql, 03/04 explain (punto 26)
│   ├── nosql/                ndjson, indices.json, 01/02 pipelines/consultas
│   ├── reports/              evidencia, resultados, reporte.html, figuras_indice.csv,
│   │                         modelo_relacional.png, KPIs, análisis (21 CSV)
│   └── figures/              13 HTML + plotly.min.js
└── .git/                     historial (la entrega vive en `main`)
```

Carpeta `logs/`: **local** (no versionada); el pipeline escribe allí
`pipeline.log` al ejecutarse (`logs/*.log` en `.gitignore`).

## 6. Parte I — Fuentes de datos

Se generan tres fuentes con formatos distintos y errores deliberados
(parte 4 del enunciado: CSV/JSON/Google Sheets):

| Fuente | Origen | Formato | Errores inyectados |
|---|---|---|---|
| A | CSV | `.csv` | duplicados (80 exactos + 200 por clave natural), ciudades con varias grafías, precios como texto (`$1,234.56`), fechas ambiguas, PK no numéricas, nulos y tipos mezclados |
| B | JSON | `.json` | estructura semiestructurada, atributos variables por familia, anidamiento (cliente embebido), ratings fuera de escala, sentimiento como texto |
| C | Google Sheets | `.xlsx` | ciudades y categorías sucias, regiones inconsistentes con la ciudad real |

Archivos crudos:

```
data/raw/csv/     clientes.csv (2,143), productos.csv (641), pedidos.csv (3,708),
                  detalle_pedido.csv (4,761), pagos.csv (3,672)
data/raw/json/    productos_semiestructurados.json (638), resenas.json (3,075),
                  actividad_usuario.json (4,854)
data/raw/sheets/  sucursales.xlsx (12), proveedores.xlsx (10),
                  promociones.xlsx (14), objetivos_venta.xlsx (9)
```

**Fuente C (Google Sheets).** El enunciado pide una fuente en Google Sheets.
Para que el pipeline sea reproducible sin credenciales se parte de la
**exportación `.xlsx`** de esas hojas (mismas columnas); en producción se
leerían con la Sheets API (`gspread`) o el enlace de exportación.

**Evidencia de extracción** (enunciado: fuente, formato, cantidad de
registros, columnas y tipos de datos):

- `data/reports/evidencia_extraccion.csv` — fuente, archivo, formato, sistema
  de origen, registros, columnas, nulos, duplicados exactos y muestra de
  valores crudos por cada archivo.
- `data/reports/evidencia_extraccion_columnas.csv` — columna por columna con
  `tipo_inferido` (entero/texto/fecha/…) para las 12 fuentes.

**Mínimos del enunciado (punto 4), superados con holgura** (verificado en
`data/reports/validacion_minimos.csv`):

| Información | Mínimo | Final | Veces el mínimo |
|---|---|---|---|
| Clientes | 1,000 | 1,862 | 1.86x |
| Productos | 500 | 606 | 1.21x |
| Pedidos | 2,000 | 3,277 | 1.64x |
| Detalles de pedido | 1,000 | 3,891 | 3.89x |
| Reseñas | 2,000 | 2,475 | 1.24x |
| Navegación | 1,000 | 4,236 | 4.24x |

## 7. Parte II — Proceso ETL

El enunciado exige extraer las tres fuentes con evidencia y transformar datos
con errores intencionales: duplicados, nulos, mayúsculas/minúsculas,
categorías con distinta escritura, fechas en varios formatos, precios como
texto, ciudades con varias grafías, cantidades inválidas y campos innecesarios.
Todo ello está presente y verificado en los datos crudos (sección 6) y se
resuelve con las 10 transformaciones obligatorias, con **93 filas de evidencia**
en `data/reports/calidad_transformaciones.csv` (filas antes/después, registros
afectados y regla aplicada).

### 7.1 Las 10 transformaciones

| # | Transformación | Qué resuelve |
|---|---|---|
| T01 | Eliminación de duplicados | Una fila por clave natural (PK o UNIQUE compuesto); p. ej. clientes 2,143 → 1,863 (280 dup), pedidos 3,708 → 3,600 (108 exactos) |
| T02 | Normalización de texto | Recorta, colapsa espacios, colapsa mayúsculas/minúsculas y convierte marcadores de faltante (`N/A`, `NULL`, `-`, `''`) en nulo real |
| T03 | Tratamiento de nulos | Imputa lo imputable (regla de negocio) y marca `Sin ...`; lo crítico se descarta |
| T04 | Corrección de tipos | `"123"` / `123.0` → entero; `"44,347"` → `44347`; `Int64` nullable |
| T05 | Estandarización de fechas | `DD/MM/YYYY`, `"14 de junio de 2026"`, epoch → `datetime64[ns]` |
| T06 | Validación de precios | Descarta no parseables y fuera de rango; márgenes fuera de `[0,1]` se recortan |
| T07 | Validación de cantidades | Enteros en `[1,100]` (imputa 1) y descuento ≥ 0 |
| T08 | Unificación de categorías y ciudades | `GDL`/`GUAD.` → Guadalajara; `PC`/`COMPUTADORAS` → Computadoras; `Ver.`/`VERACRUZ` → Veracruz |
| T09 | Eliminación de columnas innecesarias | Quita 13 campos sin valor (redundantes o vacíos) |
| T10 | Campos derivados | `costo_estimado`, `utilidad_bruta`, `trimestre`, `anio_mes`, `rango_precio`, `conciliado`, rollups |

### 7.2 Campos derivados

- `subtotal = precio * cantidad` y `total = subtotal - descuento` (ambos en
  `detalle_pedido` y, desnormalizados, en la fact).
- Fechas: `anio`, `mes`, `mes_nombre`, `trimestre`, `anio_mes`.
  Nota honesta: el enunciado **recomienda** además `dia`; el dataset no lo
  tiene. Es recomendación, no requisito.
- Derivados de negocio: `costo_estimado`, `utilidad_bruta`,
  `margen_bruto_producto`, `rango_precio`, `antiguedad_dias`,
  `diferencia_pago`, `conciliado`, montos de conciliación.

### 7.3 Productos finales del ETL

- `data/processed/dataset_postgresql.csv` — dataset **desnormalizado** para
  PostgreSQL (47 columnas; `fact_ventas`).
- `data/processed/dataset_mongodb.json` — documentos agregados para MongoDB.
- `data/processed/tablas/*.csv` — las 8 tablas normalizadas (3FN).

## 8. Parte III — PostgreSQL

### 8.1 Modelo relacional (3FN)

Las 6 tablas exigidas + 2 dimensiones (`dim_ciudades`, `dim_sucursales`) + la fact analítica (`fact_ventas`) — 9 tablas en total, más la vista:

`categorias`, `dim_ciudades`, `dim_sucursales`, `clientes`, `productos`,
`pedidos`, `detalle_pedido`, `pagos` + `fact_ventas` (desnormalizado
**deliberado**, una fila por línea de venta, para no escribir JOINs en cada
gráfico) + vista `v_resumen_ventas` (encapsula el JOIN de `pedidos`,
`detalle_pedido`, `clientes`, `productos`, `categorias` para el resumen
mensual).

**Restricciones implementadas** (verificadas en el DDL):

| Restricción | Cantidad |
|---|---|
| `PRIMARY KEY` | 9 |
| `FOREIGN KEY` | 13 |
| `UNIQUE` (llave natural: categoría, ciudad, sucursal, producto, etc.) | 4 |
| `NOT NULL` (columnas clave) | 15 |
| `CHECK` (precios > 0, margen en [0,1], cantidades, descuentos, `total = subtotal - descuento`) | 9 |

Diagrama ER (`data/reports/modelo_relacional.png`, commiteado y estable):
artefacto estático para mostrar la estructura de la base de datos; el DDL
completo vive en `data/sql/01_ddl.sql` (copia en
`data/reports/consultas_sql/01_ddl.sql`). El PNG se dibujó a partir del esquema
real y se puede reexportar manualmente si el modelo cambia.

**¿Por qué 3FN?** Cada tabla representa una entidad con dependencias
funcionales solo sobre su llave: nada describe un atributo de otra entidad
(p. ej., el nombre de la categoría no se repite en `productos`, sino que se
referencia por `id_categoria`), y los hechos (cantidades, precios) están en la
tabla central (`detalle_pedido`) referenciados por ambas puntas
(`id_pedido`, `id_producto`). El desnormalizado `fact_ventas` es la única
ruptura intencional y está documentada como tal.

### 8.2 Índices y EXPLAIN ANALYZE

**19 índices** (`ix_*`) sobre claves foráneas y columnas de filtro/orden
(fechas, estado, canal, categoría, rango de precio, conciliación) + 12 en la
parte NoSQL. Comparación **antes/después** del índice `ix_fact_anio_mes`
(`data/sql/03_explain_analyze.md` → artefacto de la corrida; evidencia medida
en `04_explain_analyze.csv`): el plan pasa de recorrido completo a
`Index Scan`, **4.17x más rápido** con el índice (0.97 ms sin índice → 0.23 ms
con él, tiempos promedio del servidor).

### 8.3 Las 20 consultas (Q01–Q20)

Cubren `INNER JOIN` y `LEFT JOIN` (Q01–Q02, Q04, Q05, Q08–Q13…), una consulta
con **7 tablas** (Q19: "detalle 360 del pedido"), agregaciones
`COUNT/SUM/AVG/MIN/MAX` (15/36/12/3/2 apariciones), `GROUP BY` (18), `HAVING` (2),
`ORDER BY` y uso de la vista (Q20). Resultados en
`data/reports/consultas_sql/Q01_*.csv` … `Q20_*.csv`; resumen en
`00_resumen_consultas.csv`.

| # | Consulta |
|---|---|
| Q01 | Top 10 productos por facturación |
| Q02 | Top 10 clientes por gasto |
| Q03 | Ventas mes a mes (serie temporal) |
| Q04 | Facturación por categoría |
| Q05 | Ticket promedio por canal de venta |
| Q06 | Productos en catálogo que **nunca se vendieron** (55 sin una línea) |
| Q07 | Clientes con pedidos cancelados |
| Q08 | Métodos de pago más usados y su conciliación |
| Q09 | Productos con mayor descuento promedio |
| Q10 | Ciudades con más facturación |
| Q11 | Clientes premium vs estándar |
| Q12 | Concentración de ventas (ley de Pareto) |
| Q13 | Productos con mejor margen real |
| Q14 | Pedidos con pago **no conciliado** |
| Q15 | Clientes nuevos vs recurrentes |
| Q16 | Trimestre × categoría (pivot de mix) |
| Q17 | Productos de alto valor y baja rotación |
| Q18 | Cobertura por sucursal y estado del pedido |
| Q19 | Detalle 360 del pedido (JOIN de 7 tablas) |
| Q20 | Resumen mensual vía vista `v_resumen_ventas` |

### 8.3.1 Distribución por nivel (criterio del equipo)

El enunciado pide que las consultas se distribuyan entre nivel **básico,
intermedio y avanzado**. El equipo asigna el nivel así:

| Nivel | Criterio | Consultas |
|---|---|---|
| **Básico** (12) | Lectura/filtro con agregación simple sobre 1–2 tablas | Q01, Q02, Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q14, Q18 |
| **Intermedio** (6) | Cruces con lógica compuesta (series, ranking, pivot, clasificación) | Q03 (serie temporal), Q12 (Pareto/ventana), Q13 (margen real), Q15 (nuevos vs recurrentes), Q16 (pivot trimestral), Q17 (HAVING) |
| **Avanzado** (2) | Multi-tabla extremo o encapsulamiento | Q19 (JOIN de 7 tablas), Q20 (resumen sobre la vista) |

20 = 12 + 6 + 2. El archivo `02_consultas.sql` no etiqueta el nivel en cada
consulta (ver sección 16, "Rúbrica vs repo: detalle de etiquetas"); si el
jurado lo exige señalado dentro del propio SQL, es un cambio de comentarios en
`integration.py` + regenerar `02_consultas.sql` — el equipo lo puede hacer y
el resultado es el mismo.

## 9. Parte IV — MongoDB

### 9.1 Colecciones (documentos semiestructurados)

| Colección | Documentos | Contenido y por qué un documento |
|---|---|---|
| `productos` | 606 | Catálogo con subdocumento `atributos` **variable por familia** (procesador/RAM en laptops, cámara/batería en smartphones…) — un esquema fijo obligaría a 30 columnas casi vacías |
| `resenas` | 2,475 | Cliente anidado (`id`, `nombre`), calificación, comentario, fecha, verificación |
| `actividad_usuario` | 4,236 | Eventos de navegación (`producto_visto`, `producto_comprado`…), dispositivo, ubicación |

NDJSON en `data/nosql/*.ndjson`; definición de índices en `indices.json`;
pipelines y consultas en `01_pipelines.js` / `02_consultas.js`; resultados en
`data/reports/consultas_mongodb/A*.csv` y `B*.csv` (con resúmenes
`00_resumen_pipelines.csv` / `00_resumen_consultas_mongo.csv`).

### 9.2 Índices (12)

4 por colección: clave natural, categoría+precio, atributo variable
(`sparse`), rango de precio (productos); reseñas por
producto/cliente, calificación y fecha (reseñas); navegación por producto,
usuario, embudo y categoría (actividad_usuario).

### 9.3 Pipelines de agregación (A01–A12)

Etapas usadas: `$match` ×12, `$group` ×14, `$sort` ×15, `$project` ×11,
`$limit` ×7, `$unwind` ×1, `$lookup` ×5.

| # | Pipeline |
|---|---|
| A01 | Top 10 productos más vistos |
| A02 | Productos vistos muchas veces y **nunca vendidos** (inversión que no convierte) |
| A03 | Productos vendidos pese a ser poco vistos |
| A04 | Distribución de visitas por mes |
| A05 | Navegación por categoría y dispositivo |
| A06 | Rating promedio y dispersión por producto |
| A07 | Productos bien valorados y con muchas reseñas |
| A08 | Catálogo por subdocumento de atributos (consulta dinámica; `atributos` existe solo en una familia) |
| A09 | Recorrido del usuario más activo |
| A10 | **Correlación visitas vs ventas por producto** |
| A11 | Calificación promedio por categoría |
| A12 | Actividad de navegación por ciudad |

Las preguntas del enunciado (mejores reseñas, rating por categoría, más
consultados, dispositivos, actividad por ciudad, usuario más activo, vistos
sin compra) tienen su pipeline: A07, A11, A01, A05, A12, A09, A02
respectivamente.

### 9.4 Consultas `find`/`countDocuments` (B01–B15)

14 × `find()` con `sort()` y `limit()` + 1 × `countDocuments()`; operadores
`$gt`, `$lt`, `$gte`, `$lte`, `$in`, `$and`, `$or` (p. ej. B01 precio >
5000, B02 precio < 1000, B06 rango 1000–5000 con `$gte/$lte`, B05 `$or`
redes/accesorios, B04 `$and`, B13 conteo de compras).

## 10. Parte V — Integración SQL + NoSQL

**Pregunta central:** ¿los productos más vistos son también los más vendidos?
Ningún motor responde solo: la navegación vive en MongoDB y las ventas en
PostgreSQL.

**Método (Python/Pandas):**

1. De PostgreSQL: `id_producto, cantidad_vendida, ingresos` (vía la fact).
2. De MongoDB: `id_producto, numero_visualizaciones`.
3. Cruce con `merge` por `id_producto`; métricas en tres poblaciones.

**Resultados (A10):**

- Pearson **+0.323** (visitados-y-vendidos), **+0.146** (todos),
  **+0.104** (visitados); Spearman **+0.270** (todos).
- Conclusión: la navegación ayuda pero no garantiza la venta (relación débil,
  no monótona perfecta).

**Las cinco preguntas del enunciado, con artefactos:**

| # | Pregunta | Evidencia |
|---|---|---|
| 1 | ¿Qué producto recibe más visitas? | A01; KPIs (`01_kpis_generales.csv`): Switch Kortex Core (23) |
| 2 | ¿Cuál vende más unidades? | KPIs: Monitor Ultrawide Kortex Air (252) |
| 3 | ¿Existe relación? | A10, `11_correlacion_visitas_ventas.csv`, `12_dispersion_visitas_ventas.csv` |
| 4 | Muchas visitas, pocas ventas | A02, `13_inventario_muerto.csv`, `20_cuadrantes_visitas_ventas.csv` |
| 5 | Pocas visitas, altas ventas | A03, `14_under_exposure.csv` |

Magnitud del fenómeno: **63** productos con tráfico y cero ventas; **122**
vendieron sin una sola visita; **55** sin una línea en ningún pedido (Q06);
**92** sin una venta completada (606 − 514).

## 11. Parte VI — Cloud Computing

### 11.1 Componentes

| Componente | Implementación | Estado |
|---|---|---|
| Cloud Database (SQL) | PostgreSQL 17 en **Supabase** (Session pooler IPv4, us-east-1) | **real** |
| Cloud Database (NoSQL) | **MongoDB Atlas** 8.0 (cluster M0, `cluster0.jnmgm6e.mongodb.net`, DB `juc`) | **real** |
| Cloud Storage | Árbol local `data/` con el layout del punto 26 | simulado |
| Cloud Computing | Ejecución portable de Python (VM / CI / contenedor) | simulado/portátil |

El enunciado permite *identificar y utilizar o simular*: los tres componentes
están identificados, dos reales y dos documentados como simulados; no se
aprovisionan buckets ni VMs. No se usan servicios de pago: Supabase free tier y
Atlas M0 (académicos/gratuitos) — la elección y sus límites están declarados en
sección 16 y 18.

### 11.2 Configuración (resumen operativo)

Ver sección 4.3. En resumen: `copy .env.example .env`; si `.env` está vacío o
las credenciales fallan → modo local sin subir nada; con credenciales válidas →
Supabase + Atlas (tablas/colecciones/índices se crean en la propia cuenta;
`.env` nunca se versiona). `pytest` no requiere nube (SQLite temporal).

### 11.3 Google Colab

**Descartado por decisión del equipo.** El enunciado lo ofrece como
recomendación/opcional, no como obligatorio; la arquitectura conserva los
cuatro componentes exigidos. Explicación para el Word: Colab representa
**cómputo remoto** (ejecuta el ETL en máquinas ajenas liberando al PC del
operador) con limitaciones reales (sesiones efímeras, límites de
cpu/ram/disk de la capa gratuita, red limitada, dependencia de notebooks y
difícil control de versiones); frente a una plataforma empresarial
(GCE/AWS/Azure + orquestador + monitoreo) perdería orquestación programada,
observabilidad y SLAs. Este proyecto lo sustituye por ejecución portable de
Python (VM/CI/contenedor) + dos Cloud Databases administradas, que es
suficiente como prototipo y más honesto para el alcance.

### 11.4 Layout de almacenamiento (punto 26)

```
data/raw/{csv,json,sheets}     crudo (A/B/C)
data/processed/tablas          3FN
data/processed/dataset_*       datasets para los motores
data/sql/                      DDL, consultas, EXPLAIN
data/nosql/                    NDJSON, índices, pipelines y consultas
data/reports/                  evidencia y resultados
data/figures/                  visualizaciones
```

## 12. Parte VII — Análisis y visualización

### 12.1 Indicadores (22; los 10 mínimos más 12)

Los **10 mínimos** del enunciado están todos en
`data/reports/analisis/01_kpis_generales.csv`: ingresos totales, pedidos
totales, ticket promedio, clientes activos, producto más vendido, producto más
visto, categoría más rentable, ciudad con mayores ventas, calificación
promedio y ventas por mes (mejor: 2024-08; serie completa en
`02_ventas_mensuales.csv`).

Más: pedidos completados (1,483), tasa de cancelación (34.35%), unidades
vendidas (10,782), unidades por pedido (7.27), productos vendidos (514),
categorías (6), utilidad bruta ($37,982,053.12), margen real ponderado
(29.46%), descuentos otorgados ($1,574,292.30), ticket con descuento
($48,090.66), ticket sin descuento ($50,042.85), ingreso por cliente
($96,907.31).

### 12.2 Análisis (21 CSV en `data/reports/analisis/`)

`01_kpis_generales` · `02_ventas_mensuales` · `03_mix_categoria` ·
`04_mix_canal` · `05_mix_region` · `06_por_sucursal` · `07_segmentos_clientes`
(RFM) · `08_detalle_segmentos` · `09_embudo_navegacion` · `10_embudo_notas` ·
`11_correlacion_visitas_ventas` · `12_dispersion_visitas_ventas` ·
`13_inventario_muerto` · `14_under_exposure` · `15_ley_pareto` ·
`16_calidad_pago` · `17_impacto_descuentos` · `18_satisfaccion` ·
`19_productos_valorados` · `20_cuadrantes_visitas_ventas` ·
`21_ventas_por_ciudad` (+ `analisis_resumen.md`, regenerado en cada corrida y
por eso ignorado por git — ver sección 17).

### 12.3 Visualizaciones (13; dos bloques)

Plotly → HTML interactivo (hover con valores exactos, zoom, aislar series).
`data/reports/reporte.html` las organiza en **Principales (1–7)** y
**Anexo (8–13)**; cada una vive también en `data/figures/*.html` con
`plotly.min.js` compartido.

| # | Visualización | Qué muestra |
|---|---|---|
| 01 | `01_ventas_mensuales` | Facturación mensual y ticket promedio |
| 02 | `02_mix_categoria` | Participación por familia y margen |
| 03 | `03_ley_de_pareto` | 24.1% de productos (124/514) → 80% de la facturación |
| 04 | `04_embudo_navegacion` | Eventos por paso (1,405 → 942 → 468) |
| 05 | `05_inventario_muerto` | Muy vistos y jamás vendidos |
| 06 | `06_impacto_descuentos` | Caída del margen con el descuento |
| 07 | `07_ventas_por_ciudad` | Facturación por ciudad (Tijuana) |
| 08 | `08_ticket_por_canal` | Ticket y margen real por canal |
| 09 | `09_segmentos_clientes` | Segmentación RFM |
| 10 | `10_correlacion_visitas_ventas` | Dispersión y ajuste lineal (Pearson) |
| 11 | `11_under_exposure` | Vendidos con pocas visitas |
| 12 | `12_satisfaccion` | Distribución de reseñas y tasa positiva |
| 13 | `13_por_sucursal` | Venta y ticket por sucursal |

Hallazgos guía (cifras completas en sección 15): cancelación 34.35%;
concentración de Pareto; embudo 67% → 50%; descuentos > 20% → margen 6.0%;
RFM: 72.4% de la facturación en Campeones+Leales, 152 "En riesgo" (19.7%);
correlación débil (+0.323 en la población favorable, +0.146/+0.104 fuera de
ella).

KPIs de comportamiento por segmento y Pareto/RFM usan las reglas documentadas
en `analysis.py`; el pie de cada figura cita su lectura correcta (p. ej. RFM
sobre los **1,010** clientes con compra completada, no sobre los 1,314 del KPI
"Clientes activos").

## 13. Elección de tecnologías: cuándo y por qué (enunciado 1)

Los cuatro componentes obligatorios no son intercambiables:

**PostgreSQL — datos estructurados, 3FN.**
*Cuándo:* entidades fuertemente tipadas y relacionadas (clientes, pedidos,
detalle, pagos) donde importan integridad referencial y transacciones.
*Ventajas:* PK/FK/UNIQUE/CHECK verificados por la base, JOINs eficientes,
agregaciones SQL, índices y planes con `EXPLAIN ANALYZE`.
*Limitaciones:* rígido para atributos variables por fila; escala
principalmente vertical.

**MongoDB — documentos.**
*Cuándo:* forma flexible (atributos por familia, reseñas anidadas, eventos).
*Ventajas:* esquema libre por documento, subdocumentos/arreglos naturales,
aggregation pipeline, escala horizontal (sharding).
*Limitaciones:* sin integridad referencial entre colecciones (`$lookup` ≠ JOIN
transaccional); analítica compleja menos expresiva que SQL; el esquema se
gobierna a nivel aplicación.

**Proceso ETL — Python + Pandas.**
*Cuándo:* limpiar/homologar/derivar antes de cargar a cada motor.
*Ventajas:* control total y auditable de las 10 transformaciones; un mismo
DataFrame alimenta el CSV relacional y el JSON documental; reproducible por
semilla.
*Limitaciones:* en memoria (no escala a datos masivos sin Spark/Dask); no es
motor transaccional.

**Cloud Computing — datos y cómputo administrados.**
*Cuándo:* disponibilidad/respaldo/acceso remoto sin mantener servidores.
*Ventajas:* PostgreSQL administrado (Supabase) y Atlas gratuitos; alta
disponibilidad sin operar infraestructura.
*Limitaciones:* dependencia de red y credenciales; cuotas de planes
gratuitos; latencia de pooler; secretos fuera del repo.

**Visualización — Plotly/HTML vs otras herramientas.** Cada punto expone su
valor en el *tooltip*, la zoom no pierde resolución y las 13 figuras se
reúnen en un único `reporte.html` autocontenido. La alternativa estática
(Power BI/Looker) era válida (el enunciado la permite); se eligió HTML para
interacción y **reproducibilidad por script**, no por export manual.

## 14. Pruebas y verificación de la entrega (2026-11-09)

**Suite:** 167 pruebas (`tests/test_transform.py`, `test_integration.py`,
`test_analysis.py`, `test_run_all.py`). No comparan contra valores fijos del
dataset (cambia con el generador), sino contra **cálculo independiente hecho a
mano** sobre fixtures mínimos: los riesgos reales de este modelo son
números plausibles y equivocados — doble conteo (la fact tiene una fila por
línea; las métricas a nivel pedido usan `id_pedido` deduplicado), mezcla de
unidades (el embudo suma **eventos** en los tres pasos) y etapas que se cuelan
en silencio (las pruebas del orquestador comprueban qué etapas se eligen).

**Verificación en vivo del 2026-11-09:**

1. `run_all.py` completo contra **Supabase** (conectado) y Atlas; la primera
   pasada de Atlas cayó a modo local con "No replica set members … Timeout"
   (fallo **transitorio** del clúster), reintentó y quedó todo OK; los
   artefactos finales son byte-idénticos a los auditados del repositorio.
2. `pytest` → 167 passed. `reporte.html` carga `plotly.min.js` (200 OK vía
   servidor HTTP local); 13/13 figuras embeben su `plotly-graph-div`; el índice
   del reporte usa dos `<ol>` (Principales start=1 / Anexo start=8) y 13 `<h2>`
   numerados.
3. No se commitean artefactos con ruido de corrida (UUIDs de plotly,
   ObjectIds, timestamps): se restauran a la última versión auditada.
4. Elementos cosméticos diferidos deliberadamente: reordenar los CSV de
   análisis por columna, unificar acento cromático; el jurado pide exactitud
   más que estética.

## 15. Hallazgos y cifras clave (para el Word)

### 15.1 Bases de cálculo de las cifras (que el jurado no pregunte dos veces)

**"Pedidos" aparece en tres cifras distintas — ninguna contradice a otra:**

| Cifra | Significado | Dónde se ve |
|---|---|---|
| **3,600** | `pedidos` tras la T01 (eliminación de duplicados) | `calidad_transformaciones.csv` |
| **3,277** | `pedidos` en la tabla normalizada 3FN (tras reglas de descarte/validación); todos únicos (`pedidos.csv`) | `validacion_minimos.csv`, `tablas/pedidos.csv` |
| **2,259** | Pedidos de la **fact** (`dataset_postgresql.csv`): solo los que tienen **al menos una línea de detalle válida** después de la limpieza (las líneas se descartan por reglas y no todos los pedidos sobreviven el cruce) | KPIs, embudo, fact |
| **1,483 / 776** | Completados / no completados de los 2,259 (cancelación = 776/2,259 = **34.35%**) | KPIs |

En corto: 3,277 es el **universo de pedidos**; 2,259 es el **universo de
ventas medibles** (los que aportan una o más líneas); 1,483 es el **universo
de ingresos**. Nunca difiere por error: indica qué población está usando
cada métrica.

**Clientes — la diferencia de 1:** tras la T01 (`2143 → 1863`), la T03
(tratamiento de nulos, imputables críticos) descarta exactamente **1** registro
(`1863 → 1862`). Por eso la tabla limpia tiene **1,862** clientes aunque la
evidencia intermedia muestre 1,863.

**Ticket promedio vs tickets con/sin descuento:**

| Métrica | Base | Valor |
|---|---|---|
| Ticket promedio ($85,863.93) | facturación de pedidos completados ÷ pedidos completados — **por pedido** | 1,483 pedidos |
| Ticket con/sin descuento ($48,090.66 / $50,042.85) | promedio **por línea** con/sin descuento | líneas `detalle_pedido` |
| Ingreso por cliente ($96,907.31) | facturación completada ÷ clientes activos | por cliente |

Son **bases distintas**: la del pedido (completa una venta) y la de la línea
(detalle de la venta). Por eso "Ticket promedio" no coincide con ellas ni
debe hacerlo.

**Rango de fechas del dataset:** `2024-01-01` hasta `2026-12-09`; 2024: 1,033
pedidos · 2025: 1,221 · 2026: 1,023. Que **el mes con mayores ventas sea
2024-08** es coherente: el dataset cubre tres años y agosto 2024 fue el pico
($6.10M); "el mejor mes" hace referencia al periodo cubierto, no a una
comparación intermensual universal.

**Facturación y completitud.** $127,336,206.51 en 1,483 pedidos completados de
2,259 (cancelación 34.35%); ticket promedio $85,864; 10,782 unidades; ingreso
por cliente $96,907.31.

**Concentración (Pareto).** 124 de 514 productos vendidos (**24.1%**) explican
el **80%** de la facturación. Implicación: foco en el catálogo pequeño que
sostiene el negocio; el resto requiere rotación/promoción o poda.

**Descuentos vs margen.** Margen 30.8% sin descuento → **6.0%** con descuento
> 20%. Los descuentos indiscriminados erosionan utilidad (descuentos otorgados
$1.57M).

**Embudo navegación–compra.** 1,405 visualizaciones → 942 al carrito (67.0%)
→ 468 compras (49.7% de quienes llegaron al carrito; 33.3% del total de
visualizaciones). El cuello de botella es la conversión de carrito a compra,
no la atracción de tráfico.

**Navegación ↔ venta (Parte V).** Pearson +0.323 (visitados y vendidos), pero
+0.146 (todos) y +0.104 (solo visitados); Spearman +0.270 confirma relación
débil y no monótona perfecta: **la navegación ayuda pero no garantiza la
venta**. 63 productos con tráfico y cero ventas (inventario muerto a atacar);
122 vendidos sin una visita; 55 sin líneas; 92 sin venta completada.

**Segmentación RFM** (reglas documentadas en `analysis.py`): **72.4%** de la
facturación está en **Campeones** + **Leales**; **152 clientes "En riesgo"**
(gastaron mucho y no vuelven; 19.7% de la venta). RFM sobre **1,010** clientes
con compra completada; el KPI "Clientes activos" cuenta **1,314** (cualquier
pedido registrado).

**Facturación por ciudad:** Tijuana $17.08M; mix por categoría: Computadoras
50.9% de la venta con 30.0% de margen — el margen real ponderado es 29.46%.

**Calidad de pagos:** conciliación con mix de métodos en
`16_calidad_pago.csv` / Q08 / Q14 (pedidos no conciliados).

## 16. Decisiones, gotchas y notas para el jurado

**Modo degradado como plan B (exposición).** Si la red de la escuela bloquea
puertos o Atlas está inestable: el pipeline degrada a SQLite/NDJSON sin
fallar; `pytest` (167 pruebas) corre 100% local en segundos; y las evidencias
(`figuras_indice.csv`, CSVs Q/A/B, `reporte.html` offline,
`04_explain_analyze.csv`) demuestran lo verificado.

**`.env` y secretos.** Nunca se versiona; `.env.example` viaja como plantilla.

**Atlas intermitente.** En la corrida del 2026-11-09 el clúster respondió con
"No replica set members… Timeout" y el pipeline cayó a modo local; minutos
después conectó normal. En el expo, si eso ocurre, muestre `pytest` y la
evidencia si el vivo falla.

**Ruido entre corridas.** UUIDs de plotly y ObjectIds cambian siempre; los CSV
de artefactos son byte-idénticos a los auditados; los tiempos del EXPLAIN
varían por sesión (la cifra citada es 4.17x, promedio del servidor).

**Doble conteo.** La fact tiene una fila por línea; toda métrica a nivel
pedido deduplica por `id_pedido` en el análisis (documentado en el código).

**Embudo.** Se suma **eventos** en los tres pasos (no personas ni productos),
para no mezclar unidades.

**1,010 vs 1,314.** RFM: clientes con compra completada; KPI "Clientes
activos": cualquier pedido registrado. Son cifras distintas a propósito.

**63 / 92 / 55 / 122.** 63 con tráfico (views>0) y cero ventas; 122 vendieron
sin una visita; 55 sin una línea en ningún pedido (Q06); 92 sin una venta
completada (606 − 514). Contextos distintos, no equivalentes.

**Rúbrica vs repo: detalle de etiquetas.** El enunciado pide las 15 consultas
"distribuidas entre nivel básico, intermedio y avanzado"; el SQL tiene las 20
con complejidad creciente (simples Q01–Q06; intermedias Q10–Q18; avanzadas
Q19 con 7 tablas, Q20 sobre vista, Q12 Pareto) pero **no las etiqueta por
nivel** en el archivo; si el jurado lo exige señalado, añadir una cabecera de
nivel por consulta es un cambio cosmético de 5 minutos.

**Campo `dia`.** El enunciado *recomienda* (no exige) derivar `dia`; el
dataset deriva `anio/mes/trimestre/anio_mes` pero no `dia`.

**Modulos opcionales ausentes.** No hay Streamlit ni dashboard en vivo: la
rúbrica acepta HTML (entregado: `reporte.html`); un dashboard tipo app sería
cosmético.

## 17. Documentación, archivos regenerables y git

`data/sql/03_explain_analyze.md`, `data/reports/consultas_sql/03_explain_analyze.md`,
`data/reports/integracion_entorno.md` y
`data/reports/analisis/analisis_resumen.md` son **artefactos regenerados por
cada corrida** (verificado por sus timestamps en corridas anteriores). Por
eso quedaron fuera del índice git (`.gitignore` los registra como
regenerables) y su contenido vive resumido en este informe; la evidencia
medición cuantitativa se conserva en `04_explain_analyze.csv` y los Q/A/B CSV.
El antiguo `modelo_relacional.md` ya no se regenera (el generador del ER se
eliminó); el diagrama quedó como `modelo_relacional.png` estático y la
justificación 3FN vive en este informe (sección 8).

**Solo 2 archivos `.md` en el repositorio** (`README.md` e `informe.md`): el
resto se eliminó (README_CARPETAS, GUIA_CONEXION_NUBE, skills de
`.opencode/`, guion y memoria `.md`/`.docx`/`.pdf`, resúmenes generados). El
Word de apoyo se desarrolla desde **este informe**.

Artefactos que **sí** permanecen (no son `.md`): `modelo_relacional.png`,
`reporte.html`, `figuras_indice.csv`, Q/A/B CSVs, `04_explain_analyze.csv`,
todas las evidencias `01_*.csv`–`21_*.csv`.

## 18. Limitaciones y trabajo futuro

- **Datos sintéticos**: describen la empresa ficticia, no un negocio real.
- **Pandas en memoria**: para volúmenes mayores, migrar el ETL a Spark/Dask.
- **Cloud simulado** en almacenamiento/cómputo (permitido); solo las Cloud
  Databases son reales.
- **Atlas transitorio**: la conexión puede fallar esporádicamente (ver 16); el
  fallback local hace que el proyecto nunca dependa de la nube para funcionar.
- **Costo de planes gratuitos**: cuotas de compute/storage; no apto para
  producción con SLAs.
- **Trabajo futuro**: orquestación programada (cron/Airflow), monitoreo de
  calidad de datos, pruebas de carga, modelo predictivo (churn /
  recomendación), dashboard web opcional.

## 19. Anexos

### A. Diccionario de datos (resumen)

- `clientes`: id_cliente, nombre, ciudad, región, es_premium, antigüedad.
- `productos`: id_producto, nombre, id_categoria, categoría, precio, costo,
  margen_bruto, rango_precio.
- `pedidos`: id_pedido, id_cliente, id_sucursal, fecha_pedido, anio_mes,
  estado, canal_venta, total_pedido, es_completado.
- `detalle_pedido`: id_detalle, id_pedido, id_producto, cantidad,
  precio_unitario, descuento, subtotal, total.
- `pagos`: id_pago, id_pedido, metodo, monto, estado_pago, diferencia_pago,
  conciliado.
- `categorias`: id_categoria, nombre. (+ `dim_ciudades`, `dim_sucursales`)

### B. Mapa rúbrica → evidencia

| Parte | Tema | Evidencia principal |
|---|---|---|
| I | Fuentes y calidad | `data/raw/**`, `evidencia_extraccion*.csv`, `validacion_minimos.csv` |
| II | ETL | `src/etl_*.py`, `calidad_transformaciones.csv` |
| III | PostgreSQL | `data/sql/01_ddl.sql`, `02_consultas.sql`, `03/04 explain`, `Q01..Q20`, `v_resumen_ventas` |
| IV | MongoDB | `data/nosql/*`, `indices.json`, `A01..A12`, `B01..B15` |
| V | Integración | `data/reports/analisis/11..14`, `20_cuadrantes_visitas_ventas.csv`, A10 |
| VI | Cloud | Supabase + Atlas reales; `.env.example`; `integracion_entorno.md` (ignorado por regenerarable; métricas citadas aquí) |
| VII | Visualización | `reporte.html`, `data/figures/`, `figuras_indice.csv` |

### C. Rutas de evidencia por área

- SQL: `data/reports/consultas_sql/` (01/02/04 + Q01..Q20).
- NoSQL: `data/reports/consultas_mongodb/` (01/02 + 00_resumen + A01..A12 +
  B01..B15).
- Calidad: `calidad_transformaciones.csv`, `validacion_minimos.csv`,
  `evidencia_extraccion*.csv`.
- Análisis: `data/reports/analisis/*.csv`.
- Visual: `data/figures/*.html`, `data/reports/reporte.html`,
  `data/reports/figuras_indice.csv`.

### D. Contenidos sugeridos para el Word de apoyo

Índice sugerido del documento derivado de este informe:

1. Portada e índice · 2. Resumen ejecutivo · 3. Contexto y problemática ·
4. Objetivo y alcance · 5. Arquitectura (diagrama) · 6. Fuentes y calidad de
datos · 7. ETL y transformaciones · 8. PostgreSQL (modelo, 3FN, índices,
EXPLAIN, consultas) · 9. MongoDB (colecciones, índices, pipelines y consultas)
· 10. Integración SQL+NoSQL y correlación · 11. Cloud (Supabase, Atlas,
layout) · 12. Indicadores y hallazgos · 13. Visualizaciones y reporte ·
14. Pruebas y verificación · 15. Comandos y flujo de ejecución (secciones
20–22) · 16. Preguntas de defensa y justificación de decisiones (secciones
23–24) · 17. Entorno y dependencias (sección 26) · 18. Limitaciones y trabajo
futuro · 19. Anexos (diccionario, rutas de evidencia, cifras, guion de
exposición).

Nota para el maquetado: las figuras del Word deben ser imágenes estáticas
(embebidas o enlazadas) o capturas del reporte; el HTML interactivo no se
incrusta en Word. El diagrama ER (`modelo_relacional.png`) ya es una imagen
lista para insertar.

## 20. Flujo de ejecución (qué pasa, en qué orden y por qué)

Comando de extremo a extremo:

```powershell
.\.venv\Scripts\python.exe src\run_all.py
```

`run_all.py` ejecuta las etapas **en el orden del pipeline** y se **detiene en
la primera que falla**: un pipeline que sigue tras un error produce datasets a
medio escribir e informes que mienten; cada etapa es una transacción: o deja
sus artefactos completos, o el proceso sale con código 1.

### 20.1 Etapa `generar` — fuentes crudas con errores

`generate_sources.main()` construye las tres fuentes con **errores
intencionales** (la práctica de calidad del enunciado): duplicados, nulos,
mayúsculas inconsistentes, categorías con varias grafías, fechas en varios
formatos, precios como texto, ciudades con varias grafías, cantidades inválidas
y columnas innecesarias (más detalle en sección 6 y 23). La semilla
`SEED = 20260904` fija cualquier aleatoriedad, así que dos corridas producen
el mismo crudo.

Detalle de diseño clave: los errores se inyectan a propósito y se documentan en
los datos crudos; el ETL los corrige y deja evidencia (sección 7). Nada se
"pierde" como magia: cada corrección aparece en
`data/reports/calidad_transformaciones.csv`.

### 20.2 Etapa `etl` — extraer, transformar, cargar

Se invoca **en el proceso** (no vía `subprocess`) para que el traceback apunte
a la línea real del error:

1. `etl_extract.extraer()` — lee las 3 fuentes, **infiere tipos** y captura
   evidencia por archivo y por columna: fuente, archivo, formato, sistema de
   origen, registros, columnas, nulos, duplicados exactos y muestra de valores
   crudos; y, columna por columna, el `tipo_inferido`. Produce
   `evidencia_extraccion.csv` y `evidencia_extraccion_columnas.csv`.
2. `etl_transform.transformar(extraer())` — aplica las **10 transformaciones**
   (T01..T10) y registra filas antes/después, registros afectados y regla.
   Produce las tablas normalizadas 3FN en `data/processed/tablas/`.
3. `etl_load.cargar(datos)` — escribe el **dataset analítico** desnormalizado
   (`data/processed/dataset_postgresql.csv`, 47 columnas, una fila por línea de
   venta), los documentos para MongoDB (`dataset_mongodb.json`) y valida contra
   los **mínimos del enunciado** (`validacion_minimos.csv`); `tracker.guardar()`
   persiste la evidencia de calidad.

### 20.3 Etapa `integracion` — SQL + NoSQL + verificación

`integration.main()` hace, en orden:

1. **DDL**: crea el esquema (9 tablas: 8 operativas + fact_ventas, más
   la vista `v_resumen_ventas`, 19 índices, restricciones PK/FK/UNIQUE/NOT NULL/CHECK — ver sección 8).
2. **Carga masiva** en **Supabase** (real) o SQLite local (si falla la conexión
   → degradación con `WARNING`; nunca aborta).
3. **20 consultas SQL** (Q01..Q20) → CSVs en `data/reports/consultas_sql/`, y
   `EXPLAIN ANALYZE` del índice `ix_fact_anio_mes` antes y después:
   recorrido completo → `Index Scan`, **4.17x** más rápido en promedio de
   servidor (`04_explain_analyze.csv` como evidencia medida).
4. **MongoDB**: **Atlas** real (o NDJSON local) — 12 índices, **12 pipelines**
   (`$match/$group/$sort/$project/$limit/$unwind/$lookup`) y **15 consultas
   `find`** con `$gt/$lt/$gte/$lte/$in/$and/$or` → CSVs `A01..A12` y `B01..B15`.
5. **Layout punto 26** en `data/sql/` (DDL/consultas/EXPLAIN) y `data/nosql/`
   (colecciones NDJSON, índices, pipelines/consultas) — réplica del almacén
   cloud, para auditar sin tocar la nube.
6. **Resumen** `integracion_resumen.csv` (47 consultas, estado, filas, más
   `integracion_entorno.md` — regenerable por corrida, por eso fuera del git).

### 20.4 Etapa `analisis` — las 21 preguntas de negocio

`analysis.main()` calcula todo sobre los datasets procesados: KPIs, serie
temporal, mixes, RFM, correlación navegación↔venta, Pareto, cuadrantes
visitas/ventas, satisfacción, inventario muerto, under-exposure, calidad de
pagos, embudo. Produce `data/reports/analisis/*.csv` (+ `analisis_resumen.md`,
también regenerable).

### 20.5 Etapa `graficos` — las 13 figuras y el reporte

`viz.main()` regenera **13 figuras Plotly** (HTML interactivo) y las
**reúne** en `data/reports/reporte.html` con los bloques *Principales (1-7)* y
*Anexo (8-13)*, más `figuras_indice.csv` (estado/peso de cada una). Se sirve
offline: doble clic sobre el archivo, sin servidor ni internet. Las figuras
individuales viven en `data/figures/` y comparten `plotly.min.js`.

### 20.6 Etapa opcional `tests`

`--con-tests` corre `pytest tests -q` como subproceso; su código de salida es el
código de la etapa. `pytest` usa SQLite temporal: **no requiere nube** y
confirma 167 pruebas antes de exponer.

### 20.7 Ejemplos de ejecución y tiempos

```powershell
.\.venv\Scripts\python.exe src\run_all.py --listar
.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos   # orden del pipeline, no del CLI
.\.venv\Scripts\python.exe src\run_all.py --sin-generar              # reutiliza data/raw existente
```

Tiempos de la última corrida verificada (2026-11-09; orientativos, varían por
máquina y por red): `generar` ≈ 2 s · `etl` ≈ 4 s · `integracion` ≈ 45–60 s
(dominado por la carga masiva a los motores cloud) · análisis y gráficos,
segundos.

### 20.8 Diagrama del flujo

```
python src/run_all.py
        |
        v
 generar ──> etl ──> integracion ──> analisis ──> graficos ──> (tests si --con-tests)
 crudo con   3FN +     Supabase/SQLite    21 CSV      13 HTML     167 pruebas
 errores     fact +    Atlas/NDJSON       de análisis + reporte.html + KPIs
 txt         JSON      47 consultas       y KPIs      interactivo
```

## 21. Comandos de referencia (guía rápida para quien clona el repo)

### 21.1 Preparación única

```powershell
cd Proyecto_BigData
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 21.2 Ejecución

| Objetivo | Comando |
|---|---|
| Pipeline completo | `.\.venv\Scripts\python.exe src\run_all.py` |
| Ver etapas | `.\.venv\Scripts\python.exe src\run_all.py --listar` |
| Reutilizar crudo existente | `.\.venv\Scripts\python.exe src\run_all.py --sin-generar` |
| Solo algunas etapas | `.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos` |
| Pipeline + suite | `.\.venv\Scripts\python.exe src\run_all.py --con-tests` |
| Suite suelta | `.\.venv\Scripts\python.exe -m pytest -q` |
| Etapas sueltas | `python src\{generate_sources,etl_extract,integration,analysis,viz}.py` |

### 21.3 Modo nube (Supabase + Atlas) — opcional

Sin `.env` el pipeline corre en **modo local** (SQLite + NDJSON) sin tocar
nada; con `.env` válido usa los motores reales.

```powershell
copy .env.example .env
# editar .env con credenciales de SU proyecto (ver README/sección 4 y 11)
```

- Supabase: usar el **Session pooler** (`aws-0-<region>.pooler.supabase.com`,
  `PG_SSLMODE=require`). El host directo (`db.<proyecto>.supabase.co`) solo
  resuelve por **IPv6**.
- Atlas: `MONGO_URI=mongodb+srv://<usuario>:<clave>@<cluster>.mongodb.net/?appName=<app>`,
  `MONGO_DB=juc`.
- Forzar local aunque haya credenciales: `SIN_POSTGRES=1`, `SIN_MONGO=1`,
  `FORZAR_SQLITE=1` (en `.env`).
- Nunca commitear `.env`; `.env.example` sí viaja.

### 21.4 Verificación y exploración de resultados

| Qué | Dónde |
|---|---|
| Estado de las 47 consultas | `data/reports/integracion_resumen.csv` |
| Pruebas | `.\.venv\Scripts\python.exe -m pytest -q` (167 passed) |
| Reporte interactivo | doble clic `data/reports/reporte.html` |
| Gráficos individuales | `data/figures/*.html` (doble clic) |
| KPIs | `data/reports/analisis/01_kpis_generales.csv` |
| Evidencia ETL | `evidencia_extraccion*.csv`, `calidad_transformaciones.csv`, `validacion_minimos.csv` |
| SQL (antes/después índice) | `data/sql/03_explain_analyze.md` / `04_explain_analyze.csv` |
| Resultados Q/A/B | `data/reports/consultas_sql/Q*.csv`, `consultas_mongodb/A*.csv`, `B*.csv` |

### 21.5 Qué hacer si algo falla

| Síntoma | Causa probable y acción |
|---|---|
| `Supabase` no conecta | Red sin IPv6 → usar pooler; o `.env` incompleto → correr sin `.env` (local) y validar primero así |
| `Atlas` no responde | Tránsito de red/DNS → reintentar; el pipeline degrada a local con un `WARNING`; `pytest` sigue verde |
| `--solo` dice "etapa desconocida" | Etapas válidas: `generar etl integracion analisis graficos tests` |
| `pytest` no pasa tras editar | Revisar el fixture tocado; las pruebas comparan contra cálculo a mano, no contra el dataset real |
| Gráficos en blanco al copiar el HTML | Falta `plotly.min.js`/estructura: llevar siempre `data/` completa (el reporte y las figuras referencian esa librería local) |

## 22. Qué hace cada archivo (para no perderse)

### 22.1 `src/`

| Archivo | Responsabilidad | Entradas (lee) | Salidas (escribe) |
|---|---|---|---|
| `config.py` | Configuración central: rutas, semilla `20260904`, catálogos, mínimos del enunciado, conexión Supabase/Atlas, layout | `.env` | Estructuras de constantes para el resto del pipeline |
| `utils.py` | Logging (consola + `logs/pipeline.log`), tablas para consola, tracker de calidad (`tracker.registrar(...)`) | — | `logs/pipeline.log` |
| `generate_sources.py` | Parte I: genera las 3 fuentes con **errores intencionales** (T01–T10 los resolverán) | — (usa config) | `data/raw/csv/*`, `data/raw/json/*`, `data/raw/sheets/*` |
| `etl_extract.py` | Extracción con evidencia: lectura, tipado a petición, nulos/duplicados por archivo y tipo por columna | `data/raw/*` | `evidencia_extraccion.csv`, `evidencia_extraccion_columnas.csv` |
| `etl_transform.py` | Las 10 transformaciones T01..T10 con reglas y evidencia | datos crudos | tablas 3FN (`data/processed/tablas/*.csv`), `calidad_transformaciones.csv` |
| `etl_load.py` | Dataset analítico (fact desnormalizada) + documentos + mínimos | tablas 3FN | `dataset_postgresql.csv`, `dataset_mongodb.json`, `validacion_minimos.csv` |
| `integration.py` | DDL + índices + EXPLAIN + DDL/consultas SQL + pipelines/consultas Mongo + verificación + layout punto 26 | datasets procesados | `data/sql/*`, `data/nosql/*`, `data/reports/consultas_*`, resultados Q/A/B + resúmenes |
| `analysis.py` | Los 21 análisis de negocio (KPIs, Pareto, RFM, correlación, embudo…) | datasets procesados | `data/reports/analisis/*.csv` |
| `viz.py` | Construye las 13 figuras Plotly y el reporte combinado | resultados del análisis | `data/figures/*.html`, `data/reports/reporte.html`, `figuras_indice.csv` |
| `run_all.py` | Orquestador: orden, flags (`--listar`, `--solo`, `--sin-generar`, `--con-tests`), detente en el primer fallo | — | Resumen por etapa con tiempos |

### 22.2 `tests/` (167 pruebas)

| Archivo | Cubre |
|---|---|
| `tests/test_transform.py` | T01..T10, imputación de nulos, limpieza, reglas de negocio |
| `tests/test_integration.py` | DDL/FK/UNIQUE/VIEW, índices, EXPLAIN, SQL, pipelines, simulación Pandas (SQLite temporal) |
| `tests/test_analysis.py` | KPIs, correlación, inventario muerto, under-exposure, cuadrantes, Pareto |
| `tests/test_run_all.py` | Selección de etapas del orquestador, orden, flags |

### 22.3 `data/`

| Carpeta | Qué contiene | Regenerable |
|---|---|---|
| `data/raw/` | Fuentes crudas (con errores): `csv/` (A), `json/` (B), `sheets/` (C, XLSX) | sí (`run_all` genera) |
| `data/processed/tablas/` | Tablas 3FN (8 CSV) | sí |
| `data/processed/` | `dataset_postgresql.csv`, `dataset_mongodb.json` | sí |
| `data/sql/` | DDL, consultas, EXPLAIN (punto 26; réplica de `data/reports/consultas_sql/`) | sí |
| `data/nosql/` | NDJSON, `indices.json`, `01_pipelines.js`, `02_consultas.js` | sí |
| `data/reports/` | Evidencia: CSV indicadores, evidencia ETL, Q/A/B, `reporte.html`, `figuras_indice.csv`, `modelo_relacional.png`, KPIs | casi todo sí; `modelo_relacional.png` commiteado |
| `data/figures/` | 13 HTML + `plotly.min.js` | sí |

## 23. Justificación de cada decisión (para "por qué hiciste X")

| Decisión / acción | Por qué (justificación) |
|---|---|
| **Semilla fija** (`SEED = 20260904`) | Reproducibilidad bit a bit: dos corridas producen el mismo crudo y los mismos KPIs; la evaluación puede confiar en los números y comparar corridas. |
| **Errores intencionales** en las fuentes | Es lo que pide el enunciado (calidad de datos) y demuestra que el ETL **detecta y corrige**, no que "limpia lo limpio". Cada error tiene su regla y su evidencia. |
| **Fuente C exportada de Google Sheets** | El enunciado exige Google Sheets; para que el pipeline sea reproducible sin credenciales se parte de la exportación `.xlsx` (mismas columnas); en producción se leería con la Sheets API. |
| **10 transformaciones T01..T10** | Son las obligatorias de la rúbrica; cada una deja evidencia (93 filas) y una regla de negocio auditable. |
| **Campos derivados** (`subtotal`, `total`, `anio`, `mes`…) | El enunciado los **exige** (`subtotal = precio × cantidad`; `total = subtotal − descuento`); el resto (margen, rango_precio, anio_mes, conciliado, trimestre) soporta las preguntas de negocio sin re-calcular. El `dia`, aunque recomendado, se omitió por no aportar a las 21 preguntas resueltas — nota honesta. |
| **Modelo 3FN** (9 tablas: 6 exigidas + `dim_ciudades` + `dim_sucursales` + `fact_ventas`) | Las tablas mínimas del enunciado más `dim_ciudades` y `dim_sucursales` (lookup geográfico/operacional); se elimina redundancia y se respetan PK/FK/UNIQUE/CHECK. |
| **`fact_ventas` desnormalizada** | Evita reescribir JOINs en cada indicador y en cada figura; es la excepción documentada al 3FN (vive la analítica, las dimensiones viven su entidad). |
| **Vista `v_resumen_ventas`** | Encapsula el JOIN de 5 tablas para el resumen mensual; Q20 la usa tal como el enunciado sugiere ("VIEW de resumen de ventas"). |
| **19 índices + `EXPLAIN ANALYZE`** | Exigencia del enunciado (comparar plan antes/después); resultado medido: 4.17x promedio servidor (`04_explain_analyze.csv`). |
| **MongoDB para el catálogo** | Estructura **variable por familia**: un esquema fijo obligaría a columnas casi vacías por documento; documento semiestructurado es el uso correcto. |
| **12 pipelines + 15 find** | Cubren las preguntas del enunciado (rating por categoría, vistos no vendidos, dispositivos…) y la sintaxis exigida (`$match`, `$group`, `$sort`, `$project`, `$limit`, `$unwind`, `$lookup`; `find/sort/limit/countDocuments` y operadores `$gt/$lt/$gte/$lte/$in/$and/$or`). |
| **Integración en Pandas (Parte V)** | Responde la pregunta central del enunciado (¿más vistos = más vendidos?) — los datos viven en dos motores; ninguno responde solo. |
| **Tres poblaciones para la correlación** | Evita engañar al lector: la correlación "visitados-y-vendidos" es la favorecida (+0.323), pero la general es +0.146/+0.104; Spearman +0.270 confirma relación débil y no monótona. |
| **RFM sobre 1,010 completadas** | "Clientes activos" (KPI, 1,314) cuenta cualquier pedido; la segmentación de valor requiere compras completadas — cita cada cifra con su contexto. |
| **13 figuras en 2 bloques** | Rúbrica pide ≥5; se entregan 13: 7 principales (relato de negocio) + 6 anexo (evidencia técnica); navegación doble (`<ol>` start=1 y start=8). |
| **Plotly / HTML offline** | Formato libre en el enunciado; HTML da valores exactos en hover y abre sin internet ni servidor; `plotly.min.js` local (sin CDN). |
| **Supabase + Atlas reales** | El enunciado exige servicios cloud; se usan alternativas gratuitas/académicas y se justifica: el mix soporta PG17 + M0 dentro de la cuota. |
| **Cloud Storage/Compute simulados** | El enunciado permite **utilizar o simular**; se documenta explícitamente qué es real y qué simulado, sin fingir infraestructura que no existe. |
| **Colab descartado** | El enunciado lo ofrece como recomendación, no obligatorio; se explicita el porqué (efímero, sin SLAs ni orquestación) y el sustituto (cómputo portable + dos Cloud DBs reales). |
| **Degradación local (SQLite/NDJSON)** | Resiliencia: el pipeline nunca deja al operador sin resultados si la red/credenciales fallan; el error es un `WARNING`, no un aborto. |
| **`.env` fuera del repo / `.env.example` dentro** | Seguridad básica de secretos; `.env.example` sirve de plantilla sin exponer claves. |
| **Artefactos commiteados (Q/A/B CSV, figuras…)** | Evidencia auditable sin re-ejecutar nada; si alguien clona el repo, ve los resultados sin montar la infraestructura. |
| **Artefactos regenerables ignorados (`.md` EXPLAIN, resúmenes…)** | Son salidas de cada corrida: commitearlas solo mete ruido de timestamps/UUIDs; su contenido vive en `informe.md`. |
| **Restaurar artefactos tras corridas con ruido** | Evita contaminar el repo con diferencias cosméticas (UUIDs, ObjectIds, timings); se conserva la versión auditada. |
| **Doble conteo (línea de fact)** | La fact tiene una fila por línea; todo agregado a nivel pedido deduplica por `id_pedido` — si no, las métricas inflan por líneas. |
| **Embudo solo con eventos** | Suma **eventos** en los tres pasos; mezclar personas×productos rompe el orden. |
| **63 ≠ 92 ≠ 55 ≠ 122** | Visto≠pedido≠vacío: 63 con tráfico cero ventas; 92 sin venta completada; 55 sin líneas en ningún pedido; 122 vendidos sin una visita. Contextos distintos del mismo fenómeno. |
| **13 campos innecesarios eliminados** | Columnas redundantes/vacías; evidencia en `calidad_transformaciones.csv` (93 filas). |
| **Diagrama ER como artefacto estático** | El enunciado exige el diagrama y la explicación 3FN, no su automatización; se quitó la generación automática para que el PNG sea un entregable estable. |

## 24. Preguntas probables del jurado (y respuestas)

**Sobre el problema y el objetivo**

1. *¿Qué problema resuelve?* Los datos de una empresa ficticia estaban dispersos en CSV, JSON y hojas de cálculo, sin unificación, indicadores ni trazabilidad; este proyecto construye el prototipo que integra, almacena, analiza y visualiza de extremo a extremo.
2. *¿Por qué PostgreSQL y MongoDB y no uno solo?* Porque hay datos estructurados transaccionales (clientes/pedidos/pagos → integridad referencial y JOINs → SQL) y datos semiestructurados de forma variable (catálogo con atributos por familia, reseñas, eventos → documentos → NoSQL). Cada uno donde tiene sentido; la Parte V los integra.
3. *¿No es redundante mantener ambos?* Es la integración que exige la rúbrica y la que resuelve la pregunta de negocio (¿más vistos = más vendidos?); cada motor responde lo suyo y Pandas los cruza.
4. *¿Qué ventaja real tiene la nube aquí?* Servicios administrados sin mantener servidores: Supabase (PostgreSQL 17) y Atlas (M0), con HA y respaldo del proveedor dentro de la cuota gratuita; el costo es dependencia de red y credenciales.

**Sobre los datos y el crudo**

5. *¿Los datos son reales?* No: son sintéticos, generados con semilla fija y errores intencionales; describen la empresa ficticia (como pide el enunciado) y las cifras son las del dataset, no de un negocio real.
6. *¿Por qué tantos errores en las fuentes crudas?* Porque el enunciado pide que las fuentes **lleven** errores (duplicados, nulos, formatos…) precisamente para demostrar que el ETL los corrige con evidencia.
7. *¿Cómo sabe que los errores estaban?* `evidencia_extraccion*.csv` (nulos/duplicados por archivo) y `evidencia_extraccion_columnas.csv` (tipo inferido por columna) muestran el estado crudo; el tracker de calidad registra cada corrección con regla aplicada.
8. *¿Cómo valida los mínimos de la rúbrica?* `validacion_minimos.csv`: clientes 1,862 (1.86x el mínimo), productos 606, pedidos 3,277, detalles 3,891, reseñas 2,475, navegación 4,236 — todos sobre el mínimo, con holgura documentada.

**Sobre el ETL**

9. *¿Cuáles son las 10 transformaciones?* Las obligatorias: duplicados, normalización de texto, nulos, tipos, fechas, precios, cantidades, unificación de categorías, columnas innecesarias, derivadas (ver sección 7).
10. *¿Qué es el tracker de calidad?* El registro de cada decisión de limpieza: filas antes/después, registros afectados y la regla, en `calidad_transformaciones.csv` — sin esto no sabría si limpió de más o de menos.
11. *¿Por qué `subtotal = precio × cantidad` y `total = subtotal − descuento` importan?* Son los campos derivados obligatorios; sin ellos no hay márgenes, conciliación ni revenue por línea, y las preguntas de negocio no se responden.

**Sobre PostgreSQL**

12. *¿Está en 3FN?* Sí: cada tabla cubre una entidad con dependencias funcionales solo sobre su llave; la fact desnormalizada es la excepción intencional; el diagrama ER y la explicación breve están en este informe (sección 8). Por la rúbrica 3FN es lo mínimo.
13. *¿Qué restricciones implementó?* 9 PK, 13 FK, 4 UNIQUE (llaves naturales), 15 NOT NULL, 9 CHECK (precios, descuentos, coherencia `total = subtotal − descuento`) más 19 índices.
14. *¿Por qué la vista `v_resumen_ventas`?* Encapsula el JOIN de 5 tablas para el resumen mensual sin reescribirlo; Q20 la usa tal cual.
15. *¿Cómo demostraron que el índice sirve?* `EXPLAIN ANALYZE` antes/después sobre `ix_fact_anio_mes`: recorrido completo → `Index Scan`, **4.17x** más rápido (promedio del servidor). Sin evidencia, "un índice ayuda" es un deseo.
16. *¿Qué consultas hace?* 20 (Q01..Q20): desde agregaciones simples (top productos) hasta JOIN de 7 tablas (Q19) y resumen sobre la vista (Q20); INNER y LEFT JOIN, HAVING, etc.

**Sobre MongoDB**

17. *¿Por qué documentos para el catálogo?* Los atributos cambian por familia (procesador/RAM vs cámara/batería); columnas fijas desperdiciarían el 80% del almacenamiento; el documento semiestructurado es el modelo natural.
18. *¿Qué demuestran con los pipelines?* Que saben agrupar y relacionar (`$group`, `$lookup`): ratings por categoría, vistos no vendidos, correlación, dispositivos, ciudad. Y con `find`+operadores: filtros y conteos reales (`$gt/$lt/$gte/$lte/$in/$and/$or`).
19. *¿Por qué `$lookup` no reemplaza un JOIN transaccional?* Porque está pensado para agregaciones, no para integridad referencial; el DDL/SQL mantiene las restricciones, Mongo mantiene la flexibilidad.

**Sobre la integración**

20. *¿Cómo conectan ambos motores?* Con Python/Pandas: ventas (PostgreSQL: id_producto, cantidad_vendida, ingresos) × navegación (MongoDB: numero_visualizaciones), cruce por `id_producto`.
21. *¿Cuál es la conclusión más importante?* La navegación ayuda pero no garantiza la venta: relación débil (+0.323 en la población favorable). Hay 63 productos con tráfico y cero ventas — operar eso es trabajo de negocio, no de "más publicidad".

**Sobre Cloud**

22. *¿Qué parte es cloud real y cuál simulada?* Cloud Database (SQL y NoSQL): **real** (Supabase/Atlas). Cloud Storage y Cloud Computing: **simulados** con árbol portable — permitido por el enunciado ("utilizar o simular"); no se finge infraestructura.
23. *¿Por qué no Colab?* Es recomendación, no obligación; se descartó por ser efímero y sin SLAs ni orquestación. En su lugar: cómputo portable + dos Cloud DBs administradas.
24. *¿Qué pasa si la demo en vivo falla (red de la escuela)?* El pipeline degrada a local y sigue; `pytest` (167) corre 100% offline en segundos; y `reporte.html` abre sin internet con doble clic.

**Sobre calidad, pruebas y reproducibilidad**

25. *¿Cómo garantizan que los números son correctos?* Pruebas contra **cálculo independiente a mano** sobre fixtures mínimos; ningún test compara contra valores fijos del dataset (cambia con el generador); protegen contra doble conteo y mezcla de órdenes en el embudo.
26. *¿Cómo reproducen lo presentado?* Semilla fija + `run_all.py`: dos corridas producen el mismo dato; los artefactos commiteados son byte-idénticos a los auditados.
27. *¿Por qué commitean los resultados?* Como evidencia auditable: el jurado puede ver cualquier Q/A/B/KPI sin infraestructura ni pipeline.
28. *¿Qué diferencia hay entre 1,010 y 1,314 "clientes activos"?* RFM segmenta a quienes **compraron completado** (1,010); el KPI "Clientes activos" cuenta cualquier pedido (1,314). Ambos citan su contexto.
29. *¿Por qué 92, 55, 63 y 122?* Vistas≠ventas en cuatro sentidos distintos (sección 15); son predicados diferentes del mismo problema de inventario.
30. *¿Puedo confiar en los KPIs?* Son el output de la corrida con semilla fija y están en CSVs commiteados; cualquiera puede recalcularlos.

**Sobre entrega**

31. *¿Dónde está el reporte?* `data/reports/reporte.html` (doble clic) + 13 figuras individuales en `data/figures/`.
32. *¿Qué vieron mal en el modelo relacional?* Nada de fondo: es un artefacto estático para el documento; se detectó solape de cajas al crecer el esquema y se corrigió — la lección: los layouts manuales se desincronizan del esquema.

## 25. Guion de explicación para el equipo (12–15 min)

**Minuto 0–1 — El problema.** "Somos consultores de datos de Corporativo JUC
(electrónica, México). Sus datos viven en CSV, hojas de cálculo, SQL y JSON;
queremos integrarlos, analizarlos y visualizarlos como prototipo."

**Minuto 1–3 — Las fuentes.** Mostrar `data/raw/`: CSV sucio (a propósito),
JSON con atributos variables por familia, Sheets→XLSX. "Toda fuente genera
errores intencionales; ustedes ven la evidencia en `evidencia_extraccion*.csv`."

**Minuto 3–5 — El ETL.** Mostrar `calidad_transformaciones.csv`: 93 filas de
evidencia, reglas aplicadas, antes/después. "El ETL no limpia en secreto:
documenta cada decisión. Importante: el subtotal/total y los campos de fecha
están como exige el enunciado."

**Minuto 5–7 — PostgreSQL.** Mostrar `01_ddl.sql` (3FN + restricciones +
índices), `03/04 explain` (índice 4.17x antes/después), `v_resumen_ventas`.
"Misma tabla-resumen tres veces: la vista no duplica lógica."

**Minuto 7–9 — MongoDB.** Mostrar `productos` con atributos por familia, luego
`A11` (rating por categoría), `A02` (vistos nunca vendidos) y `B13`
(`countDocuments`). "El catálogo no cabe en columnas fijas; por eso documentos."

**Minuto 9–11 — Integración + Cloud.** Mostrar `integracion_resumen.csv`:
47/47 OK. "SQL→Atlas: si la red falla, degrada a local; nunca sale sin
resultados. En vivo: Supabase si la escuela lo permite."

**Minuto 11–13 — Análisis y KPIs.** Mostrar `01_kpis_generales.csv`:
$127.3M facturados, 34.35% cancelación, Pareto 24.1%→80%, margen 29.46%.
"La navegación ayuda pero no pide: 63 productos con tráfico no vendieron nada."

**Minuto 13–15 — Visualizaciones y cierre.** Abrir `reporte.html` (doble
clic): recorrer Principales 1–7 y Anexo 8–13. "13 figuras interactivas; el
jurado puede aislar series; todo funciona offline. Lo que pedimos: apoyo al
equipo para defender decisiones; lo que nos llevamos: un pipeline completo,
reproducible y verificado."

## 26. Dependencias (qué hace cada paquete, para qué lo usamos)

`requirements.txt` lista **22 paquetes** (antes 31: se eliminaron 8 que no
importaba nadie — `matplotlib` y su pila porque las figuras se dibujan con
Plotly; `seaborn` nunca se llegó a usar). Versiones congeladas verificadas:
`pytest` pasa **167/167** con este conjunto. Ningún paquete se usa "por si
acaso": cada uno tiene un import real o un papel de driver/transitorio
ineludible en tiempo de ejecución.

| Paquete | Para qué sirve **en este proyecto** | Rol |
|---|---|---|
| `pandas` | Motor del ETL (T01–T10), datasets, mínimos, RFM, correlación, Pareto, embudo, KPIs | Directo (`import pandas`) |
| `numpy` | Operaciones vectorizadas del ETL y del análisis (detención, conteos, sumatorias) | Directo (`import numpy`) |
| `SQLAlchemy` | Abstracción sobre el motor relacional: el código habla SQLAlchemy, no SQL crudo (salvo DDL/consultas exportadas); conecta a Supabase o a SQLite temporal | Directo (`import sqlalchemy`) |
| `psycopg2-binary` | Controlador que SQLAlchemy usa por debajo para conectarse a PostgreSQL real (Supabase) | Transitorio requerido (conductor de SQLAlchemy) |
| `pymongo` | Conexión a MongoDB Atlas (colecciones, índices, pipelines, `find`) | Directo (`import pymongo`) |
| `dnspython` | Resolver DNS para URIs `mongodb+srv://` (la de Atlas); sin él, la conexión a Atlas no resuelve el SRV | Transitorio requerido (Atlas SRV) |
| `python-dotenv` | Carga `.env` (credenciales) al arrancar; `.env` jamás se versiona | Directo (`from dotenv import load_dotenv`) |
| `openpyxl` | Motor que Pandas usa para leer las hojas `.xlsx` de Google Sheets (fuente C) | Transitorio requerido (lectura XLSX) |
| `et_xmlfile` | Motor XML de `openpyxl` | Transitorio |
| `python-dateutil` | Parseo de fechas que usa Pandas (incluyendo formatos en español del crudo) | Transitorio (Pandas) |
| `pytz` | Zonas horarias del manejo de fechas de Pandas | Transitorio (Pandas) |
| `tzdata` | Base de datos de zonas horarias que Pandas referencia | Transitorio (Pandas) |
| `six` | Compatibilidad py2/3 que `python-dateutil` aún importa | Transitorio (dateutil) |
| `greenlet` | Soporte asíncrono opcional de SQLAlchemy; el proyecto trabaja síncrono pero se congela por consistencia | Transitorio (SQLAlchemy) |
| `plotly` | Las **13 figuras** HTML interactivas y `reporte.html` (hover, zoom, aislar series) | Directo (`plotly.graph_objects`, `plotly.subplots`) |
| `narwhals` | Capa que Plotly 7 usa para objetos Series/DataFrame | Transitorio (Plotly) |
| `pytest` | La suite de 167 pruebas y la etapa `--con-tests` del orquestador | Directo/orquestador |
| `iniconfig` | Registro y verificación de plugins de `pytest` | Transitorio (pytest) |
| `pluggy` | Sistema de plugins interno de `pytest` (carga y ciclo de vida) | Transitorio (pytest) |
| `packaging` | Verificación de versiones que usan pytest y otros | Transitorio (pytest) |
| `colorama` | Salida con color de `pytest` en Windows (verde = pasado) | Transitorio (pytest, Windows) |
| `typing_extensions` | Anotaciones modernas para `pymongo` y otros en versiones de Python anteriores a 3.10/3.11 — el `venv` usa 3.12, pero se congela por portabilidad | Transitorio |

**Regla del proyecto:** todo lo que aparece en `requirements.txt` o es
"directo" (alguien hace `import`) o "transitorio requerido" (se necesita en
tiempo de ejecución aunque no aparezca en el código: driver de conexión,
lector de XLSX, resolver SRV, dependencias de pytest). Si un paquete no tiene
cómo justificar su lugar, **no está**: se eliminaron 8 por eso, y la
verificación (167 verdes) confirmó que nada los necesita.
