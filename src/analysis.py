"""Parte V - Analisis de negocio sobre el dataset ya limpio e integrado.

Este modulo NO vuelve a limpiar ni a integrar nada: consume los datasets que
dejo `etl_load.py` y responde preguntas de negocio. Todas las funciones son
puras y devuelven un DataFrame, de modo que `viz.py` reutiliza exactamente
las mismas cifras y los graficos nunca pueden contradecir a los CSV.

Convencion de medida: la fact analitica tiene UNA FILA POR LINEA DE VENTA.
Por eso la facturacion se suma sobre `total` (importe de la linea) y
cualquier metric a nivel pedido usa `id_pedido` deduplicado. Sumar
`total_pedido` linea a linea contaria cada pedido tantas veces como lineas
tenga, que es el error clasico de este desnormalizado.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROCESSED, REPORTS
from utils import LOG, asegurar_dir, money, numero, subtitulo, tabla, titulo

DESTINO = REPORTS / "analisis"

FACT = PROCESSED / "dataset_postgresql.csv"
MONGO = PROCESSED / "dataset_mongodb.json"
TABLAS = PROCESSED / "tablas"


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def cargar_fact(ruta: Path | None = None) -> pd.DataFrame:
    """Fact analitica (una fila por linea de venta) con `fecha_pedido` como fecha."""
    ruta = ruta or FACT
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta {ruta}. Ejecuta antes:\n"
            r"  .\.venv\Scripts\python.exe src\etl_load.py"
        )
    df = pd.read_csv(ruta)
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"])
    return df


def cargar_documentos(ruta: Path | None = None) -> dict[str, list[dict]]:
    ruta = ruta or MONGO
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta {ruta}. Ejecuta antes:\n"
            r"  .\.venv\Scripts\python.exe src\etl_load.py"
        )
    return json.loads(ruta.read_text(encoding="utf-8"))


def cargar_actividad(documentos: dict | None = None) -> pd.DataFrame:
    documentos = documentos or cargar_documentos()
    act = pd.json_normalize(documentos["actividad_usuario"])
    act["fecha"] = pd.to_datetime(act["fecha"])
    return act


def cargar_resenas(documentos: dict | None = None) -> pd.DataFrame:
    documentos = documentos or cargar_documentos()
    res = pd.json_normalize(documentos["resenas"])
    res["fecha"] = pd.to_datetime(res["fecha"])
    return res


def cargar_productos(documentos: dict | None = None) -> pd.DataFrame:
    documentos = documentos or cargar_documentos()
    return pd.json_normalize(documentos["productos"])


def cargar_sucursales() -> pd.DataFrame:
    ruta = TABLAS / "dim_sucursales.csv"
    return pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()


# --------------------------------------------------------------------------
# Utilidades de calculo
# --------------------------------------------------------------------------
def pedidos_unicos(fact: pd.DataFrame) -> pd.DataFrame:
    """Una fila por pedido. Obligatorio para toda metrica a nivel pedido."""
    return fact.sort_values("id_detalle").drop_duplicates("id_pedido")


def utilidad_y_margen(fact: pd.DataFrame) -> pd.DataFrame:
    """Agrega utilidad bruta real y margen real POR LINEA.

    `costo_estimado` es el costo unitario (precio * (1 - margen)), asi que la
    utilidad de la linea es (precio_unitario - costo) * cantidad - descuento.
    """
    df = fact.copy()
    df["ingreso_bruto"] = df["precio_unitario"] * df["cantidad"]
    df["costo_total"] = df["costo_estimado"] * df["cantidad"]
    df["utilidad_bruta"] = df["ingreso_bruto"] - df["costo_total"] - df["descuento"]
    df["margen_real"] = np.where(
        df["ingreso_bruto"] > 0, df["utilidad_bruta"] / df["ingreso_bruto"], np.nan
    )
    return df


def _puntuar(serie: pd.Series, mayor_es_mejor: bool) -> pd.Series:
    """Puntaje 1..5 por quintil. `rank(method='first')` desempata de forma
    determinista: sin esto, quintiles con muchos empates (muchos clientes con
    1 sola compra)arian vacios y la segmentacion se descuadra."""
    if len(serie) == 0:
        return pd.Series(dtype=int)
    # rank devuelve 1..n; se normaliza a 0..1 para que los cortes en quintiles
    # caigan dentro del rango (con los quintiles en bruto el ultimo queda vacio).
    rango = serie.rank(method="first", ascending=mayor_es_mejor) / len(serie)
    return pd.cut(rango, bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0],
                  labels=[1, 2, 3, 4, 5]).astype(int)


# --------------------------------------------------------------------------
# 1. KPIs generales
# --------------------------------------------------------------------------
def kpis_generales(fact: pd.DataFrame) -> pd.DataFrame:
    """Tablero de una linea por indicador. Es la respuesta a 'como va la empresa'."""
    lineas = utilidad_y_margen(fact)
    completadas = lineas[lineas["es_completado"]]
    pedidos = pedidos_unicos(fact)
    completados = pedidos[pedidos["es_completado"]]
    facturacion = completadas["total"].sum()
    unidades = completadas["cantidad"].sum()
    utilidad = completadas["utilidad_bruta"].sum()

    kpis = [
        ("Facturacion", money(facturacion), "solo pedidos completados"),
        ("Pedidos totales", numero(len(pedidos)), "unicos, no lineas"),
        ("Pedidos completados", numero(len(completados)), ""),
        ("Tasa de cancelacion", f"{(1 - len(completados) / len(pedidos)) * 100:.2f}%",
         "pedidos cancelados / pedidos totales"),
        ("Unidades vendidas", numero(unidades), ""),
        ("Ticket promedio", money(facturacion / len(completados)),
         "facturacion / pedidos completados"),
        ("Unidades por pedido", f"{unidades / len(completados):.2f}", ""),
        ("Clientes", numero(pedidos["id_cliente"].nunique()), "con al menos un pedido"),
        ("Productos vendidos", numero(completadas["id_producto"].nunique()), ""),
        ("Categorias", numero(fact["categoria"].nunique()), ""),
        ("Utilidad bruta", money(utilidad), "ingreso - costo - descuentos"),
        ("Margen real ponderado", f"{utilidad / completadas['ingreso_bruto'].sum() * 100:.2f}%",
         "utilidad / ingreso bruto"),
        ("Descuentos otorgados", money(completadas["descuento"].sum()), ""),
        ("Ticket con descuento",
         money(completadas[completadas["descuento"] > 0]["total"].mean())
         if (completadas["descuento"] > 0).any() else "N/A",
         "solo lineas con descuento"),
        ("Ticket sin descuento",
         money(completadas[completadas["descuento"] == 0]["total"].mean())
         if (completadas["descuento"] == 0).any() else "N/A", ""),
        ("Ingreso por cliente", money(facturacion / pedidos["id_cliente"].nunique()), ""),
    ]
    return pd.DataFrame(kpis, columns=["indicador", "valor", "nota"])


# --------------------------------------------------------------------------
# 2. Serie temporal
# --------------------------------------------------------------------------
def ventas_mensuales(fact: pd.DataFrame) -> pd.DataFrame:
    """Facturacion por mes. El ultimo mes puede estar incompleto: se marca
    con `mes_incompleto` para que nadie compare un mes parcial contra uno
    entero y saque conclusiones equivocadas."""
    df = fact[fact["es_completado"]].copy()
    g = df.groupby("anio_mes").agg(
        facturacion=("total", "sum"),
        pedidos=("id_pedido", "nunique"),
        unidades=("cantidad", "sum"),
        clientes=("id_cliente", "nunique"),
        descuentos=("descuento", "sum"),
    ).reset_index()
    g["ticket_promedio"] = g["facturacion"] / g["pedidos"]
    g["unidades_por_pedido"] = g["unidades"] / g["pedidos"]
    g = g.sort_values("anio_mes").reset_index(drop=True)
    g["crecimiento_mom"] = g["facturacion"].pct_change() * 100
    g["mes_incompleto"] = g["anio_mes"] == g["anio_mes"].max()
    return g


# --------------------------------------------------------------------------
# 3-5. Mixes
# --------------------------------------------------------------------------
def _mix(df: pd.DataFrame, columna: str) -> pd.DataFrame:
    g = df.groupby(columna).agg(
        facturacion=("total", "sum"),
        unidades=("cantidad", "sum"),
        pedidos=("id_pedido", "nunique"),
        utilidad=("utilidad_bruta", "sum"),
    ).reset_index().rename(columns={columna: "segmento"})
    g["margen_pct"] = np.where(g["utilidad"] > 0, g["utilidad"] / g["facturacion"] * 100, np.nan)
    g["ticket_promedio"] = g["facturacion"] / g["pedidos"]
    total = g["facturacion"].sum()
    g["participacion_pct"] = g["facturacion"] / total * 100 if total else np.nan
    return g.sort_values("facturacion", ascending=False).reset_index(drop=True)


def mix_categoria(fact: pd.DataFrame) -> pd.DataFrame:
    return _mix(utilidad_y_margen(fact[fact["es_completado"]]), "categoria")


def mix_canal(fact: pd.DataFrame) -> pd.DataFrame:
    return _mix(utilidad_y_margen(fact[fact["es_completado"]]), "canal_venta")


def mix_region(fact: pd.DataFrame) -> pd.DataFrame:
    return _mix(utilidad_y_margen(fact[fact["es_completado"]]), "region")


def mix_ciudad(fact: pd.DataFrame) -> pd.DataFrame:
    return _mix(utilidad_y_margen(fact[fact["es_completado"]]), "ciudad")


def por_sucursal(fact: pd.DataFrame, sucursales: pd.DataFrame | None = None) -> pd.DataFrame:
    df = utilidad_y_margen(fact[fact["es_completado"]])
    g = df.groupby("id_sucursal").agg(
        facturacion=("total", "sum"),
        pedidos=("id_pedido", "nunique"),
        unidades=("cantidad", "sum"),
    ).reset_index()
    g["ticket_promedio"] = g["facturacion"] / g["pedidos"]
    if sucursales is not None and not sucursales.empty:
        g = g.merge(
            sucursales[["id_sucursal", "nombre", "ciudad", "region"]],
            on="id_sucursal", how="left",
        )
    g["participacion_pct"] = g["facturacion"] / g["facturacion"].sum() * 100
    return g.sort_values("facturacion", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# 6. Segmentacion de clientes (RFM)
# --------------------------------------------------------------------------
# Reglas de negocio explicitas, no cortes arbitrarios: el puntaje 1..5 sale de
# quintiles y despues se cruzan R, F y M. Se documenta para que el corte sea
# auditable y no una caja negra.
REGLAS_RFM = {
    "Campeones": "R>=4 y F>=4 y M>=4: compran reciente, frecuente y alto",
    "Leales": "F>=3 y M>=3: compran bien pero hace tiempo",
    "Potenciales": "F>=3: compran algo, gasto bajo",
    "Nuevos": "R=5 y F<=2: sealiens hace poco y aun repiten",
    "En riesgo": "F<=2 y M>=3: gastaron mucho y ya no vuelven",
    "Dormidos": "el resto: baja frecuencia y bajo gasto",
}


def segmentacion_clientes(fact: pd.DataFrame) -> pd.DataFrame:
    """Segmentacion RFM. Devuelve un dataframe por CLIENTE (no por linea)."""
    df = fact[fact["es_completado"]]
    if df.empty:
        return pd.DataFrame(columns=["id_cliente", "cliente_nombre", "ciudad",
                                     "recencia_dias", "frecuencia", "monetario",
                                     "puntaje_r", "puntaje_f", "puntaje_m",
                                     "segmento", "regla"])

    g = df.groupby("id_cliente").agg(
        cliente_nombre=("cliente_nombre", "first"),
        ciudad=("ciudad", "first"),
        es_premium=("es_premium", "first"),
        frecuencia=("id_pedido", "nunique"),
        monetario=("total", "sum"),
        unidades=("cantidad", "sum"),
        ultima_compra=("fecha_pedido", "max"),
    ).reset_index()

    referencia = df["fecha_pedido"].max()
    g["recencia_dias"] = (referencia - g["ultima_compra"]).dt.days
    g["ticket_promedio"] = g["monetario"] / g["frecuencia"]

    g["puntaje_r"] = _puntuar(g["recencia_dias"], mayor_es_mejor=False)
    g["puntaje_f"] = _puntuar(g["frecuencia"], mayor_es_mejor=True)
    g["puntaje_m"] = _puntuar(g["monetario"], mayor_es_mejor=True)

    r, f, m = g["puntaje_r"], g["puntaje_f"], g["puntaje_m"]
    g["segmento"] = np.select(
        [
            (r >= 4) & (f >= 4) & (m >= 4),
            (f >= 3) & (m >= 3),
            f >= 3,
            (r == 5) & (f <= 2),
            (f <= 2) & (m >= 3),
        ],
        ["Campeones", "Leales", "Potenciales", "Nuevos", "En riesgo"],
        default="Dormidos",
    )
    g["regla"] = g["segmento"].map(REGLAS_RFM)
    return g.sort_values("monetario", ascending=False).reset_index(drop=True)


def resumen_segmentos(segmentos: pd.DataFrame) -> pd.DataFrame:
    g = segmentos.groupby("segmento").agg(
        clientes=("id_cliente", "size"),
        facturacion=("monetario", "sum"),
        frecuencia_media=("frecuencia", "mean"),
        recencia_media=("recencia_dias", "mean"),
        ticket_promedio=("ticket_promedio", "mean"),
    ).reset_index()
    g["participacion_pct"] = g["facturacion"] / g["facturacion"].sum() * 100
    g["regla"] = g["segmento"].map(REGLAS_RFM)
    orden = ["Campeones", "Leales", "Potenciales", "Nuevos", "En riesgo", "Dormidos"]
    g["_o"] = g["segmento"].map({s: i for i, s in enumerate(orden)}).fillna(99)
    return g.sort_values(["_o", "facturacion"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)


# --------------------------------------------------------------------------
# 7-8. Navegacion: embudo y correlacion
# --------------------------------------------------------------------------
def embudo_navegacion(actividad: pd.DataFrame) -> pd.DataFrame:
    """Embudo en unidades HOMOGENEAS (eventos), no mezclando personas con
    productos: un embudo con pasos de distinta unidad no se puede leer."""
    pasos = [
        ("1. Visualizaciones", "producto_visto"),
        ("2. Al carrito", "producto_en_carrito"),
        ("3. Compras", "producto_comprado"),
    ]
    filas = []
    previo = None
    total = int((actividad["evento"] == "producto_visto").sum())
    for nombre, evento in pasos:
        n = int((actividad["evento"] == evento).sum())
        filas.append({
            "paso": nombre,
            "eventos": n,
            "participacion_pct": n / total * 100 if total else np.nan,
            "caida_vs_paso_anterior_pct": (n / previo * 100) if previo else np.nan,
        })
        previo = n
    embudo = pd.DataFrame(filas)

    # Un cliente que compro sin haber carvingotear no es un error: se reporta
    # aparte en vez de forzar los numeros para que el embudo "cuadre".
    compradores = set(actividad.loc[actividad["evento"] == "producto_comprado", "usuario"])
    con_carrito = set(actividad.loc[actividad["evento"] == "producto_en_carrito", "usuario"])
    embudo_extra = {
        "clientes_que_compraron": len(compradores),
        "clientes_que_compraron_sin_carrito": len(compradores - con_carrito),
        "clientes_navegantes": int(actividad["usuario"].nunique()),
    }
    return embudo, pd.DataFrame([embudo_extra])


def _unidades_vendidas(fact: pd.DataFrame) -> pd.Series:
    """Unidades por producto, solo de pedidos COMPLETADOS.

    Una venta cancelada no es una venta: contarla como demanda falsearia la
    correlacion con la navegacion y el analisis de exposure.
    """
    return (fact[fact["es_completado"]]
            .groupby("id_producto")["cantidad"].sum().rename("unidades"))


def _catalogo_productos(fact: pd.DataFrame, productos: pd.DataFrame | None) -> pd.DataFrame:
    """Nombre y categoria de cada producto.

    Se toma del catalogo de MongoDB y no de la fact a proposito: los productos
    que NUNCA se vendieron no existen en la fact, y son justo los que
    interesting para el analisis de inversion no convertida.
    """
    if productos is not None and not productos.empty:
        return productos[["id_producto", "nombre", "categoria", "precio"]].copy()
    return (fact.drop_duplicates("id_producto")
            .set_index("id_producto")[["producto_nombre", "categoria", "precio_lista"]]
            .rename(columns={"producto_nombre": "nombre", "precio_lista": "precio"})
            .reset_index())


def correlacion_navegacion_venta(actividad: pd.DataFrame, fact: pd.DataFrame,
                                 productos: pd.DataFrame | None = None) -> pd.DataFrame:
    """Visitas vs unidades vendidas por producto.

    La correlacion depende de QUE productos se incluyen, asi que se
    reportan las tres poblaciones por separado en vez de un unico numero:

    - todos: incluye los que nadie vio y los que nadie compro. Es la mas
      honesta sobre el negocio, pero los productos sin visita aportan un
      punto (0, 0) que no es informacion de relacion.
    - visitados: quita los (0, 0). Es la que responde "si un cliente lo ve,
      lo compra".
    - visitados y vendidos: es la que calcula el pipeline A10. Es la mas
      alta de las tres y por eso NO es la que debe citarse sola: premia al
      bestseller y esconde el inventario muerto.

    Se agrega Spearman porque Pearson aqui lo distorsiona un solo producto
    con muchas unidades.
    """
    visitas = (actividad[actividad["es_visualizacion"]]
               .groupby("producto").size().rename("visitas"))
    j = pd.concat([visitas, _unidades_vendidas(fact)], axis=1)
    j.index.name = "id_producto"
    j = j.fillna(0)

    visitados = j[j["visitas"] > 0]
    visitados_y_vendidos = j[(j["visitas"] > 0) & (j["unidades"] > 0)]

    def pearson(d: pd.DataFrame) -> float:
        return float(d[["visitas", "unidades"]].corr().iloc[0, 1]) if len(d) > 2 else float("nan")

    def spearman(d: pd.DataFrame) -> float:
        return float(d[["visitas", "unidades"]].corr(method="spearman").iloc[0, 1]) \
            if len(d) > 2 else float("nan")

    filas = [
        ("Pearson (todos los productos)", pearson(j),
         "incluye los que nadie vio y los que nadie compro"),
        ("Pearson (solo visitados)", pearson(visitados),
         "responde: si lo ven, lo compran?"),
        ("Pearson (visitados y vendidos)", pearson(visitados_y_vendidos),
         "es la que calcula el pipeline A10; premia al bestseller"),
        ("Spearman (todos los productos)", spearman(j),
         "rango: inmune a los valores extremos"),
        ("Spearman (solo visitados)", spearman(visitados), ""),
        ("Productos visitados", float(len(visitados)),
         "con al menos una visualizacion"),
        ("Productos visitados y vendidos", float(len(visitados_y_vendidos)), ""),
        ("Productos sin ninguna visita", float((j["visitas"] == 0).sum()),
         "venta que la navegacion no puede explicar"),
    ]
    detalle = j.reset_index().merge(_catalogo_productos(fact, productos),
                                    on="id_producto", how="left")
    detalle = detalle.sort_values("unidades", ascending=False).reset_index(drop=True)
    return pd.DataFrame(filas, columns=["metrica", "valor", "nota"]), detalle


def inventario_muerto(actividad: pd.DataFrame, fact: pd.DataFrame,
                      productos: pd.DataFrame | None = None) -> pd.DataFrame:
    """Inversion que no convierte: mucho trafico, cero venta."""
    visitas = (actividad[actividad["es_visualizacion"]]
               .groupby("producto").size().rename("visitas"))
    j = pd.concat([visitas, _unidades_vendidas(fact)], axis=1).fillna(0)
    j.index.name = "id_producto"
    j = j.reset_index().merge(_catalogo_productos(fact, productos),
                              on="id_producto", how="left")
    return (j[j["unidades"] == 0].sort_values("visitas", ascending=False)
            .reset_index(drop=True))


def under_exposure(actividad: pd.DataFrame, fact: pd.DataFrame,
                   productos: pd.DataFrame | None = None) -> pd.DataFrame:
    """El caso inverso: se vende mucho con muy poca exposure."""
    visitas = (actividad[actividad["es_visualizacion"]]
               .groupby("producto").size().rename("visitas"))
    j = pd.concat([visitas, _unidades_vendidas(fact)], axis=1).fillna(0)
    j.index.name = "id_producto"
    j = j.reset_index().merge(_catalogo_productos(fact, productos),
                              on="id_producto", how="left")
    j["visitas_por_unidad"] = np.where(j["unidades"] > 0, j["visitas"] / j["unidades"], np.nan)
    return (j[j["unidades"] > 0].sort_values("unidades", ascending=False)
            .reset_index(drop=True))


# --------------------------------------------------------------------------
# 9. Pareto
# --------------------------------------------------------------------------
def ley_pareto(fact: pd.DataFrame) -> pd.DataFrame:
    """Curva de concentracion de la facturacion, a nivel producto.

    `acumulado_pct` es el porcentaje de venta explicado por el prefijo de
    productos ordenados por facturacion; el ultimo registro vale 100.
    """
    df = fact[fact["es_completado"]]
    g = (df.groupby(["id_producto", "producto_nombre", "categoria"])
         .agg(facturacion=("total", "sum"), unidades=("cantidad", "sum"))
         .reset_index()
         .sort_values("facturacion", ascending=False)
         .reset_index(drop=True))
    total = g["facturacion"].sum()
    g["pct_del_total"] = g["facturacion"] / total * 100 if total else np.nan
    g["acumulado_pct"] = g["pct_del_total"].cumsum()
    g["posicion"] = np.arange(1, len(g) + 1)
    g["lleva_80_pct"] = g["acumulado_pct"] >= 80
    n80 = int(g.loc[g["lleva_80_pct"], "posicion"].min()) if g["lleva_80_pct"].any() else len(g)
    g["productos_hasta_80"] = n80
    g["pct_productos_hasta_80"] = n80 / len(g) * 100 if len(g) else np.nan
    return g


# --------------------------------------------------------------------------
# 10-12. Pagos, descuentos, satisfaccion
# --------------------------------------------------------------------------
def calidad_pago(fact: pd.DataFrame) -> pd.DataFrame:
    pagos = fact.drop_duplicates("id_pedido")
    conciliados = int(pagos["conciliado"].sum())
    g = (pagos.groupby("estado_pago")
         .agg(pedidos=("id_pedido", "size"),
              monto=("monto", "sum"),
              conciliados=("conciliado", "sum"),
              diferencia=("diferencia_pago", "sum"))
         .reset_index())
    g["tasa_conciliacion_pct"] = g["conciliados"] / g["pedidos"] * 100
    g["diferencia_absoluta"] = (pagos.assign(d=pagos["diferencia_pago"].abs())
                                 .groupby("estado_pago")["d"].sum().reindex(g["estado_pago"]).values)
    return g.sort_values("pedidos", ascending=False).reset_index(drop=True)


def impacto_descuentos(fact: pd.DataFrame) -> pd.DataFrame:
    """Los descuentos se pagan con margen. Se agrupa por rango de descuento
    para ver si el descuento de 10% esta comprando volumen o solo regalando
    utilidad."""
    df = utilidad_y_margen(fact[fact["es_completado"]]).copy()
    bins = [-0.01, 0.0001, 5, 10, 20, 100]
    etiquetas = ["0%", "1-5%", "6-10%", "11-20%", ">20%"]
    df["rango_descuento"] = pd.cut(df["porcentaje_descuento"], bins=bins, labels=etiquetas)
    g = df.groupby("rango_descuento", observed=False).agg(
        lineas=("id_detalle", "size"),
        unidades=("cantidad", "sum"),
        ingreso_bruto=("ingreso_bruto", "sum"),
        descuentos=("descuento", "sum"),
        utilidad=("utilidad_bruta", "sum"),
    ).reset_index()
    g["margen_pct"] = np.where(g["ingreso_bruto"] > 0, g["utilidad"] / g["ingreso_bruto"] * 100, np.nan)
    g["descuento_pct_del_ingreso"] = np.where(g["ingreso_bruto"] > 0,
                                              g["descuentos"] / g["ingreso_bruto"] * 100, np.nan)
    return g


def satisfaccion(resenas: pd.DataFrame) -> pd.DataFrame:
    g = (resenas.groupby("calificacion")
         .agg(resenas=("id_resena", "size"),
              verificadas=("verificada", "sum"),
              positivas=("es_positiva", "sum"))
         .reset_index())
    total = len(resenas)
    g["participacion_pct"] = g["resenas"] / total * 100 if total else np.nan
    g["tasa_positiva_pct"] = g["positivas"] / g["resenas"] * 100
    return g.sort_values("calificacion").reset_index(drop=True)


def productos_valorados(resenas: pd.DataFrame, minimo: int = 5) -> pd.DataFrame:
    """Opinion por producto, exigiendo un minimo de resenas: el promedio de
    una sola resena no es una medida de nada."""
    g = (resenas.groupby(["id_producto", "producto", "categoria"])
         .agg(resenas=("id_resena", "size"),
              calificacion_promedio=("calificacion", "mean"),
              positively=("es_positiva", "sum"))
         .reset_index()
         .rename(columns={"producto": "nombre", "positively": "positivas"}))
    g = g[g["resenas"] >= minimo].copy()
    g["tasa_positiva_pct"] = g["positivas"] / g["resenas"] * 100
    return g.sort_values("calificacion_promedio", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def construir_todos(fact: pd.DataFrame, documentos: dict,
                    sucursales: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Ejecuta todos los analisis y devuelve {nombre: dataframe}.

    `viz.py` llama a esta misma funcion, de modo que grafico y CSV salen
    siempre del mismo calculo.
    """
    actividad = cargar_actividad(documentos)
    resenas = cargar_resenas(documentos)
    productos = cargar_productos(documentos)
    embudo, embudo_extra = embudo_navegacion(actividad)
    correlacion, dispersion = correlacion_navegacion_venta(actividad, fact, productos)
    segmentos = segmentacion_clientes(fact)

    return {
        "01_kpis_generales": kpis_generales(fact),
        "02_ventas_mensuales": ventas_mensuales(fact),
        "03_mix_categoria": mix_categoria(fact),
        "04_mix_canal": mix_canal(fact),
        "05_mix_region": mix_region(fact),
        "06_por_sucursal": por_sucursal(fact, sucursales),
        "07_segmentos_clientes": resumen_segmentos(segmentos),
        "08_detalle_segmentos": segmentos,
        "09_embudo_navegacion": embudo,
        "10_embudo_notas": embudo_extra,
        "11_correlacion_visitas_ventas": correlacion,
        "12_dispersion_visitas_ventas": dispersion,
        "13_inventario_muerto": inventario_muerto(actividad, fact, productos),
        "14_under_exposure": under_exposure(actividad, fact, productos),
        "15_ley_pareto": ley_pareto(fact),
        "16_calidad_pago": calidad_pago(fact),
        "17_impacto_descuentos": impacto_descuentos(fact),
        "18_satisfaccion": satisfaccion(resenas),
        "19_productos_valorados": productos_valorados(resenas),
    }


def guardar(resultados: dict[str, pd.DataFrame], destino: Path | None = None) -> list[Path]:
    destino = asegurar_dir(destino or DESTINO)
    rutas = []
    for nombre, df in resultados.items():
        ruta = destino / f"{nombre}.csv"
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        rutas.append(ruta)
    return rutas


def _resumen_markdown(resultados: dict[str, pd.DataFrame]) -> str:
    kpis = resultados["01_kpis_generales"]
    seg = resultados["07_segmentos_clientes"]
    corr = resultados["11_correlacion_visitas_ventas"]
    pareto = resultados["15_ley_pareto"]
    muertos = resultados["13_inventario_muerto"]
    lineas = [
        "# Resumen del analisis",
        "",
        "Generado automaticamente por `src/analysis.py`.",
        "",
        "## KPIs",
        "",
        "| Indicador | Valor | Nota |",
        "|---|---|---|",
    ]
    lineas += [f"| {r.indicador} | {r.valor} | {r.nota} |" for r in kpis.itertuples()]
    lineas += [
        "", "## Segmentacion de clientes", "",
        "| Segmento | Clientes | Facturacion | % del total | Regla |",
        "|---|---|---|---|---|",
    ]
    lineas += [
        f"| {r.segmento} | {r.clientes:,} | {money(r.facturacion)} | "
        f"{r.participacion_pct:.1f}% | {r.regla} |"
        for r in seg.itertuples()
    ]
    lineas += ["", "## Navegacion -> venta", "", "| Metrica | Valor | Nota |", "|---|---|---|"]
    lineas += [
        f"| {r.metrica} | {r.valor:.4f} | {r.nota} |" for r in corr.itertuples()
    ]
    n80 = int(pareto["productos_hasta_80"].iloc[0]) if len(pareto) else 0
    p80 = float(pareto["pct_productos_hasta_80"].iloc[0]) if len(pareto) else float("nan")
    lineas += [
        "", "## Concentracion", "",
        f"- **{n80} de {len(pareto)} productos** ({p80:.1f}% del catalogo vendido) "
        "explican el 80% de la facturacion.",
        f"- **{len(muertos)} productos** reciben visitas y no registran ni una venta.",
        "",
    ]
    return "\n".join(lineas)


def main() -> None:
    print(titulo("PARTE V - ANALISIS DE NEGOCIO"))
    asegurar_dir(DESTINO)
    # Los analisis se renombran entre versiones; sin borrar, el CSV viejo
    # convive con el nuevo y el reporte termina con mas analyses de los que hay.
    for viejo in DESTINO.glob("*.csv"):
        viejo.unlink()

    fact = cargar_fact()
    documentos = cargar_documentos()
    sucursales = cargar_sucursales()
    LOG.info("  Fact %s filas x %d cols | documentos: %s",
             numero(len(fact)), len(fact.columns),
             ", ".join(f"{k} {numero(len(v))}" for k, v in documentos.items()))

    resultados = construir_todos(fact, documentos, sucursales)
    rutas = guardar(resultados)
    LOG.info("  %d analisis escritos en %s", len(rutas), DESTINO)

    print(subtitulo("KPIs generales"))
    print(tabla(resultados["01_kpis_generales"]))

    print(subtitulo("Mix por categoria"))
    print(tabla(resultados["03_mix_categoria"][[
        "segmento", "facturacion", "participacion_pct", "unidades",
        "margen_pct", "ticket_promedio"]]))

    print(subtitulo("Segmentacion de clientes (RFM)"))
    print(tabla(resultados["07_segmentos_clientes"][[
        "segmento", "clientes", "facturacion", "participacion_pct",
        "frecuencia_media", "ticket_promedio"]]))

    print(subtitulo("Navegacion -> venta"))
    print(tabla(resultados["09_embudo_navegacion"]))
    print(tabla(resultados["10_embudo_notas"]))
    print(tabla(resultados["11_correlacion_visitas_ventas"]))

    print(subtitulo("Inventario muerto (visitas sin venta)"))
    print(tabla(resultados["13_inventario_muerto"].head(10)))

    markdown = DESTINO / "analisis_resumen.md"
    markdown.write_text(_resumen_markdown(resultados), encoding="utf-8")
    LOG.info("  Resumen -> %s", markdown)

    vacios = [n for n, df in resultados.items() if df.empty]
    if vacios:
        LOG.warning("  Analisis sin filas: %s", ", ".join(vacios))


if __name__ == "__main__":
    main()
