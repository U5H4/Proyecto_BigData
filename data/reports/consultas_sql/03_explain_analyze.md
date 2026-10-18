# EXPLAIN ANALYZE: efecto del indice `ix_fact_anio_mes`

Generado: 2026-10-18 12:35:46
Motor: `sqlite` (dialecto `sqlite`)

Consulta medida:

```sql
SELECT COUNT(*) AS pedidos, ROUND(SUM(total), 2) AS facturacion FROM fact_ventas WHERE anio_mes = '2025-06'
```

| Fase | Indice | Tiempo promedio (ms) |
|---|---|---|
| CON INDICE | ix_fact_anio_mes | 0.903 |
| SIN INDICE | (eliminado) | 3.692 |

**Tiempo:** 4.09x mas lento sin indice.

**Plan:** con el indice el motor accede por indice (`Index Scan` en PostgreSQL, `SEARCH ... USING INDEX` en SQLite); sin el hace un recorrido completo de `fact_ventas` (`Seq Scan`/`SCAN`). Ese cambio de acceso es la evidencia de que el indice se usa.

## Plan de ejecucion CON indice

```
4 0 60 SEARCH fact_ventas USING INDEX ix_fact_anio_mes (anio_mes=?)
```

## Plan de ejecucion SIN indice

```
3 0 216 SCAN fact_ventas
```

> Nota: en PostgreSQL el tiempo comparado es el bloque `Execution Time`
> que reporta `EXPLAIN (ANALYZE, VERBOSE)` en el servidor; asi se excluye
> la latencia de red hacia el pooler, que de otro modo dominaria la
> medicion. En SQLite se exporta `EXPLAIN QUERY PLAN` (que revela si se
> uso el indice) y el tiempo se mide con `time.perf_counter` porque SQLite
> no reporta tiempos en el plan.
