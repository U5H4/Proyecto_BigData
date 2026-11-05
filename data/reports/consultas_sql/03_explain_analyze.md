# EXPLAIN ANALYZE: efecto del indice `ix_fact_anio_mes`

Generado: 2026-10-18 15:56:45
Motor: `Supabase` (dialecto `postgresql`)

Consulta medida:

```sql
SELECT COUNT(*) AS pedidos, ROUND(SUM(total), 2) AS facturacion FROM fact_ventas WHERE anio_mes = '2025-06'
```

| Fase | Indice | Tiempo promedio (ms) |
|---|---|---|
| CON INDICE | ix_fact_anio_mes | 0.217 |
| SIN INDICE | (eliminado) | 0.874 |

**Tiempo:** 4.03x mas lento sin indice.

**Plan:** con el indice el motor accede por indice (`Index Scan` en PostgreSQL, `SEARCH ... USING INDEX` en SQLite); sin el hace un recorrido completo de `fact_ventas` (`Seq Scan`/`SCAN`). Ese cambio de acceso es la evidencia de que el indice se usa.

## Plan de ejecucion CON indice

```
Aggregate  (cost=95.97..95.98 rows=1 width=40) (actual time=0.184..0.185 rows=1 loops=1) |   Output: count(*), round(sum(total), 2) |   ->  Bitmap Heap Scan on public.fact_ventas  (cost=2.29..95.38 rows=118 width=8) (actual time=0.033..0.134 rows=118 loops=1) |         Output: id_detalle, id_pedido, id_cliente, id_producto, id_categoria, id_sucursal, fecha_pedido, anio, mes, mes_nombre, trimestre, anio_mes, cliente_nombre, correo, ciudad, region, canal_registro, es_premium, fecha_alta_cliente, producto_nombre, categoria, descripcion_categoria, rango_precio, precio_lista, margen_bruto_producto, costo_estimado, utilidad_bruta, cantidad, precio_unitario, descuento, porcentaje_descuento, subtotal, total, canal_venta, estado, es_completado, total_pedido, unidades, lineas, categorias_distintas, ticket_promedio_linea, metodo, monto, estado_pago, diferencia_pago, conciliado, id_ciudad |         Recheck Cond: (fact_ventas.anio_mes = '2025-06'::bpchar) |         Heap Blocks: exact=89 |         ->  Bitmap Index Scan on ix_fact_anio_mes  (cost=0.00..2.27 rows=118 width=0) (actual time=0.018..0.018 rows=118 loops=1) |               Index Cond: (fact_ventas.anio_mes = '2025-06'::bpchar) | Query 
```

## Plan de ejecucion SIN indice

```
Aggregate  (cost=227.23..227.24 rows=1 width=40) (actual time=0.804..0.804 rows=1 loops=1) |   Output: count(*), round(sum(total), 2) |   ->  Seq Scan on public.fact_ventas  (cost=0.00..226.64 rows=118 width=8) (actual time=0.022..0.744 rows=118 loops=1) |         Output: id_detalle, id_pedido, id_cliente, id_producto, id_categoria, id_sucursal, fecha_pedido, anio, mes, mes_nombre, trimestre, anio_mes, cliente_nombre, correo, ciudad, region, canal_registro, es_premium, fecha_alta_cliente, producto_nombre, categoria, descripcion_categoria, rango_precio, precio_lista, margen_bruto_producto, costo_estimado, utilidad_bruta, cantidad, precio_unitario, descuento, porcentaje_descuento, subtotal, total, canal_venta, estado, es_completado, total_pedido, unidades, lineas, categorias_distintas, ticket_promedio_linea, metodo, monto, estado_pago, diferencia_pago, conciliado, id_ciudad |         Filter: (fact_ventas.anio_mes = '2025-06'::bpchar) |         Rows Removed by Filter: 3773 | Query Identifier: -4921276517541071299 | Planning Time: 0.122 ms | Execution Time: 0.842 ms
```

> Nota: en PostgreSQL el tiempo comparado es el bloque `Execution Time`
> que reporta `EXPLAIN (ANALYZE, VERBOSE)` en el servidor; asi se excluye
> la latencia de red hacia el pooler, que de otro modo dominaria la
> medicion. En SQLite se exporta `EXPLAIN QUERY PLAN` (que revela si se
> uso el indice) y el tiempo se mide con `time.perf_counter` porque SQLite
> no reporta tiempos en el plan.
