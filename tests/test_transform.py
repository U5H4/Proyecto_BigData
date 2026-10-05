"""Tests de las funciones de limpieza mas delicadas.

Ejecutar:  .\\.venv\\Scripts\\python.exe -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from etl_transform import (  # noqa: E402
    _norm,
    a_bool,
    a_entero,
    a_float,
    construir_lookup,
    limpiar_numero,
    normalizar_categoria,
    normalizar_ciudad,
)


# ==========================================================================
# T06 - limpieza de precios. El caso de miles con coma es el mas peligroso:
# "$44,347" son 44347 pesos, NO 44.347 pesos.
# ==========================================================================
@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("1234.56", 1234.56),
        ("$1,234.56", 1234.56),
        ("$1,234", 1234.0),
        ("$44,347", 44347.0),
        ("44,347.00", 44347.0),
        ("1,234,567", 1234567.0),
        ("1.234.567", 1234567.0),
        ("$68,000", 68000.0),
        ("1234,56", 1234.56),
        ("44347,56", 44347.56),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("  1234.56  ", 1234.56),
        ("1234.56 MXN", 1234.56),
        ("1234.56 usd", 1234.56),
        ("-250.00", -250.0),
        ("0.19", 0.19),
    ],
)
def test_limpiar_numero_acepta_formatos_validos(crudo, esperado):
    resultado = limpiar_numero(crudo)
    assert resultado == pytest.approx(esperado), f"{crudo!r} -> {resultado!r}"


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        # Regresion: un grupo unico de 3 decimales es DECIMAL, no miles.
        # Tratar "0.334" como miles daba 334.0 y reventaba los margenes brutos.
        ("0.334", 0.334),
        ("0.1803", 0.1803),
        ("1.234", 1.234),
        ("0.5", 0.5),
        ("44.347", 44.347),
        # Dos o mas grupos si son inequivocamente miles.
        ("1.234.567", 1234567.0),
    ],
)
def test_limpiar_numero_no_confunde_decimal_con_miles(crudo, esperado):
    resultado = limpiar_numero(crudo)
    assert resultado == pytest.approx(esperado), f"{crudo!r} -> {resultado!r}"


def test_margen_bruto_sobrevive_al_parseo():
    """Los margenes (0.18-0.42, 3-4 decimales) no deben multiplicarse x1000."""
    crudos = pd.Series(["0.334", "0.1803", "0.42", "0.227", "N/A", "NULL"])
    resultado = a_float(crudos)
    assert list(resultado.dropna()) == pytest.approx([0.334, 0.1803, 0.42, 0.227])
    assert resultado.isna().sum() == 2


@pytest.mark.parametrize(
    "crudo",
    ["N/A", "n/a", "NULL", "null", "-", "", "   ", None, np.nan,
     "consultar", "sin precio", "#VALOR!", "#N/A", "dos", "15%", "abc"],
)
def test_limpiar_numero_rechaza_no_numericos(crudo):
    assert np.isnan(limpiar_numero(crudo)), f"{crudo!r} no deberia convertirse"


def test_miles_con_coma_no_se_confunde_con_decimal():
    """Regresion: '$44,347' debe valer 44347 y no 44.347."""
    assert limpiar_numero("$44,347") == pytest.approx(44347.0)
    # Y un decimal con coma sigue siendo decimal
    assert limpiar_numero("44347,56") == pytest.approx(44347.56)
    # Un numero de 4+ digitos nunca debe "encogerse" 1000 veces
    for miles in [1234, 9999, 44347, 68000, 123456]:
        assert limpiar_numero(f"${miles:,}") == float(miles)


# ==========================================================================
# T08 - normalizacion de ciudades y categorias
# ==========================================================================
@pytest.mark.parametrize(
    "sucio,esperado",
    [
        ("Veracruz", "Veracruz"),
        ("VERACRUZ", "Veracruz"),
        ("veracruz", "Veracruz"),
        ("Ver.", "Veracruz"),
        ("Veracruz City", "Veracruz"),
        ("  Veracruz  ", "Veracruz"),
        ("CDMX", "Ciudad de Mexico"),
        ("Mexico D.F.", "Ciudad de Mexico"),
        ("  Mexico D.F. ", "Ciudad de Mexico"),
        ("Querétaro", "Queretaro"),
        ("Qro.", "Queretaro"),
        ("MÉRIDA", "Merida"),
        ("CANCÚN", "Cancun"),
        ("GDL", "Guadalajara"),
        ("PUE", "Puebla"),
    ],
)
def test_normalizar_ciudad(sucio, esperado):
    assert normalizar_ciudad(pd.Series([sucio]))[0].iloc[0] == esperado


@pytest.mark.parametrize(
    "sucio,esperado",
    [
        ("Computadoras", "Computadoras"),
        ("computadoras", "Computadoras"),
        ("COMPUTADORAS", "Computadoras"),
        ("Computadoras ", "Computadoras"),
        ("PC", "Computadoras"),
        ("Cómputo", "Computadoras"),
        ("Celulares", "Smartphones"),
        ("Smart Phone", "Smartphones"),
        ("Audífonos", "Audio"),
        ("Headphones", "Audio"),
        ("PANTALLAS", "Monitores"),
        ("Networking", "Redes"),
    ],
)
def test_normalizar_categoria(sucio, esperado):
    assert normalizar_categoria(pd.Series([sucio]))[0].iloc[0] == esperado


def test_lookup_es_inversible_y_sin_ambiguedades():
    """Dos claves canonicas no pueden(mapear a la misma variante)."""
    from config import CATEGORIAS

    lookup = construir_lookup(CATEGORIAS)
    inverso: dict[str, set[str]] = {}
    for variante, canonica in lookup.items():
        inverso.setdefault(variante, set()).add(canonica)
    colisiones = {k: v for k, v in inverso.items() if len(v) > 1}
    assert not colisiones, f"variante ambigua: {colisiones}"


# ==========================================================================
# T04 - conversion de tipos
# ==========================================================================
@pytest.mark.parametrize(
    "crudo,esperado",
    [("1", 1), (" 42 ", 42), (7.0, 7), ("-3", -3), ("0012", 12)],
)
def test_a_entero(crudo, esperado):
    assert a_entero(pd.Series([crudo])).iloc[0] == esperado


@pytest.mark.parametrize("crudo", ["N/A", "dos", "", None, "1.5", "abc", np.nan])
def test_a_entero_rechaza_no_enteros(crudo):
    assert pd.isna(a_entero(pd.Series([crudo])).iloc[0])


@pytest.mark.parametrize(
    "crudo,esperado",
    [("true", True), ("TRUE", True), ("Si", True), ("sí", True), ("1", True),
     ("false", False), ("No", False), ("0", False)],
)
def test_a_bool(crudo, esperado):
    assert bool(a_bool(pd.Series([crudo])).iloc[0]) is esperado


# ==========================================================================
# _norm
# ==========================================================================
@pytest.mark.parametrize(
    "crudo,esperado",
    [("Época", "epoca"), ("  A  B ", "a b"), ("Querétaro", "queretaro")],
)
def test_norm(crudo, esperado):
    assert _norm(crudo) == esperado


def test_norm_tolera_none_y_nan():
    assert _norm(None) == ""
    assert _norm(np.nan) == ""