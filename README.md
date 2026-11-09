# Corporativo JUC — Pipeline de datos (ETL + Cloud + Análisis)

Proyecto completo de ingeniería de datos sobre una empresa ficticia,
**Corporativo JUC S.A. de C.V.**, una tienda de electrónica en México.

El pipeline genera tres fuentes crudas **con errores intencionales**, las limpia
con 10 transformaciones auditables, las carga en un modelo relacional y un
almacén de documentos, responde 47 preguntas de negocio (20 en SQL, 12 pipelines
de agregación y 15 consultas `find`/`countDocuments` en NoSQL), y produce un
reporte con 13 gráficos **interactivos** (Plotly, HTML).

Todo es **reproducible**: la semilla `SEED = 20260904` fija los datos
sintéticos, así que dos ejecuciones dan exactamente el mismo resultado.

---

## 1. Puesta en marcha

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py
```

`run_all.py` ejecuta las cinco etapas en orden y **se detiene en la primera que
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
python src\viz.py               #            -> data/figures/ + data/reports/reporte.html
python -m pytest tests -q        # 167 pruebas
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
│   ├── integration.py        DDL, carga, verificación, 20 consultas SQL,
│   │                          12 pipelines + 15 consultas find/count NoSQL
│   ├── er_diagram.py         Diagrama ER (PNG) + justificación 3FN
│   ├── analysis.py           19 análisis de negocio
│   ├── viz.py                13 gráficos HTML interactivos (Plotly)
│   └── run_all.py            Orquestador
├── tests/                    test_transform.py, test_integration.py,
│                             test_analysis.py, test_run_all.py
├── docs/                     memoria técnica (.md/.docx/.pdf) y guion de
│                             presentación (.md)
├── .opencode/skills/         skills: project-docs, data-pipeline, informe-juc
├── data/
│   ├── raw/                  csv/, json/, sheets/   (con errores)
│   ├── processed/            tablas/, dataset_postgresql.csv, dataset_mongodb.json
│   ├── sql/                  DDL, consultas y EXPLAIN (scripts SQL)
│   ├── nosql/                colecciones NDJSON, pipelines/consultas e índices
│   ├── reports/              calidad, consultas_sql/, consultas_mongodb/,
│   │                         analisis/, modelo_relacional.md + .png,
│   │                         integracion_entorno.md, figuras_indice.csv,
│   │                         reporte.html (13 gráficos en una página)
│   └── figures/              13 HTML (Plotly) + plotly.min.js
└── logs/                     pipeline.log
```

---

## 3. Las tres fuentes y sus errores

| Fuente | Origen | Errores que se inyectan |
|---|---|---|
| **A** | CSV | Duplicados, ciudades con 7 escrituras distintas, precios `"$1,234.56"`, fechas en texto ambiguo, PK no numéricas, nulos y tipos mezclados |
| **B** | JSON semiestructurado | Cada familia de producto expone **atributos distintos**, ratings fuera de escala, sentiment guardado como texto |
| **C** | Google Sheets (exportadas a `.xlsx`) | Ciudades y categorías sucias, regiones inconsistentes con la ciudad real |

> **Fuente C (Google Sheets).** El enunciado pide una fuente en Google Sheets
> (sucursales, proveedores, promociones u objetivos de venta). Para que el
> pipeline sea reproducible sin credenciales se parte de la **exportación
> `.xlsx`** de esas hojas; en producción se leerían con la Sheets API
> (`gspread`) o con el enlace de exportación, con exactamente las mismas
> columnas.

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

**SQL (PostgreSQL, 3FN)** — 8 tablas con PK, FK, `UNIQUE` (llave natural),
`NOT NULL` de negocio, `CHECK` e índices:

```
categorias ──┐                    pedidos ──┬── detalle_pedido
dim_ciudades┤                            ├── pagos
dim_sucursales┤                          │
clientes ────┼── pedidos ────────────────┘
             └── productos
```

El diagrama se regenera en cada corrida: `data/reports/modelo_relacional.png`
(con la justificación de por qué el modelo está en 3FN en
`data/reports/modelo_relacional.md`).

Más `fact_ventas`, un desnormalizado **deliberado** de 47 columnas (una fila
por línea de venta) que existe para no escribir JOINs en cada gráfico, y la
**vista** `v_resumen_ventas`, que encapsula el JOIN de 5 tablas
(`pedidos`, `detalle_pedido`, `clientes`, `productos`, `categorias`) para el
resumen mensual.

**NoSQL (MongoDB)** — 3 colecciones con 12 índices:

| Colección | Documents | Por qué aquí |
|---|---|---|
| `productos` | 606 | `atributos` cambia por familia: un esquema fijo obligaría a 30 columnas casi vacías |
| `resenas` | 2,475 | Review anidada (`cliente.nombre`) |
| `actividad_usuario` | 4,236 | Eventos de navegación |

### Modo simulado vs servidores reales

Sin credenciales el proyecto **no se rompe**: cae a un archivo SQLite local
(el nombre se define en `src/config.py`) y a NDJSON con pipelines
equivalentes en Pandas. Todos los agregaciones tienen su versión declaradas en
las dos herramientas.

```bash
copy .env.example .env     # y define PG_* (Supabase) y MONGO_URI (Atlas)
```

| Variable | Efecto |
|---|---|
| `PG_HOST` … `PG_PASSWORD`, `PG_SSLMODE` | Usa PostgreSQL real (Supabase exige `PG_SSLMODE=require`) |
| `SUPABASE_HOST` … (pooler IPv4) | Alternativa a `PG_*` si tu red no tiene IPv6 |
| `MONGO_URI` / `MONGO_ATLAS_URI`, `MONGO_DB` | Usa MongoDB real (Atlas) |
| `SIN_POSTGRES=1` / `SIN_MONGO=1` | Fuerza el modo local |
| `FORZAR_SQLITE=1` | No intenta PostgreSQL |

Si el servidor cloud no responde, el pipeline **no falla**: registra un
`WARNING` y sigue en modo local, de modo que siempre quedan resultados.

---

## 5. Las 47 consultas

**20 SQL** (`data/reports/consultas_sql/`): top productos y clientes, serie
mensual, mix por categoría, ticket por canal, **inventario muerto** (55
productos que nunca se vendieron), clientes con cancelaciones, conciliación de
pagos, descuentos, geography, premium vs estándar, **ley de Pareto**,
nuevos vs recurrentes, mix trimestral, alta rotación, cobertura por sucursal,
**detalle 360 con JOIN de 7 tablas** (Q19) y **resumen mensual sobre la vista
`v_resumen_ventas`** (Q20).

**12 pipelines de agregación NoSQL** (`data/reports/consultas_mongodb/`): top
vistos, **inversión que no convierte**, under-exposure, tráfico mensual,
navegación por dispositivo, rating y dispersión, **consulta dinámica sobre un
atributo que solo existe en una familia** (A08), recorrido de un usuario,
**correlación visitas→venta** (A10), **calificación promedio por categoría**
(A11) y **actividad de navegación por ciudad** (A12).

**15 consultas `find`/`countDocuments` NoSQL** (B01–B15): filtros con `$gt`,
`$lt`, `$gte/$lte`, `$in`, `$and` y `$or`, ordenadas con `find().sort().limit()`
y un conteo con `countDocuments()`.

El rendimiento del índice `ix_fact_anio_mes` queda documentado con
`EXPLAIN ANALYZE` en `data/reports/consultas_sql/03_explain_analyze.md`: con el
índice el plan hace `SEARCH ... USING INDEX`, sin él un `SCAN` completo.

Cada consulta guarda su DDL/pipeline y su resultado en CSV, así que el
resultado es auditable sin volver a ejecutar nada.

---

## 6. Análisis y hallazgos

`data/reports/analisis/` (21 CSV) y `data/figures/` (13 HTML interactivos de
Plotly; el reporte unificado está en `data/reports/reporte.html`).
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
python -m pytest tests -q      # 167 pruebas, ~2 s
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
| Pruebas | 167 OK |
| Consultas SQL | 20/20 OK |
| Pipelines NoSQL | 12/12 OK |
| Consultas `find`/`count` NoSQL | 15/15 OK |
| Gráficos | 13/13 OK |
| Diagrama ER | generado (`data/reports/modelo_relacional.png`) |
| Motor relacional | **Supabase** (PostgreSQL 17, Session pooler IPv4) |
| Motor NoSQL | **MongoDB Atlas** 8.0 |
| Efecto del índice | **4.5x** (0.21 ms con índice vs 0.95 ms sin él, `Execution Time` del servidor) |
| Nulos en el dataset final | **0** en las 8 tablas y en la fact |
| Mínimos del punto 4 | todos cumplen con holgura |
| Trampas de navegación | 15 attractive (14 visitas / **0** unidades) · 15 poco-visto-mucho-vendido (1 / **12**) · 63 visto-nunca-vendido (**2** visitas / 0 unidades) |

Los resultados de arriba se generan corriendo contra **Supabase** y **MongoDB
Atlas** reales (Parte VI), configurados en `.env`. Si un servidor no respondiera,
el pipeline registra un `WARNING` y degrada a SQLite / NDJSON sin romperse, así
que el proyecto también se reproduce sin infraestructura.

> Detalle Supabase: el host directo `db.<proyecto>.supabase.co` solo resuelve a
> IPv6; por eso se usa el **Session pooler** (`aws-0-us-west-2.pooler.supabase.com`,
> usuario `postgres.<ref>`), que es IPv4.

---

## 9. Elección de tecnologías: cuándo y por qué

Los cuatro componentes de la arquitectura no son intercambiables: cada uno
resuelve una parte del problema y tiene ventajas y limitaciones que justifican
su lugar en el pipeline.

**PostgreSQL (datos estructurados, 3FN).**
*Cuándo:* entidades fuertemente tipadas y relacionadas (clientes, pedidos,
detalle, pagos) donde la integridad referencial y las transacciones importan.
*Ventajas:* esquema y tipos verificados por la base (PK/FK/UNIQUE/CHECK), JOINs
eficientes, agregaciones SQL, índices y planes con `EXPLAIN ANALYZE`.
*Limitaciones:* rígido para atributos que cambian por fila (obligaría a una
tabla puente `producto_atributo` o a columnas casi siempre nulas); escala
principalmente vertical.

**MongoDB (documentos, atributos variables).**
*Cuándo:* datos de forma flexible — cada familia de producto expone atributos
distintos, reseñas anidadas y eventos de navegación.
*Ventajas:* esquema libre por documento, subdocumentos y arreglos naturales,
aggregation pipeline potente, escala horizontal (sharding).
*Limitaciones:* sin integridad referencial entre colecciones (el `$lookup` no
reemplaza un JOIN transaccional); agregaciones analíticas complejas menos
expresivas que SQL; el esquema se gobierna a nivel aplicación.

**Proceso ETL (Python + Pandas).**
*Cuándo:* limpiar, homologar y derivar campos antes de cargar a cada motor.
*Ventajas:* control total y auditable de las 10 transformaciones; un mismo
DataFrame alimenta el CSV relacional y el JSON documental; reproducible por
semilla.
*Limitaciones:* Pandas trabaja en memoria (no escala a datos masivos sin
Spark/Dask); no es un motor transaccional.

**Cloud Computing (datos y cómputo administrados).**
*Cuándo:* disponibilidad, respaldo y acceso remoto sin mantener servidores.
*Ventajas:* PostgreSQL administrado (Supabase) y MongoDB Atlas gratuitos, alta
disponibilidad y escalabilidad sin operar infraestructura.
*Limitaciones:* dependencia de red y de credenciales, cuotas de los planes
gratuitos, latencia hacia el pooler y menor control del motor; obliga a manejar
secretos (`.env`, fuera del repositorio).

**Cómo se integran (Parte V).** La navegación vive en MongoDB (eventos
flexibles) y las ventas en PostgreSQL (datos transaccionales). La pregunta
"¿los más vistos son los más vendidos?" se resuelve **en Python/Pandas**:
`id_producto, cantidad_vendida, ingresos` se extraen de la fact SQL y
`id_producto, numero_visualizaciones` de MongoDB, y se cruzan con `merge`. Ninguno
de los dos motores haría esa integración por separado, que es justo lo que
demuestra el uso combinado.

**Visualización (Plotly / HTML).**
*Cuándo:* cuando el lector necesita **leer los valores exactos** e interactuar
con los datos (hover, zoom, aislar series), o cuando hay que presentar el
reporte sin depender de capturas estáticas.
*Ventajas:* cada punto expone su valor en el *tooltip*, acercarse a una zona no
pierde resolución (vectorial), las 12 figuras se reúnen en un único
`reporte.html` autocontenido y la librería `plotly.min.js` se comparte entre las
12 páginas para no duplicarla.
*Limitaciones:* el HTML es más pesado que un PNG (~4.7 MB la librería, una sola
vez) y no se revisa en un *diff* de git como una imagen; por eso el **diagrama
ER** sí se mantiene en PNG (`modelo_relacional.png`), donde la imagen estática
es lo natural.

---

## 10. Documentación y presentación

La entrega documental vive en `docs/`:

| Archivo | Uso |
|---|---|
| `docs/memoria-corporativo-juc.md` | fuente de verdad, versionable en git |
| `docs/memoria-corporativo-juc.docx` | entrega formal editable (13 páginas, índice actualizado) |
| `docs/memoria-corporativo-juc.pdf` | entrega para imprimir o subir |
| `docs/presentacion-corporativo-juc.md` | guion de 12 diapositivas + preguntas de defensa |

La memoria cubre las Partes I–VII de la rúbrica y cita el artefacto que respalda
cada cifra. Se regenera así (requiere `python-docx`; el PDF usa Word vía COM o
LibreOffice):

```powershell
.\.venv\Scripts\python.exe .opencode\skills\project-docs\scripts\md_a_docx.py `
  docs\memoria-corporativo-juc.md docs\memoria-corporativo-juc.docx `
  --titulo "Memoria tecnica - Corporativo JUC" `
  --subtitulo "Pipeline de datos (ETL + Cloud + Analisis)" `
  --autor "Corporativo JUC" --pdf
```

Skills reutilizables del proyecto (se cargan con `/reload` o en una sesión
nueva):

- `.opencode/skills/project-docs/` — documentar cualquier repo y exportar a
  Word/PDF.
- `.opencode/skills/data-pipeline/` — comandos, etapas y artefactos de este
  pipeline.
- `.opencode/skills/informe-juc/` — mapeo de la rúbrica y guion de exposición.
