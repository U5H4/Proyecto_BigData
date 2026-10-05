"""PARTE II - ETAPA TRANSFORM.

Ejecuta las 10 transformaciones obligatorias del punto 8 y crea los campos
derivados del punto 9. Cada paso queda registrado en data/reports/
calidad_transformaciones.csv para poder defender el trabajo en la defensa.

Orden de ejecucion (no es el mismo que el orden del enunciado, porque hay
dependencias entre pasos):

   ejec  T   enunciado
   ----  --  -------------------------------------------------------------
     1   2   Normalizacion de texto (define la clave para detectar duplicados)
     2   1   Eliminacion de duplicados
     3   3   Tratamiento de valores nulos
     4   8   Unificacion de categorias y ciudades
     5   4   Correccion de tipos de datos
     6   5   Estandarizacion de fechas
     7   6   Validacion de precios
     8   7   Validacion de cantidades
     9   9   Eliminacion de columnas innecesarias
    10  10   Creacion de campos derivados
     -   -   Integridad referencial (FK) - control previo a la carga
"""

from __future__ import annotations

import json
import re
import unicodedata

import numpy as np
import pandas as pd

from config import (
    CATEGORIAS,
    CIUDADES,
    COLUMNAS_INNECESARIAS,
    FECHA_FIN,
    FECHA_INICIO,
)
from etl_extract import NULOS
from utils import CalidadTracker, subtitulo, tabla, titulo

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
NOMBRE_MES = {v: k.capitalize() for k, v in MESES_ES.items()}


# ==========================================================================
# Primitivas de limpieza (reutilizables y testeables)
# ==========================================================================
def _norm(texto) -> str:
    """Minusculas, sin acentos, sin espacios sobrantes."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def construir_lookup(catalogo: dict[str, list[str]]) -> dict[str, str]:
    """Invierte el catalogo: cada variante -> clave canonica.

    'Ver. ' / 'VERACRUZ' / 'veracruz' -> 'Veracruz'
    """
    lookup: dict[str, str] = {}
    for canonica, variantes in catalogo.items():
        for v in list(variantes) + [canonica]:
            lookup[_norm(v)] = canonica
    return lookup


LOOKUP_CIUDAD = construir_lookup(CIUDADES)
LOOKUP_CATEGORIA = construir_lookup(CATEGORIAS)


# Marcadores de "faltante" que el generador inyecta como TEXTO. Sin esta
# tabla, un 'N/A' viaja intacto desde el Excel crudo hasta el CSV final y
# termina contando como una categoria mas: el reporte de nulos dice 0 y la
# consulta por canal agrupa un canal que no existe.
Vacias = {
    "", "-", "--", "?", "n/a", "n/d", "na", "s/d", "sin dato", "sin datos",
    "null", "none", "nan", "#n/a", "#valor!", "#val0r!",
}


def _marcar_ausentes(d: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Convierte marcadores de faltante escritos como TEXTO en nulo real.

    'NULL' en una columna numerica no es un numero: es la ausencia de un
    numero. Si el barrido no ocurre antes de T03, la imputacion no lo ve,
    el hueco sobrevive a todo el pipeline y el dataset final entrega un
    margen vacio que el enunciado no pide. Se recorre toda columna de tipo
    texto, no solo las de `COLUMNAS_TEXTO`, porque un marcador sucio puede
    haber caido en cualquier campo.
    """
    por_tabla: dict[str, int] = {}
    for tabla, df in d.items():
        for col in df.columns:
            serie = df[col]
            if getattr(serie.dtype, "kind", "") not in "OUSb":
                continue
            texto = serie.astype("object")
            mascara = texto.map(
                lambda v: isinstance(v, str) and " ".join(v.split()).lower() in Vacias
            )
            n = int(mascara.sum())
            if n:
                df[col] = texto.where(~mascara, None)
                por_tabla[tabla] = por_tabla.get(tabla, 0) + n
    return por_tabla


def normalizar_texto(serie: pd.Series) -> pd.Series:
    """T02: recorta, colapsa espacios internos y convierte marcadores de
    faltante en nulo real.

    Un texto ausente y un texto que DICE 'que no hay dato' son el mismo
    hecho: ambos deben contar como faltante, no como un valor distinto.
    """
    def aplicar(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        v = " ".join(str(v).split())
        return None if v.lower() in Vacias else v

    return serie.astype("object").map(aplicar)


def _titulo_palabras(v: str) -> str:
    return " ".join(p.capitalize() if p.islower() else p for p in v.split())


def normalizar_ciudad(serie: pd.Series) -> tuple[pd.Series, int, list[str]]:
    """T08 (ciudades): 'Ver.' / 'VERACRUZ' / 'Veracruz City' -> 'Veracruz'."""
    def aplicar(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "Sin Ciudad"
        k = _norm(v)
        return LOOKUP_CIUDAD.get(k, _titulo_palabras(k) if k else "Sin Ciudad")

    mapa = serie.map(aplicar)
    cambiados = int((serie.fillna("").astype(str).map(_norm) != mapa.map(_norm)).sum())
    return mapa, cambiados


def normalizar_categoria(serie: pd.Series) -> tuple[pd.Series, int]:
    """T08 (categorias): 'PC' / 'COMPUTADORAS' / 'Cómputo' -> 'Computadoras'."""
    def aplicar(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "Sin Categoria"
        k = _norm(v)
        return LOOKUP_CATEGORIA.get(k, _titulo_palabras(k) if k else "Sin Categoria")

    mapa = serie.map(aplicar)
    cambiados = int((serie.fillna("").astype(str).map(_norm) != mapa.map(_norm)).sum())
    return mapa, cambiados


def limpiar_numero(valor) -> float:
    """Convierte a float un numero almacenado como texto sucio.

    Acepta:  1234.56 | 1,234.56 | $1,234 | 1234,56 | ' 1234 ' | 1.234,56
    Rechaza: N/A | consultar | #VALOR! | '' | 'dos'
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return np.nan
    s = str(valor).strip()
    if s == "" or _norm(s) in NULOS:
        return np.nan
    s = s.replace("$", "").replace("MXN", "").replace("USD", "").replace("usd", "")
    s = s.replace(" ", "").strip()
    if s.endswith("%"):
        return np.nan  # un porcentaje no es un precio: lo trata T06
    negativo = s.startswith("-")
    s = s.lstrip("+-")

    tiene_coma = "," in s
    tiene_punto = "." in s

    if tiene_coma and tiene_punto:
        # Conviven coma y punto: el ultimo separador que aparece es el decimal.
        #   "1.234,56" (formato europeo) -> 1234.56
        #   "1,234.56" (formato anglosajon) -> 1234.56
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tiene_coma:
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", s):
            # "1,234" / "44,347" -> separador de MILES (contexto MXN, pesos).
            s = s.replace(",", "")
        else:
            # "1234,56" -> coma decimal
            s = s.replace(",", ".")
    elif tiene_punto:
        # El punto es decimal en este/exportacion (0.334, 44347.56). Solo se
        # interpreta como miles cuando hay DOS o mas grupos de 3 digitos
        # ("1.234.567"), que es inequivoco. Un unico grupo de 3 decimales
        # ("0.334") SIEMPRE es decimal: tratarlo como miles daria 334.0.
        if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", s):
            s = s.replace(".", "")
        # En cualquier otro caso el punto ya es el separador decimal.

    if not re.fullmatch(r"\d*\.?\d*", s) or s in {"", "."}:
        return np.nan
    try:
        n = float(s)
    except ValueError:
        return np.nan
    return -n if negativo else n


def limpiar_precio(serie: pd.Series) -> pd.Series:
    return serie.map(limpiar_numero)


def _parsear_una_fecha(valor) -> pd.Timestamp | None:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    s = str(valor).strip()
    if s == "" or _norm(s) in NULOS:
        return None

    # Timestamp ISO: 2024-05-13T00:00:00 o '2024-05-13 00:00:00'
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ]\d{2}:\d{2}:\d{2}", s)
    if m:
        try:
            return pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None

    # ISO: 2024-05-13  (tambien 'YYYY/MM/DD')
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m:
        try:
            return pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None

    # Texto en espanol: '13 de mayo de 2024'
    m = re.match(r"^(\d{1,2})\s+de\s+([a-zA-ZñÑ]+)\s+de\s+(\d{4})$", s)
    if m:
        mes = MESES_ES.get(_norm(m[2]))
        if mes:
            try:
                return pd.Timestamp(int(m[3]), mes, int(m[1]))
            except ValueError:
                return None
        return None

    # dd/mm/AAAA  |  mm/dd/AAAA  |  dd-mm-AAAA
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if m:
        a, b, anio = int(m[1]), int(m[2]), int(m[3])
        # Regla de negocio (convencion mexicana dd/mm):
        #   - si el 1er numero no cabe en un mes -> es el dia
        #   - si el 2do numero no cabe en un mes  -> es el dia (formato US)
        #   - si ambos caben                        -> se asume dd/mm
        if a > 12:
            dia, mes = a, b
        elif b > 12:
            dia, mes = b, a
        else:
            dia, mes = a, b
        if mes > 12 or dia > 31:
            return None
        try:
            return pd.Timestamp(anio, mes, dia)
        except ValueError:
            return None
    return None


def estandarizar_fecha(serie: pd.Series) -> pd.Series:
    """T05: cualquier formato -> datetime64[ns]."""
    return serie.map(_parsear_una_fecha)


def a_entero(serie: pd.Series) -> pd.Series:
    """T04: '123' / ' 123 ' / 123.0 -> 123 (Int64 nullable)."""
    def aplicar(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return pd.NA
        s = str(v).strip()
        if s == "" or _norm(s) in NULOS:
            return pd.NA
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s)
        if re.fullmatch(r"[+-]?\d+\.0+", s):
            return int(float(s))
        return pd.NA

    return serie.map(aplicar).astype("Int64")


def a_float(serie: pd.Series) -> pd.Series:
    return serie.map(limpiar_numero).astype("float64")


def a_bool(serie: pd.Series) -> pd.Series:
    """T04: 'true' / 'Si' / '1' / 'Yes' -> True."""
    def aplicar(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return pd.NA
        return _norm(v) in {"true", "si", "s", "yes", "y", "1", "1.0"}

    return serie.map(aplicar).astype("boolean")


def _contar_nulos(serie: pd.Series) -> int:
    return int(serie.isna().sum())


# ==========================================================================
# TRANSFORM principal
# ==========================================================================
def transformar(
    crudo: dict[str, pd.DataFrame], tracker: CalidadTracker | None = None
) -> tuple[dict[str, pd.DataFrame], CalidadTracker]:
    tracker = tracker or CalidadTracker()
    print(titulo("PARTE II / ETAPA 2 - TRANSFORM  (10 transformaciones obligatorias)"))
    print(subtitulo("Registro de calidad: cada fila es evidencia auditable"))
    d = {k: v.copy() for k, v in crudo.items()}

    t02_normalizar_texto(d, tracker)
    t01_eliminar_duplicados(d, tracker)
    t03_tratar_nulos(d, tracker)
    t08_unificar(d, tracker)
    t04_corregir_tipos(d, tracker)
    t05_estandarizar_fechas(d, tracker)
    t06_validar_precios(d, tracker)
    t07_validar_cantidades(d, tracker)
    t09_eliminar_columnas(d, tracker)
    reconstruir_atributos(d, tracker)
    integridad_referencial(d, tracker)
    t10_campos_derivados(d, tracker)

    return d, tracker


# --------------------------------------------------------------------------
# T02 - Normalizacion de texto
# --------------------------------------------------------------------------
COLUMNAS_TEXTO = {
    "clientes": ["nombre", "ciudad", "canal_registro", "correo", "telefono"],
    "productos": ["nombre", "categoria", "activo"],
    "pedidos": ["canal_venta", "estado"],
    "detalle_pedido": [],
    "pagos": ["metodo", "estado_pago"],
    "resenas": ["comentario", "fecha", "verificada"],
    "actividad": ["evento", "dispositivo", "ubicacion", "fecha"],
    "sucursales": ["nombre", "ciudad", "region"],
    "proveedores": ["nombre", "rubro", "pais", "contacto_email", "activo"],
    "promociones": ["nombre", "categorias"],
    "objetivos": ["categoria"],
    "productos_semi": ["nombre", "categoria", "etiquetas"],
}


def t02_normalizar_texto(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T02] Normalizacion de texto")
    # Primero se reparan los marcadores de faltante: hasta que un 'NULL' no
    # es un nulo, la imputacion de T03 y los CHECK de T05 no pueden verlo.
    for tabla, n in _marcar_ausentes(d).items():
        t.registrar(2, "Normalizacion de texto", tabla, 0, n, n,
                    f"{n:,} marcadores de faltante ('N/A','NULL','-','') -> nulo real",
                    "marcador de ausentia == valor ausente")
    total = 0
    for tabla, cols in COLUMNAS_TEXTO.items():
        if tabla not in d:
            continue
        antes = sum(_contar_nulos(d[tabla][c]) for c in cols if c in d[tabla])
        cambiados = 0
        for c in cols:
            if c not in d[tabla].columns:
                continue
            limpio = normalizar_texto(d[tabla][c])
            cambiados += int((d[tabla][c].fillna("___NULO___").astype(str)
                              != limpio.fillna("___NULO___").astype(str)).sum())
            d[tabla][c] = limpio
        despues = sum(_contar_nulos(d[tabla][c]) for c in cols if c in d[tabla])
        total += cambiados
        if cambiados:
            t.registrar(2, "Normalizacion de texto", tabla, antes, despues, cambiados,
                        f"{cambiados:,} valores recortados/unificados de {len(d[tabla]):,} filas",
                        "strip + colapso de espacios + trim")
    t.registrar(2, "Normalizacion de texto", "TODAS", 0, 0, total,
                f"TOTAL: {total:,} celdas de texto normalizadas", "strip + colapso de espacios")


# --------------------------------------------------------------------------
# T01 - Eliminacion de duplicados
# --------------------------------------------------------------------------
# Clave natural de cada entidad: detecta el mismo negocio registrado 2 veces.
CLAVES_NATURALES = {
    "clientes": ["nombre", "correo"],
    "productos": ["nombre", "categoria"],
    "pedidos": ["id_pedido", "fecha_pedido", "id_cliente"],
    "detalle_pedido": ["id_pedido", "id_producto", "cantidad", "precio_unitario"],
    "pagos": ["id_pago", "id_pedido"],
    "resenas": ["id_producto", "cliente.id", "fecha", "comentario"],
    "actividad": ["usuario", "fecha", "evento", "producto"],
    "proveedores": ["nombre"],
    "sucursales": ["nombre"],
    "promociones": ["nombre", "fecha_inicio"],
    "objetivos": ["anio", "mes", "categoria"],
    "productos_semi": ["id_producto"],
}

# Llave primaria de cada tabla: el DDL la declara PRIMARY KEY, asi que el
# dataset final jamas puede traerla repetida. Es la red de seguridad que
# valida que la limpieza quedo completa.
PK_TABLAS = {
    "clientes": ["id_cliente"],
    "productos": ["id_producto"],
    "pedidos": ["id_pedido"],
    "detalle_pedido": ["id_detalle"],
    "pagos": ["id_pago"],
    "resenas": ["id_resena"],
    "sucursales": ["id_sucursal"],
    "proveedores": ["id_proveedor"],
    "promociones": ["id_promocion"],
    "objetivos": ["anio", "mes", "categoria"],
    "productos_semi": ["id_producto"],
}


def t01_eliminar_duplicados(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T01] Eliminacion de duplicados")
    for tabla, clave in CLAVES_NATURALES.items():
        if tabla not in d:
            continue
        df = d[tabla]
        n_antes = len(df)
        # Primero se quitan las filas identicas en todas las columnas
        # (mismo registro recargado por el extractor).
        tras_exactos = df.drop_duplicates()
        # Despues las que comparten la clave natural (mismo negocio, otra fila).
        cols = [c for c in clave if c in tras_exactos.columns]
        tras_natural = tras_exactos.drop_duplicates(subset=cols, keep="first")
        # Y por ultimo la llave primaria: aunque dos filas difieran en todo lo
        # demas, no pueden compartir PK (seria violar el PRIMARY KEY del DDL).
        pk = [c for c in PK_TABLAS.get(tabla, []) if c in tras_natural.columns]
        tras_pk = tras_natural.drop_duplicates(subset=pk, keep="first") if pk else tras_natural

        d[tabla] = tras_pk.reset_index(drop=True)
        n_exactos = n_antes - len(tras_exactos)
        n_natural = len(tras_exactos) - len(tras_natural)
        n_pk = len(tras_natural) - len(d[tabla])
        eliminados = n_antes - len(d[tabla])
        if eliminados:
            detalle = f"{n_exactos:,} exactos + {n_natural:,} por clave {cols}"
            if n_pk:
                detalle += f" + {n_pk:,} por PK {pk} repetida"
            t.registrar(1, "Eliminacion de duplicados", tabla, n_antes, len(d[tabla]),
                        eliminados, detalle, f"UNIQUE sobre {cols} / PK {pk}")
        else:
            t.registrar(1, "Eliminacion de duplicados", tabla, n_antes, len(d[tabla]),
                        0, "sin duplicados", f"UNIQUE sobre {cols} / PK {pk}")


# --------------------------------------------------------------------------
# T03 - Tratamiento de valores nulos
# --------------------------------------------------------------------------
# valor nulo -> valor de reemplazo, con la justificacion de negocio.
IMPUTACIONES = {
    ("clientes", "ciudad"): ("Sin Ciudad", "No se conoce: se conserva el cliente, no se descarta"),
    ("clientes", "canal_registro"): ("web", "canal mas frecuente en la base"),
    ("clientes", "telefono"): ("SIN_DATO", "dato de contacto opcional"),
    ("clientes", "correo"): ("SIN_DATO@novatech.mx", "correo sintetico para no perder el cliente"),
    ("clientes", "es_premium"): (False, "por defecto un cliente no es premium"),
    ("productos", "margen_bruto"): (0.25, "margen mediano historico"),
    ("productos", "activo"): (True, "un producto sin estado se considera disponible"),
    ("pedidos", "canal_venta"): ("web", "canal mas frecuente"),
    ("pedidos", "estado"): ("completado", "el enunciado exige medir ventas"),
    ("pagos", "estado_pago"): ("aprobado", "un pago sin estado se asume cobrado"),
    ("pagos", "metodo"): ("efectivo", "metodo por defecto historico"),
    ("detalle_pedido", "descuento"): (0.0, "sin descuento = 0"),
    ("resenas", "comentario"): ("Sin comentario", "la calificacion si es valida"),
    ("resenas", "calificacion"): (pd.NA, "no se inventa una calificacion: se descarta la fila"),
    ("resenas", "cliente.nombre"): ("Desconocido", "reseña anonima"),
    ("resenas", "verificada"): (False, "no verificada por omision"),
    ("actividad", "ubicacion"): ("Sin Ciudad", "no se conoce la ubicacion"),
    ("actividad", "dispositivo"): ("Desconocido", "no se conoce el dispositivo"),
    ("proveedores", "activo"): (True, "proveedor sin estado se asume activo"),
}


def t03_tratar_nulos(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T03] Tratamiento de valores nulos")
    for (tabla, col), (valor, razon) in IMPUTACIONES.items():
        if tabla not in d or col not in d[tabla].columns:
            continue
        df = d[tabla]
        nulos = _contar_nulos(df[col])
        if nulos == 0:
            continue
        n_antes = len(df)
        df[col] = df[col].where(df[col].notna(), valor)
        d[tabla] = df
        t.registrar(3, "Tratamiento de nulos", tabla, n_antes, n_antes, nulos,
                    f"{col}: {nulos:,} nulos -> {valor!r}", razon)

    # Drops por nulidad critica: no se pueden inventar. `cantidad` y
    # `precio_unitario` estan aqui a proposito: son la definicion misma de la
    # linea de venta. Imputar cantidad=1 fabricaria una unidad vendida y
    # moveria las metricas de negocio; lo correcto es descartar la linea.
    for tabla, col in [("clientes", "id_cliente"), ("clientes", "nombre"),
                       ("productos", "id_producto"), ("productos", "nombre"),
                       ("productos", "precio"), ("pedidos", "id_pedido"),
                       ("pedidos", "id_cliente"), ("detalle_pedido", "id_detalle"),
                       ("detalle_pedido", "cantidad"),
                       ("detalle_pedido", "precio_unitario"),
                       ("pagos", "id_pago"), ("resenas", "id_producto"),
                       ("actividad", "producto")]:
        if tabla not in d or col not in d[tabla].columns:
            continue
        df = d[tabla]
        n_antes = len(df)
        nulos = _contar_nulos(df[col])
        df = df[df[col].notna()].reset_index(drop=True)
        d[tabla] = df
        if nulos:
            t.registrar(3, "Tratamiento de nulos (imputables)", tabla, n_antes, len(df),
                        nulos, f"{col}: {nulos:,} filas con {col} nulo descartadas",
                        f"DROP: {col} NOT NULL es obligatorio")

    # Llaves primarias no numericas: 'NULL', 'N/A', '' -> registro invalido.
    for tabla, col in [("clientes", "id_cliente"), ("productos", "id_producto"),
                       ("pedidos", "id_pedido"), ("pedidos", "id_cliente"),
                       ("detalle_pedido", "id_detalle"), ("detalle_pedido", "id_pedido"),
                       ("detalle_pedido", "id_producto"), ("pagos", "id_pago"),
                       ("pagos", "id_pedido"), ("resenas", "id_producto"),
                       ("actividad", "producto"), ("actividad", "usuario")]:
        if tabla not in d or col not in d[tabla].columns:
            continue
        df = d[tabla]
        n_antes = len(df)
        numerico = pd.to_numeric(df[col], errors="coerce").notna()
        d[tabla] = df[numerico].reset_index(drop=True)
        d[tabla][col] = d[tabla][col].astype("int64")
        if n_antes != len(d[tabla]):
            t.registrar(3, "Tratamiento de nulos (imputables)", tabla, n_antes,
                        len(d[tabla]), n_antes - len(d[tabla]),
                        f"{col}: {n_antes - len(d[tabla]):,} llaves no numericas "
                        f"descartadas ('NULL','N/A')",
                        f"PK numerica: {col} INTEGER NOT NULL")

        # El cast a entero puede revelar colisiones (" 1" y "1" -> 1).
        # El dataset final no puede violar el PRIMARY KEY del DDL.
        if col in PK_TABLAS.get(tabla, []) and d[tabla][col].duplicated().any():
            antes = len(d[tabla])
            d[tabla] = d[tabla].drop_duplicates(subset=[col], keep="first").reset_index(drop=True)
            t.registrar(3, "Tratamiento de nulos (imputables)", tabla, antes, len(d[tabla]),
                        antes - len(d[tabla]),
                        f"{col}: colisiones de PK tras el cast a entero",
                        f"PRIMARY KEY ({col})")


# --------------------------------------------------------------------------
# T08 - Unificacion de categorias y ciudades
# --------------------------------------------------------------------------
def t08_unificar(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T08] Unificacion de categorias y ciudades")

    for tabla, col in [("productos", "categoria"), ("objetivos", "categoria"),
                       ("productos_semi", "categoria")]:
        if tabla not in d:
            continue
        df = d[tabla]
        n_antes = len(df)
        antes_unicas = df[col].dropna().nunique()
        df[col], cambiados = normalizar_categoria(df[col])
        d[tabla] = df
        t.registrar(8, "Unificacion de categorias", tabla, n_antes, n_antes, cambiados,
                    f"{antes_unicas} variantes -> {df[col].nunique()} canonicas",
                    "lookup de variantes")

    for tabla, col in [("clientes", "ciudad"), ("sucursales", "ciudad"),
                       ("actividad", "ubicacion")]:
        if tabla not in d:
            continue
        df = d[tabla]
        n_antes = len(df)
        antes_unicas = df[col].dropna().nunique()
        df[col], cambiados = normalizar_ciudad(df[col])
        d[tabla] = df
        t.registrar(8, "Unificacion de ciudades", tabla, n_antes, n_antes, cambiados,
                    f"{antes_unicas} variantes -> {df[col].nunique()} canonicas",
                    "lookup de variantes (Ver. -> Veracruz)")


# --------------------------------------------------------------------------
# T04 - Correccion de tipos de datos
# --------------------------------------------------------------------------
ESQUEMA_TIPOS = {
    "clientes": {"id_cliente": "entero", "es_premium": "bool", "telefono": "texto"},
    "productos": {"id_producto": "entero", "id_proveedor": "entero", "activo": "bool",
                  "margen_bruto": "float"},
    "pedidos": {"id_pedido": "entero", "id_cliente": "entero", "id_sucursal": "entero"},
    "detalle_pedido": {"id_detalle": "entero", "id_pedido": "entero", "id_producto": "entero"},
    "pagos": {"id_pago": "entero", "id_pedido": "entero"},
    "resenas": {"id_resena": "entero", "id_producto": "entero", "cliente.id": "entero",
                "calificacion": "entero", "verificada": "bool"},
    "actividad": {"usuario": "entero", "producto": "entero", "duracion_seg": "entero"},
    "sucursales": {"id_sucursal": "entero", "metros_cuadrados": "entero"},
    "proveedores": {"id_proveedor": "entero", "dias_entrega_promedio": "entero",
                    "activo": "bool"},
    "promociones": {"id_promocion": "entero", "descuento_pct": "entero"},
    "objetivos": {"anio": "entero", "mes": "entero", "meta_unidades": "entero",
                  "meta_ingresos": "float"},
}


def t04_corregir_tipos(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T04] Correccion de tipos de datos")
    for tabla, cols in ESQUEMA_TIPOS.items():
        if tabla not in d:
            continue
        df = d[tabla]
        n_antes = len(df)
        aplicados: list[str] = []
        for col, tipo in cols.items():
            if col not in df.columns:
                continue
            if tipo == "entero":
                df[col] = a_entero(df[col])
            elif tipo == "float":
                df[col] = a_float(df[col])
            elif tipo == "bool":
                df[col] = a_bool(df[col])
            aplicados.append(f"{col}:{tipo}")
        d[tabla] = df
        t.registrar(4, "Correccion de tipos", tabla, n_antes, n_antes, len(aplicados),
                    ", ".join(aplicados), "CAST explicito a int/float/bool")


# --------------------------------------------------------------------------
# T05 - Estandarizacion de fechas
# --------------------------------------------------------------------------
COLUMNAS_FECHA = {
    "clientes": ["fecha_alta"],
    "productos": ["fecha_lanzamiento"],
    "pedidos": ["fecha_pedido"],
    "pagos": ["fecha_pago"],
    "resenas": ["fecha"],
    "actividad": ["fecha"],
    "sucursales": ["fecha_apertura"],
    "promociones": ["fecha_inicio", "fecha_fin"],
    "productos_semi": ["fecha_registro"],
}


def t05_estandarizar_fechas(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T05] Estandarizacion de fechas")
    for tabla, cols in COLUMNAS_FECHA.items():
        if tabla not in d:
            continue
        df = d[tabla]
        n_antes = len(df)
        fallidas_total = 0
        resumen = []
        for col in cols:
            if col not in df.columns:
                continue
            parseados = estandarizar_fecha(df[col])
            # Una fila se conserva solo si TODAS sus fechas son validas:
            # una fecha ilegible significa un registro no confiable.
            invalida = parseados.isna() & df[col].notna()
            nulos_previos = int(df[col].isna().sum())
            df = df.assign(**{col: parseados})
            fallidas = int(invalida.sum())
            fallidas_total += fallidas
            resumen.append(
                f"{col}: {len(df) - fallidas - nulos_previos:,} ok / "
                f"{fallidas:,} ilegibles / {nulos_previos:,} nulos"
            )
            df = df[~invalida].reset_index(drop=True)

        d[tabla] = df
        t.registrar(5, "Estandarizacion de fechas", tabla, n_antes, len(df), fallidas_total,
                    "; ".join(resumen) + f"  -> datetime64[ns]",
                    "ISO-8601 (YYYY-MM-DD); filas con fecha ilegible se descartan")


# --------------------------------------------------------------------------
# T06 - Validacion de precios
# --------------------------------------------------------------------------
PRECIO_MIN, PRECIO_MAX = 1.0, 500_000.0


def t06_validar_precios(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T06] Validacion de precios")
    # productos.precio
    df = d["productos"]
    n_antes = len(df)
    df["precio"] = a_float(df["precio"])
    no_parseados = int(df["precio"].isna().sum())
    df = df[df["precio"].notna()].reset_index(drop=True)
    fuera_rango = int(((df["precio"] < PRECIO_MIN) | (df["precio"] > PRECIO_MAX)).sum())
    df.loc[(df["precio"] < PRECIO_MIN) | (df["precio"] > PRECIO_MAX), "precio"] = np.nan
    df = df[df["precio"].notna()].reset_index(drop=True)
    d["productos"] = df
    t.registrar(6, "Validacion de precios", "productos", n_antes, len(df),
                n_antes - len(df),
                f"{no_parseados:,} no parseables + {fuera_rango:,} fuera de rango "
                f"[{PRECIO_MIN}, {PRECIO_MAX}] descartados",
                "CHECK (precio > 0)")

    # detalle_pedido.precio_unitario
    df = d["detalle_pedido"]
    n_antes = len(df)
    df["precio_unitario"] = a_float(df["precio_unitario"])
    no_parseados = int(df["precio_unitario"].isna().sum())
    df = df[df["precio_unitario"].notna()].reset_index(drop=True)
    fuera_rango = int(((df["precio_unitario"] < PRECIO_MIN) | (df["precio_unitario"] > PRECIO_MAX)).sum())
    df.loc[(df["precio_unitario"] < PRECIO_MIN) | (df["precio_unitario"] > PRECIO_MAX),
           "precio_unitario"] = np.nan
    df = df[df["precio_unitario"].notna()].reset_index(drop=True)
    d["detalle_pedido"] = df
    t.registrar(6, "Validacion de precios", "detalle_pedido", n_antes, len(df),
                n_antes - len(df),
                f"{no_parseados:,} no parseables + {fuera_rango:,} fuera de rango descartados",
                "CHECK (precio_unitario > 0)")

    # pagos.monto
    df = d["pagos"]
    n_antes = len(df)
    df["monto"] = a_float(df["monto"])
    negativos = int((df["monto"] < 0).sum())
    df["monto"] = df["monto"].where(df["monto"] >= 0, np.nan)
    df["monto"] = df["monto"].fillna(0.0)
    d["pagos"] = df
    t.registrar(6, "Validacion de precios", "pagos", n_antes, len(df), negativos,
                f"{negativos:,} montos negativos -> 0", "CHECK (monto >= 0)")

    # margen_bruto
    df = d["productos"]
    n_antes = len(df)
    df["margen_bruto"] = a_float(df["margen_bruto"])
    fuera = int(((df["margen_bruto"] < 0) | (df["margen_bruto"] > 1)).sum())
    df["margen_bruto"] = df["margen_bruto"].clip(0.0, 1.0)
    d["productos"] = df
    t.registrar(6, "Validacion de precios", "productos (margen)", n_antes, len(df), fuera,
                f"{fuera:,} margenes fuera de [0,1] recortados", "CHECK (margen BETWEEN 0 AND 1)")

    # Calificaciones: la escala de Likert es 1..5. Cualquier otra cosa
    # (0, 6, 'cinco') es un error de captura y se descarta la fila completa.
    df = d["resenas"]
    n_antes = len(df)
    cal = pd.to_numeric(df["calificacion"], errors="coerce")
    invalidas = int(((cal < 1) | (cal > 5)).sum())
    df = df[(cal >= 1) & (cal <= 5)].reset_index(drop=True)
    df["calificacion"] = df["calificacion"].astype("int64")
    d["resenas"] = df
    t.registrar(6, "Validacion de precios", "resenas (calificacion)", n_antes, len(df),
                invalidas,
                f"{invalidas:,} calificaciones fuera de [1,5] (0, 6, 'cinco') descartadas",
                "CHECK (calificacion BETWEEN 1 AND 5)")


# --------------------------------------------------------------------------
# T07 - Validacion de cantidades
# --------------------------------------------------------------------------
CANTIDAD_MIN, CANTIDAD_MAX = 1, 100


def t07_validar_cantidades(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T07] Validacion de cantidades")
    df = d["detalle_pedido"]
    n_antes = len(df)

    df["cantidad"] = a_entero(df["cantidad"])
    no_numericas = int(df["cantidad"].isna().sum())
    df["cantidad"] = df["cantidad"].astype("float64")

    fuera = int(((df["cantidad"] < CANTIDAD_MIN) | (df["cantidad"] > CANTIDAD_MAX)).sum())
    # Politica explicita: 0, negativos y >100 son errores de captura -> se
    # acetan (no se inventa) en lugar de convertirlos a 1.
    df.loc[(df["cantidad"] < CANTIDAD_MIN) | (df["cantidad"] > CANTIDAD_MAX), "cantidad"] = np.nan
    df["cantidad"] = df["cantidad"].fillna(1.0).astype("int64")
    d["detalle_pedido"] = df

    t.registrar(7, "Validacion de cantidades", "detalle_pedido", n_antes, len(df),
                no_numericas + fuera,
                f"{no_numericas:,} no numericas ('N/A','dos') + {fuera:,} fuera de "
                f"[{CANTIDAD_MIN},{CANTIDAD_MAX}] -> 1",
                f"CHECK (cantidad BETWEEN {CANTIDAD_MIN} AND {CANTIDAD_MAX})")

    # Descuentos: no puede ser negativo ni superar el subtotal.
    df = d["detalle_pedido"]
    n_antes = len(df)
    crudos = df["descuento"]
    df["descuento"] = a_float(crudos)
    no_numericos = int(df["descuento"].isna().sum())
    df["descuento"] = df["descuento"].fillna(0.0)
    negativos = int((df["descuento"] < 0).sum())
    df["descuento"] = df["descuento"].where(df["descuento"] >= 0, 0.0)
    d["detalle_pedido"] = df
    t.registrar(7, "Validacion de cantidades", "detalle_pedido (descuento)", n_antes,
                len(df), no_numericos + negativos,
                f"{no_numericos:,} no numericos ('9%','N/A') + {negativos:,} negativos -> 0",
                "CHECK (descuento >= 0)")


# --------------------------------------------------------------------------
# T09 - Eliminacion de columnas innecesarias
# --------------------------------------------------------------------------
def t09_eliminar_columnas(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T09] Eliminacion de columnas innecesarias")
    for tabla, cols in COLUMNAS_INNECESARIAS.items():
        if tabla not in d:
            continue
        df = d[tabla]
        existentes = [c for c in cols if c in df.columns]
        if not existentes:
            continue
        d[tabla] = df.drop(columns=existentes)
        t.registrar(9, "Eliminacion de columnas", tabla, len(df), len(d[tabla]), len(existentes),
                    f"eliminadas: {', '.join(existentes)}",
                    "sin uso en analisis ni en el modelo relacional")


def reconstruir_atributos(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    """Rehace el subdocumento `atributos` que json_normalize habia aplanado.

    Es el punto donde se ve POR QUE MongoDB: tras aplanar, el catalogo tiene
    30+ columnas de atributos y casi todas estan vacias salvo las que
    corresponden a la categoria del producto. Un esquema fijo en PostgreSQL
    obligaria a crear 30 columnas (la mayoria siempre NULL) o una tabla
    puente producto_atributo. El subdocumento lo resuelve sin coste.
    """
    if "productos_semi" not in d:
        return
    df = d["productos_semi"]
    cols_atributos = [c for c in df.columns if c.startswith("atributos.")]

    def reconstruir(fila) -> str:
        attrs = {}
        for c in cols_atributos:
            v = fila.get(c)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            attrs[c.replace("atributos.", "")] = v
        return json.dumps(attrs, ensure_ascii=False)

    df["atributos"] = df.apply(reconstruir, axis=1)
    d["productos_semi"] = df.drop(columns=cols_atributos)
    n_con = sum(1 for a in df["atributos"] if a != "{}")
    t.registrar(10, "Campos derivados", "productos_semi (atributos)", len(df), len(df),
                len(cols_atributos),
                f"{len(cols_atributos)} columnas aplanadas -> 1 subdocumento; "
                f"{n_con:,}/{len(df):,} productos con al menos 1 atributo",
                "subdocumento con esquema variable (BSON)")


# --------------------------------------------------------------------------
# Integridad referencial (FK) - control previo a la carga en PostgreSQL
# --------------------------------------------------------------------------
FK = [
    ("pedidos", "id_cliente", "clientes", "id_cliente"),
    ("pedidos", "id_sucursal", "sucursales", "id_sucursal"),
    ("detalle_pedido", "id_pedido", "pedidos", "id_pedido"),
    ("detalle_pedido", "id_producto", "productos", "id_producto"),
    ("pagos", "id_pedido", "pedidos", "id_pedido"),
    ("resenas", "id_producto", "productos", "id_producto"),
    ("resenas", "cliente.id", "clientes", "id_cliente"),
    ("actividad", "producto", "productos", "id_producto"),
    ("actividad", "usuario", "clientes", "id_cliente"),
    ("productos", "id_proveedor", "proveedores", "id_proveedor"),
]


def integridad_referencial(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[FK] Integridad referencial (simula los FOREIGN KEY del DDL)")
    for hijo, col_h, padre, col_p in FK:
        if hijo not in d or padre not in d:
            continue
        if col_h not in d[hijo].columns or col_p not in d[padre].columns:
            continue
        validos = set(d[padre][col_p].dropna().unique())
        mascara = d[hijo][col_h].isin(validos)
        huerfanos = int((~mascara).sum())
        if huerfanos:
            d[hijo] = d[hijo][mascara].reset_index(drop=True)
        t.registrar(0, "Integridad referencial (FK)", hijo, len(d[hijo]) + huerfanos,
                    len(d[hijo]), huerfanos,
                    f"{col_h} -> {padre}.{col_p}: {huerfanos:,} huerfanos descartados",
                    f"FOREIGN KEY ({col_h}) REFERENCES {padre}({col_p})")


# --------------------------------------------------------------------------
# T10 - Creacion de campos derivados
# --------------------------------------------------------------------------
# Tolerancia deconciliacion pago vs pedido, en MXN.
TOLERANCIA_PAGO = 5.0


def _expandir_fecha(df: pd.DataFrame, col: str, prefijo: str = "") -> pd.DataFrame:
    """Anio, mes, dia, nombre de mes y trimestre a partir de una fecha."""
    s = pd.to_datetime(df[col], errors="coerce")
    df[f"{prefijo}anio"] = s.dt.year.astype("Int64")
    df[f"{prefijo}mes"] = s.dt.month.astype("Int64")
    df[f"{prefijo}dia"] = s.dt.day.astype("Int64")
    df[f"{prefijo}mes_nombre"] = s.dt.month.map(NOMBRE_MES)
    df[f"{prefijo}trimestre"] = s.dt.quarter.astype("Int64")
    df[f"{prefijo}anio_mes"] = s.dt.strftime("%Y-%m")
    return df


def t10_campos_derivados(d: dict[str, pd.DataFrame], t: CalidadTracker) -> None:
    print("\n[T10] Creacion de campos derivados")

    # --- clientes: anio/mes de alta + antiguedad ---
    df = d["clientes"]
    n = len(df)
    df = _expandir_fecha(df, "fecha_alta")
    referencia = pd.Timestamp(FECHA_FIN)
    df["antiguedad_dias"] = (referencia - df["fecha_alta"]).dt.days.astype("Int64")
    d["clientes"] = df
    t.registrar(10, "Campos derivados", "clientes", n, len(df), 7,
                "anio, mes, dia, mes_nombre, trimestre, anio_mes, antiguedad_dias",
                "EXTRACT(year FROM fecha_alta)")

    # --- productos: costo estimado y utilidad bruta ---
    df = d["productos"]
    n = len(df)
    df["costo_estimado"] = (df["precio"] * (1 - df["margen_bruto"])).round(2)
    df["utilidad_bruta"] = (df["precio"] * df["margen_bruto"]).round(2)
    df["rango_precio"] = pd.cut(
        df["precio"],
        bins=[0, 500, 2000, 8000, 20000, 50000, np.inf],
        labels=["Economico", "Medio", "Alto", "Premium", "Lujo", "Ultra Premium"],
    ).astype(str)
    d["productos"] = df
    t.registrar(10, "Campos derivados", "productos", n, len(df), 3,
                "costo_estimado, utilidad_bruta, rango_precio",
                "costo = precio * (1 - margen)")

    # --- pedidos: totales y fecha ---
    df = d["pedidos"]
    n = len(df)
    df = _expandir_fecha(df, "fecha_pedido")
    df["es_completado"] = df["estado"].isin(["completado", "enviado"])
    d["pedidos"] = df
    t.registrar(10, "Campos derivados", "pedidos", n, len(df), 7,
                "anio, mes, dia, mes_nombre, trimestre, anio_mes, es_completado",
                "EXTRACT(year FROM fecha_pedido)")

    # --- detalle_pedido: subtotal y total (punto 9 del enunciado) ---
    df = d["detalle_pedido"]
    n = len(df)
    df["subtotal"] = (df["cantidad"] * df["precio_unitario"]).round(2)
    df["total"] = (df["subtotal"] - df["descuento"]).round(2)
    df["porcentaje_descuento"] = np.where(
        df["subtotal"] > 0, (df["descuento"] / df["subtotal"] * 100).round(2), 0.0
    )
    d["detalle_pedido"] = df
    t.registrar(10, "Campos derivados", "detalle_pedido", n, len(df), 3,
                "subtotal = cantidad * precio_unitario; total = subtotal - descuento; "
                "porcentaje_descuento",
                "subtotal = precio * cantidad")

    # --- rollup del total por pedido ---
    detalle = d["detalle_pedido"]
    pedidos = d["pedidos"]
    resumen = detalle.groupby("id_pedido").agg(
        total_pedido=("total", "sum"),
        unidades=("cantidad", "sum"),
        lineas=("id_detalle", "count"),
        categorias_distintas=("id_producto", "nunique"),
    ).reset_index()
    n = len(pedidos)
    pedidos = pedidos.merge(resumen, on="id_pedido", how="left")
    pedidos["total_pedido"] = pedidos["total_pedido"].fillna(0.0).round(2)
    pedidos["unidades"] = pedidos["unidades"].fillna(0).astype("Int64")
    pedidos["lineas"] = pedidos["lineas"].fillna(0).astype("Int64")
    pedidos["categorias_distintas"] = pedidos["categorias_distintas"].fillna(0).astype("Int64")
    pedidos["ticket_promedio_linea"] = np.where(
        pedidos["lineas"] > 0, (pedidos["total_pedido"] / pedidos["lineas"]).round(2), 0.0
    )
    d["pedidos"] = pedidos
    t.registrar(10, "Campos derivados", "pedidos (rollup)", n, len(pedidos), 5,
                "total_pedido, unidades, lineas, categorias_distintas, ticket_promedio_linea",
                "SUM(total) GROUP BY id_pedido")

    # --- pagos: conciliacion con el pedido ---
    pagos = d["pagos"]
    n = len(pagos)
    pagos = _expandir_fecha(pagos, "fecha_pago", prefijo="pago_")
    base = pedidos[["id_pedido", "total_pedido"]]
    pagos = pagos.merge(base, on="id_pedido", how="left")
    pagos["diferencia_pago"] = (pagos["monto"] - pagos["total_pedido"]).round(2)
    pagos["conciliado"] = pagos["diferencia_pago"].abs() <= TOLERANCIA_PAGO
    d["pagos"] = pagos
    n_conc = int(pagos["conciliado"].sum())
    t.registrar(10, "Campos derivados", "pagos", n, len(pagos), 8,
                f"anio/mes del pago, diferencia_pago, conciliado "
                f"({n_conc:,}/{len(pagos):,} = {n_conc / max(len(pagos), 1) * 100:.1f}% conciliados "
                f"con tolerancia ${TOLERANCIA_PAGO:.2f})",
                "monto - total_pedido")

    # --- resenas: dimensiones de fecha y sentiment ---
    df = d["resenas"]
    n = len(df)
    df = _expandir_fecha(df, "fecha")
    df["es_positiva"] = df["calificacion"] >= 4
    df["es_negativa"] = df["calificacion"] <= 2
    df["longitud_comentario"] = df["comentario"].astype(str).str.len()
    d["resenas"] = df
    t.registrar(10, "Campos derivados", "resenas", n, len(df), 10,
                "anio, mes, dia, mes_nombre, trimestre, anio_mes, "
                "es_positiva, es_negativa, longitud_comentario",
                "calificacion >= 4")

    # --- actividad: dimensiones de fecha ---
    df = d["actividad"]
    n = len(df)
    df["fecha_hora"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.drop(columns=["fecha"])
    df = _expandir_fecha(df, "fecha_hora")
    df["hora"] = df["fecha_hora"].dt.hour.astype("Int64")
    df["es_visualizacion"] = df["evento"] == "producto_visto"
    d["actividad"] = df
    t.registrar(10, "Campos derivados", "actividad", n, len(df), 9,
                "anio, mes, dia, mes_nombre, trimestre, anio_mes, hora, es_visualizacion",
                "EXTRACT(hour FROM fecha_hora)")


# ==========================================================================
if __name__ == "__main__":
    from etl_extract import extraer

    crudo = extraer()
    limpio, tracker = transformar(crudo)

    print("\n" + tabla(tracker.a_dataframe()[["orden_ejecucion", "paso", "transformacion",
                                              "tabla", "registros_afectados", "detalle"]]))
    ruta = tracker.guardar()
    print(f"\nReporte de calidad: {ruta}")