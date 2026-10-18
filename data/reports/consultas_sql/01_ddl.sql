-- DDL generado por integration.py (2026-10-18 12:35)
-- Dialecto: sqlite
-- Motor: sqlite

CREATE TABLE categorias (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(80) NOT NULL,
    descripcion VARCHAR(200),
    CONSTRAINT uq_categorias_nombre UNIQUE (nombre)
)

CREATE TABLE dim_ciudades (
    id_ciudad INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(80) NOT NULL,
    region VARCHAR(50),
    CONSTRAINT uq_ciudades_nombre UNIQUE (nombre)
)

CREATE TABLE dim_sucursales (
    id_sucursal INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(120) NOT NULL,
    ciudad VARCHAR(80),
    region VARCHAR(50),
    region_origen VARCHAR(50),
    metros_cuadrados INTEGER,
    fecha_apertura DATE,
    CONSTRAINT uq_sucursales_nombre UNIQUE (nombre)
)

CREATE TABLE clientes (
    id_cliente INTEGER PRIMARY KEY,
    nombre VARCHAR(160) NOT NULL,
    correo VARCHAR(160) NOT NULL,
    telefono VARCHAR(20),
    ciudad VARCHAR(80),
    id_ciudad INTEGER,
    fecha_alta DATE,
    canal_registro VARCHAR(30),
    es_premium INTEGER,
    anio_alta INTEGER,
    mes_alta INTEGER,
    antiguedad_dias INTEGER,
    CONSTRAINT chk_cli_antiguedad CHECK (antiguedad_dias >= 0)
)

CREATE TABLE productos (
    id_producto INTEGER PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(80),
    id_categoria INTEGER,
    precio NUMERIC(12,2) NOT NULL,
    margen_bruto NUMERIC(5,4),
    costo_estimado NUMERIC(12,2),
    utilidad_bruta NUMERIC(12,2),
    rango_precio VARCHAR(20),
    id_proveedor INTEGER,
    activo INTEGER,
    fecha_lanzamiento DATE,
    CONSTRAINT uq_productos_nombre UNIQUE (nombre),
    CONSTRAINT chk_prod_precio CHECK (precio > 0),
    CONSTRAINT chk_prod_margen CHECK (margen_bruto >= 0 AND margen_bruto <= 1)
)

CREATE TABLE pedidos (
    id_pedido INTEGER PRIMARY KEY,
    id_cliente INTEGER,
    fecha_pedido DATE NOT NULL,
    anio INTEGER,
    mes INTEGER,
    mes_nombre VARCHAR(15),
    trimestre INTEGER,
    anio_mes CHAR(7),
    canal_venta VARCHAR(30),
    id_sucursal INTEGER,
    estado VARCHAR(20),
    es_completado INTEGER,
    total_pedido NUMERIC(14,2) NOT NULL,
    unidades INTEGER,
    lineas INTEGER,
    categorias_distintas INTEGER,
    ticket_promedio_linea NUMERIC(12,2),
    CONSTRAINT chk_ped_total CHECK (total_pedido >= 0)
)

CREATE TABLE detalle_pedido (
    id_detalle INTEGER PRIMARY KEY,
    id_pedido INTEGER,
    id_producto INTEGER,
    cantidad INTEGER NOT NULL,
    precio_unitario NUMERIC(12,2) NOT NULL,
    descuento NUMERIC(12,2),
    subtotal NUMERIC(14,2) NOT NULL,
    total NUMERIC(14,2) NOT NULL,
    porcentaje_descuento NUMERIC(5,2),
    CONSTRAINT chk_det_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_det_descuento CHECK (descuento >= 0 AND descuento <= subtotal),
    CONSTRAINT chk_det_subtotal CHECK (subtotal >= 0),
    CONSTRAINT chk_det_total CHECK (ABS(total - (subtotal - descuento)) <= 0.01)
)

CREATE TABLE pagos (
    id_pago INTEGER PRIMARY KEY,
    id_pedido INTEGER,
    metodo VARCHAR(30) NOT NULL,
    monto NUMERIC(14,2) NOT NULL,
    fecha_pago DATE,
    estado_pago VARCHAR(20),
    diferencia_pago NUMERIC(14,2),
    conciliado INTEGER,
    CONSTRAINT chk_pago_monto CHECK (monto >= 0)
)

CREATE TABLE fact_ventas (
    id_detalle INTEGER PRIMARY KEY,
    id_pedido INTEGER,
    id_cliente INTEGER,
    id_producto INTEGER,
    id_categoria INTEGER,
    id_sucursal INTEGER,
    fecha_pedido DATE,
    anio INTEGER,
    mes INTEGER,
    mes_nombre VARCHAR(15),
    trimestre INTEGER,
    anio_mes CHAR(7),
    cliente_nombre VARCHAR(160),
    correo VARCHAR(160),
    ciudad VARCHAR(80),
    region VARCHAR(50),
    canal_registro VARCHAR(30),
    es_premium BOOLEAN,
    fecha_alta_cliente DATE,
    producto_nombre VARCHAR(200),
    categoria VARCHAR(80),
    descripcion_categoria VARCHAR(200),
    rango_precio VARCHAR(20),
    precio_lista NUMERIC(12,2),
    margen_bruto_producto NUMERIC(5,4),
    costo_estimado NUMERIC(12,2),
    utilidad_bruta NUMERIC(12,2),
    cantidad INTEGER,
    precio_unitario NUMERIC(12,2),
    descuento NUMERIC(12,2),
    porcentaje_descuento NUMERIC(5,2),
    subtotal NUMERIC(14,2),
    total NUMERIC(14,2),
    canal_venta VARCHAR(30),
    estado VARCHAR(20),
    es_completado BOOLEAN,
    total_pedido NUMERIC(14,2),
    unidades INTEGER,
    lineas INTEGER,
    categorias_distintas INTEGER,
    ticket_promedio_linea NUMERIC(12,2),
    metodo VARCHAR(30),
    monto NUMERIC(14,2),
    estado_pago VARCHAR(20),
    diferencia_pago NUMERIC(14,2),
    conciliado BOOLEAN,
    id_ciudad INTEGER
)

CREATE VIEW v_resumen_ventas AS
        SELECT pe.anio_mes AS anio_mes,
               MIN(pe.mes_nombre) AS mes_nombre,
               COUNT(DISTINCT pe.id_pedido) AS pedidos,
               COUNT(DISTINCT pe.id_cliente) AS clientes,
               COUNT(DISTINCT d.id_producto) AS productos,
               SUM(d.cantidad) AS unidades,
               ROUND(SUM(d.total), 2) AS facturacion,
               ROUND(AVG(pe.total_pedido), 2) AS ticket_promedio
        FROM pedidos pe
        INNER JOIN detalle_pedido d ON d.id_pedido = pe.id_pedido
        INNER JOIN clientes c       ON c.id_cliente = pe.id_cliente
        INNER JOIN productos pr     ON pr.id_producto = d.id_producto
        INNER JOIN categorias cat   ON cat.id_categoria = pr.id_categoria
        WHERE pe.es_completado = 1
        GROUP BY pe.anio_mes

CREATE INDEX ix_pedidos_id_cliente ON pedidos (id_cliente)

CREATE INDEX ix_pedidos_fecha_pedido ON pedidos (fecha_pedido)

CREATE INDEX ix_pedidos_anio_mes ON pedidos (anio_mes)

CREATE INDEX ix_pedidos_estado ON pedidos (estado)

CREATE INDEX ix_pedidos_canal_venta ON pedidos (canal_venta)

CREATE INDEX ix_detalle_pedido_id_producto ON detalle_pedido (id_producto)

CREATE INDEX ix_detalle_pedido_id_pedido ON detalle_pedido (id_pedido)

CREATE INDEX ix_pagos_id_pedido ON pagos (id_pedido)

CREATE INDEX ix_pagos_conciliado ON pagos (conciliado)

CREATE INDEX ix_clientes_ciudad ON clientes (ciudad)

CREATE INDEX ix_clientes_es_premium ON clientes (es_premium)

CREATE INDEX ix_productos_id_categoria ON productos (id_categoria)

CREATE INDEX ix_productos_categoria ON productos (categoria)

CREATE INDEX ix_productos_rango_precio ON productos (rango_precio)

CREATE INDEX ix_fact_anio_mes ON fact_ventas (anio_mes)

CREATE INDEX ix_fact_categoria ON fact_ventas (categoria)

CREATE INDEX ix_fact_producto ON fact_ventas (id_producto)

CREATE INDEX ix_fact_cliente ON fact_ventas (id_cliente)

CREATE INDEX ix_fact_estado ON fact_ventas (estado)

CREATE INDEX ix_fact_canal ON fact_ventas (canal_venta)

-- Llaves foraneas (SQLite no soporta ALTER TABLE ADD CONSTRAINT;
-- se verifican en tiempo de carga con LEFT JOIN, ver verificar()):
--   FOREIGN KEY (id_ciudad) REFERENCES dim_ciudades(id_ciudad)  -- clientes
--   FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)  -- productos
--   FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)  -- pedidos
--   FOREIGN KEY (id_sucursal) REFERENCES dim_sucursales(id_sucursal)  -- pedidos
--   FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido)  -- detalle_pedido
--   FOREIGN KEY (id_producto) REFERENCES productos(id_producto)  -- detalle_pedido
--   FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido)  -- pagos
--   FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido)  -- fact_ventas
--   FOREIGN KEY (id_producto) REFERENCES productos(id_producto)  -- fact_ventas
--   FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)  -- fact_ventas
--   FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)  -- fact_ventas
--   FOREIGN KEY (id_sucursal) REFERENCES dim_sucursales(id_sucursal)  -- fact_ventas
--   FOREIGN KEY (id_ciudad) REFERENCES dim_ciudades(id_ciudad)  -- fact_ventas
