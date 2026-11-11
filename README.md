# Corporativo JUC — Pipeline de datos (ETL + Cloud + Análisis)

Guía de uso para quien clona el proyecto y quiere **ejecutarlo**. Todo está
pensado para reproducirse con una sola orden y una semilla fija
(`SEED = 20260904`): dos ejecuciones producen exactamente el mismo dato.

> El detalle completo del proyecto — decisiones, cifras, evidencia y mapa de
> la rúbrica — está en **`informe.md`** (fuente para el documento de apoyo en
> Word). Este README es solo la guía de uso.

## 1. Qué es

Pipeline de ingeniería de datos sobre una empresa ficticia de electrónica en
México. Genera tres fuentes crudas **con errores intencionales**, las limpia
con 10 transformaciones auditables, las carga en **PostgreSQL** (3FN) y
**MongoDB** (documentos), responde **47 preguntas de negocio**, y produce un
reporte con **13 gráficos interactivos** (Plotly) y **22 indicadores**.

## 2. Requisitos

- Windows + PowerShell (probado) — también sirve cualquier Python 3
- Python 3.12, `pip`
- (Opcional, para los motores reales) credenciales de **Supabase** y
  **MongoDB Atlas**; sin ellas el pipeline corre en modo local (SQLite/NDJSON)

## 3. Puesta en marcha (modo local, sin credenciales)

```powershell
cd Proyecto_BigData
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py
```

`run_all.py` ejecuta las cinco etapas en orden
(`generar -> etl -> integracion -> analisis -> graficos`) y **se detiene en la
primera que falle**. Al terminar verás las tablas cargadas, las 47 consultas
OK, los 13 gráficos y el reporte en `data/reports/reporte.html`.

### Etapas y flags

```powershell
.\.venv\Scripts\python.exe src\run_all.py --listar         # ver etapas
.\.venv\Scripts\python.exe src\run_all.py --sin-generar    # reutilizar data/raw existente
.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos
.\.venv\Scripts\python.exe src\run_all.py --con-tests      # pipeline + pytest al final
```

### Ejecutar una etapa suelta

```powershell
.\.venv\Scripts\python.exe src\generate_sources.py   # Parte I  -> data/raw/
.\.venv\Scripts\python.exe src\etl_load.py           # Partes I-V -> data/processed/
.\.venv\Scripts\python.exe src\integration.py        # Parte Cloud -> SQL + NoSQL
.\.venv\Scripts\python.exe src\analysis.py           # Parte V   -> data/reports/analisis/
.\.venv\Scripts\python.exe src\viz.py               #            -> data/figures/ + data/reports/reporte.html
```

## 4. Modo nube (Supabase + MongoDB Atlas reales)

El pipeline intenta conectar automáticamente **solo si hay credenciales
válidas** en `.env`; si no existen (o fallan), degrada a SQLite + NDJSON sin
romperse. Nunca sube datos a cuentas ajenas: usa únicamente el `.env` que usted
defina.

```powershell
copy .env.example .env   # y edita los valores
```

**Supabase:** use el **Session pooler** (`aws-0-<region>.pooler.supabase.com`,
usuario `postgres.<proyecto>`, `PG_SSLMODE=require`) o la conexión directa si su
red tiene IPv6 (`db.<proyecto>.supabase.co` solo resuelve por IPv6).

```env
SUPABASE_HOST=aws-0-us-east-1.pooler.supabase.com
SUPABASE_PORT=5432
SUPABASE_DATABASE=postgres
SUPABASE_USER=postgres.<su_proyecto_id>
SUPABASE_PASSWORD=<su_password>
PG_SSLMODE=require
```

(`SUPABASE_HOST` tiene prioridad sobre `PG_HOST`; una conexión directa
`PG_HOST=db.<proyecto>.supabase.co` funciona si hay IPv6.)

**MongoDB Atlas:**

```env
MONGO_URI=mongodb+srv://<USUARIO>:<PASSWORD>@<CLUSTER>.mongodb.net/?appName=<APP>
MONGO_DB=juc
```

**Forzar modo local** aunque haya credenciales:

```env
SIN_POSTGRES=1   # SQLite en lugar de Supabase
SIN_MONGO=1      # NDJSON local en lugar de Atlas
FORZAR_SQLITE=1  # no intentar PostgreSQL
```

**Pasos para probar con sus propias cuentas:** crear proyecto gratuito en
Supabase (usar Session Pooler) y cluster M0 gratuito en MongoDB Atlas con un
usuario DB; permitir acceso desde su IP (o `0.0.0.0/0` para pruebas); copiar
`.env.example` a `.env` y ejecutar `src\run_all.py`. En consola aparecerá
`Supabase conectado...` y/o `MongoDB conectado...`.

> Nunca comitee `.env` (ya está en `.gitignore`); `.env.example` sí viaja al
> repositorio. Con credenciales se crean las 9 tablas + vista `v_resumen_ventas`
> en Supabase y las colecciones `productos`, `resenas`, `actividad_usuario` en
> Atlas. `pytest` siempre usa SQLite temporal: no requiere nube.

## 5. Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q    # 167 pruebas
```

Las pruebas no comparan contra valores fijos del dataset (cambia al ajustar el
generador), sino contra un **cálculo independiente hecho a mano** sobre fixtures
mínimos: lo que se valida es que el análisis no devuelva números plausibles y
equivocados.

## 6. Qué obtiene al terminar

```
data/raw/                    3 fuentes crudas con errores (CSV/JSON/XLSX)
data/processed/              tablas 3FN + dataset_postgresql.csv + dataset_mongodb.json
data/sql/                    DDL, consultas, EXPLAIN (punto 26 del enunciado)
data/nosql/                  colecciones NDJSON, pipelines, consultas, índices
data/reports/                evidencia: SQL (Q01..Q20), Mongo (A01..A12, B01..B15),
                             análisis (21 CSV), KPIs, reporte.html
data/figures/                13 HTML interactivos + plotly.min.js
```

El reporte unificado es `data/reports/reporte.html`: bloque **Principales
(01-07)** y bloque **Anexo (08-13)**. Pulse sobre cada serie para aislarla o use
zoom con la rueda del ratón. Para imprimirlo: navegador → Imprimir → Guardar
como PDF.

## 7. Cifras clave de la última corrida (semilla `SEED = 20260904`)

| Indicador | Valor |
|---|---|
| Facturación | $127,336,206.51 |
| Pedidos completados / totales | 1,483 / 2,259 |
| Ticket promedio | $85,863.93 |
| Tasa de cancelación | 34.35% |
| Utilidad bruta / margen real | $37,982,053.12 / 29.46% |
| Clientes activos | 1,314 |
| Productos vendidos | 514 de 606 (Pareto: 124 explican el 80%) |
| Calificación promedio | 3.01 (2,475 reseñas) |

Detalle completo, decisiones, evidencia y mapa de la rúbrica: **`informe.md`**.

## 8. Verificado

Corrida en vivo del 2026-11-09 contra **Supabase** (PostgreSQL 17, pooler
IPv4) y **MongoDB Atlas** (cluster M0): 5/5 etapas OK, 47/47 consultas OK,
167 pruebas en verde, 13/13 gráficos OK. Detalle y notas en `informe.md`
(por ejemplo, Atlas puede fallar transitoriamente y el pipeline degrada a
modo local con un `WARNING`).
