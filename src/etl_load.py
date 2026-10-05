"""PARTE II - ETAPA LOAD.  Genera los dos productos finales del punto 10.

  1. dataset_postgresql.csv  -> dataset analitico consolidado (una fila por
     linea de venta, con pedido, cliente, producto, categoria, sucursal y pago
     desnormalizados). Es lo que se carga en PostgreSQL y alimenta las 15
     consultas del punto 14.

  2. tablas/*.csv            -> los 6 CSV normalizados que pide el punto 11
     (clientes, productos, categorias, pedidos, detalle_pedido, pagos) mas
     dos dimensiones opcionales. Estos son los que se insertan con COPY.

  3. dataset_mongodb.json    -> objeto con las 3 colecciones del punto 16
     (productos, resenas, actividad_usuario), listas para insert_many().

Ademas valida que el dataset final siga cumpliendo los minimos del punto 4.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    MIN_ACTIVIDAD,
    MIN_CLIENTES,
    MIN_DETALLE_PEDIDO,
    MIN_PEDIDOS,
    MIN_PRODUCTOS,
    MIN_RESENAS,
    PROCESSED,
    REPORTS,
)
from utils import asegurar_dir, subtitulo, tabla, titulo

TABLAS_DIR = PROCESSED / "tablas"

# Orden de carga: primero las dimensiones, despues las tablas con FK.
# Este orden es el que respeta el DDL del punto 11.
ORDEN_CARGA = ["categorias", "dim_ciudades", "dim_sucursales", "clientes", "productos",
               "pedidos", "detalle_pedido", "pagos"]

# dim_sucursales no viene del catalogo de productos sino de la Fuente C
# (sucursales.xlsx), asi que su esquema vive aparte.
ESQUEMA_DIM_SUCURSALES = {
    "id_sucursal": "INTEGER", "nombre": "VARCHAR(120)", "ciudad": "VARCHAR(80)",
    "region": "VARCHAR(50)", "region_origen": "VARCHAR(50)",
    "metros_cuadrados": "INTEGER", "fecha_apertura": "DATE",
}

# Columnas que forman cada tabla normalizada y su tipo SQL destino.
ESQUEMA_SQL = {
    "categorias": {"id_categoria": "INTEGER", "nombre": "VARCHAR(80)", "descripcion": "VARCHAR(200)"},
    "dim_ciudades": {"id_ciudad": "INTEGER", "nombre": "VARCHAR(80)", "region": "VARCHAR(50)"},
    "clientes": {
        "id_cliente": "INTEGER", "nombre": "VARCHAR(160)", "correo": "VARCHAR(160)",
        "telefono": "VARCHAR(20)", "ciudad": "VARCHAR(80)", "fecha_alta": "DATE",
        "canal_registro": "VARCHAR(30)", "es_premium": "BOOLEAN", "anio_alta": "INTEGER",
        "mes_alta": "INTEGER", "antiguedad_dias": "INTEGER",
    },
    "productos": {
        "id_producto": "INTEGER", "nombre": "VARCHAR(200)", "categoria": "VARCHAR(80)",
        "id_categoria": "INTEGER", "precio": "NUMERIC(12,2)", "margen_bruto": "NUMERIC(5,4)",
        "costo_estimado": "NUMERIC(12,2)", "utilidad_bruta": "NUMERIC(12,2)",
        "rango_precio": "VARCHAR(20)", "id_proveedor": "INTEGER", "activo": "BOOLEAN",
        "fecha_lanzamiento": "DATE",
    },
    "pedidos": {
        "id_pedido": "INTEGER", "id_cliente": "INTEGER", "fecha_pedido": "DATE",
        "anio": "INTEGER", "mes": "INTEGER", "mes_nombre": "VARCHAR(15)",
        "trimestre": "INTEGER", "anio_mes": "CHAR(7)", "canal_venta": "VARCHAR(30)",
        "id_sucursal": "INTEGER", "estado": "VARCHAR(20)", "es_completado": "BOOLEAN",
        "total_pedido": "NUMERIC(14,2)", "unidades": "INTEGER", "lineas": "INTEGER",
        "categorias_distintas": "INTEGER", "ticket_promedio_linea": "NUMERIC(12,2)",
    },
    "detalle_pedido": {
        "id_detalle": "INTEGER", "id_pedido": "INTEGER", "id_producto": "INTEGER",
        "cantidad": "INTEGER", "precio_unitario": "NUMERIC(12,2)", "descuento": "NUMERIC(12,2)",
        "subtotal": "NUMERIC(14,2)", "total": "NUMERIC(14,2)", "porcentaje_descuento": "NUMERIC(5,2)",
    },
    "pagos": {
        "id_pago": "INTEGER", "id_pedido": "INTEGER", "metodo": "VARCHAR(30)",
        "monto": "NUMERIC(14,2)", "fecha_pago": "DATE", "estado_pago": "VARCHAR(20)",
        "diferencia_pago": "NUMERIC(14,2)", "conciliado": "BOOLEAN",
    },
}

DESC_CATEGORIA = {
    "Computadoras": "Equipos de computo: laptops, desktops, workstations",
    "Smartphones": "Telefonos inteligentes y tablets",
    "Audio": "Audifonos, bocinas y equipo de sonido",
    "Monitores": "Monitores, pantallas y video",
    "Accesorios": "Perifericos de computo",
    "Redes": "Routers, switches y conectividad",
}

REGION_CIUDAD = {
    "Veracruz": "Sureste", "Merida": "Sureste", "Cancun": "Sureste",
    "Ciudad de Mexico": "Centro", "Puebla": "Centro", "Queretaro": "Centro",
    "Guadalajara": "Occidente", "Leon": "Occidente",
    "Monterrey": "Norte", "Tijuana": "Norte",
}


# ==========================================================================
# Dimensiones derivadas de las columnas desnormalizadas
# ==========================================================================
def construir_categorias(productos: pd.DataFrame) -> pd.DataFrame:
    """Tabla `categorias`: clave primaria surrogada + nombre unico.

    Es la tabla que hace cumplir la 3FN: `productos` guarda la FK
    id_categoria y el texto de la categoria vive en un solo lugar.
    """
    nombres = sorted(p for p in productos["categoria"].dropna().unique() if p != "Sin Categoria")
    return pd.DataFrame(
        {
            "id_categoria": range(1, len(nombres) + 1),
            "nombre": nombres,
            "descripcion": [DESC_CATEGORIA.get(n, f"Categoria {n}") for n in nombres],
        }
    )


def construir_dim_ciudades(clientes: pd.DataFrame) -> pd.DataFrame:
    nombres = sorted(p for p in clientes["ciudad"].dropna().unique() if p != "Sin Ciudad")
    return pd.DataFrame(
        {
            "id_ciudad": range(1, len(nombres) + 1),
            "nombre": nombres,
            "region": [REGION_CIUDAD.get(n, "Nacional") for n in nombres],
        }
    )


def construir_dim_sucursales(sucursales: pd.DataFrame) -> pd.DataFrame:
    """Tabla `dim_sucursales`: destino de la FK pedidos.id_sucursal.

    El `region` de la fuente cruda esta sucio (el generador lo asigna al azar:
    Veracruz aparece como "Norte" y Guadalajara como "Centro"), asi que se
    sobrescribe con el catalogo canonico REGION_CIUDAD y se conserva el valor
    crudo en `region_origen` para que la discrepancia quede documentada.
    """
    if sucursales.empty or "id_sucursal" not in sucursales.columns:
        return pd.DataFrame(columns=["id_sucursal", "nombre", "ciudad", "region",
                                     "region_origen", "metros_cuadrados",
                                     "fecha_apertura"])
    df = sucursales.copy()
    df["region_origen"] = df.get("region")
    df["region"] = df["ciudad"].map(REGION_CIUDAD).fillna("Nacional")
    df = df.rename(columns={"fecha_apertura": "fecha_apertura"})
    df = df.sort_values("id_sucursal").reset_index(drop=True)
    return df[["id_sucursal", "nombre", "ciudad", "region", "region_origen",
               "metros_cuadrados", "fecha_apertura"]]


# ==========================================================================
# Tablas normalizadas
# ==========================================================================
def construir_tablas(d: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    categorias = construir_categorias(d["productos"])
    ciudades = construir_dim_ciudades(d["clientes"])
    sucursales = construir_dim_sucursales(d.get("sucursales", pd.DataFrame()))

    clientes = d["clientes"].rename(
        columns={"anio": "anio_alta", "mes": "mes_alta"}
    ).copy()

    productos = d["productos"].copy()
    productos = productos.merge(
        categorias.rename(columns={"nombre": "categoria"}),
        on="categoria", how="left",
    )

    pedidos = d["pedidos"].copy()

    detalle = d["detalle_pedido"].copy()

    pagos = d["pagos"].drop(columns=[c for c in ["pago_anio", "pago_mes", "pago_dia",
                                                "pago_mes_nombre", "pago_trimestre",
                                                "pago_anio_mes"] if c in d["pagos"].columns])
    pagos = pagos.merge(
        pedidos[["id_pedido", "anio", "mes", "mes_nombre", "trimestre", "anio_mes"]],
        on="id_pedido", how="left",
    )

    tablas = {
        "categorias": categorias,
        "dim_ciudades": ciudades,
        "dim_sucursales": sucursales,
        "clientes": clientes,
        "productos": productos,
        "pedidos": pedidos,
        "detalle_pedido": detalle,
        "pagos": pagos,
    }

    # Se recorta cada tabla a las columnas del esquema SQL declarado.
    salida = {}
    for nombre, df in tablas.items():
        if nombre == "dim_sucursales":
            salida[nombre] = df.copy()
            continue
        cols = [c for c in ESQUEMA_SQL[nombre] if c in df.columns]
        salida[nombre] = df[cols].copy()
    return salida


# ==========================================================================
# Dataset consolidado para PostgreSQL
# ==========================================================================
def construir_dataset_postgresql(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Dataset analitico: una fila por linea de venta.

    Es un desnormalizado INTENCIONAL: es la vista que usaria Business
    Intelligence para no escribir JOINs en cada grafico. La 3FN se mantiene
    en las tablas de arriba; aqui se acepta la redundancia a cambio de
    velocidad de consulta.

    Cada dimension se une YA con su nombre renombrado, para que el CSV no
    tenga columnas ambiguas del tipo nombre_x / nombre_y.
    """
    d = tablas["detalle_pedido"]
    pedidos = tablas["pedidos"]
    clientes = tablas["clientes"]
    productos = tablas["productos"]
    categorias = tablas["categorias"]
    ciudades = tablas["dim_ciudades"]
    pagos = tablas["pagos"]

    df = d.merge(
        pedidos[["id_pedido", "id_cliente", "fecha_pedido", "anio", "mes", "mes_nombre",
                 "trimestre", "anio_mes", "canal_venta", "id_sucursal", "estado",
                 "es_completado", "total_pedido", "unidades", "lineas",
                 "categorias_distintas", "ticket_promedio_linea"]],
        on="id_pedido", how="inner",
    )
    df = df.merge(
        clientes[["id_cliente", "nombre", "correo", "ciudad", "fecha_alta",
                  "canal_registro", "es_premium"]].rename(
            columns={"nombre": "cliente_nombre", "ciudad": "ciudad_cliente",
                     "fecha_alta": "fecha_alta_cliente"}),
        on="id_cliente", how="inner",
    )
    df = df.merge(
        productos[["id_producto", "nombre", "categoria", "id_categoria", "precio",
                   "margen_bruto", "costo_estimado", "utilidad_bruta", "rango_precio"]]
        .rename(columns={"nombre": "producto_nombre", "precio": "precio_lista",
                         "margen_bruto": "margen_bruto_producto"}),
        on="id_producto", how="inner",
    )
    df = df.merge(
        categorias.rename(columns={"nombre": "descripcion_categoria"}),
        on="id_categoria", how="left",
    )
    # LEFT JOIN a proposito: si la ciudad no esta en la dimension (p.ej.
    # "Sin Ciudad"), la venta se conserva igual.
    df = df.merge(
        ciudades.rename(columns={"nombre": "ciudad"}),
        left_on="ciudad_cliente", right_on="ciudad", how="left",
    )
    df = df.merge(
        pagos[["id_pedido", "metodo", "monto", "estado_pago", "diferencia_pago", "conciliado"]],
        on="id_pedido", how="left",
    )

    orden = [
        "id_detalle", "id_pedido", "id_cliente", "id_producto", "id_categoria",
        "id_sucursal", "fecha_pedido", "anio", "mes", "mes_nombre", "trimestre", "anio_mes",
        "cliente_nombre", "correo", "ciudad", "region", "canal_registro", "es_premium",
        "fecha_alta_cliente", "producto_nombre", "categoria", "descripcion_categoria",
        "rango_precio", "precio_lista", "margen_bruto_producto", "costo_estimado",
        "utilidad_bruta", "cantidad", "precio_unitario", "descuento", "porcentaje_descuento",
        "subtotal", "total", "canal_venta", "estado", "es_completado",
        "total_pedido", "unidades", "lineas", "categorias_distintas", "ticket_promedio_linea",
        "metodo", "monto", "estado_pago", "diferencia_pago", "conciliado",
    ]
    finales = [c for c in orden if c in df.columns]
    # Los JOIN dejan columnas que ya estan representadas arriba
    # (ciudad_cliente == ciudad, descripcion == descripcion_categoria). Se
    # eliminan para no duplicar el mismo dato en el CSV entregable.
    redundantes = {"ciudad_cliente", "descripcion"}
    extras = [
        c for c in df.columns
        if c not in finales and c not in redundantes
    ]
    df = df[finales + extras]

    # Los nulos categoricos NO se imputan (inventar un canal de venta que no
    # consta falsearia el dato), pero en la capa analitica se etiquetan para
    # que ninguna consulta los descarte en silencio ni los mezcle con un canal
    # real. Siguen documentados como faltantes en el reporte de calidad (T02).
    for col, etiqueta in [("canal_venta", "Sin Canal"), ("estado", "Sin Estado"),
                          ("metodo", "Sin Metodo"), ("ciudad", "Sin Ciudad"),
                          ("region", "Sin Region")]:
        if col in df.columns:
            nulos = int(df[col].isna().sum())
            if nulos:
                df[col] = df[col].fillna(etiqueta)
    return df.reset_index(drop=True)


# ==========================================================================
# Dataset para MongoDB
# ==========================================================================
def _fecha_iso(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return pd.Timestamp(v).strftime("%Y-%m-%d")


def _fecha_hora_iso(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return pd.Timestamp(v).strftime("%Y-%m-%dT%H:%M:%S")


def _limpiar_json(v, por_defecto=None):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return por_defecto
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v


def _num(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    # json.loads entrega int/float nativos; json_normalize entrega np.floating.
    # BSON distingue int de double, asi que 4.0 -> 4.
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        if pd.isna(v):
            return None
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 2**53 else f
    return v


def _limpiar_atributos(v) -> dict:
    """Subdocumento `atributos` con tipos BSON correctos."""
    datos = _limpiar_json(v, {})
    if not isinstance(datos, dict):
        return {}
    salida = {}
    for k, val in datos.items():
        if isinstance(val, str):
            # "SI"/"NO" textual llega como bool desde json_normalize
            salida[k] = val.strip()
        else:
            salida[k] = _num(val)
    return salida


def construir_documentos_mongo(
    d: dict[str, pd.DataFrame], tablas: dict[str, pd.DataFrame]
) -> dict[str, list[dict]]:
    """3 colecciones con la forma exacta del punto 16-18 del enunciado."""
    clientes = tablas["clientes"].set_index("id_cliente")
    productos = tablas["productos"].set_index("id_producto")
    ids_validos = set(productos.index)

    # ---- productos: con atributos variables como subdocumento ----
    docs_productos = []
    for _, r in d["productos_semi"].iterrows():
        if r["id_producto"] not in ids_validos:
            continue
        etiquetas = _limpiar_json(r.get("etiquetas"), [])
        if isinstance(etiquetas, str):
            etiquetas = [etiquetas]
        atributos = _limpiar_atributos(r.get("atributos"))
        p = productos.loc[r["id_producto"]]
        docs_productos.append(
            {
                "id_producto": int(r["id_producto"]),
                "nombre": r["nombre"],
                "categoria": r["categoria"],
                "precio": float(p["precio"]),
                "margen_bruto": float(p["margen_bruto"]),
                "rango_precio": p["rango_precio"],
                # Subdocumento de esquema variable: la razon de usar MongoDB
                "atributos": atributos,
                "etiquetas": etiquetas,
                "disponible": bool(r.get("disponible", True)),
                "fecha_registro": _fecha_iso(r.get("fecha_registro")),
            }
        )

    # ---- resenas: el cliente va incrustado (denormalizado a proposito) ----
    docs_resenas = []
    for _, r in d["resenas"].iterrows():
        cid = int(r["cliente.id"])
        nombre_cliente = clientes.loc[cid, "nombre"] if cid in clientes.index else "Desconocido"
        docs_resenas.append(
            {
                "id_resena": int(r["id_resena"]),
                "id_producto": int(r["id_producto"]),
                "cliente": {"id": cid, "nombre": nombre_cliente},
                "producto": productos.loc[r["id_producto"], "nombre"]
                if r["id_producto"] in productos.index else None,
                "categoria": productos.loc[r["id_producto"], "categoria"]
                if r["id_producto"] in productos.index else None,
                "calificacion": int(r["calificacion"]),
                "comentario": r["comentario"],
                "verificada": bool(r["verificada"]),
                "fecha": _fecha_iso(r["fecha"]),
                "es_positiva": bool(r["es_positiva"]),
            }
        )

    # ---- actividad_usuario: eventos de navegacion ----
    docs_actividad = []
    for _, r in d["actividad"].iterrows():
        docs_actividad.append(
            {
                "usuario": int(r["usuario"]),
                "ciudad_usuario": clientes.loc[int(r["usuario"]), "ciudad"]
                if int(r["usuario"]) in clientes.index else "Sin Ciudad",
                "fecha": _fecha_hora_iso(r["fecha_hora"]),
                "evento": r["evento"],
                "producto": int(r["producto"]),
                "nombre_producto": productos.loc[int(r["producto"]), "nombre"]
                if int(r["producto"]) in productos.index else None,
                "categoria": productos.loc[int(r["producto"]), "categoria"]
                if int(r["producto"]) in productos.index else None,
                "dispositivo": r["dispositivo"],
                "ubicacion": r["ubicacion"],
                "duracion_seg": _num(r["duracion_seg"]),
                "hora": _num(r["hora"]),
                # Campos derivados de T10: permiten indexar y filtrar por
                # navegacion sin recomputar en el cliente (punto 22 delMongo).
                "es_visualizacion": bool(r["es_visualizacion"]),
                "anio": int(r["anio"]),
                "mes": int(r["mes"]),
                "trimestre": str(r["trimestre"]),
                "anio_mes": str(r["anio_mes"]),
            }
        )

    return {
        "productos": docs_productos,
        "resenas": docs_resenas,
        "actividad_usuario": docs_actividad,
    }


# ==========================================================================
# Validacion de minimos (punto 4)
# ==========================================================================
def validar_minimos(
    tablas: dict[str, pd.DataFrame], documentos: dict[str, list[dict]]
) -> pd.DataFrame:
    """Comprueba que el dataset FINAL cumple los minimos del punto 4."""
    filas = [
        ("Clientes", "clientes", MIN_CLIENTES, len(tablas["clientes"])),
        ("Productos", "productos", MIN_PRODUCTOS, len(tablas["productos"])),
        ("Pedidos", "pedidos", MIN_PEDIDOS, len(tablas["pedidos"])),
        ("Detalles de pedidos", "detalle_pedido", MIN_DETALLE_PEDIDO, len(tablas["detalle_pedido"])),
        ("Resenas", "resenas (mongodb)", MIN_RESENAS, len(documentos["resenas"])),
        ("Registros de navegacion", "actividad_usuario (mongodb)", MIN_ACTIVIDAD,
         len(documentos["actividad_usuario"])),
    ]
    df = pd.DataFrame(
        [
            {
                "informacion": info,
                "destino": destino,
                "minimo_requerido": minimo,
                "registros_finales": n,
                "cumple": "SI" if n >= minimo else "NO",
                "holgura": n - minimo,
                "veces_el_minimo": round(n / minimo, 2),
            }
            for info, destino, minimo, n in filas
        ]
    )
    return df


def perfilar(df: pd.DataFrame, destino: str) -> pd.DataFrame:
    """Perfil de columnas: tipo, nulos, distintos, min, max."""
    filas = []
    for col in df.columns:
        s = df[col]
        filas.append(
            {
                "destino": destino,
                "columna": col,
                "tipo_sql": str(s.dtype),
                "no_nulos": int(s.notna().sum()),
                "nulos": int(s.isna().sum()),
                "valores_distintos": int(s.nunique(dropna=True)),
                "min": str(s.min())[:40] if s.notna().any() else "",
                "max": str(s.max())[:40] if s.notna().any() else "",
            }
        )
    return pd.DataFrame(filas)


# ==========================================================================
def cargar(d: dict[str, pd.DataFrame]) -> dict[str, Path]:
    print(titulo("PARTE II / ETAPA 3 - LOAD  (productos finales)"))
    asegurar_dir(PROCESSED)
    asegurar_dir(TABLAS_DIR)
    asegurar_dir(REPORTS)

    # ---------------- PostgreSQL ----------------
    tablas = construir_tablas(d)
    print("\nTablas normalizadas para el DDL del punto 11 "
          "(orden de carga respetando las FK):\n")
    for nombre in ORDEN_CARGA:
        df = tablas[nombre]
        ruta = TABLAS_DIR / f"{nombre}.csv"
        df.to_csv(ruta, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
        print(f"   {nombre:<16} {len(df):>7,} filas x {df.shape[1]:>2} cols  ->  {ruta.name}")

    dataset_pg = construir_dataset_postgresql(tablas)
    ruta_pg = PROCESSED / "dataset_postgresql.csv"
    dataset_pg.to_csv(ruta_pg, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    print(f"\n   dataset_postgresql.csv (consolidado)  {len(dataset_pg):>7,} filas x "
          f"{dataset_pg.shape[1]} cols")

    # ---------------- MongoDB ----------------
    documentos = construir_documentos_mongo(d, tablas)
    ruta_mongo = PROCESSED / "dataset_mongodb.json"
    ruta_mongo.write_text(
        json.dumps(documentos, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("\nColecciones NoSQL (listas para insert_many):\n")
    for col, docs in documentos.items():
        ejemplo = json.dumps(docs[0], ensure_ascii=False)[:150] if docs else ""
        print(f"   {col:<20} {len(docs):>7,} documentos")
    print(f"\n   dataset_mongodb.json  ->  {ruta_mongo.name}")

    # ejemplo legible de un producto con atributos variables
    if documentos["productos"]:
        muestra = json.dumps(documentos["productos"][0], ensure_ascii=False, indent=2)
        (REPORTS / "ejemplo_documento_producto.json").write_text(muestra, encoding="utf-8")

    # ---------------- Reportes ----------------
    minimos = validar_minimos(tablas, documentos)
    ruta_min = REPORTS / "validacion_minimos.csv"
    minimos.to_csv(ruta_min, index=False, encoding="utf-8-sig")

    perfiles = [perfilar(dataset_pg, "dataset_postgresql.csv")]
    for nombre in ORDEN_CARGA:
        perfiles.append(perfilar(tablas[nombre], f"tablas/{nombre}.csv"))
    pd.concat(perfiles, ignore_index=True).to_csv(
        REPORTS / "perfil_columnas.csv", index=False, encoding="utf-8-sig"
    )

    print(subtitulo("VALIDACION DE MINIMOS (punto 4)"))
    print(tabla(minimos))
    if (minimos["cumple"] == "NO").any():
        raise RuntimeError(
            "El dataset final NO cumple los minimos del punto 4:\n"
            + minimos[minimos["cumple"] == "NO"].to_string()
        )
    print(f"\n  Todos los minimos del punto 4 se cumplen. Evidencia: {ruta_min.name}")

    # Un ejemplo de documento, para la defensa oral
    if documentos["productos"]:
        print("\n  Documento de la coleccion 'productos' (subdocumento 'atributos'):\n")
        print("   " + json.dumps(documentos["productos"][0], ensure_ascii=False, indent=2)
              .replace("\n", "\n   "))

    return {
        "dataset_postgresql": ruta_pg,
        "dataset_mongodb": ruta_mongo,
        "validacion_minimos": ruta_min,
        "tablas": TABLAS_DIR,
    }


if __name__ == "__main__":
    from etl_extract import extraer
    from etl_transform import transformar

    d, tracker = transformar(extraer())
    rutas = cargar(d)
    tracker.guardar()