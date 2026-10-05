# NovaCommerce — Pipeline de datos (ETL + Cloud + Análisis)

Proyecto completo de ingeniería de datos sobre una empresa ficticia,
**NovaCommerce S.A. de C.V.**, una tienda de electrónica en México.

El pipeline genera tres fuentes crudas **con errores intencionales**, las limpia
con 10 transformaciones auditables, las carga en un modelo relacional y un
almacén de documentos, responde 28 preguntas de negocio con SQL y agregaciones
NoSQL, y produce un reporte con 12 gráficos.

Todo es **reproducible**: la semilla `SEED = 20260904` fija los datos
sintéticos, así que dos ejecuciones dan exactamente el mismo resultado.

---

## 1. Puesta en marcha

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py
```

`run_all.py` ejecuta las seis etapas en orden y **se detiene en la primera que
falle**, para no dejar datasets a medio escribir.

```bash
python src\run_all.py --listar          # ver las etapas
python src\run_all.py --sin-generar     # reutilizar data/raw ya generado
python src\run_all.py --solo analisis graficos
python src\run_all.py --con-tests       # pipeline + pytest
```

### Ejecutar una etapa suelta

```bash
python src\generate_sources.py   # Parte I  -> data/raw/
python src\etl_load.py           # Partes I-V -> data/processed/
python src\integration.py        # Parte Cloud -> SQL + NoSQL
python src\analysis.py           # Parte V   -> data/reports/analisis/
python src\viz.py               #            -> data/figures/
python -m pytest tests -q        # 146 pruebas
```

---

## 2. Estructura

```
bigdata_project/
├── src/
│   ├── config.py            Rutas, semilla, mínimos del punto 4, catálogos, paleta
│   ├── utils.py              Logging, tracker de calidad, formateo de tablas
│   ├── generate_sources.py   Parte I: las 3 fuentes crudas, sucias a propósito
│   ├── etl_extract.py        Extracción + evidencia por tabla y columna
│   ├── etl_transform.py      Las 10 transformaciones (T01..T10)
│   ├── etl_load.py           3FN → dataset analítico + documentos para MongoDB
│   ├── integration.py        DDL, carga, verificación, 18 consultas + 10 pipelines
│   ├── analysis.py           19 análisis de negocio
│   ├── viz.py                12 gráficos PNG
│   └── run_all.py            Orquestador
├── tests/                    test_transform.py, test_integration.py,
│                             test_analysis.py, test_run_all.py
├── data/
│   ├── raw/                  csv/, json/, sheets/   (con errores)
│   ├── processed/            tablas/, dataset_postgresql.csv, dataset_mongodb.json
│   ├── reports/              calidad, consultas, análisis, figuras_indice.csv
│   └── figures/              12 PNG
└── logs/                     pipeline.log
```

---

## 3. Las tres fuentes y sus errores

| Fuente | Origen | Errores que se inyectan |
|---|---|---|
| **A** | CSV + hojas `.xlsx` | Duplicados, ciudades con 7 escrituras distintas, precios `"$1,234.56"`, fechas en texto ambiguo, PK no numéricas, nulos y tipos mezclados |
| **B** | JSON semiestructurado | Cada familia de producto expone **atributos distintos**, ratings fuera de escala, sentiment guardado como texto |
| **C** | Hojas `.xlsx` | Ciudades y categorías sucias, regiones inconsistentes con la ciudad real |

Las tres se limpian con las 10 transformaciones, y **cada una deja evidencia**
en `data/reports/calidad_transformaciones.csv` (filas antes/después, registros
afectados y la regla de negocio aplicada).

### Las 10 transformaciones

| # | Transformación | Qué resuelve |
|---|---|---|
| T01 | Eliminación de duplicados | Mismo negocio registrado dos veces |
| T02 | Normalización de texto | Recortes y **marcadores de faltante** (`N/A`, `NULL`, `-`) → nulo real |
| T03 | Tratamiento de nulos | Imputa lo imputable, **descarta lo crítico** |
| T04 | Corrección de tipos | `"123"` / `123.0` → entero; `"44,347"` → `44347` |
| T05 | Validación de llaves primarias | Descarta `'NULL'`, `'N/A'` en PK |
| T06 | Validación de precios y márgenes | Fuera de `[0,1]` se recorta |
| T07 | Fechas y zona horaria | `DD/MM/YYYY`, `"14 de junio de 2026"`, epoch |
| T08 | Unificación de ciudades y categorías | `GDL`/`GUAD.` → Guadalajara |
| T09 | Eliminación de columnas innecesarias | 12 campos que no aportan |
| T10 | Campos derivados | `costo_estimado`, `utilidad_bruta`, `trimestre`, rollups |

---

## 4. Modelo de datos

**SQL (PostgreSQL, 3FN)** — 8 tablas con PK, FK, índices y `CHECK`:

```
categorias ──┐                    pedidos ──┬── detalle_pedido
dim_ciudades┤                            ├── pagos
dim_sucursales┤                          │
clientes ────┼── pedidos ────────────────┘
             └── productos
```

Más `fact_ventas`, un desnormalizado **deliberado** de 47 columnas (una fila
por línea de venta) que existe para no escribir JOINs en cada gráfico.

**NoSQL (MongoDB)** — 3 colecciones con 12 índices:

| Colección | Documents | Por qué aquí |
|---|---|---|
| `productos` | 606 | `atributos` cambia por familia: un esquema fijo obligaría a 30 columnas casi vacías |
| `resenas` | 2,475 | Review anidada (`cliente.nombre`) |
| `actividad_usuario` | 4,236 | Eventos de navegación |

### Modo simulado vs servidores reales

Sin credenciales el proyecto **no se rompe**: cae a SQLite
(`data/processed/integracion/novacommerce.db`) y a NDJSON con pipelines
equivalentes en Pandas. Todos los agregaciones tienen su versión declaradas en
las dos herramientas.

```bash
copy .env.example .env     # y define PG_* y MONGO_URI
```

| Variable | Efecto |
|---|---|
| `PG_HOST` … `PG_PASSWORD` | Usa PostgreSQL real |
| `MONGO_URI`, `MONGO_DB` | Usa MongoDB real |
| `SIN_POSTGRES=1` / `SIN_MONGO=1` |Fuerza el modo local |
| `FORZAR_SQLITE=1` | No intenta PostgreSQL |

---

## 5. Las 28 consultas

**18 SQL** (`data/reports/consultas_sql/`): top productos y clientes, serie
mensual, mix por categoría, ticket por canal, **inventario muerto** (55
productos que nunca se vendieron), clientes con cancelaciones, conciliación de
pagos, descuentos, geography, premium vs estándar, **ley de Pareto**,
nuevos vs recurrentes, mix trimestral, alta rotación y cobertura por sucursal.

**10 pipelines NoSQL** (`data/reports/consultas_mongodb/`): top vistos,
**inversión que no convierte**, under-exposure, tráfico mensual, navegación
por dispositivo, rating y dispersión, **consulta dinámica sobre un atributo
que solo existe en una familia** (A08), recorrido de un usuario y
**correlación visitas→venta** (A10).

Cada consulta guarda su DDL/pipeline y su resultado en CSV, así que el
resultado es auditable sin volver a ejecutar nada.

---

## 6. Análisis y hallazgos

`data/reports/analisis/` (19 CSV) y `data/figures/` (12 PNG).
Cifras de la ejecución con `SEED = 20260904`.

| Hallazgo | Dato |
|---|---|
| Facturación | $127.3 M en 1,483 pedidos completados |
| Ticket promedio | $85,864 |
| **Cancelación** | **34.4%** de los pedidos |
| Concentración | 124 de 514 productos vendidos (**24.1%**) explican el 80% de la venta |
| Mix | Computadoras 50.9% de la venta, 30.0% de margen |
| Margen vs descuentos | 30.8% sin descuento → **6.0%** con más del 20% |
| Embudo | 1,405 visualizaciones → 942 al carrito (67%) → 468 compras (50%) |
| **Correlación navegación→venta** | Pearson **+0.323**; Spearman **+0.270** |
| Inventario muerto | 63 productos con visitas y **cero** unidades vendidas |
| Catálogo nunca vendido | 55 productos sin una sola venta |

La correlación se reporta en **tres poblaciones** a propósito, no un solo
número: sobre todos los productos es **+0.146**, sobre visitados **+0.104**, y
sobre visitados-y-vendidos **+0.323**. Citar solo la última premia al
bestseller y esconde el inventario muerto, que es justo lo que hay que
atender: 122 productos vendieron sin que nadie los viera, y 63 recibieron
tráfico y no vendieron nada.

Segmentación RFM con reglas documentadas: el **72.4%** de la facturación está
en **Campeones** y **Leales**, y hay 152 clientes **En riesgo** que gastaron
mucho y ya no vuelven (19.7% de la venta).

---

## 7. Pruebas

```bash
python -m pytest tests -q      # 146 pruebas, ~2 s
```

Las pruebas del análisis no comparan contra valores fijos del dataset real
(que cambian cada vez que se ajusta el generador), sino contra un **cálculo
independiente hecho a mano** sobre un fixture mínimo. El riesgo de un módulo
de análisis no es que lance una excepción: es que devuelva un número
plausible y equivocado.

Se cubren en particular los dos errores clásicos de este modelo:

- **Doble conteo.** La fact tiene una fila por línea; sumar `total_pedido`
  línea a línea cuenta cada pedido tantas veces como líneas tenga. Las
  métricas a nivel pedido usan `id_pedido` deduplicado.
- **Mezcla de unidades.** El embudo mezcla **eventos** en los tres pasos,
  nunca personas con productos.
- **Etapas que se cuelan en silencio.** Si `--con-tests` se ignorara, el
  pipeline seguiría saliendo con código 0 y solo cambiaría cuánto tarda. Las
  pruebas del orquestador comprueban qué etapas se eligen, no que el pipeline
  termine bien.

---

## 8. Estado verificado

| | |
|---|---|
| Pruebas | 146 OK |
| Consultas SQL | 18/18 OK |
| Pipelines NoSQL | 10/10 OK |
| Gráficos | 12/12 OK |
| Nulos en el dataset final | **0** en las 8 tablas y en la fact |
| Mínimos del punto 4 | todos cumplen con holgura |
| Trampas de navegación | 15 attractive (14 visitas / **0** unidades) · 15 poco-visto-mucho-vendido (1 / **12**) · 63 visto-nunca-vendido (**2** visitas / 0 unidades) |

PostgreSQL y MongoDB reales **no se han podido validar** en este entorno (sin
contraseña y por timeout). Los resultados de arriba son sobre los modos
simulados, que son los que permiten reproducir el proyecto sin
infraestructura.
