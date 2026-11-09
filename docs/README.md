# Documentación del proyecto — Corporativo JUC

Este es el **punto de entrada** a la documentación del proyecto. Todo está en
Markdown (texto plano), sin diseño: se puede leer aquí, en GitHub, en VS Code o
convertir a Word/PDF cuando haga falta.

## Qué es el proyecto

Pipeline de ingeniería de datos sobre la empresa ficticia **Corporativo JUC
S.A. de C.V.** (electrónica, México). Toma tres fuentes crudas y sucias (CSV,
JSON y hojas de cálculo), las limpia con 10 transformaciones auditables, las
carga en **PostgreSQL** (modelo relacional 3FN) y **MongoDB** (documentos),
responde **47 preguntas de negocio** y produce **13 visualizaciones
interactivas** y **22 indicadores**. Todo se regenera con una orden y una semilla fija
(`SEED = 20260904`).

## Empieza por aquí

| Documento | Qué contiene |
|---|---|
| [`memoria-corporativo-juc.md`](memoria-corporativo-juc.md) | **Memoria técnica completa**: resumen, arquitectura, estructura, Partes I–VII de la rúbrica, operación, limitaciones y anexos. |
| [`presentacion-corporativo-juc.md`](presentacion-corporativo-juc.md) | Guion de 12 diapositivas, checklist de demo y preguntas probables del jurado. |
| [`../README.md`](../README.md) | Guía de operación: instalación, comandos, etapas, hallazgos y elección de tecnologías. |
| [`../README_CARPETAS.md`](../README_CARPETAS.md) | Mapa carpeta por carpeta: qué genera cada una y qué la consume. |
| [`../GUIA_CONEXION_NUBE.md`](../GUIA_CONEXION_NUBE.md) | Configuración de Supabase (PostgreSQL) y MongoDB Atlas. |
| [`../data/reports/reporte.html`](../data/reports/reporte.html) | Reporte visual con las 13 gráficas interactivas (funciona offline). |

Versiones para entrega:

- `memoria-corporativo-juc.docx` — Word editable, con portada, índice y diagrama ER.
- `memoria-corporativo-juc.pdf` — PDF de 13 páginas.

## Estructura en una vista

```text
Proyecto_BigData/
├── src/                    pipeline (generar → ETL → integración → análisis → gráficos)
├── tests/                  167 pruebas automáticas
├── docs/                   esta documentación (memoria, guion, índice)
├── data/
│   ├── raw/                fuentes crudas A (CSV), B (JSON), C (XLSX)
│   ├── processed/          tablas 3FN y datasets para cada motor
│   ├── sql/                DDL, consultas y EXPLAIN
│   ├── nosql/              colecciones, índices, pipelines y consultas
│   ├── reports/            evidencia, resultados, reporte.html
│   └── figures/            13 HTML de Plotly + plotly.min.js
├── .opencode/skills/       skills de documentación, pipeline e informe
├── README.md               operación
├── README_CARPETAS.md      estructura detallada
└── GUIA_CONEXION_NUBE.md   conexión a Supabase/Atlas
```

## Cómo ejecutarlo

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\run_all.py --con-tests
```

Etapas sueltas y flags:

```powershell
.\.venv\Scripts\python.exe src\run_all.py --listar
.\.venv\Scripts\python.exe src\run_all.py --solo analisis graficos
.\.venv\Scripts\python.exe -m pytest -q
```

Sin credenciales cloud el pipeline **degrada** a SQLite y NDJSON sin fallar.
Con `.env` configurado usa PostgreSQL en Supabase y MongoDB Atlas.

## Mapa de la rúbrica

| Parte | Tema | Evidencia principal |
|---|---|---|
| I | Fuentes y calidad | `data/raw/`, `data/reports/perfil_columnas.csv`, `evidencia_extraccion*.csv` |
| II | ETL y transformaciones | `src/etl_*.py`, `data/reports/calidad_transformaciones.csv`, `validacion_minimos.csv` |
| III | PostgreSQL | `data/sql/01_ddl.sql`, `02_consultas.sql`, `03_explain_analyze.md`, `Q01..Q20` |
| IV | MongoDB | `data/nosql/*.ndjson`, `01_pipelines.js`, `02_consultas.js`, `indices.json`, `A01..A12`, `B01..B15` |
| V | Integración SQL + NoSQL | `data/reports/analisis/11..14` y `20_cuadrantes_visitas_ventas.csv` |
| VI | Cloud | `data/reports/integracion_entorno.md`, `GUIA_CONEXION_NUBE.md`, `.env.example` |
| VII | Visualización | `data/reports/reporte.html`, `data/figures/*.html`, `figuras_indice.csv` |

## Estado verificado

| Comprobación | Resultado |
|---|---|
| Pipeline completo | 5/5 etapas OK |
| Pruebas | 167 passed |
| Consultas SQL | 20/20 OK |
| Pipelines MongoDB | 12/12 OK |
| Consultas `find`/`count` | 15/15 OK |
| Visualizaciones | 13/13 OK |
| Diagrama ER | generado |

Cifras clave de la última corrida: facturación **$127,336,206.51**, 1,483
pedidos completados de 2,259, ticket **$85,863.93**, cancelación **34.35%**,
utilidad bruta **$37,982,053.12** y margen **29.46%**.

## Regenerar la documentación

La memoria se escribe en Markdown y se exporta con el script de la skill
`project-docs`:

```powershell
.\.venv\Scripts\python.exe .opencode\skills\project-docs\scripts\md_a_docx.py `
  docs\memoria-corporativo-juc.md docs\memoria-corporativo-juc.docx `
  --titulo "Memoria tecnica - Corporativo JUC" `
  --subtitulo "Pipeline de datos (ETL + Cloud + Analisis)" `
  --autor "Corporativo JUC" --pdf
```

El PDF usa Word vía COM (o LibreOffice) y actualiza el índice antes de exportar.

## Nota sobre el diseño

Esta documentación es intencionalmente **solo texto**: no incluye plantillas,
colores ni maquetación. La estructura y el contenido están listos para que tú
decidas el formato final (Word, PDF, diapositivas o sitio web).
