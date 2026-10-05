"""Utilidades compartidas: logging, log de calidad de datos y formateo."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import LOGS, REPORTS


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
def setup_logging(nombre: str = "pipeline") -> logging.Logger:
    """Configura logging a consola + archivo logs/pipeline.log."""
    LOGS.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(nombre)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt_consola = logging.Formatter("%(levelname)-7s | %(message)s")
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(fmt_consola)
    logger.addHandler(consola)

    fmt_archivo = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    archivo = logging.FileHandler(LOGS / "pipeline.log", encoding="utf-8")
    archivo.setFormatter(fmt_archivo)
    logger.addHandler(archivo)

    return logger


LOG = setup_logging()


# --------------------------------------------------------------------------
# Log de calidad: evidencia auditable de cada transformacion obligatoria
# --------------------------------------------------------------------------
@dataclass
class RegistroCalidad:
    """Una fila del reporte de calidad de datos."""

    orden_ejecucion: int
    paso: int
    transformacion: str
    tabla: str
    filas_antes: int
    filas_despues: int
    registros_afectados: int
    detalle: str
    regla: str = ""


@dataclass
class CalidadTracker:
    """Acumula los registros de cada una de las 10 transformaciones."""

    registros: list[RegistroCalidad] = field(default_factory=list)
    _contador: int = 0

    def registrar(
        self,
        paso: int,
        transformacion: str,
        tabla: str,
        filas_antes: int,
        filas_despues: int,
        afectados: int,
        detalle: str,
        regla: str = "",
    ) -> None:
        self._contador += 1
        self.registros.append(
            RegistroCalidad(
                orden_ejecucion=self._contador,
                paso=paso,
                transformacion=transformacion,
                tabla=tabla,
                filas_antes=filas_antes,
                filas_despues=filas_despues,
                registros_afectados=afectados,
                detalle=detalle,
                regla=regla,
            )
        )
        LOG.info(
            "  #%-2d [T%02d] %-34s %-15s %6d -> %6d (%+d)  %s",
            self._contador,
            paso,
            transformacion,
            tabla,
            filas_antes,
            filas_despues,
            filas_despues - filas_antes,
            detalle,
        )

    def a_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.registros])

    def guardar(self, ruta: Path | None = None) -> Path:
        ruta = ruta or (REPORTS / "calidad_transformaciones.csv")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        df = self.a_dataframe()
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        return ruta


# --------------------------------------------------------------------------
# Formateo
# --------------------------------------------------------------------------
def peso_ajeno(valor) -> str:
    return str(valor) if pd.notna(valor) else "N/A"


def money(valor: float) -> str:
    """$1,234,567.89 -> formato con separador de miles."""
    if pd.isna(valor):
        return "N/A"
    return f"${valor:,.2f}"


def numero(valor: float, dec: int = 0) -> str:
    if pd.isna(valor):
        return "N/A"
    return f"{valor:,.{dec}f}"


def titulo(texto: str, ancho: int = 78) -> str:
    return f"\n{'=' * ancho}\n{texto}\n{'=' * ancho}"


def subtitulo(texto: str, ancho: int = 78) -> str:
    return f"\n{texto}\n{'-' * ancho}"


def tabla(df: pd.DataFrame, decimales: int = 2) -> str:
    """Imprime un DataFrame como tabla legible en consola."""
    if df.empty:
        return "  (sin datos)"
    copia = df.copy()
    for col in copia.columns:
        if pd.api.types.is_float_dtype(copia[col]):
            copia[col] = copia[col].map(lambda v: "" if pd.isna(v) else f"{v:,.{decimales}f}")
    ancho = {}
    for col in copia.columns:
        ancho[col] = max(
            len(str(col)),
            copia[col].astype(str).map(len).max() if len(copia) else 0,
        )
    lineas = ["  " + " | ".join(str(c).ljust(ancho[c]) for c in copia.columns)]
    lineas.append("  " + "-+-".join("-" * ancho[c] for c in copia.columns))
    for _, fila in copia.iterrows():
        lineas.append(
            "  " + " | ".join(str(fila[c]).ljust(ancho[c]) for c in copia.columns)
        )
    return "\n".join(lineas)


def asegurar_dir(ruta: Path) -> Path:
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
