# EXPLAIN ANALYZE: efecto del indice `ix_fact_anio_mes`

Generado: 2026-10-11 15:23:31
Motor: `Supabase` (dialecto `postgresql`)

Consulta medida:

```sql
SELECT COUNT(*) AS pedidos, ROUND(SUM(total), 2) AS facturacion FROM fact_ventas WHERE anio_mes = '2025-06'
```

| Fase | Indice | Tiempo promedio (ms) |
|---|---|---|
| CON INDICE | ix_fact_anio_mes | 0.254 |
| SIN INDICE | (eliminado) | 0.937 |

**Tiempo:** 3.70x mas lento sin indice.

**Plan:** con el indice el motor accede por indice (`Index Scan` en PostgreSQL, `SEARCH ... USING INDEX` en SQLite); sin el hace un recorrido completo de `fact_ventas` (`Seq Scan`/`SCAN`). Ese cambio de acceso es la evidencia de que el indice se usa.

## Plan de ejecucion CON indice

```
Aggregate  (cost=3.62..3.63 rows=1 width=40) (actual time=0.162..0.162 rows=1 loops=1) |   Output: count(*), round(sum(total), 2) |   ->  Index Scan using ix_fact_anio_mes on public.fact_ventas  (cost=0.27..3.61 rows=2 width=18) (actual time=0.017..0.110 rows=118 loops=1) |         Output: id_detalle, id_pedido, id_cliente, id_producto, id_categoria, id_sucursal, fecha_pedido, anio, mes, mes_nombre, trimestre, anio_mes, cliente_nombre, correo, ciudad, region, canal_registro, es_premium, fecha_alta_cliente, producto_nombre, categoria, descripcion_categoria, rango_precio, precio_lista, margen_bruto_producto, costo_estimado, utilidad_bruta, cantidad, precio_unitario, descuento, porcentaje_descuento, subtotal, total, canal_venta, estado, es_completado, total_pedido, unidades, lineas, categorias_distintas, ticket_promedio_linea, metodo, monto, estado_pago, diferencia_pago, conciliado, id_ciudad |         Index Cond: (fact_ventas.anio_mes = '2025-06'::bpchar) | Query Identifier: -172896884754862432 | Planning Time: 0.112 ms | Execution Time: 0.199 ms
```

## Plan de ejecucion SIN indice

```
Aggregate  (cost=182.46..182.47 rows=1 width=40) (actual time=0.892..0.893 rows=1 loops=1) |   Output: count(*), round(sum(total), 2) |   ->  Seq Scan on public.fact_ventas  (cost=0.00..182.45 rows=2 width=18) (actual time=0.023..0.830 rows=118 loops=1) |         Output: id_detalle, id_pedido, id_cliente, id_producto, id_categoria, id_sucursal, fecha_pedido, anio, mes, mes_nombre, trimestre, anio_mes, cliente_nombre, correo, ciudad, region, canal_registro, es_premium, fecha_alta_cliente, producto_nombre, categoria, descripcion_categoria, rango_precio, precio_lista, margen_bruto_producto, costo_estimado, utilidad_bruta, cantidad, precio_unitario, descuento, porcentaje_descuento, subtotal, total, canal_venta, estado, es_completado, total_pedido, unidades, lineas, categorias_distintas, ticket_promedio_linea, metodo, monto, estado_pago, diferencia_pago, conciliado, id_ciudad |         Filter: (fact_ventas.anio_mes = '2025-06'::bpchar) |         Rows Removed by Filter: 3773 | Query Identifier: -172896884754862432 | Planning Time: 0.096 ms | Execution Time: 0.932 ms
```

> Nota: en PostgreSQL el tiempo comparado es el bloque `Execution Time`
> que reporta `EXPLAIN (ANALYZE, VERBOSE)` en el servidor; asi se excluye
> la latencia de red hacia el pooler, que de otro modo dominaria la
> medicion. En SQLite se exporta `EXPLAIN QUERY PLAN` (que revela si se
> uso el indice) y el tiempo se mide con `time.perf_counter` porque SQLite
> no reporta tiempos en el plan.
