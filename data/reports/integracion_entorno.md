# Entorno de integracion

Generado: 2026-10-11 15:24:01

## SQL

| | |
|---|---|
| Motor usado | `Supabase` |
| DDL (tablas, vista, indices) | `data/reports/consultas_sql/01_ddl.sql` |
| Consultas analiticas | `data/reports/consultas_sql/02_consultas.sql` |
| EXPLAIN ANALYZE + indice | `data/reports/consultas_sql/03_explain_analyze.md` |
| Resultados | `data/reports/consultas_sql/Q*.csv` |

## NoSQL

| | |
|---|---|
| Motor usado | `mongodb` |
| Colecciones | productos (606), resenas (2475), actividad_usuario (4236) |
| Indices | 12 definidos |
| Pipelines (agregacion) | `data/reports/consultas_mongodb/01_pipelines.js` |
| Consultas find/count | `data/reports/consultas_mongodb/02_consultas.js` |
| Resultados | `data/reports/consultas_mongodb/A*.csv` (pipelines) y `B*.csv` (find) |

## Como usar servidores reales (Supabase + Atlas)

Copia `.env.example` a `.env` y define las variables. El script detecta
automaticamente las credenciales y sube de modo; si no responden, degrada a
SQLite / NDJSON sin fallar.

```bash
# PostgreSQL en Supabase (ver Panel > Connect)
PG_HOST=db.<proyecto>.supabase.co
PG_PORT=5432
PG_DATABASE=postgres
PG_USER=postgres
PG_PASSWORD=tu_clave
PG_SSLMODE=require

# Alternativa: usar el pooler (IPv4) si tu red no tiene IPv6
# SUPABASE_HOST=aws-0-<region>.pooler.supabase.com
# SUPABASE_PORT=5432
# SUPABASE_USER=postgres.<proyecto>

# MongoDB Atlas (NoSQL)
MONGO_URI=mongodb+srv://usuario:clave@cluster0.xxxxx.mongodb.net/?appName=Cluster0
MONGO_DB=novacommerce
```

Variables de control:

- `SIN_POSTGRES=1` fuerza el modo SQLite aunque haya credenciales.
- `SIN_MONGO=1` fuerza el modo NDJSON local.
- `FORZAR_SQLITE=1` no intenta PostgreSQL.

## Componentes cloud (Parte VI)

| Componente | Como se usa | Donde |
|---|---|---|
| Cloud Database (SQL) | **Real** | PostgreSQL administrado en Supabase (via pooler IPv4) |
| Cloud Database (NoSQL) | **Real** | MongoDB Atlas (clusters M0) |
| Cloud Storage | **Simulado** | El arbol local `data/` replica la organizacion por carpetas de un bucket (ver abajo) |
| Cloud Computing | **Local** | El ETL corre en la maquina del analista; el mismo comando corre sin cambios en una VM o en CI |

### Organizacion de almacenamiento (Cloud Storage simulado)

El layout local imita la jerarquia de carpetas de un bucket, de modo que
publicar a GCS/S3 solo exigiria cambiar el destino, no el codigo:

```
data/raw/csv      -> crudo (Fuente A, formato CSV)
data/raw/json     -> crudo (Fuente B, formato JSON)
data/raw/sheets   -> crudo (Fuente C, formato XLSX/Sheets)
data/processed/tablas           -> tablas normalizadas 3FN (carga SQL)
data/processed/dataset_mongodb.json -> documentos para la coleccion NoSQL
data/reports/     -> resultados de consultas, EXPLAIN y resumenes
data/figures/     -> graficas del reporte
```
