# Entorno de integracion

Generado: 2026-10-05 18:24:07

## SQL

| | |
|---|---|
| Motor usado | `sqlite` |
| DDL | `data/reports/consultas_sql/01_ddl.sql` |
| Consultas | `data/reports/consultas_sql/02_consultas.sql` |
| Resultados | `data/reports/consultas_sql/*.csv` |

## NoSQL

| | |
|---|---|
| Motor usado | `mongodb` |
| Colecciones | productos (606), resenas (2475), actividad_usuario (4236) |
| Indices | 12 definidos |
| Pipelines | `data/reports/consultas_mongodb/01_pipelines.js` |
| Resultados | `data/reports/consultas_mongodb/*.csv` |

## Como usar servidores reales

Copia `.env.example` a `.env` y define las variables. El script detecta
automaticamente las credenciales y sube de modo:

```bash
# SQL
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=novacommerce
PG_USER=postgres
PG_PASSWORD=tu_clave

# NoSQL
MONGO_URI=mongodb+srv://usuario:clave@cluster.mongodb.net
MONGO_DB=novacommerce
```

Variables de control:

- `SIN_POSTGRES=1` fuerza el modo SQLite aunque haya credenciales.
- `SIN_MONGO=1` fuerza el modo NDJSON local.
- `FORZAR_SQLITE=1` no intenta PostgreSQL.
