---
name: Informe Corporativo JUC
description: Usa esta skill para preparar la memoria, el informe de entrega o la presentacion del proyecto BigData de Corporativo JUC, alineando cada seccion con las Partes I-VII de la rubrica y usando los artefactos reales del repositorio.
---

# Informe / presentacion — Corporativo JUC

Combina esta skill con `project-docs` (generacion del documento) y
`data-pipeline` (comandos y estructura). Escribe **solo** lo que respalden los
artefactos del repo; nada de cifras inventadas.

## Fuente de verdad por seccion

| Seccion | Se alimenta de |
|---|---|
| Resumen y KPIs | `data/reports/analisis/01_kpis_generales.csv`, `analisis_resumen.md` |
| Parte I — Fuentes | `data/raw/{csv,json,sheets}/`, `data/reports/evidencia_extraccion*.csv`, `perfil_columnas.csv` |
| Parte II — ETL | `src/etl_*.py`, `data/reports/calidad_transformaciones.csv`, `validacion_minimos.csv`, `data/processed/dataset_postgresql.csv`, `dataset_mongodb.json` |
| Parte III — PostgreSQL | `data/sql/01_ddl.sql`, `02_consultas.sql`, `03_explain_analyze.md`, `data/reports/consultas_sql/Q01..Q20`, `modelo_relacional.md/.png`, `integracion_resumen.csv` |
| Parte IV — MongoDB | `data/nosql/*.ndjson`, `01_pipelines.js`, `02_consultas.js`, `indices.json`, `data/reports/consultas_mongodb/A01..A12`, `B01..B15` |
| Parte V — Integracion | `data/reports/analisis/11_correlacion_visitas_ventas.csv`, `12_dispersion_visitas_ventas.csv`, `13_inventario_muerto.csv`, `14_under_exposure.csv`, `20_cuadrantes_visitas_ventas.csv` |
| Parte VI — Cloud | `integracion_entorno.md`, `GUIA_CONEXION_NUBE.md`, `.env.example`, layout `data/sql` + `data/nosql` |
| Parte VII — Visualizacion | `data/reports/reporte.html`, `data/figures/*.html`, `data/reports/figuras_indice.csv` |
| Operacion y pruebas | `README.md`, `README_CARPETAS.md`, `pytest` |

## Estructura del documento

1. Portada (titulo, materia, autor, fecha, repo).
2. Resumen ejecutivo con 3–5 hallazgos y cifras reales.
3. Indice.
4. Objetivo, alcance y arquitectura (4 componentes: ETL, PostgreSQL, MongoDB,
   Cloud; diagrama de flujo).
5. **Parte I** — fuentes y calidad (tabla: fuente, formato, registros, errores).
6. **Parte II** — ETL: 10 transformaciones (tabla id/regla/afectados/evidencia),
   campos derivados y minimos.
7. **Parte III** — modelo relacional 3FN, DDL, PK/FK/UNIQUE/CHECK, vista,
   indices y `EXPLAIN ANALYZE` antes/despues; resumen de las 20 consultas.
8. **Parte IV** — colecciones, 12 pipelines y 15 consultas, indices y las 7
   preguntas del punto 20.
9. **Parte V** — integracion SQL+NoSQL: vistos vs vendidos, merge en Pandas y
   las 5 preguntas.
10. **Parte VI** — cloud: real (Supabase/Atlas) vs simulado (Storage/Computing),
    layout de almacenamiento.
11. **Parte VII** — 10 indicadores (y 22 en total) y las 13 visualizaciones, en dos bloques — Principales (1-7) y Anexo (8-13) — (que muestra cada una).
12. Conclusiones, limitaciones y trabajo futuro.
13. Anexos: diccionario de datos, consultas, evidencia, indice de figuras.

## Guion de presentacion (10–12 diapositivas)

1. Portada + problema de negocio.
2. Arquitectura (4 componentes) y flujo de datos.
3. Fuentes y errores intencionales (Parte I).
4. ETL: las 10 transformaciones y el antes/despues.
5. PostgreSQL: modelo 3FN + `EXPLAIN ANALYZE` (indice).
6. MongoDB: documentos, pipelines y consulta dinamica.
7. Integracion: "los mas vistos no son los mas vendidos".
8. Hallazgos (Pareto, margen vs descuento, RFM, embudo).
9. Cloud: Supabase + Atlas + layout.
10. Visualizaciones interactivas (abrir `reporte.html`).
11. Pruebas y reproducibilidad (167, seed).
12. Conclusiones y mejoras.

## Reglas

- No afirmes "cumple todo" sin citar el artefacto que lo demuestra.
- Separa explicitamente **real** (Supabase/Atlas) de **local/simulado**
  (SQLite/NDJSON/Storage/Computing).
- Las cifras deben coincidir con los CSV; si no, regenera el pipeline.
- Incluye el comando exacto para reproducir y la version de la BD (`juc`).
- Evita capturas desactualizadas: las figuras se regeneran con `run_all.py`.

## Entregables

```
docs/memoria-corporativo-juc.md
docs/memoria-corporativo-juc.docx
docs/memoria-corporativo-juc.pdf   (si hay Word/LibreOffice)
docs/presentacion-corporativo-juc.md
```

Genera el `.docx` y el `.pdf` con `project-docs/scripts/md_a_docx.py --pdf`
(actualiza el indice y usa Word/LibreOffice si estan disponibles).
