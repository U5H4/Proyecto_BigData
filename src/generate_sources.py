"""Generador de las tres fuentes crudas (PARTE I) con errores intencionales.

Fuente A -> CSV   : clientes, productos, pedidos, detalle_pedido, pagos
Fuente B -> JSON  : productos_semiestructurados, resenas, actividad_usuario
Fuente C -> Sheets: sucursales, proveedores, promociones, objetivos_venta  (.xlsx)

Las inconsistencias del punto 7 se inyectan aqui a proposito; el ETL debe
corregirlas. Ver README.md -> "Inconsistencias inyectadas".
"""

from __future__ import annotations

import itertools
import json
import random
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    ATRIBUTOS_VARIABLES,
    CATEGORIAS,
    CIUDADES,
    DISPOSITIVOS,
    EVENTOS,
    FECHA_FIN,
    FECHA_INICIO,
    LOGS,
    MARCAS,
    N_ACTIVIDAD,
    N_CLIENTES,
    N_DETALLE_PEDIDO,
    N_PEDIDOS,
    N_PRODUCTOS,
    N_PROMOCIONES,
    N_PROVEEDORES,
    N_RESENAS,
    N_SUCURSALES,
    PLANTILLAS_PRODUCTO,
    RAW_CSV,
    RAW_JSON,
    RAW_SHEETS,
    RUBROS_PROVEEDOR,
    SEED,
)
from utils import asegurar_dir, setup_logging, titulo

LOG = setup_logging("generate_sources")

NOMBRES = [
    "Ana", "Luis", "Maria", "Carlos", "Sofia", "Miguel", "Valeria", "Diego",
    "Camila", "Andres", "Fernanda", "Ricardo", "Daniela", "Javier", "Paola",
    "Hector", "Regina", "Oscar", "Diana", "Ernesto", "Gabriela", "Raul",
    "Leticia", "Sergio", "Alejandra", "Alberto", "Norma", "Guillermo",
    "Lorena", "Victor", "Abril", "Emmanuel", "Itzel", "Rodrigo", "Natalia",
    "Julio", "Briana", "Alonso", "Ximena", "Gerardo", "Renata", "Leandro",
    "Mariana", "Octavio", "Paulina", "Ignacio", "Citlali", "Emiliano", "Samantha",
]

APELLIDOS = [
    "Perez", "Hernandez", "Garcia", "Martinez", "Lopez", "Gonzalez", "Rodriguez",
    "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz",
    "Cruz", "Morales", "Ortiz", "Jimenez", "Ruiz", "Alvarez", "Castillo",
    "Vargas", "Mendez", "Reyes", "Guerrero", "Iglesias", "Molina", "Delgado",
    "Aguilar", "Rojas", "Contreras", "Herrera", "Bautista", "Navarro", "Campos",
    "Salazar", "Lozano", "Solis", "Vega", "Rendon", "Cardona", "Pineda",
]

MODELOS = [
    "Neo", "Prime", "Elite", "Air", "Max", "Plus", "Lite", "Ultra", "Core",
    "Edge", "Zen", "Pro", "GT", "SE", "Mini", "Fury", "Pulse", "Nova",
    "Vertex", "One",
]

PRECIOS_RANGO = {
    "Computadoras": (12_000, 68_000),
    "Smartphones": (3_500, 42_000),
    "Audio": (400, 9_500),
    "Monitores": (1_800, 28_000),
    "Accesorios": (150, 4_200),
    "Redes": (550, 18_500),
}

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
    12: "diciembre",
}

DOMINIOS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com.mx", "novatech.mx"]


# ==========================================================================
# Helpers para ensuciar datos
# ==========================================================================
def clave(texto: str) -> str:
    """Normaliza para comparar: sin acentos, minusculas, sin espacios extra."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def precio_como_texto(valor: float, rng: random.Random) -> str:
    """Devuelve el precio en una de las representaciones "sucias" del enunciado."""
    estilo = rng.choice(["plano", "simbolo", "simbolo_miles", "espacios", "decimal_coma", "sufijo"])
    if estilo == "plano":
        return f"{valor:.2f}"
    if estilo == "simbolo":
        return f"${valor:.2f}"
    if estilo == "simbolo_miles":
        return f"${valor:,.0f}"
    if estilo == "espacios":
        return f"  {valor:.2f}  "
    if estilo == "decimal_coma":
        return f"{valor:.2f}".replace(".", ",")
    return f"{valor:.2f} MXN"


def fecha_como_texto(fecha: pd.Timestamp, rng: random.Random) -> str:
    """Devuelve la fecha en uno de los 7 formatos requeridos."""
    estilo = rng.choice(
        ["iso", "iso", "dia_mes_anio", "mes_dia_anio", "guion", "texto_es", "timestamp"]
    )
    if estilo == "iso":
        return fecha.strftime("%Y-%m-%d")
    if estilo == "dia_mes_anio":
        return fecha.strftime("%d/%m/%Y")
    if estilo == "mes_dia_anio":
        return fecha.strftime("%m/%d/%Y")
    if estilo == "guion":
        return fecha.strftime("%d-%m-%Y")
    if estilo == "texto_es":
        return f"{fecha.day} de {MESES_ES[fecha.month]} de {fecha.year}"
    return f"{fecha.strftime('%Y-%m-%d')} 00:00:00"


def ciudad_sucia(canonica: str, rng: random.Random) -> str:
    return rng.choice(CIUDADES[canonica])


def categoria_sucia(canonica: str, rng: random.Random) -> str:
    return rng.choice(CATEGORIAS[canonica])


def nulos(df: pd.DataFrame, indices, claves: list[str], prob: float, rng: random.Random) -> int:
    """Pone None / vacio / 'N/A' en algunas celdas de df (modifica in place).

    Devuelve cuantas celdas quedaron sucias.
    """
    modificadas = 0
    for i in indices:
        for c in claves:
            if c in df.columns and rng.random() < prob:
                df.at[i, c] = rng.choice([None, "", "N/A", "null", "NULL", "-"])
                modificadas += 1
    return modificadas


# ==========================================================================
# Catalogo maestro de productos (compartido por CSV y JSON)
# ==========================================================================
def construir_catalogo(rng: random.Random) -> pd.DataFrame:
    """Genera N_PRODUCTOS productos unicos y deterministas.

    Devuelve el catalogo LIMPIO (este dataframe no se ensucia aqui; el
    ensuciamiento ocurre al escribir cada fuente).
    """
    combinaciones = list(itertools.product(MARCAS, MODELOS))
    registros = []
    id_producto = 0

    categorias = list(PLANTILLAS_PRODUCTO)
    # Reparto proporcional: 500 productos entre 6 categorias.
    base = N_PRODUCTOS // len(categorias)
    reparto = {c: base for c in categorias}
    for i in range(N_PRODUCTOS - base * len(categorias)):
        reparto[categorias[i % len(categorias)]] += 1

    contador = itertools.cycle(range(len(combinaciones)))

    for categoria, total in reparto.items():
        plantillas = PLANTILLAS_PRODUCTO[categoria]
        familias = ATRIBUTOS_VARIABLES[categoria]
        minimo, maximo = PRECIOS_RANGO[categoria]

        for k in range(total):
            id_producto += 1
            marca, modelo = combinaciones[next(contador)]
            nombre = plantillas[k % len(plantillas)].format(marca=marca, modelo=modelo)

            # Precio con distribucion sesgada hacia la parte baja del rango.
            base_precio = np.exp(rng.uniform(np.log(minimo), np.log(maximo)))
            jitter = rng.uniform(0.9, 1.1)
            precio = round(min(maximo, max(minimo, base_precio * jitter)), 2)

            # Variante de atributos: indice de la sub-familia + sub-indice.
            idx = k % len(familias)
            sub = k % max(2, len(plantillas))
            variantes = [v for v in range(len(familias)) if v != idx]
            familia_idx = idx if sub % 2 == 0 else rng.choice(variantes)

            registros.append(
                {
                    "id_producto": id_producto,
                    "nombre": nombre,
                    "categoria": categoria,
                    "precio": precio,
                    "id_proveedor": 0,  # se asigna luego
                    "_familia": familia_idx,
                    "_sub": sub,
                    "_margen": round(rng.uniform(0.18, 0.42), 4),
                    # Interes latente de demanda. Es la variable que hace que
                    # un producto se venda mucho mas que otro, y la que despues
                    # se usara para que las VISITAS correlacionen (no al azar)
                    # con las ventas de la Parte V.
                    "_demanda": rng.lognormvariate(0.0, 0.9),
                }
            )

    df = pd.DataFrame(registros)

    # Proveedor coherente con el rubro de cada categoria (1 proveedor x rubro).
    proveedores_por_rubro = {
        "Tecnologia / Cómputo": [1, 6],
        "Tecnología / Dispositivos móviles": [2, 7],
        "Electrónica / Audio": [3, 8],
        "Electrónica / Video": [4, 9],
        "Accesorios de Cómputo": [5, 10],
        "Networking / Telecomunicaciones": [6, 2],
    }
    df["id_proveedor"] = df["categoria"].map(
        lambda c: rng.choice(proveedores_por_rubro[RUBROS_PROVEEDOR[c]])
    )

    return df.sort_values("id_producto").reset_index(drop=True)


def construir_atributos(catalogo: pd.DataFrame, rng: random.Random) -> list[dict]:
    """Genera el documento semiestructurado de cada producto (Fuente B)."""
    documentos = []
    for _, row in catalogo.iterrows():
        familia = ATRIBUTOS_VARIABLES[row["categoria"]][row["_familia"]]
        atributos: dict[str, object] = {}
        for clave_attr, opciones in familia.items():
            valor = rng.choice(opciones)
            atributos[clave_attr] = valor
        documentos.append(
            {
                "id_producto": int(row["id_producto"]),
                "nombre": row["nombre"],
                "categoria": row["categoria"],
                "_atributos": atributos,
                "_margen": row["_margen"],
            }
        )
    return documentos


# ==========================================================================
# FUENTE A -> CSV
# ==========================================================================
def fuente_clientes(rng: random.Random) -> Path:
    canonicas = list(CIUDADES)
    filas = []
    for i in range(1, N_CLIENTES + 1):
        nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"
        apellido = nombre.split(" ")[-1]
        correo = f"{clave(nombre).replace(' ', '.')}@{rng.choice(DOMINIOS)}"
        alta = pd.Timestamp(FECHA_INICIO) + pd.Timedelta(days=rng.randint(0, 600))
        fila = {
            "id_cliente": i,
            "nombre": nombre,
            "correo": correo,
            "telefono": f"55{rng.randint(1000, 9999)}{rng.randint(1000, 9999)}",
            "ciudad": ciudad_sucia(rng.choice(canonicas), rng),
            "fecha_alta": fecha_como_texto(alta, rng),
            "canal_registro": rng.choice(["web", "app_movil", "tienda_fisica"]),
            "es_premium": rng.choice(["true", "false", "TRUE", "False", "Si", "No", "1", "0"]),
            # Columnas innecesarias (transformacion 9)
            "telefono_secundario": f"55{rng.randint(1000, 9999)}{rng.randint(1000, 9999)}",
            "fax": f"55{rng.randint(1000, 9999)}",
            "codigo_interno_legacy": f"LEG-{rng.randint(10000, 99999)}",
            "usuario_sistema": rng.choice(["", None, f"usr_{i}"]),
        }
        filas.append(fila)

    df = pd.DataFrame(filas)

    # --- Inyeccion de inconsistencias ---
    # Nulos
    nulos(df, df.index[: int(N_CLIENTES * 0.06)], ["telefono"], 0.35, rng)
    nulos(df, df.index[: int(N_CLIENTES * 0.03)], ["correo"], 0.25, rng)

    # Mayusculas/minusculas inconsistentes en el nombre (mismo cliente, dos formas)
    idx = df.sample(int(N_CLIENTES * 0.12), random_state=SEED).index
    for i in idx:
        estilo = rng.choice(["upper", "lower", "title"])
        if estilo == "upper":
            df.at[i, "nombre"] = df.at[i, "nombre"].upper()
        elif estilo == "lower":
            df.at[i, "nombre"] = str(df.at[i, "nombre"]).lower()
        else:
            df.at[i, "nombre"] = str(df.at[i, "nombre"]).title()

    # Duplicados exactos (mismo id_cliente) -> transformacion 1
    duplicados = df.sample(int(N_CLIENTES * 0.04), random_state=SEED + 1)
    df = pd.concat([df, duplicados], ignore_index=True)

    # Duplicados "reales": mismo nombre+correo, id distinto (mismo cliente dado
    # de alta dos veces por error de la app movil)
    idx = df.sample(int(len(df) * 0.03), random_state=SEED + 2).index
    for i in idx:
        df.loc[len(df)] = df.loc[i]
        df.at[len(df) - 1, "id_cliente"] = df["id_cliente"].max() + 1

    # Filas irrecuperables: id_cliente no numerico
    df.loc[len(df)] = {
        "id_cliente": "NULL",
        "nombre": "Registro Sin Identificador",
        "correo": None,
        "telefono": None,
        "ciudad": "CDMX",
        "fecha_alta": None,
        "canal_registro": "web",
        "es_premium": "No",
        "telefono_secundario": None,
        "fax": None,
        "codigo_interno_legacy": None,
        "usuario_sistema": None,
    }

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ruta = asegurar_dir(RAW_CSV) / "clientes.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    LOG.info("Fuente A  clientes.csv        %6d filas x %2d cols", len(df), df.shape[1])
    return ruta


def fuente_productos(catalogo: pd.DataFrame, rng: random.Random) -> Path:
    df = catalogo.rename(columns={"_margen": "margen_bruto"}).drop(columns=["_familia", "_sub"])
    df["margen_bruto"] = df["margen_bruto"].astype(str)  # texto en la fuente cruda

    filas = []
    for _, row in df.iterrows():
        filas.append(
            {
                "id_producto": row["id_producto"],
                "nombre": row["nombre"],
                "categoria": categoria_sucia(row["categoria"], rng),
                "precio": precio_como_texto(row["precio"], rng),
                "id_proveedor": row["id_proveedor"],
                "margen_bruto": row["margen_bruto"],
                "activo": rng.choice(["true", "false", "Si", "No", "1", "0", "TRUE"]),
                "fecha_lanzamiento": fecha_como_texto(
                    pd.Timestamp(FECHA_INICIO) + pd.Timedelta(days=rng.randint(0, 400)), rng
                ),
                # Columnas innecesarias
                "costo_fabricacion_interno": f"{rng.uniform(0.4, 0.8) * row['precio']:.2f}",
                "sku_fabricante_obsoleto": f"SKU{rng.randint(10000, 99999)}",
                "peso_envio_kg_bruto": round(rng.uniform(0.1, 12.0), 2),
            }
        )
    df = pd.DataFrame(filas)

    # Precios no numericos (irrecuperables -> se descartan en el ETL)
    for i in df.sample(int(N_PRODUCTOS * 0.01), random_state=SEED + 3).index:
        df.at[i, "precio"] = rng.choice(["N/D", "consultar", "sin precio", "#VALOR!"])

    # Nulos
    nulos(df, df.index[: int(N_PRODUCTOS * 0.04)], ["nombre"], 0.3, rng)
    nulos(df, df.index[: int(N_PRODUCTOS * 0.05)], ["margen_bruto"], 0.4, rng)

    # Duplicados
    df = pd.concat([df, df.sample(int(N_PRODUCTOS * 0.035), random_state=SEED + 4)], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    ruta = asegurar_dir(RAW_CSV) / "productos.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    LOG.info("Fuente A  productos.csv       %6d filas x %2d cols", len(df), df.shape[1])
    return ruta


def fuente_pedidos(rng: random.Random) -> Path:
    inicio, fin = pd.Timestamp(FECHA_INICIO), pd.Timestamp(FECHA_FIN)
    filas = []
    for i in range(1, N_PEDIDOS + 1):
        fecha = inicio + pd.Timedelta(
            days=int(rng.random() ** 0.85 * (fin - inicio).days)
        )
        filas.append(
            {
                "id_pedido": i,
                "fecha_pedido": fecha_como_texto(fecha, rng),
                "id_cliente": rng.randint(1, N_CLIENTES + 1),
                "canal_venta": rng.choice(["web", "app_movil", "tienda_fisica"]),
                "id_sucursal": rng.randint(1, N_SUCURSALES),
                "estado": rng.choice(
                    ["completado", "completado", "completado", "enviado", "pendiente", "cancelado"]
                ),
                # Columnas innecesarias
                "referencia_bancaria": f"REF{rng.randint(100000, 999999)}",
                "cupon_descuento_raw": rng.choice(["", None, "VERANO10", "NAVIDAD15"]),
                "hora_impresion_ticket": rng.choice(["", None, "2024-06-01 12:00"]),
            }
        )
    df = pd.DataFrame(filas)

    nulos(df, df.index[: int(N_PEDIDOS * 0.03)], ["canal_venta"], 0.3, rng)
    # Orden importante: primero las referencias huerfanas, DESPUES los
    # duplicados. Si se invirtiera, dos copias identicas de la misma fila
    # dejarian de ser identicas y sobrevivirian con el mismo id_pedido.
    for i in df.sample(int(len(df) * 0.01), random_state=SEED + 6).index:
        df.at[i, "id_cliente"] = rng.randint(N_CLIENTES + 50, N_CLIENTES + 200)
    df = pd.concat([df, df.sample(int(N_PEDIDOS * 0.03), random_state=SEED + 5)], ignore_index=True)

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ruta = asegurar_dir(RAW_CSV) / "pedidos.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    LOG.info("Fuente A  pedidos.csv         %6d filas x %2d cols", len(df), df.shape[1])
    return ruta


def fuente_detalle_pedido(
    catalogo: pd.DataFrame, rng: random.Random, solo_vistos: set[int]
) -> tuple[Path, dict[int, float]]:
    """Detalle de pedidos. Devuelve ademas el total CRUDO por pedido.

    Ese total crudo se usa para que ``pagos.csv`` tenga montos coherentes con el
    pedido; si no, la conciliacion pago-vs-pedido del ETL daria falso positivo.

    Los productos de `solo_vistos` quedan EXCLUIDOS a proposito: son los que
    se veran en el log de navegacion pero nunca en una venta, y son lo que
    permite responder "productos vistos pero no comprados".
    """
    # El peso de demanda es el MISMO que se usa para las visitas, asi ventas y
    # navegacion quedan correlacionadas de forma realista.
    cat = catalogo[~catalogo["id_producto"].isin(solo_vistos)].reset_index(drop=True)
    ids_producto = cat["id_producto"].tolist()
    pesos = cat["_demanda"].to_numpy(dtype=float)
    pesos = pesos / pesos.sum()

    precio_por_id = dict(zip(cat["id_producto"], cat["precio"]))
    inicio, fin = pd.Timestamp(FECHA_INICIO), pd.Timestamp(FECHA_FIN)
    filas = []
    suma_por_pedido: dict[int, float] = {}
    for i in range(1, N_DETALLE_PEDIDO + 1):
        fecha = inicio + pd.Timedelta(days=int(rng.random() ** 0.85 * (fin - inicio).days))
        id_producto = int(rng.choices(ids_producto, weights=pesos)[0])
        precio = float(catalogo.loc[catalogo["id_producto"] == id_producto, "precio"].iloc[0])

        # Cantidades invalidas (punto 7)
        cantidad = rng.choices(
            [rng.randint(1, 8), 0, -rng.randint(1, 5), 999, None, "N/A", "dos"],
            weights=[88, 3, 3, 1, 2, 2, 1],
        )[0]

        # Descuentos sucios: vacio, texto, negativo, porcentaje
        estilo = rng.choice(["cero", "monto", "monto", "negativo", "porcentaje", "nulo"])
        if estilo == "cero":
            descuento = 0
        elif estilo == "monto":
            descuento = round(precio * rng.uniform(0.05, 0.25), 2)
        elif estilo == "negativo":
            descuento = -round(precio * 0.05, 2)
        elif estilo == "porcentaje":
            descuento = f"{rng.randint(5, 30)}%"
        else:
            descuento = rng.choice([None, "N/A", ""])

        id_pedido = rng.randint(1, N_PEDIDOS + 1)
        # Total crudo: cantidad solo si es entero positivo; descuento solo si es monto valido.
        cant_ok = cantidad if isinstance(cantidad, int) and 1 <= cantidad <= 100 else 1
        desc_ok = descuento if isinstance(descuento, (int, float)) and descuento >= 0 else 0.0
        suma_por_pedido[id_pedido] = round(
            suma_por_pedido.get(id_pedido, 0.0) + cant_ok * precio - desc_ok, 2
        )

        filas.append(
            {
                "id_detalle": i,
                "id_pedido": id_pedido,
                "id_producto": id_producto,
                "cantidad": cantidad,
                "precio_unitario": precio_como_texto(precio, rng),
                "descuento": descuento,
                # Columnas innecesarias
                "estanteria_almacen": f"P{rng.randint(1, 40)}-F{rng.randint(1, 6)}",
                "serial_interno_caja": f"CJ{rng.randint(10000, 99999)}",
                "estatus_devolucion_bruto": rng.choice(["", None, "sin_devolucion"]),
            }
        )
    df = pd.DataFrame(filas)

    # Orden importante: referencias huerfanas primero, duplicados despues.
    for i in df.sample(int(len(df) * 0.012), random_state=SEED + 8).index:
        df.at[i, "id_pedido"] = rng.randint(N_PEDIDOS + 100, N_PEDIDOS + 300)
    for i in df.sample(int(len(df) * 0.008), random_state=SEED + 9).index:
        df.at[i, "id_producto"] = rng.randint(N_PRODUCTOS + 100, N_PRODUCTOS + 300)
    df = pd.concat([df, df.sample(int(N_DETALLE_PEDIDO * 0.035), random_state=SEED + 7)], ignore_index=True)

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ruta = asegurar_dir(RAW_CSV) / "detalle_pedido.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    LOG.info("Fuente A  detalle_pedido.csv  %6d filas x %2d cols", len(df), df.shape[1])
    return ruta, suma_por_pedido


def fuente_pagos(suma_por_pedido: dict[int, float], rng: random.Random) -> Path:
    inicio, fin = pd.Timestamp(FECHA_INICIO), pd.Timestamp(FECHA_FIN)
    filas = []
    for i in range(1, N_PEDIDOS + 1):
        fecha = inicio + pd.Timedelta(days=int(rng.random() ** 0.85 * (fin - inicio).days))
        # El monto del pago proviene del total real del pedido (con las mismas
        # reglas de imputacion que aplica el ETL), no de un numero aleatorio.
        monto = round(suma_por_pedido.get(i, 0.0) + rng.uniform(-3, 3), 2)
        filas.append(
            {
                "id_pago": i,
                "id_pedido": i,
                "metodo": rng.choice(
                    ["tarjeta_credito", "tarjeta_debito", "transferencia", "oxxo", "mpago", "efectivo"]
                ),
                "monto": precio_como_texto(max(monto, 0.0), rng),
                "fecha_pago": fecha_como_texto(fecha, rng),
                "estado_pago": rng.choice(["aprobado", "APROBADO", "aprobado", "pendiente", "rechazado"]),
            }
        )
    df = pd.DataFrame(filas)
    nulos(df, df.index[: int(N_PEDIDOS * 0.04)], ["estado_pago"], 0.35, rng)
    df = pd.concat([df, df.sample(int(N_PEDIDOS * 0.02), random_state=SEED + 10)], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ruta = asegurar_dir(RAW_CSV) / "pagos.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    LOG.info("Fuente A  pagos.csv           %6d filas x %2d cols", len(df), df.shape[1])
    return ruta


# ==========================================================================
# FUENTE B -> JSON
# ==========================================================================
def fuente_json_productos(documentos: list[dict], rng: random.Random) -> Path:
    """productos_semiestructurados.json -- el corazon de MongoDB."""
    salida = []
    for doc in documentos:
        atributos = dict(doc["_atributos"])
        # Nulos dentro del documento anidado
        if rng.random() < 0.08:
            k = rng.choice(list(atributos))
            atributos[k] = None
        if rng.random() < 0.05:
            atributos["campo_legacy_desconocido"] = rng.choice(["SI", "no", 1, 0])
        salida.append(
            {
                "id_producto": doc["id_producto"],
                "nombre": doc["nombre"] if rng.random() > 0.03 else doc["nombre"].upper(),
                "categoria": categoria_sucia(doc["categoria"], rng) if rng.random() < 0.35 else doc["categoria"],
                "atributos": atributos,
                "etiquetas": rng.sample(
                    ["nuevo", "promocion", "top", "envio-gratis", "gaming", "profesional"],
                    k=rng.randint(0, 3),
                ),
                "disponible": rng.choice([True, True, True, False]),
                "fecha_registro": fecha_como_texto(
                    pd.Timestamp(FECHA_INICIO) + pd.Timedelta(days=rng.randint(0, 700)), rng
                ),
            }
        )
    # Duplicados de documento (mismo id_producto) -> se resuelve con upsert
    salida += rng.sample(salida, k=int(len(salida) * 0.03))

    rng.shuffle(salida)
    ruta = asegurar_dir(RAW_JSON) / "productos_semiestructurados.json"
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Fuente B  productos_semi.json  %6d documentos", len(salida))
    return ruta


def fuente_json_resenas(rng: random.Random) -> Path:
    inicio, fin = pd.Timestamp(FECHA_INICIO), pd.Timestamp(FECHA_FIN)
    nombres_clientes = [f"{n} {a}" for n in NOMBRES[:12] for a in APELLIDOS[:12]]
    salida = []
    for i in range(1, N_RESENAS + 1):
        fecha = inicio + pd.Timedelta(days=int(rng.random() * (fin - inicio).days))
        calificacion = rng.choices(
            [rng.randint(1, 5), 0, 6, "cinco", None, 3], weights=[88, 3, 2, 2, 2, 3]
        )[0]
        salida.append(
            {
                "id_resena": i,
                "id_producto": rng.randint(1, N_PRODUCTOS + 1),
                "cliente": {
                    "id": rng.randint(1, N_CLIENTES + 1),
                    "nombre": rng.choice(nombres_clientes),
                },
                "calificacion": calificacion,
                "comentario": rng.choice(
                    [
                        "Excelente producto",
                        "Cumple con lo esperado",
                        "buen producto pero tardo en llegar",
                        "EXCELENTE PRODUCTO",
                        "No me convino",
                        "vale la pena",
                        "recomendado",
                        "Malo",
                        "Super recomendado",
                    ]
                ),
                "fecha": fecha.strftime("%Y-%m-%d"),
                "verificada": rng.choice([True, False, "Si", "No"]),
            }
        )
    salida += rng.sample(salida, k=int(N_RESENAS * 0.025))
    rng.shuffle(salida)
    ruta = asegurar_dir(RAW_JSON) / "resenas.json"
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Fuente B  resenas.json         %6d documentos", len(salida))
    return ruta


def construir_peso_visualizacion(
    catalogo: pd.DataFrame, rng: random.Random
) -> tuple[list[int], np.ndarray, dict[int, str], set[int]]:
    """Define cuantas visitas recibe cada producto.

    La visita NO es uniforme: parte de la misma latente de demanda que genera
    las ventas, pero con ruido propio (un producto puede ser muy popular y no
    venderse porque cuesta mucho, o al reves).

    Devuelve (ids, pesos_de_seleccion, rol, solo_vistos) donde "rol" documenta
    los casos que la Parte V debe poder responder:
      - atractivo_no_convertidor: muchas visitas, casi ninguna venta
      - poco_visto_mucho_vendido: pocas visitas, muchas ventas
      - visto_nunca_vendido:      aparece en el catalogo y se visita, pero
                                  ningun detalle_pedido lo referencia
      - normal
    """
    cat = catalogo.reset_index(drop=True)
    demanda = cat["_demanda"].to_numpy(dtype=float)

    # Exponente cercano a 1 -> la visita sigue a la demanda (y por lo tanto a las
    # ventas) de verdad. El ruido multiplicativo es acotado [0.55, 1.75] para no
    # borrar la relacion, y el piso de 0.06 evita que la cola de productos poco
    # demandados se quede sin ninguna visita (si no, quedan 200+ productos con
    # cero visitas y la correlacion se vuelve imposible de estimar).
    base = demanda**0.95
    ruido = np.array([rng.uniform(0.55, 1.75) for _ in range(len(cat))])
    visitas = base * ruido + 0.06

    n = len(cat)
    ids = cat["id_producto"].tolist()
    posicion = {id_p: i for i, id_p in enumerate(ids)}
    rol: dict[int, str] = {i: "normal" for i in ids}

    # --- Caso A: muchas visitas y pocas ventas (pregunta 4 del punto 23) ---
    # Productos de demanda BAJA-MEDIA a los que se les fija un nivel de visitas
    # del percentil 96. Es nivel ABSOLUTO (no un multiplicador): asi quedan
    # genuinamente entre los mas vistos del catalogo, que es lo que pide la
    # pregunta, y al ser solo 15 de 607 no invierten la correlacion global.
    n_trampa = 15
    nivel_alto = float(np.percentile(visitas, 96))
    umbral_bajo = np.percentile(demanda, 40)
    for i in np.argsort(demanda):
        i = int(i)
        if rol[ids[i]] != "normal" or demanda[i] > umbral_bajo:
            continue
        rol[ids[i]] = "atractivo_no_convertidor"
        visitas[i] = max(visitas[i] * 5.0, nivel_alto)
        if sum(1 for v in rol.values() if v == "atractivo_no_convertidor") >= n_trampa:
            break

    # --- Caso B: pocas visitas y muchas ventas (pregunta 5 del punto 23) ---
    # Productos de demanda ALTA a los que se les recorta la visita a un tercio.
    umbral_alto = np.percentile(demanda, 75)
    for i in np.argsort(-demanda):
        i = int(i)
        if rol[ids[i]] != "normal" or demanda[i] < umbral_alto:
            continue
        rol[ids[i]] = "poco_visto_mucho_vendido"
        visitas[i] *= 0.30
        if sum(1 for v in rol.values() if v == "poco_visto_mucho_vendido") >= n_trampa:
            break

    # --- Caso C: visto y nunca vendido ---
    # Productos que el log de navegacion registra pero que el generador de
    # detalle_pedido excluye deliberadamente de sus muestreos.
    solo_vistos: set[int] = set()
    for id_p in ids[-12:]:
        rol[id_p] = "visto_nunca_vendido"
        solo_vistos.add(id_p)
        visitas[posicion[id_p]] = max(visitas[posicion[id_p]], 12.0)

    pesos = visitas / visitas.sum()

    # Autoverificacion: la Parte V exige correlacion entre navegacion y ventas.
    # Como las ventas se muestrean con `demanda`, la correlacion visitas~demanda
    # es un proxy de visitas~ventas. Se registra para detectar regresiones.
    corr = float(np.corrcoef(visitas, demanda)[0, 1])
    if corr < 0.30:
        raise AssertionError(
            f"visitas~demanda = {corr:.3f}; el perfil de navegacion perdio la "
            "correlacion con las ventas. Revisar los multiplicadores de trampa."
        )
    LOG.info(
        f"    correlacion visitas~demanda = {corr:+.3f} (proxy de visitas~ventas)"
    )

    return ids, pesos, rol, solo_vistos


def _minutos_antes(fecha: str, minutos: int) -> str:
    """Desplaza una fecha hacia atras conservando su formato original.

    El 18% de los eventos lleva la fecha en un formato de texto "sucio"
    ("14 de junio de 2026") que a proposito no es parseable de forma
    uniforme. Cuando no se puede restar el intervalo se devuelve el texto
    tal cual: es preferible un carrito con la misma fecha en formato sucio
    (que el ETL tiene que resolver igual) que un crash.
    """
    try:
        return (pd.Timestamp(fecha) - pd.Timedelta(minutes=minutos)).strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return fecha


def fuente_json_actividad(
    catalogo: pd.DataFrame, rng: random.Random, solo_vistos: set[int]
) -> Path:
    """actividad_usuario.json -- eventos de navegacion.

    Los productos de `solo_vistos` se garantizan en el log aunque ningun
    detalle_pedido los mencione: son los que hacen posible responder
    "productos vistos pero no comprados".
    """
    inicio, fin = pd.Timestamp(FECHA_INICIO), pd.Timestamp(FECHA_FIN)
    ids, pesos, _rol, _solo = construir_peso_visualizacion(catalogo, rng)

    salida = []
    for _ in range(N_ACTIVIDAD):
        producto = int(rng.choices(ids, weights=pesos)[0])
        fecha = inicio + pd.Timedelta(
            days=int(rng.random() * (fin - inicio).days),
            seconds=int(rng.random() * 86_400),
        )
        doc = {
            "usuario": rng.randint(1, N_CLIENTES + 1),
            "fecha": fecha.strftime("%Y-%m-%dT%H:%M:%S"),
            "evento": rng.choice(EVENTOS),
            "producto": producto,
            "dispositivo": rng.choice(DISPOSITIVOS),
            "ubicacion": ciudad_sucia(rng.choice(list(CIUDADES)), rng),
            "duracion_seg": rng.randint(2, 900),
        }
        # ~18% de los eventos llegan con formato distinto -> normalizar
        if rng.random() < 0.18:
            doc["fecha"] = fecha_como_texto(fecha.normalize(), rng)
        salida.append(doc)

    # Garantia: cada producto "solo visto" aparece al menos una vez.
    for p in solo_vistos:
        if not any(d["producto"] == p for d in salida):
            fecha = inicio + pd.Timedelta(days=int(rng.random() * (fin - inicio).days))
            salida.append(
                {
                    "usuario": rng.randint(1, N_CLIENTES + 1),
                    "fecha": fecha.strftime("%Y-%m-%dT%H:%M:%S"),
                    "evento": "producto_visto",
                    "producto": p,
                    "dispositivo": rng.choice(DISPOSITIVOS),
                    "ubicacion": ciudad_sucia(rng.choice(list(CIUDADES)), rng),
                    "duracion_seg": rng.randint(30, 600),
                }
            )

    # Encadenar el embudo. Los eventos se sortean de forma independiente, asi
    # que puede haber una compra sin que ese usuario haya agregado el producto
    # al carrito: imposible en la realidad y, sobre todo, inutil para medir una
    # conversion. Se inserta el carrito que falta unos minutos antes de la
    # compra. No se tocan las visualizaciones, de modo que los pesos de
    # navegacion y la correlacion con la venta quedan intactos.
    con_carrito = {
        (d["usuario"], d["producto"])
        for d in salida if d["evento"] == "producto_en_carrito"
    }
    faltantes = [
        d for d in salida
        if d["evento"] == "producto_comprado"
        and (d["usuario"], d["producto"]) not in con_carrito
    ]
    for d in faltantes:
        con_carrito.add((d["usuario"], d["producto"]))
        salida.append(
            {
                **d,
                "fecha": _minutos_antes(d["fecha"], rng.randint(1, 45)),
                "evento": "producto_en_carrito",
                "duracion_seg": rng.randint(5, 120),
            }
        )
    if faltantes:
        LOG.info("           embudo encadenado   %6d carritos insertados antes de comprar",
                 len(faltantes))

    salida += rng.sample(salida, k=int(N_ACTIVIDAD * 0.03))
    rng.shuffle(salida)
    ruta = asegurar_dir(RAW_JSON) / "actividad_usuario.json"
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Fuente B  actividad.json      %6d documentos  (%d solo-vistos garantizados)",
             len(salida), len(solo_vistos))
    return ruta


# ==========================================================================
# FUENTE C -> Google Sheets (.xlsx)
# ==========================================================================
def fuente_hojas(catalogo: pd.DataFrame, rng: random.Random) -> Path:
    asegurar_dir(RAW_SHEETS)

    # --- sucursales ---
    # N_SUCURSALES > len(CIUDADES): se cicla la lista de ciudades.
    ciudades_canonicas = list(CIUDADES)
    sucursales = pd.DataFrame(
        {
            "id_sucursal": range(1, N_SUCURSALES + 1),
            "ciudad_canonica": [
                ciudades_canonicas[i % len(ciudades_canonicas)] for i in range(N_SUCURSALES)
            ],
            "fecha_apertura": [
                fecha_como_texto(pd.Timestamp(FECHA_INICIO) - pd.Timedelta(days=rng.randint(0, 2000)), rng)
                for _ in range(N_SUCURSALES)
            ],
            "metros_cuadrados": [rng.randint(80, 4500) for _ in range(N_SUCURSALES)],
        }
    )
    sucursales["nombre"] = [
        f"Sucursal NovaCommerce {c} {i + 1}"
        for i, c in enumerate(sucursales["ciudad_canonica"])
    ]
    sucursales["ciudad"] = [ciudad_sucia(c, rng) for c in sucursales["ciudad_canonica"]]
    sucursales["region"] = [rng.choice(["Sureste", "Centro", "Occidente", "Norte"]) for _ in range(N_SUCURSALES)]
    sucursales.drop(columns=["ciudad_canonica"]).to_excel(RAW_SHEETS / "sucursales.xlsx", index=False)

    # --- proveedores ---
    proveedores = pd.DataFrame(
        {
            "id_proveedor": range(1, N_PROVEEDORES + 1),
            "nombre": [
                f"Distribuidora {n} S.A." for n in NOMBRES[:N_PROVEEDORES]
            ],
            "rubro": [rng.choice(list(RUBROS_PROVEEDOR.values())) for _ in range(N_PROVEEDORES)],
            "pais": rng.choice(["México", "China", "USA", "Corea del Sur", "Alemania"]),
            "contacto_email": [
                f"ventas.proveedor{i}@logisticaindustrial.mx" for i in range(1, N_PROVEEDORES + 1)
            ],
            "dias_entrega_promedio": [rng.randint(3, 45) for _ in range(N_PROVEEDORES)],
            "activo": [rng.choice(["si", "no", "SI", "No"]) for _ in range(N_PROVEEDORES)],
        }
    )
    proveedores.to_excel(RAW_SHEETS / "proveedores.xlsx", index=False)

    # --- promociones ---
    promociones = pd.DataFrame(
        {
            "id_promocion": range(1, N_PROMOCIONES + 1),
            "nombre": [
                rng.choice(
                    ["Verano", "Navidad", "Back to School", "Black Friday", "Dia del Padre",
                     "Hot Sale", "Cyber Monday", "Aniversario NovaCommerce"]
                )
                for _ in range(N_PROMOCIONES)
            ],
            "descuento_pct": [rng.randint(5, 50) for _ in range(N_PROMOCIONES)],
            "fecha_inicio": [
                fecha_como_texto(pd.Timestamp(FECHA_INICIO) + pd.Timedelta(days=rng.randint(0, 900)), rng)
                for _ in range(N_PROMOCIONES)
            ],
            "fecha_fin": [
                fecha_como_texto(pd.Timestamp(FECHA_INICIO) + pd.Timedelta(days=rng.randint(0, 900)), rng)
                for _ in range(N_PROMOCIONES)
            ],
            "categorias": [", ".join(rng.sample(list(CATEGORIAS), k=rng.randint(1, 3))) for _ in range(N_PROMOCIONES)],
        }
    )
    promociones.to_excel(RAW_SHEETS / "promociones.xlsx", index=False)

    # --- objetivos de venta (targets) ---
    objetivos = pd.DataFrame(
        {
            "anio": [2024, 2024, 2024, 2025, 2025, 2025, 2026, 2026, 2026],
            "mes": [1, 7, 12, 1, 7, 12, 1, 7, 9],
            "categoria": [rng.choice(list(CATEGORIAS)) for _ in range(9)],
            "meta_ingresos": [round(rng.uniform(800_000, 4_500_000), 2) for _ in range(9)],
            "meta_unidades": [rng.randint(120, 900) for _ in range(9)],
        }
    )
    objetivos.to_excel(RAW_SHEETS / "objetivos_venta.xlsx", index=False)

    for f in ["sucursales.xlsx", "proveedores.xlsx", "promociones.xlsx", "objetivos_venta.xlsx"]:
        df = pd.read_excel(RAW_SHEETS / f)
        LOG.info("Fuente C  %-20s %6d filas x %2d cols", f, len(df), df.shape[1])
    return RAW_SHEETS


# ==========================================================================
def main() -> dict[str, Path]:
    LOG.info(titulo("PARTE I - GENERACION DE LAS 3 FUENTES CRUDAS (con errores intencionales)"))
    rng = random.Random(SEED)
    np.random.seed(SEED)

    LOG.info("\nConstruyendo catalogo maestro de productos...")
    catalogo = construir_catalogo(rng)
    documentos = construir_atributos(catalogo, random.Random(SEED + 99))

    # El perfil de navegacion se define ANTES que el detalle_pedido, porque es
    # el que decide que productos quedan "vistos pero nunca vendidos".
    ids_vis, pesos_vis, rol_vis, solo_vistos = construir_peso_visualizacion(
        catalogo, random.Random(SEED + 7)
    )
    LOG.info("Perfil de navegacion: %d productos 'vistos nunca vendidos', "
             "%d attracting-but-not-converting, %d low-visibility-high-sales",
             sum(1 for v in rol_vis.values() if v == "visto_nunca_vendido"),
             sum(1 for v in rol_vis.values() if v == "atractivo_no_convertidor"),
             sum(1 for v in rol_vis.values() if v == "poco_visto_mucho_vendido"))

    detalle_path, suma_por_pedido = fuente_detalle_pedido(catalogo, rng, solo_vistos)

    rutas = {
        "clientes": fuente_clientes(rng),
        "productos": fuente_productos(catalogo, rng),
        "pedidos": fuente_pedidos(rng),
        "detalle_pedido": detalle_path,
        "pagos": fuente_pagos(suma_por_pedido, rng),
        "productos_semi": fuente_json_productos(documentos, rng),
        "resenas": fuente_json_resenas(rng),
        "actividad": fuente_json_actividad(catalogo, random.Random(SEED + 7), solo_vistos),
        "hojas": fuente_hojas(catalogo, rng),
    }

    # El catalogo maestro se guarda como artefacto de referencia del pipeline
    # (lo usan la integracion y las graficas para leer precios limpios).
    ruta_catalogo = asegurar_dir(LOGS) / "catalogo_maestro.csv"
    catalogo.drop(columns=["_familia", "_sub", "_demanda"]).to_csv(
        ruta_catalogo, index=False, encoding="utf-8"
    )

    # Etiqueta de rol por producto: la usa la Parte V para verificar que el
    # analisis de "vistos pero no comprados" encuentra los casos que el
    # generador planto a proposito.
    pd.DataFrame(
        {
            "id_producto": list(rol_vis.keys()),
            "rol_generado": list(rol_vis.values()),
            "peso_visualizacion": [float(p) for p in pesos_vis],
        }
    ).to_csv(LOGS / "perfil_visualizacion.csv", index=False, encoding="utf-8")

    LOG.info("\nFuentes generadas:")
    for k, v in rutas.items():
        LOG.info("   %-16s -> %s", k, v)
    return rutas


if __name__ == "__main__":
    main()