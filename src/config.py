"""Configuracion central del pipeline ETL + Integracion + Analisis.

Empresa ficticia: NovaCommerce S.A. de C.V.
Todo es reproducible: la semilla (SEED) fija los datos sinteticos.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_CSV = RAW / "csv"
RAW_JSON = RAW / "json"
RAW_SHEETS = RAW / "sheets"
PROCESSED = DATA / "processed"
REPORTS = DATA / "reports"
FIGURES = DATA / "figures"
LOGS = ROOT / "logs"

ALL_DIRS = [RAW_CSV, RAW_JSON, RAW_SHEETS, PROCESSED, REPORTS, FIGURES, LOGS]

# --------------------------------------------------------------------------
# Reproducibilidad
# --------------------------------------------------------------------------
SEED = 20260904

# --------------------------------------------------------------------------
# Cantidades minimas exigidas (punto 4 del enunciado)
# --------------------------------------------------------------------------
MIN_CLIENTES = 1_000
MIN_PRODUCTOS = 500
MIN_RESENAS = 2_000
MIN_ACTIVIDAD = 1_000
MIN_DETALLE_PEDIDO = 1_000
MIN_PEDIDOS = 2_000

# Se generan por encima del minimo porque el ETL descarta registros:
# duplicados, llaves no numericas, fechas ilegibles, huerfanos de FK y
# calibraciones fuera de escala. Si se generara exactamente el minimo, el
# dataset limpio quedaria POR DEBAJO del minimo que pide el enunciado.
# Estos valores estan calibrados para que, tras las 10 transformaciones,
# el dataset final siga cumpliendo todos los minimos con holgura.
N_CLIENTES = 2_000
N_PRODUCTOS = 620
N_PEDIDOS = 3_600
N_DETALLE_PEDIDO = 4_600
N_RESENAS = 3_000
N_ACTIVIDAD = 4_200
N_SUCURSALES = 12
N_PROVEEDORES = 10
N_PROMOCIONES = 14

# Rango de fechas del negocio (tendale Historico)
FECHA_INICIO = "2024-01-01"
FECHA_FIN = "2026-09-30"

# --------------------------------------------------------------------------
# Catalogo de ciudades: clave canonica -> variantes "sucias" que aparecen
# en las fuentes (punto 7: "ciudades escritas de distintas maneras").
# --------------------------------------------------------------------------
CIUDADES: dict[str, list[str]] = {
    "Veracruz": ["Veracruz", "VERACRUZ", "veracruz", "Ver.", "Veracruz City", "  Veracruz  "],
    "Ciudad de Mexico": ["Ciudad de Mexico", "CDMX", "Mexico D.F.", "MEXICO DF", "cdmx", " Mexico D.F. "],
    "Guadalajara": ["Guadalajara", "GDL", "guadalajara", "Guad.", "GUADALAJARA"],
    "Monterrey": ["Monterrey", "MTY", "monterrey", "Monterrey NL"],
    "Puebla": ["Puebla", "PUE", "puebla", "Puebla de Zaragoza"],
    "Queretaro": ["Queretaro", "QUERÉTARO", "queretaro", "Qro.", " querétaro "],
    "Cancun": ["Cancun", "CANCÚN", "cancun", "Cancún"],
    "Merida": ["Merida", "MÉRIDA", "merida", "Mérida", "MERIDA"],
    "Tijuana": ["Tijuana", "TIJUANA", "tijuana"],
    "Leon": ["Leon", "LEÓN", "leon", "León Gto"],
}

# --------------------------------------------------------------------------
# Catalogo de categorias: clave canonica -> variantes sucias.
# "Unificacion de categorias" (transformacion 8).
# --------------------------------------------------------------------------
CATEGORIAS: dict[str, list[str]] = {
    "Computadoras": ["Computadoras", "computadoras", "COMPUTADORAS", "Computadoras ", "PC", "Cómputo", "computacion"],
    "Smartphones": ["Smartphones", "smartphones", "SMARTPHONES", "Celulares", "Telefonos", "Smart Phone", "smart phone"],
    "Audio": ["Audio", "audio", "AUDIO", "Audifonos", "Audífonos", "Headphones", "Audio "],
    "Monitores": ["Monitores", "monitores", "Monitor", "PANTALLAS", "Pantallas", "monitores"],
    "Accesorios": ["Accesorios", "accesorios", "ACCESORIOS", "Accesorios y Perifericos", "Perifericos", "accesorios "],
    "Redes": ["Redes", "redes", "REDES", "Networking", "Redes y Conectividad", "redes "],
}

# --------------------------------------------------------------------------
# Estados de pedido (para el WHERE de las consultas SQL del equipo)
# --------------------------------------------------------------------------
ESTADOS_PEDIDO = ["completado", "completado", "completado", "enviado", "pendiente", "cancelado"]
METODOS_PAGO = ["tarjeta_credito", "tarjeta_debito", "transferencia", "oxxo", "mpago", "efectivo"]
TIPO_USUARIO = ["Web", "Movil", "Tablet"]
DISPOSITIVOS = ["Android", "Android", "iOS", "iOS", "Windows", "macOS"]
EVENTOS = [
    "producto_visto",
    "producto_visto",
    "producto_visto",
    "producto_en_carrito",
    "busqueda_realizada",
    "inicio_sesion",
    "favorito_agregado",
    "producto_comprado",
]
CANALES_VENTA = ["web", "app_movil", "tienda_fisica"]

# --------------------------------------------------------------------------
# Plantillas de producto por categoria.
# {marca} y {modelo} se sustituyen para obtener 500 productos unicos.
# ----------------------------------------------------------------------------
# ATRIBUTOS_VARIABLES es el insight clave: cada categoria expone un conjunto
# de atributos distinto -> justifica MongoDB (documentos heterogeneos) frente a
# PostgreSQL (tabla puente producto_atributo o JSONB).
# --------------------------------------------------------------------------
PLANTILLAS_PRODUCTO: dict[str, list[str]] = {
    "Computadoras": [
        "Laptop {marca} {modelo}",
        "Desktop {marca} {modelo}",
        "Workstation {marca} {modelo}",
        "Mini PC {marca} {modelo}",
        "All-in-One {marca} {modelo}",
    ],
    "Smartphones": [
        "Smartphone {marca} {modelo}",
        "Tablet {marca} {modelo}",
        "Smartphone {marca} {modelo} Pro",
        "Foldable {marca} {modelo}",
        "Smartphone {marca} {modelo} Lite",
    ],
    "Audio": [
        "Audifonos {marca} {modelo}",
        "Bocina Bluetooth {marca} {modelo}",
        "Auriculares Gaming {marca} {modelo}",
        "Barra de Sonido {marca} {modelo}",
        "Microfono {marca} {modelo}",
    ],
    "Monitores": [
        "Monitor {marca} {modelo}",
        "Monitor Gamer {marca} {modelo}",
        "Monitor Ultrawide {marca} {modelo}",
        "Monitor 4K {marca} {modelo}",
        "Monitor Portatil {marca} {modelo}",
    ],
    "Accesorios": [
        "Teclado Mecanico {marca} {modelo}",
        "Mouse {marca} {modelo}",
        "Mousepad {marca} {modelo}",
        "Webcam {marca} {modelo}",
        "Hub USB-C {marca} {modelo}",
    ],
    "Redes": [
        "Router {marca} {modelo}",
        "Switch {marca} {modelo}",
        "Access Point {marca} {modelo}",
        "Adaptador WiFi {marca} {modelo}",
        "Cable de Red {marca} {modelo}",
    ],
}

# Atributos variables por categoria -> documento semiestructurado de MongoDB.
# Cada familia tiene claves propias; dentro de una familia hay sub-variantes
# (gamer vs oficina) para que un mismo esquema fijo de columnas sea insuficiente.
ATRIBUTOS_VARIABLES: dict[str, list[dict[str, object]]] = {
    "Computadoras": [
        {"procesador": ["Intel Core i5", "Intel Core i7", "AMD Ryzen 5", "AMD Ryzen 7", "Intel Core i9"],
         "ram_gb": [8, 16, 32, 64],
         "almacenamiento": ["512 GB SSD", "1 TB SSD", "2 TB SSD", "1 TB HDD"],
         "gpu": ["RTX 3050", "RTX 4060", "RTX 4070", "Intel Iris Xe", "Sin GPU dedicada"]},
        {"procesador": ["Intel Core i3", "AMD Ryzen 3"],
         "ram_gb": [4, 8],
         "almacenamiento": ["256 GB SSD", "512 GB SSD"],
         "sistema_operativo": ["Windows 11 Home", "Windows 11 Pro", "Ubuntu 24.04"],
         "pantalla_pulgadas": [14, 15.6]},
    ],
    "Smartphones": [
        {"camara_mp": [50, 64, 108, 200],
         "bateria_mah": [4000, 5000, 6000],
         "pantalla_pulgadas": [6.1, 6.7, 6.8],
         "almacenamiento_gb": [128, 256, 512]},
        {"camara_mp": [12, 48],
         "bateria_mah": [3500, 4500],
         "conectividad": ["5G", "4G LTE"],
         "resistencia_agua": ["IP68", "IP54"]},
    ],
    "Audio": [
        {"tipo": ["Over-ear", "In-ear", "On-ear"],
         "conexion": ["Bluetooth 5.3", "Cable 3.5mm", "USB-C", "Inalambrico"],
         "bateria_horas": [8, 20, 30, 60],
         "microfono": [True, False]},
        {"potencia_w": [10, 20, 40, 60],
         "canales": ["2.0", "2.1", "5.1"],
         "resistencia_agua": ["IPX4", "IP67"]},
    ],
    "Monitores": [
        {"resolucion": ["1920x1080", "2560x1440", "3840x2160"],
         "panel": ["IPS", "VA", "TN", "OLED"],
         "tasa_refresco_hz": [60, 75, 144, 165, 240],
         "pulgadas": [21.5, 24, 27, 32, 34]},
        {"resolucion": ["3440x1440"],
         "curvatura": ["Ultrawide 21:9", "Super Ultrawide 32:9"],
         "hz_ajustable": ["OverClock"]},
    ],
    "Accesorios": [
        {"teclas": ["Mecanicas", "De membrana", "Ozon"],
         "layout": ["60%", "65%", "75%", "TKL", "Full Size"],
         "iluminacion": ["RGB", "Blanco", "Sin iluminacion"],
         "conexion": ["USB-C", "Wireless 2.4GHz", "Bluetooth"]},
        {"dpi": [800, 1600, 3200, 6400],
         "sensor": ["Optico", "Laser"],
         "botones_programables": [4, 6, 8, 12],
         "peso_g": [68, 95, 120]},
    ],
    "Redes": [
        {"puertos": [4, 8, 16, 24],
         "velocidad_mbps": [1000, 2500, 10000],
         "poe": [True, False],
         "administrable": [True, False]},
        {"wifi": ["WiFi 5", "WiFi 6", "WiFi 6E", "WiFi 7"],
         "puertos": [1, 2, 4],
         "banda": ["2.4 GHz", "5 GHz", "Doble banda", "Triple banda"],
         "potencia_dbm": [20, 23, 30]},
    ],
}

MARCAS = [
    "Nova", "Auric", "Kortex", "Vertex", "Lumen", "Zylo", "Orbit",
    "Nimbus", "Quartz", "Helix", "Cobalto", "Delta", "Praxis", "Onyx",
]

# Rubros de proveedor: se cruza con la categoria para dar coherencia.
RUBROS_PROVEEDOR = {
    "Computadoras": "Tecnologia / Cómputo",
    "Smartphones": "Tecnología / Dispositivos móviles",
    "Audio": "Electrónica / Audio",
    "Monitores": "Electrónica / Video",
    "Accesorios": "Accesorios de Cómputo",
    "Redes": "Networking / Telecomunicaciones",
}

# --------------------------------------------------------------------------
# Campos que el enunciado pide eliminar por ser innecesarios (transformacion 9)
# --------------------------------------------------------------------------
COLUMNAS_INNECESARIAS = {
    "clientes": ["telefono_secundario", "fax", "codigo_interno_legacy", "usuario_sistema"],
    "productos": ["costo_fabricacion_interno", "sku_fabricante_obsoleto", "peso_envio_kg_bruto"],
    "pedidos": ["referencia_bancaria", "cupon_descuento_raw", "hora_impresion_ticket"],
    "detalle_pedido": ["estanteria_almacen", "serial_interno_caja", "estatus_devolucion_bruto"],
}

# --------------------------------------------------------------------------
# Conexiones (parte Cloud). Si no hay credenciales, el pipeline usa los
# datasets procesados en modo simulado. Configurar por .env o variables.
# --------------------------------------------------------------------------
def _env(nombre: str, default: str = "") -> str:
    return os.getenv(nombre, default)


PG_CONFIG = {
    "host": _env("PG_HOST", "localhost"),
    "port": int(_env("PG_PORT", "5432")),
    "database": _env("PG_DATABASE", "novacommerce"),
    "user": _env("PG_USER", "postgres"),
    "password": _env("PG_PASSWORD", ""),
}

MONGO_URI = _env("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = _env("MONGO_DB", "novacommerce")

# Alternativa gratuita/academica sugerida en la Parte VI.
MONGO_ATLAS_URI = _env("MONGO_ATLAS_URI", "")
CLOUD_STORAGE_URI = _env("CLOUD_STORAGE_URI", "")  # gs:// o s3://

MODO_SIMULADO = True  # el runner lo cambia a False si detecta credenciales

# --------------------------------------------------------------------------
# Paleta de colores: las 6 categorias comparten paleta en todas las graficas
# para que el reporte se vea coherente.
# --------------------------------------------------------------------------
COLOR_CATEGORIA = {
    "Computadoras": "#4C72B0",
    "Smartphones": "#DD8452",
    "Audio": "#55A868",
    "Monitores": "#C44E52",
    "Accesorios": "#8172B3",
    "Redes": "#937860",
}

COLOR_OK = "#2E7D32"
COLOR_ALERTA = "#C62828"
COLOR_NEUTRO = "#546E7A"
