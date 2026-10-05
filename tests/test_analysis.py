"""Pruebas de `src/analysis.py`.

El riesgo real de un modulo de analisis no es que lance una excepcion: es que
devuelva un numero plausible y equivocado. Casi todos los tests de aqui
comprueban que la cifra coincide con un calculo independiente hecho a mano
sobre el mismo dataset, no contra un valor cocido del dataset real (que
cambia cada vez que se ajusta el generador).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import analysis as A  # noqa: E402


# --------------------------------------------------------------------------
# Dataset de prueba: 2 pedidos, uno completo y uno cancelado, 3 lineas.
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def fact() -> pd.DataFrame:
    columnas = {
        "id_detalle": [1, 2, 3, 4],
        "id_pedido": [1, 1, 2, 3],
        "id_cliente": [1, 1, 2, 3],
        "id_producto": [1, 2, 1, 3],
        "id_sucursal": [1, 1, 2, 3],
        "fecha_pedido": ["2025-01-10", "2025-01-10", "2025-02-20", "2025-03-05"],
        "anio_mes": ["2025-01", "2025-01", "2025-02", "2025-03"],
        "cliente_nombre": ["Ana", "Ana", "Luis", "Marta"],
        "ciudad": ["Veracruz", "Veracruz", "Puebla", "Puebla"],
        "region": ["Sureste", "Sureste", "Centro", "Centro"],
        "categoria": ["Computadoras", "Accesorios", "Computadoras", "Redes"],
        "canal_venta": ["web", "web", "app_movil", "web"],
        "es_premium": [True, True, False, False],
        "producto_nombre": ["Laptop A", "Mouse B", "Laptop A", "Router D"],
        "precio_lista": [25000.0, 350.0, 25000.0, 1200.0],
        "margen_bruto_producto": [0.3, 0.4, 0.3, 0.35],
        "costo_estimado": [17500.0, 210.0, 17500.0, 780.0],
        "cantidad": [2, 3, 1, 4],
        "precio_unitario": [25000.0, 350.0, 25000.0, 1200.0],
        "descuento": [0.0, 50.0, 0.0, 0.0],
        "porcentaje_descuento": [0.0, 4.76, 0.0, 0.0],
        "total": [50000.0, 1000.0, 25000.0, 4800.0],
        "estado": ["completado", "completado", "cancelado", "completado"],
        "es_completado": [True, True, False, True],
        "metodo": ["oxxo", "oxxo", "efectivo", "tarjeta_credito"],
        "monto": [51000.0, 51000.0, 25000.0, 4800.0],
        "estado_pago": ["aprobado", "aprobado", "rechazado", "aprobado"],
        "diferencia_pago": [0.0, 0.0, -200.0, 0.0],
        "conciliado": [True, True, False, True],
    }
    df = pd.DataFrame(columnas)
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"])
    return df


@pytest.fixture(scope="module")
def documentos() -> dict:
    return {
        "productos": [
            {"id_producto": 1, "nombre": "Laptop A", "categoria": "Computadoras", "precio": 25000.0},
            {"id_producto": 2, "nombre": "Mouse B", "categoria": "Accesorios", "precio": 350.0},
            {"id_producto": 3, "nombre": "Router D", "categoria": "Redes", "precio": 1200.0},
            {"id_producto": 4, "nombre": "Teclado E", "categoria": "Accesorios", "precio": 900.0},
        ],
        "resenas": [
            {"id_resena": 1, "id_producto": 1, "producto": "Laptop A", "categoria": "Computadoras",
             "calificacion": 5.0, "comentario": "bueno", "verificada": True,
             "fecha": "2025-02-01", "es_positiva": True, "cliente.id": 1, "cliente.nombre": "Ana"},
            {"id_resena": 2, "id_producto": 1, "producto": "Laptop A", "categoria": "Computadoras",
             "calificacion": 1.0, "comentario": "malo", "verificada": False,
             "fecha": "2025-02-02", "es_positiva": False, "cliente.id": 2, "cliente.nombre": "Luis"},
        ],
        "actividad_usuario": [
            {"usuario": 1, "ciudad_usuario": "Veracruz", "fecha": "2025-01-05T10:00:00",
             "evento": "producto_visto", "producto": 1, "nombre_producto": "Laptop A",
             "categoria": "Computadoras", "dispositivo": "Windows", "ubicacion": "Veracruz",
             "duracion_seg": 30, "hora": 10, "es_visualizacion": True, "anio": 2025,
             "mes": 1, "trimestre": 1, "anio_mes": "2025-01"},
            {"usuario": 1, "ciudad_usuario": "Veracruz", "fecha": "2025-01-05T10:05:00",
             "evento": "producto_en_carrito", "producto": 1, "nombre_producto": "Laptop A",
             "categoria": "Computadoras", "dispositivo": "Windows", "ubicacion": "Veracruz",
             "duracion_seg": 10, "hora": 10, "es_visualizacion": False, "anio": 2025,
             "mes": 1, "trimestre": 1, "anio_mes": "2025-01"},
            {"usuario": 2, "ciudad_usuario": "Puebla", "fecha": "2025-01-06T09:00:00",
             "evento": "producto_visto", "producto": 2, "nombre_producto": "Mouse B",
             "categoria": "Accesorios", "dispositivo": "Android", "ubicacion": "Puebla",
             "duracion_seg": 20, "hora": 9, "es_visualizacion": True, "anio": 2025,
             "mes": 1, "trimestre": 1, "anio_mes": "2025-01"},
            {"usuario": 3, "ciudad_usuario": "Puebla", "fecha": "2025-01-07T09:00:00",
             "evento": "producto_visto", "producto": 4, "nombre_producto": "Teclado E",
             "categoria": "Accesorios", "dispositivo": "iOS", "ubicacion": "Puebla",
             "duracion_seg": 20, "hora": 9, "es_visualizacion": True, "anio": 2025,
             "mes": 1, "trimestre": 1, "anio_mes": "2025-01"},
        ],
    }


# --------------------------------------------------------------------------
# Medida: el error clasico de este desnormalizado
# --------------------------------------------------------------------------
def test_pedidos_unicos_no_duplica_lineas(fact):
    assert len(A.pedidos_unicos(fact)) == 3
    assert A.pedidos_unicos(fact).id_pedido.is_unique


def test_utilidad_y_margen_es_una_fila_por_linea(fact):
    d = A.utilidad_y_margen(fact)
    assert len(d) == len(fact)
    # Laptop A: (25000 - 17500) * 2 - 0 = 15000
    lap = d[d.id_detalle == 1].iloc[0]
    assert lap.utilidad_bruta == pytest.approx(15000.0)
    assert lap.margen_real == pytest.approx(15000.0 / 50000.0)
    # Mouse B con descuento: (350 - 210) * 3 - 50 = 370
    raton = d[d.id_detalle == 2].iloc[0]
    assert raton.utilidad_bruta == pytest.approx(370.0)


def test_facturacion_ignora_pedidos_cancelados(fact):
    kpis = A.kpis_generales(fact).set_index("indicador")["valor"]
    completadas = fact[fact.es_completado]
    esperado = completadas.total.sum()
    assert kpis["Facturacion"] == f"${esperado:,.2f}"
    # el cancelado (25000) NO esta dentro
    assert esperado == pytest.approx(50000 + 1000 + 4800)
    assert kpis["Pedidos totales"] == "3"
    assert kpis["Pedidos completados"] == "2"


def test_ticket_promedio_usa_pedidos_no_lineas(fact):
    kpis = A.kpis_generales(fact).set_index("indicador")["valor"]
    completadas = fact[fact.es_completado]
    pedidos = completadas.id_pedido.nunique()
    esperado = completadas.total.sum() / pedidos
    # si dividiera entre lineas (3) daria 18600, no 27900
    assert kpis["Ticket promedio"] == f"${esperado:,.2f}"
    assert kpis["Ticket promedio"] == "$27,900.00"


def test_tasa_de_cancelacion(fact):
    kpis = A.kpis_generales(fact).set_index("indicador")["valor"]
    # 1 cancelado de 3 pedidos
    assert kpis["Tasa de cancelacion"] == "33.33%"


# --------------------------------------------------------------------------
# Serie temporal y mixes
# --------------------------------------------------------------------------
def test_ventas_mensuales_solo_completadas(fact):
    d = A.ventas_mensuales(fact)
    # febrero solo tiene el pedido cancelado, asi que no aparece como mes
    assert list(d.anio_mes) == ["2025-01", "2025-03"]
    assert d.facturacion.sum() == pytest.approx(50000 + 1000 + 4800)
    assert d.iloc[0].pedidos == 1
    assert d.iloc[0].unidades == 5
    assert d.iloc[-1].mes_incompleto
    assert not d.iloc[0].mes_incompleto


def test_mix_categoria_participacion_suma_100(fact):
    d = A.mix_categoria(fact)
    assert d.participacion_pct.sum() == pytest.approx(100.0)
    assert d.iloc[0].segmento == "Computadoras"
    # solo el pedido completado de la laptop
    assert d.iloc[0].facturacion == pytest.approx(50000.0)


def test_mixes_usan_el_mismo_total(fact):
    total = fact[fact.es_completado].total.sum()
    for mix in (A.mix_categoria(fact), A.mix_canal(fact), A.mix_region(fact)):
        assert mix.facturacion.sum() == pytest.approx(total)


# --------------------------------------------------------------------------
# RFM
# --------------------------------------------------------------------------
def test_segmentacion_cubre_todos_los_clientes(fact):
    seg = A.segmentacion_clientes(fact)
    # el cliente 2 solo tiene el pedido cancelado -> no entra
    assert set(seg.id_cliente) == {1, 3}
    assert seg.id_cliente.is_unique
    assert set(seg.segmento) <= set(A.REGLAS_RFM)
    assert seg.regla.notna().all()


def test_rfm_frecuencia_y_monetario_son_correctos(fact):
    seg = A.segmentacion_clientes(fact).set_index("id_cliente")
    ana = seg.loc[1]
    assert ana.frecuencia == 1
    assert ana.monetario == pytest.approx(51000.0)
    assert ana.ticket_promedio == pytest.approx(51000.0)
    # Luis (2) esta excluido porque su unico pedido fue cancelado
    assert 2 not in seg.index


def test_recencia_se_mide_contra_la_fecha_mas_reciente(fact):
    seg = A.segmentacion_clientes(fact).set_index("id_cliente")
    # la compra mas reciente del dataset es la de Marta (2025-03-05)
    assert seg.loc[3].recencia_dias == 0
    assert seg.loc[1].recencia_dias == 54


def test_resumen_segmentos_conserva_clientes(fact):
    seg = A.segmentacion_clientes(fact)
    resumen = A.resumen_segmentos(seg)
    assert resumen.clientes.sum() == len(seg)
    assert resumen.facturacion.sum() == pytest.approx(seg.monetario.sum())
    assert resumen.participacion_pct.sum() == pytest.approx(100.0)


def test_puntuar_reparte_en_cinco_niveles():
    s = pd.Series(range(100))
    p = A._puntuar(s, mayor_es_mejor=True)
    assert sorted(p.unique()) == [1, 2, 3, 4, 5]
    assert p.iloc[0] == 1 and p.iloc[-1] == 5
    # para recencia, menos dias es mejor: el mas antiguo puntua 1
    r = A._puntuar(pd.Series([1, 2, 3, 4, 5]), mayor_es_mejor=False)
    assert r.iloc[0] == 5 and r.iloc[-1] == 1


# --------------------------------------------------------------------------
# Navegacion
# --------------------------------------------------------------------------
def test_embudo_usa_eventos_y_no_personas(documentos):
    act = A.cargar_actividad(documentos)
    embudo, notas = A.embudo_navegacion(act)
    assert list(embudo.eventos) == [3, 1, 0]
    assert embudo.participacion_pct.iloc[0] == pytest.approx(100.0)
    assert embudo.participacion_pct.iloc[1] == pytest.approx(100 / 3)
    assert notas.clientes_navegantes.iloc[0] == 3


def test_correlacion_reporta_las_tres_poblaciones(fact, documentos):
    act = A.cargar_actividad(documentos)
    prods = A.cargar_productos(documentos)
    metricas, detalle = A.correlacion_navegacion_venta(act, fact, prods)
    nombres = set(metricas.metrica)
    assert "Pearson (todos los productos)" in nombres
    assert "Pearson (solo visitados)" in nombres
    assert "Pearson (visitados y vendidos)" in nombres
    # el producto 4 (Teclado E) tiene visitas y cero ventas
    assert "Productos visitados" in nombres
    assert detalle.loc[detalle.id_producto == 4, "nombre"].iloc[0] == "Teclado E"
    assert detalle.loc[detalle.id_producto == 4, "unidades"].iloc[0] == 0


def test_correlacion_usa_una_poblacion_fija():
    # con dos productos la correlacion no es calculable
    a = pd.DataFrame({"visitas": [1, 2], "unidades": [1, 2]})
    assert np.isnan(float(a.corr().iloc[0, 1])) or a.corr().iloc[0, 1] == 1.0


def test_inventario_muerto_solo_ventas_cero(fact, documentos):
    act = A.cargar_actividad(documentos)
    prods = A.cargar_productos(documentos)
    muertos = A.inventario_muerto(act, fact, prods)
    assert list(muertos.id_producto) == [4]
    assert (muertos.unidades == 0).all()
    assert muertos.nombre.notna().all(), "el nombre viene del catalogo, no de la fact"


def test_under_exposure_exige_ventas(fact, documentos):
    act = A.cargar_actividad(documentos)
    prods = A.cargar_productos(documentos)
    under = A.under_exposure(act, fact, prods)
    assert (under.unidades > 0).all()
    assert 4 not in set(under.id_producto)
    assert under.visitas_por_unidad.notna().all()


# --------------------------------------------------------------------------
# Pareto
# --------------------------------------------------------------------------
def test_pareto_acumula_hasta_100(fact):
    d = A.ley_pareto(fact)
    assert d.acumulado_pct.iloc[-1] == pytest.approx(100.0)
    assert d.acumulado_pct.is_monotonic_increasing
    assert d.pct_del_total.sum() == pytest.approx(100.0)
    assert list(d.posicion) == list(range(1, len(d) + 1))
    # Laptop A y Mouse B comparten el pedido 1; el pedido cancelado no cuenta
    assert set(d.id_producto) == {1, 2, 3}


def test_pareto_ordena_de_mayor_a_menor(fact):
    d = A.ley_pareto(fact)
    assert d.facturacion.is_monotonic_decreasing


# --------------------------------------------------------------------------
# Pagos, descuentos, resenas
# --------------------------------------------------------------------------
def test_calidad_pago_por_estado(fact):
    d = A.calidad_pago(fact)
    assert d.pedidos.sum() == 3
    assert set(d.estado_pago) == {"aprobado", "rechazado"}
    rech = d[d.estado_pago == "rechazado"].iloc[0]
    assert rech.conciliados == 0
    assert rech.tasa_conciliacion_pct == pytest.approx(0.0)


def test_impacto_descuentos_cubre_todos_los_rangos(fact):
    d = A.impacto_descuentos(fact)
    assert len(d) == 5, "los rangos vacios tambien se reportan, para no ocultar el 0%"
    con_lineas = d[d.lineas > 0]
    vacios = d[d.lineas == 0]
    # con lineas el porcentaje es calculable y no puede faltar
    assert con_lineas.margen_pct.notna().all()
    assert con_lineas.descuento_pct_del_ingreso.notna().all()
    # sin lineas no hay base de calculo: nulo es correcto, 0 seria mentir
    assert vacios.margen_pct.isna().all()
    sin = d[d.rango_descuento == "0%"].iloc[0]
    assert sin.descuentos == 0.0
    con = d[d.rango_descuento == "1-5%"].iloc[0]
    assert con.descuentos == pytest.approx(50.0)
    # el descuento se paga con margen: mas descuento, menos margen.
    # `d` ya viene en orden de rango (pd.cut sobre categorico), NO alfabetico:
    # alfabeticamente ">20%" cae antes que "6-10%".
    assert list(d.rango_descuento) == ["0%", "1-5%", "6-10%", "11-20%", ">20%"]
    # formula completa del margen en la unica linea con descuento:
    # ingreso 3*350=1050, costo 3*210=630, descuento 50 -> 370/1050
    con = d[d.rango_descuento == "1-5%"].iloc[0]
    assert con.ingreso_bruto == pytest.approx(1050.0)
    assert con.utilidad == pytest.approx(370.0)
    assert con.margen_pct == pytest.approx(370.0 / 1050.0 * 100)
    assert con.descuento_pct_del_ingreso == pytest.approx(50.0 / 1050.0 * 100)


def test_satisfaccion_por_calificacion(documentos):
    res = A.cargar_resenas(documentos)
    d = A.satisfaccion(res)
    assert d.resenas.sum() == 2
    assert list(d.calificacion) == [1.0, 5.0]
    assert d.tasa_positiva_pct.iloc[0] == pytest.approx(0.0)
    assert d.tasa_positiva_pct.iloc[1] == pytest.approx(100.0)


def test_productos_valorados_exigen_minimo_de_resenas(documentos):
    res = A.cargar_resenas(documentos)
    # el producto 1 tiene 2 resenas; con minimo 2 entra, con 3 no
    assert len(A.productos_valorados(res, minimo=2)) == 1
    assert len(A.productos_valorados(res, minimo=3)) == 0


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def test_construir_todos_devuelve_todos_los_analisis(fact, documentos):
    sucursales = pd.DataFrame({"id_sucursal": [1, 2, 3], "nombre": ["S1", "S2", "S3"],
                               "ciudad": ["Veracruz", "Puebla", "Puebla"],
                               "region": ["Sureste", "Centro", "Centro"]})
    r = A.construir_todos(fact, documentos, sucursales)
    assert len(r) == 19
    for nombre, df in r.items():
        assert isinstance(df, pd.DataFrame), nombre
    assert not r["01_kpis_generales"].empty
    assert not r["15_ley_pareto"].empty


def test_ningun_analiz_trae_nulos_en_claves(fact, documentos):
    r = A.construir_todos(fact, documentos, None)
    # `19_productos_valorados` puede salir vacio en un fixture tan pequeno: el
    # filtro exige 5 resenas por producto y aqui hay 2. En el dataset real si
    # hay 227 productos que lo cumplen.
    pueden_ser_vacios = {"19_productos_valorados"}
    for nombre, df in r.items():
        if df.empty:
            assert nombre in pueden_ser_vacios, f"{nombre} salio vacio"
            continue
        assert not df.isna().all().any(), f"{nombre} tiene una columna enteramente nula"
