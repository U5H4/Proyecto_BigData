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
> decisiones, verificación y detalles prácticos; 17–18 cubren limitaciones y el
> índice propuesto para el Word.

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
| PostgreSQL | Modelo relacional 3FN (9 tablas + vista), cargado en **Supabase** (cloud real) |
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
   PostgreSQL 3FN (9 tablas + fact_ventas desnormalizada + vista v_resumen_ventas)
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

Las 6 tablas exigidas más dos dimensiones y una tabla analítica:

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

El nivel (básico/intermedio/avanzado) no está etiquetado en el SQL: hay
consultas de agregación simple (Q01–Q06), intermedias (Q10–Q18) y avanzadas
(Q19, Q20, Q12); ver sección 16, "Rúbrica vs repo: detalle de etiquetas".

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
después conectó normal. En el expo: pro Barrett, muestre `pytest` y la
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
14. Pruebas y verificación · 15. Limitaciones y trabajo futuro · 16. Anexos
(diccionario, rutas de evidencia, cifras).

Nota para el maquetado: las figuras del Word deben ser imágenes estáticas
(embebidas o enlazadas) o capturas del reporte; el HTML interactivo no se
incrusta en Word. El diagrama ER (`modelo_relacional.png`) ya es una imagen
lista para insertar.
