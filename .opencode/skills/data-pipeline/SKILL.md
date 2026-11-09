---
name: Corporativo JUC Pipeline
description: Usa esta skill cuando trabajes en el proyecto BigData de Corporativo JUC (carpeta Proyecto_BigData) — ejecutar el pipeline ETL/integracion/analisis/graficos, regenerar artefactos, entender la estructura de carpetas, o explicar su arquitectura y modos nube/local.
---

# Corporativo JUC — Pipeline de datos

Proyecto de ingeniería de datos sobre la empresa ficticia **Corporativo JUC
S.A. de C.V.** (electrónica, México). BD `juc`, semilla `SEED = 20260904`
(reproducible). Ejecutar siempre desde la raíz del proyecto.

## Comandos

```powershell
# Entorno (una vez)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Pipeline completo (5 etapas; se detiene en la primera que falle)
.\.venv\Scripts\python.exe src\run_all.py

# Variantes
.\.venv\Scripts\python.exe src\run_all.py --listar
.\.venv\Scripts\python.exe src\run_all.py --sin-generar
.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos
.\.venv\Scripts\python.exe src\run_all.py --con-tests

# Etapas sueltas
python src\generate_sources.py   # -> data/raw/
python src\etl_load.py           # -> data/processed/
python src\integration.py        # -> PostgreSQL + MongoDB (+ data/sql, data/nosql)
python src\analysis.py           # -> data/reports/analisis/
python src\viz.py                # -> data/figures/ + data/reports/reporte.html
python -m pytest tests -q        # 167 pruebas
```

## Etapas y responsabilidad

| Etapa | Módulo | Salida principal |
|---|---|---|
| generar | `generate_sources.py` | `data/raw/{csv,json,sheets}` con errores intencionales |
| etl | `etl_extract.py` → `etl_transform.py` → `etl_load.py` | `data/processed/` (tablas 3FN, datasets, evidencia) |
| integracion | `integration.py` | Supabase/SQLite, Atlas/NDJSON, `data/sql/`, `data/nosql/`, `data/reports/consultas_*` |
| analisis | `analysis.py` | 21 CSV + `analisis_resumen.md` |
| graficos | `viz.py` | 13 HTML Plotly + `plotly.min.js` + `reporte.html` |

## Modos nube / local

Se controla con `.env` (ignorado por git; ver `.env.example`):

- Con `SUPABASE_*` y `MONGO_URI` → **PostgreSQL (Supabase)** y **MongoDB Atlas**.
- Sin credenciales (o `FORZAR_SQLITE=1`, `SIN_POSTGRES=1`, `SIN_MONGO=1`) →
  degrada a **SQLite** (`data/processed/integracion/juc.db`) y **NDJSON** sin fallar.
- `juc.db` y los NDJSON locales solo se escriben en modo local; `data/sql/` y
  `data/nosql/` se generan siempre (layout del punto 26).

## Mapa de artefactos

```
data/raw/{csv,json,sheets}      fuentes crudas (A/B/C)
data/processed/tablas/          tablas normalizadas 3FN
data/processed/dataset_postgresql.csv, dataset_mongodb.json
data/processed/integracion/     SQLite local (solo modo local)
data/sql/                       01_ddl.sql, 02_consultas.sql, EXPLAIN
data/nosql/                     *.ndjson, indices.json, 01_pipelines.js, 02_consultas.js
data/reports/                   calidad, consultas_sql/, consultas_mongodb/,
                                analisis/, integracion_entorno.md, figuras_indice.csv,
                                reporte.html
data/figures/                   13 *.html + plotly.min.js
```

## Hechos que no cambian

- 3 fuentes (CSV, JSON, Google Sheets exportado a `.xlsx`).
- 10 transformaciones auditables + campos derivados.
- 9 tablas + 1 vista: las 6 exigidas (`clientes, productos, categorias, pedidos, detalle_pedido, pagos`) + `dim_ciudades`, `dim_sucursales` y `fact_ventas`.
- 47 preguntas: 20 SQL + 12 pipelines de agregación + 15 `find`/`countDocuments`.
- 13 visualizaciones interactivas (Plotly), en dos bloques: Principales (1-7) y Anexo (8-13), y diagrama ER en PNG.
- 167 pruebas (`pytest`), todas deben quedar en verde.

## Reglas

- No edites artefactos de `data/` a mano: se regeneran con el pipeline.
- No commitees `.env` ni credenciales.
- Si cambias el generador, vuelve a correr `run_all.py` completo para mantener
  coherentes datos, reportes y figuras.
- Al documentar, distingue lo real (Supabase/Atlas) de lo local/simulado.
