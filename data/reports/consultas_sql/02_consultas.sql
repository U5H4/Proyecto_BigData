-- Consultas analiticas NovaCommerce (18)
-- Ejecutadas: 2026-10-05 18:24:06
-- Dialecto: sqlite
-- @VERDADERO@/@FALSO@ se sustituyen por 1/0 (SQLite) o TRUE/FALSE (PostgreSQL)

-- Q01: Top 10 productos por facturacion
-- Pregunta: Cuales productos mueven mas dinero?
-- Resultado: Q01_top_10_productos_por_facturacion.csv

SELECT p.id_producto, p.nombre AS producto, p.categoria,
                   SUM(f.total) AS facturacion,
                   SUM(f.cantidad) AS unidades,
                   COUNT(DISTINCT f.id_pedido) AS pedidos,
                   ROUND(SUM(f.total) / SUM(f.cantidad), 2) AS precio_promedio
            FROM fact_ventas f
            JOIN productos p ON p.id_producto = f.id_producto
            WHERE f.es_completado = 1
            GROUP BY p.id_producto, p.nombre, p.categoria
            ORDER BY facturacion DESC
            LIMIT 10;


-- Q02: Top 10 clientes por gasto
-- Pregunta: Quiennes son los clientes mas valiosos?
-- Resultado: Q02_top_10_clientes_por_gasto.csv

WITH por_pedido AS (
                SELECT DISTINCT id_pedido, id_cliente, total_pedido, fecha_pedido
                FROM fact_ventas
                WHERE es_completado = 1
            )
            SELECT c.id_cliente, c.nombre AS cliente, c.ciudad, c.es_premium,
                   COUNT(p.id_pedido) AS pedidos,
                   SUM(p.total_pedido) AS gasto,
                   ROUND(AVG(p.total_pedido), 2) AS ticket_promedio,
                   MAX(p.fecha_pedido) AS ultima_compra
            FROM por_pedido p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            GROUP BY c.id_cliente, c.nombre, c.ciudad, c.es_premium
            ORDER BY gasto DESC
            LIMIT 10;


-- Q03: Ventas mes a mes (serie temporal)
-- Pregunta: Como evoluciona la facturacion?
-- Resultado: Q03_ventas_mes_a_mes_serie_temporal.csv

SELECT anio_mes,
                   MIN(anio) AS anio, MIN(mes) AS mes,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(cantidad) AS unidades,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY anio_mes
            ORDER BY anio_mes;


-- Q04: Facturacion por categoria
-- Pregunta: Que mix de producto funciona?
-- Resultado: Q04_facturacion_por_categoria.csv

SELECT categoria,
                   SUM(total) AS facturacion,
                   SUM(cantidad) AS unidades,
                   COUNT(DISTINCT producto_nombre) AS productos,
                   ROUND(100.0 * SUM(total) / (SELECT SUM(total) FROM fact_ventas
                                                WHERE es_completado = 1), 2) AS pct_del_total,
                   ROUND(AVG(porcentaje_descuento), 2) AS descuento_promedio_pct
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY categoria
            ORDER BY facturacion DESC;


-- Q05: Ticket promedio por canal de venta
-- Pregunta: El canal fisico o el digital convierte mejor?
-- Resultado: Q05_ticket_promedio_por_canal_de_venta.csv

WITH por_pedido AS (
                SELECT DISTINCT id_pedido, canal_venta, total_pedido, unidades
                FROM fact_ventas
                WHERE es_completado = 1
            )
            SELECT canal_venta,
                   COUNT(*) AS pedidos,
                   SUM(total_pedido) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio,
                   ROUND(AVG(unidades), 2) AS unidades_promedio,
                   ROUND(SUM(total_pedido) / SUM(unidades), 2) AS precio_unitario_promedio
            FROM por_pedido
            GROUP BY canal_venta
            ORDER BY facturacion DESC;


-- Q06: Productos en catalogo que NUNCA se vendieron
-- Pregunta: Cuanto inventario muerto hay?
-- Resultado: Q06_productos_en_catalogo_que_nunca_se_vendieron.csv

SELECT p.id_producto, p.nombre AS producto, p.categoria,
                   p.precio, p.fecha_lanzamiento
            FROM productos p
            LEFT JOIN detalle_pedido d ON d.id_producto = p.id_producto
            WHERE d.id_producto IS NULL
            ORDER BY p.precio DESC;


-- Q07: Clientes con pedidos cancelados
-- Pregunta: Que clientesCancelan y cuanto nos cuestan?
-- Resultado: Q07_clientes_con_pedidos_cancelados.csv

SELECT c.id_cliente, c.nombre AS cliente, c.ciudad,
                   COUNT(DISTINCT pe.id_pedido) AS pedidos_cancelados,
                   SUM(f.total) AS monto_perdido
            FROM fact_ventas f
            JOIN clientes c   ON c.id_cliente = f.id_cliente
            JOIN pedidos pe   ON pe.id_pedido = f.id_pedido
            WHERE pe.estado = 'cancelado'
            GROUP BY c.id_cliente, c.nombre, c.ciudad
            ORDER BY monto_perdido DESC
            LIMIT 25;


-- Q08: Metodos de pago mas usados y su conciliacion
-- Pregunta: Que metodo de pago y como se concilia?
-- Resultado: Q08_metodos_de_pago_mas_usados_y_su_conciliacion.csv

SELECT metodo,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(monto) AS monto,
                   ROUND(100.0 * SUM(CASE WHEN conciliado = 1 THEN 1 ELSE 0 END)
                         / COUNT(*), 2) AS pct_conciliado,
                   ROUND(AVG(diferencia_pago), 2) AS diferencia_promedio
            FROM fact_ventas
            WHERE metodo IS NOT NULL
            GROUP BY metodo
            ORDER BY monto DESC;


-- Q09: Productos con mayor descuento promedio
-- Pregunta: Donde nos estamos regalando margen?
-- Resultado: Q09_productos_con_mayor_descuento_promedio.csv

SELECT producto_nombre AS producto, categoria,
                   ROUND(AVG(porcentaje_descuento), 2) AS descuento_promedio_pct,
                   MAX(porcentaje_descuento) AS descuento_maximo_pct,
                   SUM(descuento) AS descuento_total,
                   SUM(total) AS facturacion_neta
            FROM fact_ventas
            WHERE descuento > 0
            GROUP BY producto_nombre, categoria
            ORDER BY descuento_promedio_pct DESC
            LIMIT 20;


-- Q10: Ciudades con mas facturacion
-- Pregunta: Donde esta el dinero geografico?
-- Resultado: Q10_ciudades_con_mas_facturacion.csv

SELECT ciudad, region,
                   COUNT(DISTINCT id_cliente) AS clientes,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY ciudad, region
            ORDER BY facturacion DESC;


-- Q11: Clientes premium vs estandar
-- Pregunta: El segmento premium vale la pena?
-- Resultado: Q11_clientes_premium_vs_estandar.csv

WITH por_pedido AS (
                SELECT DISTINCT id_pedido, id_cliente, total_pedido, es_premium
                FROM fact_ventas
                WHERE es_completado = 1
            ),
            totales AS (
                SELECT es_premium,
                       COUNT(DISTINCT id_cliente) AS clientes,
                       SUM(total_pedido) AS facturacion
                FROM por_pedido
                GROUP BY es_premium
            )
            SELECT CASE WHEN es_premium = 1 THEN 'Premium' ELSE 'Estandar' END
                       AS segmento,
                   clientes,
                   facturacion,
                   ROUND(facturacion / clientes, 2) AS gasto_promedio_cliente,
                   ROUND(100.0 * clientes
                         / (SELECT SUM(clientes) FROM totales), 2) AS pct_clientes,
                   ROUND(100.0 * facturacion
                         / (SELECT SUM(facturacion) FROM totales), 2) AS pct_facturacion
            FROM totales
            ORDER BY facturacion DESC;


-- Q12: Concentracion de ventas (ley de Pareto)
-- Pregunta: Cuantos productos explican la mayor parte de la venta?
-- Resultado: Q12_concentracion_de_ventas_ley_de_pareto.csv

WITH ventas AS (
                SELECT producto_nombre, SUM(total) AS facturacion
                FROM fact_ventas
                WHERE es_completado = 1
                GROUP BY producto_nombre
            ),
            acumulado AS (
                SELECT producto_nombre, facturacion,
                       SUM(facturacion) OVER (ORDER BY facturacion DESC) AS acum,
                       SUM(facturacion) OVER () AS total,
                       ROW_NUMBER() OVER (ORDER BY facturacion DESC) AS posicion
                FROM ventas
            ),
            -- posicion del primer producto que hace cuadrar el 80% del total
            corte AS (
                SELECT MIN(posicion) AS n FROM acumulado WHERE acum >= total * 0.8
            ),
            resumen AS (
                SELECT (SELECT COUNT(*) FROM ventas) AS productos,
                       (SELECT total FROM acumulado LIMIT 1) AS total,
                       -- facturacion ACUMULADA del prefijo que cruza el 80%,
                       -- no la del ultimo producto suelto
                       (SELECT acum FROM acumulado
                        WHERE posicion = (SELECT n FROM corte)) AS parcial
            )
            SELECT productos,
                   ROUND(100.0 * parcial / total, 2) AS pct_ventas_en_primer_80,
                   ROUND(100.0 * (SELECT n FROM corte) / productos, 2)
                       AS pct_productos_para_80
            FROM resumen;


-- Q13: Productos con mejor margen real
-- Pregunta: La rentabilidad por producto, no la del catalogo?
-- Resultado: Q13_productos_con_mejor_margen_real.csv

SELECT producto_nombre AS producto, categoria,
                   SUM(cantidad) AS unidades,
                   SUM(subtotal) AS ingresos_brutos,
                   SUM(descuento) AS descuentos,
                   ROUND(SUM(total) * AVG(margen_bruto_producto), 2) AS utilidad_estimada,
                   ROUND(AVG(margen_bruto_producto), 4) AS margen_promedio
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY producto_nombre, categoria
            HAVING SUM(cantidad) >= 5
            ORDER BY utilidad_estimada DESC
            LIMIT 20;


-- Q14: Pedidos con pago NO conciliado
-- Pregunta: Que pedidos tienen descuadre de dinero?
-- Resultado: Q14_pedidos_con_pago_no_conciliado.csv

SELECT id_pedido, id_cliente, estado, estado_pago, metodo,
                   total_pedido, monto, diferencia_pago,
                   ROUND(100.0 * ABS(diferencia_pago) / total_pedido, 2) AS pct_diferencia
            FROM fact_ventas
            WHERE conciliado = 0 AND total_pedido > 0
            ORDER BY ABS(diferencia_pago) DESC
            LIMIT 25;


-- Q15: Clientes nuevos vs recurrentes
-- Pregunta: El negocio esta captando o solo repite?
-- Resultado: Q15_clientes_nuevos_vs_recurrentes.csv

WITH primera AS (
                SELECT id_cliente, MIN(fecha_pedido) AS primera_compra
                FROM fact_ventas
                WHERE es_completado = 1
                GROUP BY id_cliente
            ),
            perfil AS (
                SELECT f.id_cliente,
                       COUNT(DISTINCT f.id_pedido) AS pedidos,
                       SUM(f.total) AS gasto
                FROM fact_ventas f
                WHERE f.es_completado = 1
                GROUP BY f.id_cliente
            )
            SELECT CASE WHEN pe.pedidos = 1 THEN 'Una sola compra' ELSE 'Recurrente' END AS tipo,
                   COUNT(*) AS clientes,
                   ROUND(AVG(pe.pedidos), 2) AS pedidos_promedio,
                   ROUND(SUM(pe.gasto), 2) AS facturacion,
                   ROUND(AVG(pe.gasto), 2) AS gasto_promedio
            FROM perfil pe
            GROUP BY CASE WHEN pe.pedidos = 1 THEN 'Una sola compra' ELSE 'Recurrente' END
            ORDER BY facturacion DESC;


-- Q16: Trimestre x categoria (pivot de mix)
-- Pregunta: El mix estacional cambia por trimestre?
-- Resultado: Q16_trimestre_x_categoria_pivot_de_mix.csv

SELECT anio, trimestre, categoria,
                   SUM(total) AS facturacion,
                   SUM(cantidad) AS unidades
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY anio, trimestre, categoria
            ORDER BY anio, trimestre, facturacion DESC;


-- Q17: Productos de alto valor y baja rotacion
-- Pregunta: Que productos caros no rotan?
-- Resultado: Q17_productos_de_alto_valor_y_baja_rotacion.csv

SELECT producto_nombre AS producto, categoria, rango_precio,
                   precio_lista, SUM(cantidad) AS unidades,
                   ROUND(SUM(total), 2) AS facturacion,
                   COUNT(DISTINCT id_cliente) AS clientes_distintos
            FROM fact_ventas
            WHERE es_completado = 1
            GROUP BY producto_nombre, categoria, rango_precio, precio_lista
            HAVING SUM(cantidad) <= 2
            ORDER BY precio_lista DESC
            LIMIT 25;


-- Q18: Cobertura por sucursal y estado del pedido
-- Pregunta: Como rinde cada sucursal?
-- Resultado: Q18_cobertura_por_sucursal_y_estado_del_pedido.csv

SELECT id_sucursal, estado,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            GROUP BY id_sucursal, estado
            ORDER BY id_sucursal, facturacion DESC;


