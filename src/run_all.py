"""Orquestador del pipeline completo.

Ejecuta las etapas en orden y para en la primera que falle. Un pipeline que
sigue adelante despues de un error produce datasets a medio escribir y un
informe que miente; aqui cada etapa es una transaccion: o deja sus artefactos
completos, o el proceso sale con codigo 1.

    python src/run_all.py                 # pipeline completo
    python src/run_all.py --listar        # ver etapas
    python src/run_all.py --sin-generar   # reutiliza data/raw ya generado
    python src/run_all.py --solo analisis graficos
    python src/run_all.py --con-tests     # ademas corre la suite de pytest
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils import LOG, tabla, titulo  # noqa: E402


@dataclass
class Etapa:
    clave: str
    nombre: str
    fn: Callable[[], object]
    obligatoria: bool = True


def etapa_generar() -> object:
    import generate_sources
    return generate_sources.main()


def etapa_etl() -> object:
    """Extraer -> transformar -> cargar. Se invoca por funciones y no por
    `subprocess` para que el traceback apunte a la linea real del error."""
    from etl_extract import extraer
    from etl_load import cargar
    from etl_transform import transformar
    datos, tracker = transformar(extraer())
    rutas = cargar(datos)
    tracker.guardar()
    return rutas


def etapa_integracion() -> object:
    import integration
    return integration.main()


def etapa_analisis() -> object:
    import analysis
    return analysis.main()


def etapa_graficos() -> object:
    import viz
    return viz.main()


def etapa_tests() -> object:
    """Suite de pytest sobre `tests/`. Se lanza como subproceso para que el
    codigo de salida de pytest sea el codigo de salida de la etapa."""
    raiz = SRC.parent
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=raiz, check=False,
    ).returncode


ETAPAS: list[Etapa] = [
    Etapa("generar", "Generar fuentes crudas sucias", etapa_generar),
    Etapa("etl", "ETL: extraer, transformar, cargar", etapa_etl),
    Etapa("integracion", "Integracion SQL + NoSQL", etapa_integracion),
    Etapa("analisis", "Analisis de negocio", etapa_analisis),
    Etapa("graficos", "Graficos del reporte", etapa_graficos),
    Etapa("tests", "Suite de pruebas", etapa_tests, obligatoria=False),
]


def ejecutar(claves: list[str]) -> int:
    elegidas = [e for e in ETAPAS if e.clave in claves]
    if not elegidas:
        LOG.error("Ninguna etapa valida. Disponibles: %s",
                  ", ".join(e.clave for e in ETAPAS))
        return 2

    print(titulo("PIPELINE COMPLETO - NovaCommerce"))
    LOG.info("  Etapas: %s", " -> ".join(e.clave for e in elegidas))

    resultados = []
    for i, etapa in enumerate(elegidas, start=1):
        LOG.info("")
        LOG.info("=" * 78)
        LOG.info("  ETAPA %d/%d  %s", i, len(elegidas), etapa.nombre)
        LOG.info("=" * 78)
        t0 = time.perf_counter()
        try:
            salida = etapa.fn()
        except Exception as exc:  # noqa: BLE001 - aqui el fallo si es el resultado
            segundos = time.perf_counter() - t0
            LOG.error("  FALLO en la etapa '%s' tras %.1f s", etapa.clave, segundos)
            LOG.error("  %s: %s", type(exc).__name__, exc)
            import traceback
            traceback.print_exc()
            resultados.append({"etapa": etapa.clave, "estado": "FALLO", "segundos": round(segundos, 1)})
            _resumen(resultados)
            return 1
        segundos = time.perf_counter() - t0
        estado = "OK"
        if isinstance(salida, int) and salida != 0:
            estado = "FALLO"
        resultados.append({"etapa": etapa.clave, "estado": estado, "segundos": round(segundos, 1)})
        if estado == "FALLO":
            LOG.error("  La etapa '%s' devolvio codigo %s", etapa.clave, salida)
            _resumen(resultados)
            return 1
        LOG.info("  Etapa '%s' completada en %.1f s", etapa.clave, segundos)

    _resumen(resultados)
    LOG.info("")
    LOG.info("  PIPELINE COMPLETO: %d etapas OK", len(elegidas))
    return 0


def _resumen(resultados: list[dict]) -> None:
    import pandas as pd
    print("")
    print(titulo("Resumen del pipeline"))
    print(tabla(pd.DataFrame(resultados)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline ETL + integracion + analisis + graficos.",
    )
    parser.add_argument("--listar", action="store_true", help="lista las etapas y sale")
    parser.add_argument("--solo", nargs="+", metavar="ETAPA",
                        help="ejecuta solo esas etapas, en el orden del pipeline")
    parser.add_argument("--sin-generar", action="store_true",
                        help="no regenera data/raw (reutiliza lo que ya existe)")
    parser.add_argument("--con-tests", action="store_true",
                        help="incluye la suite de pytest como etapa final")
    args = parser.parse_args()

    # Las etapas opcionales no entran por defecto: `tests` solo con
    # --con-tests, porque duplica el tiempo del pipeline y no cambia ningun
    # artefacto de `data/`.
    obligatorias = [e.clave for e in ETAPAS if e.obligatoria]
    opcionales = [e.clave for e in ETAPAS if not e.obligatoria]
    claves = list(obligatorias)
    if args.listar:
        import pandas as pd
        print(titulo("Etapas disponibles"))
        print(tabla(pd.DataFrame([
            {"clave": e.clave, "etapa": e.nombre,
             "obligatoria": "si" if e.obligatoria else "opcional"}
            for e in ETAPAS
        ])))
        return 0

    if args.solo:
        desconocidas = [c for c in args.solo if c not in obligatorias + opcionales]
        if desconocidas:
            LOG.error("Etapas desconocidas: %s", ", ".join(desconocidas))
            return 2
        # Se respeta el orden del pipeline, no el del command line.
        claves = [c for c in [e.clave for e in ETAPAS] if c in args.solo]
    else:
        if args.sin_generar:
            claves = [c for c in claves if c != "generar"]
        if args.con_tests:
            claves += [c for c in opcionales if c not in claves]

    return ejecutar(claves)


if __name__ == "__main__":
    raise SystemExit(main())
