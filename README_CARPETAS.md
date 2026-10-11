# Descripción de carpetas y archivos

## /src
Contiene el código fuente del pipeline (ETL, integración SQL+NoSQL, análisis, visualización y orquestador).

- `generate_sources.py` - Genera las 3 fuentes crudas (CSV/JSON/XLSX) con errores intencionales para el ETL.
- `etl_extract.py` - Extrae y valida las fuentes crudas; genera evidencia de extracción.
- `etl_transform.py` - Aplica las 10 transformaciones necesarias; produce tablas normalizadas 3FN.
- `etl_load.py` - Carga dimensiones y fact_ventas; genera datasets procesados.
- `integration.py` - Integra con Supabase (PostgreSQL) o SQLite; integra con MongoDB Atlas o NDJSON; ejecuta consultas/pipelines, EXPLAIN, DDL y genera `integracion_entorno.md`.
- `analysis.py` - Cálculos de negocio: KPIs, series temporales, mixes, RFM, correlación navegación-venta, Pareto, cuadrantes visitas/ventas, satisfacción.
- `viz.py` - Genera 12 gráficas a partir de los resultados del análisis.
- `run_all.py` - Orquestador de las 5 etapas (generar, etl, integracion, analisis, graficos).
- `config.py` - Configuración central (rutas, semilla, catálogos, conexiones Supabase/Atlas).
- `utils.py` - Utilidades comunes (logging, formateadores, tablas).
- `er_diagram.py` - Genera diagrama ER (PNG + MD).
- `__init__.py` - Módulo Python.

## /tests
Pruebas automatizadas (pytest, 160 passed).

- `test_analysis.py` - Valida KPIs, correlación, inventario muerto, under-exposure, cuadrantes, Pareto.
- `test_integration.py` - Valida DDL/FK/UNIQUE/VIEW, índices Mongo, EXPLAIN, consultas SQL/Mongo, simulación Pandas.
- `test_run_all.py` - Valida que el orquestador ejecuta las 5 etapas correctamente.
- `test_transform.py` - Valida transformaciones, normalización, limpieza y reglas de negocio.
- `test_utils.py` - Valida utilidades.

## /data
Datos organizados como replica de almacenamiento cloud (jerarquía por carpetas).

### data/raw
Datos crudos generados (con errores intencionales).

- `raw/csv/` - Fuente A: `clientes.csv`, `productos.csv`, `pedidos.csv`, `detalle_pedido.csv`, `pagos.csv`
- `raw/json/` - Fuente B: `productos_semiestructurados.json`, `resenas.json`, `actividad_usuario.json`
- `raw/sheets/` - Fuente C: `sucursales.xlsx`, `proveedores.xlsx`, `promociones.xlsx`, `objetivos_venta.xlsx`

### data/processed
Datos limpios/listos para integración y análisis.

- `processed/tablas/` - Tablas normalizadas 3FN (SQL): `clientes.csv`, `productos.csv`, `categorias.csv`, `pedidos.csv`, `detalle_pedido.csv`, `pagos.csv`, `dim_ciudades.csv`, `dim_sucursales.csv`
- `processed/dataset_postgresql.csv` - Dataset fact_ventas desnormalizado para consultas SQL.
- `processed/dataset_mongodb.json` - Documentos agregados para carga en MongoDB.
- `processed/integracion/` - Artefactos de integración: `novacommerce.db` (SQLite simulado), `mongo/*.ndjson` (colecciones), `mongo/indices.json`
- `processed/integracion/mongo/` - `productos.ndjson`, `resenas.ndjson`, `actividad_usuario.ndjson`, `indices.json`

### data/reports
Reportes, evidencia, consultas y artefactos entregables.

- Raíz: `calidad_transformaciones.csv`, `evidencia_extraccion.csv`, `evidencia_extraccion_columnas.csv`, `validacion_minimos.csv`, `perfil_columnas.csv`, `integracion_resumen.csv`, `figuras_indice.csv`, `integracion_entorno.md`, `modelo_relacional.png`, `modelo_relacional.md`, `ejemplo_documento_producto.json`
- `reports/consultas_sql/` - `01_ddl.sql`, `02_consultas.sql`, `03_explain_analyze.md`, `04_explain_analyze.csv`, `Q01_*.csv`..`Q20_*.csv`
- `reports/consultas_mongodb/` - `01_pipelines.js`, `02_consultas.js`, `A01_*.csv`..`A10_*.csv`, `B01_*.csv`..`B15_*.csv`
- `reports/analisis/` - `01_kpis_generales.csv`, `02_ventas_mensuales.csv`, `03_mix_categoria.csv`, `04_mix_canal.csv`, `05_mix_region.csv`, `06_por_sucursal.csv`, `07_segmentos_clientes.csv`, `08_detalle_segmentos.csv`, `09_embudo_navegacion.csv`, `10_embudo_notas.csv`, `11_correlacion_visitas_ventas.csv`, `12_dispersion_visitas_ventas.csv`, `13_inventario_muerto.csv`, `14_under_exposure.csv`, `15_ley_pareto.csv`, `16_calidad_pago.csv`, `17_impacto_descuentos.csv`, `18_satisfaccion.csv`, `19_productos_valorados.csv`, `20_cuadrantes_visitas_ventas.csv`, `analisis_resumen.md`

### data/figures
Gráficas PNG (12): `01_ventas_mensuales.png`, `02_mix_categoria.png`, `03_ticket_por_canal.png`, `04_ley_de_pareto.png`, `05_segmentos_clientes.png`, `06_embudo_navegacion.png`, `07_correlacion_visitas_ventas.png`, `08_inventario_muerto.png`, `09_under_exposure.png`, `10_impacto_descuentos.png`, `11_satisfaccion.png`, `12_por_sucursal.png`

## /logs
Logs y artefactos de referencia.

- `pipeline.log` - Log completo de ejecución (run_all.py)
- `catalogo_maestro.csv` - Catálogo maestro limpio (referencia)
- `perfil_visualizacion.csv` - Rol generado por producto (navegación vs ventas)

## /tests (resumen funcional)
Pruebas que validan integridad end-to-end: fuentes→ETL→SQL/NoSQL→análisis→gráficas.
