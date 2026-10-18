"""Parte Cloud: integracion con PostgreSQL y MongoDB usando Pandas.

Enfoque
-------
El enunciado pide integrar el dataset limpio a "una base de datos relacional
(PostgreSQL) y una no relacional (MongoDB)" y "usar Pandas para la integracion".
Este modulo cumple las dos cosas:

1. Construye el DDL (llaves primarias, foraneas, CHECK e indices) y carga las
   7 tablas normalizadas mas la vista analitica, con ``DataFrame.to_sql``.
2. Ejecuta las consultas analiticas y los pipelines de agregacion, y exporta
   cada resultado a CSV para que sirvan de evidencia.

Modo real vs simulado
---------------------
Si no hay credenciales, el script NO se queda sin hacer nada: degrada a un
SQLite local (mismo SQL, mismo esquema) y a un almacén de documentos en
carpeta. Asi las consultas siempre se ejecutan y siempre hay resultados que
revisar; cuando se levanta un servidor, los mismos SQL corren sin cambios
porque todo va por SQLAlchemy.

    PG_HOST=... PG_USER=... PG_PASSWORD=...      -> PostgreSQL real
    MONGO_URI=mongodb+srv://...                   -> MongoDB real
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config import (
    EMPRESA,
    MONGO_ATLAS_URI,
    MONGO_DB,
    MONGO_URI,
    NOMBRE_BD_SQLITE,
    PROCESSED,
    REPORTS,
    config_pg,
)
from etl_load import (
    ESQUEMA_DIM_SUCURSALES,
    ESQUEMA_SQL,
    ORDEN_CARGA,
)
from utils import LOG, asegurar_dir, subtitulo, tabla, titulo

# --------------------------------------------------------------------------
# Rutas de la integracion
# --------------------------------------------------------------------------
INTEGRACION = PROCESSED / "integracion"
SQL_DIR = INTEGRACION / "sql"
MONGO_DIR = INTEGRACION / "mongo"
REPORTE_SQL = REPORTS / "consultas_sql"
REPORTE_MONGO = REPORTS / "consultas_mongodb"
SQLITE_PATH = INTEGRACION / NOMBRE_BD_SQLITE

# --------------------------------------------------------------------------
# Claves primarias y foraneas. El DDL se deriva de aqui + ESQUEMA_SQL.
# --------------------------------------------------------------------------
CLAVES_PRIMARIAS = {
    "categorias": "id_categoria",
    "dim_ciudades": "id_ciudad",
    "dim_sucursales": "id_sucursal",
    "clientes": "id_cliente",
    "productos": "id_producto",
    "pedidos": "id_pedido",
    "detalle_pedido": "id_detalle",
    "pagos": "id_pago",
    "fact_ventas": "id_detalle",
}

# (columna_hija, tabla_padre, columna_padre). El orden de ORDEN_CARGA garantiza
# que el padre ya existe cuando se inserta la hija.
CLAVES_FORANEAS = [
    ("clientes", "id_ciudad", "dim_ciudades", "id_ciudad"),
    ("productos", "id_categoria", "categorias", "id_categoria"),
    ("pedidos", "id_cliente", "clientes", "id_cliente"),
    ("pedidos", "id_sucursal", "dim_sucursales", "id_sucursal"),
    ("detalle_pedido", "id_pedido", "pedidos", "id_pedido"),
    ("detalle_pedido", "id_producto", "productos", "id_producto"),
    ("pagos", "id_pedido", "pedidos", "id_pedido"),
]

# FK de la fact analitica. fact_ventas NO es una tabla de hechos normalizada
# (es un desnormalizado intencional con los nombres ya pegados), pero conserva
# las llaves de cada dimension para poder declarar las mismas relaciones en el
# motor: asi el visualizador de esquema muestra el modelo estrella completo.
# (columna_fact, tabla_padre, columna_padre).
CLAVES_FORANEAS_FACT = [
    ("id_pedido", "pedidos", "id_pedido"),
    ("id_producto", "productos", "id_producto"),
    ("id_cliente", "clientes", "id_cliente"),
    ("id_categoria", "categorias", "id_categoria"),
    ("id_sucursal", "dim_sucursales", "id_sucursal"),
    ("id_ciudad", "dim_ciudades", "id_ciudad"),
]

# Indices para los patrones de consulta mas frecuentes del punto 13.
INDICES = [
    ("pedidos", ["id_cliente"]),
    ("pedidos", ["fecha_pedido"]),
    ("pedidos", ["anio_mes"]),
    ("pedidos", ["estado"]),
    ("pedidos", ["canal_venta"]),
    ("detalle_pedido", ["id_producto"]),
    ("detalle_pedido", ["id_pedido"]),
    ("pagos", ["id_pedido"]),
    ("pagos", ["conciliado"]),
    ("clientes", ["ciudad"]),
    ("clientes", ["es_premium"]),
    ("productos", ["id_categoria"]),
    ("productos", ["categoria"]),
    ("productos", ["rango_precio"]),
]

# Restricciones CHECK: reglas de negocio que el enunciado espera que la base
# rejeche, no solo Pandas.
#
# La tolerancia de 0.01 en chk_det_total NO es laxitud: subtotal y total son
# NUMERIC(14,2), pero en SQLite se guardan como REAL, y en coma flotante
# 41097.36 - 854.97 = 40242.389999999996, que es distinto de 40242.39. Una
# igualdad exacta rechazaria filas validas, asi que se compara con tolerancia
# de un centavo (el ultimo digitoSignificant del tipo NUMERIC).
CHECKS = {
    "detalle_pedido": [
        ("chk_det_cantidad", "cantidad > 0"),
        ("chk_det_descuento", "descuento >= 0 AND descuento <= subtotal"),
        ("chk_det_subtotal", "subtotal >= 0"),
        ("chk_det_total", "ABS(total - (subtotal - descuento)) <= 0.01"),
    ],
    "pagos": [
        ("chk_pago_monto", "monto >= 0"),
    ],
    "productos": [
        ("chk_prod_precio", "precio > 0"),
        ("chk_prod_margen", "margen_bruto >= 0 AND margen_bruto <= 1"),
    ],
    "clientes": [
        ("chk_cli_antiguedad", "antiguedad_dias >= 0"),
    ],
    "pedidos": [
        ("chk_ped_total", "total_pedido >= 0"),
    ],
}

# Tipo de la columna cuando se crea la tabla (PK autoincremental, etc).
COLUMNAS_AUTOMATICAS = {
    ("categorias", "id_categoria"),
    ("dim_ciudades", "id_ciudad"),
    ("dim_sucursales", "id_sucursal"),
}

TIPO_DIM_SUCURSALES = ESQUEMA_DIM_SUCURSALES

# Columnas de negocio que el dataset garantiza no nulas (verificado en
# data/reports/perfil_columnas.csv: 0 nulos). Se declaran NOT NULL para que
# la base, no solo Pandas, haga cumplir la regla.
COLUMNAS_NOT_NULL = {
    "categorias": ["nombre"],
    "dim_ciudades": ["nombre"],
    "dim_sucursales": ["nombre"],
    "clientes": ["nombre", "correo"],
    "productos": ["nombre", "precio"],
    "pedidos": ["fecha_pedido", "total_pedido"],
    "detalle_pedido": ["cantidad", "precio_unitario", "subtotal", "total"],
    "pagos": ["metodo", "monto"],
}

# Restricciones UNIQUE de llave natural. `clientes.correo` NO entra: el dataset
# tiene 36 correos repetidos (compras compartidas) y el enunciado pide UNIQUE,
# no deduplicar. Se usa la llave natural de las dimensiones, que si es unica.
UNICAS = [
    ("categorias", ["nombre"], "uq_categorias_nombre"),
    ("dim_ciudades", ["nombre"], "uq_ciudades_nombre"),
    ("dim_sucursales", ["nombre"], "uq_sucursales_nombre"),
    ("productos", ["nombre"], "uq_productos_nombre"),
]

# Tokens de booleano que se sustituyen en las consultas segun el dialecto.
# SQLite guarda BOOLEAN como 0/1 y NO acepta `= TRUE`; PostgreSQL al reves.
TOKEN_VERDADERO = "@VERDADERO@"
TOKEN_FALSO = "@FALSO@"


def _adaptar_booleanos(sql: str, dialecto: str) -> str:
    v, f = ("1", "0") if dialecto == "sqlite" else ("TRUE", "FALSE")
    return sql.replace(TOKEN_VERDADERO, v).replace(TOKEN_FALSO, f)


# ==========================================================================
# Utilidades de dialecto
# ==========================================================================
def _tipo(dialecto: str, tipo_pg: str) -> str:
    """Adapta los tipos del DDL de PostgreSQL a los de SQLite.

    SQLite es dinamicamente tipado y acepta casi cualquier declaracion de
    tipo, pero no tiene SERIAL ni BOOLEAN nativos, asi que se traducen.
    """
    if dialecto != "sqlite":
        return tipo_pg
    if tipo_pg.startswith("SERIAL") or tipo_pg.startswith("BIGSERIAL"):
        return "INTEGER"
    if tipo_pg == "BOOLEAN":
        return "INTEGER"
    return tipo_pg


def _ddl_tabla(tabla: str, dialecto: str) -> str:
    """Genera el CREATE TABLE de una tabla normalizada."""
    esquema = TIPO_DIM_SUCURSALES if tabla == "dim_sucursales" else ESQUEMA_SQL[tabla]
    pk = CLAVES_PRIMARIAS.get(tabla)

    lineas = []
    not_null = set(COLUMNAS_NOT_NULL.get(tabla, []))
    for col, tipo in esquema.items():
        partes = [f"    {col} {_tipo(dialecto, tipo)}"]
        if (tabla, col) in COLUMNAS_AUTOMATICAS:
            partes.append("PRIMARY KEY AUTOINCREMENT" if dialecto == "sqlite"
                          else "PRIMARY KEY")
        elif col == pk:
            partes.append("PRIMARY KEY")
        if col.endswith("_id") and col != "id_sucursal":
            partes.append("NOT NULL")
        elif col in not_null and col != pk:
            partes.append("NOT NULL")
        lineas.append(" ".join(partes))

    # Restricciones UNIQUE (llave natural). Se emiten como CONSTRAINT de tabla,
    # que es portable entre SQLite y PostgreSQL.
    for tabla_uq, columnas_uq, nombre_uq in UNICAS:
        if tabla_uq == tabla:
            lineas.append(f"    CONSTRAINT {nombre_uq} UNIQUE ({', '.join(columnas_uq)})")

    # CHECK como restriccion de tabla: SQLite moderno y PostgreSQL lo aceptan.
    for nombre_chk, expr in CHECKS.get(tabla, []):
        lineas.append(f"    CONSTRAINT {nombre_chk} CHECK ({expr})")

    cuerpo = ",\n".join(lineas)
    return f"CREATE TABLE {tabla} (\n{cuerpo}\n)"


def _ddl_indices() -> list[str]:
    ddls = []
    for tabla, columnas in INDICES:
        cols = ", ".join(columnas)
        # prefijo ix_ + tabla + columnas evita colisiones entre tablas
        nombre = f"ix_{tabla}_{'_'.join(columnas)}"[:60]
        ddls.append(f"CREATE INDEX {nombre} ON {tabla} ({cols})")
    return ddls


def _tipo_por_dtype(serie: pd.Series) -> str:
    """Mapea un dtype de Pandas al tipo SQL declarado."""
    if pd.api.types.is_bool_dtype(serie):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(serie):
        return "INTEGER"
    if pd.api.types.is_float_dtype(serie):
        return "NUMERIC(14,2)"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "TIMESTAMP"
    return "VARCHAR(200)"


# Anchos mayores para las columnas de texto que lo necesitan. El resto se
# resuelve con el default de _tipo_por_dtype.
ANCHOS_FACT = {
    "cliente_nombre": "VARCHAR(160)", "correo": "VARCHAR(160)",
    "producto_nombre": "VARCHAR(200)", "ciudad": "VARCHAR(80)",
    "region": "VARCHAR(50)", "canal_registro": "VARCHAR(30)",
    "categoria": "VARCHAR(80)", "descripcion_categoria": "VARCHAR(200)",
    "rango_precio": "VARCHAR(20)", "mes_nombre": "VARCHAR(15)",
    "anio_mes": "CHAR(7)", "canal_venta": "VARCHAR(30)", "estado": "VARCHAR(20)",
    "metodo": "VARCHAR(30)", "estado_pago": "VARCHAR(20)",
    "precio_lista": "NUMERIC(12,2)", "precio_unitario": "NUMERIC(12,2)",
    "margen_bruto_producto": "NUMERIC(5,4)", "costo_estimado": "NUMERIC(12,2)",
    "utilidad_bruta": "NUMERIC(12,2)", "descuento": "NUMERIC(12,2)",
    "porcentaje_descuento": "NUMERIC(5,2)", "subtotal": "NUMERIC(14,2)",
    "total": "NUMERIC(14,2)", "total_pedido": "NUMERIC(14,2)",
    "monto": "NUMERIC(14,2)", "diferencia_pago": "NUMERIC(14,2)",
    "ticket_promedio_linea": "NUMERIC(12,2)", "fecha_pedido": "DATE",
    "fecha_alta_cliente": "DATE",
}


def _esquema_fact(fact: pd.DataFrame) -> dict[str, str]:
    """Esquema de fact_ventas derivado del dataset real.

    Se deriva del DataFrame y no de una lista escrita a mano: asi el DDL no
    puede desincronizarse del CSV si anade o renombra una columna.
    """
    esquema: dict[str, str] = {}
    for col in fact.columns:
        if col == "id_detalle":
            esquema[col] = "INTEGER PRIMARY KEY"
            continue
        esquema[col] = ANCHOS_FACT.get(col) or _tipo_por_dtype(fact[col])
    return esquema


def _ddl_vista_resumen(dialecto: str) -> str:
    """Vista de negocio `v_resumen_ventas` (punto 13 + requisito de VIEW).

    Encapsula un JOIN de 5 tablas (pedidos, detalle_pedido, clientes, productos
    y categorias) en un objeto reutilizable: los reportes leen la vista en vez
    de repetir el JOIN. Es el complemento de `fact_ventas`: la fact es el
    contrato ancho para BI; la vista es la capa semantica gobernada por la base.
    """
    sql = """
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
        WHERE pe.es_completado = @VERDADERO@
        GROUP BY pe.anio_mes
    """.strip()
    return _adaptar_booleanos(sql, dialecto)


def _ddl_vista_analitica(fact: pd.DataFrame) -> str:
    """El dataset desnormalizado se materializa como tabla `fact_ventas`.

    No es una vista SQL porque sus columnas son el contrato que consume
    Business Intelligence; es el objeto que evita escribir un JOIN en cada
    grafico. El DDL se genera desde el dataset, no a mano.
    """
    esquema = _esquema_fact(fact)
    cuerpo = ",\n".join(f"    {col} {tipo}" for col, tipo in esquema.items())
    return f"CREATE TABLE fact_ventas (\n{cuerpo}\n)".strip()


# ==========================================================================
# Parte SQL
# ==========================================================================
class IntegradorSQL:
    """Carga el dataset limpio en una base relacional y consulta."""

    def __init__(self, motor: Engine, nombre: str, dialecto: str):
        self.motor = motor
        self.nombre = nombre
        self.dialecto = dialecto
        self.tablas_cargadas: dict[str, int] = {}
        self.ddl_ejecutado: list[str] = []

    # -- conexion ---------------------------------------------------------
    @classmethod
    def crear(cls) -> "IntegradorSQL":
        """Intenta PostgreSQL; si no hay servidor, cae a SQLite local."""
        if os.getenv("FORZAR_SQLITE") == "1":
            LOG.info("  FORZAR_SQLITE=1: se usa SQLite sin intentar PostgreSQL")
        elif _intentar_postgres():
            motor = _motor_postgres()
            if motor is not None:
                return motor
        asegurar_dir(SQLITE_PATH.parent)
        motor = create_engine(f"sqlite:///{SQLITE_PATH}")
        LOG.info("  Modo simulado: SQLite local en %s", SQLITE_PATH)
        return cls(motor, "sqlite", "sqlite")

    # -- DDL --------------------------------------------------------------
    def crear_esquema(self, fact: pd.DataFrame) -> None:
        LOG.info(subtitulo("DDL: esquema relacional (3FN)"))
        esquema_tablas = {t: (TIPO_DIM_SUCURSALES if t == "dim_sucursales"
                              else ESQUEMA_SQL[t]) for t in ORDEN_CARGA}
        with self.motor.begin() as conn:
            inspector = inspect(self.motor)
            existentes = set(inspector.get_table_names())
            # La vista depende de las tablas: se elimina antes que ellas.
            conn.execute(text("DROP VIEW IF EXISTS v_resumen_ventas"))
            # Drop en orden inverso a las dependencias FK
            for tabla in ["fact_ventas", "pagos", "detalle_pedido", "pedidos",
                          "productos", "clientes", "dim_sucursales",
                          "dim_ciudades", "categorias"]:
                if tabla in existentes:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tabla}"))

            # ORDEN_CARGA ya respeta las dependencias: las dimensiones primero.
            for tabla in ORDEN_CARGA:
                ddl = _ddl_tabla(tabla, self.dialecto)
                conn.execute(text(ddl))
                self.ddl_ejecutado.append(ddl)
                LOG.info("  CREATE TABLE %-16s %2d columnas", tabla,
                         len(esquema_tablas[tabla]))

            # FKs. SQLite no soporta ALTER TABLE ... ADD CONSTRAINT, asi que ahi
            # las FK se documentan en el DDL exportado pero la integridad la
            # verifica el paso `verificar()` con LEFT JOIN.
            for hija, col, padre, col_padre in CLAVES_FORANEAS:
                if self.dialecto == "sqlite":
                    continue
                nombre = f"fk_{hija}_{col}"
                ddl = (f"ALTER TABLE {hija} ADD CONSTRAINT {nombre} "
                       f"FOREIGN KEY ({col}) REFERENCES {padre}({col_padre})")
                conn.execute(text(ddl))
                self.ddl_ejecutado.append(ddl)

            ddl_fact = _ddl_vista_analitica(fact)
            conn.execute(text(ddl_fact))
            self.ddl_ejecutado.append(ddl_fact)
            LOG.info("  CREATE TABLE %-16s %2d columnas  (dataset analitico)",
                     "fact_ventas", len(_esquema_fact(fact)))

            # FK de la fact hacia sus dimensiones (solo donde SQL lo admite). Se
            # declaran despues de crear fact_ventas porque sus padres ya existen.
            cols_fact = set(_esquema_fact(fact))
            for col, padre, col_padre in CLAVES_FORANEAS_FACT:
                if self.dialecto == "sqlite" or col not in cols_fact:
                    continue
                nombre = f"fk_fact_ventas_{col}"
                ddl = (f"ALTER TABLE fact_ventas ADD CONSTRAINT {nombre} "
                       f"FOREIGN KEY ({col}) REFERENCES {padre}({col_padre})")
                conn.execute(text(ddl))
                self.ddl_ejecutado.append(ddl)

            # Vista de negocio: encapsula el JOIN de 5 tablas mas usado.
            ddl_vista = _ddl_vista_resumen(self.dialecto)
            conn.execute(text(ddl_vista))
            self.ddl_ejecutado.append(ddl_vista)
            LOG.info("  CREATE VIEW  %-16s (JOIN de 5 tablas)",
                     "v_resumen_ventas")

            for ddl in _ddl_indices() + _ddl_indices_fact():
                try:
                    conn.execute(text(ddl))
                    self.ddl_ejecutado.append(ddl)
                except SQLAlchemyError as exc:
                    LOG.warning("  indice omitido (%s): %s", ddl.split("(")[0].strip(),
                                _corto(exc))

            if self.dialecto == "sqlite":
                self.ddl_ejecutado.append(_comentario_fk_sqlite())

        (REPORTE_SQL / "01_ddl.sql").parent.mkdir(parents=True, exist_ok=True)
        (REPORTE_SQL / "01_ddl.sql").write_text(
            f"-- DDL generado por integration.py ({datetime.now():%Y-%m-%d %H:%M})\n"
            f"-- Dialecto: {self.dialecto}\n"
            f"-- Motor: {self.nombre}\n\n"
            + "\n\n".join(self.ddl_ejecutado) + "\n",
            encoding="utf-8",
        )
        LOG.info("  DDL exportado -> %s", REPORTE_SQL / "01_ddl.sql")

    # -- carga ------------------------------------------------------------
    def cargar(self, tablas: dict[str, pd.DataFrame], fact: pd.DataFrame) -> None:
        LOG.info(subtitulo(f"Carga masiva en {self.nombre}"))
        with self.motor.begin() as conn:
            for tabla in ORDEN_CARGA:
                esquema = (TIPO_DIM_SUCURSALES if tabla == "dim_sucursales"
                           else ESQUEMA_SQL[tabla])
                df = self._adaptar(tablas[tabla], esquema)
                # to_sql(if_exists=append) delega el INSERT en el driver, que es
                # la via que pide el enunciado ("usar Pandas para la integracion").
                df.to_sql(tabla, conn, if_exists="append", index=False, chunksize=1000)
                self.tablas_cargadas[tabla] = len(df)
                LOG.info("  INSERT %-16s %6d filas", tabla, len(df))

            cols_fact = list(_esquema_fact(fact))
            fact[cols_fact].to_sql("fact_ventas", conn, if_exists="append",
                                   index=False, chunksize=1000)
            self.tablas_cargadas["fact_ventas"] = len(fact)
            LOG.info("  INSERT %-16s %6d filas  (dataset analitico, %d columnas)",
                     "fact_ventas", len(fact), len(cols_fact))

    def _adaptar(self, df: pd.DataFrame, esquema: dict[str, str]) -> pd.DataFrame:
        """Recorta al esquema y castea a los tipos SQL de destino.

        Pandas escribe NaN como NULL, que es lo correcto. Los booleanos se
        fuerzan a 0/1 en SQLite porque no tiene BOOLEAN nativo.
        """
        salida = df.reindex(columns=list(esquema))
        for col, tipo in esquema.items():
            if col not in salida:
                continue
            serie = salida[col]
            if tipo.startswith("NUMERIC"):
                salida[col] = pd.to_numeric(serie, errors="coerce")
            elif tipo == "BOOLEAN":
                if self.dialecto == "sqlite":
                    salida[col] = serie.map(
                        lambda v: None if v is None or pd.isna(v) else int(bool(v))
                    )
            elif tipo == "INTEGER":
                salida[col] = pd.to_numeric(serie, errors="coerce").astype("Int64")
        return salida

    # -- verificacion -----------------------------------------------------
    def verificar(self) -> pd.DataFrame:
        """Compara conteos cargados contra el origen y busca huerfanos de FK."""
        LOG.info(subtitulo("Verificacion de integridad referencial"))
        filas = []
        with self.motor.connect() as conn:
            for tabla in list(ORDEN_CARGA) + ["fact_ventas"]:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar_one()
                esperado = self.tablas_cargadas.get(tabla, 0)
                filas.append({
                    "tabla": tabla,
                    "filas_cargadas": n,
                    "filas_esperadas": esperado,
                    "coincide": "SI" if n == esperado else "NO",
                })
        df = pd.DataFrame(filas)
        if (df.coincide == "NO").any():
            raise AssertionError(f"Conteos no coinciden:\n{df}")
        LOG.info("  Conteos: %d tablas, %d filas, todas coinciden",
                 len(df), int(df.filas_cargadas.sum()))

        huerfanos = []
        with self.motor.connect() as conn:
            for hija, col, padre, col_padre in CLAVES_FORANEAS:
                sql = (f"SELECT COUNT(*) FROM {hija} h "
                       f"LEFT JOIN {padre} p ON h.{col} = p.{col_padre} "
                       f"WHERE h.{col} IS NOT NULL AND p.{col_padre} IS NULL")
                n = conn.execute(text(sql)).scalar_one()
                LOG.info("  FK %-15s.%-13s -> %-15s  %s", hija, col, padre,
                         "OK" if n == 0 else f"{n} HUERFANOS")
                if n:
                    huerfanos.append(f"{hija}.{col}->{padre}: {n}")

        # Integridad de la fact analitica: cada linea debe encontrar su padre
        # (mismas FK que CLAVES_FORANEAS_FACT; se verifica con LEFT JOIN para que
        # la comprobacion funcione tambien en SQLite, que no declara las FK).
        cols_fact = {c["name"] for c in inspect(self.motor).get_columns("fact_ventas")}
        with self.motor.connect() as conn:
            for col, padre, col_padre in CLAVES_FORANEAS_FACT:
                if col not in cols_fact:
                    continue
                sql = (f"SELECT COUNT(*) FROM fact_ventas f "
                       f"LEFT JOIN {padre} p ON f.{col} = p.{col_padre} "
                       f"WHERE f.{col} IS NOT NULL AND p.{col_padre} IS NULL")
                n = conn.execute(text(sql)).scalar_one()
                LOG.info("  FK fact_ventas.%-13s -> %-15s  %s", col, padre,
                         "OK" if n == 0 else f"{n} HUERFANOS")
                if n:
                    huerfanos.append(f"fact_ventas.{col}->{padre}: {n}")

        if huerfanos:
            raise AssertionError("Huerfanos de FK:\n  " + "\n  ".join(huerfanos))
        return df

    # -- rendimiento ------------------------------------------------------
    def benchmark_indice(self, tabla: str, columnas: list[str], sql: str,
                         nombre: str | None = None,
                         repeticiones: int = 5) -> list[dict]:
        """Mide la consulta con y sin indice y captura el plan de ejecucion.

        En PostgreSQL se usa EXPLAIN (ANALYZE, VERBOSE), que reporta el plan
        real con tiempos; el tiempo que se compara es el `Execution Time` del
        servidor (no el reloj del cliente, que incluiria la latencia de red al
        pooler y taparia el efecto del indice). SQLite no tiene esa variante:
        se registra EXPLAIN QUERY PLAN (que muestra si uso el indice) y se
        cronometra la consulta con time.perf_counter, que es la evidencia
        disponible en ese motor.
        """
        nombre_idx = nombre or f"ix_{tabla}_{'_'.join(columnas)}"[:60]
        ddl_idx = (f"CREATE INDEX IF NOT EXISTS {nombre_idx} ON {tabla} "
                   f"({', '.join(columnas)})")

        def _tiempo_servidor(texto: str) -> float | None:
            tiempos = re.findall(r"Execution Time:\s*([0-9.]+)\s*ms", texto)
            return sum(float(t) for t in tiempos) if tiempos else None

        def medir() -> float:
            if self.dialecto != "sqlite":
                total = 0.0
                for _ in range(repeticiones):
                    with self.motor.connect() as conn:
                        filas = conn.execute(
                            text(f"EXPLAIN (ANALYZE, VERBOSE) {sql}")).fetchall()
                    texto = " ".join(" ".join(str(x) for x in f) for f in filas)
                    t = _tiempo_servidor(texto)
                    if t is not None:
                        total += t
                if total > 0:
                    return total / repeticiones
            with self.motor.connect() as conn:
                t0 = time.perf_counter()
                for _ in range(repeticiones):
                    conn.execute(text(sql)).fetchall()
                return (time.perf_counter() - t0) * 1000 / repeticiones

        def plan() -> str:
            stmt = (f"EXPLAIN (ANALYZE, VERBOSE) {sql}" if self.dialecto != "sqlite"
                    else f"EXPLAIN QUERY PLAN {sql}")
            try:
                with self.motor.connect() as conn:
                    filas = conn.execute(text(stmt)).fetchall()
                return " | ".join(
                    " ".join(str(x) for x in fila) for fila in filas
                )[:1200]
            except SQLAlchemyError as exc:
                return _corto(exc)

        with self.motor.begin() as conn:
            conn.execute(text(ddl_idx))
        t_con, plan_con = medir(), plan()

        with self.motor.begin() as conn:
            conn.execute(text(f"DROP INDEX IF EXISTS {nombre_idx}"))
        t_sin, plan_sin = medir(), plan()

        with self.motor.begin() as conn:
            conn.execute(text(ddl_idx))  # se restaura el indice

        mejora = (f"{t_sin / t_con:.2f}x mas lento sin indice" if t_sin > t_con
                  else "sin diferencia de tiempo (ver columna plan: SEARCH vs SCAN)")
        return [
            {"fase": "CON INDICE", "indice": nombre_idx,
             "ejecucion_ms": round(t_con, 3), "mejora": "", "plan": plan_con},
            {"fase": "SIN INDICE", "indice": nombre_idx,
             "ejecucion_ms": round(t_sin, 3), "mejora": mejora, "plan": plan_sin},
        ]


def _motor_postgres() -> "IntegradorSQL | None":
    """Construye el motor de PostgreSQL (local o Supabase) si responde."""
    cfg = config_pg()
    sslmode = os.getenv("PG_SSLMODE", "prefer")
    url = (f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
           f"@{cfg['host']}:{cfg['port']}/{cfg['database']}")
    connect_args = {"connect_timeout": 5}
    if sslmode and sslmode != "off":
        connect_args["sslmode"] = sslmode
    try:
        motor = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        with motor.connect() as conn:
            conn.execute(text("SELECT 1"))
        etiqueta = "Supabase" if os.getenv("SUPABASE_HOST") else "PostgreSQL"
        LOG.info("  %s conectado en %s:%s/%s (sslmode=%s)",
                 etiqueta, cfg["host"], cfg["port"], cfg["database"], sslmode)
        return IntegradorSQL(motor, etiqueta, "postgresql")
    except SQLAlchemyError as exc:
        LOG.warning("  PostgreSQL no disponible (%s)", _corto(exc))
        return None


def _ddl_indices_fact() -> list[str]:
    return [
        "CREATE INDEX ix_fact_anio_mes ON fact_ventas (anio_mes)",
        "CREATE INDEX ix_fact_categoria ON fact_ventas (categoria)",
        "CREATE INDEX ix_fact_producto ON fact_ventas (id_producto)",
        "CREATE INDEX ix_fact_cliente ON fact_ventas (id_cliente)",
        "CREATE INDEX ix_fact_estado ON fact_ventas (estado)",
        "CREATE INDEX ix_fact_canal ON fact_ventas (canal_venta)",
    ]


def _comentario_fk_sqlite() -> str:
    """Documenta en el DDL exportado las FKs que SQLite no puede aplicar."""
    lineas = ["-- Llaves foraneas (SQLite no soporta ALTER TABLE ADD CONSTRAINT;",
              "-- se verifican en tiempo de carga con LEFT JOIN, ver verificar()):"]
    for hija, col, padre, col_padre in CLAVES_FORANEAS:
        lineas.append(f"--   FOREIGN KEY ({col}) REFERENCES {padre}({col_padre})  -- {hija}")
    for col, padre, col_padre in CLAVES_FORANEAS_FACT:
        lineas.append(f"--   FOREIGN KEY ({col}) REFERENCES {padre}({col_padre})  "
                      f"-- fact_ventas")
    return "\n".join(lineas)


def _intentar_postgres() -> bool:
    return os.getenv("SIN_POSTGRES") != "1" and bool(config_pg().get("host"))


def _corto(exc: Exception) -> str:
    return str(exc).splitlines()[0][:110]


# ==========================================================================
# Consultas analiticas (punto 13 del enunciado)
# ==========================================================================
# Cada consulta tiene id, titulo, para-que-sirve y el SQL. Se ejecutan todas y
# se exportan a CSV para poder citarlas en el reporte.
CONSULTAS_SQL: list[dict] = [
    {
        "id": "Q01",
        "titulo": "Top 10 productos por facturacion",
        "pregunta": "Cuales productos mueven mas dinero?",
        "sql": """
            SELECT p.id_producto, p.nombre AS producto, p.categoria,
                   SUM(f.total) AS facturacion,
                   SUM(f.cantidad) AS unidades,
                   COUNT(DISTINCT f.id_pedido) AS pedidos,
                   ROUND(SUM(f.total) / SUM(f.cantidad), 2) AS precio_promedio
            FROM fact_ventas f
            INNER JOIN productos p ON p.id_producto = f.id_producto
            WHERE f.es_completado = @VERDADERO@
            GROUP BY p.id_producto, p.nombre, p.categoria
            ORDER BY facturacion DESC
            LIMIT 10
        """,
    },
    {
        "id": "Q02",
        "titulo": "Top 10 clientes por gasto",
        "pregunta": "Quiennes son los clientes mas valiosos?",
        "sql": """
            WITH por_pedido AS (
                SELECT DISTINCT id_pedido, id_cliente, total_pedido, fecha_pedido
                FROM fact_ventas
                WHERE es_completado = @VERDADERO@
            )
            SELECT c.id_cliente, c.nombre AS cliente, c.ciudad, c.es_premium,
                   COUNT(p.id_pedido) AS pedidos,
                   SUM(p.total_pedido) AS gasto,
                   ROUND(AVG(p.total_pedido), 2) AS ticket_promedio,
                   MAX(p.fecha_pedido) AS ultima_compra
            FROM por_pedido p
            INNER JOIN clientes c ON c.id_cliente = p.id_cliente
            GROUP BY c.id_cliente, c.nombre, c.ciudad, c.es_premium
            ORDER BY gasto DESC
            LIMIT 10
        """,
    },
    {
        "id": "Q03",
        "titulo": "Ventas mes a mes (serie temporal)",
        "pregunta": "Como evoluciona la facturacion?",
        "sql": """
            SELECT anio_mes,
                   MIN(anio) AS anio, MIN(mes) AS mes,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(cantidad) AS unidades,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY anio_mes
            ORDER BY anio_mes
        """,
    },
    {
        "id": "Q04",
        "titulo": "Facturacion por categoria",
        "pregunta": "Que mix de producto funciona?",
        "sql": """
            SELECT categoria,
                   SUM(total) AS facturacion,
                   SUM(cantidad) AS unidades,
                   COUNT(DISTINCT producto_nombre) AS productos,
                   ROUND(100.0 * SUM(total) / (SELECT SUM(total) FROM fact_ventas
                                                WHERE es_completado = @VERDADERO@), 2) AS pct_del_total,
                   ROUND(AVG(porcentaje_descuento), 2) AS descuento_promedio_pct
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY categoria
            ORDER BY facturacion DESC
        """,
    },
    {
        "id": "Q05",
        "titulo": "Ticket promedio por canal de venta",
        "pregunta": "El canal fisico o el digital convierte mejor?",
        "sql": """
            WITH por_pedido AS (
                SELECT DISTINCT id_pedido, canal_venta, total_pedido, unidades
                FROM fact_ventas
                WHERE es_completado = @VERDADERO@
            )
            SELECT canal_venta,
                   COUNT(*) AS pedidos,
                   SUM(total_pedido) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio,
                   ROUND(AVG(unidades), 2) AS unidades_promedio,
                   ROUND(SUM(total_pedido) / SUM(unidades), 2) AS precio_unitario_promedio
            FROM por_pedido
            GROUP BY canal_venta
            ORDER BY facturacion DESC
        """,
    },
    {
        "id": "Q06",
        "titulo": "Productos en catalogo que NUNCA se vendieron",
        "pregunta": "Cuanto inventario muerto hay?",
        "sql": """
            SELECT p.id_producto, p.nombre AS producto, p.categoria,
                   p.precio, p.fecha_lanzamiento
            FROM productos p
            LEFT JOIN detalle_pedido d ON d.id_producto = p.id_producto
            WHERE d.id_producto IS NULL
            ORDER BY p.precio DESC
        """,
    },
    {
        "id": "Q07",
        "titulo": "Clientes con pedidos cancelados",
        "pregunta": "Que clientes cancelan y cuanto nos cuestan?",
        "sql": """
            SELECT c.id_cliente, c.nombre AS cliente, c.ciudad,
                   COUNT(DISTINCT pe.id_pedido) AS pedidos_cancelados,
                   SUM(f.total) AS monto_perdido
            FROM fact_ventas f
            INNER JOIN clientes c   ON c.id_cliente = f.id_cliente
            INNER JOIN pedidos pe   ON pe.id_pedido = f.id_pedido
            WHERE pe.estado = 'cancelado'
            GROUP BY c.id_cliente, c.nombre, c.ciudad
            ORDER BY monto_perdido DESC
            LIMIT 25
        """,
    },
    {
        "id": "Q08",
        "titulo": "Metodos de pago mas usados y su conciliacion",
        "pregunta": "Que metodo de pago y como se concilia?",
        "sql": """
            SELECT metodo,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(monto) AS monto,
                   ROUND(100.0 * SUM(CASE WHEN conciliado = @VERDADERO@ THEN 1 ELSE 0 END)
                         / COUNT(*), 2) AS pct_conciliado,
                   ROUND(AVG(diferencia_pago), 2) AS diferencia_promedio
            FROM fact_ventas
            WHERE metodo IS NOT NULL
            GROUP BY metodo
            ORDER BY monto DESC
        """,
    },
    {
        "id": "Q09",
        "titulo": "Productos con mayor descuento promedio",
        "pregunta": "Donde nos estamos regalando margen?",
        "sql": """
            SELECT producto_nombre AS producto, categoria,
                   ROUND(AVG(porcentaje_descuento), 2) AS descuento_promedio_pct,
                   MAX(porcentaje_descuento) AS descuento_maximo_pct,
                   SUM(descuento) AS descuento_total,
                   SUM(total) AS facturacion_neta
            FROM fact_ventas
            WHERE descuento > 0
            GROUP BY producto_nombre, categoria
            ORDER BY descuento_promedio_pct DESC
            LIMIT 20
        """,
    },
    {
        "id": "Q10",
        "titulo": "Ciudades con mas facturacion",
        "pregunta": "Donde esta el dinero geografico?",
        "sql": """
            SELECT ciudad, region,
                   COUNT(DISTINCT id_cliente) AS clientes,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY ciudad, region
            ORDER BY facturacion DESC
        """,
    },
    {
        "id": "Q11",
        "titulo": "Clientes premium vs estandar",
        "pregunta": "El segmento premium vale la pena?",
        "sql": """
            WITH por_pedido AS (
                SELECT DISTINCT id_pedido, id_cliente, total_pedido, es_premium
                FROM fact_ventas
                WHERE es_completado = @VERDADERO@
            ),
            totales AS (
                SELECT es_premium,
                       COUNT(DISTINCT id_cliente) AS clientes,
                       SUM(total_pedido) AS facturacion
                FROM por_pedido
                GROUP BY es_premium
            )
            SELECT CASE WHEN es_premium = @VERDADERO@ THEN 'Premium' ELSE 'Estandar' END
                       AS segmento,
                   clientes,
                   facturacion,
                   ROUND(facturacion / clientes, 2) AS gasto_promedio_cliente,
                   ROUND(100.0 * clientes
                         / (SELECT SUM(clientes) FROM totales), 2) AS pct_clientes,
                   ROUND(100.0 * facturacion
                         / (SELECT SUM(facturacion) FROM totales), 2) AS pct_facturacion
            FROM totales
            ORDER BY facturacion DESC
        """,
    },
    {
        "id": "Q12",
        "titulo": "Concentracion de ventas (ley de Pareto)",
        "pregunta": "Cuantos productos explican la mayor parte de la venta?",
        "sql": """
            WITH ventas AS (
                SELECT producto_nombre, SUM(total) AS facturacion
                FROM fact_ventas
                WHERE es_completado = @VERDADERO@
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
            FROM resumen
        """,
    },
    {
        "id": "Q13",
        "titulo": "Productos con mejor margen real",
        "pregunta": "La rentabilidad por producto, no la del catalogo?",
        "sql": """
            SELECT producto_nombre AS producto, categoria,
                   SUM(cantidad) AS unidades,
                   SUM(subtotal) AS ingresos_brutos,
                   SUM(descuento) AS descuentos,
                   ROUND(SUM(total) * AVG(margen_bruto_producto), 2) AS utilidad_estimada,
                   ROUND(AVG(margen_bruto_producto), 4) AS margen_promedio
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY producto_nombre, categoria
            HAVING SUM(cantidad) >= 5
            ORDER BY utilidad_estimada DESC
            LIMIT 20
        """,
    },
    {
        "id": "Q14",
        "titulo": "Pedidos con pago NO conciliado",
        "pregunta": "Que pedidos tienen descuadre de dinero?",
        "sql": """
            SELECT id_pedido, id_cliente, estado, estado_pago, metodo,
                   total_pedido, monto, diferencia_pago,
                   ROUND(100.0 * ABS(diferencia_pago) / total_pedido, 2) AS pct_diferencia
            FROM fact_ventas
            WHERE conciliado = @FALSO@ AND total_pedido > 0
            ORDER BY ABS(diferencia_pago) DESC
            LIMIT 25
        """,
    },
    {
        "id": "Q15",
        "titulo": "Clientes nuevos vs recurrentes",
        "pregunta": "El negocio esta captando o solo repite?",
        "sql": """
            WITH primera AS (
                SELECT id_cliente, MIN(fecha_pedido) AS primera_compra
                FROM fact_ventas
                WHERE es_completado = @VERDADERO@
                GROUP BY id_cliente
            ),
            perfil AS (
                SELECT f.id_cliente,
                       COUNT(DISTINCT f.id_pedido) AS pedidos,
                       SUM(f.total) AS gasto
                FROM fact_ventas f
                WHERE f.es_completado = @VERDADERO@
                GROUP BY f.id_cliente
            )
            SELECT CASE WHEN pe.pedidos = 1 THEN 'Una sola compra' ELSE 'Recurrente' END AS tipo,
                   COUNT(*) AS clientes,
                   ROUND(AVG(pe.pedidos), 2) AS pedidos_promedio,
                   ROUND(SUM(pe.gasto), 2) AS facturacion,
                   ROUND(AVG(pe.gasto), 2) AS gasto_promedio
            FROM perfil pe
            GROUP BY CASE WHEN pe.pedidos = 1 THEN 'Una sola compra' ELSE 'Recurrente' END
            ORDER BY facturacion DESC
        """,
    },
    {
        "id": "Q16",
        "titulo": "Trimestre x categoria (pivot de mix)",
        "pregunta": "El mix estacional cambia por trimestre?",
        "sql": """
            SELECT anio, trimestre, categoria,
                   SUM(total) AS facturacion,
                   SUM(cantidad) AS unidades
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY anio, trimestre, categoria
            ORDER BY anio, trimestre, facturacion DESC
        """,
    },
    {
        "id": "Q17",
        "titulo": "Productos de alto valor y baja rotacion",
        "pregunta": "Que productos caros no rotan?",
        "sql": """
            SELECT producto_nombre AS producto, categoria, rango_precio,
                   precio_lista, SUM(cantidad) AS unidades,
                   ROUND(SUM(total), 2) AS facturacion,
                   COUNT(DISTINCT id_cliente) AS clientes_distintos
            FROM fact_ventas
            WHERE es_completado = @VERDADERO@
            GROUP BY producto_nombre, categoria, rango_precio, precio_lista
            HAVING SUM(cantidad) <= 2
            ORDER BY precio_lista DESC
            LIMIT 25
        """,
    },
    {
        "id": "Q18",
        "titulo": "Cobertura por sucursal y estado del pedido",
        "pregunta": "Como rinde cada sucursal?",
        "sql": """
            SELECT id_sucursal, estado,
                   COUNT(DISTINCT id_pedido) AS pedidos,
                   SUM(total) AS facturacion,
                   ROUND(AVG(total_pedido), 2) AS ticket_promedio
            FROM fact_ventas
            GROUP BY id_sucursal, estado
            ORDER BY id_sucursal, facturacion DESC
        """,
    },
    {
        "id": "Q19",
        "titulo": "Detalle 360 del pedido (JOIN de 6 tablas)",
        "pregunta": "Cual es el detalle completo de cada linea de venta?",
        "sql": """
            SELECT c.nombre AS cliente, c.ciudad, cat.nombre AS categoria,
                   pr.nombre AS producto, pe.id_pedido, pe.fecha_pedido,
                   d.cantidad, d.precio_unitario, d.descuento, d.total,
                   pg.metodo AS metodo_pago, pg.estado_pago
            FROM detalle_pedido d
            INNER JOIN pedidos pe     ON pe.id_pedido = d.id_pedido
            INNER JOIN clientes c     ON c.id_cliente = pe.id_cliente
            INNER JOIN productos pr   ON pr.id_producto = d.id_producto
            INNER JOIN categorias cat ON cat.id_categoria = pr.id_categoria
            LEFT JOIN pagos pg  ON pg.id_pedido = pe.id_pedido
            WHERE pe.es_completado = @VERDADERO@
            ORDER BY pe.fecha_pedido DESC, pe.id_pedido
            LIMIT 20
        """,
    },
    {
        "id": "Q20",
        "titulo": "Resumen mensual via vista v_resumen_ventas",
        "pregunta": "Cual es el pulso mensual sin reescribir el JOIN?",
        "sql": """
            SELECT anio_mes, mes_nombre, pedidos, clientes, productos,
                   unidades, facturacion, ticket_promedio
            FROM v_resumen_ventas
            ORDER BY anio_mes
        """,
    },
]


def _limpiar_reportes_previos(directorio: Path, patron: str) -> int:
    """Borra los resultados de una corrida anterior antes de exportar los nuevos.

    Sin esto, renombrar o eliminar una consulta deja su CSV viejo en el disco y
    el reporte termina con mas archivos que consultas: el revisor cuenta 11
    pipelines cuando hay 10, y no sabe cual es el vigente.
    """
    asegurar_dir(directorio)
    borrados = 0
    for viejo in directorio.glob(patron):
        if viejo.is_file():
            viejo.unlink()
            borrados += 1
    if borrados:
        LOG.info("  %d resultado(s) de la corrida anterior eliminado(s)", borrados)
    return borrados


def ejecutar_consultas_sql(integrador: IntegradorSQL) -> pd.DataFrame:
    """Ejecuta las consultas analiticas y exporta cada resultado."""
    LOG.info(subtitulo(f"{len(CONSULTAS_SQL)} consultas analiticas ({integrador.nombre})"))
    _limpiar_reportes_previos(REPORTE_SQL, "Q*.csv")
    resumen = []
    with integrador.motor.connect() as conn:
        for cons in CONSULTAS_SQL:
            t0 = datetime.now()
            sql = _adaptar_booleanos(cons["sql"], integrador.dialecto)
            try:
                df = pd.read_sql_query(text(sql), conn)
                estado = "OK"
                error = ""
            except SQLAlchemyError as exc:
                df = pd.DataFrame()
                estado = "ERROR"
                error = _corto(exc)
            ms = (datetime.now() - t0).total_seconds() * 1000

            destino = REPORTE_SQL / f"{cons['id']}_{_slug(cons['titulo'])}.csv"
            df.to_csv(destino, index=False, encoding="utf-8-sig")

            resumen.append({
                "id": cons["id"],
                "titulo": cons["titulo"],
                "pregunta": cons["pregunta"],
                "estado": estado,
                "filas": len(df),
                "columnas": len(df.columns),
                "ms": round(ms, 1),
                "error": error,
                "archivo": destino.name,
            })
            LOG.info("  %-4s %-46s %-5s %5d filas  %6.1f ms",
                     cons["id"], cons["titulo"], estado, len(df), ms)

    resumen_df = pd.DataFrame(resumen)
    resumen_df.to_csv(REPORTE_SQL / "00_resumen_consultas.csv", index=False,
                      encoding="utf-8-sig")

    # Documento con el SQL de cada consulta (evidencia para el reporte)
    with (REPORTE_SQL / "02_consultas.sql").open("w", encoding="utf-8") as fh:
        fh.write(f"-- Consultas analiticas {EMPRESA} ({len(CONSULTAS_SQL)})\n")
        fh.write(f"-- Ejecutadas: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.write(f"-- Dialecto: {integrador.dialecto}\n")
        fh.write("-- @VERDADERO@/@FALSO@ se sustituyen por 1/0 (SQLite) o TRUE/FALSE (PostgreSQL)\n\n")
        for cons in CONSULTAS_SQL:
            fh.write(f"-- {cons['id']}: {cons['titulo']}\n")
            fh.write(f"-- Pregunta: {cons['pregunta']}\n")
            fh.write(f"-- Resultado: {cons['id']}_{_slug(cons['titulo'])}.csv\n\n")
            fh.write(_adaptar_booleanos(cons["sql"], integrador.dialecto).strip() + ";\n\n\n")
    return resumen_df


# Consulta que se usa para demostrar el efecto del indice: filtra por mes, que
# es justo lo que cubre ix_fact_anio_mes. Con el indice el plan hace SEARCH; sin
# el, un SCAN completo de la tabla.
SQL_BENCHMARK = ("SELECT COUNT(*) AS pedidos, ROUND(SUM(total), 2) AS facturacion "
                 "FROM fact_ventas WHERE anio_mes = '2025-06'")
INDICE_BENCHMARK = "ix_fact_anio_mes"


def ejecutar_explain_analyze(integrador: IntegradorSQL) -> pd.DataFrame:
    """Evidencia de rendimiento: plan y tiempos con/sin indice (punto 15)."""
    LOG.info(subtitulo(f"EXPLAIN ANALYZE del indice {INDICE_BENCHMARK} ({integrador.nombre})"))
    filas = integrador.benchmark_indice(
        "fact_ventas", ["anio_mes"], SQL_BENCHMARK, nombre=INDICE_BENCHMARK
    )
    df = pd.DataFrame(filas)
    df.to_csv(REPORTE_SQL / "04_explain_analyze.csv", index=False, encoding="utf-8-sig")

    con = df[df.fase == "CON INDICE"].iloc[0]
    sin = df[df.fase == "SIN INDICE"].iloc[0]
    lineas = [
        f"# EXPLAIN ANALYZE: efecto del indice `{INDICE_BENCHMARK}`",
        "",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Motor: `{integrador.nombre}` (dialecto `{integrador.dialecto}`)",
        "",
        f"Consulta medida:\n\n```sql\n{SQL_BENCHMARK}\n```",
        "",
        "| Fase | Indice | Tiempo promedio (ms) |",
        "|---|---|---|",
        f"| CON INDICE | {con.indice} | {con.ejecucion_ms} |",
        f"| SIN INDICE | (eliminado) | {sin.ejecucion_ms} |",
        "",
        f"**Tiempo:** {sin.mejora}.",
        "",
        "**Plan:** con el indice el motor accede por indice (`Index Scan` en "
        "PostgreSQL, `SEARCH ... USING INDEX` en SQLite); sin el hace un "
        "recorrido completo de `fact_ventas` (`Seq Scan`/`SCAN`). Ese cambio de "
        "acceso es la evidencia de que el indice se usa.",
        "",
        "## Plan de ejecucion CON indice",
        "",
        f"```\n{con.plan}\n```",
        "",
        "## Plan de ejecucion SIN indice",
        "",
        f"```\n{sin.plan}\n```",
        "",
        "> Nota: en PostgreSQL el tiempo comparado es el bloque `Execution Time`",
        "> que reporta `EXPLAIN (ANALYZE, VERBOSE)` en el servidor; asi se excluye",
        "> la latencia de red hacia el pooler, que de otro modo dominaria la",
        "> medicion. En SQLite se exporta `EXPLAIN QUERY PLAN` (que revela si se",
        "> uso el indice) y el tiempo se mide con `time.perf_counter` porque SQLite",
        "> no reporta tiempos en el plan.",
    ]
    (REPORTE_SQL / "03_explain_analyze.md").write_text("\n".join(lineas) + "\n",
                                                       encoding="utf-8")
    LOG.info("  CON indice %8.3f ms  |  SIN indice %8.3f ms  -> %s",
             con.ejecucion_ms, sin.ejecucion_ms, sin.mejora or "sin cambio")
    return df


# ==========================================================================
# Parte NoSQL (MongoDB)
# ==========================================================================
# Indices que se crean en cada coleccion, con la razon de cada uno.
INDICES_MONGO = {
    "productos": [
        ([("id_producto", 1)], "unique", "Llave natural del documento"),
        ([("categoria", 1), ("precio", -1)], "", "Catalogo por categoria y precio"),
        ([("atributos.procesador", 1)], "sparse", "Busqueda por atributo variable"),
        ([("rango_precio", 1)], "", "Segmentacion por rango de precio"),
    ],
    "resenas": [
        ([("id_producto", 1)], "", "Resenas de un producto"),
        ([("cliente.id", 1)], "", "Resenas de un cliente (historial)"),
        ([("calificacion", -1)], "", "ORDER BY calificacion"),
        ([("fecha", -1)], "", "Resenas recientes"),
    ],
    "actividad_usuario": [
        ([("producto", 1)], "", "Visitas de un producto (correlacion con ventas)"),
        ([("usuario", 1)], "", "Recorrido de un usuario"),
        ([("es_visualizacion", 1), ("fecha", -1)], "", "Funnel de navegacion"),
        ([("categoria", 1)], "", "Navegacion por categoria"),
    ],
}


class IntegradorMongo:
    """Carga las colecciones y ejecuta pipelines de agregacion.

    Con MONGO_URI alcanzable usa MongoDB real. Sin servidor, escribe cada coleccion en
    NDJSON y ejecuta los mismos pipelines con Pandas para que los resultados
    existan siempre.
    """

    def __init__(self, documentos: dict[str, list[dict]]):
        self.documentos = documentos
        self.cliente = None
        self.db = None
        self.modo = "local"
        self.ruta: Path | None = None
        self.colecciones: dict[str, int] = {}
        self.indices_creados: list[str] = []

    # -- conexion ---------------------------------------------------------
    def conectar(self) -> str:
        uri = MONGO_ATLAS_URI or MONGO_URI
        if os.getenv("SIN_MONGO") == "1" or not uri:
            return self._modo_local()
        try:
            from pymongo import MongoClient

            cliente = MongoClient(uri, serverSelectionTimeoutMS=3000)
            cliente.admin.command("ping")
            self.cliente = cliente
            self.db = cliente[MONGO_DB]
            self.modo = "mongodb"
            destino = uri.split("@")[-1] if "@" in uri else uri
            LOG.info("  MongoDB conectado en %s (db=%s)", destino, MONGO_DB)
            return self.modo
        except Exception as exc:  # noqa: BLE001 - pymongo lanza varios tipos
            LOG.warning("  MongoDB no disponible (%s)", _corto(exc))
            return self._modo_local()

    def _modo_local(self) -> str:
        asegurar_dir(MONGO_DIR)
        if MONGO_DIR.exists():
            shutil.rmtree(MONGO_DIR)
        asegurar_dir(MONGO_DIR)
        self.ruta = MONGO_DIR
        LOG.info("  Modo simulado: colecciones NDJSON en %s", MONGO_DIR)
        return self.modo

    # -- carga ------------------------------------------------------------
    def crear_colecciones(self) -> None:
        LOG.info(subtitulo("Colecciones MongoDB"))
        if self.modo == "mongodb":
            for nombre in self.documentos:
                self.db[nombre].drop()
            for nombre, docs in self.documentos.items():
                if docs:
                    self.db[nombre].insert_many(docs)
                self.colecciones[nombre] = len(docs)
                LOG.info("  INSERT %-20s %6d documentos", nombre, len(docs))
                self._crear_indices(nombre)
        else:
            for nombre, docs in self.documentos.items():
                destino = self.ruta / f"{nombre}.ndjson"
                with destino.open("w", encoding="utf-8") as fh:
                    for doc in docs:
                        fh.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")
                self.colecciones[nombre] = len(docs)
                LOG.info("  ESCRIBE %-19s %6d documentos -> %s", nombre, len(docs),
                         destino.name)
            self._registrar_indices()

    def _crear_indices(self, coleccion: str) -> None:
        for claves, opciones, razon in INDICES_MONGO[coleccion]:
            try:
                from pymongo import ASCENDING, DESCENDING

                mapeo = {c: (ASCENDING if d == 1 else DESCENDING) for c, d in claves}
                kwargs = {"name": f"ix_{'_'.join(c for c, _ in claves)}"[:60]}
                if opciones:
                    kwargs[opciones] = True
                self.db[coleccion].create_index(list(mapeo.items()), **kwargs)
                self.indices_creados.append(
                    f"{coleccion}: {[(c, d) for c, d in claves]} {opciones or ''}  # {razon}"
                )
            except Exception as exc:  # noqa: BLE001
                LOG.warning("  indice %s.%s fallo: %s", coleccion, claves, _corto(exc))

    def _registrar_indices(self) -> None:
        for coleccion, defs in INDICES_MONGO.items():
            for claves, opciones, razon in defs:
                self.indices_creados.append(
                    f"{coleccion}: {[(c, d) for c, d in claves]} {opciones or ''}  # {razon}"
                )
        destino = MONGO_DIR / "indices.json"
        destino.write_text(
            json.dumps(
                {c: [{"claves": k, "opciones": o, "razon": r} for k, o, r in v]
                 for c, v in INDICES_MONGO.items()},
                ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOG.info("  Indices especificados -> %s (%d definidos)",
                 destino.name, len(self.indices_creados))

    # -- lectura ----------------------------------------------------------
    def leer(self, coleccion: str) -> pd.DataFrame:
        """Devuelve la coleccion como DataFrame, sea real o simulada."""
        if self.modo == "mongodb":
            docs = list(self.db[coleccion].find({}, {"_id": 0}))
            return pd.json_normalize(docs)
        ruta = self.ruta / f"{coleccion}.ndjson"
        with ruta.open(encoding="utf-8") as fh:
            docs = [json.loads(l) for l in fh if l.strip()]
        return pd.json_normalize(docs)

    # -- consultas find/countDocuments ------------------------------------
    def ejecutar_consulta(self, cons: dict) -> pd.DataFrame:
        """Ejecuta una consulta B* contra MongoDB real o su equivalente Pandas."""
        col = cons["coleccion"]
        filtro = cons.get("filtro") or {}
        if cons["tipo"] == "countDocuments":
            if self.modo == "mongodb":
                n = self.db[col].count_documents(filtro)
            else:
                n = len(_aplicar_filtro(self.leer(col), filtro))
            return pd.DataFrame([{"coleccion": col, "total": int(n)}])

        if self.modo == "mongodb":
            proyeccion = {"_id": 0}
            proyeccion.update({c: 1 for c in cons.get("proyeccion", [])})
            cursor = self.db[col].find(filtro, proyeccion)
            for campo, direccion in cons.get("sort", []):
                cursor = cursor.sort(campo, direccion)
            if cons.get("limit"):
                cursor = cursor.limit(cons["limit"])
            return pd.DataFrame(list(cursor))

        df = _aplicar_filtro(self.leer(col), filtro)
        orden = cons.get("sort") or []
        if orden and all(c in df.columns for c, _ in orden):
            df = df.sort_values([c for c, _ in orden],
                                ascending=[d == 1 for _, d in orden])
        if cons.get("limit"):
            df = df.head(cons["limit"])
        if cons.get("proyeccion"):
            cols = [c for c in cons["proyeccion"] if c in df.columns]
            df = df[cols]
        return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# Pipelines de agregacion. Cada uno tiene su equivalente en Pandas para el modo
# simulado; `validar_equivalencia` comprueba que den el mismo numero de filas.
# --------------------------------------------------------------------------
PIPELINES_MONGO: list[dict] = [
    {
        "id": "A01",
        "titulo": "Top 10 productos mas vistos",
        "pregunta": "Que productos concentran la atencion?",
        "colectivo": "actividad_usuario",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": "$producto", "visitas": {"$sum": 1},
                        "usuarios": {"$addToSet": "$usuario"},
                        "categorias": {"$first": "$categoria"}}},
            {"$addFields": {"usuarios_unicos": {"$size": "$usuarios"}}},
            {"$sort": {"visitas": -1}},
            {"$limit": 10},
            {"$project": {"_id": 0, "producto": "$_id", "visitas": 1,
                          "usuarios_unicos": 1, "categoria": "$categorias"}},
        ],
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .groupby("producto")
            .agg(visitas=("producto", "size"), usuarios_unicos=("usuario", "nunique"),
                 categoria=("categoria", "first"))
            .reset_index()
            .sort_values("visitas", ascending=False)
            .head(10)
        ),
    },
    {
        "id": "A02",
        "titulo": "Productos vistos muchas veces y NUNCA vendidos",
        "pregunta": "Cual es la inversion publicitaria que no convierte?",
        "colectivo": "actividad_usuario",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": "$producto", "visitas": {"$sum": 1},
                        "nombre": {"$first": "$nombre_producto"},
                        "categoria": {"$first": "$categoria"}}},
            {"$sort": {"visitas": -1}},
            {"$limit": 150},
        ],
        "post": "excluir_vendidos(150)",
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .groupby("producto")
            .agg(visitas=("producto", "size"), nombre=("nombre_producto", "first"),
                 categoria=("categoria", "first"))
            .reset_index()
            .sort_values("visitas", ascending=False)
            .head(150)
        ),
    },
    {
        "id": "A03",
        "titulo": "Productos vendidos pese a ser poco vistos",
        "pregunta": "Cual es la under-exposure que nos cuesta venta?",
        "colectivo": "actividad_usuario",
        "nota": "Cruce navegacion (MongoDB) contra fact_ventas (SQL): el $lookup "
                "se resuelve aqui porque las dos bases son sistemas distintos.",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": "$producto", "visitas": {"$sum": 1},
                        "nombre": {"$first": "$nombre_producto"},
                        "categoria": {"$first": "$categoria"}}},
            {"$sort": {"visitas": 1}},
            {"$limit": 150},
        ],
        "post": "cruzar_ventas",
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .groupby("producto")
            .agg(visitas=("producto", "size"), nombre=("nombre_producto", "first"),
                 categoria=("categoria", "first"))
            .reset_index()
            .sort_values("visitas")
            .head(150)
        ),
    },
    {
        "id": "A04",
        "titulo": "Distribucion de visitas por mes",
        "pregunta": "Como se mueve el trafico web?",
        "colectivo": "actividad_usuario",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": {"$substr": ["$fecha", 0, 7]}, "visitas": {"$sum": 1},
                        "usuarios": {"$addToSet": "$usuario"}}},
            {"$addFields": {"usuarios_unicos": {"$size": "$usuarios"}}},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "anio_mes": "$_id", "visitas": 1,
                          "usuarios_unicos": 1}},
        ],
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .assign(anio_mes=lambda x: x.fecha.astype(str).str.slice(0, 7))
            .groupby("anio_mes")
            .agg(visitas=("producto", "size"), usuarios_unicos=("usuario", "nunique"))
            .reset_index()
            .sort_values("anio_mes")
        ),
    },
    {
        "id": "A05",
        "titulo": "Navegacion por categoria y dispositivo",
        "pregunta": "Que dispositivo prefiere cada categoria?",
        "colectivo": "actividad_usuario",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": {"categoria": "$categoria", "dispositivo": "$dispositivo"},
                        "visitas": {"$sum": 1},
                        "duracion_promedio": {"$avg": "$duracion_seg"}}},
            {"$sort": {"visitas": -1}},
            {"$project": {"_id": 0, "categoria": "$_id.categoria",
                          "dispositivo": "$_id.dispositivo", "visitas": 1,
                          "duracion_promedio": 1}},
        ],
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .groupby(["categoria", "dispositivo"])
            .agg(visitas=("producto", "size"), duracion_promedio=("duracion_seg", "mean"))
            .reset_index()
            .sort_values("visitas", ascending=False)
        ),
    },
    {
        "id": "A06",
        "titulo": "Rating promedio y dispersion por producto",
        "pregunta": "Que tan bien recibidos estan los productos?",
        "colectivo": "resenas",
        "pipeline": [
            {"$group": {"_id": "$id_producto", "rating_promedio": {"$avg": "$calificacion"},
                        "total_resenas": {"$sum": 1},
                        "positivas": {"$sum": {"$cond": [{"$gte": ["$calificacion", 4]}, 1, 0]}},
                        "negativas": {"$sum": {"$cond": [{"$lte": ["$calificacion", 2]}, 1, 0]}},
                        "ultima_resena": {"$max": "$fecha"}}},
            {"$addFields": {"tasa_negativas": {"$round": [
                {"$multiply": [100, {"$divide": ["$negativas", "$total_resenas"]}]}, 2]}}},
            {"$sort": {"total_resenas": -1}},
            {"$limit": 25},
            {"$project": {"_id": 0, "id_producto": "$_id", "rating_promedio": 1,
                          "total_resenas": 1, "positivas": 1, "negativas": 1,
                          "tasa_negativas": 1, "ultima_resena": 1}},
        ],
        "pandas": lambda d: (
            d.groupby("id_producto")
            .agg(rating_promedio=("calificacion", "mean"),
                 total_resenas=("calificacion", "size"),
                 positivas=("calificacion", lambda s: int((s >= 4).sum())),
                 negativas=("calificacion", lambda s: int((s <= 2).sum())),
                 ultima_resena=("fecha", "max"))
            .reset_index()
            .assign(tasa_negativas=lambda x: (100 * x.negativas / x.total_resenas).round(2))
            .sort_values("total_resenas", ascending=False)
            .head(25)
        ),
    },
    {
        "id": "A07",
        "titulo": "Productos bien valorados y con muchas resenas",
        "pregunta": "El juicio positivo se sostiene entre productos?",
        "colectivo": "resenas",
        "pipeline": [
            {"$match": {"calificacion": {"$gte": 4}}},
            {"$group": {"_id": "$id_producto", "likes": {"$sum": 1},
                        "rating_promedio": {"$avg": "$calificacion"}}},
            {"$sort": {"likes": -1}},
            {"$limit": 20},
            {"$project": {"_id": 0, "id_producto": "$_id", "likes": 1,
                          "rating_promedio": 1}},
        ],
        "pandas": lambda d: (
            d[d.calificacion >= 4]
            .groupby("id_producto")
            .agg(likes=("calificacion", "size"), rating_promedio=("calificacion", "mean"))
            .reset_index()
            .sort_values("likes", ascending=False)
            .head(20)
        ),
    },
    {
        "id": "A08",
        "titulo": "Catalogo por subdocumento de atributos (consulta dinamica)",
        "pregunta": "Se puede consultar un atributo que solo existe en una familia?",
        "colectivo": "productos",
        "nota": "Este es el caso de uso que justifica MongoDB: la clave "
                "atributos.procesador NO existe en todas las categorias. En "
                "PostgreSQL habria que unir una tabla puente producto_atributo "
                "o usar JSONB. pd.json_normalize aplana el subdocumento, asi que "
                "la columna queda como 'atributos.procesador'.",
        "pipeline": [
            {"$match": {"atributos.procesador": {"$exists": True}}},
            {"$group": {"_id": "$atributos.procesador",
                        "productos": {"$sum": 1},
                        "precio_promedio": {"$avg": "$precio"},
                        "categorias": {"$addToSet": "$categoria"}}},
            {"$sort": {"productos": -1}},
        ],
        "pandas": lambda d: (
            d[d["atributos.procesador"].notna()]
            .groupby("atributos.procesador")
            .agg(productos=("id_producto", "size"), precio_promedio=("precio", "mean"),
                 categorias=("categoria", lambda s: ", ".join(sorted(set(s)))))
            .reset_index()
            .rename(columns={"atributos.procesador": "_id"})
            .sort_values("productos", ascending=False)
        ),
    },
    {
        "id": "A09",
        "titulo": "Recorrido del usuario mas activo",
        "pregunta": "Como se ve la sesion de un cliente que si navego?",
        "colectivo": "actividad_usuario",
        "nota": "El usuario se elige con $group+$sort en vez de hardcodear un id: "
                "así el pipeline funciona con cualquier dataset. El $lookup "
                "sobre la misma coleccion reconstruye el trayecto.",
        "pipeline": [
            {"$group": {"_id": "$usuario", "eventos": {"$sum": 1}}},
            {"$sort": {"eventos": -1}},
            {"$limit": 1},
            {"$lookup": {
                "from": "actividad_usuario",
                "let": {"usuario_activo": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$usuario", "$$usuario_activo"]}}},
                    {"$sort": {"fecha": 1}},
                    {"$limit": 40},
                ],
                "as": "trayecto",
            }},
            {"$unwind": "$trayecto"},
            {"$replaceRoot": {"newRoot": "$trayecto"}},
            {"$project": {"_id": 0, "fecha": 1, "evento": 1, "producto": 1,
                          "nombre_producto": 1, "duracion_seg": 1}},
        ],
        "pandas": lambda d: _trayecto_usuario_mas_activo(d),
    },
    {
        "id": "A10",
        "titulo": "Correlacion visitas vs ventas por producto",
        "pregunta": "La navegacion predice la venta (punto 23 del enunciado)?",
        "colectivo": "actividad_usuario",
        "pipeline": [
            {"$match": {"es_visualizacion": True}},
            {"$group": {"_id": "$producto", "visitas": {"$sum": 1}}},
            {"$sort": {"visitas": -1}},
        ],
        "post": "cruzar_con_fact_ventas",
        "pandas": lambda d: (
            d[d.es_visualizacion == True]
            .groupby("producto")
            .agg(visitas=("producto", "size"), nombre=("nombre_producto", "first"),
                 categoria=("categoria", "first"))
            .reset_index()
            .sort_values("visitas", ascending=False)
        ),
    },
]


# --------------------------------------------------------------------------
# Consultas MongoDB de tipo find/countDocuments (punto 14 del enunciado).
# A diferencia de los pipelines (que agregan), estas consultas ejercitan los
# operadores de filtro y los metodos basicos del driver: find().sort().limit()
# y countDocuments(). Todas tienen equivalente Pandas para el modo simulado.
# --------------------------------------------------------------------------
CONSULTAS_MONGO: list[dict] = [
    {
        "id": "B01", "titulo": "Productos premium (precio > 5000)",
        "pregunta": "Que articulos de gama alta tenemos?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"precio": {"$gt": 5000}},
        "sort": [("precio", -1)], "limit": 10,
        "proyeccion": ["id_producto", "nombre", "categoria", "precio", "rango_precio"],
    },
    {
        "id": "B02", "titulo": "Productos economicos (precio < 1000)",
        "pregunta": "Que opciones de bajo costo hay?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"precio": {"$lt": 1000}},
        "sort": [("precio", 1)], "limit": 10,
        "proyeccion": ["id_producto", "nombre", "categoria", "precio"],
    },
    {
        "id": "B03", "titulo": "Catalogo de Computadoras y Monitores",
        "pregunta": "Que hay en las categorias de mayor ticket?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"categoria": {"$in": ["Computadoras", "Monitores"]}},
        "sort": [("precio", -1)], "limit": 15,
        "proyeccion": ["id_producto", "nombre", "categoria", "precio"],
    },
    {
        "id": "B04", "titulo": "Rango Alto y menos de 30000 ($and)",
        "pregunta": "Que productos caros siguen siendo alcanzables?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"$and": [{"rango_precio": "Alto"}, {"precio": {"$lt": 30000}}]},
        "sort": [("precio", -1)], "limit": 10,
        "proyeccion": ["id_producto", "nombre", "precio", "rango_precio"],
    },
    {
        "id": "B05", "titulo": "Redes o Accesorios ($or)",
        "pregunta": "Cual es el surtido de conectividad y perifericos?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"$or": [{"categoria": "Redes"}, {"categoria": "Accesorios"}]},
        "sort": [("nombre", 1)], "limit": 20,
        "proyeccion": ["id_producto", "nombre", "categoria", "precio"],
    },
    {
        "id": "B06", "titulo": "Banda de precio 1000-5000 ($gte/$lte)",
        "pregunta": "Cual es el corazon del catalogo?",
        "coleccion": "productos", "tipo": "find",
        "filtro": {"precio": {"$gte": 1000, "$lte": 5000}},
        "sort": [("precio", 1)], "limit": 15,
        "proyeccion": ["id_producto", "nombre", "categoria", "precio"],
    },
    {
        "id": "B07", "titulo": "Resenas de 5 estrellas ($gt)",
        "pregunta": "Que opiniones sobresalientes hay?",
        "coleccion": "resenas", "tipo": "find",
        "filtro": {"calificacion": {"$gt": 4}},
        "sort": [("fecha", -1)], "limit": 20,
        "proyeccion": ["id_resena", "id_producto", "producto", "calificacion", "fecha"],
    },
    {
        "id": "B08", "titulo": "Resenas negativas ($lt)",
        "pregunta": "Que productos estan generando insatisfaccion?",
        "coleccion": "resenas", "tipo": "find",
        "filtro": {"calificacion": {"$lt": 3}},
        "sort": [("calificacion", 1)], "limit": 20,
        "proyeccion": ["id_resena", "id_producto", "producto", "calificacion", "comentario"],
    },
    {
        "id": "B09", "titulo": "Resenas 1 y 2 estrellas ($in)",
        "pregunta": "Cuales son las quejas duras?",
        "coleccion": "resenas", "tipo": "find",
        "filtro": {"calificacion": {"$in": [1, 2]}},
        "sort": [("fecha", -1)], "limit": 25,
        "proyeccion": ["id_resena", "producto", "calificacion", "comentario"],
    },
    {
        "id": "B10", "titulo": "Resenas buenas y verificadas ($and)",
        "pregunta": "Que alabanzas vienen de compras confirmadas?",
        "coleccion": "resenas", "tipo": "find",
        "filtro": {"$and": [{"calificacion": {"$gte": 4}}, {"verificada": True}]},
        "sort": [("fecha", -1)], "limit": 20,
        "proyeccion": ["id_resena", "producto", "calificacion", "verificada", "fecha"],
    },
    {
        "id": "B11", "titulo": "Resenas extremas 1 o 5 ($or)",
        "pregunta": "Que productos polarizan la opinion?",
        "coleccion": "resenas", "tipo": "find",
        "filtro": {"$or": [{"calificacion": 1}, {"calificacion": 5}]},
        "sort": [("fecha", -1)], "limit": 20,
        "proyeccion": ["id_resena", "producto", "calificacion", "es_positiva"],
    },
    {
        "id": "B12", "titulo": "Visualizaciones largas (>300s) ($and/$gt)",
        "pregunta": "Que productos retienen la atencion?",
        "coleccion": "actividad_usuario", "tipo": "find",
        "filtro": {"$and": [{"es_visualizacion": True},
                            {"duracion_seg": {"$gt": 300}}]},
        "sort": [("duracion_seg", -1)], "limit": 20,
        "proyeccion": ["usuario", "producto", "nombre_producto",
                       "duracion_seg", "fecha"],
    },
    {
        "id": "B13", "titulo": "Conteo de compras registradas (countDocuments)",
        "pregunta": "Cuantos eventos de compra hay en total?",
        "coleccion": "actividad_usuario", "tipo": "countDocuments",
        "filtro": {"evento": "producto_comprado"},
    },
    {
        "id": "B14", "titulo": "Navegacion desde equipos Apple ($in)",
        "pregunta": "Como navega el usuario de ecosistema Apple?",
        "coleccion": "actividad_usuario", "tipo": "find",
        "filtro": {"dispositivo": {"$in": ["iOS", "macOS"]}},
        "sort": [("fecha", -1)], "limit": 20,
        "proyeccion": ["usuario", "producto", "dispositivo", "duracion_seg", "fecha"],
    },
    {
        "id": "B15", "titulo": "Sesiones muy cortas o muy largas ($or)",
        "pregunta": "Donde el engagement es anomalo?",
        "coleccion": "actividad_usuario", "tipo": "find",
        "filtro": {"$or": [{"duracion_seg": {"$lt": 30}},
                           {"duracion_seg": {"$gt": 1200}}]},
        "sort": [("duracion_seg", -1)], "limit": 25,
        "proyeccion": ["usuario", "producto", "evento", "duracion_seg"],
    },
]


def _comparar(df: pd.DataFrame, campo: str, op: str, valor) -> pd.Series:
    """Evalua un operador de comparacion Mongo sobre una columna (Pandas)."""
    if campo not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[campo]
    if op == "$gt":
        return s > valor
    if op == "$gte":
        return s >= valor
    if op == "$lt":
        return s < valor
    if op == "$lte":
        return s <= valor
    if op == "$eq":
        return s == valor
    if op == "$in":
        return s.isin(valor)
    return pd.Series(False, index=df.index)


def _mascara(df: pd.DataFrame, filtro: dict | None) -> pd.Series:
    """Convierte un filtro Mongo en una mascara booleana de Pandas."""
    m = pd.Series(True, index=df.index)
    if not filtro:
        return m
    for campo, valor in filtro.items():
        if campo == "$and":
            for sub in valor:
                m &= _mascara(df, sub)
        elif campo == "$or":
            acumulado = pd.Series(False, index=df.index)
            for sub in valor:
                acumulado |= _mascara(df, sub)
            m &= acumulado
        elif isinstance(valor, dict):
            for op, v in valor.items():
                m &= _comparar(df, campo, op, v)
        else:
            m &= _comparar(df, campo, "$eq", valor)
    return m


def _aplicar_filtro(df: pd.DataFrame, filtro: dict | None) -> pd.DataFrame:
    """Aplica un filtro Mongo sobre un DataFrame.

    Soporta igualdad, los operadores $gt/$gte/$lt/$lte/$eq/$in y los
    conectores logicos $and/$or. Basta para reproducir las consultas B01-B15
    sin un servidor MongoDB (modo simulado).
    """
    return df[_mascara(df, filtro)]


def _trayecto_usuario_mas_activo(d: pd.DataFrame) -> pd.DataFrame:
    """Equivalente en Pandas del pipeline A09."""
    if d.empty:
        return pd.DataFrame()
    usuario = d["usuario"].value_counts().idxmax()
    cols = ["fecha", "evento", "producto", "nombre_producto", "duracion_seg"]
    disponibles = [c for c in cols if c in d.columns]
    return (d[d.usuario == usuario]
            .sort_values("fecha")
            .head(40)[disponibles]
            .reset_index(drop=True))


def ejecutar_pipelines(integrador: IntegradorMongo, fact: pd.DataFrame) -> pd.DataFrame:
    """Ejecuta los 10 pipelines y exporta resultados.

    Con MongoDB real corre el pipeline nativo. Sin servidor se calcula el
    equivalente con Pandas. En ambos casos se exporta el resultado.
    """
    LOG.info(subtitulo(f"{len(PIPELINES_MONGO)} pipelines de agregacion "
                       f"({integrador.modo})"))
    _limpiar_reportes_previos(REPORTE_MONGO, "A*.csv")

    vendidos = set(fact.loc[fact.es_completado == True, "id_producto"]) \
        if "es_completado" in fact else set()
    # Unidades de pedidos COMPLETADOS. Debe usar el mismo filtro que
    # `vendidos`: si `unidades` contara lineas canceladas, un producto
    # apareceria como "vendido = False" con unidades > 0, que se contradice.
    fact_completado = fact[fact.es_completado == True] if "es_completado" in fact else fact
    unidades = fact_completado.groupby("id_producto")["cantidad"].sum().to_dict() \
        if "cantidad" in fact else {}

    resumen = []
    for p in PIPELINES_MONGO:
        t0 = datetime.now()
        if integrador.modo == "mongodb":
            docs = list(integrador.db[p["colectivo"]].aggregate(p["pipeline"]))
            df = pd.json_normalize(docs) if docs else pd.DataFrame()
            origen = "mongodb"
        else:
            df = p["pandas"](integrador.leer(p["colectivo"]))
            origen = "pandas"
        estado, error = "OK", ""

        # Post-procesos: en MongoDB real estos cortes se harian con un
        # $lookup contra la fact; aqui se resuelven con el DataFrame de
        # fact_ventas que ya esta en memoria.
        if p.get("post") == "excluir_vendidos(150)" and not df.empty:
            if "producto" not in df.columns and "_id" in df.columns:
                df["producto"] = df["_id"]
            if "producto" in df.columns:
                df = df[~df["producto"].isin(vendidos)].copy()
        elif p.get("post") == "cruzar_ventas" and not df.empty:
            if "producto" not in df.columns and "_id" in df.columns:
                df["producto"] = df["_id"]
            if "producto" in df.columns:
                df["unidades"] = df["producto"].map(unidades).fillna(0).astype(int)
                df = df[df["unidades"] > 0]
                df = df.sort_values("unidades", ascending=False)
        elif p.get("post") == "cruzar_con_fact_ventas" and not df.empty:
            if "producto" not in df.columns and "_id" in df.columns:
                df["producto"] = df["_id"]
            if "producto" in df.columns:
                df["unidades"] = df["producto"].map(unidades).fillna(0).astype(int)
                df["vendido"] = df["unidades"] > 0
                df["ratio_ventas_por_visita"] = np.where(
                    df.visitas > 0, (df.unidades / df.visitas).round(3), 0.0
                )
                df = df.sort_values(["vendido", "unidades"], ascending=[False, False])

        if not df.empty and "visitas" in df.columns and "unidades" in df.columns:
            sub = df[(df.visitas > 0) & (df.unidades > 0)]
            if len(sub) > 2:
                corr = round(float(sub.visitas.corr(sub.unidades)), 4)
            else:
                corr = float("nan")
        else:
            corr = float("nan")

        df.to_csv(REPORTE_MONGO / f"{p['id']}_{_slug(p['titulo'])}.csv",
                  index=False, encoding="utf-8-sig")
        ms = (datetime.now() - t0).total_seconds() * 1000

        resumen.append({
            "id": p["id"], "titulo": p["titulo"], "pregunta": p["pregunta"],
            "colectivo": p["colectivo"], "origen": origen, "estado": estado,
            "filas": len(df), "columnas": len(df.columns), "ms": round(ms, 1),
            "correlacion_visitas_unidades": corr, "error": error,
        })
        extra = f"  corr={corr:+.3f}" if not pd.isna(corr) else ""
        LOG.info("  %-4s %-46s %-5s %5d filas %6.1f ms%s",
                 p["id"], p["titulo"], origen, len(df), ms, extra)

    resumen_df = pd.DataFrame(resumen)
    resumen_df.to_csv(REPORTE_MONGO / "00_resumen_pipelines.csv", index=False,
                      encoding="utf-8-sig")

    with (REPORTE_MONGO / "01_pipelines.js").open("w", encoding="utf-8") as fh:
        fh.write(f"// Pipelines de agregacion {EMPRESA}\n")
        fh.write(f"// Generados: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.write("// Ejecutar con mongosh / mongodump sobre la base de datos NoSQL "
                 "(ver MONGO_DB en src/config.py)\n\n")
        for p in PIPELINES_MONGO:
            fh.write(f"// {p['id']}: {p['titulo']}\n")
            fh.write(f"// Pregunta: {p['pregunta']}\n")
            if p.get("nota"):
                fh.write(f"// Nota: {p['nota']}\n")
            fh.write(f"db.{p['colectivo']}.aggregate(\n")
            fh.write(json.dumps(p["pipeline"], indent=2, ensure_ascii=False))
            fh.write("\n)\n\n")
    return resumen_df


def ejecutar_consultas_mongo(integrador: IntegradorMongo) -> pd.DataFrame:
    """Ejecuta las 15 consultas find/countDocuments (B01-B15) y exporta."""
    LOG.info(subtitulo(f"{len(CONSULTAS_MONGO)} consultas find/countDocuments "
                       f"({integrador.modo})"))
    _limpiar_reportes_previos(REPORTE_MONGO, "B*.csv")
    resumen = []
    for cons in CONSULTAS_MONGO:
        t0 = datetime.now()
        try:
            df = integrador.ejecutar_consulta(cons)
            estado, error = "OK", ""
        except Exception as exc:  # noqa: BLE001 - pymongo/pandas varios tipos
            df = pd.DataFrame()
            estado, error = "ERROR", _corto(exc)
        ms = (datetime.now() - t0).total_seconds() * 1000

        destino = REPORTE_MONGO / f"{cons['id']}_{_slug(cons['titulo'])}.csv"
        df.to_csv(destino, index=False, encoding="utf-8-sig")
        resumen.append({
            "id": cons["id"], "titulo": cons["titulo"], "pregunta": cons["pregunta"],
            "coleccion": cons["coleccion"], "operacion": cons["tipo"],
            "estado": estado, "filas": len(df), "columnas": len(df.columns),
            "ms": round(ms, 1), "error": error, "archivo": destino.name,
        })
        LOG.info("  %-4s %-48s %-5s %5d filas  %6.1f ms",
                 cons["id"], cons["titulo"], estado, len(df), ms)

    resumen_df = pd.DataFrame(resumen)
    resumen_df.to_csv(REPORTE_MONGO / "00_resumen_consultas_mongo.csv",
                      index=False, encoding="utf-8-sig")

    with (REPORTE_MONGO / "02_consultas.js").open("w", encoding="utf-8") as fh:
        fh.write(f"// Consultas find/countDocuments {EMPRESA} (B01-B15)\n")
        fh.write(f"// Generadas: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.write("// Ejecutar con mongosh sobre la base de datos NoSQL "
                 "(ver MONGO_DB en src/config.py)\n\n")
        for cons in CONSULTAS_MONGO:
            fh.write(f"// {cons['id']}: {cons['titulo']}\n")
            fh.write(f"// Pregunta: {cons['pregunta']}\n")
            filtro = json.dumps(cons.get("filtro") or {}, ensure_ascii=False)
            if cons["tipo"] == "countDocuments":
                fh.write(f"db.{cons['coleccion']}.countDocuments({filtro})\n\n")
                continue
            proy = {c: 1 for c in cons.get("proyeccion", [])}
            proy["_id"] = 0
            fh.write(f"db.{cons['coleccion']}.find({filtro}, "
                     f"{json.dumps(proy, ensure_ascii=False)})\n")
            if cons.get("sort"):
                orden = {c: d for c, d in cons["sort"]}
                fh.write(f"  .sort({json.dumps(orden, ensure_ascii=False)})\n")
            if cons.get("limit"):
                fh.write(f"  .limit({cons['limit']})\n")
            fh.write("\n")
    return resumen_df


# ==========================================================================
# Orquestacion
# ==========================================================================
def _slug(texto: str) -> str:
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t[:60]


def main() -> None:
    LOG.info(titulo("PARTE CLOUD - INTEGRACION SQL + NOSQL"))

    processed = PROCESSED
    tablas_csv = processed / "tablas"
    fact_csv = processed / "dataset_postgresql.csv"

    if not fact_csv.exists() or not tablas_csv.exists():
        raise FileNotFoundError(
            "Faltan los datasets procesados. Ejecuta antes:\n"
            "  .\\.venv\\Scripts\\python.exe src\\etl_load.py"
        )

    # ---- SQL ------------------------------------------------------------
    tablas = {nombre: pd.read_csv(tablas_csv / f"{nombre}.csv") for nombre in ORDEN_CARGA}
    fact = pd.read_csv(fact_csv)

    sql = IntegradorSQL.crear()
    LOG.info(titulo(f"Base de datos relacional: {sql.nombre}"))
    sql.crear_esquema(fact)
    sql.cargar(tablas, fact)
    verif = sql.verificar()
    print(tabla(verif))
    resumen_sql = ejecutar_consultas_sql(sql)
    resumen_explain = ejecutar_explain_analyze(sql)
    print(tabla(resumen_explain[["fase", "indice", "ejecucion_ms", "mejora"]]))

    # ---- NoSQL ----------------------------------------------------------
    documentos = json.loads(
        (processed / "dataset_mongodb.json").read_text(encoding="utf-8")
    )
    mongo = IntegradorMongo(documentos)
    mongo.conectar()
    LOG.info(titulo(f"Almacen NoSQL: {mongo.modo}"))
    mongo.crear_colecciones()
    resumen_mongo = ejecutar_pipelines(mongo, fact)
    resumen_busqueda = ejecutar_consultas_mongo(mongo)

    # ---- Reporte --------------------------------------------------------
    LOG.info(titulo("Resumen de la integracion"))
    resumen = pd.concat(
        [
            resumen_sql.assign(tipo="SQL", motor=sql.nombre),
            resumen_mongo.assign(tipo="NoSQL (aggregate)", motor=mongo.modo),
            resumen_busqueda.assign(tipo="NoSQL (find)", motor=mongo.modo),
        ],
        ignore_index=True,
    )
    cols = ["tipo", "motor", "id", "titulo", "estado", "filas", "columnas", "ms"]
    print(tabla(resumen[cols]))
    destino = REPORTS / "integracion_resumen.csv"
    resumen.to_csv(destino, index=False, encoding="utf-8-sig")
    LOG.info("  Resumen -> %s", destino)

    # ---- Diagrama ER y justificacion 3FN --------------------------------
    from er_diagram import generar_modelo

    generar_modelo(REPORTS)

    (REPORTS / "integracion_entorno.md").write_text(_texto_entorno(sql, mongo), encoding="utf-8")
    LOG.info("  Entorno -> %s", REPORTS / "integracion_entorno.md")

    fallidas = resumen[resumen.estado != "OK"]
    if len(fallidas):
        raise AssertionError(f"{len(fallidas)} consultas fallaron:\n{fallidas}")
    LOG.info("  %d consultas SQL + %d pipelines + %d consultas NoSQL sin error",
             len(resumen_sql), len(resumen_mongo), len(resumen_busqueda))


def _texto_entorno(sql: IntegradorSQL, mongo: IntegradorMongo) -> str:
    return f"""# Entorno de integracion

Generado: {datetime.now():%Y-%m-%d %H:%M:%S}

## SQL

| | |
|---|---|
| Motor usado | `{sql.nombre}` |
| DDL (tablas, vista, indices) | `data/reports/consultas_sql/01_ddl.sql` |
| Consultas analiticas | `data/reports/consultas_sql/02_consultas.sql` |
| EXPLAIN ANALYZE + indice | `data/reports/consultas_sql/03_explain_analyze.md` |
| Resultados | `data/reports/consultas_sql/Q*.csv` |

## NoSQL

| | |
|---|---|
| Motor usado | `{mongo.modo}` |
| Colecciones | {', '.join(f'{k} ({v})' for k, v in mongo.colecciones.items())} |
| Indices | {len(mongo.indices_creados)} definidos |
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
MONGO_DB={MONGO_DB}
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
"""


if __name__ == "__main__":
    main()
