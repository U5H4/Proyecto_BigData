"""Tests de la Parte Cloud: DDL, carga, integridad y consultas.

Estos tests NO requieren PostgreSQL ni MongoDB: usan SQLite en un archivo
temporal, que es exactamente el mismo camino de codigo que el modo simulado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import integration as I  # noqa: E402
from etl_load import ESQUEMA_SQL, ORDEN_CARGA  # noqa: E402


# ==========================================================================
# Fixtures: un dataset pequeno pero con las mismas claves que el real
# ==========================================================================
@pytest.fixture(scope="module")
def fact() -> pd.DataFrame:
    """Dataset analitico minimo con las columnas que usan las consultas.

    Se repite el producto 1 en varias lineas para que Q13 (que exige
    HAVING SUM(cantidad) >= 5) tenga un producto que lo cumpla.
    """
    base = {
        "id_detalle": [1, 2, 3, 4, 5],
        "id_pedido": [1, 1, 2, 3, 3],
        "id_cliente": [1, 1, 2, 3, 3],
        "id_producto": [1, 2, 1, 3, 4],
        "id_categoria": [1, 2, 1, 1, 3],
        "id_sucursal": [1, 1, 2, 1, 3],
        "id_ciudad": [1, 1, 2, 3, 3],
        "fecha_pedido": ["2025-01-05", "2025-01-05", "2025-02-10",
                         "2025-03-15", "2025-03-15"],
        "anio": [2025] * 5,
        "mes": [1, 1, 2, 3, 3],
        "mes_nombre": ["Enero", "Enero", "Febrero", "Marzo", "Marzo"],
        "trimestre": [1] * 5,
        "anio_mes": ["2025-01", "2025-01", "2025-02", "2025-03", "2025-03"],
        "cliente_nombre": ["Ana", "Ana", "Luis", "Marta", "Marta"],
        "correo": ["a@x.com", "a@x.com", "l@x.com", "m@x.com", "m@x.com"],
        "ciudad": ["Veracruz", "Veracruz", "Ciudad de Mexico", "Puebla", "Puebla"],
        "region": ["Sureste", "Sureste", "Centro", "Centro", "Centro"],
        "canal_registro": ["Web", "Web", "Movil", "Web", "Web"],
        "es_premium": [True, True, False, False, False],
        "producto_nombre": ["Laptop A", "Mouse B", "Laptop A", "Monitor C", "Router D"],
        "categoria": ["Computadoras", "Accesorios", "Computadoras",
                      "Monitores", "Redes"],
        "descripcion_categoria": ["Eq", "Per", "Eq", "Vid", "Net"],
        "rango_precio": ["Alto", "Economico", "Alto", "Medio", "Economico"],
        "precio_lista": [25000.0, 350.0, 25000.0, 8000.0, 1200.0],
        "margen_bruto_producto": [0.3, 0.4, 0.3, 0.25, 0.35],
        "costo_estimado": [17500.0, 210.0, 17500.0, 6000.0, 780.0],
        "utilidad_bruta": [7500.0, 140.0, 7500.0, 2000.0, 420.0],
        "cantidad": [2, 2, 3, 3, 1],
        "precio_unitario": [25000.0, 350.0, 25000.0, 8000.0, 1200.0],
        "descuento": [0.0, 50.0, 0.0, 2400.0, 0.0],
        "porcentaje_descuento": [0.0, 7.14, 0.0, 10.0, 0.0],
        "subtotal": [50000.0, 700.0, 75000.0, 24000.0, 1200.0],
        "total": [50000.0, 650.0, 75000.0, 21600.0, 1200.0],
        "canal_venta": ["web", "web", "app_movil", "web", "tienda_fisica"],
        "estado": ["completado", "completado", "completado",
                   "cancelado", "completado"],
        "es_completado": [True, True, True, False, True],
        "total_pedido": [50650.0, 50650.0, 75000.0, 21600.0, 1200.0],
        "unidades": [4, 4, 3, 3, 1],
        "lineas": [2, 2, 1, 1, 1],
        "categorias_distintas": [2, 2, 1, 1, 1],
        "ticket_promedio_linea": [25325.0, 25325.0, 50000.0, 21600.0, 1200.0],
        "metodo": ["oxxo", "oxxo", "mpago", "efectivo", "tarjeta_credito"],
        "monto": [50650.0, 50650.0, 50000.0, 21000.0, 1200.0],
        "estado_pago": ["aprobado", "aprobado", "aprobado", "rechazado", "aprobado"],
        "diferencia_pago": [0.0, 0.0, 0.0, -600.0, 0.0],
        "conciliado": [True, True, True, False, True],
    }
    return pd.DataFrame(base)


@pytest.fixture()
def motor(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture()
def integ(motor, tmp_path):
    return I.IntegradorSQL(motor, "sqlite", "sqlite", tmp_path / "reportes")


# ==========================================================================
# DDL
# ==========================================================================
def test_crea_todas_las_tablas_del_esquema(integ, fact):
    integ.crear_esquema(fact)
    tablas = set(inspect(integ.motor).get_table_names())
    for t in ORDEN_CARGA:
        assert t in tablas, f"falta la tabla {t}"
    assert "fact_ventas" in tablas


def test_ddl_lleva_pk_en_todas_las_tablas(integ, fact):
    integ.crear_esquema(fact)
    insp = inspect(integ.motor)
    for tabla, pk in I.CLAVES_PRIMARIAS.items():
        got = insp.get_pk_constraint(tabla)["constrained_columns"]
        assert got == [pk], f"{tabla}: PK {got} != [{pk}]"
    assert insp.get_pk_constraint("fact_ventas")["constrained_columns"] == ["id_detalle"]


def test_ddl_no_crea_columnas_inexistentes(integ, fact):
    """El DDL de fact_ventas se deriva del dataset, no de una lista a mano."""
    integ.crear_esquema(fact)
    cols = {c["name"] for c in inspect(integ.motor).get_columns("fact_ventas")}
    assert cols == set(fact.columns)


def test_esquema_fact_respeta_tipos_declarados(fact):
    esquema = I._esquema_fact(fact)
    assert esquema["id_detalle"] == "INTEGER PRIMARY KEY"
    assert esquema["es_completado"] == "BOOLEAN"
    assert esquema["total"] == "NUMERIC(14,2)"
    assert esquema["margen_bruto_producto"] == "NUMERIC(5,4)"
    assert esquema["fecha_pedido"] == "DATE"
    # columna no declarada: se infiere del dtype
    assert esquema["anio"] == "INTEGER"
    assert esquema["categoria"] == "VARCHAR(80)"


def test_check_de_total_tolera_error_de_coma_flotante(integ, fact):
    """Regresion: 41097.36 - 854.97 = 40242.389999999996 en IEEE-754.

    Un CHECK con igualdad exacta rechazaria filas validas.
    """
    integ.crear_esquema(fact)
    with integ.motor.begin() as conn:
        det = pd.DataFrame([{
            "id_detalle": 99, "id_pedido": 1, "id_producto": 1, "cantidad": 1,
            "precio_unitario": 41097.36, "descuento": 854.97,
            "subtotal": 41097.36, "total": 40242.39, "porcentaje_descuento": 2.08,
        }])
        det.to_sql("detalle_pedido", conn, if_exists="append", index=False)
        n = conn.execute(text("SELECT COUNT(*) FROM detalle_pedido")).scalar_one()
    assert n == 1


def test_check_rechaza_total_incoherente(integ, fact):
    """El CHECK debe atrapar un total que no cuadra con subtotal - descuento."""
    integ.crear_esquema(fact)
    with pytest.raises(IntegrityError):
        with integ.motor.begin() as conn:
            conn.execute(text(
                "INSERT INTO detalle_pedido (id_detalle, id_pedido, id_producto, "
                "cantidad, precio_unitario, descuento, subtotal, total) "
                "VALUES (99, 1, 1, 1, 100.0, 10.0, 100.0, 999.0)"
            ))


def test_booleanos_se_adaptan_al_dialecto():
    sql = "WHERE es_completado = @VERDADERO@ AND conciliado = @FALSO@"
    assert I._adaptar_booleanos(sql, "sqlite") == "WHERE es_completado = 1 AND conciliado = 0"
    assert I._adaptar_booleanos(sql, "postgresql") == (
        "WHERE es_completado = TRUE AND conciliado = FALSE"
    )


def test_ninguna_consulta_usa_booleano_literal():
    """Las consultas no pueden traer `= 1` sobre columnas BOOLEAN.

    En SQLite 0/1 funciona, pero en PostgreSQL `es_completado = 1` es un error
    de tipo. Por eso el SQL fuente usa los tokens @VERDADERO@/@FALSO@ y el
    literal se decide segun el dialecto en tiempo de ejecucion.
    """
    import re

    for cons in I.CONSULTAS_SQL:
        for izq in re.findall(r"(\w+)\s*=\s*[01]\b", cons["sql"]):
            assert izq not in {"es_completado", "conciliado", "es_premium"}, (
                f"{cons['id']}: {izq} = literal sobre una columna BOOLEAN; "
                "usa @VERDADERO@ / @FALSO@"
            )
        assert "@VERDADERO@" in cons["sql"] or "@FALSO@" in cons["sql"] \
            or not re.search(r"\b(es_completado|conciliado|es_premium)\b", cons["sql"]), (
            f"{cons['id']} filtra por un booleano pero no usa los tokens"
        )


# ==========================================================================
# Carga e integridad
# ==========================================================================
def _tablas_pequenas() -> dict[str, pd.DataFrame]:
    return {
        "categorias": pd.DataFrame(
            {"id_categoria": [1, 2, 3], "nombre": ["Computadoras", "Accesorios", "Redes"],
             "descripcion": ["Eq", "Per", "Net"]}),
        "dim_ciudades": pd.DataFrame(
            {"id_ciudad": [1, 2, 3], "nombre": ["Veracruz", "Ciudad de Mexico", "Puebla"],
             "region": ["Sureste", "Centro", "Centro"]}),
        "dim_sucursales": pd.DataFrame(
            {"id_sucursal": [1, 2, 3], "nombre": ["S1", "S2", "S3"],
             "ciudad": ["Veracruz", "Ciudad de Mexico", "Puebla"],
             "region": ["Sureste", "Centro", "Centro"], "region_origen": ["Norte", "Norte", "Centro"],
             "metros_cuadrados": [300, 400, 500], "fecha_apertura": ["2020-01-01"] * 3}),
        "clientes": pd.DataFrame(
            {"id_cliente": [1, 2, 3], "nombre": ["Ana", "Luis", "Marta"],
             "correo": ["a@x.com", "l@x.com", "m@x.com"], "telefono": ["1", "2", "3"],
             "ciudad": ["Veracruz", "Ciudad de Mexico", "Puebla"],
             "fecha_alta": ["2023-01-01", "2023-02-01", "2023-03-01"],
             "canal_registro": ["Web", "Movil", "Web"], "es_premium": [True, False, False],
             "anio_alta": [2023, 2023, 2023], "mes_alta": [1, 2, 3],
             "antiguedad_dias": [700, 600, 500]}),
        "productos": pd.DataFrame(
            # El producto 5 existe en el catalogo pero no aparece en ningun
            # detalle_pedido: es el caso "inventario muerto" de Q06.
            {"id_producto": [1, 2, 3, 4, 5],
             "nombre": ["Laptop A", "Mouse B", "Monitor C", "Router D", "Teclado E"],
             "categoria": ["Computadoras", "Accesorios", "Monitores", "Redes", "Accesorios"],
             "id_categoria": [1, 2, 1, 3, 2],
             "precio": [25000.0, 350.0, 8000.0, 1200.0, 900.0],
             "margen_bruto": [0.3, 0.4, 0.25, 0.35, 0.45],
             "costo_estimado": [17500.0, 210.0, 6000.0, 780.0, 495.0],
             "utilidad_bruta": [7500.0, 140.0, 2000.0, 420.0, 405.0],
             "rango_precio": ["Alto", "Economico", "Medio", "Economico", "Economico"],
             "id_proveedor": [1, 1, 2, 3, 1], "activo": [True] * 5,
             "fecha_lanzamiento": ["2024-01-01"] * 5}),
        "pedidos": pd.DataFrame(
            {"id_pedido": [1, 2, 3], "id_cliente": [1, 2, 3],
             "fecha_pedido": ["2025-01-05", "2025-02-10", "2025-03-15"],
             "anio": [2025] * 3, "mes": [1, 2, 3],
             "mes_nombre": ["Enero", "Febrero", "Marzo"], "trimestre": [1] * 3,
             "anio_mes": ["2025-01", "2025-02", "2025-03"],
             "canal_venta": ["web", "app_movil", "web"],
             "id_sucursal": [1, 2, 1], "estado": ["completado", "completado", "cancelado"],
             "es_completado": [True, True, False], "total_pedido": [25650.0, 25000.0, 21600.0],
             "unidades": [3, 1, 3], "lineas": [2, 1, 1], "categorias_distintas": [2, 1, 1],
             "ticket_promedio_linea": [12825.0, 25000.0, 21600.0]}),
        "detalle_pedido": pd.DataFrame(
            {"id_detalle": [1, 2, 3, 4, 5], "id_pedido": [1, 1, 2, 3, 3],
             "id_producto": [1, 2, 1, 3, 4], "cantidad": [1, 2, 1, 3, 1],
             "precio_unitario": [25000.0, 350.0, 25000.0, 8000.0, 1200.0],
             "descuento": [0.0, 50.0, 0.0, 2400.0, 0.0],
             "subtotal": [25000.0, 700.0, 25000.0, 24000.0, 1200.0],
             "total": [25000.0, 650.0, 25000.0, 21600.0, 1200.0],
             "porcentaje_descuento": [0.0, 7.14, 0.0, 10.0, 0.0]}),
        "pagos": pd.DataFrame(
            {"id_pago": [1, 2, 3], "id_pedido": [1, 2, 3],
             "metodo": ["oxxo", "mpago", "efectivo"],
             "monto": [25650.0, 25000.0, 21000.0],
             "fecha_pago": ["2025-01-06", "2025-02-11", "2025-03-16"],
             "estado_pago": ["aprobado", "aprobado", "rechazado"],
             "diferencia_pago": [0.0, 0.0, -600.0],
             "conciliado": [True, True, False]}),
    }


def test_carga_y_verificacion_pasan(integ, fact):
    tablas = _tablas_pequenas()
    integ.crear_esquema(fact)
    integ.cargar(tablas, fact)
    verif = integ.verificar()
    assert (verif.coincide == "SI").all()
    esperado = sum(len(df) for df in tablas.values()) + len(fact)
    assert int(verif.filas_cargadas.sum()) == esperado
    assert set(verif.tabla) == set(ORDEN_CARGA) | {"fact_ventas"}


def test_detecta_huerfano_de_fk(integ, fact):
    """Si una FK queda rota, verificar() debe EXPLOTAR, no pasar."""
    tablas = _tablas_pequenas()
    integ.crear_esquema(fact)
    integ.cargar(tablas, fact)
    with integ.motor.begin() as conn:
        conn.execute(text("UPDATE detalle_pedido SET id_producto = 999"))
    with pytest.raises(AssertionError, match="Huerfanos"):
        integ.verificar()


def test_detecta_conteo_descuadrado(integ, fact):
    tablas = _tablas_pequenas()
    integ.crear_esquema(fact)
    integ.cargar(tablas, fact)
    with integ.motor.begin() as conn:
        conn.execute(text("DELETE FROM clientes"))
    with pytest.raises(AssertionError, match="Conteos"):
        integ.verificar()


# ==========================================================================
# Las consultas SQL deben correr y devolver filas
# ==========================================================================
def test_las_consultas_sql_ejecutan_sin_error(integ, fact):
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    with integ.motor.connect() as conn:
        for cons in I.CONSULTAS_SQL:
            sql = I._adaptar_booleanos(cons["sql"], integ.dialecto)
            df = pd.read_sql_query(text(sql), conn)
            assert not df.empty, f"{cons['id']} ({cons['titulo']}) devolvio 0 filas"
            assert len(df.columns) > 1, f"{cons['id']} devolvio una sola columna"


def test_identificadores_y_titulos_de_consulta_son_unicos():
    ids = [c["id"] for c in I.CONSULTAS_SQL]
    titulos = [c["titulo"] for c in I.CONSULTAS_SQL]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 18, "el enunciado pide al menos las consultas analiticas"
    assert len(titulos) == len(set(titulos))
    for c in I.CONSULTAS_SQL:
        assert c["pregunta"].endswith("?"), f"{c['id']} sin pregunta de negocio"
        assert "SELECT" in c["sql"].upper()


def test_existe_consulta_con_join_de_cuatro_o_mas_tablas():
    """El enunciado exige una consulta con JOIN de cuatro tablas o mas."""
    max_joins = 0
    for c in I.CONSULTAS_SQL:
        n = c["sql"].upper().count(" JOIN ")
        max_joins = max(max_joins, n)
    assert max_joins >= 4, f"solo hay JOINs de {max_joins} tablas"


def test_ddl_define_llave_unica_y_not_null(integ, fact):
    """El DDL debe declarar UNIQUE (llave natural) y NOT NULL de negocio."""
    for tabla in ("categorias", "dim_ciudades", "productos"):
        assert "UNIQUE (nombre)" in I._ddl_tabla(tabla, "sqlite"), tabla

    integ.crear_esquema(fact)
    insp = inspect(integ.motor)
    nullable = {c["name"]: c["nullable"] for c in insp.get_columns("clientes")}
    assert nullable["nombre"] is False
    assert nullable["correo"] is False


def test_esquema_estrella_clientes_apunta_a_dim_ciudades():
    """clientes debe llevar la FK a dim_ciudades, no solo el texto de la ciudad."""
    assert "id_ciudad" in ESQUEMA_SQL["clientes"]
    assert ("clientes", "id_ciudad", "dim_ciudades", "id_ciudad") in I.CLAVES_FORANEAS


def test_fact_declara_fk_a_todas_las_dimensiones(fact):
    """fact_ventas conserva la llave de cada dimension y la declara como FK."""
    cols = {c for c, _, _ in I.CLAVES_FORANEAS_FACT}
    assert {"id_pedido", "id_producto", "id_cliente", "id_categoria",
            "id_sucursal", "id_ciudad"} <= cols
    for col, padre, col_padre in I.CLAVES_FORANEAS_FACT:
        assert padre in I.CLAVES_PRIMARIAS, padre
        assert I.CLAVES_PRIMARIAS[padre] == col_padre
        assert col in I._esquema_fact(fact), f"fact_ventas sin columna {col}"


def test_construir_tablas_mapea_id_ciudad_en_clientes():
    """La ciudad vive en dim_ciudades; clientes guarda id_ciudad."""
    from etl_load import construir_tablas

    d = _tablas_pequenas().copy()
    d["productos"] = d["productos"].drop(columns=["id_categoria"])
    tablas = construir_tablas(d)
    cli = tablas["clientes"].set_index("id_cliente")
    ids = tablas["dim_ciudades"].set_index("nombre")["id_ciudad"]
    assert cli.loc[1, "id_ciudad"] == ids["Veracruz"]        # cliente 1
    assert cli.loc[2, "id_ciudad"] == ids["Ciudad de Mexico"]  # cliente 2
    assert cli.loc[3, "id_ciudad"] == ids["Puebla"]          # cliente 3
    assert cli["id_ciudad"].notna().all()


def test_unique_se_hace_cumplir_en_la_base(integ, fact):
    """La llave natural UNIQUE rechaza un valor duplicado de verdad."""
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    with pytest.raises(IntegrityError):
        with integ.motor.begin() as conn:
            conn.execute(text(
                "INSERT INTO categorias (id_categoria, nombre, descripcion) "
                "VALUES (99, 'Computadoras', 'duplicada')"
            ))


def test_existe_vista_de_resumen_de_ventas(integ, fact):
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    vistas = set(inspect(integ.motor).get_view_names())
    assert "v_resumen_ventas" in vistas
    q20 = next(c["sql"] for c in I.CONSULTAS_SQL if c["id"] == "Q20")
    with integ.motor.connect() as conn:
        df = pd.read_sql_query(
            text(I._adaptar_booleanos(q20, integ.dialecto)), conn)
    assert not df.empty
    assert {"anio_mes", "facturacion", "pedidos"} <= set(df.columns)


def test_benchmark_de_indice_reporta_dos_fases(integ, fact):
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    filas = integ.benchmark_indice(
        "fact_ventas", ["anio_mes"], I.SQL_BENCHMARK, nombre="ix_fact_anio_mes",
        repeticiones=2)
    assert {f["fase"] for f in filas} == {"CON INDICE", "SIN INDICE"}
    for f in filas:
        assert f["ejecucion_ms"] >= 0
        assert f["plan"].strip(), "cada fase debe traer su plan de ejecucion"


def test_consulta_pareto_es_matematicamente_coherente(integ, fact):
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    with integ.motor.connect() as conn:
        sql = I._adaptar_booleanos(
            next(c["sql"] for c in I.CONSULTAS_SQL if c["id"] == "Q12"), "sqlite"
        )
        r = pd.read_sql_query(text(sql), conn).iloc[0]
        vendidos = conn.execute(text(
            "SELECT COUNT(DISTINCT producto_nombre) FROM fact_ventas "
            "WHERE es_completado = 1"
        )).scalar_one()
    # Solo cuenta los productos con venta completada
    assert r["productos"] == vendidos
    assert 0 < r["pct_ventas_en_primer_80"] <= 100
    assert 0 < r["pct_productos_para_80"] <= 100
    #-products que explican el 80% no pueden ser mas que el total
    assert r["pct_productos_para_80"] <= 100


def test_q06_encuentra_el_inventario_muerto(integ, fact):
    integ.crear_esquema(fact)
    integ.cargar(_tablas_pequenas(), fact)
    with integ.motor.connect() as conn:
        sql = I._adaptar_booleanos(
            next(c["sql"] for c in I.CONSULTAS_SQL if c["id"] == "Q06"), "sqlite"
        )
        r = pd.read_sql_query(text(sql), conn)
    assert list(r.id_producto) == [5], "el producto 5 esta en catalogo y no se vendio"


# ==========================================================================
# NoSQL
# ==========================================================================
def test_pipelines_no_tienen_placeholders_pendientes():
    """Cada $stage de Mongo debe ser uno valido del aggregation framework."""
    validos = {
        "$match", "$group", "$sort", "$limit", "$project", "$addFields",
        "$unwind", "$replaceRoot", "$lookup", "$count", "$facet", "$skip",
    }
    for p in I.PIPELINES_MONGO:
        for etapa in p["pipeline"]:
            assert len(etapa) == 1, f"{p['id']}: etapa con mas de un operador"
            op = next(iter(etapa))
            assert op in validos, f"{p['id']}: operador desconocido {op}"


def test_los_10_pipelines_declaran_equivalente_pandas():
    ids = [p["id"] for p in I.PIPELINES_MONGO]
    assert len(ids) == len(set(ids)) == 10
    for p in I.PIPELINES_MONGO:
        assert callable(p["pandas"]), f"{p['id']} sin equivalente en pandas"
        assert p["pregunta"].endswith("?")


def _operadores_de(filtro: dict) -> set[str]:
    ops: set[str] = set()
    for clave, valor in filtro.items():
        if clave in ("$and", "$or"):
            ops.add(clave)
            for sub in valor:
                ops |= _operadores_de(sub)
        elif isinstance(valor, dict):
            ops.update(valor.keys())
    return ops


def test_las_15_consultas_mongo_usan_los_metodos_y_operadores_requeridos():
    ids = [c["id"] for c in I.CONSULTAS_MONGO]
    assert len(ids) == len(set(ids)) == 15
    tipos, ops = set(), set()
    for c in I.CONSULTAS_MONGO:
        assert c["pregunta"].endswith("?"), f"{c['id']} sin pregunta de negocio"
        assert c["tipo"] in ("find", "countDocuments"), f"{c['id']} tipo invalido"
        assert c["coleccion"] in I.INDICES_MONGO
        tipos.add(c["tipo"])
        ops |= _operadores_de(c.get("filtro") or {})
    assert {"$gt", "$lt", "$in", "$and", "$or"} <= ops, f"faltan operadores: {ops}"
    assert {"find", "countDocuments"} <= tipos
    # las consultas find deben declarar sort y limit (find().sort().limit())
    for c in I.CONSULTAS_MONGO:
        if c["tipo"] == "find":
            assert c.get("sort"), f"{c['id']} sin sort"
            assert c.get("limit"), f"{c['id']} sin limit"


def test_aplicar_filtro_soporta_operadores_mongo():
    df = pd.DataFrame({"precio": [100, 500, 6000, 25000],
                       "categoria": ["A", "B", "A", "C"]})
    assert list(I._aplicar_filtro(df, {"precio": {"$gt": 500}}).precio) == [6000, 25000]
    assert list(I._aplicar_filtro(df, {"precio": {"$lt": 600}}).precio) == [100, 500]
    assert list(I._aplicar_filtro(df, {"categoria": {"$in": ["A", "C"]}}).precio) \
        == [100, 6000, 25000]
    conj = I._aplicar_filtro(df, {"$and": [{"categoria": "A"}, {"precio": {"$lt": 1000}}]})
    assert list(conj.precio) == [100]
    disy = I._aplicar_filtro(df, {"$or": [{"precio": {"$lt": 200}},
                                          {"precio": {"$gt": 10000}}]})
    assert list(disy.precio) == [100, 25000]


def test_consultas_mongo_locales_devuelven_resultados(monkeypatch, tmp_path):
    monkeypatch.setenv("SIN_MONGO", "1")
    docs = {
        "productos": [
            {"id_producto": 1, "nombre": "A", "categoria": "Redes",
             "precio": 8000, "rango_precio": "Alto"},
            {"id_producto": 2, "nombre": "B", "categoria": "Audio",
             "precio": 500, "rango_precio": "Economico"},
        ],
        "resenas": [
            {"id_resena": 1, "producto": "A", "calificacion": 5,
             "fecha": "2025-01-01", "verificada": True},
            {"id_resena": 2, "producto": "B", "calificacion": 2,
             "fecha": "2025-01-02", "verificada": False},
        ],
        "actividad_usuario": [
            {"usuario": "u1", "producto": "A", "dispositivo": "iOS",
             "duracion_seg": 400, "es_visualizacion": True,
             "evento": "producto_visto", "fecha": "2025-01-01"},
            {"usuario": "u2", "producto": "B", "dispositivo": "Windows",
             "duracion_seg": 10, "es_visualizacion": True,
             "evento": "producto_comprado", "fecha": "2025-01-02"},
        ],
    }
    integ = I.IntegradorMongo(docs, tmp_path / "mongo")
    assert integ.conectar() == "local"
    integ.crear_colecciones()

    b01 = next(c for c in I.CONSULTAS_MONGO if c["id"] == "B01")  # precio > 5000
    assert list(integ.ejecutar_consulta(b01)["id_producto"]) == [1]
    b13 = next(c for c in I.CONSULTAS_MONGO if c["id"] == "B13")  # countDocuments
    assert int(integ.ejecutar_consulta(b13)["total"].iloc[0]) == 1
    b14 = next(c for c in I.CONSULTAS_MONGO if c["id"] == "B14")  # iOS/macOS
    assert list(integ.ejecutar_consulta(b14)["usuario"]) == ["u1"]


def test_esquema_de_indices_cubre_las_tres_colecciones():
    assert set(I.INDICES_MONGO) == {"productos", "resenas", "actividad_usuario"}
    for nombre, defs in I.INDICES_MONGO.items():
        assert defs, f"{nombre} sin indices"
        for claves, opciones, razon in defs:
            assert claves and all(len(k) == 2 for k in claves)
            assert opciones in ("", "unique", "sparse")
            assert razon.strip(), "cada indice debe justificar su existencia"
    # el indice que habilita el analisis de navegacion debe existir
    assert any(
        "producto" in dict((c, d) for c, d in claves)
        for claves, _, _ in I.INDICES_MONGO["actividad_usuario"]
    )


def test_slug_es_seguro_para_nombre_de_archivo():
    assert I._slug("Top 10 productos por facturacion") == "top_10_productos_por_facturacion"
    assert I._slug("Anio/Mes + Ventas?") == "anio_mes_ventas"
    assert "/" not in I._slug("a/b/c") and "?" not in I._slug("a?b")
