# Corporativo JUC — Pipeline de datos

**ETL + PostgreSQL + MongoDB + Cloud Computing, de fuentes crudas a un reporte interactivo.**
Proyecto de ingeniería de datos sobre una empresa ficticia de electrónica (México),
reproducible con una sola orden y una semilla fija (`SEED = 20260904`).

| En un vistazo | |
|---|---|
| Datos | 3 fuentes (CSV / JSON / Google Sheets→`.xlsx`) con errores intencionales |
| Limpieza | 10 transformaciones auditables + evidencia (93 filas) |
| Modelo | PostgreSQL 3FN (9 objetos + vista `v_resumen_ventas`) · MongoDB (3 colecciones, 12 índices) |
| Preguntas de negocio | 20 SQL + 12 pipelines + 15 `find`/`count` (**47/47 OK**) |
| Indicadores | 22 KPIs |
| Visualizaciones | 13 gráficos Plotly interactivos en `reporte.html` |
| Pruebas | 167 (pytest) |
| Cloud | **Supabase** (PostgreSQL 17) + **MongoDB Atlas** M0 — o modo local sin credenciales |

> Toda la explicación profunda — arquitectura, decisiones, la rúbrica Parte I–VII,
> comandos, preguntas de defensa y guion de exposición — vive en **[`informe.md`](informe.md)**.
> Este README es la guía mínima para ejecutarlo.

## Inicio rápido (sin credenciales)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py
```

El orquestador ejecuta `generar -> etl -> integracion -> analisis -> graficos` y
**se detiene en la primera etapa que falle**. Al terminar abre
**`data/reports/reporte.html`** (doble clic): el reporte con los 13 gráficos, o combina
lo que ya se generó si prefieres revisar paso a paso.

### Comandos esenciales

```powershell
.\.venv\Scripts\python.exe src\run_all.py --listar        # ver etapas
.\.venv\Scripts\python.exe src\run_all.py --sin-generar   # reutilizar data/raw
.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos
.\.venv\Scripts\python.exe src\run_all.py --con-tests     # pipeline + pytest
.\.venv\Scripts\python.exe -m pytest -q                   # solo la suite (167)
```

## Modo nube (opcional)

Con un `.env` rellenado, el pipeline **usa los motores reales**; sin él (o si fallan),
**degrada a SQLite/NDJSON local** sin dejar de producir resultados. Nunca sube datos a
cuentas ajenas: usa solo las credenciales del operador.

```powershell
copy .env.example .env   # edita con tus credenciales
```

- Supabase: usa el **Session pooler** (`aws-0-<region>.pooler.supabase.com`, `PG_SSLMODE=require`).
  El host directo resuelve solo por IPv6.
- MongoDB Atlas: `MONGO_URI=mongodb+srv://<usuario>:<clave>@<cluster>.mongodb.net/?appName=<app>`, `MONGO_DB=juc`.
- Forzar modo local: `SIN_POSTGRES=1`, `SIN_MONGO=1` (o `FORZAR_SQLITE=1`).
- `.env` nunca se versiona (en `.gitignore`); `.env.example` viaja como plantilla.

## Estructura

```text
src/            generate_sources → etl_extract → etl_transform → etl_load
                → integration → analysis → viz   (+ run_all.py, config.py, utils.py)
tests/          167 pruebas (analysis, integration, run_all, transform)
data/raw/       fuentes crudas (CSV / JSON / Sheets)
data/processed/ tablas normalizadas 3FN + datasets para cada motor
data/sql/       DDL, consultas, EXPLAIN ANALYZE (layout del enunciado)
data/nosql/     colecciones NDJSON, índices, pipelines y consultas
data/reports/   evidencia + KPIs + reporte.html
data/figures/   13 HTML interactivos + plotly.min.js
```

## Resultados de la última corrida (semilla `SEED = 20260904`)

| Indicador | Valor |
|---|---|
| Facturación | $127,336,206.51 |
| Pedidos completados / totales | 1,483 / 2,259 |
| Ticket promedio | $85,863.93 |
| Cancelación | 34.35% |
| Margen real ponderado | 29.46% |
| Clientes activos | 1,314 |
| Productos vendidos | 514 de 606 (Pareto: 124 explican el 80%) |

## Notas

- **Datos sintéticos**: las conclusiones describen la empresa ficticia, no un negocio real.
- Verificado en vivo el 2026-11-09 contra Supabase + Atlas: 5/5 etapas OK, 47/47
  consultas OK, 167 pruebas, 13/13 gráficos. Si la red falla, degrada a local y
  sigue funcionando.
- Documentación completa: **[`informe.md`](informe.md)** · reporte interactivo:
  **`data/reports/reporte.html`** · evidencia: `data/reports/`.
